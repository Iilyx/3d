"""Born-digital Source ingest (no OCR)."""

from __future__ import annotations

from pathlib import Path

import pytest

from case3.source_ingest import (
    IngestDependencyError,
    IngestResult,
    ScanPdfError,
    UnsupportedSourceFormatError,
    file_to_markdown,
)


def test_txt_becomes_markdown_paragraphs(tmp_path: Path) -> None:
    src = tmp_path / "notes.txt"
    src.write_text("Выручка 10 млн.\n\nДоля 35%.\n", encoding="utf-8")
    result = file_to_markdown(src)
    assert isinstance(result, IngestResult)
    assert "Выручка 10 млн." in result.markdown
    assert "Доля 35%." in result.markdown
    assert result.format == "txt"


def test_md_passthrough(tmp_path: Path) -> None:
    src = tmp_path / "s.md"
    src.write_text("# Title\n\n| a | b |\n|---|---|\n| 1 | 2 |\n", encoding="utf-8")
    result = file_to_markdown(src)
    assert result.markdown.startswith("# Title")
    assert result.format == "md"


def test_image_rejected(tmp_path: Path) -> None:
    src = tmp_path / "scan.png"
    src.write_bytes(b"\x89PNG\r\n\x1a\n")
    with pytest.raises(UnsupportedSourceFormatError, match="иллюстрац"):
        file_to_markdown(src)


def test_unknown_extension_rejected(tmp_path: Path) -> None:
    src = tmp_path / "data.xlsx"
    src.write_bytes(b"PK")
    with pytest.raises(UnsupportedSourceFormatError):
        file_to_markdown(src)


def test_scan_only_pdf_refused(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    src = tmp_path / "scan.pdf"
    src.write_bytes(b"%PDF-1.4")

    class FakeTriage:
        usable = False
        scan_pages: list[int] = [1]

        def warn(self) -> None:
            return None

    monkeypatch.setattr(
        "case3.source_ingest.triage_pdf",
        lambda _path: FakeTriage(),
    )
    with pytest.raises(ScanPdfError, match="текстового слоя"):
        file_to_markdown(src)


def test_docx_wide_table_keeps_every_column_and_a_repeated_neighbor(tmp_path: Path) -> None:
    from docx import Document

    src = tmp_path / "wide.docx"
    doc = Document()
    table = doc.add_table(rows=2, cols=14)
    header = [f"c{i}" for i in range(14)]
    values = ["77", "77"] + [str(i) for i in range(12)]
    for index, cell in enumerate(header):
        table.cell(0, index).text = cell
    for index, cell in enumerate(values):
        table.cell(1, index).text = cell
    doc.save(src)

    markdown = file_to_markdown(src).markdown
    assert "| c13 |" in markdown
    assert "| 77 | 77 |" in markdown
    assert "truncated" not in markdown


def test_docx_tables_and_numbers(tmp_path: Path) -> None:
    from docx import Document

    src = tmp_path / "t.docx"
    doc = Document()
    doc.add_heading("Отчёт", level=1)
    doc.add_paragraph("Выручка выросла.")
    table = doc.add_table(rows=2, cols=2)
    table.cell(0, 0).text = "Метрика"
    table.cell(0, 1).text = "Значение"
    table.cell(1, 0).text = "Выручка"
    table.cell(1, 1).text = "42"
    doc.save(src)

    result = file_to_markdown(src)
    assert result.format == "docx"
    assert "Отчёт" in result.markdown
    assert "42" in result.markdown
    assert "| Метрика | Значение |" in result.markdown
    assert "| Выручка | 42 |" in result.markdown


def test_pdf_missing_pypdfium2(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    src = tmp_path / "a.pdf"
    src.write_bytes(b"%PDF-1.4")

    def _boom(_path: Path) -> object:
        raise ImportError("No module named 'pypdfium2'")

    monkeypatch.setattr("case3.source_ingest.triage_pdf", _boom)
    with pytest.raises(IngestDependencyError, match="pypdfium2"):
        file_to_markdown(src)


def test_markdown_over_limit_rejected(tmp_path: Path) -> None:
    src = tmp_path / "big.txt"
    src.write_text("x" * 100, encoding="utf-8")
    with pytest.raises(UnsupportedSourceFormatError, match="2 MiB"):
        file_to_markdown(src, max_markdown_bytes=50)
