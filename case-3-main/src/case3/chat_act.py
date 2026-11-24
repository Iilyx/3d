"""What a follow-up in one chat is asking for.

Talk stays in the thread. Build uses the existing pipeline. Revise edits the
artifact already on the table, the same one the rail buttons edit.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from case3.turn_route import resolve_turn

_UNDO = re.compile(r"\b(отмени|отменить)\b", re.IGNORECASE)
_REDO = re.compile(r"верни правку|повтори правку", re.IGNORECASE)
_RECOLOR = re.compile(
    r"перекрась|перекрасить|измени цвет|поменяй цвет|смени цвет|смени стиль|смени тему|другой цвет",
    re.IGNORECASE,
)
_CHARTS = re.compile(r"график", re.IGNORECASE)
_REWRITE = re.compile(
    r"перепиши|переписать|переформулируй|сократи раздел|сократи абзац|"
    r"распиши|разверни|расширь|дополни",
    re.IGNORECASE,
)
_PROSE = re.compile(
    r"переделай|переделать|точнее|не нравится|улучши|улучшить|поправь|"
    r"слабо|размыт|перефразир|короче|сократи|подробнее|детальнее|шире",
    re.IGNORECASE,
)
_VISUAL = re.compile(r"красивее|покрасивее", re.IGNORECASE)
_REPORT_WORD = re.compile(r"отч[её]т|раздел|абзац", re.IGNORECASE)
_STOP_NAME = frozenset(
    {
        "тот",
        "этот",
        "эта",
        "это",
        "мне",
        "его",
        "ее",
        "её",
        "так",
        "уже",
        "тут",
        "там",
        "мой",
        "моя",
        "мое",
        "моё",
        "отчет",
        "презентация",
        "преза",
        "презу",
        "схема",
        "схему",
        "график",
        "графики",
        "это",
        "вот",
        "все",
        "короче",
        "точнее",
        "красивее",
        "текст",
        "файл",
        "слайд",
        "слайды",
    }
)
_EDIT = re.compile(
    r"\b(измени|изменить|исправь|исправить|замени|заменить|удали|удалить|"
    r"убери|убрать|добавь|добавить|поправь)\b",
    re.IGNORECASE,
)
def asks_without_order(raw: str) -> bool:
    """True when the line is a question and not an order.

    «почему» and «зачем» are always questions. A trailing ? on
    «убери слайд 2» is still an order.
    """
    text = raw or ""
    if re.search(r"(?:^|\s)(?:почему|зачем|на\s+сколько\s+измен)\b", text, re.IGNORECASE):
        return True
    if "?" not in text:
        return False
    if (
        _EDIT.search(text)
        or _REWRITE.search(text)
        or _PROSE.search(text)
        or _RECOLOR.search(text)
        or _VISUAL.search(text)
    ):
        return False
    return True
_REF = re.compile(
    r"тот раздел|этот раздел|эту часть|там же|то же место",
    re.IGNORECASE,
)
_AGAIN = re.compile(r"^(?:ещё|еще|снова)\b", re.IGNORECASE)
_BARE_AGAIN = re.compile(r"^(?:ещё|еще|снова)[.!?\s]*$", re.IGNORECASE)
_BRIEF_ONLY = re.compile(
    r"^(?:еще\s+)?(?:короче|точнее|не нравится)[.!?\s]*$",
    re.IGNORECASE,
)
_SECTION_PATTERNS = (
    re.compile(
        r"(?:раздел\w*|абзац\w*|глав\w*)\s+[«\"]?([A-Za-zА-Яа-яЁё0-9][^:.\n,!?—–]{1,48})",
        re.IGNORECASE,
    ),
    re.compile(
        r"(?:переделай|переделать|перепиши|переписать|улучши|поправь|уточни|сократи|распиши|разверни|расширь|дополни)\s+"
        r"(?:раздел\w*\s+|абзац\w*\s+|глав\w*\s+)?[«\"]?"
        r"([A-Za-zА-Яа-яЁё0-9][^:.\n,!?—–]{1,48})",
        re.IGNORECASE,
    ),
)
_KNOWN_SECTION = re.compile(
    r"\b(введени\w*|заключени\w*|вывод\w*|обзор\w*|результат\w*|методик\w*)\b",
    re.IGNORECASE,
)
_PACK_CYCLE = (
    "atelier",
    "board",
    "signal",
    "relay",
    "ink",
    "voltage",
    "studio",
    "botanical",
)

# Deck skins. Order matters: longer phrases before short ones.
_PACKS: tuple[tuple[str, str], ...] = (
    ("botanical", r"ботаническ|dark botanical|botanical"),
    ("voltage", r"voltage|вольт"),
    ("studio", r"workshop|мастерск|studio"),
    ("ink", r"\bink\b|чернил"),
    ("relay", r"relay|пастел"),
    ("signal", r"signal|оранж"),
    ("board", r"northstar|сапфир|\bboard\b|\bсиний\b|\bсиняя\b|\bсинее\b|\bсиние\b|\bголубой\b"),
    ("atelier", r"atelier|ателье|олив"),
)
_PALETTES: tuple[tuple[str, str], ...] = (
    ("editorial", r"editorial|редакц"),
    ("ocean", r"ocean|океан|морск"),
    ("sunset", r"sunset|закат"),
    ("mono", r"\bmono\b|моно|чёрно-бел|черно-бел"),
    ("atelier", r"atelier|ателье"),
)

PACK_LABELS = {
    "atelier": "Atelier Olive",
    "board": "Northstar",
    "signal": "Bold Signal",
    "relay": "Split Pastel",
    "ink": "Relay Ink",
    "voltage": "Creative Voltage",
    "studio": "Workshop Studio",
    "botanical": "Dark Botanical",
}
PALETTE_LABELS = {
    "editorial": "editorial",
    "ocean": "ocean",
    "sunset": "sunset",
    "mono": "mono",
    "atelier": "atelier",
}


@dataclass(frozen=True)
class ChatAct:
    kind: str  # talk | build | revise
    op: str = ""  # undo | redo | recolor_deck | recolor_charts | rewrite | ask
    pack: str = ""
    palette: str = ""
    build: str = ""
    say: str = ""
    section: str = ""
    brief: str = ""  # supplied | clearer | tighter | dislike | prettier
    slide: int = 0
    slide_to: int = 0
    title: str = ""
    title_on: str = ""  # report | deck
    chart: str = ""
    chart_at: int = 0
    slot: int = 0
    items: tuple[str, ...] = ()


def _norm(text: str) -> str:
    return (text or "").replace("ё", "е").replace("Ё", "Е")


def _named(raw: str, table: tuple[tuple[str, str], ...]) -> str:
    for key, pattern in table:
        if re.search(pattern, raw, re.IGNORECASE):
            return key
    return ""


def hue_edit(text: str | None) -> str:
    """Hue when the line is a color change, not a mention of a green zone."""
    from case3.chart_style import hue_from_text

    raw = _norm(text or "").strip()
    hue = hue_from_text(raw)
    if not hue:
        return ""
    if re.search(r"цвет|палитр|перекрас|гамм|доработ", raw, re.IGNORECASE):
        return hue
    if len(raw) <= 48 and re.search(
        r"сделай|столбц|график|покрас|лини|пончик|кругов",
        raw,
        re.IGNORECASE,
    ):
        return hue
    if len(raw) <= 24:
        return hue
    return ""


def _hue_act(raw: str, hue: str) -> ChatAct:
    from case3.chart_style import HUE_SAY

    label = HUE_SAY.get(hue, hue)
    return ChatAct(
        kind="revise",
        op="recolor_hue",
        palette=hue,
        chart=chart_type_named(raw),
        say=f"Перекрашиваю график в {label}. Числа те же.",
    )


def next_deck_pack(current: str) -> str:
    """Next real deck skin. Empty and unknown start from Atelier."""
    cur = (current or "").strip().lower()
    if cur == "pastel":
        cur = "relay"
    if cur not in _PACK_CYCLE:
        cur = "atelier"
    return _PACK_CYCLE[(_PACK_CYCLE.index(cur) + 1) % len(_PACK_CYCLE)]


def _clean_name(name: str) -> str:
    cleaned = " ".join((name or "").split()).strip(" «»\"")
    cleaned = re.split(r"\s+(?:мне|пожалуйста)\b", cleaned, maxsplit=1, flags=re.IGNORECASE)[0]
    while True:
        trimmed = re.sub(
            r"\s+(?:покороче|короче|кратко|вкратце|подробнее|подробней|детальнее|проще|попроще|понятнее|понятней|лучше|аккуратнее|красивее|строже|деловитее|сжатее|полнее|целиком)\s*$",
            "",
            cleaned,
            flags=re.IGNORECASE,
        ).strip()
        if trimmed == cleaned:
            break
        cleaned = trimmed
    cleaned = cleaned.strip(" «»\"")
    if not cleaned:
        return ""
    if cleaned.split()[0].casefold() in _STOP_NAME:
        return ""
    if cleaned.casefold() in {"раздел", "абзац", "глава", "часть", "текст"}:
        return ""
    if cleaned.islower():
        return cleaned[:1].upper() + cleaned[1:]
    return cleaned


def section_target(text: str | None) -> str:
    """Heading named in a loose edit request. Empty when none is named."""
    raw = _norm(text or "")
    parsed = parse_rewrite(raw)
    if parsed:
        return parsed[0]
    for pattern in _SECTION_PATTERNS:
        match = pattern.search(raw)
        if not match:
            continue
        name = _clean_name(match.group(1))
        if name:
            return name
    known = _KNOWN_SECTION.search(raw)
    if not known:
        return ""
    word = known.group(1)
    return word[:1].upper() + word[1:]


_SLIDE_N = (
    (10, "десят"),
    (9, "девят"),
    (8, "восьм"),
    (7, "седьм"),
    (6, "шест"),
    (5, "пят"),
    (4, "четверт"),
    (3, "трет"),
    (2, "втор"),
    (1, "перв"),
)


def slide_index(text: str | None) -> int:
    """1-based slide named in «убери второй слайд». 0 when it is not a delete."""
    raw = _norm(text or "")
    if not re.search(r"слайд", raw, re.IGNORECASE):
        return 0
    if not re.search(r"убери|удали|убрать|удалить", raw, re.IGNORECASE):
        return 0
    number = re.search(r"\b(\d{1,2})\b", raw)
    if number:
        value = int(number.group(1))
        return value if 1 <= value <= 24 else 0
    for index, stem in _SLIDE_N:
        if re.search(stem, raw, re.IGNORECASE):
            return index
    return 0


_CHART_WORDS = (
    ("stacked_bar", r"накоплен|stacked"),
    ("grouped_bar", r"группир|grouped"),
    ("horizontal_bar", r"горизонтал"),
    ("donut", r"пончик|кольц|donut"),
    ("line", r"лине|лини|\bline\b"),
    ("area", r"площад|\barea\b"),
    ("scatter", r"точк|scatter|рассеян"),
    ("kpi", r"\bkpi\b"),
    ("bar", r"столбц|столбчат|\bbar\b"),
)
CHART_SAY = {
    "line": "линии",
    "bar": "столбцы",
    "donut": "пончик",
    "horizontal_bar": "горизонтальные столбцы",
    "area": "площадь",
    "scatter": "точки",
    "kpi": "kpi",
    "stacked_bar": "накопленные столбцы",
    "grouped_bar": "групповые столбцы",
}


def slide_move(text: str | None) -> tuple[int, int]:
    """«Переставь слайд 3 на место 1» → (3, 1). (0, 0) when it is not a move."""
    raw = _norm(text or "")
    if not re.search(r"слайд", raw, re.IGNORECASE):
        return 0, 0
    if re.search(r"убери|удали|убрать|удалить", raw, re.IGNORECASE):
        return 0, 0
    if not re.search(r"перестав|перемест|подвинь|поставь", raw, re.IGNORECASE):
        return 0, 0
    found: list[int] = []
    for match in re.finditer(r"\b(\d{1,2})\b", raw):
        value = int(match.group(1))
        if 1 <= value <= 24:
            found.append(value)
    if len(found) < 2:
        for match in re.finditer(
            r"перв\w*|втор\w*|трет\w*|четверт\w*|пят\w*|шест\w*|седьм\w*|восьм\w*|девят\w*|десят\w*",
            raw,
            re.IGNORECASE,
        ):
            index = _ord_index(match.group(0))
            if index:
                found.append(index)
    if len(found) < 2:
        return 0, 0
    return found[0], found[1]


def _ord_index(token: str) -> int:
    stems = (
        (10, "десят"),
        (9, "девят"),
        (8, "восьм"),
        (7, "седьм"),
        (6, "шест"),
        (5, "пят"),
        (4, "четверт"),
        (3, "трет"),
        (2, "втор"),
        (1, "перв"),
    )
    folded = token.casefold()
    for index, stem in stems:
        if folded.startswith(stem):
            return index
    return 0


def chart_at(text: str | None) -> int:
    """1-based chart when the user names one. Zero means every chart."""
    raw = _norm(text or "")
    match = re.search(r"график\w*\s+(\d{1,2})|(\d{1,2})\s*график", raw, re.IGNORECASE)
    if match:
        return int(match.group(1) or match.group(2))
    for stem, index in (
        ("перв", 1),
        ("втор", 2),
        ("трет", 3),
        ("четвер", 4),
        ("пят", 5),
    ):
        if re.search(rf"{stem}\w*\s+график", raw, re.IGNORECASE):
            return index
    return 0


def parse_section_rename(text: str | None) -> tuple[str, str] | None:
    raw = _norm(text or "").strip()
    match = re.search(r"переименуй(?:те)?\s+раздел\s+(.+?)\s+в\s+(.+)$", raw, re.IGNORECASE)
    if not match:
        return None
    old = match.group(1).strip()
    new = match.group(2).strip(" .")
    if not old or not new:
        return None
    return old, new


def parse_slide_body(text: str | None) -> tuple[int, str]:
    raw = _norm(text or "").strip()
    if re.search(r"добав|перестав|перемест|подвинь|убери|удали", raw, re.IGNORECASE):
        return 0, ""
    if not re.search(r"напиши|текст", raw, re.IGNORECASE):
        return 0, ""
    match = re.search(r"слайд\w*\s+(\d{1,2})", raw, re.IGNORECASE)
    if not match:
        match = re.search(r"(\d{1,2})\s*слайд\w*", raw, re.IGNORECASE)
    if not match:
        return 0, ""
    body = re.sub(
        r"^[\s:—\-]*(?:напиши|поставь|текст|на)?\s*",
        "",
        raw[match.end() :],
        flags=re.IGNORECASE,
    ).strip(" .")
    return int(match.group(1)), body


def _slot_index(raw: str, noun: str) -> int:
    numbered = re.search(rf"(\d{{1,2}})\s*{noun}|{noun}\w*\s+(\d{{1,2}})", raw, re.IGNORECASE)
    if numbered:
        value = int(numbered.group(1) or numbered.group(2))
        return value if 1 <= value <= 20 else 0
    for stem, index in (("перв", 1), ("втор", 2), ("трет", 3), ("четвер", 4)):
        if re.search(rf"{stem}\w*\s+{noun}", raw, re.IGNORECASE):
            return index
    return 0


def _swap(raw: str) -> tuple[str, str] | None:
    match = re.search(
        r"(?:замени|смени|поменяй|исправь)\s+(.+?)\s+на\s+(.+)$", raw, re.IGNORECASE
    )
    if not match:
        return None
    old = match.group(1).strip(" «».")
    new = match.group(2).strip(" «».")
    if not old or not new:
        return None
    return old, new


def parse_cell_replace(text: str | None) -> tuple[int, str, str] | None:
    """«В таблице замени Гомель на Брест» → (0, old, new). None when it is not a cell edit."""
    raw = _norm(text or "").strip()
    if not re.search(r"таблиц", raw, re.IGNORECASE):
        return None
    swapped = _swap(raw)
    if not swapped:
        return None
    return _slot_index(raw, "таблиц"), swapped[0], swapped[1]


def parse_row_add(text: str | None) -> tuple[int, tuple[str, ...]] | None:
    """«В таблице добавь строку: Гомель; 12» → (slot, cells)."""
    raw = _norm(text or "").strip()
    if not re.search(r"таблиц", raw, re.IGNORECASE):
        return None
    if not re.search(r"добав", raw, re.IGNORECASE) or not re.search(r"строк", raw, re.IGNORECASE):
        return None
    match = re.search(r"строк\w*\s*[:—–-]\s*(.+)$", raw, re.IGNORECASE)
    if not match:
        match = re.search(r"строк\w*\s+(.+)$", raw, re.IGNORECASE)
    body = match.group(1).strip(" .") if match else ""
    body = re.sub(r"^(?:в\s+)?(?:\d+\s+)?таблиц\w*\s*", "", body, flags=re.IGNORECASE).strip(" .")
    if not body:
        return _slot_index(raw, "таблиц"), ()
    if "|" in body:
        cells = [part.strip(" .") for part in body.split("|")]
    elif ";" in body:
        cells = [part.strip(" .") for part in body.split(";")]
    else:
        cells = [body]
    cells = tuple(cell for cell in cells if cell)
    return _slot_index(raw, "таблиц"), cells


def parse_row_delete(text: str | None) -> tuple[int, str] | None:
    """«Убери из таблицы строку Гомель» → (slot, label)."""
    raw = _norm(text or "").strip()
    if not re.search(r"таблиц", raw, re.IGNORECASE) or not re.search(r"строк", raw, re.IGNORECASE):
        return None
    if not re.search(r"убери|удали|убрать|удалить", raw, re.IGNORECASE):
        return None
    match = re.search(r"строк\w*\s+(.+)$", raw, re.IGNORECASE)
    label = match.group(1) if match else ""
    label = re.sub(r"\s+из\s+(?:\w+\s+)?таблиц\w*.*$", "", label, flags=re.IGNORECASE)
    label = re.sub(r"^(?:из\s+)?(?:\w+\s+)?таблиц\w*\s*", "", label, flags=re.IGNORECASE)
    return _slot_index(raw, "таблиц"), label.strip(" .«»")


def parse_item_replace(text: str | None) -> tuple[int, str, str] | None:
    raw = _norm(text or "").strip()
    if not re.search(r"спис", raw, re.IGNORECASE):
        return None
    swapped = _swap(raw)
    if not swapped:
        return None
    return _slot_index(raw, "спис"), swapped[0], swapped[1]


_STRUCTURES = (
    ("investor", r"инвестор"),
    ("board_update", r"совет директор|борд"),
    ("qbr", r"квартальн"),
    ("performance", r"эффективн"),
    ("launch", r"запуск"),
    ("survey", r"исследован"),
    ("campaign", r"кампан"),
    ("workshop", r"воркшоп|мастерск"),
    ("hire", r"найм"),
    ("council", r"архитектурн"),
    ("quarter", r"стратег"),
)
STRUCTURE_SAY = {
    "investor": "инвестора",
    "board_update": "совета",
    "qbr": "квартального обзора",
    "performance": "эффективности",
    "launch": "запуска",
    "survey": "исследования",
    "campaign": "кампании",
    "workshop": "воркшопа",
    "hire": "найма",
    "council": "архитектурного совета",
    "quarter": "стратегии",
}
STRUCTURE_ASK = (
    "инвестора, совета, квартала, эффективности, запуска, "
    "исследования, кампании, воркшопа, найма, архитектурного совета, стратегии"
)


def parse_item_add(text: str | None) -> tuple[int, str] | None:
    raw = _norm(text or "").strip()
    if not re.search(r"спис", raw, re.IGNORECASE) or not re.search(r"добав", raw, re.IGNORECASE):
        return None
    if re.search(r"слайд", raw, re.IGNORECASE):
        return None
    match = re.search(r"пункт\s+(.+)$", raw, re.IGNORECASE)
    if not match:
        return None
    item = re.sub(r"\s+в\s+список\w*$", "", match.group(1), flags=re.IGNORECASE).strip(" .")
    if not item:
        return None
    return _slot_index(raw, "спис"), item


def parse_item_delete(text: str | None) -> tuple[int, str] | None:
    """«Убери кассу из списка» → (0, кассу). None when it is not a list delete."""
    raw = _norm(text or "").strip()
    if re.search(r"слайд", raw, re.IGNORECASE):
        return None
    if not re.search(r"спис", raw, re.IGNORECASE):
        return None
    if not re.search(r"убери|удали|убрать|удалить", raw, re.IGNORECASE):
        return None
    match = re.search(
        r"(?:убери|удали|убрать|удалить)\s+(?:пункт\s+)?(.+?)\s+из\s+спис",
        raw,
        re.IGNORECASE,
    )
    if not match:
        return None
    word = match.group(1).strip(" «».")
    if not word:
        return None
    return _slot_index(raw, "спис"), word


def paragraph_at(text: str | None) -> tuple[int, str]:
    """«Второй абзац введения» → (2, Введение). (0, '') when no ordinal is named."""
    raw = _norm(text or "")
    if not re.search(r"абзац", raw, re.IGNORECASE):
        return 0, ""
    number = re.search(
        r"(\d)\s*[-–]?\s*й?\s*абзац|абзац\w*\s+(\d)",
        raw,
        re.IGNORECASE,
    )
    ordinal = int(number.group(1) or number.group(2)) if number else 0
    if not ordinal:
        for index, stem in ((5, "пят"), (4, "четвер"), (3, "трет"), (2, "втор"), (1, "перв")):
            if re.search(rf"{stem}\w*\s+абзац", raw, re.IGNORECASE):
                ordinal = index
                break
    if ordinal < 1:
        return 0, ""
    match = re.search(
        r"абзац\w*(?:\s+\d)?\s+([A-Za-zА-Яа-яЁё-]{4,})",
        raw,
        re.IGNORECASE,
    )
    name = _clean_name(match.group(1)) if match else ""
    return ordinal, name


def parse_paragraph_add(text: str | None) -> tuple[str, str] | None:
    """«Добавь абзац во введение: …» → (section, user text)."""
    raw = _norm(text or "").strip()
    if not re.search(r"добав", raw, re.IGNORECASE) or not re.search(r"абзац", raw, re.IGNORECASE):
        return None
    if re.search(r"слайд", raw, re.IGNORECASE):
        return None
    match = re.search(
        r"(?:в|во)\s+([A-Za-zА-Яа-яЁё-]{4,}).{0,40}?[:—–-]\s*(.{8,})",
        raw,
        re.IGNORECASE | re.DOTALL,
    )
    if not match:
        return None
    name = _clean_name(match.group(1))
    body = match.group(2).strip()
    if not name or len(body) < 8:
        return None
    return name, body


def parse_section_add(text: str | None) -> tuple[str, str] | None:
    """«Добавь раздел Выводы: …» → (name, user text)."""
    raw = _norm(text or "").strip()
    if not re.search(r"добав", raw, re.IGNORECASE) or not re.search(r"раздел", raw, re.IGNORECASE):
        return None
    match = re.search(
        r"раздел\w*\s+[«\"]?([A-Za-zА-Яа-яЁё0-9][^:«»\"\n]{1,40}?)[»\"]?\s*[:—–-]\s*(.{8,})",
        raw,
        re.IGNORECASE | re.DOTALL,
    )
    if not match:
        return None
    name = _clean_name(match.group(1))
    body = match.group(2).strip()
    if not name or len(body) < 8:
        return None
    return name, body


def parse_caption(text: str | None) -> tuple[str, str] | None:
    """«Подпись рисунка fig_01: …» → (id or '', caption)."""
    raw = _norm(text or "").strip()
    if not re.search(r"подпис", raw, re.IGNORECASE):
        return None
    if not re.search(r"рисун|фото|фигур|график", raw, re.IGNORECASE):
        return None
    found = re.search(r"\b((?:fig|usr|cht|dia)_[A-Za-z0-9_]+)", raw, re.IGNORECASE)
    body = re.search(r"[:—–-]\s*(.{2,})$", raw)
    if not body:
        return None
    caption = body.group(1).strip(" .")
    if not caption:
        return None
    return (found.group(1) if found else ""), caption


def parse_photo_edit(text: str | None) -> tuple[str, str] | None:
    """None when this is not a pixel edit of a photo already on the table.

    ("", "") means the photo was named and the change was not.
    The id is "" when the user did not name usr_NN.
    """
    raw = _norm(text or "").strip()
    if re.search(r"подпис", raw, re.IGNORECASE):
        return None
    if not re.search(r"\bфото\b|usr_", raw, re.IGNORECASE):
        return None
    aimed = re.search(
        r"на фото|у фото|это фото|поправь\s+фото|измени\s+фото|перерисуй\s+фото|убери\s+.+?\s+с фото|фото\s+usr_",
        raw,
        re.IGNORECASE,
    )
    if not aimed:
        return None
    found = re.search(r"\b(usr_[A-Za-z0-9_]+)", raw, re.IGNORECASE)
    fid = found.group(1) if found else ""
    tail = re.search(r"[:—–-]\s*(.{2,})$", raw)
    if tail:
        return fid, tail.group(1).strip(" .")
    inline = re.search(
        r"(?:на фото|у фото|это фото)\s+(?:сделай|убери|добавь|поправь|измени|перерисуй)\s+(.{2,})$",
        raw,
        re.IGNORECASE,
    )
    if inline:
        return fid, inline.group(1).strip(" .")
    return fid, ""


def parse_section_delete(text: str | None) -> str | None:
    """None when this is not a section delete. Empty string asks for the name."""
    raw = _norm(text or "").strip()
    if not re.search(r"раздел", raw, re.IGNORECASE):
        return None
    if re.search(r"слайд|спис|таблиц|строк|абзац", raw, re.IGNORECASE):
        return None
    if not re.search(r"убери|удали|убрать|удалить", raw, re.IGNORECASE):
        return None
    match = re.search(
        r"(?:убери|удали|убрать|удалить)\s+раздел\w*\s+[«\"]?(.{2,80})",
        raw,
        re.IGNORECASE,
    )
    if not match:
        return ""
    return _clean_name(match.group(1).strip(" «».:"))


def wants_whole_report(text: str | None) -> bool:
    raw = _norm(text or "")
    if not re.search(r"короче|сократ", raw, re.IGNORECASE):
        return False
    return bool(re.search(r"весь отчет|весь текст|все разделы|целиком", raw, re.IGNORECASE))


def parse_diagram_edit(text: str | None) -> str | None:
    """None when this is not an edit of a scheme already on the table.

    Empty string means the user named the scheme but not the change.
    «Доработай схему: сделай стрелки толще» is an edit. The word «сделай»
    inside the instruction must not start a new scheme.
    """
    raw = _norm(text or "").strip()
    if not re.search(r"схем", raw, re.IGNORECASE):
        return None
    fresh = re.match(
        r"^(?:пожалуйста[, ]+)?"
        r"(?:сделай|собери|нарисуй|построй|сгенерируй)\s+"
        r"(?:новую\s+|новый\s+)?схем",
        raw,
        re.IGNORECASE,
    )
    fix = re.search(
        r"доработай|исправь|поправь|измени|убери|перерисуй|уточни|переделай",
        raw,
        re.IGNORECASE,
    )
    if fresh and not fix:
        return None
    match = re.search(
        r"(?:доработай|исправь|поправь|измени|перерисуй|уточни|переделай)\s+"
        r"схем\w*\s*[:—-]?\s*(.*)$",
        raw,
        re.IGNORECASE,
    )
    if match:
        return match.group(1).strip(" .,;:—-")
    match = re.search(r"на\s+схеме\s+(.+)$", raw, re.IGNORECASE)
    if match and match.group(1).strip(" ."):
        return match.group(1).strip(" .")
    if fix:
        return ""
    return None


def parse_slide_bullets(text: str | None) -> tuple[int, tuple[str, ...]] | None:
    """«На слайде 2 пункты: риски; сроки» → (2, (...)). None when it is not points."""
    raw = _norm(text or "").strip()
    if not re.search(r"слайд", raw, re.IGNORECASE):
        return None
    if not re.search(r"пункт|тезис", raw, re.IGNORECASE):
        return None
    number = re.search(r"слайд\w*\s+(\d{1,2})|(\d{1,2})\s*слайд", raw, re.IGNORECASE)
    if not number:
        return 0, ()
    index = int(number.group(1) or number.group(2))
    tail = re.search(r"(?:пункт\w*|тезис\w*)\s*[:—-]?\s*(.*)$", raw, re.IGNORECASE)
    body = (tail.group(1) if tail else "").strip()
    parts = [part.strip(" .") for part in re.split(r"\s*[;•]\s*|\n+", body) if part.strip(" .")]
    return index, tuple(parts)


def parse_new_slide(text: str | None) -> str | None:
    """None when this is not a new slide. Empty string asks for a topic."""
    raw = _norm(text or "").strip()
    match = re.search(r"добав(?:ь|ить)\s+слайд(?:\s+про)?\s*(.*)$", raw, re.IGNORECASE)
    if not match:
        return None
    return match.group(1).strip(" .")


def chart_type_named(text: str | None) -> str:
    """A whitelist chart type named next to the word «график»."""
    raw = _norm(text or "")
    if not re.search(r"график", raw, re.IGNORECASE):
        return ""
    for key, pattern in _CHART_WORDS:
        if re.search(pattern, raw, re.IGNORECASE):
            return key
    return ""


def parse_title(text: str | None) -> str:
    """«Поменяй заголовок на Гомель» → Гомель. Empty when no new title."""
    raw = _norm(text or "")
    match = re.search(
        r"(?:поменяй|смени|измени|переименуй)\s+заголовок"
        r"(?:\s+(?:презентац\w*|презу|преза|отч[её]т\w*|документ\w*|слайд\w*(?:\s+\d{1,2})?|\d{1,2}\s+слайд\w*|"
        r"(?:перв|втор|трет|четверт|пят|шест|седьм|восьм|девят|десят)\w*\s+слайд\w*))?"
        r"(?:\s+(?:на|в))?\s*[:—–-]?\s*(.+)",
        raw,
        re.IGNORECASE,
    )
    if not match:
        return ""
    title = match.group(1).strip()
    title = title.strip(" «».")
    if len(title) < 2:
        return ""
    return title[:120]


def _slide_number_named(text: str | None) -> int:
    """1-based slide index when a message names a specific slide (e.g. 'слайда 3', 'второго слайда')."""
    raw = _norm(text or "")
    if not re.search(r"слайд", raw, re.IGNORECASE):
        return 0
    m = re.search(r"слайд\w*\s+(\d{1,2})|(\d{1,2})\s*слайд", raw, re.IGNORECASE)
    if m:
        val = int(m.group(1) or m.group(2))
        return val if 1 <= val <= 24 else 0
    for index, stem in _SLIDE_N:
        if re.search(rf"{stem}\w*\s+слайд|слайд\w*\s+{stem}", raw, re.IGNORECASE):
            return index
    return 0


def title_target(text: str | None) -> str:
    """deck when the message names the presentation, report when it names the report."""
    raw = _norm(text or "")
    if re.search(r"презентац|презу|преза|слайд", raw, re.IGNORECASE):
        return "deck"
    if re.search(r"отч[её]т|документ", raw, re.IGNORECASE):
        return "report"
    return ""


def _brief_for(raw: str) -> str:
    if "точн" in raw.casefold():
        return "clearer"
    if re.search(r"короче|сократ", raw, re.IGNORECASE):
        return "tighter"
    if re.search(r"не нравится|слаб|размыт", raw, re.IGNORECASE):
        return "dislike"
    return "prettier"


_REWRITE_INSTRUCTION_BODY = re.compile(
    r"(?:^|\b)(?:сделай|добавь|убери|сократи|распиши|укажи|выдели|акцент|подробн\w*|"
    r"короче|точнее|фокус|включи|отметь|уточни|перепиши|переформулируй|оставь\s+только|"
    r"больше\s+внимани|меньше\s+вод)\b",
    re.IGNORECASE,
)


def parse_rewrite(text: str | None) -> tuple[str, str] | None:
    """«Перепиши раздел Введение: новый текст» → (name, body)."""
    raw = _norm(text or "")
    match = re.search(
        r"(?:раздел|абзац)\s+[«\"]?(.{2,80}?)[»\"]?\s*[:—–-]\s*(.{8,})",
        raw,
        re.IGNORECASE | re.DOTALL,
    )
    if not match:
        return None
    name = " ".join(match.group(1).split())
    body = match.group(2).strip()
    if not name or not body:
        return None
    if _REWRITE_INSTRUCTION_BODY.search(body):
        return None
    return name, body


def _clarify(
    *,
    has_deck: bool,
    has_report: bool,
    has_diagram: bool,
    last_section: str,
) -> str:
    bits: list[str] = []
    if last_section and has_report:
        bits.append(f"продолжить раздел «{last_section}»")
    elif has_report:
        bits.append("назвать раздел")
    if has_deck:
        bits.append("назвать стиль презентации")
    if has_report or has_deck:
        bits.append("назвать цвет графиков")
    if has_deck or has_report or has_diagram:
        bits.append("написать «отмени», чтобы вернуть прошлый вид")
    if not bits:
        return "Пока нечего править. Спроси по тексту или напиши, что собрать."
    return "Не взял правку, нужно точнее. Можно " + ", ".join(bits) + "."


def _unsupported_shape(raw: str) -> bool:
    """A change the phrase router will never perform."""
    if re.search(r"график", raw, re.IGNORECASE) and re.search(
        r"числ|данн|столб|значен", raw, re.IGNORECASE
    ):
        if chart_type_named(raw) or _named(raw, _PALETTES):
            return False
        return True
    if re.search(r"схем", raw, re.IGNORECASE) and re.search(r"легенд", raw, re.IGNORECASE):
        return True
    return False


_CLAUSE_JOIN = re.compile(r"\s+и\s+|;\s+")
_CLAUSE_VERB = re.compile(
    r"убери|удали|перекрас|перепиш|сократ|добав|перестав|смен|поменя|замен|отмен|верни правк",
    re.IGNORECASE,
)


def edit_clauses(text: str | None) -> list[str]:
    """Split a line only when every piece is its own edit.

    «Гомель; 12» stays one clause: the second piece has no edit verb.
    """
    raw = _norm(text or "").strip()
    if not raw:
        return []
    parts = [part.strip(" ,.") for part in _CLAUSE_JOIN.split(raw) if part.strip()]
    if len(parts) < 2 or not all(_CLAUSE_VERB.search(part) for part in parts):
        return [raw]
    return parts


_NEW_BUILD_ARTIFACT = re.compile(
    r"\b(?:сделай|собери|перестрой|пересобери|подготовь|оформи|сверстай|сгенерируй|напиши|создай)\b"
    r"[^.!?\n]{0,120}\b(?:новый\s+|новую\s+)?(?:отчет\w*|презентац\w*|през[уа]|схем\w*|pdf|docx|word|ворд|pptx)\b",
    re.IGNORECASE,
)


def _explicit_new_artifact(raw: str) -> bool:
    return bool(_NEW_BUILD_ARTIFACT.search(raw or ""))


def resolve_act(
    text: str | None,
    *,
    bias: str | None = None,
    has_deck: bool = False,
    has_report: bool = False,
    has_diagram: bool = False,
    has_chart: bool = False,
    last_section: str = "",
    last_op: str = "",
) -> ChatAct:
    """Classify one user message. Build wins when they name a new artifact."""
    raw = _norm(text or "").strip()
    has_any = has_deck or has_report or has_diagram or has_chart

    if _unsupported_shape(raw):
        return ChatAct(kind="talk")

    if has_any and _REDO.search(raw) and len(raw) < 80:
        return ChatAct(kind="revise", op="redo", say="Вернул последнюю правку.")
    if has_any and _UNDO.search(raw) and len(raw) < 80:
        return ChatAct(kind="revise", op="undo", say="Отменил последнюю правку.")

    if _RECOLOR.search(raw):
        charts = bool(_CHARTS.search(raw))
        if charts:
            palette = _named(raw, _PALETTES)
            hue = hue_edit(raw)
            if not palette and hue and (has_report or has_deck or has_chart):
                return _hue_act(raw, hue)
            if not palette:
                names = ", ".join(PALETTE_LABELS)
                return ChatAct(
                    kind="revise",
                    op="ask",
                    say=f"Какой цвет графиков: {names}? Фиолетового нет.",
                )
            if not (has_report or has_deck or has_chart):
                return ChatAct(
                    kind="talk",
                    say="Графиков в этом чате ещё нет. Могу собрать отчёт или презу.",
                )
            return ChatAct(
                kind="revise",
                op="recolor_charts",
                palette=palette,
                say=f"Перекрашиваю графики в {PALETTE_LABELS[palette]}.",
            )
        pack = _named(raw, _PACKS)
        if not has_deck:
            return ChatAct(
                kind="talk",
                say="Презентации в этом чате ещё нет. Напиши «сделай презентацию», если её собрать.",
            )
        if not pack:
            names = ", ".join(PACK_LABELS.values())
            return ChatAct(
                kind="revise",
                op="ask",
                say=f"Какой стиль презентации: {names}?",
            )
        return ChatAct(
            kind="revise",
            op="recolor_deck",
            pack=pack,
            say=f"Перекрашиваю презентацию в {PACK_LABELS[pack]}. Слайды соберутся заново, текст тот же.",
        )

    added_paragraph = parse_paragraph_add(raw) if has_report else None
    if added_paragraph:
        return ChatAct(
            kind="revise",
            op="add_paragraph",
            section=added_paragraph[0],
            title=added_paragraph[1],
            say=f"Добавляю абзац в «{added_paragraph[0]}».",
        )
    added_section = parse_section_add(raw) if has_report else None
    if added_section:
        return ChatAct(
            kind="revise",
            op="add_section",
            section=added_section[0],
            title=added_section[1],
            say=f"Добавляю раздел «{added_section[0]}».",
        )

    supplied = parse_rewrite(raw) if has_report else None
    if supplied:
        return ChatAct(
            kind="revise",
            op="rewrite",
            section=supplied[0],
            brief="supplied",
            say=f"Перепишу раздел «{supplied[0]}» твоим текстом.",
        )

    if _VISUAL.search(raw):
        about_report = bool(_REPORT_WORD.search(raw))
        if about_report and has_report:
            return ChatAct(
                kind="revise",
                op="rewrite",
                section=section_target(raw),
                brief="prettier",
                say="Поправлю текст отчёта по документам. Новых чисел не добавлю.",
            )
        if has_deck and has_report and not about_report:
            return ChatAct(
                kind="revise",
                op="ask",
                say="Сделать красивее текст или стиль презентации? Напиши «текст» или имя стиля.",
            )
        if has_deck and not about_report:
            return ChatAct(
                kind="revise",
                op="recolor_deck",
                say="Соберу презентацию в следующем стиле. Текст слайдов тот же.",
            )
        if has_report:
            return ChatAct(
                kind="revise",
                op="rewrite",
                brief="prettier",
                say="Поправлю введение по документам. Новых чисел не добавлю.",
            )
        return ChatAct(
            kind="talk",
            say="Пока нечего менять. Сначала собери отчёт или презентацию.",
        )

    question = asks_without_order(raw)
    remembered = (last_section or "").strip()
    if not question and _BARE_AGAIN.match(raw):
        if last_op == "recolor_deck" and has_deck and not remembered:
            return ChatAct(
                kind="revise",
                op="recolor_deck",
                say="Соберу презентацию в следующем стиле. Текст слайдов тот же.",
            )
        if last_op == "recolor_deck" and has_deck and remembered:
            return ChatAct(
                kind="revise",
                op="ask",
                say=f"Продолжить стиль презентации или раздел «{remembered}»?",
            )
        if remembered and has_report and last_op in {"", "rewrite"}:
            return ChatAct(
                kind="revise",
                op="rewrite",
                section=remembered,
                brief="prettier",
                say=f"Перепишу раздел «{remembered}» по документам. Новых чисел не добавлю.",
            )
        if last_op and last_op not in {"rewrite", "recolor_deck"}:
            return ChatAct(
                kind="revise",
                op="ask",
                say=_clarify(
                    has_deck=has_deck,
                    has_report=has_report,
                    has_diagram=has_diagram,
                    last_section=remembered,
                ),
            )
        return ChatAct(
            kind="revise",
            op="ask",
            say=_clarify(
                has_deck=has_deck,
                has_report=has_report,
                has_diagram=has_diagram,
                last_section=remembered,
            ),
        )
    if (
        not question
        and remembered
        and has_report
        and (_REF.search(raw) or _AGAIN.search(raw))
    ):
        return ChatAct(
            kind="revise",
            op="rewrite",
            section=remembered,
            brief=_brief_for(raw),
            say=f"Перепишу раздел «{remembered}» по документам. Новых чисел не добавлю.",
        )

    if not question and remembered and has_report and _BRIEF_ONLY.match(raw):
        return ChatAct(
            kind="revise",
            op="rewrite",
            section=remembered,
            brief=_brief_for(raw),
            say=f"Перепишу раздел «{remembered}» по документам. Новых чисел не добавлю.",
        )

    if not question:
        if wants_whole_report(raw) and has_report:
            return ChatAct(
                kind="revise",
                op="rewrite_all",
                brief="tighter",
                say="Сокращу каждый раздел по документам. Новых чисел не добавлю.",
            )
        if re.search(r"структур", raw, re.IGNORECASE) and re.search(
            r"презентац|слайд|дек", raw, re.IGNORECASE
        ):
            if not has_deck:
                return ChatAct(
                    kind="talk",
                    say="Презентации в этом чате ещё нет. Напиши «сделай презентацию», если её собрать.",
                )
            structure = _named(raw, _STRUCTURES)
            if not structure:
                return ChatAct(
                    kind="revise",
                    op="ask",
                    say=f"Какая структура: {STRUCTURE_ASK}?",
                )
            return ChatAct(
                kind="revise",
                op="restyle_structure",
                title=structure,
                say=f"Собираю презентацию для {STRUCTURE_SAY[structure]}. Текст возьму из документов.",
            )
        removed_section = parse_section_delete(raw)
        if removed_section is not None:
            if not has_report:
                return ChatAct(
                    kind="talk",
                    say="Отчёта в этом чате ещё нет, раздел убрать некуда.",
                )
            if not removed_section:
                return ChatAct(
                    kind="revise",
                    op="ask",
                    say="Какой раздел убрать? Напиши «убери раздел Введение».",
                )
            return ChatAct(
                kind="revise",
                op="delete_section",
                section=removed_section,
                say=f"Убираю раздел «{removed_section}».",
            )
        ordinal, para_name = paragraph_at(raw)
        if ordinal and para_name and has_report:
            return ChatAct(
                kind="revise",
                op="rewrite",
                section=para_name,
                slot=ordinal,
                brief=_brief_for(raw),
                say=f"Перепишу абзац {ordinal} раздела «{para_name}». Новых чисел не добавлю.",
            )
        added_paragraph = parse_paragraph_add(raw)
        if added_paragraph:
            if not has_report:
                return ChatAct(kind="talk", say="Отчёта в этом чате ещё нет, абзац добавить некуда.")
            return ChatAct(
                kind="revise",
                op="add_paragraph",
                section=added_paragraph[0],
                title=added_paragraph[1],
                say=f"Добавляю абзац в «{added_paragraph[0]}».",
            )
        added_section = parse_section_add(raw)
        if added_section:
            if not has_report:
                return ChatAct(kind="talk", say="Отчёта в этом чате ещё нет, раздел добавить некуда.")
            return ChatAct(
                kind="revise",
                op="add_section",
                section=added_section[0],
                title=added_section[1],
                say=f"Добавляю раздел «{added_section[0]}».",
            )
        caption = parse_caption(raw)
        if caption:
            if not has_report:
                return ChatAct(kind="talk", say="Отчёта в этом чате ещё нет, подпись ставить некуда.")
            return ChatAct(
                kind="revise",
                op="caption",
                section=caption[0],
                title=caption[1],
                say="Меняю подпись рисунка.",
            )
        photo = parse_photo_edit(raw)
        if photo is not None:
            fid, instruction = photo
            if not instruction:
                return ChatAct(
                    kind="revise",
                    op="ask",
                    say="Что изменить на фото? Напиши «на фото сделай небо темнее».",
                )
            say = f"Меняю фото {fid}." if fid else "Меняю фото."
            return ChatAct(
                kind="revise",
                op="edit_photo",
                section=fid,
                title=instruction,
                say=say + " Картинку перерисую по твоей фразе.",
            )
        removed_item = parse_item_delete(raw)
        if removed_item:
            if not has_report:
                return ChatAct(kind="talk", say="Отчёта в этом чате ещё нет, список править негде.")
            return ChatAct(
                kind="revise",
                op="delete_item",
                slot=removed_item[0],
                section=removed_item[1],
                say=f"Убираю «{removed_item[1]}» из списка.",
            )
        added_row = parse_row_add(raw)
        if added_row is not None:
            if not has_report:
                return ChatAct(kind="talk", say="Отчёта в этом чате ещё нет, таблицу править негде.")
            if not added_row[1]:
                return ChatAct(
                    kind="revise",
                    op="ask",
                    say="Какие ячейки в строке? Напиши «в таблице добавь строку: Гомель; 12».",
                )
            shown = "; ".join(added_row[1])
            return ChatAct(
                kind="revise",
                op="add_row",
                slot=added_row[0],
                items=added_row[1],
                say=f"Добавляю в таблицу строку: {shown}.",
            )
        removed_row = parse_row_delete(raw)
        if removed_row is not None:
            if not has_report:
                return ChatAct(kind="talk", say="Отчёта в этом чате ещё нет, таблицу править негде.")
            if not removed_row[1]:
                return ChatAct(
                    kind="revise",
                    op="ask",
                    say="Какую строку убрать? Напиши «убери из таблицы строку Гомель».",
                )
            return ChatAct(
                kind="revise",
                op="delete_row",
                slot=removed_row[0],
                section=removed_row[1],
                say=f"Убираю из таблицы строку «{removed_row[1]}».",
            )
        cell = parse_cell_replace(raw)
        if cell:
            if not has_report:
                return ChatAct(kind="talk", say="Отчёта в этом чате ещё нет, таблицу править негде.")
            return ChatAct(
                kind="revise",
                op="replace_cell",
                slot=cell[0],
                section=cell[1],
                title=cell[2],
                say=f"Меняю «{cell[1]}» на «{cell[2]}» в таблице.",
            )
        item = parse_item_replace(raw)
        if item:
            if not has_report:
                return ChatAct(kind="talk", say="Отчёта в этом чате ещё нет, список править негде.")
            return ChatAct(
                kind="revise",
                op="replace_item",
                slot=item[0],
                section=item[1],
                title=item[2],
                say=f"Меняю «{item[1]}» на «{item[2]}» в списке.",
            )
        added_item = parse_item_add(raw)
        if added_item:
            if not has_report:
                return ChatAct(kind="talk", say="Отчёта в этом чате ещё нет, список править негде.")
            return ChatAct(
                kind="revise",
                op="add_item",
                slot=added_item[0],
                title=added_item[1],
                say=f"Добавляю в список пункт «{added_item[1]}».",
            )
        if re.search(r"таблиц", raw, re.IGNORECASE) and re.search(
            r"поправь|измени|замени", raw, re.IGNORECASE
        ):
            if not has_report:
                return ChatAct(kind="talk", say="Отчёта в этом чате ещё нет, таблицу править негде.")
            return ChatAct(
                kind="revise",
                op="ask",
                say="Что заменить в таблице? Напиши «в таблице замени 10 на 12».",
            )
        if re.search(r"спис", raw, re.IGNORECASE) and re.search(
            r"поправь|измени|замени", raw, re.IGNORECASE
        ):
            if not has_report:
                return ChatAct(kind="talk", say="Отчёта в этом чате ещё нет, список править негде.")
            return ChatAct(
                kind="revise",
                op="ask",
                say="Что заменить в списке? Напиши «в списке замени кассу на выручку».",
            )
        diagram_edit = parse_diagram_edit(raw)
        if diagram_edit is not None:
            if not has_diagram:
                return ChatAct(
                    kind="talk",
                    say="Схемы в этом чате ещё нет. Напиши «сделай схему», если её собрать.",
                )
            if not diagram_edit:
                return ChatAct(
                    kind="revise",
                    op="ask",
                    say="Что изменить на схеме? Напиши «на схеме убери кассу».",
                )
            return ChatAct(
                kind="revise",
                op="refine_diagram",
                title=diagram_edit,
                say="Меняю схему по твоей фразе. Новых чисел не добавлю.",
            )

    if not question and (_REWRITE.search(raw) or _PROSE.search(raw)):
        if not has_report:
            if re.search(r"отч[её]т|раздел|абзац", raw, re.IGNORECASE):
                return ChatAct(
                    kind="talk",
                    say="Отчёта в этом чате ещё нет, переписывать нечего.",
                )
            return ChatAct(kind="talk")
        name = section_target(raw)
        if not name:
            return ChatAct(
                kind="revise",
                op="ask",
                say="Какой раздел переделать? Напиши название, например «переделай введение».",
            )
        return ChatAct(
            kind="revise",
            op="rewrite",
            section=name,
            brief=_brief_for(raw),
            say=f"Перепишу раздел «{name}» по документам. Новых чисел не добавлю.",
        )

    if not question and re.search(r"слайд", raw, re.IGNORECASE) and re.search(
        r"убери|удали|убрать|удалить", raw, re.IGNORECASE
    ):
        if not has_deck:
            return ChatAct(
                kind="talk",
                say="Презентации в этом чате ещё нет. Напиши «сделай презентацию», если её собрать.",
            )
        index = slide_index(raw)
        if not index:
            return ChatAct(
                kind="revise",
                op="ask",
                say="Какой слайд убрать? Напиши номер, например «убери слайд 2».",
            )
        return ChatAct(
            kind="revise",
            op="delete_slide",
            slide=index,
            say=f"Убираю слайд {index}. Остальные соберутся заново.",
        )

    renamed = parse_section_rename(raw) if (not question and has_report) else None
    if renamed and not has_report:
        return ChatAct(
            kind="talk",
            say="Отчёта в этом чате ещё нет, переименовать нечего.",
        )
    if renamed:
        return ChatAct(
            kind="revise",
            op="rename_heading",
            section=renamed[0],
            title=renamed[1],
            say=f"Переименую раздел «{renamed[0]}» в «{renamed[1]}». Текст раздела тот же.",
        )
    if not question and parse_section_rename(raw) and not has_report:
        return ChatAct(
            kind="talk",
            say="Отчёта в этом чате ещё нет, переименовать нечего.",
        )

    if not question and re.search(r"заголовок", raw, re.IGNORECASE) and re.search(
        r"поменяй|смени|измени|переименуй", raw, re.IGNORECASE
    ):
        if not (has_report or has_deck):
            return ChatAct(
                kind="talk",
                say="Пока нечего переименовать. Сначала собери отчёт или презентацию.",
            )
        title = parse_title(raw)
        if not title:
            return ChatAct(
                kind="revise",
                op="ask",
                say="Какой заголовок поставить?",
            )
        target = title_target(raw)
        if target == "deck" and not has_deck:
            return ChatAct(
                kind="talk",
                say="Презентации в этом чате ещё нет. Напиши «сделай презентацию», если её собрать.",
            )
        if target == "report" and not has_report:
            return ChatAct(
                kind="talk",
                say="Отчёта в этом чате ещё нет. Напиши «сделай отчёт», если его собрать.",
            )
        if not target and has_report and has_deck:
            return ChatAct(
                kind="revise",
                op="ask",
                say="Заголовок отчёта или презентации? Напиши «заголовок отчёта» или «заголовок презентации».",
            )
        if not target:
            target = "deck" if has_deck and not has_report else "report"
        slide_num = _slide_number_named(raw) if target == "deck" else 0
        place = (f"слайда {slide_num}" if slide_num > 1 else "слайда") if target == "deck" else "отчёта"
        return ChatAct(
            kind="revise",
            op="retitle",
            title=title,
            title_on=target,
            slide=slide_num,
            say=f"Меняю заголовок {place} на «{title}».",
        )

    if not question and re.search(r"слайд", raw, re.IGNORECASE) and re.search(
        r"перестав|перемест|подвинь|поставь", raw, re.IGNORECASE
    ) and not re.search(r"убери|удали|убрать|удалить", raw, re.IGNORECASE):
        if not has_deck:
            return ChatAct(
                kind="talk",
                say="Презентации в этом чате ещё нет. Напиши «сделай презентацию», если её собрать.",
            )
        source, dest = slide_move(raw)
        if not source or not dest:
            return ChatAct(
                kind="revise",
                op="ask",
                say="Какой слайд и на какое место? Например «переставь слайд 3 на место 1».",
            )
        return ChatAct(
            kind="revise",
            op="reorder_slide",
            slide=source,
            slide_to=dest,
            say=f"Переставляю слайд {source} на место {dest}.",
        )

    if not question and not _explicit_new_artifact(raw):
        hue = hue_edit(raw)
        if hue and (
            has_chart
            or ((has_report or has_deck) and re.search(r"график|столбц|цвет", raw, re.IGNORECASE))
        ):
            return _hue_act(raw, hue)

    if (
        not question
        and not _explicit_new_artifact(raw)
        and re.search(r"график", raw, re.IGNORECASE)
        and re.search(r"смени|поменяй|сделай|переделай|вид", raw, re.IGNORECASE)
    ):
        if not (has_report or has_deck or has_chart):
            return ChatAct(
                kind="talk",
                say="Графиков в этом чате ещё нет. Могу собрать отчёт или презу.",
            )
        chart = chart_type_named(raw)
        index = chart_at(raw)
        if not chart:
            names = ", ".join(CHART_SAY[key] for key in ("line", "bar", "donut", "horizontal_bar", "area", "scatter"))
            return ChatAct(
                kind="revise",
                op="ask",
                say=f"Какой вид графика: {names}?",
            )
        if index:
            return ChatAct(
                kind="revise",
                op="retype_chart",
                chart=chart,
                chart_at=index,
                say=f"Меняю график {index} на {CHART_SAY[chart]}. Числа те же.",
            )
        return ChatAct(
            kind="revise",
            op="retype_charts",
            chart=chart,
            say=f"Меняю графики на {CHART_SAY[chart]}. Числа те же.",
        )

    points = parse_slide_bullets(raw) if not question else None
    if points is not None:
        if not has_deck:
            return ChatAct(
                kind="talk",
                say="Презентации в этом чате ещё нет. Напиши «сделай презентацию», если её собрать.",
            )
        if not points[0]:
            return ChatAct(
                kind="revise",
                op="ask",
                say="На каком слайде пункты? Например «на слайде 2 пункты: риски; сроки».",
            )
        if not points[1]:
            return ChatAct(
                kind="revise",
                op="ask",
                say="Какие пункты поставить? Раздели их точкой с запятой.",
            )
        if len(points[1]) > 5:
            return ChatAct(
                kind="revise",
                op="ask",
                say="На слайде не больше 5 пунктов. Оставь пять и раздели их точкой с запятой.",
            )
        shown = "; ".join(points[1])
        return ChatAct(
            kind="revise",
            op="slide_bullets",
            slide=points[0],
            items=points[1],
            say=f"Ставлю на слайд {points[0]} пункты: {shown}.",
        )

    slide_body = parse_slide_body(raw) if not question else (0, "")
    if slide_body[0]:
        if not has_deck:
            return ChatAct(
                kind="talk",
                say="Презентации в этом чате ещё нет. Напиши «сделай презентацию», если её собрать.",
            )
        if not slide_body[1]:
            return ChatAct(
                kind="revise",
                op="ask",
                say="Что написать на слайде? Например «на слайде 2 напиши риски».",
            )
        return ChatAct(
            kind="revise",
            op="slide_text",
            slide=slide_body[0],
            title=slide_body[1],
            say=f"Меняю заголовок слайда {slide_body[0]}. Новых чисел нет.",
        )

    topic = parse_new_slide(raw) if not question else None
    if topic is not None:
        if not has_deck:
            return ChatAct(
                kind="talk",
                say="Презентации в этом чате ещё нет. Напиши «сделай презентацию», если её собрать.",
            )
        if not topic:
            return ChatAct(
                kind="revise",
                op="ask",
                say="О чём слайд? Напиши «добавь слайд про …». Новых чисел не добавлю.",
            )
        return ChatAct(
            kind="revise",
            op="add_slide",
            title=topic,
            say=f"Добавляю слайд «{topic}». Новых чисел нет.",
        )

    if (
        not question
        and (has_deck or has_report or has_diagram)
        and not _explicit_new_artifact(raw)
        and _EDIT.search(raw)
    ):
        return ChatAct(
            kind="revise",
            op="ask",
            say=_clarify(
                has_deck=has_deck,
                has_report=has_report,
                has_diagram=has_diagram,
                last_section=remembered,
            ),
        )

    if raw == "текст" and has_report:
        return ChatAct(
            kind="revise",
            op="rewrite",
            section=remembered,
            brief="prettier",
            say="Поправлю текст по документам. Новых чисел не добавлю.",
        )
    if raw == "стиль" and has_deck:
        return ChatAct(
            kind="revise",
            op="recolor_deck",
            say="Соберу презентацию в следующем стиле. Текст слайдов тот же.",
        )

    named_pack = _named(raw, _PACKS)
    if (
        has_deck
        and named_pack
        and re.search(r"презентац|презу|преза", raw, re.IGNORECASE)
        and not re.search(
            r"сделай|собрать|подготовь|оформи|сверстай|нарисуй|построй|сгенерируй|новую|новый",
            raw,
            re.IGNORECASE,
        )
    ):
        return ChatAct(
            kind="revise",
            op="recolor_deck",
            pack=named_pack,
            say=(
                f"Перекрашиваю презентацию в {PACK_LABELS[named_pack]}. "
                "Слайды соберутся заново, текст тот же."
            ),
        )

    route = resolve_turn(raw, bias)
    if route != "chat":
        return ChatAct(kind="build", build=route)
    return ChatAct(kind="talk")
