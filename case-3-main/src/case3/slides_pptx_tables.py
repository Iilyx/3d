"""Native OOXML tables for Liber deck PPTX."""

from __future__ import annotations

from typing import Any

from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN
from pptx.util import Inches, Pt

_STATUS_RGB = {
    "масштаб": RGBColor(0x1F, 0x4D, 0x12),
    "scale": RGBColor(0x1F, 0x4D, 0x12),
    "пауза": RGBColor(0x7A, 0x2E, 0x16),
    "pause": RGBColor(0x7A, 0x2E, 0x16),
    "держать": RGBColor(0x3D, 0x44, 0x50),
    "hold": RGBColor(0x3D, 0x44, 0x50),
}


def table_block_inches(n_rows: int) -> float:
    """Row height follows the row count so five lines do not stretch into empty slabs."""
    body = max(1, n_rows - 1)
    if body <= 5:
        each = 0.68
    elif body <= 8:
        each = 0.46
    else:
        each = 0.32
    return min(4.7, 0.48 + each * body)


def add_native_table(
    slide,
    rows: list[list[str]],
    *,
    left,
    top,
    width,
    height,
    header_fill: RGBColor,
    header_ink: RGBColor,
    body_ink: RGBColor,
    grid: RGBColor,
    body_fill: RGBColor | None = None,
    font_name: str = "Calibri",
    font_pt: int = 14,
) -> bool:
    if not rows or len(rows) < 2:
        return False
    n_rows = len(rows)
    n_cols = len(rows[0])
    try:
        table_shape = slide.shapes.add_table(n_rows, n_cols, left, top, width, height)
    except Exception:
        return False
    # Light decks keep white body; dark packs pass panel/paper via body_fill.
    row_fill = body_fill if body_fill is not None else RGBColor(0xFF, 0xFF, 0xFF)
    table = table_shape.table
    for r, row in enumerate(rows):
        for c, cell_text in enumerate(row):
            cell = table.cell(r, c)
            cell.text = str(cell_text or "")
            for p in cell.text_frame.paragraphs:
                p.alignment = PP_ALIGN.LEFT if c == 0 else PP_ALIGN.RIGHT
                for run in p.runs:
                    run.font.size = Pt(max(11, font_pt - 2) if r == 0 else font_pt)
                    run.font.bold = r == 0
                    run.font.name = font_name
                    ink = header_ink if r == 0 else body_ink
                    status = _STATUS_RGB.get(str(cell_text or "").strip().casefold())
                    if status is not None and r:
                        ink = status
                        run.font.bold = True
                    run.font.color.rgb = ink
            fill = cell.fill
            fill.solid()
            if r == 0:
                fill.fore_color.rgb = header_fill
            else:
                fill.fore_color.rgb = row_fill
    return True
