"""Disk waiter: one queued run survives an API restart (ADR-0010)."""

from __future__ import annotations

import json
import time
from pathlib import Path

from fastapi.testclient import TestClient

from case3.api import app, _claim_pipeline_slot, _release_pipeline_slot
from case3.pipeline_queue import clear_waiter, load_waiter, save_waiter


def _source(root: Path, name: str = "source.txt") -> Path:
    upload = root / "runs" / "uploads" / "stamp"
    upload.mkdir(parents=True, exist_ok=True)
    path = upload / name
    path.write_text("Выручка 12 и 40%.", encoding="utf-8")
    return path


def _queued_meta(root: Path, run_id: str) -> None:
    out = root / "runs" / "out" / run_id
    out.mkdir(parents=True, exist_ok=True)
    (out / "meta.json").write_text(
        json.dumps(
            {
                "run_id": run_id,
                "status": "queued",
                "stage": "queued",
                "steps": [
                    {
                        "event": "stage",
                        "stage": "queued",
                        "scope": "pipeline",
                        "t": 1.0,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )


def test_save_and_load_roundtrip(tmp_path: Path) -> None:
    src = _source(tmp_path)
    save_waiter(
        tmp_path,
        {
            "src_path": str(src),
            "run_id": "source_20261110T120000Z",
            "formats": ["pdf"],
            "dry_run": False,
            "intent": "Отчёт",
            "max_images": 1,
            "max_charts": 2,
            "max_diagrams": 0,
            "user_figures": [{"id": "usr_01", "caption": "экран"}],
            "output_mode": "report",
        },
    )
    loaded = load_waiter(tmp_path)
    assert loaded is not None
    assert loaded["run_id"] == "source_20261110T120000Z"
    assert loaded["user_figures"] == [{"id": "usr_01", "caption": "экран"}]
    assert loaded["formats"] == ["pdf"]
    assert Path(loaded["src_path"]) == src.resolve()


def test_load_rejects_path_outside_root(tmp_path: Path) -> None:
    outside = tmp_path.parent / "not-a-run-source.txt"
    outside.write_text("x", encoding="utf-8")
    save_waiter(
        tmp_path,
        {
            "src_path": str(outside),
            "run_id": "source_20261110T120001Z",
            "formats": ["pdf"],
            "dry_run": False,
            "intent": "Отчёт",
            "max_images": 0,
            "max_charts": 0,
            "max_diagrams": 0,
            "user_figures": [],
            "output_mode": "report",
        },
    )
    assert load_waiter(tmp_path) is None


def test_clear_waiter_only_matching_run(tmp_path: Path) -> None:
    src = _source(tmp_path)
    payload = {
        "src_path": str(src),
        "run_id": "source_keep",
        "formats": ["docx"],
        "dry_run": False,
        "intent": "x",
        "max_images": 0,
        "max_charts": 0,
        "max_diagrams": 0,
        "user_figures": [],
        "output_mode": "report",
    }
    save_waiter(tmp_path, payload)
    assert clear_waiter(tmp_path, run_id="source_other") is False
    assert load_waiter(tmp_path) is not None
    assert clear_waiter(tmp_path, run_id="source_keep") is True
    assert load_waiter(tmp_path) is None


def test_post_run_persists_waiter(tmp_path: Path, monkeypatch) -> None:
    import threading

    monkeypatch.setenv("CASE3_MAX_CONCURRENT_RUNS", "1")
    monkeypatch.setenv("CASE3_MAX_QUEUED_RUNS", "1")
    ran = threading.Event()

    def _fake_bg(**kwargs: object) -> None:
        ran.set()

    monkeypatch.setattr("case3.run_store.ROOT", tmp_path)
    monkeypatch.setattr("case3.api._bg_run_pipeline", _fake_bg)
    assert _claim_pipeline_slot("holder_run") is None
    run_id = ""
    try:
        client = TestClient(app)
        queued = client.post(
            "/api/run",
            data={"source_text": "Текст отчёта с числами 12 и 40%", "intent": "Отчёт"},
        )
        assert queued.status_code == 202
        run_id = queued.json()["run_id"]
        stored = load_waiter(tmp_path)
        assert stored is not None
        assert stored["run_id"] == run_id
        meta = json.loads(
            (tmp_path / "runs" / "out" / run_id / "meta.json").read_text(encoding="utf-8")
        )
        assert meta["status"] == "queued"
        assert any(
            isinstance(s, dict) and s.get("stage") == "queued" for s in meta.get("steps") or []
        )
    finally:
        _release_pipeline_slot("holder_run")
        if run_id:
            assert ran.wait(2)
            _release_pipeline_slot(run_id)


def test_two_runs_in_the_same_second_get_different_ids(tmp_path: Path, monkeypatch) -> None:
    from datetime import datetime, timezone

    from case3.pipeline import prepare_run_dirs

    class _Frozen:
        @staticmethod
        def now(tz=None):
            return datetime(2026, 11, 19, 6, 55, tzinfo=timezone.utc)

    monkeypatch.setattr("case3.pipeline.datetime", _Frozen)
    src = _source(tmp_path)
    first, *_ = prepare_run_dirs(src, project_root=tmp_path)
    second, *_ = prepare_run_dirs(src, project_root=tmp_path)
    assert first == "source_20261119T065500Z"
    assert second == "source_20261119T065500Z_2"
    assert (tmp_path / "runs" / "out" / first).is_dir()
    assert (tmp_path / "runs" / "out" / second).is_dir()


def test_chat_question_starts_beside_a_queued_report(tmp_path: Path, monkeypatch) -> None:
    """A question must not take the build slot or the single waiter."""
    import threading

    from case3.api import _drop_queued_waiter, _pipeline_active_run

    monkeypatch.setenv("CASE3_MAX_CONCURRENT_RUNS", "1")
    monkeypatch.setenv("CASE3_MAX_QUEUED_RUNS", "1")
    monkeypatch.setattr("case3.run_store.ROOT", tmp_path)
    chat_ran = threading.Event()
    monkeypatch.setattr(
        "case3.api._bg_run_pipeline",
        lambda **kwargs: chat_ran.set() if kwargs.get("output_mode") == "chat" else None,
    )
    assert _claim_pipeline_slot("holder_run") is None
    report_id = ""
    try:
        client = TestClient(app)
        report = client.post(
            "/api/run",
            data={"source_text": "Выручка была 12.", "intent": "Сделай отчёт", "output_mode": "report"},
        )
        assert report.status_code == 202
        assert report.json()["status"] == "queued"
        report_id = report.json()["run_id"]
        third = client.post(
            "/api/run",
            data={"source_text": "Выручка была 12.", "intent": "Сделай ещё отчёт", "output_mode": "report"},
        )
        assert third.status_code == 409
        chat = client.post(
            "/api/run",
            data={
                "source_text": "Выручка была 12.",
                "intent": "почему выручка такая",
                "output_mode": "chat",
            },
        )
        assert chat.status_code == 202
        body = chat.json()
        assert body["status"] == "started"
        assert body["output_mode"] == "chat"
        assert body["run_id"] != report_id
        assert _pipeline_active_run() == "holder_run"
        stored = load_waiter(tmp_path)
        assert stored is not None
        assert stored["run_id"] == report_id
        assert chat_ran.wait(2)
    finally:
        if report_id:
            _drop_queued_waiter(report_id)
        _release_pipeline_slot("holder_run")
        active = _pipeline_active_run()
        if active:
            _release_pipeline_slot(active)


def test_recover_starts_queued_job_after_restart(tmp_path: Path, monkeypatch) -> None:
    from case3.api import recover_persisted_pipeline

    started: list[str] = []

    def _fake_bg(**kwargs: object) -> None:
        started.append(str(kwargs["run_id"]))

    monkeypatch.setattr("case3.run_store.ROOT", tmp_path)
    monkeypatch.setattr("case3.api._bg_run_pipeline", _fake_bg)
    run_id = "source_20261110T130000Z"
    src = _source(tmp_path)
    _queued_meta(tmp_path, run_id)
    save_waiter(
        tmp_path,
        {
            "src_path": str(src),
            "run_id": run_id,
            "formats": ["pdf", "docx"],
            "dry_run": True,
            "intent": "Отчёт",
            "max_images": 0,
            "max_charts": 0,
            "max_diagrams": 0,
            "user_figures": [],
            "output_mode": "report",
        },
    )
    try:
        assert recover_persisted_pipeline() == run_id
        for _ in range(50):
            if started and load_waiter(tmp_path) is None:
                break
            time.sleep(0.02)
        assert started == [run_id]
        assert load_waiter(tmp_path) is None
    finally:
        _release_pipeline_slot(run_id)


def test_recover_drops_terminal_and_cancelled(tmp_path: Path, monkeypatch) -> None:
    from case3.api import recover_persisted_pipeline

    monkeypatch.setattr("case3.run_store.ROOT", tmp_path)
    monkeypatch.setattr(
        "case3.api._bg_run_pipeline",
        lambda **kwargs: (_ for _ in ()).throw(AssertionError("must not start")),
    )
    run_id = "source_20261110T130001Z"
    src = _source(tmp_path)
    out = tmp_path / "runs" / "out" / run_id
    out.mkdir(parents=True)
    (out / "meta.json").write_text(
        json.dumps({"run_id": run_id, "status": "queued", "cancel_requested": True}),
        encoding="utf-8",
    )
    save_waiter(
        tmp_path,
        {
            "src_path": str(src),
            "run_id": run_id,
            "formats": ["pdf"],
            "dry_run": False,
            "intent": "Отчёт",
            "max_images": 0,
            "max_charts": 0,
            "max_diagrams": 0,
            "user_figures": [],
            "output_mode": "report",
        },
    )
    assert recover_persisted_pipeline() is None
    assert load_waiter(tmp_path) is None
