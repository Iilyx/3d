from pathlib import Path

from case3.chat_turn import opening_fallback, try_chat_answer, try_opening


class _Fake:
    def __init__(self, text: str) -> None:
        self.text = text

    def stream(self, **_kwargs):
        yield self.text


def test_what_can_you_do_answers_without_the_model():
    from case3.input_validation import validate_input_heuristics

    valid, msg = validate_input_heuristics("", "Что ты умеешь?", output_mode="chat")
    assert valid and msg is None
    text = try_chat_answer(
        "",
        "Что ты умеешь?",
        client=_Fake(
            "Привет! Я Liber — аналитический помощник по дашбордам Stimulsoft и документам. "
            "Могу разбирать таблицы, строить графики, схемы, отчёты (PDF/DOCX) и презентации (PPTX)."
        ),
    )
    assert "отч" in text.lower()
    assert "схем" in text.lower()
    assert "дашборд" in text.lower()


def test_opening_fallback_does_not_claim_the_file_is_done():
    line = opening_fallback("presentation", "Выручка 10 и 12")
    assert "презентац" in line.lower()
    assert "готово" not in line.lower()
    assert "10" in line


def test_bad_opening_is_replaced_and_only_the_fallback_is_emitted():
    seen: list[str] = []
    text = try_opening(
        "report",
        "Собери отчёт по выручке 10",
        client=_Fake("Готово. PDF готов, можно скачивать."),
        on_delta=seen.append,
    )
    assert text == seen[0]
    assert "готово" not in text.lower()
    assert "отч" in text.lower()


def test_section_draft_keeps_only_numbers_already_in_the_text():
    from case3.chat_turn import draft_section

    allowed = "Выручка была 10, стала 12."
    kept = draft_section(
        section="Введение",
        current=allowed,
        source="Выручка была 10, стала 12.",
        brief="clearer",
        client=_Fake(
            "Выручка была 10, затем стала 12. Других цифр в тексте нет."
        ),
    )
    assert "10" in kept and "12" in kept

    rejected = draft_section(
        section="Введение",
        current=allowed,
        source=allowed,
        brief="clearer",
        client=_Fake("Выручка выросла на 20 процентов, с 10 до 12."),
    )
    assert rejected == ""


class _Seq:
    def __init__(self, texts: list[str]) -> None:
        self.texts = list(texts)
        self.calls = 0
        self.seen: list[str] = []

    def stream(self, **kwargs):
        self.calls += 1
        self.seen.append(kwargs.get("user_text") or "")
        yield self.texts.pop(0)


class _Boom:
    def stream(self, **_kwargs):
        raise AssertionError("model should not be called")
        yield ""


def test_chat_answer_asks_instead_of_inventing_a_percent():
    seen: list[str] = []
    client = _Seq(
        [
            "Выручка выросла на 20% , с 10 до 12.",
            "Выручка выросла на 20 процентов.",
        ]
    )
    text = try_chat_answer(
        "Выручка была 10, стала 12.",
        "Проанализируй динамику",
        client=client,
        on_delta=seen.append,
    )
    assert client.calls == 2
    assert "20" in text
    assert "нет" in text.lower()
    assert "выросла на 20" not in text.lower()
    assert seen == [text]


def test_chat_answer_retries_once_and_keeps_a_clean_second_draft():
    client = _Seq(
        [
            "Выручка выросла на 20%, с 10 до 12.",
            "Выручка была 10, затем стала 12. Новую долю не считаю.",
        ]
    )
    text = try_chat_answer(
        "Выручка была 10, стала 12.",
        "Проанализируй динамику",
        client=client,
    )
    assert client.calls == 2
    assert text.startswith("Выручка была 10")
    assert "20" not in text


def test_chat_answer_keeps_a_number_the_user_added():
    client = _Seq(["Открыли 3 точки. Касса в документе 20."])
    text = try_chat_answer(
        "Касса 20.",
        "Учти, что открыли 3 точки, и разбери кассу",
        client=client,
    )
    assert text.startswith("Открыли 3")
    assert client.calls == 1


def test_chat_answer_asks_when_the_user_disagrees_with_the_document():
    text = try_chat_answer(
        "Касса была 20, выручка 12.",
        "Касса была 40, разбери",
        client=_Boom(),
    )
    assert "20" in text and "40" in text
    assert "оставить" in text


def test_slide_number_does_not_look_like_a_fact_conflict():
    client = _Seq(["Касса 20. Это про третий слайд."])
    text = try_chat_answer(
        "Касса 20.",
        "почему слайд 3 про кассу",
        client=client,
    )
    assert text.startswith("Касса 20")
    assert "оставить" not in text


def test_old_request_number_does_not_enter_the_answer():
    intent = (
        "что с кассой\n\n"
        "Разговор этого чата (не Source).\n"
        "Ход 1. Запрос: выручка 77\n"
        "Ответ: было."
    )
    client = _Seq(["Выручка 77.", "Выручка 77."])
    text = try_chat_answer("Касса была 20.", intent, client=client)
    assert text.startswith("В документах")
    assert "Выручка 77" not in text


def test_choosing_the_document_number_drops_the_rejected_one():
    prior = (
        "20\n\n"
        "Разговор этого чата (не Source).\n"
        "Ход 1. Запрос: касса была 40\n"
        "Ответ: В документе у «касса» стоит 20, ты написал 40. "
        "Напиши 40, чтобы оставить твоё, или 20, чтобы оставить документ."
    )
    client = _Seq(
        [
            "Оставляю 40, как ты писал раньше.",
            "Оставляю 40 снова.",
        ]
    )
    text = try_chat_answer(
        "Касса была 20.",
        prior,
        client=client,
    )
    assert "нет" in text.lower()
    assert "40" in text
    assert "Оставляю 40" not in text
    assert any("выбрал 20" in blob for blob in client.seen)


def test_section_draft_keeps_a_number_the_user_wrote():
    from case3.chat_turn import draft_section

    kept = draft_section(
        section="Введение",
        current="Касса была 20.",
        source="Касса была 20.",
        brief="clearer",
        user_text="поставь в кассе 40",
        client=_Fake("В кассе теперь 40."),
    )
    assert "40" in kept


def test_long_thread_keeps_the_latest_answer_and_its_paragraphs():
    """Memory sits after the question. A front clip drops the latest answer."""
    latest = "Касса в прошлом ответе держится.\n\nХВОСТОВЕТ остаётся абзацем."
    recall = "Один прошлый ход (не Source).\nОтвет: ВСПОМНИЛКАССУ по запросу."
    intent = (
        "Первая мысль.\n\nВторая мысль. Что с кассой?\n\n"
        "Карточка этого чата (не Source).\n"
        "документы: касса.txt.\n\n"
        "Разговор этого чата (не Source).\n"
        "Числа и факты бери только из документов этого запроса.\n"
        "Ход 1. Запрос: древний\n"
        "Ответ: ДРЕВНИЙМАРКЕР " + ("н" * 4000) + "\n"
        "Ход 2. Запрос: сейчас\n"
        f"Ответ: {latest}\n\n"
        f"{recall}"
    )
    client = _Seq(["Касса в документе 20. Новых цифр не добавляю."])
    try_chat_answer("Касса была 20.", intent, client=client)
    prompt = client.seen[0]
    assert "Первая мысль.\n\nВторая мысль." in prompt
    assert "ХВОСТОВЕТ остаётся абзацем." in prompt
    assert "ВСПОМНИЛКАССУ" in prompt
    assert "не Source" in prompt
    assert "ТЕКСТ:\nКасса была 20." in prompt
    assert prompt.index("ХВОСТОВЕТ") > prompt.index("ТЕКСТ:")
    assert prompt.index("ВСПОМНИЛКАССУ") > prompt.index("ХВОСТОВЕТ")


def test_overflow_drops_the_old_thread_and_keeps_the_tail():
    from case3.chat_turn import _MEMORY_CAP

    filler = "ДРЕВНИЙМАРКЕР " + ("н" * (_MEMORY_CAP + 2000))
    intent = (
        "Что с кассой?\n\n"
        "Разговор этого чата (не Source).\n"
        f"Ход 1. Запрос: старое\nОтвет: {filler}\n"
        "обрывок древнего абзаца\n"
        "Ход 2. Запрос: сейчас\nОтвет: ХВОСТОВЕТ живой."
    )
    client = _Seq(["Касса в документе 20. Новых цифр не добавляю."])
    try_chat_answer("Касса была 20.", intent, client=client)
    prompt = client.seen[0]
    assert "ХВОСТОВЕТ живой." in prompt
    assert "не Source" in prompt
    assert "ДРЕВНИЙМАРКЕР" not in prompt
    assert "обрывок древнего абзаца" not in prompt
    assert prompt.index("Ход 2") < prompt.index("ХВОСТОВЕТ живой.")


def test_formatted_thread_keeps_the_latest_paragraph():
    """The block prior_turn actually pastes, not a hand-built lookalike."""
    from case3.chat_memory import format_card, format_thread, memory_card, recall_block

    turns = [
        {
            "chat_prompt": f"вопрос {i} про кассу",
            "chat_summary": "старый ответ " + ("н" * 1500),
            "output_mode": "chat",
        }
        for i in range(6)
    ]
    turns[-1]["chat_summary"] = "Касса держится.\n\nХВОСТОВЕТ в свежем ответе."
    source = "===== Касса =====\nКасса была 20."
    block = "\n\n".join(
        part
        for part in (
            format_card(memory_card(turns, source)),
            format_thread(turns),
            recall_block(turns, "вспомни что ты говорил про кассу"),
        )
        if part
    )
    client = _Seq(["Касса в документе 20. Новых цифр не добавляю."])
    try_chat_answer("Касса была 20.", "Что с кассой сейчас?\n\n" + block, client=client)
    prompt = client.seen[0]
    assert "Касса держится.\n\nХВОСТОВЕТ в свежем ответе." in prompt
    assert "не Source" in prompt
    assert prompt.index("ХВОСТОВЕТ в свежем ответе.") > prompt.index("ТЕКСТ:")


def test_fattest_legal_thread_is_pasted_whole():
    """format_thread already budgets the chain. The prompt must not cut it again."""
    from case3.chat_memory import format_card, format_thread, memory_card, recall_block

    turns = []
    for i in range(48):
        turns.append(
            {
                "chat_prompt": f"вопрос {i} " + ("п" * 4000),
                "chat_summary": "ответ " + ("о" * 4000),
                "output_mode": "chat",
                "dialogue": [
                    {"user": "у" * 500, "assistant": "а" * 500} for _ in range(12)
                ],
                "last_edit": {"section": "Введение"},
            }
        )
    turns[-1]["chat_summary"] = "ХВОСТОВЕТ " + ("о" * 4000)
    source = "===== Документ =====\n" + ("текст " * 200)
    block = "\n\n".join(
        part
        for part in (
            format_card(memory_card(turns, source)),
            format_thread(turns),
            recall_block(turns, "вспомни что ты говорил про вопрос"),
        )
        if part
    )
    client = _Seq(["Касса в документе 20. Новых цифр не добавляю."])
    try_chat_answer("Касса была 20.", "Что с кассой?\n\n" + block, client=client)
    prompt = client.seen[0]
    assert block in prompt
    assert "ХВОСТОВЕТ" in prompt
    assert prompt.index("ХВОСТОВЕТ") > prompt.index("ТЕКСТ:")


def test_trim_keeps_the_second_paragraph_of_the_latest_answer():
    from case3.chat_turn import _MEMORY_CAP

    filler = "н" * (_MEMORY_CAP + 500)
    intent = (
        "Что с кассой?\n\n"
        "Разговор этого чата (не Source).\n"
        f"Ответ: {filler}\n"
        "ХВОСТОВЕТ вторым абзацем.\n"
        "Дальше: поправили заголовок"
    )
    client = _Seq(["Касса в документе 20. Новых цифр не добавляю."])
    try_chat_answer("Касса была 20.", intent, client=client)
    prompt = client.seen[0]
    assert "ХВОСТОВЕТ вторым абзацем." in prompt
    assert "Дальше: поправили заголовок" in prompt
    assert prompt.index("ХВОСТОВЕТ вторым абзацем.") < prompt.index("Дальше:")


def test_long_line_with_not_source_does_not_eat_the_tail():
    from case3.chat_turn import _MEMORY_CAP

    old = "Ответ: это не Source ДРЕВНИЙ " + ("н" * 8000)
    middle = "Ход 9. Запрос: середина\nОтвет: " + ("с" * (_MEMORY_CAP - 1000))
    intent = (
        "Что с кассой?\n\n"
        "Разговор этого чата (не Source).\n"
        f"{old}\n"
        f"{middle}\n"
        "Ход 2. Запрос: сейчас\n"
        "Ответ: ХВОСТОВЕТ живой."
    )
    client = _Seq(["Касса в документе 20. Новых цифр не добавляю."])
    try_chat_answer("Касса была 20.", intent, client=client)
    prompt = client.seen[0]
    assert "ХВОСТОВЕТ живой." in prompt
    assert "Разговор этого чата (не Source)." in prompt
    assert "ДРЕВНИЙ" not in prompt


def test_long_question_keeps_its_last_paragraph():
    opening = "Сначала про выручку. " * 400
    intent = opening + "\n\nХВОСТВОПРОСА почему касса упала?"
    client = _Seq(["Касса в документе 20. Новых цифр не добавляю."])
    try_chat_answer("Касса была 20.", intent, client=client)
    prompt = client.seen[0]
    assert "Сначала про выручку." in prompt
    assert "ХВОСТВОПРОСА почему касса упала?" in prompt
    assert prompt.index("ХВОСТВОПРОСА") > prompt.index("Сначала про выручку.")


def test_long_source_keeps_the_head_the_match_and_the_tail():
    from case3.chat_turn import _clip_source

    parts = [
        "НАЧАЛО " + ("а" * 2200),
        "МАСЛОУНИК " + ("м" * 2200),
        "СКЛАДМАРКЕР на складе тихо.",
        ("в" * 2200) + " ХВОСТДОКУМЕНТА",
    ]
    clipped = _clip_source("\n\n".join(parts), 6000, "что на складе")
    assert len(clipped) <= 6000
    assert "НАЧАЛО" in clipped
    assert "СКЛАДМАРКЕР" in clipped
    assert "ХВОСТДОКУМЕНТА" in clipped
    assert "МАСЛОУНИК" not in clipped
    assert _clip_source("короткий текст", 6000, "склад") == "короткий текст"


def test_list_markers_are_not_numbers():
    from case3.chat_turn import number_norms, stray_numbers

    assert number_norms("1. Выручка 10\n2. Касса 20") == {"10", "20"}
    assert "2024" in number_norms("2024. Выручка 10")
    assert "10" in number_norms("2024. Выручка 10")
    assert stray_numbers("1. В тексте 10.", {"10"}) == []
    assert stray_numbers("Пункт 1 стоит отдельно.", {"10"}) == ["1"]
    assert "1.1" in number_norms("1.1. Глобальный тренд 3")


def test_chat_prompt_shows_the_whole_table_and_names_the_count():
    rows = ["| Область | Сумма |", "| --- | --- |"]
    for index in range(160):
        rows.append(f"| Район {index:03d} длинная подпись области | {1000 + index} |")
    source = "\n".join(rows)
    assert len(source) > 6000

    class _Catch:
        def __init__(self) -> None:
            self.user = ""
            self.system = ""

        def stream(self, **kwargs):
            self.user = kwargs.get("user_text") or ""
            self.system = kwargs.get("system") or ""
            yield "Район 159 в таблице."

    client = _Catch()
    try_chat_answer(source, "что в таблице", client=client)
    assert "Район 159" in client.user
    assert "1159" in client.user
    assert "Вижу все 160 строк." in client.user
    assert "Вижу" in client.system and "строк" in client.system


def test_chat_drops_a_number_that_belongs_to_another_row():
    source = (
        "| Область | Сумма |\n"
        "| --- | --- |\n"
        "| Минская | 100 |\n"
        "| Гомельская | 40 |\n"
    )
    text = try_chat_answer(
        source,
        "что у Гомельской",
        client=_Fake("У Гомельской сумма 100."),
    )
    assert "100" not in text
    assert "строк" in text


def test_a_long_table_uses_the_chat_cap_not_a_short_slice():
    from case3.chat_turn import _clip_source

    rows = ["| Область | Сумма |", "| --- | --- |"]
    for index in range(4000):
        rows.append(f"| Район {index:04d} | {index} |")
    source = "\n".join(rows)
    clipped = _clip_source(source, focus="что в таблице")
    assert "Район 0150" in clipped
    assert len(clipped) > 5000


def test_long_table_keeps_the_header_and_the_named_region():
    from case3.chat_turn import _clip_source

    rows = ["| Область | Сумма |", "| --- | --- |"]
    for index, name in enumerate(
        ["Брестская", "Витебская", "Гомельская", "Гродненская", "Минская", "Могилевская"]
        * 80
    ):
        rows.append(f"| {name} область | {1000 + index} |")
    source = "Экран дашборда.\n\n" + "\n".join(rows)
    assert len(source) > 6000
    clipped = _clip_source(source, 6000, "что в Гомельской")
    assert "| Область | Сумма |" in clipped
    assert "Гомельская" in clipped
    assert len(clipped) <= 6000


def test_chat_answer_asks_for_a_long_reply():
    class _Catch:
        def __init__(self) -> None:
            self.max_tokens = 0

        def stream(self, **kwargs):
            self.max_tokens = kwargs.get("max_tokens") or 0
            yield "Касса в документе 20. Разбор ниже, без новой цифры."

    client = _Catch()
    text = try_chat_answer("Касса была 20.", "что с кассой, разбери подробнее", client=client)
    assert client.max_tokens >= 4096
    assert "20" in text


def test_chat_answer_uses_the_model_text():
    seen: list[str] = []
    answer = (
        "Выручка выросла с 10 до 12. "
        "Доля рынка в тексте не указана, поэтому её не считаю."
    )
    text = try_chat_answer(
        "Выручка 10, потом 12.",
        "Проанализируй динамику",
        client=_Fake(answer),
        on_delta=seen.append,
    )
    assert text == answer
    assert seen == [answer]


def test_user_stated_number_enters_the_answer():
    intent = (
        "сколько я называл\n\n"
        "Числа из реплик пользователя (его слова, не ответ модели):\n"
        "77\n\n"
        "Разговор этого чата (не Source).\n"
        "Ход 1. Запрос: выручка 77\n"
        "Ответ: было."
    )
    client = _Seq(["Выручка 77.", "Выручка 77."])
    text = try_chat_answer("Касса была 20.", intent, client=client)
    assert "77" in text
    assert not text.startswith("В документах")


def test_answer_number_stays_out_when_the_card_lists_only_the_user():
    intent = (
        "что с кассой\n\n"
        "Числа из реплик пользователя (его слова, не ответ модели):\n"
        "77\n\n"
        "Разговор этого чата (не Source).\n"
        "Ответ: модель написала 88."
    )
    client = _Seq(["Там 88.", "Там 88."])
    text = try_chat_answer("Касса была 20.", intent, client=client)
    assert text.startswith("В документах")
    assert "Там 88" not in text


def test_long_source_prompt_keeps_the_middle_when_the_file_fits():
    from case3.chat_turn import _user_block

    middle = "# Касса в середине\n\n" + ("абзац про склад. " * 80)
    source = ("# Начало\n\n" + ("вводные слова. " * 200)) + "\n\n" + middle
    source += "\n\n# Конец\n\n" + ("хвост документа. " * 200)
    assert len(source) > 6000
    block = _user_block(source, "что в конце")
    assert "# Касса в середине" in block
    assert "склад" in block
    assert "Оглавление документа" not in block


def test_source_past_the_chat_cap_still_names_the_middle_heading():
    from case3.chat_turn import _CHAT_SOURCE_CAP, _user_block

    filler = "вводные слова. " * 3000
    middle = "# Касса в середине\n\n" + ("абзац про склад. " * 40)
    source = "# Начало\n\n" + filler + "\n\n" + middle + "\n\n# Конец\n\n" + filler
    assert len(source) > _CHAT_SOURCE_CAP
    block = _user_block(source, "что в конце")
    assert "# Касса в середине" in block
    assert len(block) < len(source)


def test_short_source_has_no_extra_outline():
    from case3.chat_turn import _user_block

    block = _user_block("# Касса\n\nБыло 20.", "что в кассе")
    assert block.count("# Касса") == 1
    assert "Оглавление документа" not in block


def test_unsupported_edit_tells_the_model_the_file_stayed():
    class _Catch:
        def __init__(self) -> None:
            self.system = ""
            self.user = ""

        def stream(self, **kwargs):
            self.system = kwargs.get("system") or ""
            self.user = kwargs.get("user_text") or ""
            yield "Числа на графике я поменять не умею. Могу перекрасить или сменить вид. Напиши «перекрась графики в ocean»."

    client = _Catch()
    text = try_chat_answer("Касса была 20.", "поменяй числа на графике", client=client)
    assert "Файл не изменился" in client.user
    assert "числа на графике" in client.system
    assert "не умею" in text
    assert "ПРАВКА НЕ ВЗЯТА" not in text


def test_chat_answer_does_not_read_the_memory_label_aloud():
    intent = (
        "какое число я назвал\n\n"
        "Числа из реплик пользователя (его слова, не ответ модели):\n"
        "77\n"
    )
    client = _Seq(["### Числа из реплик пользователя\n\nТы написал 77."])
    text = try_chat_answer("Касса была 20.", intent, client=client)
    assert "Числа из реплик пользователя" not in text
    assert "77" in text


def test_every_dashboard_shot_survives_a_short_budget():
    from case3.chat_turn import _clip_source

    shots = []
    for name, city in (("one", "Минск"), ("two", "Брест"), ("three", "Гомель")):
        shots.append(
            f"===== {name}.md =====\n# Данные дашборда\n\n{city}\n\n" + ("строка\n" * 40)
        )
    packed = "\n\n".join(shots)
    shown = _clip_source(packed, 500, focus="сколько")
    assert "Минск" in shown and "Брест" in shown and "Гомель" in shown


def test_chat_chart_canvas_fills_the_frame():
    from case3.chart_harden import full_chat_canvas

    html = full_chat_canvas("<canvas id='c' width='320' height='140' style='width:320px'></canvas>")
    assert 'width="1100"' in html
    assert 'height="560"' in html
    assert "320" not in html


def test_dashboard_landing_stops_after_four_sentences():
    class _Cap:
        def __init__(self) -> None:
            self.tokens = 0
            self.user = ""

        def stream(self, **kwargs):
            self.tokens = int(kwargs.get("max_tokens") or 0)
            self.user = kwargs.get("user_text") or ""
            yield (
                "На экране поступления. Факт уже в таблице. "
                "Спросите уровень. Это четвёртое. Это пятое лишнее."
            )

    client = _Cap()
    text = try_chat_answer(
        "# Данные дашборда\n\nФакт 10.",
        "Экраны уже в тексте. Длинный разбор в чат не пиши.",
        client=client,
    )
    assert client.tokens == 320
    assert "не больше четырёх" in client.user
    assert "четвёртое" in text
    assert "пятое" not in text


def test_a_plain_question_has_no_limit_note():
    client = _Seq(["Касса была 20."])
    try_chat_answer("Касса была 20.", "что с кассой", client=client)
    assert "Файл не изменился" not in client.seen[0]


def test_generate_chat_charts_and_diagram_receive_chat_memory_and_analysis(tmp_path: Path):
    from case3.chat_turn import generate_chat_charts, generate_chat_diagram

    seen_prompts: list[str] = []

    class _FakeLLM:
        def complete(
            self, *, system: str, user_text: str, reasoning: str = "off", **_kw
        ) -> str:
            seen_prompts.append(user_text)
            if "Mermaid" in system or "схем" in system.lower():
                return '```json\n{"diagrams": [{"id": "dia_01", "title": "Сценарий", "mermaid": "flowchart TD\\nA[Гомель 7994] --> B[План 8200]"}]}\n```'
            return (
                '```json\n{"charts": [{"id": "cht_01", "type": "bar", "caption": "Гомель сценарий", '
                '"html": "<canvas id=\\\'c\\\'></canvas><script>new Chart(document.getElementById(\\\'c\\\'), '
                '{type:\\\'bar\\\',data:{labels:[\\\'Гомель\\\'],datasets:[{data:[7994]}]}});</script>"}]}\n```'
            )

    source = "| Регион | Факт | План |\n| --- | --- | --- |\n| Гомель | 7544 | 8200 |\n"
    intent = (
        "построй график по этому сценарию\n\n"
        "Разговор этого чата (не Source):\n"
        "Пользователь: Допустим, для Гомеля выделили резерв 450.\n"
        "Ассистент: С резервом 450 факт Гомеля станет 7994."
    )
    fake = _FakeLLM()
    generate_chat_charts(
        source,
        intent,
        max_charts=1,
        figs_dir=tmp_path / "figs",
        charts_dir=tmp_path / "charts",
        client=fake,
        extra_context="Новый факт Гомеля 7994 при плане 8200.",
    )
    generate_chat_diagram(
        source,
        intent,
        figs_dir=tmp_path / "figs2",
        client=fake,
        extra_context="С резервом 450 дефицит сокращается.",
    )
    assert len(seen_prompts) == 2
    assert "7994" in seen_prompts[0]
    assert "резерв 450" in seen_prompts[0]
    assert "7994" in seen_prompts[1] or "резерв 450" in seen_prompts[1]


def test_try_chat_answer_continues_on_finish_reason_length():
    class _CutClient:
        def __init__(self) -> None:
            self.calls = 0
            self.last_finish_reason = "length"

        def complete(self, *, system: str, user_text: str, reasoning: str = "off") -> str:
            self.calls += 1
            if self.calls == 1:
                self.last_finish_reason = "length"
                return "По Гомельской области факт составляет 7544, что меньше"
            self.last_finish_reason = "stop"
            return "плана 8200 на 656."

    client = _CutClient()
    ans = try_chat_answer(
        "| Регион | Факт | План | Откл. |\n| --- | --- | --- | --- |\n| Гомель | 7544 | 8200 | -656 |\n",
        "Что по Гомелю?",
        client=client,
    )
    assert client.calls == 2
    assert "7544" in ans
    assert "плана 8200" in ans


def test_try_chat_answer_allows_prefix_region_rollups_and_without_stray_never_corrupts_tables():
    from case3.chat_turn import _without_stray

    source = (
        "| Регион / Инспекция | План | Факт | Отклонение |\n"
        "| --- | --- | --- | --- |\n"
        "| г. Минск — Центральный | 18400 | 19850 | +1450 |\n"
        "| г. Минск — Советский | 14200 | 14910 | +710 |\n"
        "| г. Минск — Первомайский | 11500 | 11960 | +460 |\n"
        "| Гомельская область — г. Гомель | 8200 | 7544 | -656 |\n"
        "| Витебская область — г. Витебск | 5900 | 5605 | -295 |\n"
    )
    reply = (
        "### Лидеры\n"
        "- Топ-3 инспекции (все — г. Минск): Центральный (19 850), Советский (14 910), Первомайский (11 960).\n"
        "| Регион | План | Факт | Откл. |\n"
        "| --- | --- | --- | --- |\n"
        "| г. Минск (3 инспекции) | 44 100 | 46 720 | +2 620 |\n"
        "Все 3 инспекции с плюсом дали +2 620, а 2 отстающие — -951."
    )
    client = _Seq([reply])
    ans = try_chat_answer(source, "Проанализируй по регионам", client=client)
    assert "44 100" in ans
    assert "46 720" in ans
    assert "2 620" in ans
    assert "-951" in ans
    assert "| |" not in ans

    # Check _without_stray safety on genuinely unverified rows + г. Минск abbreviation
    corrupted_check = _without_stray(
        "Топ-3 (все — г. Минск) выросли.\n| Заглушка | 999999 |\nВыдумка 888888 руб.",
        ["999999", "888888"],
    )
    assert "все — г. Минск" in corrupted_check
    assert "| Заглушка |" not in corrupted_check


def test_opening_fallback_strips_internal_memory_scaffolding() -> None:
    from case3.chat_turn import opening_fallback, try_opening

    decorated = (
        "Собери презентацию на 6 слайдов по итогам поступлений.\n\n"
        "Числа из реплик пользователя (его слова, не ответ модели):\n50 добавить\n\n"
        "Карточка этого чата (не Source).\nдокументы: Документ."
    )
    fb = opening_fallback("presentation", decorated)
    assert "Собери презентацию на 6 слайдов" in fb
    assert "Числа из реплик" not in fb
    assert "Карточка этого чата" not in fb

    seen_prompts: list[str] = []

    class _FakeLLM:
        def complete(self, *, system: str, user_text: str, reasoning: str = "off", **_kw) -> str:
            seen_prompts.append(user_text)
            return "Собираю презентацию по поступлениям."

    spoken = try_opening("presentation", decorated, client=_FakeLLM())
    assert spoken == "Собираю презентацию по поступлениям."
    assert seen_prompts and "Числа из реплик" not in seen_prompts[0]


def test_filter_date_and_wide_table_column_do_not_trigger_false_fact_conflict() -> None:
    from case3.chat_turn import fact_conflict

    source = (
        "# Данные дашборда\n\n"
        "## Заголовок\nПоступления за январь 2025 года\n\n"
        "## Фильтры\n- Отчётная дата: на 1 февраля 2025\n\n"
        "## Таблица PDF\n"
        "| Округ | Инспекция | План | Ожидание | Факт | Выполнение, % |\n"
        "| --- | --- | --- | --- | --- | --- |\n"
        "| Южный | ИМНС по Гомельской области | 90 000,0 | 95 000,0 | 105 865,2 | 105,9% |\n"
    )
    # 1. "на 1 февраля 2025" must not clash with "2025" near "Поступления"
    assert (
        fact_conflict(
            "Какие поступления были при фильтре на 1 февраля 2025 у Гомельской области?",
            source,
        )
        is None
    )
    # 2. A number from a far column (105 865,2) of the same named row must not clash with column 1 (90 000,0)
    assert (
        fact_conflict(
            "По Гомельской области факт 105 865,2, почему так?",
            source,
        )
        is None
    )


def test_chat_answer_strips_raw_chartjs_json_fences() -> None:
    raw_json_reply = (
        "Построил график фактических поступлений за январь.\n\n"
        "```json\n"
        '{"type": "bar", "data": {"labels": ["Минск"], "datasets": [{"data": [100]}]}}\n'
        "```\n"
    )
    ans = try_chat_answer(
        "Минск: 100.",
        "Построй в чате график поступлений",
        client=_Fake(raw_json_reply),
    )
    assert '"datasets"' not in ans
    assert "```json" not in ans
    assert "Построил график" in ans


def test_chat_answer_Rejects_thousands_collapsed_into_decimal() -> None:
    source = (
        "| Инспекция | Факт |\n"
        "| --- | --- |\n"
        "| ИМНС по Гомельской области | 105 865,2 |\n"
        "| ИМНС по Минской области | 94 073,5 |\n"
    )
    client = _Seq(
        [
            "У Гомельской области факт 105,8652, а у Минской — 94,0735.",
            "У Гомельской области факт 105 865,2, а у Минской — 94 073,5.",
        ]
    )
    ans = try_chat_answer(source, "Назови факт по областям", client=client)
    assert client.calls == 2
    assert "105,8652" not in ans
    assert "105 865,2" in ans


def test_chart_followup_rejects_stale_prior_turn_reserve_calculation() -> None:
    source = (
        "| Код ИМНС | Область | Инспекция | План, тыс. руб. | Факт, тыс. руб. | Выполнение (%) |\n"
        "| --- | --- | --- | --- | --- | --- |\n"
        "| 101 | г. Минск | ИМНС по Центральному району | 179 500,0 | 184 520,0 | 102,8% |\n"
        "| 403 | Брестская область | ИМНС по Пинскому району | 12 200,0 | 10 790,0 | 88,4% |\n"
    )
    intent = (
        "Построй в чате столбчатый график факта поступлений по областям.\n\n"
        "Числа из реплик пользователя (его слова, не ответ модели):\n"
        "450 резерв\n\n"
        "Разговор этого чата (не Source).\n"
        "Ход 2. Запрос: Если Пинскому району добавить резерв 450 тыс. руб., сколько станет его факт?\n"
        "Ответ (chat): Новый факт: 11 240,0 тыс. руб. Новое выполнение плана: 92,1%."
    )
    client = _Seq(
        [
            "**Строка:** 403\n**Новый факт:** 11 240,0 тыс. руб. (10 790,0 + 450,0)\n**Новое выполнение плана:** 92,1%",
            "По факту поступлений по областям: г. Минск — 184 520,0 тыс. руб., Брестская область — 10 790,0 тыс. руб.",
        ]
    )
    ans = try_chat_answer(source, intent, client=client)
    assert client.calls == 2
    assert "11 240" not in ans
    assert "92,1" not in ans
    assert "184 520" in ans
    assert "ТЕКУЩИЙ ЗАПРОС" in client.seen[0]
    assert client.seen[0].rindex("ТЕКУЩИЙ ЗАПРОС") > client.seen[0].rindex("92,1%")


def test_chart_followup_keeps_prior_numbers_when_scenario_explicitly_requested() -> None:
    source = "| Область | План | Факт |\n| --- | --- | --- |\n| Брестская область | 12 200,0 | 10 790,0 |\n"
    intent = (
        "Построй график по этому сценарию с резервом.\n\n"
        "Числа из реплик пользователя (его слова, не ответ модели):\n"
        "450 резерв\n\n"
        "Разговор этого чата (не Source).\n"
        "Ход 2. Запрос: Добавь резерв 450.\n"
        "Ответ (chat): Новый факт 11 240,0, выполнение 92,1%."
    )
    client = _Seq(["По сценарию с резервом 450 новый факт Брестской области 11 240,0 (92,1%)."])
    ans = try_chat_answer(source, intent, client=client)
    assert client.calls == 1
    assert "11 240" in ans
    assert "92,1" in ans


def test_chart_followup_generic_metric_stem_in_user_numbers_does_not_trigger_prior_scenario() -> None:
    source = (
        "| Область | План, тыс. руб. | Факт, тыс. руб. |\n"
        "| --- | --- | --- |\n"
        "| г. Минск | 179 500,0 | 184 520,0 |\n"
        "| Брестская область | 59 200,0 | 57 846,4 |\n"
    )
    intent = (
        "Построй в чате столбчатый график факта поступлений по областям.\n\n"
        "Числа из реплик пользователя (его слова, не ответ модели):\n"
        "450 факт\n\n"
        "Разговор этого чата (не Source).\n"
        "Ход 2. Запрос: Если к факту добавить 450, сколько станет?\n"
        "Ответ (chat): Новый факт 58 296,4."
    )
    client = _Seq(
        [
            "Новый факт с добавкой 450 составит 58 296,4.",
            "Факт поступлений по областям: г. Минск — 184 520,0, Брестская область — 57 846,4.",
        ]
    )
    ans = try_chat_answer(source, intent, client=client)
    assert client.calls == 2
    assert "58 296,4" not in ans
    assert "184 520,0" in ans


def test_generate_chat_charts_strips_stale_user_number_on_non_scenario_turn(tmp_path: Path, monkeypatch) -> None:
    from case3.chat_turn import generate_chat_charts

    source = "| Область | Факт |\n| --- | --- |\n| г. Минск | 184 520 |\n| Брестская область | 57 846 |\n"
    intent = (
        "Построй в чате столбчатый график факта поступлений по областям.\n\n"
        "Числа из реплик пользователя (его слова, не ответ модели):\n"
        "450 резерв\n\n"
        "Разговор этого чата (не Source).\n"
        "Ход 2. Запрос: Добавь резерв 450.\n"
        "Ответ (chat): Новый факт 11 240."
    )

    class _ChartLLM:
        def complete(self, *, system: str, user_text: str, reasoning: str = "off", **_kw) -> str:
            return (
                '```json\n{"charts": [{"id": "cht_01", "type": "bar", "caption": "Факт", '
                '"html": "<canvas id=\\\'c\\\'></canvas><script>new Chart(document.getElementById(\\\'c\\\'), '
                '{type:\\\'bar\\\',data:{labels:[\\\'Минск\\\',\\\'Резерв\\\'],datasets:[{label:\\\'Факт\\\',data:[184520,450]}]}});</script>"}]}\n```'
            )

    monkeypatch.setattr("case3.charts.render_charts_batch", lambda items: {"cht_01": {"ok": True}})
    charts, _status = generate_chat_charts(
        source,
        intent,
        max_charts=1,
        figs_dir=tmp_path / "figs",
        charts_dir=tmp_path / "charts",
        client=_ChartLLM(),
    )
    # 450 from Turn 2 must NOT be grounded on Turn 3 (chart dropped or 450 stripped)
    assert not any("450" in str(c.get("html") or "") for c in charts)


def test_try_chat_answer_strips_leaked_chart_json_blocks():
    source = "| Область | Сумма |\n| --- | --- |\n| Минская | 100 |\n| Гомельская | 40 |\n"
    leaked = (
        "Минская собрала 100, Гомельская 40.\n\n"
        "```json\n"
        '{"charts": [{"id": "cht_01", "type": "bar", "data": [100, 40]}]}\n'
        "```\n\n"
        "| Область | Сумма |\n| --- | --- |\n| Минская | 100 |\n| Гомельская | 40 |\n"
    )
    ans = try_chat_answer(source, "построй график по областям", client=_Seq([leaked]))
    assert "```json" not in ans
    assert '"charts"' not in ans
    assert "Минская собрала 100" in ans
    assert "| Область | Сумма |" in ans

    bare = (
        '{"charts": [{"id": "cht_01", "type": "bar", "data": [100, 40]}]}\n\n'
        "Минская собрала 100, Гомельская 40."
    )
    ans_bare = try_chat_answer(source, "построй график по областям", client=_Seq([bare]))
    assert '"charts"' not in ans_bare
    assert "Минская собрала 100" in ans_bare


def test_generate_chat_charts_retries_once_when_first_json_is_invalid(tmp_path: Path, monkeypatch) -> None:
    from case3.chat_turn import generate_chat_charts

    source = "| Область | Факт |\n| --- | --- |\n| Минск | 184 520 |\n| Брест | 57 846 |\n"

    class _RetryChartLLM:
        def __init__(self) -> None:
            self.calls = 0

        def complete(self, *, system: str, user_text: str, reasoning: str = "off", **_kw) -> str:
            self.calls += 1
            if self.calls == 1:
                return "Невалидный ответ без json"
            return (
                '```json\n{"charts": [{"id": "cht_01", "type": "bar", "caption": "Факт", '
                '"html": "<canvas id=\\\'c\\\'></canvas><script>new Chart(document.getElementById(\\\'c\\\'), '
                '{type:\\\'bar\\\',data:{labels:[\\\'Минск\\\',\\\'Брест\\\'],datasets:[{label:\\\'Факт\\\',data:[184520,57846]}]}});</script>"}]}\n```'
            )

    monkeypatch.setattr("case3.charts.render_charts_batch", lambda items: {"cht_01": {"ok": True}})
    llm = _RetryChartLLM()
    charts, status = generate_chat_charts(
        source,
        "построй график",
        max_charts=1,
        figs_dir=tmp_path / "figs",
        charts_dir=tmp_path / "charts",
        client=llm,
    )
    assert llm.calls == 2
    assert len(charts) == 1
    assert status.get("cht_01", {}).get("ok") is True


def test_without_stray_never_leaves_header_only_tables() -> None:
    from case3.chat_turn import _without_stray

    md = (
        "Краткий вывод.\n\n"
        "| Регион | Выдумка |\n"
        "| --- | --- |\n"
        "| Минск | 999999 |\n"
        "| Брест | 888888 |\n\n"
        "| Регион | Факт |\n"
        "| --- | --- |\n"
        "| Минск | 184 520 |\n"
        "| Брест | 999999 |"
    )
    cleaned = _without_stray(md, ["999999", "888888"])
    assert "| Регион | Выдумка |" not in cleaned
    assert "| Минск | 184 520 |" in cleaned
    assert "| Регион | Факт |" in cleaned
    assert "999999" not in cleaned


def test_streamed_answer_is_not_rewritten_by_a_second_draft() -> None:
    """A visible stream stays. A later invented digit is cut in place, not by a new essay."""
    source = "| Область | Факт |\n| --- | --- |\n| Минск | 10 |\n| Брест | 8 |\n"
    first = (
        "Сравнить эти два снимка за один период не получится: это не разные месяцы. "
        "Брестская область в файле есть, выдуманная доля 77 не нужна."
    )

    class _StreamOnce:
        def __init__(self) -> None:
            self.stream_calls = 0
            self.complete_calls = 0

        def stream(self, **_kw):
            self.stream_calls += 1
            yield first

        def complete(self, **_kw):
            self.complete_calls += 1
            return "Совсем другой ответ про кассу 20."

    replaced: list[str] = []
    client = _StreamOnce()
    ans = try_chat_answer(
        source,
        "сравни снимки в динамике",
        client=client,  # type: ignore[arg-type]
        on_delta=lambda _piece: None,
        on_replace=lambda full: replaced.append(full),
    )
    assert client.stream_calls == 1
    assert client.complete_calls == 0
    assert "не получится" in ans
    assert "77" not in ans
    assert "кассу" not in ans
    assert replaced
    assert all(item.startswith("Сравнить эти два снимка") for item in replaced)


def test_blank_chart_html_is_dropped(tmp_path: Path, monkeypatch) -> None:
    from case3.chat_turn import chart_plot_blank, generate_chat_charts

    assert chart_plot_blank(
        "new Chart(c,{type:'line',data:{labels:['А'],datasets:[{data:[0,null]}]}})"
    )
    assert not chart_plot_blank(
        "new Chart(c,{type:'bar',data:{labels:['А'],datasets:[{data:[10,20]}]}})"
    )

    class _EmptyChart:
        def complete(self, **_kw) -> str:
            return (
                '```json\n{"charts":[{"id":"cht_01","type":"line","caption":"Пусто",'
                '"html":"<canvas id=\'c\'></canvas><script>new Chart(c,{type:\'line\','
                'data:{labels:[\'Акцизы\'],datasets:[{data:[0,0]}]}});</script>"}]}\n```'
            )

    monkeypatch.setattr("case3.charts.render_charts_batch", lambda items: {"cht_01": {"ok": True}})
    charts, _status = generate_chat_charts(
        "| Вид | Факт |\n| --- | --- |\n| Акцизы | 10 |\n",
        "сравни динамику",
        max_charts=1,
        figs_dir=tmp_path / "figs",
        charts_dir=tmp_path / "charts",
        client=_EmptyChart(),  # type: ignore[arg-type]
    )
    assert charts == []


def test_try_chat_answer_grounds_table_shares_ranks_and_header_units_without_retry() -> None:
    source = (
        "| Область | Факт | План |\n"
        "| --- | --- | --- |\n"
        "| Минская | 105 865,2 | 100 000,0 |\n"
        "| Гомельская | 94 073,0 | 95 000,0 |\n"
    )
    reply = (
        "Анализ таблицы:\n\n"
        "| № | Область | Факт, млн | Доля, % | Выполнение, % |\n"
        "| --- | --- | --- | --- | --- |\n"
        "| 1 | Минская | 105,9 | 52,9 | 105,9 |\n"
        "| 2 | Гомельская | 94,1 | 47,1 | 99,0 |\n"
    )

    class _OnceStreamLLM:
        def __init__(self) -> None:
            self.calls = 0

        def stream(self, **_kw):
            self.calls += 1
            if self.calls > 1:
                raise AssertionError("try_chat_answer triggered an unexpected retry!")
            yield reply

    replaced: list[str] = []
    client = _OnceStreamLLM()
    ans = try_chat_answer(
        source,
        "проанализируй таблицу",
        client=client,  # type: ignore[arg-type]
        on_delta=lambda _d: None,
        on_replace=lambda full: replaced.append(full),
    )
    assert client.calls == 1
    assert replaced == []
    assert "| 1 | Минская | 105,9 | 52,9 | 105,9 |" in ans
    assert "| 2 | Гомельская | 94,1 | 47,1 | 99,0 |" in ans


def test_generate_chat_charts_preserves_prev_type_hint_when_color_only_edit(tmp_path: Path, monkeypatch) -> None:
    from case3.chat_turn import generate_chat_charts

    seen: list[str] = []

    class _ColorLLM:
        def complete(self, *, system: str, user_text: str, **_kw) -> str:
            seen.append(user_text)
            return (
                '```json\n{"charts": [{"id": "cht_01", "type": "pie", "caption": "Доли", '
                '"html": "<canvas id=\'c\'></canvas><script>new Chart(document.getElementById(\'c\'), '
                '{type:\'pie\',data:{labels:[\'Минск\',\'Брест\'],datasets:[{data:[184520,57846]}]}});</script>"}]}\n```'
            )

    monkeypatch.setattr("case3.charts.render_charts_batch", lambda items: {"cht_01": {"ok": True}})
    generate_chat_charts(
        "| Регион | Факт |\n| --- | --- |\n| Минск | 184 520 |\n| Брест | 57 846 |\n",
        "сделай оранжевым",
        max_charts=1,
        figs_dir=tmp_path / "figs",
        charts_dir=tmp_path / "charts",
        client=_ColorLLM(),
        previous_chart={"id": "cht_02", "type": "pie", "caption": "Доли", "html": "<canvas id='c'></canvas>"},
    )
    assert seen and "СОХРАНИ type=pie" in seen[0]
