"""Dashboard screen (Qwen) + born-digital table PDF → one markdown source."""

from __future__ import annotations

from pathlib import Path

import pytest

from case3 import prompts
from case3.dashboard_source import (
    DashboardSourceError,
    choose_grids,
    join_page_tables,
    dashboard_title,
    note_closed_month,
    parse_dashboard,
    prefer_ruled_tables,
    read_dashboard_png,
    strip_screen_table,
    table_block,
    words_to_rows,
)


def test_table_keeps_russian_headers_duplicate_numbers_and_spaces() -> None:
    md, note = table_block(
        [
            ["Поступления за январь 2025", "", "", "", ""],
            [
                "Наименование платежа",
                "Вид бюджета",
                "Факт (руб.)",
                "План (руб.)",
                "Выполнение плана (%)",
            ],
            ["НДС", "Республиканский", "142 597,4", "100,0", "17,8%"],
            ["НДС", "Местный", "100,0", "100,0", "8,6%"],
        ]
    )
    assert md.startswith("## Поступления за январь 2025")
    assert "| Наименование платежа | Вид бюджета | Факт (руб.) |" in md
    assert "142 597,4" in md
    assert md.count("100,0") == 3
    assert "17,8%" in md
    assert note is None


def test_pipe_in_a_cell_is_escaped() -> None:
    md, _note = table_block([["A|B", "n"], ["x", "1"]])
    assert r"A\|B" in md
    assert "| A|B |" not in md


def test_overwide_table_is_cut_and_noted() -> None:
    header = [f"c{i}" for i in range(65)]
    row = [str(i) for i in range(65)]
    md, note = table_block([header, row])
    assert "| c63 |" in md
    assert "| c64 |" not in md
    assert note is not None
    assert "65" in note
    assert "Таблица обрезана" in md
    assert "65" in md


def test_ruled_grid_beats_a_noisier_text_split() -> None:
    ruled = [[["Налог", "Факт"], ["НДС", "10"]]]
    noisy = [
        [["Налог", "Факт"], ["НДС", "10"], ["10", "10"], ["11", "12"]],
    ]
    chosen = prefer_ruled_tables(ruled, noisy)
    assert chosen == ruled


def test_word_positions_keep_spaced_numbers_and_a_wrapped_header() -> None:
    rows = words_to_rows(_pivot_words())
    assert rows[0] == [
        "Наименование платежа",
        "Вид бюджета",
        "ИМНС",
        "Факт (руб.)",
        "План (руб.)",
        "Выполнение плана (%)",
        "Выполнение плана (руб.)",
    ]
    assert rows[1] == [
        "Налог на добавленную стоимость, всего",
        "Республиканский",
        "216 ИМНС по Пинскому р-ну",
        "105 865,2",
        "94 073,0",
        "-20,7%",
        "139 289,1",
    ]
    assert rows[2][0] == ""
    assert rows[2][1] == "Консолидированный"
    assert rows[2][3] == "142 597,4"


def test_split_word_grid_loses_to_columns_from_positions() -> None:
    text = [
        [
            ["Налог", "ИМНС", "по", "105", "865,2", "94", "073,0"],
            ["НДС", "216", "ИМНС", "142", "597,4", "120", "000,0"],
        ]
    ]
    word = [
        [
            ["Наименование платежа", "ИМНС", "Факт (руб.)", "План (руб.)"],
            ["Налог на добавленную стоимость, всего", "216 ИМНС по Пинскому р-ну", "105 865,2", "94 073,0"],
        ]
    ]
    assert choose_grids([], word, text) is word


def test_paperclip_pdf_keeps_a_wide_grid_and_a_repeated_neighbor(tmp_path: Path) -> None:
    from case3.source_ingest import file_to_markdown

    path = tmp_path / "wide.pdf"
    header = [f"c{i}" for i in range(14)]
    row = ["77", "77"] + [str(i) for i in range(12)]
    _write_grid_pdf(path, [header, row], caption="Wide")
    markdown = file_to_markdown(path).markdown
    assert "| c13 |" in markdown
    assert markdown.count("77") >= 2
    assert "truncated" not in markdown


def test_two_region_pdf_carries_the_computed_share(tmp_path: Path) -> None:
    path = tmp_path / "regions.pdf"
    _write_grid_pdf(
        path,
        [["Region", "Sum"], ["Minsk", "60"], ["Gomel", "40"]],
        caption="Regions",
    )
    result = parse_dashboard(pdf=path)
    assert "## Производные" in result.markdown
    assert "Minsk" in result.markdown
    assert "60%" in result.markdown
    assert "40%" in result.markdown


def test_open_pivot_pdf_keeps_the_spaced_number(tmp_path: Path) -> None:
    path = tmp_path / "open.pdf"
    _write_open_pivot(path)
    result = parse_dashboard(pdf=path)
    assert "105 865,56" in result.markdown
    assert "| 105 | 865,56 |" not in result.markdown
    assert "94,1" in result.markdown


def test_wider_text_grid_beats_merged_ruled_columns() -> None:
    ruled = [
        [
            ["Налог", "Вид", "Факт (руб.) План (руб.)"],
            ["НДС", "Респ", "105 865,2 94 073,0"],
        ]
    ]
    text = [
        [
            ["Налог", "Вид", "Факт", "План"],
            ["НДС", "Респ", "105 865,2", "94 073,0"],
        ]
    ]
    assert prefer_ruled_tables(ruled, text) is text


def test_png_miss_keeps_the_pdf_table(tmp_path: Path) -> None:
    path = tmp_path / "one.pdf"
    _write_grid_pdf(
        path,
        [["Tax", "Fact"], ["VAT", "10"]],
        caption="Payments table for the dashboard export",
    )

    def boom(_raw: bytes) -> str:
        raise RuntimeError("qwen down")

    result = parse_dashboard(png=_tiny_png(), pdf=path, vision=boom)
    assert "VAT" in result.pdf_markdown
    assert result.png_markdown == ""
    assert any("qwen down" in note for note in result.warnings)
    assert "## Таблица PDF" in result.markdown
    assert "## Экран" not in result.markdown


def test_continuation_page_appends_under_the_same_header() -> None:
    header = ["Налог", "Факт"]
    page1 = [header, ["НДС", "10"]]
    page2 = [["Повтор заголовка страницы", ""], header, ["Акциз", "20"]]
    other = [["Регион", "Доля"], ["Брест", "31,8%"]]
    joined = join_page_tables([[page1], [page2, other]])
    assert joined[0] == [header, ["НДС", "10"], ["Акциз", "20"]]
    assert joined[1][0] == ["Регион", "Доля"]


def test_continuation_page_without_repeated_header_and_single_row_total() -> None:
    header = ["Регион", "План", "Факт"]
    page1 = [header, ["Минск", "100", "110"], ["Брест", "80", "85"]]
    page2 = [["Гомель", "90", "80"]]
    page3 = [["Итого", "270", "275"]]
    joined = join_page_tables([[page1], [page2], [page3]])
    assert len(joined) == 1
    assert joined[0] == [
        header,
        ["Минск", "100", "110"],
        ["Брест", "80", "85"],
        ["Гомель", "90", "80"],
        ["Итого", "270", "275"],
    ]


def test_pdf_keeps_every_column_and_the_line_above_the_grid(tmp_path: Path) -> None:
    header = [f"c{i}" for i in range(14)]
    row = ["1 234,56" if i == 0 else ("77" if i in (1, 2) else str(i)) for i in range(14)]
    path = tmp_path / "wide.pdf"
    _write_grid_pdf(path, [header, row], caption="January 2025 payments")
    result = parse_dashboard(pdf=path)
    assert "January 2025 payments" in result.markdown
    assert "1 234,56" in result.markdown
    assert "| c13 |" in result.markdown
    assert "| 77 | 77 |" in result.markdown
    assert result.pdf_table_count == 1
    assert result.pdf_numeric_cells >= 14
    assert "## Таблица PDF" in result.markdown
    assert "## Экран" not in result.markdown
    assert result.warnings == []


def test_scan_pdf_is_refused(tmp_path: Path) -> None:
    path = tmp_path / "blank.pdf"
    _write_blank_pdf(path)
    with pytest.raises(DashboardSourceError) as caught:
        parse_dashboard(pdf=path)
    assert caught.value.code == "scan_pdf"


def test_png_vision_text_becomes_the_screen_section() -> None:
    seen: list[bytes] = []

    def vision(raw: bytes) -> str:
        seen.append(raw)
        return "```markdown\n## Заголовок и фильтры\n\nБрестская область\n```"

    result = parse_dashboard(png=_tiny_png(), vision=vision)
    assert seen and seen[0].startswith(b"\x89PNG")
    assert "Брестская область" in result.markdown
    assert "```" not in result.markdown
    assert "## Экран" in result.markdown
    assert "## Таблица PDF" not in result.markdown
    assert result.png_markdown.startswith("## Заголовок")


def test_png_and_pdf_land_in_one_document(tmp_path: Path) -> None:
    path = tmp_path / "one.pdf"
    _write_grid_pdf(
        path,
        [["Tax", "Fact"], ["VAT", "10"]],
        caption="Payments table for the dashboard export",
    )
    result = parse_dashboard(
        png=_tiny_png(),
        pdf=path,
        vision=lambda _raw: "Карточка 100%",
    )
    assert result.markdown.index("## Экран") < result.markdown.index("## Таблица PDF")
    assert "Карточка 100%" in result.png_markdown
    assert "VAT" in result.pdf_markdown
    assert "Карточка 100%" in result.markdown and "VAT" in result.markdown


def test_missing_files_and_bad_bytes() -> None:
    with pytest.raises(DashboardSourceError) as missing:
        parse_dashboard()
    assert missing.value.code == "missing_input"
    with pytest.raises(DashboardSourceError) as bad_pdf:
        parse_dashboard(pdf=b"hello")
    assert bad_pdf.value.code == "bad_pdf"
    with pytest.raises(DashboardSourceError) as bad_png:
        parse_dashboard(png=b"not-a-png", vision=lambda _raw: "x")
    assert bad_png.value.code == "bad_png"


def test_oversize_pdf_stops_before_parse(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("case3.dashboard_source.MAX_PDF_BYTES", 8)
    with pytest.raises(DashboardSourceError) as caught:
        parse_dashboard(pdf=b"%PDF-1.4\n" + b"x" * 20)
    assert caught.value.code == "too_large"


def test_dashboard_prompt_tells_qwen_not_to_invent() -> None:
    text = prompts.load("dashboard_png")
    assert "не разобрать" in text
    assert "markdown" in text.lower()
    assert "Не округляй" in text
    assert "нет видимых фильтров" in text
    assert "ИМНС" not in text
    assert "Таблицу на экране" not in text
    assert "не читаешь" in text


def test_png_without_pdf_keeps_the_wide_table() -> None:
    wide = "\n".join(
        [
            "## Фильтры",
            "",
            "| Фильтр | Выбрано |",
            "| --- | --- |",
            "| Режим | Общие данные |",
            "",
            "## Таблица",
            "",
            "| Наименование | Вид | ИМНС | Факт | План | Процент |",
            "| --- | --- | --- | --- | --- | --- |",
            "| НДС | Респ | 216 | 105 865,2 | 94 073,0 | -20,7% |",
        ]
    )
    result = parse_dashboard(png=_tiny_png(), vision=lambda _raw: wide)
    assert "105 865,2" in result.markdown
    assert "Наименование" in result.markdown
    assert "Общие данные" in result.markdown
    assert "## Таблица PDF" not in result.markdown


def test_png_beside_pdf_still_drops_the_screen_table(tmp_path: Path) -> None:
    path = tmp_path / "one.pdf"
    _write_grid_pdf(
        path,
        [["Tax", "Fact"], ["VAT", "10"]],
        caption="Payments table for the dashboard export",
    )
    wide = "\n".join(
        [
            "| Наименование | Вид | ИМНС | Факт | План | Процент |",
            "| --- | --- | --- | --- | --- | --- |",
            "| НДС | Респ | 216 | 105 865,2 | 94 073,0 | -20,7% |",
        ]
    )
    result = parse_dashboard(png=_tiny_png(), pdf=path, vision=lambda _raw: wide)
    assert "105 865,2" not in result.markdown
    assert "VAT" in result.markdown


def test_screen_reading_drops_the_green_table_and_keeps_the_cards() -> None:
    raw = "\n".join(
        [
            "## Фильтры",
            "",
            "| Фильтр | Выбрано |",
            "| --- | --- |",
            "| Режим | Общие данные |",
            "| Детализация | Детализация |",
            "| Код и название ИМНС | All |",
            "",
            "## Карточки",
            "",
            "| Показатель | Сумма | Доля |",
            "| --- | --- | --- |",
            "| Консолидированный бюджет | 722 087,17 | 100,0% |",
            "",
            "## Таблица на экране",
            "",
            "| Наименование | Вид | ИМНС | Факт | План | Процент | Руб |",
            "| --- | --- | --- | --- | --- | --- | --- |",
            "| НДС | Респ | 216 | 105 865,2 | 94 073,0 | -20,7% | 139 289,1 |",
        ]
    )
    cleaned = strip_screen_table(raw)
    assert "105 865,2" not in cleaned
    assert "Таблица на экране" not in cleaned
    assert "Общие данные" in cleaned
    assert "722 087,17" in cleaned
    assert "All" in cleaned


def test_png_only_reader_asks_for_the_payment_table() -> None:
    class _Fake:
        def complete(self, *, system: str, user_text: str, images=None, **_kwargs):
            assert "единственный источник" in system
            assert "не читаешь" not in system
            assert images and images[0][0] == "dashboard"
            return "| A | B | C | D | E |\n| --- | --- | --- | --- | --- |\n| 1 | 2 | 3 | 4 | 5 |"

    md = read_dashboard_png(_tiny_png(), client=_Fake(), keep_table=True)
    assert "1" in md and "5" in md


def test_qwen_reader_sends_the_png_and_the_prompt() -> None:
    class _Fake:
        def complete(self, *, system: str, user_text: str, images=None, **_kwargs):
            assert "не разобрать" in system
            assert images and images[0][0] == "dashboard"
            assert str(images[0][1]).startswith("data:image/png;base64,")
            assert "дашборд" in user_text.lower()
            return "Фильтр: все"

    md = read_dashboard_png(_tiny_png(), client=_Fake())
    assert md == "Фильтр: все"


def _tiny_png() -> bytes:
    import struct
    import zlib

    def chunk(tag: bytes, data: bytes) -> bytes:
        return (
            struct.pack(">I", len(data))
            + tag
            + data
            + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
        )

    ihdr = struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0)
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", ihdr)
        + chunk(b"IDAT", zlib.compress(b"\x00\x00\x00\x00"))
        + chunk(b"IEND", b"")
    )


_FEBRUARY_SCREEN = """\
## Заголовок
Поступления за январь 2025 года (с нарастающим итогом)

## Фильтры

| Фильтр | Выбрано |
| --- | --- |
| Дата | на 1 февраля |
| Год | 2025 |
"""

_JANUARY_TITLE = """\
# Данные дашборда

## Экран

## Заголовок
Поступления за январь 2025 года (с нарастающим итогом)

## Карточки
Итог: факт 5,83 млн. руб.
"""


def test_screen_heading_becomes_the_dashboard_name() -> None:
    assert (
        dashboard_title(_FEBRUARY_SCREEN)
        == "Поступления за январь 2025 года"
    )
    assert dashboard_title("# Данные дашборда\n\n## Экран\n\nкарточка\n") == ""


def test_february_filter_is_noted_as_january_receipts() -> None:
    noted = note_closed_month(_FEBRUARY_SCREEN)
    assert "закрывает предыдущий месяц" in noted
    assert "феврал" in noted.casefold()
    assert "январ" in noted.casefold()
    assert note_closed_month(noted) == noted


def test_february_question_uses_january_receipts_already_in_the_text() -> None:
    from case3.chat_turn import _user_block

    block = _user_block(_JANUARY_TITLE, "разбери поступления за февраль 2025")
    assert "закрывает предыдущий месяц" in block
    assert "5,83" in block


def test_a_later_month_is_not_called_the_closed_month() -> None:
    assert "закрывает предыдущий месяц" not in note_closed_month(
        _JANUARY_TITLE,
        "разбери поступления за март 2025",
    )
    older = "## Заголовок\nПоступления за январь 2024 года\n"
    assert "закрывает предыдущий месяц" not in note_closed_month(
        older,
        "разбери февраль 2025",
    )


def test_december_closes_on_the_first_of_january() -> None:
    screen = """\
## Заголовок
Поступления за декабрь 2025 года (с нарастающим итогом)

## Фильтры

| Фильтр | Выбрано |
| --- | --- |
| Дата | на 1 января |
| Год | 2026 |
"""
    noted = note_closed_month(screen)
    assert "январ" in noted.casefold()
    assert "декабр" in noted.casefold()
    assert "2026" in noted
    assert "2025" in noted


def test_two_months_on_a_chart_are_not_a_filter_lag() -> None:
    screen = """\
## Заголовок
Выручка

## Фильтры

| Фильтр | Выбрано |
| --- | --- |
| Год | 2025 |

## График или карта
Столбцы за январь и февраль.
"""
    assert note_closed_month(screen) == screen.strip()
    assert "закрывает предыдущий месяц" not in note_closed_month(
        screen,
        "что было в феврале",
    )


def test_parse_dashboard_keeps_the_closed_month_note() -> None:
    result = parse_dashboard(png=_tiny_png(), vision=lambda _raw: _FEBRUARY_SCREEN)
    assert "закрывает предыдущий месяц" in result.markdown
    assert "5,83" not in result.markdown or "январ" in result.markdown.casefold()


def test_prompts_tell_the_model_the_filter_closes_the_previous_month() -> None:
    chat = prompts.load("chat_answer")
    assert "предыдущий месяц" in chat
    assert "не отказывайся" in chat
    screen = prompts.load("dashboard_png").casefold()
    only = prompts.load("dashboard_png_only").casefold()
    assert "не подгоняй заголовок под фильтр" in screen
    assert "не подгоняй заголовок под фильтр" in only


def _word(text: str, x0: float, x1: float, top: float) -> dict[str, float | str]:
    return {"text": text, "x0": x0, "x1": x1, "top": top, "bottom": top + 8}


def _pivot_words() -> list[dict[str, float | str]]:
    """Positions copied from a Stimulsoft-like pivot: wrapped header, right-aligned sums."""
    words: list[dict[str, float | str]] = []

    def add(top: float, items: list[tuple[str, float, float]]) -> None:
        for text, x0, x1 in items:
            words.append(_word(text, x0, x1, top))

    add(78, [
        ("Наименование", 32, 100),
        ("Вид", 250, 270),
        ("ИМНС", 360, 390),
        ("Факт", 470, 500),
        ("(руб.)", 502, 545),
        ("План", 580, 610),
        ("(руб.)", 612, 655),
        ("Выполнение", 700, 760),
        ("Выполнение", 800, 860),
    ])
    add(88, [
        ("платежа", 32, 70),
        ("бюджета", 250, 300),
        ("плана", 700, 735),
        ("(%)", 737, 760),
        ("плана", 800, 835),
        ("(руб.)", 837, 880),
    ])
    add(112, [
        ("Налог", 32, 58),
        ("на", 60, 72),
        ("добавленную", 74, 140),
        ("стоимость,", 142, 190),
        ("всего", 192, 220),
        ("Республиканский", 250, 330),
        ("216", 360, 378),
        ("ИМНС", 380, 410),
        ("по", 412, 424),
        ("Пинскому", 426, 470),
        ("р-ну", 472, 500),
        ("105", 530, 552),
        ("865,2", 554, 575),
        ("94", 630, 648),
        ("073,0", 650, 670),
        ("-20,7%", 720, 770),
        ("139", 840, 862),
        ("289,1", 864, 890),
    ])
    add(134, [
        ("Консолидированный", 250, 345),
        ("216", 360, 378),
        ("ИМНС", 380, 410),
        ("по", 412, 424),
        ("Пинскому", 426, 470),
        ("р-ну", 472, 500),
        ("142", 530, 552),
        ("597,4", 554, 575),
        ("120", 625, 648),
        ("000,0", 650, 670),
        ("17,6%", 730, 770),
        ("22", 850, 862),
        ("597,4", 864, 890),
    ])
    return words


def _write_open_pivot(path: Path) -> None:
    """Horizontal rules only. '105' and '865,56' are separate text objects."""
    ops = [
        "0.6 w",
        "36 80 m 360 80 l S",
        "36 60 m 360 60 l S",
        "36 40 m 360 40 l S",
        "BT /F1 8 Tf",
        "1 0 0 1 40 66 Tm (Name) Tj",
        "1 0 0 1 180 66 Tm (Fact) Tj",
        "1 0 0 1 280 66 Tm (Plan) Tj",
        "1 0 0 1 40 46 Tm (VAT) Tj",
        "1 0 0 1 168 46 Tm (105) Tj",
        "1 0 0 1 186 46 Tm (865,56) Tj",
        "1 0 0 1 280 46 Tm (94,1) Tj",
        "ET",
    ]
    _finish_pdf(path, "\n".join(ops).encode("latin-1"), width=400, height=140)


def _write_blank_pdf(path: Path) -> None:
    stream = b"q Q"
    _finish_pdf(path, stream, width=200, height=200)


def _write_grid_pdf(
    path: Path,
    rows: list[list[str]],
    *,
    caption: str = "",
) -> None:
    cols = max(len(row) for row in rows)
    col_w = 70
    row_h = 18
    margin = 36
    caption_h = 22 if caption else 0
    width = margin * 2 + col_w * cols
    height = margin * 2 + caption_h + row_h * len(rows)
    ops: list[str] = ["0.6 w"]
    top = margin + row_h * len(rows)
    for r in range(len(rows) + 1):
        y = margin + r * row_h
        ops.append(f"{margin} {y} m {margin + col_w * cols} {y} l S")
    for c in range(cols + 1):
        x = margin + c * col_w
        ops.append(f"{x} {margin} m {x} {top} l S")
    ops.append("BT /F1 8 Tf")
    if caption:
        ops.append(f"1 0 0 1 {margin} {top + 8} Tm ({_pdf_text(caption)}) Tj")
    for ri, row in enumerate(rows):
        for ci, cell in enumerate(row):
            x = margin + ci * col_w + 3
            y = margin + (len(rows) - ri - 1) * row_h + 5
            ops.append(f"1 0 0 1 {x} {y} Tm ({_pdf_text(cell)}) Tj")
    ops.append("ET")
    _finish_pdf(path, "\n".join(ops).encode("latin-1"), width=width, height=height)


def _pdf_text(value: str) -> str:
    return (
        value.replace("\\", "\\\\")
        .replace("(", "\\(")
        .replace(")", "\\)")
    )


def _finish_pdf(path: Path, stream: bytes, *, width: int, height: int) -> None:
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        (
            f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 {width} {height}] "
            f"/Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>"
        ).encode("ascii"),
        b"<< /Length " + str(len(stream)).encode("ascii") + b" >>\nstream\n" + stream + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    out = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for index, body in enumerate(objects, start=1):
        offsets.append(len(out))
        out += f"{index} 0 obj\n".encode("ascii") + body + b"\nendobj\n"
    xref = len(out)
    out += f"xref\n0 {len(objects) + 1}\n".encode("ascii")
    out += b"0000000000 65535 f \n"
    for offset in offsets[1:]:
        out += f"{offset:010d} 00000 n \n".encode("ascii")
    out += (
        f"trailer << /Size {len(objects) + 1} /Root 1 0 R >>\n"
        f"startxref\n{xref}\n%%EOF\n"
    ).encode("ascii")
    path.write_bytes(out)
