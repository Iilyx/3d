from __future__ import annotations

import json
import pytest

from case3.input_validation import InsufficientDataError
from case3.parse_output import parse_model_output
from case3.diagram_repair import parse_repair_response
from case3.slides_job import _extract_json_object
from case3.slides_ir import parse_deck_ir


def test_parse_model_output_insufficient_data():
    raw = (
        "```json\n"
        "{\n"
        '  "status": "insufficient_data",\n'
        '  "message": "Недостаточно конкретных фактов для отчёта."\n'
        "}\n"
        "```"
    )
    with pytest.raises(InsufficientDataError) as exc_info:
        parse_model_output(raw, max_images=2, max_charts=2)

    assert "Недостаточно конкретных фактов для отчёта" in exc_info.value.message


def test_parse_repair_response_insufficient_data():
    raw = (
        "```json\n"
        "{\n"
        '  "status": "insufficient_data",\n'
        '  "message": "В запросе нет описания процессов для схемы."\n'
        "}\n"
        "```"
    )
    with pytest.raises(InsufficientDataError) as exc_info:
        parse_repair_response(raw, max_diagrams=2)

    assert "В запросе нет описания процессов" in exc_info.value.message


def test_deck_ir_insufficient_data():
    raw = (
        "```json\n"
        "{\n"
        '  "status": "insufficient_data",\n'
        '  "message": "Недостаточно данных для презентации."\n'
        "}\n"
        "```"
    )
    data = _extract_json_object(raw)
    assert data.get("status") == "insufficient_data"
    with pytest.raises(InsufficientDataError) as exc_info:
        parse_deck_ir(data, source="")
    assert "Недостаточно данных для презентации" in exc_info.value.message
