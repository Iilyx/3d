import json
from pathlib import Path

from case3.chat_memory import format_sources, format_thread, load_chain


def test_thread_marks_itself_as_not_source_and_shrinks_old_turns():
    from case3.chat_memory import _WINDOW

    turns = [
        {"chat_prompt": f"вопрос {i}", "chat_summary": f"ответ {i}", "output_mode": "chat"}
        for i in range(_WINDOW + 2)
    ]
    text = format_thread(turns)
    assert "не Source" in text
    assert f"Ход {_WINDOW + 2}" in text
    assert "Раньше:" in text
    assert "Ход 1. вопрос → ответ" in text
    assert "Ход 2. вопрос → ответ" in text
    assert format_thread([]) == ""


def test_chain_walks_prior_run_id_oldest_first(tmp_path: Path):
    root = tmp_path
    first = "source_20261118T100000Z"
    second = "source_20261118T110000Z"
    for run_id, prior, prompt in (
        (first, "", "первый"),
        (second, first, "второй"),
    ):
        out = root / "runs" / "out" / run_id
        out.mkdir(parents=True)
        (out / "meta.json").write_text(
            json.dumps(
                {
                    "run_id": run_id,
                    "prior_run_id": prior,
                    "chat_prompt": prompt,
                    "chat_summary": prompt + " готов",
                    "output_mode": "chat",
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
    chain = load_chain(root, second)
    assert [m["chat_prompt"] for m in chain] == ["первый", "второй"]
    text = format_thread(chain)
    assert text.index("первый") < text.index("второй")


def test_sources_stay_labeled():
    text = format_sources([("Договор.pdf", "пункт 2"), ("", "")])
    assert "===== Договор.pdf =====" in text
    assert "пункт 2" in text
    assert format_sources([]) == ""


def test_thread_names_the_last_edit_as_dialogue_not_fact():
    text = format_thread(
        [
            {
                "chat_prompt": "переделай введение",
                "chat_summary": "Переписал раздел",
                "last_edit": {"section": "Введение"},
            }
        ]
    )
    assert "Введение" in text
    assert "не Source" in text
    assert text.count("Последняя правка") == 1


def test_memory_card_keeps_labels_and_drops_numbers_from_the_open_question():
    from case3.chat_memory import format_card, memory_card

    card = memory_card(
        [
            {
                "chat_prompt": "почему так?",
                "chat_summary": "Уточни, это про 20 процентов?",
                "last_edit": {"section": "Введение", "pack": "board"},
            }
        ],
        "===== a.txt =====\nбыло 10\n===== b.txt =====\nстало 12\n",
    )
    assert card["documents"] == ["a.txt", "b.txt"]
    assert card["section"] == "Введение"
    assert card["style"] == "board"
    assert card["turn_count"] == 1
    assert "20" not in card["open_question"]
    text = format_card(card)
    assert "не Source" in text
    assert "a.txt" in text
    assert "20" not in text


def test_recall_finds_the_same_word_in_another_case():
    from case3.chat_memory import recall_block

    hit = recall_block(
        [{"chat_prompt": "касса выросла", "chat_summary": "КАССАСЕМЬ"}],
        "что ты говорил про кассу",
    )
    assert "КАССАСЕМЬ" in hit
    other = recall_block(
        [{"chat_prompt": "доля в тексте", "chat_summary": "ДОЛЯСТАРТ"}],
        "что ты говорил про долю",
    )
    assert "ДОЛЯСТАРТ" in other


def test_recall_lifts_one_older_turn_and_says_when_it_is_missing():
    from case3.chat_memory import recall_block

    turns = [
        {"chat_prompt": "про долю", "chat_summary": "Доля в тексте есть."},
        {"chat_prompt": "про кассу", "chat_summary": "Касса отдельно."},
    ]
    hit = recall_block(turns, "как ты отвечал про долю")
    assert "Один прошлый ход" in hit
    assert "не Source" in hit
    assert "Доля в тексте есть." in hit
    assert "Касса" not in hit
    miss = recall_block(turns, "что ты говорил про маржу")
    assert "не видно" in miss
    assert recall_block(turns, "что такое доля") == ""


def test_prior_block_shows_the_card_and_not_the_carried_chat(tmp_path: Path):
    from case3.prior_turn import prior_block_for_form

    old = "source_20261118T100000Z"
    new = "source_20261118T110000Z"
    old_dir = tmp_path / "runs" / "out" / old
    new_dir = tmp_path / "runs" / "out" / new
    source = tmp_path / "runs" / "out" / new / "source.txt"
    old_dir.mkdir(parents=True)
    new_dir.mkdir(parents=True)
    source.write_text("===== a.txt =====\nбыло 10\n", encoding="utf-8")
    (old_dir / "meta.json").write_text(
        json.dumps(
            {
                "run_id": old,
                "chat_prompt": "секретный старый вопрос",
                "chat_summary": "старый ответ про долю",
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    (new_dir / "meta.json").write_text(
        json.dumps(
            {
                "run_id": new,
                "chat_prompt": "новый вопрос",
                "chat_summary": "новый ответ",
                "source": str(source),
                "carried_run_id": old,
                "last_edit": {"section": "Введение"},
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    block = prior_block_for_form(new, root=tmp_path, user_text="как ты отвечал про долю")
    assert "Карточка этого чата" in block
    assert "a.txt" in block
    assert "Введение" in block
    assert "новый вопрос" in block
    assert "секретный" not in block
    assert "Один прошлый ход" in block
    assert "не видно" in block


def test_chain_notice_only_on_the_turns_that_matter():
    from case3.chat_memory import chain_notice

    assert chain_notice(39) == ""
    assert "40" in chain_notice(40)
    assert "Новый чат" in chain_notice(40)
    assert chain_notice(46) == ""
    assert "один ход" in chain_notice(47)
    last = chain_notice(48)
    assert "последний" in last
    assert "Новый чат" in last


def test_carry_keeps_the_chat_notice():
    from case3.pipeline import carry_chat_prompt

    meta: dict = {}
    carry_chat_prompt(meta, {"chat_notice": "Остался один ход после этого."})
    assert meta["chat_notice"] == "Остался один ход после этого."


def _marked(marker: str, at: int, tail: str = "КОНЕЦ") -> str:
    gap = max(0, at - len(marker))
    return marker + ("н" * gap) + tail


def test_latest_answer_keeps_the_analysis_the_screen_shows():
    body = (
        "Абзац один про кассу.\n\nАбзац два про долю.\n\n"
        + ("н" * 360)
        + "СЕРЕДИНАРАЗБОРА"
        + ("н" * 1700)
        + "ЛИШНЕЕ"
    )
    text = format_thread(
        [{"chat_prompt": "разбери", "chat_summary": body, "output_mode": "chat"}]
    )
    assert "Абзац один про кассу.\n\nАбзац два про долю." in text
    assert "СЕРЕДИНАРАЗБОРА" in text
    assert "ЛИШНЕЕ" not in text
    assert "не Source" in text


def test_thread_budget_shrinks_as_turns_get_older():
    """Every turn inside the window keeps paragraphs. The previous turn keeps 1600."""
    turns = [
        {"chat_prompt": "старт", "chat_summary": "начало разговора"},
        {"chat_prompt": "давно", "chat_summary": "давний ответ"},
        {"chat_prompt": "далеко", "chat_summary": _marked("ДАЛЕКО", 900, "СРЕЗДАЛЕКО")},
        {"chat_prompt": "середина", "chat_summary": _marked("СЕРЕДИНА", 1300, "СРЕЗСЕРЕДИНА")},
        {
            "chat_prompt": "прошлый",
            "chat_summary": "ПРОШЛЫЙ" + ("н" * 1400) + "ДЕРЖУПРОШЛЫЙ" + ("н" * 400) + "СРЕЗПРОШЛЫЙ",
        },
        {"chat_prompt": "сейчас", "chat_summary": "короткий текущий"},
    ]
    text = format_thread(turns)
    assert "начало разговора" in text
    assert "Раньше:" not in text
    assert "ДАЛЕКО" in text
    assert "СРЕЗДАЛЕКО" not in text
    assert "СРЕЗСЕРЕДИНА" not in text
    assert "ПРОШЛЫЙ" in text
    assert "ДЕРЖУПРОШЛЫЙ" in text
    assert "СРЕЗПРОШЛЫЙ" not in text
    assert "сейчас" in text


def test_recall_returns_the_old_analysis_not_a_stub():
    from case3.chat_memory import recall_block

    summary = (
        "Касса выросла в тексте.\n\n"
        + ("н" * 400)
        + "ПАМЯТЬ"
        + ("н" * 1700)
        + "ХВОСТПАМЯТИ"
    )
    hit = recall_block(
        [{"chat_prompt": "разбор кассы", "chat_summary": summary}],
        "что ты говорил про кассу",
    )
    assert "Касса выросла в тексте." in hit
    assert "ПАМЯТЬ" in hit
    assert "ХВОСТПАМЯТИ" not in hit


def test_latest_edit_note_is_not_cut_at_the_old_limit():
    note = "а" * 180 + "КОНЕЦЗАМЕТКИ"
    text = format_thread(
        [
            {
                "chat_prompt": "поправь",
                "chat_summary": "Переписал",
                "dialogue": [{"user": note, "assistant": "Сделал правку в разделе"}],
            }
        ]
    )
    assert "КОНЕЦЗАМЕТКИ" in text
    assert "Сделал правку в разделе" in text


def test_long_thread_keeps_the_start_and_one_edit_line():
    turns = []
    for i in range(12):
        turns.append(
            {
                "chat_prompt": f"вопрос {i}",
                "chat_summary": "старт разговора" if i == 0 else ("ответ " + "слово " * 40),
                "last_edit": {"op": "rewrite", "section": "Введение"},
            }
        )
    text = format_thread(turns)
    assert "старт разговора" in text
    assert "вопрос 11" in text
    assert text.count("Последняя правка") == 1


def test_split_sources_roundtrip_and_plain_text():
    from case3.chat_memory import split_sources

    packed = format_sources([("А.pdf", "один"), ("Б.md", "два")])
    assert split_sources(packed) == [("А.pdf", "один"), ("Б.md", "два")]
    assert split_sources("просто текст") == [("Документ", "просто текст")]
    assert split_sources("  ") == []


def test_focus_source_keeps_only_the_named_document():
    from case3.chat_memory import focus_source

    packed = format_sources([("А.pdf", "один"), ("Б.md", "два")])
    focused = focus_source(packed, "разбери по второму файлу")
    assert "Б.md" in focused
    assert "один" not in focused
    assert focus_source(packed, "что здесь?") == packed


def test_newest_edit_walks_past_a_chat_turn(tmp_path: Path):
    from case3.chat_memory import newest_edit

    root = tmp_path
    report = "source_20261118T100000Z"
    chat = "source_20261118T110000Z"
    for run_id, prior, edit in (
        (report, "", {"op": "rewrite", "section": "Введение"}),
        (chat, report, {}),
    ):
        out = root / "runs" / "out" / run_id
        out.mkdir(parents=True)
        (out / "meta.json").write_text(
            json.dumps(
                {"run_id": run_id, "prior_run_id": prior, "last_edit": edit},
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
    found = newest_edit(root, chat)
    assert found.get("section") == "Введение"


def test_undo_keeps_the_section_it_followed(tmp_path: Path):
    from case3.chat_memory import newest_edit

    root = tmp_path
    report = "source_20261118T100000Z"
    chat = "source_20261118T110000Z"
    for run_id, prior, edit in (
        (report, "", {"op": "rewrite", "section": "Введение"}),
        (chat, report, {"op": "undo"}),
    ):
        out = root / "runs" / "out" / run_id
        out.mkdir(parents=True)
        (out / "meta.json").write_text(
            json.dumps(
                {"run_id": run_id, "prior_run_id": prior, "last_edit": edit},
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
    found = newest_edit(root, chat)
    assert found.get("section") == "Введение"
    assert found.get("op") == "undo"


def test_twelve_turns_still_find_the_report_and_the_edit(tmp_path: Path):
    from case3.chat_memory import memory_view

    root = tmp_path
    prev = ""
    ids = []
    for i in range(12):
        run_id = f"source_20261118T{i:02d}0000Z"
        ids.append(run_id)
        out = root / "runs" / "out" / run_id
        out.mkdir(parents=True)
        edit = {"op": "rewrite", "section": "Введение"} if i == 0 else {}
        (out / "meta.json").write_text(
            json.dumps(
                {
                    "run_id": run_id,
                    "prior_run_id": prev,
                    "chat_prompt": "старт" if i == 0 else f"вопрос {i}",
                    "chat_summary": "ответ",
                    "output_mode": "report" if i == 0 else "chat",
                    "last_edit": edit,
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        if i == 0:
            (out / "note.tex").write_text("\\section{Введение}\nБыло 10.\n", encoding="utf-8")
        prev = run_id
    chain = load_chain(root, ids[-1])
    assert len(chain) == 12
    assert chain[0]["chat_prompt"] == "старт"
    view = memory_view(root, ids[-1])
    assert view is not None
    assert view["turns"][0]["chat_prompt"] == "старт"
    assert view["last_edit"]["section"] == "Введение"
    assert view["artifact_run_id"] == ids[0]


def test_memory_view_keeps_paragraphs_and_list_lines(tmp_path: Path):
    from case3.chat_memory import memory_view

    run_id = "source_20261119T120000Z"
    out = tmp_path / "runs" / "out" / run_id
    out.mkdir(parents=True)
    (out / "meta.json").write_text(
        json.dumps(
            {
                "run_id": run_id,
                "chat_prompt": "Первая мысль.\n\nВторая мысль.",
                "chat_summary": "Касса держится.\n\n- пункт один\n- пункт два",
                "chat_opening": "Соберу ответ.\nБез новых чисел.",
                "output_mode": "chat",
                "dialogue": [
                    {
                        "user": "ещё короче",
                        "assistant": "Готово.\nСтрока осталась.",
                    }
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    view = memory_view(tmp_path, run_id)
    assert view is not None
    turn = view["turns"][0]
    assert turn["chat_prompt"] == "Первая мысль.\n\nВторая мысль."
    assert turn["chat_summary"] == "Касса держится.\n\n- пункт один\n- пункт два"
    assert turn["chat_opening"] == "Соберу ответ.\nБез новых чисел."
    assert turn["dialogue"][0]["assistant"] == "Готово.\nСтрока осталась."


def test_memory_view_keeps_the_dashboard_screen(tmp_path: Path) -> None:
    from case3.chat_memory import memory_view

    run_id = "source_20261123T120000Z"
    out = tmp_path / "runs" / "out" / run_id
    out.mkdir(parents=True)
    src = tmp_path / "runs" / "uploads" / "screen.md"
    src.parent.mkdir(parents=True)
    src.write_text(
        "# Данные дашборда\n\n## Заголовок\nПоступления\n\n| А | Б |\n| --- | --- |\n| Минск | 12 |\n",
        encoding="utf-8",
    )
    (out / "meta.json").write_text(
        json.dumps(
            {
                "run_id": run_id,
                "source": str(src),
                "chat_prompt": "разбери",
                "chat_summary": "Выручка 12.",
                "output_mode": "chat",
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    view = memory_view(tmp_path, run_id)
    assert view is not None
    assert "Минск" in view["turns"][0]["dashboard_source"]


def test_followup_uses_the_dashboard_screen_not_the_later_note(tmp_path: Path) -> None:
    from case3.chat_memory import dashboard_screen, dashboard_screens, source_for_followup

    screen = tmp_path / "runs" / "uploads" / "screen.md"
    screen.parent.mkdir(parents=True)
    screen.write_text(
        "# Данные дашборда\n\n| Уровень | Факт |\n| --- | --- |\n| Минск | 12 |\n",
        encoding="utf-8",
    )
    note = tmp_path / "runs" / "uploads" / "note.md"
    note.write_text("сделай мне графики по данным", encoding="utf-8")
    first = "source_20261123T120000Z"
    second = "source_20261123T120100Z"
    for run_id, prior, src in (
        (first, "", screen),
        (second, first, note),
    ):
        out = tmp_path / "runs" / "out" / run_id
        out.mkdir(parents=True)
        (out / "meta.json").write_text(
            json.dumps({"run_id": run_id, "prior_run_id": prior, "source": str(src)}),
            encoding="utf-8",
        )
    saved = dashboard_screen(tmp_path, second)
    assert "Минск" in saved
    assert "Минск" in source_for_followup("сделай мне графики по данным", saved, "сделай мне графики по данным", picture=True)
    assert "Минск" in source_for_followup("сколько факт", saved, "сколько факт", picture=False)
    long_other = "Договор\n\n" + ("пункт про срок. " * 80)
    assert source_for_followup(long_other, saved, "что в договоре", picture=False) == long_other
    brest = tmp_path / "runs" / "uploads" / "brest.md"
    brest.write_text(
        "# Данные дашборда\n\n| Уровень | Факт |\n| --- | --- |\n| Брест | 7 |\n",
        encoding="utf-8",
    )
    older = "source_20261123T115900Z"
    older_out = tmp_path / "runs" / "out" / older
    older_out.mkdir(parents=True)
    (older_out / "meta.json").write_text(
        json.dumps({"run_id": older, "prior_run_id": "", "source": str(brest)}),
        encoding="utf-8",
    )
    linked = json.loads((tmp_path / "runs" / "out" / first / "meta.json").read_text(encoding="utf-8"))
    linked["prior_run_id"] = older
    (tmp_path / "runs" / "out" / first / "meta.json").write_text(json.dumps(linked), encoding="utf-8")
    both = dashboard_screens(tmp_path, second)
    assert "Брест" in both and "Минск" in both
    followed = source_for_followup("сколько по областям", both, "сколько по областям", picture=False)
    assert "Брест" in followed and "Минск" in followed
    gomel = "===== Гомель.md =====\n# Данные дашборда\n\n| Уровень | Факт |\n| --- | --- |\n| Гомель | 3 |\n"
    three = source_for_followup(gomel, both, "ещё снимок", picture=False)
    assert "Брест" in three and "Минск" in three and "Гомель" in three
    report = source_for_followup(
        "сделай отчёт по этим данным",
        both,
        "сделай отчёт по этим данным",
        picture=False,
    )
    assert "Брест" in report and "Минск" in report

    long_chat_msg = "Подготовь детальный разбор по областям с учётом сценария. " * 15
    assert len(long_chat_msg) >= 600
    assert "Брест" in source_for_followup(
        long_chat_msg + "\n\nТребования UI:\n- палитра atelier",
        both,
        long_chat_msg,
        picture=False,
    )
    first_meta = tmp_path / "runs" / "out" / first / "meta.json"
    stored = json.loads(first_meta.read_text(encoding="utf-8"))
    stored["dashboard_note"] = "На экране поступления за январь."
    first_meta.write_text(json.dumps(stored), encoding="utf-8")
    from case3.chat_memory import latest_dashboard_note

    assert "январь" in latest_dashboard_note(tmp_path, second)


def test_memory_view_returns_only_uploaded_photos(tmp_path: Path):
    from case3.chat_memory import memory_view

    run_id = "source_20261118T120000Z"
    out = tmp_path / "runs" / "out" / run_id
    figs = out / "figures"
    figs.mkdir(parents=True)
    (figs / "usr_01.png").write_bytes(b"png")
    (figs / "cht_01.png").write_bytes(b"chart")
    (out / "meta.json").write_text(
        json.dumps(
            {"run_id": run_id, "chat_prompt": "смотри фото", "output_mode": "chat"},
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    view = memory_view(tmp_path, run_id)
    assert view is not None
    assert view["turns"][0]["photos"] == [
        {"name": "usr_01", "url": f"/api/runs/{run_id}/figures/usr_01.png"}
    ]
    assert view["turns"][0]["previews"] == [
        {"id": "cht_01", "kind": "chart", "url": f"/api/runs/{run_id}/figures/cht_01.png"}
    ]


def test_verbatim_window_is_eight_and_a_plain_question_lifts_the_ninth():
    """A live chain stops at 48. Only the last 8 turns stay as paragraphs."""
    from case3.chat_memory import _MAX_HOPS, _WINDOW, recall_block

    assert _WINDOW == 8
    assert _MAX_HOPS == 48
    turns = [
        {
            "chat_prompt": "разбор кассы",
            "chat_summary": "Выручка 77.\n\nКАССАЦЕЛЬ вторым абзацем.",
        }
    ]
    turns.extend(
        {"chat_prompt": f"другой {i}", "chat_summary": f"спокойно {i}\n\nещё абзац"}
        for i in range(8)
    )
    text = format_thread(turns)
    assert "Раньше:" in text
    assert "ещё абзац" in text
    archived = [line for line in text.splitlines() if line.startswith("Ход 1.")]
    assert len(archived) == 1
    assert "77" not in archived[0]
    assert "КАССАЦЕЛЬ" in archived[0]
    assert "\n" not in archived[0]
    assert "Выручка 77." not in text
    lifted = recall_block(turns, "что с кассой")
    assert "Выручка 77." in lifted
    assert "КАССАЦЕЛЬ вторым абзацем." in lifted
    assert "спокойно" not in lifted


def test_full_window_keeps_paragraphs_and_the_turn_past_it_is_one_line():
    """Turns inside the verbatim window keep paragraphs. The turn before that is one line."""
    from case3.chat_memory import _WINDOW

    older = {
        "chat_prompt": "сколько было в кассе",
        "chat_summary": "Выручка 20. МАРКЕРСТАР\n\nВторой абзац старого ответа.",
    }
    window = []
    for i in range(_WINDOW - 1):
        window.append(
            {"chat_prompt": f"промежуточный {i}", "chat_summary": f"короткий {i}"}
        )
    window.append(
        {
            "chat_prompt": "сейчас",
            "chat_summary": "Абзац один про кассу.\n\nАбзац два про долю.",
        }
    )
    text = format_thread([older, *window])
    assert "Абзац один про кассу.\n\nАбзац два про долю." in text
    assert "Раньше:" in text
    first = [line for line in text.splitlines() if line.startswith("Ход 1.")]
    assert len(first) == 1
    assert "МАРКЕРСТАР" in first[0]
    assert "20" not in first[0]
    assert "\n" not in first[0]


def test_previous_turn_keeps_1600_and_drops_the_tail():
    body = "ПРОШЛЫЙ" + ("н" * 1400) + "ДЕРЖУПРОШЛЫЙ" + ("н" * 400) + "СРЕЗПРОШЛЫЙ"
    text = format_thread(
        [
            {"chat_prompt": "давно", "chat_summary": "архив"},
            {"chat_prompt": "прошлый", "chat_summary": body},
            {"chat_prompt": "сейчас", "chat_summary": "Абзац.\n\nЖивой."},
        ]
    )
    assert "ПРОШЛЫЙ" in text
    assert "ДЕРЖУПРОШЛЫЙ" in text
    assert "СРЕЗПРОШЛЫЙ" not in text
    assert "Абзац.\n\nЖивой." in text


def test_oldest_window_turn_keeps_a_paragraph_break():
    """The oldest turn in the window is still prose, capped near 800, not flattened."""
    from case3.chat_memory import _WINDOW

    body = "Абзац склада.\n\n" + ("н" * 900) + "ХВОСТОКНА"
    turns = [{"chat_prompt": "край", "chat_summary": body}]
    turns.extend(
        {"chat_prompt": f"ход {i}", "chat_summary": "ок"} for i in range(_WINDOW - 1)
    )
    text = format_thread(turns)
    assert "Абзац склада.\n\n" in text
    assert "ХВОСТОКНА" not in text
    assert "Раньше:" not in text


def test_older_lines_drop_from_the_front_past_6000():
    letters = "абвгдежзийклмнопрстуфхцчшщыэюя"
    span = len(letters)
    older = []
    for i in range(40):
        tag = "ТОЧКА" + letters[i % span] + letters[(i // span) % span]
        older.append(
            {
                "chat_prompt": tag + " " + ("б" * 200),
                "chat_summary": "выручка 98765 " + ("в" * 200),
            }
        )
    from case3.chat_memory import _WINDOW

    window = [
        {"chat_prompt": f"свежий {i}", "chat_summary": "ок"} for i in range(_WINDOW)
    ]
    text = format_thread(older + window)
    assert "Раньше:" in text
    earlier = text.split("Раньше:\n", 1)[1].split("\nХод 41.", 1)[0]
    assert len(earlier) <= 6000
    first = "ТОЧКА" + letters[0] + letters[0]
    last = "ТОЧКА" + letters[39 % span] + letters[(39 // span) % span]
    assert first not in earlier
    assert last in earlier
    assert "98765" not in earlier
    assert "свежий 0" in text


def test_recall_without_pro_lifts_the_named_turn():
    from case3.chat_memory import recall_block

    hit = recall_block(
        [{"chat_prompt": "разбор кассы", "chat_summary": "КАССАЦЕЛЬ"}],
        "вспомни кассу",
    )
    assert "КАССАЦЕЛЬ" in hit
    assert "не Source" in hit


def test_plain_question_lifts_a_turn_outside_the_window():
    from case3.chat_memory import recall_block

    turns = [
        {
            "chat_prompt": "общий вопрос",
            "chat_summary": "ничего особенного",
            "dialogue": [
                {"user": "подвинь кассу", "assistant": "КАССАЗАМЕТКА в правке"}
            ],
        }
    ]
    from case3.chat_memory import _WINDOW

    turns.extend(
        {"chat_prompt": f"другой ход {i}", "chat_summary": "спокойно"}
        for i in range(_WINDOW)
    )
    hit = recall_block(turns, "что с кассой")
    assert "Один прошлый ход" in hit
    assert "КАССАЗАМЕТКА" in hit
    assert "спокойно" not in hit
    assert recall_block(turns[-2:], "что такое доля") == ""


def test_recall_does_not_duplicate_a_turn_already_in_the_window():
    from case3.chat_memory import recall_block

    turns = [
        {"chat_prompt": "разбор кассы", "chat_summary": "СТАРЫЙКАССА"},
        {"chat_prompt": "ещё про кассу", "chat_summary": "СВЕЖИЙКАССА"},
    ]
    assert recall_block(turns, "что с кассой") == ""
    explicit = recall_block(turns, "что ты говорил про кассу")
    assert "СВЕЖИЙКАССА" in explicit


def test_memory_keeps_a_photo_that_was_left_beside_the_source(tmp_path: Path):
    from case3.chat_memory import memory_view

    run_id = "source_20261118T130000Z"
    upload = tmp_path / "runs" / "uploads" / "stamp"
    (upload / "user_photos").mkdir(parents=True)
    (upload / "user_photos" / "usr_01.png").write_bytes(b"png-bytes")
    (upload / "source.txt").write_text("было 10", encoding="utf-8")
    out = tmp_path / "runs" / "out" / run_id
    out.mkdir(parents=True)
    (out / "meta.json").write_text(
        json.dumps(
            {
                "run_id": run_id,
                "chat_prompt": "что на фото",
                "output_mode": "chat",
                "source": str(upload / "source.txt"),
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    view = memory_view(tmp_path, run_id)
    assert view is not None
    assert view["turns"][0]["photos"] == [
        {"name": "usr_01", "url": f"/api/runs/{run_id}/figures/usr_01.png"}
    ]
    assert (out / "figures" / "usr_01.png").read_bytes() == b"png-bytes"


def test_user_number_line_keeps_the_word_beside_the_digit():
    from case3.chat_memory import format_user_numbers

    line = format_user_numbers(
        [
            {"chat_prompt": "на слайде 2 было", "chat_summary": "модель сказала 9"},
        ]
    )
    assert "2 слайд" in line
    assert "9" not in line


def test_user_number_line_keeps_user_tokens_and_drops_the_answer():
    from case3.chat_memory import format_user_numbers

    turns = [
        {
            "chat_prompt": "выручка 77",
            "chat_summary": "модель сказала 88",
            "dialogue": [
                {"user": "в кассе 12,5", "assistant": "оставил 99"},
            ],
        }
    ]
    line = format_user_numbers(turns)
    assert line.startswith("Числа из реплик пользователя")
    assert "77" in line
    assert "12,5" in line
    assert "88" not in line
    assert "99" not in line


def test_user_number_line_ignores_a_thread_pasted_into_the_prompt():
    from case3.chat_memory import format_user_numbers

    turns = [
        {
            "chat_prompt": (
                "что с кассой\n\n"
                "Разговор этого чата (не Source).\n"
                "Ход 1. Запрос: выручка 77\n"
                "Ответ: было 88."
            ),
            "chat_summary": "ок",
        }
    ]
    assert format_user_numbers(turns) == ""


def test_two_stems_do_not_lift_a_turn_that_shares_one():
    from case3.chat_memory import _WINDOW, recall_block

    turns = [
        {"chat_prompt": "отчёт за квартал", "chat_summary": "КВАРТАЛТОЛЬКО"},
        {"chat_prompt": "выручка за квартал", "chat_summary": "ОБАСТОВА"},
    ]
    turns.extend(
        {"chat_prompt": f"другой ход {i}", "chat_summary": "спокойно"}
        for i in range(_WINDOW)
    )
    weak = recall_block(turns[:1] + turns[2:], "что с выручкой за квартал")
    assert weak == ""
    strong = recall_block(turns, "что с выручкой за квартал")
    assert "ОБАСТОВА" in strong
    assert "КВАРТАЛТОЛЬКО" not in strong


def test_memory_view_restores_attachments_only_on_turns_that_attached_them(tmp_path: Path):
    from case3.chat_memory import memory_view

    doc_text = "===== отчёт.pdf =====\nВыручка 120.\n\n===== таблица.md =====\n| А | Б |\n| --- | --- |\n| 1 | 2 |"
    u1 = tmp_path / "runs" / "uploads" / "u1"
    u1.mkdir(parents=True)
    (u1 / "source.txt").write_text(doc_text, encoding="utf-8")
    r1 = "source_20261124T100001Z"
    o1 = tmp_path / "runs" / "out" / r1
    o1.mkdir(parents=True)
    (o1 / "meta.json").write_text(
        json.dumps(
            {
                "run_id": r1,
                "chat_prompt": "Разбери оба файла",
                "chat_summary": "Разобрал.",
                "output_mode": "chat",
                "source": str(u1 / "source.txt"),
                "attachments": [
                    {
                        "title": "отчёт.pdf",
                        "fileName": "отчёт.pdf",
                        "viewMode": "document",
                        "previewUrl": "/api/source/files/ing_1/preview",
                        "originalUrl": "/api/source/files/ing_1/original",
                        "format": "pdf",
                    },
                    {
                        "title": "таблица.md",
                        "fileName": "таблица.md",
                        "viewMode": "text",
                    },
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    u2 = tmp_path / "runs" / "uploads" / "u2"
    u2.mkdir(parents=True)
    (u2 / "source.txt").write_text(doc_text, encoding="utf-8")
    r2 = "source_20261124T100002Z"
    o2 = tmp_path / "runs" / "out" / r2
    o2.mkdir(parents=True)
    (o2 / "meta.json").write_text(
        json.dumps(
            {
                "run_id": r2,
                "prior_run_id": r1,
                "chat_prompt": "А по таблице?",
                "chat_summary": "В таблице 1 и 2.",
                "output_mode": "chat",
                "source": str(u2 / "source.txt"),
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    view = memory_view(tmp_path, r2)
    assert view is not None
    t1, t2 = view["turns"]
    assert len(t1["attachments"]) == 2
    assert t1["attachments"][0]["fileName"] == "отчёт.pdf"
    assert t1["attachments"][0]["viewMode"] == "document"
    assert t1["attachments"][0]["previewUrl"] == "/api/source/files/ing_1/preview"
    assert t1["attachments"][1]["fileName"] == "таблица.md"
    assert "1 | 2" in t1["attachments"][1]["text"]
    assert t2.get("attachments", []) == []
