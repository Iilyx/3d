"""SSE summary stream + status payload fields."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from case3 import api as api_mod
from case3.summary_bus import BUS


@pytest.fixture()
def client(api_client: TestClient) -> TestClient:
    return api_client


def _seed_ok_run(tmp_path: Path, run_id: str, *, summary: str = "Готово.") -> None:
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
                "chat_summary": summary,
                "summary_status": "ok",
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    (out / "demo.tex").write_text(
        r"\documentclass{article}\begin{document}Hi\end{document}",
        encoding="utf-8",
    )


def test_status_reports_insufficient_data(client: TestClient, tmp_path: Path) -> None:
    run_id = "insuf_api_20261122T000000Z"
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
                "insufficient_data": True,
                "chat_summary": "В запросе недостаточно данных.",
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    st = client.get(f"/api/runs/{run_id}/status")
    assert st.status_code == 200
    body = st.json()
    assert body["insufficient_data"] is True
    assert body["chat_summary"] == "В запросе недостаточно данных."


def test_status_includes_chat_summary(client: TestClient, tmp_path: Path) -> None:
    run_id = "sum_api_20261021T000000Z"
    _seed_ok_run(tmp_path, run_id, summary="Собрал отчёт.")
    st = client.get(f"/api/runs/{run_id}/status")
    assert st.status_code == 200
    body = st.json()
    assert body["chat_summary"] == "Собрал отчёт."
    assert body["summary_status"] == "ok"


def test_summary_stream_replays_finished(client: TestClient, tmp_path: Path) -> None:
    run_id = "sum_sse_20261021T000000Z"
    _seed_ok_run(tmp_path, run_id, summary="Итог текста.")
    BUS.start(run_id)
    BUS.publish(run_id, "Итог ")
    BUS.publish(run_id, "текста.")
    BUS.finish(run_id, "Итог текста.", "ok")

    with client.stream("GET", f"/api/runs/{run_id}/summary/stream") as resp:
        assert resp.status_code == 200
        assert "text/event-stream" in resp.headers.get("content-type", "")
        raw = "".join(resp.iter_text())
    assert "event: done" in raw
    assert "Итог текста." in raw
