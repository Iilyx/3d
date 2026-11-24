"""Windows-safe subprocess text capture."""

from __future__ import annotations

import sys

from case3.procutil import run_captured


def test_run_captured_decodes_utf8_cyrillic() -> None:
    # Echo bytes that are invalid in cp1251 alone but valid UTF-8 (₽ / Cyrillic).
    code = "import sys; sys.stdout.buffer.write('отчёт \\u20bd\\n'.encode('utf-8'))"
    proc = run_captured([sys.executable, "-c", code], check=True)
    assert "отчёт" in proc.stdout
    assert proc.returncode == 0


def test_run_captured_replaces_undecodable() -> None:
    code = "import sys; sys.stdout.buffer.write(b'ok\\x98bad\\n')"
    proc = run_captured([sys.executable, "-c", code], check=True)
    assert "ok" in proc.stdout
    assert proc.returncode == 0
