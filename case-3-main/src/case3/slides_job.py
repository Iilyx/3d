"""On-demand Liber deck job: LLM IR → PNG capture → image PPTX + deck PDF."""

from __future__ import annotations

from case3.paths import repo_root

import json
import logging
import re
from pathlib import Path
from typing import Any, Callable

from case3.chart_html import sanitize_chart_html
from case3.chart_style import (
    apply_hex_series_to_html,
    apply_pack_category_colors_to_html,
    normalize_palette_id,
)
from case3.charts import _DEFAULT_RENDER_CHART_PNG, render_chart_png, render_charts_batch
from case3.deck_theme import normalize_pack_id, resolve_deck_theme
from case3.input_validation import InsufficientDataError
from case3.llm_client import LLMClient, LLMConfig, LLMConfigError, LLMError
from case3.run_cancel import RunCancelled, raise_if_cancelled
from case3.run_events import EVENTS
from case3.slides_beat_planner import (
    format_beat_overlay,
    maybe_apply_pack_hint,
    plan_beats,
)
from case3.slides_chart_data import (
    attach_series_ir_to_charts,
    ensure_deck_charts,
    ensure_deck_diagrams,
    ensure_deck_photos,
    series_from_figures_json,
    series_map_from_figures,
)
from case3.slides_lo import write_deck_pdf
from case3.slides_pptx_native import build_native_pptx
from case3.source_brief import (
    code_highlights,
    ensure_code_callouts,
    slides_source_text,
)
from case3.schema_redraw import (
    redraw_attached_schemas,
    schema_source_ids,
    select_schema_photos,
)
from case3.slides_ir import DeckIrError, parse_deck_ir, scrub_invented_numbers
from case3.slides_media import (
    collect_run_media,
    ensure_diagram_pngs,
    load_figures_json,
)
from case3.slides_render import render_deck_pngs

log = logging.getLogger("case3.slides_job")

_JSON_FENCE = re.compile(r"```(?:json)?\s*([\s\S]*?)```", re.I)
_META_WRITE = Callable[[dict[str, Any]], None]


def _repo_root() -> Path:
    return repo_root()


def _ids_block(ids: list[str], *, empty: str) -> str:
    return ", ".join(ids) if ids else empty


def _media_catalog_block(out_dir: Path) -> str:
    """Human catalog so LLM titles match real chart/figure/diagram captions."""
    fj = load_figures_json(out_dir)
    lines: list[str] = []
    for ch in fj.get("charts") or []:
        if not isinstance(ch, dict):
            continue
        cid = str(ch.get("id") or "").strip()
        if not cid:
            continue
        cap = str(ch.get("caption") or "").strip() or "(no caption)"
        ctype = str(ch.get("type") or "").strip()
        lines.append(f"- chart {cid} [{ctype}]: {cap}")
    for fig in fj.get("figures") or []:
        if not isinstance(fig, dict):
            continue
        fid = str(fig.get("id") or "").strip()
        if not fid:
            continue
        cap = str(fig.get("caption") or "").strip() or "(no caption)"
        lines.append(f"- figure {fid}: {cap}")
    for dia in fj.get("diagrams") or []:
        if not isinstance(dia, dict):
            continue
        did = str(dia.get("id") or "").strip()
        if not did:
            continue
        title = str(dia.get("title") or dia.get("caption") or "").strip() or "(no title)"
        dtype = str(dia.get("type") or "").strip()
        lines.append(f"- diagram {did} [{dtype}]: {title}")
    return "\n".join(lines) if lines else "(no media catalog)"


def _theme_overlay(theme_pack: str | None) -> str:
    """Optional visual/tone overlay from prompt/themes/slides_{pack}.md."""
    from case3.deck_theme import normalize_pack_id
    from case3.prompts import load_theme

    pack = normalize_pack_id(theme_pack)
    return load_theme("slides", pack, fallback="atelier")


def load_slides_system_prompt(
    *,
    palette: str,
    chart_ids: list[str],
    figure_ids: list[str],
    diagram_ids: list[str],
    intent: str,
    source: str,
    media_catalog: str = "",
    theme_pack: str | None = None,
    structure_id: str | None = None,
    beat_overlay: str | None = None,
) -> str:
    from case3.deck_structure import structure_overlay
    from case3.prompts import load as load_prompt

    overlay = _theme_overlay(theme_pack)
    struct = (beat_overlay or "").strip() or structure_overlay(structure_id)
    return load_prompt(
        "system_slides",
        PALETTE=palette,
        THEME_OVERLAY=overlay,
        STRUCTURE_OVERLAY=struct,
        CHART_IDS=_ids_block(
            chart_ids, empty="(none — do not use chart_hero / chart_split)"
        ),
        FIGURE_IDS=_ids_block(figure_ids, empty="(none — no photos)"),
        DIAGRAM_IDS=_ids_block(diagram_ids, empty="(none — no diagrams)"),
        MEDIA_CATALOG=media_catalog or "(no media catalog)",
        INTENT=intent or "",
        SOURCE=source or "",
    )


def _repair_json_text(blob: str) -> str:
    """Best-effort fixes for common LLM JSON slips."""
    s = blob
    # Trailing commas before } or ]
    s = re.sub(r",(\s*[}\]])", r"\1", s)
    # Smart quotes → plain
    s = s.replace("“", '"').replace("”", '"').replace("‘", "'").replace("’", "'")
    return s


def _balanced_objects(text: str) -> list[str]:
    """Every top-level `{…}` span, respecting strings."""
    spans: list[str] = []
    n = len(text)
    i = 0
    while i < n:
        if text[i] != "{":
            i += 1
            continue
        depth = 0
        in_str = False
        esc = False
        for j in range(i, n):
            ch = text[j]
            if in_str:
                if esc:
                    esc = False
                elif ch == "\\":
                    esc = True
                elif ch == '"':
                    in_str = False
                continue
            if ch == '"':
                in_str = True
            elif ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    spans.append(text[i : j + 1])
                    i = j + 1
                    break
        else:
            break
    return spans


def _load_object(blob: str) -> dict[str, Any] | None:
    for candidate in (blob, _repair_json_text(blob)):
        try:
            data = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if isinstance(data, dict):
            return data
    return None


def _retry_user(user: str, error: str, allowed_preview: str) -> str:
    """Second ask keeps the Source. A retry that only quotes the error drops the deck."""
    return (
        f"{user}\n\n"
        f"Previous answer was rejected: {error}. "
        "Return ONLY one JSON object with a non-empty slides array. "
        "No prose and no markdown fence. "
        "Choose layouts that Source can fill; do not copy a theme script; "
        "≥5 distinct layouts when ≥8 slides; "
        "at most 2 consecutive scorecard/kpi_row; "
        "Use available media ids; "
        f"ONLY these number tokens (or Source): {allowed_preview}; "
        "bullets ≤140 chars, a full sentence not a label; title first, closing last. "
        "Do not invent averages or deltas."
    )


def _extract_json_object(raw: str) -> dict[str, Any]:
    text = (raw or "").strip()
    m = _JSON_FENCE.search(text)
    if m:
        text = m.group(1).strip()
    decks: list[dict[str, Any]] = []
    other: dict[str, Any] | None = None
    for blob in _balanced_objects(text):
        data = _load_object(blob)
        if data is None:
            continue
        slides = data.get("slides")
        if isinstance(slides, list) and slides:
            decks.append(data)
        elif other is None:
            other = data
    if decks:
        return max(decks, key=lambda d: len(d["slides"]))
    if other is not None:
        return other
    raise DeckIrError("LLM response has no JSON object")


def _read_meta(out_dir: Path) -> dict[str, Any]:
    from case3.run_meta import read_meta

    return read_meta(out_dir) or {}


def _write_meta(out_dir: Path, meta: dict[str, Any], logs_dir: Path | None = None) -> None:
    from case3.run_events import _meta_file_lock, write_meta_atomic
    from case3.run_meta import read_meta

    with _meta_file_lock:
        disk = read_meta(out_dir)
        if disk.get("cancel_requested"):
            meta["cancel_requested"] = True
        payload = json.dumps(meta, ensure_ascii=False, indent=2)
        logs_meta = (logs_dir / "meta.json") if logs_dir is not None else None
        write_meta_atomic(out_dir / "meta.json", payload, logs_meta=logs_meta)


def _set_slides(
    out_dir: Path,
    meta: dict[str, Any],
    *,
    status: str,
    stage: str,
    error: str | None = None,
    logs_dir: Path | None = None,
) -> None:
    if status == "running":
        raise_if_cancelled(out_dir)
    meta["slides_status"] = status
    meta["slides_stage"] = stage
    if error is not None:
        meta["slides_error"] = error
    elif "slides_error" in meta and status == "ok":
        meta["slides_error"] = None
    from case3.run_events import note_craft_stage

    note_craft_stage(meta, stage=stage, scope="slides")
    _write_meta(out_dir, meta, logs_dir)
    run_id = str(meta.get("run_id") or out_dir.name)
    if status == "running":
        EVENTS.publish_stage(run_id, stage, scope="slides")
        EVENTS.scan_artifacts(run_id, out_dir)
    elif status == "ok":
        EVENTS.scan_artifacts(run_id, out_dir)
        EVENTS.publish_stage(run_id, "ok", scope="slides")
        EVENTS.publish_terminal(
            run_id, "ok", recap=EVENTS.success_recap(run_id)
        )
    elif status == "error":
        EVENTS.publish_stage(run_id, "error", detail=error, scope="slides")
        EVENTS.publish_terminal(run_id, "error", error=error)
    elif status == "cancelled":
        EVENTS.publish_stage(run_id, "cancelled", scope="slides")
        EVENTS.publish_terminal(run_id, "cancelled")


def _load_source_and_intent(out_dir: Path, meta: dict[str, Any]) -> tuple[str, str]:
    intent = str(meta.get("intent") or "")
    source = ""
    src_meta = meta.get("source")
    if isinstance(src_meta, str) and src_meta.strip():
        p = Path(src_meta)
        if p.is_file():
            source = p.read_text(encoding="utf-8")
    if not source:
        for cand in out_dir.glob("*.txt"):
            if cand.name.endswith(".raw_model.txt"):
                continue
            source = cand.read_text(encoding="utf-8")
            break
    if not source.strip():
        # Last resort: copy from uploads path pattern in meta
        raise RuntimeError("Source text not found for slides job")
    return source, intent


def deck_vision_images(
    png_by_id: dict[str, Path],
    figure_ids: list[str],
    *,
    limit: int = 5,
    max_edge: int = 768,
) -> list[tuple[str, str]]:
    """JPEG data-URLs for Qwen-VL. Logos and UI shots, not chart PNGs.

    Resized so a Windows GGUF context still fits the deck JSON request.
    """
    ids = [
        fid
        for fid in figure_ids
        if fid.startswith(("usr_", "fig_")) and fid in png_by_id
    ][: max(0, limit)]
    out: list[tuple[str, str]] = []
    for fid in ids:
        url = _jpeg_data_url(png_by_id[fid], max_edge=max_edge)
        if url:
            out.append((fid, url))
    return out


def _jpeg_data_url(path: Path, *, max_edge: int) -> str | None:
    try:
        from PIL import Image
    except ImportError:
        log.warning("slides vision skipped: pillow missing")
        return None
    try:
        im = Image.open(path)
        im = im.convert("RGB")
        im.thumbnail((max_edge, max_edge))
        buf = __import__("io").BytesIO()
        im.save(buf, format="JPEG", quality=80, optimize=True)
    except (OSError, ValueError) as exc:
        log.warning("slides vision skip %s: %s", path.name, exc)
        return None
    import base64

    b64 = base64.b64encode(buf.getvalue()).decode("ascii")
    return f"data:image/jpeg;base64,{b64}"


def _stem_from_out(out_dir: Path, meta: dict[str, Any]) -> str:
    for art in sorted(out_dir.glob("*.pdf")):
        name = art.name
        if name.endswith("_deck.pdf"):
            continue
        return art.stem
    for art in sorted(out_dir.glob("*.tex")):
        return art.stem
    return str(meta.get("run_id") or out_dir.name)


def run_slides_job(
    run_id: str,
    *,
    root: Path | None = None,
    llm: LLMClient | None = None,
    skip_llm_ir: dict[str, Any] | None = None,
) -> None:
    """Generate deck artifacts under ``runs/out/{run_id}/``. Soft-fail into slides_* meta."""
    root = Path(root) if root is not None else _repo_root()
    out_dir = (root / "runs" / "out" / run_id).resolve()
    logs_dir = root / "runs" / "logs" / run_id
    if not out_dir.is_dir() or not (out_dir / "meta.json").is_file():
        raise FileNotFoundError(f"run out missing: {out_dir}")

    meta = _read_meta(out_dir)
    if meta.get("status") != "ok":
        raise RuntimeError("report run is not ok")

    _set_slides(out_dir, meta, status="running", stage="queued", logs_dir=logs_dir)
    try:
        source, intent = _load_source_and_intent(out_dir, meta)
        (
            chart_ids,
            figure_ids,
            diagram_ids,
            png_by_id,
            diagram_specs,
        ) = collect_run_media(out_dir, meta)
        fj_schema = load_figures_json(out_dir)
        schema_figs = (
            fj_schema.get("figures") if isinstance(fj_schema, dict) else None
        ) or []
        if select_schema_photos(schema_figs, intent):
            try:
                schema_client = llm or LLMClient(LLMConfig.from_env())
                fresh = redraw_attached_schemas(
                    figures=schema_figs,
                    intent=intent,
                    png_by_id=png_by_id,
                    existing_ids=list(diagram_ids),
                    client=schema_client,
                    vision_images=deck_vision_images,
                )
            except (LLMError, LLMConfigError, OSError, RuntimeError, ValueError) as exc:
                log.warning("schema redraw skipped: %s", exc)
                fresh = []
            if fresh and isinstance(fj_schema, dict):
                have = [
                    d
                    for d in (fj_schema.get("diagrams") or [])
                    if isinstance(d, dict)
                ]
                fj_schema["diagrams"] = have + fresh
                (out_dir / "figures.json").write_text(
                    json.dumps(fj_schema, ensure_ascii=False, indent=2),
                    encoding="utf-8",
                )
                meta["slides_schema_redrawn"] = [d["id"] for d in fresh]
                meta["diagrams_planned"] = [
                    str(d.get("id") or "")
                    for d in fj_schema["diagrams"]
                    if isinstance(d, dict) and d.get("id")
                ]
                _write_meta(out_dir, meta, logs_dir)
                (
                    chart_ids,
                    figure_ids,
                    diagram_ids,
                    png_by_id,
                    diagram_specs,
                ) = collect_run_media(out_dir, meta)
                hidden = schema_source_ids(fresh)
                figure_ids = [fid for fid in figure_ids if fid not in hidden]
        palette = normalize_palette_id(str(meta.get("chart_palette") or "atelier"))
        if palette == "auto":
            palette = "atelier"
        from case3.chart_style import palette_from_intent

        parsed = palette_from_intent(intent)
        if parsed and parsed != "auto":
            palette = parsed

        # Deck theme (Julius parity) — does not mutate report chart_palette.
        style_meta = meta.get("slides_style") if isinstance(meta.get("slides_style"), dict) else {}
        theme_pack_raw = str(
            style_meta.get("theme_pack")
            or meta.get("slides_theme_pack")
            or "atelier"
        )
        style_settings = style_meta.get("style_settings")
        if not isinstance(style_settings, dict):
            style_settings = None
        structure_id = str(
            style_meta.get("structure_id")
            or meta.get("slides_structure_id")
            or ""
        ).strip() or None
        # Freeform: infer beat plan (+ pack hint). Structured: plan from template arc.
        raw_target = meta.get("slides_target")
        try:
            slide_target = int(raw_target) if raw_target is not None else None
        except (TypeError, ValueError):
            slide_target = None
        slides_source = slides_source_text(source)
        code_notes = code_highlights(source)
        if slides_source != source:
            log.info(
                "slides source brief %d chars from %d",
                len(slides_source),
                len(source),
            )
        beat_plan = plan_beats(
            source=slides_source,
            intent=intent,
            chart_ids=chart_ids,
            figure_ids=figure_ids,
            diagram_ids=diagram_ids,
            structure_id=structure_id,
            target_slides=slide_target,
        )
        # Pack is "explicit" when UI chose a non-default pack, custom hex, or flag.
        chosen = normalize_pack_id(theme_pack_raw)
        pack_explicit = bool(
            meta.get("slides_pack_explicit")
            or style_meta.get("pack_explicit")
            or style_settings
            or (style_meta.get("theme_pack") and chosen != "atelier")
        )
        theme_pack = maybe_apply_pack_hint(
            structure_id=structure_id,
            current_pack=theme_pack_raw,
            plan=beat_plan,
            pack_explicit=pack_explicit,
        )
        theme_tokens = resolve_deck_theme(theme_pack, style_settings=style_settings)
        beat_overlay = format_beat_overlay(beat_plan)
        meta["slides_beat"] = {
            "mode": beat_plan.mode,
            "pack_hint": beat_plan.pack_hint,
            "pack_applied": theme_tokens.pack_id,
            "from_structure": beat_plan.from_structure,
            "beats": list(beat_plan.beats),
            "rationale": beat_plan.rationale,
        }

        allowed_media = frozenset(chart_ids + figure_ids + diagram_ids)
        from case3.fact_ground import fact_number_tokens

        # Chart JSON can repeat a number the model copied from chat memory.
        # Only Source and the user's own message license a digit on a slide.
        allowed_numbers = fact_number_tokens(source, intent or "")
        locked_arc = list(beat_plan.beats) if beat_plan.from_structure else None

        def _bound(deck: dict[str, Any]) -> dict[str, Any]:
            from case3.fact_ground import bind_deck_numbers

            return bind_deck_numbers(deck, source=source, intent=intent or "")

        _set_slides(out_dir, meta, status="running", stage="llm", logs_dir=logs_dir)
        if skip_llm_ir is not None:
            raw_ir = skip_llm_ir
            deck = _bound(
                parse_deck_ir(
                    raw_ir,
                    source=source,
                    allowed_media_ids=allowed_media,
                    allowed_number_strings=allowed_numbers,
                    locked_arc=locked_arc,
                )
            )
        else:
            system = load_slides_system_prompt(
                palette=palette,
                chart_ids=chart_ids,
                figure_ids=figure_ids,
                diagram_ids=diagram_ids,
                intent=intent,
                source=slides_source,
                media_catalog=_media_catalog_block(out_dir),
                theme_pack=theme_tokens.pack_id,
                structure_id=structure_id,
                beat_overlay=beat_overlay,
            )
            allowed_preview = ", ".join(sorted(allowed_numbers)[:60]) or "(none from charts)"
            if beat_plan.from_structure:
                user = (
                    "Build the executive deck JSON now. "
                    "The BEAT PLAN is the locked skeleton of the chosen template. "
                    "Fill those layouts in that order. "
                    "Drop a beat when Source has no fact for it. "
                    "Do not replace a chart, table, scorecard, compare, quote, "
                    "stat, or card row with a bullet list. "
                    f"Target {beat_plan.target_slides} slides. "
                )
            else:
                user = (
                    "Build the executive deck JSON now. "
                    "Choose layouts from the BEAT PLAN menu by what Source can fill. "
                    "Do not follow a theme script. "
                    f"Target {beat_plan.target_slides} slides. "
                )
            user += (
                "If Source lacks distinct facts, emit fewer (still title … closing) — "
                "do not invent numbers or repeat the same claim. "
                + (
                    ""
                    if beat_plan.from_structure
                    else "Keep ≥5 distinct layouts when ≥8 slides. "
                )
                + "Use available chart/figure/diagram ids only. "
                "Numbers only from Source or this allowed token list "
                f"(the user's own message, not the chat memory): {allowed_preview}. "
                "Do not invent decimals. "
                "If images are attached, look at them: logo wordmark and UI labels "
                "only if they are visible. "
                + (
                    f"If user photos are in Available figures ({', '.join(f for f in figure_ids if f.startswith('usr_'))}), "
                    "you MUST place each photo on a slide using layout 'media_hero' or 'media_split' with "
                    "media_id matching the photo id, with a clear, descriptive Russian title and caption based on what is shown on the photo. "
                    "Use each photo at most once. "
                    if any(f.startswith("usr_") for f in figure_ids)
                    else ""
                )
                + (
                    "CODE HIGHLIGHTS are required callout slides: term is the name, "
                    "definition is that single line. Do not paste the rest of a listing. "
                    if code_notes
                    else ""
                )
                + "Return only the JSON object."
            )
            vision = deck_vision_images(png_by_id, figure_ids)
            if vision:
                log.info("slides vision images=%s", [mid for mid, _ in vision])
            client = llm or LLMClient(LLMConfig.from_env())

            def _parse_or_scrub(raw_ir: dict[str, Any]) -> dict[str, Any]:
                from case3.slides_ir import scrub_unavailable_media

                if isinstance(raw_ir, dict) and raw_ir.get("status") == "insufficient_data":
                    from case3.input_validation import InsufficientDataError

                    msg = str(raw_ir.get("message") or "В запросе недостаточно конкретных данных для презентации.")
                    raise InsufficientDataError(msg)

                try:
                    return _bound(
                        parse_deck_ir(
                            raw_ir,
                            source=source,
                            allowed_media_ids=allowed_media,
                            allowed_number_strings=allowed_numbers,
                            locked_arc=locked_arc,
                        )
                    )
                except DeckIrError as err:
                    # Digits scrub + demote chart/media slides with no PNG
                    # (Playwright timeout on Win left cht_* planned but unavailable).
                    healed = scrub_invented_numbers(
                        raw_ir,
                        source=source,
                        allowed_number_strings=allowed_numbers,
                    )
                    healed = scrub_unavailable_media(
                        healed, allowed_media_ids=allowed_media
                    )
                    try:
                        deck_h = _bound(
                            parse_deck_ir(
                                healed,
                                source=source,
                                allowed_media_ids=allowed_media,
                                allowed_number_strings=allowed_numbers,
                                locked_arc=locked_arc,
                            )
                        )
                    except DeckIrError as scrub_err:
                        # Prefer the post-scrub error (chart_id after number heal).
                        raise scrub_err from err
                    meta["slides_number_scrub"] = True
                    if not allowed_media:
                        meta["slides_media_scrub"] = True
                    log.warning("deck IR reject healed by scrub: %s", err)
                    return deck_h

            def _cancel() -> None:
                raise_if_cancelled(out_dir)

            raw_text = client.complete(
                system=system,
                user_text=user,
                reasoning="off",
                cancel_check=_cancel,
                images=vision,
            )
            try:
                raw_ir = _extract_json_object(raw_text)
                deck = _parse_or_scrub(raw_ir)
            except DeckIrError as first_err:
                log.warning("deck IR rejected, retrying once: %s", first_err)
                _set_slides(
                    out_dir,
                    meta,
                    status="running",
                    stage="llm_retry",
                    logs_dir=logs_dir,
                )
                retry_user = _retry_user(user, str(first_err), allowed_preview)
                raw_text = client.complete(
                    system=system,
                    user_text=retry_user,
                    reasoning="off",
                    cancel_check=_cancel,
                    images=vision,
                )
                raw_ir = _extract_json_object(raw_text)
                deck = _parse_or_scrub(raw_ir)
        code_ids = ensure_code_callouts(deck, code_notes)
        if code_ids:
            meta["slides_code_callouts"] = code_ids
            log.info("slides: code callouts %s", code_ids)
        # Freeze theme into IR (overwrite any LLM paint fields).
        deck["theme_id"] = theme_tokens.pack_id
        deck["style"] = theme_tokens.as_dict()
        deck["palette"] = palette

        # Every native-eligible cht_* with a PNG must appear (skip failed renders).
        fj_early = load_figures_json(out_dir)
        attach_series_ir_to_charts(fj_early.get("charts") if isinstance(fj_early, dict) else None)
        series_all = series_map_from_figures(fj_early if isinstance(fj_early, dict) else {})
        series_all = {k: v for k, v in series_all.items() if k in png_by_id}
        chart_titles = {
            str(ch.get("id") or ""): str(ch.get("caption") or ch.get("title") or "").strip()
            for ch in (fj_early.get("charts") or [])
            if isinstance(ch, dict) and ch.get("id")
        }
        injected = ensure_deck_charts(deck, series_all, titles=chart_titles)
        if injected:
            meta["slides_chart_injected"] = injected
            log.info("slides: injected chart_hero for %s", injected)
        hidden_sources = schema_source_ids(
            fj_early.get("diagrams") if isinstance(fj_early, dict) else []
        )
        photos = [
            fig
            for fig in (fj_early.get("figures") or [])
            if isinstance(fig, dict)
            and str(fig.get("id") or "") in png_by_id
            and str(fig.get("id") or "") not in hidden_sources
        ]
        photo_ids = ensure_deck_photos(deck, photos)
        dia_ids = ensure_deck_diagrams(
            deck,
            [
                d
                for d in ((fj_early.get("diagrams") if isinstance(fj_early, dict) else None) or [])
                if isinstance(d, dict)
            ],
        )
        if dia_ids:
            meta["slides_diagram_injected"] = dia_ids
            log.info("slides: placed diagrams %s", dia_ids)
        if photo_ids:
            meta["slides_photo_injected"] = photo_ids
            log.info("slides: placed photos %s", photo_ids)
            fj_path = out_dir / "figures.json"
            if fj_path.is_file() and isinstance(fj_early, dict):
                fj_path.write_text(
                    json.dumps(fj_early, ensure_ascii=False, indent=2),
                    encoding="utf-8",
                )

        _materialize_deck_artifacts(
            out_dir,
            meta,
            deck=deck,
            palette=palette,
            chart_ids=chart_ids,
            png_by_id=png_by_id,
            diagram_specs=diagram_specs,
            logs_dir=logs_dir,
        )
        log.info(
            "slides ok run_id=%s slides=%s",
            run_id,
            (meta.get("slides_artifacts") or {}).get("png_count"),
        )
    except RunCancelled:
        log.info("slides cancelled run_id=%s", run_id)
        meta = _read_meta(out_dir)
        _set_slides(
            out_dir,
            meta,
            status="cancelled",
            stage="cancelled",
            error="Остановлено",
            logs_dir=logs_dir,
        )
    except InsufficientDataError as exc:
        log.info("slides model refused with insufficient_data run_id=%s: %s", run_id, exc.message)
        meta = _read_meta(out_dir)
        meta["insufficient_data"] = True
        meta["slides_status"] = "ok"
        meta["slides_stage"] = "ok"
        meta["slides_artifacts"] = {}
        meta["chat_summary"] = exc.message
        meta.pop("slides_stage_detail", None)
        _set_slides(out_dir, meta, status="ok", stage="ok", logs_dir=logs_dir)
        (out_dir / "chat_summary.txt").write_text(exc.message, encoding="utf-8")
        EVENTS.publish_stage(run_id, "ok", detail="Недостаточно данных", scope="slides")
        EVENTS.publish_terminal(run_id, "ok", recap={"headline": "Недостаточно данных", "body": exc.message})
    except (DeckIrError, LLMError, LLMConfigError, OSError, RuntimeError, ValueError) as exc:
        log.exception("slides failed run_id=%s", run_id)
        meta = _read_meta(out_dir)
        _set_slides(
            out_dir,
            meta,
            status="error",
            stage="error",
            error=str(exc),
            logs_dir=logs_dir,
        )


def _chart_ids_in_deck(deck: dict[str, Any]) -> set[str]:
    out: set[str] = set()
    for s in deck.get("slides") or []:
        if not isinstance(s, dict):
            continue
        for key in ("chart_id", "media_id"):
            mid = str(s.get(key) or "").strip()
            if mid.startswith("cht_"):
                out.add(mid)
    return out


def _recolor_deck_charts(
    out_dir: Path,
    deck: dict[str, Any],
    *,
    slides_dir: Path,
) -> dict[str, Path]:
    """Re-render deck-referenced charts with pack ``chart_series`` colors.

    Report figures/ stay untouched; deck copies live under ``slides/charts/``.
    """
    style = deck.get("style") if isinstance(deck.get("style"), dict) else {}
    series = [
        str(x)
        for x in (style.get("chart_series") or [])
        if str(x).strip()
    ]
    if not series:
        return {}
    colors = style.get("colors") if isinstance(style.get("colors"), dict) else {}
    muted = str(colors.get("muted") or "") or None
    motif = style.get("motif") if isinstance(style.get("motif"), dict) else {}
    pack = str(style.get("pack_id") or deck.get("theme_id") or "")
    dark = pack in ("signal", "ink", "voltage", "botanical") or str(
        motif.get("atmosphere") or ""
    ) == "dark"
    foil = str(colors.get("foil") or colors.get("accent") or series[0])
    ink = str(colors.get("ink") or ("#F7F5F0" if dark else "#14161A"))
    bg = str(colors.get("paper") or colors.get("sheet") or ("#161618" if dark else "#FFFCF7"))
    # Soft area/grid from first series
    fr, fg, fb = (
        int(foil.lstrip("#")[0:2], 16),
        int(foil.lstrip("#")[2:4], 16),
        int(foil.lstrip("#")[4:6], 16),
    )
    area = f"rgba({fr},{fg},{fb},0.28)"
    grid = (
        "rgba(255,255,255,0.10)" if dark else f"rgba({fr},{fg},{fb},0.12)"
    )

    needed = _chart_ids_in_deck(deck)
    if not needed:
        return {}
    fj = load_figures_json(out_dir)
    html_by_id: dict[str, str] = {}
    type_by_id: dict[str, str] = {}
    for ch in fj.get("charts") or []:
        if not isinstance(ch, dict):
            continue
        cid = str(ch.get("id") or "").strip()
        if cid in needed and str(ch.get("html") or "").strip():
            html_by_id[cid] = str(ch.get("html") or "")
            type_by_id[cid] = str(ch.get("type") or "").strip().lower()

    from case3.chart_style import palette_color_list

    user_series: dict[str, list[str]] = {}
    for ch in fj.get("charts") or []:
        if not isinstance(ch, dict) or not ch.get("style_user"):
            continue
        cid = str(ch.get("id") or "").strip()
        cols = palette_color_list(str(ch.get("palette") or ""))
        if cid and len(cols) >= 2:
            user_series[cid] = cols

    dest_dir = slides_dir / "charts"
    dest_dir.mkdir(parents=True, exist_ok=True)
    work_root = slides_dir / "chart_work"
    work_root.mkdir(parents=True, exist_ok=True)
    out_map: dict[str, Path] = {}
    batch_items: list[tuple[str, dict[str, Any], Path, Path]] = []
    for cid, html in html_by_id.items():
        try:
            use = user_series.get(cid) or series
            remapped = apply_hex_series_to_html(
                sanitize_chart_html(html),
                use,
                muted=muted,
                area=area,
                grid=grid,
            )
            # Twin ≈ native: per-category colors on single-series bar/donut.
            remapped = apply_pack_category_colors_to_html(
                remapped,
                use,
                chart_type=type_by_id.get(cid) or None,
            )
            if dark:
                remapped = re.sub(
                    r"(?<!background)(?<!border)color\s*:\s*['\"]#[0-9A-Fa-f]{3,6}['\"]",
                    f"color:'{ink}'",
                    remapped,
                    flags=re.I,
                )
                muted_ink = muted or ink
                remapped = (
                    f"<style>html,body,#mount{{background:{bg}!important;"
                    f"color:{ink}!important;"
                    f"--chart-ink:{ink}!important;"
                    f"--chart-accent:{foil}!important;"
                    f"--chart-muted:{muted_ink}!important;"
                    f"--kpi-value:{foil}!important;"
                    f"--kpi-label:{muted_ink}!important;"
                    f"--kpi-ink:{ink}!important}}</style>"
                    f"<script>if(window.Chart){{Chart.defaults.color='{ink}';"
                    f"Chart.defaults.scale.grid.color='{grid}';"
                    f"Chart.defaults.scale.border.color='{grid}';}}</script>"
                    + remapped
                )
            else:
                muted_ink = muted or "#64748B"
                remapped = (
                    f"<style>#mount{{--chart-ink:{ink};"
                    f"--chart-accent:{foil};"
                    f"--chart-muted:{muted_ink};"
                    f"--kpi-value:{foil};"
                    f"--kpi-label:{muted_ink};"
                    f"--kpi-ink:{ink}}}</style>"
                    f"<script>if(window.Chart){{Chart.defaults.color='{ink}';"
                    f"Chart.defaults.scale.grid.color='{grid}';}}</script>"
                    + remapped
                )
            dest = dest_dir / f"{cid}.png"
            batch_items.append((cid, {"html": remapped}, dest, work_root / cid))
        except (OSError, RuntimeError, ValueError) as exc:
            log.warning("deck chart recolor skipped %s: %s", cid, exc)

    if batch_items:
        if render_chart_png is not _DEFAULT_RENDER_CHART_PNG:
            for cid, chart_obj, dest, cdir in batch_items:
                try:
                    render_chart_png(chart_obj, dest, work_dir=cdir)
                    if dest.is_file():
                        out_map[cid] = dest
                        log.info("deck chart recolor ok %s → %s", cid, dest.name)
                except (OSError, RuntimeError, ValueError) as exc:
                    log.warning("deck chart recolor skipped %s: %s", cid, exc)
        else:
            batch_res = render_charts_batch(batch_items)
            for cid, _chart_obj, dest, _cdir in batch_items:
                if batch_res.get(cid, {}).get("ok") and dest.is_file():
                    out_map[cid] = dest
                    log.info("deck chart recolor ok %s → %s", cid, dest.name)
    return out_map


def _materialize_deck_artifacts(
    out_dir: Path,
    meta: dict[str, Any],
    *,
    deck: dict[str, Any],
    palette: str,
    chart_ids: list[str],
    png_by_id: dict[str, Path],
    diagram_specs: dict[str, dict[str, str]] | None,
    logs_dir: Path | None,
) -> None:
    """Write deck.json + PNG twin + native PPTX + deck PDF."""
    slides_dir = out_dir / "slides"
    slides_dir.mkdir(parents=True, exist_ok=True)
    (slides_dir / "deck.json").write_text(
        json.dumps(deck, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    needed_dias: set[str] = set()
    for s in deck.get("slides") or []:
        if not isinstance(s, dict):
            continue
        if s.get("layout") in ("media_hero", "media_split"):
            mid = str(s.get("media_id") or "")
            if mid.startswith("dia_"):
                needed_dias.add(mid)

    _set_slides(out_dir, meta, status="running", stage="diagrams", logs_dir=logs_dir)
    media_map = dict(png_by_id)
    if needed_dias:
        style_dict = deck.get("style") if isinstance(deck.get("style"), dict) else {}
        pack_for_dia = str(
            style_dict.get("pack_id") or deck.get("theme_id") or ""
        ).strip() or None
        series_for_dia = [
            str(x)
            for x in (style_dict.get("chart_series") or [])
            if str(x).strip()
        ]
        dia_pngs = ensure_diagram_pngs(
            diagram_specs or {},
            dest_dir=slides_dir / "diagrams",
            palette=palette,
            needed_ids=needed_dias,
            series=series_for_dia or None,
            theme_pack=pack_for_dia,
        )
        media_map.update(dia_pngs)

    _set_slides(out_dir, meta, status="running", stage="charts", logs_dir=logs_dir)
    try:
        media_map.update(_recolor_deck_charts(out_dir, deck, slides_dir=slides_dir))
    except (OSError, RuntimeError, ValueError) as exc:
        log.warning("deck chart recolor batch failed: %s", exc)

    _set_slides(out_dir, meta, status="running", stage="render", logs_dir=logs_dir)
    raise_if_cancelled(out_dir)
    work_root = slides_dir / "work"
    pngs = render_deck_pngs(
        deck,
        work_root=work_root,
        out_dir=slides_dir,
        media_png_by_id=media_map,
        diagrams_by_id=diagram_specs,
    )
    if not pngs:
        raise RuntimeError("no slide PNGs produced")

    _set_slides(out_dir, meta, status="running", stage="pptx", logs_dir=logs_dir)
    raise_if_cancelled(out_dir)
    stem = _stem_from_out(out_dir, meta)
    pptx_path = out_dir / f"{stem}_slides.pptx"
    pdf_path = out_dir / f"{stem}_deck.pdf"
    tmp_pptx = out_dir / f".{stem}_slides.pptx.tmp"
    tmp_pdf = out_dir / f".{stem}_deck.pdf.tmp"
    fj = load_figures_json(out_dir)
    if isinstance(fj, dict):
        attach_series_ir_to_charts(fj.get("charts"))
        # Keep figures.json series in sync for Liber re-exports / edits.
        fj_path = out_dir / "figures.json"
        try:
            fj_path.write_text(
                json.dumps(fj, ensure_ascii=False, indent=2), encoding="utf-8"
            )
        except OSError:
            pass
    # Every cht_* referenced by the deck must resolve series when possible.
    needed = set(chart_ids) | _chart_ids_in_deck(deck)
    chart_series: dict[str, dict[str, Any]] = {}
    for cid in sorted(needed):
        ir = series_from_figures_json(fj if isinstance(fj, dict) else {}, cid)
        if ir:
            chart_series[cid] = ir
    # Also pull any leftover eligible charts (ensure path / multi-ref).
    for cid, ir in series_map_from_figures(
        fj if isinstance(fj, dict) else {}
    ).items():
        chart_series.setdefault(cid, ir)
    # Drop series not on deck slides — avoid unused chart parts; keep only needed.
    chart_series = {cid: ir for cid, ir in chart_series.items() if cid in needed}
    missing = sorted(needed - set(chart_series))
    if missing:
        log.warning(
            "native chart series missing for %s — those slides fall back to PNG",
            missing,
        )
    from case3.chart_style import palette_color_list

    series_hex_by_id: dict[str, list[str]] = {}
    for ch in (fj.get("charts") if isinstance(fj, dict) else []) or []:
        if not isinstance(ch, dict) or not ch.get("style_user"):
            continue
        cid = str(ch.get("id") or "").strip()
        cols = palette_color_list(str(ch.get("palette") or ""))
        if cid in needed and len(cols) >= 2:
            series_hex_by_id[cid] = cols

    diagrams_by_id: dict[str, dict[str, Any]] = {}
    for d in (fj.get("diagrams") if isinstance(fj, dict) else []) or []:
        if isinstance(d, dict) and d.get("id"):
            diagrams_by_id[str(d["id"]).strip()] = d

    build_native_pptx(
        deck,
        tmp_pptx,
        media_by_id=media_map,
        chart_series_by_id=chart_series,
        series_hex_by_id=series_hex_by_id,
        diagrams_by_id=diagrams_by_id,
    )
    meta["slides_native_charts"] = sorted(chart_series.keys())

    raise_if_cancelled(out_dir)
    # Julius path: LO-convert native PPTX → PDF; PNG stitch if soffice missing.
    _, pdf_mode = write_deck_pdf(tmp_pptx, pngs, tmp_pdf)
    actual_pptx = _safe_replace_artifact(tmp_pptx, pptx_path)
    actual_pdf = _safe_replace_artifact(tmp_pdf, pdf_path)

    meta["slides_artifacts"] = {
        "pptx": actual_pptx.name,
        "deck_pdf": actual_pdf.name,
        "deck_pdf_mode": pdf_mode,
        "ir": "slides/deck.json",
        "png_count": len(pngs),
    }
    _set_slides(out_dir, meta, status="ok", stage="ok", logs_dir=logs_dir)


def _safe_replace_artifact(src: Path, dest: Path) -> Path:
    """Atomically replace dest with src, with Windows retry & fallback on PermissionError."""
    import time

    for attempt in range(4):
        try:
            src.replace(dest)
            return dest
        except PermissionError as exc:
            if attempt < 3:
                time.sleep(0.3 * (2**attempt))
                continue
            log.warning(
                "cannot overwrite %s (file locked/open on Windows): %s",
                dest.name,
                exc,
            )
            fallback = dest.with_name(f"{dest.stem}_v{int(time.time())}{dest.suffix}")
            try:
                src.replace(fallback)
                log.info("saved locked slide artifact to fallback %s", fallback.name)
                return fallback
            except Exception:
                raise exc
    return dest


def rebuild_slides_from_deck(
    run_id: str,
    deck: dict[str, Any],
    *,
    root: Path | None = None,
    preserve_structure: bool = False,
) -> dict[str, Any]:
    """Re-render PPTX + twin PNGs/PDF from an already-validated deck IR (no LLM)."""
    root = Path(root) if root is not None else _repo_root()
    out_dir = (root / "runs" / "out" / run_id).resolve()
    logs_dir = root / "runs" / "logs" / run_id
    meta = _read_meta(out_dir)
    if meta.get("status") != "ok":
        raise RuntimeError("report run is not ok")
    (
        chart_ids,
        _figure_ids,
        _diagram_ids,
        png_by_id,
        diagram_specs,
    ) = collect_run_media(out_dir, meta)
    fj_rebuild = load_figures_json(out_dir)
    if isinstance(fj_rebuild, dict):
        chart_titles = {
            str(ch.get("id") or ""): str(ch.get("caption") or ch.get("title") or "").strip()
            for ch in (fj_rebuild.get("charts") or [])
            if isinstance(ch, dict) and ch.get("id")
        }
        ensure_deck_charts(deck, {}, titles=chart_titles)
        if not preserve_structure:
            hidden_sources = schema_source_ids(fj_rebuild.get("diagrams") or [])
            photo_ids = ensure_deck_photos(
                deck,
                [
                    fig
                    for fig in (fj_rebuild.get("figures") or [])
                    if isinstance(fig, dict)
                    and str(fig.get("id") or "") in png_by_id
                    and str(fig.get("id") or "") not in hidden_sources
                ],
            )
            ensure_deck_diagrams(
                deck,
                [d for d in (fj_rebuild.get("diagrams") or []) if isinstance(d, dict)],
            )
            if photo_ids:
                meta["slides_photo_injected"] = photo_ids
    palette = normalize_palette_id(str(meta.get("chart_palette") or "atelier"))
    if palette == "auto":
        palette = "atelier"
    # Keep frozen style from deck if present.
    if not isinstance(deck.get("style"), dict):
        style_meta = meta.get("slides_style") if isinstance(meta.get("slides_style"), dict) else {}
        theme_tokens = resolve_deck_theme(
            str(style_meta.get("theme_pack") or "atelier"),
            style_settings=style_meta.get("style_settings")
            if isinstance(style_meta.get("style_settings"), dict)
            else None,
        )
        deck = dict(deck)
        deck["theme_id"] = theme_tokens.pack_id
        deck["style"] = theme_tokens.as_dict()
    try:
        _materialize_deck_artifacts(
            out_dir,
            meta,
            deck=deck,
            palette=palette,
            chart_ids=chart_ids,
            png_by_id=png_by_id,
            diagram_specs=diagram_specs,
            logs_dir=logs_dir,
        )
    except RunCancelled:
        meta = _read_meta(out_dir)
        _set_slides(
            out_dir,
            meta,
            status="cancelled",
            stage="cancelled",
            error="Остановлено",
            logs_dir=logs_dir,
        )
        raise
    return _read_meta(out_dir)
