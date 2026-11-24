"""Transcript of one Liber chat. It explains the next line. It is not Source."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

# Eight recent turns stay as paragraphs. Older turns of the 48-hop chain
# are one digit-free line, and a matching question lifts one of them.
# Tail turns stay near 800 characters; the two newest stay longer.
_WINDOW = 8
_WINDOW_CAPS = (2000, 1600, 1200, 800)
_MAX_HOPS = 48
_TAIL = _WINDOW_CAPS[0]
_PREV = _WINDOW_CAPS[1]
_LINE = _WINDOW_CAPS[-1]
_OLDER_LINE = 160
_OLDER_CAP = 6000
_NOTE = 300
_NOTE_SHORT = 160


def _clip(value: object, limit: int) -> str:
    text = " ".join(str(value or "").split())
    if len(text) <= limit:
        return text
    if limit <= 1:
        return ""
    return text[: limit - 1].rstrip() + "…"


def _clip_prose(value: object, limit: int) -> str:
    """Keep paragraphs. Cut near a break when the tail is long."""
    text = str(value or "").replace("\r\n", "\n").replace("\r", "\n").strip()
    text = re.sub(r"[ \t]+\n", "\n", text)
    text = re.sub(r"[ \t]{2,}", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    if len(text) <= limit:
        return text
    if limit <= 1:
        return ""
    cut = text[: limit - 1]
    floor = int(limit * 0.6)
    for sep in ("\n\n", "\n", ". "):
        spot = cut.rfind(sep)
        if spot >= floor:
            cut = cut[:spot].rstrip()
            break
    else:
        cut = cut.rstrip()
    return cut + "…"


def _turn_budget(offset: int) -> tuple[int, int, int]:
    """Prompt, answer, edit-note. Offset 0 is the latest turn."""
    slot = min(max(offset, 0), len(_WINDOW_CAPS) - 1)
    cap = _WINDOW_CAPS[slot]
    note = _NOTE if slot <= 1 else _NOTE_SHORT
    return cap, cap, note


def _older_line(turn: dict[str, Any], index: int) -> str:
    """One index line. Digits are stripped: this line is not a fact."""
    prefix = f"Ход {index}. "
    room = _OLDER_LINE - len(prefix)
    if room < 20:
        return ""
    half = max(20, (room - 3) // 2)
    prompt = _clip(_strip_digits(turn.get("chat_prompt")), half)
    summary = _clip(
        _strip_digits(turn.get("chat_summary") or turn.get("chat_opening")),
        half,
    )
    if not summary:
        for note in reversed(turn.get("dialogue") or []):
            if not isinstance(note, dict):
                continue
            said = str(note.get("assistant") or "").strip()
            if said:
                summary = _clip(_strip_digits(said), half)
                break
    if prompt and summary:
        body = f"{prompt} → {summary}"
    else:
        body = prompt or summary
    body = _clip(body, room)
    if not body:
        return ""
    return prefix + body


def _older_lines(rows: list[dict[str, Any]]) -> list[str]:
    """One line per old turn. Drop the oldest lines when the block is past the cap."""
    lines: list[str] = []
    for index, turn in enumerate(rows, start=1):
        line = _older_line(turn, index)
        if line:
            lines.append(line)
    while lines and sum(len(line) + 1 for line in lines) - 1 > _OLDER_CAP:
        lines.pop(0)
    return lines


def format_thread(turns: list[dict[str, Any]] | None) -> str:
    """Oldest first. Eight recent turns keep paragraphs. Older turns are one line each."""
    rows = [t for t in (turns or []) if isinstance(t, dict)]
    if not rows:
        return ""
    lines = [
        "Разговор этого чата (не Source).",
        "Числа и факты бери из документов этого запроса. "
        "Число из прошлого ответа повторяй, только если оно есть в этих документах. "
        "Прошлые ответы нужны, чтобы понять, о чём речь.",
    ]
    older = rows[:-_WINDOW] if len(rows) > _WINDOW else []
    recent = rows[-_WINDOW:]
    archived = _older_lines(older)
    if archived:
        lines.append("Раньше:")
        lines.extend(archived)
    for pos, turn in enumerate(recent):
        offset = len(recent) - 1 - pos
        index = len(older) + pos + 1
        prompt_cap, answer_cap, note_cap = _turn_budget(offset)
        prompt = _clip_prose(turn.get("chat_prompt"), prompt_cap)
        summary = _clip_prose(
            turn.get("chat_summary") or turn.get("chat_opening"), answer_cap
        )
        mode = _clip(turn.get("output_mode"), 20)
        if prompt:
            lines.append(f"Ход {index}. Запрос: {prompt}")
        if summary:
            tail = f" ({mode})" if mode else ""
            lines.append(f"Ответ{tail}: {summary}")
        notes = [
            note
            for note in (turn.get("dialogue") or [])
            if isinstance(note, dict)
        ]
        # The two newest turns keep every edit. Further back, one short note.
        # Eight verbatim turns plus the one-line archive stay under the prompt cap.
        if offset > 1:
            notes = notes[-1:]
            note_cap = 120
        for note in notes:
            user = _clip_prose(note.get("user"), note_cap)
            agent = _clip_prose(note.get("assistant"), note_cap)
            if user:
                lines.append(f"Дальше: {user}")
            if agent:
                lines.append(f"Ответ: {agent}")
    for turn in reversed(rows):
        edit = turn.get("last_edit")
        if not isinstance(edit, dict):
            continue
        section = _clip(edit.get("section"), 80)
        if not section:
            continue
        lines.append(f"Последняя правка раздела: {section}. Это не новый факт.")
        break
    return "\n".join(lines)


def _strip_digits(value: object) -> str:
    return re.sub(r"\d+", "", str(value or "")).strip()


def memory_card(turns: list[dict[str, Any]] | None, source_text: str = "") -> dict[str, Any]:
    """Labels for this chat. The open question keeps no digits."""
    rows = [t for t in (turns or []) if isinstance(t, dict)]
    section = ""
    style = ""
    for turn in reversed(rows):
        edit = turn.get("last_edit")
        if not isinstance(edit, dict):
            continue
        if not section:
            section = str(edit.get("section") or "").strip()
        if not style:
            style = str(edit.get("pack") or edit.get("palette") or "").strip()
    question = ""
    if rows:
        last = rows[-1]
        prompt = str(last.get("chat_prompt") or "")
        summary = str(last.get("chat_summary") or last.get("chat_opening") or "")
        folded = prompt.casefold()
        asks = "?" in prompt or folded.startswith("почему") or "зачем" in folded
        if asks and "?" in summary:
            question = _clip(_strip_digits(summary), 160)
    return {
        "documents": [name for name, _body in split_sources(source_text)],
        "section": section,
        "style": style,
        "open_question": question,
        "turn_count": len(rows),
    }


def format_card(card: dict[str, Any] | None) -> str:
    data = card or {}
    docs = [str(name).strip() for name in (data.get("documents") or []) if str(name).strip()]
    section = str(data.get("section") or "").strip()
    style = str(data.get("style") or "").strip()
    question = _clip(_strip_digits(data.get("open_question")), 160)
    if not docs and not section and not style and not question:
        return ""
    lines = ["Карточка этого чата (не Source)."]
    bits: list[str] = []
    if docs:
        bits.append("документы: " + ", ".join(docs))
    if section:
        bits.append("раздел: " + section)
    if style:
        bits.append("стиль: " + style)
    if bits:
        lines.append(". ".join(bits) + ".")
    if question:
        lines.append("Открытый вопрос: " + question)
    return "\n".join(lines)


_USER_NUMBER_MARK = "Числа из реплик пользователя"
_USER_NUMBER_CAP = 40
_PROMPT_CUTS = (
    "Требования UI:",
    "Разговор этого чата",
    "Карточка этого чата",
    "Один прошлый ход",
    "Предыдущий ход этого чата",
    _USER_NUMBER_MARK,
)


def _user_words(value: object) -> str:
    text = str(value or "")
    for marker in _PROMPT_CUTS:
        at = text.find(marker)
        if at != -1:
            text = text[:at]
    return text


def _binding_stem(blob: str, start: int, end: int) -> str:
    """The word next to a number. «слайд 2» and «2 слайда» both keep «слайд»."""
    before = re.findall(r"[0-9A-Za-zА-Яа-яЁё]{4,}", blob[max(0, start - 48) : start])
    word = before[-1] if before else ""
    if not word:
        after = re.findall(r"[0-9A-Za-zА-Яа-яЁё]{4,}", blob[end : end + 40])
        word = after[0] if after else ""
    stem = _stem(word)
    if len(stem) < 4 or stem in _LIFT_STOP:
        return ""
    return stem


def user_number_tokens(turns: list[dict[str, Any]] | None) -> list[str]:
    """Spellings the user wrote. Assistant fields are not scanned."""
    return [token for token, _stem in user_number_pairs(turns)]


def user_number_pairs(turns: list[dict[str, Any]] | None) -> list[tuple[str, str]]:
    """(spelling, stem). The same value can sit beside more than one word."""
    from case3.chat_turn import _NUM, _norm_num

    found: list[tuple[str, str]] = []
    seen: set[tuple[str, str]] = set()
    norms: list[str] = []
    for turn in turns or []:
        if not isinstance(turn, dict):
            continue
        blobs = [_user_words(turn.get("chat_prompt"))]
        for note in turn.get("dialogue") or []:
            if isinstance(note, dict):
                blobs.append(_user_words(note.get("user")))
        for blob in blobs:
            for match in _NUM.finditer(blob):
                token = match.group(0)
                norm = _norm_num(token)
                if not norm:
                    continue
                if norm not in norms:
                    if len(norms) >= _USER_NUMBER_CAP:
                        return found
                    norms.append(norm)
                stem = _binding_stem(blob, match.start(), match.end())
                key = (norm, stem)
                if key in seen:
                    continue
                seen.add(key)
                found.append((token, stem))
    return found


def format_user_numbers(turns: list[dict[str, Any]] | None) -> str:
    pairs = user_number_pairs(turns)
    if not pairs:
        return ""
    shown = [f"{token} {stem}".strip() for token, stem in pairs]
    return f"{_USER_NUMBER_MARK} (его слова, не ответ модели):\n" + ", ".join(shown)


_ENDINGS = (
    "ами",
    "ями",
    "ого",
    "ему",
    "ому",
    "ыми",
    "ими",
    "ах",
    "ях",
    "ов",
    "ев",
    "ам",
    "ям",
    "ом",
    "ем",
    "ой",
    "ей",
    "ый",
    "ий",
    "ая",
    "ое",
    "ее",
    "ую",
    "юю",
    "ие",
    "ые",
    "у",
    "ю",
    "а",
    "я",
    "ы",
    "и",
    "е",
    "о",
)


def _stem(word: str) -> str:
    """Cut a Russian ending so «кассу» meets «касса». Stems stay at least 3 letters."""
    token = word.casefold().replace("ё", "е")
    for ending in _ENDINGS:
        if token.endswith(ending) and len(token) - len(ending) >= 3:
            return token[: -len(ending)]
    return token


_RECALL = re.compile(
    r"как ты (отвечал|писал|говорил)|что ты (отвечал|писал|говорил|сказал)|вспомни|вернись к",
    re.IGNORECASE,
)
_FILLER = frozenset({"пожалуйста", "спасибо", "теперь"})
# Automatic lift ignores these. An explicit «вспомни …» still searches them.
_LIFT_STOP = frozenset(
    {
        "отчет",
        "раздел",
        "текст",
        "документ",
        "вопрос",
        "ответ",
        "сообщен",
        "чат",
        "можн",
        "нужн",
        "сдела",
        "собер",
        "почем",
        "почему",
        "зачем",
        "прост",
        "сейчас",
        "тогда",
        "потом",
        "тольк",
        "здесь",
        "очень",
        "хоч",
        "напиш",
        "скаж",
        "расскаж",
        "объясн",
        "такой",
        "така",
        "этот",
        "было",
        "стал",
        "пожалуйста",
        "спасибо",
    }
)


def _turn_blob(turn: dict[str, Any]) -> str:
    parts = [
        turn.get("chat_prompt"),
        turn.get("chat_summary"),
        turn.get("chat_opening"),
    ]
    for note in turn.get("dialogue") or []:
        if isinstance(note, dict):
            parts.append(note.get("user"))
            parts.append(note.get("assistant"))
    return " ".join(str(part or "") for part in parts)


def _stem_set(text: str) -> set[str]:
    blob = text.casefold().replace("ё", "е")
    return {_stem(token) for token in re.findall(r"[0-9a-zа-я]{3,}", blob)}


def _topic_words(raw: str) -> list[str]:
    """Words the user named. «про …» wins. Otherwise the phrase after the verb."""
    found = re.search(r"\bпро\s+(\S.*?)\s*$", raw, re.IGNORECASE)
    if found and found.group(1).strip():
        topic = found.group(1)
    else:
        topic = _RECALL.sub(" ", raw)
    topic = re.sub(r"[?.!,;:]+", "", topic)
    words = re.findall(r"[0-9a-zа-я]{4,}", topic.casefold().replace("ё", "е"))
    return [word for word in words if _stem(word) not in _FILLER]


def _query_stems(raw: str) -> list[str]:
    stems: list[str] = []
    seen: set[str] = set()
    for word in re.findall(r"[0-9a-zа-я]{4,}", raw.casefold().replace("ё", "е")):
        stem = _stem(word)
        if len(stem) < 4 or stem in _LIFT_STOP or stem in _FILLER or stem in seen:
            continue
        seen.add(stem)
        stems.append(stem)
    return stems


def _covers(words: list[str], blob: str) -> bool:
    folded = blob.casefold().replace("ё", "е")
    stems = _stem_set(blob)
    return all(_stem(word) in stems or word.casefold().replace("ё", "е") in folded for word in words)


def _lift_notes(turn: dict[str, Any], needles: set[str]) -> list[dict[str, Any]]:
    notes = [note for note in (turn.get("dialogue") or []) if isinstance(note, dict)]
    if len(notes) <= 2:
        return notes
    early = []
    for note in notes[:-1]:
        blob = f"{note.get('user') or ''} {note.get('assistant') or ''}"
        if needles & _stem_set(blob):
            early.append(note)
            break
    return (early + notes[-1:])[:2]


def _render_lift(turn: dict[str, Any], needles: set[str]) -> str:
    prompt = _clip_prose(turn.get("chat_prompt"), _TAIL)
    summary = _clip_prose(turn.get("chat_summary") or turn.get("chat_opening"), _TAIL)
    lines = ["Один прошлый ход (не Source)."]
    if prompt:
        lines.append("Запрос: " + prompt)
    if summary:
        lines.append("Ответ: " + summary)
    for note in _lift_notes(turn, needles):
        user = _clip_prose(note.get("user"), _NOTE)
        agent = _clip_prose(note.get("assistant"), _NOTE)
        if user:
            lines.append("Дальше: " + user)
        if agent:
            lines.append("Ответ: " + agent)
    return "\n".join(lines)


def _best_older(rows: list[dict[str, Any]], stems: list[str]) -> dict[str, Any] | None:
    """Highest overlap among turns outside the verbatim window. Newer wins a tie."""
    if len(rows) <= _WINDOW or not stems:
        return None
    best: dict[str, Any] | None = None
    best_score = 0
    for turn in rows[:-_WINDOW]:
        have = _stem_set(_turn_blob(turn))
        score = sum(1 for stem in stems if stem in have)
        if score > best_score:
            best = turn
            best_score = score
        elif score == best_score and score:
            best = turn
    need = 2 if len(stems) >= 2 else 1
    if best_score < need:
        return None
    return best


def recall_block(turns: list[dict[str, Any]] | None, text: str | None) -> str:
    """One older turn in full.

    An explicit recall («вспомни», «что ты говорил») searches every turn,
    including dialogue, and does not need the word «про». A plain message
    lifts one turn only when that turn is already outside the eight-turn window.
    """
    raw = (text or "").replace("ё", "е").replace("Ё", "Е")
    rows = [turn for turn in (turns or []) if isinstance(turn, dict)]
    if _RECALL.search(raw):
        words = _topic_words(raw)
        if not words:
            return "Один прошлый ход (не Source): напиши, про какой ответ вспомнить."
        match: dict[str, Any] | None = None
        for turn in rows:
            if _covers(words, _turn_blob(turn)):
                match = turn
        if match is None:
            return "Один прошлый ход (не Source): такого ответа в этом чате не видно."
        needles = {_stem(word) for word in words}
        return _render_lift(match, needles)
    match = _best_older(rows, _query_stems(raw))
    if match is None:
        return ""
    return _render_lift(match, set(_query_stems(raw)))


def chain_notice(turns_after: int) -> str:
    """Short warning on the 40th, 47th, and last turn. Empty otherwise."""
    if turns_after == 40:
        return (
            "В этом чате 40 ходов из 48. "
            "Потом новый вопрос попросит открыть «Новый чат»."
        )
    if turns_after == 47:
        return "Остался один ход после этого. Дальше открой «Новый чат»."
    if turns_after == _MAX_HOPS:
        return (
            "Этот ход последний в чате. "
            "Следующий вопрос попросит открыть «Новый чат»."
        )
    return ""


def chain_notice_for_prior(root: Path, prior_run_id: str | None) -> str:
    rid = (prior_run_id or "").strip()
    already = len(load_chain(root, rid)) if rid else 0
    return chain_notice(already + 1)


def chain_limit_say() -> str:
    return (
        f"В этом чате уже {_MAX_HOPS} ходов, дальше контекст не помещается. "
        "«Пустой» начнёт новый разговор. «С этими документами» заберёт файлы без старых ответов. "
        "Этот чат останется в списке слева."
    )


def chain_limit_payload(root: Path, prior_run_id: str | None) -> dict[str, Any] | None:
    """A new question or build past the chain cap. Edits are decided earlier."""
    rid = (prior_run_id or "").strip()
    if not rid:
        return None
    if len(load_chain(root, rid)) < _MAX_HOPS:
        return None
    return {
        "mode": "chat_revise",
        "status": "ok",
        "run_id": rid,
        "chat": chain_limit_say(),
        "op": "full",
        "surface": "",
        "output_mode": "chat",
    }


def load_chain(root: Path, run_id: str, *, hops: int = _MAX_HOPS) -> list[dict[str, Any]]:
    """Walk prior_run_id back to the start of this chat. Oldest first."""
    out_root = (Path(root) / "runs" / "out").resolve()
    seen: set[str] = set()
    found: list[dict[str, Any]] = []
    current = (run_id or "").strip()
    while current and current not in seen and len(found) < hops:
        seen.add(current)
        meta_path = (out_root / current / "meta.json").resolve()
        if not str(meta_path).startswith(str(out_root)) or not meta_path.is_file():
            break
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            break
        if not isinstance(meta, dict):
            break
        found.append(meta)
        current = str(meta.get("prior_run_id") or "").strip()
    found.reverse()
    return found


def append_dialogue(meta: dict[str, Any], user: str, assistant: str) -> None:
    """Remember an in-place edit on the same run. Cap the list."""
    notes = meta.get("dialogue")
    if not isinstance(notes, list):
        notes = []
    notes.append(
        {
            "user": _clip_prose(user, 300),
            "assistant": _clip_prose(assistant, 300),
        }
    )
    meta["dialogue"] = notes[-12:]


def format_sources(parts: list[tuple[str, str]] | None) -> str:
    """Labeled documents. The model can tell them apart."""
    rows = []
    for name, text in parts or []:
        title = " ".join(str(name or "Документ").split()) or "Документ"
        body = str(text or "").strip()
        if not body:
            continue
        rows.append(f"===== {title} =====\n{body}")
    return "\n\n".join(rows)


_PART = re.compile(r"^===== (.+?) =====\s*$", re.MULTILINE)


def split_sources(text: str | None) -> list[tuple[str, str]]:
    """Inverse of format_sources. A plain file stays one document."""
    raw = (text or "").strip()
    if not raw:
        return []
    marks = list(_PART.finditer(raw))
    if not marks:
        return [("Документ", raw)]
    parts: list[tuple[str, str]] = []
    for index, mark in enumerate(marks):
        start = mark.end()
        end = marks[index + 1].start() if index + 1 < len(marks) else len(raw)
        body = raw[start:end].strip()
        name = " ".join(mark.group(1).split()) or "Документ"
        if body:
            parts.append((name, body))
    return parts[:5]


_ORDINALS = (
    (1, re.compile(r"перв", re.IGNORECASE)),
    (2, re.compile(r"втор", re.IGNORECASE)),
    (3, re.compile(r"трет", re.IGNORECASE)),
    (4, re.compile(r"четверт", re.IGNORECASE)),
    (5, re.compile(r"пят", re.IGNORECASE)),
)
_DOC_WORD = re.compile(r"файл|документ", re.IGNORECASE)
_DOC_NUM = re.compile(r"\b([1-5])\b")


def document_index(message: str | None) -> int:
    """1-based document named in the message. 0 when none is named."""
    raw = (message or "").replace("ё", "е").replace("Ё", "Е")
    if not _DOC_WORD.search(raw):
        return 0
    number = _DOC_NUM.search(raw)
    if number:
        return int(number.group(1))
    for index, pattern in _ORDINALS:
        if pattern.search(raw):
            return index
    return 0


def focus_source(text: str | None, message: str | None) -> str:
    """Keep one labeled document when the message points at it."""
    raw = text or ""
    index = document_index(message)
    parts = split_sources(raw)
    if not index or index > len(parts):
        return raw
    name, body = parts[index - 1]
    return format_sources([(name, body)])


def load_chain_dirs(root: Path, run_id: str, *, hops: int = _MAX_HOPS) -> list[tuple[str, Path, dict[str, Any]]]:
    """Same walk as load_chain, with the run directory kept."""
    out_root = (Path(root) / "runs" / "out").resolve()
    seen: set[str] = set()
    found: list[tuple[str, Path, dict[str, Any]]] = []
    current = (run_id or "").strip()
    while current and current not in seen and len(found) < hops:
        seen.add(current)
        out_dir = (out_root / current).resolve()
        if not str(out_dir).startswith(str(out_root)):
            break
        meta_path = out_dir / "meta.json"
        if not meta_path.is_file():
            break
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            break
        if not isinstance(meta, dict):
            break
        found.append((current, out_dir, meta))
        current = str(meta.get("prior_run_id") or "").strip()
    found.reverse()
    return found


def report_tex(root: Path, run_id: str) -> str:
    """Newest report in this chat. A later note without sections is skipped."""
    rid = (run_id or "").strip()
    if not rid:
        return ""
    for _rid, path, _meta in reversed(load_chain_dirs(root, rid)):
        for tex in sorted(path.glob("*.tex")):
            try:
                text = tex.read_text(encoding="utf-8")
            except OSError:
                continue
            if r"\section" in text:
                return text
    return ""


def merge_edit(found: dict[str, str], raw: object) -> dict[str, str]:
    """Keep a section when a later note, such as undo, does not name one."""
    if not isinstance(raw, dict):
        return found
    nxt = dict(found)
    for key in ("op", "section", "pack", "palette", "surface"):
        val = str(raw.get(key) or "").strip()
        if val:
            nxt[key] = val
    return nxt


def newest_edit(root: Path, run_id: str) -> dict[str, str]:
    """Latest section or style remembered anywhere in this chat."""
    found: dict[str, str] = {}
    for _run_id, _path, meta in load_chain_dirs(root, run_id):
        found = merge_edit(found, meta.get("last_edit"))
    return found


def _dialogue(meta: dict[str, Any]) -> list[dict[str, str]]:
    notes = meta.get("dialogue")
    if not isinstance(notes, list):
        return []
    out: list[dict[str, str]] = []
    for note in notes:
        if not isinstance(note, dict):
            continue
        out.append(
            {
                "user": _clip_prose(note.get("user"), 300),
                "assistant": _clip_prose(note.get("assistant"), 300),
            }
        )
    return out[-12:]


_ON_THIS_DATA = re.compile(r"по\s+(?:этим\s+)?данным", re.IGNORECASE)


def earlier_source(root: Path, prior_run_id: str) -> str:
    """Document of a previous turn. Empty when that turn had no file."""
    rid = (prior_run_id or "").strip()
    if not rid:
        return ""
    for turn in reversed(load_chain(root, rid)):
        text = _source_file(root, turn).strip()
        if text:
            return text
    return ""


def dashboard_screen(root: Path, prior_run_id: str) -> str:
    """Newest dashboard document in this chat. A later note without the screen is skipped."""
    rid = (prior_run_id or "").strip()
    if not rid:
        return ""
    for turn in reversed(load_chain(root, rid)):
        text = _source_file(root, turn).strip()
        if "# Данные дашборда" in text:
            return text
    return ""


def dashboard_parts(text: str) -> list[tuple[str, str]]:
    """Every packed screen. The five-document cap does not apply."""
    raw = (text or "").strip()
    if "# Данные дашборда" not in raw:
        return []
    marks = list(_PART.finditer(raw))
    if not marks:
        return [("Экран", raw)]
    parts: list[tuple[str, str]] = []
    for index, mark in enumerate(marks):
        start = mark.end()
        end = marks[index + 1].start() if index + 1 < len(marks) else len(raw)
        body = raw[start:end].strip()
        if "# Данные дашборда" not in body:
            continue
        name = " ".join(mark.group(1).split()) or "Экран"
        parts.append((name, body))
    return parts


def _merge_screens(chunks: list[str]) -> str:
    seen: set[str] = set()
    parts: list[tuple[str, str]] = []
    for chunk in chunks:
        for name, body in dashboard_parts(chunk):
            key = " ".join(body.split())
            if not key or key in seen:
                continue
            seen.add(key)
            parts.append((name, body))
    return format_sources(parts)


def dashboard_screens(root: Path, prior_run_id: str) -> str:
    """Every dashboard snapshot in this chat, oldest first. A repeated screen is kept once."""
    rid = (prior_run_id or "").strip()
    if not rid:
        return ""
    return _merge_screens(
        [_source_file(root, turn) for turn in load_chain(root, rid)]
    )


def latest_dashboard_note(root: Path, prior_run_id: str) -> str:
    """Short note written when the screen was saved. Empty when this chat has none."""
    rid = (prior_run_id or "").strip()
    if not rid:
        return ""
    for turn in reversed(load_chain(root, rid)):
        text = str(turn.get("dashboard_note") or "").strip()
        if text:
            return text
    return ""


def source_for_followup(current: str, screen: str, user_text: str, *, picture: bool) -> str:
    """Keep every saved screen. A different long document stays as it is."""
    here = current or ""
    saved = _merge_screens([screen, here])
    if not saved:
        return here
    if dashboard_parts(here):
        return saved
    asked = picture or bool(_ON_THIS_DATA.search(user_text or ""))
    clean_user = (user_text or "").strip()
    clean_here = here.strip()
    same_as_question = clean_here == clean_user or (
        bool(clean_user) and clean_user in clean_here
    )
    if asked or same_as_question or len(here) < 600:
        return saved
    return here


def prior_document_source(root: Path, prior_run_id: str) -> str:
    """Restore an earlier attached source document when no dashboard screen exists."""
    rid = (prior_run_id or "").strip()
    if not rid:
        return ""
    for turn in reversed(load_chain(root, rid)):
        src = _source_file(root, turn)
        if not src.strip():
            continue
        chat_prompt = str(turn.get("chat_prompt") or "").strip()
        if src.strip() != chat_prompt or len(src.strip()) >= 240:
            return src
    return ""


def _source_file(root: Path, meta: dict[str, Any]) -> str:
    raw = str(meta.get("source") or "").strip()
    if not raw:
        return ""
    path = Path(raw).expanduser().resolve()
    base = (Path(root) / "runs").resolve()
    try:
        path.relative_to(base)
    except ValueError:
        return ""
    try:
        if path.is_file():
            return path.read_text(encoding="utf-8")
    except OSError:
        return ""
    return ""


def _copy_source_photos(root: Path, run_id: str, figs: Path) -> None:
    """A chat that never reached figures/ still has usr_*.png next to source.txt."""
    meta_path = Path(root) / "runs" / "out" / run_id / "meta.json"
    try:
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return
    if not isinstance(meta, dict):
        return
    source = Path(str(meta.get("source") or "")).expanduser()
    if not source.is_absolute():
        return
    base = (Path(root) / "runs").resolve()
    try:
        source.resolve().relative_to(base)
    except ValueError:
        return
    folder = source.parent / "user_photos"
    if not folder.is_dir():
        return
    pngs = sorted(folder.glob("usr_*.png"))
    if not pngs:
        return
    try:
        figs.mkdir(parents=True, exist_ok=True)
    except OSError:
        return
    for png in pngs[:5]:
        dest = figs / png.name
        if dest.is_file():
            continue
        try:
            dest.write_bytes(png.read_bytes())
        except OSError:
            continue


def _photo_thumbs(root: Path, run_id: str) -> list[dict[str, str]]:
    rid = (run_id or "").strip()
    if not re.fullmatch(r"[A-Za-z0-9_]+", rid):
        return []
    figs = (Path(root) / "runs" / "out" / rid / "figures").resolve()
    base = (Path(root) / "runs" / "out").resolve()
    try:
        figs.relative_to(base)
    except ValueError:
        return []
    if not figs.is_dir() or not any(figs.glob("usr_*.png")):
        _copy_source_photos(root, rid, figs)
    if not figs.is_dir():
        return []
    thumbs: list[dict[str, str]] = []
    for png in sorted(figs.glob("usr_*.png")):
        if not png.is_file():
            continue
        thumbs.append(
            {"name": png.stem, "url": f"/api/runs/{rid}/figures/{png.name}"}
        )
        if len(thumbs) == 5:
            break
    return thumbs


def _chat_previews(root: Path, run_id: str, meta: dict[str, Any]) -> list[dict[str, str]]:
    """Inline chat chart/diagram PNG previews (cht_* / dia_*) for a run."""
    rid = (run_id or "").strip()
    if not re.fullmatch(r"[A-Za-z0-9_]+", rid):
        return []
    figs = (Path(root) / "runs" / "out" / rid / "figures").resolve()
    base = (Path(root) / "runs" / "out").resolve()
    try:
        figs.relative_to(base)
    except ValueError:
        return []
    if not figs.is_dir():
        return []
    status = meta.get("media_status") if isinstance(meta.get("media_status"), dict) else {}
    previews: list[dict[str, str]] = []
    for png in sorted(figs.glob("*.png")):
        if not png.is_file():
            continue
        stem = png.stem
        if not (stem.startswith("cht_") or stem.startswith("dia_")):
            continue
        info = status.get(stem) if isinstance(status, dict) else None
        if isinstance(info, dict) and info.get("ok") is False:
            continue
        kind = (
            str(info.get("kind") or "")
            if isinstance(info, dict)
            else ""
        ) or ("diagram" if stem.startswith("dia_") else "chart")
        previews.append(
            {
                "id": stem,
                "kind": kind,
                "url": f"/api/runs/{rid}/figures/{png.name}",
            }
        )
    return previews


def _turn_attachments(
    meta: dict[str, Any],
    source_text: str,
    prev_source_text: str,
) -> list[dict[str, Any]]:
    """Documents attached directly on this turn (metadata + extracted text)."""
    raw_meta = meta.get("attachments")
    raw_src = (source_text or "").strip()
    if "# Данные дашборда" in raw_src:
        return []
    parts = split_sources(raw_src)
    if isinstance(raw_meta, list) and raw_meta:
        out: list[dict[str, Any]] = []
        for idx, item in enumerate(raw_meta[:5]):
            if not isinstance(item, dict):
                continue
            part_name, part_body = (
                parts[idx]
                if idx < len(parts)
                else (
                    str(item.get("fileName") or item.get("title") or "Документ"),
                    raw_src,
                )
            )
            entry = {
                "name": str(item.get("fileName") or item.get("title") or part_name),
                "title": str(item.get("title") or item.get("fileName") or part_name),
                "fileName": str(item.get("fileName") or item.get("title") or part_name),
                "text": _clip_prose(part_body, 100_000),
            }
            for key in ("viewMode", "previewUrl", "originalUrl", "ingestId", "format"):
                val = item.get(key)
                if isinstance(val, str) and val.strip():
                    entry[key] = val.strip()
            out.append(entry)
        return out
    # Legacy runs without meta["attachments"]: attach only when this turn introduced
    # an explicit document/marked source distinct from chat_prompt and prior turn.
    if not raw_src or raw_src == (prev_source_text or "").strip():
        return []
    prompt = str(meta.get("chat_prompt") or "").strip()
    if not _PART.search(raw_src) and raw_src == prompt:
        return []
    if not _PART.search(raw_src) and len(raw_src) < 240:
        return []
    return [
        {
            "name": name,
            "title": name,
            "fileName": name,
            "text": _clip_prose(body, 100_000),
            "viewMode": "text",
        }
        for name, body in parts
    ]


def memory_view(root: Path, run_id: str) -> dict[str, Any] | None:
    """One chat: turns oldest-first, plus the documents of the latest run."""
    chain = load_chain(root, run_id)
    if not chain:
        return None
    turns: list[dict[str, Any]] = []
    prev_raw_source = ""
    for meta in chain:
        edit = meta.get("last_edit")
        turn_id = str(meta.get("run_id") or "")
        turn_source = _source_file(root, meta)
        row: dict[str, Any] = {
            "run_id": turn_id,
            "chat_prompt": _clip_prose(meta.get("chat_prompt"), 2000),
            "chat_summary": _clip_prose(
                meta.get("chat_summary") or meta.get("chat_opening"), 2000
            ),
            "chat_opening": _clip_prose(meta.get("chat_opening"), 600),
            "output_mode": _clip(meta.get("output_mode"), 20),
            "dialogue": _dialogue(meta),
            "last_edit": edit if isinstance(edit, dict) else {},
            "photos": _photo_thumbs(root, turn_id),
            "previews": _chat_previews(root, turn_id, meta),
        }
        attachments = _turn_attachments(meta, turn_source, prev_raw_source)
        if attachments:
            row["attachments"] = attachments
        if turn_source.strip():
            prev_raw_source = turn_source
        shot = _clip_prose(turn_source, 200_000)
        if "# Данные дашборда" in shot:
            row["dashboard_source"] = shot
        turns.append(row)
    source = ""
    for meta in reversed(chain):
        source = _source_file(root, meta)
        if source.strip():
            break
    if len(source) > 500_000:
        source = source[:500_000]
    documents = [{"name": name, "text": text} for name, text in split_sources(source)]
    return {
        "turns": turns,
        "documents": documents,
        "last_edit": newest_edit(root, run_id),
        "artifact_run_id": _artifact_run_id(root, run_id),
    }


def _artifact_run_id(root: Path, run_id: str) -> str:
    """Newest run in this chat that still holds a report or a deck."""
    found = ""
    for rid, path, meta in load_chain_dirs(root, run_id):
        mode = str(meta.get("output_mode") or "")
        slides = str(meta.get("slides_status") or "")
        artifacts = meta.get("artifacts")
        has_deck = mode == "presentation" or slides in {"ok", "running", "error"}
        has_report = mode == "report" or any(path.glob("*.tex")) or (
            isinstance(artifacts, dict) and bool(artifacts)
        )
        if has_deck or has_report:
            found = rid
    return found
