"""Chat answers about the open report see its outline and the named section.

The report is not Source. A number that lives only in TeX must not survive
the answer.
"""

import json
from pathlib import Path

from case3.chat_turn import chat_report_block, report_context, try_chat_answer

_TEX = r"""
\documentclass{article}
\title{Касса за день}
\begin{document}
\maketitle
\section{Введение}
Касса была тихой.

Во второй строке тишина.
\section{Касса}
Выручка 77 за смену.
\end{document}
"""


class _Seq:
    def __init__(self, texts: list[str]) -> None:
        self.texts = list(texts)
        self.seen: list[str] = []

    def stream(self, **kwargs):
        self.seen.append(kwargs.get("user_text") or "")
        yield self.texts.pop(0)


def test_named_section_keeps_its_paragraphs_and_leaves_the_other_out():
    block = report_context(_TEX, "что во введении")
    assert "Открытый отчёт (не Source)." in block
    assert "- Введение" in block
    assert "- Касса" in block
    assert "Касса была тихой." in block
    assert "Во второй строке тишина." in block
    assert "Выручка 77" not in block


def test_plain_question_gets_the_outline_only():
    block = report_context(_TEX, "о чём этот документ")
    assert "- Введение" in block
    assert "- Касса" in block
    assert "Касса была тихой." not in block
    assert "Выручка 77" not in block


def test_missing_section_is_said_out_loud():
    block = report_context(_TEX, "что в разделе Марс")
    assert "Раздела «Марс» в отчёте нет." in block
    assert "- Введение" in block
    assert "Касса была тихой." not in block


def test_unique_heading_word_opens_that_section():
    block = report_context(_TEX, "что с кассой")
    assert "Выручка 77 за смену." in block
    assert "Касса была тихой." not in block


def test_memory_paste_does_not_pick_a_section():
    pasted = (
        "что во введении\n\n"
        "Разговор этого чата (не Source).\n"
        "Ход 1\n"
        "Запрос: что в разделе Марс\n"
        "Ответ: там пусто."
    )
    block = report_context(_TEX, pasted)
    assert "Касса была тихой." in block
    assert "Раздела «Марс»" not in block


def test_section_number_is_not_a_source_number():
    block = report_context(_TEX, "что в разделе Касса")
    client = _Seq(
        [
            "В разделе касса выручка 77.",
            "В разделе касса смена прошла, без новой цифры.",
        ]
    )
    spoken = try_chat_answer(
        "выручка 20",
        "что в разделе Касса",
        client=client,
        report=block,
    )
    assert "77" not in spoken
    assert "смена прошла" in spoken
    assert len(client.seen) == 2
    for prompt in client.seen:
        assert "Выручка 77 за смену." in prompt
        assert "Касса была тихой." not in prompt
        assert "Открытый отчёт (не Source)." in prompt
        assert "Повтор:" in prompt or prompt is client.seen[0]


def test_source_number_stays_when_the_section_is_open():
    block = report_context(_TEX, "что в разделе Касса")
    client = _Seq(["В кассе выручка 20."])
    spoken = try_chat_answer(
        "выручка 20",
        "что в разделе Касса",
        client=client,
        report=block,
    )
    assert spoken == "В кассе выручка 20."
    assert len(client.seen) == 1


def test_tied_headings_stay_an_outline():
    tex = r"""
\documentclass{article}
\begin{document}
\section{Касса бара}
Бар один.
\section{Касса зала}
Зал два.
\end{document}
"""
    block = report_context(tex, "что с кассой")
    assert "- Касса бара" in block
    assert "- Касса зала" in block
    assert "Бар один." not in block
    assert "Зал два." not in block


def test_subsection_stops_at_the_next_section():
    tex = r"""
\documentclass{article}
\begin{document}
\section{Результаты}
Общий итог.
\subsection{Методика}
Сбор вручную.
\section{Касса}
Другое место.
\end{document}
"""
    block = report_context(tex, "что в методике")
    assert "Сбор вручную." in block
    assert "Общий итог." not in block
    assert "Другое место." not in block


def test_report_on_disk_reaches_the_block_and_a_later_chat_does_not_hide_it(tmp_path: Path):
    report_id = "source_20261119T100000Z"
    chat_id = "source_20261119T110000Z"
    report_dir = tmp_path / "runs" / "out" / report_id
    chat_dir = tmp_path / "runs" / "out" / chat_id
    report_dir.mkdir(parents=True)
    chat_dir.mkdir(parents=True)
    (report_dir / "meta.json").write_text(
        json.dumps({"run_id": report_id, "output_mode": "report"}),
        encoding="utf-8",
    )
    (report_dir / "report.tex").write_text(_TEX, encoding="utf-8")
    (chat_dir / "meta.json").write_text(
        json.dumps(
            {
                "run_id": chat_id,
                "output_mode": "chat",
                "prior_run_id": report_id,
            }
        ),
        encoding="utf-8",
    )
    (chat_dir / "notes.tex").write_text(
        "\\documentclass{article}\n\\begin{document}\nчерновик\n\\end{document}\n",
        encoding="utf-8",
    )
    block = chat_report_block(tmp_path, chat_id, "что во введении")
    assert "Касса была тихой." in block
    assert "черновик" not in block


def test_named_section_keeps_a_long_table():
    rows = "\n".join(f"РЯД{i:02d} & {i} \\\\" for i in range(1, 11))
    tex = (
        "\\documentclass{article}\n\\begin{document}\n"
        "\\section{Города}\n"
        "\\begin{table}\n\\caption{Список}\n\\begin{tabular}{ll}\n"
        "Город & Люди \\\\\n"
        f"{rows}\n"
        "\\end{tabular}\n\\end{table}\n"
        "\\end{document}\n"
    )
    block = report_context(tex, "что в разделе Города")
    assert "РЯД09" in block
    assert "РЯД10" in block
