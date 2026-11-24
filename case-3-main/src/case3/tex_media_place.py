"""Scatter trailing gallery dumps / EOF media piles into prose sections."""

from __future__ import annotations

import re
from typing import Any

# Heading command + title; gallery decided by _is_gallery_title.
_HEADING = re.compile(
    r"\\((?:sub)*section)\*?\{([^{}]*)\}"
)
_GALLERY_TITLE = re.compile(
    r"(?i)("
    r"визуализац|иллюстрац|"
    r"(?:^|[\s\d.:]*)графики(?:\b|$)|(?:^|[\s\d.:]*)рисунки(?:\b|$)|"
    r"\bfigures?\b|\bcharts?\b|visuali[sz]ation|"
    r"приложение.{0,80}визуал|детализированн.{0,60}визуал"
    r")"
)
_SECTION_OPEN = _HEADING


def _is_gallery_title(title: str) -> bool:
    t = (title or "").strip()
    if not t:
        return False
    return bool(_GALLERY_TITLE.search(t))


def _find_gallery_heading(body: str) -> re.Match[str] | None:
    for m in _HEADING.finditer(body or ""):
        if _is_gallery_title(m.group(2)):
            return m
    return None
_SLOT = re.compile(
    r"(?m)^[ \t]*%CASE3_(FIG|CHART|DIAG):([a-z][a-z0-9_]{0,31})%[^\n]*\r?\n?"
)
_SLOT_ANY = re.compile(
    r"%CASE3_(FIG|CHART|DIAG):([a-z][a-z0-9_]{0,31})%"
)
_FIGURE_ENV = re.compile(
    r"\\begin\{figure\*?\}.*?\\end\{figure\*?\}",
    re.S,
)
_CAPTION = re.compile(r"\\caption\{([^{}]*)\}")
_TOKEN = re.compile(r"[A-Za-zА-Яа-яЁё0-9]{3,}")

# Soft domain bridges: caption «заводской цех» ↔ section «Промышленность».
_SYNONYM_GROUPS: tuple[frozenset[str], ...] = (
    frozenset({"промышл", "завод", "цех", "зпк", "производ", "робот", "станк"}),
    frozenset({"сельск", "агро", "дроны", "дрон", "полев", "ферм", "посев", "урожа"}),
    frozenset({"банк", "финанс", "кредит", "roi", "платёж", "платеж"}),
    frozenset({"логист", "склад", "транспорт", "постав", "цеп"}),
    frozenset({"образован", "школ", "вуз", "универ", "обучен", "кадр"}),
    frozenset({"энерг", "жкх", "электр", "тепл", "сет"}),
    frozenset({"госсектор", "госуслуг", "гос ", "чинов", "портал"}),
    frozenset({"рынок", "бюджет", "динамик", "прогноз", "доля"}),
)


def _tokens(text: str) -> set[str]:
    raw = {t.lower() for t in _TOKEN.findall(text or "")}
    # Light stem: keep prefixes so «промышленности» ↔ «Промышленность».
    out: set[str] = set(raw)
    for t in raw:
        if len(t) >= 6:
            out.add(t[:6])
        if len(t) >= 8:
            out.add(t[:8])
    # Synonym expansion via stem prefixes.
    expanded: set[str] = set(out)
    for tok in list(out):
        for group in _SYNONYM_GROUPS:
            if any(tok.startswith(g) or g.startswith(tok[: max(4, min(6, len(tok)))]) for g in group):
                expanded |= group
                break
            # also: tok contains group stem
            if any(g in tok for g in group if len(g) >= 4):
                expanded |= group
                break
    return expanded


def _score(hint: str, section_title: str, section_body: str) -> float:
    ht = _tokens(hint)
    if not ht:
        return 0.0
    st = _tokens(section_title) | _tokens(section_body[:600])
    if not st:
        return 0.0
    overlap = ht & st
    # Title matches weigh more than body prose.
    title_hit = len(ht & _tokens(section_title))
    return (len(overlap) + 2.0 * title_hit) / max(len(ht), 1)


def media_slots_pile_at_eof(tex: str, *, frac: float = 0.20, min_slots: int = 3) -> bool:
    """True when ≥50% of FIG/CHART slots sit in the last ``frac`` of the body."""
    mdoc = re.search(
        r"(\\begin\{document\})([\s\S]*?)(\\end\{document\})",
        tex or "",
    )
    if not mdoc:
        return False
    body = mdoc.group(2)
    matches = list(_SLOT_ANY.finditer(body))
    if len(matches) < min_slots:
        return False
    cut = int(len(body) * (1.0 - frac))
    in_tail = sum(1 for m in matches if m.start() >= cut)
    return in_tail >= max(min_slots, (len(matches) + 1) // 2)


def _extract_slots_from_region(
    region: str,
) -> tuple[list[tuple[str, str, str]], str]:
    """Pull (kind, id, hint) from bare slots + figure-wrapped slots; return cleaned region.

    Returns slots and the region with those media blocks removed (for callers that
    keep a prefix); gallery path discards the region entirely.
    """
    slots: list[tuple[str, str, str]] = []
    # Prefer subsection title immediately above each slot as hint.
    last_sub = ""
    # First peel figure environments that contain a slot.
    def fig_repl(m: re.Match[str]) -> str:
        nonlocal last_sub
        block = m.group(0)
        sm = _SLOT_ANY.search(block)
        if not sm:
            return block
        kind, mid = sm.group(1).upper(), sm.group(2)
        cap_m = _CAPTION.search(block)
        hint = (cap_m.group(1) if cap_m else last_sub) or last_sub
        slots.append((kind, mid, hint))
        return ""

    # Track subsection titles while walking lines for bare slots.
    # Process figures first so we don't double-count inner slot lines.
    region_wo_figs = _FIGURE_ENV.sub(fig_repl, region)

    kept: list[str] = []
    for ln in region_wo_figs.splitlines(keepends=True):
        sm = re.match(r"\\subsection\*?\{([^{}]*)\}", ln.strip())
        if sm:
            last_sub = sm.group(1)
            # Drop gallery-only subsection titles; keep others if any.
            if _is_gallery_title(last_sub):
                continue
            kept.append(ln)
            continue
        sm2 = _SLOT.match(ln)
        if sm2:
            kind, mid = sm2.group(1).upper(), sm2.group(2)
            slots.append((kind, mid, last_sub))
            continue
        # Drop leftover bold "График N:" labels from dumps.
        if re.match(r"^[ \t]*\\textbf\{График\b", ln):
            continue
        kept.append(ln)
    return slots, "".join(kept)


def _split_prose_parts(prose: str) -> list[dict[str, str]]:
    parts: list[dict[str, str]] = []
    idx = 0
    for m in _SECTION_OPEN.finditer(prose):
        if m.start() > idx:
            if not parts:
                parts.append(
                    {"title": "", "cmd": "", "body": prose[idx : m.start()]}
                )
            else:
                parts[-1]["body"] += prose[idx : m.start()]
        parts.append(
            {
                "title": m.group(2),
                "cmd": m.group(0),
                "body": "",
            }
        )
        idx = m.end()
    if not parts:
        parts.append({"title": "", "cmd": "", "body": prose})
    else:
        parts[-1]["body"] += prose[idx:]
    return parts


def _place_slots(
    parts: list[dict[str, str]],
    slots: list[tuple[str, str, str]],
    cap_by_id: dict[str, str],
) -> None:
    content_idxs = [i for i, p in enumerate(parts) if p["title"]]
    if not content_idxs:
        # Nowhere to put — append into last part body.
        inject = "".join(f"%CASE3_{k}:{i}%\n" for k, i, _ in slots)
        if parts:
            parts[-1]["body"] = parts[-1]["body"].rstrip() + "\n\n" + inject + "\n"
        return

    used: set[int] = set()
    placements: list[tuple[int, str, str]] = []
    for kind, mid, hint in slots:
        caption = cap_by_id.get(mid, "")
        score_hint = f"{hint} {caption}".strip()
        best_i = content_idxs[0]
        best_s = -1.0
        for i in content_idxs:
            s = _score(score_hint, parts[i]["title"], parts[i]["body"])
            if i in used:
                s -= 0.15
            if s > best_s:
                best_s = s
                best_i = i
        used.add(best_i)
        placements.append((best_i, kind, mid))

    by_part: dict[int, list[str]] = {}
    for i, kind, mid in placements:
        by_part.setdefault(i, []).append(f"%CASE3_{kind}:{mid}%")

    for i, lines in by_part.items():
        body = parts[i]["body"]
        insert_at = None
        seen_text = False
        acc = 0
        for ln in body.splitlines(keepends=True):
            acc += len(ln)
            if ln.strip():
                seen_text = True
            elif seen_text:
                insert_at = acc
                break
        block = "\n" + "\n".join(lines) + "\n\n"
        if insert_at is None:
            parts[i]["body"] = body.rstrip() + "\n" + block
        else:
            parts[i]["body"] = body[:insert_at] + block + body[insert_at:]


def _rebuild(tex: str, mdoc: re.Match[str], parts: list[dict[str, str]]) -> str:
    begin, end = mdoc.group(1), mdoc.group(3)
    new_prose: list[str] = []
    for p in parts:
        if p["cmd"]:
            new_prose.append(p["cmd"] + "\n")
        new_prose.append(p["body"])
    new_body = "".join(new_prose)
    if not new_body.endswith("\n"):
        new_body += "\n"
    return tex[: mdoc.start()] + begin + new_body + end + tex[mdoc.end() :]


def redistribute_gallery_slots(
    tex: str,
    *,
    figures: list[dict[str, Any]] | None = None,
    charts: list[dict[str, Any]] | None = None,
    diagrams: list[dict[str, Any]] | None = None,
) -> str:
    """Move slots out of trailing gallery / EOF piles into matching prose sections.

    Win desk 081536: ``\\section{Визуализация}`` / ``Иллюстрации``.
    Win desk 082722: ``\\section{Приложение: … визуализации}`` + ``\\subsection{Графики}``
    with slots wrapped in ``figure`` envs.
    """
    if not tex:
        return tex

    mdoc = re.search(
        r"(\\begin\{document\})([\s\S]*?)(\\end\{document\})",
        tex,
    )
    if not mdoc:
        return tex
    body = mdoc.group(2)

    cap_by_id: dict[str, str] = {}
    for f in figures or []:
        if isinstance(f, dict) and f.get("id"):
            cap_by_id[str(f["id"])] = str(f.get("caption") or "")
    for c in charts or []:
        if isinstance(c, dict) and c.get("id"):
            cap_by_id[str(c["id"])] = str(c.get("caption") or "")
    for d in diagrams or []:
        if isinstance(d, dict) and d.get("id"):
            cap_by_id[str(d["id"])] = str(d.get("title") or d.get("caption") or "")

    gm = _find_gallery_heading(body)
    eof_pile = media_slots_pile_at_eof(tex)

    if not gm and not eof_pile:
        return tex

    if gm:
        prose = body[: gm.start()]
        gallery = body[gm.start() :]
        slots, kept_tail = _extract_slots_from_region(gallery)
        if not slots:
            return tex
        # Strip empty gallery section/subsection shells; keep any real prose/sections.
        cleaned_tail = re.sub(
            r"\\(?:sub)*section\*?\{[^{}]*\}[ \t]*\r?\n?",
            "",
            kept_tail,
        ).strip()
        if cleaned_tail:
            prose = prose + kept_tail
    else:
        # EOF pile: relocate only slots in the last 20% of the body.
        cut = int(len(body) * 0.80)
        # Snap cut back to start of a trailing media run if possible.
        tail = body[cut:]
        first_slot = _SLOT_ANY.search(tail)
        if not first_slot:
            return tex
        abs_start = cut + first_slot.start()
        # Include a preceding \begin{figure} if the slot is inside one.
        pre = body[:abs_start]
        fig_open = pre.rfind(r"\begin{figure")
        fig_close = pre.rfind(r"\end{figure")
        if fig_open > fig_close:
            abs_start = fig_open
        prose = body[:abs_start]
        gallery = body[abs_start:]
        slots, kept_tail = _extract_slots_from_region(gallery)
        if not slots:
            return tex
        # Keep non-media residue after the pile (rare).
        prose = prose + kept_tail

    # Drop empty trailing gallery-only section cmd left in prose (title with no body).
    prose = re.sub(
        r"\n?\\(?:sub)*section\*?\{[^}]*\}[ \t]*\n?\Z",
        "\n",
        prose.rstrip() + "\n",
    )

    parts = _split_prose_parts(prose)
    # Prefer non-gallery content parts for placement.
    for p in parts:
        if p["title"] and _is_gallery_title(p["title"]):
            p["title"] = ""  # exclude from content_idxs scoring

    _place_slots(parts, slots, cap_by_id)
    # Remove parts that were gallery headings with empty bodies after extract.
    cleaned: list[dict[str, str]] = []
    for p in parts:
        if p["title"] == "" and p["cmd"] and _is_gallery_title(
            re.sub(r"^\\(?:sub)*section\*?\{|\}$", "", p["cmd"])
        ):
            if not (p["body"] or "").strip():
                continue
        # Also drop if cmd title is gallery (title cleared above).
        hm = _HEADING.match(p["cmd"]) if p["cmd"] else None
        if hm and _is_gallery_title(hm.group(2)) and not (p["body"] or "").strip():
            continue
        cleaned.append(p)
    return _rebuild(tex, mdoc, cleaned)
