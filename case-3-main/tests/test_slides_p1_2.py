"""P1.2 regression tests: slide watermarks, units/percent preservation, hbar legend & labels, diagram legends."""

from __future__ import annotations

import pytest


def test_theme_packs_have_no_debug_watermark_and_slides_omit_empty_brand(tmp_path) -> None:
    from pptx import Presentation

    from case3.deck_theme import PACK_IDS, resolve_deck_theme
    from case3.slides_html import render_slide_html
    from case3.slides_pptx_native import build_native_pptx

    for pid in PACK_IDS:
        tok = resolve_deck_theme(pid)
        assert tok.brand_mark == "", f"{pid} leaked brand_mark {tok.brand_mark!r}"

    sig = resolve_deck_theme("signal").as_dict()
    html = render_slide_html(
        {"id": "s02", "layout": "bullets", "title": "Итоги", "bullets": ["Пункт 1"]},
        palette="atelier",
        style=sig,
    )
    assert "BOLD SIGNAL" not in html
    assert "LIBER · ATELIER" not in html
    assert '<div class="brand">' not in html

    # Explicit user-supplied brand_mark still renders.
    custom_html = render_slide_html(
        {"id": "s02", "layout": "bullets", "title": "Итоги", "bullets": ["Пункт 1"]},
        palette="atelier",
        style={"brand_mark": "ОТДЕЛ АНАЛИТИКИ"},
    )
    assert "ОТДЕЛ АНАЛИТИКИ" in custom_html

    deck = {
        "version": 1,
        "palette": "atelier",
        "style": sig,
        "slides": [
            {"id": "s01", "layout": "title", "title": "Поступления"},
            {"id": "s02", "layout": "bullets", "title": "Итоги", "bullets": ["Факт 100 тыс. руб."]},
            {"id": "s03", "layout": "closing", "title": "Вывод", "bullets": ["Готово"]},
        ],
    }
    pptx_path = tmp_path / "deck.pptx"
    build_native_pptx(deck, pptx_path)
    prs = Presentation(str(pptx_path))
    all_text = "\n".join(
        sh.text_frame.text
        for sl in prs.slides
        for sh in sl.shapes
        if getattr(sh, "has_text_frame", False)
    )
    assert "BOLD SIGNAL" not in all_text
    assert "LIBER · ATELIER" not in all_text


def test_scrub_invented_numbers_preserves_units_and_percent_on_valid_numbers() -> None:
    from case3.slides_ir import parse_deck_ir, scrub_invented_numbers

    source = (
        "| Инспекция | План, тыс. руб. | Факт, тыс. руб. | Вып., % |\n"
        "| --- | --- | --- | --- |\n"
        "| Минская | 400 000,0 | 412 850,4 | 103,2% |\n"
    )
    raw = {
        "version": 1,
        "palette": "atelier",
        "slides": [
            {"id": "s01", "layout": "title", "title": "Итоги, тыс. руб."},
            {
                "id": "s02",
                "layout": "scorecard",
                "title": "Факт 412 850,4 тыс. руб. и 103,2%",
                "kpis": [
                    {"label": "Факт, тыс. руб.", "value": "412 850,4 тыс. руб.", "delta": "103,2%"},
                ],
            },
            {
                "id": "s03",
                "layout": "table_hero",
                "title": "Таблица поступлений",
                "rows": [
                    ["Инспекция", "Факт, тыс. руб.", "Вып., %"],
                    ["Минская", "412 850,4 тыс. руб.", "103,2%"],
                ],
            },
            {
                "id": "s04",
                "layout": "closing",
                "title": "Итоги",
                "bullets": [
                    "Минская: факт 103,2%, без 999 тыс. руб.",
                ],
            },
        ],
    }
    healed = scrub_invented_numbers(raw, source=source)
    ir = parse_deck_ir(healed, source=source)
    sc = ir["slides"][1]
    assert "тыс." in sc["title"]
    assert "103,2%" in sc["title"]
    assert sc["kpis"][0]["label"] == "Факт, тыс. руб."
    assert sc["kpis"][0]["value"] == "412 850,4 тыс. руб."
    assert sc["kpis"][0]["delta"] == "103,2%"
    tbl = ir["slides"][2]
    assert tbl["rows"][0] == ["Инспекция", "Факт, тыс. руб.", "Вып., %"]
    assert tbl["rows"][1] == ["Минская", "412 850,4 тыс. руб.", "103,2%"]
    closing_bullet = ir["slides"][3]["bullets"][0]
    assert "103,2%" in closing_bullet
    assert "999" not in closing_bullet


def test_horizontal_bar_keeps_multiseries_legend_and_disables_y_autoskip() -> None:
    from case3.chart_harden import _hide_legend_if_unnamed_dataset, harden_chart_html

    cats = [f"ИМНС №{i}" for i in range(1, 13)]
    vals1 = [100 + i * 10 for i in range(12)]
    vals2 = [110 + i * 10 for i in range(12)]
    raw = (
        "<canvas id='c' width='1100' height='560'></canvas>"
        "<script>new Chart(document.getElementById('c'),{"
        "type:'bar',"
        f"data:{{labels:{cats!r},datasets:[{{label:'План',data:{vals1!r},backgroundColor:'#1c352d'}},{{label:'Факт',data:{vals2!r},backgroundColor:'#b8860b'}}]}},"
        "options:{indexAxis:'y',responsive:false,animation:false}"
        "});</script>"
    )
    step1 = _hide_legend_if_unnamed_dataset(raw)
    assert "display:false" not in step1
    step2 = harden_chart_html(step1, "horizontal_bar", palette_id="atelier")
    assert "autoSkip:false" in step2.replace(" ", "")


def test_diagram_slide_avoids_hardcoded_legend_for_non_flowchart_and_uses_actual_roles() -> None:
    from case3.slides_html import render_slide_html

    mm_html = render_slide_html(
        {
            "id": "s04",
            "layout": "media_hero",
            "title": "Структура налогов",
            "media_id": "dia_01",
            "caption": "Основные группы поступлений",
        },
        palette="atelier",
        media_png_href="dia.png",
        diagram_spec={"id": "dia_01", "type": "mindmap", "mermaid": "mindmap\n  root((Налоги))"},
    )
    assert '<ul class="dia-legend"' not in mm_html

    fc_html = render_slide_html(
        {
            "id": "s05",
            "layout": "media_hero",
            "title": "Согласование",
            "media_id": "dia_02",
            "caption": "Два ключевых узла",
        },
        palette="atelier",
        media_png_href="dia2.png",
        diagram_spec={
            "id": "dia_02",
            "type": "flowchart",
            "mermaid": "flowchart LR\n  A[Старт]:::start --> B[Готово]:::ok",
        },
    )
    assert "dia-legend" in fc_html
    assert "Старт" in fc_html
    assert "Успех" in fc_html
    assert "Решение" not in fc_html
    assert "Риск" not in fc_html
