"""Post-pandoc DOCX polish (D5 tables, light chrome). Soft-fail friendly."""

from __future__ import annotations

import logging
import re
from copy import deepcopy
from pathlib import Path

log = logging.getLogger("case3.docx_polish")

_NUM = re.compile(
    r"^[-+]?(?:\d{1,3}(?:[ \u00a0]\d{3})*|\d+)(?:[.,]\d+)?%?$"
)

# Header cells: white fill (override pandoc/reference firstRow greens).
_HEADER_FILL = "FFFFFF"
_RULE_COLOR = "3F5210"  # readable olive ink on white
_BODY_RULE = "C5CDB0"
_INK = "121212"


def _cell_text(cell) -> str:  # noqa: ANN001
    return (cell.text or "").strip()


def _is_numeric(text: str) -> bool:
    t = (text or "").strip().replace("\u00a0", " ")
    if not t:
        return False
    compact = t.replace(" ", "")
    return bool(_NUM.match(compact))


def _ensure_runs_bold(cell) -> None:  # noqa: ANN001
    for p in cell.paragraphs:
        if p.runs:
            for run in p.runs:
                run.bold = True
            continue
        text = p.text or ""
        if not text:
            continue
        run = p.add_run(text)
        run.bold = True


def _qn(tag: str):
    from docx.oxml.ns import qn

    return qn(tag)


def _set_cell_shading(cell, fill_hex: str) -> None:  # noqa: ANN001
    from docx.oxml import OxmlElement

    tc = cell._tc
    tc_pr = tc.get_or_add_tcPr()
    for child in list(tc_pr):
        if child.tag == _qn("w:shd"):
            tc_pr.remove(child)
    shd = OxmlElement("w:shd")
    shd.set(_qn("w:val"), "clear")
    shd.set(_qn("w:color"), "auto")
    shd.set(_qn("w:fill"), fill_hex.upper())
    tc_pr.append(shd)


def _set_cell_margins(cell, *, dxa: int = 80) -> None:  # noqa: ANN001
    """Comfortable cell padding (dxa = twentieths of a point)."""
    from docx.oxml import OxmlElement

    tc = cell._tc
    tc_pr = tc.get_or_add_tcPr()
    for child in list(tc_pr):
        if child.tag == _qn("w:tcMar"):
            tc_pr.remove(child)
    mar = OxmlElement("w:tcMar")
    for edge in ("top", "left", "bottom", "right"):
        node = OxmlElement(f"w:{edge}")
        node.set(_qn("w:w"), str(dxa))
        node.set(_qn("w:type"), "dxa")
        mar.append(node)
    tc_pr.append(mar)


def _border(tag: str, *, sz: int, color: str, val: str = "single") -> object:
    from docx.oxml import OxmlElement

    el = OxmlElement(f"w:{tag}")
    el.set(_qn("w:val"), val)
    el.set(_qn("w:sz"), str(sz))  # eighths of a point
    el.set(_qn("w:space"), "0")
    el.set(_qn("w:color"), color)
    return el


def _apply_booktabs_table(table) -> None:  # noqa: ANN001
    """Full width + Liber grid: outer frame + row/column dividers (Word-visible)."""
    from docx.oxml import OxmlElement

    tbl = table._tbl
    tbl_pr = tbl.tblPr
    if tbl_pr is None:
        tbl_pr = OxmlElement("w:tblPr")
        tbl.insert(0, tbl_pr)

    # Width ~100% of text
    for child in list(tbl_pr):
        if child.tag in {_qn("w:tblW"), _qn("w:tblBorders"), _qn("w:jc")}:
            tbl_pr.remove(child)
    tbl_w = OxmlElement("w:tblW")
    tbl_w.set(_qn("w:type"), "pct")
    tbl_w.set(_qn("w:w"), "5000")  # 5000 = 100%
    tbl_pr.append(tbl_w)
    jc = OxmlElement("w:jc")
    jc.set(_qn("w:val"), "center")
    tbl_pr.append(jc)

    borders = OxmlElement("w:tblBorders")
    # Outer frame + insideH/V so columns and rows read as a grid in Word.
    borders.append(_border("top", sz=12, color=_RULE_COLOR))
    borders.append(_border("left", sz=8, color=_BODY_RULE))
    borders.append(_border("bottom", sz=12, color=_RULE_COLOR))
    borders.append(_border("right", sz=8, color=_BODY_RULE))
    borders.append(_border("insideH", sz=6, color=_BODY_RULE))
    borders.append(_border("insideV", sz=6, color=_BODY_RULE))
    tbl_pr.append(borders)


def _style_header_row(row) -> None:  # noqa: ANN001
    for cell in row.cells:
        _ensure_runs_bold(cell)
        # Force white — Word table styles (reference.docx) tint firstRow green.
        _set_cell_shading(cell, _HEADER_FILL)
        _set_cell_margins(cell, dxa=90)
        # Slight bottom emphasis via cell bottom border
        from docx.oxml import OxmlElement

        tc_pr = cell._tc.get_or_add_tcPr()
        for child in list(tc_pr):
            if child.tag == _qn("w:tcBorders"):
                tc_pr.remove(child)
        tc_borders = OxmlElement("w:tcBorders")
        tc_borders.append(_border("bottom", sz=12, color=_RULE_COLOR))
        tc_pr.append(tc_borders)



def _force_black_headings(doc) -> None:  # noqa: ANN001
    """Title / Heading styles → black ink (reference.docx used theme blue)."""
    from docx.oxml import OxmlElement
    from docx.shared import RGBColor

    ink = RGBColor(0x12, 0x12, 0x12)
    for name in ("Title", "Heading 1", "Heading 2", "Heading 3"):
        try:
            st = doc.styles[name]
        except KeyError:
            continue
        st.font.color.rgb = ink
        rpr = st.element.get_or_add_rPr()
        for child in list(rpr):
            if child.tag == _qn("w:color"):
                rpr.remove(child)
        color = OxmlElement("w:color")
        color.set(_qn("w:val"), _INK)
        rpr.append(color)
    # Also pin runs on heading paragraphs (pandoc may set theme color on runs).
    for p in doc.paragraphs:
        style_name = (p.style.name if p.style else "") or ""
        if style_name not in {"Title", "Heading 1", "Heading 2", "Heading 3"}:
            continue
        for run in p.runs:
            run.font.color.rgb = ink


_CAPTION_ALREADY = re.compile(
    r"^(?:Рис\.|Рисунок|Fig\.|Figure)\s*\d*",
    re.IGNORECASE,
)
_TABLE_CAPTION_ALREADY = re.compile(
    r"^(?:Таблица|Table)\s*\d*",
    re.IGNORECASE,
)
# Body lead-ins that sit above the real caption — do not promote to Таблица N.
_TABLE_BODY_LEADIN = re.compile(
    r"^(?:В\s+таблице|See\s+table|Table\s+\d+\s+shows)\b",
    re.IGNORECASE,
)
_MAX_CAPTION_CHARS = 300
# A4 text width ≈ 6.54in with 2.2cm margins; keep drawings ≤ 0.92 of that.
_EMU_PER_INCH = 914400
_MAX_DRAWING_CX = int(6.54 * 0.92 * _EMU_PER_INCH)  # ≈ 5.50e6
# Maximum drawing height in DOCX so tall diagrams don't overflow the page.
_MAX_DRAWING_CY = int(4.6 * _EMU_PER_INCH)  # ≈ 4.20e6


def _para_has_media(para) -> bool:  # noqa: ANN001
    """True if paragraph holds a drawing, VML pict, or chart graphic."""
    return bool(
        para._p.xpath(
            './/*[local-name()="drawing" or local-name()="pict" or local-name()="chart"]'
        )
    )


def _style_caption_runs(para) -> None:  # noqa: ANN001
    from docx.shared import Pt, RGBColor

    ink = RGBColor(0x12, 0x12, 0x12)
    for run in para.runs:
        if not (run.text or "").strip() and not run.text:
            continue
        run.font.color.rgb = ink
        run.font.size = Pt(11)
        run.font.italic = False


def _rewrite_caption_text(para, text: str) -> None:  # noqa: ANN001
    """Replace paragraph text with a single styled run (drop gray/tiny pandoc runs)."""
    from docx.shared import Pt, RGBColor

    # Clear existing runs' text first (keeps paragraph properties).
    for run in list(para.runs):
        run.text = ""
    if para.runs:
        run = para.runs[0]
        run.text = text
    else:
        run = para.add_run(text)
    run.font.color.rgb = RGBColor(0x12, 0x12, 0x12)
    run.font.size = Pt(11)
    run.font.italic = False
    run.bold = False


def polish_media_captions(doc) -> int:  # noqa: ANN001
    """Center media paras; next short caption → ``Рис. N. …`` centered Liber ink.

    Returns how many captions were numbered/rewritten (0 if none).
    """
    from docx.enum.text import WD_ALIGN_PARAGRAPH

    paras = list(doc.paragraphs)
    fig_n = 0
    touched = 0
    i = 0
    while i < len(paras):
        p = paras[i]
        if not _para_has_media(p):
            i += 1
            continue
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        j = i + 1
        while j < len(paras) and not (paras[j].text or "").strip():
            j += 1
        if j >= len(paras):
            i += 1
            continue
        cap = paras[j]
        style_name = (cap.style.name if cap.style else "") or ""
        if style_name.startswith("Heading") or _para_has_media(cap):
            i += 1
            continue
        raw = (cap.text or "").strip()
        if not raw or len(raw) > _MAX_CAPTION_CHARS:
            i += 1
            continue
        fig_n += 1
        cap.alignment = WD_ALIGN_PARAGRAPH.CENTER
        if _CAPTION_ALREADY.match(raw):
            _style_caption_runs(cap)
        else:
            _rewrite_caption_text(cap, f"Рис. {fig_n}. {raw}")
            touched += 1
        i = j + 1
    return touched


def _iter_body_blocks(doc):  # noqa: ANN001
    """Yield ``('p', Paragraph)`` / ``('t', Table)`` in document order."""
    from docx.oxml.ns import qn
    from docx.table import Table
    from docx.text.paragraph import Paragraph

    for child in doc.element.body.iterchildren():
        if child.tag == qn("w:p"):
            yield "p", Paragraph(child, doc)
        elif child.tag == qn("w:tbl"):
            yield "t", Table(child, doc)


def polish_table_captions(doc) -> int:  # noqa: ANN001
    """Pandoc puts table title *before* the table — prefix ``Таблица N.``."""
    from docx.enum.text import WD_ALIGN_PARAGRAPH

    blocks = list(_iter_body_blocks(doc))
    table_n = 0
    touched = 0
    for i, (kind, obj) in enumerate(blocks):
        if kind != "t":
            continue
        # Walk back to previous non-empty paragraph.
        j = i - 1
        while j >= 0:
            k, prev = blocks[j]
            if k == "t":
                break
            if (prev.text or "").strip():
                break
            j -= 1
        else:
            continue
        if j < 0 or blocks[j][0] != "p":
            continue
        cap = blocks[j][1]
        style_name = (cap.style.name if cap.style else "") or ""
        if style_name.startswith("Heading") or _para_has_media(cap):
            continue
        raw = (cap.text or "").strip()
        if not raw or len(raw) > _MAX_CAPTION_CHARS:
            continue
        if _TABLE_BODY_LEADIN.match(raw):
            continue
        if _CAPTION_ALREADY.match(raw):
            # Figure caption accidentally adjacent — leave alone.
            continue
        table_n += 1
        cap.alignment = WD_ALIGN_PARAGRAPH.CENTER
        if _TABLE_CAPTION_ALREADY.match(raw):
            _style_caption_runs(cap)
        else:
            _rewrite_caption_text(cap, f"Таблица {table_n}. {raw}")
            touched += 1
    return touched


def clamp_drawing_widths(
    doc, *, max_cx: int = _MAX_DRAWING_CX, max_cy: int = _MAX_DRAWING_CY
) -> int:  # noqa: ANN001
    """Scale down oversized ``wp:extent`` / ``a:ext`` so media fits the text block (width & height)."""
    clamped = 0
    for para in doc.paragraphs:
        if not _para_has_media(para):
            continue
        for ext in para._p.xpath('.//*[local-name()="extent" or local-name()="ext"]'):
            cx_raw = ext.get("cx")
            cy_raw = ext.get("cy")
            if cx_raw is None:
                continue
            try:
                cx = int(cx_raw)
                cy = int(cy_raw) if cy_raw is not None else 0
            except ValueError:
                continue
            if cx <= 0:
                continue
            scale_x = max_cx / float(cx) if cx > max_cx else 1.0
            scale_y = max_cy / float(cy) if (cy > 0 and cy > max_cy) else 1.0
            scale = min(scale_x, scale_y)
            if scale >= 1.0:
                continue
            new_cx = max(1, int(round(cx * scale)))
            new_cy = max(1, int(round(cy * scale))) if cy else cy
            ext.set("cx", str(new_cx))
            if cy_raw is not None:
                ext.set("cy", str(new_cy))
            clamped += 1
    return clamped


def polish_paragraph_rhythm(doc) -> None:  # noqa: ANN001
    """Light body spacing so pandoc dumps don't look glued or sparse."""
    from docx.shared import Pt

    for para in doc.paragraphs:
        style_name = (para.style.name if para.style else "") or ""
        if style_name.startswith("Heading") or style_name == "Title":
            continue
        if _para_has_media(para):
            pf = para.paragraph_format
            pf.space_before = Pt(10)
            pf.space_after = Pt(4)
            continue
        text = (para.text or "").strip()
        pf = para.paragraph_format
        if text.startswith(("Рис.", "Таблица ", "Figure ", "Table ")):
            pf.space_before = Pt(2)
            pf.space_after = Pt(10)
            continue
        if not text:
            continue
        pf.space_before = Pt(0)
        pf.space_after = Pt(8)
        if pf.line_spacing is None:
            pf.line_spacing = 1.15


def polish_docx(path: Path | str) -> Path:
    """Liber tables + centered media + ``Рис./Таблица N.`` + width clamp + rhythm."""
    try:
        from docx import Document
        from docx.enum.text import WD_ALIGN_PARAGRAPH
    except ImportError as exc:
        raise RuntimeError("python-docx required for DOCX polish") from exc

    path = Path(path)
    doc = Document(str(path))
    _force_black_headings(doc)
    for table in doc.tables:
        if not table.rows:
            continue
        _apply_booktabs_table(table)
        _style_header_row(table.rows[0])
        for row in table.rows[1:]:
            for cell in row.cells:
                _set_cell_margins(cell, dxa=80)
                if not _is_numeric(_cell_text(cell)):
                    continue
                for p in cell.paragraphs:
                    p.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    n_fig = polish_media_captions(doc)
    n_tbl = polish_table_captions(doc)
    n_clamp = clamp_drawing_widths(doc)
    polish_paragraph_rhythm(doc)
    doc.save(str(path))
    log.info(
        "polished DOCX (fig_caps=%d tbl_caps=%d clamps=%d) → %s",
        n_fig,
        n_tbl,
        n_clamp,
        path,
    )
    return path


def _page_size(sect, *, landscape: bool) -> None:  # noqa: ANN001
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn

    page = sect.find(qn("w:pgSz"))
    if page is None:
        page = OxmlElement("w:pgSz")
        sect.append(page)
    if landscape:
        page.set(qn("w:w"), "16838")
        page.set(qn("w:h"), "11906")
        page.set(qn("w:orient"), "landscape")
        return
    if page.get(qn("w:orient")) == "landscape":
        page.set(qn("w:w"), "11906")
        page.set(qn("w:h"), "16838")
    if qn("w:orient") in page.attrib:
        del page.attrib[qn("w:orient")]


def _section_break(template, *, landscape: bool):  # noqa: ANN001
    """A paragraph that ends the current section on a new page."""
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn

    paragraph = OxmlElement("w:p")
    props = OxmlElement("w:pPr")
    sect = deepcopy(template)
    _page_size(sect, landscape=landscape)
    kind = sect.find(qn("w:type"))
    if kind is None:
        kind = OxmlElement("w:type")
        sect.insert(0, kind)
    kind.set(qn("w:val"), "nextPage")
    props.append(sect)
    paragraph.append(props)
    return paragraph


def _is_table_caption(element) -> bool:  # noqa: ANN001
    from docx.oxml.ns import qn

    if element.tag != qn("w:p"):
        return False
    props = element.find(qn("w:pPr"))
    if props is not None and props.find(qn("w:sectPr")) is not None:
        return False
    text = "".join(node.text or "" for node in element.iter(qn("w:t"))).strip()
    return bool(_TABLE_CAPTION_ALREADY.match(text))


def _wide_clusters(blocks: list, wide_ids: set[int]) -> list[tuple[int, int]]:
    clusters: list[tuple[int, int]] = []
    index = 0
    while index < len(blocks):
        if id(blocks[index]) not in wide_ids:
            index += 1
            continue
        start = index
        if start > 0 and _is_table_caption(blocks[start - 1]):
            start -= 1
        end = index
        while end + 1 < len(blocks) and id(blocks[end + 1]) in wide_ids:
            end += 1
        clusters.append((start, end))
        index = end + 1
    return clusters


def orient_wide_tables(path: Path | str) -> bool:
    """Turn only the wide table's page sideways.

    Pandoc drops the LaTeX landscape environment. A table of six or more
    columns gets its own landscape page. Text before and after stays portrait.
    The caption «Таблица N» stays on that landscape page. Returns True when a
    page was turned.
    """
    from docx import Document
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn

    doc = Document(str(path))
    wide = [table for table in doc.tables if table.rows and len(table.rows[0].cells) >= 6]
    if not wide:
        return False
    for table in wide:
        tbl_pr = table._tbl.tblPr
        if tbl_pr is None:
            continue
        width = tbl_pr.find(qn("w:tblW"))
        if width is None:
            width = OxmlElement("w:tblW")
            tbl_pr.append(width)
        width.set(qn("w:w"), "14400")
        width.set(qn("w:type"), "dxa")

    body = doc.element.body
    sect_tag = qn("w:sectPr")
    final = next((child for child in body if child.tag == sect_tag), None)
    if final is None:
        final = OxmlElement("w:sectPr")
        body.append(final)
    portrait = deepcopy(final)
    blocks = [child for child in list(body) if child.tag != sect_tag]
    clusters = _wide_clusters(blocks, {id(table._tbl) for table in wide})
    for start, end in reversed(clusters):
        first, last = blocks[start], blocks[end]
        if end < len(blocks) - 1:
            last.addnext(_section_break(portrait, landscape=True))
        else:
            _page_size(final, landscape=True)
        if start > 0:
            first.addprevious(_section_break(portrait, landscape=False))
    doc.save(str(path))
    return True


def try_polish_docx(path: Path | str) -> bool:
    """Best-effort polish; never raise into render."""
    try:
        polish_docx(path)
        return True
    except Exception as exc:  # noqa: BLE001 — soft-fail
        log.warning("docx polish skipped: %s", exc)
        return False
