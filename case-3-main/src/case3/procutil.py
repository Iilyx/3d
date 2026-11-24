"""Subprocess helpers — Windows-safe text capture.

Docker / TeX / LibreOffice often emit UTF-8. On Russian Windows the default
locale is cp1251; ``text=True`` without ``encoding=`` then raises
``UnicodeDecodeError`` in ``subprocess``'s reader thread (byte 0x98 etc.).
"""

from __future__ import annotations

import subprocess
from typing import Any


def run_captured(*args: Any, **kwargs: Any) -> subprocess.CompletedProcess[str]:
    """``subprocess.run`` with UTF-8 decode (replace undecodable bytes)."""
    kwargs.pop("text", None)
    kwargs.pop("universal_newlines", None)
    kwargs.setdefault("encoding", "utf-8")
    kwargs.setdefault("errors", "replace")
    kwargs.setdefault("capture_output", True)
    return subprocess.run(*args, **kwargs)
