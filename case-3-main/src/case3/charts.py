"""Render LLM HTML charts to PNG via Playwright (offline Chart.js)."""

from __future__ import annotations

import concurrent.futures
import logging
import os
import shutil
import threading
import urllib.parse
from contextvars import copy_context
from pathlib import Path
from typing import Any, Callable, TypeVar

from case3.chart_html import assets_charts_dir, sanitize_chart_html, wrap_chart_page

log = logging.getLogger("case3.charts")

_T = TypeVar("_T")


def _prefer_stable_playwright_browsers() -> None:
    """Prefer real OS browser cache over Cursor sandbox temp (often incomplete → launch fail)."""
    current = os.environ.get("PLAYWRIGHT_BROWSERS_PATH") or ""
    sandboxish = "cursor-sandbox-cache" in current or "/var/folders/" in current
    if current and not sandboxish:
        return
    candidates = [
        Path.home() / "Library" / "Caches" / "ms-playwright",  # macOS
        Path.home() / ".cache" / "ms-playwright",  # Linux
        Path.home() / "AppData" / "Local" / "ms-playwright",  # Windows
    ]
    for c in candidates:
        if c.is_dir() and any(c.glob("chromium*")):
            os.environ["PLAYWRIGHT_BROWSERS_PATH"] = str(c)
            log.info("PLAYWRIGHT_BROWSERS_PATH → %s", c)
            return


_PW_SEM_LOCK = threading.Lock()
_PW_SEM_LIMIT = 0
_PW_SEM: threading.BoundedSemaphore | None = None


def _playwright_semaphore() -> threading.BoundedSemaphore:
    global _PW_SEM_LIMIT, _PW_SEM
    raw = (os.environ.get("CASE3_MAX_PLAYWRIGHT") or "4").strip() or "4"
    try:
        limit = max(1, min(int(raw), 8))
    except ValueError:
        limit = 4
    with _PW_SEM_LOCK:
        if _PW_SEM is None or _PW_SEM_LIMIT != limit:
            _PW_SEM = threading.BoundedSemaphore(limit)
            _PW_SEM_LIMIT = limit
        return _PW_SEM


def _run_sync_playwright(fn: Callable[[], _T]) -> _T:
    """Always run Playwright Sync API in a fresh OS thread with bounded concurrency.

    FastAPI/uvicorn may call us under a running asyncio loop (or from
    ``asyncio.to_thread`` on a worker that still confuses Playwright on
    Windows). A dedicated thread has no running loop → Sync API is safe.
    """
    with _playwright_semaphore():
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            return pool.submit(copy_context().run, fn).result()

_MAX_PNG = 12 * 1024 * 1024
# Single env knob for chart budget (used by generate / parse / pipeline / render).
ENV_MAX_CHARTS = "CASE3_MAX_CHARTS"


def max_charts_from_env() -> int:
    """Only CASE3_MAX_CHARTS controls how many charts may appear."""
    try:
        # Default 2 matches API/UI when .env forgot the knobs (0 still disables).
        return max(0, int(os.environ.get(ENV_MAX_CHARTS, "2") or "2"))
    except ValueError:
        return 2


def chart_timeout_s() -> float:
    try:
        # Win desk 091728 still had CASE3_CHART_TIMEOUT_S=15 → bar/line READY waits
        # burned the whole budget on JS throw. Floor 45s; prefer fixing HTML too.
        return max(45.0, float(os.environ.get("CASE3_CHART_TIMEOUT_S", "45") or "45"))
    except ValueError:
        return 45.0


def file_url_to_path(url: str) -> Path:
    """Convert file:// URL to a filesystem Path (Windows Chromium-safe)."""
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme != "file":
        raise ValueError(f"not a file URL: {url!r}")
    raw = urllib.parse.unquote(parsed.path or "")
    # Windows: urlparse gives /C:/Users/... or /C|/Users/...
    if len(raw) >= 3 and raw[0] == "/" and raw[2] in ":|":
        raw = raw[1:]
        if raw[1] == "|":
            raw = raw[0] + ":" + raw[2:]
    # UNC: file://server/share → netloc set
    if parsed.netloc and parsed.netloc not in ("", "localhost"):
        raw = f"//{parsed.netloc}{raw}"
    return Path(raw)


def paths_equal(a: Path, b: Path) -> bool:
    try:
        return a.resolve() == b.resolve()
    except OSError:
        return os.path.normcase(os.path.normpath(str(a))) == os.path.normcase(
            os.path.normpath(str(b))
        )


def _write_frame(work_dir: Path) -> Path:
    """Write empty frame (fragment injected via DOM to avoid #mount breakout)."""
    work_dir.mkdir(parents=True, exist_ok=True)
    vendor = assets_charts_dir() / "chart.umd.min.js"
    if not vendor.is_file():
        raise RuntimeError(f"missing vendored Chart.js: {vendor}")
    shutil.copy2(vendor, work_dir / "chart.umd.min.js")
    page = wrap_chart_page(fragment="")  # mount left empty
    index = work_dir / "index.html"
    index.write_text(page, encoding="utf-8")
    return index


def is_blank_chart_error(exc: BaseException) -> bool:
    """True when Playwright accepted READY but canvas stayed white (transient flake)."""
    return isinstance(exc, RuntimeError) and "blank chart screenshot" in str(exc)


def _force_chart_paint(page) -> None:  # noqa: ANN001
    """Nudge Chart.js after READY — first paint can lag under Image API / matrix load."""
    page.evaluate(
        """() => {
          try {
            if (window.Chart && Chart.instances) {
              const inst = Chart.instances;
              const list = Array.isArray(inst) ? inst : Object.values(inst);
              for (const c of list) {
                if (c && typeof c.update === 'function') c.update('none');
              }
            }
          } catch (e) { /* ignore */ }
        }"""
    )


def _assert_chart_visible(page) -> None:  # noqa: ANN001
    """Reject blank / empty charts before accepting PNG."""
    stats = page.evaluate(
        """() => {
          const mount = document.getElementById('mount');
          if (!mount) return {ok: false, reason: 'no mount'};
          const canvas = mount.querySelector('canvas');
          if (canvas && canvas.width > 0 && canvas.height > 0) {
            const ctx = canvas.getContext('2d');
            const {width, height} = canvas;
            const data = ctx.getImageData(0, 0, width, height).data;
            let painted = 0;
            for (let i = 0; i < data.length; i += 16) {
              const a = data[i+3];
              if (a < 8) continue;  // ignore fully transparent
              if (data[i] < 250 || data[i+1] < 250 || data[i+2] < 250) painted++;
            }
            return {ok: painted >= 40, reason: 'canvas painted=' + painted, painted};
          }
          const text = (mount.innerText || '').trim();
          if (text.length >= 1) return {ok: true, reason: 'kpi/text'};
          return {ok: false, reason: 'empty mount'};
        }"""
    )
    if not stats or not stats.get("ok"):
        raise RuntimeError(f"blank chart screenshot: {stats}")


def _plotted_series(page) -> list[list[float | None]]:  # noqa: ANN001
    """Numbers Chart.js plotted. One list per dataset."""
    raw = page.evaluate(
        """() => {
          const canvas = document.querySelector('#mount canvas');
          const chart = (window.Chart && canvas && Chart.getChart)
            ? Chart.getChart(canvas) : null;
          if (!chart) return [];
          return chart.data.datasets.map((ds) => (ds.data || []).map((v) => {
            if (v == null) return null;
            if (typeof v === 'object') return (v && 'y' in v) ? Number(v.y) : null;
            const n = Number(v);
            return Number.isFinite(n) ? n : null;
          }));
        }"""
    )
    if not isinstance(raw, list):
        return []
    out: list[list[float | None]] = []
    for row in raw:
        if not isinstance(row, list):
            continue
        points: list[float | None] = []
        for item in row:
            if item is None:
                points.append(None)
            else:
                points.append(float(item))
        out.append(points)
    return out


def _render_chart_in_browser(
    browser: Any,
    html: str,
    dest_png: Path,
    *,
    work_dir: Path,
    timeout_ms: int,
    series_out: list[list[float | None]] | None = None,
) -> None:
    index = _write_frame(work_dir)
    dest_png.parent.mkdir(parents=True, exist_ok=True)
    work_dir = work_dir.resolve()
    index = index.resolve()
    allowed = {
        index.resolve(),
        (work_dir / "chart.umd.min.js").resolve(),
    }
    context = browser.new_context(
        viewport={"width": 1200, "height": 680},
        device_scale_factor=2,
    )
    try:

        def _route(route, request):  # noqa: ANN001
            url = request.url
            if url.startswith("data:"):
                route.continue_()
                return
            if url.startswith("file:"):
                try:
                    resolved = file_url_to_path(url)
                except (ValueError, OSError):
                    route.abort()
                    return
                if any(paths_equal(resolved, a) for a in allowed):
                    route.continue_()
                else:
                    route.abort()
                return
            route.abort()

        context.route("**/*", _route)
        page = context.new_page()
        page.goto(index.as_uri(), wait_until="load", timeout=timeout_ms)
        # Inject via DOM (stray </div> cannot break #mount). Re-exec <script>
        # because browsers do not run scripts inserted with innerHTML.
        page.evaluate(
            """(html) => {
              const mount = document.getElementById('mount');
              window.__CASE3_CHART_READY = false;
              window.__CASE3_CHART_ERROR = null;
              mount.innerHTML = html;
              for (const old of Array.from(mount.querySelectorAll('script'))) {
                const src = old.textContent || '';
                old.remove();
                try {
                  // eval so Chart ctor throws are catchable (replaceWith is not).
                  (0, eval)(src);
                } catch (err) {
                  window.__CASE3_CHART_ERROR = String(err && err.message || err);
                  window.__CASE3_CHART_READY = true;
                }
              }
            }""",
            html,
        )
        page.wait_for_function(
            "() => window.__CASE3_CHART_READY === true",
            timeout=timeout_ms,
        )
        js_err = page.evaluate("() => window.__CASE3_CHART_ERROR")
        if js_err:
            raise RuntimeError(f"chart JS error: {js_err}")
        _force_chart_paint(page)
        # Poll until canvas has ink — READY can still beat first paint.
        # Under matrix load 2.5s was too short (grouped_bar → painted=0).
        deadline = timeout_ms
        step = 50
        last_err: Exception | None = None
        waited = 0
        while waited <= deadline:
            try:
                _assert_chart_visible(page)
                last_err = None
                break
            except RuntimeError as exc:
                last_err = exc
                if waited > 0 and waited % 500 < step:
                    _force_chart_paint(page)
                page.wait_for_timeout(step)
                waited += step
        if last_err is not None:
            raise last_err
        if series_out is not None:
            series_out[:] = _plotted_series(page)
        page.locator("#mount").screenshot(path=str(dest_png), type="png")
    finally:
        context.close()


def _validate_chart_png(dest_png: Path) -> None:
    data = dest_png.read_bytes()
    if len(data) > _MAX_PNG:
        dest_png.unlink(missing_ok=True)
        raise RuntimeError(f"chart png too large: {len(data)} bytes")
    if not data.startswith(b"\x89PNG\r\n\x1a\n"):
        dest_png.unlink(missing_ok=True)
        raise RuntimeError("chart screenshot is not PNG")
    if len(data) < 800:
        dest_png.unlink(missing_ok=True)
        raise RuntimeError(f"chart png suspiciously small: {len(data)} bytes")


def render_chart_png(
    chart: dict[str, Any] | str,
    dest_png: Path,
    *,
    work_dir: Path | None = None,
    series_out: list[list[float | None]] | None = None,
) -> None:
    raw_html = chart if isinstance(chart, str) else str(chart.get("html") or "")
    html = sanitize_chart_html(raw_html)
    dest_png = Path(dest_png)
    if work_dir is None:
        work_dir = dest_png.parent.parent / "chart_work" / dest_png.stem
    timeout_ms = int(chart_timeout_s() * 1000)

    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise RuntimeError(
            "playwright not installed — run: pip install playwright && playwright install chromium"
        ) from exc

    def _render() -> None:
        _prefer_stable_playwright_browsers()
        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=True,
                args=["--disable-dev-shm-usage", "--no-sandbox"],
            )
            try:
                _render_chart_in_browser(
                    browser,
                    html,
                    dest_png,
                    work_dir=work_dir,
                    timeout_ms=timeout_ms,
                    series_out=series_out,
                )
            finally:
                browser.close()

    # One full Chromium relaunch on blank canvas — seen after Image API photo+chart
    # (READY true, painted=0). Second pass almost always paints.
    try:
        _run_sync_playwright(_render)
    except RuntimeError as exc:
        if not is_blank_chart_error(exc):
            raise
        log.warning("blank chart — retrying once with fresh browser: %s", exc)
        _run_sync_playwright(_render)

    _validate_chart_png(dest_png)


_DEFAULT_RENDER_CHART_PNG = render_chart_png


def probe_playwright_chromium(*, deep: bool = False) -> tuple[bool, str | None]:
    """Check Playwright + Chromium availability without cold-launching headless browser by default."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        return False, str(exc)[:200]

    _prefer_stable_playwright_browsers()
    if not deep:
        env_path = os.environ.get("PLAYWRIGHT_BROWSERS_PATH")
        roots = [Path(env_path)] if env_path else []
        roots.extend(
            [
                Path.home() / "Library" / "Caches" / "ms-playwright",
                Path.home() / ".cache" / "ms-playwright",
                Path.home() / "AppData" / "Local" / "ms-playwright",
            ]
        )
        for r in roots:
            if r.is_dir() and any(r.glob("chromium*")):
                return True, None

    try:

        def _probe() -> None:
            with sync_playwright() as p:
                if deep:
                    browser = p.chromium.launch(headless=True)
                    browser.close()
                else:
                    exe = Path(p.chromium.executable_path)
                    if not exe.is_file():
                        raise RuntimeError(f"chromium executable missing: {exe}")

        _run_sync_playwright(_probe)
        return True, None
    except Exception as exc:  # noqa: BLE001
        log.info("playwright check failed: %s", exc)
        return False, str(exc)[:200]


def render_charts_batch(
    items: list[tuple[str, dict[str, Any], Path, Path]],
    *,
    on_progress: Callable[[str], None] | None = None,
    cancel_check: Callable[[], None] | None = None,
) -> dict[str, dict[str, Any]]:
    """Render multiple charts sharing one Chromium browser instance across the batch."""
    from case3.run_cancel import RunCancelled

    status: dict[str, dict[str, Any]] = {}
    if not items:
        return status

    # If a test monkeypatched charts.render_chart_png, honor it per item.
    if render_chart_png is not _DEFAULT_RENDER_CHART_PNG:
        for cid, chart, dest, cdir in items:
            if cancel_check:
                cancel_check()
            if on_progress:
                on_progress(cid)
            try:
                render_chart_png(chart, dest, work_dir=cdir)
                status[cid] = {"ok": True, "path": str(dest), "kind": "chart"}
                log.info("chart ok %s → %s", cid, dest)
            except RunCancelled:
                raise
            except Exception as exc:  # noqa: BLE001
                status[cid] = {"ok": False, "error": str(exc)[:400], "kind": "chart"}
                log.warning("chart failed %s: %s", cid, exc)
                if dest.exists():
                    dest.unlink()
        return status

    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        err = f"playwright not installed — run: pip install playwright && playwright install chromium ({exc})"
        for cid, _chart, dest, _cdir in items:
            if cancel_check:
                cancel_check()
            if on_progress:
                on_progress(cid)
            status[cid] = {"ok": False, "error": err[:400], "kind": "chart"}
        return status

    timeout_ms = int(chart_timeout_s() * 1000)

    def _batch_worker() -> None:
        _prefer_stable_playwright_browsers()
        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=True,
                args=["--disable-dev-shm-usage", "--no-sandbox"],
            )
            try:
                for cid, chart, dest, cdir in items:
                    if cancel_check:
                        cancel_check()
                    if on_progress:
                        on_progress(cid)
                    html = sanitize_chart_html(
                        chart if isinstance(chart, str) else str(chart.get("html") or "")
                    )
                    try:
                        try:
                            _render_chart_in_browser(
                                browser,
                                html,
                                dest,
                                work_dir=cdir,
                                timeout_ms=timeout_ms,
                            )
                        except RuntimeError as exc:
                            if not is_blank_chart_error(exc):
                                raise
                            log.warning(
                                "blank chart %s — retrying once with fresh browser: %s",
                                cid,
                                exc,
                            )
                            try:
                                browser.close()
                            except Exception:  # noqa: BLE001
                                pass
                            browser = p.chromium.launch(
                                headless=True,
                                args=["--disable-dev-shm-usage", "--no-sandbox"],
                            )
                            _render_chart_in_browser(
                                browser,
                                html,
                                dest,
                                work_dir=cdir,
                                timeout_ms=timeout_ms,
                            )
                        _validate_chart_png(dest)
                        status[cid] = {"ok": True, "path": str(dest), "kind": "chart"}
                        log.info("chart ok %s → %s", cid, dest)
                    except RunCancelled:
                        raise
                    except Exception as exc:  # noqa: BLE001 — soft-fail per chart
                        status[cid] = {
                            "ok": False,
                            "error": str(exc)[:400],
                            "kind": "chart",
                        }
                        log.warning("chart failed %s: %s", cid, exc)
                        if dest.exists():
                            dest.unlink()
            finally:
                try:
                    browser.close()
                except Exception:  # noqa: BLE001
                    pass

    _run_sync_playwright(_batch_worker)
    return status


def generate_all_charts(
    charts: list[dict[str, Any]],
    figures_dir: Path,
    *,
    work_root: Path | None = None,
    max_charts: int | None = None,
    on_progress: Callable[[str], None] | None = None,
    cancel_check: Callable[[], None] | None = None,
) -> dict[str, Any]:
    """Render charts into figures_dir/<id>.png. Soft-fail per chart."""
    if cancel_check:
        cancel_check()
    limit = max_charts_from_env() if max_charts is None else max(0, int(max_charts))
    if limit <= 0:
        return {}
    figures_dir.mkdir(parents=True, exist_ok=True)
    root = work_root or (figures_dir.parent / "chart_work")
    items: list[tuple[str, dict[str, Any], Path, Path]] = []
    for chart in charts[:limit]:
        cid = chart["id"]
        dest = figures_dir / f"{cid}.png"
        cdir = root / cid
        items.append((cid, chart, dest, cdir))
    return render_charts_batch(
        items,
        on_progress=on_progress,
        cancel_check=cancel_check,
    )
