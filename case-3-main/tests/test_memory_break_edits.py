"""Adversarial tests: chat memory must survive undo/redo and fuzzy word edits."""

import json
from pathlib import Path

from case3.chat_revise import try_chat_revise


def _report_chain(tmp_path: Path, *, section: str = "Введение") -> tuple[str, str, Path, Path]:
    report = "source_20261118T100000Z"
    chat = "source_20261118T110000Z"
    report_dir = tmp_path / "runs" / "out" / report
    chat_dir = tmp_path / "runs" / "out" / chat
    report_dir.mkdir(parents=True)
    chat_dir.mkdir(parents=True)
    (report_dir / "note.tex").write_text(f"\\section{{{section}}}\nБыло 10.\n", encoding="utf-8")
    (report_dir / "meta.json").write_text(
        json.dumps(
            {
                "run_id": report,
                "output_mode": "report",
                "artifacts": {"pdf": "report.pdf"},
                "last_edit": {"op": "rewrite", "section": section},
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    (chat_dir / "meta.json").write_text(
        json.dumps(
            {"run_id": chat, "prior_run_id": report, "output_mode": "chat"},
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    return report, chat, report_dir, chat_dir


_TABLE_TEX = """\\documentclass{article}
\\begin{document}
\\begin{table}
\\caption{Города}
\\begin{tabular}{ll}
Город & Люди \\\\
Гомель & 10 \\\\
\\end{tabular}
\\end{table}
\\begin{itemize}
\\item касса была пустой
\\item доля рынка
\\end{itemize}
\\end{document}
"""


def _single_report(tmp_path: Path) -> tuple[str, Path]:
    report = "source_20261118T100000Z"
    out = tmp_path / "runs" / "out" / report
    out.mkdir(parents=True)
    (out / "note.tex").write_text(_TABLE_TEX, encoding="utf-8")
    (out / "meta.json").write_text(
        json.dumps(
            {"run_id": report, "output_mode": "report", "artifacts": {"pdf": "report.pdf"}},
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    return report, out


def test_undo_redo_then_shorter_keeps_original_section(tmp_path: Path, monkeypatch):
    """Attack 1: undo → redo → «короче» must still target the first section."""
    report, chat, report_dir, _chat_dir = _report_chain(tmp_path)
    monkeypatch.setattr("case3.run_undo.apply_undo", lambda *a, **k: {})
    monkeypatch.setattr("case3.run_undo.apply_redo", lambda *a, **k: {})
    seen: dict[str, str] = {}

    def fake_rewrite(out_dir: Path, text: str, act) -> str:
        seen["section"] = act.section
        return "Переписал раздел «Введение» по документам. Новых чисел нет."

    monkeypatch.setattr("case3.chat_revise._rewrite", fake_rewrite)

    undone = try_chat_revise("отмени", chat, root=tmp_path)
    assert undone is not None and undone["op"] == "undo"
    from case3.chat_memory import newest_edit

    found = newest_edit(tmp_path, chat)
    assert found.get("section") == "Введение"
    assert found.get("op") == "undo"
    head_meta = json.loads((_chat_dir / "meta.json").read_text(encoding="utf-8"))
    report_meta = json.loads((report_dir / "meta.json").read_text(encoding="utf-8"))
    assert [note.get("user") for note in head_meta.get("dialogue") or []] == ["отмени"]
    assert "dialogue" not in report_meta

    redone = try_chat_revise("верни правку", chat, root=tmp_path)
    assert redone is not None and redone["op"] == "redo"

    result = try_chat_revise("короче", chat, root=tmp_path)
    assert result is not None and result["op"] == "rewrite"
    assert seen.get("section") == "Введение"


def test_table_cell_genitive_declension_replaces_row(tmp_path: Path, monkeypatch):
    """Attack 2: «Гомеля» in the user phrase must hit cell «Гомель»."""
    report, out = _single_report(tmp_path)
    seen: dict[str, object] = {}

    def fake_edit(out_dir, index, *, caption, headers, rows, formats):
        seen["rows"] = rows

    monkeypatch.setattr("case3.table_edit.edit_table_in_run", fake_edit)
    phrase = "в таблице замени Гомеля на Брест"
    result = try_chat_revise(phrase, report, root=tmp_path)
    assert result is not None
    assert result["op"] == "replace_cell"
    assert "нет" not in result["chat"].casefold()
    assert seen["rows"] == [["Брест", "10"]]


def test_list_replace_swaps_one_word_inside_long_item(tmp_path: Path, monkeypatch):
    """Attack 3: only the matched word changes inside a longer list item."""
    report, out = _single_report(tmp_path)
    seen: dict[str, object] = {}

    def fake_edit(out_dir, index, *, items, ordered=None, formats=None):
        seen["items"] = items

    monkeypatch.setattr("case3.list_edit.edit_list_in_run", fake_edit)
    phrase = "в списке замени кассу на выручку"
    result = try_chat_revise(phrase, report, root=tmp_path)
    assert result is not None and result["op"] == "replace_item"
    assert seen["items"] == ["выручку была пустой", "доля рынка"]


def test_cell_replace_records_dialogue_on_work_run(tmp_path: Path, monkeypatch):
    """Attack 4: successful edit must appear in dialogue somewhere in the chain."""
    report, chat, report_dir, chat_dir = _report_chain(tmp_path)
    (report_dir / "note.tex").write_text(_TABLE_TEX, encoding="utf-8")

    def fake_edit(out_dir, index, *, caption, headers, rows, formats):
        return {}

    monkeypatch.setattr("case3.table_edit.edit_table_in_run", fake_edit)
    phrase = "в таблице замени Гомель на Брест"
    result = try_chat_revise(phrase, chat, root=tmp_path)
    assert result is not None and result["op"] == "replace_cell"

    report_meta = json.loads((report_dir / "meta.json").read_text(encoding="utf-8"))
    chat_meta = json.loads((chat_dir / "meta.json").read_text(encoding="utf-8"))
    report_dialogue = report_meta.get("dialogue") or []
    chat_dialogue = chat_meta.get("dialogue") or []
    combined = report_dialogue + chat_dialogue
    assert combined, "dialogue must record the edit"
    users = [note.get("user", "") for note in combined if isinstance(note, dict)]
    assert any(phrase in u or "Гомель" in u for u in users)


def test_two_letter_stem_does_not_touch_unrelated_list_word(tmp_path: Path, monkeypatch):
    """Attack 5: stem «до» (len<3) must not replace «доля»."""
    report, out = _single_report(tmp_path)
    called: list[str] = []

    def fake_edit(out_dir, index, *, items, ordered=None, formats=None):
        called.append("edited")
        return {}

    monkeypatch.setattr("case3.list_edit.edit_list_in_run", fake_edit)
    result = try_chat_revise("в списке замени до на нет", report, root=tmp_path)
    assert result is not None
    assert not called
    assert "доля" in (out / "note.tex").read_text(encoding="utf-8")