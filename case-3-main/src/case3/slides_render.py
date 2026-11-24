"""Playwright capture of static Liber slides (1920×1080)."""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any

from case3.charts import (
    _prefer_stable_playwright_browsers,
    _run_sync_playwright,
    chart_timeout_s,
    file_url_to_path,
    paths_equal,
)
from case3.slides_html import SLIDE_VIEWPORT, write_slide_work

log = logging.getLogger("case3.slides_render")

_MAX_PNG = 12 * 1024 * 1024


def _validate_png(dest_png: Path) -> None:
    data = dest_png.read_bytes()
    if len(data) > _MAX_PNG:
        dest_png.unlink(missing_ok=True)
        raise RuntimeError(f"slide png too large: {len(data)} bytes")
    if not data.startswith(b"\x89PNG\r\n\x1a\n"):
        dest_png.unlink(missing_ok=True)
        raise RuntimeError("slide screenshot is not PNG")
    if len(data) < 2000:
        dest_png.unlink(missing_ok=True)
        raise RuntimeError(f"slide png suspiciously small: {len(data)} bytes")


def _allowed_assets(html_dir: Path, index: Path) -> set[Path]:
    allowed = {index}
    for name in ("chart.png", "media.png", "botanical_bg.png"):
        asset = html_dir / name
        if asset.is_file():
            allowed.add(asset.resolve())
    fonts = html_dir / "fonts"
    if fonts.is_dir():
        for f in fonts.glob("*.woff2"):
            allowed.add(f.resolve())
    return allowed


def capture_slide_png(html_dir: Path, dest_png: Path) -> None:
    """Screenshot ``#slide`` from ``html_dir/index.html`` via Playwright."""
    html_dir = Path(html_dir).resolve()
    index = (html_dir / "index.html").resolve()
    if not index.is_file():
        raise FileNotFoundError(index)

    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise RuntimeError(
            "playwright not installed — run: pip install playwright && playwright install chromium"
        ) from exc

    dest_png = Path(dest_png)
    dest_png.parent.mkdir(parents=True, exist_ok=True)
    timeout_ms = int(chart_timeout_s() * 1000)
    vw, vh = SLIDE_VIEWPORT
    allowed = _allowed_assets(html_dir, index)

    def _render() -> None:
        # Cursor sandbox may set a broken PLAYWRIGHT_BROWSERS_PATH — clear if empty.
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
                    viewport={"width": vw, "height": vh},
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
                page.locator("#slide").wait_for(state="visible", timeout=timeout_ms)
                # Let fonts/layout settle.
                page.wait_for_timeout(80)
                page.locator("#slide").screenshot(path=str(dest_png), type="png")
                context.close()
            finally:
                browser.close()

    _run_sync_playwright(_render)
    _validate_png(dest_png)


_DEFAULT_CAPTURE_SLIDE_PNG = capture_slide_png


def _capture_deck_slides_batch(tasks: list[tuple[Path, Path]]) -> None:
    """Capture multiple slide screenshots sharing a single Chromium browser instance."""
    if not tasks:
        return
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise RuntimeError(
            "playwright not installed — run: pip install playwright && playwright install chromium"
        ) from exc

    timeout_ms = int(chart_timeout_s() * 1000)
    vw, vh = SLIDE_VIEWPORT

    def _batch_render() -> None:
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
                for work, dest_png in tasks:
                    index = (work / "index.html").resolve()
                    if not index.is_file():
                        raise FileNotFoundError(index)
                    dest_png = Path(dest_png)
                    dest_png.parent.mkdir(parents=True, exist_ok=True)
                    allowed = _allowed_assets(work, index)

                    context = browser.new_context(
                        viewport={"width": vw, "height": vh},
                        device_scale_factor=2,
                    )

                    def _route(route, request, _allowed=allowed):  # noqa: ANN001
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
                            if any(paths_equal(resolved, a) for a in _allowed):
                                route.continue_()
                            else:
                                route.abort()
                            return
                        route.abort()

                    context.route("**/*", _route)
                    page = context.new_page()
                    page.goto(index.as_uri(), wait_until="load", timeout=timeout_ms)
                    page.locator("#slide").wait_for(state="visible", timeout=timeout_ms)
                    page.wait_for_timeout(80)
                    page.locator("#slide").screenshot(path=str(dest_png), type="png")
                    context.close()
                    _validate_png(dest_png)
            finally:
                browser.close()

    _run_sync_playwright(_batch_render)


def render_deck_pngs(
    deck: dict[str, Any],
    *,
    work_root: Path,
    out_dir: Path,
    chart_png_by_id: dict[str, Path] | None = None,
    media_png_by_id: dict[str, Path] | None = None,
    diagrams_by_id: dict[str, dict[str, Any]] | None = None,
) -> list[Path]:
    """Write HTML work dirs + PNGs for each slide; return ordered PNG paths."""
    import re
    work_root = Path(work_root)
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    slides = [s for s in (deck.get("slides") or []) if isinstance(s, dict)]
    new_count = len(slides)

    # Clean up stale slide_*.png files from deleted slides
    for p in out_dir.glob("slide_*.png"):
        m = re.match(r"^slide_(\d+)\.png$", p.name)
        if m and int(m.group(1)) > new_count:
            p.unlink(missing_ok=True)

    media = dict(chart_png_by_id or {})
    if media_png_by_id:
        media.update(media_png_by_id)
    diagrams = diagrams_by_id or {}
    palette = str(deck.get("palette") or "atelier")
    language = str(deck.get("language") or "ru")
    style = deck.get("style") if isinstance(deck.get("style"), dict) else None

    tasks: list[tuple[Path, Path]] = []
    paths: list[Path] = []

    for i, slide in enumerate(slides, start=1):
        sid = str(slide.get("id") or f"s{i:02d}")
        work = work_root / sid
        media_path: Path | None = None
        layout = str(slide.get("layout") or "")
        asset_id = ""
        if layout in ("chart_hero", "chart_split"):
            asset_id = str(slide.get("chart_id") or "")
        elif layout in ("media_hero", "media_split", "title", "closing"):
            asset_id = str(slide.get("media_id") or slide.get("chart_id") or "")
        if asset_id:
            cand = media.get(asset_id)
            if cand and Path(cand).is_file():
                media_path = Path(cand)
            else:
                log.warning("%s %s missing png for %s", layout, sid, asset_id)
        write_slide_work(
            slide,
            work,
            palette=palette,
            language=language,
            media_png=media_path,
            style=style,
            slide_index=i - 1,
            diagram_spec=diagrams.get(asset_id) if asset_id.startswith("dia_") else None,
        )
        dest = out_dir / f"slide_{i:02d}.png"
        tasks.append((work, dest))
        paths.append(dest)

    if capture_slide_png is not _DEFAULT_CAPTURE_SLIDE_PNG:
        for work, dest in tasks:
            capture_slide_png(work, dest)
    else:
        _capture_deck_slides_batch(tasks)

    return paths

