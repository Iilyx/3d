"""LibreOffice prints a wide Word table on a landscape page and leaves the rest portrait."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pdfplumber
import pytest
from docx import Document


def _to_pdf(docx: Path) -> Path:
    soffice = shutil.which("soffice")
    if not soffice:
        pytest.skip("soffice is not installed")
    profile = (docx.parent / "lo-profile").resolve()
    subprocess.run(
        [
            soffice,
            f"-env:UserInstallation=file://{profile}",
            "--headless",
            "--norestore",
            "--convert-to",
            "pdf",
            "--outdir",
            str(docx.parent),
            str(docx),
        ],
        check=True,
        timeout=90,
        capture_output=True,
    )
    return docx.with_suffix(".pdf")


def _pages(pdf: Path) -> list[tuple[float, float, str]]:
    with pdfplumber.open(str(pdf)) as opened:
        return [
            (page.width, page.height, page.extract_text() or "")
            for page in opened.pages
        ]


def test_libreoffice_prints_only_the_wide_table_sideways(tmp_path: Path) -> None:
    from case3.docx_polish import orient_wide_tables

    docx = tmp_path / "mixed.docx"
    doc = Document()
    doc.add_paragraph("До широкой таблицы")
    doc.add_table(rows=1, cols=2)
    doc.add_paragraph("Между таблицами")
    doc.add_paragraph("Таблица 1. Показатели")
    wide = doc.add_table(rows=1, cols=6)
    for index, cell in enumerate(wide.rows[0].cells):
        cell.text = f"c{index}"
    doc.add_paragraph("После широкой таблицы")
    doc.save(str(docx))
    assert orient_wide_tables(docx) is True

    pages = _pages(_to_pdf(docx))
    filled = [page for page in pages if page[2].strip()]
    assert len(filled) == 3
    before, table, after = filled
    assert before[0] < before[1]
    assert table[0] > table[1]
    assert after[0] < after[1]
    assert abs(table[0] - 841.9) < 2
    assert abs(table[1] - 595.3) < 2
    assert "До широкой таблицы" in before[2]
    assert "Между таблицами" in before[2]
    assert "c0" in table[2] and "c5" in table[2]
    assert "Таблица 1" in table[2]
    assert "После широкой таблицы" in after[2]
    assert "После" not in table[2]
