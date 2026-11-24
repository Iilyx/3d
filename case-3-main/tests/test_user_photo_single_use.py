"""Tests ensuring user-uploaded photos are used at most once in reports,
and can be used and placed on slides in presentations.
"""

from __future__ import annotations

from typing import Any
import pytest

from case3.inject import inject_media
from case3.parse_output import parse_model_output
from case3.user_photos import deduplicate_slots_in_tex, ensure_user_slots_in_tex
from case3.slides_patch import apply_deck_text_patch, apply_deck_structure
from case3.slides_ir import parse_deck_ir


def test_inject_media_deduplicates_repeated_user_slots() -> None:
    tex = (
        r"\begin{document}" "\n"
        r"Раздел 1" "\n"
        r"%CASE3_FIG:usr_01%" "\n"
        r"Раздел 2" "\n"
        r"%CASE3_FIG:usr_01%" "\n"
        r"\end{document}"
    )
    figures = [{"id": "usr_01", "caption": "Моё фото"}]
    status = {"usr_01": {"ok": True}}
    out = inject_media(tex, figures, [], status)

    assert out.count("usr_01.png") == 1
    assert out.count(r"\begin{figure}") == 1


def test_inject_media_deduplicates_existing_includegraphics() -> None:
    tex = (
        r"\begin{document}" "\n"
        r"Раздел 1" "\n"
        r"\includegraphics[width=0.8\linewidth]{figures/usr_01.png}" "\n"
        r"Раздел 2" "\n"
        r"%CASE3_FIG:usr_01%" "\n"
        r"\end{document}"
    )
    figures = [{"id": "usr_01", "caption": "Моё фото"}]
    status = {"usr_01": {"ok": True}}
    out = inject_media(tex, figures, [], status)

    assert out.count("usr_01.png") == 1


def test_deduplicate_slots_in_tex() -> None:
    tex = (
        r"Начало" "\n"
        r"%CASE3_FIG:usr_01%" "\n"
        r"Середина" "\n"
        r"%CASE3_FIG:usr_01%" "\n"
        r"%CASE3_CHART:cht_01%" "\n"
        r"%CASE3_CHART:cht_01%" "\n"
        r"Конец"
    )
    clean = deduplicate_slots_in_tex(tex)
    assert clean.count("%CASE3_FIG:usr_01%") == 1
    assert clean.count("%CASE3_CHART:cht_01%") == 1


def test_parse_output_does_not_duplicate_slotted_user_photo() -> None:
    raw = (
        "```latex\n"
        "\\begin{document}\n"
        "\\section{Раздел 1}\n"
        "Вот фото интерфейса:\n"
        "%CASE3_FIG:usr_01%\n"
        "\\end{document}\n"
        "```\n"
        "```json\n"
        '{"figures": [{"id": "usr_01", "caption": "Интерфейс"}]}\n'
        "```\n"
    )
    tex, figures, charts, diagrams, *_ = parse_model_output(raw, max_images=1)
    assert tex.count("%CASE3_FIG:usr_01%") == 1


def test_patch_slides_ir_allows_setting_media_id() -> None:
    deck = {
        "version": 1,
        "slides": [
            {"id": "s01", "layout": "title", "title": "Обзор"},
            {"id": "s02", "layout": "media_hero", "title": "Схема", "media_id": "dia_01"},
            {"id": "s03", "layout": "closing", "title": "Итог", "bullets": ["A", "B", "C"]},
        ],
    }
    patch = {
        "slides": [
            {"id": "s02", "media_id": "usr_01", "title": "Фото цеха"},
        ],
    }
    res = apply_deck_text_patch(deck, patch)
    assert res["slides"][1]["media_id"] == "usr_01"
    assert res["slides"][1]["title"] == "Фото цеха"


def test_apply_deck_structure_insert_media_hero_with_usr_photo() -> None:
    deck = {
        "version": 1,
        "slides": [
            {"id": "s01", "layout": "title", "title": "Обзор"},
            {"id": "s02", "layout": "closing", "title": "Итог", "bullets": ["A", "B", "C"]},
        ],
    }
    op_body = {
        "op": "insert",
        "after_id": "s01",
        "layout": "media_hero",
        "media_id": "usr_01",
        "title": "Интерфейс системы",
        "caption": "Панель управления",
    }
    res = apply_deck_structure(deck, op_body)
    new_slide = res["slides"][1]
    assert new_slide["layout"] == "media_hero"
    assert new_slide["media_id"] == "usr_01"
    assert new_slide["title"] == "Интерфейс системы"

    # Must pass parse_deck_ir validation without error
    validated = parse_deck_ir(res, source="Обзор", allowed_media_ids=frozenset(["usr_01"]))
    assert validated["slides"][1]["media_id"] == "usr_01"
