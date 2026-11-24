"""Cancel endpoint + cooperative flag."""

from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient

from case3.api import app


def test_cancel_marks_meta(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr("case3.run_store.ROOT", tmp_path)
    run_id = "run_cancel_test"
    out = tmp_path / "runs" / "out" / run_id
    out.mkdir(parents=True)
    (out / "meta.json").write_text(
        json.dumps({"run_id": run_id, "status": "running", "stage": "latex"}),
        encoding="utf-8",
    )
    client = TestClient(app)
    r = client.post(f"/api/runs/{run_id}/cancel")
    assert r.status_code == 200
    body = r.json()
    assert body["cancel_requested"] is True
    meta = json.loads((out / "meta.json").read_text(encoding="utf-8"))
    assert meta["cancel_requested"] is True
    assert meta["status"] == "running"


def test_cancel_queued_run_settles_and_drops_waiter(tmp_path: Path, monkeypatch) -> None:
    import case3.api as api
    from case3.pipeline_queue import load_waiter, save_waiter

    monkeypatch.setattr("case3.run_store.ROOT", tmp_path)
    monkeypatch.setattr("case3.api.recover_persisted_pipeline", lambda: None)
    run_id = "source_20261110T140000Z"
    out = tmp_path / "runs" / "out" / run_id
    out.mkdir(parents=True)
    (out / "meta.json").write_text(
        json.dumps(
            {
                "run_id": run_id,
                "status": "queued",
                "stage": "queued",
                "stage_detail": "Жду прогон other",
                "waiting_for": "other",
            }
        ),
        encoding="utf-8",
    )
    src = tmp_path / "runs" / "uploads" / "source.txt"
    src.parent.mkdir(parents=True)
    src.write_text("Выручка 10", encoding="utf-8")
    save_waiter(
        tmp_path,
        {
            "src_path": str(src),
            "run_id": run_id,
            "formats": ["pdf"],
            "dry_run": False,
            "intent": "",
            "max_images": 0,
            "max_charts": 0,
            "max_diagrams": 0,
            "user_figures": [],
            "output_mode": "report",
        },
    )
    api._PIPELINE_WAITER = api._PipelineJob(
        src_path=src,
        run_id=run_id,
        formats={"pdf"},
        dry_run=False,
        intent="",
        max_images=0,
        max_charts=0,
        max_diagrams=0,
        user_figures=[],
        output_mode="report",
    )
    api._WAITER_RESERVED = True
    try:
        client = TestClient(app)
        r = client.post(f"/api/runs/{run_id}/cancel")
        assert r.status_code == 200
        meta = json.loads((out / "meta.json").read_text(encoding="utf-8"))
        assert meta["status"] == "cancelled"
        assert meta["stage"] == "cancelled"
        assert meta["cancel_requested"] is True
        assert "waiting_for" not in meta
        assert load_waiter(tmp_path) is None
        assert api._PIPELINE_WAITER is None
        assert api._WAITER_RESERVED is False
        st = client.get(f"/api/runs/{run_id}/status")
        assert st.status_code == 200
        assert st.json()["status"] == "cancelled"
    finally:
        api._PIPELINE_WAITER = None
        api._WAITER_RESERVED = False
