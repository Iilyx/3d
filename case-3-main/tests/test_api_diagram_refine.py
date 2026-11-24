"""Tests for diagram refine API endpoint (AI Copilot)."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client(api_client: TestClient) -> TestClient:
    return api_client


def _seed_run(repo_root: Path, run_id: str = "run_diag_refine") -> Path:
    out = repo_root / "runs" / "out" / run_id
    out.mkdir(parents=True, exist_ok=True)
    (out / "meta.json").write_text(
        json.dumps(
            {
                "run_id": run_id,
                "status": "ok",
                "output_mode": "diagram",
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    (out / "figures.json").write_text(
        json.dumps(
            {
                "diagrams": [
                    {
                        "id": "dia_01",
                        "title": "Исходная схема",
                        "type": "flowchart",
                        "mermaid": "flowchart TD\nA-->B",
                    }
                ],
                "figures": [],
                "charts": [],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    return out


def test_refine_rejects_empty_instruction(client: TestClient, repo_root: Path) -> None:
    _seed_run(repo_root)
    res = client.post(
        "/api/runs/run_diag_refine/diagrams/dia_01/refine",
        json={"instruction": "   "},
    )
    assert res.status_code == 400
    assert "укажите" in res.json()["detail"].lower()


def test_refine_rejects_invalid_diagram_id(client: TestClient, repo_root: Path) -> None:
    _seed_run(repo_root)
    res = client.post(
        "/api/runs/run_diag_refine/diagrams/bad!id/refine",
        json={"instruction": "измени"},
    )
    assert res.status_code == 400



def test_refine_success_returns_updated_diagram_and_undo(
    client: TestClient, repo_root: Path
) -> None:
    _seed_run(repo_root)
    fake_result = {
        "id": "dia_01",
        "title": "Улучшенная схема",
        "type": "flowchart",
        "mermaid": "flowchart TD\nA-->L-->B",
        "undo": {"kind": "diagram_refine", "target": "dia_01"},
    }

    with patch("case3.api_edits.refine_diagram_in_run", return_value=fake_result):
        res = client.post(
            "/api/runs/run_diag_refine/diagrams/dia_01/refine",
            json={"instruction": "добавь этап юристов"},
        )

    assert res.status_code == 200
    data = res.json()
    assert data["diagram"]["title"] == "Улучшенная схема"
    assert data["undo"]["kind"] == "diagram_refine"
    assert isinstance(data["diagrams"], list)
