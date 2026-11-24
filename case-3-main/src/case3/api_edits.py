"""Liber edit / chart / diagram routes (mounted on main FastAPI app)."""

from __future__ import annotations

import asyncio
import json
import logging
import re
import time
from functools import partial
from typing import Any, Optional

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel, Field

from case3.chart_edit import (
    ChartEditError,
    ChartNumberChange,
    edit_chart_in_run,
    preview_chart_html,
    recolor_all_charts_in_run,
)
from case3.chart_html import CHART_TYPES
from case3.chart_style import normalize_palette_id
from case3.diagram_edit import (
    DiagramEditError,
    edit_diagram_in_run,
    refine_diagram_in_run,
    regenerate_diagrams_in_run,
)
from case3.figure_edit import FigureEditError, edit_figure_in_run
from case3.llm_client import LLMClient, LLMConfig, LLMConfigError, LLMError
from case3.heading_edit import HeadingEditError, edit_heading_in_run, edit_title_in_run
from case3.list_edit import ListEditError, edit_list_in_run
from case3.paragraph_edit import (
    ParagraphEditError,
    edit_paragraph_in_run,
    insert_paragraph_in_run,
)
from case3.render import RenderError
from case3.table_edit import TableEditError, edit_table_in_run
from case3.run_store import (
    FILE_OK,
    artifact_downloads,
    build_preview_payload,
    diagram_print_formats,
    edit_response_envelope,
    formats_from_edit_body,
    load_diagrams_from_out,
    load_figures_json,
    resolve_run_dir,
)

log = logging.getLogger("case3.api_edits")
router = APIRouter(tags=["edits"])


class ChartEditBody(BaseModel):
    palette: str | None = Field(default=None)
    style: str | None = Field(default="")
    chart_type: str | None = Field(default="")
    formats: str = Field(default="both")
    accepted_html: str | None = Field(default="")


class ChartPreviewBody(BaseModel):
    """Local live preview (palette + type coerce). Style notes deferred to Apply."""

    palette: str | None = Field(default=None)
    chart_type: str | None = Field(default="")


class DiagramEditBody(BaseModel):
    mermaid: str = Field(default="")
    title: str | None = Field(default=None)
    formats: list[str] | None = Field(
        default=None,
        description="Print formats to rebuild (e.g. ['pdf', 'docx']); empty/None skips rebuild",
    )


class DiagramRegenBody(BaseModel):
    palette: str | None = Field(default=None)


class DiagramRefineBody(BaseModel):
    instruction: str = Field(default="")
    palette: str | None = Field(default=None)
    formats: list[str] | None = Field(
        default=None,
        description="Print formats to rebuild (e.g. ['pdf', 'docx']); empty/None skips rebuild",
    )


class FigureEditBody(BaseModel):
    """mode=generate → POST /generate; mode=edit → POST /edit with current PNG."""

    mode: str = Field(default="generate")
    prompt: str = Field(default="")
    caption: str | None = Field(default=None)
    formats: str = Field(default="both")


class FigureEditFormatsBody(BaseModel):
    """Optional formats payload for figure delete (default: rebuild both or none)."""

    formats: str | None = Field(default=None)



class TableEditBody(BaseModel):
    """Structured table replace → patch TeX → rebuild PDF/DOCX."""

    caption: str = Field(default="")
    headers: list[str] = Field(default_factory=list)
    rows: list[list[str]] = Field(default_factory=list)
    formats: str = Field(default="both")


class ParagraphEditBody(BaseModel):
    """Plain prose replace → patch TeX paragraph → rebuild PDF/DOCX."""

    text: str = Field(default="")
    formats: str = Field(default="both")


class ParagraphInsertBody(BaseModel):
    """Insert new prose → patch TeX → rebuild PDF/DOCX."""

    text: str = Field(default="")
    after_paragraph_index: int | None = Field(default=None)
    after_heading_index: int | None = Field(default=None)
    formats: str = Field(default="both")


class HeadingEditBody(BaseModel):
    """Plain title replace → patch TeX section/subsection → rebuild."""

    text: str = Field(default="")
    formats: str = Field(default="both")


class TitleEditBody(BaseModel):
    """Plain title replace → patch TeX \\title → rebuild PDF/DOCX."""

    text: str = Field(default="")
    formats: str = Field(default="both")



class ListEditBody(BaseModel):
    """Replace list items → patch TeX itemize/enumerate → rebuild."""

    items: list[str] = Field(default_factory=list)
    ordered: bool | None = Field(default=None)
    formats: str = Field(default="both")

@router.get("/api/runs/{run_id}/charts/{chart_id}")
def get_run_chart(run_id: str, chart_id: str) -> dict[str, Any]:
    """Chart fragment + meta for Liber live Chart.js (G9/G12)."""
    if not FILE_OK.match(chart_id):
        raise HTTPException(400, detail="invalid chart_id")
    out_dir = resolve_run_dir(run_id)
    fj = load_figures_json(out_dir)
    charts = fj.get("charts") or []
    chart = next(
        (c for c in charts if isinstance(c, dict) and c.get("id") == chart_id),
        None,
    )
    if not chart:
        raise HTTPException(404, detail="chart not found")
    html = str(chart.get("html") or "").strip()
    if not html:
        raise HTTPException(404, detail="chart html missing")
    return {
        "id": chart_id,
        "type": str(chart.get("type") or "").strip(),
        "caption": str(chart.get("caption") or "").strip(),
        "html": html,
    }


@router.post("/api/runs/{run_id}/charts/{chart_id}/preview")
def preview_run_chart(
    run_id: str, chart_id: str, body: ChartPreviewBody
) -> dict[str, Any]:
    """Local palette/type preview — no PNG/PDF write (Apply still commits)."""
    if not FILE_OK.match(chart_id):
        raise HTTPException(400, detail="invalid chart_id")
    out_dir = resolve_run_dir(run_id)
    try:
        return preview_chart_html(
            out_dir,
            chart_id,
            palette=body.palette,
            chart_type=body.chart_type,
        )
    except ChartEditError as exc:
        raise HTTPException(400, detail=str(exc)) from exc


@router.post("/api/runs/{run_id}/diagrams/{diagram_id}/edit")
async def edit_run_diagram(
    run_id: str, diagram_id: str, body: DiagramEditBody
) -> dict[str, Any]:
    """Save edited Mermaid for one Liber diagram, re-render PNG, and optionally rebuild PDF/DOCX."""
    if not FILE_OK.match(diagram_id):
        raise HTTPException(400, detail="invalid diagram_id")
    out_dir = resolve_run_dir(run_id)
    fmt_set = diagram_print_formats(body.formats)
    try:
        diagram = await asyncio.to_thread(
            partial(
                edit_diagram_in_run,
                out_dir,
                diagram_id,
                mermaid=body.mermaid or "",
                title=body.title,
                formats=fmt_set,
            )
        )
    except DiagramEditError as exc:
        raise HTTPException(400, detail=str(exc)) from exc
    except RenderError as exc:
        raise HTTPException(500, detail=str(exc)) from exc
    undo = None
    artifacts = None
    if isinstance(diagram, dict):
        undo = diagram.pop("undo", None)
        artifacts = diagram.pop("artifacts", None)
    res: dict[str, Any] = {
        "diagram": diagram,
        "diagrams": load_diagrams_from_out(out_dir),
        "undo": undo,
    }
    if artifacts:
        res["artifacts"] = artifacts
    return res


@router.post("/api/runs/{run_id}/diagrams/{diagram_id}/refine")
async def refine_run_diagram(
    run_id: str, diagram_id: str, body: DiagramRefineBody
) -> dict[str, Any]:
    """Targeted differential LLM refine for one Liber diagram (AI Copilot)."""
    if not FILE_OK.match(diagram_id):
        raise HTTPException(400, detail="invalid diagram_id")
    instr = (body.instruction or "").strip()
    if not instr:
        raise HTTPException(400, detail="укажите, что изменить в схеме")
    out_dir = resolve_run_dir(run_id)
    meta_path = out_dir / "meta.json"
    run_meta: dict[str, Any] = {}
    if meta_path.is_file():
        try:
            run_meta = json.loads(meta_path.read_text(encoding="utf-8"))
        except OSError:
            pass
    default_palette = str(run_meta.get("chart_palette") or run_meta.get("image_style_pack") or "atelier")
    palette = normalize_palette_id(body.palette or default_palette)
    fmt_set = diagram_print_formats(body.formats)
    try:
        diagram = await asyncio.to_thread(
            partial(
                refine_diagram_in_run,
                out_dir,
                diagram_id,
                instruction=instr,
                client=LLMClient(LLMConfig.from_env()),
                palette=palette,
                formats=fmt_set,
            )
        )
    except DiagramEditError as exc:
        raise HTTPException(400, detail=str(exc)) from exc
    except RenderError as exc:
        raise HTTPException(500, detail=str(exc)) from exc
    except (LLMError, LLMConfigError) as exc:
        raise HTTPException(502, detail=str(exc)) from exc
    undo = None
    artifacts = None
    if isinstance(diagram, dict):
        undo = diagram.pop("undo", None)
        artifacts = diagram.pop("artifacts", None)
    res: dict[str, Any] = {
        "diagram": diagram,
        "diagrams": load_diagrams_from_out(out_dir),
        "undo": undo,
    }
    if artifacts:
        res["artifacts"] = artifacts
    return res


@router.get("/api/runs/{run_id}/diagrams/{diagram_id}/svg")
async def download_diagram_svg(run_id: str, diagram_id: str) -> Response:
    """Mermaid → SVG for Liber schema download (no PNG raster)."""
    from case3.diagram_svg import DiagramSvgError, export_diagram_svg, load_diagram_spec

    if not FILE_OK.match(diagram_id):
        raise HTTPException(400, detail="invalid diagram_id")
    out_dir = resolve_run_dir(run_id)
    try:
        meta = json.loads((out_dir / "meta.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        meta = {}
    palette = normalize_palette_id(str(meta.get("chart_palette") or "atelier"))
    try:
        spec = load_diagram_spec(out_dir, diagram_id)
        svg = await asyncio.to_thread(
            partial(export_diagram_svg, out_dir, diagram_id, palette=palette)
        )
    except DiagramSvgError as exc:
        raise HTTPException(404 if "not found" in str(exc) else 400, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001 — Playwright missing browsers, etc.
        log.exception("diagram svg render failed run_id=%s id=%s", run_id, diagram_id)
        raise HTTPException(
            503, detail=f"svg render unavailable: {exc}"
        ) from exc
    # ASCII-only filename (Starlette headers are latin-1); UTF-8 title → slug fallback
    raw_title = spec.get("title") or diagram_id
    safe = re.sub(r"[^a-zA-Z0-9._-]+", "-", str(raw_title)).strip("-_.")[:48] or diagram_id
    return Response(
        content=svg.encode("utf-8"),
        media_type="image/svg+xml; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="{safe}.svg"',
            "Cache-Control": "no-store",
        },
    )


@router.post("/api/runs/{run_id}/diagrams/regenerate")
async def regenerate_run_diagrams(
    run_id: str, body: DiagramRegenBody | None = None
) -> dict[str, Any]:
    """Full LLM regenerate of diagrams[] (+ repair). No TeX/PDF."""
    out_dir = resolve_run_dir(run_id)
    meta_path = out_dir / "meta.json"
    run_meta: dict[str, Any] = {}
    if meta_path.is_file():
        try:
            run_meta = json.loads(meta_path.read_text(encoding="utf-8"))
        except OSError:
            pass
    default_palette = str(run_meta.get("chart_palette") or run_meta.get("image_style_pack") or "atelier")
    palette = normalize_palette_id((body.palette if body else None) or default_palette)
    try:
        result = await asyncio.to_thread(
            partial(
                regenerate_diagrams_in_run,
                out_dir,
                palette=palette,
                client=LLMClient(LLMConfig.from_env()),
            )
        )
    except DiagramEditError as exc:
        raise HTTPException(400, detail=str(exc)) from exc
    except (LLMError, LLMConfigError) as exc:
        raise HTTPException(502, detail=str(exc)) from exc
    return {
        "diagrams": result.get("diagrams") or load_diagrams_from_out(out_dir),
        "diagrams_repaired": bool(result.get("diagrams_repaired")),
        "diagrams_ok": int(result.get("diagrams_ok") or 0),
        "undo": result.get("undo"),
    }


@router.post("/api/runs/{run_id}/charts/{chart_id}/edit")
async def edit_run_chart(run_id: str, chart_id: str, body: ChartEditBody) -> dict[str, Any]:
    """Restyle one chart in-place and rebuild PDF/DOCX (same PNG path → docs update)."""
    if not FILE_OK.match(chart_id):
        raise HTTPException(400, detail="invalid chart_id")
    out_dir = resolve_run_dir(run_id)
    fmt_set = formats_from_edit_body(body.formats)

    palette = normalize_palette_id(body.palette) if body.palette else None
    style = (body.style or "").strip()
    chart_type = (body.chart_type or "").strip()
    if chart_type and chart_type not in CHART_TYPES:
        raise HTTPException(400, detail=f"unknown chart_type: {chart_type}")
    if (palette == "auto" or (not palette and not style and not chart_type)):
        raise HTTPException(400, detail="укажите палитру, тип или текст «как изменить»")

    try:
        result = await asyncio.to_thread(
            partial(
                edit_chart_in_run,
                out_dir,
                chart_id,
                palette=palette,
                style=style or None,
                chart_type=chart_type or None,
                formats=fmt_set,
                accepted_html=(body.accepted_html or "").strip() or None,
            )
        )
    except ChartNumberChange as exc:
        raise HTTPException(
            409,
            detail={
                "code": "numbers_changed",
                "message": str(exc),
                "html": exc.html,
            },
        ) from exc
    except ChartEditError as exc:
        raise HTTPException(400, detail=str(exc)) from exc
    except (LLMError, LLMConfigError) as exc:
        raise HTTPException(502, detail=str(exc)) from exc
    except RenderError as exc:
        raise HTTPException(500, detail=str(exc)) from exc

    v = int(result.get("version") or 0)
    return edit_response_envelope(
        run_id=run_id,
        out_dir=out_dir,
        result=result,
        bust_needles=(chart_id, "cht_"),
        extra={
            "chart_id": chart_id,
            "mode": result.get("mode"),
            "palette": result.get("palette"),
            "style": result.get("style"),
            "preview_figure": {
                "id": chart_id,
                "kind": "chart",
                "url": f"/api/runs/{run_id}/figures/{chart_id}.png?v={v}",
            },
        },
    )


class BatchRecolorBody(BaseModel):
    palette: str = Field(default="atelier")
    formats: str = Field(default="both")


@router.post("/api/runs/{run_id}/charts/recolor")
async def batch_recolor_charts(run_id: str, body: BatchRecolorBody) -> dict[str, Any]:
    """Recolor all charts in the run to a given palette without LLM re-run."""
    out_dir = resolve_run_dir(run_id)
    fmt_set = formats_from_edit_body(body.formats)
    try:
        result = await asyncio.to_thread(
            partial(
                recolor_all_charts_in_run,
                out_dir,
                palette=body.palette,
                formats=fmt_set,
            )
        )
    except ChartEditError as exc:
        raise HTTPException(400, detail=str(exc)) from exc

    return edit_response_envelope(
        run_id=run_id,
        out_dir=out_dir,
        result=result,
        bust_needles=("cht_",),
        extra={
            "palette": result.get("palette"),
            "charts_recolored": result.get("charts_recolored"),
        },
    )


@router.post("/api/runs/{run_id}/figures/{figure_id}/edit")
async def edit_run_figure(run_id: str, figure_id: str, body: FigureEditBody) -> dict[str, Any]:
    """Regenerate (generate) or img2img-edit one photo; rebuild PDF/DOCX."""
    if not FILE_OK.match(figure_id):
        raise HTTPException(400, detail="invalid figure_id")
    if figure_id.startswith("cht_"):
        raise HTTPException(400, detail="use /charts/{id}/edit for charts")
    out_dir = resolve_run_dir(run_id)

    mode = (body.mode or "generate").strip().lower()
    if mode not in {"generate", "edit"}:
        raise HTTPException(400, detail="mode must be generate|edit")
    prompt = (body.prompt or "").strip()
    if not prompt:
        raise HTTPException(400, detail="prompt required")

    fmt_set = formats_from_edit_body(body.formats)
    caption = (body.caption or "").strip() or None

    try:
        result = await asyncio.to_thread(
            partial(
                edit_figure_in_run,
                out_dir,
                figure_id,
                mode=mode,  # type: ignore[arg-type]
                prompt=prompt,
                caption=caption,
                formats=fmt_set,
            )
        )
    except FigureEditError as exc:
        raise HTTPException(400, detail=str(exc)) from exc
    except RenderError as exc:
        raise HTTPException(500, detail=str(exc)) from exc

    v = int(result.get("version") or 0)
    return edit_response_envelope(
        run_id=run_id,
        out_dir=out_dir,
        result=result,
        bust_needles=(figure_id,),
        extra={
            "figure_id": figure_id,
            "mode": result.get("mode"),
            "prompt": result.get("prompt"),
            "caption": result.get("caption"),
            "preview_figure": {
                "id": figure_id,
                "kind": "figure",
                "url": f"/api/runs/{run_id}/figures/{figure_id}.png?v={v}",
            },
        },
    )


@router.post("/api/runs/{run_id}/figures/{figure_id}/upload")
async def upload_run_figure(
    run_id: str,
    figure_id: str,
    image: Optional[UploadFile] = File(None),
    file: Optional[UploadFile] = File(None),
    caption: str = Form(""),
) -> dict[str, Any]:
    """Replace one photo with an uploaded image file; rebuild PDF/DOCX and deck."""
    if not FILE_OK.match(figure_id):
        raise HTTPException(400, detail="invalid figure_id")
    if figure_id.startswith("cht_"):
        raise HTTPException(400, detail="cannot upload to chart_id")
    upload = image or file
    if upload is None:
        raise HTTPException(422, detail="field 'image' or 'file' required")
    out_dir = resolve_run_dir(run_id)

    raw = await upload.read()
    if not raw:
        raise HTTPException(400, detail="uploaded file is empty")
    from case3.user_photos import _MAX_BYTES

    if len(raw) > _MAX_BYTES:
        raise HTTPException(
            400,
            detail=(
                f"файл слишком большой ({len(raw) // 1024} КБ, "
                f"лимит {_MAX_BYTES // (1024 * 1024)} МБ)"
            ),
        )

    from io import BytesIO
    from PIL import Image
    from starlette.concurrency import run_in_threadpool

    def _process_upload() -> dict[str, Any]:
        try:
            Image.MAX_IMAGE_PIXELS = 36_000_000
            im = Image.open(BytesIO(raw))
            im.load()
        except Exception as exc:
            raise HTTPException(400, detail=f"invalid image file: {exc}") from exc

        figs_dir = out_dir / "figures"
        figs_dir.mkdir(parents=True, exist_ok=True)
        dest = figs_dir / f"{figure_id}.png"

        from case3.run_undo import capture_before_edit

        capture_before_edit(out_dir, kind="figure", target=figure_id)

        if im.mode not in ("RGB", "RGBA"):
            im = im.convert("RGBA" if "transparency" in im.info else "RGB")
        im.save(dest, format="PNG")

        caption_clean = caption.strip() or None
        fj_path = out_dir / "figures.json"
        if fj_path.is_file():
            try:
                fj = json.loads(fj_path.read_text(encoding="utf-8"))
                figures = list(fj.get("figures") or [])
                idx = next(
                    (
                        i
                        for i, f in enumerate(figures)
                        if isinstance(f, dict) and f.get("id") == figure_id
                    ),
                    -1,
                )
                if idx >= 0:
                    fig = dict(figures[idx])
                    if caption_clean:
                        fig["caption"] = caption_clean
                    figures[idx] = fig
                    fj["figures"] = figures
                    fj_path.write_text(
                        json.dumps(fj, ensure_ascii=False, indent=2),
                        encoding="utf-8",
                    )
            except Exception:
                pass

        from case3.run_meta import update_meta

        def _mut_upload(m: dict[str, Any]) -> None:
            med = dict(m.get("media_status") or {})
            med[figure_id] = {"ok": True, "path": str(dest), "kind": "figure"}
            m["media_status"] = med
            m["last_figure_edit"] = {
                "id": figure_id,
                "mode": "upload",
                "caption": caption_clean,
                "ts": int(time.time()),
            }

        meta = update_meta(out_dir, _mut_upload)

        from case3.run_rebuild import rebuild_run_docs

        has_report_tex = any(
            (out_dir / cand).is_file()
            for cand in ("report.tex", "main.tex", f"{out_dir.name}.tex")
        ) or bool(list(out_dir.glob("*.tex")))
        has_print = (out_dir / "report.pdf").is_file() or (out_dir / "report.docx").is_file()
        rebuild_fmts = {"pdf", "docx"} if (has_report_tex and has_print) else {"none"}
        try:
            artifacts = rebuild_run_docs(out_dir, formats=rebuild_fmts)
        except Exception:
            artifacts = {}

        from case3.deck_refresh import refresh_deck_from_ir

        refresh_deck_from_ir(out_dir)

        v = int(dest.stat().st_mtime)
        from case3.run_undo import undo_meta

        result = {
            "figure_id": figure_id,
            "mode": "upload",
            "caption": caption_clean,
            "media_status": meta.get("media_status") or {},
            "artifacts": {k: str(p) for k, p in artifacts.items()},
            "version": v,
            "undo": undo_meta(out_dir),
        }

        return edit_response_envelope(
            run_id=run_id,
            out_dir=out_dir,
            result=result,
            bust_needles=(figure_id,),
            extra={
                "figure_id": figure_id,
                "mode": "upload",
                "caption": caption_clean,
                "preview_figure": {
                    "id": figure_id,
                    "kind": "figure",
                    "url": f"/api/runs/{run_id}/figures/{figure_id}.png?v={v}",
                },
            },
        )

    return await run_in_threadpool(_process_upload)


@router.post("/api/runs/{run_id}/figures/{figure_id}/delete")
def delete_run_figure(
    run_id: str,
    figure_id: str,
    body: Optional[FigureEditFormatsBody] = None,
) -> dict[str, Any]:
    """Delete a figure/chart/diagram from LaTeX, figures.json, and meta.json."""
    if not FILE_OK.match(figure_id):
        raise HTTPException(400, detail="invalid figure_id")
    out_dir = resolve_run_dir(run_id)
    formats = formats_from_edit_body(body.formats if body else None)
    from case3.figure_edit import delete_figure_in_run

    result = delete_figure_in_run(out_dir, figure_id, formats=formats)
    return edit_response_envelope(
        run_id=run_id,
        out_dir=out_dir,
        result=result,
        bust_needles=(figure_id,),
        extra={"figure_id": figure_id, "deleted": True},
    )


@router.post("/api/runs/{run_id}/tables/{table_index}/edit")
async def edit_run_table(
    run_id: str, table_index: int, body: TableEditBody
) -> dict[str, Any]:
    """Replace one preview table (caption + grid) and rebuild PDF/DOCX."""
    out_dir = resolve_run_dir(run_id)
    if table_index < 1:
        raise HTTPException(400, detail="table_index must be ≥ 1")

    fmt_set = formats_from_edit_body(body.formats)
    headers = [str(h) for h in (body.headers or [])]
    rows = [[str(c) for c in row] for row in (body.rows or [])]
    caption = str(body.caption or "")

    try:
        result = await asyncio.to_thread(
            partial(
                edit_table_in_run,
                out_dir,
                table_index,
                caption=caption,
                headers=headers,
                rows=rows,
                formats=fmt_set,
            )
        )
    except TableEditError as exc:
        raise HTTPException(400, detail=str(exc)) from exc
    except RenderError as exc:
        raise HTTPException(500, detail=str(exc)) from exc

    return edit_response_envelope(
        run_id=run_id,
        out_dir=out_dir,
        result=result,
        extra={
            "table_index": table_index,
            "caption": result.get("caption"),
        },
    )


@router.post("/api/runs/{run_id}/paragraphs/{paragraph_index}/edit")
async def edit_run_paragraph(
    run_id: str, paragraph_index: int, body: ParagraphEditBody
) -> dict[str, Any]:
    """Replace one preview paragraph (para-N) and rebuild PDF/DOCX."""
    out_dir = resolve_run_dir(run_id)
    if paragraph_index < 1:
        raise HTTPException(400, detail="paragraph_index must be ≥ 1")

    fmt_set = formats_from_edit_body(body.formats)

    try:
        result = await asyncio.to_thread(
            partial(
                edit_paragraph_in_run,
                out_dir,
                paragraph_index,
                text=str(body.text or ""),
                formats=fmt_set,
            )
        )
    except ParagraphEditError as exc:
        raise HTTPException(400, detail=str(exc)) from exc
    except RenderError as exc:
        raise HTTPException(500, detail=str(exc)) from exc

    return edit_response_envelope(
        run_id=run_id,
        out_dir=out_dir,
        result=result,
        extra={
            "paragraph_index": paragraph_index,
            "text": result.get("text"),
        },
    )


@router.post("/api/runs/{run_id}/paragraphs/insert")
async def insert_run_paragraph(
    run_id: str, body: ParagraphInsertBody
) -> dict[str, Any]:
    """Insert a new paragraph into TeX and rebuild PDF/DOCX."""
    out_dir = resolve_run_dir(run_id)
    fmt_set = formats_from_edit_body(body.formats)

    try:
        result = await asyncio.to_thread(
            partial(
                insert_paragraph_in_run,
                out_dir,
                text=str(body.text or ""),
                after_paragraph_index=body.after_paragraph_index,
                after_heading_index=body.after_heading_index,
                formats=fmt_set,
            )
        )
    except ParagraphEditError as exc:
        raise HTTPException(400, detail=str(exc)) from exc
    except RenderError as exc:
        raise HTTPException(500, detail=str(exc)) from exc

    return edit_response_envelope(
        run_id=run_id,
        out_dir=out_dir,
        result=result,
        extra={
            "after_paragraph_index": body.after_paragraph_index,
            "after_heading_index": body.after_heading_index,
            "text": result.get("text"),
        },
    )



@router.post("/api/runs/{run_id}/headings/{heading_index}/edit")
async def edit_run_heading(
    run_id: str, heading_index: int, body: HeadingEditBody
) -> dict[str, Any]:
    """Replace one preview heading and rebuild PDF/DOCX."""
    out_dir = resolve_run_dir(run_id)
    if heading_index < 1:
        raise HTTPException(400, detail="heading_index must be ≥ 1")

    fmt_set = formats_from_edit_body(body.formats)

    try:
        result = await asyncio.to_thread(
            partial(
                edit_heading_in_run,
                out_dir,
                heading_index,
                text=str(body.text or ""),
                formats=fmt_set,
            )
        )
    except HeadingEditError as exc:
        raise HTTPException(400, detail=str(exc)) from exc
    except RenderError as exc:
        raise HTTPException(500, detail=str(exc)) from exc

    return edit_response_envelope(
        run_id=run_id,
        out_dir=out_dir,
        result=result,
        extra={
            "heading_index": heading_index,
            "text": result.get("text"),
        },
    )


@router.post("/api/runs/{run_id}/title/edit")
async def edit_run_title(
    run_id: str, body: TitleEditBody
) -> dict[str, Any]:
    """Replace document \\title and rebuild PDF/DOCX."""
    out_dir = resolve_run_dir(run_id)
    fmt_set = formats_from_edit_body(body.formats)

    try:
        result = await asyncio.to_thread(
            partial(
                edit_title_in_run,
                out_dir,
                text=str(body.text or ""),
                formats=fmt_set,
            )
        )
    except HeadingEditError as exc:
        raise HTTPException(400, detail=str(exc)) from exc
    except RenderError as exc:
        raise HTTPException(500, detail=str(exc)) from exc

    return edit_response_envelope(
        run_id=run_id,
        out_dir=out_dir,
        result=result,
        extra={
            "title": result.get("title"),
        },
    )



@router.post("/api/runs/{run_id}/lists/{list_index}/edit")
async def edit_run_list(
    run_id: str, list_index: int, body: ListEditBody
) -> dict[str, Any]:
    """Replace one preview list (list-N) and rebuild PDF/DOCX."""
    out_dir = resolve_run_dir(run_id)
    if list_index < 1:
        raise HTTPException(400, detail="list_index must be ≥ 1")

    fmt_set = formats_from_edit_body(body.formats)

    try:
        result = await asyncio.to_thread(
            partial(
                edit_list_in_run,
                out_dir,
                list_index,
                items=list(body.items or []),
                ordered=body.ordered,
                formats=fmt_set,
            )
        )
    except ListEditError as exc:
        raise HTTPException(400, detail=str(exc)) from exc
    except RenderError as exc:
        raise HTTPException(500, detail=str(exc)) from exc

    return edit_response_envelope(
        run_id=run_id,
        out_dir=out_dir,
        result=result,
        extra={
            "list_index": list_index,
            "items": result.get("items"),
        },
    )


def _history_response(
    run_id: str,
    out_dir: Any,
    result: dict[str, Any],
    *,
    action_key: str,
) -> dict[str, Any]:
    """Shared JSON after undo/redo: preview + stack descriptor."""
    from pathlib import Path

    from case3.run_undo import undo_meta

    out = Path(out_dir)
    media: dict[str, Any] = {}
    meta_obj: dict[str, Any] = {}
    meta_path = out / "meta.json"
    if meta_path.is_file():
        try:
            loaded = json.loads(meta_path.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                meta_obj = loaded
                media = loaded.get("media_status") or {}
        except (OSError, json.JSONDecodeError):
            media = {}
    if not isinstance(media, dict):
        media = {}
    v = int(time.time())
    preview = build_preview_payload(run_id, out, media)
    for block in preview.get("blocks") or []:
        if isinstance(block, dict) and block.get("type") == "figure" and block.get("url"):
            url = str(block["url"])
            sep = "&" if "?" in url else "?"
            block["url"] = f"{url}{sep}v={v}"

    last_edit = meta_obj.get("last_edit") if isinstance(meta_obj.get("last_edit"), dict) else {}
    memory_section = "" if last_edit.get("op") == "undo" else str(last_edit.get("section") or "")

    return {
        "run_id": run_id,
        "status": "ok",
        action_key: {"kind": result.get("kind"), "target": result.get("target")},
        "downloads": artifact_downloads(run_id, out, v),
        "preview": preview,
        "undo": undo_meta(out),
        "memory_section": memory_section,
        "warnings": (
            [str(result["rebuild_error"])] if result.get("rebuild_error") else []
        ),
    }


def _parse_rebuild_flag(raw: str | None) -> bool:
    """Query ``rebuild``: default True; 0/false/no → False."""
    if raw is None or raw.strip() == "":
        return True
    return raw.strip().lower() not in {"0", "false", "no", "off"}


@router.post("/api/runs/{run_id}/docs/rebuild")
async def rebuild_run_documents(run_id: str) -> dict[str, Any]:
    """Force PDF+DOCX from current TeX (edit-session «Готово»)."""
    from case3.run_rebuild import rebuild_run_docs
    from case3.run_undo import undo_meta

    out_dir = resolve_run_dir(run_id)
    try:
        artifacts = await asyncio.to_thread(
            partial(rebuild_run_docs, out_dir, formats={"pdf", "docx"})
        )
    except FileNotFoundError as exc:
        raise HTTPException(404, detail=str(exc)) from exc
    except RenderError as exc:
        raise HTTPException(500, detail=str(exc)) from exc

    v = int(time.time())
    media: dict[str, Any] = {}
    meta_path = out_dir / "meta.json"
    if meta_path.is_file():
        try:
            media = (json.loads(meta_path.read_text(encoding="utf-8")) or {}).get(
                "media_status"
            ) or {}
        except (OSError, json.JSONDecodeError):
            media = {}
    if not isinstance(media, dict):
        media = {}
    preview = build_preview_payload(run_id, out_dir, media)
    return {
        "run_id": run_id,
        "status": "ok",
        "artifacts": {k: str(p) for k, p in artifacts.items()},
        "downloads": artifact_downloads(run_id, out_dir, v),
        "preview": preview,
        "undo": undo_meta(out_dir),
        "warnings": [],
    }


@router.post("/api/runs/{run_id}/undo")
async def undo_last_edit(
    run_id: str, rebuild: str | None = None
) -> dict[str, Any]:
    """Pop one snapshot from the session undo stack (redo keeps forward)."""
    from case3.run_undo import UndoError, apply_undo

    out_dir = resolve_run_dir(run_id)
    do_rebuild = _parse_rebuild_flag(rebuild)
    try:
        result = await asyncio.to_thread(
            partial(apply_undo, out_dir, rebuild=do_rebuild)
        )
    except UndoError as exc:
        raise HTTPException(400, detail=str(exc)) from exc
    from case3.run_meta import update_meta

    def _mark_undo(m: dict[str, Any]) -> None:
        prev = dict(m.get("last_edit") or {}) if isinstance(m.get("last_edit"), dict) else {}
        prev["op"] = "undo"
        m["last_edit"] = prev

    update_meta(out_dir, _mark_undo)
    return _history_response(run_id, out_dir, result, action_key="undone")


@router.post("/api/runs/{run_id}/redo")
async def redo_last_edit(
    run_id: str, rebuild: str | None = None
) -> dict[str, Any]:
    """Re-apply the last undone Liber edit from the redo branch."""
    from case3.run_undo import UndoError, apply_redo

    out_dir = resolve_run_dir(run_id)
    do_rebuild = _parse_rebuild_flag(rebuild)
    try:
        result = await asyncio.to_thread(
            partial(apply_redo, out_dir, rebuild=do_rebuild)
        )
    except UndoError as exc:
        raise HTTPException(400, detail=str(exc)) from exc
    from case3.run_meta import update_meta

    def _mark_redo(m: dict[str, Any]) -> None:
        prev = dict(m.get("last_edit") or {}) if isinstance(m.get("last_edit"), dict) else {}
        if prev.get("op") == "undo":
            prev["op"] = "redo"
            m["last_edit"] = prev

    update_meta(out_dir, _mark_redo)
    return _history_response(run_id, out_dir, result, action_key="redone")


@router.post("/api/runs/{run_id}/edit-history/clear")
async def clear_edit_history_route(run_id: str) -> dict[str, Any]:
    """Drop session undo/redo (UI «Готово»)."""
    from case3.run_undo import clear_undo, undo_meta

    out_dir = resolve_run_dir(run_id)
    cleared = await asyncio.to_thread(clear_undo, out_dir)
    return {
        "run_id": run_id,
        "status": "ok",
        "cleared": bool(cleared),
        "undo": undo_meta(out_dir),
    }


