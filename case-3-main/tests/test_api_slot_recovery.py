"""Tests for pipeline slot self-healing and reset endpoint."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock

from fastapi.testclient import TestClient

from case3.api import app, _claim_pipeline_slot, _release_pipeline_slot, _pipeline_active_run


def test_stale_slot_auto_reclaimed_when_terminal_meta_exists(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr("case3.run_store.ROOT", tmp_path)
    run_id = "source_20261108T194925Z"
    out = tmp_path / "runs" / "out" / run_id
    logs = tmp_path / "runs" / "logs" / run_id
    out.mkdir(parents=True)
    logs.mkdir(parents=True)
    (out / "meta.json").write_text(
        json.dumps({"run_id": run_id, "status": "cancelled", "error": "Остановлено"}),
        encoding="utf-8",
    )
    # Simulate slot being locked by this cancelled run
    assert _claim_pipeline_slot(run_id) is None
    assert _pipeline_active_run() == run_id

    # A subsequent attempt to claim the slot must auto-reclaim it because status is cancelled
    new_holder = "source_new_test_123"
    claimed = _claim_pipeline_slot(new_holder)
    assert claimed is None
    assert _pipeline_active_run() == new_holder

    _release_pipeline_slot(new_holder)
    assert _pipeline_active_run() is None


def test_release_starts_the_waiting_run(tmp_path: Path, monkeypatch) -> None:
    import time

    from case3.api import _claim_pipeline_slot, _release_pipeline_slot

    started: list[str] = []

    def _fake_bg(**kwargs: object) -> None:
        started.append(str(kwargs["run_id"]))
        _release_pipeline_slot(str(kwargs["run_id"]))

    monkeypatch.setattr("case3.run_store.ROOT", tmp_path)
    monkeypatch.setattr("case3.api._bg_run_pipeline", _fake_bg)
    monkeypatch.setenv("CASE3_MAX_CONCURRENT_RUNS", "1")
    assert _claim_pipeline_slot("holder_run") is None
    try:
        client = TestClient(app)
        queued = client.post(
            "/api/run",
            data={"source_text": "Текст отчёта с числами 12 и 40%", "intent": "Отчёт"},
        )
        assert queued.status_code == 202
        run_id = queued.json()["run_id"]
        assert started == []
        _release_pipeline_slot("holder_run")
        for _ in range(50):
            if started:
                break
            time.sleep(0.02)
        assert started == [run_id]
    finally:
        if not started:
            _release_pipeline_slot("holder_run")


def test_stale_finally_same_run_does_not_drop_new_owner(
    tmp_path: Path, monkeypatch
) -> None:
    """Terminal meta reclaims the slot for the same run_id; the old finally must keep the new owner."""
    from case3.api import _PIPELINE_SLOT, _release_pipeline_slot, _slot_generation

    monkeypatch.setattr("case3.run_store.ROOT", tmp_path)
    run_id = "source_20261110T120000Z"
    out = tmp_path / "runs" / "out" / run_id
    out.mkdir(parents=True)
    (out / "meta.json").write_text(
        json.dumps({"run_id": run_id, "status": "ok"}),
        encoding="utf-8",
    )
    assert _claim_pipeline_slot(run_id) is None
    stale_gen = _slot_generation()

    assert _claim_pipeline_slot(run_id) is None
    fresh_gen = _slot_generation()
    assert fresh_gen != stale_gen
    assert _pipeline_active_run() == run_id

    _release_pipeline_slot(run_id, generation=stale_gen)
    assert _pipeline_active_run() == run_id
    assert _PIPELINE_SLOT.locked()

    _release_pipeline_slot(run_id, generation=fresh_gen)
    assert _pipeline_active_run() is None
    assert not _PIPELINE_SLOT.locked()


def test_pipeline_slot_reset_endpoint() -> None:
    assert _claim_pipeline_slot("mock_stuck_run") is None
    assert _pipeline_active_run() == "mock_stuck_run"

    client = TestClient(app)
    resp = client.post("/api/pipeline/slot/reset")
    assert resp.status_code == 200
    assert resp.json() == {"ok": True, "reset_from": "mock_stuck_run"}
    assert _pipeline_active_run() is None


def test_pipeline_slot_reset_refuses_while_thread_alive() -> None:
    """Reset must not drop a slot whose pipeline thread is still running."""
    import threading

    from case3.api import _release_pipeline_slot

    started = threading.Event()
    finish = threading.Event()

    def _hold() -> None:
        started.set()
        finish.wait(5)

    thread = threading.Thread(target=_hold, name="case3-pipeline-live_run", daemon=True)
    thread.start()
    assert started.wait(2)
    assert _claim_pipeline_slot("live_run") is None
    try:
        client = TestClient(app)
        resp = client.post("/api/pipeline/slot/reset")
        assert resp.status_code == 409
        assert _pipeline_active_run() == "live_run"
    finally:
        _release_pipeline_slot("live_run")
        finish.set()
        thread.join(2)
