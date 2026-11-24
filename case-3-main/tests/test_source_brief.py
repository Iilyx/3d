"""Long technical Source becomes a brief; code listings become one callout."""

from __future__ import annotations

from case3.source_brief import code_highlights, ensure_code_callouts, slides_source_text


def test_code_fence_keeps_the_signature_not_the_body() -> None:
    source = (
        "Сервис считает брак.\n\n"
        "```python\n"
        "def defect_rate(bad, total):\n"
        "    if total == 0:\n"
        "        return 0\n"
        "    return bad / total\n"
        "```\n"
    )
    highs = code_highlights(source)
    assert len(highs) == 1
    assert highs[0]["name"] == "defect_rate"
    assert highs[0]["line"].startswith("def defect_rate")
    assert "return 0" not in highs[0]["line"]


def test_long_tech_doc_becomes_a_short_map_that_keeps_facts() -> None:
    section = (
        "## Смена 2\n"
        "Брак на линии B составил 3.4% при плане 1.1%. "
        + ("Дальше идёт пояснение процесса без новых чисел. " * 80)
        + "\n\n"
    )
    source = section * 6 + (
        "```python\n"
        "def defect_rate(bad, total):\n"
        "    return bad / total\n"
        "```\n"
    )
    assert len(source) > 8000
    brief = slides_source_text(source)
    assert len(brief) < 14000
    assert "3.4%" in brief
    assert "1.1%" in brief
    assert "Смена 2" in brief
    assert "def defect_rate" in brief
    assert "return bad / total" not in brief
    assert str(len(source)) in brief


def test_long_region_table_keeps_rows_not_a_240_char_slice() -> None:
    rows = ["| Область | Сумма |", "| --- | --- |"]
    for name in (
        "Брестская",
        "Витебская",
        "Гомельская",
        "Гродненская",
        "Минская",
        "Могилевская",
    ):
        rows.append(
            f"| {name} область | платежи по налогу на добавленную стоимость за период | 100 |"
        )
    filler = "Пояснение без чисел. " * 500
    source = filler + "\n\n## Таблица\n" + "\n".join(rows) + "\n"
    assert len(source) > 8000
    brief = slides_source_text(source)
    assert "Гомельская" in brief
    assert "Могилевская" in brief
    assert "| Область | Сумма |" in brief or "Область" in brief


def test_one_section_keeps_every_numbered_sentence() -> None:
    filler = "Пояснение без чисел. " * 400
    source = (
        "## Каналы\n"
        "Сайт принёс 6,2. Партнёры принесли 4,1. Звонки закрыли 8,1. "
        + filler
    )
    assert len(source) > 8000
    brief = slides_source_text(source)
    assert "6,2" in brief
    assert "4,1" in brief
    assert "8,1" in brief


def test_code_callout_is_inserted_once() -> None:
    deck = {
        "slides": [
            {"id": "s01", "layout": "title", "title": "Итоги"},
            {"id": "s02", "layout": "bullets", "title": "Факты", "bullets": ["Брак 3.4%"]},
            {"id": "s03", "layout": "closing", "title": "Дальше", "bullets": ["ok"]},
        ]
    }
    highs = [{"name": "defect_rate", "line": "def defect_rate(bad, total):"}]
    placed = ensure_code_callouts(deck, highs)
    assert placed == ["defect_rate"]
    slide = next(s for s in deck["slides"] if s.get("term") == "defect_rate")
    assert slide["layout"] == "callout"
    assert "def defect_rate" in slide["definition"]
    assert deck["slides"][-1]["layout"] == "closing"
    assert ensure_code_callouts(deck, highs) == []


def test_slides_source_text_keeps_derivatives_beyond_eight_lines() -> None:
    filler = "Пояснение без чисел. " * 400
    deriv_lines = [f"- Регион {i} — доля {i}%, место {i}" for i in range(1, 20)]
    source = (
        filler
        + "\n\n## Производные\n\n"
        + "\n".join(deriv_lines)
        + "\nСумма по строкам: 1000\n"
    )
    brief = slides_source_text(source)
    assert "Регион 15" in brief
    assert "Сумма по строкам: 1000" in brief

