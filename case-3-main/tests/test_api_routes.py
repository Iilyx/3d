"""HTTP contract for Liber ↔ FastAPI (Windows desk: Qwen + Image API)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from case3 import api as api_mod


@pytest.fixture()
def client(api_client: TestClient) -> TestClient:
    return api_client


def test_health_ok(client: TestClient) -> None:
    r = client.get("/api/health")
    assert r.status_code == 200
    data = r.json()
    assert "vision_configured" in data
    assert "image_api_configured" in data or "kandinsky_configured" in data
    assert "chart_types" in data
    assert "chart_palettes" in data


def test_status_rejects_bad_run_id(client: TestClient) -> None:
    # Slash / traversal never reach handler (404) or fail _RUN_ID_OK (400).
    r = client.get("/api/runs/bad/id/with/slash/status")
    assert r.status_code in {400, 404}
    r2 = client.get("/api/runs/not_a_real_run_zzz/status")
    assert r2.status_code == 404
    r3 = client.get("/api/runs/has spaces/status")
    assert r3.status_code in {400, 404}


def test_run_returns_202_and_status_poll(
    client: TestClient, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def _fake_pipeline(*_a, run_id: str, **_kw):
        out = tmp_path / "runs" / "out" / run_id
        out.mkdir(parents=True, exist_ok=True)
        (out / "meta.json").write_text(
            json.dumps(
                {
                    "run_id": run_id,
                    "status": "ok",
                    "stage": "ok",
                    "figures_planned": [],
                    "charts_planned": [],
                    "media_status": {},
                    "max_charts": 0,
                    "max_images": 0,
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        (out / "demo.tex").write_text(
            r"\documentclass{article}\begin{document}Hi\end{document}",
            encoding="utf-8",
        )
        return out

    monkeypatch.setattr(api_mod, "run_pipeline", _fake_pipeline)

    r = client.post(
        "/api/run",
        data={
            "source_text": "Выручка 10 20 30",
            "intent": "краткий отчёт",
            "max_charts": "0",
            "max_images": "0",
            "forbid_charts": "true",
            "forbid_images": "true",
            "dry_run": "true",
            "formats": "both",
            "chart_auto": "true",
            "chart_palette": "atelier",
        },
    )
    assert r.status_code == 202, r.text
    body = r.json()
    assert body.get("status") == "started"
    run_id = body["run_id"]
    assert run_id

    # Daemon thread — poll (TestClient no longer awaits BackgroundTasks).
    import time

    payload: dict = {}
    for _ in range(80):
        st = client.get(f"/api/runs/{run_id}/status")
        assert st.status_code == 200
        payload = st.json()
        if payload.get("status") in {"ok", "error"}:
            break
        time.sleep(0.05)
    assert payload.get("status") == "ok", payload.get("error") or payload
    assert payload["run_id"] == run_id


def test_run_rejects_second_while_busy(client: TestClient, monkeypatch) -> None:
    """Under CASE3_MAX_CONCURRENT_RUNS=1, second queues and third gets 409."""
    monkeypatch.setenv("CASE3_MAX_CONCURRENT_RUNS", "1")
    monkeypatch.setenv("CASE3_MAX_QUEUED_RUNS", "1")
    assert api_mod._claim_pipeline_slot("holder_test") is None
    started: list[str] = []

    def _fake_bg(**kwargs: object) -> None:
        started.append(str(kwargs["run_id"]))

    original = api_mod._bg_run_pipeline
    api_mod._bg_run_pipeline = _fake_bg  # type: ignore[assignment]
    try:
        r = client.post(
            "/api/run",
            data={
                "source_text": "Выручка 10",
                "intent": "Сделай отчёт",
                "output_mode": "report",
                "max_charts": "0",
                "max_images": "0",
                "forbid_charts": "true",
                "forbid_images": "true",
                "dry_run": "true",
                "formats": "both",
            },
        )
        assert r.status_code == 202, r.text
        assert r.json()["status"] == "queued"
        assert r.json()["waiting_for"] == "holder_test"
        assert started == []
        third = client.post(
            "/api/run",
            data={
                "source_text": "Выручка 20",
                "intent": "Сделай второй отчёт",
                "output_mode": "report",
                "dry_run": "true",
            },
        )
        assert third.status_code == 409, third.text
        detail = third.json().get("detail") or ""
        assert "уже ждёт" in detail
        assert "Этот запрос не поставлен" in detail
        assert "перезапуск" not in detail
        assert "holder_test" not in detail
    finally:
        # Release/drain queued waiter while _fake_bg is still stubbed so no real thread escapes.
        api_mod._release_pipeline_slot("holder_test")
        if api_mod._PIPELINE_SLOT.locked():
            api_mod._release_pipeline_slot()
        for _ in range(25):
            if started:
                break
            import time

            time.sleep(0.01)
        api_mod._bg_run_pipeline = original


def test_chart_edit_404_missing_run(client: TestClient) -> None:
    r = client.post(
        "/api/runs/missing_run_20260101T000000Z/charts/cht_01/edit",
        json={"palette": "atelier", "formats": "both"},
    )
    assert r.status_code == 404


def test_table_edit_404_missing_run(client: TestClient) -> None:
    r = client.post(
        "/api/runs/missing_run_20260101T000000Z/tables/1/edit",
        json={
            "caption": "T",
            "headers": ["A"],
            "rows": [["1"]],
            "formats": "both",
        },
    )
    assert r.status_code == 404
