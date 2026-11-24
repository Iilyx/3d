from __future__ import annotations

import json
from pathlib import Path

from case3.pipeline import run_pipeline


def test_pipeline_insufficient_data_short_circuits(tmp_path: Path):
    root = tmp_path / "project"
    root.mkdir()
    (root / "prompt" / "gold").mkdir(parents=True)

    src = tmp_path / "source.txt"
    src.write_text("привет, сделай отчет", encoding="utf-8")

    out_dir = run_pipeline(
        src,
        project_root=root,
        intent="сделай отчет",
        output_mode="report",
        dry_run=True,
    )

    meta_file = out_dir / "meta.json"
    assert meta_file.is_file(), "meta.json must be written"
    meta = json.loads(meta_file.read_text(encoding="utf-8"))

    assert meta.get("insufficient_data") is True
    assert meta.get("status") == "ok"
    assert meta.get("stage") == "ok"
    assert meta.get("artifacts") == {}
    assert "недостаточно данных" in (meta.get("chat_summary") or "").lower()

    summary_file = out_dir / "chat_summary.txt"
    assert summary_file.is_file()
    assert "недостаточно данных" in summary_file.read_text(encoding="utf-8").lower()


def test_pipeline_restores_dashboard_screen_before_validation(tmp_path: Path):
    root = tmp_path / "project"
    root.mkdir()
    (root / "prompt" / "gold").mkdir(parents=True)

    prior_id = "source_20261123T120000Z"
    prior_dir = root / "runs" / "out" / prior_id
    prior_dir.mkdir(parents=True)
    screen_file = root / "runs" / "uploads" / "screen.md"
    screen_file.parent.mkdir(parents=True)
    screen_file.write_text(
        "# Данные дашборда\n\n| Регион | Факт | План |\n| --- | --- | --- |\n| Минск | 120 | 100 |\n",
        encoding="utf-8",
    )
    (prior_dir / "meta.json").write_text(
        json.dumps({"run_id": prior_id, "source": str(screen_file), "output_mode": "chat"}),
        encoding="utf-8",
    )

    followup_src = tmp_path / "followup.txt"
    followup_src.write_text("Сделай отчёт", encoding="utf-8")

    out_dir = run_pipeline(
        followup_src,
        project_root=root,
        intent="Сделай отчёт",
        output_mode="report",
        formats={"pdf"},
        prior_run_id=prior_id,
        dry_run=True,
    )
    meta = json.loads((out_dir / "meta.json").read_text(encoding="utf-8"))
    assert meta.get("insufficient_data") is not True
