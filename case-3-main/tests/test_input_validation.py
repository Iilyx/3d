from __future__ import annotations

import pytest

from case3.input_validation import validate_input_heuristics


def test_ui_block_is_not_user_text_and_empty_chat_gets_brief():
    from case3.generate import DEFAULT_INTENT
    from case3.input_validation import user_text_before_ui, with_default_brief
    from case3.intent_compose import build_intent_from_ui

    intent = build_intent_from_ui(
        chat="",
        chart_types=[],
        max_charts=2,
        max_images=0,
        forbid_charts=False,
        forbid_images=True,
        chart_auto=True,
        output_mode="report",
    )
    user = user_text_before_ui(intent)
    assert user == ""
    valid, _ = validate_input_heuristics("привет", user)
    assert not valid
    valid, _ = validate_input_heuristics("", user)
    assert not valid
    valid, msg = validate_input_heuristics("Выручка 10 млн, доля 35%", user)
    assert valid and msg is None
    briefed = with_default_brief(intent, user)
    assert briefed.startswith(DEFAULT_INTENT)
    assert "Требования UI:" in briefed
    typed = with_default_brief("свой бриф\n\nТребования UI:\n- x", "свой бриф")
    assert typed.startswith("свой бриф")


def test_greeting_file_with_empty_intent_is_refused():
    valid, msg = validate_input_heuristics("привет", "")
    assert not valid
    assert "недостаточно данных" in msg.lower()


def test_factual_file_with_empty_intent_passes():
    valid, msg = validate_input_heuristics("Выручка 10 млн, доля 35%", "")
    assert valid
    assert msg is None


def test_empty_and_whitespace():
    valid, msg = validate_input_heuristics("", "")
    assert not valid
    assert "недостаточно данных" in msg.lower()

    valid, msg = validate_input_heuristics("   \n\t  ", "   ")
    assert not valid
    assert "недостаточно данных" in msg.lower()


def test_short_garbage():
    for garbage in ["а", "1", "...", "йц", "abc"]:
        valid, msg = validate_input_heuristics(garbage, "")
        assert not valid
        assert "недостаточно данных" in msg.lower()
    # In chat mode, any short meaningful question or greeting passes to LLM!
    for chat_msg in ["привет", "ку", "кто ты?", "как дела?", "помоги с дашбордом", "что умеешь?"]:
        valid, msg = validate_input_heuristics(chat_msg, chat_msg, output_mode="chat")
        assert valid, f"Expected chat mode to pass '{chat_msg}' to LLM"
        assert msg is None
    # Empty or keyboard mash in chat mode is still rejected
    valid_empty, _ = validate_input_heuristics("", "", output_mode="chat")
    assert not valid_empty
    valid_mash, _ = validate_input_heuristics("ывафыавфа", "ывафыавфа", output_mode="chat")
    assert not valid_mash


def test_repetitive_keyboard_smash():
    for smash in ["aaaaaaa", "asdfasdfasdf", "йцукенйцукен", "ахахахахахах"]:
        valid, msg = validate_input_heuristics(smash, "")
        assert not valid
        assert "недостаточно данных" in msg.lower()


def test_pure_greetings_and_intent_triggers():
    triggers = [
        "привет",
        "здравствуйте",
        "ку",
        "hello",
        "сделай отчет",
        "отчет",
        "презентация",
        "сделай презу",
        "схема",
        "покажи схему",
        "сделай красиво",
        "как дела",
        "тест",
        "Привет, сделай отчет пожалуйста",
        "Сделай презентацию",
    ]
    for text in triggers:
        valid, msg = validate_input_heuristics(text, "")
        assert not valid, f"Expected invalid for '{text}'"
        assert "недостаточно данных" in msg.lower()


def test_mode_tailored_message():
    _, msg_report = validate_input_heuristics("привет", "", output_mode="report")
    assert "отчёта" in msg_report.lower() or "отчета" in msg_report.lower()

    _, msg_deck = validate_input_heuristics("привет", "", output_mode="presentation")
    assert "презентации" in msg_deck.lower()

    _, msg_diag = validate_input_heuristics("привет", "", output_mode="diagram")
    assert "схемы" in msg_diag.lower()


def test_silly_or_informal_requests_with_numbers_pass():
    queries = [
        "Вася съел 3 яблока, Маша 5 груш. Сделай отчет",
        "наш стартап заработал 100 баксов за январь и 200 за февраль",
        "было 10 пользователей, стало 50",
        "в 2024 году рост составил 15%",
        "3 шага: шаг 1 регистрация, шаг 2 оплата, шаг 3 получение",
    ]
    for text in queries:
        valid, msg = validate_input_heuristics(text, "")
        assert valid, f"Expected valid for '{text}', got msg: {msg}"
        assert msg is None


def test_bullet_points_and_tables_pass():
    structured = (
        "- пункт 1\n"
        "- пункт 2\n"
        "- пункт 3"
    )
    valid, msg = validate_input_heuristics(structured, "")
    assert valid
    assert msg is None

    table = (
        "Имя | Роль\n"
        "Иван | Разработчик\n"
        "Ольга | Дизайнер"
    )
    valid, msg = validate_input_heuristics(table, "")
    assert valid
    assert msg is None


def test_substantial_descriptive_text_passes():
    text = "Система управления складом включает модуль учета остатков, интерфейс оператора и интеграцию с 1С."
    valid, msg = validate_input_heuristics(text, "")
    assert valid
    assert msg is None


def test_attachments_do_not_bypass_heuristic_check_when_data_free():
    valid, msg = validate_input_heuristics("привет", "", has_attachments=True)
    assert not valid
    assert "недостаточно данных" in msg.lower()

    valid, msg = validate_input_heuristics("ывафыавфа", "", has_attachments=True)
    assert not valid
    assert "недостаточно данных" in msg.lower()


def test_attachments_with_meaningful_request_pass():
    valid, msg = validate_input_heuristics(
        "Вот фото цеха, составь отчет о запуске линии упаковки",
        "",
        has_attachments=True,
    )
    assert valid
    assert msg is None


def test_current_turn_user_text_strips_chat_memory():
    from case3.input_validation import current_turn_user_text, user_text_before_ui

    intent = (
        "Какая доля у Минской области?\n\n"
        "Разговор этого чата (не Source).\n"
        "Запрос: построй график по регионам\n\n"
        "Требования UI:\n- палитра: atelier"
    )
    assert "Разговор этого чата" in user_text_before_ui(intent)
    assert "Требования UI" not in user_text_before_ui(intent)
    assert current_turn_user_text(intent) == "Какая доля у Минской области?"
