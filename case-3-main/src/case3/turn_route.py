"""Decide chat vs artifact from the user's words and an optional plaque.

The plaque is a default, not a gate. A named action in the message wins.
An analyze line that names no artifact uses the plaque, unless that plaque
was negated («без схемы, расскажи»).
"""

from __future__ import annotations

import re

TurnKind = str  # chat | report | diagram | presentation

_MAKE = re.compile(
    r"\b("
    r"сделай|сделать|собери|собрать|перестрой|перестроить|пересобери|пересобрать|"
    r"подготовь|подготовить|"
    r"оформи|оформить|сверстай|нарисуй|построй|построить|"
    r"сгенерируй|сгенерировать|напиши|написать|выгрузи|экспортируй"
    r")\b",
    re.IGNORECASE,
)
_ANALYZE = re.compile(
    r"\b("
    r"проанализируй|проанализировать|разбери|разобрать|разложи|разложить|"
    r"сравни|сравнить|объясни|объяснить|посчитай|посчитать|"
    r"расскажи|рассказать|поясни|пояснить|оцени|оценить|"
    r"перескажи|почему|зачем|"
    r"опиши|описать|выдели|выделить|"
    r"суммируй|суммировать|перечисли|кратко"
    r")\b",
    re.IGNORECASE,
)
_PRESENTATION = re.compile(
    r"презентац|презу|преза|слайд|pptx|\bdeck\b",
    re.IGNORECASE,
)
_DIAGRAM = re.compile(
    r"схем|flowchart|mermaid",
    re.IGNORECASE,
)
_REPORT = re.compile(
    r"отч[её]т|\bpdf\b|\bdocx\b|\bword\b|ворд|справк",
    re.IGNORECASE,
)
_CHART_REQ = re.compile(
    r"график|диаграмм|чарт|\bchart\b|гистограмм|кругов\w*|линейн\w*|визуализ\w*|наглядн\w*",
    re.IGNORECASE,
)
_NEG_CHART = re.compile(
    r"(?:без|не\s+(?:надо|нужен|нужно|делай|рисуй|строй))\s+(?:график\w*|диаграмм\w*|визуализац\w*|картин\w*)"
    r"|только\s+текст\w*",
    re.IGNORECASE,
)
_AUTO_CHART_CUE = re.compile(
    r"\b("
    r"сравни\w*|динамик\w*|структур\w*|дол[яией]\w*|топ[-\s]?\d*|лидер\w*|отста\w*|"
    r"рейтинг\w*|распределен\w*|разрез\w*|отклонен\w*|тренд\w*|итог\w*|показател\w*|"
    r"област\w*|регион\w*|инспекц\w*|факт\w*|план\w*|выручк\w*|поступлен\w*"
    r")\b",
    re.IGNORECASE,
)
_CHITCHAT = re.compile(
    r"^\s*(?:привет|здравствуй|добрый\s+(?:день|вечер|утро)|спасибо|ок|понятно|кто\s+ты|что\s+ты\s+умеешь)\b",
    re.IGNORECASE,
)
_CHART_FOLLOWUP = re.compile(
    r"горизонтальн|вертикальн|столбчат|кругов\w*|кольц\w*|бублик|пончик|пирог|\bbar\b|\bdonut\b|\bdoughnut\b|\bpie\b|\bline\b|"
    r"палитр|перекрас|цвет\w*|оранжев\w*|син\w*|голуб\w*|зел[её]н\w*|красн\w*|ж[её]лт\w*|сер[ыоа]\w*|ч[её]рн\w*|"
    r"тепл\w*|холодн\w*|\b(?:ocean|sunset|mono|atelier|editorial)\b|"
    r"легенд|ось|осям|подпис\w*|убери\s+итог|без\s+итог",
    re.IGNORECASE,
)
_DIAGRAM_FOLLOWUP = re.compile(
    r"добав\w*\s+узел|убер\w*\s+узел|перерисуй|направлени\w*\s+(?:слева|сверху)|"
    r"\blr\b|\btd\b|стрелк\w*|ветк\w*",
    re.IGNORECASE,
)
_IN_CHAT = re.compile(
    r"(?:^|\s)(?:в\s+чат[е]?|без\s+отч[её]т[ао]?)\b",
    re.IGNORECASE,
)
_ON_THIS_DATA = re.compile(
    r"по\s+(?:этим\s+)?данным",
    re.IGNORECASE,
)
_QUESTION = re.compile(
    r"\?\s*$|"
    r"(?:^|[\s,])(?:"
    r"почему|зачем|насколько|на\s+сколько|"
    r"что|как|где|какой|какая|какие|какое|каких|какую|"
    r"сколько|когда|кто|чем|чему"
    r")\b",
    re.IGNORECASE,
)
# «не делай отчёт», «без схемы» — noun is present, the request is not.
_NEG_BEFORE = re.compile(
    r"(?:^|\s)(?:не|без)(?:\s+(?:надо|нужно|нужен|нужна|делай|сделай|собери|хочу))?\s*$",
    re.IGNORECASE,
)


def _norm(text: str) -> str:
    return (text or "").replace("ё", "е").replace("Ё", "Е")


def _plaque_blocked(raw: str, plaque: str) -> bool:
    """True when every mention of this plaque's artifact is negated."""
    pattern = {
        "presentation": _PRESENTATION,
        "diagram": _DIAGRAM,
        "report": _REPORT,
    }[plaque]
    matches = list(pattern.finditer(raw))
    if not matches:
        return False
    for match in matches:
        window = raw[max(0, match.start() - 32) : match.start()]
        if not _NEG_BEFORE.search(window):
            return False
    return True


def _live_kinds(raw: str) -> list[str]:
    found: list[str] = []
    for kind, pattern in (
        ("presentation", _PRESENTATION),
        ("report", _REPORT),
        ("diagram", _DIAGRAM),
    ):
        for match in pattern.finditer(raw):
            window = raw[max(0, match.start() - 32) : match.start()]
            if _NEG_BEFORE.search(window):
                continue
            found.append(kind)
            break
    return found


def _asked(pattern: re.Pattern[str], text: str | None) -> bool:
    raw = _norm(text or "")
    for match in pattern.finditer(raw):
        window = raw[max(0, match.start() - 32) : match.start()]
        if not _NEG_BEFORE.search(window):
            return True
    return False


def wants_chat_chart(text: str | None, *, has_prior_chart: bool = False) -> bool:
    """True when the user asks to draw a chart/graph or refines an inline chart."""
    raw = _norm(text or "")
    if _NEG_CHART.search(raw):
        return False
    if _asked(_CHART_REQ, raw):
        return True
    if has_prior_chart and _asked(_CHART_FOLLOWUP, raw):
        return True
    return False


def _has_chartable_table_or_series(text: str | None) -> bool:
    raw = (text or "").strip()
    if not raw:
        return False
    table_numeric_rows = 0
    for line in raw.splitlines():
        s = line.strip()
        if s.startswith("|") and s.endswith("|"):
            # Skip markdown separator rows like | --- | --- |
            if re.fullmatch(r"\|[\s:|-]+\|", s):
                continue
            if re.search(r"\d", s):
                table_numeric_rows += 1
    if table_numeric_rows >= 3:
        return True
    # Also accept 4+ distinct bullet/entity lines with numbers (outside headings)
    num_lines = sum(
        1
        for line in raw.splitlines()
        if line.strip()
        and not line.lstrip().startswith("#")
        and re.search(r"[А-Яа-яA-Za-z]{2,}.*\d", line)
    )
    return num_lines >= 4


_DECLINE_CHART = re.compile(
    r"не\s+получится|не\s+могу\s+(?:сравнить|построить|показать|сопоставить)|"
    r"это\s+не\s+разные\s+месяц|нет\s+(?:данных|чисел|снимков)\s+для|"
    r"сравнить .{0,60}не\s+получится",
    re.IGNORECASE,
)


def answer_declines_chart(answer: str | None) -> bool:
    """True when the reply already says the picture cannot be built."""
    return bool(_DECLINE_CHART.search(answer or ""))


def should_auto_chat_chart(
    turn_text: str | None,
    source_text: str | None,
    answer_text: str | None = None,
    *,
    has_prior_diagram: bool = False,
) -> bool:
    """True when an ordinary analytical chat answer benefits from an inline chart."""
    raw = _norm(turn_text or "").strip()
    if not raw or _CHITCHAT.search(raw) or _NEG_CHART.search(raw):
        return False
    if "длинный разбор в чат не пиши" in raw.lower():
        return False
    if wants_chat_diagram(raw, has_prior_diagram=has_prior_diagram):
        return False
    has_data = _has_chartable_table_or_series(source_text) or _has_chartable_table_or_series(answer_text)
    if not has_data:
        return False
    if _AUTO_CHART_CUE.search(raw) or _ANALYZE.search(raw):
        return True
    return _has_chartable_table_or_series(answer_text)


def wants_chat_diagram(text: str | None, *, has_prior_diagram: bool = False) -> bool:
    """True when the user asks for a schema in the chat, or refines a prior inline diagram."""
    if _asked(_DIAGRAM, text):
        return True
    if has_prior_diagram and _asked(_DIAGRAM_FOLLOWUP, text):
        return True
    return False


def resolve_turn(text: str | None, bias: str | None) -> TurnKind:
    """Return chat, report, diagram, or presentation."""
    raw = _norm(text or "")
    plaque = (bias or "").strip().lower()
    if plaque not in {"report", "diagram", "presentation"}:
        plaque = ""

    kinds = _live_kinds(raw)

    make = bool(_MAKE.search(raw))
    analyze = bool(_ANALYZE.search(raw))
    # Explicit «в чате» / «без отчёта» keeps chart/analysis requests out of file builds.
    if _IN_CHAT.search(raw) and not kinds:
        return "chat"
    # A question reads the file. It does not start a new one.
    if _QUESTION.search(raw) and not make:
        return "chat"
    # Inline chart request («построй график по регионам») stays in chat unless an artifact is explicitly named.
    if wants_chat_chart(raw) and not kinds:
        return "chat"

    if (
        kinds == ["diagram"]
        and plaque != "diagram"
        and (_ON_THIS_DATA.search(raw) or _IN_CHAT.search(raw))
    ):
        return "chat"
    if kinds and (make or not analyze):
        if plaque and plaque in kinds:
            return plaque
        return kinds[0]
    if analyze:
        if plaque and not kinds and not _plaque_blocked(raw, plaque):
            return plaque
        return "chat"
    if plaque:
        return plaque
    if kinds:
        if plaque and plaque in kinds:
            return plaque
        return kinds[0]
    return "chat"
