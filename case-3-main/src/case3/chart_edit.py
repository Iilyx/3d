"""Per-chart restyle for an existing run: palette remap ± LLM style → PNG → docs."""

from __future__ import annotations

import json
import logging
import re
import time
from pathlib import Path
from typing import Any

from case3.chart_html import ChartHtmlError, sanitize_chart_html
from case3.chart_style import (
    apply_kpi_palette_vars,
    apply_palette_to_html,
    intent_palette_lines,
    normalize_palette_id,
)
from case3.chart_coerce import apply_type_to_chart
from case3.chart_type_fit import (
    chart_number_change_warning,
    chart_type_change_warning,
)
from case3.chart_donut import enhance_donut_html
from case3.chart_harden import harden_chart_html
from case3.charts import _DEFAULT_RENDER_CHART_PNG, render_chart_png, render_charts_batch
from case3.llm_client import LLMClient, LLMConfig, LLMConfigError, LLMError
from case3.render import RenderError
from case3.run_meta import update_meta
from case3.run_rebuild import rebuild_run_docs

log = logging.getLogger("case3.chart_edit")

_FENCE = re.compile(r"```(?:html|javascript|js)?\s*([\s\S]*?)```", re.I)


class ChartEditError(RuntimeError):
    pass


class ChartNumberChange(ChartEditError):
    """Style rewrite changed data numbers. Nothing was written."""

    def __init__(self, message: str, html: str) -> None:
        super().__init__(message)
        self.html = html


def _extract_html_fragment(raw: str) -> str:
    text = (raw or "").strip()
    m = _FENCE.search(text)
    if m:
        text = m.group(1).strip()
    # Prefer from first <canvas or bare new Chart
    for marker in ("<canvas", "<div", "new Chart"):
        i = text.lower().find(marker.lower() if marker != "new Chart" else "new chart")
        if marker == "new Chart":
            i = text.find("new Chart")
            if i < 0:
                i = text.lower().find("new chart")
        if i >= 0:
            text = text[i:]
            break
    return text.strip()


def rewrite_chart_html_with_llm(
    html: str,
    *,
    palette_id: str,
    style_notes: str,
    chart_type: str = "",
    target_type: str = "",
    llm: LLMClient | None = None,
) -> str:
    """Ask the model to restyle one Chart.js fragment without changing data."""
    client = llm or LLMClient(LLMConfig.from_env())
    palette_bits = "\n".join(intent_palette_lines(palette_id, style_notes))
    want = (target_type or chart_type or "").strip()
    type_rule = (
        f"- Chart.js type / our catalog type MUST be: {want} "
        f"(map grouped_bar/stacked_bar → type:'bar' with datasets; "
        f"donut → doughnut; horizontal_bar → indexAxis:'y'; kpi → HTML cards if needed)."
        if want
        else "- Keep chart type unless the user explicitly asks to change it."
    )
    system = (
        "You restyle ONE offline Chart.js HTML fragment for a print report.\n"
        "Rules:\n"
        "- Return ONLY the HTML fragment: <canvas>…</canvas><script>new Chart(…)</script>\n"
        "- Keep EVERY data array, label string, and dataset length EXACTLY as given.\n"
        f"{type_rule}\n"
        "- Colors must follow the palette lines in the user message.\n"
        "- Set options.responsive:false, animation:false, maintainAspectRatio:false.\n"
        "- No remote URLs, no markdown, no explanation."
    )
    user = (
        f"Палитра / стиль:\n{palette_bits}\n\n"
        f"Тип сейчас: {chart_type or 'unknown'}\n"
        f"Новый тип: {want or '(без смены)'}\n"
        f"Пожелание: {(style_notes or '').strip() or '(тип/палитра)'}\n\n"
        f"Текущий HTML:\n{html}"
    )
    raw = client.complete(system=system, user_text=user, reasoning="off")
    frag = _extract_html_fragment(raw)
    if not frag:
        raise ChartEditError("LLM returned empty chart HTML")
    return sanitize_chart_html(frag)


def _load_chart_from_run(out_dir: Path, chart_id: str) -> tuple[dict[str, Any], dict[str, Any], int]:
    """Return (figures_json, chart_dict, index). Raises ChartEditError."""
    out_dir = out_dir.resolve()
    fj_path = out_dir / "figures.json"
    if not fj_path.is_file():
        raise ChartEditError("figures.json missing")
    try:
        fj = json.loads(fj_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ChartEditError(f"figures.json unreadable: {exc}") from exc

    charts = list(fj.get("charts") or [])
    idx = next(
        (i for i, c in enumerate(charts) if isinstance(c, dict) and c.get("id") == chart_id),
        -1,
    )
    if idx < 0:
        raise ChartEditError(f"chart {chart_id!r} not found")
    chart = dict(charts[idx])
    html = str(chart.get("html") or "").strip()
    if not html:
        raise ChartEditError(f"chart {chart_id!r} has no html")
    return fj, chart, idx


def _local_restyle_html(
    chart: dict[str, Any],
    *,
    palette_id: str,
    want_type: str,
) -> tuple[str, str, list[str]]:
    """Palette + type coerce only (no LLM). Returns (html, final_type, modes)."""
    html = str(chart.get("html") or "").strip()
    current_type = str(chart.get("type") or "").strip()
    want = (want_type or current_type or "").strip()
    type_changed = bool(want) and want != current_type
    modes: list[str] = []
    work = dict(chart)
    new_html = html

    if want == "kpi":
        modes.append("local_kpi")
        if type_changed:
            modes.append("type_change")
            modes.append("local_type")
        work["type"] = "kpi"
        work["html"] = html
        work = apply_type_to_chart(work, "kpi")
        new_html = str(work.get("html") or "")
        if palette_id != "auto":
            new_html = apply_kpi_palette_vars(new_html, palette_id)
            modes.append("local_palette")
    else:
        if type_changed and want:
            modes.append("type_change")
            modes.append("local_type")
            work["html"] = html
            work["type"] = want
            work = apply_type_to_chart(work, want)
            new_html = str(work.get("html") or "")
        if palette_id != "auto":
            modes.append("local_palette")
            new_html = sanitize_chart_html(apply_palette_to_html(new_html, palette_id))
        elif not type_changed:
            raise ChartEditError("укажите палитру или тип для превью")

    if want:
        work["type"] = want
        work["html"] = new_html
        work = apply_type_to_chart(work, want)
        new_html = str(work.get("html") or "")
    final_type = str(work.get("type") or want or current_type)
    if final_type == "donut" and new_html:
        new_html = enhance_donut_html(new_html)
        modes.append("donut_enhance")
    if new_html and palette_id != "auto":
        new_html = apply_kpi_palette_vars(new_html, palette_id)
    if new_html:
        new_html = harden_chart_html(new_html, final_type)
    return new_html, final_type, modes


def deck_chart_series(out_dir: Path) -> list[str]:
    """Three pack colors from the frozen deck, when this run has a presentation."""
    path = Path(out_dir) / "slides" / "deck.json"
    if not path.is_file():
        return []
    try:
        deck = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    style = deck.get("style") if isinstance(deck, dict) else None
    if not isinstance(style, dict):
        return []
    return [
        str(x).strip()
        for x in (style.get("chart_series") or [])
        if str(x).strip()
    ]


def paint_deck_chart_html(out_dir: Path, html: str, chart_type: str | None) -> str:
    """Keep a chart inside the deck's soft triad after a palette or type edit."""
    series = deck_chart_series(out_dir)
    if len(series) < 2 or not (html or "").strip():
        return html
    from case3.chart_style import (
        apply_hex_series_to_html,
        apply_pack_category_colors_to_html,
    )

    if chart_type == "kpi" or 'class="kpi"' in html:
        foil = series[0]
        muted = series[1] if len(series) > 1 else "#64748B"
        res = re.sub(r'--kpi-value\s*:\s*[^;]+;', f'--kpi-value:{foil};', html)
        return re.sub(r'--kpi-label\s*:\s*[^;]+;', f'--kpi-label:{muted};', res)

    painted = apply_hex_series_to_html(sanitize_chart_html(html), series)
    return apply_pack_category_colors_to_html(
        painted, series, chart_type=chart_type or None
    )


def preview_chart_html(
    out_dir: Path,
    chart_id: str,
    *,
    palette: str | None = None,
    chart_type: str | None = None,
) -> dict[str, Any]:
    """Local-only restyle for Liber live preview (no LLM, no disk write).

    Style notes from the edit sheet are deferred until Apply — they need the LLM.
    """
    _fj, chart, _idx = _load_chart_from_run(out_dir, chart_id)
    stored = str(chart.get("palette") or "").strip()
    effective_palette = (palette or "").strip() or stored or "editorial"
    palette_id = normalize_palette_id(effective_palette)
    current_type = str(chart.get("type") or "").strip()
    want_type = (chart_type or "").strip() or current_type
    type_warning = ""
    if want_type and want_type != current_type:
        type_warning = chart_type_change_warning(chart, want_type)
    new_html, final_type, modes = _local_restyle_html(
        chart, palette_id=palette_id, want_type=want_type
    )
    user_style = bool(chart.get("style_user")) or (
        bool(palette) and palette not in ("", "auto") and palette_id != stored
    )
    if not user_style:
        new_html = paint_deck_chart_html(out_dir, new_html, final_type)
    return {
        "chart_id": chart_id,
        "id": chart_id,
        "type": final_type,
        "palette": palette_id,
        "html": new_html,
        "modes": modes,
        "caption": str(chart.get("caption") or "").strip(),
        "style_deferred": True,
        "type_warning": type_warning,
    }


def edit_chart_in_run(
    out_dir: Path,
    chart_id: str,
    *,
    palette: str | None = None,
    style: str | None = None,
    chart_type: str | None = None,
    formats: set[str] | None = None,
    llm: LLMClient | None = None,
    accepted_html: str | None = None,
) -> dict[str, Any]:
    """Update one chart PNG + figures.json and rebuild PDF/DOCX in out_dir."""
    out_dir = out_dir.resolve()
    fj, chart, idx = _load_chart_from_run(out_dir, chart_id)
    charts = list(fj.get("charts") or [])
    html = str(chart.get("html") or "").strip()

    stored_palette = str(chart.get("palette") or "").strip()
    effective_palette = (palette or "").strip() or stored_palette or "editorial"
    palette_id = normalize_palette_id(effective_palette)
    style_notes = (style or "").strip()
    accepted = (accepted_html or "").strip()
    current_type = str(chart.get("type") or "").strip()
    want_type = (chart_type or "").strip() or current_type
    type_changed = bool(want_type) and want_type != current_type
    modes: list[str] = []

    new_html = html
    # KPI is HTML cards, not Chart.js — never ask the LLM for a <canvas> kpi.
    if want_type == "kpi":
        modes.append("local_kpi")
        if type_changed:
            modes.append("type_change")
            modes.append("local_type")
        chart["type"] = "kpi"
        chart["html"] = html
        chart = apply_type_to_chart(chart, "kpi")
        new_html = str(chart.get("html") or "")
        if palette_id != "auto":
            # KPI cards use CSS vars from palette (frame .kpi / --kpi-value).
            new_html = apply_kpi_palette_vars(new_html, palette_id)
            modes.append("local_palette")
    elif bool(style_notes) and accepted:
        modes.append("llm_style")
        modes.append("numbers_accepted")
        new_html = accepted
    elif bool(style_notes):
        # Free-text restyle always needs the model.
        modes.append("llm_style")
        if type_changed:
            modes.append("type_change")
        try:
            new_html = rewrite_chart_html_with_llm(
                html,
                palette_id=palette_id,
                style_notes=style_notes,
                chart_type=current_type,
                target_type=want_type,
                llm=llm,
            )
        except (LLMError, LLMConfigError, ChartHtmlError, ChartEditError) as exc:
            raise ChartEditError(f"style rewrite failed: {exc}") from exc
        # Enforce palette after LLM (model may ignore)
        if palette_id != "auto":
            new_html = apply_palette_to_html(new_html, palette_id)
            modes.append("local_palette")
            new_html = sanitize_chart_html(new_html)
        # Deterministic type lock after LLM (model often keeps type:'bar').
        if want_type:
            chart["html"] = new_html
            chart["type"] = want_type
            chart = apply_type_to_chart(chart, want_type)
            new_html = str(chart.get("html") or "")
    elif type_changed:
        # Type/palette only — same local coerce as /preview (no 20s LLM).
        modes.append("type_change")
        modes.append("local_type")
        chart["html"] = html
        chart["type"] = want_type
        chart = apply_type_to_chart(chart, want_type)
        new_html = str(chart.get("html") or "")
        if palette_id != "auto":
            if want_type == "kpi" or 'class="kpi"' in new_html:
                new_html = apply_kpi_palette_vars(new_html, palette_id)
            else:
                new_html = sanitize_chart_html(
                    apply_palette_to_html(new_html, palette_id)
                )
            modes.append("local_palette")
    else:
        if palette_id == "auto":
            raise ChartEditError("укажите палитру, тип или текст «как изменить»")
        modes.append("local_palette")
        # G4: KPI cards need CSS vars, not Chart.js color remap.
        if current_type == "kpi" or want_type == "kpi" or 'class="kpi"' in html:
            new_html = apply_kpi_palette_vars(html, palette_id)
        else:
            new_html = sanitize_chart_html(apply_palette_to_html(html, palette_id))

    # Commit figures.json only after PNG succeeds (avoid HTML/PNG drift).
    if want_type:
        chart["type"] = want_type
        chart["html"] = new_html
        chart = apply_type_to_chart(chart, want_type)
        new_html = str(chart.get("html") or "")
    final_type = str(chart.get("type") or want_type or current_type)
    # Re-apply Mary donut shell after LLM/palette (edit used to drop legend).
    if final_type == "donut" and new_html:
        new_html = enhance_donut_html(new_html)
        modes.append("donut_enhance")
    if new_html and palette_id != "auto":
        new_html = apply_kpi_palette_vars(new_html, palette_id)
    if new_html:
        new_html = harden_chart_html(new_html, final_type)
    stored_palette = str(chart.get("palette") or "").strip()
    user_style = bool(chart.get("style_user")) or bool(style_notes) or (
        bool(palette) and palette not in ("", "auto") and palette_id != stored_palette
    )
    if new_html and not user_style:
        new_html = paint_deck_chart_html(out_dir, new_html, final_type)
    if style_notes and not accepted:
        number_warning = chart_number_change_warning(
            html, new_html, chart_type=current_type
        )
        if number_warning:
            raise ChartNumberChange(number_warning, new_html)
    from case3.run_undo import capture_before_edit

    capture_before_edit(out_dir, kind="chart", target=chart_id)
    chart["html"] = new_html
    chart["type"] = final_type
    # G2: persist so Liber edit sheet seeds this figure's palette next open.
    if user_style:
        if palette_id and palette_id != "auto":
            chart["palette"] = palette_id
        chart["style_user"] = True
    elif stored_palette:
        chart["palette"] = stored_palette
    from case3.slides_chart_data import attach_series_ir

    attach_series_ir(chart)
    charts[idx] = chart
    fj["charts"] = charts
    figs_dir = out_dir / "figures"
    figs_dir.mkdir(parents=True, exist_ok=True)
    dest = figs_dir / f"{chart_id}.png"
    work = out_dir / "chart_work" / chart_id
    bak: bytes | None = dest.read_bytes() if dest.is_file() else None
    try:
        render_chart_png(chart, dest, work_dir=work)
    except Exception as exc:  # noqa: BLE001
        if bak is not None:
            dest.write_bytes(bak)
        from case3.run_undo import clear_undo

        clear_undo(out_dir)
        raise ChartEditError(f"chart render failed: {exc}") from exc

    # Invalidate stale slide chart cache so download_slide_media serves fresh figure immediately
    stale_slide_chart = out_dir / "slides" / "charts" / f"{chart_id}.png"
    if stale_slide_chart.is_file():
        try:
            stale_slide_chart.unlink()
        except OSError:
            pass

    fj_path = out_dir / "figures.json"
    fj_path.write_text(json.dumps(fj, ensure_ascii=False, indent=2), encoding="utf-8")

    # meta media_status
    def _mut_chart_edit(m: dict[str, Any]) -> None:
        med = dict(m.get("media_status") or {})
        med[chart_id] = {"ok": True, "path": str(dest), "kind": "chart"}
        m["media_status"] = med
        m["chart_edit_last"] = {
            "id": chart_id,
            "palette": palette_id,
            "style": style_notes,
            "chart_type": want_type,
            "modes": modes,
            "ts": int(time.time()),
        }

    meta = update_meta(out_dir, _mut_chart_edit)
    media = dict(meta.get("media_status") or {})

    try:
        artifacts = rebuild_run_docs(out_dir, formats=formats)
    except FileNotFoundError as exc:
        raise ChartEditError(str(exc)) from exc
    except RenderError as exc:
        raise ChartEditError(f"document rebuild failed: {exc}") from exc

    from case3.deck_refresh import refresh_deck_from_ir

    refresh_deck_from_ir(out_dir)

    v = int(dest.stat().st_mtime)
    from case3.run_undo import undo_meta

    return {
        "chart_id": chart_id,
        "mode": "+".join(modes),
        "media_status": media,
        "artifacts": {k: str(p) for k, p in artifacts.items()},
        "version": v,
        "palette": palette_id,
        "style": style_notes,
        "undo": undo_meta(out_dir),
    }


def paint_hue_charts_in_run(
    out_dir: Path,
    hue: str,
    *,
    chart_type: str = "",
    formats: set[str] | None = None,
) -> dict[str, Any]:
    """Recolor existing charts to a named hue. Numbers and labels stay. No model call."""
    from case3.chart_style import paint_hue_on_html
    from case3.charts import render_charts_batch
    from case3.slides_chart_data import attach_series_ir_to_charts

    out_dir = out_dir.resolve()
    fj_path = out_dir / "figures.json"
    if not fj_path.is_file():
        raise ChartEditError("figures.json not found")
    try:
        fj = json.loads(fj_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ChartEditError(f"could not read figures.json: {exc}") from exc
    charts = [c for c in (fj.get("charts") or []) if isinstance(c, dict)]
    if not charts:
        raise ChartEditError("нет графиков для перекрашивания")

    from case3.run_undo import capture_before_edit, undo_meta

    capture_before_edit(out_dir, kind="batch_recolor", target=hue)
    figs_dir = out_dir / "figures"
    figs_dir.mkdir(parents=True, exist_ok=True)
    work_root = out_dir / "chart_recolor_work"
    want = (chart_type or "").strip()
    painted = 0
    painted_paths: dict[str, Path] = {}
    batch_items: list[tuple[str, dict[str, Any], Path, Path]] = []
    for index, chart in enumerate(charts):
        cid = str(chart.get("id") or "").strip()
        html = str(chart.get("html") or "").strip()
        if not cid or not html:
            continue
        current = str(chart.get("type") or "").strip()
        if want and want != current:
            chart = apply_type_to_chart(dict(chart), want)
            html = str(chart.get("html") or html)
        new_html = paint_hue_on_html(html, hue)
        if not new_html:
            continue
        chart["html"] = new_html
        chart["style_user"] = True
        chart["hue"] = hue
        charts[index] = chart
        png_path = figs_dir / f"{cid}.png"
        batch_items.append((cid, chart, png_path, work_root / cid))
        painted += 1
    if not painted:
        raise ChartEditError("нет графиков для перекрашивания")
    batch_res = render_charts_batch(batch_items) if batch_items else {}
    for cid, _chart, png_path, _cdir in batch_items:
        if batch_res.get(cid, {}).get("ok"):
            painted_paths[cid] = png_path
    attach_series_ir_to_charts(charts)
    fj["charts"] = charts
    fj_path.write_text(json.dumps(fj, ensure_ascii=False, indent=2), encoding="utf-8")

    def _mut(meta: dict[str, Any]) -> None:
        med = dict(meta.get("media_status") or {})
        for cid, png_path in painted_paths.items():
            med[cid] = {"ok": True, "path": str(png_path), "kind": "chart"}
        meta["media_status"] = med

    meta = update_meta(out_dir, _mut)
    artifacts = None
    if formats:
        try:
            artifacts = rebuild_run_docs(out_dir, formats=formats)
        except Exception as exc:
            log.warning("rebuild_run_docs failed during hue recolor: %s", exc)
    from case3.deck_refresh import refresh_deck_from_ir

    refresh_deck_from_ir(out_dir)
    return {
        "ok": True,
        "hue": hue,
        "charts_recolored": len(painted_paths) or painted,
        "media_status": dict(meta.get("media_status") or {}),
        "artifacts": {k: str(p) for k, p in (artifacts or {}).items()},
        "undo": undo_meta(out_dir),
    }


def recolor_all_charts_in_run(
    out_dir: Path,
    palette: str,
    *,
    formats: set[str] | None = None,
) -> dict[str, Any]:
    """Batch recolor all charts in an existing run to a new palette without LLM re-run."""
    out_dir = out_dir.resolve()
    fj_path = out_dir / "figures.json"
    if not fj_path.is_file():
        fj_path = out_dir.parent.parent / "work" / out_dir.name / "figures.json"
    if not fj_path.is_file():
        raise ChartEditError("figures.json not found")

    try:
        fj = json.loads(fj_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ChartEditError(f"could not read figures.json: {exc}") from exc

    charts = list(fj.get("charts") or [])
    if not charts:
        raise ChartEditError("нет графиков для перекрашивания")

    palette_id = normalize_palette_id(palette or "atelier")
    if palette_id in ("", "auto"):
        palette_id = "atelier"

    from case3.run_undo import capture_before_edit, undo_meta

    capture_before_edit(out_dir, kind="batch_recolor", target=palette_id)

    figs_dir = out_dir / "figures"
    figs_dir.mkdir(parents=True, exist_ok=True)
    work_root = out_dir / "chart_recolor_work"

    recolored = 0
    recolored_paths: dict[str, Path] = {}
    batch_items: list[tuple[str, dict[str, Any], Path, Path]] = []
    for chart in charts:
        cid = str(chart.get("id") or "").strip()
        html = str(chart.get("html") or "").strip()
        if not html:
            continue
        ctype = str(chart.get("type") or "").strip()
        if ctype == "kpi" or 'class="kpi"' in html:
            new_html = apply_kpi_palette_vars(html, palette_id)
        else:
            new_html = sanitize_chart_html(apply_palette_to_html(html, palette_id))

        if ctype == "donut" and new_html:
            new_html = enhance_donut_html(new_html)
        if new_html:
            new_html = apply_kpi_palette_vars(new_html, palette_id)
            new_html = harden_chart_html(new_html, ctype or "bar")

        chart["palette"] = palette_id
        chart["html"] = new_html
        chart["style_user"] = True

        stale_slide_chart = out_dir / "slides" / "charts" / f"{cid}.png"
        if stale_slide_chart.is_file():
            try:
                stale_slide_chart.unlink()
            except OSError:
                pass

        png_path = figs_dir / f"{cid}.png"
        if render_chart_png is not _DEFAULT_RENDER_CHART_PNG:
            render_chart_png(new_html, png_path)
            recolored_paths[cid] = png_path
            recolored += 1
        else:
            batch_items.append((cid, chart, png_path, work_root / cid))

    if batch_items:
        batch_res = render_charts_batch(batch_items)
        for cid, _chart, png_path, _cdir in batch_items:
            if batch_res.get(cid, {}).get("ok"):
                recolored_paths[cid] = png_path
                recolored += 1

    from case3.slides_chart_data import attach_series_ir_to_charts

    attach_series_ir_to_charts(charts)
    fj["charts"] = charts
    fj_path.write_text(json.dumps(fj, ensure_ascii=False, indent=2), encoding="utf-8")

    def _mut_recolor(m: dict[str, Any]) -> None:
        med = dict(m.get("media_status") or {})
        for cid, png_path in recolored_paths.items():
            med[cid] = {"ok": True, "path": str(png_path), "kind": "chart"}
        m["chart_palette"] = palette_id
        m["media_status"] = med

    meta = update_meta(out_dir, _mut_recolor)
    media = dict(meta.get("media_status") or {})

    artifacts = None
    if formats:
        from case3.run_rebuild import rebuild_run_docs
        try:
            artifacts = rebuild_run_docs(out_dir, formats=formats)
        except Exception as exc:
            log.warning("rebuild_run_docs failed during batch recolor: %s", exc)

    from case3.deck_refresh import refresh_deck_from_ir

    refresh_deck_from_ir(out_dir)

    v = int(time.time())
    return {
        "ok": True,
        "palette": palette_id,
        "charts_recolored": recolored,
        "version": v,
        "media_status": media,
        "artifacts": {k: str(p) for k, p in (artifacts or {}).items()},
        "undo": undo_meta(out_dir),
    }
