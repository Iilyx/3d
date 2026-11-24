"""Export Liber diagrams as SVG (client parity + API)."""

from __future__ import annotations

import json
import logging
import os
import re
import shutil
from pathlib import Path
from typing import Any

log = logging.getLogger("case3.diagram_svg")

_SVG_ROOT = re.compile(r"<svg\b[^>]*>", re.I)


class DiagramSvgError(RuntimeError):
    pass


def normalize_svg_document(svg: str) -> str:
    """Ensure a standalone SVG document string (xmlns)."""
    text = (svg or "").strip()
    if not text:
        raise DiagramSvgError("empty svg")
    if "xmlns=" not in text[:200].lower():
        text = _SVG_ROOT.sub(
            lambda m: m.group(0)[:-1]
            + ' xmlns="http://www.w3.org/2000/svg"'
            + m.group(0)[-1],
            text,
            count=1,
        )
    if not text.lstrip().startswith("<svg"):
        raise DiagramSvgError("not an svg document")
    return text


def load_diagram_spec(out_dir: Path, diagram_id: str) -> dict[str, str]:
    """Read one diagram from figures.json."""
    out_dir = Path(out_dir)
    fj_path = out_dir / "figures.json"
    if not fj_path.is_file():
        raise DiagramSvgError("figures.json missing")
    try:
        data = json.loads(fj_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise DiagramSvgError("corrupt figures.json") from exc
    diagrams = data.get("diagrams") if isinstance(data, dict) else None
    if not isinstance(diagrams, list):
        raise DiagramSvgError("no diagrams")
    want = str(diagram_id or "").strip()
    for d in diagrams:
        if not isinstance(d, dict):
            continue
        if str(d.get("id") or "").strip() != want:
            continue
        mermaid = str(d.get("mermaid") or "").strip()
        if not mermaid:
            raise DiagramSvgError("empty mermaid")
        return {
            "id": want,
            "title": str(d.get("title") or d.get("caption") or want).strip(),
            "type": str(d.get("type") or "").strip(),
            "mermaid": mermaid,
        }
    raise DiagramSvgError(f"diagram not found: {want}")


def render_mermaid_svg_string(
    *,
    mermaid: str,
    palette: str = "atelier",
    work_dir: Path | None = None,
) -> str:
    """Render Mermaid → SVG markup via Playwright (same stack as PNG)."""
    from case3.chart_style import normalize_palette_id
    from case3.charts import (
        _prefer_stable_playwright_browsers,
        _run_sync_playwright,
        chart_timeout_s,
        file_url_to_path,
        paths_equal,
    )
    from case3.slides_media import _mermaid_js_path, render_diagram_html

    work = Path(work_dir) if work_dir else Path.cwd() / ".mmd_svg_work"
    work.mkdir(parents=True, exist_ok=True)
    js_src = _mermaid_js_path()
    js_dest = work / "mermaid.min.js"
    if not js_dest.is_file() or js_dest.stat().st_size != js_src.stat().st_size:
        shutil.copy2(js_src, js_dest)

    pid = normalize_palette_id(palette)
    if pid == "auto":
        pid = "atelier"
    html = render_diagram_html(mermaid=mermaid, palette=pid)
    index = (work / "index.html").resolve()
    index.write_text(html, encoding="utf-8")
    js_dest = js_dest.resolve()

    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise DiagramSvgError("playwright not installed") from exc

    timeout_ms = int(chart_timeout_s() * 1000)
    allowed = {index, js_dest}
    holder: dict[str, Any] = {"svg": ""}

    def _render() -> None:
        bp = os.environ.get("PLAYWRIGHT_BROWSERS_PATH")
        if bp and not Path(bp).exists():
            os.environ.pop("PLAYWRIGHT_BROWSERS_PATH", None)
        _prefer_stable_playwright_browsers()
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
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
                page.wait_for_timeout(200)
                holder["svg"] = page.locator("#diagram svg").evaluate(
                    "el => el.outerHTML"
                )
                context.close()
            finally:
                browser.close()

    _run_sync_playwright(_render)
    raw = str(holder.get("svg") or "").strip()
    if not raw:
        raise DiagramSvgError("svg render empty")
    if (
        'aria-roledescription="error"' in raw
        or "error-icon" in raw
        or "Syntax error in text" in raw
    ):
        raise DiagramSvgError("mermaid syntax error rendered")
    return normalize_svg_document(raw)


def export_diagram_svg(out_dir: Path, diagram_id: str, *, palette: str = "atelier") -> str:
    """Load diagram from run + render SVG string."""
    spec = load_diagram_spec(out_dir, diagram_id)
    work = out_dir / "figures" / ".svg_work" / diagram_id
    return render_mermaid_svg_string(
        mermaid=spec["mermaid"], palette=palette, work_dir=work
    )
