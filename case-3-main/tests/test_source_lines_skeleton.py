"""Sparse-fill must not dump meta-skeleton Source or prompt commands as the report body."""

from case3.generate import _source_lines_to_tex, fill_sparse_tex_with_source
from case3.tex_preamble import ensure_document_preamble
from case3.tex_preview import build_report_preview


def _region_table(n: int) -> str:
    lines = ["| Район | Сумма |", "| --- | --- |"]
    for i in range(1, n + 1):
        lines.append(f"| Район {i:02d} | {1000 + i} |")
    return "\n".join(lines)


def test_source_lines_drops_meta_framing_and_emoji_headings() -> None:
    src = (
        "Вот полный комплект исходных данных, структур и инструкций, "
        "которые вы можете использовать как «скелет» для создания отчета.\n"
        "\n"
        "Вы можете взять эти блоки и заполнить их текстом.\n"
        "\n"
        "### 📂 БЛОК 1: СТРУКТУРА ОТЧЕТА\n"
        "*Используйте эту структуру для создания оглавления.*\n"
        "* 1.1. Глобальный тренд.\n"
        "* 1.2. Специфика Беларуси.\n"
        "\n"
        "| Год | Рынок |\n"
        "| --- | --- |\n"
        "| 2024 | 30 |\n"
    )
    lines = _source_lines_to_tex(src)
    blob = "\n".join(lines)
    assert "полный комплект" not in blob
    assert "скелет" not in blob
    assert "Вы можете взять" not in blob
    assert "Используйте эту структуру" not in blob
    assert "📂" not in blob
    assert r"\begin{itemize}" in blob
    assert r"\item 1.1. Глобальный тренд." in blob
    assert r"\begin{tabularx}" in blob


def test_source_lines_strips_imperative_prompt_instructions() -> None:
    """192348Z regression: do not print 'Сгенерируй фото...' or 'Сделай полный отчёт...' in prose."""
    src = (
        "Отчёт по итогам года нашего IT-стартапа по автоматизации бухгалтерии.\n"
        "Ключевые метрики: 850 платящих компаний, регулярная выручка ARR 45 млн руб.\n"
        "Сгенерируй фото современного open-space офиса с молодыми программистами.\n"
        "Сделай полный отчёт с таблицами метрик, графиками долей и роста.\n"
    )
    lines = _source_lines_to_tex(src)
    blob = "\n".join(lines)
    assert "850 платящих компаний" in blob
    assert "Сгенерируй фото" not in blob
    assert "Сделай полный отчёт" not in blob


def test_fill_sparse_keeps_tables_not_meta_instructions() -> None:
    preamble = (
        r"\documentclass{article}"
        "\n"
        r"\begin{document}"
        "\n"
        r"\end{document}"
        "\n"
    )
    src = (
        "Вот «полный комплект» как скелет для отчета.\n"
        "### Данные\n"
        "| Год | M2 |\n"
        "| --- | --- |\n"
        "| 2023 | 26 |\n"
        "| 2024 | 30 |\n"
    )
    out = fill_sparse_tex_with_source(
        preamble, src, chart_ids=["cht_01"], figure_ids=[], diagram_ids=["dia_01"]
    )
    assert "полный комплект" not in out
    assert "скелет" not in out
    assert r"\begin{tabularx}" in out
    assert "%CASE3_CHART:cht_01%" in out
    assert "%CASE3_DIAG:dia_01%" in out


def test_short_region_table_stays_on_one_page_box() -> None:
    blob = "\n".join(_source_lines_to_tex(_region_table(6)))
    assert r"\begin{tabularx}" in blob
    assert r"\begin{xltabular}" not in blob
    assert "Район 06" in blob
    tex = (
        "\\documentclass{article}\n\\begin{document}\n"
        + blob
        + "\\end{document}\n"
    )
    tables = [
        block
        for block in build_report_preview(tex, run_id="t")["blocks"]
        if block.get("type") == "table"
    ]
    assert len(tables) == 1
    assert tables[0]["rows"][-1][0] == "Район 06"


def test_long_region_table_keeps_every_row_and_breaks_pages() -> None:
    blob = "\n".join(_source_lines_to_tex(_region_table(30)))
    assert "Район 01" in blob
    assert "Район 30" in blob
    assert r"\begin{xltabular}{\textwidth}{YY}" in blob
    assert r"\endhead" in blob
    assert r"\begin{tabularx}" not in blob
    tex = (
        "\\documentclass{article}\n\\begin{document}\n"
        + blob
        + "\\end{document}\n"
    )
    prepared = ensure_document_preamble(tex)
    assert r"\usepackage{xltabular}" in prepared
    tables = [
        block
        for block in build_report_preview(prepared, run_id="t")["blocks"]
        if block.get("type") == "table"
    ]
    assert len(tables) == 1
    assert tables[0]["headers"] == ["Район", "Сумма"]
    assert len(tables[0]["rows"]) == 30
    assert tables[0]["rows"][-1][0] == "Район 30"


def test_report_answer_keeps_a_row_past_the_old_page() -> None:
    from case3.chat_turn import _table_prose

    rows = [[f"Район {i:02d}", str(1000 + i)] for i in range(1, 31)]
    text = _table_prose({"headers": ["Район", "Сумма"], "rows": rows})
    assert "Район 30" in text
    assert "…" not in text
