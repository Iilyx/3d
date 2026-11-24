"""A run left running when the API process dies becomes an error on the next start."""

from __future__ import annotations

import json
import threading
import time
from pathlib import Path

from fastapi.testclient import TestClient


def _seed_running(tmp_path: Path, run_id: str, *, stage: str = "latex") -> Path:
    out = tmp_path / "runs" / "out" / run_id
    work = tmp_path / "runs" / "work" / run_id
    out.mkdir(parents=True)
    work.mkdir(parents=True)
    (work / "brief.tex").write_text(
        r"\documentclass{article}\begin{document}x\end{document}",
        encoding="utf-8",
    )
    (work / "figures.json").write_text("{}", encoding="utf-8")
    (out / "meta.json").write_text(
        json.dumps(
            {
                "run_id": run_id,
                "status": "running",
                "stage": stage,
                "source": str(work / "brief.txt"),
            }
        ),
        encoding="utf-8",
    )
    return out


def test_restart_makes_a_dead_run_resumable(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr("case3.run_store.ROOT", tmp_path)
    monkeypatch.setattr("case3.render.warmup_docker", lambda *a, **k: None)
    run_id = "source_20261122T193700Z"
    out = _seed_running(tmp_path, run_id)
    queued = "source_20261122T193701Z"
    qdir = tmp_path / "runs" / "out" / queued
    qdir.mkdir(parents=True)
    (qdir / "meta.json").write_text(
        json.dumps({"run_id": queued, "status": "queued", "stage": "queued"}),
        encoding="utf-8",
    )

    from case3.api import app

    started: list[str] = []

    def _fake_resume(run_id: str, slot_gen: int | None = None) -> None:
        from case3.api import _release_pipeline_slot

        started.append(run_id)
        _release_pipeline_slot(run_id, generation=slot_gen)

    monkeypatch.setattr("case3.api._bg_resume_pipeline", _fake_resume)

    with TestClient(app) as client:
        body = client.get(f"/api/runs/{run_id}/status").json()
        waiting = client.get(f"/api/runs/{queued}/status").json()
        resumed = client.post(f"/api/runs/{run_id}/resume")

    assert body["status"] == "error"
    assert body["failed_stage"] == "latex"
    assert body["can_resume"] is True
    assert "перезапустил" in body["error"]
    disk = json.loads((out / "meta.json").read_text(encoding="utf-8"))
    assert disk["failed_stage"] == "latex"
    assert waiting["status"] == "queued"
    assert resumed.status_code == 200
    assert resumed.json()["status"] == "started"
    assert resumed.json()["resumed_from"] == "latex"
    for _ in range(50):
        if started:
            break
        time.sleep(0.02)
    assert started == [run_id]


def test_a_live_pipeline_thread_is_not_marked_failed(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr("case3.run_store.ROOT", tmp_path)
    monkeypatch.setattr("case3.render.warmup_docker", lambda *a, **k: None)
    run_id = "source_20261122T193702Z"
    out = _seed_running(tmp_path, run_id)
    release = threading.Event()
    thread = threading.Thread(
        target=release.wait,
        name=f"case3-pipeline-{run_id}",
        daemon=True,
    )
    thread.start()
    try:
        from case3.api import settle_orphaned_runs

        assert run_id not in settle_orphaned_runs()
        disk = json.loads((out / "meta.json").read_text(encoding="utf-8"))
        assert disk["status"] == "running"
    finally:
        release.set()
        thread.join(timeout=2)


def test_a_cancelled_run_does_not_offer_resume(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr("case3.run_store.ROOT", tmp_path)
    run_id = "source_20261122T193703Z"
    out = _seed_running(tmp_path, run_id)
    meta = json.loads((out / "meta.json").read_text(encoding="utf-8"))
    meta["cancel_requested"] = True
    (out / "meta.json").write_text(json.dumps(meta), encoding="utf-8")

    from case3.api import settle_orphaned_runs

    assert settle_orphaned_runs() == [run_id]
    disk = json.loads((out / "meta.json").read_text(encoding="utf-8"))
    assert disk["status"] == "cancelled"
    assert disk.get("failed_stage") in {None, ""}


def test_a_dead_deck_build_stops_spinning(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr("case3.run_store.ROOT", tmp_path)
    run_id = "source_20261122T193704Z"
    out = tmp_path / "runs" / "out" / run_id
    out.mkdir(parents=True)
    (out / "meta.json").write_text(
        json.dumps(
            {
                "run_id": run_id,
                "status": "ok",
                "stage": "ok",
                "slides_status": "running",
                "slides_stage": "pptx",
            }
        ),
        encoding="utf-8",
    )

    from case3.api import settle_orphaned_runs

    assert settle_orphaned_runs() == [run_id]
    disk = json.loads((out / "meta.json").read_text(encoding="utf-8"))
    assert disk["status"] == "ok"
    assert disk["slides_status"] == "error"
    assert "перезапустил" in disk["slides_error"]
