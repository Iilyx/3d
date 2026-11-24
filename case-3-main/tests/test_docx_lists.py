"""C7: post-pandoc DOCX itemize/enumerate → List Bullet / List Number."""

from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("docx")

from docx import Document  # noqa: E402
from docx.oxml.ns import qn  # noqa: E402

from case3.docx_lists import fix_docx_lists, try_fix_docx_lists  # noqa: E402


def _has_num_pr(paragraph) -> bool:  # noqa: ANN001
    pPr = paragraph._p.get_or_add_pPr()
    return pPr.find(qn("w:numPr")) is not None


def test_fix_docx_lists_promotes_plain_markers(tmp_path: Path) -> None:
    path = tmp_path / "lists.docx"
    doc = Document()
    doc.add_paragraph("Введение")
    doc.add_paragraph("- первый пункт")
    doc.add_paragraph("- второй пункт")
    doc.add_paragraph("1. нумерованный")
    doc.add_paragraph("2. ещё один")
    doc.save(str(path))

    fix_docx_lists(path)

    out = Document(str(path))
    texts = [p.text for p in out.paragraphs]
    assert "Введение" in texts
    assert "первый пункт" in texts
    assert "- первый пункт" not in texts
    assert "нумерованный" in texts
    assert not any(t.startswith("1. ") for t in texts)

    bullets = [p for p in out.paragraphs if p.text == "первый пункт" or p.text == "второй пункт"]
    assert len(bullets) == 2
    for p in bullets:
        assert p.style.name.startswith("List Bullet")
        assert _has_num_pr(p)

    numbered = [p for p in out.paragraphs if p.text in {"нумерованный", "ещё один"}]
    assert len(numbered) == 2
    for p in numbered:
        assert p.style.name.startswith("List Number")
        assert _has_num_pr(p)


def test_fix_docx_lists_idempotent(tmp_path: Path) -> None:
    path = tmp_path / "lists.docx"
    doc = Document()
    doc.add_paragraph("• уже bullet")
    doc.save(str(path))
    fix_docx_lists(path)
    fix_docx_lists(path)
    out = Document(str(path))
    assert out.paragraphs[-1].text == "уже bullet"
    assert out.paragraphs[-1].style.name.startswith("List Bullet")


def test_try_fix_docx_lists_soft_fail(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    path = tmp_path / "bad.docx"
    path.write_bytes(b"not-a-docx")

    assert try_fix_docx_lists(path) is False
