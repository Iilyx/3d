"""Chat reply and the line spoken before an artifact job."""

from __future__ import annotations

import logging
import re
from dataclasses import replace
from typing import Callable

from case3.chat_summary import is_clean_chat_summary
from case3.llm_client import LLMClient, LLMConfig, LLMConfigError, LLMError
from case3.prompts import load as load_prompt

log = logging.getLogger(__name__)

_KIND_LABEL = {
    "report": "отчёт",
    "diagram": "схему",
    "presentation": "презентацию",
}

_DONE_CLAIM = re.compile(r"(?i)\b(готово|собрано|pdf готов|презентац\w* готов\w*)\b")
# A year or a rank is not a rival cell. «за 2025», «1 место», «в 2 раза».
_ASIDE_YEAR = re.compile(r"(?:19|20)\d{2}")
_ASIDE_AFTER = re.compile(
    r"^\s*(?:"
    r"место|раз|раза|квартал\w*|полугоди\w*|"
    r"январ\w*|феврал\w*|март\w*|апрел\w*|ма[йяюем]|июн\w*|июл\w*|август\w*|"
    r"сентябр\w*|октябр\w*|ноябр\w*|декабр\w*"
    r")\b",
    re.IGNORECASE,
)
# Spaced thousands are one value: «105 865,2», not 105 and 865,2.
# Boundaries protect hex colors (#4E79A7), IDs (B2B, s01, cht_01), and CSS (2px).
_NUM = re.compile(
    r"(?<![0-9A-Za-zА-Яа-яЁё#_])"
    r"(?:(?<![0-9A-Za-zА-Яа-яЁё#_.,])[-−])?"
    r"(?:"
    r"\d{1,3}(?:[ \u00a0\u202f]\d{3})+(?:[.,]\d+)?"
    r"|\d+(?:\\,\d{3})+(?:[.,]\d+)?"
    r"|\d+\{,\}\d+"
    r"|\d+(?:[.,]\d+)?"
    r")"
    r"(?:\\%|%)?"
    r"(?![0-9A-Za-z_])"
)
# Longer stems first so «двадцать» is not read as «два».
_SPOKEN_NUMBER = (
    ("девятнадцат", "19"),
    ("восемнадцат", "18"),
    ("семнадцат", "17"),
    ("шестнадцат", "16"),
    ("пятнадцат", "15"),
    ("четырнадцат", "14"),
    ("тринадцат", "13"),
    ("двенадцат", "12"),
    ("одиннадцат", "11"),
    ("девяност", "90"),
    ("восьмидесят", "80"),
    ("семидесят", "70"),
    ("шестидесят", "60"),
    ("пятидесят", "50"),
    ("тридцат", "30"),
    ("двадцат", "20"),
    ("четыр", "4"),
    ("девят", "9"),
    ("восем", "8"),
    ("десять", "10"),
    ("сорок", "40"),
    ("шест", "6"),
    ("пять", "5"),
    ("семь", "7"),
    ("три", "3"),
    ("сто", "100"),
    ("две", "2"),
    ("два", "2"),
)
_SPOKEN_RE = re.compile(
    r"\b(?:"
    + "|".join(stem for stem, _digit in _SPOKEN_NUMBER)
    + r")(?:ь|и|ю|е|а|у|о)?\b",
    re.IGNORECASE,
)
_SPOKEN_VALUE = {stem: digit for stem, digit in _SPOKEN_NUMBER}

_BRIEF_LINE = {
    "clearer": "Сделай формулировку точнее. Смысл и числа те же.",
    "tighter": "Сделай короче. Смысл и числа те же.",
    "dislike": "Перепиши так, чтобы читалось яснее. Смысл и числа те же.",
    "prettier": "Сделай абзац ровнее и яснее. Смысл и числа те же.",
}


def _plain_user_prompt(text: str | None) -> str:
    """Strip internal memory/UI sections so openings only quote the user's request."""
    raw = text or ""
    cut = len(raw)
    for marker in _MEMORY_AT:
        idx = raw.find(marker)
        if 0 <= idx < cut:
            cut = idx
    return raw[:cut].strip()


def opening_fallback(kind: str, user_text: str) -> str:
    """Local line when the opening model is unavailable. Does not claim the file is done."""
    label = _KIND_LABEL.get(kind, "материал")
    topic = " ".join(_plain_user_prompt(user_text).split())
    if len(topic) > 90:
        topic = topic[:89].rstrip() + "…"
    if topic:
        return (
            f"Соберу {label} по этому запросу: {topic}. "
            "Возьму только то, что уже написано, и ничего не допишу."
        )
    return (
        f"Соберу {label} по приложенным данным. "
        "Числа возьму только оттуда."
    )


_TITLE_LEAD = re.compile(
    r"^(?:ну[, ]+|пожалуйста[, ]+)?"
    r"(?:дай(?:те)?(?:\s+мне)?|покажи(?:те)?|скажи(?:те)?|назови(?:те)?|"
    r"проанализируй(?:те)?|разбери(?:те)?|открой(?:те)?|посмотри(?:те)?|"
    r"объясни(?:те)?|сделай(?:те)?|расскажи(?:те)?|найди(?:те)?|выведи(?:те)?)\s+",
    re.IGNORECASE,
)
_TITLE_META = re.compile(r"назван|как назвать|что это", re.IGNORECASE)
_TITLE_SKIP = re.compile(
    r"^(?:#+\s*)?(?:данные дашборда|экран|таблица pdf|производные|фильтры|"
    r"карточки|график или карта|заголовок)$",
    re.IGNORECASE,
)


def _clip_title(text: str) -> str:
    words = " ".join(text.split())
    if len(words) > 48:
        words = words[:45].rstrip(" ,.;:") + "…"
    if not words:
        return ""
    return words[:1].upper() + words[1:]


def _source_phrase(source: str) -> str:
    for raw in (source or "").replace("\r\n", "\n").splitlines():
        line = raw.strip().lstrip("#").strip()
        if not line or line.startswith("|") or line.startswith("====="):
            continue
        if _TITLE_SKIP.match(line):
            continue
        if line.startswith("Фильтр «") or line.startswith("Числа "):
            continue
        return _clip_title(line)
    return ""


def session_title(user_text: str, source: str = "") -> str:
    """Sidebar name. A dashboard heading wins over the user's command."""
    from case3.dashboard_source import dashboard_title

    named = dashboard_title(source or "")
    if named:
        return named
    first = " ".join((user_text or "").strip().splitlines()[:1]).strip()
    if first and not _TITLE_META.search(first):
        topic = _TITLE_LEAD.sub("", first).strip(" ?.!,")
        if topic and (topic.casefold() != first.casefold() or not _TITLE_LEAD.match(first)):
            clipped = _clip_title(topic)
            if len(clipped) >= 3:
                return clipped
    return _source_phrase(source) or "Разбор"


def chat_fallback() -> str:
    return (
        "Не удалось получить ответ модели. "
        "Повторите вопрос или пришлите текст, который нужно разобрать."
    )


def _source_paragraphs(text: str) -> list[str]:
    return [part.strip() for part in re.split(r"\n\s*\n", text) if part.strip()]


def _fit_front(paras: list[str], budget: int) -> tuple[list[str], int]:
    from case3.chat_memory import _clip_prose

    chosen: list[str] = []
    used = 0
    for index, para in enumerate(paras):
        gap = 2 if chosen else 0
        if used + gap + len(para) <= budget:
            chosen.append(para)
            used += gap + len(para)
            continue
        room = budget - used - gap
        if room > 80 and not chosen:
            piece = _shrink_paragraph(para, room)
            if not piece:
                piece = _clip_prose(para, room)
            chosen.append(piece)
            return chosen, index + 1
        break
    return chosen, len(chosen)


def _fit_back(paras: list[str], budget: int) -> tuple[list[str], int]:
    chosen: list[str] = []
    used = 0
    start = len(paras)
    for index in range(len(paras) - 1, -1, -1):
        para = paras[index]
        gap = 2 if chosen else 0
        if used + gap + len(para) <= budget:
            chosen.append(para)
            used += gap + len(para)
            start = index
            continue
        room = budget - used - gap
        if room > 80:
            piece = _shrink_paragraph(para, room)
            if not piece:
                piece = para[-room:].lstrip()
                if len(para) > room:
                    piece = "…" + piece
            chosen.append(piece)
            start = index
        break
    chosen.reverse()
    return chosen, start


def _shrink_paragraph(para: str, room: int) -> str:
    """A cut table keeps its header. Prose returns empty so the caller slices it."""
    if not (para or "").lstrip().startswith("|"):
        return ""
    return _focus_table(para, set(), room) or ""


def _focus_hits(para: str, stems: set[str]) -> int:
    from case3.chat_memory import _stem

    if not stems:
        return 0
    found = {
        _stem(word)
        for word in re.findall(r"[0-9A-Za-zА-Яа-яЁё]{4,}", para)
    }
    return len(stems & found)


def _focus_table(para: str, stems: set[str], budget: int) -> str | None:
    """Header, rows the question names, then as many other rows as fit."""
    lines = [line.rstrip() for line in (para or "").splitlines() if line.strip()]
    if len(lines) < 2 or not lines[0].lstrip().startswith("|"):
        return None
    header = [lines[0]]
    rest = lines[1:]
    if rest and re.match(r"^\|?[\s\-:|]+\|?$", rest[0].strip()):
        header.append(rest[0])
        rest = rest[1:]
    scored = [
        (_focus_hits(row, stems), index)
        for index, row in enumerate(rest)
    ]
    first = [
        index
        for score, index in sorted(scored, key=lambda item: (-item[0], item[1]))
        if score >= 1
    ]
    if not first:
        first = list(range(min(4, len(rest))))
    order = first + [index for index in range(len(rest)) if index not in set(first)]
    kept = list(header)
    for index in order:
        trial = "\n".join(kept + [rest[index]])
        if len(trial) > budget:
            break
        kept.append(rest[index])
    return "\n".join(kept)


# A dashboard of 500 rows fits. Past this, the prompt says how many rows remain.
_CHAT_SOURCE_CAP = 80_000


def _clip_source(source: str, limit: int = _CHAT_SOURCE_CAP, focus: str = "") -> str:
    """Head, paragraphs that match the question, then the tail.

    A short document is unchanged. A long one stays inside ``limit``.
    A markdown table keeps its header and the rows the question names.
    """
    text = (source or "").strip()
    if len(text) <= limit:
        return text
    shared = _clip_dashboard_shots(text, limit, focus)
    if shared:
        return shared
    from case3.chat_memory import _query_stems

    stems = set(_query_stems(focus or ""))
    paras = [
        _focus_table(para, stems, limit) or para
        for para in _source_paragraphs(text)
    ]
    if not paras:
        return text[: limit - 1].rstrip() + "…"
    if len(paras) == 1:
        single = paras[0]
        if len(single) <= limit:
            return single
        return single[: limit - 1].rstrip() + "…"
    head, head_n = _fit_front(paras, max(200, (limit * 2) // 5))
    tail, tail_at_rel = _fit_back(paras[head_n:], max(200, limit // 4))
    tail_at = head_n + tail_at_rel
    if head_n > tail_at:
        chunks = [part for part in ("\n\n".join(head), "\n\n".join(tail)) if part]
        body = "\n\n…\n\n".join(chunks)
        if len(body) <= limit:
            return body
        return body[: limit - 1].rstrip() + "…"
    middle = paras[head_n:tail_at]
    ranked = sorted(
        range(len(middle)),
        key=lambda index: (-_focus_hits(middle[index], stems), index),
    )
    used = len("\n\n".join(head)) + len("\n\n".join(tail)) + 12
    picked: list[tuple[int, str]] = []
    for index in ranked:
        if _focus_hits(middle[index], stems) < 1:
            break
        para = middle[index]
        if used + len(para) + 2 > limit:
            continue
        picked.append((index, para))
        used += len(para) + 2
    picked.sort(key=lambda item: item[0])
    chunks = ["\n\n".join(head)]
    if picked:
        chunks.append("\n\n".join(para for _index, para in picked))
    if tail:
        chunks.append("\n\n".join(tail))
    body = "\n\n…\n\n".join(chunk for chunk in chunks if chunk)
    if len(body) <= limit:
        return body
    return body[: limit - 1].rstrip() + "…"


# format_thread keeps eight turns as paragraphs and the rest as short lines.
# A legal 48-hop thread stays under this cap
# (test_fattest_legal_thread_is_pasted_whole). The cap only stops a runaway
# blob. 150000 characters is about 75–95k tokens of Russian.
_MEMORY_CAP = 150_000
_CHAT_ANSWER_TOKENS = 4096
_PIN_BITS = (
    "не Source",
    "не источник",
    "Числа и факты бери только из",
)


def _split_message(intent: str) -> tuple[str, str]:
    """User words, then the memory blocks pasted after them."""
    text = intent or ""
    cut = len(text)
    for marker in _MEMORY_AT:
        at = text.find(marker)
        if at != -1:
            cut = min(cut, at)
    return text[:cut].strip(), text[cut:].strip()


def _end_slice(text: str, limit: int) -> str:
    """Keep the end of one over-long line, on a word break when it is close."""
    if len(text) <= limit:
        return text
    if limit <= 1:
        return ""
    piece = text[-(limit - 1) :]
    spot = piece.find(" ")
    if 0 < spot <= 40:
        piece = piece[spot + 1 :]
    return "…" + piece


_TURN_START = (
    "Ход ",
    "Начало:",
    "Раньше:",
    "Дальше:",
    "Ответ",
    "Последняя правка",
    "Один прошлый",
    "Запрос:",
    "Карточка",
    "Предыдущий",
)
# A new block. An unlabeled line before one of these is the cut edge of an
# older turn. A line before «Ответ» or «Дальше» is the previous paragraph.
_NEW_BLOCK = (
    "Ход ",
    "Начало:",
    "Раньше:",
    "Один прошлый",
    "Карточка",
    "Предыдущий",
    "Последняя правка",
)
_PIN_MAX = 240
_MESSAGE_CAP = 6000


def _on_turn_boundary(line: str) -> bool:
    return line.startswith(_TURN_START) or (
        len(line) <= _PIN_MAX and any(bit in line for bit in _PIN_BITS)
    )


def _is_pin(line: str) -> bool:
    """Short grounding line. A long answer that mentions the phrase is not one."""
    return len(line) <= _PIN_MAX and any(bit in line for bit in _PIN_BITS)


def _pack_tail(lines: list[str], limit: int) -> list[str]:
    if limit <= 1:
        return []
    chosen: list[str] = []
    used = 0
    for line in reversed(lines):
        need = len(line) + (1 if chosen else 0)
        if used + need > limit:
            if not chosen:
                chosen.append(_end_slice(line, limit))
            break
        chosen.append(line)
        used += need
    chosen.reverse()
    return chosen


def _snap_before_new_block(chosen: list[str]) -> list[str]:
    while len(chosen) > 1 and not _on_turn_boundary(chosen[0]):
        if not chosen[1].startswith(_NEW_BLOCK):
            break
        chosen.pop(0)
    return chosen


def _dropped_pins(lines: list[str], tail: str) -> list[str]:
    kept = set(tail.split("\n"))
    pins: list[str] = []
    seen: set[str] = set()
    for line in lines:
        if not _is_pin(line) or line in seen or line in kept:
            continue
        seen.add(line)
        pins.append(line)
    return pins


def _keep_tail(text: str, limit: int) -> str:
    """Drop old lines first. The latest answer stays. Short grounding lines stay."""
    body = (text or "").strip()
    if len(body) <= limit:
        return body
    lines = body.split("\n")
    chosen = _snap_before_new_block(_pack_tail(lines, limit))
    tail = "\n".join(chosen).strip()
    pins = _dropped_pins(lines, tail)
    pin = "\n".join(pins)
    if not pin:
        return tail
    glued = pin + "\n…\n" + tail
    if len(glued) <= limit:
        return glued
    room = limit - len(pin) - len("\n…\n")
    if room <= 1:
        return _end_slice(body, limit)
    chosen = _snap_before_new_block(_pack_tail(tail.split("\n"), room))
    tail = "\n".join(chosen).strip()
    if not tail:
        return pin
    return pin + "\n…\n" + tail


def _keep_question(text: str, limit: int = _MESSAGE_CAP) -> str:
    """The current question. Over the cap, keep the opening and the last paragraph."""
    from case3.chat_memory import _clip_prose

    raw = str(text or "").replace("\r\n", "\n").replace("\r", "\n").strip()
    if len(raw) <= limit:
        return _clip_prose(raw, limit)
    head_budget = max(1, (limit * 2) // 3)
    tail_budget = max(1, limit - head_budget - 5)
    head = _clip_prose(raw, head_budget)
    piece = raw[-tail_budget:]
    for sep in ("\n\n", "\n", ". "):
        spot = piece.find(sep)
        if 0 <= spot <= 180:
            piece = piece[spot + len(sep) :].lstrip()
            break
    piece = piece.strip()
    if not piece or piece in head:
        return head
    return head + "\n\n…\n\n" + piece


_MD_HEADING = re.compile(r"^(#{1,3})[ \t]+(\S.*?)\s*$", re.MULTILINE)


def _source_outline(text: str, limit: int = 1200) -> str:
    titles: list[str] = []
    for match in _MD_HEADING.finditer(text or ""):
        title = " ".join(match.group(2).split())
        if title:
            titles.append(f"{match.group(1)} {title}")
    if not titles:
        return ""
    body = "\n".join(titles)
    if len(body) > limit:
        body = body[: limit - 1].rstrip() + "…"
    return "Оглавление документа:\n" + body


def _row_noun(count: int, case: str) -> str:
    """Accusative after «вижу», genitive after «из»."""
    rest = abs(count) % 100
    tail = rest % 10
    if case == "gen":
        word = "строки" if tail == 1 and rest != 11 else "строк"
        return word
    if 11 <= rest <= 14:
        return "строк"
    if tail == 1:
        return "строку"
    if 2 <= tail <= 4:
        return "строки"
    return "строк"


def _markdown_data_rows(text: str) -> list[str]:
    lines = (text or "").splitlines()
    rows: list[str] = []
    index = 0
    while index < len(lines):
        if not lines[index].strip().startswith("|"):
            index += 1
            continue
        block: list[str] = []
        while index < len(lines) and lines[index].strip().startswith("|"):
            block.append(lines[index].strip())
            index += 1
        if len(block) >= 2 and re.match(r"^\|?[\s\-:|]+\|?$", block[1]) and "-" in block[1]:
            rows.extend(block[2:])
    return rows


def _table_coverage_line(full: str, shown: str) -> str:
    """The sentence the model must copy. Empty when the text has no table."""
    total = _markdown_data_rows(full)
    if len(total) < 2:
        return ""
    visible = _markdown_data_rows(shown)
    if len(visible) >= len(total):
        noun = _row_noun(len(total), "acc")
        return f"Вижу все {len(total)} {noun}."
    noun = _row_noun(len(total), "gen")
    return f"Вижу {len(visible)} из {len(total)} {noun}."


def _clip_dashboard_shots(text: str, limit: int, focus: str) -> str:
    """Keep every snapshot. A long screen keeps a share of the budget, not only the ends."""
    from case3.chat_memory import dashboard_parts, format_sources

    parts = dashboard_parts(text)
    if len(parts) < 2:
        return ""
    packed = format_sources(parts)
    if len(packed) <= limit:
        return packed
    budget = max(1500, limit // len(parts))
    clipped: list[tuple[str, str]] = []
    for name, body in parts:
        shown = body if len(body) <= budget else _clip_source(body, budget, focus)
        clipped.append((name, shown))
    return format_sources(clipped)


def _user_block(source: str, intent: str) -> str:
    """Question, document, then memory.

    The question keeps its paragraphs, and its last paragraph if it is long.
    Memory is cut from the front, so the latest answer is the last thing in
    the prompt when the chain is long.
    """
    message, memory = _split_message(intent or "")
    message = _keep_question(message)
    memory = _keep_tail(memory, _MEMORY_CAP)
    from case3.dashboard_source import note_closed_month

    full = note_closed_month((source or "").strip(), message)
    limit = 200_000 if "# Данные дашборда" in full else _CHAT_SOURCE_CAP
    src = _clip_source(full, limit, focus=message)
    coverage = _table_coverage_line(full, src)
    if src and len(src) < len(full):
        outline = _source_outline(source)
        if outline:
            src = outline + "\n\n" + src
    elif not src:
        src = _source_outline(source)
    if coverage:
        src = (src + "\n\n" + coverage).strip() if src else coverage
    parts: list[str] = []
    if message:
        parts.append("СООБЩЕНИЕ:\n" + message)
    if src and src != message:
        parts.append("ТЕКСТ:\n" + src)
    elif src and not message:
        parts.append("ТЕКСТ:\n" + src)
    if memory:
        parts.append(memory)
    return "\n\n".join(parts) or "(пусто)"


def _speak(
    client: LLMClient,
    *,
    system: str,
    user_text: str,
    max_tokens: int,
    on_delta: Callable[[str], None] | None,
) -> str:
    parts: list[str] = []

    def emit(piece: str) -> None:
        if not piece:
            return
        parts.append(piece)
        if on_delta:
            on_delta(piece)

    if on_delta is None and hasattr(client, "complete"):
        emit(
            client.complete(
                system=system,
                user_text=user_text,
                reasoning="off",
            )
        )
    elif hasattr(client, "stream"):
        for piece in client.stream(
            system=system,
            user_text=user_text,
            reasoning="off",
            max_tokens=max_tokens,
        ):
            emit(piece or "")
    else:
        emit(
            client.complete(
                system=system,
                user_text=user_text,
                reasoning="off",
            )
        )
    out = "".join(parts).strip()
    if (
        out
        and getattr(client, "last_finish_reason", "") == "length"
        and out.rstrip()[-1] not in ".!?»\")…]"
        and hasattr(client, "complete")
    ):
        try:
            cont = client.complete(
                system=system,
                user_text=(
                    user_text
                    + "\n\nНачало ответа уже написано:\n"
                    + out[-1200:]
                    + "\n\nЗаверши последнюю мысль и итог кратко (2–4 предложения), без повторения начала."
                ),
                reasoning="off",
            )
        except (LLMError, LLMConfigError, OSError, ValueError):
            cont = ""
        cont_s = (cont or "").strip()
        if cont_s:
            sep = "" if out.endswith((" ", "\n", "—", "-")) else " "
            out = (out + sep + cont_s).strip()
            if on_delta:
                on_delta(sep + cont_s)
    return out


def _client(max_tokens: int, timeout_s: float) -> LLMClient:
    cfg = LLMConfig.from_env()
    return LLMClient(
        replace(
            cfg,
            timeout_s=min(float(cfg.timeout_s), timeout_s),
            max_retries=max(1, int(cfg.max_retries or 0)),
            max_tokens=max_tokens,
            reasoning="off",
        )
    )


def _accepted(text: str, *, block_done: bool = False) -> str:
    """Keep a chat answer that says «собрано». Block that word only in the opening line."""
    cleaned = (text or "").strip()
    if not cleaned:
        return ""
    if block_done and _DONE_CLAIM.search(cleaned):
        return ""
    if not is_clean_chat_summary(cleaned):
        return ""
    return cleaned


def try_opening(
    kind: str,
    user_text: str,
    *,
    client: LLMClient | None = None,
    on_delta: Callable[[str], None] | None = None,
) -> str:
    """Short line before the artifact job. Always returns Russian text."""
    plain = _plain_user_prompt(user_text)
    fallback = opening_fallback(kind, plain)
    system = load_prompt("chat_opening").strip()
    user = (
        f"Артефакт: {_KIND_LABEL.get(kind, kind)}.\n"
        f"Запрос:\n{plain[:1500] or '(только вложение)'}"
    )
    text = ""
    try:
        llm = client or _client(1024, 30.0)
        text = _accepted(
            _speak(llm, system=system, user_text=user, max_tokens=1024, on_delta=None),
            block_done=True,
        )
    except (LLMError, LLMConfigError, OSError, ValueError) as exc:
        log.warning("opening failed: %s", exc)
        text = ""
    spoken = text or fallback
    if on_delta:
        on_delta(spoken)
    return spoken


_MEMORY_AT = (
    "\n\nЧисла из реплик пользователя",
    "\n\nКарточка этого чата",
    "\n\nРазговор этого чата",
    "\n\nПредыдущий ход этого чата",
    "\n\nОдин прошлый ход",
    "\n\nТребования UI:",
)
_CHOICE = re.compile(
    r"стоит (?P<doc>\d+(?:[.,]\d+)?%?), ты написал (?P<user>\d+(?:[.,]\d+)?%?)"
)
_INDEX_STEMS = frozenset(
    {
        "слайд",
        "пункт",
        "раздел",
        "глав",
        "строк",
        "таблиц",
        "график",
        "страниц",
        "рисун",
        "ход",
        "абзац",
    }
)
_STOP_STEMS = frozenset(
    {
        "был",
        "стал",
        "этот",
        "документ",
        "текст",
        "отчет",
        "отче",
        "чат",
        "сообщ",
        "напиш",
        "остав",
        "год",
        "числ",
        "сумм",
        "всег",
        "окол",
        "прим",
        "проц",
        "тольк",
        "потом",
        "затем",
        "котор",
        "нужн",
        "откры",
        # Column words on every dashboard row. A named region still conflicts.
        "область",
        "област",
        "регион",
        "район",
    }
)


def _aside_number(text: str, match: re.Match[str]) -> bool:
    """True when this digit is a period or a rank, not a cell the user is correcting."""
    token = match.group(0).replace("%", "")
    if _ASIDE_YEAR.fullmatch(token):
        return True
    return bool(_ASIDE_AFTER.match(text[match.end() : match.end() + 16]))


_MEMORY_HEADS = tuple(marker.lstrip("\n") for marker in _MEMORY_AT)


def latest_user_line(intent: str | None) -> str:
    """The user's own words. Memory pasted after them is not a new statement."""
    text = intent or ""
    cut = len(text)
    for marker in _MEMORY_AT:
        at = text.find(marker)
        if at != -1:
            cut = min(cut, at)
    for head in _MEMORY_HEADS:
        if text.startswith(head):
            return ""
        at = text.find("\n" + head)
        if at != -1:
            cut = min(cut, at)
    return text[:cut].strip()


def spoken_number_norms(text: str | None) -> set[str]:
    """Cardinals written as words. «двенадцать» is 12. «один» is not a number."""
    found: set[str] = set()
    for match in _SPOKEN_RE.finditer(text or ""):
        stem = match.group(0).casefold().replace("ё", "е")
        for prefix, digit in _SPOKEN_NUMBER:
            if stem.startswith(prefix):
                found.add(digit)
                break
    return found


def _is_list_marker(text: str, start: int, end: int) -> bool:
    """``1. Пункт`` is a marker. ``2024. Выручка`` and ``1.1. Раздел`` are numbers."""
    token = (text or "")[start:end]
    if not token.isdigit() or len(token) >= 4:
        return False
    line_start = text.rfind("\n", 0, start) + 1
    if text[line_start:start].strip():
        return False
    return bool(re.match(r"[.)](?:\s|$)", text[end:]))


def _fact_tokens(text: str | None) -> list[str]:
    raw = text or ""
    return [
        match.group(0)
        for match in _NUM.finditer(raw)
        if not _is_list_marker(raw, match.start(), match.end())
    ]


def number_norms(text: str | None) -> set[str]:
    return {_norm_num(token) for token in _fact_tokens(text)} | spoken_number_norms(text)


def user_stated_norms(intent: str | None) -> set[str]:
    """Norms from the one user-number line. The rest of the thread is ignored."""
    text = intent or ""
    mark = "Числа из реплик пользователя"
    at = text.find(mark)
    if at < 0:
        return set()
    rest = text[at + len(mark) :]
    line = rest.split("\n", 1)[0]
    body = rest.split("\n", 1)[1] if "\n" in rest else ""
    body = body.split("\n", 1)[0]
    return number_norms(body if body.strip() else line)


def stray_numbers(text: str | None, allowed: set[str]) -> list[str]:
    """Number tokens in text that are not in the allowed set. Order kept."""
    found: list[str] = []
    seen: set[str] = set()
    for token in _fact_tokens(text):
        norm = _norm_num(token)
        if norm in allowed or norm in seen:
            continue
        seen.add(norm)
        found.append(token)
    for match in _SPOKEN_RE.finditer(text or ""):
        word = match.group(0)
        stem = word.casefold().replace("ё", "е")
        digit = ""
        for prefix, value in _SPOKEN_NUMBER:
            if stem.startswith(prefix):
                digit = value
                break
        if not digit or digit in allowed or digit in seen:
            continue
        seen.add(digit)
        found.append(word)
    return found


def _words_before(text: str, start: int) -> list[str]:
    window = text[max(0, start - 48) : start]
    return re.findall(r"[0-9A-Za-zА-Яа-яЁё]{3,}", window)[-3:]


def _subject_word(text: str, start: int) -> str:
    from case3.chat_memory import _stem

    words = _words_before(text, start)
    picked = ""
    for word in words:
        stem = _stem(word)
        if stem in _INDEX_STEMS:
            continue
        if stem in _STOP_STEMS or len(stem) < 4:
            continue
        picked = word
    return picked


def _fact_words(text: str, start: int) -> list[tuple[str, str]]:
    """Content words before a number, nearest last. «кассе теперь 30» keeps both."""
    from case3.chat_memory import _stem

    found: list[tuple[str, str]] = []
    for word in _words_before(text, start):
        stem = _stem(word)
        if stem in _INDEX_STEMS or stem in _STOP_STEMS or len(stem) < 4:
            continue
        found.append((word, stem))
    return found


def _subjects_near(text: str, start: int) -> set[str]:
    return {stem for _word, stem in _fact_words(text, start)}


def _nearest_stem(text: str, start: int) -> str:
    words = _fact_words(text, start)
    return words[-1][1] if words else ""


_CHANGE_PREFIXES = ("вырос", "сниз", "упа", "прирос", "измен", "увелич", "сократ", "паден")


def _claim_words(text: str, start: int, token: str) -> list[tuple[str, str]]:
    """A growth percent belongs to the verb, not the noun before it."""
    words = _fact_words(text, start)
    if token.endswith("%") and words and words[-1][1].startswith(_CHANGE_PREFIXES):
        return [words[-1]]
    return words


def fact_conflict(user_text: str | None, source: str | None) -> tuple[str, str, str] | None:
    """User number and a different document number about the same word."""
    raw = user_text or ""
    doc = source or ""
    from case3.fact_ground import table_grid

    grid = table_grid(doc) if "|" in doc else None
    for hit in _NUM.finditer(raw):
        if _is_list_marker(raw, hit.start(), hit.end()) or _aside_number(raw, hit):
            continue
        pairs = _claim_words(raw, hit.start(), hit.group())
        user_stems = {stem for _word, stem in pairs}
        if not user_stems:
            continue
        user_norm = _norm_num(hit.group())
        if grid is not None and grid.rows:
            if any(
                user_norm in grid.rows.get(stem, set())
                or user_norm in grid.aggregates
                for stem in user_stems
            ):
                continue
            row_stems = user_stems & set(grid.rows.keys())
            if row_stems and all(
                user_norm in grid.rows.get(stem, set()) for stem in row_stems
            ):
                continue
        same_subject_same_value = False
        for other in _NUM.finditer(doc):
            if _norm_num(other.group()) != user_norm:
                continue
            # The same digit on a later metric does not excuse this one.
            if _nearest_stem(doc, other.start()) in user_stems:
                same_subject_same_value = True
                break
        if same_subject_same_value:
            continue
        for other in _NUM.finditer(doc):
            if _is_list_marker(doc, other.start(), other.end()) or _aside_number(doc, other):
                continue
            if _norm_num(other.group()) == user_norm:
                continue
            shared = user_stems & _subjects_near(doc, other.start())
            if not shared:
                continue
            word = ""
            for surface, stem in pairs:
                if stem in shared:
                    word = surface
            return word, other.group(), hit.group()
    return None


def conflict_question(word: str, doc: str, user: str) -> str:
    label = word[:1].upper() + word[1:] if word else "этом месте"
    return (
        f"В документе у «{label}» стоит {doc}, ты написал {user}. "
        f"Напиши {user}, чтобы оставить твоё, или {doc}, чтобы оставить документ."
    )


def invention_question(tokens: list[str]) -> str:
    shown = tokens[:3]
    if len(shown) == 1:
        names = f"числа {shown[0]}"
    else:
        names = "чисел " + " и ".join(shown)
    more = f" и ещё {len(tokens) - 3}" if len(tokens) > 3 else ""
    return (
        f"В документах и в твоём сообщении нет {names}{more}. "
        "Напиши нужное число, если его надо учесть, или напиши «без числа»."
    )


def _request_blob(intent: str) -> str:
    """Only the latest line. A «Запрос:» inside the thread is not an allow-list."""
    return latest_user_line(intent)


def _answering_choice(intent: str) -> bool:
    latest = latest_user_line(intent)
    if (
        len(latest) <= 80
        and re.search(r"без\s+числа", latest, re.IGNORECASE)
        and "В документах и в твоём сообщении нет" in (intent or "")
    ):
        return True
    found = _CHOICE.search(intent or "")
    if not found:
        return False
    latest = latest_user_line(intent)
    if len(latest) > 80:
        return False
    if number_norms(latest) & { _norm_num(found.group("doc")), _norm_num(found.group("user")) }:
        return True
    return bool(re.search(r"документ|твоё|твое|без числа", latest, re.IGNORECASE))


def choice_instruction(intent: str) -> tuple[str, set[str]]:
    """What the user picked, and number norms that pick removes."""
    found = _CHOICE.search(intent or "")
    if not found or not _answering_choice(intent):
        return "", set()
    doc, usr = found.group("doc"), found.group("user")
    latest = latest_user_line(intent)
    picked_doc = _norm_num(doc) in number_norms(latest) and _norm_num(usr) not in number_norms(latest)
    if picked_doc or re.search(r"как в документе|из документа|оставь документ", latest, re.IGNORECASE):
        return f"Пользователь выбрал {doc} из документа, не {usr}.", {_norm_num(usr)}
    if _norm_num(usr) in number_norms(latest) or re.search(r"моё|мое|как я", latest, re.IGNORECASE):
        return f"Пользователь выбрал {usr}, не {doc} из документа.", set()
    return "", set()


def _derived_table_math_norms(source: str) -> set[str]:
    """Column, prefix-group, and positive/negative deviation subtotals from Source tables."""
    from decimal import Decimal

    from case3.dashboard_source import (
        _CODE_HEADER,
        _YEAR_HEADER,
        _cell_decimal,
        _find_fact_plan_pair,
        _is_total_row,
        _label_column,
        _markdown_tables,
    )

    out: set[str] = set()

    def _add_dec(val: Decimal) -> None:
        for d in (val, abs(val)):
            if d == d.to_integral_value():
                out.add(str(int(d)))
            else:
                s = f"{d:.2f}".rstrip("0").rstrip(".")
                out.add(s)
                out.add(f"{d:.1f}".rstrip("0").rstrip("."))

    for _title, rows in _markdown_tables(source or ""):
        if len(rows) < 2:
            continue
        header, body = rows[0], rows[1:]
        data = [row for row in body if not _is_total_row(row)]
        if len(data) < 2:
            continue
        label_at = _label_column(data)
        width = max(len(row) for row in rows)
        prefixes: list[str] = []
        for row in data:
            lbl = row[label_at].strip() if label_at is not None and label_at < len(row) else ""
            if " — " in lbl:
                prefixes.append(lbl.split(" — ", 1)[0].strip())
            elif " - " in lbl:
                prefixes.append(lbl.split(" - ", 1)[0].strip())
            else:
                prefixes.append("")
        has_prefix_groups = len({p for p in prefixes if p}) >= 2
        for col in range(width):
            if label_at is not None and col == label_at:
                continue
            name = header[col].strip() if col < len(header) else ""
            if not name or _YEAR_HEADER.match(name) or _CODE_HEADER.search(name):
                continue
            col_vals: list[Decimal] = []
            by_pref: dict[str, list[Decimal]] = {}
            for pref, row in zip(prefixes, data):
                v = _cell_decimal(row[col].strip()) if col < len(row) else None
                if v is None:
                    continue
                col_vals.append(v)
                if has_prefix_groups and pref:
                    by_pref.setdefault(pref, []).append(v)
            if len(col_vals) >= 2:
                _add_dec(sum(col_vals, Decimal(0)))
                pos = [v for v in col_vals if v > 0]
                neg = [v for v in col_vals if v < 0]
                if len(pos) >= 2:
                    _add_dec(sum(pos, Decimal(0)))
                if len(neg) >= 2:
                    _add_dec(sum(neg, Decimal(0)))
                for pvals in by_pref.values():
                    if len(pvals) >= 2:
                        _add_dec(sum(pvals, Decimal(0)))
        pair = _find_fact_plan_pair(header)
        if pair is not None and has_prefix_groups:
            fcol, pcol = pair
            fp_pref: dict[str, tuple[Decimal, Decimal]] = {}
            for pref, row in zip(prefixes, data):
                if not pref:
                    continue
                fv = _cell_decimal(row[fcol].strip()) if fcol < len(row) else None
                pv = _cell_decimal(row[pcol].strip()) if pcol < len(row) else None
                if fv is not None and pv is not None:
                    sf, sp = fp_pref.get(pref, (Decimal(0), Decimal(0)))
                    fp_pref[pref] = (sf + fv, sp + pv)
            for sf, sp in fp_pref.values():
                if sp > 0:
                    _add_dec(sf * Decimal(100) / sp)
                    _add_dec(sf - sp)
    return out


def _table_row_share_and_delta_norms(source: str) -> set[str]:
    """Direct per-row shares of column totals and fact/plan deltas/ratios (membership-only, not math operands)."""
    from decimal import Decimal

    from case3.dashboard_source import (
        _CODE_HEADER,
        _YEAR_HEADER,
        _cell_decimal,
        _find_fact_plan_pair,
        _is_total_row,
        _label_column,
        _markdown_tables,
    )

    out: set[str] = set()

    def _add(val: Decimal) -> None:
        for d in (val, abs(val)):
            if d == d.to_integral_value():
                out.add(str(int(d)))
            else:
                out.add(f"{d:.2f}".rstrip("0").rstrip("."))
                out.add(f"{d:.1f}".rstrip("0").rstrip("."))

    for _title, rows in _markdown_tables(source or ""):
        if len(rows) < 2:
            continue
        header, body = rows[0], rows[1:]
        data = [row for row in body if not _is_total_row(row)]
        if len(data) < 2:
            continue
        label_at = _label_column(data)
        width = max(len(row) for row in rows)
        for col in range(width):
            if label_at is not None and col == label_at:
                continue
            name = header[col].strip() if col < len(header) else ""
            if not name or _YEAR_HEADER.match(name) or _CODE_HEADER.search(name):
                continue
            col_vals = [
                v
                for row in data
                if (v := (_cell_decimal(row[col].strip()) if col < len(row) else None)) is not None
            ]
            if len(col_vals) >= 2:
                col_sum = sum(col_vals, Decimal(0))
                abs_sum = sum((abs(v) for v in col_vals), Decimal(0))
                for v in col_vals:
                    if col_sum != 0:
                        _add(abs(v) * Decimal(100) / abs(col_sum))
                    if abs_sum != 0 and abs_sum != abs(col_sum):
                        _add(abs(v) * Decimal(100) / abs_sum)
        pair = _find_fact_plan_pair(header)
        if pair is not None:
            fcol, pcol = pair
            for row in data:
                fv = _cell_decimal(row[fcol].strip()) if fcol < len(row) else None
                pv = _cell_decimal(row[pcol].strip()) if pcol < len(row) else None
                if fv is not None and pv is not None:
                    _add(fv - pv)
                    if pv > 0:
                        _add(fv * Decimal(100) / pv)
    return out


_CHAT_CARDINAL = re.compile(
    r"(?:\bтоп[-\s]?(\d{1,2})\b|\b(?:все(?:го)?\s+)?(\d{1,2})\s+"
    r"(?:регион\w*|област\w*|район\w*|инспекц\w*|позиц\w*|строк\w*|категор\w*|город\w*|лидер\w*|аутсайдер\w*|отстающ\w*|плюс\w*|минус\w*))",
    re.IGNORECASE,
)
_TABLE_RANK_CELL = re.compile(r"^\s*\|\s*(\d{1,2})\s*\|")
_TABLE_SEP_LINE = re.compile(r"^\s*\|[\s\-:|]+\|\s*$")


def _filter_verifiable_stray(
    text: str,
    stray: list[str],
    allowed: set[str],
    source: str,
    *,
    message_ok: set[str] | None = None,
    user_question: str = "",
) -> list[str]:
    if not stray:
        return []
    from case3.fact_ground import _is_small_cardinal_in_clause, _row_mentions, _verifies_math, table_grid

    derived = _derived_table_math_norms(source)
    row_calc = _table_row_share_and_delta_norms(source)
    grid = table_grid(source) if "|" in (source or "") else None
    full_pool = allowed | derived
    doc_row_pool: set[str] = set()
    if grid is not None and grid.rows:
        for _s, _e, rstem in _row_mentions(f"{user_question}\n{text}", grid):
            doc_row_pool |= grid.rows.get(rstem, set())
    verified: set[str] = set()
    lines = (text or "").splitlines()
    active_header = ""
    for idx, line in enumerate(lines):
        stripped = line.strip()
        is_pipe = stripped.startswith("|") and stripped.endswith("|")
        if is_pipe and idx + 1 < len(lines) and _TABLE_SEP_LINE.match(lines[idx + 1]):
            active_header = stripped
        elif not is_pipe:
            active_header = ""

        row_pool: set[str] = set(doc_row_pool)
        if grid is not None and grid.rows:
            for _s, _e, rstem in _row_mentions(line, grid):
                row_pool |= grid.rows.get(rstem, set())
        extra = (message_ok or set()) | derived | row_pool
        clause_ctx = f"{active_header}\n{line}" if (is_pipe and active_header) else line
        if is_pipe and not _TABLE_SEP_LINE.match(stripped):
            rank_match = _TABLE_RANK_CELL.match(stripped)
            if rank_match and 1 <= int(rank_match.group(1)) <= 50:
                verified.add(str(int(rank_match.group(1))))
        for m in _CHAT_CARDINAL.finditer(line):
            hit = m.group(1) or m.group(2)
            if hit and 1 <= int(hit) <= 50:
                verified.add(str(int(hit)))
        for token in stray:
            norm = _norm_num(token)
            if not norm or norm in verified:
                continue
            if norm in full_pool:
                verified.add(norm)
            elif (is_pipe or "%" in line or "дол" in line.lower()) and norm in row_calc:
                verified.add(norm)
            elif _is_small_cardinal_in_clause(line, norm):
                verified.add(norm)
            elif extra and _verifies_math(clause_ctx, norm, full_pool | row_pool, extra):
                verified.add(norm)
            elif extra and _verifies_math(text or "", norm, full_pool | row_pool, extra):
                verified.add(norm)
    return [tok for tok in stray if _norm_num(tok) not in verified]


_PRIOR_SCENARIO_CUE = re.compile(
    r"(?:сценари|резерв|добав|учт|учест|прошл|предыдущ|ранее|писал|называл|"
    r"пересчит|скорректир|новый\s+факт|новое\s+выполнен|если|"
    r"этом\w*\s+(?:график|расч[её]т|вариант)|этому\s+сценари|по\s+нему)",
    re.IGNORECASE,
)
_PRIOR_SCENARIO_GENERIC_STEMS = frozenset(
    {
        "факт",
        "план",
        "поступлен",
        "поступлени",
        "выполнен",
        "выполнени",
        "отклонен",
        "отклонени",
        "темп",
        "рост",
        "выручк",
        "прибыль",
        "прибыл",
        "доход",
        "расход",
        "показатель",
        "показател",
        "значен",
        "значени",
        "данн",
        "процент",
        "дол",
        "рубль",
        "рубл",
        "тыс",
        "тысяч",
        "млн",
        "млрд",
        "итог",
        "общ",
        "инспекц",
        "инспекци",
        "имнс",
        "город",
        "область",
    }
)


def _user_stated_line(intent: str | None) -> str:
    text = intent or ""
    mark = "Числа из реплик пользователя"
    at = text.find(mark)
    if at < 0:
        return ""
    rest = text[at + len(mark) :]
    return rest.split("\n", 1)[1].split("\n", 1)[0] if "\n" in rest else ""


def _asks_about_prior_scenario(message: str | None, intent: str | None) -> bool:
    """True when the current message references an earlier scenario or prior user numbers."""
    msg = (message or "").strip()
    if not msg:
        return False
    if _PRIOR_SCENARIO_CUE.search(msg):
        return True
    stated_line = _user_stated_line(intent)
    if not stated_line.strip():
        return False
    msg_nums = number_norms(msg)
    if msg_nums & number_norms(stated_line):
        return True
    msg_stems = set(_content_words(msg))
    ignore = _STOP_STEMS | _PRIOR_SCENARIO_GENERIC_STEMS
    stated_stems = {
        stem for stem in _content_words(stated_line) if stem not in ignore
    }
    return bool(msg_stems & stated_stems)


def _allowed_norms(
    source: str,
    intent: str,
    drop: set[str],
    *,
    include_user_stated: bool = True,
) -> set[str]:
    have = number_norms(source) | number_norms(_request_blob(intent))
    if include_user_stated:
        have = have | user_stated_norms(intent)
    # Prose often phrases negative deviations as positive magnitudes («отставание на 1 527»).
    have = have | {n[1:] for n in have if n.startswith("-")}
    return have - drop


def _visual_memory_context(intent: str, extra_context: str = "") -> str:
    """Preserve prior chat thread + scenario analysis for inline chart/diagram prompts."""
    raw = intent or ""
    earliest = len(raw)
    for marker in _MEMORY_AT:
        if marker == "\n\nТребования UI:":
            continue
        pos = raw.find(marker)
        if pos != -1 and pos < earliest:
            earliest = pos
    parts: list[str] = []
    if earliest < len(raw):
        tail = raw[earliest:].strip()
        ui_pos = tail.find("\n\nТребования UI:")
        if ui_pos != -1:
            tail = tail[:ui_pos].strip()
        if tail:
            parts.append(tail[:3500])
    extra = (extra_context or "").strip()
    if extra:
        parts.append("Анализ и расчёты текущего ответа:\n" + extra[:2500])
    return "\n\n".join(parts)


def chart_plot_blank(html: str | None) -> bool:
    """True when Chart.js has no non-zero point. Axes alone are an empty picture."""
    arrays = re.findall(r"data\s*:\s*\[([^\]]*)\]", html or "", flags=re.I)
    if not arrays:
        return True
    for body in arrays:
        for token in re.findall(r"-?\d+(?:[.,]\d+)?", body):
            try:
                value = abs(float(token.replace(",", ".")))
            except ValueError:
                continue
            if value > 0:
                return False
    return True


def generate_chat_charts(
    source: str,
    intent: str,
    *,
    max_charts: int,
    palette_id: str = "atelier",
    figs_dir,
    charts_dir,
    client: LLMClient | None = None,
    extra_context: str = "",
    previous_chart: dict | None = None,
) -> tuple[list[dict], dict[str, dict]]:
    """Build and render 1..max_charts grounded Chart.js PNGs for an inline chat turn."""
    from pathlib import Path

    from case3.chart_coerce import (
        coerce_chart_types,
        ensure_all_charts_match_types,
        polish_charts,
    )
    from case3.chart_html import CHART_TYPES
    from case3.chart_style import (
        hue_from_text,
        hue_prompt_line,
        intent_palette_lines,
        normalize_palette_id,
        paint_hue_on_html,
    )
    from case3.charts import render_charts_batch
    from case3.fact_ground import ground_generated
    from case3.generate import preferred_types_from_intent
    from case3.parse_output import _load_media_payload, _parse_charts_list, _pick_fences

    cap = max(1, min(int(max_charts or 1), 4))
    palette = normalize_palette_id(palette_id)
    types_list = ", ".join(sorted(CHART_TYPES))
    palette_hint = "\n".join(intent_palette_lines(palette))
    system = (
        "Ты визуализатор аналитики Liber. Построй по запросу 1-"
        f"{cap} Chart.js график(а) строго по числам из Source и согласованного сценария.\n"
        f"Допустимые type: {types_list}.\n"
        f"{palette_hint}\n"
        "Холст 1100×560. Не задавай маленький canvas и не ставь width в style. "
        "Подписи категорий целиком, шрифт осей не меньше 16. График заполняет холст.\n"
        "Пиши <canvas id='c' width='1100' height='560'></canvas>"
        "<script>new Chart(document.getElementById('c'), {type: 'bar', data: {labels: ['А', 'Б'], datasets: [{label: 'Показатель', data: [10, 20]}]}, options: {responsive: false}});</script> "
        "(подставь реальные подписи, числа и тип из Source; никогда не пиши многоточие `...` в JS, без CSS и комментариев).\n"
        "Верни ТОЛЬКО JSON-объект в блоке ```json вида:\n"
        '{"charts": [{"id": "cht_01", "type": "bar", "caption": "...", "html": "<canvas id=\'c\'></canvas><script>...</script>"}]}'
    )
    message = latest_user_line(intent) or intent or "Построй график по данным."
    color_line = hue_prompt_line(message)
    if color_line:
        system += "\n" + color_line
    prior_scenario = _asks_about_prior_scenario(message, intent)
    mem_ctx = _visual_memory_context(intent, extra_context)
    clipped_src = _clip_source(source, focus=f"{message}\n{mem_ctx}".strip())
    prompt_parts = [f"ЗАПРОС:\n{message}"]
    if isinstance(previous_chart, dict) and (previous_chart.get("html") or "").strip():
        prev_type = str(previous_chart.get("type") or "")
        prev_cap = str(previous_chart.get("caption") or "")
        prev_html = str(previous_chart.get("html") or "")[:3000]
        type_changed = bool(
            re.search(
                r"(?:столбч|лине[йя]|кругов|кольц|пончик|радар|точеч|площад|горизонт|"
                r"\bbar\b|\bline\b|\bpie\b|\bdoughnut\b|\bradar\b|\bscatter\b|\bhorizontal_bar\b)",
                message or "",
                re.IGNORECASE,
            )
        )
        preserve_note = (
            f" СОХРАНИ type={prev_type} (пользователь не просил менять тип диаграммы)."
            if prev_type and not type_changed
            else ""
        )
        prompt_parts.append(
            f"ТЕКУЩИЙ ГРАФИК ДЛЯ ДОРАБОТКИ (type={prev_type}, caption={prev_cap}):{preserve_note}\n{prev_html}"
        )
    if mem_ctx:
        prompt_parts.append(mem_ctx)
    prompt_parts.append(f"SOURCE:\n{clipped_src}")
    if not previous_chart and not prior_scenario:
        prompt_parts.append(
            f"ФОКУС ГРАФИКА: строй график строго по запросу «{message}» на исходных данных из SOURCE, "
            "не подмешивая условные расчёты или добавки из прошлых ходов."
        )
    user_prompt = "\n\n".join(prompt_parts)

    llm = client or _client(_CHAT_ANSWER_TOKENS, 120.0)
    ground_intent = intent if (previous_chart or prior_scenario) else message
    grounded: list[dict] = []
    retry_note = ""
    for attempt in range(2):
        prompt = user_prompt if not retry_note else f"{user_prompt}\n\n{retry_note}"
        try:
            raw = llm.complete(system=system, user_text=prompt, reasoning="off")
        except (LLMError, LLMConfigError, OSError, ValueError) as exc:
            log.warning("chat chart generation failed (attempt %d): %s", attempt + 1, exc)
            return [], {}

        _tex, json_body = _pick_fences(raw or "")
        data = _load_media_payload(raw or "", json_body)
        parsed = _parse_charts_list((data or {}).get("charts"), max_charts=cap)
        if not parsed:
            retry_note = (
                "ПОВТОР: прошлый ответ не содержал корректного JSON вида "
                '```json {"charts": [{"id": "cht_01", "type": "bar", "caption": "...", '
                '"html": "<canvas id=\'c\'></canvas><script>new Chart(...)</script>"}]} ```. '
                "Верни только такой JSON-блок без лишнего текста."
            )
            continue

        _tex_out, grounded, _figs, _diags, _dropped = ground_generated(
            "",
            parsed,
            [],
            [],
            source=source,
            intent=ground_intent,
        )
        if grounded:
            break
        retry_note = (
            "ПОВТОР: прошлый график был отклонён, потому что содержал числа не из SOURCE. "
            "Используй ТОЛЬКО точные числа, которые явно записаны в SOURCE."
        )
    if not grounded:
        return [], {}

    preferred = preferred_types_from_intent(intent or "")
    if preferred:
        grounded = coerce_chart_types(grounded, preferred)
    else:
        grounded = ensure_all_charts_match_types(grounded)
    grounded = polish_charts(grounded, palette_id=palette)
    from case3.chart_harden import full_chat_canvas

    named_hue = hue_from_text(message)
    for item in grounded:
        item["html"] = full_chat_canvas(
            str(item.get("html") or ""),
            chart_type=str(item.get("type") or ""),
        )
        if named_hue:
            item["html"] = paint_hue_on_html(str(item.get("html") or ""), named_hue)
            item["hue"] = named_hue
    grounded = [item for item in grounded if not chart_plot_blank(str(item.get("html") or ""))]
    if not grounded:
        return [], {}

    out_figs = Path(figs_dir)
    out_charts = Path(charts_dir)
    out_figs.mkdir(parents=True, exist_ok=True)
    out_charts.mkdir(parents=True, exist_ok=True)
    batch_items = [
        (item["id"], item, out_figs / f"{item['id']}.png", out_charts)
        for item in grounded
        if isinstance(item, dict) and item.get("id")
    ]
    status = render_charts_batch(batch_items) if batch_items else {}
    return grounded, status


def generate_chat_diagram(
    source: str,
    intent: str,
    *,
    palette_id: str = "atelier",
    figs_dir,
    client: LLMClient | None = None,
    extra_context: str = "",
    previous_diagram: dict | None = None,
) -> tuple[list[dict], dict[str, dict]]:
    """One Mermaid schema from the chat text. No report file."""
    from pathlib import Path

    from case3.chart_style import normalize_palette_id
    from case3.diagram_generate import complete_diagrams
    from case3.slides_media import ensure_diagram_pngs

    llm = client or _client(2048, 60.0)
    message = latest_user_line(intent) or intent
    mem_ctx = _visual_memory_context(intent, extra_context)
    diag_parts = [message]
    if isinstance(previous_diagram, dict):
        prev_code = str(previous_diagram.get("mermaid") or previous_diagram.get("code") or "").strip()
        if prev_code:
            diag_parts.append(f"ТЕКУЩАЯ СХЕМА ДЛЯ ДОРАБОТКИ:\n{prev_code[:3000]}")
    if mem_ctx:
        diag_parts.append(mem_ctx)
    diag_intent = "\n\n".join(diag_parts)
    try:
        diagrams = complete_diagrams(
            intent=diag_intent,
            source_text=_clip_source(source, focus=diag_intent),
            max_diagrams=1,
            client=llm,
            palette=normalize_palette_id(palette_id),
        )
    except Exception as exc:  # noqa: BLE001 — a picture must not drop the answer
        log.warning("chat diagram generation failed: %s", exc)
        return [], {}
    if not diagrams:
        return [], {}
    dest = Path(figs_dir)
    specs = {
        str(item.get("id") or "dia_01"): item
        for item in diagrams
        if isinstance(item, dict) and (item.get("mermaid") or item.get("code"))
    }
    for spec in specs.values():
        if not spec.get("mermaid") and spec.get("code"):
            spec["mermaid"] = spec["code"]
    rendered = ensure_diagram_pngs(specs, dest_dir=dest, palette=normalize_palette_id(palette_id))
    status = {
        did: {"ok": True, "path": str(path), "kind": "diagram"}
        for did, path in rendered.items()
    }
    kept = [item for item in diagrams if str(item.get("id") or "") in status]
    return kept, status


def dashboard_landing(user_text: str) -> bool:
    """The automatic line sent when a dashboard screen is closed."""
    return "Длинный разбор в чат не пиши" in (user_text or "")


def _first_sentences(text: str, count: int) -> str:
    parts = [part.strip() for part in re.split(r"(?<=[.!?…])\s+", (text or "").strip()) if part.strip()]
    if len(parts) <= count:
        return (text or "").strip()
    return " ".join(parts[:count]).strip()


def _ask_model(
    client: LLMClient,
    system: str,
    user_text: str,
    *,
    max_tokens: int = _CHAT_ANSWER_TOKENS,
    on_delta: Callable[[str], None] | None = None,
) -> str:
    try:
        return _accepted(
            _speak(
                client,
                system=system,
                user_text=user_text,
                max_tokens=max_tokens,
                on_delta=on_delta,
            )
        )
    except (LLMError, LLMConfigError, OSError, ValueError) as exc:
        log.error("chat answer failed: %s", exc)
        return ""


_ASK_STOP_WORDS = (
    "отчёт",
    "отчет",
    "раздел",
    "текст",
    "документ",
    "чат",
    "файл",
    "вопрос",
    "сообщение",
    "ответ",
    "этот",
    "эта",
)
_SECTION_CAP = 3500
_OUTLINE_CAP = 24


def _content_words(text: str) -> list[str]:
    from case3.chat_memory import _stem

    stems: list[str] = []
    for word in re.findall(r"[0-9A-Za-zА-Яа-яЁё]+", text or ""):
        stem = _stem(word)
        if len(stem) >= 4:
            stems.append(stem)
    return stems


def _same_topic(left: str, right: str) -> bool:
    """«введении» and «введение» keep one letter of difference after stemming."""
    if left == right:
        return True
    short, long = (left, right) if len(left) <= len(right) else (right, left)
    return len(short) >= 5 and long.startswith(short)


def _heading_score(title: str, needles: list[str]) -> float:
    title_stems = _content_words(title)
    if not title_stems or not needles:
        return 0.0
    hits = sum(
        1 for stem in title_stems if any(_same_topic(stem, needle) for needle in needles)
    )
    if hits == 0:
        return 0.0
    return hits / len(title_stems)


def _named_heading(question: str, titles: list[str]) -> tuple[str, str]:
    """(heading title, name the user asked). Title is empty when nothing matches."""
    from case3.chat_act import section_target
    from case3.chat_memory import _stem

    asked = section_target(latest_user_line(question))
    if asked:
        needles = _content_words(asked)
        best = ""
        best_score = 0.0
        for title in titles:
            score = _heading_score(title, needles)
            if score > best_score:
                best_score = score
                best = title
        return best, asked
    stop = {_stem(word) for word in _ASK_STOP_WORDS}
    needles = [stem for stem in _content_words(latest_user_line(question)) if stem not in stop]
    scored = [(_heading_score(title, needles), title) for title in titles]
    scored = [item for item in scored if item[0] > 0]
    scored.sort(key=lambda item: item[0], reverse=True)
    if not scored or (len(scored) > 1 and scored[0][0] == scored[1][0]):
        return "", ""
    return scored[0][1], ""


def _table_prose(block: dict) -> str:
    lines: list[str] = []
    caption = str(block.get("caption") or "").strip()
    if caption:
        lines.append("Таблица: " + caption)
    headers = [str(cell).strip() for cell in (block.get("headers") or [])]
    if headers:
        lines.append(" | ".join(headers))
    rows = [row for row in (block.get("rows") or []) if isinstance(row, list)]
    for row in rows:
        lines.append(" | ".join(str(cell).strip() for cell in row))
    return "\n".join(lines)


def _section_prose(blocks: list[dict], title: str) -> str:
    from case3.chat_memory import _clip_prose

    start = -1
    level = 1
    for index, block in enumerate(blocks):
        if block.get("type") == "heading" and str(block.get("text") or "").strip() == title:
            start = index
            level = int(block.get("level") or 1)
            break
    if start < 0:
        return ""
    parts: list[str] = []
    for block in blocks[start + 1 :]:
        kind = block.get("type")
        if kind == "heading" and int(block.get("level") or 1) <= level:
            break
        if kind == "heading":
            text = str(block.get("text") or "").strip()
        elif kind == "paragraph":
            text = str(block.get("text") or "").strip()
        elif kind == "list":
            rows = [
                "- " + str((item or {}).get("text") or "").strip()
                for item in (block.get("items") or [])
                if str((item or {}).get("text") or "").strip()
            ]
            text = "\n".join(rows)
        elif kind == "table":
            text = _table_prose(block)
        elif kind == "figure":
            caption = str(block.get("caption") or "").strip()
            text = "Рисунок: " + caption if caption else ""
        else:
            text = ""
        if text:
            parts.append(text)
    return _clip_prose("\n\n".join(parts), _SECTION_CAP)


def report_context(tex: str, question: str) -> str:
    """Outline plus the named section. Empty when this chat has no report.

    The block is labeled not-Source. Numbers in it stay illegal unless Source
    or the user's own message already has them.
    """
    from case3.tex_preview import tex_to_preview_blocks

    data = tex_to_preview_blocks(tex or "")
    blocks = [block for block in (data.get("blocks") or []) if isinstance(block, dict)]
    headings = [
        (str(block.get("text") or "").strip(), int(block.get("level") or 1))
        for block in blocks
        if block.get("type") == "heading" and str(block.get("text") or "").strip()
    ]
    if not headings:
        return ""
    lines = [
        "Открытый отчёт (не Source).",
        "Числа и факты бери только из текста документов.",
        "Оглавление:",
    ]
    title = str(data.get("title") or "").strip()
    if title:
        lines.append("Название: " + title)
    for text, level in headings[:_OUTLINE_CAP]:
        pad = "  " if level > 1 else ""
        lines.append(f"{pad}- {text}")
    if len(headings) > _OUTLINE_CAP:
        lines.append("- …")
    found, asked = _named_heading(question, [text for text, _level in headings])
    if found:
        body = _section_prose(blocks, found)
        lines.append(f"Раздел «{found}»:")
        if body:
            lines.append(body)
    elif asked:
        lines.append(f"Раздела «{asked}» в отчёте нет.")
    return "\n".join(lines)


def chat_report_block(root, prior_run_id: str, user_text: str) -> str:
    """Report block for the chat that continues prior_run_id."""
    from pathlib import Path

    from case3.chat_memory import report_tex

    return report_context(report_tex(Path(root), prior_run_id or ""), user_text or "")


def limit_note(intent: str) -> str:
    """Tell the talk model that this line did not edit the file."""
    from case3.chat_act import _EDIT, _PROSE, _unsupported_shape, resolve_act

    line = latest_user_line(intent)
    if not line:
        return ""
    act = resolve_act(
        line,
        has_deck=True,
        has_report=True,
        has_diagram=True,
    )
    if act.kind != "talk":
        return ""
    if not (_EDIT.search(line) or _PROSE.search(line) or _unsupported_shape(line)):
        return ""
    return (
        "Файл не изменился.\n"
        "Ответь обычным предложением, без заголовка капсом: чего не умеешь, "
        "что рядом умеешь, и одну фразу, которую можно скопировать."
    )


def try_chat_answer(
    source: str,
    intent: str,
    *,
    client: LLMClient | None = None,
    on_delta: Callable[[str], None] | None = None,
    on_replace: Callable[[str], None] | None = None,
    report: str = "",
) -> str:
    """Full chat answer. No TeX.

    A number the user wrote is kept. A number neither they nor the document
    stated is not shown. A clash on the same word becomes one question.
    """
    note, drop = choice_instruction(intent)
    if not _answering_choice(intent):
        clash = fact_conflict(latest_user_line(intent), source)
        if clash:
            question = conflict_question(*clash)
            if on_delta:
                on_delta(question)
            return question

    system = load_prompt("chat_answer").strip()
    user = _user_block(source, intent)
    if note:
        user += "\n\n" + note
    extra = (report or "").strip()
    if extra:
        user += "\n\n" + extra
    note_limit = limit_note(intent)
    if note_limit:
        user += "\n\n" + note_limit
    landing = dashboard_landing(intent)
    answer_tokens = 320 if landing else _CHAT_ANSWER_TOKENS
    if landing:
        user += (
            "\n\nВ чат — не больше четырёх предложений: что на экране и какой вопрос уместен. "
            "Без таблицы и без обзора."
        )
    said = latest_user_line(intent)
    from case3.turn_route import wants_chat_chart, wants_chat_diagram

    is_visual_turn = wants_chat_chart(said) or wants_chat_diagram(said)
    prior_scenario = _asks_about_prior_scenario(said, intent)
    has_memory = any(
        marker in user
        for marker in (
            "\n\nРазговор этого чата",
            "\n\nЧисла из реплик пользователя",
            "\n\nКарточка этого чата",
            "\n\nПредыдущий ход",
        )
    )
    if said and has_memory and not landing:
        if is_visual_turn and not prior_scenario:
            user += (
                f"\n\nТЕКУЩИЙ ЗАПРОС (ответь строго на него): {said}\n"
                "Разбери только исходные числа из блока «ТЕКСТ» для запрошенного разреза. "
                "Не повторяй условные добавки и расчёты из прошлых ходов, если о них не спрашивают в этом сообщении."
            )
        else:
            user += f"\n\nТЕКУЩИЙ ЗАПРОС (ответь именно на него): {said}"
    llm = client or _client(answer_tokens, 60.0 if landing else 180.0)
    allowed = _allowed_norms(
        source,
        intent,
        drop,
        include_user_stated=not (is_visual_turn and not prior_scenario),
    )
    msg_ok = number_norms(said)
    streamed_chunks: list[str] = []

    def _emit_chunk(piece: str) -> None:
        if not piece:
            return
        streamed_chunks.append(piece)
        if on_delta:
            on_delta(piece)

    text = _ask_model(
        llm,
        system,
        user,
        max_tokens=answer_tokens,
        on_delta=_emit_chunk if (on_delta is not None and on_replace is not None) else None,
    )
    streamed_raw = "".join(streamed_chunks).strip()
    stray = (
        _filter_verifiable_stray(
            text,
            stray_numbers(text, allowed),
            allowed,
            source,
            message_ok=msg_ok,
            user_question=said,
        )
        if text
        else []
    )
    from case3.fact_ground import wrong_row_tokens

    wrong = wrong_row_tokens(text, source, said) if text and not stray else []
    shown = bool(streamed_raw)
    if stray and shown:
        kept = _without_stray(text or streamed_raw, stray)
        if len(re.findall(r"[А-Яа-яЁё]", kept)) >= 40:
            text = kept
        else:
            text = streamed_raw
        stray = []
    if stray:
        first_text, first_stray = text, stray
        if is_visual_turn and not prior_scenario:
            retry = (
                user
                + "\n\nПовтор: в текущем запросе просят «"
                + said
                + "». Не пиши условные или отсутствующие числа ("
                + ", ".join(stray)
                + "); разбери исходные показатели из ТЕКСТ для запрошенного разреза."
            )
        else:
            retry = (
                user
                + "\n\nПовтор: не пиши числа, которых нет в сообщении и в тексте: "
                + ", ".join(stray)
                + ". Если цифры не хватает, так и напиши, без новой цифры."
            )
        retried = _ask_model(llm, system, retry, max_tokens=answer_tokens)
        if retried:
            text = retried
            stray = _filter_verifiable_stray(
                text,
                stray_numbers(text, allowed),
                allowed,
                source,
                message_ok=msg_ok,
                user_question=said,
            )
        else:
            text = first_text
            stray = first_stray
    if stray:
        kept = _without_stray(text, stray)
        if len(re.findall(r"[А-Яа-яЁё]", kept)) >= 12:
            spoken = kept
        elif is_visual_turn and not prior_scenario:
            spoken = "Построил график по исходным данным документа для запрошенного разреза."
        else:
            spoken = invention_question(stray)
    elif wrong and shown:
        text = streamed_raw
        wrong = []
        spoken = text
    elif wrong:
        first_text, first_wrong = text, wrong
        retry = (
            user
            + "\n\nПовтор: это число стоит в другой строке таблицы. "
            "Назови строку и колонку, как они записаны. Не переноси чужую ячейку: "
            + ", ".join(wrong)
            + "."
        )
        retried = _ask_model(llm, system, retry, max_tokens=answer_tokens)
        if retried:
            text = retried
            wrong = wrong_row_tokens(text, source, said)
        else:
            text = _without_stray(first_text, first_wrong)
            wrong = wrong_row_tokens(text, source, said) if text else first_wrong
        if wrong:
            spoken = (
                "Число из другой строки таблицы сюда не переношу. "
                "Назови область и колонку ещё раз."
            )
        else:
            spoken = text or chat_fallback()
    else:
        spoken = text or chat_fallback()
    spoken = _hide_memory_marks(spoken)
    if landing:
        spoken = _first_sentences(spoken, 4)
    if streamed_chunks:
        if spoken != streamed_raw and on_replace:
            on_replace(spoken)
    elif on_delta:
        on_delta(spoken)
    return spoken


_ABBR_DOT = re.compile(
    r"\b(г|тыс|млн|млрд|руб|коп|обл|р-н|стр|ст|ул|д|кв|им|п|см|др|пр|т)\.",
    re.IGNORECASE,
)


def _without_stray(text: str, stray: list[str]) -> str:
    """Drop sentences or table rows with foreign numbers without leaving orphan header-only tables."""
    norms = {_norm_num(token) for token in stray}
    if not text or not norms:
        return text or ""
    raw_lines = text.split("\n")
    kept_lines: list[str] = []
    idx = 0
    while idx < len(raw_lines):
        line = raw_lines[idx]
        stripped = line.strip()
        if (
            stripped.startswith("|")
            and stripped.endswith("|")
            and idx + 1 < len(raw_lines)
            and re.match(r"^\s*\|[\s\-:|]+\|\s*$", raw_lines[idx + 1])
        ):
            header_line = line
            sep_line = raw_lines[idx + 1]
            idx += 2
            kept_body: list[str] = []
            while idx < len(raw_lines):
                body_line = raw_lines[idx]
                bs = body_line.strip()
                if not (bs.startswith("|") and bs.endswith("|")):
                    break
                idx += 1
                row_nums = {_norm_num(token) for token in _NUM.findall(body_line)}
                if row_nums & norms:
                    continue
                kept_body.append(body_line)
            if kept_body:
                kept_lines.append(header_line)
                kept_lines.append(sep_line)
                kept_lines.extend(kept_body)
            continue
        idx += 1
        if stripped.startswith("|") and stripped.endswith("|"):
            # Fallback for headerless pipe lines: drop matching lines.
            if not re.match(r"^\|[\s\-:|]+\|$", stripped):
                row_nums = {_norm_num(token) for token in _NUM.findall(line)}
                if row_nums & norms:
                    continue
            kept_lines.append(line)
            continue
        protected = _ABBR_DOT.sub("\\1\x00", line)
        bits = re.split(r"([.!?]+(?:\s+|$))", protected)
        kept: list[str] = []
        index = 0
        while index < len(bits):
            chunk = bits[index].replace("\x00", ".")
            delim = bits[index + 1] if index + 1 < len(bits) else ""
            index += 2 if delim else 1
            nums = {_norm_num(token) for token in _NUM.findall(chunk)}
            if nums and nums <= norms:
                continue
            if nums & norms:
                chunk = _NUM.sub(
                    lambda match: "" if _norm_num(match.group(0)) in norms else match.group(0),
                    chunk,
                )
                chunk = re.sub(
                    r"\*{2,}\s*[+\-−]?\s*(?:тыс\.?|млн\.?|млрд\.?)?\s*(?:руб\.?|%)?\s*\*{2,}",
                    "",
                    chunk,
                )
            chunk = re.sub(r"[ \t]{2,}", " ", chunk).strip(" ,;")
            if not chunk or re.fullmatch(r"[\*+\-−\s]+", chunk):
                continue
            kept.append(chunk)
            if delim:
                kept.append(delim if delim.startswith((".", "!", "?")) else " ")
        if kept:
            kept_lines.append("".join(kept).strip())
    return "\n".join(kept_lines).strip()


_CHART_JSON_FENCE = re.compile(
    r"```(?:json|javascript|js|html)?\s*[\{\[][\s\S]*?(?:\"datasets\"|\"labels\"|\"charts\"|\"mermaid\"|new\s+Chart)[\s\S]*?```",
    re.IGNORECASE,
)
_BARE_CHART_JSON = re.compile(
    r'(?:^|\n)\s*\{\s*"(?:charts|diagrams)"\s*:\s*\[[\s\S]*?\]\s*\}\s*(?=\n|$)',
    re.IGNORECASE,
)


def _hide_memory_marks(text: str) -> str:
    """The model must not read the memory labels aloud or dump raw chart JSON fences."""
    cleaned = _CHART_JSON_FENCE.sub("", text or "")
    cleaned = _BARE_CHART_JSON.sub("\n", cleaned)
    kept: list[str] = []
    for line in cleaned.split("\n"):
        bare = line.strip().lstrip("#").strip()
        if bare.startswith(
            (
                "Числа из реплик пользователя",
                "Разговор этого чата",
                "Карточка этого чата",
            )
        ):
            continue
        kept.append(
            line.replace("Числа из реплик пользователя", "твои числа")
            .replace("Разговор этого чата", "этот разговор")
            .replace("Карточка этого чата", "этот разговор")
        )
    out = "\n".join(kept).strip()
    if not out and (text or "").strip():
        return "Построил визуализацию по данным."
    return out


def _norm_num(token: str) -> str:
    compact = re.sub(r"[ \u00a0\u202f]+", "", token or "")
    compact = compact.replace("−", "-")
    compact = compact.replace("{,}", ",").replace("{.}", ".")
    compact = compact.replace("\\,", "")
    compact = compact.replace("\\%", "")
    compact = compact.replace(",", ".").replace("%", "")
    compact = re.sub(r"\.0+$", "", compact)
    return "0" if compact == "-0" else compact


def _numbers_grounded(draft: str, allowed: str, source: str = "") -> bool:
    from case3.fact_ground import _is_small_cardinal_in_clause, table_grid

    have = {_norm_num(token) for token in _fact_tokens(allowed)}
    if source:
        grid = table_grid(source)
        have |= grid.all_row_norms | grid.aggregates | _derived_table_math_norms(source)
    have |= {n[1:] for n in have if n.startswith("-")}
    for token in _fact_tokens(draft):
        norm = _norm_num(token)
        if norm in have or _is_small_cardinal_in_clause(draft, norm):
            continue
        return False
    return True


def draft_section(
    *,
    section: str,
    current: str,
    source: str,
    brief: str,
    user_text: str = "",
    client: LLMClient | None = None,
) -> str:
    """One replacement paragraph. Empty when the draft adds a number or fails.

    A number the user wrote in this message is allowed. A number from neither
    the section, the source, nor that message is not.
    """
    system = load_prompt("chat_section").strip()
    task = _BRIEF_LINE.get(brief, _BRIEF_LINE["prettier"])
    said = (user_text or "").strip()[:500]
    user = (
        f"Раздел: {(section or 'Раздел').strip()[:80]}\n"
        f"Задача: {task}\n\n"
        f"СООБЩЕНИЕ ПОЛЬЗОВАТЕЛЯ:\n{said or '(нет)'}\n\n"
        f"ТЕКСТ РАЗДЕЛА:\n{(current or '').strip()[:4000]}\n\n"
        f"SOURCE:\n{_clip_source(source, focus=said)}"
    )
    text = ""
    try:
        llm = client or _client(500, 40.0)
        text = _accepted(
            _speak(llm, system=system, user_text=user, max_tokens=500, on_delta=None)
        )
    except (LLMError, LLMConfigError, OSError, ValueError) as exc:
        log.warning("section draft failed: %s", exc)
        text = ""
    allowed = f"{current}\n{source}\n{said}"
    if not text or not _numbers_grounded(text, allowed, source=source):
        return ""
    return " ".join(text.split())
