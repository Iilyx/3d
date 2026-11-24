"""C8: latex log tail + failed chart ids on pipeline/API error."""

from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient

from case3 import api as api_mod
from case3.pipeline import _attach_error_diagnostics, _latex_log_tail


def test_latex_log_tail_reads_last_lines(tmp_path: Path) -> None:
    log = tmp_path / "doc.log"
    log.write_text("\n".join(f"L{i}" for i in range(100)), encoding="utf-8")
    tail = _latex_log_tail(log, lines=5)
    assert "L95" in tail
    assert "L99" in tail
    assert "L0" not in tail


def test_latex_error_keeps_the_bang_line_not_only_the_tail(tmp_path: Path) -> None:
    log = tmp_path / "doc.log"
    body = [
        "! Undefined control sequence.",
        "l.42 \\badcommand",
        "",
    ]
    body.extend("Transcript written on doc.log." for _ in range(60))
    log.write_text("\n".join(body), encoding="utf-8")
    tail = _latex_log_tail(log, lines=8)
    assert "! Undefined control sequence." in tail
    assert "l.42" in tail


def test_attach_error_diagnostics_collects_failed_charts(tmp_path: Path) -> None:
    logs = tmp_path / "logs"
    logs.mkdir()
    (logs / "report.log").write_text(
        "!\nMisplaced alignment tab character &.\n",
        encoding="utf-8",
    )
    meta = {
        "charts_planned": ["cht_01", "cht_02"],
        "figures_planned": ["fig_01"],
        "media_status": {
            "cht_01": {"ok": True, "kind": "chart"},
            "cht_02": {"ok": False, "error": "timeout", "kind": "chart"},
            "fig_01": {"ok": False, "error": "api", "kind": "figure"},
        },
    }
    out = _attach_error_diagnostics(meta, logs_dir=logs, error="latexmk failed")
    assert out["failed_charts"] == ["cht_02"]
    assert out["failed_figures"] == ["fig_01"]
    assert "cht_02" in out["error"]
    assert "Misplaced" in (out.get("latex_log_tail") or "")


def test_status_error_exposes_diagnostics(
    tmp_path: Path, monkeypatch
) -> None:
    runs = tmp_path / "runs"
    for sub in ("out", "logs"):
        (runs / sub / "run_err_20260101T000000Z").mkdir(parents=True)
    rid = "run_err_20260101T000000Z"
    meta = {
        "run_id": rid,
        "status": "error",
        "stage": "error",
        "error": "latexmk did not produce PDF; charts failed: cht_01",
        "failed_charts": ["cht_01"],
        "failed_figures": [],
        "latex_log_tail": "! Misplaced &.\nl.12",
        "max_charts": 1,
        "max_images": 0,
    }
    (runs / "out" / rid / "meta.json").write_text(
        json.dumps(meta), encoding="utf-8"
    )
    monkeypatch.setattr("case3.run_store.ROOT", tmp_path)
    client = TestClient(api_mod.app)
    r = client.get(f"/api/runs/{rid}/status")
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "error"
    assert data["failed_charts"] == ["cht_01"]
    assert "Misplaced" in data["latex_log_tail"]
