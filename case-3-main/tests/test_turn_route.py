from case3.turn_route import resolve_turn


def test_word_and_spravka_leave_chat():
    assert resolve_turn("Сделай word", None) == "report"
    assert resolve_turn("сделай справку по областям", None) == "report"
    assert resolve_turn("Собери ворд", None) == "report"
    assert resolve_turn("что в справке?", "report") == "chat"


def test_a_question_does_not_rebuild_because_the_plaque_is_on():
    assert resolve_turn("Какая доля Минской?", "report") == "chat"
    assert resolve_turn("что в отчёте по Гомельской", "report") == "chat"
    assert resolve_turn("что на слайде", "presentation") == "chat"


def test_question_stays_chat_even_if_plaque_is_report():
    assert resolve_turn("Проанализируй отчёт и разложи цифры", "report") == "chat"


def test_analyze_without_an_artifact_noun_uses_the_plaque():
    assert resolve_turn("проанализируй регионы", "report") == "report"
    assert resolve_turn("сравни области", "report") == "report"
    assert resolve_turn("посчитай доли", "presentation") == "presentation"
    assert resolve_turn("проанализируй регионы", None) == "chat"
    assert resolve_turn("не делай отчёт, просто разбери цифры", "report") == "chat"


def test_explicit_deck_wins_over_plaque_and_over_analyze():
    assert resolve_turn("Проанализируй и собери презентацию", "report") == "presentation"


def test_a_chart_request_runs_in_chat_unless_report_requested():
    assert resolve_turn("Построй график по областям", None) == "chat"
    assert resolve_turn("Нарисуй диаграмму продаж", None) == "chat"
    assert resolve_turn("Построй график по областям", "report") == "chat"
    assert resolve_turn("Сделай отчёт с графиками продаж", None) == "report"
    assert resolve_turn("Нарисуй схему онбординга", None) == "diagram"


def test_why_without_question_mark_and_chart_request_stay_chat_under_plaque():
    from case3.turn_route import wants_chat_chart

    assert resolve_turn("почему в Гомеле просадка", "report") == "chat"
    assert resolve_turn("построй график по регионам", "report") == "chat"
    assert wants_chat_chart("построй график по регионам") is True


def test_explicit_diagram_and_report():
    assert resolve_turn("Нарисуй схему онбординга", None) == "diagram"
    assert resolve_turn("Напиши отчёт по этим цифрам", None) == "report"


def test_plaque_is_the_default_when_the_text_names_no_action():
    assert resolve_turn("Выручка 10 и 12, доля 30%", "presentation") == "presentation"
    assert resolve_turn("Выручка 10 и 12, доля 30%", None) == "chat"


def test_bare_artifact_noun_without_analyze_is_a_request():
    assert resolve_turn("Нужна схема процесса оплаты", None) == "diagram"


def test_empty_message_uses_plaque_or_chat():
    assert resolve_turn("", "diagram") == "diagram"
    assert resolve_turn("   ", None) == "chat"


def test_negated_artifact_is_not_a_request():
    assert resolve_turn("не делай отчёт, просто разбери цифры", None) == "chat"
    assert resolve_turn("без схемы, расскажи про оплату", "diagram") == "chat"
    assert resolve_turn("не презентацию, сделай отчёт", None) == "report"


def test_describe_stays_chat_even_if_the_noun_is_present():
    assert resolve_turn("Опиши отчёт по этим цифрам", "report") == "chat"
    assert resolve_turn("Кратко сделай презу", None) == "presentation"


def test_report_with_diagram_stays_report_not_diagram_only():
    assert resolve_turn("Сделай отчёт с таблицей и схемой", "report") == "report"
    assert resolve_turn("Сделай отчёт с таблицей и схемой", None) == "report"
    assert resolve_turn("Собери презентацию со схемой", "presentation") == "presentation"
    assert resolve_turn("Собери презентацию со схемой", None) == "presentation"


def test_a_declined_comparison_does_not_ask_for_a_chart():
    from case3.turn_route import answer_declines_chart

    assert answer_declines_chart(
        "Сравнить показатели между двумя снимками в динамике не получится: "
        "это не разные месяцы."
    )
    assert answer_declines_chart("Минск лидирует с фактом 120.") is False


def test_wants_and_auto_chat_chart_cover_visual_and_numeric_analysis():
    from case3.turn_route import should_auto_chat_chart, wants_chat_chart

    assert wants_chat_chart("визуализируй данные по областям") is True
    assert wants_chat_chart("покажи наглядно структуру доходов") is True
    assert wants_chat_chart("без визуализации, просто текст") is False

    rich_table = (
        "| Область | Факт | План |\n"
        "| --- | --- | --- |\n"
        "| Минск | 184 520 | 170 000 |\n"
        "| Брест | 57 846 | 55 000 |\n"
        "| Гомель | 61 200 | 60 000 |\n"
    )
    assert should_auto_chat_chart("сравни области", rich_table, "Минск лидирует.") is True
    assert should_auto_chat_chart("какие доли по регионам?", rich_table, "Минск 60%.") is True
    assert should_auto_chat_chart("без графика сравни области", rich_table, "Минск лидирует.") is False
    assert should_auto_chat_chart("привет, как дела?", rich_table, "Привет!") is False
    assert should_auto_chat_chart("сравни области", "короткая заметка без таблицы", "Ок.") is False
