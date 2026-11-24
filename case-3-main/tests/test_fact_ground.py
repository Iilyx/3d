"""A new report may repeat Source and the user's own number. Not a memory number."""

from pathlib import Path

from case3.fact_ground import fact_number_tokens, ground_generated
from case3.generate import generate_document

_TEX = r"""
\documentclass[a4paper,12pt]{article}
\begin{document}
\section{Касса}
Выручка 77. В источнике 20. Новых точек 15.
\includegraphics[width=0.85\textwidth]{figures/cht_01.png}
\end{document}
"""


def test_tex_thousands_and_column_span_stay_when_the_cell_is_in_source():
    tex = r"""
\documentclass{article}
\begin{document}
Собрано 85\,000. Чужое 12\,345.
\multicolumn{3}{c}{Итого}
\end{document}
"""
    out, _charts, _figures, _diagrams, _dropped = ground_generated(
        tex,
        [],
        [],
        [],
        source="собрано 85000",
        intent="отчёт",
    )
    assert r"85\,000" in out
    assert r"12\,345" not in out
    assert r"\multicolumn{3}" in out


def test_chart_array_keeps_both_points_when_the_comma_has_no_space():
    tex = r"""
\documentclass{article}
\begin{document}
Минская 100. Гомельская 40.
\end{document}
"""
    _out, charts, _figures, _diagrams, _dropped = ground_generated(
        tex,
        [{"id": "cht_01", "caption": "Области", "html": "data: [100,40]"}],
        [],
        [],
        source=(
            "| Область | Сумма |\n"
            "| --- | --- |\n"
            "| Минская | 100 |\n"
            "| Гомельская | 40 |\n"
        ),
        intent="отчёт",
    )
    html = charts[0]["html"]
    assert "100" in html
    assert "40" in html
    assert "null" not in html
    assert "100.40" not in html
    assert "100,40" not in html or "100, 40" in html or html.index("40") > html.index("100")


def test_named_region_keeps_its_column_and_drops_the_other_row():
    source = (
        "| Область | План | Факт |\n"
        "| --- | --- | --- |\n"
        "| Минская | 10 | 12 |\n"
        "| Гомельская | 40 | 48 |\n"
    )
    tex = r"""
\documentclass{article}
\begin{document}
Гомельская план 40. Гомельская план 10. Минская факт 12.
\end{document}
"""
    out, _charts, _figures, _diagrams, _dropped = ground_generated(
        tex,
        [],
        [],
        [],
        source=source,
        intent="отчёт",
    )
    assert "Гомельская план 40" in out
    assert "план 10" not in out
    assert "Минская факт 12" in out


def test_two_regions_in_one_sentence_keep_their_own_sums():
    source = (
        "| Область | Сумма |\n"
        "| --- | --- |\n"
        "| Минская | 105 865,2 |\n"
        "| Гомельская | 94 073,0 |\n"
    )
    tex = r"""
\documentclass{article}
\begin{document}
Минская 94 073,0; Гомельская 105 865,2.
Минская 94 073,0 и Гомельская 105 865,2.
Минская 105 865,2 и Гомельская 94 073,0.
\end{document}
"""
    out, _charts, _figures, _diagrams, _dropped = ground_generated(
        tex, [], [], [], source=source, intent="отчёт"
    )
    assert "94 073,0; Гомельская 105 865,2" not in out
    assert "94 073,0 и Гомельская 105 865,2" not in out
    assert "Минская 105 865,2 и Гомельская 94 073,0" in out


def test_a_share_is_not_the_regions_sum():
    from case3.dashboard_source import derivative_block

    table = (
        "| Область | Сумма |\n"
        "| --- | --- |\n"
        "| Минская | 105 865,2 |\n"
        "| Гомельская | 94 073,0 |\n"
    )
    source = table + "\n## Производные\n" + derivative_block(table)
    tex = r"""
\documentclass{article}
\begin{document}
Минская собрала 52,9.
Доля Минской 52,9%.
\end{document}
"""
    out, charts, _figures, _diagrams, _dropped = ground_generated(
        tex,
        [
            {
                "id": "cht_01",
                "caption": "Минская",
                "html": "labels: ['Минская'], data: [52.9]",
            }
        ],
        [],
        [],
        source=source,
        intent="отчёт",
    )
    assert "собрала" not in out
    assert "Доля Минской 52,9%" in out
    assert "52.9" not in charts[0]["html"]


def test_share_stays_on_the_region_it_was_computed_for():
    from case3.dashboard_source import derivative_block

    table = (
        "| Область | Сумма |\n"
        "| --- | --- |\n"
        "| Минская | 105 865,2 |\n"
        "| Гомельская | 94 073,0 |\n"
    )
    source = table + "\n## Производные\n" + derivative_block(table)
    tex = r"""
\documentclass{article}
\begin{document}
Доля Минской 52,9%.
Доля Гомельской 52,9%.
\end{document}
"""
    out, _charts, _figures, _diagrams, _dropped = ground_generated(
        tex,
        [],
        [],
        [],
        source=source,
        intent="отчёт",
    )
    assert out.count("52,9%") == 1
    assert "Гомель" not in out


def test_a_chart_point_stays_on_the_region_it_labels():
    source = (
        "| Область | Сумма |\n"
        "| --- | --- |\n"
        "| Минская | 105 865,2 |\n"
        "| Гомельская | 94 073,0 |\n"
    )
    tex = r"""
\documentclass{article}
\begin{document}
Сравнение областей.
\end{document}
"""
    _out, charts, _figures, _diagrams, _dropped = ground_generated(
        tex,
        [
            {
                "id": "cht_01",
                "caption": "Области",
                "html": "labels: ['Гомельская','Минская'], data: [105865.2, 105865.2]",
            }
        ],
        [],
        [],
        source=source,
        intent="Сделай отчёт.",
    )
    html = charts[0]["html"]
    assert "data: [null, 105865.2]" in html
    months, _figures, _diagrams, _dropped = ground_generated(
        tex,
        [
            {
                "id": "cht_02",
                "caption": "По месяцам",
                "html": "labels: ['Январь','Февраль'], data: [105865.2, 94073.0]",
            }
        ],
        [],
        [],
        source=source,
        intent="Сделай отчёт.",
    )[1:]
    assert "105865.2" in months[0]["html"]
    assert "94073.0" in months[0]["html"]


def test_spaced_thousands_are_one_number_in_prose_and_in_chart_data():
    from case3.chat_turn import number_norms

    source = "Минская область | 105 865,2"
    norms = number_norms(source)
    assert "105865.2" in norms
    assert "105" not in norms
    assert "865.2" not in norms
    tex = r"""
\documentclass{article}
\begin{document}
В Минской области собрано 105 865,2.
\end{document}
"""
    out, charts, _figures, _diagrams, dropped = ground_generated(
        tex,
        [
            {
                "id": "cht_01",
                "caption": "Минская область",
                "html": "data: [105865.2, 999], labels: ['Минская','Гомельская']",
            }
        ],
        [],
        [],
        source=source,
        intent="Сделай отчёт.",
    )
    assert "105 865,2" in out
    assert "999" not in charts[0]["html"]
    assert "105865.2" in charts[0]["html"]
    assert "999" in dropped


def test_a_year_at_the_start_of_a_line_stays_in_the_report():
    tex = r"""
\documentclass{article}
\begin{document}
В 2024 году выручка составила 10.
\end{document}
"""
    out, _charts, _figures, _diagrams, _dropped = ground_generated(
        tex, [], [], [], source="2024. Выручка 10", intent="отчёт"
    )
    assert "2024" in out
    assert "10" in out


def test_a_foreign_number_in_the_title_does_not_reach_the_first_page():
    tex = r"""
\documentclass{article}
\title{Поступления 999}
\begin{document}
Касса 20.
\end{document}
"""
    out, _charts, _figures, _diagrams, _dropped = ground_generated(
        tex, [], [], [], source="Касса 20.", intent="отчёт"
    )
    assert "999" not in out
    assert r"\title{Отчёт}" in out
    assert "Касса 20" in out


def test_a_short_decimal_comma_in_chart_data_is_one_point():
    tex = r"""
\documentclass{article}
\begin{document}
Маржа 12,5. В Минской собрано 105 865,2.
\end{document}
"""
    _out, charts, _figures, _diagrams, _dropped = ground_generated(
        tex,
        [
            {
                "id": "cht_01",
                "caption": "Маржа",
                "html": "labels: ['Маржа'], data: [12,5]",
            },
            {
                "id": "cht_02",
                "caption": "Сумма",
                "html": "labels: ['Минская'], data: [105 865,2]",
            },
        ],
        [],
        [],
        source="Маржа 12,5.\nМинская 105 865,2.",
        intent="Сделай отчёт.",
    )
    assert charts[0]["html"] == "labels: ['Маржа'], data: [12.5]"
    assert charts[1]["html"] == "labels: ['Минская'], data: [105865.2]"


def test_decimal_comma_stays_when_a_foreign_number_is_dropped():
    tex = r"""
\documentclass{article}
\begin{document}
Маржа 12,5. Память 77.
\end{document}
"""
    out, _charts, _figures, _diagrams, dropped = ground_generated(
        tex,
        [],
        [],
        [],
        source="Маржа 12,5.",
        intent="Сделай отчёт.",
    )
    assert "12,5" in out
    assert "12, 5" not in out
    assert "77" not in out
    assert "77" in dropped


def test_memory_number_leaves_the_report_and_the_source_number_stays():
    intent = (
        "Сделай отчёт. Новых точек 15.\n\n"
        "Разговор этого чата (не Source).\n"
        "Ответ: выручка 77.\n"
        "Запрос: было 99."
    )
    tex, charts, _figures, _diagrams, dropped = ground_generated(
        _TEX,
        [
            {
                "id": "cht_01",
                "caption": "Выручка 77",
                "html": "data: [20, 77], labels: ['смена']",
                "insight": "скачок 77",
            }
        ],
        [],
        [],
        source="выручка 20",
        intent=intent,
    )
    assert "77" not in tex
    assert "Выручка ." not in tex
    assert "Выручка." not in tex
    assert "20" in tex
    assert "15" in tex
    assert "0.85" in tex
    assert "12pt" in tex
    assert "77" not in charts[0]["caption"]
    assert "77" not in charts[0]["insight"]
    assert "data: [20, null]" in charts[0]["html"]
    assert "77" in dropped
    assert "20" not in dropped
    assert "15" not in dropped


def test_generate_document_strips_a_memory_number(tmp_path: Path):
    source = tmp_path / "source.txt"
    source.write_text("выручка 20\n", encoding="utf-8")
    out = tmp_path / "work" / "doc.tex"
    raw = (
        "```json\n"
        '{"charts":[],"diagrams":[],"figures":[]}\n'
        "```\n"
        "```latex\n"
        "\\documentclass{article}\n"
        "\\begin{document}\n"
                "Выручка 77 держится второй месяц подряд, хотя в источнике указано только 20.\n"
        "\\end{document}\n"
        "```\n"
    )
    generate_document(
        source,
        out_tex=out,
        intent=(
            "Сделай отчёт.\n\n"
            "Разговор этого чата (не Source).\n"
            "Ответ: выручка 77."
        ),
        replay_raw=raw,
        max_images=0,
        max_charts=0,
        max_diagrams=0,
    )
    text = out.read_text(encoding="utf-8")
    assert "77" not in text
    assert "20" in text


def test_slide_scrub_uses_source_not_memory():
    from case3.slides_ir import DeckIrError, parse_deck_ir, scrub_invented_numbers

    source = "выручка 20"
    intent = (
        "Собери слайды.\n\n"
        "Разговор этого чата (не Source).\n"
        "Ответ: доля 77%."
    )
    raw = {
        "version": 1,
        "palette": "atelier",
        "slides": [
            {"id": "s01", "layout": "title", "title": "Касса"},
            {
                "id": "s02",
                "layout": "scorecard",
                "title": "Цифры",
                "kpis": [
                    {"label": "Выручка", "value": "20"},
                    {"label": "Память", "value": "77"},
                ],
            },
            {
                "id": "s03",
                "layout": "closing",
                "title": "Дальше",
                "bullets": ["Держим 20"],
            },
        ],
    }
    allowed = fact_number_tokens(source, intent)
    try:
        parse_deck_ir(raw, source=source, allowed_number_strings=allowed)
    except DeckIrError:
        healed = scrub_invented_numbers(
            raw, source=source, allowed_number_strings=allowed
        )
    else:
        raise AssertionError("77 must not pass as a slide fact")
    assert healed["slides"][1]["kpis"] == [{"label": "Выручка", "value": "20"}]


def test_escaped_percent_does_not_hide_the_memory_number():
    tex = r"""
\documentclass{article}
\begin{document}
В источнике 20\%, а в памяти 77.
% черновик 77
\end{document}
"""
    out, _charts, _figures, _diagrams, dropped = ground_generated(
        tex,
        [],
        [],
        [],
        source="выручка 20",
        intent="Сделай отчёт.\n\nРазговор этого чата (не Source).\nОтвет: 77.",
    )
    assert r"\%77" not in out
    assert "а в памяти 77" not in out
    assert "20" in out
    assert "% черновик 77" in out
    assert "77" in dropped


def test_chart_tooltip_loses_a_memory_number():
    _tex, charts, _figures, _diagrams, _dropped = ground_generated(
        r"\documentclass{article}\begin{document}В источнике 20.\end{document}",
        [
            {
                "id": "cht_01",
                "caption": "Касса",
                "html": "data: [20], title: { text: 'Выручка 77' }, color: 'rgba(77, 77, 77)'",
            }
        ],
        [],
        [],
        source="выручка 20",
        intent="Сделай отчёт.",
    )
    html = charts[0]["html"]
    assert "Выручка 77" not in html
    assert "data: [20]" in html
    assert "rgba(77, 77, 77)" in html


def test_slide_allow_list_keeps_source_spellings_and_drops_memory():
    intent = (
        "Собери слайды.\n\n"
        "Разговор этого чата (не Source).\n"
        "Ответ: доля 77%."
    )
    allowed = fact_number_tokens("Доля 12,5 и 35%.", intent)
    assert "12.5" in allowed
    assert "12,5" in allowed
    assert "35" in allowed
    assert "77" not in allowed


def test_user_number_stays_only_beside_its_word_and_spoken_twelve_counts():
    from case3.fact_ground import ground_generated

    intent = (
        "собери отчёт\n\n"
        "Числа из реплик пользователя (его слова, не ответ модели):\n"
        "2 слайд\n\n"
        "Разговор этого чата (не Source).\n"
    )
    tex = (
        "\\documentclass{article}\n\\begin{document}\n"
        "Выручка 2. Слайд 2 остаётся.\n"
        "\\end{document}\n"
    )
    out, _charts, _figures, _diagrams, _dropped = ground_generated(
        tex, [], [], [], source="Касса без цифр.", intent=intent
    )
    assert "Выручка 2" not in out
    assert "Слайд 2" in out

    spoken_source = ground_generated(
        "\\documentclass{article}\n\\begin{document}\nИтог 12.\n\\end{document}\n",
        [],
        [],
        [],
        source="В кассе двенадцать.",
        intent="собери отчёт",
    )[0]
    assert "12" in spoken_source
    ninety = ground_generated(
        "\\documentclass{article}\n\\begin{document}\nИтог 90.\n\\end{document}\n",
        [],
        [],
        [],
        source="В кассе девяносто.",
        intent="собери отчёт",
    )[0]
    assert "90" in ninety
    invented = ground_generated(
        "\\documentclass{article}\n\\begin{document}\nБыло двенадцать.\n\\end{document}\n",
        [],
        [],
        [],
        source="Касса тихая.",
        intent="собери отчёт",
    )[0]
    assert "двенадцать" not in invented
    from case3.fact_ground import bind_deck_numbers

    deck = bind_deck_numbers(
        {
            "slides": [
                {
                    "kpis": [
                        {"label": "Выручка", "value": "2"},
                        {"label": "Слайд", "value": "2"},
                    ]
                }
            ]
        },
        source="Касса без цифр.",
        intent=intent,
    )
    labels = [item["label"] for item in deck["slides"][0]["kpis"]]
    assert labels == ["Слайд"]
    _bound_tex, charts, _figures, _diagrams, _dropped_chart = ground_generated(
        "\\documentclass{article}\n\\begin{document}\nСлайд 2.\n\\end{document}\n",
        [
            {
                "html": "data: [2], labels: ['касса']",
                "caption": "Слайд 2",
                "highlights": [
                    {"label": "Выручка", "value": "2"},
                    {"label": "Слайд", "value": "2"},
                ],
            }
        ],
        [],
        [],
        source="Касса без цифр.",
        intent=intent,
    )
    assert "data: [2]" not in charts[0]["html"]
    assert "null" in charts[0]["html"]
    assert "Слайд 2" in charts[0]["caption"]
    shown = [row["label"] for row in charts[0]["highlights"] if row.get("value") == "2"]
    assert shown == ["Слайд"]


def test_user_stated_number_stays_in_a_new_report_and_the_answer_number_goes():
    from case3.fact_ground import ground_generated

    intent = (
        "собери отчёт\n\n"
        "Числа из реплик пользователя (его слова, не ответ модели):\n"
        "77 выручк\n\n"
        "Разговор этого чата (не Source).\n"
        "Ответ: было 88."
    )
    tex = (
        "\\documentclass{article}\n\\begin{document}\n"
        "Выручка 77. Модель дописала 88.\n"
        "\\end{document}\n"
    )
    out, charts, figures, diagrams, dropped = ground_generated(
        tex, [], [], [], source="Касса 20.", intent=intent
    )
    assert "77" in out
    assert "88" not in out
    assert "88" in dropped


def test_a_slide_emptied_by_numbers_is_dropped_on_the_second_pass() -> None:
    from case3.fact_ground import bind_deck_numbers

    deck = bind_deck_numbers(
        {
            "slides": [
                {"id": "s01", "layout": "title", "title": "Итоги"},
                {
                    "id": "s02",
                    "layout": "bullets",
                    "title": "999",
                    "bullets": ["888"],
                },
                {"id": "s03", "layout": "closing", "title": "Конец", "bullets": ["ок"]},
            ]
        },
        source="Касса без цифр.",
        intent="собери отчёт",
    )
    ids = [slide.get("id") for slide in deck["slides"]]
    assert "s02" not in ids
    assert "s01" in ids
    assert "s03" in ids
    blank = bind_deck_numbers(
        {"slides": [{"id": "s01", "layout": "bullets", "title": "999", "bullets": ["4"]}]},
        source="Касса без цифр.",
        intent="собери отчёт",
    )
    assert blank["slides"]
    assert "999" not in str(blank)
    assert str(blank["slides"][0].get("title") or "").strip()


def test_a_three_letter_month_stays_on_its_row():
    source = (
        "| Область | Май | Июнь |\n"
        "| --- | --- | --- |\n"
        "| Минская | 14 | 15 |\n"
        "| Гомельская | 11 | 12 |\n"
    )
    tex = (
        "\\documentclass{article}\n\\begin{document}\n"
        "Минская & 14 & 15 \\\\\n"
        "Гомельская & 11 & 12 \\\\\n"
        "\\end{document}\n"
    )
    out, _charts, _figures, _diagrams, _dropped = ground_generated(
        tex, [], [], [], source=source, intent="отчёт"
    )
    assert "& 14 &" in out
    assert "& 11 &" in out


def test_an_invented_share_does_not_leave_a_hole_in_the_sentence():
    source = (
        "| Область | Сумма |\n"
        "| --- | --- |\n"
        "| Минская | 100 |\n"
        "| Гомельская | 40 |\n"
    )
    tex = (
        "\\documentclass{article}\n\\begin{document}\n"
        "Минская область — 100 единиц, Гомельская область — 40 единиц.\n"
        "Доля Минской около 71{,}4\\%, доля Гомельской около 28{,}6\\%.\n"
        "По сравнению с Гомельской её сумма выше более чем в два раза: 100 против 40.\n"
        "\\end{document}\n"
    )
    out, _charts, _figures, _diagrams, _dropped = ground_generated(
        tex, [], [], [], source=source, intent="отчёт"
    )
    assert "100 единиц" in out
    assert "40 единиц" in out
    assert "71" not in out
    assert "раза" not in out
    assert "\\%" not in out


def test_a_spoken_count_does_not_leave_the_tail_of_the_sentence():
    tex = (
        "\\documentclass{article}\n\\begin{document}\n"
        "В исходных данных приведены значения кассы за три месяца: март, апрель и май. "
        "В марте касса составила 18.\n"
        "\\end{document}\n"
    )
    out, _charts, _figures, _diagrams, _dropped = ground_generated(
        tex,
        [],
        [],
        [],
        source="В марте касса была 18.\nВ апреле касса была 22.\nВ мае касса была 19.\n",
        intent="отчёт",
    )
    assert "апрель и май" not in out
    assert "18" in out


def test_a_slide_does_not_keep_a_hole_where_the_number_was():
    from case3.fact_ground import bind_deck_numbers

    deck = bind_deck_numbers(
        {
            "slides": [
                {
                    "id": "s01",
                    "layout": "section",
                    "title": "Минская в два раза больше Гомельской",
                },
                {
                    "id": "s02",
                    "layout": "title",
                    "title": "Касса",
                    "takeaway": "Минская лидирует с 100 против 40",
                },
            ]
        },
        source=(
            "| Область | Сумма |\n"
            "| --- | --- |\n"
            "| Минская | 100 |\n"
            "| Гомельская | 40 |\n"
        ),
        intent="презентация",
    )
    blob = str(deck)
    assert "раза" not in blob
    assert "против" not in blob
    assert any(slide.get("title") == "Касса" for slide in deck["slides"])


def test_table_row_with_percent_and_multicolumn_header_survive_grounding():
    source = (
        "| Регион | Факт | План | Выполнение |\n"
        "| --- | --- | --- | --- |\n"
        "| Москва | 105865.2 | 100000.0 | 105.9% |\n"
        "| Тюмень | 24650.9 | 26000.0 | 94.8% |\n"
    )
    tex = r"""
\documentclass{article}
\begin{document}
В таблице~\ref{tab:rev} приведены данные B2B. Москва продолжает рост: 105865,2.

\begin{tabularx}{\textwidth}{lXXX}
\toprule
\multicolumn{1}{c}{Регион} & \multicolumn{1}{c}{Факт} & \multicolumn{1}{c}{План} & \multicolumn{1}{c}{Выполнение, \%} \\
\midrule
Москва & 105865,2 & 100000,0 & 105,9\% \\
Тюмень & 24650,9 & 26000,0 & 94,8\% \\
\bottomrule
\end{tabularx}

%CASE3_CHART:cht_01%

Текст после слота.
\end{document}
"""
    charts = [{"id": "cht_01", "caption": "Откл.", "html": "data: [-38, -12.5]"}]
    diagrams = [
        {
            "id": "dia_01",
            "title": "Поток",
            "mermaid": "flowchart TD\nA1[B2B] --> B2[OK]\nclassDef start fill:#DCE6F0,stroke:#4E79A7,color:#1a2e22",
        }
    ]
    out, out_charts, _figs, out_diags, _dropped = ground_generated(
        tex,
        charts,
        [],
        diagrams,
        source=source + "\nОтклонение -38 и -12,5.",
        intent="отчёт",
    )
    assert r"\multicolumn{1}{c}{Выполнение, \%} \\" in out
    assert r"Москва & 105865,2 & 100000,0 & 105,9\% \\" in out
    assert r"Тюмень & 24650,9 & 26000,0 & 94,8\% \\" in out
    assert "Москва продолжает рост: 105865,2" in out
    assert "данные B2B" in out
    assert r"В таблице~\ref{tab:rev} приведены" in out
    assert "\n%CASE3_CHART:cht_01%\n" in out
    assert "null" not in out_charts[0]["html"]
    assert "-38" in out_charts[0]["html"]
    assert "classDef start fill:#DCE6F0,stroke:#4E79A7,color:#1a2e22" in out_diags[0]["mermaid"]


def test_bind_deck_numbers_keeps_kicker_chrome_and_strips_ui_block_on_empty_chat():
    from case3.fact_ground import bind_deck_numbers

    ui_only_intent = "Требования UI:\n- canvas 1100×560\n- hex #004D47"
    deck = bind_deck_numbers(
        {
            "slides": [
                {"id": "s01", "layout": "title", "title": "Итоги", "kicker": "01"},
                {
                    "id": "s02",
                    "layout": "table_hero",
                    "title": "Сравнение",
                    "rows": [["Канал", "Факт"], ["B2B", "быстро"]],
                },
                {"id": "s03", "layout": "bullets", "title": "Холст", "bullets": ["Ширина 1100"]},
            ]
        },
        source="Канал B2B работает.",
        intent=ui_only_intent,
    )
    assert deck["slides"][0]["kicker"] == "01"
    assert deck["slides"][1]["rows"] == [["Канал", "Факт"], ["B2B", "быстро"]]
    # 1100 from Требования UI must NOT slip into slides
    assert "1100" not in str(deck)


def test_scrub_html_bound_preserves_canvas_attrs_js_options_and_arrays():
    from case3.fact_ground import _scrub_html_bound, table_grid

    source = (
        "| Регион | Факт |\n"
        "| --- | --- |\n"
        "| Минск | 19850 |\n"
        "| Гомель | 14910 |\n"
        "| Брест | 11960 |\n"
        "| Витебск | 10290 |\n"
    )
    html = (
        "<canvas id='c2' width='1100' height='560'></canvas>"
        "<script>new Chart(document.getElementById('c2'),{"
        "type:'bar',data:{labels:['Минск','Гомель','Брест','Витебск'],"
        "datasets:[{data:[19850,14910,11960,10290]}]},"
        "options:{cutout:'60%',scales:{x:{ticks:{maxRotation:45}}}}});</script>"
    )
    cleaned = _scrub_html_bound(
        html,
        {"19850", "14910", "11960", "10290"},
        [],
        grid=table_grid(source),
    )
    assert "width='1100'" in cleaned
    assert "height='560'" in cleaned
    assert "cutout:'60%'" in cleaned
    assert "maxRotation:45" in cleaned
    assert "data: [19850,14910,11960,10290]" in cleaned or "data:[19850,14910,11960,10290]" in cleaned


def test_scrub_html_bound_allows_user_scenario_bindings_in_data():
    from case3.fact_ground import fact_context, ground_generated

    source = "| Регион | Факт |\n| --- | --- |\n| Гомель | 7544 |\n| Минск | 19850 |\n"
    intent = "покажи график с новым фактом Гомель 7994 и Минск 19850"
    html = (
        "<script>new Chart(c,{data:{labels:['Гомель','Минск'],"
        "datasets:[{data:[7994,19850]}]}});</script>"
    )
    _tex, out_charts, _figs, _diags, _dropped = ground_generated(
        "",
        [{"id": "cht_1", "html": html, "caption": "Сценарий Гомель 7994"}],
        [],
        [],
        source=source,
        intent=intent,
    )
    assert "7994" in out_charts[0]["html"]
    assert "19850" in out_charts[0]["html"]
    assert "null" not in out_charts[0]["html"]


def test_protect_keeps_full_tabular_and_never_unbalances_textbf():
    from case3.fact_ground import ground_generated

    source = "| Регион | Факт | План |\n| --- | --- | --- |\n| Гомель | 7544 | 8200 |\n"
    tex = (
        "\\documentclass{article}\n\\begin{document}\n"
        "\\textbf{Гомель показал 7544, выдумка 99999}.\n"
        "\\begin{tabularx}{\\textwidth}{lrr}\n"
        "Регион & Факт & Вып. \\\\\n"
        "Гомель & 7544 & 92,0\\% \\\\\n"
        "\\end{tabularx}\n"
        "\\begin{xltabular}{\\textwidth}{lr}\n"
        "Показатель & Откл. \\\\\n"
        "Гомель & -656 \\\\\n"
        "\\end{xltabular}\n"
        "\\end{document}\n"
    )
    out, _charts, _figs, _diags, _dropped = ground_generated(
        tex, [], [], [], source=source, intent="отчёт"
    )
    assert "Гомель & 7544 & 92,0\\%" in out
    assert "Гомель & -656" in out
    assert "99999" not in out
    assert out.count("{") == out.count("}")


def test_table_grid_keeps_minsk_variants_duplicates_and_fact_plan_derivs():
    from case3.fact_ground import table_grid

    source = (
        "| Регион | Факт |\n| --- | --- |\n| г. Минск | 120 |\n| Минская область | 85 |\n\n"
        "| Регион | План |\n| --- | --- |\n| г. Минск | 100 |\n\n"
        "## Производные\n\n"
        "Отклонение и выполнение (Факт − План, база 100%):\n"
        "- г. Минск: откл. +20, вып. 120%\n"
        "- Минская область: откл. -15, вып. 85%\n"
    )
    grid = table_grid(source)
    assert "минск" in grid.rows
    assert "120" in grid.rows["минск"]
    assert "85" in grid.rows["минск"]
    assert "100" in grid.rows["минск"]
    assert "20" in grid.rows["минск"]


def test_clause_allows_metadata_unsigned_delta_small_counts_and_verifiable_math():
    from case3.fact_ground import ground_generated

    source = (
        "## Заголовок\nОтчёт за 2025 год по состоянию на 1 февраля.\n\n"
        "| Регион | План | Факт | Отклонение |\n"
        "| --- | --- | --- | --- |\n"
        "| Гомельская | 8200 | 7544 | -656 |\n"
        "| Минская | 10000 | 10500 | +500 |\n\n"
        "## Производные\n\n"
        "- Гомельская — доля 41,8%, место 2\n"
        "- Минская — доля 58,2%, место 1\n"
    )
    tex = (
        "\\documentclass{article}\n\\begin{document}\n"
        "По Гомельской области в 2025 году дефицит составил 656.\n"
        "Если добавить резерв 450, факт вырастет (7544 + 450 = 7994), что составляет 97,5\\% от плана 8200.\n"
        "Выделены 5 регионов и топ-3 лидера.\n"
        "Суммарный вклад позиций 18,3\\% + 13,8\\% + 11,0\\% составляет 43,1\\%.\n"
        "\\end{document}\n"
    )
    extra_src = source + "\nДоля лидера 18,3%, второго 13,8%, третьего 11,0%."
    out, _charts, _figures, _diagrams, _dropped = ground_generated(
        tex,
        [],
        [],
        [],
        source=extra_src,
        intent="Допустим, для Гомельской выделили резерв 450",
    )
    assert "2025" in out
    assert "656" in out
    assert "7994" in out
    assert "97,5" in out
    assert "5 регионов" in out
    assert "топ-3" in out
    assert "43,1" in out


def test_table_grid_computes_all_rows_and_group_shares_even_when_compact() -> None:
    from case3.dashboard_source import derivative_block
    from case3.fact_ground import ground_generated, table_grid

    rows = [
        "| Округ | Инспекция | План | Факт |",
        "| --- | --- | --- | --- |",
    ]
    for i in range(1, 21):
        okrug = "Центральный" if i <= 10 else "Западный"
        rows.append(f"| {okrug} | Инспекция_{i:02d} | {100 * i} | {110 * i} |")
    table_md = "\n".join(rows)
    source = table_md + "\n\n## Производные\n\n" + derivative_block(table_md)
    grid = table_grid(source)
    # Compact mode (>16 rows) must still populate shares, ranks, and group shares in TableGrid
    assert "центральн" in grid.rows
    assert "западн" in grid.rows
    tex = (
        "\\documentclass{article}\n\\begin{document}\n"
        "На Центральный округ приходится 26,2\\% факта, тогда как на Западный — 73,8\\%.\n"
        "По Инспекция_18 отклонение составило +180 при выполнении 110,0\\%.\n"
        "\\end{document}\n"
    )
    out, _c, _f, _d, _dropped = ground_generated(tex, [], [], [], source=source, intent="отчёт")
    assert "тогда как на Западный — 73,8\\%" in out
    assert "+180" in out


def test_cross_shot_differences_and_comma_enumerations_survive_grounding() -> None:
    from case3.fact_ground import ground_generated

    source = (
        "===== Январь =====\n"
        "| Округ | Инспекция | План | Факт | Вып., % |\n"
        "| --- | --- | --- | --- | --- |\n"
        "| Центральный | ИМНС по г. Минску | 140 000,0 | 152 340,0 | 108,8% |\n"
        "| Восточный | ИМНС по Могилёвской области | 60 000,0 | 58 200,0 | 97,0% |\n"
        "| Северный | ИМНС по Витебской области | 68 000,0 | 64 500,0 | 94,9% |\n"
        "| Южный | ИМНС по Брестской области | 75 000,0 | 71 200,0 | 94,9% |\n\n"
        "===== Февраль =====\n"
        "| Округ | Инспекция | План | Факт | Вып., % |\n"
        "| --- | --- | --- | --- | --- |\n"
        "| Центральный | ИМНС по г. Минску | 280 000,0 | 310 500,0 | 110,9% |\n"
        "| Восточный | ИМНС по Могилёвской области | 120 000,0 | 117 600,0 | 98,0% |\n"
        "| Северный | ИМНС по Витебской области | 136 000,0 | 130 200,0 | 95,7% |\n"
        "| Южный | ИМНС по Брестской области | 150 000,0 | 145 000,0 | 96,7% |\n"
    )
    tex = (
        "\\documentclass{article}\n\\begin{document}\n"
        "Наибольший прирост за февраль обеспечила ИМНС по г. Минску (158\\,160,0 млн руб.), "
        "наименьший --- ИМНС по Могилёвской области (59\\,400,0 млн руб.).\n"
        "Зона риска --- три инспекции с выполнением ниже 100\\%: Витебская (95,7\\%), Брестская (96,7\\%) и Могилёвская (98,0\\%).\n"
        "\\end{document}\n"
    )
    out, _c, _f, _d, _dropped = ground_generated(tex, [], [], [], source=source, intent="отчёт")
    assert "158\\,160,0" in out
    assert "59\\,400,0" in out
    assert "Брестская (96,7\\%)" in out
    assert "Могилёвская (98,0\\%)" in out


def test_imns_multi_row_with_parenthetical_city_not_blocked_by_wrong_row_tokens() -> None:
    from case3.fact_ground import wrong_row_tokens

    source = (
        "| Инспекция | План | Факт |\n"
        "| --- | --- | --- |\n"
        "| ИМНС по г. Минску | 150 000,0 | 140 000,0 |\n"
        "| ИМНС по Центральному району (г. Минск) | 64 000,0 | 65 420,5 |\n"
        "| ИМНС по Советскому району (г. Минск) | 50 000,0 | 48 100,0 |\n"
    )
    ok_text = (
        "ИМНС по Центральному району (г. Минск): 65 420,5.\n"
        "ИМНС по г. Минску: 140 000,0; ИМНС по Советскому району (г. Минск): 48 100,0."
    )
    assert wrong_row_tokens(ok_text, source) == []
    bad_text = "ИМНС по Центральному району (г. Минск): 140 000,0."
    assert wrong_row_tokens(bad_text, source) == ["140 000,0"]


def test_verifies_math_two_step_what_if_formula() -> None:
    from case3.chat_turn import _filter_verifiable_stray, number_norms
    from case3.fact_ground import ground_generated

    source = (
        "| Инспекция | План | Факт |\n"
        "| --- | --- | --- |\n"
        "| Гомельская | 8200 | 7544 |\n"
    )
    intent = "Допустим, для Гомельской выделили резерв 450"
    # Intermediate 7994 is NOT stated — only (7544 + 450) / 8200 * 100 = 97.49%
    tex = (
        "\\documentclass{article}\n\\begin{document}\n"
        "Для Гомельской с учётом резерва 450 при плане 8200 выполнение составит 97,5\\%.\n"
        "\\end{document}\n"
    )
    out, _c, _f, _d, _dropped = ground_generated(
        tex, [], [], [], source=source, intent=intent
    )
    assert "97,5" in out

    # Also verify chat_turn's stray filter keeps 97,5% in chat answers
    chat_text = "С учётом резерва 450 при плане 8200 выполнение по Гомельской составит 97,5%."
    allowed = number_norms(source) | number_norms(intent)
    stray = _filter_verifiable_stray(
        chat_text, ["97,5%"], allowed, source, message_ok=number_norms(intent)
    )
    assert stray == []


def test_chart_computed_shares_survive_grounding() -> None:
    source = (
        "| Инспекция | План | Факт |\n"
        "| --- | --- | --- |\n"
        "| Альфа | 600 | 610 |\n"
        "| Бета | 400 | 390 |\n"
    )
    # Donut chart computes plan shares (60%, 40%) even without ## Производные
    html = (
        "<canvas id='c1' width='520' height='520'></canvas>"
        "<script>new Chart(document.getElementById('c1'),{"
        "type:'doughnut',data:{labels:['Альфа','Бета'],"
        "datasets:[{label:'Доля, %',data:[60,40]}]}});</script>"
    )
    _tex, charts, _figs, _diags, _dropped = ground_generated(
        "",
        [{"id": "cht_01", "type": "donut", "caption": "Доля в плане, %", "html": html}],
        [],
        [],
        source=source,
        intent="Построй круговую диаграмму долей плана",
    )
    out_html = charts[0]["html"]
    assert "null" not in out_html
    assert "60" in out_html
    assert "40" in out_html


def test_two_shot_dashboard_region_comparison_and_cross_row_sum_in_chat() -> None:
    from case3.chat_turn import _allowed_norms, _filter_verifiable_stray, stray_numbers
    from case3.dashboard_source import derivative_block
    from case3.fact_ground import wrong_row_tokens

    jan_tbl = (
        "| Код ИМНС | Область | Инспекция | План, тыс. руб. | Факт, тыс. руб. | Выполнение (%) | Плательщики |\n"
        "| --- | --- | --- | --- | --- | --- | --- |\n"
        "| 101 | г. Минск | ИМНС по Центральному району | 179 500,0 | 184 520,0 | 102,8% | 34 200 |\n"
        "| 201 | Минская область | ИМНС по Минскому району | 44 200,0 | 46 850,0 | 106,0% | 14 500 |\n"
        "| 202 | Минская область | ИМНС по Борисовскому району | 49 300,0 | 47 223,2 | 95,8% | 11 100 |\n"
        "| 301 | Гомельская область | ИМНС по Центральному району г. Гомеля | 76 000,0 | 76 410,8 | 100,5% | 16 400 |\n"
        "| 401 | Брестская область | ИМНС по г. Бресту | 47 000,0 | 47 056,4 | 100,1% | 10 000 |\n"
        "| 403 | Брестская область | ИМНС по Пинскому району | 12 200,0 | 10 790,0 | 88,4% | 2 840 |\n"
    )
    feb_tbl = (
        "| Код ИМНС | Область | Инспекция | План, тыс. руб. | Факт, тыс. руб. | Выполнение (%) | Плательщики |\n"
        "| --- | --- | --- | --- | --- | --- | --- |\n"
        "| 101 | г. Минск | ИМНС по Центральному району | 185 000,0 | 192 400,0 | 104,0% | 34 350 |\n"
        "| 201 | Минская область | ИМНС по Минскому району | 45 000,0 | 48 150,0 | 107,0% | 14 620 |\n"
        "| 202 | Минская область | ИМНС по Борисовскому району | 50 000,0 | 49 500,0 | 99,0% | 11 120 |\n"
        "| 301 | Гомельская область | ИМНС по Центральному району г. Гомеля | 78 000,0 | 79 560,0 | 102,0% | 16 450 |\n"
        "| 401 | Брестская область | ИМНС по г. Бресту | 49 000,0 | 49 980,0 | 102,0% | 10 050 |\n"
        "| 403 | Брестская область | ИМНС по Пинскому району | 13 000,0 | 11 610,0 | 89,3% | 2 850 |\n"
    )
    # Note: Just like pipeline.py when 2 shots are attached without pre-rendered ## Производные
    raw_two_shots = (
        "===== Поступления за январь 2025 года =====\n\n# Данные дашборда\n\n## Таблица PDF\n\n"
        + jan_tbl
        + "\n\n===== Поступления за февраль 2025 года =====\n\n# Данные дашборда\n\n## Таблица PDF\n\n"
        + feb_tbl
    )
    two_shots = raw_two_shots + "\n\n## Производные\n\n" + derivative_block(raw_two_shots)
    msg_compare = "Сравни фактические поступления за январь и февраль 2025 по областям"
    reply_compare = (
        "| Область | Январь, тыс. руб. | Февраль, тыс. руб. | Прирост, тыс. руб. | Темп роста, % |\n"
        "| --- | --- | --- | --- | --- |\n"
        "| г. Минск | 184 520,0 | 192 400,0 | +7 880,0 | +4,3% |\n"
        "| Минская область | 94 073,2 | 97 650,0 | +3 576,8 | +3,8% |\n"
        "| Гомельская область | 76 410,8 | 79 560,0 | +3 149,2 | +4,1% |\n"
        "| Брестская область | 57 846,4 | 61 590,0 | +3 743,6 | +6,5% |\n\n"
        "По Минской и Брестской областям совокупный факт в январе составил 151 919,6 тыс. руб., "
        "а в целом по четырём областям факт вырос с 412 850,4 до 431 200,0 тыс. руб.\n"
        "В Минской области (Минский и Борисовский районы) факт вырос с 94 073,2 до 97 650,0 тыс. руб."
    )
    allowed = _allowed_norms(two_shots, msg_compare, set())
    stray = _filter_verifiable_stray(
        reply_compare,
        stray_numbers(reply_compare, allowed),
        allowed,
        two_shots,
        message_ok=set(),
    )
    assert stray == []
    assert wrong_row_tokens(reply_compare, two_shots, msg_compare) == []

    # Separate sentence cross-row sum & difference where region names are NOT repeated in the sum sentence
    one_shot = jan_tbl + "\n## Производные\n" + derivative_block(jan_tbl)
    msg_sum = "Посчитай суммарный факт Гомельской и Брестской областей и на сколько Гомельская собрала больше Брестской?"
    reply_sum = (
        "- Гомельская область: 76 410,8 тыс. руб.\n"
        "- Брестская область: 57 846,4 тыс. руб.\n"
        "Суммарный факт двух областей составляет 134 257,2 тыс. руб.\n"
        "Разница между ними равна 18 564,4 тыс. руб."
    )
    allowed_one = _allowed_norms(one_shot, msg_sum, set())
    stray_sum = _filter_verifiable_stray(
        reply_sum,
        stray_numbers(reply_sum, allowed_one),
        allowed_one,
        one_shot,
        message_ok=set(),
    )
    assert stray_sum == []
    assert wrong_row_tokens(reply_sum, one_shot, msg_sum) == []

    # Real LLM output cases that triggered wrong_row_tokens or _without_stray:
    # 1) A single sentence without commas mentioning two regions + a cell from one of them
    # or a cross-row difference/ratio that happens to exist in source_ok (e.g. rank 2 or share):
    two_regions_clause = (
        "Минская область (94 073,2) опережает Гомельскую область (76 410,8) на 17 662,4 тыс. руб., "
        "а в Брестской области наибольший вклад дал г. Брест — 47 056,4 тыс. руб. при 10 790,0 у Пинского района."
    )
    assert wrong_row_tokens(two_regions_clause, two_shots, msg_compare) == []

    # 2) Separate bullet/sentence sum of 3 regions without repeating their individual numbers in that sentence:
    msg_three = "Какой суммарный факт по Минской, Гомельской и Брестской областям?"
    reply_three = "Суммарный факт по этим областям составил 228 330,4 тыс. руб."
    allowed_three = _allowed_norms(one_shot, msg_three, set())
    stray_three = _filter_verifiable_stray(
        reply_three,
        stray_numbers(reply_three, allowed_three),
        allowed_three,
        one_shot,
        message_ok=set(),
        user_question=msg_three,
    )
    assert stray_three == []
    assert wrong_row_tokens(reply_three, one_shot, msg_three) == []


def test_wrong_row_tokens_allows_share_column_in_table_with_share_header() -> None:
    from case3.dashboard_source import derivative_block
    from case3.fact_ground import wrong_row_tokens

    table = (
        "| Область | Сумма |\n"
        "| --- | --- |\n"
        "| Минская | 105 865,2 |\n"
        "| Гомельская | 94 073,0 |\n"
    )
    src = table + "\n## Производные\n" + derivative_block(table)
    table_reply = (
        "| Область | Сумма | Доля, % |\n"
        "| --- | --- | --- |\n"
        "| Минская | 105 865,2 | 52,9 |\n"
        "| Гомельская | 94 073,0 | 47,1 |"
    )
    assert wrong_row_tokens(table_reply, src, "покажи доли областей") == []
    assert wrong_row_tokens("Минская собрала 52,9.", src, "сколько собрала Минская") == ["52,9"]

