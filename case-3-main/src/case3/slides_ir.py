"""Parse and validate Liber deck IR (executive slides, Source-bound)."""

from __future__ import annotations

import re
from decimal import Decimal
from typing import Any

from case3.chart_style import normalize_palette_id

SLIDE_LAYOUTS = frozenset(
    {
        "title",
        "chart_hero",
        "chart_split",
        "media_hero",
        "media_split",
        "bullets",
        "kpi_row",
        "closing",
        "section",
        "scorecard",
        "callout",
        "table_hero",
        "card_row",
        "stat_hero",
        "timeline",
        "compare",
        "quote",
    }
)

_ID_OK = re.compile(r"^[a-z][a-z0-9_]{1,31}$")
_CHART_ID_OK = re.compile(r"^[a-z][a-z0-9_]{1,31}$")
_MEDIA_ID_OK = re.compile(r"^(cht|fig|usr|dia)_[a-z0-9_]{1,28}$")
_NUMBER_RUN = re.compile(r"\d+(?:[.,]\d+)?")

_MAX_SLIDES = 24
_MIN_SLIDES_SOFT = 8  # prompt prefers 10–12; hard min stays 3
_MAX_TITLE = 80
_MAX_SUBTITLE = 120
_MAX_TAKEAWAY = 120
_MAX_KICKER = 40
_MAX_BULLET = 140
_MAX_BULLETS = 5
_MAX_CAPTION = 160
_MAX_KPI = 4
_MAX_KPI_LABEL = 40
_MAX_KPI_VALUE = 24
_MAX_DELTA = 16
_MAX_TERM = 56
_MAX_DEFINITION = 280
_MAX_CARDS = 3
_MAX_CARD_KICKER = 48
_MAX_CARD_TITLE = 72
_MAX_CARD_BODY = 240
_MAX_TABLE_ROWS = 14
_MAX_TABLE_COLS = 8
_MAX_CELL = 48
_MAX_CONSECUTIVE_BULLETS = 2
_KPI_STATUS = frozenset({"up", "down", "flat"})


class DeckIrError(ValueError):
    """Deck IR rejected."""


def _norm_ws(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").strip())


def _collect_text_blobs(slide: dict[str, Any]) -> list[tuple[str, bool]]:
    """Text on a slide, and whether that field is only a section kicker."""
    blobs: list[tuple[str, bool]] = []
    for key in (
        "title",
        "subtitle",
        "caption",
        "body",
        "kicker",
        "takeaway",
        "term",
        "definition",
    ):
        val = slide.get(key)
        if isinstance(val, str) and val.strip():
            blobs.append((val, key == "kicker"))
    bullets = slide.get("bullets")
    if isinstance(bullets, list):
        for b in bullets:
            if isinstance(b, str) and b.strip():
                blobs.append((b, False))
    kpis = slide.get("kpis")
    if isinstance(kpis, list):
        for k in kpis:
            if not isinstance(k, dict):
                continue
            for key in ("label", "value", "hint", "delta"):
                val = k.get(key)
                if isinstance(val, str) and val.strip():
                    blobs.append((val, False))
    rows = slide.get("rows")
    if isinstance(rows, list):
        for row in rows:
            if isinstance(row, list):
                for cell in row:
                    if isinstance(cell, str) and cell.strip():
                        blobs.append((cell, False))
    for card in slide.get("cards") or []:
        if not isinstance(card, dict):
            continue
        for key in ("title", "body", "kicker"):
            val = card.get(key)
            if isinstance(val, str) and val.strip():
                blobs.append((val, False))
    return blobs


def _compact_spaced_thousands(text: str) -> str:
    """Join ``9 330`` / ``9 330`` into ``9330`` before digit gating."""
    return re.sub(
        r"(?<=\d)[\s\u00a0\u202f]+(?=\d{3}(?:\D|$))",
        "",
        text or "",
    )


def _numbers_in_text(text: str) -> list[str]:
    return _NUMBER_RUN.findall(_compact_spaced_thousands(text))


def _number_variants(num: str) -> list[str]:
    n = num or ""
    return list({n, n.replace(",", "."), n.replace(".", ",")})


def _is_section_index_chrome(num: str, blob: str = "") -> bool:
    """A kicker that is only ``01`` or ``1``…``24`` (or ``01 / HEADLINE``).

    The same digits in a sentence or a table cell are a fact and need Source.
    """
    n = num or ""
    padded = bool(re.fullmatch(r"0\d{1,2}", n))
    short = bool(re.fullmatch(r"[1-9]|1[0-9]|2[0-4]", n))
    if not padded and not short:
        return False
    return bool(re.fullmatch(r"\s*[0-9]{1,3}(?:\s*[/·:\-]\s*\D.*)?\s*", blob or ""))


def _boundary_hit(num: str, source_norm: str) -> bool:
    """Whole-token match — ``38`` must not hitchhike on ``38000``."""
    if not num or not source_norm:
        return False
    for m in re.finditer(re.escape(num), source_norm):
        start, end = m.span()
        before = source_norm[start - 1] if start > 0 else ""
        after = source_norm[end] if end < len(source_norm) else ""
        # Part of a longer integer/decimal run → reject this hit.
        if before.isdigit():
            continue
        if before in ".," and start >= 2 and source_norm[start - 2].isdigit():
            continue
        if after.isdigit():
            continue
        if after in ".," and end + 1 < len(source_norm) and source_norm[end + 1].isdigit():
            continue
        return True
    return False


def _number_in_source(num: str, source_norm: str) -> bool:
    """Match a spaced cell and the same cell after the spaces are joined."""
    if _boundary_hit(num, source_norm):
        return True
    compact_num = _compact_spaced_thousands(num)
    compact_src = _compact_spaced_thousands(source_norm)
    if compact_num != num or compact_src != source_norm:
        return _boundary_hit(compact_num, compact_src)
    return False


_SCALE_WORD = re.compile(
    r"(\d{1,3}(?:[\s\u00a0\u202f]+\d{3})+(?:[.,]\d+)?|\d+(?:[.,]\d+)?)\s*(тысяч\w*|тыс\.?|млн\.?|млрд\.?)",
    re.IGNORECASE,
)


def _scaled_magnitudes(text: str) -> set[str]:
    """``86 тысяч`` → ``86000``. Bare ``86000`` does not unlock ``86``."""
    out: set[str] = set()
    for match in _SCALE_WORD.finditer(_compact_spaced_thousands(text or "")):
        raw = match.group(1).replace(",", ".")
        unit = match.group(2).lower()
        if unit.startswith("тыс"):
            mult = 1000
        elif unit.startswith("млн"):
            mult = 1_000_000
        else:
            mult = 1_000_000_000
        try:
            val = Decimal(raw) * Decimal(mult)
        except Exception:
            continue
        if val == val.to_integral_value():
            out.add(str(int(val)))
    return out


def _number_is_allowed(
    num: str,
    *,
    source_norm: str,
    allowed: frozenset[str],
    blob: str = "",
    chrome: bool = False,
) -> bool:
    if chrome and _is_section_index_chrome(num, blob):
        return True
    for v in _number_variants(num):
        if v in allowed or _number_in_source(v, source_norm):
            return True
        plain = v.replace(",", ".")
        if plain in _scaled_magnitudes(source_norm):
            return True
    return False


def _assert_numbers_allowed(
    text: str,
    *,
    source_norm: str,
    allowed: frozenset[str],
    chrome: bool = False,
) -> None:
    for num in _numbers_in_text(text):
        if _number_is_allowed(
            num,
            source_norm=source_norm,
            allowed=allowed,
            blob=text,
            chrome=chrome,
        ):
            continue
        raise DeckIrError(
            f"number {num!r} not found in Source (and not in allowed chart numbers)"
        )


_ORPHAN_UNIT = re.compile(
    r"(?:°C|°F|℃|℉|%|(?:тыс\.?|млн\.?|млрд\.?)\s+руб\.?|тыс\.?|млн\.?|млрд\.?|чел\.?|pp|п\.?\s?п\.?)",
    re.IGNORECASE,
)
_ORPHAN_UNIT_ONLY = re.compile(
    rf"^\s*(?:[-−–—+]?\s*)?(?:{_ORPHAN_UNIT.pattern})\s*$",
    re.IGNORECASE,
)


def _strip_orphan_units(text: str) -> str:
    """Remove unit tokens left orphaned after digit scrub (never strip units beside kept digits)."""
    out = text or ""
    # dash/colon + unit (when not preceded by a digit)
    out = re.sub(
        rf"(?<!\d)\s*[-−–—:]\s*(?:{_ORPHAN_UNIT.pattern})(?![\w./])",
        "",
        out,
        flags=re.IGNORECASE,
    )
    # bare unit tokens not preceded by a digit (kept numbers keep their units: 103,2% / 412 850,4 тыс. руб.)
    out = re.sub(
        rf"(?P<keep>\d[\s\u00a0\u202f]*)?(?<![\w./])(?P<unit>{_ORPHAN_UNIT.pattern})(?![\w./])",
        lambda m: m.group(0) if m.group("keep") else "",
        out,
        flags=re.IGNORECASE,
    )
    # empty parens left by removed numbers
    out = re.sub(r"\(\s*\)", "", out)
    out = re.sub(r"\[\s*\]", "", out)
    # orphan sign left after scrubbing the digits of −38 → "−"
    out = re.sub(r"(?<![\d])[-−–+](?!\d)", "", out)
    out = re.sub(r"\s{2,}", " ", out)
    out = re.sub(r"\s+([,.;:!?])", r"\1", out)
    out = re.sub(r"([-−–—,:;])\s*\1+", r"\1", out)
    out = re.sub(r"^[\s,.;:!?−–—-]+|[\s,.;:!?−–—-]+$", "", out)
    return out.strip()


def _kpi_value_ok(value: str) -> bool:
    v = (value or "").strip()
    if not v:
        return False
    if _ORPHAN_UNIT_ONLY.match(v):
        return False
    # Prefer values that still carry a digit, sign, or word (not only punctuation)
    if not re.search(r"[\dA-Za-zА-Яа-яЁё]", v):
        return False
    return True


_BROKEN_SCRUB = re.compile(
    r"(?:"
    r"\b(?:на|с|от|до|около|порядка|минус|плюс)\s*$"
    r"|\bна\s*[;,]|\bна\s+(?:за|с|по|от|до)\b"
    r"|\b(?:выросла?|вырос|увеличил(?:ась|ся)?|снизил(?:ась|ся)?|сократил(?:ась|ся)?|"
    r"достигл[аио]?|составил[аио]?)\s+(?:на\s+)?(?:от\s+)?"
    r"(?:понедельник|вторник|сред|четверг|пятниц|суббот|воскресен|в\b)"
    r"|\b(?:на|минус|плюс)\s+(?:тыс|млн|млрд|чел|от|до)\b"
    r"|\(\s*\)"
    r")",
    re.IGNORECASE,
)


def _text_ok_after_scrub(
    text: str, *, min_len: int = 2, had_digits: bool = False
) -> bool:
    t = (text or "").strip()
    if len(t) < min_len:
        return False
    if _ORPHAN_UNIT_ONLY.match(t):
        return False
    if _BROKEN_SCRUB.search(t):
        return False
    # Invented-number scrub removed the only facts → drop the stub.
    if had_digits and not re.search(r"\d", t):
        return False
    # Quantitative fragments that lost their digits (доля / % / рост).
    if not re.search(r"\d", t) and re.search(
        r"\b(?:доля|совокупн\w*|прирост|убыль|рост)\b", t, flags=re.IGNORECASE
    ):
        return False
    return True


def _derived_table_numbers(source: str) -> frozenset[str]:
    """Column sums, means, shares, group rollups, and Fact/Plan deltas derived from tables in Source."""
    from case3.chat_turn import _derived_table_math_norms
    from case3.dashboard_source import (
        _CODE_HEADER,
        _YEAR_HEADER,
        _cell_decimal,
        _find_fact_plan_pair,
        _is_total_row,
        _label_column,
        _markdown_tables,
    )
    from case3.fact_ground import table_grid

    extra: set[str] = set()

    def _add_val(v: Decimal) -> None:
        for d in (v, abs(v)):
            if d == d.to_integral_value():
                s_int = str(int(d))
                extra.add(s_int)
                extra.add(f"{s_int}.0")
                extra.add(f"{s_int},0")
            else:
                for fmt in (f"{d:.1f}", f"{d:.2f}", f"{d:.0f}"):
                    clean = fmt.rstrip("0").rstrip(".") if "." in fmt else fmt
                    extra.add(fmt)
                    extra.add(fmt.replace(".", ","))
                    extra.add(clean)
                    extra.add(clean.replace(".", ","))

    grid = table_grid(source or "")
    for n in (grid.all_row_norms | grid.aggregates | _derived_table_math_norms(source or "")):
        if not n:
            continue
        bare = n[1:] if n.startswith("-") else n
        for tok in (n, bare):
            extra.add(tok)
            extra.add(tok.replace(".", ","))
            if "." not in tok and tok.isdigit():
                extra.add(f"{tok}.0")
                extra.add(f"{tok},0")

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
            vals: list[Decimal] = []
            for row in data:
                v = _cell_decimal(row[col].strip()) if col < len(row) else None
                if v is not None:
                    vals.append(v)
            if len(vals) >= 2:
                total = sum(vals, Decimal(0))
                mean = total / Decimal(len(vals))
                _add_val(total)
                _add_val(mean)
        pair = _find_fact_plan_pair(header)
        if pair is not None:
            fcol, pcol = pair
            fv_sum = Decimal(0)
            pv_sum = Decimal(0)
            for row in data:
                fv = _cell_decimal(row[fcol].strip()) if fcol < len(row) else None
                pv = _cell_decimal(row[pcol].strip()) if pcol < len(row) else None
                if fv is not None and pv is not None:
                    fv_sum += fv
                    pv_sum += pv
                    _add_val(fv - pv)
                    if pv > 0:
                        _add_val(fv * Decimal(100) / pv)
            if pv_sum > 0:
                _add_val(fv_sum * Decimal(100) / pv_sum)
                _add_val(fv_sum - pv_sum)
    return frozenset(extra)


_SPACED_OR_PLAIN_NUMBER = re.compile(
    r"\d{1,3}(?:[\s\u00a0\u202f]+\d{3})+(?:[.,]\d+)?|\d+(?:[.,]\d+)?"
)


def scrub_invented_numbers(
    deck: dict[str, Any],
    *,
    source: str,
    allowed_number_strings: frozenset[str] | None = None,
) -> dict[str, Any]:
    """Drop digit runs not present in Source/charts (LLM heal after IR reject)."""
    source_norm = _norm_ws(source)
    allowed = frozenset(allowed_number_strings or ()) | _derived_table_numbers(source)

    def _scrub_text(text: str, *, chrome: bool = False) -> str:
        scrubbed = False

        def repl(m: re.Match[str]) -> str:
            nonlocal scrubbed
            raw_num = m.group(0)
            compact_num = _compact_spaced_thousands(raw_num)
            if _number_is_allowed(
                compact_num,
                source_norm=source_norm,
                allowed=allowed,
                blob=text or "",
                chrome=chrome,
            ):
                return raw_num
            scrubbed = True
            return ""

        out = _SPACED_OR_PLAIN_NUMBER.sub(repl, text or "")
        out = re.sub(r"\s{2,}", " ", out)
        out = re.sub(r"\s+([,.;:!?])", r"\1", out)
        cleaned = _strip_orphan_units(out.strip()) if scrubbed else out.strip()
        return clean_source_placeholders(cleaned)

    slides_out: list[dict[str, Any]] = []
    for s in deck.get("slides") or []:
        if not isinstance(s, dict):
            continue
        s2 = dict(s)
        for key in (
            "title",
            "subtitle",
            "caption",
            "body",
            "kicker",
            "takeaway",
            "term",
            "definition",
        ):
            if isinstance(s2.get(key), str):
                raw_t = str(s2[key])
                had = bool(_NUMBER_RUN.search(raw_t))
                cleaned = _scrub_text(raw_t, chrome=(key == "kicker"))
                if key in ("takeaway", "subtitle", "body", "caption", "definition"):
                    s2[key] = (
                        cleaned
                        if _text_ok_after_scrub(cleaned, had_digits=had)
                        else ""
                    )
                    if not s2[key]:
                        s2.pop(key, None)
                else:
                    s2[key] = cleaned
        if isinstance(s2.get("bullets"), list):
            kept: list[str] = []
            for b in s2["bullets"]:
                raw_b = str(b)
                if not raw_b.strip():
                    continue
                had = bool(_NUMBER_RUN.search(raw_b))
                cleaned = _scrub_text(raw_b)
                if _text_ok_after_scrub(cleaned, had_digits=had):
                    kept.append(cleaned)
            s2["bullets"] = kept
        if isinstance(s2.get("kpis"), list):
            kpis = []
            for k in s2["kpis"]:
                if not isinstance(k, dict):
                    continue
                k2 = dict(k)
                for key in ("label", "value", "hint", "delta"):
                    if isinstance(k2.get(key), str):
                        k2[key] = _scrub_text(str(k2[key]))
                if _kpi_value_ok(str(k2.get("value") or "")) and str(
                    k2.get("label") or ""
                ).strip():
                    kpis.append(k2)
            s2["kpis"] = kpis
        if isinstance(s2.get("cards"), list):
            cards = []
            for c in s2["cards"]:
                if not isinstance(c, dict):
                    continue
                c2 = dict(c)
                for key in ("title", "body", "kicker"):
                    if isinstance(c2.get(key), str):
                        raw_c = str(c2[key])
                        had = bool(_NUMBER_RUN.search(raw_c))
                        cleaned = _scrub_text(raw_c)
                        if key == "body" and not _text_ok_after_scrub(
                            cleaned, had_digits=had
                        ):
                            c2[key] = ""
                        else:
                            c2[key] = cleaned
                if str(c2.get("title") or "").strip():
                    cards.append(c2)
            s2["cards"] = cards
        if isinstance(s2.get("rows"), list):
            rows = []
            for row in s2["rows"]:
                if not isinstance(row, list):
                    continue
                cells = [_scrub_text(str(cell)) or "—" for cell in row]
                if any(c.strip() and c != "—" for c in cells):
                    rows.append(cells)
            # Drop data rows with no remaining digits (facts were invented).
            if rows:
                header, data = rows[0], rows[1:]
                data = [
                    r
                    for r in data
                    if any(re.search(r"\d", c) for c in r)
                ]
                rows = [header] + data if data else []
            s2["rows"] = rows
        # Demote layouts that lost required payload after scrub → bullets.
        layout = str(s2.get("layout") or "")

        def _demote_to_bullets(slide: dict[str, Any], fallback: str) -> None:
            slide["layout"] = "bullets"
            for key in ("rows", "kpis", "cards", "term", "definition", "body"):
                slide.pop(key, None)
            bullets = slide.get("bullets")
            if not isinstance(bullets, list) or not any(str(b).strip() for b in bullets):
                slide["bullets"] = [str(slide.get("title") or fallback)]

        if layout == "table_hero" and len(s2.get("rows") or []) < 2:
            _demote_to_bullets(s2, "Сводка")
        if layout in ("scorecard", "kpi_row") and len(s2.get("kpis") or []) < 1:
            _demote_to_bullets(s2, "Показатели")
        if layout == "card_row" and len(s2.get("cards") or []) < 2:
            _demote_to_bullets(s2, "Наблюдения")
        if layout == "stat_hero" and len(s2.get("kpis") or []) < 1:
            _demote_to_bullets(s2, "Показатель")
        if layout in ("timeline", "compare") and len(s2.get("cards") or []) < 2:
            _demote_to_bullets(s2, "Шаги")
        if layout == "quote" and not str(s2.get("definition") or "").strip():
            _demote_to_bullets(s2, "Цитата")
        if layout == "callout":
            title = str(s2.get("title") or "Смысл").strip() or "Смысл"
            if not str(s2.get("term") or "").strip():
                s2["term"] = title[:40]
            if not str(s2.get("definition") or "").strip():
                body = str(s2.get("body") or "").strip()
                s2["definition"] = body or title
        slides_out.append(s2)
    out = dict(deck)
    out["slides"] = slides_out
    return out


def scrub_unavailable_media(
    deck: dict[str, Any],
    *,
    allowed_media_ids: frozenset[str] | None,
) -> dict[str, Any]:
    """Demote chart/media slides whose ids have no PNG (Playwright fail → empty media).

    Win desk: charts timeout → LLM still emits cht_01 → DeckIrError killed the deck.
    """
    if allowed_media_ids is None:
        return deck
    allowed = frozenset(allowed_media_ids)

    def _demote_callout(slide: dict[str, Any], fallback: str) -> None:
        title = str(slide.get("title") or fallback).strip() or fallback
        body = (
            str(slide.get("caption") or "").strip()
            or str(slide.get("body") or "").strip()
            or title
        )
        slide["layout"] = "callout"
        slide["title"] = title
        slide["term"] = title[:40]
        slide["definition"] = body[:220]
        for key in (
            "chart_id",
            "media_id",
            "rows",
            "kpis",
            "cards",
            "bullets",
            "caption",
            "body",
        ):
            slide.pop(key, None)

    slides_out: list[dict[str, Any]] = []
    for s in deck.get("slides") or []:
        if not isinstance(s, dict):
            continue
        s2 = dict(s)
        layout = str(s2.get("layout") or "")
        if layout in ("chart_hero", "chart_split"):
            cid = str(s2.get("chart_id") or "").strip()
            if cid not in allowed:
                _demote_callout(s2, "График")
        elif layout in ("media_hero", "media_split"):
            mid = str(s2.get("media_id") or "").strip()
            if mid not in allowed:
                _demote_callout(s2, "Иллюстрация")
        elif layout == "title":
            mid = str(s2.get("media_id") or "").strip()
            if mid and mid not in allowed:
                s2.pop("media_id", None)
        elif layout == "closing":
            mid = str(s2.get("media_id") or "").strip()
            if mid and mid not in allowed:
                s2.pop("media_id", None)
                bullets = s2.get("bullets")
                if not isinstance(bullets, list) or not any(
                    str(b).strip() for b in bullets
                ):
                    s2["bullets"] = [str(s2.get("title") or "Итоги")]
        slides_out.append(s2)
    out = dict(deck)
    out["slides"] = slides_out
    return out


_PLACEHOLDER_SOURCE_RE = re.compile(
    r"(?i)(?:\s*[|·•—–(-]\s*)?"
    r"(?:только\s+)?"
    r"(?:(?:источник(?:и|а)?|цифр(?:ы|а)|чис(?:ла|ло)|данны(?:е|х)|факт(?:ы|ов))\s*(?:—|–|-|:)?\s*)?"
    r"(?:только\s+)?(?:из\s+)?(?:source|соурс(?:а|е)?)\b"
    r"(?:\s*[|·•—–)-])?",
    re.IGNORECASE,
)

_STANDALONE_PLACEHOLDER_RE = re.compile(
    r"(?i)^(?:источник(?:и|а)?|source|соурс(?:а)?|данные|data|только)$",
    re.IGNORECASE,
)


def clean_source_placeholders(text: str) -> str:
    """Strip debug phrases like 'Источник — Source', 'Цифры из Source', 'из Source'."""
    if not text:
        return ""
    cleaned = _PLACEHOLDER_SOURCE_RE.sub("", text)
    cleaned = re.sub(r"\s{2,}", " ", cleaned)
    cleaned = re.sub(r"^\s*[|·•—–:,;\-()]\s*", "", cleaned)
    cleaned = re.sub(r"\s*[|·•—–:,;\-()]\s*$", "", cleaned)
    cleaned = cleaned.strip()
    if _STANDALONE_PLACEHOLDER_RE.match(cleaned):
        return ""
    return cleaned


def _clip_str(val: Any, *, field: str, max_len: int, required: bool = False) -> str:
    if val is None or (isinstance(val, str) and not val.strip()):
        if required:
            raise DeckIrError(f"{field} required")
        return ""
    if not isinstance(val, str):
        raise DeckIrError(f"{field} must be string")
    s = _norm_ws(val)
    s = clean_source_placeholders(s)
    if not s:
        if required:
            if "title" in field:
                s = "Ключевые показатели"
            elif "term" in field:
                s = "Тезис"
            elif "definition" in field:
                s = "Основной вывод"
            else:
                raise DeckIrError(f"{field} required")
        else:
            return ""
    if len(s) <= max_len:
        return s
    # A 4B model overruns the box. Cut the string; do not fail the deck.
    if max_len <= 1:
        return s[:max_len]
    return s[: max_len - 1].rstrip() + "…"


def _parse_bullets(raw: Any, *, required: bool) -> list[str]:
    if not isinstance(raw, list) or not raw:
        if required:
            raise DeckIrError("bullets list required")
        return []
    if len(raw) > _MAX_BULLETS:
        raw = raw[:_MAX_BULLETS]
    out: list[str] = []
    for i, b in enumerate(raw):
        cleaned_b = _clip_str(b, field=f"bullets[{i}]", max_len=_MAX_BULLET, required=False)
        if cleaned_b:
            out.append(cleaned_b)
    if required and not out:
        out.append("Ключевой фактор роста")
    return out


def _parse_cards(raw: Any, *, limit: int = _MAX_CARDS) -> list[dict[str, str]]:
    """Narrative cards. ``card_row`` keeps 3; timeline and compare pass their own cap."""
    if not isinstance(raw, list) or not raw:
        raise DeckIrError("cards required")
    if len(raw) > limit:
        raw = raw[:limit]
    out: list[dict[str, str]] = []
    for i, item in enumerate(raw):
        if not isinstance(item, dict):
            raise DeckIrError(f"cards[{i}] must be object")
        title = _clip_str(
            item.get("title"),
            field=f"cards[{i}].title",
            max_len=_MAX_CARD_TITLE,
            required=True,
        )
        row: dict[str, str] = {"title": title}
        kicker = _clip_str(
            item.get("kicker"),
            field=f"cards[{i}].kicker",
            max_len=_MAX_CARD_KICKER,
        )
        if kicker:
            row["kicker"] = kicker
        body = _clip_str(
            item.get("body"), field=f"cards[{i}].body", max_len=_MAX_CARD_BODY
        )
        if body:
            row["body"] = body
        out.append(row)
    return out


def _parse_kpis(raw: Any, *, allow_delta: bool = False) -> list[dict[str, str]]:
    if not isinstance(raw, list) or not raw:
        raise DeckIrError("kpi_row/scorecard requires non-empty kpis")
    if len(raw) > _MAX_KPI:
        raw = raw[:_MAX_KPI]
    out: list[dict[str, str]] = []
    for i, item in enumerate(raw):
        if not isinstance(item, dict):
            raise DeckIrError(f"kpis[{i}] must be object")
        label = _clip_str(
            item.get("label"),
            field=f"kpis[{i}].label",
            max_len=_MAX_KPI_LABEL,
            required=True,
        )
        value = _clip_str(
            item.get("value"),
            field=f"kpis[{i}].value",
            max_len=_MAX_KPI_VALUE,
            required=True,
        )
        row: dict[str, str] = {"label": label, "value": value}
        hint = _clip_str(
            item.get("hint"), field=f"kpis[{i}].hint", max_len=_MAX_KPI_LABEL
        )
        if hint:
            row["hint"] = hint
        if allow_delta:
            delta = _clip_str(
                item.get("delta"), field=f"kpis[{i}].delta", max_len=_MAX_DELTA
            )
            if delta:
                row["delta"] = delta
            status = item.get("status")
            if isinstance(status, str) and status.strip().lower() in _KPI_STATUS:
                row["status"] = status.strip().lower()
        out.append(row)
    return out


def _parse_table_rows(raw: Any) -> list[list[str]]:
    if not isinstance(raw, list) or len(raw) < 2:
        raise DeckIrError("table_hero requires rows (header + ≥1 data)")
    if len(raw) > _MAX_TABLE_ROWS:
        raw = raw[:_MAX_TABLE_ROWS]
    out: list[list[str]] = []
    width = 0
    for i, row in enumerate(raw):
        if not isinstance(row, list) or not row:
            raise DeckIrError(f"rows[{i}] must be non-empty list")
        trimmed = row[:_MAX_TABLE_COLS]
        # Empty / scrubbed cells soft-fill. scrub_invented_numbers writes "—",
        # but clean_source_placeholders strips a lone dash — do not fail the deck.
        cells = [
            _clip_str(c, field=f"rows[{i}][{j}]", max_len=_MAX_CELL, required=False)
            or "—"
            for j, c in enumerate(trimmed)
        ]
        if i == 0:
            width = len(cells)
        elif len(cells) < width:
            cells = cells + ["—"] * (width - len(cells))
        elif len(cells) > width:
            cells = cells[:width]
        out.append(cells)
    return out


def _parse_slide(
    raw: Any,
    *,
    source_norm: str,
    allowed: frozenset[str],
    seen_ids: set[str],
    allowed_media_ids: frozenset[str] | None,
) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise DeckIrError("slide must be object")

    sid = raw.get("id")
    if not isinstance(sid, str) or not _ID_OK.match(sid):
        raise DeckIrError(f"invalid slide id: {sid!r}")
    if sid in seen_ids:
        raise DeckIrError(f"duplicate slide id: {sid}")
    seen_ids.add(sid)

    layout = raw.get("layout")
    if not isinstance(layout, str) or layout not in SLIDE_LAYOUTS:
        raise DeckIrError(f"unknown or missing layout: {layout!r}")

    title = _clip_str(raw.get("title"), field="title", max_len=_MAX_TITLE, required=True)
    out: dict[str, Any] = {"id": sid, "layout": layout, "title": title}
    kicker = _clip_str(raw.get("kicker"), field="kicker", max_len=_MAX_KICKER)
    if kicker:
        out["kicker"] = kicker
    raw_takeaway = raw.get("takeaway")
    if isinstance(raw_takeaway, str) and "\n" in raw_takeaway.strip():
        # ``VALUE — label`` per line → keep pairs apart; _norm_ws would glue
        # them into one chunk and the cover would show a single KPI card.
        raw_takeaway = " · ".join(
            ln.strip() for ln in raw_takeaway.splitlines() if ln.strip()
        )
    takeaway = _clip_str(raw_takeaway, field="takeaway", max_len=_MAX_TAKEAWAY)
    if takeaway:
        out["takeaway"] = takeaway
    chapter = raw.get("chapter")
    if chapter is not None:
        try:
            ch_i = int(chapter)
        except (TypeError, ValueError) as exc:
            raise DeckIrError("chapter must be int") from exc
        if ch_i < 1 or ch_i > 20:
            raise DeckIrError("chapter out of range")
        out["chapter"] = ch_i
    if raw.get("appendix") is True:
        out["appendix"] = True

    if layout == "title":
        sub = _clip_str(raw.get("subtitle"), field="subtitle", max_len=_MAX_SUBTITLE)
        if sub:
            out["subtitle"] = sub
        mid = raw.get("media_id")
        if isinstance(mid, str) and mid.strip():
            if not _MEDIA_ID_OK.match(mid):
                raise DeckIrError("title media_id must be cht_/fig_/usr_/dia_")
            if allowed_media_ids is not None and mid not in allowed_media_ids:
                raise DeckIrError(f"media_id {mid!r} not available for this run")
            out["media_id"] = mid
    elif layout == "section":
        sub = _clip_str(raw.get("subtitle"), field="subtitle", max_len=_MAX_SUBTITLE)
        if sub:
            out["subtitle"] = sub
    elif layout == "scorecard":
        out["kpis"] = _parse_kpis(raw.get("kpis"), allow_delta=True)
    elif layout == "card_row":
        out["cards"] = _parse_cards(raw.get("cards"))
        sub = _clip_str(raw.get("subtitle"), field="subtitle", max_len=_MAX_SUBTITLE)
        if sub:
            out["subtitle"] = sub
        # Optional gold gate line (Julius VALIDATION GATE / DISCIPLINE).
        gate = _clip_str(raw.get("caption"), field="caption", max_len=_MAX_CAPTION)
        if gate:
            out["caption"] = gate
    elif layout == "callout":
        term = _clip_str(raw.get("term"), field="term", max_len=_MAX_TERM, required=True)
        definition = _clip_str(
            raw.get("definition"),
            field="definition",
            max_len=_MAX_DEFINITION,
            required=True,
        )
        out["term"] = term
        out["definition"] = definition
        body = _clip_str(raw.get("body"), field="body", max_len=220)
        if body:
            out["body"] = body
    elif layout == "quote":
        definition = _clip_str(
            raw.get("definition"),
            field="definition",
            max_len=_MAX_DEFINITION,
            required=True,
        )
        out["definition"] = definition
        term = _clip_str(raw.get("term"), field="term", max_len=_MAX_TERM)
        if term:
            out["term"] = term
        body = _clip_str(raw.get("body"), field="body", max_len=220)
        if body:
            out["body"] = body
    elif layout == "table_hero":
        out["rows"] = _parse_table_rows(raw.get("rows"))
        cap = _clip_str(raw.get("caption"), field="caption", max_len=_MAX_CAPTION)
        if cap:
            out["caption"] = cap
    elif layout in ("chart_hero", "chart_split"):
        cid = raw.get("chart_id")
        if not isinstance(cid, str) or not _CHART_ID_OK.match(cid):
            raise DeckIrError(f"{layout} requires valid chart_id")
        if allowed_media_ids is not None and cid not in allowed_media_ids:
            raise DeckIrError(f"chart_id {cid!r} not available for this run")
        out["chart_id"] = cid
        cap = _clip_str(raw.get("caption"), field="caption", max_len=_MAX_CAPTION)
        if cap:
            out["caption"] = cap
        if layout == "chart_split":
            body = _clip_str(raw.get("body"), field="body", max_len=220)
            bullets = _parse_bullets(raw.get("bullets"), required=False)
            if body:
                out["body"] = body
            if bullets:
                out["bullets"] = bullets
            if not body and not bullets:
                # Soft heal: empty split → hero (caption optional)
                out["layout"] = "chart_hero"
                layout = "chart_hero"
    elif layout in ("media_hero", "media_split"):
        mid = raw.get("media_id")
        if not isinstance(mid, str) or not _MEDIA_ID_OK.match(mid):
            raise DeckIrError(f"{layout} requires valid media_id (cht_/fig_/usr_/dia_)")
        if allowed_media_ids is not None and mid not in allowed_media_ids:
            raise DeckIrError(f"media_id {mid!r} not available for this run")
        out["media_id"] = mid
        cap = _clip_str(raw.get("caption"), field="caption", max_len=_MAX_CAPTION)
        if cap:
            out["caption"] = cap
        if layout == "media_split":
            body = _clip_str(raw.get("body"), field="body", max_len=220)
            bullets = _parse_bullets(raw.get("bullets"), required=False)
            if body:
                out["body"] = body
            if bullets:
                out["bullets"] = bullets
            if not body and not bullets:
                out["layout"] = "media_hero"
                layout = "media_hero"
        if isinstance(raw.get("bullet_node_map"), dict):
            out["bullet_node_map"] = {
                str(k): (
                    [str(x) for x in v] if isinstance(v, list) else str(v)
                )
                for k, v in raw["bullet_node_map"].items()
                if v is not None
            }
    elif layout == "stat_hero":
        raw_kpis = raw.get("kpis")
        if not raw_kpis and (raw.get("value") or raw.get("label")):
            raw_kpis = [
                {
                    "value": raw.get("value"),
                    "label": raw.get("label") or raw.get("title"),
                    "delta": raw.get("delta"),
                    "hint": raw.get("hint"),
                }
            ]
        kpis = _parse_kpis(raw_kpis, allow_delta=True)
        out["kpis"] = kpis[:1]
        out["bullets"] = _parse_bullets(raw.get("bullets"), required=True)
    elif layout == "timeline":
        cards = _parse_cards(raw.get("cards"), limit=6)
        if len(cards) < 2:
            raise DeckIrError("timeline requires at least 2 steps")
        out["cards"] = cards
    elif layout == "compare":
        cards = _parse_cards(raw.get("cards"), limit=2)
        if len(cards) < 2:
            raise DeckIrError("compare requires 2 cards")
        out["cards"] = cards
    elif layout == "kpi_row":
        out["kpis"] = _parse_kpis(raw.get("kpis"), allow_delta=False)
    elif layout in ("bullets", "closing"):
        if layout == "bullets":
            out["bullets"] = _parse_bullets(raw.get("bullets"), required=True)
            # Soft heal: bullets that only echo the title look empty on the deck.
            title_n = _norm_ws(title).casefold()
            echoes = [
                b
                for b in out["bullets"]
                if _norm_ws(str(b)).casefold() == title_n
            ]
            if out["bullets"] and len(echoes) == len(out["bullets"]):
                out["layout"] = "section"
                layout = "section"
                out.pop("bullets", None)
                if not out.get("subtitle"):
                    sub = _clip_str(
                        raw.get("subtitle") or raw.get("kicker"),
                        field="subtitle",
                        max_len=_MAX_SUBTITLE,
                    )
                    if sub:
                        out["subtitle"] = sub
        else:
            # Closing may be hero-bleed (media) or bullet checklist.
            bullets = _parse_bullets(raw.get("bullets"), required=False)
            if bullets:
                out["bullets"] = bullets
            mid = raw.get("media_id")
            if isinstance(mid, str) and mid.strip():
                if not _MEDIA_ID_OK.match(mid):
                    raise DeckIrError("closing media_id must be cht_/fig_/usr_/dia_")
                if allowed_media_ids is not None and mid not in allowed_media_ids:
                    raise DeckIrError(f"media_id {mid!r} not available for this run")
                out["media_id"] = mid
            sub = _clip_str(raw.get("subtitle"), field="subtitle", max_len=_MAX_SUBTITLE)
            if sub:
                out["subtitle"] = sub
            # A title-only close is the decision. Bullets and a photo are optional.

    for blob, chrome in _collect_text_blobs(out):
        _assert_numbers_allowed(
            blob, source_norm=source_norm, allowed=allowed, chrome=chrome
        )

    return out


def _assert_layout_variety(slides: list[dict[str, Any]]) -> None:
    """Reject monotone decks (scorecard spam) — mirrors system_slides anti-monotony."""
    n = len(slides)
    layouts = [str(s.get("layout") or "") for s in slides]
    distinct = {x for x in layouts if x}
    if n >= 8 and len(distinct) < 5:
        raise DeckIrError(
            f"layout variety: need ≥5 distinct layouts when ≥8 slides "
            f"(got {len(distinct)}: {sorted(distinct)})"
        )
    if 6 <= n <= 7 and len(distinct) < 4:
        raise DeckIrError(
            f"layout variety: need ≥4 distinct layouts when 6–7 slides "
            f"(got {len(distinct)}: {sorted(distinct)})"
        )
    # Cap consecutive scorecard / kpi_row
    run = 0
    for lay in layouts:
        if lay in ("scorecard", "kpi_row"):
            run += 1
            if run > 2:
                raise DeckIrError(
                    "layout variety: at most 2 consecutive scorecard/kpi_row slides"
                )
        else:
            run = 0


def _assert_deck_arc(slides: list[dict[str, Any]]) -> None:
    if not slides:
        raise DeckIrError("slides must be a non-empty list")
    if slides[0]["layout"] != "title":
        raise DeckIrError("first slide must be layout title")
    if slides[-1]["layout"] != "closing":
        raise DeckIrError("last slide must be layout closing")
    run = 0
    for s in slides:
        if s["layout"] == "bullets":
            run += 1
            if run > _MAX_CONSECUTIVE_BULLETS:
                raise DeckIrError(
                    f"at most {_MAX_CONSECUTIVE_BULLETS} consecutive bullets slides"
                )
        else:
            run = 0
    _assert_layout_variety(slides)


_WORD4 = re.compile(r"[0-9A-Za-zА-Яа-яЁё]{4,}")


def _word_keys(text: str) -> set[str]:
    return {w.casefold() for w in _WORD4.findall(text or "")}


def _slide_blob(slide: dict[str, Any]) -> str:
    parts: list[str] = []
    for key in (
        "title",
        "subtitle",
        "takeaway",
        "body",
        "definition",
        "term",
        "kicker",
        "caption",
    ):
        val = slide.get(key)
        if isinstance(val, str) and val.strip():
            parts.append(val)
    for bullet in slide.get("bullets") or []:
        if isinstance(bullet, str):
            parts.append(bullet)
    for card in slide.get("cards") or []:
        if isinstance(card, dict):
            parts.extend(
                str(card.get(k) or "") for k in ("title", "body", "kicker")
            )
    for kpi in slide.get("kpis") or []:
        if isinstance(kpi, dict):
            parts.extend(
                str(kpi.get(k) or "") for k in ("value", "label", "hint", "delta")
            )
    return " ".join(p for p in parts if p)


def _source_question(source: str) -> str:
    match = re.search(r"((?:вопрос\s+)?[^.?]{0,70}или нет)", source or "", re.I)
    if not match:
        match = re.search(r"([^.]{8,80}\?)", source or "")
    if not match:
        return ""
    text = match.group(1).strip()
    text = re.sub(r"^.*?вопрос\s+", "", text, flags=re.I)
    text = re.sub(r"\s+или нет\s*$", "", text, flags=re.I).strip(" ,.;:—-")
    if len(text) < 8:
        return ""
    text = text[0].upper() + text[1:]
    if not text.endswith("?"):
        text += "?"
    return text[:_MAX_DEFINITION]


def _yes_no_labels(left: str, right: str) -> bool:
    """«Нанять» / «Не нанимать» is one question, not two columns."""
    a = left.casefold().strip()
    b = right.casefold().strip()
    if a.startswith("не "):
        a, b = b, a[3:].strip()
    elif b.startswith("не "):
        b = b[3:].strip()
    else:
        return False
    if len(a) < 3 or len(b) < 3:
        return False
    return a[:3] == b[:3]


def _negation_pair(left: str, right: str) -> bool:
    a_neg = left.casefold().strip().startswith("не ")
    b_neg = right.casefold().strip().startswith("не ")
    if a_neg == b_neg:
        return False
    ka = {w[:4] for w in _word_keys(left)}
    kb = {w[:4] for w in _word_keys(right)}
    return len(ka & kb) >= 2


def _demote_fake_compare(slide: dict[str, Any], source: str) -> None:
    if slide.get("layout") != "compare":
        return
    cards = [c for c in (slide.get("cards") or []) if isinstance(c, dict)]
    if len(cards) < 2:
        return
    titles = [str(c.get("title") or "") for c in cards]
    kickers = [str(c.get("kicker") or "") for c in cards]
    bodies = [_norm_ws(str(c.get("body") or "")).casefold() for c in cards]
    same_body = bool(bodies[0] and bodies[0] == bodies[1])
    yes_no = _yes_no_labels(kickers[0], kickers[1]) or _yes_no_labels(
        titles[0], titles[1]
    )
    if not _negation_pair(titles[0], titles[1]) and not same_body and not yes_no:
        return
    question = _source_question(source)
    if not question:
        question = str(slide.get("title") or titles[0] or "Вопрос").strip()
        if question and not question.endswith("?"):
            question += "?"
    slide["layout"] = "callout"
    slide["title"] = "Вопрос"
    slide["term"] = "Вопрос"
    slide["definition"] = question[:_MAX_DEFINITION]
    slide.pop("cards", None)
    slide.pop("subtitle", None)
    slide.pop("kicker", None)


def _shorten_scorecard(slide: dict[str, Any]) -> None:
    if slide.get("layout") != "scorecard":
        return
    kpi_nums: set[str] = set()
    for kpi in slide.get("kpis") or []:
        if isinstance(kpi, dict):
            kpi_nums.update(_numbers_in_text(str(kpi.get("value") or "")))
    if len(set(_numbers_in_text(str(slide.get("title") or ""))) & kpi_nums) >= 2:
        kicker = str(slide.get("kicker") or "").strip()
        if kicker.isupper():
            kicker = kicker.capitalize()
        slide["title"] = kicker if kicker and not _numbers_in_text(kicker) else "Сводка"
    if len(set(_numbers_in_text(str(slide.get("subtitle") or ""))) & kpi_nums) >= 2:
        slide.pop("subtitle", None)
    if len(set(_numbers_in_text(str(slide.get("takeaway") or ""))) & kpi_nums) >= 2:
        slide.pop("takeaway", None)
    if str(slide.get("kicker") or "").casefold() == str(slide.get("title") or "").casefold():
        slide.pop("kicker", None)


_FILLER = re.compile(r"без добавлен|факты без", re.IGNORECASE)


def _slide_payload(slide: dict[str, Any]) -> str:
    """Facts on the slide, without the title, so a retitled copy still matches."""
    parts: list[str] = []
    for key in ("subtitle", "body", "definition", "takeaway"):
        val = slide.get(key)
        if isinstance(val, str) and val.strip():
            parts.append(val)
    for bullet in slide.get("bullets") or []:
        if isinstance(bullet, str):
            parts.append(bullet)
    for card in slide.get("cards") or []:
        if isinstance(card, dict):
            parts.append(str(card.get("title") or ""))
            parts.append(str(card.get("body") or ""))
    for kpi in slide.get("kpis") or []:
        if isinstance(kpi, dict):
            parts.append(str(kpi.get("value") or ""))
            parts.append(str(kpi.get("label") or ""))
    for row in slide.get("rows") or []:
        if isinstance(row, list):
            parts.append(" ".join(str(cell) for cell in row))
    return _norm_ws(" ".join(parts)).casefold()


def _echoes_title(text: str, title: str) -> bool:
    left = _norm_ws(text).casefold()
    right = _norm_ws(title).casefold()
    if not left or not right:
        return False
    if left == right:
        return True
    shorter, longer = (left, right) if len(left) <= len(right) else (right, left)
    return len(shorter) >= 12 and shorter in longer


def _trim_slide_copy(slide: dict[str, Any]) -> None:
    """One line per role: drop a repeat, keep kicker + line + one support."""
    title = str(slide.get("title") or "")
    if _echoes_title(str(slide.get("body") or ""), title):
        slide.pop("body", None)
    bullets = [
        b
        for b in (slide.get("bullets") or [])
        if isinstance(b, str) and b.strip() and not _echoes_title(b, title)
    ]
    if bullets:
        slide["bullets"] = bullets
    elif slide.get("bullets"):
        slide.pop("bullets", None)
    subtitle = str(slide.get("subtitle") or "")
    takeaway = str(slide.get("takeaway") or "")
    if subtitle and takeaway:
        sub_w, take_w = _word_keys(subtitle), _word_keys(takeaway)
        if sub_w and take_w and (sub_w <= take_w or take_w <= sub_w or len(sub_w & take_w) >= 2):
            slide.pop("takeaway", None)
    if _echoes_title(str(slide.get("subtitle") or ""), title):
        slide.pop("subtitle", None)
    if _echoes_title(str(slide.get("takeaway") or ""), title):
        slide.pop("takeaway", None)
    if slide.get("layout") in ("chart_hero", "chart_split", "media_hero", "media_split"):
        caption = str(slide.get("caption") or "").strip()
        takeaway = str(slide.get("takeaway") or "").strip()
        if not caption and takeaway:
            slide["caption"] = takeaway
        slide.pop("takeaway", None)
        if slide.get("layout") != "chart_split":
            slide.pop("body", None)


def _fit_deck_content(
    slides: list[dict[str, Any]], source_norm: str
) -> list[dict[str, Any]]:
    """One fact per slide, no invented second side, the ask stands alone."""
    if len(slides) < 3:
        return slides
    for slide in slides:
        _strip_slide_scale(slide, source_norm)
        _trim_slide_copy(slide)
        _demote_fake_compare(slide, source_norm)
        _shorten_scorecard(slide)

    kept: list[dict[str, Any]] = [slides[0]]
    seen_payloads: set[str] = set()
    first_payload = _slide_payload(slides[0])
    if first_payload:
        seen_payloads.add(first_payload)
    for slide in slides[1:-1]:
        blob = _slide_blob(slide)
        if (
            slide.get("layout") == "section"
            and not _numbers_in_text(blob)
            and _FILLER.search(blob)
        ):
            continue
        payload = _slide_payload(slide)
        if payload and payload in seen_payloads:
            continue
        if payload:
            seen_payloads.add(payload)
        kept.append(slide)
    kept.append(slides[-1])

    closing = kept[-1]
    bullets = [b for b in (closing.get("bullets") or []) if isinstance(b, str)]
    if bullets:
        earlier = re.sub(
            r"[^\w\s%+-]",
            "",
            " ".join(_slide_blob(s) for s in kept[:-1]).casefold(),
        )
        fresh = []
        for bullet in bullets:
            flat = re.sub(r"[^\w\s%+-]", "", _norm_ws(bullet).casefold())
            if flat and flat in earlier:
                continue
            fresh.append(bullet)
        if fresh and len(fresh) < len(bullets):
            closing["bullets"] = fresh

    _ground_closing(closing, source_norm)

    question = _source_question(source_norm)
    if question:
        q_words = _word_keys(question)
        already = any(_slide_asks(s, q_words) for s in kept)
        if not already and q_words:
            ask_id = "s_ask"
            used = {str(s.get("id") or "") for s in kept}
            n = 2
            while ask_id in used:
                ask_id = f"s_ask{n}"
                n += 1
            kept.insert(
                -1,
                {
                    "id": ask_id,
                    "layout": "callout",
                    "title": "Вопрос",
                    "term": "Вопрос",
                    "definition": question,
                },
            )
        kept = _one_question(kept, _word_keys(question))
    return kept


_CHROME_WORDS = frozenset({"решение", "дальше", "итог", "вопрос", "совет", "вывод"})


def _strip_unlicensed_scale(text: str, source_norm: str) -> str:
    """Bare ``19`` does not become ``19 млн`` unless Source declares that unit."""

    def repl(match: re.Match[str]) -> str:
        mags = _scaled_magnitudes(match.group(0))
        if any(_number_in_source(mag, source_norm) for mag in mags):
            return match.group(0)
        num = _compact_spaced_thousands(match.group(1)).replace(" ", "")
        family = match.group(2).lower()[:3]
        if num and _number_in_source(num, source_norm) and re.search(
            rf"(?<![А-Яа-яЁёA-Za-z0-9]){re.escape(family)}(?:[а-яё]*\.?)(?![А-Яа-яЁёA-Za-z0-9])",
            source_norm or "",
            re.IGNORECASE,
        ):
            return match.group(0)
        for src in _SCALE_WORD.finditer(source_norm or ""):
            src_num = _compact_spaced_thousands(src.group(1)).replace(" ", "")
            same_num = src_num in {
                num,
                num.replace(",", "."),
                num.replace(".", ","),
            }
            if same_num and src.group(2).lower().startswith(family):
                return match.group(0)
        return match.group(1)

    return _SCALE_WORD.sub(repl, text or "")


def _strip_slide_scale(slide: dict[str, Any], source_norm: str) -> None:
    for key in ("title", "definition", "term", "kicker", "takeaway"):
        if isinstance(slide.get(key), str):
            slide[key] = _strip_unlicensed_scale(slide[key], source_norm)
    kpis = slide.get("kpis")
    if isinstance(kpis, list):
        for kpi in kpis:
            if not isinstance(kpi, dict):
                continue
            for key in ("label", "value", "hint"):
                if isinstance(kpi.get(key), str):
                    kpi[key] = _strip_unlicensed_scale(kpi[key], source_norm)
    bullets = slide.get("bullets")
    if isinstance(bullets, list):
        slide["bullets"] = [
            _strip_unlicensed_scale(b, source_norm) if isinstance(b, str) else b
            for b in bullets
        ]
    cards = slide.get("cards")
    if isinstance(cards, list):
        for card in cards:
            if not isinstance(card, dict):
                continue
            for key in ("value", "label", "body", "title", "text"):
                if isinstance(card.get(key), str):
                    card[key] = _strip_unlicensed_scale(card[key], source_norm)


def _content_words(text: str) -> set[str]:
    return {w for w in _word_keys(text) if w not in _CHROME_WORDS and len(w) >= 5}


def _text_grounded(text: str, source: str) -> bool:
    words = _content_words(text)
    if not words:
        return True
    src = _word_keys(source)
    stems = {w[:4] for w in src}
    hit = sum(1 for w in words if w in src or w[:4] in stems)
    return hit * 2 >= len(words)


def _fact_sentence(source: str) -> str:
    for part in re.split(r"(?<=[.!?])\s+", source or ""):
        flat = _norm_ws(part).strip(" .")
        if re.search(r"\d", flat) and len(flat) > 8:
            return flat[:_MAX_TITLE]
    return ""


def _ground_closing(slide: dict[str, Any], source: str) -> None:
    if slide.get("layout") != "closing":
        return
    fact = _fact_sentence(source)
    title = str(slide.get("title") or "")
    if not _text_grounded(title, source) and fact:
        slide["title"] = fact
    bullets = [b for b in (slide.get("bullets") or []) if isinstance(b, str)]
    kept_b = [b for b in bullets if _text_grounded(b, source)]
    if kept_b:
        slide["bullets"] = kept_b
    elif bullets:
        slide.pop("bullets", None)


def _slide_asks(slide: dict[str, Any], q_words: set[str]) -> bool:
    if not q_words:
        return False
    blob = _word_keys(_slide_blob(slide))
    return len(q_words & blob) >= min(2, len(q_words))


def _one_question(slides: list[dict[str, Any]], q_words: set[str]) -> list[dict[str, Any]]:
    seen = False
    out: list[dict[str, Any]] = []
    for slide in slides:
        if slide.get("layout") == "callout" and _slide_asks(slide, q_words):
            if seen:
                continue
            seen = True
        out.append(slide)
    return out


def _bind_locked_arc(
    slides: list[dict[str, Any]], arc: list[str]
) -> list[dict[str, Any]]:
    """Keep the template's layouts. A missing fact drops the slot.

    A bullet list does not stand in for a chart, table, or scorecard.
    """
    if len(slides) < 3 or len(arc) < 3:
        return slides
    buckets: dict[str, list[dict[str, Any]]] = {}
    for slide in slides:
        buckets.setdefault(str(slide.get("layout") or ""), []).append(slide)
    bound: list[dict[str, Any]] = []
    for layout in arc:
        bucket = buckets.get(layout) or []
        if not bucket:
            continue
        bound.append(bucket.pop(0))
    if len(bound) < 3:
        return slides
    if bound[0].get("layout") != "title":
        return slides
    if bound[-1].get("layout") != "closing":
        return slides
    return bound


def parse_deck_ir(
    data: dict[str, Any] | Any,
    *,
    source: str,
    max_slides: int = _MAX_SLIDES,
    allowed_number_strings: frozenset[str] | None = None,
    allowed_media_ids: frozenset[str] | None = None,
    locked_arc: list[str] | None = None,
) -> dict[str, Any]:
    """Validate and normalize deck IR.

    Raises ``DeckIrError`` on any violation.
    """
    if not isinstance(data, dict):
        raise DeckIrError("deck IR must be an object")

    if data.get("status") == "insufficient_data":
        from case3.input_validation import InsufficientDataError

        msg = str(data.get("message") or "В запросе недостаточно конкретных данных для презентации.")
        raise InsufficientDataError(msg)

    max_slides = max(1, min(int(max_slides), _MAX_SLIDES))
    source_norm = _norm_ws(source)
    allowed = frozenset(allowed_number_strings or ()) | _derived_table_numbers(source)
    media_allow = (
        frozenset(allowed_media_ids) if allowed_media_ids is not None else None
    )

    version = data.get("version", 1)
    try:
        version_i = int(version)
    except (TypeError, ValueError) as exc:
        raise DeckIrError("version must be int") from exc
    if version_i != 1:
        raise DeckIrError("unsupported deck IR version")

    aspect = data.get("aspect") or "16:9"
    if aspect != "16:9":
        raise DeckIrError("aspect must be 16:9")

    pid = normalize_palette_id(str(data.get("palette") or "atelier"))
    if pid == "auto":
        pid = "atelier"

    language = data.get("language") or "ru"
    if not isinstance(language, str) or not language.strip():
        language = "ru"
    else:
        language = language.strip()[:16]

    slides_raw = data.get("slides")
    if not isinstance(slides_raw, list) or not slides_raw:
        raise DeckIrError("slides must be a non-empty list")
    if len(slides_raw) > max_slides:
        raise DeckIrError(f"at most {max_slides} slides")
    if len(slides_raw) < 3:
        raise DeckIrError("at least 3 slides (title … closing)")

    prepared: list[Any] = []
    for raw_slide in slides_raw:
        if not isinstance(raw_slide, dict):
            continue
        title = str(raw_slide.get("title") or "").strip()
        if not title:
            kick = str(raw_slide.get("kicker") or "").strip()
            if not kick:
                continue
            raw_slide = {**raw_slide, "title": kick}
        prepared.append(raw_slide)
    if len(prepared) < 3:
        raise DeckIrError("at least 3 slides (title … closing)")

    seen: set[str] = set()
    slides = [
        _parse_slide(
            s,
            source_norm=source_norm,
            allowed=allowed,
            seen_ids=seen,
            allowed_media_ids=media_allow,
        )
        for s in prepared
    ]
    slides = _fit_deck_content(slides, source_norm)
    if locked_arc:
        slides = _bind_locked_arc(slides, list(locked_arc))
    _assert_deck_arc(slides)

    return {
        "version": 1,
        "aspect": "16:9",
        "palette": pid,
        "language": language,
        "slides": slides,
    }
