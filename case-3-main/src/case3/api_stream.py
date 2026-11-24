"""SSE streams for Liber run events + chat summary."""

from __future__ import annotations

import json
import logging
from typing import Any

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from case3 import run_store
from case3.run_events import EVENTS
from case3.run_store import RUN_ID_OK
from case3.summary_bus import BUS

log = logging.getLogger("case3.api_stream")
router = APIRouter(tags=["stream"])

def _sse_pack(event: str, data: dict[str, Any]) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


@router.get("/api/runs/{run_id}/events")
async def stream_run_events(run_id: str) -> StreamingResponse:
    """SSE: stage / artifact / done|error|cancelled (no model thoughts)."""
    if not RUN_ID_OK.match(run_id):
        raise HTTPException(400, detail="invalid run_id")
    out_dir = (run_store.ROOT / "runs" / "out" / run_id).resolve()
    out_root = (run_store.ROOT / "runs" / "out").resolve()
    if not str(out_dir).startswith(str(out_root)):
        raise HTTPException(404, detail="run not found")
    work = run_store.ROOT / "runs" / "work" / run_id
    if not out_dir.is_dir() and not work.is_dir():
        raise HTTPException(404, detail="run not found")

    async def gen():
        import time as _time

        # meta.steps[] is the prefix. RAM is only the live tail after that.
        snap = EVENTS.snapshot(run_id)
        meta_path = out_dir / "meta.json"
        if meta_path.is_file():
            try:
                meta = json.loads(meta_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                meta = {}
            EVENTS.bind_out(run_id, out_dir)
            durable = meta.get("steps") if isinstance(meta.get("steps"), list) else []
            st = str(meta.get("status") or "")
            stage = str(meta.get("stage") or "queued")
            detail = meta.get("stage_detail")
            playable: list[Any] = []
            if durable:
                # While still running, drop terminal entries so SSE stays open
                # (pipeline may have logged done before slides reopen).
                playable = (
                    [
                        s
                        for s in durable
                        if isinstance(s, dict)
                        and str(s.get("event") or "")
                        not in {"done", "error", "cancelled"}
                    ]
                    if st == "running"
                    or (
                        st == "ok"
                        and str(meta.get("slides_status") or "")
                        in {"running", "queued"}
                    )
                    else durable
                )
                EVENTS.merge_durable_steps(run_id, playable)
            # Follow-up stage/terminal only for an empty RAM bus (restart).
            # A live bus already has the tail; merge above only fills gaps.
            if snap.get("count", 0) != 0:
                pass
            elif playable and (
                st == "running"
                or (
                    st == "ok"
                    and str(meta.get("slides_status") or "") in {"running", "queued"}
                )
            ):
                EVENTS.ensure(run_id)
                EVENTS.scan_artifacts(run_id, out_dir)
            elif playable and st in {"ok", "error", "cancelled"}:
                has_terminal = any(
                    isinstance(ev, dict)
                    and str(ev.get("event") or "") in {"done", "error", "cancelled"}
                    for ev in playable
                )
                if not has_terminal:
                    kind = "done" if st == "ok" else st
                    payload_t: dict[str, Any] = {"status": st, "t": _time.time()}
                    if meta.get("error"):
                        payload_t["error"] = meta.get("error")
                    yield _sse_pack(kind, payload_t)
                    return
            elif st == "running":
                EVENTS.publish_stage(
                    run_id,
                    stage,
                    detail=str(detail) if detail else None,
                    scope="pipeline",
                )
                EVENTS.scan_artifacts(run_id, out_dir)
            elif st in {"ok", "error", "cancelled"} and not durable:
                slides_st = str(meta.get("slides_status") or "idle")
                out_mode = str(meta.get("output_mode") or "")
                if st == "ok" and slides_st in {"running", "queued"}:
                    EVENTS.reopen(run_id)
                    EVENTS.publish_stage(
                        run_id,
                        str(meta.get("slides_stage") or "starting"),
                        scope="slides",
                    )
                    EVENTS.scan_artifacts(run_id, out_dir)
                elif (
                    st == "ok"
                    and out_mode == "presentation"
                    and slides_st in {"idle", ""}
                ):
                    EVENTS.ensure(run_id)
                    EVENTS.publish_stage(run_id, "pipeline_ok", scope="pipeline")
                    EVENTS.scan_artifacts(run_id, out_dir)
                else:
                    kind = "done" if st == "ok" else st
                    payload: dict[str, Any] = {"status": st, "t": _time.time()}
                    if meta.get("error"):
                        payload["error"] = meta.get("error")
                    yield _sse_pack(kind, payload)
                    return

        async for ev in EVENTS.subscribe_async(run_id, timeout_s=1200.0, keepalive_s=15.0):
            kind = str(ev.get("event") or "stage")
            # SSE comment — keeps Vite proxy / TCP alive during long llm waits
            if kind == "ping":
                yield ": keepalive\n\n"
                continue
            data = {k: v for k, v in ev.items() if k != "event"}
            yield _sse_pack(kind, data)
            if kind in {"done", "error", "cancelled"}:
                return

    return StreamingResponse(
        gen(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/api/runs/{run_id}/summary/stream")
async def stream_run_summary(run_id: str) -> StreamingResponse:
    """SSE: chat summary deltas while PDF renders (replay-safe)."""
    if not RUN_ID_OK.match(run_id):
        raise HTTPException(400, detail="invalid run_id")
    out_dir = (run_store.ROOT / "runs" / "out" / run_id).resolve()
    out_root = (run_store.ROOT / "runs" / "out").resolve()
    if not str(out_dir).startswith(str(out_root)):
        raise HTTPException(404, detail="run not found")
    # Allow stream as soon as run dirs exist (work or out)
    work = run_store.ROOT / "runs" / "work" / run_id
    if not out_dir.is_dir() and not work.is_dir():
        raise HTTPException(404, detail="run not found")

    async def gen():
        # If bus already finished, subscribe still replays.
        # If meta already has final summary and bus never started (restart), emit once.
        snap = BUS.snapshot(run_id)
        meta_path = out_dir / "meta.json"
        if meta_path.is_file() and not snap.get("done") and not snap.get("text"):
            try:
                meta = json.loads(meta_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                meta = {}
            final = str(meta.get("chat_summary") or "")
            st = str(meta.get("summary_status") or "")
            if final and st in {"ok", "error", "skipped"}:
                if final:
                    yield _sse_pack("delta", {"text": final})
                yield _sse_pack("done", {"text": final, "status": st or "ok"})
                return

        async for ev in BUS.subscribe_async(run_id, timeout_s=180.0):
            kind = ev.get("event") or "delta"
            if kind in {"delta", "replace"}:
                yield _sse_pack(kind, {"text": ev.get("text") or ""})
            else:
                yield _sse_pack(
                    "done",
                    {
                        "text": ev.get("text") or "",
                        "status": ev.get("status") or "ok",
                    },
                )

    return StreamingResponse(
        gen(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )

