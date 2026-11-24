"""Real PDF shares and a real PPTX after a foreign table cell is removed."""

from __future__ import annotations

import importlib.util
from pathlib import Path

from pptx import Presentation

from case3.dashboard_source import parse_dashboard
from case3.slides_ir import parse_deck_ir, scrub_invented_numbers
from case3.slides_pptx_native import build_native_pptx


def _write_grid_pdf(path: Path, rows: list[list[str]]) -> None:
    spec = importlib.util.spec_from_file_location(
        "dash_pdf_fixture",
        Path(__file__).with_name("test_dashboard_source.py"),
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module._write_grid_pdf(path, rows)


def test_a_real_pdf_shares_a_number_without_thousand_spaces(tmp_path: Path) -> None:
    pdf = tmp_path / "plain.pdf"
    _write_grid_pdf(
        pdf,
        [
            ["Region", "Sum"],
            ["Minsk", "105865"],
            ["Gomel", "40000"],
        ],
    )
    text = parse_dashboard(pdf=pdf).markdown
    derived = text.split("## Производные", 1)[1]
    assert "72,6%" in derived
    assert "27,4%" in derived
    assert "105865" in text


_DECK = {
    "version": 1,
    "palette": "atelier",
    "slides": [
        {"id": "s01", "layout": "title", "title": "Итоги", "kicker": "01"},
        {
            "id": "s02",
            "layout": "table_hero",
            "title": "Коды",
            "rows": [["Код", "Сумма"], ["07", "12"]],
        },
        {"id": "s03", "layout": "closing", "title": "Дальше", "bullets": ["ок"]},
    ],
}


def _pptx_text(path: Path) -> str:
    deck = Presentation(str(path))
    parts: list[str] = []
    for slide in deck.slides:
        for shape in slide.shapes:
            if shape.has_text_frame:
                parts.append(shape.text_frame.text)
            if shape.has_table:
                for row in shape.table.rows:
                    for cell in row.cells:
                        parts.append(cell.text)
    return "\n".join(parts)


def test_a_real_pptx_drops_an_index_shaped_cell(tmp_path: Path) -> None:
    healed = scrub_invented_numbers(_DECK, source="Касса 20.")
    deck = parse_deck_ir(healed, source="Касса 20.")
    dest = tmp_path / "deck.pptx"
    build_native_pptx(deck, dest)
    text = _pptx_text(dest)
    assert dest.stat().st_size > 1000
    assert "01" in text
    assert "07" not in text
    assert "12" not in text
