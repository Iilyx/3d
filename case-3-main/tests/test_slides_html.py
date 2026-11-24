"""Static Liber slide HTML from deck IR."""

from __future__ import annotations

from case3.slides_html import render_slide_html


def test_title_slide_dimensions_and_layout() -> None:
    html = render_slide_html(
        {"id": "s01", "layout": "title", "title": "Итоги года", "subtitle": "2024"},
        palette="atelier",
        chart_png_href=None,
    )
    assert 'id="slide"' in html
    assert 'data-layout="title"' in html
    assert "1920px" in html and "1080px" in html
    assert "Итоги года" in html
    assert "2024" in html
    assert "purple" not in html.lower()
    assert "#3f5210" in html or "--primary" in html


def test_bullets_slide() -> None:
    html = render_slide_html(
        {
            "id": "s02",
            "layout": "bullets",
            "title": "Факты",
            "bullets": ["Выручка 120 млн", "Доля 35%"],
        },
        palette="ocean",
        chart_png_href=None,
    )
    assert 'data-layout="bullets"' in html
    assert "<li>" in html
    assert "Выручка 120 млн" in html


def test_chart_hero_embeds_img() -> None:
    html = render_slide_html(
        {
            "id": "s03",
            "layout": "chart_hero",
            "title": "Доля",
            "caption": "Source",
            "chart_id": "cht_01",
        },
        palette="atelier",
        chart_png_href="chart.png",
    )
    assert 'data-layout="chart_hero"' in html
    assert 'src="chart.png"' in html
    assert "Source" in html
    assert "caption--insight" in html


def test_chart_hero_promotes_takeaway_to_insight_caption() -> None:
    html = render_slide_html(
        {
            "id": "s03b",
            "layout": "chart_hero",
            "title": "Growth",
            "takeaway": "Return outpaces spend",
            "chart_id": "cht_01",
        },
        palette="atelier",
        chart_png_href="chart.png",
    )
    assert "caption--insight" in html
    assert "Return outpaces spend" in html
    # Takeaway should not also sit in the section head.
    assert html.count("Return outpaces spend") == 1


def test_card_row_percent_meters() -> None:
    html = render_slide_html(
        {
            "id": "s04b",
            "layout": "card_row",
            "title": "Loves",
            "cards": [
                {"kicker": "68%", "title": "Clarity", "body": "Knows the next step"},
                {"kicker": "104% NA", "title": "North America", "body": "Above plan"},
            ],
        },
        palette="atelier",
        style={"pack_id": "voltage"},
    )
    assert "narr-meter" in html
    assert "--pct:68" in html
    assert "--pct:100" in html  # 104 clamped
    assert "is-pct" in html


def test_closing_slide() -> None:
    html = render_slide_html(
        {"id": "s04", "layout": "closing", "title": "Далее", "bullets": ["Шаг 1"]},
        palette="mono",
        chart_png_href=None,
    )
    assert 'data-layout="closing"' in html
    assert "Шаг 1" in html


def test_kpi_row_slide() -> None:
    html = render_slide_html(
        {
            "id": "s05",
            "layout": "kpi_row",
            "title": "KPI",
            "kpis": [
                {"label": "Выручка", "value": "120 млн", "hint": "год"},
                {"label": "Доля", "value": "35%"},
            ],
        },
        palette="atelier",
    )
    assert 'data-layout="kpi_row"' in html
    assert "kpi-card" in html
    assert "120 млн" in html


def test_chart_split_slide() -> None:
    html = render_slide_html(
        {
            "id": "s06",
            "layout": "chart_split",
            "title": "Разбор",
            "chart_id": "cht_01",
            "body": "Короткий комментарий",
            "bullets": ["Пункт A"],
        },
        palette="ocean",
        chart_png_href="chart.png",
    )
    assert 'data-layout="chart_split"' in html
    assert "chart-split" in html
    assert "chart-col" in html
    assert 'src="chart.png"' in html


def test_media_hero_photo() -> None:
    html = render_slide_html(
        {
            "id": "s07",
            "layout": "media_hero",
            "kicker": "Контекст",
            "title": "Витрина",
            "media_id": "fig_01",
            "caption": "Магазин электроники",
        },
        palette="atelier",
        media_png_href="media.png",
    )
    assert 'data-layout="media_hero"' in html
    assert "media-frame" in html
    assert "kicker" in html
    assert 'src="media.png"' in html


def test_media_split_diagram() -> None:
    html = render_slide_html(
        {
            "id": "s08",
            "layout": "media_split",
            "kicker": "Схема",
            "title": "Процесс",
            "media_id": "dia_01",
            "body": "Короткий разбор",
            "bullets": ["Шаг один"],
        },
        palette="editorial",
        media_png_href="media.png",
    )
    assert 'data-layout="media_split"' in html
    assert "media-split__grid" in html
    assert "Шаг один" in html


def test_section_splash_twin_panel() -> None:
    html = render_slide_html(
        {
            "id": "s09",
            "layout": "section",
            "chapter": 2,
            "title": "Рост каналов",
            "subtitle": "Q3",
        },
        palette="atelier",
        style={"brand_mark": "LIBER · BOARD"},
    )
    assert 'data-layout="section"' in html
    assert "section-splash__panel" in html
    assert "02" in html
    assert "LIBER · BOARD" in html


def test_parse_hero_metrics_newlines_and_dots() -> None:
    from case3.slides_html import parse_hero_metrics, render_slide_html

    assert parse_hero_metrics("4,8 млрд\nВыручка\n27%\nE-com") == [
        ("4,8 млрд", "Выручка"),
        ("27%", "E-com"),
    ]
    assert parse_hero_metrics("$9.6M — pipeline · 8.0x — efficiency") == [
        ("$9.6M", "pipeline"),
        ("8.0x", "efficiency"),
    ]
    html = render_slide_html(
        {
            "id": "s01",
            "layout": "title",
            "title": "QBR",
            "takeaway": "4,8 млрд\nВыручка\n27%\nE-com",
        },
        palette="atelier",
        style={
            "pack_id": "relay",
            "motif": {"split": 0.55, "panels": ["#E8E0F2"]},
        },
    )
    assert "hero-metric__value" in html
    assert "4,8 млрд" in html
    assert 'data-pack="relay"' in html


def test_scorecard_pastel_kpi_cards() -> None:
    style = {
        "pack_id": "relay",
        "motif": {"panels": ["#E8E0F2", "#DDEADB", "#F6DDD0", "#DDEAF0"]},
    }
    html = render_slide_html(
        {
            "id": "s03",
            "layout": "scorecard",
            "title": "Scorecard",
            "kpis": [
                {"label": "Pipeline", "value": "$9.6M", "delta": "+12%"},
                {"label": "Spend", "value": "8.0x", "delta": "eff."},
            ],
        },
        palette="atelier",
        style=style,
        slide_index=2,
    )
    assert "background:#E8E0F2" in html  # card 0
    assert "background:#DDEADB" in html  # card 1


def test_section_panel_rotates_motif_panels() -> None:
    style = {
        "brand_mark": "MARKETING / Q3",
        "motif": {
            "split": 0.55,
            "panels": ["#E8E0F2", "#DDEADB", "#F6DDD0", "#DDEAF0"],
        },
        "colors": {"panel": "#E8E0F2", "paper": "#FBF9F4", "accent": "#416650"},
    }
    slide = {
        "id": "s02",
        "layout": "section",
        "chapter": 1,
        "title": "Search and webinars",
    }
    h0 = render_slide_html(slide, palette="atelier", style=style, slide_index=0)
    h1 = render_slide_html(slide, palette="atelier", style=style, slide_index=1)
    h5 = render_slide_html(slide, palette="atelier", style=style, slide_index=5)
    assert "--panel: #E8E0F2" in h0
    assert "--panel: #DDEADB" in h1
    assert "--panel: #DDEADB" in h5  # 5 % 4 == 1
    assert ".section-splash__panel" in h1
    assert "background: var(--panel)" in h1


def test_card_row_narr_cards_and_gate() -> None:
    html = render_slide_html(
        {
            "id": "s05",
            "layout": "card_row",
            "kicker": "Target audience",
            "title": "Start with the ritual-minded.",
            "subtitle": "Audience hypotheses to validate.",
            "caption": "VALIDATION GATE  15 interviews + 50 tasting sessions",
            "cards": [
                {
                    "kicker": "PRIMARY / THE EVENING EDITOR",
                    "title": "Design-conscious adults",
                    "body": "Ages 28–44; busy routines.",
                },
                {
                    "kicker": "SECONDARY / THE QUIET GIVER",
                    "title": "Thoughtful gift buyers",
                    "body": "Shops for hosts and care packages.",
                },
                {
                    "kicker": "CONTEXT / THE SLOW MOMENT",
                    "title": "One cup. One cue.",
                    "body": "After dinner, before a book.",
                },
            ],
        },
        palette="atelier",
        style={
            "pack_id": "botanical",
            "motif": {"panels": ["#2A4538", "#334F40", "#3A5646"]},
        },
    )
    assert 'data-layout="card_row"' in html
    assert "narr-grid" in html
    assert "narr-card" in html
    assert "Design-conscious adults" in html
    assert "narr-gate" in html
    assert "VALIDATION GATE" in html
    assert 'data-pack="botanical"' in html


def test_scorecard_callout_table() -> None:
    score = render_slide_html(
        {
            "id": "s10",
            "layout": "scorecard",
            "title": "KPI",
            "takeaway": "Рост устойчивый",
            "kpis": [
                {
                    "label": "Выручка",
                    "value": "120",
                    "delta": "+8%",
                    "status": "up",
                }
            ],
        },
        palette="atelier",
    )
    assert "scorecard-grid" in score
    assert "+8%" in score
    assert "Рост устойчивый" in score

    callout = render_slide_html(
        {
            "id": "s11",
            "layout": "callout",
            "title": "Смысл",
            "term": "NPS",
            "definition": "Лояльность клиентов",
            "body": "Источник: опрос",
        },
        palette="atelier",
    )
    assert "callout-stage" in callout
    assert "NPS" in callout

    table = render_slide_html(
        {
            "id": "s12",
            "layout": "table_hero",
            "title": "Сводка",
            "rows": [["A", "B"], ["1", "2"]],
        },
        palette="atelier",
    )
    assert "deck-table" in table
    assert "<th>A</th>" in table
    assert "is-roomy" in table

    dense_rows = [["Область", "Факт"]] + [
        [name, "да"]
        for name in (
            "Минская",
            "Гомельская",
            "Брестская",
            "Витебская",
            "Гродненская",
            "Могилевская",
            "Минск",
            "Борисов",
            "Пинск",
        )
    ]
    dense = render_slide_html(
        {
            "id": "s13",
            "layout": "table_hero",
            "title": "Области",
            "rows": dense_rows,
        },
        palette="atelier",
    )
    assert "is-dense" in dense
    assert "Пинск" in dense


def test_plain_title_is_an_accent_field_and_split_stays() -> None:
    from case3.deck_theme import resolve_deck_theme

    voltage = resolve_deck_theme("voltage").as_dict()
    loud = render_slide_html(
        {
            "id": "s01",
            "layout": "title",
            "kicker": "Планёрка",
            "title": "Что крутить дальше",
            "subtitle": "86 тысяч за неделю",
        },
        palette="voltage",
        style=voltage,
    )
    assert 'class="slide-inner title-stage title-stage--field"' in loud
    assert "title-field__rail" in loud
    board = resolve_deck_theme("board").as_dict()
    split = render_slide_html(
        {"id": "s01", "layout": "title", "title": "Совет", "takeaway": "120 млн — выручка"},
        palette="board",
        style=board,
    )
    assert 'class="slide-inner title-stage title-stage--split"' in split
    assert 'class="slide-inner title-stage title-stage--field"' not in split


def test_compare_columns_are_two_color_fields() -> None:
    from case3.deck_theme import resolve_deck_theme

    html = render_slide_html(
        {
            "id": "s04",
            "layout": "compare",
            "title": "Поиск против баннеров",
            "cards": [
                {"title": "Поиск", "body": "Поиск хороший."},
                {"title": "Баннеры", "body": "Баннеры плохие, отдача 1,4."},
            ],
        },
        palette="signal",
        style=resolve_deck_theme("signal").as_dict(),
    )
    assert 'class="compare compare--fields"' in html
    assert html.count('class="compare__col') == 2
    assert ">01<" in html and ">02<" in html


def test_media_hero_diagram_renders_section_head_and_pack_legend() -> None:
    from case3.deck_theme import resolve_deck_theme
    from case3.diagram_style import ensure_role_classdefs, role_colors_for_palette

    sig_colors = role_colors_for_palette("signal")
    board_colors = role_colors_for_palette("board")
    assert sig_colors["start"]["stroke"].upper() == "#E86A33"
    assert board_colors["start"]["stroke"].upper() == "#226496"

    mmd = ensure_role_classdefs("flowchart LR\n  A[Старт]:::start --> B[Итог]:::ok", "signal")
    assert "fill:" in mmd and "#E86A33" in mmd.upper()

    html = render_slide_html(
        {
            "id": "s_dia",
            "layout": "media_hero",
            "kicker": "13 / АРХИТЕКТУРА ПОТОКА",
            "title": "Контур сквозной синхронизации",
            "caption": "Автоматическая проверка качества данных на каждом гейте",
            "media_id": "dia_arch",
        },
        palette="atelier",
        media_png_href="media.png",
        style=resolve_deck_theme("signal").as_dict(),
    )
    assert "media-hero--diagram" in html
    assert "13 / АРХИТЕКТУРА ПОТОКА" in html
    assert "Контур сквозной синхронизации" in html
    assert "Автоматическая проверка качества данных на каждом гейте" in html
    assert "#E86A33" in html.upper()


def test_media_split_uses_numbered_bands_and_diagram_legend() -> None:
    from case3.deck_theme import resolve_deck_theme

    html = render_slide_html(
        {
            "id": "s_ms",
            "layout": "media_split",
            "kicker": "12 / КОКПИТ",
            "title": "Живой радар телеметрии",
            "media_id": "dia_flow",
            "body": "Единая шина событий",
            "bullets": ["Первый контур", "Второй контур"],
            "caption": "Схема маршрутизации",
        },
        palette="atelier",
        media_png_href="media.png",
        style=resolve_deck_theme("board").as_dict(),
    )
    assert "bullets--bands" in html
    assert "dia-legend" in html
    assert "#226496" in html.upper()


def test_relay_terracotta_blush_theme_and_qbr_15_slides() -> None:
    from case3.deck_structure import list_structures
    from case3.deck_theme import resolve_deck_theme
    from case3.diagram_style import role_colors_for_palette

    tok = resolve_deck_theme("relay")
    assert tok.pack_id == "relay"
    assert tok.colors["primary"].upper() == "#5C2A24"
    assert tok.colors["accent"].upper() == "#C45B46"
    assert tok.colors["foil"].upper() == "#D4884E"
    assert len(tok.motif.get("panels") or []) == 4
    assert tok.motif["panels"][0].upper() == "#FADFD8"

    roles = role_colors_for_palette("relay")
    assert roles["start"]["stroke"].upper() == "#C45B46"

    rows = {s["id"]: s for s in list_structures()}
    qbr = rows["qbr"]
    assert qbr["default_pack"] == "relay"
    assert len(qbr["arc"]) == 15
    assert qbr["arc"].count("section") == 2
    assert "media_hero" in qbr["arc"] and "media_split" in qbr["arc"]


def test_voltage_and_studio_distinct_themes_structures_and_layouts() -> None:
    from case3.deck_structure import list_structures
    from case3.deck_theme import resolve_deck_theme

    volt = resolve_deck_theme("voltage")
    assert volt.pack_id == "voltage"
    assert volt.colors["sheet"].upper() == "#111823"
    assert volt.colors["accent"].upper() == "#38BDF8"
    assert volt.colors["foil"].upper() == "#E4E869"

    volt_title = render_slide_html(
        {
            "id": "s01",
            "layout": "title",
            "kicker": "UX LAB · Q3",
            "title": "Импульс продукта",
            "takeaway": "72% — CSAT\n+41 — NPS\n240 — респондентов",
        },
        palette="voltage",
        style=volt.as_dict(),
    )
    assert 'class="slide-inner title-stage title-stage--field"' in volt_title
    assert "title-field__rail" in volt_title
    assert "hero-metrics" in volt_title

    studio = resolve_deck_theme("studio")
    assert studio.pack_id == "studio"
    assert studio.colors["sheet"].upper() == "#FBF6EE"
    assert studio.colors["primary"].upper() == "#2D5A88"
    assert studio.colors["foil"].upper() == "#D47A3E"
    assert len(studio.motif.get("panels") or []) == 4

    rows = {s["id"]: s for s in list_structures()}
    survey = rows["survey"]
    assert survey["default_pack"] == "voltage"
    assert len(survey["arc"]) == 14
    assert "chart_hero" not in survey["arc"]
    assert "chart_split" in survey["arc"]
    assert "media_hero" in survey["arc"] and "media_split" in survey["arc"]

    council = rows["council"]
    assert council["default_pack"] == "studio"
    assert len(council["arc"]) == 15
    assert "table_hero" not in council["arc"]
    assert "chart_hero" in council["arc"] and "chart_split" in council["arc"]
    assert "media_hero" in council["arc"] and "media_split" in council["arc"]


def test_atelier_botanical_ink_themes_and_structures() -> None:
    from case3.deck_structure import list_structures
    from case3.deck_theme import resolve_deck_theme

    atelier = resolve_deck_theme("atelier")
    assert atelier.pack_id == "atelier"
    assert atelier.colors["primary"].upper() == "#233322"
    assert atelier.colors["accent"].upper() == "#5A7D4C"
    assert atelier.colors["foil"].upper() == "#C87D4B"

    bot = resolve_deck_theme("botanical")
    assert bot.pack_id == "botanical"
    assert bot.colors["sheet"].upper() == "#101F19"
    assert bot.colors["foil"].upper() == "#C4AD7A"
    assert bot.motif.get("hero_bleed") is True

    ink = resolve_deck_theme("ink")
    assert ink.pack_id == "ink"
    assert ink.colors["sheet"].upper() == "#0F1520"
    assert ink.colors["accent"].upper() == "#4EA8DE"
    assert ink.colors["foil"].upper() == "#E6B85C"

    rows = {s["id"]: s for s in list_structures()}
    camp = rows["campaign"]
    assert camp["default_pack"] == "atelier"
    assert len(camp["arc"]) == 14
    assert "media_hero" in camp["arc"] and "media_split" in camp["arc"]

    qtr = rows["quarter"]
    assert qtr["default_pack"] == "botanical"
    assert len(qtr["arc"]) == 15
    assert qtr["arc"].count("section") == 2
    assert "media_hero" in qtr["arc"] and "media_split" in qtr["arc"]

    inv = rows["investor"]
    assert inv["default_pack"] == "ink"
    assert len(inv["arc"]) == 14
    assert "media_hero" in inv["arc"] and "media_split" in inv["arc"]





