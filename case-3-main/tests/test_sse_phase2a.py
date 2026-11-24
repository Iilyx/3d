"""SSE phase 2A: steps, ETA helpers, terminal hint."""

from __future__ import annotations

from case3.run_events import RunEventBus
from case3.stage_eta import (
    error_hint,
    estimate_eta_s,
    record_stage_duration,
    reset_timings_for_tests,
)


def setup_function() -> None:
    reset_timings_for_tests()


def test_publish_step_and_eta_on_stage() -> None:
    bus = RunEventBus()
    bus.start("r2a")
    bus.publish_stage("r2a", "charts", detail=None, eta_s=42.0)
    bus.publish_step(
        "r2a",
        parent="charts",
        step_id="cht_01",
        status="active",
    )
    bus.publish_step(
        "r2a",
        parent="charts",
        step_id="cht_01",
        status="done",
    )
    bus.publish_step(
        "r2a",
        parent="photos",
        step_id="photos",
        status="skipped",
        reason="IMAGE_API_BASE_URL empty",
    )
    bus.publish_terminal("r2a", "error", error="boom", hint="TeX: tabularx")
    events = list(bus.subscribe("r2a", timeout_s=1.0))
    kinds = [e["event"] for e in events]
    assert kinds.count("step") >= 3
    stage = next(e for e in events if e["event"] == "stage")
    assert stage.get("eta_s") == 42.0
    skip = next(e for e in events if e.get("status") == "skipped")
    assert skip.get("parent") == "photos"
    assert "IMAGE" in str(skip.get("reason") or "")
    err = next(e for e in events if e["event"] == "error")
    assert err.get("hint") == "TeX: tabularx"


def test_eta_needs_samples() -> None:
    assert estimate_eta_s("charts") is None
    record_stage_duration("charts", 30.0)
    assert estimate_eta_s("charts") is None  # need ≥2
    record_stage_duration("charts", 50.0)
    eta = estimate_eta_s("charts")
    assert eta is not None
    assert 30 <= eta <= 50


def test_error_hint_tex() -> None:
    h = error_hint(RuntimeError("latexmk failed: tabularx"), stage="latex")
    assert h
    assert "TeX" in h or "tabular" in h.lower() or "latex" in h.lower()
