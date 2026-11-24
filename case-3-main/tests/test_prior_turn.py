"""One previous run is dialogue context. It is not a new Source of facts."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from case3.pipeline import carry_chat_prompt
from case3.prior_turn import (
    format_prior_turn,
    insert_prior_turn,
    prior_block_for_form,
)


def test_format_prior_turn_marks_context_and_clips() -> None:
    text = format_prior_turn(
        {
            "chat_prompt": "сделай короче",
            "chat_summary": "Итог: три пункта про выручку.",
        }
    )
    assert "не Source" in text
    assert "сделай короче" in text
    assert "три пункта" in text
    assert format_prior_turn({}) == ""
    long = format_prior_turn({"chat_prompt": "а" * 5000, "chat_summary": ""})
    assert len(long) < 2000


def test_insert_prior_turn_sits_between_ask_and_ui_rules() -> None:
    intent = "Сделай короче прошлый текст\n\nТребования UI:\n- режим отчёт"
    block = format_prior_turn(
        {"chat_prompt": "отчёт по выручке", "chat_summary": "Было три раздела."}
    )
    merged = insert_prior_turn(intent, block)
    assert merged.index("Сделай короче") < merged.index("Предыдущий ход")
    assert merged.index("Предыдущий ход") < merged.index("Требования UI:")
    assert insert_prior_turn(intent, "") == intent


def test_prior_block_reads_run_and_rejects_bad_id(tmp_path: Path) -> None:
    run_id = "source_20261110T120000Z"
    out = tmp_path / "runs" / "out" / run_id
    out.mkdir(parents=True)
    (out / "meta.json").write_text(
        json.dumps(
            {
                "chat_prompt": "первый запрос",
                "chat_summary": "Собрали отчёт.",
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    block = prior_block_for_form(run_id, root=tmp_path)
    assert "первый запрос" in block
    assert "Собрали отчёт" in block
    assert prior_block_for_form("missing_run_id", root=tmp_path) == ""
    assert prior_block_for_form("  ", root=tmp_path) == ""
    with pytest.raises(ValueError):
        prior_block_for_form("../secret", root=tmp_path)


def test_carry_chat_prompt_survives_pipeline_meta_rebuild() -> None:
    meta: dict = {"run_id": "r", "status": "running"}
    carry_chat_prompt(meta, {"chat_prompt": "  исходный вопрос  ", "intent": "ignored"})
    assert meta["chat_prompt"] == "исходный вопрос"
    carry_chat_prompt(meta, {"chat_prompt": "другой"})
    assert meta["chat_prompt"] == "исходный вопрос"
