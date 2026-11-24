"""Resolve run media (charts / photos / diagrams) for Liber decks."""

from __future__ import annotations

from case3.paths import repo_root

import json
import logging
import os
import re
import shutil
from pathlib import Path
from typing import Any

from case3.chart_style import _PALETTES, normalize_palette_id
from case3.charts import (
    _prefer_stable_playwright_browsers,
    _run_sync_playwright,
    chart_timeout_s,
    file_url_to_path,
    paths_equal,
)

log = logging.getLogger("case3.slides_media")

_MEDIA_ID = re.compile(r"^(cht|fig|usr|dia)_[a-z0-9_]{1,28}$")
_DIAGRAM_FRAME: str | None = None


def is_media_id(mid: str) -> bool:
    return bool(_MEDIA_ID.match(mid or ""))


def _repo_root() -> Path:
    return repo_root()


def _diagram_template() -> str:
    global _DIAGRAM_FRAME
    if _DIAGRAM_FRAME is None:
        path = Path(__file__).resolve().parent / "templates" / "diagram_capture.html"
        _DIAGRAM_FRAME = path.read_text(encoding="utf-8")
    return _DIAGRAM_FRAME


def _mermaid_js_path() -> Path:
    root = _repo_root()
    vendored = root / "assets" / "charts" / "mermaid.min.js"
    if vendored.is_file():
        return vendored
    cand = root / "web" / "node_modules" / "mermaid" / "dist" / "mermaid.min.js"
    if cand.is_file():
        return cand
    raise FileNotFoundError(
        "mermaid.min.js missing — run npm install in web/ "
        f"(expected {vendored} or {cand})"
    )


_NUMBER_RUN = re.compile(r"\d+(?:[.,]\d+)?")


def numbers_from_media_json(fj: dict[str, Any]) -> frozenset[str]:
    """Digit runs from captions + chart ``data:[…]`` (not canvas/CSS junk)."""
    blobs: list[str] = []
    for key in ("charts", "figures", "diagrams"):
        for item in fj.get(key) or []:
            if not isinstance(item, dict):
                continue
            for field in ("caption", "title", "mermaid", "prompt"):
                val = item.get(field)
                if isinstance(val, str) and val.strip():
                    blobs.append(val)
            html = item.get("html")
            if isinstance(html, str) and html.strip():
                # Prefer dataset values / labels over width/height/color hex noise.
                for m in re.finditer(
                    r"data\s*:\s*\[([^\]]+)\]|labels\s*:\s*\[([^\]]+)\]",
                    html,
                    flags=re.IGNORECASE,
                ):
                    chunk = m.group(1) or m.group(2) or ""
                    # Split CSV so ``9410,9370`` is two ints, not one decimal.
                    for part in re.split(r"[,]", chunk):
                        part = part.strip().strip("'\"")
                        if part:
                            blobs.append(part)
                # Captions embedded in tooltip strings
                for m in re.finditer(r"['\"]([^'\"]{0,80}\d[^'\"]{0,80})['\"]", html):
                    s = m.group(1)
                    if "тыс" in s.lower() or "°" in s or "%" in s or "чел" in s.lower():
                        blobs.append(s)
    text = "\n".join(blobs)
    found = set(_NUMBER_RUN.findall(text))
    extra: set[str] = set()
    for n in found:
        extra.add(n.replace(",", "."))
        extra.add(n.replace(".", ","))
    return frozenset(found | extra)


def load_figures_json(out_dir: Path) -> dict[str, Any]:
    fj = Path(out_dir) / "figures.json"
    if not fj.is_file():
        return {}
    try:
        data = json.loads(fj.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def collect_run_media(
    out_dir: Path,
    meta: dict[str, Any] | None = None,
) -> tuple[list[str], list[str], list[str], dict[str, Path], dict[str, dict[str, str]]]:
    """Return chart_ids, figure_ids, diagram_ids, png_by_id, diagram_specs.

    ``png_by_id`` only includes raster files that already exist (cht/fig/usr).
    Diagrams are listed separately until rasterized.
    """
    out_dir = Path(out_dir)
    meta = meta or {}
    fj = load_figures_json(out_dir)
    figs_dir = out_dir / "figures"

    chart_ids: list[str] = []
    figure_ids: list[str] = []
    diagram_ids: list[str] = []
    png_by_id: dict[str, Path] = {}
    diagram_specs: dict[str, dict[str, str]] = {}

    for key, bucket in (
        ("charts_planned", chart_ids),
        ("figures_planned", figure_ids),
        ("diagrams_planned", diagram_ids),
    ):
        for x in meta.get(key) or []:
            s = str(x).strip()
            if s and s not in bucket:
                bucket.append(s)

    for ch in fj.get("charts") or []:
        if not isinstance(ch, dict):
            continue
        cid = str(ch.get("id") or "").strip()
        if cid and cid not in chart_ids:
            chart_ids.append(cid)

    for fig in fj.get("figures") or []:
        if not isinstance(fig, dict):
            continue
        fid = str(fig.get("id") or "").strip()
        if fid and fid not in figure_ids:
            figure_ids.append(fid)

    for dia in fj.get("diagrams") or []:
        if not isinstance(dia, dict):
            continue
        did = str(dia.get("id") or "").strip()
        if not did:
            continue
        if did not in diagram_ids:
            diagram_ids.append(did)
        mermaid = str(dia.get("mermaid") or "").strip()
        title = str(dia.get("title") or dia.get("caption") or "").strip()
        if mermaid:
            diagram_specs[did] = {"mermaid": mermaid, "title": title}

    if figs_dir.is_dir():
        for png in figs_dir.glob("*.png"):
            stem = png.stem
            if not is_media_id(stem):
                continue
            png_by_id[stem] = png
            if stem.startswith("cht_") and stem not in chart_ids:
                chart_ids.append(stem)
            elif stem.startswith(("fig_", "usr_")) and stem not in figure_ids:
                figure_ids.append(stem)

    # Only keep ids that have PNG (charts/figures) — diagrams stay for render
    chart_ids = [c for c in chart_ids if c in png_by_id]
    figure_ids = [f for f in figure_ids if f in png_by_id]
    diagram_ids = [d for d in diagram_ids if d in diagram_specs]

    return chart_ids, figure_ids, diagram_ids, png_by_id, diagram_specs


def render_diagram_html(
    *,
    mermaid: str,
    palette: str = "atelier",
    primary: str | None = None,
    accent: str | None = None,
    theme_pack: str | None = None,
) -> str:
    """Populate all diagram_capture.html theme placeholders consistently."""
    from case3.diagram_style import ensure_role_classdefs, role_colors_for_palette

    style_key = (theme_pack or palette or "atelier").strip().lower()
    role_colors = role_colors_for_palette(style_key)
    dark = style_key in ("signal", "voltage", "botanical", "ink")

    if not (primary and accent):
        primary = role_colors["start"]["stroke"]
        accent = role_colors["decision"]["stroke"]

    node_fill = role_colors["process"]["fill"]
    text_color = role_colors["process"]["color"]
    start_fill = role_colors["start"]["fill"]
    start_stroke = role_colors["start"]["stroke"]
    decision_fill = role_colors["decision"]["fill"]
    decision_stroke = role_colors["decision"]["stroke"]
    ok_fill = role_colors["ok"]["fill"]
    ok_stroke = role_colors["ok"]["stroke"]
    warn_fill = role_colors["warn"]["fill"]
    warn_stroke = role_colors["warn"]["stroke"]
    data_fill = role_colors["data"]["fill"]
    data_stroke = role_colors["data"]["stroke"]
    line_color = "#A89D91" if style_key == "signal" else (
        "#94A3B8" if dark else role_colors["process"]["stroke"]
    )
    cluster_fill = "#241F1C" if style_key == "signal" else (
        "#1E242B" if dark else "#F4F6F8"
    )
    cluster_border = "#4A3F37" if style_key == "signal" else (
        "#3A4452" if dark else "#CBD5E1"
    )
    label_bg = "#241F1C" if style_key == "signal" else ("#1E242B" if dark else "#FFFFFF")

    styled_mermaid = ensure_role_classdefs(
        mermaid, style_key, overwrite=bool(theme_pack)
    )
    body = (
        (styled_mermaid or "")
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )
    return (
        _diagram_template()
        .replace("{{MERMAID}}", body)
        .replace("{{PRIMARY}}", primary)
        .replace("{{ACCENT}}", accent)
        .replace("{{NODE_FILL}}", node_fill)
        .replace("{{TEXT_COLOR}}", text_color)
        .replace("{{LINE_COLOR}}", line_color)
        .replace("{{CLUSTER_FILL}}", cluster_fill)
        .replace("{{CLUSTER_BORDER}}", cluster_border)
        .replace("{{LABEL_BG}}", label_bg)
        .replace("{{START_FILL}}", start_fill)
        .replace("{{START_STROKE}}", start_stroke)
        .replace("{{DECISION_FILL}}", decision_fill)
        .replace("{{DECISION_STROKE}}", decision_stroke)
        .replace("{{OK_FILL}}", ok_fill)
        .replace("{{OK_STROKE}}", ok_stroke)
        .replace("{{WARN_FILL}}", warn_fill)
        .replace("{{WARN_STROKE}}", warn_stroke)
        .replace("{{DATA_FILL}}", data_fill)
        .replace("{{DATA_STROKE}}", data_stroke)
    )


def render_mermaid_png(
    *,
    mermaid: str,
    dest: Path,
    palette: str = "atelier",
    work_dir: Path | None = None,
    primary: str | None = None,
    accent: str | None = None,
    theme_pack: str | None = None,
) -> Path:
    """Rasterize Mermaid to PNG via Playwright + local mermaid.min.js."""
    dest = Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    work = Path(work_dir) if work_dir else dest.parent / f".mmd_{dest.stem}"
    work.mkdir(parents=True, exist_ok=True)

    js_src = _mermaid_js_path()
    js_dest = work / "mermaid.min.js"
    if not js_dest.is_file() or js_dest.stat().st_size != js_src.stat().st_size:
        shutil.copy2(js_src, js_dest)

    html = render_diagram_html(
        mermaid=mermaid,
        palette=palette,
        primary=primary,
        accent=accent,
        theme_pack=theme_pack,
    )
    index = (work / "index.html").resolve()
    index.write_text(html, encoding="utf-8")
    js_dest = js_dest.resolve()

    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise RuntimeError("playwright not installed") from exc

    timeout_ms = int(chart_timeout_s() * 1000)
    allowed = {index, js_dest}

    def _render() -> None:
        bp = os.environ.get("PLAYWRIGHT_BROWSERS_PATH")
        if bp and not Path(bp).exists():
            os.environ.pop("PLAYWRIGHT_BROWSERS_PATH", None)
        _prefer_stable_playwright_browsers()
        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=True,
                args=["--disable-dev-shm-usage", "--no-sandbox"],
            )
            try:
                context = browser.new_context(
                    viewport={"width": 2400, "height": 1400},
                    device_scale_factor=2,
                )

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
                page.wait_for_selector(
                    "#diagram svg", state="attached", timeout=timeout_ms
                )
                is_err = page.evaluate(
                    """() => {
                  const svg = document.querySelector('#diagram svg');
                  if (!svg) return true;
                  if (svg.getAttribute('aria-roledescription') === 'error') return true;
                  if (svg.querySelector('.error-icon, .error-text')) return true;
                  const txt = svg.textContent || '';
                  return txt.includes('Syntax error in text');
                }"""
                )
                if is_err:
                    raise RuntimeError("mermaid syntax error rendered")
                # Unhide + scale Mermaid; capture SVG tightly (not empty 16:9).
                page.evaluate(
                    """() => {
                  const svg = document.querySelector('#diagram svg');
                  if (!svg) return;
                  svg.style.visibility = 'visible';
                  svg.style.opacity = '1';
                  svg.style.display = 'block';
                  svg.removeAttribute('hidden');
                  const vb = svg.viewBox && svg.viewBox.baseVal;
                  const vw = (vb && vb.width) || 400;
                  const vh = (vb && vb.height) || 400;
                  // Match slide frame (~1700×900): oversized PNGs shrink fonts on contain.
                  const maxW = 1700, maxH = 900;
                  const scale = Math.min(maxW / vw, maxH / vh);
                  const w = Math.max(640, vw * scale);
                  const h = Math.max(420, vh * scale);
                  svg.setAttribute('width', String(w));
                  svg.setAttribute('height', String(h));
                  svg.style.width = w + 'px';
                  svg.style.height = h + 'px';
                  svg.style.maxWidth = 'none';
                  svg.style.maxHeight = 'none';
                  svg.style.background = 'transparent';
                  const box = svg.getBBox();
                  svg.querySelectorAll('rect').forEach((r) => {
                    if (r.closest && r.closest('.cluster')) return;
                    let w = 0, h = 0;
                    try { w = r.getBBox().width; h = r.getBBox().height; } catch (e) {}
                    if (w > box.width * 0.92 && h > box.height * 0.92) {
                      r.setAttribute('fill', 'transparent');
                      r.style.fill = 'transparent';
                    }
                  });
                  document.body.style.width = (w + 64) + 'px';
                  document.body.style.height = (h + 64) + 'px';
                  svg.querySelectorAll('rect').forEach((r) => {
                    if (r.closest && r.closest('.cluster')) {
                      r.setAttribute('rx', '16');
                      r.setAttribute('ry', '16');
                      return;
                    }
                    let w = 0, h = 0;
                    try { w = r.getBBox().width; h = r.getBBox().height; } catch (e) {}
                    if (w > 18 && h > 14 && w < box.width * 0.8 && h < box.height * 0.8) {
                      const rx = Math.min(14, Math.max(6, Math.min(w, h) * 0.18));
                      r.setAttribute('rx', String(rx));
                      r.setAttribute('ry', String(rx));
                    }
                  });
                  svg.querySelectorAll('path, line, polyline, polygon').forEach((el) => {
                    el.setAttribute('stroke-linecap', 'round');
                    el.setAttribute('stroke-linejoin', 'round');
                  });
                  return { w, h };
                }"""
                )
                page.wait_for_timeout(300)
                box = page.locator("#diagram svg").bounding_box() or {}
                page.set_viewport_size(
                    {
                        "width": max(1800, int((box.get("width") or 1700) + 100)),
                        "height": max(1000, int((box.get("height") or 900) + 100)),
                    }
                )
                page.wait_for_timeout(100)
                tmp = work / f"{dest.stem}_raw.png"
                page.locator("#diagram svg").screenshot(
                    path=str(tmp), type="png", omit_background=True
                )
                context.close()
                _crop_diagram_png(tmp, dest, pad=36, min_h=0)
            finally:
                browser.close()

    _run_sync_playwright(_render)
    if not dest.is_file() or dest.stat().st_size < 2000:
        raise RuntimeError(f"diagram png failed: {dest}")
    return dest


def _crop_diagram_png(
    src: Path, dest: Path, *, pad: int = 48, min_h: int = 0
) -> None:
    """Trim near-white margins so the flowchart fills the slide frame."""
    try:
        from PIL import Image
        import numpy as np
    except ImportError:
        shutil.copy2(src, dest)
        return
    im = Image.open(src).convert("RGBA")
    arr = np.asarray(im)
    alpha = arr[:, :, 3]
    # Screenshot uses omit_background=True, so any visible pixel has alpha > 12.
    ink = alpha > 12
    if not ink.any():
        shutil.copy2(src, dest)
        return
    ys, xs = np.where(ink)
    y0, y1 = int(ys.min()), int(ys.max()) + 1
    x0, x1 = int(xs.min()), int(xs.max()) + 1
    y0 = max(0, y0 - pad)
    x0 = max(0, x0 - pad)
    y1 = min(arr.shape[0], y1 + pad)
    x1 = min(arr.shape[1], x1 + pad)
    cropped = im.crop((x0, y0, x1, y1))
    # Optional upscale only when explicitly requested (avoid shrinking fonts later).
    if min_h > 0 and cropped.height < min_h:
        scale = min_h / float(cropped.height)
        cropped = cropped.resize(
            (max(1, int(cropped.width * scale)), min_h),
            Image.Resampling.LANCZOS,
        )
    cropped.save(dest, format="PNG", optimize=True)
    try:
        src.unlink(missing_ok=True)
    except OSError:
        pass


def ensure_diagram_pngs(
    diagram_specs: dict[str, dict[str, str]],
    *,
    dest_dir: Path,
    palette: str,
    needed_ids: set[str] | None = None,
    series: list[str] | None = None,
    theme_pack: str | None = None,
) -> dict[str, Path]:
    """Render requested diagrams; return id → png path."""
    dest_dir = Path(dest_dir)
    dest_dir.mkdir(parents=True, exist_ok=True)
    out: dict[str, Path] = {}
    ids = needed_ids if needed_ids is not None else set(diagram_specs)
    for did in ids:
        spec = diagram_specs.get(did)
        if not spec:
            log.warning("diagram %s missing from figures.json", did)
            continue
        dest = dest_dir / f"{did}.png"
        try:
            primary = series[0] if series else None
            accent = series[1] if series and len(series) > 1 else None
            render_mermaid_png(
                mermaid=spec["mermaid"],
                dest=dest,
                palette=palette,
                work_dir=dest_dir / f"work_{did}",
                primary=primary,
                accent=accent,
                theme_pack=theme_pack,
            )
            out[did] = dest
        except Exception:
            log.exception("failed to rasterize diagram %s", did)
    return out
