"""In-process SSE bus for Liber run progress (stages / artifacts / terminal).

Does not stream model thoughts — only craft stage bumps and file-ready pulses.
Durable craft log: meta["steps"] (stage/step/terminal only; no film/sound).
"""

from __future__ import annotations

import asyncio
import json
import os
import threading
import time
from collections.abc import AsyncIterator, Iterator
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

STEPS_CAP = 200
DEFAULT_BUS_TTL_S = 1800.0
_meta_file_lock = threading.RLock()


@dataclass
class _RunEvents:
    lock: threading.Lock = field(default_factory=threading.Lock)
    events: list[dict[str, Any]] = field(default_factory=list)
    done: bool = False
    terminal: str | None = None  # done|error|cancelled
    artifacts_seen: set[str] = field(default_factory=set)
    film_seen: set[str] = field(default_factory=set)
    started_at: float = field(default_factory=time.time)
    finished_at: float | None = None
    out_dir: Path | None = None
    cond: threading.Condition = field(default_factory=threading.Condition)


def compact_step_entry(event: dict[str, Any]) -> dict[str, Any] | None:
    """Shrink SSE event for meta.steps[] (skip film/artifact)."""
    kind = str(event.get("event") or "")
    if kind not in {"stage", "step", "done", "error", "cancelled"}:
        return None
    out: dict[str, Any] = {
        "event": kind,
        "t": float(event.get("t") or time.time()),
    }
    if kind == "stage":
        out["stage"] = str(event.get("stage") or "queued")
        scope = str(event.get("scope") or "")
        if scope:
            out["scope"] = scope
        detail = event.get("detail")
        if detail:
            out["detail"] = str(detail)
    elif kind == "step":
        out["parent"] = str(event.get("parent") or "charts")
        out["id"] = str(event.get("id") or "step")
        out["status"] = str(event.get("status") or "active")
        scope = str(event.get("scope") or "")
        if scope:
            out["scope"] = scope
        if event.get("reason"):
            out["reason"] = str(event.get("reason"))
        if event.get("label"):
            out["label"] = str(event.get("label"))
    else:
        if event.get("status") is not None:
            out["status"] = event.get("status")
        if event.get("error"):
            out["error"] = str(event.get("error"))
        if event.get("hint"):
            out["hint"] = str(event.get("hint"))
    return out


def note_craft_stage(
    meta: dict[str, Any],
    *,
    stage: str,
    scope: str = "pipeline",
    detail: str | None = None,
) -> None:
    """Append one durable stage when the stage *id* changes (not every cht_ detail).

    Avoids Windows meta.json write storms during charts/images progress bumps.
    """
    key = f"{scope}:{stage}"
    if str(meta.get("_craft_stage_key") or "") == key:
        return
    entry = compact_step_entry(
        {
            "event": "stage",
            "stage": stage,
            "scope": scope,
            "t": time.time(),
            **({"detail": detail} if detail else {}),
        }
    )
    if not entry:
        return
    steps = list(meta.get("steps") or [])
    if not isinstance(steps, list):
        steps = []
    steps.append(entry)
    meta["steps"] = steps[-STEPS_CAP:]
    meta["_craft_stage_key"] = key


def write_meta_atomic(
    meta_path: Path,
    payload: str,
    *,
    logs_meta: Path | None = None,
) -> None:
    """Write meta.json via tmp+replace (Windows-safe vs readers/AV)."""
    meta_path = Path(meta_path)
    with _meta_file_lock:
        meta_path.parent.mkdir(parents=True, exist_ok=True)
        tmp = meta_path.with_suffix(".json.tmp")
        last_err: OSError | None = None
        for attempt in range(6):
            try:
                tmp.write_text(payload, encoding="utf-8")
                os.replace(tmp, meta_path)
                last_err = None
                break
            except OSError as exc:
                last_err = exc
                time.sleep(0.04 * (attempt + 1))
        if last_err is not None:
            # Last resort — may still race with status poll on Win
            meta_path.write_text(payload, encoding="utf-8")
        if logs_meta is not None:
            try:
                logs_meta.parent.mkdir(parents=True, exist_ok=True)
                logs_meta.write_text(payload, encoding="utf-8")
            except OSError:
                pass


def _durable_key(ev: dict[str, Any]) -> tuple[str, ...]:
    return (
        str(ev.get("event") or ""),
        str(ev.get("stage") or ""),
        str(ev.get("scope") or ""),
        str(ev.get("parent") or ""),
        str(ev.get("id") or ""),
        str(ev.get("status") or ""),
        str(ev.get("detail") or ""),
    )


def _normalize_steps(steps: list[Any]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for raw in steps:
        if not isinstance(raw, dict):
            continue
        kind = str(raw.get("event") or "")
        if kind not in {"stage", "step", "done", "error", "cancelled"}:
            continue
        ev = dict(raw)
        if "t" not in ev:
            ev["t"] = time.time()
        out.append(ev)
    return out


def seed_events_from_steps(
    bus: RunEventBus,
    run_id: str,
    steps: list[Any],
) -> int:
    """Replay durable meta.steps into an empty bus (late SSE join)."""
    return bus.seed_from_steps(run_id, steps)


def build_success_recap(
    *,
    elapsed_s: float,
    artifacts_seen: set[str] | None = None,
    charts: int = 0,
    figures: int = 0,
) -> dict[str, Any]:
    """Payload for SSE done.recap (success only)."""
    seen = artifacts_seen or set()
    formats: list[str] = []
    for key in ("pdf", "docx", "pptx", "slides_pdf"):
        if key in seen:
            formats.append(key)
    return {
        "elapsed_s": max(0, int(round(float(elapsed_s)))),
        "charts": max(0, int(charts)),
        "figures": max(0, int(figures)),
        "formats": formats,
    }


class RunEventBus:
    """Publish stage/artifact/terminal; subscribers get replay + live until done."""

    def __init__(self) -> None:
        self._runs: dict[str, _RunEvents] = {}
        self._lock = threading.Lock()

    def _state(self, run_id: str) -> _RunEvents:
        with self._lock:
            st = self._runs.get(run_id)
            if st is None:
                st = _RunEvents()
                self._runs[run_id] = st
            return st

    def evict_stale(self, *, max_age_s: float = DEFAULT_BUS_TTL_S) -> int:
        """Remove completed runs older than ``max_age_s`` from memory."""
        cutoff = time.time() - max(1.0, float(max_age_s))
        removed = 0
        with self._lock:
            stale_ids = [
                rid
                for rid, st in self._runs.items()
                if st.done and float(st.finished_at or st.started_at or 0.0) < cutoff
            ]
            for rid in stale_ids:
                self._runs.pop(rid, None)
                removed += 1
        return removed

    def start(self, run_id: str) -> None:
        """Reset bus for a new run (clears history)."""
        self.evict_stale()
        st = self._state(run_id)
        with st.cond:
            st.events.clear()
            st.done = False
            st.terminal = None
            st.artifacts_seen.clear()
            st.film_seen.clear()
            st.out_dir = None
            st.started_at = time.time()
            st.finished_at = None
            st.cond.notify_all()

    def bind_out(self, run_id: str, out_dir: Path) -> None:
        """Attach out/ so stage/step/terminal append meta.steps[]."""
        st = self._state(run_id)
        with st.cond:
            st.out_dir = Path(out_dir)

    def ensure(self, run_id: str) -> None:
        """Open bus without wiping events (pipeline after API queued seed)."""
        st = self._state(run_id)
        with st.cond:
            st.done = False
            st.terminal = None
            st.finished_at = None
            st.cond.notify_all()

    def reopen(self, run_id: str) -> None:
        """Allow more events after pipeline terminal (e.g. on-demand slides job)."""
        self.ensure(run_id)

    def seed_from_steps(self, run_id: str, steps: list[Any]) -> int:
        """Load meta.steps into an empty in-memory bus (no re-persist)."""
        st = self._state(run_id)
        normalized = _normalize_steps(steps)
        with st.cond:
            if st.events:
                return 0
            return self._append_steps_locked(st, normalized)

    def merge_durable_steps(self, run_id: str, steps: list[Any]) -> int:
        """Append meta.steps the RAM bus does not already have.

        Disk is the prefix. Live events that are not in the file stay in place.
        Nothing is written back to meta.json.
        """
        st = self._state(run_id)
        normalized = _normalize_steps(steps)
        with st.cond:
            if not st.events:
                return self._append_steps_locked(st, normalized)
            have = {_durable_key(ev) for ev in st.events}
            missing = [ev for ev in normalized if _durable_key(ev) not in have]
            return self._append_steps_locked(st, missing)

    def _append_steps_locked(self, st: _RunEvents, steps: list[dict[str, Any]]) -> int:
        """Caller holds ``st.cond``."""
        n = 0
        for ev in steps:
            st.events.append(ev)
            kind = str(ev.get("event") or "")
            if kind in {"done", "error", "cancelled"}:
                st.done = True
                st.terminal = kind
                st.finished_at = float(ev.get("t") or time.time())
            n += 1
        if n:
            st.cond.notify_all()
        return n

    def publish(self, run_id: str, event: dict[str, Any]) -> None:
        st = self._state(run_id)
        appended = False
        with st.cond:
            kind = str(event.get("event") or "")
            scope = str(event.get("scope") or "")
            # Slides craft can continue after pipeline terminal if reopened;
            # drop only hard duplicates of terminal while still closed.
            if st.done and kind in {"done", "error", "cancelled"}:
                return
            if st.done and kind not in {"stage", "step", "artifact", "film"}:
                return
            if st.done and kind == "stage" and scope != "slides":
                return
            st.events.append(dict(event))
            appended = True
            if kind in {"done", "error", "cancelled"}:
                st.done = True
                st.terminal = kind
                st.finished_at = time.time()
            st.cond.notify_all()
        # Do NOT persist meta.steps here — pipeline/slides write steps once per
        # stage id. Double RMW on every publish hammered Windows meta.json (AV).

    def publish_stage(
        self,
        run_id: str,
        stage: str,
        *,
        detail: str | None = None,
        scope: str = "pipeline",
        eta_s: float | None = None,
    ) -> None:
        payload: dict[str, Any] = {
            "event": "stage",
            "stage": stage,
            "scope": scope,  # pipeline | slides
            "t": time.time(),
        }
        if detail:
            payload["detail"] = detail
        if eta_s is not None and eta_s > 0:
            payload["eta_s"] = float(eta_s)
        self.publish(run_id, payload)

    def publish_step(
        self,
        run_id: str,
        *,
        parent: str,
        step_id: str,
        status: str = "active",
        reason: str | None = None,
        label: str | None = None,
        scope: str = "pipeline",
    ) -> None:
        """Fine-grained craft beat (cht_01 under charts, skipped photos, …)."""
        st = (status or "active").strip().lower()
        if st not in {"active", "done", "skipped"}:
            st = "active"
        payload: dict[str, Any] = {
            "event": "step",
            "parent": (parent or "").strip() or "charts",
            "id": (step_id or "").strip() or "step",
            "status": st,
            "scope": scope,
            "t": time.time(),
        }
        if reason:
            payload["reason"] = reason
        if label:
            payload["label"] = label
        self.publish(run_id, payload)

    def publish_artifact(self, run_id: str, kind: str) -> None:
        st = self._state(run_id)
        with st.cond:
            if kind in st.artifacts_seen or st.done:
                return
            st.artifacts_seen.add(kind)
            st.events.append(
                {
                    "event": "artifact",
                    "kind": kind,
                    "ready": True,
                    "t": time.time(),
                }
            )
            st.cond.notify_all()

    def publish_film_frame(
        self,
        run_id: str,
        *,
        frame_id: str,
        kind: str,
        url: str,
    ) -> None:
        """One PNG birth for ThinkingFold film strip (cht_* / fig_*)."""
        fid = (frame_id or "").strip()
        if not fid or not url:
            return
        st = self._state(run_id)
        with st.cond:
            if fid in st.film_seen:
                return
            st.film_seen.add(fid)
            st.events.append(
                {
                    "event": "film",
                    "id": fid,
                    "kind": (kind or "chart").strip() or "chart",
                    "url": url,
                    "t": time.time(),
                }
            )
            st.cond.notify_all()

    def publish_terminal(
        self,
        run_id: str,
        status: str,
        *,
        error: str | None = None,
        hint: str | None = None,
        recap: dict[str, Any] | None = None,
    ) -> None:
        kind = status if status in {"done", "error", "cancelled"} else "done"
        if status == "ok":
            kind = "done"
        payload: dict[str, Any] = {"event": kind, "status": status, "t": time.time()}
        if error:
            payload["error"] = error
        if hint:
            payload["hint"] = hint
        # Recap only on success
        if kind == "done" and recap:
            payload["recap"] = dict(recap)
        self.publish(run_id, payload)

    def elapsed_s(self, run_id: str) -> float:
        st = self._state(run_id)
        with st.cond:
            return max(0.0, time.time() - float(st.started_at or time.time()))

    def success_recap(
        self,
        run_id: str,
        *,
        charts: int = 0,
        figures: int = 0,
    ) -> dict[str, Any]:
        st = self._state(run_id)
        with st.cond:
            seen = set(st.artifacts_seen)
            elapsed = max(0.0, time.time() - float(st.started_at or time.time()))
            # Prefer film counts when meta counts missing
            film_charts = sum(1 for x in st.film_seen if x.startswith("cht_"))
            film_figs = sum(
                1 for x in st.film_seen if x.startswith(("fig_", "usr_"))
            )
        return build_success_recap(
            elapsed_s=elapsed,
            artifacts_seen=seen,
            charts=charts or film_charts,
            figures=figures or film_figs,
        )

    def scan_artifacts(self, run_id: str, out_dir: Path) -> None:
        """Detect PDF/DOCX/PPTX/PNG ready under out/ and emit once each."""
        out = Path(out_dir)
        if not out.is_dir():
            return
        for pdf in out.glob("*.pdf"):
            if pdf.is_file() and pdf.stat().st_size > 100:
                name = pdf.name.lower()
                if "deck" in name or name.startswith("slides"):
                    self.publish_artifact(run_id, "slides_pdf")
                else:
                    self.publish_artifact(run_id, "pdf")
                break
        for docx in out.glob("*.docx"):
            if docx.is_file() and docx.stat().st_size > 100:
                self.publish_artifact(run_id, "docx")
                break
        slides = out / "slides"
        pptx_candidates = list(out.glob("*.pptx")) + (
            list(slides.glob("*.pptx")) if slides.is_dir() else []
        )
        for pptx in pptx_candidates:
            if pptx.is_file() and pptx.stat().st_size > 100:
                self.publish_artifact(run_id, "pptx")
                break
        figs = out / "figures"
        if figs.is_dir():
            pngs = [
                p
                for p in sorted(figs.glob("*.png"))
                if p.is_file() and p.stat().st_size > 50
            ]
            if any(p.name.startswith("cht_") for p in pngs):
                self.publish_artifact(run_id, "chart")
            if any(p.name.startswith("fig_") for p in pngs):
                self.publish_artifact(run_id, "figure")
            elif pngs and not any(p.name.startswith("cht_") for p in pngs):
                self.publish_artifact(run_id, "figure")
            for png in pngs:
                stem = png.stem
                if stem.startswith("cht_"):
                    kind = "chart"
                elif stem.startswith(("fig_", "usr_")):
                    kind = "figure"
                else:
                    continue
                self.publish_film_frame(
                    run_id,
                    frame_id=stem,
                    kind=kind,
                    url=f"/api/runs/{run_id}/figures/{png.name}",
                )

    def snapshot(self, run_id: str) -> dict[str, Any]:
        st = self._state(run_id)
        with st.cond:
            return {
                "count": len(st.events),
                "done": st.done,
                "terminal": st.terminal,
                "artifacts": sorted(st.artifacts_seen),
                "film": sorted(st.film_seen),
            }

    def subscribe(
        self,
        run_id: str,
        *,
        timeout_s: float = 1200.0,
        keepalive_s: float = 15.0,
    ) -> Iterator[dict[str, Any]]:
        """Yield event dicts until terminal or timeout.

        Emits ``event: ping`` every ``keepalive_s`` while idle so Vite/proxies
        do not idle-reset the SSE socket (ECONNRESET in the frontend terminal).
        """
        st = self._state(run_id)
        sent = 0
        timeout_s = max(0.1, float(timeout_s))
        deadline = time.monotonic() + timeout_s
        last_out = time.monotonic()
        keep_every = max(1.0, float(keepalive_s))
        while True:
            ping: dict[str, Any] | None = None
            batch: list[dict[str, Any]] = []
            finished = False
            with st.cond:
                while sent >= len(st.events) and not st.done:
                    remaining = deadline - time.monotonic()
                    if remaining <= 0:
                        yield {
                            "event": "error",
                            "status": "error",
                            "error": "events timeout",
                            "t": time.time(),
                        }
                        return
                    st.cond.wait(timeout=min(0.5, remaining))
                    if sent >= len(st.events) and not st.done:
                        if time.monotonic() - last_out >= keep_every:
                            ping = {"event": "ping", "t": time.time()}
                            break

                while sent < len(st.events):
                    batch.append(dict(st.events[sent]))
                    sent += 1
                finished = st.done and sent >= len(st.events)

            if ping is not None:
                # Idle budget, not a clock from the moment the client connected.
                deadline = time.monotonic() + timeout_s
                last_out = time.monotonic()
                yield ping
            for ev in batch:
                deadline = time.monotonic() + timeout_s
                last_out = time.monotonic()
                yield ev
            if finished:
                return

    async def subscribe_async(
        self,
        run_id: str,
        *,
        timeout_s: float = 1200.0,
        keepalive_s: float = 15.0,
        poll_s: float = 0.04,
    ) -> AsyncIterator[dict[str, Any]]:
        """Non-blocking async generator yielding event dicts until terminal or timeout."""
        st = self._state(run_id)
        sent = 0
        timeout_s = max(0.1, float(timeout_s))
        deadline = time.monotonic() + timeout_s
        last_out = time.monotonic()
        keep_every = max(1.0, float(keepalive_s))
        while True:
            batch: list[dict[str, Any]] = []
            finished = False
            with st.cond:
                while sent < len(st.events):
                    batch.append(dict(st.events[sent]))
                    sent += 1
                finished = st.done and sent >= len(st.events)

            if batch:
                for ev in batch:
                    deadline = time.monotonic() + timeout_s
                    last_out = time.monotonic()
                    yield ev
                if finished:
                    return
                continue

            if finished:
                return

            now = time.monotonic()
            remaining = deadline - now
            if remaining <= 0:
                yield {
                    "event": "error",
                    "status": "error",
                    "error": "events timeout",
                    "t": time.time(),
                }
                return

            if now - last_out >= keep_every:
                deadline = time.monotonic() + timeout_s
                last_out = now
                yield {"event": "ping", "t": time.time()}
                continue

            await asyncio.sleep(min(poll_s, max(0.005, remaining)))


# Process-wide bus used by pipeline + slides + API
EVENTS = RunEventBus()
