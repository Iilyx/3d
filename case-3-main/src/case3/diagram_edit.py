"""Edit / regenerate Liber Mermaid diagrams in an existing run (UI-only)."""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Any, Protocol

from case3.diagram_repair import parse_repair_response, repair_diagrams
from case3.diagram_style import format_diagram_color_prompt
from case3.diagrams import DIAGRAM_TYPES, parse_diagrams, sanitize_mermaid
from case3.diagrams import DiagramError

log = logging.getLogger("case3.diagram_edit")

_ID_OK = re.compile(r"^[a-z][a-z0-9_]{0,31}$")


class DiagramEditError(RuntimeError):
    pass


class _Completer(Protocol):
    def complete(
        self, *, system: str, user_text: str, reasoning: str | None = None
    ) -> str: ...


def _load_fj(out_dir: Path) -> dict[str, Any]:
    path = out_dir / "figures.json"
    if not path.is_file():
        raise DiagramEditError("figures.json missing")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise DiagramEditError(f"figures.json unreadable: {exc}") from exc
    if not isinstance(data, dict):
        raise DiagramEditError("figures.json invalid")
    return data


def _save_fj(out_dir: Path, data: dict[str, Any]) -> None:
    path = out_dir / "figures.json"
    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _load_meta(out_dir: Path) -> dict[str, Any]:
    path = out_dir / "meta.json"
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def _sync_diagram_slide(out_dir: Path, diagram_id: str, title: str) -> None:
    """Copy the saved diagram title onto the deck slide that shows it."""
    label = (title or "").strip()
    if not label:
        return
    path = out_dir / "slides" / "deck.json"
    if not path.is_file():
        return
    try:
        deck = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return
    slides = deck.get("slides") if isinstance(deck, dict) else None
    if not isinstance(slides, list):
        return
    changed = False
    for slide in slides:
        if not isinstance(slide, dict):
            continue
        if str(slide.get("media_id") or "") != diagram_id:
            continue
        slide["title"] = label[:80]
        slide["caption"] = label[:120]
        changed = True
    if changed:
        path.write_text(
            json.dumps(deck, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )


def edit_diagram_in_run(
    out_dir: Path,
    diagram_id: str,
    *,
    mermaid: str,
    title: str | None = None,
    formats: set[str] | None = None,
) -> dict[str, Any]:
    """Replace one diagram's mermaid/title in figures.json, re-render PNG, and sync slides/docs."""
    out_dir = out_dir.resolve()
    did = (diagram_id or "").strip()
    if not _ID_OK.match(did):
        raise DiagramEditError("invalid diagram id")
    from case3.run_undo import capture_before_edit

    capture_before_edit(out_dir, kind="diagram", target=did)
    fj = _load_fj(out_dir)
    diagrams = list(fj.get("diagrams") or [])
    idx = next(
        (
            i
            for i, d in enumerate(diagrams)
            if isinstance(d, dict) and str(d.get("id") or "") == did
        ),
        None,
    )
    if idx is None:
        raise DiagramEditError(f"diagram {did!r} not found")
    item = dict(diagrams[idx])
    dtype = str(item.get("type") or "flowchart").strip() or "flowchart"
    try:
        clean = sanitize_mermaid(mermaid)
    except DiagramError as exc:
        raise DiagramEditError(str(exc)) from exc
    # Re-validate via parse_diagrams
    parsed = parse_diagrams(
        [
            {
                "id": did,
                "title": (title if title is not None else item.get("title") or did),
                "type": dtype if dtype in DIAGRAM_TYPES else "flowchart",
                "mermaid": clean,
            }
        ],
        max_diagrams=1,
    )
    if not parsed:
        raise DiagramEditError("mermaid failed validation (type/header)")
    diagrams[idx] = parsed[0]
    fj["diagrams"] = diagrams
    _save_fj(out_dir, fj)
    _sync_diagram_slide(out_dir, did, str(parsed[0].get("title") or ""))

    # Re-render PNG in figures/ for PDF/DOCX reports
    figs_dir = out_dir / "figures"
    dest_png = figs_dir / f"{did}.png"
    meta = _load_meta(out_dir)
    palette = str(meta.get("chart_palette") or meta.get("image_style_pack") or "atelier")
    png_rendered = False
    try:
        from case3.slides_media import render_mermaid_png

        render_mermaid_png(
            mermaid=clean,
            dest=dest_png,
            palette=palette,
            theme_pack=palette,
        )
        png_rendered = dest_png.is_file() and dest_png.stat().st_size > 0
    except Exception:
        log.warning("failed to re-render PNG for diagram %s", did, exc_info=True)

    meta_path = out_dir / "meta.json"
    if meta_path.is_file() and png_rendered:
        from case3.run_meta import update_meta

        def _mut_dia_edit(m: dict[str, Any]) -> None:
            med = dict(m.get("media_status") or {})
            med[did] = {"ok": True, "path": str(dest_png), "kind": "diagram"}
            m["media_status"] = med

        update_meta(out_dir, _mut_dia_edit)

    artifacts: dict[str, str] = {}
    if formats:
        from case3.run_rebuild import rebuild_run_docs

        art_paths = rebuild_run_docs(out_dir, formats=formats)
        artifacts = {k: str(p) for k, p in art_paths.items()}

    from case3.run_undo import undo_meta

    out = dict(parsed[0])
    out["undo"] = undo_meta(out_dir)
    if artifacts:
        out["artifacts"] = artifacts
    if png_rendered:
        out["version"] = int(dest_png.stat().st_mtime)
    from case3.deck_refresh import refresh_deck_from_ir

    refresh_deck_from_ir(out_dir)
    return out


def _load_generate_system(*, max_diagrams: int, palette: str) -> str:
    from case3.prompts import load as load_prompt

    return load_prompt(
        "diagram_generate",
        MAX_DIAGRAMS=max_diagrams,
        DIAGRAM_COLOR_TABLE=format_diagram_color_prompt(palette),
    )


def regenerate_diagrams_in_run(
    out_dir: Path,
    *,
    palette: str = "atelier",
    client: _Completer,
    skip_repair: bool = False,
) -> dict[str, Any]:
    """Full LLM regenerate of diagrams[] (+ optional repair). No TeX/PDF."""
    out_dir = out_dir.resolve()
    meta = _load_meta(out_dir)
    source_path = Path(str(meta.get("source") or ""))
    if not source_path.is_file():
        raise DiagramEditError("source file missing for regenerate")
    source = source_path.read_text(encoding="utf-8")
    intent = str(meta.get("intent") or "")
    max_d = int(meta.get("max_diagrams") or 2)
    max_d = max(1, min(max_d, 3))

    system = _load_generate_system(max_diagrams=max_d, palette=palette)
    user = (
        f"## Intent\n{intent.strip() or '(none)'}\n\n"
        f"## Source\n{source[:12000]}\n\n"
    )
    try:
        raw = client.complete(system=system, user_text=user)
    except Exception as exc:
        raise DiagramEditError(f"LLM generate failed: {exc}") from exc

    diagrams = parse_repair_response(raw or "", max_diagrams=max_d)
    if not diagrams:
        raise DiagramEditError("model returned no valid diagrams")

    repaired = False
    if not skip_repair:
        diagrams, rmeta = repair_diagrams(
            diagrams,
            source=source,
            intent=intent,
            max_diagrams=max_d,
            client=client,
            palette=palette,
        )
        repaired = bool(rmeta.get("diagrams_repaired"))

    from case3.run_undo import capture_before_edit, undo_meta

    capture_before_edit(out_dir, kind="diagram_regen", target="*")

    fj = _load_fj(out_dir)
    fj["diagrams_draft"] = fj.get("diagrams")
    fj["diagrams"] = diagrams
    _save_fj(out_dir, fj)

    # Re-render PNGs in figures/ for PDF/DOCX and twin presentation
    figs_dir = out_dir / "figures"
    figs_dir.mkdir(parents=True, exist_ok=True)
    rendered_paths: dict[str, Path] = {}
    for d in diagrams:
        did = str(d.get("id") or "").strip()
        mmd = str(d.get("mermaid") or "").strip()
        if not did or not mmd:
            continue
        dest_png = figs_dir / f"{did}.png"
        try:
            from case3.slides_media import render_mermaid_png

            render_mermaid_png(
                mermaid=mmd,
                dest=dest_png,
                palette=palette,
                theme_pack=palette,
            )
            if dest_png.is_file() and dest_png.stat().st_size > 0:
                rendered_paths[did] = dest_png
        except Exception:
            log.warning("failed to re-render PNG for regenerated diagram %s", did, exc_info=True)

    meta_path = out_dir / "meta.json"
    if meta_path.is_file():
        from case3.run_meta import update_meta

        def _mut_dia_regen(m: dict[str, Any]) -> None:
            m["diagrams_planned"] = [d["id"] for d in diagrams]
            m["diagrams_ok"] = len(diagrams)
            m["diagrams_repaired"] = repaired
            med = dict(m.get("media_status") or {})
            for did, p in rendered_paths.items():
                med[did] = {"ok": True, "path": str(p), "kind": "diagram"}
            m["media_status"] = med

        update_meta(out_dir, _mut_dia_regen)

    from case3.deck_refresh import refresh_deck_from_ir

    refresh_deck_from_ir(out_dir)

    return {
        "diagrams": diagrams,
        "diagrams_repaired": repaired,
        "diagrams_ok": len(diagrams),
        "undo": undo_meta(out_dir),
    }


def _parse_refine_response(raw: str, target_id: str) -> dict[str, Any] | None:
    text = (raw or "").strip()
    if not text:
        return None
    body = text
    m = re.search(r"```(?:json)?\s*\n([\s\S]*?)\n?```", text, re.I)
    if m:
        body = m.group(1).strip()
    else:
        start = text.find("{")
        end = text.rfind("}")
        if start >= 0 and end > start:
            body = text[start : end + 1]
    try:
        data = json.loads(body)
    except json.JSONDecodeError:
        log.warning("diagram_refine: invalid JSON: %s", text[:200])
        return None
    if not isinstance(data, dict):
        return None
    item = None
    if isinstance(data.get("diagram"), dict):
        item = data["diagram"]
    elif isinstance(data.get("diagrams"), list) and data["diagrams"]:
        item = next(
            (
                d
                for d in data["diagrams"]
                if isinstance(d, dict) and str(d.get("id") or "") == target_id
            ),
            data["diagrams"][0],
        )
    elif "mermaid" in data:
        item = data
    if not isinstance(item, dict) or not item.get("mermaid"):
        return None
    item["id"] = target_id
    return item


def refine_diagram_in_run(
    out_dir: Path,
    diagram_id: str,
    *,
    instruction: str,
    client: _Completer,
    palette: str = "atelier",
    formats: set[str] | None = None,
) -> dict[str, Any]:
    """Targeted differential LLM refinement of one diagram in an existing run."""
    out_dir = out_dir.resolve()
    did = (diagram_id or "").strip()
    if not _ID_OK.match(did):
        raise DiagramEditError("invalid diagram id")
    instr = (instruction or "").strip()
    if not instr:
        raise DiagramEditError("укажите, что изменить в схеме")

    fj = _load_fj(out_dir)
    diagrams = list(fj.get("diagrams") or [])
    idx = next(
        (
            i
            for i, d in enumerate(diagrams)
            if isinstance(d, dict) and str(d.get("id") or "") == did
        ),
        None,
    )
    if idx is None:
        raise DiagramEditError(f"diagram {did!r} not found")
    item = dict(diagrams[idx])

    from case3.run_undo import capture_before_edit

    capture_before_edit(out_dir, kind="diagram_refine", target=did)

    meta = _load_meta(out_dir)
    source = ""
    source_path = Path(str(meta.get("source") or ""))
    if source_path.is_file():
        try:
            source = source_path.read_text(encoding="utf-8")
        except OSError:
            pass
    intent = str(meta.get("intent") or "")

    from case3.prompts import load as load_prompt

    system = load_prompt(
        "diagram_refine",
        DIAGRAM_COLOR_TABLE=format_diagram_color_prompt(palette),
    )
    user = (
        f"## User Instruction\n{instr}\n\n"
        f"## Current Diagram to Modify\n"
        f"ID: {did}\n"
        f"Title: {item.get('title') or did}\n"
        f"Type: {item.get('type') or 'flowchart'}\n"
        f"Mermaid:\n{item.get('mermaid') or ''}\n\n"
        f"## Source Context\n{source[:10000] if source else '(none)'}\n\n"
        f"## Intent Context\n{intent if intent else '(none)'}\n"
    )

    try:
        raw = client.complete(system=system, user_text=user)
    except Exception as exc:
        raise DiagramEditError(f"LLM refine failed: {exc}") from exc

    refined = _parse_refine_response(raw or "", did)
    if not refined:
        raise DiagramEditError("модель не вернула валидную схему по инструкции")

    dtype = str(refined.get("type") or item.get("type") or "flowchart").strip() or "flowchart"
    try:
        clean = sanitize_mermaid(str(refined.get("mermaid") or ""))
    except DiagramError as exc:
        raise DiagramEditError(str(exc)) from exc

    parsed = parse_diagrams(
        [
            {
                "id": did,
                "title": str(refined.get("title") or item.get("title") or did),
                "type": dtype if dtype in DIAGRAM_TYPES else "flowchart",
                "mermaid": clean,
            }
        ],
        max_diagrams=1,
    )
    if not parsed:
        raise DiagramEditError("mermaid failed validation after refinement")

    diagrams[idx] = parsed[0]
    fj["diagrams"] = diagrams
    _save_fj(out_dir, fj)
    _sync_diagram_slide(out_dir, did, str(parsed[0].get("title") or ""))

    # Re-render PNG in figures/ for PDF/DOCX
    figs_dir = out_dir / "figures"
    dest_png = figs_dir / f"{did}.png"
    png_rendered = False
    try:
        from case3.slides_media import render_mermaid_png

        render_mermaid_png(
            mermaid=clean,
            dest=dest_png,
            palette=palette,
            theme_pack=palette,
        )
        png_rendered = dest_png.is_file() and dest_png.stat().st_size > 0
    except Exception:
        log.warning("failed to re-render PNG for diagram %s", did, exc_info=True)

    meta_path = out_dir / "meta.json"
    if meta_path.is_file() and png_rendered:
        from case3.run_meta import update_meta

        def _mut_dia_edit(m: dict[str, Any]) -> None:
            med = dict(m.get("media_status") or {})
            med[did] = {"ok": True, "path": str(dest_png), "kind": "diagram"}
            m["media_status"] = med

        update_meta(out_dir, _mut_dia_edit)

    artifacts: dict[str, str] = {}
    if formats:
        from case3.run_rebuild import rebuild_run_docs

        art_paths = rebuild_run_docs(out_dir, formats=formats)
        artifacts = {k: str(p) for k, p in art_paths.items()}

    from case3.run_undo import undo_meta

    out = dict(parsed[0])
    out["undo"] = undo_meta(out_dir)
    if artifacts:
        out["artifacts"] = artifacts
    if png_rendered:
        out["version"] = int(dest_png.stat().st_mtime)
    from case3.deck_refresh import refresh_deck_from_ir

    refresh_deck_from_ir(out_dir)
    return out
