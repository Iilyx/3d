"""Adversarial tests for chat number grounding and fact conflicts."""

from case3.chat_turn import (
    fact_conflict,
    try_chat_answer,
    _answering_choice,
    choice_instruction,
)


class _Seq:
    def __init__(self, texts: list[str]) -> None:
        self.texts = list(texts)
        self.calls = 0

    def stream(self, **kwargs):
        self.calls += 1
        yield self.texts.pop(0)


class _Boom:
    def stream(self, **_kwargs):
        raise AssertionError("model should not be called")
        yield ""


def test_attack1_assistant_99_in_memory_is_not_allowed_in_answer():
    """Ответ: 99 must not enter the allow-list; model «было 99» → question with «нет»."""
    prior = (
        "Разбери кассу\n\n"
        "Разговор этого чата (не Source).\n"
        "Ход 1. Запрос: касса 20\n"
        "Ответ: В прошлый раз было 99, это не из документа."
    )
    client = _Seq(["Касса была 99 по моей оценке.", "Снова было 99."])
    text = try_chat_answer(
        "Касса была 20.",
        prior,
        client=client,
    )
    assert client.calls == 2
    assert "нет" in text.lower()
    assert "99" in text
    assert "было 99" not in text.lower()


def test_attack2_same_digit_different_subject_is_still_kassa_conflict():
    """касса 40 vs doc касса 20 + выручка 40 — conflict on касса, not masked by 40 elsewhere."""
    clash = fact_conflict("Касса была 40, разбери", "Касса была 20, выручка 40.")
    assert clash is not None
    word, doc_n, user_n = clash
    assert word.lower().startswith("касс")
    assert doc_n == "20"
    assert user_n == "40"

    text = try_chat_answer(
        "Касса была 20, выручка 12.",
        "Касса была 40, разбери",
        client=_Boom(),
    )
    assert "20" in text and "40" in text
    assert "оставить" in text


def test_attack3_short_reply_40_after_conflict_is_choice_not_reask():
    """User picks 40 after conflict question — model may say 40, no second ask."""
    prior = (
        "40\n\n"
        "Разговор этого чата (не Source).\n"
        "Ход 1. Запрос: касса была 40\n"
        "Ответ: В документе у «Касса» стоит 20, ты написал 40. "
        "Напиши 40, чтобы оставить твоё, или 20, чтобы оставить документ."
    )
    assert _answering_choice(prior)
    client = _Seq(["Касса была 40, как ты выбрал."])
    text = try_chat_answer(
        "Касса была 20.",
        prior,
        client=client,
    )
    assert client.calls == 1
    assert "оставить" not in text
    assert "40" in text
    assert "нет" not in text.lower()


def test_attack4_bez_chisla_choice_not_conflict_and_no_digit_required():
    """«без числа» resolves invention flow without a new fact conflict."""
    prior = (
        "без числа\n\n"
        "Разговор этого чата (не Source).\n"
        "Ход 1. Запрос: динамика выручки\n"
        "Ответ: В документах и в твоём сообщении нет чисел 15. "
        "Напиши нужное число, если его надо учесть, или напиши «без числа»."
    )
    # Not a conflict-resolution choice pattern — must not look like касса clash.
    clash = fact_conflict("без числа", "Касса была 20, выручка 40.")
    assert clash is None
    assert _answering_choice(prior)

    client = _Seq(["Динамику опишу словами, без новых цифр."])
    text = try_chat_answer(
        "Выручка была 10, стала 12.",
        prior,
        client=client,
    )
    assert client.calls == 1
    assert "оставить" not in text


def test_attack5_user_percent_7_allowed_despite_other_percents_in_doc():
    """User «выросла на 7%» may be repeated; other % in source do not block."""
    client = _Seq(["Выручка выросла на 7%, как ты написал. Было 10, стало 12."])
    text = try_chat_answer(
        "Выручка была 10, стала 12.",
        "По твоим данным выручка выросла на 7%",
        client=client,
    )
    assert client.calls == 1
    assert "7" in text
    assert "нет" not in text.lower()


def test_attack6_comma_decimal_equivalent_to_dot_no_false_conflict():
    """12,5 in user vs 12.5 in doc — same number, no clash; model may echo 12,5."""
    clash = fact_conflict("Касса 12,5", "Касса 12.5.")
    assert clash is None

    client = _Seq(["Касса составила 12,5 по твоим словам."])
    text = try_chat_answer(
        "Касса 12.5.",
        "Уточни кассу: 12,5",
        client=client,
    )
    assert client.calls == 1
    assert "оставить" not in text
    assert "12" in text


def test_a_word_between_the_subject_and_the_number_still_conflicts():
    """«в кассе теперь 30» against «Касса … 20» must ask, not accept 30."""
    clash = fact_conflict("В кассе теперь 30.", "Касса за смену 20 рублей.")
    assert clash is not None
    word, doc_n, user_n = clash
    assert word.casefold().startswith("касс")
    assert doc_n == "20" and user_n == "30"

    text = try_chat_answer(
        "Касса за смену 20 рублей.",
        "В кассе теперь 30.",
        client=_Boom(),
    )
    assert "20" in text and "30" in text
    assert "оставить" in text


def test_region_period_and_rank_are_not_a_cell_conflict():
    """A year, a rank, or «в N раза» next to a region is not a rival cell."""
    src = "Минская область | 105 865,2\nГомельская область | 80 100,0"
    assert fact_conflict("Покажи Минскую область за 2025", src) is None
    assert fact_conflict("Какая область в 2 раза лучше?", src) is None
    assert fact_conflict("Минская область 1 место?", src) is None


def test_region_cell_still_conflicts_when_the_user_names_another_sum():
    clash = fact_conflict(
        "В Минской области теперь 80.",
        "Минская область | 105 865,2",
    )
    assert clash is not None
    _word, doc_n, user_n = clash
    assert doc_n == "105 865,2"
    assert user_n == "80"


def test_chat_keeps_sobrano_and_drops_only_the_extra_number():
    source = "Минская область | 105 865,2"
    client = _Seq(
        [
            "Минская область лидирует. Собрано 105 865,2. Доля составила 125.",
            "Минская область лидирует. Собрано 105 865,2. Доля составила 125.",
        ]
    )
    text = try_chat_answer(source, "Кто лидирует?", client=client)
    assert "собрано" in text.lower()
    assert "лидирует" in text.lower()
    assert "125" not in text
    assert "нет числа" not in text.lower()
    assert "нет чисел" not in text.lower()


def test_attack6b_slide_index_plus_real_conflict_in_one_message():
    """«слайд 3» plus касса 40 vs doc 20 — still one conflict question, model not called."""
    clash = fact_conflict(
        "почему на слайде 3 касса 40",
        "Касса была 20.",
    )
    assert clash is not None
    _, doc_n, user_n = clash
    assert doc_n == "20" and user_n == "40"

    text = try_chat_answer(
        "Касса была 20.",
        "почему на слайде 3 касса 40",
        client=_Boom(),
    )
    assert "20" in text and "40" in text


def test_choice_instruction_drops_user_number_when_doc_picked():
    note, drop = choice_instruction(
        "20\n\n"
        "Разговор этого чата (не Source).\n"
        "Ход 1. Запрос: касса 40\n"
        "Ответ: В документе у «касса» стоит 20, ты написал 40. "
        "Напиши 40, чтобы оставить твоё, или 20, чтобы оставить документ."
    )
    assert "20" in note
    assert "40" in drop or drop == {"40"}