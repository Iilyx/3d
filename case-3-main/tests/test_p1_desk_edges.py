"""P1 desk edges: source cap, live vision, media warnings, resume crash."""

from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient

from case3 import api as api_mod
from case3.api import _warnings


def test_source_text_over_2mib_rejected_before_slot(api_client: TestClient) -> None:
    huge = "a" * (2 * 1024 * 1024 + 1)
    response = api_client.post(
        "/api/run",
        data={"source_text": huge, "intent": "Отчёт"},
    )
    assert response.status_code == 400
    assert "2 MiB" in response.json()["detail"]


def test_health_ok_requires_live_vision(
    api_client: TestClient, monkeypatch
) -> None:
    api_mod.clear_health_cache()
    monkeypatch.setattr(api_mod, "ensure_image", lambda: None)
    monkeypatch.setattr(api_mod, "probe_playwright_chromium", lambda **_k: (True, None))
    monkeypatch.setattr(api_mod, "probe_image_api", lambda **_k: (False, "down"))
    monkeypatch.setattr(api_mod, "probe_vision", lambda **_k: (True, False, "down"))
    down = api_client.get("/api/health?fresh=1")
    assert down.status_code == 200
    body = down.json()
    assert body["vision_configured"] is True
    assert body["ok"] is False
    assert "image_api_base_url" not in body

    monkeypatch.setattr(api_mod, "probe_vision", lambda **_k: (True, True, None))
    live = api_client.get("/api/health?fresh=1")
    assert live.json()["ok"] is True
    api_mod.clear_health_cache()


def test_warnings_name_failed_charts_and_figures() -> None:
    lines = _warnings(
        {
            "charts_planned": ["cht_01", "cht_02"],
            "figures_planned": ["fig_01", "usr_01"],
            "media_status": {
                "cht_01": {"ok": True},
                "cht_02": {"ok": False, "error": "blank"},
                "fig_01": {"ok": False},
                "usr_01": {"ok": True},
            },
        },
        max_images=2,
    )
    assert any("cht_02" in line for line in lines)
    assert any("fig_01" in line for line in lines)
    assert not any("cht_01" in line for line in lines)
    assert not any("usr_01" in line for line in lines)
    assert _warnings(
        {"figures_planned": ["fig_01"], "media_status": {"fig_01": {"ok": False}}},
        max_images=0,
    ) == []


def test_resume_crash_does_not_stay_running(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr("case3.run_store.ROOT", tmp_path)
    run_id = "source_20261110T210000Z"
    out = tmp_path / "runs" / "out" / run_id
    out.mkdir(parents=True)
    (out / "meta.json").write_text(
        json.dumps({"run_id": run_id, "status": "running", "stage": "latex"}),
        encoding="utf-8",
    )

    def _boom(*_a, **_k):
        raise RuntimeError("disk gone")

    monkeypatch.setattr("case3.pipeline.resume_pipeline", _boom)
    api_mod._bg_resume_pipeline(run_id)
    meta = json.loads((out / "meta.json").read_text(encoding="utf-8"))
    assert meta["status"] == "error"
    assert "disk gone" in str(meta.get("error") or "")
