"""Cooperative cancel flag helpers."""

from __future__ import annotations

from pathlib import Path

import pytest

from case3.run_cancel import (
    RunCancelled,
    is_cancel_requested,
    mark_cancel_requested,
    raise_if_cancelled,
)


def test_mark_and_raise(tmp_path: Path) -> None:
    out = tmp_path / "out"
    out.mkdir()
    (out / "meta.json").write_text("{}", encoding="utf-8")
    assert not is_cancel_requested(out)
    mark_cancel_requested(out, logs_dir=tmp_path / "logs")
    assert is_cancel_requested(out)
    with pytest.raises(RunCancelled):
        raise_if_cancelled(out)
