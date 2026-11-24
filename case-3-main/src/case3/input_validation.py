"""Smart input validation for reports, presentations, and diagrams.

Detects unfeasible, empty, or data-free user requests early so the pipeline
does not generate dummy documents ("запрос сделан, данных нет") or invoke
heavy rendering (Docker TeX, Playwright, LibreOffice).

Guarantees that simple or informal queries with minimal facts/numbers
(e.g., "Вася съел 3 яблока, Маша 5 груш. Сделай отчет") pass through seamlessly.
"""

from __future__ import annotations

import re


class InsufficientDataError(ValueError):
    """Raised when user request or model output indicates insufficient data."""

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message

_COMMON_KEYBOARD_MASH = {
    "asdfghjkl",
    "asdfasdf",
    "qwertyqwerty",
    "qwerty",
    "йцукенйцукен",
    "йцукен",
    "фывапролдж",
    "фывапрол",
    "ывафыавфа",
    "фывафыва",
    "фыва",
    "ываф",
    "йцук",
    "ячсм",
    "ячсмить",
    "asdf",
    "asdfg",
    "zxcv",
    "qwer",
}

_TRIGGER_WORDS = {
    "привет",
    "здравствуйте",
    "добрый",
    "день",
    "вечер",
    "утро",
    "ку",
    "хай",
    "hello",
    "hi",
    "hey",
    "сделай",
    "сделать",
    "составь",
    "составить",
    "напиши",
    "написать",
    "подготовь",
    "подготовить",
    "покажи",
    "показать",
    "отчет",
    "отчёт",
    "отчета",
    "отчёта",
    "документ",
    "презентацию",
    "презентация",
    "презентации",
    "презу",
    "слайды",
    "схему",
    "схема",
    "схемы",
    "диаграмму",
    "диаграмма",
    "диаграммы",
    "пожалуйста",
    "плиз",
    "плииз",
    "красиво",
    "быстро",
    "как",
    "дела",
    "что",
    "ты",
    "умеешь",
    "помоги",
    "тест",
    "test",
    "проверка",
    "для",
    "меня",
    "мне",
    "нам",
    "наш",
    "наша",
    "по",
    "нужен",
    "нужна",
    "хочу",
}


_CAPABILITY = re.compile(
    r"(?i)^\s*(?:"
    r"что ты умеешь|что умеешь|что ты можешь|чем можешь помочь|"
    r"какие у тебя возможности"
    r")\s*\??\s*$"
)


def capability_reply(text: str | None) -> str:
    """Local answer. The capability list in the prompt is never read for this question."""
    if not _CAPABILITY.match((text or "").strip()):
        return ""
    return (
        "Могу разобрать приложенные данные в чате, собрать отчёт, схему или презентацию.\n\n"
        "По уже готовому файлу могу по фразе:\n"
        "- переписать или сократить раздел;\n"
        "- поправить ячейку, строку или пункт списка;\n"
        "- сменить вид графика, цвет или стиль слайда;\n"
        "- поправить схему одной фразой или отменить последний шаг.\n\n"
        "Числа беру только из ваших данных. Напишите вопрос по тексту или попросите отчёт."
    )


def _format_refusal_message(output_mode: str) -> str:
    mode = (output_mode or "report").strip().lower()
    if mode == "chat":
        return (
            "Напишите, что разобрать: вопрос, текст или документ с фактами. "
            "Пустое сообщение и случайный набор букв я не берусь разбирать."
        )
    if mode == "presentation":
        target = "презентации"
    elif mode == "diagram":
        target = "схемы"
    else:
        target = "отчёта"
    return (
        f"В запросе недостаточно данных для составления {target}. "
        "Пожалуйста, укажите конкретные факты, числа или описание задачи, "
        "либо прикрепите документ с исходными данными."
    )


def user_text_before_ui(intent: str | None) -> str:
    """Chat text before the injected UI block (preserving prior chat memory)."""
    text = intent or ""
    for marker in ("\n\nТребования UI:", "\nТребования UI:", "Требования UI:"):
        idx = text.find(marker)
        if idx != -1:
            text = text[:idx]
            break
    return text.strip()


def current_turn_user_text(intent: str | None) -> str:
    """Current turn chat text only, before injected chat memory or UI blocks."""
    text = user_text_before_ui(intent)
    markers = (
        "\n\nЧисла из реплик пользователя",
        "\n\nКарточка этого чата",
        "\n\nРазговор этого чата",
        "\n\nПредыдущий ход этого чата",
        "\n\nОдин прошлый ход",
    )
    earliest: int | None = None
    for marker in markers:
        idx = text.find(marker)
        if idx != -1 and (earliest is None or idx < earliest):
            earliest = idx
    if earliest is not None:
        text = text[:earliest]
    return text.strip()


def with_default_brief(intent: str | None, user_text: str) -> str:
    """After validation, an empty chat still gets the model brief."""
    if user_text.strip():
        return intent or ""
    from case3.generate import DEFAULT_INTENT

    rest = (intent or "").strip()
    if not rest:
        return DEFAULT_INTENT
    return f"{DEFAULT_INTENT}\n\n{rest}"


def validate_input_heuristics(
    source_text: str | None,
    intent: str | None,
    *,
    output_mode: str = "report",
    has_attachments: bool = False,
) -> tuple[bool, str | None]:
    """Fast local validation of user inputs.

    Returns (True, None) if inputs contain sufficient data signals,
    or (False, refusal_message) if the request is empty, nonsensical,
    or a pure trigger without substance. Attached user photos are
    illustrations and do not replace factual data.
    """
    combined = ((source_text or "") + "\n" + (intent or "")).strip()
    is_chat = (output_mode or "").strip().lower() == "chat"
    if not combined:
        return False, _format_refusal_message(output_mode)
    if not is_chat and len(combined) < 4:
        return False, _format_refusal_message(output_mode)

    # 1. Check for keyboard mash / repetitive characters
    text_for_mash = ((intent or "") if is_chat else combined).strip()
    raw_letters = "".join(re.findall(r"[a-zA-Zа-яА-ЯёЁ]", text_for_mash.lower()))
    if is_chat and not raw_letters and not re.search(r"\d", text_for_mash):
        return False, _format_refusal_message(output_mode)
    if len(raw_letters) >= 4:
        unique_letters = set(raw_letters)
        if len(unique_letters) <= 2:
            return False, _format_refusal_message(output_mode)
        if raw_letters in _COMMON_KEYBOARD_MASH:
            return False, _format_refusal_message(output_mode)
        if len(raw_letters) >= 8 and re.search(r"(.{2,4})\1{2,}", raw_letters):
            return False, _format_refusal_message(output_mode)

    # In chat mode, any non-empty, non-keyboard-mash message goes directly to the LLM!
    if is_chat:
        return True, None

    # 2. Strong data signals: digits, markdown lists, tables, key-values
    # If any digit is present (e.g. counts, percentages, dates, metrics), always pass
    if re.search(r"\d", combined):
        return True, None

    # Markdown bullet lists or numbered lists
    if re.search(r"(?:^|\n)\s*[-*•]\s+\S+", combined):
        return True, None

    # Markdown tables
    if re.search(r"\|[^\n]+\|[^\n]+\|", combined):
        return True, None

    # Code blocks or key-value pairs
    if "```" in combined or re.search(r"(?:^|\n)\s*[A-Za-zА-Яа-яЁё0-9_-]+\s*:\s*\S+", combined):
        return True, None

    if (output_mode or "").strip().lower() == "chat" and _CAPABILITY.match((intent or "").strip()):
        return True, None

    # 3. Analyze words against generic trigger words / greetings
    words = [w.lower() for w in re.findall(r"[a-zA-Zа-яА-ЯёЁ]+", combined)]
    content_words = [w for w in words if w not in _TRIGGER_WORDS]

    if not content_words:
        return False, _format_refusal_message(output_mode)

    # If only 1-2 content words in a short phrase without data signals
    if len(content_words) < 3 and len(combined) < 50:
        return False, _format_refusal_message(output_mode)

    return True, None
