"""Infer a narrative beat plan when no deck structure template is selected.

Keeps gallery structures as optional DNA; freeform runs get a Source+media
driven skeleton so LLM decks do not collapse to scorecard spam.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Sequence

from case3.deck_structure import normalize_structure_id, structure_meta

# mode → default visual pack (Julius pairs)
_MODE_PACK: dict[str, str] = {
    "board_update": "board",
    "performance": "signal",
    "qbr": "relay",
    "survey": "voltage",
    "investor": "ink",
    "launch": "botanical",
    "campaign": "atelier",
    "workshop": "studio",
    "hire": "board",
    "council": "studio",
    "quarter": "botanical",
    "general": "atelier",
}

_MODE_ARCS: dict[str, list[str]] = {
    "board_update": [
        "title",
        "scorecard",
        "table_hero",
        "chart_hero",
        "table_hero",
        "card_row",
        "callout",
        "closing",
    ],
    "performance": [
        "title",
        "chart_hero",
        "chart_split",
        "table_hero",
        "scorecard",
        "card_row",
        "callout",
        "closing",
    ],
    "qbr": [
        "title",
        "section",
        "scorecard",
        "card_row",
        "chart_hero",
        "section",
        "callout",
        "closing",
    ],
    "survey": [
        "title",
        "callout",
        "scorecard",
        "card_row",
        "quote",
        "callout",
        "closing",
    ],
    "investor": [
        "title",
        "stat_hero",
        "chart_hero",
        "bullets",
        "callout",
        "closing",
    ],
    "council": [
        "title",
        "callout",
        "scorecard",
        "callout",
        "closing",
    ],
    "quarter": [
        "title",
        "section",
        "card_row",
        "section",
        "table_hero",
        "callout",
        "closing",
    ],
    "launch": [
        "title",
        "callout",
        "card_row",
        "media_hero",
        "table_hero",
        "scorecard",
        "card_row",
        "closing",
    ],
    "campaign": [
        "title",
        "compare",
        "table_hero",
        "chart_hero",
        "card_row",
        "callout",
        "closing",
    ],
    "workshop": [
        "title",
        "timeline",
        "card_row",
        "card_row",
        "section",
        "table_hero",
        "bullets",
        "closing",
    ],
    "hire": [
        "title",
        "callout",
        "compare",
        "bullets",
        "scorecard",
        "quote",
        "section",
        "closing",
    ],
    "general": [
        "title",
        "scorecard",
        "callout",
        "table_hero",
        "card_row",
        "section",
        "bullets",
        "closing",
    ],
}


SLIDE_TARGET_MIN = 6
SLIDE_TARGET_MAX = 24

_NARRATIVE_FILLERS = (
    "callout",
    "card_row",
    "table_hero",
    "section",
    "bullets",
)


def clamp_slide_target(raw: int | None) -> int | None:
    """User wish for deck length. ``None`` keeps the automatic 6–12 band."""
    if raw is None:
        return None
    try:
        n = int(raw)
    except (TypeError, ValueError):
        return None
    return max(SLIDE_TARGET_MIN, min(SLIDE_TARGET_MAX, n))


@dataclass(frozen=True)
class BeatPlan:
    mode: str
    pack_hint: str
    target_slides: int
    beats: tuple[str, ...]
    rationale: str
    from_structure: bool = False


def _blob(*parts: str) -> str:
    return " ".join(p for p in parts if p).lower()


def _score_modes(
    text: str,
    *,
    n_charts: int,
    n_figs: int,
    n_dias: int,
) -> dict[str, float]:
    scores = {m: 0.0 for m in _MODE_ARCS}
    # Keyword / shape signals (RU+EN)
    rules: list[tuple[str, Sequence[str], float]] = [
        (
            "board_update",
            (
                "board",
                "совет",
                "ask:",
                "approve",
                "утверд",
                "nrr",
                "burn",
                "runway",
                "arr ",
            ),
            2.0,
        ),
        (
            "hire",
            (
                "hiring",
                "найм",
                "нанять",
                "hire",
                "headcount",
                "оффер",
                "вакан",
            ),
            3.0,
        ),
        (
            "performance",
            (
                "roas",
                "spend",
                "cac",
                "attributed",
                "канал",
                "campaign",
                "кампан",
                "media spend",
                "pipeline /",
            ),
            2.2,
        ),
        (
            "qbr",
            ("qbr", "quarterly", "квартал", "q3", "q4", "reallocate", "перераспред"),
            2.0,
        ),
        (
            "survey",
            (
                "survey",
                "опрос",
                "csat",
                "nps",
                "feedback",
                "респондент",
                "friction",
                "% love",
                "satisfaction",
            ),
            2.4,
        ),
        (
            "investor",
            ("investor", "инвестор", "arr", "series", "runway", "fundraising"),
            1.8,
        ),
        (
            "launch",
            ("launch", "запуск", "product launch", "waitlist", "ритуал", "vesper"),
            2.0,
        ),
        (
            "campaign",
            ("weekly", "this week", "creative", "pause", "scale", "roas", "cpa"),
            1.6,
        ),
        (
            "workshop",
            ("workshop", "facilitat", "agenda", "упражнен", "ретро", "exercise"),
            2.2,
        ),
    ]
    for mode, keys, w in rules:
        hits = sum(1 for k in keys if k in text)
        if hits:
            scores[mode] += w * hits

    # Media shapes
    if n_charts >= 2:
        scores["performance"] += 3.0
        scores["qbr"] += 1.5
        scores["campaign"] += 1.0
    elif n_charts == 1:
        scores["performance"] += 1.5
        scores["investor"] += 1.0
        scores["campaign"] += 1.0
        scores["general"] += 0.5

    if n_figs >= 1:
        scores["launch"] += 2.5
    if n_dias >= 1:
        scores["workshop"] += 1.5
        scores["general"] += 1.0

    # Percent-heavy survey fingerprint
    pcts = len(re.findall(r"\b\d{1,3}\s*%", text))
    if pcts >= 3 and n_charts <= 1:
        scores["survey"] += 3.0

    # Thin source → shorter general arc
    if len(text) < 280 and n_charts == 0 and n_figs == 0:
        scores["general"] += 2.0
        scores["campaign"] += 1.0

    scores["general"] += 0.1  # never empty winner
    return scores


def _trim_beats(
    beats: list[str],
    *,
    n_charts: int,
    n_figs: int,
    n_dias: int,
    target: int,
) -> list[str]:
    """Drop media layouts the run cannot fill; keep title/closing; hit target length."""
    out: list[str] = []
    charts_left = n_charts
    figs_left = n_figs + n_dias
    for b in beats:
        if b in ("chart_hero", "chart_split"):
            if charts_left <= 0:
                # substitute a table or callout so variety holds
                out.append("table_hero" if "table_hero" not in out[-2:] else "callout")
                continue
            charts_left -= 1
        if b in ("media_hero", "media_split"):
            if figs_left <= 0:
                out.append("callout")
                continue
            figs_left -= 1
        out.append(b)

    # Ensure bookends
    if not out or out[0] != "title":
        out = ["title", *out]
    if out[-1] != "closing":
        out = [*out, "closing"]

    # Shrink toward target (prefer dropping middle duplicates)
    while len(out) > target and len(out) > 6:
        # drop a duplicate table_hero / card_row from the middle
        dropped = False
        for layout in ("table_hero", "card_row", "bullets", "section"):
            idxs = [i for i, x in enumerate(out) if x == layout and 0 < i < len(out) - 1]
            if len(idxs) >= 2:
                del out[idxs[-1]]
                dropped = True
                break
        if not dropped:
            # drop middle callout
            mid = len(out) // 2
            if out[mid] not in ("title", "closing"):
                del out[mid]
            else:
                break

    # Grow if too short
    fillers = ["callout", "card_row", "table_hero", "section", "bullets"]
    fi = 0
    while len(out) < max(6, min(target, 15)):
        insert_at = max(1, len(out) - 1)
        out.insert(insert_at, fillers[fi % len(fillers)])
        fi += 1
        if fi > 12:
            break

    return out


def _expand_signature(
    beats: list[str],
    target: int,
    *,
    dna: Sequence[str],
) -> list[str]:
    """Repeat the template's narrative layouts until ``target``.

    Charts and photos stay as the base arc placed them — extra slots are
    sections, tables, cards, callouts, and bullets so a long Source has
    room without fake media.
    """
    out = list(beats)
    fillers = [
        b
        for b in dna
        if b
        not in (
            "title",
            "closing",
            "chart_hero",
            "chart_split",
            "media_hero",
            "media_split",
        )
    ]
    if not fillers:
        fillers = list(_NARRATIVE_FILLERS)
    fi = 0
    spins = 0
    cap = max(SLIDE_TARGET_MIN, min(int(target), SLIDE_TARGET_MAX))
    while len(out) < cap and spins < cap * 4:
        layout = fillers[fi % len(fillers)]
        fi += 1
        spins += 1
        prev = out[-2] if len(out) >= 2 else ""
        prev2 = out[-3] if len(out) >= 3 else ""
        content_n = max(0, len(out) - 1)
        if cap >= 16 and content_n % 6 == 0 and prev != "section":
            layout = "section"
        if layout == prev == prev2:
            continue
        if layout == "bullets" and prev == "bullets" and prev2 == "bullets":
            continue
        if (
            layout in ("scorecard", "kpi_row")
            and prev in ("scorecard", "kpi_row")
            and prev2 in ("scorecard", "kpi_row")
        ):
            continue
        out.insert(-1, layout)
    if out[0] != "title":
        out.insert(0, "title")
    if out[-1] != "closing":
        out.append("closing")
    return out[:SLIDE_TARGET_MAX]


def _reserve_media_beats(
    beats: list[str],
    *,
    n_charts: int,
    n_figs: int,
) -> list[str]:
    """Keep chart and photo slots inside the target length.

    Swaps filler layouts so ``ensure_deck_charts`` does not append a spare
    slide, and so attached ``usr_*`` photos have a ``media_*`` beat to fill.
    """
    out = list(beats)
    need: list[str] = []
    if n_charts > 0 and not any(b in ("chart_hero", "chart_split") for b in out):
        need.append("chart_hero")
    have_media = sum(1 for b in out if b in ("media_hero", "media_split"))
    for i in range(max(0, min(n_figs, 5) - have_media)):
        need.append("media_hero" if i % 2 == 0 else "media_split")
    fillers = {"card_row", "callout", "bullets", "table_hero", "section", "scorecard"}
    for layout in need:
        idx = next(
            (
                i
                for i in range(len(out) - 2, 0, -1)
                if out[i] in fillers
            ),
            None,
        )
        if idx is not None:
            out[idx] = layout
    return out


def plan_beats(
    *,
    source: str,
    intent: str = "",
    chart_ids: Sequence[str] | None = None,
    figure_ids: Sequence[str] | None = None,
    diagram_ids: Sequence[str] | None = None,
    structure_id: str | None = None,
    target_slides: int | None = None,
) -> BeatPlan:
    """Build a layout skeleton from structure template or Source+media signals."""
    charts = [str(x) for x in (chart_ids or []) if str(x).strip()]
    figs = [str(x) for x in (figure_ids or []) if str(x).strip()]
    dias = [str(x) for x in (diagram_ids or []) if str(x).strip()]
    sid = normalize_structure_id(structure_id)

    if sid:
        meta = structure_meta(sid) or {}
        arc = [str(x) for x in (meta.get("arc") or []) if str(x).strip()]
        if not arc:
            arc = list(_MODE_ARCS.get(sid, _MODE_ARCS["general"]))
        pack = str(meta.get("default_pack") or _MODE_PACK.get(sid, "atelier"))
        slides_range = meta.get("slides") or [8, 12]
        try:
            lo, hi = int(slides_range[0]), int(slides_range[-1])
        except (TypeError, ValueError, IndexError):
            lo, hi = 8, 12
        media_n = len(charts) + len(figs) + len(dias)
        text_len = len(_blob(source, intent))
        if media_n >= 2 or text_len >= 600:
            raw_t = len(arc)
        elif media_n >= 1 or text_len >= 280:
            raw_t = min(len(arc), max(10, lo + 2))
        else:
            raw_t = max(8, lo)
        target = max(lo, min(hi, raw_t))
        rationale = f"structure template {sid}"
        from_structure = True
        mode = sid
    else:
        text = _blob(source, intent)
        scores = _score_modes(
            text, n_charts=len(charts), n_figs=len(figs), n_dias=len(dias)
        )
        mode = max(scores, key=lambda m: scores[m])
        arc = list(_MODE_ARCS[mode])
        pack = _MODE_PACK[mode]
        # Richer media → longer deck
        richness = len(charts) + len(figs) + len(dias) + (1 if len(text) > 600 else 0)
        target = 10 if richness >= 2 else (8 if richness >= 1 or len(text) > 400 else 7)
        target = max(6, min(12, target))
        top = sorted(scores.items(), key=lambda kv: -kv[1])[:3]
        rationale = (
            f"inferred mode={mode} from Source/media; "
            f"scores=" + ", ".join(f"{m}:{s:.1f}" for m, s in top)
        )
        from_structure = False

    asked = clamp_slide_target(target_slides)
    if asked is not None:
        target = asked
        rationale = (
            f"{rationale}; user target {asked} slides "
            "(drop beats if Source lacks distinct facts)"
        )
    beats = _trim_beats(
        arc, n_charts=len(charts), n_figs=len(figs), n_dias=len(dias), target=target
    )
    if asked is not None and len(beats) < asked:
        beats = _expand_signature(beats, asked, dna=arc)
    beats = _reserve_media_beats(
        beats, n_charts=len(charts), n_figs=len(figs) + len(dias)
    )
    return BeatPlan(
        mode=mode if not from_structure else sid,
        pack_hint=pack,
        target_slides=len(beats),
        beats=tuple(beats),
        rationale=rationale,
        from_structure=from_structure,
    )


def format_beat_overlay(plan: BeatPlan) -> str:
    """Layout menu for the model. A chosen template locks the skeleton."""
    hint = " → ".join(plan.beats)
    if plan.from_structure:
        return "\n".join(
            [
                "# BEAT PLAN (locked template skeleton)",
                "",
                f"**Target length:** {plan.target_slides} slides. "
                "Drop a beat when Source has no fact for it. "
                "Do not invent facts to hit the number.",
                f"**Visual pack:** `{plan.pack_hint}` — this template's only colors.",
                f"**Template:** `{plan.mode}`.",
                "",
                "Use these layouts in this order. "
                "Do not replace `chart_hero`, `chart_split`, `table_hero`, "
                "`compare`, `stat_hero`, `scorecard`, `quote`, or `card_row` "
                "with `bullets`.",
                f"`{hint}`",
                "",
            ]
        )
    lines = [
        "# BEAT PLAN (length + menu — you choose the layouts)",
        "",
        f"**Target length:** {plan.target_slides} slides. "
        "Shorter is correct when Source has fewer distinct facts. "
        "Do not invent facts to hit the number.",
        f"**Visual pack:** `{plan.pack_hint}` — colors, type, and chrome only. "
        "The pack does not decide which layout to use.",
        f"**Situation hint:** `{plan.mode}`. A hint, not a script. "
        f"Why it came up: {plan.rationale}",
        "",
        "Open with `title`. Close with `closing`. Between them, pick a layout only when "
        "Source has that shape:",
        "",
        "| Layout | Use when Source has | Skip when |",
        "|--------|---------------------|-----------|",
        "| `stat_hero` | one number that should dominate, plus 2–4 sentences | several equal KPIs |",
        "| `scorecard` | 3–4 comparable KPIs, each with delta or a hint sentence | a single hero number |",
        "| `compare` | exactly two opposing calls (scale/pause, win/miss, love/friction) | three or more peers |",
        "| `timeline` | ordered steps or timeboxes | an unordered list |",
        "| `table_hero` | a real grid; status cell may be `Масштаб` / `Пауза` / `Держать` | a sentence |",
        "| `chart_hero` / `chart_split` | a real chart id | no chart |",
        "| `card_row` | three parallel items, each a full sentence | two items (`compare`) or one (`callout`) |",
        "| `callout` | one named claim (term + definition) | a voice line from a person |",
        "| `quote` | a sentence someone actually said, plus who said it | a claim with no speaker |",
        "| `section` | a real chapter break | you would be inserting one every other slide |",
        "| `media_*` | a real photo or diagram id | no media |",
        "| `bullets` | 3–5 clauses that are not a table, cards, or a comparison | a richer layout fits |",
        "",
        "If several shapes are present, this order is a reasonable default. "
        "Reorder or drop any beat that Source cannot fill:",
        f"`{hint}`",
        "",
        "Rules:",
        "1. Do not emit a layout because the hint or the pack names it.",
        "2. One claim per slide. A repeated layout is a new claim, not the same sentence again.",
        "3. Titles state the insight. Chart slides need an insight `caption`. "
        "Closing: `VALUE — label` only when Source has that number, plus 3 bullets.",
        "4. Numbers ⊆ Source / chart captions. ≥5 distinct layouts when ≥8 slides. "
        "At most 2 scorecards in a row.",
        "5. Every photo or diagram id you were given should appear if it belongs on a slide. "
        "Do not invent ids.",
    ]
    return "\n".join(lines)


def maybe_apply_pack_hint(
    *,
    structure_id: str | None,
    current_pack: str | None,
    plan: BeatPlan,
    pack_explicit: bool = False,
) -> str:
    """When freeform (no structure) and pack not explicitly chosen, use plan hint."""
    if structure_id or pack_explicit:
        return (current_pack or "atelier").strip() or "atelier"
    cur = (current_pack or "atelier").strip().lower() or "atelier"
    # Default atelier on freeform → upgrade to narrative DNA pack
    if cur in ("", "atelier", "auto"):
        return plan.pack_hint
    return cur
