"""Desk health probes + /api/health desk fields."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from case3 import api as api_mod
from case3.desk_health import build_desk_probes


@pytest.fixture()
def client(api_client: TestClient) -> TestClient:
    return api_client


def test_build_desk_probes_five() -> None:
    probes = build_desk_probes(
        docker_ok=True,
        docker_error=None,
        playwright_ok=True,
        vision_configured=True,
        vision_ok=True,
        vision_error=None,
        image_configured=True,
        image_ok=False,
        image_error="connection refused",
        soffice_ok=False,
        soffice_hint="install LO",
    )
    ids = [p["id"] for p in probes]
    assert ids == ["vision", "image", "docker", "soffice", "playwright"]
    image = next(p for p in probes if p["id"] == "image")
    assert image["status"] == "amber"
    assert "case3-image" in (image["hint"] or "")
    soffice = next(p for p in probes if p["id"] == "soffice")
    assert soffice["status"] == "amber"


def test_health_includes_probes_and_soffice(client: TestClient) -> None:
    r = client.get("/api/health")
    assert r.status_code == 200
    data = r.json()
    assert "probes" in data
    assert len(data["probes"]) == 5
    assert "soffice_ok" in data
    assert "vision_ok" in data
    # Image red/amber must not force overall ok=false alone
    assert "image_api_ok" in data


def test_run_events_bus_replay() -> None:
    from case3.run_events import RunEventBus

    bus = RunEventBus()
    bus.start("r1")
    bus.publish_stage("r1", "llm", detail=None)
    bus.publish_artifact("r1", "pdf")
    bus.publish_terminal("r1", "ok")
    events = list(bus.subscribe("r1", timeout_s=1.0))
    kinds = [e["event"] for e in events]
    assert "stage" in kinds
    assert "artifact" in kinds
    assert "done" in kinds


def test_events_endpoint_finished_run(
    client: TestClient, tmp_path: Path
) -> None:
    run_id = "finished_run_sse"
    out = tmp_path / "runs" / "out" / run_id
    out.mkdir(parents=True)
    (out / "meta.json").write_text(
        '{"run_id":"finished_run_sse","status":"ok","stage":"ok"}',
        encoding="utf-8",
    )
    with client.stream("GET", f"/api/runs/{run_id}/events") as r:
        assert r.status_code == 200
        body = "".join(r.iter_text())
    assert "event: done" in body or "event: error" in body or "done" in body
