"""DOCX package gate used after polish/lists/native mutations."""

from __future__ import annotations

import zipfile
from pathlib import Path

from case3.docx_validate import docx_charts_word_safe, docx_package_ok


def test_docx_package_ok_on_reference() -> None:
    ref = Path(__file__).resolve().parents[1] / "assets" / "docx" / "reference.docx"
    assert ref.is_file()
    assert docx_package_ok(ref) is True


def test_docx_package_rejects_garbage(tmp_path: Path) -> None:
    p = tmp_path / "bad.docx"
    p.write_text("not a zip", encoding="utf-8")
    assert docx_package_ok(p) is False


def test_docx_charts_word_safe_rejects_external_data(tmp_path: Path) -> None:
    p = tmp_path / "embed.docx"
    with zipfile.ZipFile(p, "w") as zf:
        zf.writestr(
            "[Content_Types].xml",
            '<?xml version="1.0"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"></Types>',
        )
        zf.writestr("word/document.xml", "<w:document/>")
        zf.writestr(
            "word/charts/chart1.xml",
            '<c:chartSpace><c:externalData r:id="rId1"/><c:ser><c:val><c:numCache/></c:val></c:ser></c:chartSpace>',
        )
        zf.writestr("word/embeddings/Microsoft_Excel_Worksheet.xlsx", b"PK\x03\x04fake")
    assert docx_charts_word_safe(p) is False
