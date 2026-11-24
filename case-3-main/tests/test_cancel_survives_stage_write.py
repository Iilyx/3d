"""Stage snapshots must not drop cancel_requested written by another thread."""

from __future__ import annotations

import json
from pathlib import Path

from case3.pipeline import _set_stage, _write_meta
from case3.run_cancel import mark_cancel_requested


def _dirs(tmp_path: Path) -> tuple[Path, Path, dict]:
    out = tmp_path / "out"
    logs = tmp_path / "logs"
    out.mkdir()
    logs.mkdir()
    meta = {"run_id": "r_keep_cancel", "status": "running", "stage": "llm"}
    _write_meta(meta, out, logs)
    return out, logs, meta


def test_set_stage_keeps_cancel_requested_from_disk(tmp_path: Path) -> None:
    out, logs, meta = _dirs(tmp_path)
    mark_cancel_requested(out, logs_dir=logs)
    assert "cancel_requested" not in meta

    _set_stage(meta, out, logs, "charts", detail="cht_01")

    disk = json.loads((out / "meta.json").read_text(encoding="utf-8"))
    assert disk["cancel_requested"] is True
    assert disk["stage"] == "charts"
    assert meta["cancel_requested"] is True


def test_success_snapshot_does_not_erase_inflight_cancel(tmp_path: Path) -> None:
    out, logs, meta = _dirs(tmp_path)
    mark_cancel_requested(out, logs_dir=logs)
    meta["status"] = "ok"
    meta["stage"] = "ok"
    meta.pop("cancel_requested", None)

    _write_meta(meta, out, logs)

    disk = json.loads((out / "meta.json").read_text(encoding="utf-8"))
    assert disk["cancel_requested"] is True
    assert disk["status"] != "ok"
