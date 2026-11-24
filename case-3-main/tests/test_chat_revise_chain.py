import json
from pathlib import Path

from case3.chat_revise import try_chat_revise


def test_shorter_edits_the_report_behind_a_chat_turn(tmp_path: Path, monkeypatch):
    report = "source_20261118T100000Z"
    chat = "source_20261118T110000Z"
    report_dir = tmp_path / "runs" / "out" / report
    chat_dir = tmp_path / "runs" / "out" / chat
    report_dir.mkdir(parents=True)
    chat_dir.mkdir(parents=True)
    (report_dir / "meta.json").write_text(
        json.dumps(
            {
                "run_id": report,
                "output_mode": "report",
                "artifacts": {"pdf": "report.pdf"},
                "last_edit": {"op": "rewrite", "section": "Введение"},
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    (report_dir / "note.tex").write_text("\\section{Введение}\nБыло 10.\n", encoding="utf-8")
    (chat_dir / "meta.json").write_text(
        json.dumps(
            {
                "run_id": chat,
                "prior_run_id": report,
                "output_mode": "chat",
                "artifacts": {},
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    seen: dict[str, str] = {}

    def fake_rewrite(out_dir: Path, text: str, act) -> str:
        seen["dir"] = out_dir.name
        seen["section"] = act.section
        return "Переписал раздел «Введение» по документам. Новых чисел нет."

    monkeypatch.setattr("case3.chat_revise._rewrite", fake_rewrite)
    result = try_chat_revise("короче", chat, root=tmp_path)
    assert result is not None
    assert result["run_id"] == chat
    assert seen["dir"] == report
    assert seen["section"] == "Введение"
    head = json.loads((chat_dir / "meta.json").read_text(encoding="utf-8"))
    report_meta = json.loads((report_dir / "meta.json").read_text(encoding="utf-8"))
    assert head["last_edit"]["section"] == "Введение"
    assert result["surface"] == "report"
    assert [note.get("user") for note in head.get("dialogue") or []] == ["короче"]
    assert "dialogue" not in report_meta


def test_named_deck_title_edits_the_slide_not_the_report(tmp_path: Path, monkeypatch):
    report = "source_20261118T100000Z"
    deck = "source_20261118T130000Z"
    report_dir = tmp_path / "runs" / "out" / report
    deck_dir = tmp_path / "runs" / "out" / deck
    report_dir.mkdir(parents=True)
    deck_dir.mkdir(parents=True)
    (report_dir / "note.tex").write_text("\\title{Старое}\n", encoding="utf-8")
    (report_dir / "meta.json").write_text(
        json.dumps(
            {"run_id": report, "output_mode": "report", "artifacts": {"pdf": "a.pdf"}},
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    (deck_dir / "meta.json").write_text(
        json.dumps(
            {
                "run_id": deck,
                "prior_run_id": report,
                "output_mode": "presentation",
                "slides_status": "ok",
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    seen: dict[str, object] = {}

    def fake_slide(run_id: str, out_dir: Path, title: str, index: int = 1) -> str:
        seen["dir"] = out_dir.name
        seen["title"] = title
        seen["index"] = index
        return f"Заголовок слайда {index} теперь «{title}»."

    monkeypatch.setattr("case3.chat_revise._retitle_slide", fake_slide)
    result = try_chat_revise(
        "поменяй заголовок презентации на Гомель",
        deck,
        root=tmp_path,
    )
    assert result is not None
    assert result["surface"] == "deck"
    assert seen["dir"] == deck
    assert seen["title"] == "Гомель"
    assert seen["index"] == 1


def test_shorter_still_edits_a_report_twelve_answers_later(tmp_path: Path, monkeypatch):
    root = tmp_path
    prev = ""
    report = ""
    head = ""
    for i in range(12):
        run_id = f"source_20261118T{i:02d}0000Z"
        out = root / "runs" / "out" / run_id
        out.mkdir(parents=True)
        if i == 0:
            report = run_id
            (out / "note.tex").write_text("\\section{Введение}\nБыло 10.\n", encoding="utf-8")
        head = run_id
        (out / "meta.json").write_text(
            json.dumps(
                {
                    "run_id": run_id,
                    "prior_run_id": prev,
                    "output_mode": "report" if i == 0 else "chat",
                    "artifacts": {"pdf": "a.pdf"} if i == 0 else {},
                    "last_edit": {"op": "rewrite", "section": "Введение"} if i == 0 else {},
                    "chat_prompt": "старт" if i == 0 else f"вопрос {i}",
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        prev = run_id
    seen: dict[str, str] = {}

    def fake_rewrite(out_dir: Path, text: str, act) -> str:
        seen["dir"] = out_dir.name
        return "Переписал раздел «Введение» по документам. Новых чисел нет."

    monkeypatch.setattr("case3.chat_revise._rewrite", fake_rewrite)
    result = try_chat_revise("короче", head, root=root)
    assert result is not None
    assert result["op"] == "rewrite"
    assert result["run_id"] == head
    assert result["artifact_run_id"] == report
    assert seen["dir"] == report


def test_a_full_chat_asks_for_a_new_one_but_still_edits(tmp_path: Path, monkeypatch):
    from case3.chat_memory import _MAX_HOPS
    from case3.chat_revise import continue_or_limit

    root = tmp_path
    prev = ""
    head = ""
    for i in range(_MAX_HOPS):
        run_id = f"source_20261119T{i:06d}Z"
        out = root / "runs" / "out" / run_id
        out.mkdir(parents=True)
        if i == 0:
            (out / "note.tex").write_text("\\section{Введение}\nБыло 10.\n", encoding="utf-8")
        head = run_id
        (out / "meta.json").write_text(
            json.dumps(
                {
                    "run_id": run_id,
                    "prior_run_id": prev,
                    "output_mode": "report" if i == 0 else "chat",
                    "artifacts": {"pdf": "a.pdf"} if i == 0 else {},
                    "last_edit": {"op": "rewrite", "section": "Введение"} if i == 0 else {},
                    "chat_prompt": f"ход {i}",
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        prev = run_id

    def fake_rewrite(out_dir: Path, text: str, act) -> str:
        return "Переписал раздел «Введение» по документам. Новых чисел нет."

    monkeypatch.setattr("case3.chat_revise._rewrite", fake_rewrite)
    edit = continue_or_limit("короче", head, root=root)
    assert edit is not None
    assert edit["op"] == "rewrite"
    blocked = continue_or_limit("что это значит", head, root=root)
    assert blocked is not None
    assert blocked["op"] == "full"
    assert "Пустой" in blocked["chat"]
    assert "С этими документами" in blocked["chat"]
    assert blocked["run_id"] == head
    assert not (root / "runs" / "out").joinpath("source_20261119T999999Z").exists()


def test_carried_file_can_be_edited_without_joining_its_chat(tmp_path: Path, monkeypatch):
    old = "source_20261118T100000Z"
    old_dir = tmp_path / "runs" / "out" / old
    old_dir.mkdir(parents=True)
    (old_dir / "note.tex").write_text("\\section{Введение}\nБыло 10.\n", encoding="utf-8")
    (old_dir / "meta.json").write_text(
        json.dumps(
            {
                "run_id": old,
                "output_mode": "report",
                "chat_prompt": "секретный старый вопрос",
                "artifacts": {"pdf": "a.pdf"},
                "last_edit": {"op": "rewrite", "section": "Введение"},
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    def fake_rewrite(out_dir: Path, text: str, act) -> str:
        assert out_dir.name == old
        return "Переписал раздел «Введение» по документам. Новых чисел нет."

    monkeypatch.setattr("case3.chat_revise._rewrite", fake_rewrite)
    result = try_chat_revise("короче", "", root=tmp_path, carried_run_id=old)
    assert result is not None
    assert result["isolate"] is True
    assert result["run_id"] == old
    meta = json.loads((old_dir / "meta.json").read_text(encoding="utf-8"))
    assert "dialogue" not in meta
    assert meta["chat_prompt"] == "секретный старый вопрос"


def test_rename_heading_uses_the_report_dir(tmp_path: Path, monkeypatch):
    report = "source_20261118T100000Z"
    report_dir = tmp_path / "runs" / "out" / report
    report_dir.mkdir(parents=True)
    (report_dir / "note.tex").write_text("\\section{Введение}\nТекст.\n", encoding="utf-8")
    (report_dir / "meta.json").write_text(
        json.dumps({"run_id": report, "output_mode": "report", "artifacts": {"pdf": "a.pdf"}}),
        encoding="utf-8",
    )
    seen: dict[str, str] = {}

    def fake_rename(out_dir: Path, old: str, new: str) -> str:
        seen["dir"] = out_dir.name
        seen["old"] = old
        seen["new"] = new
        return "Переименовал раздел «Введение» в «Контекст»."

    monkeypatch.setattr("case3.chat_revise._rename_heading", fake_rename)
    result = try_chat_revise("переименуй раздел Введение в Контекст", report, root=tmp_path)
    assert result is not None
    assert result["surface"] == "report"
    assert seen == {"dir": report, "old": "Введение", "new": "Контекст"}


def _report_dir(tmp_path: Path, run_id: str = "source_20261118T100000Z") -> Path:
    out = tmp_path / "runs" / "out" / run_id
    out.mkdir(parents=True)
    (out / "note.tex").write_text("\\section{Введение}\nБыло 10.\n", encoding="utf-8")
    (out / "meta.json").write_text(
        json.dumps(
            {
                "run_id": run_id,
                "output_mode": "report",
                "artifacts": {"pdf": "report.pdf"},
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    return out


def test_whole_report_shortens_the_file_behind_the_chat(tmp_path: Path, monkeypatch):
    report = "source_20261118T100000Z"
    chat = "source_20261118T110000Z"
    report_dir = tmp_path / "runs" / "out" / report
    chat_dir = tmp_path / "runs" / "out" / chat
    report_dir.mkdir(parents=True)
    chat_dir.mkdir(parents=True)
    (report_dir / "note.tex").write_text(
        "\\section{Введение}\nБыло 10.\n", encoding="utf-8"
    )
    (report_dir / "meta.json").write_text(
        json.dumps(
            {"run_id": report, "output_mode": "report", "artifacts": {"pdf": "report.pdf"}},
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
    seen: dict[str, str] = {}

    def fake_all(out_dir: Path, text: str, act) -> str:
        seen["dir"] = out_dir.name
        return "Сократил разделы: Введение."

    monkeypatch.setattr("case3.chat_revise._rewrite_all", fake_all)
    result = try_chat_revise("сократи весь отчёт", chat, root=tmp_path)
    assert result is not None
    assert result["op"] == "rewrite_all"
    assert result["artifact_run_id"] == report
    assert seen["dir"] == report


def test_failed_table_row_does_not_replace_the_last_edit(tmp_path: Path, monkeypatch):
    report = "source_20261118T100000Z"
    chat = "source_20261118T110000Z"
    report_dir = tmp_path / "runs" / "out" / report
    chat_dir = tmp_path / "runs" / "out" / chat
    report_dir.mkdir(parents=True)
    chat_dir.mkdir(parents=True)
    (report_dir / "note.tex").write_text(_TABLE_TEX, encoding="utf-8")
    (report_dir / "meta.json").write_text(
        json.dumps(
            {
                "run_id": report,
                "output_mode": "report",
                "artifacts": {"pdf": "report.pdf"},
                "last_edit": {"op": "rewrite", "section": "Введение"},
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
    called = {"n": 0}

    def fake_edit(*_args, **_kwargs):
        called["n"] += 1
        return {}

    monkeypatch.setattr("case3.table_edit.edit_table_in_run", fake_edit)
    result = try_chat_revise(
        "в таблице добавь строку: только", chat, root=tmp_path
    )
    assert result is not None
    assert "ячеек" in result["chat"]
    assert called["n"] == 0
    from case3.chat_memory import newest_edit

    found = newest_edit(tmp_path, chat)
    assert found.get("op") == "rewrite"
    assert found.get("section") == "Введение"


def test_chart_recolor_from_chat_rebuilds_pdf_and_docx(tmp_path: Path, monkeypatch):
    report = "source_20261118T100000Z"
    _report_dir(tmp_path, report)
    seen: dict[str, object] = {}

    def fake_recolor(out_dir: Path, palette: str, formats=None):
        seen["dir"] = out_dir.name
        seen["palette"] = palette
        seen["formats"] = formats
        return {"ok": True}

    monkeypatch.setattr("case3.chart_edit.recolor_all_charts_in_run", fake_recolor)
    result = try_chat_revise("перекрась графики в ocean", report, root=tmp_path)
    assert result is not None
    assert result["op"] == "recolor_charts"
    assert seen["dir"] == report
    assert seen["palette"] == "ocean"
    assert seen["formats"] == {"pdf", "docx"}


def test_green_phrase_repaints_the_chat_chart(tmp_path: Path, monkeypatch):
    chat = "source_20261118T150000Z"
    chat_dir = tmp_path / "runs" / "out" / chat
    figs = chat_dir / "figures"
    figs.mkdir(parents=True)
    html = (
        "<canvas id='c'></canvas><script>"
        "new Chart(c,{type:'bar',data:{labels:['Минск','Брест'],datasets:["
        "{label:'Факт',data:[10,20]}]},options:{responsive:false}});"
        "</script>"
    )
    (chat_dir / "figures.json").write_text(
        json.dumps(
            {"figures": [], "charts": [{"id": "cht_01", "type": "bar", "caption": "Факт", "html": html}], "diagrams": []},
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    (chat_dir / "meta.json").write_text(
        json.dumps({"run_id": chat, "output_mode": "chat", "charts_planned": ["cht_01"]}),
        encoding="utf-8",
    )

    def fake_batch(items):
        status = {}
        for cid, _chart, png_path, _cdir in items:
            png_path.parent.mkdir(parents=True, exist_ok=True)
            png_path.write_bytes(b"\x89PNG\r\n")
            status[cid] = {"ok": True}
        return status

    monkeypatch.setattr("case3.charts.render_charts_batch", fake_batch)
    result = try_chat_revise("Доработай график: сделай в зеленых цветах", chat, root=tmp_path)
    assert result is not None
    assert result["op"] == "recolor_hue"
    assert "зелён" in result["chat"]
    assert result["previews"][0]["id"] == "cht_01"
    saved = json.loads((chat_dir / "figures.json").read_text(encoding="utf-8"))
    assert "#1F8A45" in saved["charts"][0]["html"].upper()
    assert "data:[10,20]" in saved["charts"][0]["html"]


def test_chart_recolor_without_a_report_does_not_ask_for_print(tmp_path: Path, monkeypatch):
    deck = "source_20261118T140000Z"
    deck_dir = tmp_path / "runs" / "out" / deck
    deck_dir.mkdir(parents=True)
    (deck_dir / "meta.json").write_text(
        json.dumps(
            {
                "run_id": deck,
                "output_mode": "presentation",
                "slides_status": "ok",
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    seen: dict[str, object] = {}

    def fake_recolor(out_dir: Path, palette: str, formats=None):
        seen["formats"] = formats
        return {"ok": True}

    monkeypatch.setattr("case3.chart_edit.recolor_all_charts_in_run", fake_recolor)
    result = try_chat_revise("перекрась графики в ocean", deck, root=tmp_path)
    assert result is not None
    assert seen["formats"] == set()


def test_undo_and_structure_after_chat_stay_on_the_deck(tmp_path: Path, monkeypatch):
    report = "source_20261121T200000Z"
    deck = "source_20261121T200100Z"
    chat = "source_20261121T200200Z"
    report_dir = tmp_path / "runs" / "out" / report
    deck_dir = tmp_path / "runs" / "out" / deck
    chat_dir = tmp_path / "runs" / "out" / chat
    for path in (report_dir, deck_dir, chat_dir):
        path.mkdir(parents=True)
    (report_dir / "note.tex").write_text(
        "\\section{Введение}\nБыло 10.\n", encoding="utf-8"
    )
    (report_dir / "meta.json").write_text(
        json.dumps(
            {"run_id": report, "output_mode": "report", "artifacts": {"pdf": "a.pdf"}},
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    (deck_dir / "meta.json").write_text(
        json.dumps(
            {
                "run_id": deck,
                "prior_run_id": report,
                "output_mode": "presentation",
                "slides_status": "ok",
                "last_edit": {"op": "recolor_deck", "pack": "board"},
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    (chat_dir / "meta.json").write_text(
        json.dumps(
            {
                "run_id": chat,
                "prior_run_id": deck,
                "output_mode": "chat",
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    undone: list[str] = []

    def apply_undo(out_dir: Path, *, rebuild: bool = True):
        undone.append(Path(out_dir).name)
        return {}

    monkeypatch.setattr("case3.run_undo.apply_undo", apply_undo)
    first = try_chat_revise("отмени", chat, root=tmp_path)
    second = try_chat_revise("отмени", chat, root=tmp_path)
    assert first is not None and first["surface"] == "deck"
    assert second is not None and second["surface"] == "deck"
    assert undone == [deck, deck]

    styled: list[str] = []

    def restyle(_run_id: str, out_dir: Path, _structure: str) -> str:
        styled.append(Path(out_dir).name)
        return "Собираю презентацию для инвестора."

    monkeypatch.setattr("case3.chat_revise._restyle_structure", restyle)
    changed = try_chat_revise(
        "смени структуру презентации на инвестора", chat, root=tmp_path
    )
    assert changed is not None
    assert changed["op"] == "restyle_structure"
    assert styled == [deck]


def test_undo_and_redo_from_chat_rebuild_print_files(tmp_path: Path, monkeypatch):
    report = "source_20261118T100000Z"
    _report_dir(tmp_path, report)
    seen: dict[str, bool] = {}

    def fake_undo(out_dir: Path, *, rebuild: bool = True):
        seen["undo"] = rebuild
        return {}

    def fake_redo(out_dir: Path, *, rebuild: bool = True):
        seen["redo"] = rebuild
        return {}

    monkeypatch.setattr("case3.run_undo.apply_undo", fake_undo)
    monkeypatch.setattr("case3.run_undo.apply_redo", fake_redo)
    undone = try_chat_revise("отмени", report, root=tmp_path)
    redone = try_chat_revise("верни правку", report, root=tmp_path)
    assert undone is not None and undone["op"] == "undo"
    assert redone is not None and redone["op"] == "redo"
    assert seen == {"undo": True, "redo": True}


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
\\item касса
\\item доля
\\end{itemize}
\\end{document}
"""


def test_table_cell_from_chat_rewrites_the_grid(tmp_path: Path, monkeypatch):
    report = "source_20261118T100000Z"
    out = _report_dir(tmp_path, report)
    (out / "note.tex").write_text(_TABLE_TEX, encoding="utf-8")
    seen: dict[str, object] = {}

    def fake_edit(out_dir, index, *, caption, headers, rows, formats):
        seen["index"] = index
        seen["rows"] = rows
        seen["formats"] = formats
        return {}

    monkeypatch.setattr("case3.table_edit.edit_table_in_run", fake_edit)
    result = try_chat_revise("в таблице замени Гомель на Брест", report, root=tmp_path)
    assert result is not None
    assert result["op"] == "replace_cell"
    assert result["surface"] == "report"
    assert seen["index"] == 1
    assert seen["formats"] == {"pdf", "docx"}
    assert seen["rows"] == [["Брест", "10"]]


def test_table_row_from_chat_is_appended_and_removed(tmp_path: Path, monkeypatch):
    report = "source_20261118T100000Z"
    out = _report_dir(tmp_path, report)
    (out / "note.tex").write_text(_TABLE_TEX, encoding="utf-8")
    seen: dict[str, object] = {}

    def fake_edit(out_dir, index, *, caption, headers, rows, formats):
        seen["rows"] = rows
        seen["formats"] = formats
        return {}

    monkeypatch.setattr("case3.table_edit.edit_table_in_run", fake_edit)
    added = try_chat_revise(
        "в таблице добавь строку: Брест; 12", report, root=tmp_path
    )
    assert added is not None
    assert added["op"] == "add_row"
    assert seen["rows"] == [["Гомель", "10"], ["Брест", "12"]]
    assert seen["formats"] == {"pdf", "docx"}
    removed = try_chat_revise("убери из таблицы строку Гомель", report, root=tmp_path)
    assert removed is not None
    assert removed["op"] == "delete_row"
    assert seen["rows"] == []


def test_list_item_from_chat_is_appended(tmp_path: Path, monkeypatch):
    report = "source_20261118T100000Z"
    out = _report_dir(tmp_path, report)
    (out / "note.tex").write_text(_TABLE_TEX, encoding="utf-8")
    seen: dict[str, object] = {}

    def fake_edit(out_dir, index, *, items, ordered=None, formats=None):
        seen["index"] = index
        seen["items"] = items
        seen["formats"] = formats
        return {}

    monkeypatch.setattr("case3.list_edit.edit_list_in_run", fake_edit)
    result = try_chat_revise(
        "добавь в список пункт риски поставки", report, root=tmp_path
    )
    assert result is not None
    assert result["op"] == "add_item"
    assert seen["items"] == ["касса", "доля", "риски поставки"]
    assert seen["formats"] == {"pdf", "docx"}


def test_list_item_decline_still_replaces_the_word(tmp_path: Path, monkeypatch):
    report = "source_20261118T100000Z"
    out = _report_dir(tmp_path, report)
    (out / "note.tex").write_text(_TABLE_TEX, encoding="utf-8")
    seen: dict[str, object] = {}

    def fake_edit(out_dir, index, *, items, ordered=None, formats=None):
        seen["items"] = items
        return {}

    monkeypatch.setattr("case3.list_edit.edit_list_in_run", fake_edit)
    result = try_chat_revise("в списке замени кассу на выручку", report, root=tmp_path)
    assert result is not None
    assert result["op"] == "replace_item"
    assert seen["items"] == ["выручку", "доля"]


def test_undo_does_not_forget_which_section_to_shorten(tmp_path: Path, monkeypatch):
    report = "source_20261118T100000Z"
    chat = "source_20261118T110000Z"
    report_dir = _report_dir(tmp_path, report)
    (report_dir / "meta.json").write_text(
        json.dumps(
            {
                "run_id": report,
                "output_mode": "report",
                "artifacts": {"pdf": "report.pdf"},
                "last_edit": {"op": "rewrite", "section": "Введение"},
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    chat_dir = tmp_path / "runs" / "out" / chat
    chat_dir.mkdir(parents=True)
    (chat_dir / "meta.json").write_text(
        json.dumps(
            {
                "run_id": chat,
                "prior_run_id": report,
                "output_mode": "chat",
                "last_edit": {"op": "undo"},
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    seen: dict[str, str] = {}

    def fake_rewrite(out_dir: Path, text: str, act) -> str:
        seen["section"] = act.section
        return "Переписал раздел «Введение» по документам. Новых чисел нет."

    monkeypatch.setattr("case3.chat_revise._rewrite", fake_rewrite)
    result = try_chat_revise("короче", chat, root=tmp_path)
    assert result is not None
    assert result["op"] == "rewrite"
    assert seen["section"] == "Введение"


def test_undo_then_shorter_keeps_the_section_on_the_report(tmp_path: Path, monkeypatch):
    report = "source_20261118T100000Z"
    chat = "source_20261118T110000Z"
    report_dir = _report_dir(tmp_path, report)
    (report_dir / "meta.json").write_text(
        json.dumps(
            {
                "run_id": report,
                "output_mode": "report",
                "artifacts": {"pdf": "report.pdf"},
                "last_edit": {"op": "rewrite", "section": "Введение"},
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    chat_dir = tmp_path / "runs" / "out" / chat
    chat_dir.mkdir(parents=True)
    (chat_dir / "meta.json").write_text(
        json.dumps(
            {"run_id": chat, "prior_run_id": report, "output_mode": "chat"},
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr("case3.run_undo.apply_undo", lambda *a, **k: {})
    seen: dict[str, str] = {}

    def fake_rewrite(out_dir: Path, text: str, act) -> str:
        seen["section"] = act.section
        return "Переписал раздел «Введение» по документам. Новых чисел нет."

    monkeypatch.setattr("case3.chat_revise._rewrite", fake_rewrite)
    undone = try_chat_revise("отмени", chat, root=tmp_path)
    assert undone is not None and undone["op"] == "undo"
    result = try_chat_revise("короче", chat, root=tmp_path)
    assert result is not None
    assert result["op"] == "rewrite"
    assert seen["section"] == "Введение"


def test_diagram_phrase_refines_the_only_scheme(tmp_path: Path, monkeypatch):
    report = "source_20261118T100000Z"
    out = _report_dir(tmp_path, report)
    (out / "figures.json").write_text(
        json.dumps(
            {"diagrams": [{"id": "dia_01", "title": "Касса", "mermaid": "graph LR\nA-->B"}]},
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    seen: dict[str, object] = {}

    def fake_refine(out_dir, diagram_id, *, instruction, client, palette, formats):
        seen["id"] = diagram_id
        seen["instruction"] = instruction
        seen["formats"] = formats
        return {"id": diagram_id}

    monkeypatch.setattr("case3.diagram_edit.refine_diagram_in_run", fake_refine)
    monkeypatch.setattr(
        "case3.llm_client.LLMConfig.from_env",
        lambda: object(),
    )
    monkeypatch.setattr("case3.llm_client.LLMClient", lambda _cfg: object())
    result = try_chat_revise("на схеме убери кассу", report, root=tmp_path)
    assert result is not None
    assert result["op"] == "refine_diagram"
    assert seen["id"] == "dia_01"
    assert "кассу" in str(seen["instruction"])
    assert seen["formats"] == {"pdf", "docx"}


def test_slide_points_from_chat_patch_bullets(tmp_path: Path, monkeypatch):
    deck = "source_20261118T140000Z"
    deck_dir = tmp_path / "runs" / "out" / deck
    deck_dir.mkdir(parents=True)
    (deck_dir / "meta.json").write_text(
        json.dumps(
            {"run_id": deck, "output_mode": "presentation", "slides_status": "ok"},
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    seen: dict[str, object] = {}

    def fake_load(run_id, out_dir):
        return (
            {
                "slides": [
                    {"id": "s1", "title": "Старт"},
                    {"id": "s2", "title": "Середина", "bullets": ["старое"]},
                ]
            },
            deck_dir / "slides" / "deck.json",
        )

    def fake_patch(base, patch):
        seen["patch"] = patch
        return base

    def fake_enqueue(*_args, **_kwargs):
        seen["enqueued"] = True

    monkeypatch.setattr("case3.api_slides._load_deck_for_patch", fake_load)
    monkeypatch.setattr("case3.slides_patch.apply_deck_text_patch", fake_patch)
    monkeypatch.setattr("case3.api_slides._enqueue_deck_rebuild", fake_enqueue)
    result = try_chat_revise(
        "на слайде 2 пункты: риски; сроки", deck, root=tmp_path
    )
    assert result is not None
    assert result["op"] == "slide_bullets"
    assert result["surface"] == "deck"
    assert seen["patch"]["slides"][0]["bullets"] == ["риски", "сроки"]
    assert seen["enqueued"] is True


def test_a_failed_rewrite_asks_for_the_number(tmp_path: Path, monkeypatch):
    report = "source_20261118T100000Z"
    _report_dir(tmp_path, report)
    meta_path = tmp_path / "runs" / "out" / report / "meta.json"
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    meta["last_edit"] = {"op": "rewrite", "section": "Введение"}
    meta_path.write_text(json.dumps(meta, ensure_ascii=False), encoding="utf-8")

    def empty_draft(**_kwargs):
        return ""

    monkeypatch.setattr("case3.chat_turn.draft_section", empty_draft)
    result = try_chat_revise("короче", report, root=tmp_path)
    assert result is not None
    assert "40" in result["chat"]
    assert "черновик вышел пустым" not in result["chat"]


def test_a_rewrite_keeps_a_number_the_user_wrote(tmp_path: Path, monkeypatch):
    report = "source_20261118T100000Z"
    _report_dir(tmp_path, report)
    meta_path = tmp_path / "runs" / "out" / report / "meta.json"
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    meta["last_edit"] = {"op": "rewrite", "section": "Введение"}
    meta_path.write_text(json.dumps(meta, ensure_ascii=False), encoding="utf-8")
    seen: dict[str, str] = {}

    def draft(**kwargs):
        seen["user_text"] = kwargs.get("user_text") or ""
        return "В кассе теперь 40."

    def edit(*_args, **_kwargs):
        return None

    monkeypatch.setattr("case3.chat_turn.draft_section", draft)
    monkeypatch.setattr("case3.paragraph_edit.edit_paragraph_in_run", edit)
    result = try_chat_revise("ещё короче, касса 40", report, root=tmp_path)
    assert result is not None
    assert "40" in seen["user_text"]
    assert "40" in result["chat"]
    assert "твоего сообщения" in result["chat"]


def test_unclear_edit_lists_the_real_headings(tmp_path: Path):
    run_id = "source_20261118T120000Z"
    out = tmp_path / "runs" / "out" / run_id
    out.mkdir(parents=True)
    (out / "meta.json").write_text(
        json.dumps(
            {
                "run_id": run_id,
                "output_mode": "report",
                "artifacts": {"pdf": "report.pdf"},
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    (out / "note.tex").write_text(
        "\\section{Введение}\nБыло 10.\n\\section{Итог}\nСтало 12.\n",
        encoding="utf-8",
    )
    result = try_chat_revise("поправь отчёт", run_id, root=tmp_path)
    assert result is not None
    assert result["op"] == "ask"
    assert "Введение" in result["chat"]
    assert "Итог" in result["chat"]


def test_diagram_phrase_keeps_the_run_palette(tmp_path: Path, monkeypatch):
    report = "source_20261119T120000Z"
    out = _report_dir(tmp_path, report)
    meta_path = out / "meta.json"
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    meta["chart_palette"] = "ocean"
    meta_path.write_text(json.dumps(meta, ensure_ascii=False), encoding="utf-8")
    (out / "figures.json").write_text(
        json.dumps(
            {"diagrams": [{"id": "dia_01", "title": "Касса", "mermaid": "graph LR\nA-->B"}]},
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    seen: dict[str, object] = {}

    def fake_refine(out_dir, diagram_id, *, instruction, client, palette, formats):
        seen["palette"] = palette
        return {"id": diagram_id}

    monkeypatch.setattr("case3.diagram_edit.refine_diagram_in_run", fake_refine)
    monkeypatch.setattr("case3.llm_client.LLMConfig.from_env", lambda: object())
    monkeypatch.setattr("case3.llm_client.LLMClient", lambda _cfg: object())
    result = try_chat_revise("на схеме убери кассу", report, root=tmp_path)
    assert result is not None
    assert seen["palette"] == "ocean"


def test_photo_phrase_edits_the_only_png(tmp_path: Path, monkeypatch):
    report = "source_20261119T130000Z"
    out = _report_dir(tmp_path, report)
    figs = out / "figures"
    figs.mkdir()
    (figs / "usr_01.png").write_bytes(b"png")
    seen: dict[str, object] = {}

    def fake_edit(out_dir, figure_id, *, mode, prompt, caption=None, formats=None, cfg=None):
        seen["id"] = figure_id
        seen["mode"] = mode
        seen["prompt"] = prompt
        seen["formats"] = formats
        return {"figure_id": figure_id}

    monkeypatch.setattr("case3.figure_edit.edit_figure_in_run", fake_edit)
    result = try_chat_revise("на фото сделай небо темнее", report, root=tmp_path)
    assert result is not None
    assert result["op"] == "edit_photo"
    assert seen["id"] == "usr_01"
    assert seen["mode"] == "edit"
    assert seen["prompt"] == "небо темнее"
    assert seen["formats"] == {"pdf", "docx"}


def test_missing_deck_returns_the_canned_line(tmp_path: Path):
    report = "source_20261121T180000Z"
    _report_dir(tmp_path, report)
    result = try_chat_revise("убери слайд 2?", report, root=tmp_path)
    assert result is not None
    assert result["op"] == "talk"
    assert result["chat"].startswith("Презентации в этом чате ещё нет")
    meta = json.loads(
        (tmp_path / "runs" / "out" / report / "meta.json").read_text(encoding="utf-8")
    )
    notes = meta.get("dialogue") or []
    assert notes[-1]["user"] == "убери слайд 2?"
    assert notes[-1]["assistant"].startswith("Презентации в этом чате ещё нет")


def test_two_verbs_run_in_the_order_they_were_written(tmp_path: Path, monkeypatch):
    run_id = "source_20261121T190000Z"
    out = tmp_path / "runs" / "out" / run_id
    out.mkdir(parents=True)
    (out / "note.tex").write_text("\\section{Введение}\nБыло 10.\n", encoding="utf-8")
    (out / "meta.json").write_text(
        json.dumps(
            {
                "run_id": run_id,
                "output_mode": "report",
                "slides_status": "ok",
                "artifacts": {"pdf": "report.pdf"},
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    seen: list[str] = []

    def delete_slide(*_args, **_kwargs):
        seen.append("delete")
        return "Убираю слайд 2."

    def recolor(*_args, **_kwargs):
        seen.append("recolor")
        return "Перекрасил графики в ocean."

    monkeypatch.setattr("case3.chat_revise._delete_slide", delete_slide)
    monkeypatch.setattr("case3.chat_revise._recolor_charts", recolor)
    result = try_chat_revise(
        "убери слайд 2 и перекрась графики в ocean",
        run_id,
        root=tmp_path,
    )
    assert result is not None
    assert seen == ["delete", "recolor"]
    assert "Убираю слайд 2." in result["chat"]
    assert "ocean" in result["chat"]
    assert result["op"] == "batch"
    assert result["surfaces"] == [
        {"surface": "deck", "artifact_run_id": run_id, "op": "delete_slide"},
        {"surface": "report", "artifact_run_id": run_id, "op": "recolor_charts"},
    ]


def test_plain_question_still_goes_to_the_model(tmp_path: Path):
    report = "source_20261121T180100Z"
    _report_dir(tmp_path, report)
    assert try_chat_revise("что с кассой", report, root=tmp_path) is None
    assert try_chat_revise("поменяй числа на графике", report, root=tmp_path) is None
    assert try_chat_revise("почему бы не убрать слайд 2?", report, root=tmp_path) is None


def test_retype_chart_hides_raw_english_js_error_from_user(tmp_path: Path, monkeypatch):
    from case3.chart_edit import ChartEditError

    run_id = "source_20261123T173136Z"
    out = tmp_path / "runs" / "out" / run_id
    out.mkdir(parents=True)
    (out / "meta.json").write_text(
        json.dumps(
            {
                "run_id": run_id,
                "output_mode": "chat",
                "charts_planned": ["cht_01"],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    def boom(*_args, **_kwargs):
        raise ChartEditError(
            "chart render failed: chart JS error: Cannot read properties of undefined (reading 'axis')"
        )

    monkeypatch.setattr("case3.chart_edit.edit_chart_in_run", boom)
    result = try_chat_revise("сделай этот график линейным", run_id, root=tmp_path)
    assert result is not None
    msg = result["chat"]
    assert "chart render failed" not in msg
    assert "chart JS error" not in msg
    assert "reading 'axis'" not in msg
    assert any("а" <= ch.lower() <= "я" for ch in msg)
