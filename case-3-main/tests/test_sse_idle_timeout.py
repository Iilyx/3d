"""SSE subscribe deadline is idle time, not a wall clock from connect."""

from __future__ import annotations

import asyncio

from case3.run_events import RunEventBus


def test_subscribe_async_survives_past_timeout_when_idle_pings_flow() -> None:
    async def _run() -> list[str]:
        bus = RunEventBus()
        bus.start("sse_long")

        async def _consume() -> list[str]:
            kinds: list[str] = []
            async for ev in bus.subscribe_async(
                "sse_long",
                timeout_s=1.2,
                keepalive_s=1.0,
                poll_s=0.02,
            ):
                kinds.append(str(ev.get("event")))
                if ev.get("event") in {"done", "error", "cancelled"}:
                    break
            return kinds

        task = asyncio.create_task(_consume())
        # Past the original deadline, after at least one keepalive.
        await asyncio.sleep(1.5)
        bus.publish_terminal("sse_long", "ok")
        return await asyncio.wait_for(task, timeout=2)

    kinds = asyncio.run(_run())
    assert "ping" in kinds
    assert kinds[-1] == "done"
    assert "error" not in kinds


def test_subscribe_async_times_out_when_nothing_is_yielded() -> None:
    async def _run() -> dict:
        bus = RunEventBus()
        bus.start("sse_idle")
        async for ev in bus.subscribe_async(
            "sse_idle",
            timeout_s=0.15,
            keepalive_s=10,
            poll_s=0.02,
        ):
            return ev
        return {}

    ev = asyncio.run(_run())
    assert ev.get("event") == "error"
    assert ev.get("error") == "events timeout"
