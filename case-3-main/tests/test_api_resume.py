"""POST /api/runs/{id}/resume eligibility + kick."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock

from fastapi.testclient import TestClient

from case3.api import app


def _failed_run(tmp_path: Path, *, failed_stage: str = "latex") -> str:
    run_id = "brief_20261029T120000Z"
    work = tmp_path / "runs" / "work" / run_id
    out = tmp_path / "runs" / "out" / run_id
    logs = tmp_path / "runs" / "logs" / run_id
    for d in (work, out, logs):
        d.mkdir(parents=True)
    (work / "brief.tex").write_text(
        r"\documentclass{article}\begin{document}x\end{document}",
        encoding="utf-8",
    )
    (work / "figures.json").write_text(
        json.dumps({"figures": [], "charts": [], "diagrams": []}),
        encoding="utf-8",
    )
    meta = {
        "run_id": run_id,
        "status": "error",
        "stage": "error",
        "failed_stage": failed_stage,
        "formats": ["pdf"],
        "error": "latexmk failed",
    }
    (out / "meta.json").write_text(json.dumps(meta), encoding="utf-8")
    return run_id


def test_resume_409_when_not_eligible(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr("case3.run_store.ROOT", tmp_path)
    run_id = _failed_run(tmp_path, failed_stage="llm")
    client = TestClient(app)
    r = client.post(f"/api/runs/{run_id}/resume")
    assert r.status_code == 409


def test_resume_200_kicks_background(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr("case3.run_store.ROOT", tmp_path)
    run_id = _failed_run(tmp_path, failed_stage="latex")
    kicked = MagicMock()
    monkeypatch.setattr("case3.api._kick_resume_thread", kicked)
    from case3.api import _release_pipeline_slot

    client = TestClient(app)
    try:
        r = client.post(f"/api/runs/{run_id}/resume")
        assert r.status_code == 200
        body = r.json()
        assert body["run_id"] == run_id
        assert body["status"] == "started"
        kicked.assert_called_once_with(run_id)
    finally:
        _release_pipeline_slot(run_id)


def test_status_error_includes_can_resume(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr("case3.run_store.ROOT", tmp_path)
    run_id = _failed_run(tmp_path, failed_stage="charts")
    client = TestClient(app)
    r = client.get(f"/api/runs/{run_id}/status")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "error"
    assert body["can_resume"] is True
    assert body["failed_stage"] == "charts"


def test_resume_claim_failure_keeps_error_meta(tmp_path: Path, monkeypatch) -> None:
    """Slot loss must not flip meta to running — otherwise «Продолжить» disappears."""
    monkeypatch.setattr("case3.run_store.ROOT", tmp_path)
    run_id = _failed_run(tmp_path, failed_stage="latex")
    monkeypatch.setattr("case3.api._claim_pipeline_slot", lambda _rid: "other_run")
    client = TestClient(app)
    r = client.post(f"/api/runs/{run_id}/resume")
    assert r.status_code == 409
    meta = json.loads(
        (tmp_path / "runs" / "out" / run_id / "meta.json").read_text(encoding="utf-8")
    )
    assert meta["status"] == "error"
    assert meta["failed_stage"] == "latex"


def test_resume_409_when_pipeline_slot_busy(tmp_path: Path, monkeypatch) -> None:
    from case3.api import _claim_pipeline_slot, _release_pipeline_slot

    monkeypatch.setenv("CASE3_MAX_CONCURRENT_RUNS", "1")
    monkeypatch.setattr("case3.run_store.ROOT", tmp_path)
    run_id = _failed_run(tmp_path, failed_stage="latex")
    kicked = MagicMock()
    monkeypatch.setattr("case3.api._kick_resume_thread", kicked)
    assert _claim_pipeline_slot("other_active_run") is None
    try:
        client = TestClient(app)
        r = client.post(f"/api/runs/{run_id}/resume")
        assert r.status_code == 409
        assert "other_active_run" in str(r.json().get("detail") or "")
        kicked.assert_not_called()
    finally:
        _release_pipeline_slot("other_active_run")


def test_resume_200_real_background_pipeline_transitions_to_ok(
    tmp_path: Path, monkeypatch
) -> None:
    """Real _bg_resume_pipeline must not fail eligibility after resume_run flips state."""
    from case3.api import _bg_resume_pipeline

    monkeypatch.setattr("case3.run_store.ROOT", tmp_path)
    run_id = _failed_run(tmp_path, failed_stage="latex")

    def fake_render(tex_path: Path, **kwargs):  # noqa: ANN001
        out_dir = kwargs["out_dir"]
        pdf = out_dir / f"{tex_path.stem}.pdf"
        pdf.write_bytes(b"%PDF-1.4")
        return {"pdf": pdf}

    monkeypatch.setattr("case3.pipeline.render_tex", fake_render)
    monkeypatch.setattr(
        "case3.pipeline.try_generate_chat_summary",
        lambda *a, **k: ("ok", "summary"),
    )

    def sync_kick(rid: str) -> None:
        from case3.api import _slot_generation

        _bg_resume_pipeline(rid, slot_gen=_slot_generation())

    monkeypatch.setattr("case3.api._kick_resume_thread", sync_kick)
    client = TestClient(app)
    r = client.post(f"/api/runs/{run_id}/resume")
    assert r.status_code == 200
    meta = json.loads(
        (tmp_path / "runs" / "out" / run_id / "meta.json").read_text(encoding="utf-8")
    )
    assert meta["status"] == "ok"


def test_datetime_stamp_unique_within_same_second() -> None:
    from case3.api import datetime_stamp

    s1 = datetime_stamp()
    s2 = datetime_stamp()
    assert s1 != s2


def test_create_run_queues_one_waiter_and_third_writes_nothing(
    tmp_path: Path, monkeypatch
) -> None:
    """Under 1+1 limit, one run executes, one waits, the third is 409 and must not touch disk."""
    from case3.api import _PIPELINE_SLOT, _claim_pipeline_slot, _release_pipeline_slot

    monkeypatch.setenv("CASE3_MAX_CONCURRENT_RUNS", "1")
    monkeypatch.setenv("CASE3_MAX_QUEUED_RUNS", "1")
    monkeypatch.setattr("case3.run_store.ROOT", tmp_path)
    monkeypatch.setattr("case3.api._bg_run_pipeline", lambda **_k: None)
    assert _claim_pipeline_slot("busy_run_123") is None
    try:
        client = TestClient(app)
        queued = client.post(
            "/api/run",
            data={"source_text": "Конфиденциальный отчёт за Q4", "intent": "Отчёт"},
        )
        assert queued.status_code == 202, queued.text
        body = queued.json()
        assert body["status"] == "queued"
        assert body["waiting_for"] == "busy_run_123"
        run_id = body["run_id"]
        meta = json.loads(
            (tmp_path / "runs" / "out" / run_id / "meta.json").read_text(encoding="utf-8")
        )
        assert meta["status"] == "queued"
        assert meta["waiting_for"] == "busy_run_123"
        uploads_root = tmp_path / "runs" / "uploads"
        written = list(uploads_root.rglob("source.txt"))
        assert len(written) == 1

        rejected = client.post(
            "/api/run",
            data={"source_text": "Ещё один отчёт", "intent": "Отчёт"},
        )
        assert rejected.status_code == 409
        written_after = list(uploads_root.rglob("source.txt"))
        assert written_after == written

        status = client.get(f"/api/runs/{run_id}/status")
        assert status.status_code == 200
        assert status.json()["status"] == "queued"
    finally:
        from case3.api import _drop_queued_waiter

        if "run_id" in locals() and run_id:
            _drop_queued_waiter(run_id)
        _release_pipeline_slot("busy_run_123")
        if _PIPELINE_SLOT.locked():
            _release_pipeline_slot()


