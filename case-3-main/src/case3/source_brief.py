"""Map a long technical Source into a deck brief, and lift one line from each listing.

A 30k-character spec does not fit the slides model. The brief keeps headings,
sentences that contain numbers, and one signature per code fence. The rest of
the listing stays out of the deck.
"""

from __future__ import annotations

import re
from typing import Any

_FENCE = re.compile(r"```([A-Za-z0-9_+-]*)\n(.*?)```", re.S)
_HEAD = re.compile(r"^(#{1,3})\s+(.+)$", re.M)
_SENT_SPLIT = re.compile(r"(?<=[.!?])\s+")
_DEF_NAME = re.compile(
    r"(?:^|\s)(?:async\s+)?(?:def|function|func|fn|class|interface|struct)\s+"
    r"([A-Za-z_][\w]*)"
)
_METHOD = re.compile(
    r"(?:public|private|protected)\s+[\w.<>\[\]]+\s+([A-Za-z_]\w*)\s*\("
)

_BRIEF_AT = 8000
_BRIEF_MAX = 32000
_FACTS_PER_SECTION = 8
_FACTS_RICH_SECTION = 80
_RICH_SECTION = re.compile(r"^(?:производные|карточки|таблица(?:\s+pdf)?)$", re.IGNORECASE)
_CODE_MAX = 4
_TERM_MAX = 48
_DEF_MAX = 220
_TITLE_MAX = 80


def code_highlights(source: str, *, limit: int = _CODE_MAX) -> list[dict[str, str]]:
    """One signature (or first real line) from each fenced listing."""
    out: list[dict[str, str]] = []
    seen: set[str] = set()
    for match in _FENCE.finditer(source or ""):
        name, line = _important_line(match.group(2))
        if not line:
            continue
        key = name.casefold()
        if key in seen:
            continue
        seen.add(key)
        out.append({"name": name[:_TERM_MAX], "line": line[:_DEF_MAX]})
        if len(out) >= limit:
            break
    return out


def slides_source_text(source: str) -> str:
    """What the slides model should read.

    Short prose is unchanged. A long spec, or any spec with listings, becomes
    a map: size, headings, numbered facts, and CODE HIGHLIGHTS.
    """
    text = source or ""
    highs = code_highlights(text)
    if len(text) <= _BRIEF_AT and not highs:
        return text
    if len(text) <= _BRIEF_AT:
        return text.rstrip() + "\n\n" + _highlights_block(highs)
    prose = _FENCE.sub("\n", text)
    parts = [
        f"Объём исходника: {len(text)} символов. "
        "Ниже карта для презы: заголовки и фразы с числами. "
        "Не добавляй факты, которых здесь нет."
    ]
    if highs:
        parts.append(_highlights_block(highs))
    for title, body in _sections(prose):
        sec_limit = _FACTS_RICH_SECTION if _RICH_SECTION.match(title) else _FACTS_PER_SECTION
        facts = _fact_lines(body, limit=sec_limit)
        if not title and not facts:
            continue
        if title:
            parts.append(f"## {title}")
        parts.extend(f"- {fact}" for fact in facts)
        blob = "\n".join(parts)
        if len(blob) >= _BRIEF_MAX:
            return blob[:_BRIEF_MAX]
    return "\n".join(parts)[:_BRIEF_MAX]


def ensure_code_callouts(
    deck: dict[str, Any],
    highlights: list[dict[str, str]],
    *,
    max_slides: int = 24,
) -> list[str]:
    """Insert a callout per highlight the model skipped. One line, not the listing."""
    if not isinstance(deck, dict) or not highlights:
        return []
    slides = [s for s in (deck.get("slides") or []) if isinstance(s, dict)]
    if not slides:
        return []
    have = " ".join(
        f"{s.get('term') or ''} {s.get('title') or ''} {s.get('definition') or ''}"
        for s in slides
    ).casefold()
    used_ids = {str(s.get("id") or "") for s in slides}
    placed: list[str] = []
    for item in highlights[:_CODE_MAX]:
        name = str(item.get("name") or "").strip()
        line = str(item.get("line") or "").strip()
        if not name or not line or name.casefold() in have:
            continue
        slide = {
            "id": _fresh_id(used_ids, name),
            "layout": "callout",
            "kicker": "КОД",
            "title": _clip(name, _TITLE_MAX),
            "term": _clip(name, _TERM_MAX),
            "definition": _clip(line, _DEF_MAX),
        }
        if not _insert(slides, slide, max_slides=max_slides):
            continue
        used_ids.add(slide["id"])
        have = f"{have} {name.casefold()}"
        placed.append(name)
    deck["slides"] = slides
    return placed


def _important_line(body: str) -> tuple[str, str]:
    lines = []
    for raw in (body or "").splitlines():
        stripped = raw.strip()
        if not stripped or stripped.startswith(("#", "//", "/*", "*", "--")):
            continue
        lines.append(stripped)
    for line in lines:
        match = _DEF_NAME.search(line)
        if match:
            return match.group(1), line
        match = _METHOD.search(line)
        if match:
            return match.group(1), line
    if not lines:
        return "", ""
    line = lines[0]
    token = re.split(r"[\s(]", line, maxsplit=1)[0]
    name = token if re.match(r"[A-Za-z_]\w*$", token) else "код"
    return name, line


def _highlights_block(highlights: list[dict[str, str]]) -> str:
    lines = [
        "CODE HIGHLIGHTS (один callout на пункт: term = имя, definition = эта строка; весь листинг не копировать):"
    ]
    for item in highlights:
        lines.append(f"- {item['name']}: {item['line']}")
    return "\n".join(lines)


def _sections(prose: str) -> list[tuple[str, str]]:
    matches = list(_HEAD.finditer(prose or ""))
    if not matches:
        return [("", prose or "")]
    chunks: list[tuple[str, str]] = []
    if matches[0].start() > 0:
        chunks.append(("", prose[: matches[0].start()]))
    for i, match in enumerate(matches):
        end = matches[i + 1].start() if i + 1 < len(matches) else len(prose)
        chunks.append((match.group(2).strip(), prose[match.end() : end]))
    return chunks


def _fact_lines(body: str, *, limit: int) -> list[str]:
    lines = [line.strip() for line in (body or "").splitlines() if line.strip()]
    table = [
        line
        for line in lines
        if line.startswith("|") and not re.match(r"^\|?[\s\-:|]+\|?$", line)
    ]
    out: list[str] = []
    if table:
        row_cap = max(limit, 150)
        for line in table:
            flat = " ".join(line.split())
            if len(flat) > 400:
                flat = flat[:399].rstrip() + "…"
            out.append(flat)
            if len(out) >= row_cap:
                break
        non_table_lines = [line for line in lines if not line.startswith("|")]
        if not non_table_lines:
            return out
    else:
        non_table_lines = lines
    candidates: list[str] = []
    for ln in non_table_lines:
        if not ln:
            continue
        if re.match(r"^(?:[-*•]|\d+[.)])\s+", ln):
            candidates.append(re.sub(r"^(?:[-*•]|\d+[.)])\s+", "", ln).strip())
        else:
            candidates.extend(s.strip() for s in _SENT_SPLIT.split(ln) if s.strip())
    sentences = [s for s in candidates if s]
    numbered = [s for s in sentences if re.search(r"\d", s)]
    chosen = numbered or ([] if table else sentences[:1])
    prose_added = 0
    for sentence in chosen:
        flat = " ".join(sentence.split())
        if len(flat) > 400:
            flat = flat[:399].rstrip() + "…"
        out.append(flat)
        prose_added += 1
        if prose_added >= limit:
            break
    return out


def _clip(text: str, limit: int) -> str:
    raw = " ".join(text.split())
    if len(raw) <= limit:
        return raw
    if limit <= 1:
        return raw[:limit]
    return raw[: limit - 1].rstrip() + "…"


def _fresh_id(used: set[str], name: str) -> str:
    base = "s_code_" + re.sub(r"[^a-z0-9_]", "", name.lower())[:16]
    if len(base) < 3:
        base = "s_code_item"
    if base not in used:
        return base
    n = 2
    while f"{base}_{n}" in used:
        n += 1
    return f"{base}_{n}"


def _insert(slides: list[dict[str, Any]], slide: dict[str, Any], *, max_slides: int) -> bool:
    if len(slides) >= max_slides:
        for i in range(len(slides) - 2, 0, -1):
            if str(slides[i].get("layout") or "") in {"bullets", "callout", "card_row"}:
                if str(slides[i].get("kicker") or "") == "КОД":
                    continue
                slides[i] = slide
                return True
        return False
    at = next(
        (i for i, s in enumerate(slides) if str(s.get("layout") or "") == "closing"),
        len(slides),
    )
    slides.insert(at, slide)
    return True
