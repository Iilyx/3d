"""intent+source → LLM tex → Image API + HTML charts → inject → PDF/DOCX."""

from __future__ import annotations

import json
import logging
import re
import shutil
import threading
import traceback
from concurrent.futures import ThreadPoolExecutor
from contextvars import ContextVar, copy_context
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable  # Any used by user_figures metas

from case3.charts import generate_all_charts, max_charts_from_env
from case3.chat_summary import seal_chat_summary, try_generate_chat_summary
from case3.diagrams import max_diagrams_from_env
from case3.generate import generate_document, max_images_from_env, resolve_text_file
from case3.inject import write_injected
from case3.image_api import ImageApiConfig, generate_all_figures
from case3.render import RenderError, render_tex
from case3.run_cancel import RunCancelled, raise_if_cancelled
from case3.run_events import EVENTS
from case3.summary_bus import BUS
from case3.user_photos import (
    ensure_user_slots_in_tex,
    materialize_user_figures,
    merge_user_figures,
)
log = logging.getLogger("case3.pipeline")

# Stages eligible for POST /resume.
# ``llm`` replays work/*.raw_model.txt and does not call the model again.
RESUME_STAGES = frozenset({"llm", "images", "charts", "inject", "latex", "docx"})

# Isolate pipeline.log per run when multiple FileHandlers share logger "case3"
# (Win AV + cross-run emit was a hang amplifier; see debug 114628).
_PIPELINE_RUN_ID: ContextVar[str] = ContextVar("case3_pipeline_run_id", default="")


class _RunIdLogFilter(logging.Filter):
    """Only emit records while this handler's run_id owns the context."""

    def __init__(self, run_id: str) -> None:
        super().__init__()
        self.run_id = run_id

    def filter(self, record: logging.LogRecord) -> bool:
        return _PIPELINE_RUN_ID.get() == self.run_id


def _attach_pipeline_log_handler(logs: Path, run_id: str) -> logging.Handler:
    handler = logging.FileHandler(logs / "pipeline.log", encoding="utf-8")
    handler.setFormatter(
        logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
    )
    handler.addFilter(_RunIdLogFilter(run_id))
    root_logger = logging.getLogger("case3")
    root_logger.addHandler(handler)
    root_logger.setLevel(logging.INFO)
    return handler


def resolve_pipeline_formats(formats: set[str] | None) -> set[str]:
    """Default print formats. ``None`` → ``{pdf}``; empty set stays empty (none)."""
    if formats is None:
        return {"pdf"}
    return set(formats)


def _find_run_tex(work: Path, out: Path) -> Path | None:
    for d in (work, out):
        if not d.is_dir():
            continue
        cands = sorted(
            p
            for p in d.glob("*.tex")
            if ".raw_model" not in p.name and not p.name.endswith(".uninjected.tex")
        )
        if cands:
            return cands[0]
    return None


def _media_ok_on_disk(mid: str, status: dict[str, Any], figs_dir: Path) -> bool:
    st = status.get(mid)
    if not (isinstance(st, dict) and st.get("ok")):
        return False
    return (figs_dir / f"{mid}.png").is_file()


def _saved_raw_model(work: Path, source: Path | None = None) -> Path | None:
    """Non-empty ``*.raw_model.txt`` written before parse (see generate.py)."""
    if not work.is_dir():
        return None
    if source is not None:
        named = work / f"{source.stem}.raw_model.txt"
        if named.is_file() and named.stat().st_size > 0:
            return named
    for path in sorted(work.glob("*.raw_model.txt")):
        if path.is_file() and path.stat().st_size > 0:
            return path
    return None


def can_resume_run(
    meta: dict[str, Any], *, work: Path, out: Path
) -> bool:
    """True when Liber may offer «Продолжить» for this failed run."""
    if str(meta.get("status") or "") != "error":
        return False
    stage = str(meta.get("failed_stage") or "")
    if stage not in RESUME_STAGES:
        return False
    if stage == "llm":
        source = Path(str(meta.get("source") or ""))
        return source.is_file() and _saved_raw_model(work, source) is not None
    if _find_run_tex(work, out) is None:
        return False
    fj = work / "figures.json"
    if not fj.is_file():
        fj = out / "figures.json"
    return fj.is_file()


def _record_failed_stage(meta: dict[str, Any]) -> None:
    """Keep the real craft stage when flipping status to error."""
    prev = str(meta.get("stage") or "").strip()
    if prev and prev not in {"error", "ok", "cancelled", "queued"}:
        meta["failed_stage"] = prev
    elif not meta.get("failed_stage"):
        meta["failed_stage"] = prev or "error"


class PipelineError(RuntimeError):
    """Pipeline failed after writing meta/logs — includes run_id for debug upload."""

    def __init__(
        self,
        message: str,
        *,
        run_id: str,
        out_dir: Path,
        logs_dir: Path,
        meta: dict,
    ) -> None:
        super().__init__(message)
        self.run_id = run_id
        self.out_dir = out_dir
        self.logs_dir = logs_dir
        self.meta = meta


def _latex_log_tail(path: Path | None, *, lines: int = 40) -> str:
    """Last N lines of a TeX log (C8 diagnostics)."""
    if path is None or not Path(path).is_file():
        return ""
    try:
        text = Path(path).read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""
    parts = text.splitlines()
    if not parts:
        return ""
    bang = next((i for i, line in enumerate(parts) if line.startswith("!")), None)
    if bang is None:
        return "\n".join(parts[-max(1, lines) :])
    return "\n".join(parts[bang : bang + 12])


def _abort_open_summary(run_id: str, error: str) -> None:
    """If the chat is still waiting on the summary, say the print failed."""
    snap = BUS.snapshot(run_id)
    if snap.get("status") != "streaming" or snap.get("done"):
        return
    BUS.finish(
        run_id,
        seal_chat_summary("", {}, render_error=error),
        "error",
    )


def _find_latex_log(logs_dir: Path) -> Path | None:
    if not logs_dir.is_dir():
        return None
    preferred = sorted(logs_dir.glob("*.log"))
    for p in preferred:
        if p.name != "pipeline.log":
            return p
    pipe = logs_dir / "pipeline.log"
    return pipe if pipe.is_file() else None


def _attach_error_diagnostics(
    meta: dict[str, Any],
    *,
    logs_dir: Path,
    error: str,
    log_path: Path | None = None,
) -> dict[str, Any]:
    """Enrich meta with failed media ids + latex log tail (C8)."""
    out = dict(meta)
    media = out.get("media_status") or {}
    if not isinstance(media, dict):
        media = {}
    failed_c = [
        cid
        for cid in (out.get("charts_planned") or [])
        if not (isinstance(media.get(cid), dict) and media[cid].get("ok"))
    ]
    failed_f = [
        fid
        for fid in (out.get("figures_planned") or [])
        if not (isinstance(media.get(fid), dict) and media[fid].get("ok"))
    ]
    out["failed_charts"] = failed_c
    out["failed_figures"] = failed_f
    bits = [str(error).strip()]
    if failed_c:
        bits.append(f"charts failed: {', '.join(failed_c)}")
    if failed_f:
        bits.append(f"figures failed: {', '.join(failed_f)}")
    out["error"] = "; ".join(b for b in bits if b)
    lp = Path(log_path) if log_path else _find_latex_log(logs_dir)
    tail = _latex_log_tail(lp)
    if tail:
        out["latex_log_tail"] = tail
        out["latex_log_path"] = str(lp) if lp else None
    return out


def _diagram_chat_blurb(diagrams: list[dict[str, Any]] | None) -> str:
    """Short Liber chat line without a second Vision round-trip."""
    items = [d for d in (diagrams or []) if isinstance(d, dict)]
    if not items:
        return "Схема готова — откройте вкладку «Схема» в панели."
    titles = [
        str(d.get("title") or d.get("id") or "схема").strip() for d in items
    ]
    titles = [t for t in titles if t]
    if len(titles) == 1:
        return f"Готово: схема «{titles[0]}»."
    shown = ", ".join(f"«{t}»" for t in titles[:3])
    more = f" и ещё {len(titles) - 3}" if len(titles) > 3 else ""
    return f"Готово: {len(titles)} схем — {shown}{more}."


def _presentation_chat_blurb(
    *,
    charts: list[dict[str, Any]] | None = None,
    figures: list[dict[str, Any]] | None = None,
) -> str:
    """Local blurb for presentation — skip second LLM; slides job is the product."""
    n_ch = len([c for c in (charts or []) if isinstance(c, dict)])
    n_fig = len([f for f in (figures or []) if isinstance(f, dict)])
    bits: list[str] = []
    if n_ch:
        bits.append(f"графиков: {n_ch}")
    if n_fig:
        bits.append(f"фото: {n_fig}")
    media = f" ({', '.join(bits)})" if bits else ""
    return f"Ок, собираем презентацию{media}…"


def _write_meta(meta: dict[str, Any], out: Path, logs: Path) -> None:
    from case3.run_events import _meta_file_lock
    from case3.run_meta import read_meta, write_meta

    with _meta_file_lock:
        # The pipeline holds one in-memory snapshot. A concurrent
        # mark_cancel_requested writes the flag on disk; the next stage
        # dump must not erase it.
        disk = read_meta(out)
        wid = str(disk.get("workspace_id") or "").strip()
        if wid and not str(meta.get("workspace_id") or "").strip():
            meta["workspace_id"] = wid
        if disk.get("cancel_requested"):
            meta["cancel_requested"] = True
            if meta.get("status") == "ok":
                meta["status"] = "cancelled"
                meta["stage"] = "cancelled"
                meta["error"] = "Остановлено"
                meta.pop("stage_detail", None)
        write_meta(out, meta, logs_dir=logs)


def _set_stage(
    meta: dict[str, Any],
    out: Path,
    logs: Path,
    stage: str,
    *,
    detail: str | None = None,
    status: str = "running",
    project_root: Path | None = None,
) -> None:
    meta["status"] = status
    meta["stage"] = stage
    if detail:
        meta["stage_detail"] = detail
    else:
        meta.pop("stage_detail", None)
    from case3.run_events import note_craft_stage

    # One steps[] row per stage id — not per cht_/fig_ detail bump.
    note_craft_stage(meta, stage=stage, scope="pipeline", detail=detail)
    _write_meta(meta, out, logs)
    run_id = str(meta.get("run_id") or "")
    if run_id:
        from case3.stage_eta import note_stage_enter

        # Only roll ETA when the stage id changes (not every cht_* detail bump).
        prev = str(meta.get("_eta_stage") or "")
        eta = None
        if stage != prev:
            eta = note_stage_enter(run_id, stage, project_root=project_root)
            meta["_eta_stage"] = stage
            timings = list(meta.get("stage_timings") or [])
            if isinstance(timings, list):
                timings.append({"stage": stage, "t": __import__("time").time()})
                meta["stage_timings"] = timings[-40:]
        EVENTS.publish_stage(
            run_id, stage, detail=detail, scope="pipeline", eta_s=eta
        )
        # Phase 2A: fine steps for charts / photos
        det = (detail or "").strip()
        if stage == "charts" and det.startswith("cht_"):
            EVENTS.publish_step(
                run_id, parent="charts", step_id=det, status="active", label=det
            )
        elif stage == "images" and det.startswith(("fig_", "usr_")):
            EVENTS.publish_step(
                run_id, parent="photos", step_id=det, status="active", label=det
            )
        # Scan out/ only when print artifacts can appear — not every fig/cht bump
        # (Win AV on glob×N amplified hangs after bump with no following log line).
        if stage in {"latex", "docx", "summary", "ok", "pipeline_ok"} or (
            stage == "inject" and not det
        ):
            EVENTS.scan_artifacts(run_id, out)


_DESK_SLIDES_KEYS = (
    "deck_pack",
    "slides_theme_pack",
    "slides_structure_id",
    "slides_style",
    "slides_target",
)


def carry_chat_prompt(meta: dict[str, Any], previous: dict[str, Any] | None) -> None:
    """Keep the user's own words when the pipeline rebuilds meta from scratch.

    ``/api/run`` stamps ``chat_prompt`` before the thread starts. The first
    ``_write_meta`` would otherwise drop it, and the next turn could not
    quote what the user actually asked.
    """
    prev = previous or {}
    incoming = str(prev.get("chat_prompt") or "").strip()
    if incoming and not str(meta.get("chat_prompt") or "").strip():
        meta["chat_prompt"] = incoming
    prior = str(prev.get("prior_run_id") or "").strip()
    if prior and not str(meta.get("prior_run_id") or "").strip():
        meta["prior_run_id"] = prior
    wid = str(prev.get("workspace_id") or "").strip()
    if wid and not str(meta.get("workspace_id") or "").strip():
        meta["workspace_id"] = wid
    prev_edit = prev.get("last_edit")
    if isinstance(prev_edit, dict) and prev_edit and not meta.get("last_edit"):
        kept = {
            key: str(prev_edit.get(key) or "").strip()
            for key in ("op", "section", "pack", "palette")
            if str(prev_edit.get(key) or "").strip()
        }
        if kept:
            meta["last_edit"] = kept
    notice = str(prev.get("chat_notice") or "").strip()
    if notice and not str(meta.get("chat_notice") or "").strip():
        meta["chat_notice"] = notice
    carried = str(prev.get("carried_run_id") or "").strip()
    if carried and not str(meta.get("carried_run_id") or "").strip():
        meta["carried_run_id"] = carried


def merge_desk_slides_fields(
    meta: dict[str, Any], previous: dict[str, Any] | None
) -> dict[str, Any]:
    """Keep Liber desk deck pack/structure/style stamped by ``/api/run``."""
    prev = previous or {}
    for key in _DESK_SLIDES_KEYS:
        if prev.get(key) is not None:
            meta[key] = prev[key]
    return meta


_RUN_DIR_LOCK = threading.Lock()


def prepare_run_dirs(
    source: Path,
    *,
    project_root: Path,
    run_id: str | None = None,
) -> tuple[str, Path, Path, Path, Path]:
    """Create work/out/logs for a run. Returns run_id, text_path, work, out, logs."""
    root = project_root.resolve()
    text_path = resolve_text_file(source)
    stem = text_path.stem
    with _RUN_DIR_LOCK:
        if run_id is None:
            stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
            run_id = f"{stem}_{stamp}"
            extra = 2
            while True:
                candidate = root / "runs" / "out" / run_id
                try:
                    candidate.mkdir(parents=True, exist_ok=False)
                    break
                except FileExistsError:
                    run_id = f"{stem}_{stamp}_{extra}"
                    extra += 1
        work = root / "runs" / "work" / run_id
        out = root / "runs" / "out" / run_id
        logs = root / "runs" / "logs" / run_id
        for d in (work, out, logs):
            d.mkdir(parents=True, exist_ok=True)
    return run_id, text_path, work, out, logs



def _pipeline_materialize_media(
    *,
    status: dict[str, Any],
    figures: list,
    charts: list,
    diagrams: list | None = None,
    fj: dict[str, Any],
    fj_path: Path,
    figs_dir: Path,
    work: Path,
    images_budget: int,
    charts_budget: int,
    dry_run: bool,
    intent: str | None,
    meta: dict[str, Any],
    bump: Callable[[str, str | None], None],
    run_id: str,
    only_missing: bool = False,
    publish_events: bool = False,
) -> None:
    """Shared images + charts materialization (run + resume).

    ``only_missing``: resume — skip ids already OK on disk.
    ``publish_events``: full run publishes EVENTS photo/chart steps.
    """
    if figures and not dry_run and images_budget > 0:
        if publish_events:
            log.info(
                "images stage: %d figures, budget=%d (probe/POST next)",
                len(figures),
                images_budget,
            )
        bump("images")
        status.update(materialize_user_figures(figures, figs_dir))
        need_api = [
            f
            for f in figures
            if str(f.get("source") or "") != "upload"
            and (
                not only_missing
                or not _media_ok_on_disk(str(f.get("id") or ""), status, figs_dir)
            )
        ]
        cfg = ImageApiConfig.from_env()
        cfg = replace(cfg, max_images=images_budget)
        if publish_events:
            log.info(
                "images cfg base_url=%s need_api=%d",
                (cfg.base_url or "")[:80] or "-",
                len(need_api),
            )
        if need_api and not cfg.base_url:
            if publish_events:
                log.warning(
                    "figures planned but IMAGE_API_BASE_URL empty — strip slots"
                )
            for f in need_api:
                fid = str(f.get("id") or "")
                if fid:
                    status[fid] = {
                        "ok": False,
                        "error": "IMAGE_API_BASE_URL empty",
                        "kind": "figure",
                    }
            if publish_events:
                EVENTS.publish_step(
                    run_id,
                    parent="photos",
                    step_id="photos",
                    status="skipped",
                    reason="IMAGE_API_BASE_URL empty",
                    label="Фото",
                )
        elif need_api:

            def _img_progress(fid: str) -> None:
                bump("images", fid)
                if publish_events and fid:
                    EVENTS.publish_step(
                        run_id,
                        parent="photos",
                        step_id=fid,
                        status="done",
                        label=fid,
                    )

            from case3.chart_style import palette_from_intent

            pack_for_photos = (
                str(meta.get("image_style_pack") or "")
                or palette_from_intent(intent or "")
                or "atelier"
            )
            if publish_events or not meta.get("image_style_pack"):
                meta["image_style_pack"] = pack_for_photos
            targets = figures if not only_missing else need_api
            out_dir_for_cancel = work.parent.parent / "out" / run_id
            status.update(
                generate_all_figures(
                    targets,
                    figs_dir,
                    cfg=cfg,
                    on_progress=_img_progress,
                    pack_id=pack_for_photos,
                    cancel_check=lambda: raise_if_cancelled(out_dir_for_cancel),
                )
            )

    if charts and not dry_run and charts_budget > 0:
        bump("charts")
        chart_targets = (
            [
                c
                for c in charts
                if not _media_ok_on_disk(str(c.get("id") or ""), status, figs_dir)
            ]
            if only_missing
            else list(charts)
        )

        def _chart_progress(cid: str) -> None:
            bump("charts", cid)
            if publish_events and cid:
                EVENTS.publish_step(
                    run_id,
                    parent="charts",
                    step_id=cid,
                    status="done",
                    label=cid,
                )

        to_render = chart_targets if only_missing else charts
        if to_render:
            out_dir_for_cancel = work.parent.parent / "out" / run_id
            status.update(
                generate_all_charts(
                    to_render,
                    figs_dir,
                    work_root=work / "chart_work",
                    max_charts=charts_budget,
                    on_progress=_chart_progress,
                    cancel_check=lambda: raise_if_cancelled(out_dir_for_cancel),
                )
            )
        from case3.slides_chart_data import attach_series_ir_to_charts

        attach_series_ir_to_charts(charts)
        fj["charts"] = charts
        fj_path.write_text(
            json.dumps(fj, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    if diagrams is None and isinstance(fj.get("diagrams"), list):
        diagrams = fj["diagrams"]

    if diagrams and not dry_run:
        diagram_targets = [
            d
            for d in diagrams
            if isinstance(d, dict)
            and d.get("id")
            and (
                not only_missing
                or not _media_ok_on_disk(str(d.get("id")), status, figs_dir)
            )
        ]
        if diagram_targets:
            bump("charts", "схемы…")
            from case3.chart_style import palette_from_intent
            from case3.slides_media import ensure_diagram_pngs

            palette_for_diags = (
                str(meta.get("image_style_pack") or "")
                or palette_from_intent(intent or "")
                or "atelier"
            )
            specs = {d["id"]: d for d in diagram_targets}
            rendered = ensure_diagram_pngs(
                specs,
                dest_dir=figs_dir,
                palette=palette_for_diags,
                theme_pack=palette_for_diags,
            )
            for d in diagram_targets:
                did = str(d.get("id") or "")
                if (
                    did in rendered
                    and rendered[did].is_file()
                    and rendered[did].stat().st_size > 0
                ):
                    status[did] = {"ok": True, "kind": "diagram"}
                elif (
                    (figs_dir / f"{did}.png").is_file()
                    and (figs_dir / f"{did}.png").stat().st_size > 0
                ):
                    status[did] = {"ok": True, "kind": "diagram"}
                else:
                    status[did] = {
                        "ok": False,
                        "error": "render failed",
                        "kind": "diagram",
                    }


def _pipeline_print_and_summary(
    *,
    meta: dict[str, Any],
    out: Path,
    logs: Path,
    root: Path,
    run_id: str,
    tex_path: Path,
    figures: list,
    charts: list,
    diagrams: list,
    status: dict[str, Any],
    figs_dir: Path,
    formats: set[str],
    dry_run: bool,
    mode: str,
    intent: str | None,
    bump: Callable[[str, str | None], None],
    force_render: bool = False,
) -> dict[str, Path]:
    """Shared latex/docx + chat summary after inject (run + resume)."""
    skip_print = not formats
    injected_tex = tex_path.read_text(encoding="utf-8")

    def _do_summary() -> tuple[str, str, dict[str, Any]]:
        chart_ids = [
            str(c.get("id") or "")
            for c in (charts or [])
            if isinstance(c, dict) and c.get("id")
        ]
        fig_ids = [
            str(f.get("id") or "")
            for f in (figures or [])
            if isinstance(f, dict) and f.get("id")
        ]
        media_facts = {
            "charts_planned": len(chart_ids),
            "figures_planned": len(fig_ids),
            "diagrams_planned": len(diagrams or []),
            # Prefer on-disk PNG truth (resume status can be stale-ok).
            "charts_ok": sum(
                1 for cid in chart_ids if _media_ok_on_disk(cid, status, figs_dir)
            ),
            "figures_ok": sum(
                1 for fid in fig_ids if _media_ok_on_disk(fid, status, figs_dir)
            ),
        }
        # Do not publish while print is still running. The caller seals and finishes.
        text, status_sum = try_generate_chat_summary(
            injected_tex,
            intent=intent,
            media=media_facts,
        )
        return text, status_sum, media_facts

    def _do_render() -> dict:
        return render_tex(
            tex_path,
            out_dir=out,
            formats=formats,
            extra_dirs=[figs_dir] if figs_dir.is_dir() else None,
            log_dir=logs,
            project_root=root,
            force=force_render,
            on_format=lambda fmt: bump("docx" if fmt == "docx" else "latex"),
        )

    def _sync_render_meta_fields() -> None:
        from case3.run_meta import read_meta

        disk_meta = read_meta(out)
        if "docx_native_charts" in disk_meta:
            meta["docx_native_charts"] = disk_meta["docx_native_charts"]

    if dry_run:
        meta["chat_summary"] = ""
        meta["summary_status"] = "skipped"
        BUS.start(run_id)
        BUS.finish(run_id, "", "skipped")
        if skip_print:
            return {}
        res = _do_render()
        _sync_render_meta_fields()
        return res

    if skip_print:
        artifacts: dict[str, Path] = {}
        BUS.start(run_id)
        bump("summary")
        if mode == "diagram":
            summary_text = _diagram_chat_blurb(diagrams)
            summary_status = "ok"
        elif mode == "presentation":
            summary_text = _presentation_chat_blurb(charts=charts, figures=figures)
            summary_status = "ok"
        else:
            meta["summary_status"] = "streaming"
            meta["chat_summary"] = ""
            _write_meta(meta, out, logs)
            summary_text, summary_status, _media_facts = _do_summary()
        BUS.finish(run_id, summary_text or "", summary_status)
        meta["chat_summary"] = summary_text or ""
        meta["summary_status"] = summary_status
        if summary_text:
            (out / "chat_summary.txt").write_text(summary_text, encoding="utf-8")
            (logs / "chat_summary.txt").write_text(summary_text, encoding="utf-8")
        return artifacts

    meta["summary_status"] = "streaming"
    meta["chat_summary"] = ""
    _write_meta(meta, out, logs)
    BUS.start(run_id)
    with ThreadPoolExecutor(max_workers=2) as pool:
        fut_r = pool.submit(copy_context().run, _do_render)
        fut_s = pool.submit(copy_context().run, _do_summary)
        artifacts = fut_r.result()
        _sync_render_meta_fields()
        bump("summary")
        summary_text, summary_status, media_facts = fut_s.result()
    summary_text = seal_chat_summary(summary_text, media_facts)
    BUS.finish(run_id, summary_text or "", summary_status)
    meta["chat_summary"] = summary_text or ""
    meta["summary_status"] = summary_status
    if summary_text:
        (out / "chat_summary.txt").write_text(summary_text, encoding="utf-8")
        (logs / "chat_summary.txt").write_text(summary_text, encoding="utf-8")
    return artifacts


def resume_pipeline(
    run_id: str,
    *,
    project_root: Path,
    on_stage: Callable[[str, str | None], None] | None = None,
) -> Path:
    """Continue a failed run without a new model call.

    Media/render stages need TeX + ``figures.json``. Stage ``llm`` needs the
    Source file and a non-empty ``*.raw_model.txt`` saved before parse.
    """
    root = project_root.resolve()
    work = root / "runs" / "work" / run_id
    out = root / "runs" / "out" / run_id
    logs = root / "runs" / "logs" / run_id
    for d in (work, out, logs):
        d.mkdir(parents=True, exist_ok=True)

    meta_path = out / "meta.json"
    if not meta_path.is_file():
        meta_path = logs / "meta.json"
    if not meta_path.is_file():
        raise PipelineError(
            "resume: meta.json missing",
            run_id=run_id,
            out_dir=out,
            logs_dir=logs,
            meta={"run_id": run_id, "status": "error"},
        )
    try:
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise PipelineError(
            f"resume: corrupt meta.json ({exc})",
            run_id=run_id,
            out_dir=out,
            logs_dir=logs,
            meta={"run_id": run_id, "status": "error"},
        ) from exc
    if not isinstance(meta, dict):
        meta = {"run_id": run_id}

    # POST /api/runs/{id}/resume pre-flips status="running" before kicking the background
    # thread so UI polling leaves the error state immediately while failed_stage stays set.
    check_meta = (
        {**meta, "status": "error"}
        if str(meta.get("status") or "") == "running"
        and str(meta.get("failed_stage") or "") in RESUME_STAGES
        else meta
    )
    if not can_resume_run(check_meta, work=work, out=out):
        raise PipelineError(
            "resume: run is not eligible",
            run_id=run_id,
            out_dir=out,
            logs_dir=logs,
            meta=meta,
        )

    failed_from = str(meta.get("failed_stage") or "")
    llm_replay = failed_from == "llm"
    source_path = Path(str(meta.get("source") or ""))
    if llm_replay:
        tex_path = work / f"{source_path.stem}.tex"
        fj_path = work / "figures.json"
        fj = {}
        figures = []
        charts = []
        diagrams = []
    else:
        tex_path = _find_run_tex(work, out)
        assert tex_path is not None  # can_resume_run checked
        # Prefer work copy for inject mutability
        if tex_path.parent != work:
            work_tex = work / tex_path.name
            shutil.copy2(tex_path, work_tex)
            tex_path = work_tex

        fj_path = work / "figures.json"
        if not fj_path.is_file():
            src_fj = out / "figures.json"
            shutil.copy2(src_fj, fj_path)
        try:
            fj = json.loads(fj_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            fj = {}
        if not isinstance(fj, dict):
            fj = {}
        figures = [f for f in (fj.get("figures") or []) if isinstance(f, dict)]
        charts = [c for c in (fj.get("charts") or []) if isinstance(c, dict)]
        diagrams = [d for d in (fj.get("diagrams") or []) if isinstance(d, dict)]

    status: dict[str, Any] = {}
    for candidate in (work / "status.json", out / "status.json"):
        if candidate.is_file():
            try:
                loaded = json.loads(candidate.read_text(encoding="utf-8"))
                if isinstance(loaded, dict):
                    status = dict(loaded)
                    break
            except (OSError, json.JSONDecodeError):
                pass
    if not status and isinstance(meta.get("media_status"), dict):
        status = dict(meta["media_status"])

    raw_fmt = meta.get("formats")
    if isinstance(raw_fmt, list):
        formats = set(str(x) for x in raw_fmt)
    elif isinstance(raw_fmt, (set, frozenset)):
        formats = set(raw_fmt)
    else:
        formats = {"pdf"}
    formats = resolve_pipeline_formats(formats)
    intent = meta.get("intent")
    if intent is not None:
        intent = str(intent)
    images_budget = int(meta.get("max_images") if meta.get("max_images") is not None else max_images_from_env())
    charts_budget = int(meta.get("max_charts") if meta.get("max_charts") is not None else max_charts_from_env())
    mode = str(meta.get("output_mode") or "auto").strip().lower()
    if mode not in {"report", "diagram", "presentation", "auto", "chat"}:
        mode = "auto"
    dry_run = bool(meta.get("dry_run"))

    handler = _attach_pipeline_log_handler(logs, run_id)
    root_logger = logging.getLogger("case3")
    _run_token = _PIPELINE_RUN_ID.set(run_id)

    meta["status"] = "running"
    meta["stage"] = "queued"
    meta.pop("error", None)
    meta.pop("traceback", None)
    meta.pop("latex_log_tail", None)
    meta.pop("cancel_requested", None)
    meta["resumed_from_stage"] = failed_from
    meta["resume_count"] = int(meta.get("resume_count") or 0) + 1
    meta["run_id"] = run_id
    stem = tex_path.stem
    figs_dir = work / "figures"
    figs_dir.mkdir(parents=True, exist_ok=True)
    # Restore PNGs from out/figures if work is empty but out has them
    out_figs = out / "figures"
    if out_figs.is_dir():
        for png in out_figs.glob("*.png"):
            dest = figs_dir / png.name
            if not dest.is_file():
                shutil.copy2(png, dest)

    from case3.stage_eta import load_timings

    load_timings(root)
    EVENTS.ensure(run_id)
    _write_meta(meta, out, logs)
    EVENTS.publish_stage(run_id, "queued", scope="pipeline")

    def bump(stage: str, detail: str | None = None) -> None:
        raise_if_cancelled(out)
        _set_stage(meta, out, logs, stage, detail=detail, project_root=root)
        if on_stage:
            on_stage(stage, detail)

    try:
        if llm_replay:
            raw_path = _saved_raw_model(work, source_path)
            if raw_path is None or not source_path.is_file():
                raise PipelineError(
                    "resume llm: saved model text or source missing",
                    run_id=run_id,
                    out_dir=out,
                    logs_dir=logs,
                    meta=meta,
                )
            bump("llm", "разбор сохранённого ответа…")
            _, figures, charts, diagrams = generate_document(
                source_path,
                out_tex=tex_path,
                intent=intent,
                gold_dir=root / "prompt" / "gold",
                max_images=images_budget,
                max_charts=charts_budget,
                max_diagrams=int(meta.get("max_diagrams") or 0),
                dry_run=False,
                replay_raw=raw_path.read_text(encoding="utf-8"),
                cancel_check=lambda: raise_if_cancelled(out),
            )
            try:
                fj = json.loads(fj_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                fj = {}
            if not isinstance(fj, dict):
                fj = {}

        need_media = failed_from in {"images", "charts", "llm"} or any(
            not _media_ok_on_disk(str(x.get("id") or ""), status, figs_dir)
            for x in figures + charts + diagrams
            if isinstance(x, dict) and x.get("id")
        )

        if need_media:
            _pipeline_materialize_media(
                status=status,
                figures=figures,
                charts=charts,
                diagrams=diagrams,
                fj=fj,
                fj_path=fj_path,
                figs_dir=figs_dir,
                work=work,
                images_budget=images_budget,
                charts_budget=charts_budget,
                dry_run=dry_run,
                intent=intent,
                meta=meta,
                bump=bump,
                run_id=run_id,
                only_missing=True,
                publish_events=True,
            )

        # Keep prior ok entries for ids we skipped
        meta["media_status"] = status
        (work / "status.json").write_text(
            json.dumps(status, ensure_ascii=False, indent=2), encoding="utf-8"
        )

        bump("inject")
        write_injected(
            tex_path, figures, status, charts=charts, diagrams=diagrams
        )
        shutil.copy2(tex_path, out / tex_path.name)
        for name in ("figures.json", "status.json"):
            p = work / name
            if p.is_file():
                shutil.copy2(p, out / name)
        if figs_dir.is_dir() and any(figs_dir.glob("*.png")):
            dest = out / "figures"
            if dest.exists():
                shutil.rmtree(dest)
            shutil.copytree(figs_dir, dest)

        bump("latex" if formats else "summary")
        artifacts = _pipeline_print_and_summary(
            meta=meta,
            out=out,
            logs=logs,
            root=root,
            run_id=run_id,
            tex_path=tex_path,
            figures=figures,
            charts=charts,
            diagrams=diagrams,
            status=status,
            figs_dir=figs_dir,
            formats=formats,
            dry_run=dry_run,
            mode=mode,
            intent=intent,
            bump=bump,
            force_render=True,
        )

        raise_if_cancelled(out)
        meta["artifacts"] = {k: str(v) for k, v in artifacts.items()}
        meta["status"] = "ok"
        meta["stage"] = "ok"
        meta.pop("stage_detail", None)
        meta.pop("failed_stage", None)
        _write_meta(meta, out, logs)
        EVENTS.scan_artifacts(run_id, out)
        if mode != "presentation":
            EVENTS.publish_terminal(
                run_id,
                "ok",
                recap=EVENTS.success_recap(
                    run_id,
                    charts=sum(
                        1
                        for c in charts
                        if _media_ok_on_disk(str(c.get("id") or ""), status, figs_dir)
                    ),
                    figures=sum(
                        1
                        for f in figures
                        if _media_ok_on_disk(str(f.get("id") or ""), status, figs_dir)
                    ),
                ),
            )
        else:
            EVENTS.publish_stage(run_id, "pipeline_ok", scope="pipeline")
        log.info("resume done run_id=%s out=%s", run_id, out)
    except RunCancelled:
        meta["status"] = "cancelled"
        meta["stage"] = "cancelled"
        meta["error"] = "Остановлено"
        meta.pop("stage_detail", None)
        _write_meta(meta, out, logs)
        EVENTS.publish_terminal(run_id, "cancelled", error="Остановлено")
        return out
    except Exception as exc:
        _record_failed_stage(meta)
        meta["status"] = "error"
        meta["stage"] = "error"
        log_path = getattr(exc, "log_path", None) if isinstance(exc, RenderError) else None
        meta.update(
            _attach_error_diagnostics(
                meta,
                logs_dir=logs,
                error=str(exc),
                log_path=Path(log_path) if log_path else None,
            )
        )
        meta["traceback"] = traceback.format_exc()
        log.exception("resume pipeline failed")
        (logs / "error.txt").write_text(meta["traceback"], encoding="utf-8")
        _write_meta(meta, out, logs)
        _abort_open_summary(run_id, str(meta.get("error") or exc))
        from case3.stage_eta import error_hint

        EVENTS.publish_terminal(
            run_id,
            "error",
            error=str(meta.get("error") or exc),
            hint=error_hint(exc, stage=str(meta.get("failed_stage") or "")),
        )
        raise PipelineError(
            str(meta.get("error") or exc),
            run_id=run_id,
            out_dir=out,
            logs_dir=logs,
            meta=meta,
        ) from exc
    finally:
        root_logger.removeHandler(handler)
        handler.close()
        _PIPELINE_RUN_ID.reset(_run_token)

    log.info("resume done run_id=%s out=%s", run_id, out)
    return out


_BARE_VISUAL_EDIT_CUE = re.compile(
    r"(?:измен|поменя|передела|отредактир|обнов|подправ|доработ)\w*",
    re.IGNORECASE,
)
_CONCRETE_VISUAL_SPEC = re.compile(
    r"(?:столбч|лине[йя]|кругов|кольц|пончик|радар|точеч|площад|горизонт|"
    r"bar|line|pie|doughnut|radar|scatter|"
    r"цвет|палитр|оранжев|син|голуб|зел[её]н|красн|сер[ыо]|ч[её]рн|ж[её]лт|т[её]мн|светл|ocean|sunset|mono|editorial|atelier|"
    r"подпис|заголов|легенд|ось|оси|топ[-\s]?\d|убер|добав|удал|остав|отсортир|по\s+возраст|по\s+убыван|"
    r"вертикал|горизонтал|слева\s+направо|сверху\s+вниз|по\s+(?:регион|област|месяц|квартал|год)|в\s+(?:процент|дол|тыс|млн)|\d)",
    re.IGNORECASE,
)
_CLARIFY_ANSWER_CUE = re.compile(
    r"(?:\?\s*$|уточн|как\s+именно|что\s+именно|какие\s+именно|напишите,?\s*(?:что|как)|подскажите,?\s*(?:что|как))",
    re.IGNORECASE,
)


def _is_clarifying_visual_request(turn_text: str | None, answer: str | None, *, kind: str) -> bool:
    """True when user wrote a bare 'edit chart/diagram' and the assistant asked how."""
    turn = (turn_text or "").strip()
    ans = (answer or "").strip()
    if not turn or not ans:
        return False
    noun_ok = (
        bool(re.search(r"график|диаграмм|чарт|визуал", turn, re.IGNORECASE))
        if kind == "chart"
        else bool(re.search(r"схем|диаграмм|блок", turn, re.IGNORECASE))
    )
    if not noun_ok or not _BARE_VISUAL_EDIT_CUE.search(turn):
        return False
    if _CONCRETE_VISUAL_SPEC.search(turn):
        return False
    return bool(_CLARIFY_ANSWER_CUE.search(ans))


def run_pipeline(
    source: Path,
    *,
    project_root: Path,
    formats: set[str] | None = None,
    dry_run: bool = False,
    intent: str | None = None,
    max_images: int | None = None,
    max_charts: int | None = None,
    max_diagrams: int | None = None,
    run_id: str | None = None,
    on_stage: Callable[[str, str | None], None] | None = None,
    user_figures: list[dict[str, Any]] | None = None,
    output_mode: str = "auto",
    prior_run_id: str | None = None,
) -> Path:
    formats = resolve_pipeline_formats(formats)
    root = project_root.resolve()
    run_id, text_path, work, out, logs = prepare_run_dirs(
        source, project_root=root, run_id=run_id
    )
    stem = text_path.stem
    stamp = run_id.rsplit("_", 1)[-1] if "_" in run_id else datetime.now(
        timezone.utc
    ).strftime("%Y%m%dT%H%M%SZ")

    images_budget = max_images_from_env() if max_images is None else max(0, int(max_images))
    charts_budget = max_charts_from_env() if max_charts is None else max(0, int(max_charts))
    from case3.diagrams import clamp_diagram_budget

    diagrams_budget = clamp_diagram_budget(max_diagrams)
    mode = (output_mode or "auto").strip().lower()
    if mode not in {"report", "diagram", "presentation", "auto", "chat"}:
        mode = "auto"
    if mode == "presentation":
        formats = set()
    user_figs = list(user_figures or [])
    # Opt-in for generated fig_*; uploads (usr_*) still merge when attached.
    source_peek = ""
    if text_path.is_file():
        try:
            source_peek = text_path.read_text(encoding="utf-8")
        except OSError:
            source_peek = ""
    from case3.image_opt_in import apply_gen_image_budget, wants_generated_images

    images_opt_in = wants_generated_images(intent, source_peek)
    # Presentation + uploads: do not leave budget for invented fig_*.
    llm_image_budget, images_budget = apply_gen_image_budget(
        images_budget,
        len(user_figs),
        mode=mode,
        opt_in=images_opt_in,
    )

    # Heartbeat BEFORE FileHandler / load_timings: on Win those can stall (AV lock)
    # and Liber sat forever on status=running stage=queued («Читаю Source»).
    # Preserve deck style stamped by /api/run (auto-kick slides needs structure_id).
    from case3.chart_style import palette_from_intent
    from case3.run_meta import read_meta as _read_meta_desk

    prev_desk = _read_meta_desk(out)
    chart_palette0 = palette_from_intent(intent or "")
    meta: dict = {
        "run_id": run_id,
        "source": str(text_path),
        "intent": intent,
        "formats": sorted(formats),
        "output_mode": mode,
        "dry_run": dry_run,
        "max_images": images_budget,
        "max_charts": charts_budget,
        "max_diagrams": diagrams_budget,
        "images_opt_in": images_opt_in,
        "user_figures": [f.get("id") for f in user_figs],
        "chart_palette": chart_palette0,
        "started_at": stamp,
        "status": "running",
        "stage": "llm",
        "stage_detail": "жду модель…",
    }
    merge_desk_slides_fields(meta, prev_desk)
    carry_chat_prompt(meta, prev_desk)
    if prior_run_id and str(prior_run_id).strip():
        meta["prior_run_id"] = str(prior_run_id).strip()
    EVENTS.ensure(run_id)
    from case3.run_events import note_craft_stage

    note_craft_stage(meta, stage="llm", scope="pipeline", detail="жду модель…")
    _write_meta(meta, out, logs)
    EVENTS.publish_stage(run_id, "llm", detail="жду модель…", scope="pipeline")

    handler = _attach_pipeline_log_handler(logs, run_id)
    root_logger = logging.getLogger("case3")
    _run_token = _PIPELINE_RUN_ID.set(run_id)

    from case3.stage_eta import load_timings

    load_timings(root)

    def bump(stage: str, detail: str | None = None) -> None:
        raise_if_cancelled(out)
        _set_stage(
            meta, out, logs, stage, detail=detail, project_root=root
        )
        if on_stage:
            on_stage(stage, detail)

    from case3.input_validation import (
        InsufficientDataError,
        user_text_before_ui,
        validate_input_heuristics,
        with_default_brief,
    )

    def _handle_insufficient_data(msg: str) -> Path:
        log.info("insufficient data run_id=%s mode=%s: %s", run_id, mode, msg)
        meta["insufficient_data"] = True
        meta["status"] = "ok"
        meta["stage"] = "ok"
        meta["artifacts"] = {}
        meta["chat_summary"] = msg
        meta.pop("stage_detail", None)
        _write_meta(meta, out, logs)
        (out / "chat_summary.txt").write_text(msg, encoding="utf-8")
        (logs / "chat_summary.txt").write_text(msg, encoding="utf-8")
        BUS.start(run_id)
        BUS.finish(run_id, msg, "ok")
        EVENTS.publish_stage(run_id, "ok", detail="Недостаточно данных", scope="pipeline")
        EVENTS.publish_terminal(run_id, "ok", recap={"headline": "Недостаточно данных", "body": msg})
        return out

    def _emit_chat(phase: str, text: str, kind: str) -> None:
        if text:
            EVENTS.publish(
                run_id,
                {"event": "chat", "phase": phase, "text": text, "mode": kind},
            )

    def _finish_chat_answer(user_text: str, source_text: str) -> Path:
        bump("chat", "отвечаю…")
        from case3.chat_turn import (
            chat_fallback,
            chat_report_block,
            dashboard_landing,
            generate_chat_charts,
            generate_chat_diagram,
            try_chat_answer,
        )
        from case3.dashboard_source import derivative_block
        from case3.input_validation import current_turn_user_text
        from case3.turn_route import (
            answer_declines_chart,
            should_auto_chat_chart,
            wants_chat_chart,
            wants_chat_diagram,
        )

        turn_text = current_turn_user_text(user_text)
        enriched_source = source_text or ""
        def _prior_chat_visuals(prev_id: str) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
            if not prev_id:
                return None, None
            from case3.chat_memory import load_chain_dirs

            found_chart: dict[str, Any] | None = None
            found_diag: dict[str, Any] | None = None
            for _rid, prev_out, prev_meta in reversed(load_chain_dirs(root, prev_id)):
                if any(prev_out.glob("*.pdf")) or any(prev_out.glob("*.docx")):
                    continue
                fj_file = prev_out / "figures.json"
                if not fj_file.is_file():
                    continue
                try:
                    prev_fj = json.loads(fj_file.read_text(encoding="utf-8"))
                except (OSError, json.JSONDecodeError):
                    continue
                if not isinstance(prev_fj, dict):
                    continue
                m_status = prev_meta.get("media_status") if isinstance(prev_meta, dict) else {}
                if not isinstance(m_status, dict):
                    m_status = {}
                if found_chart is None:
                    p_charts = [c for c in (prev_fj.get("charts") or []) if isinstance(c, dict)]
                    ok_charts = [
                        c
                        for c in p_charts
                        if not isinstance(m_status.get(c.get("id")), dict)
                        or m_status[c["id"]].get("ok") is not False
                    ]
                    if ok_charts:
                        found_chart = ok_charts[-1]
                    elif p_charts:
                        found_chart = p_charts[-1]
                if found_diag is None:
                    p_diags = [d for d in (prev_fj.get("diagrams") or []) if isinstance(d, dict)]
                    ok_diags = [
                        d
                        for d in p_diags
                        if not isinstance(m_status.get(d.get("id")), dict)
                        or m_status[d["id"]].get("ok") is not False
                    ]
                    if ok_diags:
                        found_diag = ok_diags[-1]
                    elif p_diags:
                        found_diag = p_diags[-1]
                if found_chart is not None and found_diag is not None:
                    break
            return found_chart, found_diag

        prior = str(meta.get("prior_run_id") or "")
        prev_chart, prev_diagram = _prior_chat_visuals(prior)
        picture = wants_chat_chart(turn_text, has_prior_chart=prev_chart is not None) or wants_chat_diagram(
            turn_text, has_prior_diagram=prev_diagram is not None
        )
        from case3.chat_memory import (
            dashboard_screens,
            latest_dashboard_note,
            source_for_followup,
        )
        enriched_source = source_for_followup(
            enriched_source,
            dashboard_screens(root, prior),
            turn_text,
            picture=picture,
        )
        landing = dashboard_landing(turn_text)
        asked = user_text
        if not landing:
            remembered = latest_dashboard_note(root, prior)
            if remembered:
                asked = (
                    user_text
                    + "\n\nЗаметка по этому экрану (уже сказано, целиком не повторяй):\n"
                    + remembered
                )
        if "## Производные" not in enriched_source:
            deriv = derivative_block(enriched_source)
            if deriv:
                enriched_source = (enriched_source + "\n\n## Производные\n\n" + deriv).strip()

        if user_figs:
            materialize_user_figures(user_figs, out / "figures")
        charts_list: list[dict[str, Any]] = []
        diagrams: list[dict[str, Any]] = []
        media_status: dict[str, dict[str, Any]] = {}
        if dry_run:
            answer = "Разбор останется в чате. В пробном прогоне модель не вызывается."
            BUS.start(run_id)
            BUS.publish(run_id, answer)
        else:
            report = chat_report_block(root, prior, turn_text)
            BUS.start(run_id)
            answer = try_chat_answer(
                enriched_source,
                asked,
                report=report,
                on_delta=lambda piece: BUS.publish(run_id, piece),
                on_replace=lambda full: BUS.replace(run_id, full),
            )
            explicit_chart = wants_chat_chart(
                turn_text, has_prior_chart=prev_chart is not None
            ) and not _is_clarifying_visual_request(turn_text, answer, kind="chart")
            wants_diag = wants_chat_diagram(
                turn_text, has_prior_diagram=prev_diagram is not None
            ) and not _is_clarifying_visual_request(turn_text, answer, kind="diagram")
            clarifying_visual = _is_clarifying_visual_request(
                turn_text, answer, kind="chart"
            ) or _is_clarifying_visual_request(turn_text, answer, kind="diagram")
            auto_chart = (
                not explicit_chart
                and not wants_diag
                and not clarifying_visual
                and not landing
                and not answer_declines_chart(answer)
                and should_auto_chat_chart(
                    turn_text,
                    enriched_source,
                    answer,
                    has_prior_diagram=prev_diagram is not None,
                )
            )
            eff_charts_budget = charts_budget or (1 if prev_chart is not None else 0)
            if (explicit_chart or auto_chart) and eff_charts_budget > 0:
                bump("charts", "рисую график…")
                charts_list, media_status = generate_chat_charts(
                    enriched_source,
                    intent or user_text,
                    max_charts=eff_charts_budget if explicit_chart else 1,
                    palette_id=str(meta.get("chart_palette") or "atelier"),
                    figs_dir=out / "figures",
                    charts_dir=work / "charts",
                    extra_context=answer,
                    previous_chart=prev_chart,
                )
            if wants_diag:
                bump("charts", "рисую схему…")
                diagrams, diagram_status = generate_chat_diagram(
                    enriched_source,
                    intent or user_text,
                    palette_id=str(meta.get("chart_palette") or "atelier"),
                    figs_dir=out / "figures",
                    extra_context=answer,
                    previous_diagram=prev_diagram,
                )
                media_status.update(diagram_status)
                if diagrams:
                    meta["diagrams_planned"] = [d.get("id") for d in diagrams if d.get("id")]
                    meta["diagrams_ok"] = sum(
                        1 for v in diagram_status.values() if isinstance(v, dict) and v.get("ok")
                    )
        meta["output_mode"] = "chat"
        meta["chat_summary"] = answer
        meta["chat_opening"] = answer
        if landing and not dry_run and answer and answer != chat_fallback():
            meta["dashboard_note"] = answer
            (out / "dashboard_note.md").write_text(
                "# Заметка по экрану\n\n" + answer + "\n",
                encoding="utf-8",
            )
        from case3.chat_turn import session_title

        meta["title"] = session_title(user_text, enriched_source)
        if charts_list or diagrams:
            (out / "figures.json").write_text(
                json.dumps(
                    {
                        "figures": [],
                        "charts": charts_list,
                        "diagrams": diagrams,
                    },
                    ensure_ascii=False,
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
            )
            meta["media_status"] = media_status
        if charts_list:
            meta["charts_planned"] = [c["id"] for c in charts_list if c.get("id")]
            meta["charts_ok"] = sum(
                1 for k, v in media_status.items() if k.startswith("cht_") and isinstance(v, dict) and v.get("ok")
            )
        if not dry_run and answer == chat_fallback():
            log.error("chat answer fell back to unavailable message run_id=%s", run_id)
            meta["summary_status"] = "error"
        else:
            meta["summary_status"] = "ok"
        meta["status"] = "ok"
        meta["stage"] = "ok"
        meta["artifacts"] = {}
        meta.pop("stage_detail", None)
        _write_meta(meta, out, logs)
        (out / "chat_summary.txt").write_text(answer, encoding="utf-8")
        (logs / "chat_summary.txt").write_text(answer, encoding="utf-8")
        BUS.finish(run_id, answer, "ok")
        EVENTS.publish_stage(run_id, "ok", detail="Ответ в чате", scope="pipeline")
        EVENTS.publish_terminal(run_id, "ok")
        return out

    def _publish_stage_lines(kind: str, user_text: str) -> None:
        """Model sentences for steps. The chat reveals one only when that step starts."""
        if dry_run:
            EVENTS.publish(run_id, {"event": "narration", "lines": {}})
            return
        try:
            from case3.chat_turn import _client
            from case3.stage_narration import narrate_stages

            lines = narrate_stages(
                user_text,
                kind,
                lambda **kw: _client(2048, 45.0).complete(**kw),
            )
        except Exception:
            log.exception("stage narration failed run_id=%s", run_id)
            lines = {}
        meta["stage_lines"] = lines
        EVENTS.publish(run_id, {"event": "narration", "lines": lines})

    def _speak_before_artifact(kind: str, user_text: str) -> None:
        from case3.chat_turn import opening_fallback, try_opening

        if dry_run:
            spoken = opening_fallback(kind, user_text)
            _emit_chat("opening", spoken, kind)
        else:
            spoken = try_opening(
                kind,
                user_text,
                on_delta=lambda piece: _emit_chat("opening", piece, kind),
            )
        meta["chat_opening"] = spoken
        _write_meta(meta, out, logs)

    try:
        # Tier 1: Restore prior dashboard/document source before input validation.
        source_raw = text_path.read_text(encoding="utf-8") if text_path.is_file() else ""
        user_intent = user_text_before_ui(intent)
        from case3.input_validation import current_turn_user_text

        turn_text = current_turn_user_text(intent)
        from case3.chat_memory import (
            dashboard_screens,
            prior_document_source,
            source_for_followup,
        )
        from case3.turn_route import (
            should_auto_chat_chart,
            wants_chat_chart,
            wants_chat_diagram,
        )

        prior = str(meta.get("prior_run_id") or "")
        if prior:
            screened = source_for_followup(
                source_raw,
                dashboard_screens(root, prior),
                turn_text,
                picture=(
                    wants_chat_chart(turn_text)
                    or wants_chat_diagram(turn_text)
                    or should_auto_chat_chart(turn_text, source_raw)
                ),
            )
            if screened.strip() and screened != source_raw:
                source_raw = screened
                text_path = work / "screen_source.md"
                text_path.write_text(screened, encoding="utf-8")
            elif (
                not source_raw.strip()
                or source_raw.strip() == turn_text.strip()
                or len(source_raw.strip()) < 240
            ):
                fallback_doc = prior_document_source(root, prior)
                if fallback_doc.strip():
                    source_raw = fallback_doc
                    text_path = work / "screen_source.md"
                    text_path.write_text(fallback_doc, encoding="utf-8")

        valid_in, refusal_msg = validate_input_heuristics(
            source_raw,
            turn_text,
            output_mode=mode,
            has_attachments=bool(user_figs),
        )
        if not valid_in:
            return _handle_insufficient_data(refusal_msg or "В запросе недостаточно данных.")
        if not turn_text.strip():
            intent = with_default_brief(intent, turn_text)

        from case3.dashboard_source import derivative_block

        if "## Производные" not in source_raw:
            deriv = derivative_block(source_raw)
            if deriv:
                source_raw = (source_raw + "\n\n## Производные\n\n" + deriv).strip()
        if source_raw != (text_path.read_text(encoding="utf-8") if text_path.is_file() else ""):
            text_path = out / "source_effective.md"
            text_path.write_text(source_raw, encoding="utf-8")
            meta["source"] = str(text_path)
            _write_meta(meta, out, logs)

        if mode == "chat":
            from case3.chat_memory import focus_source

            asked = str(meta.get("chat_prompt") or turn_text)
            return _finish_chat_answer(user_intent, focus_source(source_raw, asked))
        if mode in {"report", "diagram", "presentation"}:
            spoken_about = turn_text.strip()
            attached = source_raw.strip()
            if attached and attached != spoken_about:
                clip = " ".join(attached.split())
                if len(clip) > 420:
                    clip = clip[:419].rstrip() + "…"
                spoken_about = f"{spoken_about}\n\nМатериал:\n{clip}".strip()
            _speak_before_artifact(mode, spoken_about or attached[:800])
            _publish_stage_lines(mode, spoken_about or attached[:800])

        # Re-enter llm for ETA / craft cursor (stage id unchanged → light bump).
        bump("llm", "жду модель…")
        tex_path = work / f"{stem}.tex"
        if mode == "presentation":
            # Presentation builds slides via slides_job; skip heavy LaTeX article prose.
            from case3.chart_style import palette_from_intent
            from case3.chat_memory import focus_source
            from case3.chat_turn import generate_chat_charts
            from case3.diagram_generate import complete_diagrams
            from case3.llm_client import LLMClient, LLMConfig

            asked = str(meta.get("chat_prompt") or "")
            focused = focus_source(source_raw, asked) or source_raw
            figures = merge_user_figures([], user_figs, max_images=images_budget)
            charts = []
            diagrams = []
            if charts_budget > 0 and not dry_run:
                charts, _chart_status = generate_chat_charts(
                    focused,
                    intent or "",
                    max_charts=min(charts_budget, 4),
                    palette_id=str(meta.get("chart_palette") or "atelier"),
                    figs_dir=work / "figures",
                    charts_dir=work / "charts",
                )
            if diagrams_budget > 0 and not dry_run:
                try:
                    diagrams = complete_diagrams(
                        intent=intent or "",
                        source_text=focused,
                        max_diagrams=diagrams_budget,
                        client=LLMClient(LLMConfig.from_env()),
                        palette=palette_from_intent(intent or "")
                        or str(meta.get("chart_palette") or "atelier"),
                        cancel_check=lambda: raise_if_cancelled(out),
                    )
                except Exception as exc:  # noqa: BLE001
                    log.warning("presentation diagrams failed (soft): %s", exc)
                    diagrams = []
            from case3.tex_safe import escape_tex_text

            plain_intent = str(meta.get("chat_prompt") or "").strip()
            if not plain_intent:
                plain_intent = (intent or "").split("\n\n", 1)[0].strip()
            title = escape_tex_text(plain_intent[:60].strip() or "Презентация")
            stub_lines = [
                f"\\documentclass{{article}}",
                f"\\title{{{title}}}",
                f"\\begin{{document}}",
                f"\\maketitle",
                f"Презентация формируется по данным запроса.",
            ]
            for ch in charts:
                if isinstance(ch, dict) and ch.get("id"):
                    stub_lines.append(f"%CASE3_CHART:{ch['id']}%")
            for dg in diagrams:
                if isinstance(dg, dict) and dg.get("id"):
                    stub_lines.append(f"%CASE3_DIAG:{dg['id']}%")
            stub_lines.append("\\end{document}\n")
            stub = "\n".join(stub_lines)
            tex_path.write_text(stub, encoding="utf-8")
            fj = {"figures": figures, "charts": charts, "diagrams": diagrams}
            fj_path = work / "figures.json"
            fj_path.write_text(
                json.dumps(fj, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
        elif mode == "diagram":
            from case3.chart_style import palette_from_intent
            from case3.diagram_generate import complete_diagrams
            from case3.llm_client import LLMClient, LLMConfig

            source_text = text_path.read_text(encoding="utf-8")
            pal = palette_from_intent(intent or "")
            cfg = LLMConfig.from_env()
            diag_cfg = LLMConfig(
                base_url=cfg.base_url,
                api_key=cfg.api_key,
                api_keys=cfg.api_keys,
                model=cfg.model,
                timeout_s=min(cfg.timeout_s, 90.0),
                max_retries=1,
                temperature=cfg.temperature,
                reasoning=cfg.reasoning,
                max_tokens=max(cfg.max_tokens, 8192),
            )
            if dry_run:
                diagrams = []
            else:
                try:
                    diagrams = complete_diagrams(
                        intent=intent,
                        source_text=source_text,
                        max_diagrams=diagrams_budget,
                        client=LLMClient(diag_cfg),
                        palette=pal,
                        cancel_check=lambda: raise_if_cancelled(out),
                    )
                except InsufficientDataError as exc:
                    return _handle_insufficient_data(exc.message)
            from case3.tex_safe import escape_tex_text

            figures = []
            charts = []
            title = escape_tex_text((intent or "").split("\n", 1)[0][:60].strip() or "Схема")
            safe_source_head = escape_tex_text(source_text[:1000])
            stub = (
                f"\\documentclass{{article}}\n\\title{{{title}}}\n\\begin{{document}}\n"
                f"\\maketitle\n{safe_source_head}\n\\end{{document}}\n"
            )
            tex_path.write_text(stub, encoding="utf-8")
            fj = {"figures": [], "charts": [], "diagrams": diagrams}
            fj_path = work / "figures.json"
            fj_path.write_text(
                json.dumps(fj, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
        else:
            try:
                from case3.chat_memory import focus_source

                asked = str(meta.get("chat_prompt") or "")
                focused = focus_source(source_raw, asked)
                gen_path = text_path
                if focused and focused != source_raw:
                    gen_path = work / "focus_source.txt"
                    gen_path.write_text(focused, encoding="utf-8")
                _, figures, charts, diagrams = generate_document(
                    gen_path,
                    out_tex=tex_path,
                    intent=intent,
                    gold_dir=root / "prompt" / "gold",
                    dry_run=dry_run,
                    max_images=llm_image_budget,
                    max_charts=charts_budget,
                    max_diagrams=diagrams_budget,
                    cancel_check=lambda: raise_if_cancelled(out),
                    user_figures=user_figs,
                )
            except InsufficientDataError as exc:
                return _handle_insufficient_data(exc.message)
            figures = merge_user_figures(figures, user_figs, max_images=images_budget)
            raw_tex = tex_path.read_text(encoding="utf-8")
            tex_path.write_text(ensure_user_slots_in_tex(raw_tex, user_figs), encoding="utf-8")
            # Persist merged figures.json for Liber edit / preview
            fj_path = work / "figures.json"
            if fj_path.is_file():
                try:
                    fj = json.loads(fj_path.read_text(encoding="utf-8"))
                except (OSError, json.JSONDecodeError):
                    fj = {}
            else:
                fj = {}

        # Mode «Схема»: if first LLM pass returned no diagrams (CoT / missing JSON),
        # dedicated regenerate via diagram_generate.md (same as Liber «Ещё вариант»).
        if mode == "diagram" and not diagrams and not dry_run and diagrams_budget >= 1:
            bump("diagram_generate", "повтор: только Mermaid JSON…")
            try:
                from case3.chart_style import palette_from_intent
                from case3.diagram_generate import complete_diagrams
                from case3.llm_client import LLMClient, LLMConfig

                source_text = text_path.read_text(encoding="utf-8")
                pal = palette_from_intent(intent or "")
                diagrams = complete_diagrams(
                    intent=intent,
                    source_text=source_text,
                    max_diagrams=diagrams_budget,
                    client=LLMClient(LLMConfig.from_env()),
                    palette=pal,
                    cancel_check=lambda: raise_if_cancelled(out),
                )
                meta["diagrams_recovery"] = "generate" if diagrams else "empty"
                log.info(
                    "diagram recovery → %d diagrams (budget=%d)",
                    len(diagrams),
                    diagrams_budget,
                )
            except Exception as exc:  # noqa: BLE001
                log.warning("diagram recovery failed: %s", exc)
                meta["diagrams_recovery_error"] = str(exc)[:200]

        # Mode «Схема»: optional second LLM pass. Skip when draft already has Mermaid
        # (default) — set CASE3_DIAGRAM_REPAIR=1 to force. Soft-fail keeps draft.
        if mode == "diagram" and diagrams and not dry_run:
            import os as _os

            force_repair = (_os.environ.get("CASE3_DIAGRAM_REPAIR") or "").strip() == "1"

            def _draft_has_mermaid(d: dict) -> bool:
                body = str(d.get("mermaid") or d.get("code") or "").strip()
                return len(body) >= 40

            if not force_repair and all(
                isinstance(d, dict) and _draft_has_mermaid(d) for d in diagrams
            ):
                meta["diagrams_repair_skipped"] = "draft_has_mermaid"
                log.info(
                    "diagram_repair skipped — draft mermaid present "
                    "(CASE3_DIAGRAM_REPAIR=1 to force)"
                )
            else:
                bump("diagram_repair", "второй вызов модели…")
                from case3.diagram_repair import repair_diagrams
                from case3.llm_client import LLMClient, LLMConfig

                fj["diagrams_draft"] = diagrams
                source_text = text_path.read_text(encoding="utf-8")
                from case3.chart_style import palette_from_intent

                diagrams, repair_meta = repair_diagrams(
                    diagrams,
                    source=source_text,
                    intent=intent or "",
                    max_diagrams=diagrams_budget,
                    client=LLMClient(LLMConfig.from_env()),
                    palette=palette_from_intent(intent or ""),
                )
                meta["diagrams_repaired"] = bool(repair_meta.get("diagrams_repaired"))
                meta["diagrams_draft_slop"] = bool(repair_meta.get("diagrams_draft_slop"))

        fj["figures"] = figures
        fj["charts"] = charts
        fj["diagrams"] = diagrams
        # Persist ChartSeriesIR for native PPTX (prefer over HTML regex later).
        from case3.slides_chart_data import attach_series_ir_to_charts

        attach_series_ir_to_charts(charts)
        fj["charts"] = charts
        # Keep diagrams_dropped from generate if present (soft-fail telemetry).
        fj_path.write_text(json.dumps(fj, ensure_ascii=False, indent=2), encoding="utf-8")

        meta["figures_planned"] = [f["id"] for f in figures]
        meta["charts_planned"] = [c["id"] for c in charts]
        meta["diagrams_planned"] = [d["id"] for d in diagrams]
        meta["diagrams_ok"] = len(diagrams)
        dropped = fj.get("diagrams_dropped") if isinstance(fj.get("diagrams_dropped"), list) else []
        if dropped:
            meta["diagrams_dropped"] = dropped
        _write_meta(meta, out, logs)

        status: dict = {}
        figs_dir = work / "figures"

        _pipeline_materialize_media(
            status=status,
            figures=figures,
            charts=charts,
            diagrams=diagrams,
            fj=fj,
            fj_path=fj_path,
            figs_dir=figs_dir,
            work=work,
            images_budget=images_budget,
            charts_budget=charts_budget,
            dry_run=dry_run,
            intent=intent,
            meta=meta,
            bump=bump,
            run_id=run_id,
            only_missing=False,
            publish_events=True,
        )

        meta["media_status"] = status
        (work / "status.json").write_text(
            json.dumps(status, ensure_ascii=False, indent=2), encoding="utf-8"
        )

        # Log BEFORE bump: Win AV can stall meta write; without this line stage=inject
        # looked like a hang inside inject with no pipeline.log progress.
        log.info(
            "inject: about to bump run_id=%s figs=%d charts=%d diags=%d",
            run_id,
            len(figures or []),
            len(charts or []),
            len(diagrams or []),
        )
        bump("inject")
        log.info("inject: write_injected start run_id=%s", run_id)
        write_injected(
            tex_path, figures, status, charts=charts, diagrams=diagrams
        )
        log.info("inject: write_injected done, copy → out/")

        shutil.copy2(tex_path, out / tex_path.name)
        for name in ("figures.json", "status.json", f"{stem}.raw_model.txt"):
            p = work / name
            if p.is_file():
                shutil.copy2(p, out / name)
        # Debug prompts dump (CASE3_DUMP_PROMPTS) lives under work/ — mirror to out/
        prompts_src = work / "prompts_used"
        if prompts_src.is_dir():
            prompts_dst = out / "prompts_used"
            if prompts_dst.exists():
                shutil.rmtree(prompts_dst)
            shutil.copytree(prompts_src, prompts_dst)
        if figs_dir.is_dir() and any(figs_dir.glob("*.png")):
            dest = out / "figures"
            if dest.exists():
                shutil.rmtree(dest)
            shutil.copytree(figs_dir, dest)

        bump("latex" if formats else "summary")
        log.info(
            "post-inject stage=%s formats=%s (docker next if pdf/docx)",
            "latex" if formats else "summary",
            sorted(formats),
        )
        artifacts = _pipeline_print_and_summary(
            meta=meta,
            out=out,
            logs=logs,
            root=root,
            run_id=run_id,
            tex_path=tex_path,
            figures=figures,
            charts=charts,
            diagrams=diagrams,
            status=status,
            figs_dir=figs_dir,
            formats=formats,
            dry_run=dry_run,
            mode=mode,
            intent=intent,
            bump=bump,
            force_render=False,
        )

        raise_if_cancelled(out)
        meta["artifacts"] = {k: str(v) for k, v in artifacts.items()}
        meta["status"] = "ok"
        meta["stage"] = "ok"
        meta.pop("stage_detail", None)
        meta.pop("cancel_requested", None)
        _write_meta(meta, out, logs)
        if meta.get("status") == "cancelled":
            raise RunCancelled("cancelled by user")
        EVENTS.scan_artifacts(run_id, out)
        # Presentation: slides job continues on the same bus — defer terminal.
        if mode != "presentation":
            chart_ids = [
                str(c.get("id") or "")
                for c in (charts or [])
                if isinstance(c, dict) and c.get("id")
            ]
            fig_ids = [
                str(f.get("id") or "")
                for f in (figures or [])
                if isinstance(f, dict) and f.get("id")
            ]
            charts_ok = sum(
                1 for cid in chart_ids if _media_ok_on_disk(cid, status, figs_dir)
            )
            figures_ok = sum(
                1 for fid in fig_ids if _media_ok_on_disk(fid, status, figs_dir)
            )
            EVENTS.publish_terminal(
                run_id,
                "ok",
                recap=EVENTS.success_recap(
                    run_id, charts=charts_ok, figures=figures_ok
                ),
            )
        else:
            EVENTS.publish_stage(run_id, "pipeline_ok", scope="pipeline")
        log.info("done run_id=%s out=%s", run_id, out)
    except RunCancelled:
        meta["status"] = "cancelled"
        meta["stage"] = "cancelled"
        meta["error"] = "Остановлено"
        meta.pop("stage_detail", None)
        log.info("pipeline cancelled run_id=%s", run_id)
        _write_meta(meta, out, logs)
        EVENTS.publish_terminal(run_id, "cancelled", error="Остановлено")
        return out
    except Exception as exc:
        _record_failed_stage(meta)
        meta["status"] = "error"
        meta["stage"] = "error"
        log_path = getattr(exc, "log_path", None) if isinstance(exc, RenderError) else None
        meta.update(
            _attach_error_diagnostics(
                meta,
                logs_dir=logs,
                error=str(exc),
                log_path=Path(log_path) if log_path else None,
            )
        )
        meta["traceback"] = traceback.format_exc()
        log.exception("pipeline failed")
        (logs / "error.txt").write_text(meta["traceback"], encoding="utf-8")
        _write_meta(meta, out, logs)
        _abort_open_summary(run_id, str(meta.get("error") or exc))
        from case3.stage_eta import error_hint

        EVENTS.publish_terminal(
            run_id,
            "error",
            error=str(meta.get("error") or exc),
            hint=error_hint(exc, stage=str(meta.get("stage") or "")),
        )
        raise PipelineError(
            str(meta.get("error") or exc),
            run_id=run_id,
            out_dir=out,
            logs_dir=logs,
            meta=meta,
        ) from exc
    finally:
        root_logger.removeHandler(handler)
        handler.close()
        _PIPELINE_RUN_ID.reset(_run_token)

    log.info("done run_id=%s out=%s", run_id, out)
    return out
