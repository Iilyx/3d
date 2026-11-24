"""Unified meta.json read/write for Liber runs."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable

from case3.run_events import _meta_file_lock, write_meta_atomic


def read_meta(out_dir: Path) -> dict[str, Any]:
    """Load ``out_dir/meta.json`` (empty dict if missing/corrupt)."""
    with _meta_file_lock:
        path = Path(out_dir) / "meta.json"
        if not path.is_file():
            return {}
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}
        return data if isinstance(data, dict) else {}


def write_meta(
    out_dir: Path,
    meta: dict[str, Any],
    *,
    logs_dir: Path | None = None,
    atomic: bool = True,
) -> str:
    """Serialize meta to ``out_dir/meta.json`` (+ optional logs twin).

    Returns the JSON payload string written.
    """
    out_dir = Path(out_dir)
    payload = json.dumps(meta, ensure_ascii=False, indent=2)
    meta_path = out_dir / "meta.json"
    logs_meta = (Path(logs_dir) / "meta.json") if logs_dir is not None else None
    if atomic:
        write_meta_atomic(meta_path, payload, logs_meta=logs_meta)
    else:
        out_dir.mkdir(parents=True, exist_ok=True)
        meta_path.write_text(payload, encoding="utf-8")
        if logs_meta is not None:
            try:
                logs_meta.parent.mkdir(parents=True, exist_ok=True)
                logs_meta.write_text(payload, encoding="utf-8")
            except OSError:
                pass
    return payload


def update_meta(
    out_dir: Path,
    mutator: Callable[[dict[str, Any]], None],
    *,
    logs_dir: Path | None = None,
) -> dict[str, Any]:
    """Atomically read-modify-write ``out_dir/meta.json`` under ``_meta_file_lock``."""
    out_dir = Path(out_dir)
    with _meta_file_lock:
        meta = read_meta(out_dir) or {}
        mutator(meta)
        write_meta(out_dir, meta, logs_dir=logs_dir, atomic=True)
        return meta

