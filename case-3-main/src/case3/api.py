"""FastAPI demo wrapper around run_pipeline (for React UI)."""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import shutil
import threading
from contextlib import asynccontextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from fastapi import Body, FastAPI, File, Form, Header, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import (
    FileResponse,
    JSONResponse,
    RedirectResponse,
    Response,
)

from case3.chart_html import CHART_TYPES
from case3.chart_style import palette_public
from case3.charts import max_charts_from_env, probe_playwright_chromium
from case3.diagrams import DIAGRAMS_HARD_MAX, max_diagrams_from_env
from case3.envfile import load_dotenv
from case3.generate import max_images_from_env, resolve_text_file
from case3.desk_health import build_desk_probes, probe_soffice, probe_vision
from case3.image_api import image_api_configured, probe_image_api
from case3.api_photo import quick_photo_edit
from case3.run_events import EVENTS
from case3.pipeline import PipelineError, prepare_run_dirs, run_pipeline
from case3.render import IMAGE, ensure_image, is_docker_warmed
from case3.dashboard_remote import (
    DashboardRemoteError,
    capture_documents,
    fetch_export,
    fetch_shot_payload,
    fetch_dashboard_preview,
    fetch_dashboards,
    fetch_filter_catalog,
    open_named_dashboard,
    finish_dashboard_phrase,
    might_ask_dashboard,
    plan_dashboard_phrase,
    service_base,
    viewer_url,
)
from case3.dashboard_source import DashboardSourceError, parse_dashboard
from case3.source_ingest import (
    DEFAULT_MAX_MARKDOWN_BYTES,
    IngestDependencyError,
    OfficeConvertError,
    ScanPdfError,
    SourceIngestError,
    UnsupportedSourceFormatError,
    file_to_markdown,
)
from case3.user_photos import (
    UserPhotoError,
    captions_from_intent,
    clip_photo_files,
    save_user_photos,
)
from case3.intent_compose import build_intent_from_ui
from case3 import run_store
from case3.run_store import (
    RUN_ID_OK as _RUN_ID_OK,
    build_preview_payload as _build_preview_payload,
    load_diagrams_from_out as _load_diagrams_from_out,
    parse_formats_form,
    resolve_run_dir as _resolve_run_dir,
    safe_run_file as _safe_run_file,
)

log = logging.getLogger("case3.api")

# FastAPI calls Request.form() with Starlette's 1 MiB default, so the 2 MiB
# source check never ran. Parts must fit the largest accepted upload
# (photos or born-digital PDF/DOCX ingest).
_SOURCE_MAX_BYTES = 2 * 1024 * 1024
_INGEST_MAX_BYTES = 20 * 1024 * 1024
_FORM_PART_MAX_BYTES = _INGEST_MAX_BYTES
_INGEST_ID_OK = re.compile(r"^[0-9]{8}T[0-9]{6}Z_[0-9a-f]{6}$")


def _raise_form_part_limit() -> None:
    """Let form fields reach the source and photo checks above Starlette's 1 MiB."""
    from starlette.requests import Request

    if getattr(Request.form, "_case3_part_limit", False):
        return
    original = Request.form

    def form(self: Request, *args: Any, **kwargs: Any):  # type: ignore[no-untyped-def]
        current = int(kwargs.get("max_part_size") or 0)
        kwargs["max_part_size"] = max(current, _FORM_PART_MAX_BYTES)
        return original(self, *args, **kwargs)

    form._case3_part_limit = True  # type: ignore[attr-defined]
    Request.form = form  # type: ignore[method-assign]


_raise_form_part_limit()

load_dotenv(run_store.ROOT / ".env")


def __getattr__(name: str):
    """``api.ROOT`` always tracks ``run_store.ROOT`` (canonical for Liber runs)."""
    if name == "ROOT":
        return run_store.ROOT
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

@asynccontextmanager
async def lifespan(app: FastAPI):
    from case3.render import warmup_docker
    warmup_docker(background=True)
    try:
        settle_orphaned_runs()
    except Exception:  # noqa: BLE001
        log.exception("orphan run settle failed")
    try:
        recover_persisted_pipeline()
    except Exception:  # noqa: BLE001
        log.exception("pipeline queue recover failed")
    yield


app = FastAPI(title="case-3 demo", version="0.4.0", lifespan=lifespan)

_RUN_PATH_RE = re.compile(r"^/api/runs/([A-Za-z0-9_.-]+)(?:/|$)")


@app.middleware("http")
async def _enforce_run_workspace_middleware(request: Request, call_next):
    match = _RUN_PATH_RE.match(request.url.path)
    if match:
        run_id = match.group(1)
        x_wid = request.headers.get("X-Workspace-Id")
        if x_wid and _RUN_ID_OK.match(run_id):
            out_dir = (run_store.ROOT / "runs" / "out" / run_id).resolve()
            out_root = (run_store.ROOT / "runs" / "out").resolve()
            if out_dir.is_relative_to(out_root):
                meta_dir = (
                    out_dir
                    if (out_dir / "meta.json").is_file()
                    else (run_store.ROOT / "runs" / "logs" / run_id)
                )
                try:
                    run_store.assert_run_workspace(meta_dir, x_wid)
                except HTTPException as exc:
                    return JSONResponse(
                        status_code=exc.status_code, content={"detail": exc.detail}
                    )
    return await call_next(request)


_cors_env = (os.environ.get("CASE3_CORS_ORIGINS") or "").strip()
_cors_origins = (
    [o.strip() for o in _cors_env.split(",") if o.strip()]
    if _cors_env
    else [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:4173",
        "http://127.0.0.1:4173",
    ]
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_origin_regex=None if _cors_env else r"https?://.*",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def root() -> RedirectResponse:
    """Redirect API root to OpenAPI docs; UI is on :5173."""
    return RedirectResponse("/docs")


def _parse_chart_types(raw: str | None) -> list[str]:
    if not raw:
        return []
    parts = re.split(r"[,;\s]+", raw.strip())
    return [p for p in parts if p in CHART_TYPES]


def _as_bool(raw: str | bool | None) -> bool:
    if isinstance(raw, bool):
        return raw
    return str(raw or "").strip().lower() in {"1", "true", "yes", "on"}


_HEALTH_CACHE_TTL_S = 60.0
_health_cache_lock = threading.Lock()
_health_cache_payload: dict[str, Any] | None = None
_health_cache_ts: float = 0.0
_health_cache_key: tuple[Any, ...] | None = None


def clear_health_cache() -> None:
    """Invalidate the cached /api/health snapshot."""
    global _health_cache_payload, _health_cache_ts, _health_cache_key
    with _health_cache_lock:
        _health_cache_payload = None
        _health_cache_ts = 0.0
        _health_cache_key = None


def _current_health_env_key() -> tuple[Any, ...]:
    return (
        os.environ.get("VISION_API_BASE_URL", ""),
        os.environ.get("IMAGE_API_BASE_URL", ""),
        os.environ.get("KANDINSKY_API_BASE_URL", ""),
        os.environ.get("CASE3_MAX_CHARTS", ""),
        os.environ.get("CASE3_MAX_IMAGES", ""),
        os.environ.get("CASE3_MAX_DIAGRAMS", ""),
        os.environ.get("CASE3_SOFFICE", ""),
        id(ensure_image),
        id(probe_playwright_chromium),
        id(probe_vision),
        id(probe_image_api),
        id(probe_soffice),
    )


@app.get("/api/health")
def health(fresh: str | bool | None = None) -> dict[str, Any]:
    import time as _time

    global _health_cache_payload, _health_cache_ts, _health_cache_key
    env_key = _current_health_env_key()
    now = _time.monotonic()
    if not _as_bool(fresh):
        with _health_cache_lock:
            if (
                _health_cache_payload is not None
                and _health_cache_key == env_key
                and (now - _health_cache_ts) < _HEALTH_CACHE_TTL_S
            ):
                return dict(_health_cache_payload)

    docker_ok = False
    docker_err = None
    try:
        ensure_image()
        docker_ok = True
    except Exception as exc:  # noqa: BLE001
        docker_err = str(exc)[:200]

    playwright_ok, playwright_err = probe_playwright_chromium()

    vision_cfg, vision_live, vision_err = probe_vision()
    images_configured = image_api_configured()
    image_live_ok = False
    image_live_err: str | None = None
    if images_configured:
        image_live_ok, image_live_err = probe_image_api(timeout_s=1.5)
    else:
        image_live_err = "IMAGE_API_BASE_URL empty"
    soffice_ok, soffice_path, soffice_hint = probe_soffice()
    probes = build_desk_probes(
        docker_ok=docker_ok,
        docker_error=docker_err,
        playwright_ok=playwright_ok,
        playwright_error=playwright_err,
        vision_configured=vision_cfg,
        vision_ok=vision_live,
        vision_error=vision_err,
        image_configured=images_configured,
        image_ok=bool(image_live_ok),
        image_error=image_live_err,
        soffice_ok=soffice_ok,
        soffice_path=soffice_path,
        soffice_hint=soffice_hint,
    )
    # ok = Docker image present and Vision answered. A configured-but-down
    # model must not look ready. Image red/amber does not block.
    payload = {
        "ok": bool(docker_ok and vision_live),
        "docker_image": IMAGE,
        "docker_ok": docker_ok,
        "docker_error": docker_err,
        "docker_warmed": is_docker_warmed(),
        "playwright_ok": playwright_ok,
        "playwright_error": playwright_err,
        "vision_configured": vision_cfg,
        "vision_ok": vision_live,
        "vision_error": vision_err,
        "image_api_configured": images_configured,
        # live probe (short timeout) — UI chip Image · ok / down
        "image_api_ok": bool(image_live_ok),
        "image_api_error": image_live_err,
        # alias for Liber UI that still reads kandinsky_configured
        "kandinsky_configured": images_configured,
        "soffice_ok": soffice_ok,
        "soffice_path": soffice_path,
        "soffice_hint": soffice_hint,
        "probes": probes,
        "defaults": {
            "max_charts": max_charts_from_env(),
            "max_images": max_images_from_env(),
            "max_diagrams": max_diagrams_from_env(),
            # Settings «Схем ≤» input max — CASE3_MAX_DIAGRAMS hard ceiling.
            "max_diagrams_cap": DIAGRAMS_HARD_MAX,
        },
        "chart_types": sorted(CHART_TYPES),
        "chart_palettes": palette_public(),
    }
    with _health_cache_lock:
        _health_cache_payload = dict(payload)
        _health_cache_ts = _time.monotonic()
        _health_cache_key = env_key
    return payload


@app.get("/api/chart-types")
def chart_types() -> dict[str, Any]:
    return {"types": sorted(CHART_TYPES), "palettes": palette_public()}


def _turn_count(run_id: str) -> int:
    from case3.chat_memory import load_chain

    return len(load_chain(run_store.ROOT, run_id))


def _memory_section(run_id: str) -> str:
    from case3.chat_memory import newest_edit

    edit = newest_edit(run_store.ROOT, run_id)
    if edit.get("op") == "undo":
        return ""
    return str(edit.get("section") or "")


def _run_result_payload(
    run_id: str,
    out_dir: Path,
    meta: dict[str, Any],
    *,
    intent: str | None = None,
    max_charts: int | None = None,
    max_images: int | None = None,
    max_diagrams: int | None = None,
) -> dict[str, Any]:
    files: dict[str, str] = {}
    for art in out_dir.iterdir():
        if not art.is_file():
            continue
        suf = art.suffix.lower()
        name = art.name
        # Report PDF/DOCX only — never map *_deck.pdf onto key "pdf".
        if suf == ".pdf" and not name.endswith("_deck.pdf"):
            files["pdf"] = f"/api/runs/{run_id}/files/{name}"
        elif suf == ".docx":
            files["docx"] = f"/api/runs/{run_id}/files/{name}"

    slides_art = meta.get("slides_artifacts") or {}
    if isinstance(slides_art, dict):
        pptx_name = slides_art.get("pptx")
        deck_pdf_name = slides_art.get("deck_pdf")
        if isinstance(pptx_name, str) and (out_dir / pptx_name).is_file():
            files["pptx"] = f"/api/runs/{run_id}/files/{pptx_name}"
        if isinstance(deck_pdf_name, str) and (out_dir / deck_pdf_name).is_file():
            files["deck_pdf"] = f"/api/runs/{run_id}/files/{deck_pdf_name}"

    media = meta.get("media_status") or {}
    if not isinstance(media, dict):
        media = {}
    chart_ids = set(meta.get("charts_planned") or [])
    fig_ids = set(meta.get("figures_planned") or [])
    charts_ok = sum(
        1 for cid in chart_ids if isinstance(media.get(cid), dict) and media[cid].get("ok")
    )
    figs_ok = sum(
        1 for fid in fig_ids if isinstance(media.get(fid), dict) and media[fid].get("ok")
    )
    mc = int(max_charts if max_charts is not None else meta.get("max_charts") or 0)
    mi = int(max_images if max_images is not None else meta.get("max_images") or 0)
    md = int(
        max_diagrams if max_diagrams is not None else meta.get("max_diagrams") or 0
    )
    diagrams = _load_diagrams_from_out(out_dir)
    chat_summary = str(meta.get("chat_summary") or "")
    summary_status = str(meta.get("summary_status") or "")
    if not summary_status and chat_summary:
        summary_status = "ok"
    slides_dir = out_dir / "slides"
    user_text = _user_source_text(meta)
    slide_pngs = (
        [
            f"/api/runs/{run_id}/slides/png/{p.name}"
            for p in sorted(slides_dir.glob("slide_*.png"))
        ]
        if slides_dir.is_dir()
        else []
    )
    from case3.api_slides import is_slides_patch_active

    patch_active = is_slides_patch_active(run_id)
    return {
        "run_id": run_id,
        "status": meta.get("status", "ok"),
        "stage": meta.get("stage"),
        "stage_detail": meta.get("stage_detail"),
        "intent": intent if intent is not None else meta.get("intent"),
        "max_charts": mc,
        "max_images": mi,
        "max_diagrams": md,
        "figures_planned": meta.get("figures_planned") or [],
        "charts_planned": meta.get("charts_planned") or [],
        "diagrams_planned": meta.get("diagrams_planned") or [d["id"] for d in diagrams],
        "diagrams": diagrams,
        "diagrams_ok": int(meta.get("diagrams_ok") or len(diagrams)),
        "media_status": media,
        "charts_ok": charts_ok,
        "figures_ok": figs_ok,
        "files": files,
        "downloads": files,
        "previews": _media_previews(run_id, out_dir, media),
        "preview": _build_preview_payload(run_id, out_dir, media),
        "title": str(meta.get("title") or ""),
        "chat_summary": chat_summary,
        "chat_opening": str(meta.get("chat_opening") or ""),
        "chat_notice": str(meta.get("chat_notice") or ""),
        "turn_count": _turn_count(run_id),
        "memory_section": _memory_section(run_id),
        "summary_status": summary_status or None,
        "slides_status": "running" if patch_active else (meta.get("slides_status") or "idle"),
        "slides_stage": "patch" if patch_active else meta.get("slides_stage"),
        "slides_error": meta.get("slides_error"),
        "slides_artifacts": meta.get("slides_artifacts"),
        # Twin thumbs for Liber chat/rail — without these, pptx-ready runs look empty.
        "slide_pngs": slide_pngs,
        "output_mode": meta.get("output_mode") or "auto",
        "prior_run_id": str(meta.get("prior_run_id") or ""),
        "user_text": user_text,
        "error": meta.get("error"),
        "warnings": _warnings(meta, max_images=mi),
        "insufficient_data": bool(meta.get("insufficient_data")),
    }


def _user_source_text(meta: dict[str, Any]) -> str:
    """The message the user sent. Intent is the expanded UI prompt."""
    chat_p = meta.get("chat_prompt")
    if isinstance(chat_p, str) and chat_p.strip():
        return chat_p.strip()
    raw = meta.get("source")
    if not isinstance(raw, str) or not raw.strip():
        return ""
    path = Path(raw).expanduser().resolve()
    root = (run_store.ROOT / "runs").resolve()
    try:
        path.relative_to(root)
    except ValueError:
        return ""
    if not path.is_file():
        return ""
    try:
        if path.stat().st_size > 200_000:
            return ""
        return path.read_text(encoding="utf-8").strip()[:20_000]
    except OSError:
        return ""


# Win desk: parallel daemon pipelines share case3 FileHandlers + meta lock and
# leave zombies (stage=images/inject forever). One report executes, one waits.
@dataclass
class _PipelineJob:
    src_path: Path
    run_id: str
    formats: set[str]
    dry_run: bool
    intent: str
    max_images: int
    max_charts: int
    max_diagrams: int
    user_figures: list[dict[str, Any]] | None
    output_mode: str

    def kwargs(self) -> dict[str, Any]:
        return {
            "src_path": self.src_path,
            "run_id": self.run_id,
            "formats": self.formats,
            "dry_run": self.dry_run,
            "intent": self.intent,
            "max_images": self.max_images,
            "max_charts": self.max_charts,
            "max_diagrams": self.max_diagrams,
            "user_figures": self.user_figures,
            "output_mode": self.output_mode,
        }


def _max_concurrent_runs() -> int:
    raw = (os.environ.get("CASE3_MAX_CONCURRENT_RUNS") or "3").strip() or "3"
    try:
        return max(1, min(int(raw), 8))
    except ValueError:
        return 3


def _max_queued_runs() -> int:
    raw = (os.environ.get("CASE3_MAX_QUEUED_RUNS") or "8").strip() or "8"
    try:
        return max(1, min(int(raw), 32))
    except ValueError:
        return 8


class _CompatPipelineSlot:
    """Compatibility view over concurrent active slots."""

    def locked(self) -> bool:
        with _PIPELINE_ACTIVE_GUARD:
            return bool(_PIPELINE_ACTIVE)


_PIPELINE_SLOT = _CompatPipelineSlot()
_PIPELINE_ACTIVE: dict[str, int] = {}
_PIPELINE_ACTIVE_GUARD = threading.Lock()
_PIPELINE_WAITERS: list[_PipelineJob] = []
_PIPELINE_WAITER: _PipelineJob | None = None
_WAITER_RESERVED = False
_WAITER_RESERVED_COUNT = 0
# Bumps on every claim/bind. A thread releases only with the generation it
# captured at claim time, so a stale finally cannot drop a newer owner of the
# same run_id (terminal meta + reclaim, then resume).
_SLOT_GEN = 0
# >0 while a thread has been claimed/bound and is being spawned.
_SLOT_HANDOFF = 0


def _slot_generation(run_id: str | None = None) -> int:
    with _PIPELINE_ACTIVE_GUARD:
        if run_id and run_id in _PIPELINE_ACTIVE:
            return _PIPELINE_ACTIVE[run_id]
        return _SLOT_GEN


def _set_slot_handoff(active: bool) -> None:
    global _SLOT_HANDOFF
    with _PIPELINE_ACTIVE_GUARD:
        if active:
            _SLOT_HANDOFF += 1
        else:
            _SLOT_HANDOFF = max(0, _SLOT_HANDOFF - 1)


def _stamp_owner(run_id: str, *, replace_key: str | None = None) -> int:
    """Caller holds ``_PIPELINE_ACTIVE_GUARD``. Returns the new generation."""
    global _SLOT_GEN
    if replace_key and replace_key != run_id:
        _PIPELINE_ACTIVE.pop(replace_key, None)
    _SLOT_GEN += 1
    _PIPELINE_ACTIVE[run_id] = _SLOT_GEN
    return _SLOT_GEN


def _pipeline_active_run() -> str | None:
    with _PIPELINE_ACTIVE_GUARD:
        return next(iter(_PIPELINE_ACTIVE), None)


def _is_run_active(run_id: str) -> bool:
    with _PIPELINE_ACTIVE_GUARD:
        return run_id in _PIPELINE_ACTIVE


def _is_pipeline_thread_alive(run_id: str | None) -> bool:
    if not run_id or run_id == "pending" or run_id.startswith("pending#"):
        return False
    names = {t.name for t in threading.enumerate()}
    return f"case3-pipeline-{run_id}" in names or f"case3-resume-{run_id}" in names


def _reclaim_stale_slot_if_dead() -> bool:
    """Release any active slot whose thread is already gone and meta is terminal."""
    with _PIPELINE_ACTIVE_GUARD:
        if not _PIPELINE_ACTIVE or _SLOT_HANDOFF > 0:
            return False
        candidates = list(_PIPELINE_ACTIVE.items())

    reclaimed = False
    for active_id, gen in candidates:
        if active_id == "pending" or active_id.startswith("pending#"):
            continue
        if _is_pipeline_thread_alive(active_id):
            continue
        out_dir = run_store.ROOT / "runs" / "out" / active_id
        logs_dir = run_store.ROOT / "runs" / "logs" / active_id
        meta_path = out_dir / "meta.json"
        if not meta_path.is_file():
            meta_path = logs_dir / "meta.json"
        if not meta_path.is_file():
            continue
        try:
            m = json.loads(meta_path.read_text(encoding="utf-8"))
        except Exception:
            continue
        if m.get("status") in {"ok", "error", "cancelled"}:
            log.warning(
                "Pipeline slot held by terminal run %s (%s) with dead thread; releasing slot",
                active_id,
                m.get("status"),
            )
            _release_pipeline_slot(active_id, generation=gen)
            reclaimed = True
    return reclaimed


def _claim_pipeline_slot(run_id: str) -> str | None:
    """Return None if claimed; else a run_id holding full capacity."""
    _reclaim_stale_slot_if_dead()
    limit = _max_concurrent_runs()
    with _PIPELINE_ACTIVE_GUARD:
        if run_id in _PIPELINE_ACTIVE:
            _stamp_owner(run_id)
            return None
        if len(_PIPELINE_ACTIVE) < limit:
            _stamp_owner(run_id)
            return None
        return next(iter(_PIPELINE_ACTIVE), "busy")


def _bind_pipeline_slot(run_id: str, *, pending_key: str | None = None) -> int:
    with _PIPELINE_ACTIVE_GUARD:
        return _stamp_owner(run_id, replace_key=pending_key)


def _release_pipeline_slot(
    run_id: str | None = None, *, generation: int | None = None
) -> None:
    """Drop the slot owned by ``run_id`` (or reset all if ``run_id is None``) and start FIFO waiters."""
    global _PIPELINE_WAITER
    to_spawn: list[tuple[_PipelineJob, int]] = []
    limit = _max_concurrent_runs()
    with _PIPELINE_ACTIVE_GUARD:
        if run_id is None:
            _PIPELINE_ACTIVE.clear()
        else:
            if run_id not in _PIPELINE_ACTIVE:
                return
            if generation is not None and _PIPELINE_ACTIVE[run_id] != generation:
                return
            _PIPELINE_ACTIVE.pop(run_id, None)

        while (_PIPELINE_WAITERS or _PIPELINE_WAITER is not None) and len(_PIPELINE_ACTIVE) < limit:
            if _PIPELINE_WAITERS:
                job = _PIPELINE_WAITERS.pop(0)
            else:
                job = _PIPELINE_WAITER  # type: ignore[assignment]
                _PIPELINE_WAITER = None
            if _PIPELINE_WAITERS:
                _PIPELINE_WAITER = _PIPELINE_WAITERS[0]
            elif _PIPELINE_WAITER is job:
                _PIPELINE_WAITER = None
            if _waiter_should_drop(job.run_id):
                from case3.pipeline_queue import clear_waiter

                clear_waiter(run_store.ROOT, run_id=job.run_id)
                continue
            spawn_gen = _stamp_owner(job.run_id)
            to_spawn.append((job, spawn_gen))

    for job, spawn_gen in to_spawn:
        _spawn_pipeline_thread(job, slot_gen=spawn_gen)


def _reserve_run_turn() -> tuple[str, str | None]:
    """``run`` claims an active worker slot; ``queue`` reserves FIFO queue; ``busy`` when queue full."""
    global _WAITER_RESERVED, _WAITER_RESERVED_COUNT
    _reclaim_stale_slot_if_dead()
    max_runs = _max_concurrent_runs()
    max_queue = _max_queued_runs()
    with _PIPELINE_ACTIVE_GUARD:
        if len(_PIPELINE_ACTIVE) < max_runs and not _PIPELINE_WAITERS and _PIPELINE_WAITER is None:
            global _SLOT_GEN
            _SLOT_GEN += 1
            pending_key = f"pending#{_SLOT_GEN}"
            _PIPELINE_ACTIVE[pending_key] = _SLOT_GEN
            return "run", pending_key
        active = next(iter(_PIPELINE_ACTIVE), "busy")
        reserved = _WAITER_RESERVED_COUNT or (1 if _WAITER_RESERVED else 0)
        if len(_PIPELINE_WAITERS) + reserved >= max_queue:
            return "busy", active
        _WAITER_RESERVED_COUNT = reserved + 1
        _WAITER_RESERVED = _WAITER_RESERVED_COUNT > 0
        return "queue", active


def _cancel_queue_reservation() -> None:
    global _WAITER_RESERVED, _WAITER_RESERVED_COUNT
    with _PIPELINE_ACTIVE_GUARD:
        _WAITER_RESERVED_COUNT = max(0, _WAITER_RESERVED_COUNT - 1)
        _WAITER_RESERVED = _WAITER_RESERVED_COUNT > 0


def _commit_waiter(job: _PipelineJob) -> str:
    """Append to FIFO queue, or start immediately if a worker slot freed during upload."""
    global _PIPELINE_WAITER, _WAITER_RESERVED, _WAITER_RESERVED_COUNT
    max_runs = _max_concurrent_runs()
    with _PIPELINE_ACTIVE_GUARD:
        _WAITER_RESERVED_COUNT = max(0, _WAITER_RESERVED_COUNT - 1)
        _WAITER_RESERVED = _WAITER_RESERVED_COUNT > 0
        if len(_PIPELINE_ACTIVE) < max_runs and not _PIPELINE_WAITERS and _PIPELINE_WAITER is None:
            _stamp_owner(job.run_id)
            return "start"
        from case3.pipeline_queue import append_waiter

        append_waiter(run_store.ROOT, _job_payload(job))
        _PIPELINE_WAITERS.append(job)
        _PIPELINE_WAITER = _PIPELINE_WAITERS[0]
        return "queued"


def _job_payload(job: _PipelineJob) -> dict[str, Any]:
    return {
        "src_path": str(job.src_path),
        "run_id": job.run_id,
        "formats": sorted(job.formats),
        "dry_run": job.dry_run,
        "intent": job.intent,
        "max_images": job.max_images,
        "max_charts": job.max_charts,
        "max_diagrams": job.max_diagrams,
        "user_figures": list(job.user_figures or []),
        "output_mode": job.output_mode,
    }


def _spawn_pipeline_thread(
    job: _PipelineJob, slot_gen: int | None = None
) -> None:
    if slot_gen is None:
        slot_gen = _slot_generation()
    kwargs = job.kwargs()
    kwargs["slot_gen"] = slot_gen

    def _run() -> None:
        from case3.pipeline_queue import clear_waiter

        clear_waiter(run_store.ROOT, run_id=job.run_id)
        _bg_run_pipeline(**kwargs)

    threading.Thread(
        target=_run,
        name=f"case3-pipeline-{job.run_id}",
        daemon=True,
    ).start()


_ORPHAN_RUN = "Сервер перезапустился, прогон оборвался."
_ORPHAN_SLIDES = "Сервер перезапустился, сборка презентации оборвалась."


def _run_is_live(run_id: str) -> bool:
    """True while this process still owns the pipeline thread or the start handoff."""
    if _is_pipeline_thread_alive(run_id):
        return True
    with _PIPELINE_ACTIVE_GUARD:
        return bool(_SLOT_HANDOFF and run_id in _PIPELINE_ACTIVE)


def _slides_thread_alive(run_id: str) -> bool:
    names = {thread.name for thread in threading.enumerate()}
    return (
        f"case3-slides-{run_id}" in names
        or f"case3-slides-patch-{run_id}" in names
    )


def _persist_settled_meta(run_id: str, meta: dict[str, Any]) -> None:
    from case3.run_meta import write_meta

    out = run_store.ROOT / "runs" / "out" / run_id
    logs = run_store.ROOT / "runs" / "logs" / run_id
    if (out / "meta.json").is_file() or not (logs / "meta.json").is_file():
        write_meta(out, meta, logs_dir=logs if logs.is_dir() else None)
        return
    write_meta(logs, meta)


def settle_orphaned_runs() -> list[str]:
    """Turn a dead ``running`` run into ``error`` so the spinner can stop.

    Called once at process start, before the queued waiter is picked up.
    A live thread is left alone. ``queued`` stays queued. A run the user
    already cancelled becomes ``cancelled`` and does not offer «Продолжить».
    """
    ids: set[str] = set()
    for base in ("out", "logs"):
        root = run_store.ROOT / "runs" / base
        if not root.is_dir():
            continue
        for path in root.glob("*/meta.json"):
            ids.add(path.parent.name)
    changed: list[str] = []
    for run_id in sorted(ids):
        if _settle_one_orphan(run_id):
            changed.append(run_id)
    return changed


def _settle_one_orphan(run_id: str) -> bool:
    meta = _read_run_meta(run_id)
    if not meta:
        return False
    changed = False
    if str(meta.get("status") or "") == "running" and not _run_is_live(run_id):
        if meta.get("cancel_requested"):
            meta["status"] = "cancelled"
            meta["stage"] = "cancelled"
            meta["error"] = meta.get("error") or "Остановлено"
        else:
            from case3.pipeline import _record_failed_stage

            _record_failed_stage(meta)
            meta["status"] = "error"
            meta["stage"] = "error"
            meta["error"] = _ORPHAN_RUN
        changed = True
    slides = str(meta.get("slides_status") or "")
    if (
        slides in {"running", "queued"}
        and not _slides_thread_alive(run_id)
        and not _run_is_live(run_id)
    ):
        meta["slides_status"] = "error"
        meta["slides_stage"] = "error"
        meta["slides_error"] = _ORPHAN_SLIDES
        changed = True
    if not changed:
        return False
    _persist_settled_meta(run_id, meta)
    if meta.get("status") in {"error", "cancelled"} and str(meta.get("error") or "") in {
        _ORPHAN_RUN,
        "Остановлено",
    }:
        try:
            from case3.run_events import EVENTS

            EVENTS.publish_terminal(
                run_id,
                str(meta["status"]),
                error=str(meta.get("error") or ""),
            )
        except Exception:  # noqa: BLE001
            log.exception("could not publish orphan terminal run_id=%s", run_id)
    return True


def recover_persisted_pipeline() -> str | None:
    """Start persisted queued jobs after a process restart (FIFO up to slot capacity)."""
    from case3.pipeline_queue import clear_waiter, load_waiters

    payloads = load_waiters(run_store.ROOT)
    first_started: str | None = None
    for payload in payloads:
        run_id = str(payload["run_id"])
        if _is_pipeline_thread_alive(run_id):
            continue
        meta = _read_run_meta(run_id)
        if meta.get("status") != "queued" or meta.get("cancel_requested"):
            clear_waiter(run_store.ROOT, run_id=run_id)
            continue
        if _claim_pipeline_slot(run_id) is not None:
            break
        job = _PipelineJob(
            src_path=Path(str(payload["src_path"])),
            run_id=run_id,
            formats=set(payload.get("formats") or []),
            dry_run=bool(payload.get("dry_run")),
            intent=str(payload.get("intent") or ""),
            max_images=int(payload.get("max_images") or 0),
            max_charts=int(payload.get("max_charts") or 0),
            max_diagrams=int(payload.get("max_diagrams") or 0),
            user_figures=list(payload.get("user_figures") or []),
            output_mode=str(payload.get("output_mode") or "auto"),
        )
        _spawn_pipeline_thread(job)
        if first_started is None:
            first_started = run_id
    return first_started


def _drop_queued_waiter(run_id: str) -> None:
    """A cancelled queued run must not stay in memory or on disk."""
    global _PIPELINE_WAITER, _WAITER_RESERVED, _WAITER_RESERVED_COUNT
    from case3.pipeline_queue import clear_waiter

    clear_waiter(run_store.ROOT, run_id=run_id)
    with _PIPELINE_ACTIVE_GUARD:
        _PIPELINE_WAITERS[:] = [w for w in _PIPELINE_WAITERS if w.run_id != run_id]
        if _PIPELINE_WAITERS:
            _PIPELINE_WAITER = _PIPELINE_WAITERS[0]
        elif _PIPELINE_WAITER is not None and _PIPELINE_WAITER.run_id == run_id:
            _PIPELINE_WAITER = None
        if not _PIPELINE_WAITERS and _PIPELINE_WAITER is None:
            _WAITER_RESERVED_COUNT = 0
            _WAITER_RESERVED = False


def _waiter_should_drop(run_id: str) -> bool:
    """A queued run that was cancelled or already finished must not start."""
    meta = _read_run_meta(run_id)
    if not meta:
        return False
    if meta.get("cancel_requested"):
        return True
    return str(meta.get("status") or "") in {"ok", "error", "cancelled"}


def _read_run_meta(run_id: str) -> dict[str, Any]:
    for path in (
        run_store.ROOT / "runs" / "out" / run_id / "meta.json",
        run_store.ROOT / "runs" / "logs" / run_id / "meta.json",
    ):
        if not path.is_file():
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}
        return data if isinstance(data, dict) else {}
    return {}


def _busy_detail(_active: str | None) -> str:
    return (
        "Сейчас собирается один документ, и ещё один уже ждёт. "
        "Этот запрос не поставлен. Дождись, пока освободится очередь."
    )


def _auto_kick_presentation_slides(run_id: str) -> None:
    try:
        from case3.api_slides import _kick_slides_thread, try_claim_slides_start
        from case3.run_events import EVENTS as _EV

        out = run_store.ROOT / "runs" / "out" / run_id
        logs = run_store.ROOT / "runs" / "logs" / run_id
        claimed, meta = try_claim_slides_start(
            run_id,
            out_dir=out,
            logs_dir=logs,
            kick_source="api_auto",
            only_if_unbuilt=True,
        )
        if claimed:
            _EV.reopen(run_id)
            _EV.bind_out(run_id, out)
            _EV.publish_stage(run_id, "starting", scope="slides")
            _kick_slides_thread(run_id)
            log.info(
                "auto-kicked slides run_id=%s pack=%s structure=%s",
                run_id,
                meta.get("slides_theme_pack"),
                meta.get("slides_structure_id"),
            )
    except Exception:  # noqa: BLE001
        log.exception("auto-kick slides failed run_id=%s", run_id)


def apply_mode_caps(
    out_mode: str,
    *,
    max_charts: int,
    max_images: int,
    max_diagrams: int,
    formats: str,
    no_charts: bool,
    no_images: bool,
    allow_chat_charts: bool = False,
) -> tuple[int, int, int, str, bool, bool]:
    """Chat and scheme drop print media. A deck still gets dia_* for its slides."""
    if out_mode == "chat":
        if no_charts or max_charts <= 0:
            return 0, 0, 0, "none", True, True
        cap = min(int(max_charts), 2) if allow_chat_charts else 1
        return cap, 0, 0, "none", False, True
    if out_mode == "diagram":
        return 0, 0, max(1, max_diagrams), "none", True, True
    if out_mode == "presentation":
        return max_charts, max_images, max(1, max_diagrams), "none", no_charts, no_images
    return max_charts, max_images, max_diagrams, formats, no_charts, no_images


def _bg_run_pipeline(
    src_path: Path,
    *,
    run_id: str,
    formats: set[str],
    dry_run: bool,
    intent: str,
    max_images: int,
    max_charts: int,
    max_diagrams: int = 0,
    user_figures: list[dict[str, Any]] | None = None,
    output_mode: str = "auto",
    slot_gen: int | None = None,
) -> None:
    # print+flush: uvicorn often hides case3.api INFO; Win desk needs a visible line.
    print(f"[case3] pipeline thread start run_id={run_id}", flush=True)
    log.info("pipeline thread start run_id=%s", run_id)
    try:
        run_pipeline(
            src_path,
            project_root=run_store.ROOT,
            formats=formats,
            dry_run=dry_run,
            intent=intent,
            max_images=max_images,
            max_charts=max_charts,
            max_diagrams=max_diagrams,
            run_id=run_id,
            user_figures=user_figures,
            output_mode=output_mode,
        )
        # Presentation: Liber UI also POSTs /slides; auto-kick so CLI/matrix
        # get PPTX without a browser (idempotent if already running).
        if (output_mode or "").strip().lower() == "presentation":
            from case3.run_meta import read_meta

            out_meta = read_meta(run_store.ROOT / "runs" / "out" / run_id)
            if (
                out_meta.get("status") == "ok"
                and not out_meta.get("insufficient_data")
                and not out_meta.get("cancel_requested")
            ):
                _auto_kick_presentation_slides(run_id)
    except PipelineError:
        # meta already written with status=error
        log.exception("background pipeline failed run_id=%s", run_id)
    except Exception:  # noqa: BLE001
        log.exception("background pipeline crashed run_id=%s", run_id)
        out = run_store.ROOT / "runs" / "out" / run_id
        logs = run_store.ROOT / "runs" / "logs" / run_id
        from case3.run_meta import update_meta

        def _mut_crash(m: dict[str, Any]) -> None:
            if not m:
                m["run_id"] = run_id
            m.update({"status": "error", "stage": "error", "error": "pipeline crashed"})

        update_meta(out, _mut_crash, logs_dir=logs)
        try:
            from case3.run_events import EVENTS

            EVENTS.publish_terminal(run_id, "error", error="pipeline crashed")
        except Exception:  # noqa: BLE001
            log.exception("could not publish crash terminal run_id=%s", run_id)
    finally:
        _release_pipeline_slot(run_id, generation=slot_gen)


def _ingest_dir(ingest_id: str) -> Path:
    if not _INGEST_ID_OK.match(ingest_id):
        raise HTTPException(400, detail="bad ingest id")
    path = (run_store.ROOT / "runs" / "uploads" / "ingest" / ingest_id).resolve()
    root = (run_store.ROOT / "runs" / "uploads" / "ingest").resolve()
    if path != root and root not in path.parents:
        raise HTTPException(400, detail="bad ingest id")
    if not path.is_dir():
        raise HTTPException(404, detail="ingest not found")
    return path


def _write_office_preview(upload_dir: Path, src: Path, fmt: str) -> str | None:
    """Return preview.pdf basename when a viewable PDF is available."""
    preview = upload_dir / "preview.pdf"
    if fmt == "pdf":
        if src.resolve() != preview.resolve():
            shutil.copy2(src, preview)
        return preview.name
    if fmt in {"docx", "doc", "docm", "rtf"}:
        try:
            from case3.office_convert import LibreOfficeNotFoundError, convert_to_pdf

            made = convert_to_pdf(src, output_dir=upload_dir)
            if made.resolve() != preview.resolve():
                made.replace(preview)
            return preview.name if preview.is_file() else None
        except LibreOfficeNotFoundError:
            return None
        except Exception as exc:  # noqa: BLE001
            log.warning("office preview pdf failed: %s", exc)
            return None
    return None


def _dashboard_http_status(code: str) -> int:
    if code in {"missing_input", "too_large", "bad_pdf", "bad_png", "missing_file"}:
        return 400
    if code in {"vision_failed", "ingest_dependency"}:
        return 503
    return 422


@app.post("/api/dashboard/phrase")
async def api_dashboard_phrase(payload: dict = Body(...)) -> JSONResponse:
    """Chat sentence → GET /filters, POST /open, iframe loads that /open page."""
    text = str((payload or {}).get("text") or "")
    if not might_ask_dashboard(text):
        return JSONResponse({"pull": False})
    import httpx

    from case3.llm_client import LLMClient, LLMConfig, LLMConfigError

    base = service_base()
    timeout = httpx.Timeout(60.0, connect=5.0)

    def _run_phrase() -> dict[str, Any]:
        with httpx.Client(timeout=timeout) as client:
            catalog = fetch_filter_catalog(base, client, question=text)
            llm = LLMClient(LLMConfig.from_env())
            plan = plan_dashboard_phrase(
                text,
                catalog,
                lambda **kwargs: llm.complete(**kwargs, reasoning="off"),
            )
            return finish_dashboard_phrase(plan, base, client)

    try:
        plan = await asyncio.to_thread(_run_phrase)
    except DashboardRemoteError as exc:
        raise HTTPException(502, detail=exc.message) from exc
    except LLMConfigError as exc:
        raise HTTPException(503, detail=str(exc)) from exc
    except httpx.HTTPError as exc:
        raise HTTPException(502, detail="сервис дашборда недоступен") from exc
    return JSONResponse(plan)


@app.get("/api/dashboard/dashboards")
def api_dashboard_dashboards() -> JSONResponse:
    """Names of the .mrt files in the viewer local folder."""
    import httpx

    base = service_base()
    timeout = httpx.Timeout(15.0, connect=5.0)
    try:
        with httpx.Client(timeout=timeout) as client:
            rows = fetch_dashboards(base, client)
    except DashboardRemoteError as exc:
        raise HTTPException(502, detail=exc.message) from exc
    except httpx.HTTPError as exc:
        raise HTTPException(502, detail="сервис дашборда недоступен") from exc
    return JSONResponse({"dashboards": rows})


@app.get("/api/dashboard/preview")
def api_dashboard_preview(mrt: str) -> Response:
    """Picture placed next to this .mrt in the viewer local folder."""
    import httpx

    name = (mrt or "").strip()
    if not name:
        raise HTTPException(400, detail="нужно имя дашборда")
    base = service_base()
    timeout = httpx.Timeout(15.0, connect=5.0)
    try:
        with httpx.Client(timeout=timeout) as client:
            content, media = fetch_dashboard_preview(base, name, client)
    except DashboardRemoteError as exc:
        status = 404 if exc.code == "preview" and exc.message == "нет снимка" else 502
        raise HTTPException(status, detail=exc.message) from exc
    except httpx.HTTPError as exc:
        raise HTTPException(502, detail="сервис дашборда недоступен") from exc
    return Response(content=content, media_type=media, headers={"Cache-Control": "no-store"})


@app.post("/api/dashboard/open")
def api_dashboard_open(payload: dict = Body(...)) -> JSONResponse:
    """Filters for the chosen .mrt, then /open. The iframe loads that page."""
    import httpx

    name = str((payload or {}).get("mrt") or "").strip()
    if not name:
        raise HTTPException(400, detail="нужно имя дашборда")
    base = service_base()
    timeout = httpx.Timeout(60.0, connect=5.0)
    try:
        with httpx.Client(timeout=timeout) as client:
            plan = open_named_dashboard(base, name, client)
    except DashboardRemoteError as exc:
        raise HTTPException(502, detail=exc.message) from exc
    except httpx.HTTPError as exc:
        raise HTTPException(502, detail="сервис дашборда недоступен") from exc
    return JSONResponse(plan)


@app.get("/api/dashboard/service")
def api_dashboard_service() -> JSONResponse:
    """Viewer URL for the pick modal. One env: DASHBOARD_SERVICE_URL."""
    return JSONResponse({"base": service_base(), "viewer": viewer_url()})


@app.post("/api/dashboard/service-capture")
def api_dashboard_service_capture(payload: dict | None = Body(default=None)) -> JSONResponse:
    """GET the open viewer's /shot, then parse the screen and tables as one document."""
    import httpx

    mrt = str((payload or {}).get("mrt") or "").strip() if isinstance(payload, dict) else ""
    base = service_base()
    timeout = httpx.Timeout(100.0, connect=5.0)
    try:
        with httpx.Client(timeout=timeout) as client:
            shot_payload = fetch_shot_payload(base, client, mrt=mrt)
            documents = capture_documents(
                shot_payload,
                lambda name: fetch_export(base, name, client),
                parse_dashboard,
            )
    except DashboardRemoteError as exc:
        raise HTTPException(502, detail=exc.message) from exc
    except httpx.HTTPError as exc:
        raise HTTPException(
            502,
            detail="сервис дашборда недоступен",
        ) from exc
    return JSONResponse({"documents": documents})


@app.post("/api/dashboard/parse")
async def api_dashboard_parse(
    png: UploadFile | None = File(None),
    pdf: UploadFile | None = File(None),
) -> JSONResponse:
    """Dashboard PNG (Qwen) and/or table PDF → markdown. No report run."""
    png_bytes = await png.read() if png is not None else None
    pdf_bytes = await pdf.read() if pdf is not None else None
    if png_bytes == b"":
        png_bytes = None
    if pdf_bytes == b"":
        pdf_bytes = None
    try:
        result = await asyncio.to_thread(
            parse_dashboard,
            png=png_bytes,
            pdf=pdf_bytes,
        )
    except DashboardSourceError as exc:
        raise HTTPException(
            _dashboard_http_status(exc.code),
            detail=exc.message,
        ) from exc
    return JSONResponse(
        {
            "markdown": result.markdown,
            "png_markdown": result.png_markdown,
            "pdf_markdown": result.pdf_markdown,
            "warnings": result.warnings,
            "pdf_table_count": result.pdf_table_count,
            "pdf_numeric_cells": result.pdf_numeric_cells,
        }
    )


@app.post("/api/source/ingest")
async def api_source_ingest(
    file: UploadFile = File(...),
) -> JSONResponse:
    """Born-digital PDF/DOCX/TXT/RTF → silent extract + optional PDF preview."""
    name = Path(file.filename or "upload.bin").name
    raw = await file.read()
    if not raw:
        raise HTTPException(400, detail="пустой файл")
    if len(raw) > _INGEST_MAX_BYTES:
        raise HTTPException(400, detail="файл слишком большой (>20 MiB)")

    ingest_id = datetime_stamp()
    upload_dir = run_store.ROOT / "runs" / "uploads" / "ingest" / ingest_id
    upload_dir.mkdir(parents=True, exist_ok=True)
    dest = upload_dir / name
    dest.write_bytes(raw)

    def _ingest_sync():
        res = file_to_markdown(dest, max_markdown_bytes=DEFAULT_MAX_MARKDOWN_BYTES)
        (upload_dir / "source.txt").write_text(res.markdown, encoding="utf-8")
        pname = _write_office_preview(upload_dir, dest, res.format)
        return res, pname

    try:
        result, preview_name = await asyncio.to_thread(_ingest_sync)
    except IngestDependencyError as exc:
        raise HTTPException(503, detail=exc.message) from exc
    except (ScanPdfError, UnsupportedSourceFormatError, OfficeConvertError) as exc:
        raise HTTPException(422, detail=exc.message) from exc
    except SourceIngestError as exc:
        raise HTTPException(422, detail=exc.message) from exc
    except FileNotFoundError as exc:
        raise HTTPException(400, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        log.exception("source ingest failed name=%s", name)
        raise HTTPException(500, detail=f"не удалось разобрать файл: {exc}") from exc

    office = result.format in {"pdf", "docx", "doc", "docm", "rtf"}
    payload: dict[str, Any] = {
        "markdown": result.markdown,
        "text": result.markdown,
        "filename": result.filename,
        "format": result.format,
        "warnings": result.warnings,
        "ingest_id": ingest_id,
        "view_mode": "document" if office else "text",
        "original_url": f"/api/source/files/{ingest_id}/original",
    }
    if preview_name:
        payload["preview_url"] = f"/api/source/files/{ingest_id}/preview"
    return JSONResponse(payload)


@app.get("/api/source/files/{ingest_id}/preview")
def api_source_preview(ingest_id: str) -> FileResponse:
    folder = _ingest_dir(ingest_id)
    path = folder / "preview.pdf"
    if not path.is_file():
        raise HTTPException(404, detail="preview pdf not available")
    return FileResponse(
        path,
        media_type="application/pdf",
        filename="preview.pdf",
        content_disposition_type="inline",
    )


@app.get("/api/source/files/{ingest_id}/original")
def api_source_original(ingest_id: str) -> FileResponse:
    folder = _ingest_dir(ingest_id)
    meta_txt = folder / "source.txt"
    originals = [
        p
        for p in folder.iterdir()
        if p.is_file() and p.name not in {"source.txt", "preview.pdf"}
    ]
    if not originals:
        raise HTTPException(404, detail="original file not found")
    path = originals[0]
    suf = path.suffix.lower()
    media = "application/octet-stream"
    if suf == ".pdf":
        media = "application/pdf"
    elif suf == ".docx":
        media = (
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        )
    elif suf in {".md", ".markdown"}:
        media = "text/markdown; charset=utf-8"
    elif suf == ".txt":
        media = "text/plain; charset=utf-8"
    _ = meta_txt  # extract sibling; keep for debugging
    return FileResponse(path, media_type=media, filename=path.name)


@app.post("/api/run")
async def api_run(
    source: UploadFile | None = File(None),
    source_text: str | None = Form(None),
    intent: str = Form(""),
    max_charts: int | None = Form(None),
    max_images: int | None = Form(None),
    max_diagrams: int | None = Form(None),
    chart_types: str = Form(""),
    chart_hints: str = Form(""),
    chart_auto: str = Form("false"),
    chart_palette: str = Form("atelier"),
    chart_style: str = Form(""),
    doc_title: str = Form(""),
    forbid_charts: str = Form("false"),
    forbid_images: str = Form("false"),
    formats: str = Form("both"),
    dry_run: str = Form("false"),
    photo_mode: str = Form("document"),
    output_mode: str = Form("auto"),
    artifact_bias: str = Form(""),
    deck_pack: str = Form(""),
    deck_structure_id: str = Form(""),
    deck_style_json: str = Form(""),
    target_slides: int | None = Form(None),
    photos: list[UploadFile] = File(default_factory=list),
    photo_captions: str = Form(""),
    prior_run_id: str = Form(""),
    carried_run_id: str = Form(""),
    attachments_json: str = Form(""),
    x_workspace_id: str | None = Header(default=None, alias="X-Workspace-Id"),
) -> JSONResponse:
    no_charts = _as_bool(forbid_charts)
    no_images = _as_bool(forbid_images)
    is_dry = _as_bool(dry_run)
    is_auto = _as_bool(chart_auto)
    mode = (photo_mode or "document").strip().lower()
    if mode not in {"document", "edit"}:
        raise HTTPException(400, detail="photo_mode must be document|edit")
    if source_text and len(source_text.encode("utf-8")) > _SOURCE_MAX_BYTES:
        raise HTTPException(400, detail="source text too large (>2 MiB)")

    out_mode = (output_mode or "auto").strip().lower()
    bias = (artifact_bias or "").strip().lower()
    if bias not in {"", "report", "diagram", "presentation"}:
        raise HTTPException(
            400, detail="artifact_bias must be report|diagram|presentation"
        )
    if out_mode == "auto":
        from case3.input_validation import current_turn_user_text
        from case3.turn_route import resolve_turn

        out_mode = resolve_turn(current_turn_user_text(intent), bias or None)
    if out_mode not in {"report", "diagram", "presentation", "chat"}:
        raise HTTPException(
            400, detail="output_mode must be report|diagram|presentation|chat|auto"
        )

    if max_charts is None:
        max_charts = max_charts_from_env()
    if max_images is None:
        max_images = max_images_from_env()
    if max_diagrams is None:
        max_diagrams = max_diagrams_from_env()
    if no_charts:
        max_charts = 0
    if no_images:
        max_images = 0
    max_charts = max(0, min(int(max_charts), 8))
    max_images = max(0, min(int(max_images), 8))
    # Ceiling from CASE3_MAX_DIAGRAMS via DIAGRAMS_HARD_MAX (default 5).
    max_diagrams = max(0, min(int(max_diagrams), DIAGRAMS_HARD_MAX))
    from case3.input_validation import current_turn_user_text
    from case3.turn_route import wants_chat_chart

    # Chat and scheme skip print. Presentation keeps charts and dia_* for the deck.
    has_prior_chart = False
    if out_mode == "chat" and (prior_run_id or "").strip():
        from case3.chat_memory import load_chain_dirs

        for _rid, _prev_out, _m in reversed(
            load_chain_dirs(run_store.ROOT, (prior_run_id or "").strip())
        ):
            if any(_prev_out.glob("*.pdf")) or any(_prev_out.glob("*.docx")):
                continue
            _prev_fj = _prev_out / "figures.json"
            if not _prev_fj.is_file():
                continue
            try:
                _fj_data = json.loads(_prev_fj.read_text(encoding="utf-8"))
                if (
                    isinstance(_fj_data, dict)
                    and isinstance(_fj_data.get("charts"), list)
                    and _fj_data["charts"]
                ):
                    has_prior_chart = True
                    break
            except (OSError, json.JSONDecodeError):
                continue

    max_charts, max_images, max_diagrams, formats, no_charts, no_images = apply_mode_caps(
        out_mode,
        max_charts=max_charts,
        max_images=max_images,
        max_diagrams=max_diagrams,
        formats=formats,
        no_charts=no_charts,
        no_images=no_images,
        allow_chat_charts=out_mode == "chat"
        and wants_chat_chart(current_turn_user_text(intent), has_prior_chart=has_prior_chart),
    )

    # FastAPI may pass a single UploadFile when the client sends one file.
    if isinstance(photos, list):
        photo_files = list(photos)
    elif photos is None:
        photo_files = []
    else:
        photo_files = [photos]
    cap_list = [c.strip() for c in (photo_captions or "").split("\n") if c.strip()]
    user_figures: list[dict[str, Any]] = []
    photo_files = clip_photo_files(photo_files)
    if not cap_list and photo_files:
        cap_list = captions_from_intent(intent or "", len(photo_files))

    # Chat-only edit: one photo + prompt → /edit → preview message (no full report)
    if mode == "edit":
        if not photo_files:
            raise HTTPException(400, detail="прикрепи фото для режима «Только правка»")
        prompt = (intent or "").strip()
        if not prompt:
            raise HTTPException(400, detail="нужен текст: что изменить на фото")
        upload_dir = run_store.ROOT / "runs" / "uploads" / datetime_stamp()
        upload_dir.mkdir(parents=True, exist_ok=True)
        blobs: list[tuple[str, bytes]] = []
        for uf in photo_files:
            raw = await uf.read()
            blobs.append((uf.filename or "photo.png", raw))
        try:
            user_figures = save_user_photos(upload_dir, blobs, captions=cap_list)
        except UserPhotoError as exc:
            raise HTTPException(400, detail=str(exc)) from exc
        return await quick_photo_edit(
            user_figures[0],
            prompt=prompt,
            caption=(cap_list[0] if cap_list else user_figures[0].get("caption") or "Правка фото"),
        )

    try:
        fmt_set = parse_formats_form(formats)
    except ValueError as exc:
        raise HTTPException(400, detail=str(exc)) from exc

    # Third request must not touch disk. One waiter is reserved before the upload.
    from case3.prior_turn import insert_prior_turn, prior_block_for_form

    from case3.chat_revise import continue_or_limit
    from case3.input_validation import current_turn_user_text as _user_line

    user_line = _user_line(intent)
    try:
        prior_block = prior_block_for_form(
            prior_run_id, root=run_store.ROOT, user_text=user_line
        )
    except ValueError as exc:
        raise HTTPException(400, detail=str(exc)) from exc

    revised = await asyncio.to_thread(
        continue_or_limit,
        user_line,
        prior_run_id,
        root=run_store.ROOT,
        bias=bias or None,
        carried_run_id=carried_run_id,
    )
    if revised is not None:
        return JSONResponse(revised)

    # A chat answer does not take the build slot. A report can keep running,
    # and the one queued report stays queued.
    if out_mode == "chat":
        turn, waiting_for = "aside", None
    else:
        turn, waiting_for = _reserve_run_turn()
        if turn == "busy":
            raise HTTPException(409, detail=_busy_detail(waiting_for))

    try:
        # Persist as .../uploads/<stamp>/source.txt so run_id stem stays "source_*"
        upload_dir = run_store.ROOT / "runs" / "uploads" / datetime_stamp()
        upload_dir.mkdir(parents=True, exist_ok=True)

        if photo_files:
            blobs = []
            for uf in photo_files:
                raw = await uf.read()
                blobs.append((uf.filename or "photo.png", raw))
            try:
                user_figures = save_user_photos(upload_dir, blobs, captions=cap_list)
            except UserPhotoError as exc:
                raise HTTPException(400, detail=str(exc)) from exc
            # Uploads keep usr_* placement; do not alone unlock generated fig_*.
            no_images = False

        src_path = upload_dir / "source.txt"
        source_body = ""
        if source is not None and source.filename:
            name = Path(source.filename).name
            if not name.lower().endswith((".txt", ".md")):
                raise HTTPException(400, detail="source file must be .txt or .md")
            data = await source.read()
            if len(data) > _SOURCE_MAX_BYTES:
                raise HTTPException(400, detail="source file too large (>2 MiB)")
            src_path.write_bytes(data)
            source_body = data.decode("utf-8", errors="replace")
        elif source_text and source_text.strip():
            source_body = source_text.strip()
            src_path.write_text(source_body, encoding="utf-8")
        elif (prior_run_id or "").strip():
            from case3.chat_memory import dashboard_screens, earlier_source

            pid = (prior_run_id or "").strip()
            source_body = (
                dashboard_screens(run_store.ROOT, pid)
                or earlier_source(run_store.ROOT, pid)
            ).strip()
            if not source_body:
                raise HTTPException(400, detail="provide source file or source_text")
            src_path.write_text(source_body, encoding="utf-8")
        else:
            raise HTTPException(400, detail="provide source file or source_text")

        from case3.image_opt_in import wants_generated_images

        images_opt_in = (not no_images) and wants_generated_images(intent, source_body)
        gen_max_images = int(max_images) if images_opt_in else 0
        if user_figures:
            max_images = max(gen_max_images, len(user_figures))
        else:
            max_images = gen_max_images

        types = [] if is_auto else _parse_chart_types(chart_types)
        full_intent = build_intent_from_ui(
            chat=intent,
            chart_types=types,
            max_charts=max_charts,
            max_images=gen_max_images,
            max_diagrams=max_diagrams,
            forbid_charts=no_charts,
            forbid_images=no_images,
            chart_hints=chart_hints or "",
            chart_auto=is_auto,
            chart_palette=chart_palette or "atelier",
            chart_style=chart_style or "",
            doc_title=(doc_title or "").strip()[:200],
            output_mode=out_mode,
            deck_pack=(deck_pack or "").strip()[:40],
        )
        full_intent = insert_prior_turn(full_intent, prior_block)
        if user_figures:
            ids = ", ".join(f["id"] for f in user_figures)
            if out_mode == "presentation":
                full_intent = (
                    full_intent
                    + "\n\nПрикреплённые фото пользователя (переданы как изображения, файлы PNG уже сохранены):\n"
                    + f"- Идентификаторы: {ids}\n"
                    + "- Внимательно посмотри на прикреплённые изображения и определи, что на них изображено.\n"
                    + "- ОБЯЗАТЕЛЬНО используй эти фото на подходящих по смыслу слайдах презентации!\n"
                    + f"- Размести каждое фото на отдельном слайде, используя layout 'media_hero' (полноразмерное фото) или 'media_split' (фото + описание/тезисы) с атрибутом media_id (ровно ID из {ids}).\n"
                    + "- В поле title и caption слайда укажи информативный заголовок и описание того, что реально видно на фото.\n"
                    + "- Используй каждое фото ровно ОДИН раз (не дублируй на нескольких слайдах)."
                )
            else:
                fig_extra = (
                    "- Дополнительные fig_* через Image API — только если Intent/Source "
                    "явно просили картинку и остался бюджет."
                    if gen_max_images > 0
                    else "- Не создавай дополнительные fig_* через Image API — только usr_* из вложений."
                )
                full_intent = (
                    full_intent
                    + "\n\nПрикреплённые фото пользователя (переданы как изображения, файлы PNG уже сохранены):\n"
                    + f"- Идентификаторы: {ids}\n"
                    + "- Внимательно посмотри на прикреплённые изображения и определи, что на них изображено.\n"
                    + "- Обязательно опиши содержание каждого фото в подходящем по смыслу разделе и абзаце текста отчёта, сославшись на него.\n"
                    + f"- Вставь слот %CASE3_FIG:id% (ровно с id из {ids}) в LaTeX рядом с соответствующим абзацем текста (не в конце отчёта!).\n"
                    + "- ВАЖНО: используй каждый слот %CASE3_FIG:id% ровно ОДИН раз во всём отчёте (не дублируй фото).\n"
                    + "- В JSON figures[] укажи для каждого id конкретный осмысленный caption на русском языке с описанием того, что реально видно на фото.\n"
                    + fig_extra
                )
        # Reserve run_id + write stage=llm BEFORE kick (Win: 2nd run sat on queued while
        # prior LLM thread still held the desk; Liber must not wait on thread scheduling).
        run_id, _, _, out_dir, logs_dir = prepare_run_dirs(src_path, project_root=run_store.ROOT)
        run_slot_gen: int | None = None
        if turn == "run":
            run_slot_gen = _bind_pipeline_slot(run_id, pending_key=waiting_for)
    except BaseException:
        if turn == "queue":
            _cancel_queue_reservation()
        elif turn == "run":
            _release_pipeline_slot(waiting_for or "pending")
        raise

    from case3.deck_structure import normalize_structure_id
    from case3.deck_theme import normalize_pack_id

    pack0 = normalize_pack_id((deck_pack or "").strip()[:40] or "atelier")
    structure0 = normalize_structure_id((deck_structure_id or "").strip() or None)
    style_settings0: dict[str, Any] | None = None
    raw_style = (deck_style_json or "").strip()
    if raw_style:
        try:
            parsed_style = json.loads(raw_style)
            if isinstance(parsed_style, dict):
                style_settings0 = {
                    str(k): str(v)
                    for k, v in parsed_style.items()
                    if isinstance(k, str) and v is not None
                }
        except json.JSONDecodeError:
            style_settings0 = None
    from case3.chart_style import normalize_palette_id
    from case3.chat_memory import chain_notice_for_prior, newest_edit
    from case3.slides_beat_planner import clamp_slide_target

    chart_palette0 = normalize_palette_id(chart_palette or "atelier")
    slides_target0 = clamp_slide_target(target_slides)
    slides_style0 = {
        "theme_pack": pack0,
        "structure_id": structure0,
        "style_settings": style_settings0,
        "target_slides": slides_target0,
    }
    from case3.api_history import sanitize_workspace_id

    attachments_meta: list[dict[str, Any]] = []
    if attachments_json and attachments_json.strip():
        try:
            raw_att = json.loads(attachments_json)
            if isinstance(raw_att, list):
                for item in raw_att[:5]:
                    if not isinstance(item, dict):
                        continue
                    row_att: dict[str, Any] = {}
                    for k in ("title", "fileName", "viewMode", "previewUrl", "originalUrl", "ingestId", "format"):
                        v = item.get(k)
                        if isinstance(v, str) and v.strip():
                            row_att[k] = v.strip()[:500]
                    if row_att:
                        attachments_meta.append(row_att)
        except json.JSONDecodeError:
            attachments_meta = []

    from case3.source_attach import merge_ingested_sources

    merged_source = merge_ingested_sources(source_body, attachments_meta, run_store.ROOT)
    if merged_source != source_body:
        source_body = merged_source
        src_path.write_text(source_body, encoding="utf-8")

    wid = sanitize_workspace_id(x_workspace_id)
    meta0 = {
        "run_id": run_id,
        "workspace_id": wid,
        "source": str(resolve_text_file(src_path)),
        "chat_prompt": (intent or "").strip(),
        "prior_run_id": (prior_run_id or "").strip(),
        "carried_run_id": (carried_run_id or "").strip(),
        **({"attachments": attachments_meta} if attachments_meta else {}),
        "last_edit": newest_edit(run_store.ROOT, (prior_run_id or "").strip())
        if (prior_run_id or "").strip()
        else {},
        "intent": full_intent,
        "formats": sorted(fmt_set),
        "output_mode": out_mode,
        "dry_run": is_dry,
        "max_images": max_images,
        "max_charts": max_charts,
        "max_diagrams": max_diagrams,
        "images_opt_in": images_opt_in,
        "user_figures": [f.get("id") for f in user_figures],
        "chart_palette": chart_palette0,
        "deck_pack": pack0,
        "slides_theme_pack": pack0,
        "slides_structure_id": structure0,
        "slides_style": slides_style0,
        "slides_target": slides_target0,
        "status": "running",
        "stage": "llm",
        "stage_detail": "жду модель…",
        "chat_notice": chain_notice_for_prior(
            run_store.ROOT, (prior_run_id or "").strip()
        ),
    }
    from case3.run_events import write_meta_atomic

    job = _PipelineJob(
        src_path=src_path,
        run_id=run_id,
        formats=fmt_set,
        dry_run=is_dry,
        intent=full_intent,
        max_images=max_images,
        max_charts=max_charts,
        max_diagrams=max_diagrams,
        user_figures=user_figures,
        output_mode=out_mode,
    )
    waiting_detail = (
        f"Жду прогон {waiting_for}" if waiting_for else "Жду текущий прогон"
    )
    if turn == "queue":
        meta0["status"] = "queued"
        meta0["stage"] = "queued"
        meta0["stage_detail"] = waiting_detail
        meta0["waiting_for"] = waiting_for
        from case3.run_events import note_craft_stage

        note_craft_stage(
            meta0, stage="queued", scope="pipeline", detail=waiting_detail
        )
        payload0 = json.dumps(meta0, ensure_ascii=False, indent=2)
        write_meta_atomic(out_dir / "meta.json", payload0, logs_meta=logs_dir / "meta.json")
        EVENTS.start(run_id)
        EVENTS.bind_out(run_id, out_dir)
        EVENTS.publish_stage(run_id, "queued", detail=waiting_detail, scope="pipeline")
        if _commit_waiter(job) == "queued":
            return JSONResponse(
                status_code=202,
                content={
                    "run_id": run_id,
                    "status": "queued",
                    "stage": "queued",
                    "stage_detail": waiting_detail,
                    "waiting_for": waiting_for,
                    "output_mode": out_mode,
                    "max_charts": max_charts,
                    "max_images": max_images,
                    "max_diagrams": max_diagrams,
                },
            )
        meta0["status"] = "running"
        meta0["stage"] = "llm"
        meta0["stage_detail"] = "жду модель…"
        meta0.pop("waiting_for", None)

    payload0 = json.dumps(meta0, ensure_ascii=False, indent=2)
    write_meta_atomic(out_dir / "meta.json", payload0, logs_meta=logs_dir / "meta.json")
    if turn != "queue":
        EVENTS.start(run_id)
        EVENTS.bind_out(run_id, out_dir)
    EVENTS.publish_stage(run_id, "llm", detail="жду модель…", scope="pipeline")

    # Slot already claimed — thread only releases in finally (do not claim again).
    _spawn_pipeline_thread(job, slot_gen=run_slot_gen)

    return JSONResponse(
        status_code=202,
        content={
            "run_id": run_id,
            "status": "started",
            "stage": "llm",
            "output_mode": out_mode,
            "max_charts": max_charts,
            "max_images": max_images,
            "max_diagrams": max_diagrams,
        },
    )


@app.get("/api/runs/{run_id}/memory")
def get_run_memory(run_id: str) -> dict[str, Any]:
    """Turns of this chat, oldest first, and the documents still attached."""
    if not _RUN_ID_OK.match(run_id):
        raise HTTPException(400, detail="invalid run_id")
    from case3.chat_memory import memory_view

    payload = memory_view(run_store.ROOT, run_id)
    if not payload:
        raise HTTPException(404, detail="run not found")
    return payload


@app.get("/api/runs/{run_id}/status")
def get_run_status(run_id: str) -> dict[str, Any]:
    if not _RUN_ID_OK.match(run_id):
        raise HTTPException(400, detail="invalid run_id")
    out_dir = (run_store.ROOT / "runs" / "out" / run_id).resolve()
    out_root = (run_store.ROOT / "runs" / "out").resolve()
    if not str(out_dir).startswith(str(out_root)):
        raise HTTPException(404, detail="run not found")
    meta_path = out_dir / "meta.json"
    if not meta_path.is_file():
        logs_meta = run_store.ROOT / "runs" / "logs" / run_id / "meta.json"
        if logs_meta.is_file():
            meta_path = logs_meta
        else:
            raise HTTPException(404, detail="run not found")
    try:
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise HTTPException(500, detail="corrupt meta.json") from exc

    status = meta.get("status") or "running"
    if status in {"running", "queued"}:
        return {
            "run_id": run_id,
            "status": status,
            "stage": meta.get("stage") or "queued",
            "stage_detail": meta.get("stage_detail"),
            "waiting_for": meta.get("waiting_for"),
            "max_charts": meta.get("max_charts"),
            "max_images": meta.get("max_images"),
            "chat_summary": str(meta.get("chat_summary") or ""),
            "summary_status": meta.get("summary_status"),
            "slides_status": meta.get("slides_status") or "idle",
            "slides_stage": meta.get("slides_stage"),
            "cancel_requested": bool(meta.get("cancel_requested")),
            "steps": meta.get("steps") if isinstance(meta.get("steps"), list) else [],
        }
    if status == "cancelled":
        err = meta.get("error") or "Остановлено"
        return {
            "run_id": run_id,
            "status": "cancelled",
            "stage": "cancelled",
            "error": err,
            "message": err,
            "slides_status": meta.get("slides_status") or "idle",
            "slides_stage": meta.get("slides_stage"),
            "slides_error": meta.get("slides_error"),
        }
    if status == "error":
        err = meta.get("error") or "pipeline failed"
        failed_c = meta.get("failed_charts")
        failed_f = meta.get("failed_figures")
        if not isinstance(failed_c, list) or not isinstance(failed_f, list):
            media = meta.get("media_status") or {}
            if not isinstance(media, dict):
                media = {}
            if not isinstance(failed_c, list):
                failed_c = [
                    cid
                    for cid in (meta.get("charts_planned") or [])
                    if not (isinstance(media.get(cid), dict) and media[cid].get("ok"))
                ]
            if not isinstance(failed_f, list):
                failed_f = [
                    fid
                    for fid in (meta.get("figures_planned") or [])
                    if not (isinstance(media.get(fid), dict) and media[fid].get("ok"))
                ]
        work_dir = run_store.ROOT / "runs" / "work" / run_id
        from case3.pipeline import can_resume_run

        return {
            "run_id": run_id,
            "status": "error",
            "stage": "error",
            "error": err,
            "message": err,
            "hint": f"logs: runs/logs/{run_id}",
            "failed_charts": failed_c,
            "failed_figures": failed_f,
            "failed_stage": meta.get("failed_stage"),
            "can_resume": can_resume_run(meta, work=work_dir, out=out_dir),
            "latex_log_tail": meta.get("latex_log_tail") or "",
            "max_charts": meta.get("max_charts"),
            "max_images": meta.get("max_images"),
        }
    # ok (or unknown → treat as result payload if out exists)
    if not out_dir.is_dir():
        out_dir = run_store.ROOT / "runs" / "out" / run_id
    return _run_result_payload(run_id, out_dir, meta)


def _media_previews(
    run_id: str, out_dir: Path, media: dict[str, Any]
) -> list[dict[str, str]]:
    """PNG thumbnails that succeeded (charts / Image API) under out/figures/."""
    figs = out_dir / "figures"
    if not figs.is_dir():
        return []
    out: list[dict[str, str]] = []
    for png in sorted(figs.glob("*.png")):
        mid = png.stem
        st = media.get(mid) if isinstance(media.get(mid), dict) else {}
        if st and not st.get("ok"):
            continue
        if not png.is_file():
            continue
        kind = str(st.get("kind") or ("chart" if mid.startswith("cht_") else "figure"))
        out.append(
            {
                "id": mid,
                "kind": kind,
                "url": f"/api/runs/{run_id}/figures/{png.name}",
            }
        )
    return out


@app.get("/api/runs/{run_id}/preview")
def get_run_preview(run_id: str) -> dict[str, Any]:
    out_dir = _resolve_run_dir(run_id)
    meta: dict[str, Any] = {}
    meta_path = out_dir / "meta.json"
    if meta_path.is_file():
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            meta = {}
    media = meta.get("media_status") or {}
    preview = _build_preview_payload(
        run_id, out_dir, media if isinstance(media, dict) else {}
    )
    # Cache-bust figure URLs (edit responses already add ?v=; GET must too).
    bust = 0
    figs = out_dir / "figures"
    if figs.is_dir():
        for p in figs.glob("*.png"):
            try:
                bust = max(bust, int(p.stat().st_mtime))
            except OSError:
                continue
    if not bust:
        try:
            bust = int((meta.get("chart_edit_last") or {}).get("ts") or 0)
        except (TypeError, ValueError):
            bust = 0
    if bust:
        for block in preview.get("blocks") or []:
            if (
                isinstance(block, dict)
                and block.get("type") == "figure"
                and block.get("url")
            ):
                url = str(block["url"])
                if "v=" in url:
                    continue
                sep = "&" if "?" in url else "?"
                block["url"] = f"{url}{sep}v={bust}"
    return preview


def _warnings(meta: dict[str, Any], *, max_images: int) -> list[str]:
    """One short line per soft-failed chart or figure. The report still ships."""
    media = meta.get("media_status") or {}
    if not isinstance(media, dict):
        media = {}
    lines: list[str] = []
    for cid in meta.get("charts_planned") or []:
        slot = media.get(cid)
        if isinstance(slot, dict) and slot.get("ok"):
            continue
        lines.append(f"График {cid} не собрался")
    if max_images > 0:
        for fid in meta.get("figures_planned") or []:
            slot = media.get(fid)
            if isinstance(slot, dict) and slot.get("ok"):
                continue
            lines.append(f"Рисунок {fid} не собрался")
    if lines:
        log.info("media soft-failed: %s", ", ".join(lines))
    if len(lines) > 4:
        extra = len(lines) - 3
        lines = lines[:3] + [f"Ещё {extra} не собрались"]
    return lines


def datetime_stamp() -> str:
    from datetime import datetime, timezone
    import uuid

    return f"{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}_{uuid.uuid4().hex[:6]}"


@app.get("/api/runs/{run_id}/files/{name}")
def download_file(run_id: str, name: str) -> FileResponse:
    path = _safe_run_file(run_id, name)
    suf = path.suffix.lower()
    media = "application/octet-stream"
    if suf == ".pdf":
        media = "application/pdf"
    elif suf == ".docx":
        media = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    elif suf == ".png":
        media = "image/png"
    elif suf == ".pptx":
        media = (
            "application/vnd.openxmlformats-officedocument.presentationml.presentation"
        )
    return FileResponse(path, media_type=media, filename=path.name)


def _bg_resume_pipeline(run_id: str, slot_gen: int | None = None) -> None:
    print(f"[case3] resume thread start run_id={run_id}", flush=True)
    log.info("resume thread start run_id=%s", run_id)
    from case3.pipeline import PipelineError, resume_pipeline
    from case3.run_meta import read_meta

    try:
        resume_pipeline(run_id, project_root=run_store.ROOT)
        out = run_store.ROOT / "runs" / "out" / run_id
        meta = read_meta(out) or {}
        if str(meta.get("output_mode") or "").strip().lower() == "presentation":
            _auto_kick_presentation_slides(run_id)
    except PipelineError as exc:
        log.exception("background resume failed run_id=%s", run_id)
        _settle_resume_if_still_running(run_id, str(exc) or "resume failed")
    except Exception as exc:  # noqa: BLE001
        log.exception("background resume crashed run_id=%s", run_id)
        _settle_resume_if_still_running(run_id, str(exc) or "resume crashed")
    finally:
        _release_pipeline_slot(run_id, generation=slot_gen)


def _settle_resume_if_still_running(run_id: str, message: str) -> None:
    """A resume that died before writing meta must not leave status=running."""
    from case3.run_meta import read_meta, update_meta

    out = run_store.ROOT / "runs" / "out" / run_id
    logs = run_store.ROOT / "runs" / "logs" / run_id
    current = read_meta(out)
    if str(current.get("status") or "") != "running":
        return
    text = (message or "resume crashed")[:500]

    def _mut(meta: dict[str, Any]) -> None:
        if str(meta.get("status") or "") != "running":
            return
        meta["status"] = "error"
        meta["stage"] = "error"
        meta["error"] = text

    update_meta(out, _mut, logs_dir=logs)
    try:
        from case3.run_events import EVENTS

        EVENTS.publish_terminal(run_id, "error", error=text)
    except Exception:  # noqa: BLE001
        log.exception("could not publish resume terminal run_id=%s", run_id)


def _kick_resume_thread(run_id: str) -> None:
    """Start resume. Caller already owns the slot (``resume_run`` claimed it)."""
    gen = _slot_generation(run_id)
    threading.Thread(
        target=_bg_resume_pipeline,
        kwargs={"run_id": run_id, "slot_gen": gen},
        name=f"case3-resume-{run_id}",
        daemon=True,
    ).start()


@app.post("/api/runs/{run_id}/resume")
def resume_run(run_id: str) -> dict[str, Any]:
    """Continue a failed run from failed_stage.

    ``llm`` replays ``work/*.raw_model.txt`` and does not call the model.
    The slot is claimed before meta flips to ``running``.
    """
    if not _RUN_ID_OK.match(run_id):
        raise HTTPException(400, detail="invalid run_id")
    out_dir = (run_store.ROOT / "runs" / "out" / run_id).resolve()
    work_dir = run_store.ROOT / "runs" / "work" / run_id
    out_root = (run_store.ROOT / "runs" / "out").resolve()
    if not str(out_dir).startswith(str(out_root)):
        raise HTTPException(404, detail="run not found")
    meta_path = out_dir / "meta.json"
    if not meta_path.is_file():
        logs_meta = run_store.ROOT / "runs" / "logs" / run_id / "meta.json"
        if logs_meta.is_file():
            meta_path = logs_meta
        else:
            raise HTTPException(404, detail="run not found")
    try:
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise HTTPException(500, detail="corrupt meta.json") from exc
    if not isinstance(meta, dict):
        meta = {}
    from case3.pipeline import can_resume_run

    if not can_resume_run(meta, work=work_dir, out=out_dir):
        raise HTTPException(
            409,
            detail="run is not eligible to resume (need error after LLM on media/render)",
        )
    # Claim before any meta write. A 409 must leave status=error so «Продолжить» stays.
    busy = _claim_pipeline_slot(run_id)
    if busy is not None:
        raise HTTPException(
            409,
            detail=f"Уже идёт прогон {busy}. Дождись конца.",
        )
    resumed_from = meta.get("failed_stage")
    _set_slot_handoff(True)
    try:
        # Flip to running so Liber poll leaves the error card immediately.
        meta["status"] = "running"
        meta["stage"] = resumed_from or "queued"
        meta.pop("cancel_requested", None)
        meta.pop("error", None)
        logs_dir = run_store.ROOT / "runs" / "logs" / run_id
        from case3.run_meta import write_meta

        write_meta(out_dir, meta, logs_dir=logs_dir)
        _kick_resume_thread(run_id)
    except Exception:
        _release_pipeline_slot(run_id, generation=_slot_generation(run_id))
        raise
    finally:
        _set_slot_handoff(False)
    return {"run_id": run_id, "status": "started", "resumed_from": resumed_from}


@app.post("/api/runs/{run_id}/cancel")
def cancel_run(run_id: str) -> dict[str, Any]:
    """Cooperative stop: UI frees immediately; pipeline/slides exit between stages."""
    if not _RUN_ID_OK.match(run_id):
        raise HTTPException(400, detail="invalid run_id")
    out_dir = (run_store.ROOT / "runs" / "out" / run_id).resolve()
    out_root = (run_store.ROOT / "runs" / "out").resolve()
    if not str(out_dir).startswith(str(out_root)):
        raise HTTPException(404, detail="run not found")
    logs_dir = run_store.ROOT / "runs" / "logs" / run_id
    if not (out_dir / "meta.json").is_file() and not (logs_dir / "meta.json").is_file():
        raise HTTPException(404, detail="run not found")
    settled_queue = False

    def _mut_cancel(m: dict[str, Any]) -> None:
        nonlocal settled_queue
        m["cancel_requested"] = True
        if str(m.get("status") or "") == "queued":
            settled_queue = True
            m["status"] = "cancelled"
            m["stage"] = "cancelled"
            m["error"] = "Остановлено"
            m.pop("stage_detail", None)
            m.pop("waiting_for", None)

    from case3.run_meta import update_meta

    meta = update_meta(out_dir, _mut_cancel, logs_dir=logs_dir)
    if settled_queue:
        _drop_queued_waiter(run_id)
        try:
            from case3.run_events import EVENTS

            EVENTS.publish_terminal(run_id, "cancelled", error="Остановлено")
        except Exception:  # noqa: BLE001
            log.exception("could not publish queued cancel run_id=%s", run_id)
    from case3.api_slides import _slides_patch_lock, _slides_patch_pending

    with _slides_patch_lock:
        _slides_patch_pending.pop(run_id, None)
    if _is_run_active(run_id):
        if not _is_pipeline_thread_alive(run_id):
            _release_pipeline_slot(run_id)
    return {
        "run_id": run_id,
        "status": "cancelling",
        "cancel_requested": True,
        "pipeline_status": meta.get("status"),
        "slides_status": meta.get("slides_status"),
    }


@app.post("/api/pipeline/slot/reset")
def reset_pipeline_slot() -> dict[str, Any]:
    """Release desk slots only when their pipeline threads are already dead."""
    with _PIPELINE_ACTIVE_GUARD:
        active_ids = list(_PIPELINE_ACTIVE.keys())
    for aid in active_ids:
        if aid == "pending" or aid.startswith("pending#") or _is_pipeline_thread_alive(aid):
            raise HTTPException(
                409,
                detail=(
                    f"Прогон {aid} ещё выполняется. "
                    "Сброс слота только если поток уже умер."
                ),
            )
    _release_pipeline_slot()
    return {"ok": True, "reset_from": active_ids[0] if active_ids else None}


@app.get("/api/runs/{run_id}/figures/{name}")
def download_figure(run_id: str, name: str) -> FileResponse:
    if not name.lower().endswith(".png"):
        raise HTTPException(400, detail="only PNG figures")
    path = _safe_run_file(run_id, "figures", name)
    return FileResponse(path, media_type="image/png", filename=path.name)


from case3.api_edits import router as edits_router
from case3.api_history import router as history_router
from case3.api_photo import router as photo_router
from case3.api_slides import router as slides_router
from case3.api_stream import router as stream_router

app.include_router(edits_router)
app.include_router(history_router)
app.include_router(photo_router)
app.include_router(slides_router)
app.include_router(stream_router)
