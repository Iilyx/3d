"""In-process token bus for chat-summary SSE (per run_id)."""

from __future__ import annotations

import asyncio
import threading
import time
from collections.abc import AsyncIterator, Iterator
from dataclasses import dataclass, field
from typing import Any

DEFAULT_SUMMARY_BUS_TTL_S = 1800.0


@dataclass
class _RunState:
    lock: threading.Lock = field(default_factory=threading.Lock)
    deltas: list[str] = field(default_factory=list)
    ops: list[tuple[str, str]] = field(default_factory=list)
    full: str = ""
    status: str = "pending"  # pending|streaming|ok|error|skipped
    done: bool = False
    started_at: float = field(default_factory=time.time)
    finished_at: float | None = None
    waiters: list[threading.Event] = field(default_factory=list)
    cond: threading.Condition = field(default_factory=threading.Condition)


class SummaryBus:
    """Publish deltas; subscribers get replay + live until done."""

    def __init__(self) -> None:
        self._runs: dict[str, _RunState] = {}
        self._lock = threading.Lock()

    def _state(self, run_id: str) -> _RunState:
        with self._lock:
            st = self._runs.get(run_id)
            if st is None:
                st = _RunState()
                self._runs[run_id] = st
            return st

    def evict_stale(self, *, max_age_s: float = DEFAULT_SUMMARY_BUS_TTL_S) -> int:
        """Remove completed summary states older than ``max_age_s`` from memory."""
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
        self.evict_stale()
        st = self._state(run_id)
        with st.cond:
            st.status = "streaming"
            st.done = False
            st.deltas.clear()
            st.ops.clear()
            st.full = ""
            st.started_at = time.time()
            st.finished_at = None
            st.cond.notify_all()

    def publish(self, run_id: str, text: str) -> None:
        if not text:
            return
        st = self._state(run_id)
        with st.cond:
            st.deltas.append(text)
            st.ops.append(("delta", text))
            st.status = "streaming"
            st.cond.notify_all()

    def replace(self, run_id: str, text: str) -> None:
        """Reset streamed prefix to corrected text (after verification/grounding)."""
        st = self._state(run_id)
        with st.cond:
            st.deltas.clear()
            if text:
                st.deltas.append(text)
            st.ops.append(("replace", text))
            st.status = "streaming"
            st.cond.notify_all()

    def finish(self, run_id: str, text: str, status: str = "ok") -> None:
        st = self._state(run_id)
        with st.cond:
            st.full = text or "".join(st.deltas)
            st.status = status
            st.done = True
            st.finished_at = time.time()
            st.cond.notify_all()

    def snapshot(self, run_id: str) -> dict[str, Any]:
        st = self._state(run_id)
        with st.cond:
            return {
                "text": st.full or "".join(st.deltas),
                "status": st.status,
                "done": st.done,
            }

    def subscribe(self, run_id: str, *, timeout_s: float = 120.0) -> Iterator[dict[str, Any]]:
        """Yield {event, text?, status?} until done or timeout."""
        st = self._state(run_id)
        sent = 0
        deadline = time.monotonic() + max(0.1, timeout_s)
        while True:
            with st.cond:
                while sent >= len(st.ops) and not st.done:
                    remaining = deadline - time.monotonic()
                    if remaining <= 0:
                        yield {
                            "event": "done",
                            "text": st.full or "".join(st.deltas),
                            "status": st.status if st.done else "error",
                        }
                        return
                    st.cond.wait(timeout=min(0.5, remaining))

                while sent < len(st.ops):
                    kind, piece = st.ops[sent]
                    sent += 1
                    yield {"event": kind, "text": piece}

                if st.done:
                    yield {
                        "event": "done",
                        "text": st.full or "".join(st.deltas),
                        "status": st.status,
                    }
                    return

    async def subscribe_async(
        self,
        run_id: str,
        *,
        timeout_s: float = 120.0,
        poll_s: float = 0.04,
    ) -> AsyncIterator[dict[str, Any]]:
        """Non-blocking async generator yielding {event, text?, status?} until done or timeout."""
        st = self._state(run_id)
        sent = 0
        deadline = time.monotonic() + max(0.1, timeout_s)
        while True:
            pieces: list[tuple[str, str]] = []
            done_payload: dict[str, Any] | None = None
            with st.cond:
                while sent < len(st.ops):
                    pieces.append(st.ops[sent])
                    sent += 1
                if st.done and sent >= len(st.ops):
                    done_payload = {
                        "event": "done",
                        "text": st.full or "".join(st.deltas),
                        "status": st.status,
                    }

            for kind, piece in pieces:
                yield {"event": kind, "text": piece}
            if done_payload is not None:
                yield done_payload
                return
            if pieces:
                continue

            remaining = deadline - time.monotonic()
            if remaining <= 0:
                with st.cond:
                    full_text = st.full or "".join(st.deltas)
                    cur_status = st.status if st.done else "error"
                yield {
                    "event": "done",
                    "text": full_text,
                    "status": cur_status,
                }
                return

            await asyncio.sleep(min(poll_s, max(0.005, remaining)))


# Process-wide bus used by pipeline + API
BUS = SummaryBus()
