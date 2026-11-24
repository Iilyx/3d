"""Outline + prompt for chat summary (no invention, CTA)."""

from __future__ import annotations

from pathlib import Path

from case3.chat_summary import (
    SUMMARY_SYSTEM,
    build_outline,
    build_summary_user,
    local_summary_blurb,
)

FIXTURE = Path(__file__).parent / "fixtures" / "preview_sample.tex"


def test_outline_keeps_the_table_cell_not_only_the_caption() -> None:
    tex = (
        "\\documentclass{article}\n\\begin{document}\n"
        "\\begin{tabularx}{\\textwidth}{YY}\n"
        "Область & Сумма \\\\\n"
        "Минская & 105 865,2 \\\\\n"
        "\\end{tabularx}\n"
        "\\end{document}\n"
    )
    outline = build_outline(tex)
    assert "105 865,2" in outline
    assert "Минская" in outline
    blurb = local_summary_blurb(tex)
    assert "105 865,2" in blurb


def test_build_outline_includes_title_headings_captions() -> None:
    tex = FIXTURE.read_text(encoding="utf-8")
    outline = build_outline(tex)
    assert "Демография 2019–2023" in outline
    assert "Общая" in outline
    assert "Численность населения" in outline
    # No massive raw TeX dump
    assert r"\documentclass" not in outline
    assert r"\usepackage" not in outline


def test_summary_system_forbids_invention_and_asks_cta() -> None:
    s = SUMMARY_SYSTEM.lower()
    assert "не выдумыв" in s or "only from" in s or "только из" in s
    assert "полн" in SUMMARY_SYSTEM.lower() or "документ" in SUMMARY_SYSTEM.lower()
    assert "media" in s or "график" in SUMMARY_SYSTEM.lower()


def test_build_summary_user_embeds_outline_and_intent() -> None:
    user = build_summary_user("TITLE: Demo\n- Sec A", intent="Сделай краткий обзор")
    assert "Demo" in user
    assert "Sec A" in user
    assert "Сделай краткий обзор" in user


def test_build_summary_user_includes_media_delivered_counts() -> None:
    user = build_summary_user(
        "TITLE: Demo\nFIGURE: photo",
        intent="нужны 3 графика и 1 картинка",
        media={"charts_ok": 0, "figures_ok": 1, "charts_planned": 0, "figures_planned": 1},
    )
    assert "MEDIA_DELIVERED" in user
    assert "charts_ok: 0" in user
    assert "figures_ok: 1" in user
    # Intent wish must not be the only signal — media block present
    assert "нужны 3 графика" in user


def test_build_outline_marks_chart_vs_figure() -> None:
    tex = FIXTURE.read_text(encoding="utf-8")
    outline = build_outline(tex)
    # preview fixture chart id cht_01
    assert "CHART:" in outline or "FIGURE:" in outline


def test_is_clean_chat_summary_rejects_reasoning_leak() -> None:
    from case3.chat_summary import is_clean_chat_summary

    leaked = (
        "The user wants me to write a short chat message (like Cursor/DeepSeek) summarizing what was prepared.\n"
        "Let me check the constraints:\n"
        "1. Write in Russian\n"
        "Let me draft:\n"
        "Отчёт готов."
    )
    assert not is_clean_chat_summary(leaked)

    english_only = "The report is ready with 5 charts and 1 figure."
    assert not is_clean_chat_summary(english_only)

    valid_russian = (
        "Отчёт о сети кофеен «Бодрый день» за прошлый месяц готов. "
        "Внутри — разделов: 5, таблиц: 1, графиков: 5, иллюстраций: 1. "
        "Подробности — в превью и PDF."
    )
    assert is_clean_chat_summary(valid_russian)


def test_local_blurb_says_when_a_chart_did_not_arrive() -> None:
    blurb = local_summary_blurb(
        "\\section{Касса}\n\nТекст без таблицы.",
        media={"charts_planned": 2, "charts_ok": 1, "figures_ok": 0},
    )
    assert "не собрал" in blurb
    assert "1" in blurb


def test_ready_line_waits_until_the_pdf_exists() -> None:
    from case3.chat_summary import seal_chat_summary

    held = seal_chat_summary(
        "Готов: отчёт.",
        {},
        render_error="! Undefined control sequence.\nl.42 \\bad",
    )
    assert "Готов" not in held
    assert "! Undefined control sequence." in held
    ok = seal_chat_summary(
        "Готов: отчёт.",
        {"charts_planned": 2, "charts_ok": 1},
    )
    assert "Готов" in ok
    assert "не собрал" in ok


def test_local_summary_blurb_uses_title_and_counts() -> None:
    tex = FIXTURE.read_text(encoding="utf-8")
    blurb = local_summary_blurb(
        tex, media={"charts_ok": 1, "figures_ok": 0}
    )
    assert "Демография" in blurb
    assert "таблиц" in blurb
    assert "графиков: 1" in blurb
    assert "превью" in blurb.lower() or "PDF" in blurb
