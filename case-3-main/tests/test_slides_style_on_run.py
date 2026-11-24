"""Presentation deck style must survive /api/run → pipeline → auto-kick."""

from __future__ import annotations

import json
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import case3.api as api_mod
from case3.pipeline import merge_desk_slides_fields


@pytest.fixture()
def client(api_client: TestClient) -> TestClient:
    return api_client


def test_merge_desk_slides_fields_keeps_structure() -> None:
    prev = {
        "deck_pack": "signal",
        "slides_theme_pack": "signal",
        "slides_structure_id": "qbr",
        "slides_style": {
            "theme_pack": "signal",
            "structure_id": "qbr",
            "style_settings": {"primary": "#202020"},
        },
    }
    meta = {"run_id": "x", "status": "running", "stage": "llm"}
    out = merge_desk_slides_fields(meta, prev)
    assert out["slides_structure_id"] == "qbr"
    assert out["slides_theme_pack"] == "signal"
    assert out["slides_style"]["style_settings"]["primary"] == "#202020"


def test_run_stamps_structure_and_style_then_autokick_uses_them(
    client: TestClient, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    captured: dict = {}

    def _fake_pipeline(src_path, **kwargs):
        from case3.run_meta import read_meta, write_meta

        run_id = kwargs["run_id"]
        root = kwargs["project_root"]
        out = Path(root) / "runs" / "out" / run_id
        logs = Path(root) / "runs" / "logs" / run_id
        out.mkdir(parents=True, exist_ok=True)
        logs.mkdir(parents=True, exist_ok=True)
        prev = read_meta(out)
        meta = {
            "run_id": run_id,
            "source": str(src_path),
            "status": "ok",
            "stage": "ok",
            "output_mode": "presentation",
            "formats": [],
        }
        merge_desk_slides_fields(meta, prev)
        write_meta(out, meta, logs_dir=logs)
        captured["meta_after_pipeline"] = dict(meta)

    kicked: list[str] = []

    def _fake_kick(run_id: str) -> None:
        kicked.append(run_id)
        from case3.run_meta import read_meta

        out = api_mod.run_store.ROOT / "runs" / "out" / run_id
        captured["meta_at_kick"] = read_meta(out)

    monkeypatch.setattr(api_mod, "run_pipeline", _fake_pipeline)
    monkeypatch.setattr("case3.api_slides._kick_slides_thread", _fake_kick)

    style = {
        "primary": "#112233",
        "accent": "#445566",
        "background": "#fffef9",
        "text": "#111111",
        "fontTitle": "Georgia",
        "fontBody": "Calibri",
    }
    r = client.post(
        "/api/run",
        data={
            "source_text": "Воронка: 10 → 5 → 2. CAC 100.",
            "intent": "дек",
            "output_mode": "presentation",
            "formats": "none",
            "max_charts": "1",
            "max_images": "0",
            "forbid_images": "true",
            "dry_run": "true",
            "deck_pack": "botanical",
            "deck_structure_id": "investor",
            "deck_style_json": json.dumps(style),
        },
    )
    assert r.status_code == 202, r.text
    run_id = r.json()["run_id"]

    body: dict = {}
    for _ in range(100):
        st = client.get(f"/api/runs/{run_id}/status")
        body = st.json()
        if body.get("status") == "ok" and kicked:
            break
        time.sleep(0.05)

    assert body.get("status") == "ok", body
    assert kicked == [run_id]
    meta_kick = captured.get("meta_at_kick") or {}
    assert meta_kick.get("slides_structure_id") == "investor"
    assert meta_kick.get("slides_theme_pack") == "botanical"
    ss = meta_kick.get("slides_style") or {}
    assert ss.get("structure_id") == "investor"
    assert ss.get("theme_pack") == "botanical"
    settings = ss.get("style_settings") or {}
    assert settings.get("primary") == "#112233"
    assert settings.get("fontTitle") == "Georgia"
    assert meta_kick.get("slides_status") == "running"
