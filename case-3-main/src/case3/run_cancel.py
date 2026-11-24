"""Cooperative cancel for report pipeline + slides jobs."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from case3.run_meta import read_meta as _read_meta_locked
from case3.run_meta import update_meta


class RunCancelled(Exception):
    """User requested stop — exit between stages without treating as hard error."""


def read_meta(out_dir: Path) -> dict[str, Any]:
    return _read_meta_locked(out_dir) or {}


def is_cancel_requested(out_dir: Path) -> bool:
    return bool(read_meta(out_dir).get("cancel_requested"))


def raise_if_cancelled(out_dir: Path) -> None:
    if is_cancel_requested(out_dir):
        raise RunCancelled("cancelled by user")


def mark_cancel_requested(out_dir: Path, logs_dir: Path | None = None) -> dict[str, Any]:
    def _mut(m: dict[str, Any]) -> None:
        m["cancel_requested"] = True

    return update_meta(out_dir, _mut, logs_dir=logs_dir)
