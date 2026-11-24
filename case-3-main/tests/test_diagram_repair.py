"""Diagram repair pass (output_mode=diagram) — enrich Mermaid from Source."""

from __future__ import annotations

import json
from typing import Any

import pytest

from case3.diagram_repair import (
    looks_like_linear_slop,
    parse_repair_response,
    repair_diagrams,
)


def test_looks_like_linear_slop_detects_generic_stages() -> None:
    src = (
        "flowchart LR\n"
        "  A[Начало] --> B[Этап 1]\n"
        "  B --> C[Этап 2]\n"
        "  C --> D[Этап 3]\n"
        "  D --> E[Завершение]"
    )
    assert looks_like_linear_slop(src) is True


def test_looks_like_linear_slop_false_for_branching() -> None:
    src = (
        "flowchart TD\n"
        "  A[Заявка] --> B{Проверка ОК}\n"
        "  B -->|да| C[Договор]\n"
        "  B -->|нет| A"
    )
    assert looks_like_linear_slop(src) is False


def test_parse_repair_response_accepts_json_fence() -> None:
    raw = """```json
{
  "diagrams": [
    {
      "id": "dia_01",
      "title": "Онбординг",
      "type": "flowchart",
      "mermaid": "flowchart TD\\n  A[Заявка] --> B{ОК?}\\n  B -->|да| C[Готово]"
    }
  ]
}
```"""
    items = parse_repair_response(raw, max_diagrams=2)
    assert len(items) == 1
    assert items[0]["id"] == "dia_01"
    assert "{" in items[0]["mermaid"]


def test_parse_repair_response_accepts_array_and_single_object() -> None:
    # 1. Bare JSON array
    raw_array = json.dumps([
        {
            "id": "dia_01",
            "title": "Онбординг",
            "type": "flowchart",
            "mermaid": "flowchart TD\n  A[Заявка] --> B[Готово]",
        }
    ])
    items = parse_repair_response(raw_array, max_diagrams=2)
    assert len(items) == 1
    assert items[0]["id"] == "dia_01"

    # 2. Single diagram object
    raw_single = json.dumps({
        "id": "dia_02",
        "title": "Схема",
        "type": "flowchart",
        "mermaid": "flowchart LR\n  X --> Y",
    })
    items2 = parse_repair_response(raw_single, max_diagrams=2)
    assert len(items2) == 1
    assert items2[0]["id"] == "dia_02"



def test_repair_soft_fails_to_draft_on_empty_llm() -> None:
    draft = [
        {
            "id": "dia_01",
            "title": "Процесс",
            "type": "flowchart",
            "mermaid": "flowchart LR\n  A[Начало] --> B[Конец]",
        }
    ]

    class Boom:
        def complete(self, *, system: str, user_text: str, reasoning: str | None = None) -> str:
            return ""

    out, meta = repair_diagrams(
        draft,
        source="Клиент подаёт заявку. Если ОК ок — договор, иначе отказ.",
        intent="режим схема",
        max_diagrams=2,
        client=Boom(),  # type: ignore[arg-type]
    )
    assert out == draft
    assert meta["diagrams_repaired"] is False


def test_repair_replaces_with_enriched_when_ok() -> None:
    draft = [
        {
            "id": "dia_01",
            "title": "Универсальная схема процесса",
            "type": "flowchart",
            "mermaid": (
                "flowchart LR\n"
                "  A[Начало] --> B[Этап 1]\n"
                "  B --> C[Этап 2]\n"
                "  C --> D[Завершение]"
            ),
        }
    ]
    enriched_mermaid = (
        "flowchart TD\n"
        "  A[Заявка клиента] --> B{КИН ок?}\n"
        "  B -->|да| C[Договор]\n"
        "  B -->|нет| D[Отказ]"
    )
    payload = {
        "diagrams": [
            {
                "id": "dia_01",
                "title": "Согласование заявки",
                "type": "flowchart",
                "mermaid": enriched_mermaid,
            }
        ]
    }

    class Ok:
        def complete(self, *, system: str, user_text: str, reasoning: str | None = None) -> str:
            assert "Заявка" in user_text or "КИН" in user_text or "клиент" in user_text.lower()
            assert "diagrams" in system.lower() or "mermaid" in system.lower()
            return "```json\n" + json.dumps(payload, ensure_ascii=False) + "\n```"

    out, meta = repair_diagrams(
        draft,
        source="Клиент подаёт заявку. Если КИН ок — договор, иначе отказ.",
        intent="режим схема",
        max_diagrams=2,
        client=Ok(),  # type: ignore[arg-type]
    )
    assert meta["diagrams_repaired"] is True
    assert len(out) == 1
    assert out[0]["title"] == "Согласование заявки"
    assert "КИН" in out[0]["mermaid"] or "ок" in out[0]["mermaid"].lower()
    assert looks_like_linear_slop(out[0]["mermaid"]) is False


def test_repair_skips_when_no_drafts() -> None:
    class Never:
        def complete(self, *, system: str, user_text: str, reasoning: str | None = None) -> str:
            raise AssertionError("should not call LLM")

    out, meta = repair_diagrams(
        [],
        source="x",
        intent="y",
        max_diagrams=2,
        client=Never(),  # type: ignore[arg-type]
    )
    assert out == []
    assert meta["diagrams_repaired"] is False
