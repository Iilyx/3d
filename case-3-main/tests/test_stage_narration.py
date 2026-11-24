"""Model step lines stay inside the beats of this job."""

from case3.stage_narration import beats_for, narrate_stages, parse_stage_lines


def test_chat_beats_are_read_and_write() -> None:
    assert beats_for("chat") == ("source", "layout")


def test_parse_keeps_only_beats_for_this_job() -> None:
    raw = """
    {"lines":[
      {"id":"source","text":"Смотрю поступления за январь."},
      {"id":"slides_pack","text":"Пакую презентацию."},
      {"id":"pdf","text":"Готово, PDF собран."},
      {"id":"layout","text":"Пишу разбор этих чисел."}
    ]}
    """
    lines = parse_stage_lines(raw, "report")
    assert lines == {
        "source": "Смотрю поступления за январь.",
        "layout": "Пишу разбор этих чисел.",
    }


def test_narrate_asks_the_model_and_drops_a_blank() -> None:
    seen: dict[str, str] = {}

    def complete(*, system: str, user_text: str, reasoning: str = "") -> str:
        seen["system"] = system
        seen["user"] = user_text
        seen["reasoning"] = reasoning
        return '{"lines":[{"id":"layout","text":"Разбираю вопрос про январь."}]}'

    assert narrate_stages("что с январём", "chat", complete) == {
        "layout": "Разбираю вопрос про январь.",
    }
    assert "layout" in seen["user"]
    assert seen["reasoning"] == "off"
