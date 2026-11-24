"""Repo root resolution — one place instead of scattered ``parents[2]``."""

from __future__ import annotations

import os
from pathlib import Path


def repo_root(*, start: Path | None = None) -> Path:
    """Return case-3 repo root (directory that contains ``Dockerfile`` or ``prompt``+``assets``).

    Falls back to ``Path.cwd()`` when the sentinel is missing (Docker / installed wheel).
    """
    env_root = (os.environ.get("CASE3_ROOT") or "").strip()
    if env_root:
        cand = Path(env_root).resolve()
        if cand.is_dir():
            return cand
    here = (start or Path(__file__)).resolve()
    for cand in [here, *here.parents]:
        if (cand / "Dockerfile").is_file() and (cand / "src" / "case3").is_dir():
            return cand
        if (cand / "prompt").is_dir() and (cand / "assets").is_dir():
            return cand
    cwd = Path.cwd().resolve()
    if (cwd / "prompt").is_dir() and (cwd / "assets").is_dir():
        return cwd
    # Legacy depth used by api.py / cli when Dockerfile check was shallow.
    if len(here.parents) >= 2:
        shallow = here.parents[2] if here.name != "paths.py" else Path(__file__).resolve().parents[2]
        if (shallow / "Dockerfile").is_file():
            return shallow
    return cwd
