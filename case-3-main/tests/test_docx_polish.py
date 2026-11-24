"""D5/D8: post-pandoc DOCX table + chrome polish."""

from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("docx")

from docx import Document  # noqa: E402
from docx.enum.text import WD_ALIGN_PARAGRAPH  # noqa: E402

from case3.docx_polish import polish_docx  # noqa: E402


def _make_sample(path: Path) -> None:
    doc = Document()
    doc.add_heading("Отчёт", level=1)
    table = doc.add_table(rows=3, cols=2)
    table.rows[0].cells[0].text = "Метрика"
    table.rows[0].cells[1].text = "Значение"
    table.rows[1].cells[0].text = "A"
    table.rows[1].cells[1].text = "12"
    table.rows[2].cells[0].text = "B"
    table.rows[2].cells[1].text = "28.5"
    doc.save(str(path))


def test_polish_docx_bolds_header_and_right_aligns_numbers(tmp_path: Path) -> None:
    path = tmp_path / "sample.docx"
    _make_sample(path)
    polish_docx(path)
    doc = Document(str(path))
    header = doc.tables[0].rows[0]
    assert any(run.bold for cell in header.cells for p in cell.paragraphs for run in p.runs)
    num_cell = doc.tables[0].rows[1].cells[1]
    assert num_cell.paragraphs[0].alignment == WD_ALIGN_PARAGRAPH.RIGHT
    num_cell2 = doc.tables[0].rows[2].cells[1]
    assert num_cell2.paragraphs[0].alignment == WD_ALIGN_PARAGRAPH.RIGHT


def test_polish_docx_header_fill_and_booktabs_borders(tmp_path: Path) -> None:
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn

    path = tmp_path / "sample.docx"
    _make_sample(path)
    # Simulate pandoc/reference firstRow green (e.g. D6E3BC / D5DEC0)
    doc0 = Document(str(path))
    for cell in doc0.tables[0].rows[0].cells:
        tc_pr = cell._tc.get_or_add_tcPr()
        shd = OxmlElement("w:shd")
        shd.set(qn("w:val"), "clear")
        shd.set(qn("w:color"), "auto")
        shd.set(qn("w:fill"), "D6E3BC")
        tc_pr.append(shd)
    doc0.save(str(path))

    polish_docx(path)
    doc = Document(str(path))
    table = doc.tables[0]
    # Header: bold + bottom rule, white/no green fill (override Word table styles)
    header_xml = "".join(c._tc.xml for c in table.rows[0].cells)
    assert "D5DEC0" not in header_xml.upper()
    assert "D6E3BC" not in header_xml.upper()
    assert "E8EDD8" not in header_xml.upper()
    assert 'w:fill="FFFFFF"' in header_xml or 'w:fill="ffffff"' in header_xml
    # Grid: outer + insideH + insideV so Word shows column/row dividers
    tbl_xml = table._tbl.xml
    assert "tblBorders" in tbl_xml
    assert "insideV" in tbl_xml
    assert "insideH" in tbl_xml
    # Verticals must be real lines (not nil/none)
    assert 'w:insideV w:val="nil"' not in tbl_xml
    assert 'w:insideV w:val="none"' not in tbl_xml
    assert 'w:val="single"' in tbl_xml
    # Full-ish width
    assert 'w:type="pct"' in tbl_xml or "tblW" in tbl_xml


def test_polish_docx_is_idempotent(tmp_path: Path) -> None:
    path = tmp_path / "sample.docx"
    _make_sample(path)
    polish_docx(path)
    polish_docx(path)
    doc = Document(str(path))
    assert len(doc.tables) == 1
    assert doc.tables[0].rows[0].cells[0].text == "Метрика"
    header_xml = "".join(c._tc.xml for c in doc.tables[0].rows[0].cells)
    assert "D5DEC0" not in header_xml.upper()


def test_reference_docx_has_liber_margins_and_header() -> None:
    root = Path(__file__).resolve().parents[1]
    ref = root / "assets" / "docx" / "reference.docx"
    assert ref.is_file(), "run scripts/build_reference_docx.py"
    doc = Document(str(ref))
    sec = doc.sections[0]
    # ~2.2cm = 793700 EMUs; allow small float noise
    assert abs(sec.top_margin.cm - 2.2) < 0.15
    assert abs(sec.left_margin.cm - 2.2) < 0.15
    header_text = "\n".join(p.text for p in sec.header.paragraphs)
    # Header may be empty visually but must exist / not linked blindly
    assert sec.header is not None
    footer_xml = sec.footer._element.xml
    assert "PAGE" in footer_xml or "fldChar" in footer_xml or "w:instrText" in footer_xml


def _tiny_png(path: Path) -> None:
    import struct
    import zlib

    def chunk(tag: bytes, data: bytes) -> bytes:
        return (
            struct.pack(">I", len(data))
            + tag
            + data
            + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
        )

    ihdr = struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0)
    idat = zlib.compress(b"\x00\xff\x00\x00")
    path.write_bytes(
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", ihdr)
        + chunk(b"IDAT", idat)
        + chunk(b"IEND", b"")
    )


def test_polish_centers_picture_and_prefixes_ris_caption(tmp_path: Path) -> None:
    from docx.shared import Inches, Pt, RGBColor

    png = tmp_path / "px.png"
    _tiny_png(png)
    path = tmp_path / "media.docx"
    doc = Document()
    doc.add_paragraph("Intro")
    doc.add_picture(str(png), width=Inches(1.5))
    cap = doc.add_paragraph("Ночной склад в Бресте")
    # Simulate pandoc gray tiny caption
    for run in cap.runs:
        run.font.size = Pt(8)
        run.font.color.rgb = RGBColor(0x80, 0x80, 0x80)
    doc.add_paragraph("Длинный абзац прозы после подписи, который не должен стать Рис.")
    doc.save(str(path))

    polish_docx(path)
    out = Document(str(path))
    media_i = next(
        i
        for i, p in enumerate(out.paragraphs)
        if p._p.xpath('.//*[local-name()="drawing"]')
    )
    assert out.paragraphs[media_i].alignment == WD_ALIGN_PARAGRAPH.CENTER
    cap_p = out.paragraphs[media_i + 1]
    assert cap_p.alignment == WD_ALIGN_PARAGRAPH.CENTER
    assert cap_p.text.startswith("Рис. 1. ")
    assert "Ночной склад в Бресте" in cap_p.text
    assert any(
        (r.font.color.rgb == RGBColor(0x12, 0x12, 0x12))
        or (r.font.size and r.font.size.pt >= 10)
        for r in cap_p.runs
        if r.text
    )
    # Body unchanged
    assert not any(p.text.startswith("Рис.") and "Длинный" in p.text for p in out.paragraphs)


def test_polish_caption_idempotent_keeps_existing_ris_prefix(tmp_path: Path) -> None:
    from docx.shared import Inches

    png = tmp_path / "px.png"
    _tiny_png(png)
    path = tmp_path / "media2.docx"
    doc = Document()
    doc.add_picture(str(png), width=Inches(1.2))
    doc.add_paragraph("Рис. 1. Уже готовая подпись")
    doc.save(str(path))
    polish_docx(path)
    polish_docx(path)
    text = Document(str(path)).paragraphs[1].text
    assert text == "Рис. 1. Уже готовая подпись"
    assert text.count("Рис.") == 1


def test_polish_table_caption_before_table(tmp_path: Path) -> None:
    path = tmp_path / "tbl.docx"
    doc = Document()
    doc.add_paragraph("В таблице 1 приведены метрики за квартал.")
    doc.add_paragraph("Ключевые показатели Q3")
    table = doc.add_table(rows=2, cols=2)
    table.rows[0].cells[0].text = "Метрика"
    table.rows[0].cells[1].text = "Значение"
    table.rows[1].cells[0].text = "A"
    table.rows[1].cells[1].text = "12"
    doc.save(str(path))

    polish_docx(path)
    out = Document(str(path))
    texts = [p.text.strip() for p in out.paragraphs]
    assert "Таблица 1. Ключевые показатели Q3" in texts
    assert texts[0] == "В таблице 1 приведены метрики за квартал."


def test_polish_clamps_wide_drawing(tmp_path: Path) -> None:
    from docx.oxml.ns import qn
    from docx.shared import Inches

    png = tmp_path / "px.png"
    _tiny_png(png)
    path = tmp_path / "wide.docx"
    doc = Document()
    doc.add_picture(str(png), width=Inches(8.0))
    doc.add_paragraph("Подпись широкая")
    doc.save(str(path))

    polish_docx(path)
    out = Document(str(path))
    media = next(p for p in out.paragraphs if p._p.xpath('.//*[local-name()="drawing"]'))
    cxs = []
    for ext in media._p.xpath('.//*[local-name()="extent"]'):
        cxs.append(int(ext.get("cx") or ext.get(qn("wp:cx") or "cx") or 0))
    assert cxs, "expected wp:extent"
    # A4 text ~6.5in; clamp ≤ 0.92 of that
    assert max(cxs) <= 5_600_000
    assert out.paragraphs[1].text.startswith("Рис. 1.")


def test_polish_body_spacing_soft(tmp_path: Path) -> None:
    path = tmp_path / "space.docx"
    doc = Document()
    doc.add_paragraph("Первый абзац.")
    doc.add_paragraph("Второй абзац.")
    doc.save(str(path))
    polish_docx(path)
    out = Document(str(path))
    for p in out.paragraphs:
        if not (p.text or "").strip():
            continue
        assert p.paragraph_format.space_after is not None
        assert p.paragraph_format.space_after.pt >= 4


def test_polish_docx_forces_black_headings(tmp_path: Path) -> None:
    from docx.oxml.ns import qn
    from docx.shared import RGBColor

    path = tmp_path / "heads.docx"
    doc = Document()
    doc.styles["Heading 1"].font.color.rgb = RGBColor(0x36, 0x5F, 0x91)
    doc.add_heading("Раздел", level=1)
    doc.save(str(path))
    polish_docx(path)
    doc2 = Document(str(path))
    st = doc2.styles["Heading 1"]
    assert st.font.color.rgb == RGBColor(0x12, 0x12, 0x12)
    rPr = st.element.find(qn("w:rPr"))
    color = rPr.find(qn("w:color")) if rPr is not None else None
    assert color is not None
    assert color.get(qn("w:val"), "").upper() == "121212"


def test_a_wide_table_turns_the_word_page_sideways(tmp_path: Path) -> None:
    import zipfile

    from case3.docx_polish import orient_wide_tables

    path = tmp_path / "wide.docx"
    doc = Document()
    table = doc.add_table(rows=1, cols=6)
    for index, cell in enumerate(table.rows[0].cells):
        cell.text = f"c{index}"
    doc.save(str(path))
    assert orient_wide_tables(path) is True
    xml = zipfile.ZipFile(path).read("word/document.xml").decode("utf-8")
    assert "landscape" in xml
    assert "16838" in xml


def test_only_the_wide_table_turns_sideways(tmp_path: Path) -> None:
    from docx.enum.section import WD_ORIENT
    from docx.oxml.ns import qn

    from case3.docx_polish import orient_wide_tables

    path = tmp_path / "mixed.docx"
    doc = Document()
    doc.add_paragraph("До")
    doc.add_table(rows=1, cols=2)
    doc.add_paragraph("Между")
    doc.add_paragraph("Таблица 1. Показатели")
    wide = doc.add_table(rows=1, cols=6)
    for index, cell in enumerate(wide.rows[0].cells):
        cell.text = f"c{index}"
    doc.add_paragraph("После")
    doc.save(str(path))
    assert orient_wide_tables(path) is True
    out = Document(str(path))
    assert [sect.orientation for sect in out.sections] == [
        WD_ORIENT.PORTRAIT,
        WD_ORIENT.LANDSCAPE,
        WD_ORIENT.PORTRAIT,
    ]
    wide_sect = out.sections[1]
    assert wide_sect.page_width.twips == 16838
    assert wide_sect.page_height.twips == 11906
    chunks: list[list[str]] = [[]]
    for child in out.element.body:
        p_pr = child.find(qn("w:pPr")) if child.tag == qn("w:p") else None
        if p_pr is not None and p_pr.find(qn("w:sectPr")) is not None:
            chunks.append([])
            continue
        if child.tag == qn("w:sectPr"):
            continue
        chunks[-1].append("".join(node.text or "" for node in child.iter(qn("w:t"))))
    assert "До" in chunks[0] and "Между" in chunks[0]
    assert "Таблица 1. Показатели" in chunks[1]
    assert "c0" in "".join(chunks[1])
    assert chunks[2] == ["После"]


def test_a_narrow_table_stays_portrait(tmp_path: Path) -> None:
    import zipfile

    from case3.docx_polish import orient_wide_tables

    path = tmp_path / "narrow.docx"
    doc = Document()
    doc.add_table(rows=1, cols=2)
    doc.save(str(path))
    assert orient_wide_tables(path) is False
    xml = zipfile.ZipFile(path).read("word/document.xml").decode("utf-8")
    assert "landscape" not in xml
