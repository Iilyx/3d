"""Chat name follows the screen, not the command the user typed."""

from case3.chat_turn import session_title

_SCREEN = """\
# Данные дашборда

## Заголовок
Поступления за январь 2025 года (с нарастающим итогом)
"""


def test_dashboard_heading_names_the_chat() -> None:
    assert (
        session_title("дай мне название данных", _SCREEN)
        == "Поступления за январь 2025 года"
    )


def test_a_plain_question_keeps_its_topic() -> None:
    assert session_title("сколько выручка в Москве") == "Сколько выручка в Москве"


def test_a_bare_command_without_a_screen_is_not_the_title() -> None:
    assert session_title("дай мне название данных") == "Разбор"
