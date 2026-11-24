"""Per-run summary token bus with replay for late SSE subscribers."""

from __future__ import annotations

import threading
import time

from case3.summary_bus import SummaryBus


def test_publish_and_subscribe_receives_deltas_and_done() -> None:
    bus = SummaryBus()
    bus.start("r1")
    bus.publish("r1", "Привет")
    bus.publish("r1", ", мир")
    bus.finish("r1", "Привет, мир", "ok")

    events = list(bus.subscribe("r1", timeout_s=1.0))
    kinds = [e["event"] for e in events]
    assert kinds.count("delta") >= 2
    assert kinds[-1] == "done"
    assert events[-1]["text"] == "Привет, мир"
    assert events[-1]["status"] == "ok"


def test_late_subscriber_gets_replay() -> None:
    bus = SummaryBus()
    bus.start("r2")
    bus.publish("r2", "A")
    bus.finish("r2", "A", "ok")
    events = list(bus.subscribe("r2", timeout_s=0.5))
    assert any(e["event"] == "delta" and e.get("text") == "A" for e in events)
    assert events[-1]["event"] == "done"


def test_live_subscriber_sees_new_deltas() -> None:
    bus = SummaryBus()
    bus.start("r3")
    out: list[dict] = []

    def reader() -> None:
        for ev in bus.subscribe("r3", timeout_s=2.0):
            out.append(ev)
            if ev["event"] == "done":
                break

    t = threading.Thread(target=reader, daemon=True)
    t.start()
    time.sleep(0.05)
    bus.publish("r3", "x")
    bus.finish("r3", "x", "ok")
    t.join(timeout=2.0)
    assert any(e.get("text") == "x" for e in out if e["event"] == "delta")
    assert out[-1]["event"] == "done"
