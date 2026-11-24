"""D1: Liber reference.docx uses Liberation Serif, not Times."""

from __future__ import annotations

from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
REF = ROOT / "assets" / "docx" / "reference.docx"


def test_reference_docx_not_times() -> None:
    pytest.importorskip("docx")
    from docx import Document

    assert REF.is_file(), f"missing {REF}"
    doc = Document(str(REF))
    name = (doc.styles["Normal"].font.name or "").strip()
    assert name, "Normal style has no font name"
    assert "times" not in name.lower(), f"still Times: {name}"
    assert name in {"Liberation Serif", "DejaVu Serif"}, name
    for need in ("Heading 3", "Quote", "List Bullet", "List Number"):
        assert need in [s.name for s in doc.styles], f"missing style {need}"
