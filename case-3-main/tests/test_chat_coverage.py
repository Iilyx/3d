"""Chat edits that the rail already knew how to do."""

from pathlib import Path

from case3.chat_act import resolve_act
from case3.chat_revise import (
    _add_paragraph,
    _add_section,
    _caption,
    _delete_item,
    _paragraph_after,
    _restyle_structure,
    _rewrite,
    _rewrite_all,
)


def test_list_delete_cell_is_not_a_slide():
    act = resolve_act("убери кассу из списка", has_report=True)
    assert act.op == "delete_item"
    assert act.section == "кассу"


def test_second_paragraph_is_named():
    act = resolve_act("сделай второй абзац введения короче", has_report=True)
    assert act.op == "rewrite"
    assert act.slot == 2
    assert "введен" in act.section.casefold()
    assert act.brief == "tighter"


def test_user_paragraph_is_inserted():
    act = resolve_act(
        "добавь абзац во введение: Касса была тихой весь день.",
        has_report=True,
    )
    assert act.op == "add_paragraph"
    assert "введен" in act.section.casefold()
    assert "тихой" in act.title


def test_user_section_is_inserted():
    act = resolve_act(
        "добавь раздел Выводы: Касса закрылась без новой цифры.",
        has_report=True,
    )
    assert act.op == "add_section"
    assert act.section == "Выводы"
    assert "закрылась" in act.title


def test_caption_names_the_figure():
    act = resolve_act("подпись рисунка fig_01: Касса за день", has_report=True)
    assert act.op == "caption"
    assert act.section == "fig_01"
    assert act.title == "Касса за день"


def test_whole_report_is_one_act():
    act = resolve_act("сократи весь отчёт", has_report=True)
    assert act.op == "rewrite_all"
    assert act.brief == "tighter"


def test_deck_structure_is_named():
    act = resolve_act("смени структуру презентации на инвестора", has_deck=True)
    assert act.op == "restyle_structure"
    assert act.title == "investor"
    missing = resolve_act("смени структуру презентации", has_deck=True)
    assert missing.op == "ask"


_TEX = r"""
\documentclass{article}
\begin{document}
\section{Введение}
Первый абзац введения.

Второй абзац введения.
\section{Касса}
Один абзац кассы.
\begin{itemize}
\item касса молчит
\item зал открыт
\end{itemize}
\begin{figure}
\includegraphics{figures/fig_01.png}
\caption{Старая}
\label{fig:fig_01}
\end{figure}
\end{document}
"""


def test_ordinal_picks_the_second_paragraph(tmp_path: Path, monkeypatch):
    out = tmp_path / "out"
    out.mkdir()
    (out / "report.tex").write_text(_TEX, encoding="utf-8")
    assert _paragraph_after(_TEX, "Введение", 2)
    seen: dict = {}

    def edit(_out, index, *, text, formats):
        seen["index"] = index
        seen["text"] = text
        return {}

    monkeypatch.setattr("case3.paragraph_edit.edit_paragraph_in_run", edit)
    monkeypatch.setattr(
        "case3.chat_turn.draft_section",
        lambda **_kwargs: "Короче второй.",
    )
    from case3.chat_act import ChatAct

    say = _rewrite(
        out,
        "сделай второй абзац введения короче",
        ChatAct(kind="revise", op="rewrite", section="Введение", slot=2, brief="tighter"),
    )
    assert seen["text"] == "Короче второй."
    assert "Второй абзац" not in say or seen["index"] > 1
    first = _paragraph_after(_TEX, "Введение", 1)
    assert seen["index"] != first


def test_rewrite_section_touches_every_paragraph(tmp_path: Path, monkeypatch):
    out = tmp_path / "out"
    out.mkdir()
    (out / "report.tex").write_text(_TEX, encoding="utf-8")
    (out / "meta.json").write_text('{"source":""}', encoding="utf-8")
    currents: list[str] = []

    def draft(*, section, current, source, brief, user_text="", client=None):
        currents.append(current)
        return "Новый " + section + " " + str(len(currents))

    monkeypatch.setattr("case3.chat_turn.draft_section", draft)
    rebuilds: list[str] = []
    monkeypatch.setattr(
        "case3.run_rebuild.rebuild_run_docs",
        lambda *_a, **_k: rebuilds.append("pdf") or {},
    )
    from case3.chat_act import ChatAct

    say = _rewrite(
        out,
        "перепиши введение",
        ChatAct(kind="revise", op="rewrite", section="Введение", brief="clearer"),
    )
    tex = (out / "report.tex").read_text(encoding="utf-8")
    assert currents == ["Первый абзац введения.", "Второй абзац введения."]
    assert "Новый Введение 1" in tex
    assert "Новый Введение 2" in tex
    assert "Один абзац кассы." in tex
    assert rebuilds == ["pdf"]
    assert "2" in say
    assert "Введение" in say


def test_supplied_section_text_replaces_the_other_paragraphs(tmp_path: Path, monkeypatch):
    out = tmp_path / "out"
    out.mkdir()
    (out / "report.tex").write_text(_TEX, encoding="utf-8")
    (out / "meta.json").write_text('{"source":""}', encoding="utf-8")
    rebuilds: list[str] = []
    monkeypatch.setattr(
        "case3.run_rebuild.rebuild_run_docs",
        lambda *_a, **_k: rebuilds.append("pdf") or {},
    )
    from case3.chat_act import ChatAct

    say = _rewrite(
        out,
        "Перепиши раздел Введение: Касса была тихой весь день без второй мысли.",
        ChatAct(kind="revise", op="rewrite", section="Введение", brief="supplied"),
    )
    tex = (out / "report.tex").read_text(encoding="utf-8")
    assert "тихой весь день" in tex
    assert "Второй абзац введения" not in tex
    assert "Первый абзац введения" not in tex
    assert "Один абзац кассы." in tex
    assert rebuilds == ["pdf"]
    assert "Введение" in say


def test_delete_item_drops_only_the_named_line(tmp_path: Path, monkeypatch):
    out = tmp_path / "out"
    out.mkdir()
    (out / "report.tex").write_text(_TEX, encoding="utf-8")
    seen: dict = {}

    def edit(_out, index, *, items, formats):
        seen["index"] = index
        seen["items"] = items
        return {}

    monkeypatch.setattr("case3.list_edit.edit_list_in_run", edit)
    say = _delete_item(out, 0, "кассу")
    assert seen["items"] == ["зал открыт"]
    assert "касс" in say.casefold()


def test_caption_rewrites_the_figure(tmp_path: Path, monkeypatch):
    out = tmp_path / "out"
    out.mkdir()
    (out / "report.tex").write_text(_TEX, encoding="utf-8")
    (out / "meta.json").write_text("{}", encoding="utf-8")
    monkeypatch.setattr(
        "case3.run_rebuild.rebuild_run_docs",
        lambda *_a, **_k: {},
    )
    say = _caption(out, "fig_01", "Касса за день")
    tex = (out / "report.tex").read_text(encoding="utf-8")
    assert "Касса за день" in tex
    assert "Старая" not in tex
    assert "Подпись" in say


def test_added_paragraph_uses_the_user_text(tmp_path: Path, monkeypatch):
    out = tmp_path / "out"
    out.mkdir()
    (out / "report.tex").write_text(_TEX, encoding="utf-8")
    seen: dict = {}

    def insert(_out, *, text, after_paragraph_index=None, after_heading_index=None, formats=None):
        seen["text"] = text
        seen["after"] = after_paragraph_index
        return {}

    monkeypatch.setattr("case3.paragraph_edit.insert_paragraph_in_run", insert)
    say = _add_paragraph(out, "Введение", "Касса была тихой весь день.")
    assert seen["text"] == "Касса была тихой весь день."
    assert seen["after"] == _paragraph_after(_TEX, "Введение", 2)
    assert "Введение" in say


def test_added_section_lands_before_the_end(tmp_path: Path, monkeypatch):
    out = tmp_path / "out"
    out.mkdir()
    (out / "report.tex").write_text(_TEX, encoding="utf-8")
    (out / "meta.json").write_text("{}", encoding="utf-8")
    monkeypatch.setattr("case3.run_rebuild.rebuild_run_docs", lambda *_a, **_k: {})
    say = _add_section(out, "Выводы", "Касса закрылась без новой цифры.")
    tex = (out / "report.tex").read_text(encoding="utf-8")
    assert r"\section{Выводы}" in tex
    assert "закрылась" in tex
    assert tex.index("Выводы") < tex.index(r"\end{document}")
    assert "Выводы" in say


def test_whole_report_touches_every_section(tmp_path: Path, monkeypatch):
    out = tmp_path / "out"
    out.mkdir()
    (out / "report.tex").write_text(_TEX, encoding="utf-8")
    (out / "meta.json").write_text('{"source":""}', encoding="utf-8")
    names: list[str] = []

    def draft(*, section, current, source, brief, user_text="", client=None):
        names.append(section)
        assert brief == "tighter"
        return "Короче " + section

    monkeypatch.setattr("case3.chat_turn.draft_section", draft)
    rebuilds: list[str] = []
    monkeypatch.setattr(
        "case3.run_rebuild.rebuild_run_docs",
        lambda *_a, **_k: rebuilds.append("pdf") or {},
    )
    from case3.chat_act import ChatAct

    say = _rewrite_all(
        out,
        "сократи весь отчёт",
        ChatAct(kind="revise", op="rewrite_all", brief="tighter"),
    )
    tex = (out / "report.tex").read_text(encoding="utf-8")
    assert names == ["Введение", "Введение", "Касса"]
    assert tex.count("Короче Введение") == 2
    assert "Короче Касса" in tex
    assert "Второй абзац введения" not in tex
    assert rebuilds == ["pdf"]
    assert "Введение" in say and "Касса" in say


def test_structure_claims_the_deck(tmp_path: Path, monkeypatch):
    out = tmp_path / "out"
    out.mkdir()
    (out / "meta.json").write_text(
        '{"status":"ok","slides_status":"idle","slides_theme_pack":"atelier"}',
        encoding="utf-8",
    )
    kicked: list[str] = []
    monkeypatch.setattr(
        "case3.api_slides._kick_slides_thread",
        lambda run_id: kicked.append(run_id),
    )
    say = _restyle_structure("run1", out, "investor")
    meta = (out / "meta.json").read_text(encoding="utf-8")
    assert "investor" in meta
    assert kicked == ["run1"]
    assert "инвестор" in say.casefold()


def test_delete_section_drops_that_heading_and_keeps_the_next(tmp_path: Path, monkeypatch):
    from case3.chat_revise import _delete_section

    tex = (
        "\\documentclass{article}\n\\begin{document}\n"
        "\\section{Введение}\nКасса была тихой.\n"
        "\\subsection{Ночь}\nСмена кончилась.\n"
        "\\section{Выводы}\nДальше пусто.\n"
        "\\end{document}\n"
    )
    out = tmp_path / "out"
    out.mkdir()
    (out / "report.tex").write_text(tex, encoding="utf-8")
    (out / "meta.json").write_text("{}", encoding="utf-8")
    monkeypatch.setattr("case3.run_rebuild.rebuild_run_docs", lambda *_a, **_k: {})
    say = _delete_section(out, "Введение")
    got = (out / "report.tex").read_text(encoding="utf-8")
    assert "Введение" not in got
    assert "Ночь" not in got
    assert "Смена" not in got
    assert r"\section{Выводы}" in got
    assert r"\end{document}" in got
    assert "Введение" in say


def test_delete_subsection_leaves_the_parent(tmp_path: Path, monkeypatch):
    from case3.chat_revise import _delete_section

    tex = (
        "\\documentclass{article}\n\\begin{document}\n"
        "\\section{Введение}\nКасса была тихой.\n"
        "\\subsection{Ночь}\nСмена кончилась.\n"
        "\\section{Выводы}\nДальше пусто.\n"
        "\\end{document}\n"
    )
    out = tmp_path / "out"
    out.mkdir()
    (out / "report.tex").write_text(tex, encoding="utf-8")
    (out / "meta.json").write_text("{}", encoding="utf-8")
    monkeypatch.setattr("case3.run_rebuild.rebuild_run_docs", lambda *_a, **_k: {})
    _delete_section(out, "Ночь")
    got = (out / "report.tex").read_text(encoding="utf-8")
    assert r"\section{Введение}" in got
    assert "Касса" in got
    assert "Ночь" not in got
    assert "Смена" not in got
    assert r"\section{Выводы}" in got


def test_last_section_delete_keeps_the_file_and_says_so(tmp_path: Path, monkeypatch):
    from case3.chat_revise import _delete_section

    tex = (
        "\\documentclass{article}\n\\begin{document}\n"
        "\\section{Введение}\nКасса была 20.\n"
        "\\end{document}\n"
    )
    out = tmp_path / "out"
    out.mkdir()
    (out / "report.tex").write_text(tex, encoding="utf-8")
    (out / "meta.json").write_text("{}", encoding="utf-8")

    def boom(*_a, **_k):
        raise RuntimeError("docker latexmk failed\nNo pages of output.\n" + ("x" * 4000))

    monkeypatch.setattr("case3.run_rebuild.rebuild_run_docs", boom)
    say = _delete_section(out, "Введение")
    assert say == "Это последний раздел. Без него отчёт не соберётся. Текст остался как был."
    assert "Касса была 20." in (out / "report.tex").read_text(encoding="utf-8")
    assert "xxxx" not in say
