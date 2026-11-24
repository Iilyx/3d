"""Load KEY=VALUE from .env into os.environ (no dependency)."""

from __future__ import annotations

import os
from pathlib import Path


def load_dotenv(path: Path, *, override: bool = True) -> None:
    """Load KEY=VALUE from .env.

    override=True (default): .env wins over ambient env so uvicorn --reload
    picks up edits without killing api.cmd (parent shell may have stale values).
    """
    if not path.is_file():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        key = key.strip()
        val = val.strip().strip('"').strip("'")
        if not key:
            continue
        if override or key not in os.environ:
            os.environ[key] = val
