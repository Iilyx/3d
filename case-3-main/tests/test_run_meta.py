"""run_meta read/write (+ atomic twin)."""

from __future__ import annotations

import json
from pathlib import Path

from case3.run_meta import read_meta, write_meta


def test_write_meta_atomic_leaves_valid_json(tmp_path: Path) -> None:
    out = tmp_path / "out"
    logs = tmp_path / "logs"
    out.mkdir()
    logs.mkdir()
    write_meta(out, {"run_id": "r1", "status": "ok"}, logs_dir=logs, atomic=True)
    assert read_meta(out)["status"] == "ok"
    twin = json.loads((logs / "meta.json").read_text(encoding="utf-8"))
    assert twin["run_id"] == "r1"


def test_read_meta_missing_is_empty(tmp_path: Path) -> None:
    assert read_meta(tmp_path / "missing") == {}
