"""Native OOXML tables for Liber deck PPTX."""

from __future__ import annotations

from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.util import Inches

from case3.slides_pptx_tables import add_native_table, table_block_inches


def test_dark_table_body_fill_is_not_white() -> None:
    """Botanical/dark packs: body cells must not hardcode #FFFFFF (invisible ink)."""
    prs = Presentation()
    prs.slide_width = Inches(13.333)
    prs.slide_height = Inches(7.5)
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    body_fill = RGBColor(0x24, 0x3D, 0x32)
    ok = add_native_table(
        slide,
        [
            ["Channel", "Job"],
            ["Creator seeding", "Show the evening ritual"],
        ],
        left=Inches(0.7),
        top=Inches(1.7),
        width=Inches(11.9),
        height=Inches(4.6),
        header_fill=RGBColor(0x19, 0x2D, 0x25),
        header_ink=RGBColor(0xF0, 0xEA, 0xDD),
        body_ink=RGBColor(0xF0, 0xEA, 0xDD),
        body_fill=body_fill,
        grid=RGBColor(0x2A, 0x40, 0x36),
    )
    assert ok
    table = next(s.table for s in slide.shapes if s.has_table)
    cell = table.cell(1, 0)
    fill = cell.fill
    # solid fill → fore_color must match body_fill, not white
    assert fill.fore_color.rgb == body_fill


def test_short_table_is_shorter_than_a_long_one() -> None:
    assert table_block_inches(4) < table_block_inches(12)
    assert table_block_inches(12) <= 4.7
