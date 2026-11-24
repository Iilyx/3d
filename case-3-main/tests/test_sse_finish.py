"""SSE finish: durable meta.steps[] + seed bus for late join."""

from __future__ import annotations

from pathlib import Path

from case3.run_events import (
    RunEventBus,
    compact_step_entry,
    note_craft_stage,
    seed_events_from_steps,
    write_meta_atomic,
)


def test_compact_step_entry_stage_and_step() -> None:
    st = compact_step_entry(
        {"event": "stage", "stage": "charts", "scope": "pipeline", "t": 1.0, "detail": "cht_01"}
    )
    assert st is not None
    assert st["event"] == "stage"
    assert st["stage"] == "charts"
    assert st["detail"] == "cht_01"

    step = compact_step_entry(
        {
            "event": "step",
            "parent": "charts",
            "id": "cht_01",
            "status": "done",
            "t": 2.0,
        }
    )
    assert step is not None
    assert step["id"] == "cht_01"
    assert step["status"] == "done"

    assert compact_step_entry({"event": "film", "id": "cht_01"}) is None


def test_note_craft_stage_dedupes_detail_bumps(tmp_path: Path) -> None:
    meta: dict = {"run_id": "r"}
    note_craft_stage(meta, stage="charts", detail="cht_01")
    note_craft_stage(meta, stage="charts", detail="cht_02")  # same stage id
    note_craft_stage(meta, stage="images", detail="fig_01")
    assert len(meta["steps"]) == 2
    assert meta["steps"][0]["stage"] == "charts"
    assert meta["steps"][1]["stage"] == "images"
    payload = __import__("json").dumps(meta)
    write_meta_atomic(tmp_path / "meta.json", payload)
    assert (tmp_path / "meta.json").is_file()


def test_publish_does_not_touch_meta_file(tmp_path: Path) -> None:
    """Bus must not RMW meta.json (Windows AV storm)."""
    out = tmp_path / "out"
    out.mkdir()
    (out / "meta.json").write_text('{"steps":[]}', encoding="utf-8")
    before = (out / "meta.json").read_text(encoding="utf-8")
    bus = RunEventBus()
    bus.start("rfin")
    bus.bind_out("rfin", out)
    bus.publish_stage("rfin", "charts", detail="cht_01", scope="pipeline")
    bus.publish_step(
        "rfin", parent="charts", step_id="cht_01", status="done", label="cht_01"
    )
    after = (out / "meta.json").read_text(encoding="utf-8")
    assert after == before


def test_merge_durable_steps_appends_disk_tail_when_bus_is_partial() -> None:
    """RAM is a live tail. meta.steps stays the prefix after a restart or a late join."""
    bus = RunEventBus()
    bus.start("rmerge")
    bus.publish_stage("rmerge", "llm", scope="pipeline")
    disk = [
        {"event": "stage", "stage": "llm", "scope": "pipeline", "t": 1.0},
        {"event": "stage", "stage": "charts", "scope": "pipeline", "t": 2.0},
        {"event": "done", "status": "ok", "t": 3.0},
    ]
    added = bus.merge_durable_steps("rmerge", disk)
    assert added == 2
    events = list(bus.subscribe("rmerge", timeout_s=1.0))
    assert [e["event"] for e in events] == ["stage", "stage", "done"]
    assert [e.get("stage") for e in events[:2]] == ["llm", "charts"]
    assert bus.merge_durable_steps("rmerge", disk) == 0


def test_seed_events_from_steps_replays_into_bus() -> None:
    bus = RunEventBus()
    bus.start("rseed")
    steps = [
        {"event": "stage", "stage": "llm", "scope": "pipeline", "t": 1.0},
        {
            "event": "step",
            "parent": "charts",
            "id": "cht_01",
            "status": "active",
            "t": 2.0,
        },
        {"event": "done", "status": "ok", "t": 3.0},
    ]
    n = seed_events_from_steps(bus, "rseed", steps)
    assert n == 3
    events = list(bus.subscribe("rseed", timeout_s=1.0))
    assert [e["event"] for e in events] == ["stage", "step", "done"]


def test_subscribe_emits_keepalive_ping_while_idle() -> None:
    bus = RunEventBus()
    bus.start("rping")
    bus.publish_stage("rping", "llm", scope="pipeline")
    it = bus.subscribe("rping", timeout_s=3.0, keepalive_s=0.4)
    first = next(it)
    assert first["event"] == "stage"
    ping = next(it)
    assert ping["event"] == "ping"
    bus.publish_terminal("rping", "ok")
    rest = list(it)
    assert any(e["event"] == "done" for e in rest)
