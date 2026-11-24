"""Extract / persist Chart.js series for native PPTX charts."""

from __future__ import annotations

import re
from typing import Any

from case3.chart_number import compact_chart_number_text, take_chart_number

# Types we can map to python-pptx chart kinds.
NATIVE_CHART_TYPES = frozenset(
    {
        "bar",
        "grouped_bar",
        "stacked_bar",
        "line",
        "horizontal_bar",
        "area",
        "donut",
    }
)

_LABELS = re.compile(r"labels\s*:\s*\[([^\]]*)\]", re.I | re.S)


def _datasets_bodies(html: str) -> list[str]:
    """Top-level objects inside the first ``datasets`` array, braces included."""
    match = re.search(r"datasets\s*:\s*\[", html or "", re.I)
    if not match:
        return []
    text = html or ""
    index = match.end()
    bodies: list[str] = []
    while index < len(text):
        while index < len(text) and text[index] in " \t\r\n,":
            index += 1
        if index >= len(text) or text[index] == "]":
            break
        if text[index] != "{":
            index += 1
            continue
        start = index
        depth = 0
        while index < len(text):
            char = text[index]
            if char == "{":
                depth += 1
            elif char == "}":
                depth -= 1
                if depth == 0:
                    index += 1
                    bodies.append(text[start:index])
                    break
            index += 1
        else:
            break
    return bodies


def _array_body(obj: str, key: str) -> str | None:
    match = re.search(rf"\b{key}\s*:\s*\[", obj or "", re.I)
    if not match:
        return None
    index = match.end()
    depth = 1
    start = index
    while index < len(obj) and depth:
        if obj[index] == "[":
            depth += 1
        elif obj[index] == "]":
            depth -= 1
        index += 1
    if depth:
        return None
    return obj[start : index - 1]


def _series_from_datasets(html: str) -> list[dict[str, Any]]:
    series: list[dict[str, Any]] = []
    for body in _datasets_bodies(html):
        data = _array_body(body, "data")
        if data is None:
            continue
        values = _parse_numbers(data)
        if not values:
            continue
        label_m = re.search(
            r"""\blabel\s*:\s*(['"])(?P<label>.*?)\1""",
            body,
            re.I | re.S,
        )
        name = (label_m.group("label") if label_m else "Series").strip() or "Series"
        series.append({"name": name, "values": values})
    return series


_NUM = re.compile(r"-?\d+(?:\.\d+)?")
_SCATTER_POINT = re.compile(
    r"\{\s*x\s*:\s*(-?\d+(?:\.\d+)?)\s*,\s*y\s*:\s*(-?\d+(?:\.\d+)?)\s*\}",
    re.I,
)
_KPI_VALUE = re.compile(
    r'class\s*=\s*["\']value["\'][^>]*>([^<]+)',
    re.I,
)
_KPI_LABEL = re.compile(
    r'class\s*=\s*["\']label["\'][^>]*>([^<]+)',
    re.I,
)


def _parse_labels(blob: str) -> list[str]:
    return re.findall(r"""['"]([^'"]*)['"]""", blob or "")


def _parse_numbers(blob: str) -> list[float | None]:
    """One float per slot. ``12,5`` and ``105 865,2`` are one point. ``null`` keeps the slot."""
    text = compact_chart_number_text(blob)
    out: list[float | None] = []
    index = 0
    size = len(text)
    while index < size:
        if text[index].isspace() or text[index] == ",":
            index += 1
            continue
        if text[index : index + 4].lower() == "null" and (
            index == 0 or not text[index - 1].isalnum()
        ):
            out.append(None)
            index += 4
            continue
        taken = take_chart_number(text, index)
        if not taken:
            index += 1
            continue
        token, index = taken
        try:
            out.append(float(token))
        except ValueError:
            continue
    return out


def normalize_series_ir(raw: Any, *, default_type: str = "bar") -> dict[str, Any] | None:
    """Validate ChartSeriesIR shape; return a clean copy or None."""
    if not isinstance(raw, dict):
        return None
    cats = list(raw.get("categories") or [])
    series = list(raw.get("series") or [])
    if not cats or not series:
        return None
    cleaned: list[dict[str, Any]] = []
    for s in series:
        if not isinstance(s, dict):
            continue
        vals = list(s.get("values") or [])
        nums: list[float | None] = []
        for v in vals:
            if v is None or (isinstance(v, str) and v.strip().lower() == "null"):
                nums.append(None)
                continue
            try:
                nums.append(float(v))
            except (TypeError, ValueError):
                nums.append(None)
        if not any(isinstance(n, (int, float)) for n in nums):
            continue
        cleaned.append(
            {
                "name": str(s.get("name") or "Series").strip() or "Series",
                "values": nums,
            }
        )
    if not cleaned:
        return None
    n_cat = min(len(cats), min(len(s["values"]) for s in cleaned))
    if n_cat < 1:
        return None
    ctype = str(raw.get("type") or default_type).strip().lower() or "bar"
    if ctype not in NATIVE_CHART_TYPES:
        ctype = "bar"
    return {
        "type": ctype,
        "categories": [str(c) for c in cats[:n_cat]],
        "series": [
            {"name": s["name"], "values": s["values"][:n_cat]} for s in cleaned
        ],
    }


def extract_scatter_ir(html: str) -> dict[str, Any] | None:
    points = [
        {"x": float(x), "y": float(y)} for x, y in _SCATTER_POINT.findall(html or "")
    ]
    if len(points) < 2:
        return None
    name_m = re.search(r"label\s*:\s*['\"]([^'\"]+)['\"]", html or "", re.I)
    name = (name_m.group(1).strip() if name_m else "") or "Точки"
    return {"type": "scatter", "series": [{"name": name, "points": points}]}


def extract_kpi_ir(html: str) -> dict[str, Any] | None:
    value_m = _KPI_VALUE.search(html or "")
    if not value_m:
        return None
    value = " ".join(value_m.group(1).split())
    if not value:
        return None
    label_m = _KPI_LABEL.search(html or "")
    label = " ".join(label_m.group(1).split()) if label_m else ""
    return {"type": "kpi", "value": value[:48], "label": label[:48]}


def extract_chart_series(
    html: str,
    *,
    chart_type: str | None = None,
) -> dict[str, Any] | None:
    """Return ChartSeriesIR or None if not extractable / not native-eligible."""
    ctype = (chart_type or "").strip().lower() or "bar"
    if ctype == "kpi":
        return extract_kpi_ir(html)
    if ctype == "scatter":
        return extract_scatter_ir(html)
    if ctype not in NATIVE_CHART_TYPES and ctype not in ("bar", "line"):
        # Still try bar/line-shaped data for unknown types
        if "labels" not in (html or "") or "data:" not in (html or ""):
            return None

    labels_m = _LABELS.search(html or "")
    if not labels_m:
        return None
    categories = _parse_labels(labels_m.group(1))
    if not categories:
        return None

    series = _series_from_datasets(html or "")

    if not series:
        # Single anonymous data:[] near labels
        data_m = re.search(r"data\s*:\s*\[([^\]]*)\]", html or "", re.I)
        if not data_m:
            return None
        values = _parse_numbers(data_m.group(1))
        n = min(len(categories), len(values))
        if n < 1:
            return None
        series = [{"name": "Series", "values": values[:n]}]

    # Align category length to shortest series
    n_cat = min(len(categories), min(len(s["values"]) for s in series))
    return {
        "type": ctype if ctype in NATIVE_CHART_TYPES else "bar",
        "categories": categories[:n_cat],
        "series": [
            {"name": s["name"], "values": s["values"][:n_cat]} for s in series
        ],
    }


def _donut_series_name(chart: dict[str, Any], current: str) -> str:
    """Prefer caption/title over anonymous Chart.js 'Series' for donut legend."""
    cur = (current or "").strip()
    if cur and cur.lower() not in ("series", "dataset", "data"):
        return cur
    for key in ("caption", "title", "label"):
        val = str(chart.get(key) or "").strip()
        if val:
            return val[:48]
    return "Доля"


def _polish_donut_names(chart: dict[str, Any], ir: dict[str, Any]) -> dict[str, Any]:
    if ir.get("type") == "donut":
        for s in ir["series"]:
            s["name"] = _donut_series_name(chart, str(s.get("name") or ""))
    return ir


def attach_series_ir(chart: dict[str, Any]) -> dict[str, Any] | None:
    """Persist native-eligible series on a chart dict; return IR or None.

    After a Liber type change, re-extract from HTML when stored IR type
    mismatches chart.type (stale bar IR must not ship as native donut).
    """
    if not isinstance(chart, dict):
        return None
    ctype = str(chart.get("type") or "").strip().lower()
    if ctype == "kpi":
        ir = extract_kpi_ir(str(chart.get("html") or ""))
        if ir:
            chart["series"] = ir
            return ir
        chart.pop("series", None)
        return None
    if ctype == "scatter":
        ir = extract_scatter_ir(str(chart.get("html") or ""))
        if ir:
            chart["series"] = ir
            return ir
        chart.pop("series", None)
        return None
    existing = normalize_series_ir(chart.get("series"), default_type=ctype or "bar")
    type_ok = bool(existing) and existing.get("type") == ctype
    if existing and type_ok:
        chart["series"] = _polish_donut_names(chart, existing)
        return existing
    ir = extract_chart_series(
        str(chart.get("html") or ""),
        chart_type=ctype or None,
    )
    if not ir:
        # Coerce path left HTML unparseable — keep values, force chart type.
        if existing and ctype in NATIVE_CHART_TYPES:
            existing = dict(existing)
            existing["type"] = ctype
            chart["series"] = _polish_donut_names(chart, existing)
            return existing
        chart.pop("series", None)
        return None
    chart["series"] = _polish_donut_names(chart, ir)
    return ir


def attach_series_ir_to_charts(charts: list[Any] | None) -> int:
    """Attach series IR to each chart; return how many got IR."""
    n = 0
    for ch in charts or []:
        if isinstance(ch, dict) and attach_series_ir(ch):
            n += 1
    return n


def series_from_figures_json(
    figures: dict[str, Any],
    chart_id: str,
) -> dict[str, Any] | None:
    for ch in figures.get("charts") or []:
        if not isinstance(ch, dict):
            continue
        if str(ch.get("id") or "") != chart_id:
            continue
        ctype = str(ch.get("type") or "bar").strip().lower() or "bar"
        if ctype == "kpi":
            return extract_kpi_ir(str(ch.get("html") or "")) or (
                ch.get("series") if isinstance(ch.get("series"), dict) and ch["series"].get("type") == "kpi" else None
            )
        if ctype == "scatter":
            stored_sc = ch.get("series")
            if isinstance(stored_sc, dict) and stored_sc.get("type") == "scatter" and stored_sc.get("series"):
                return stored_sc
            return extract_scatter_ir(str(ch.get("html") or ""))
        stored = normalize_series_ir(
            ch.get("series"),
            default_type=ctype,
        )
        if stored and stored.get("type") == ctype:
            return stored
        ir = extract_chart_series(
            str(ch.get("html") or ""),
            chart_type=ctype,
        )
        if ir:
            ch["series"] = ir
            return ir
        if stored and ctype in NATIVE_CHART_TYPES:
            stored = dict(stored)
            stored["type"] = ctype
            ch["series"] = stored
            return stored
        return None
    return None


def series_map_from_figures(figures: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """All native-eligible chart ids → series IR from figures.json."""
    out: dict[str, dict[str, Any]] = {}
    for ch in figures.get("charts") or []:
        if not isinstance(ch, dict):
            continue
        cid = str(ch.get("id") or "").strip()
        if not cid.startswith("cht_"):
            continue
        ir = series_from_figures_json(figures, cid)
        if ir:
            out[cid] = ir
    return out


def _deck_chart_ids(deck: dict[str, Any]) -> set[str]:
    out: set[str] = set()
    for s in deck.get("slides") or []:
        if not isinstance(s, dict):
            continue
        for key in ("chart_id", "media_id"):
            mid = str(s.get(key) or "").strip()
            if mid.startswith("cht_"):
                out.add(mid)
    return out


def _chart_hero_slide(cid: str, *, title: str | None = None) -> dict[str, Any]:
    return {
        "id": f"s_native_{cid}",
        "layout": "chart_hero",
        "title": _clip_label(title) or "Ключевые показатели",
        "chart_id": cid,
    }


def ensure_deck_charts(
    deck: dict[str, Any],
    series_by_id: dict[str, dict[str, Any]],
    *,
    titles: dict[str, str] | None = None,
) -> list[str]:
    """Ensure every native-eligible cht_* appears on a slide. Return injected ids."""
    for s in deck.get("slides") or []:
        if not isinstance(s, dict):
            continue
        cid = str(s.get("chart_id") or "").strip()
        title = str(s.get("title") or "")
        cap = (titles or {}).get(cid) or ""
        if cid and cap and title.startswith("График "):
            s["title"] = _clip_label(cap)
    if not series_by_id:
        return []
    present = _deck_chart_ids(deck)
    missing = sorted(set(series_by_id.keys()) - present)
    if not missing:
        return []
    slides = list(deck.get("slides") or [])
    close_i = next(
        (
            i
            for i, s in enumerate(slides)
            if isinstance(s, dict) and str(s.get("layout") or "") == "closing"
        ),
        None,
    )
    if close_i is not None:
        insert_at = close_i
    elif slides and str(slides[0].get("layout") or "") == "title":
        insert_at = 1
    else:
        insert_at = len(slides)
    injected: list[str] = []
    for j, cid in enumerate(missing):
        slides.insert(
            insert_at + j,
            _chart_hero_slide(cid, title=(titles or {}).get(cid) or None),
        )
        injected.append(cid)
    deck["slides"] = slides
    return injected


_TOKEN = re.compile(r"[0-9A-Za-zА-Яа-яЁё]{4,}")
_FILLER_LAYOUTS = frozenset({"card_row", "bullets", "callout", "section"})


def _clip_label(text: str | None, limit: int = 80) -> str:
    raw = " ".join(str(text or "").split())
    if len(raw) <= limit:
        return raw
    return raw[: limit - 1].rstrip() + "…"


def _tokens(text: str) -> set[str]:
    return {m.group(0).casefold() for m in _TOKEN.finditer(text or "")}


def _same_word(a: str, b: str) -> bool:
    if a == b:
        return True
    # линия/линию, смена/смены — same stem, not a full lemmatizer.
    if len(a) >= 5 and len(b) >= 5 and a[:4] == b[:4]:
        return True
    return False


def _overlap(left: set[str], right: set[str]) -> int:
    n = 0
    for a in left:
        if any(_same_word(a, b) for b in right):
            n += 1
    return n


def _used_media_ids(deck: dict[str, Any]) -> set[str]:
    used: set[str] = set()
    for s in deck.get("slides") or []:
        if not isinstance(s, dict):
            continue
        mid = str(s.get("media_id") or s.get("chart_id") or "").strip()
        if mid:
            used.add(mid)
    return used


_LOGO = re.compile(r"лог|logo", re.IGNORECASE)


def _is_logo(caption: str) -> bool:
    return bool(_LOGO.search(caption or ""))


def _insert_after_match(slides: list[dict[str, Any]], caption: str) -> tuple[int, int]:
    """Index after the slide whose copy shares the most words with the caption.

    Returns ``(index, score)``. Score 0 means nothing in the deck matches.
    """
    want = _tokens(caption)
    best_i: int | None = None
    best = 0
    for i, s in enumerate(slides):
        if str(s.get("layout") or "") in ("title", "closing"):
            continue
        blob = " ".join(
            str(s.get(k) or "")
            for k in ("title", "subtitle", "takeaway", "caption", "term", "definition")
        )
        score = _overlap(want, _tokens(blob))
        if score > best:
            best = score
            best_i = i
    if best_i is not None:
        return best_i + 1, best
    for i, s in enumerate(slides):
        if str(s.get("layout") or "") == "closing":
            return i, 0
    return len(slides), 0


def _content_slots(slides: list[dict[str, Any]]) -> list[int]:
    return [
        i
        for i, s in enumerate(slides)
        if str(s.get("layout") or "")
        not in ("title", "closing", "media_hero", "media_split")
    ]


def _fresh_photo_id(used: set[str], fid: str) -> str:
    base = f"s_photo_{fid}"
    if base not in used:
        return base
    n = 2
    while f"{base}_{n}" in used:
        n += 1
    return f"{base}_{n}"


def _photo_slide(
    used_ids: set[str],
    fid: str,
    caption: str,
    *,
    layout: str,
    kicker: str,
) -> dict[str, Any]:
    return {
        "id": _fresh_photo_id(used_ids, fid),
        "layout": layout,
        "kicker": kicker,
        "title": _clip_label(caption),
        "media_id": fid,
        "caption": _clip_label(caption, 120),
    }


def _place_photo(
    slides: list[dict[str, Any]],
    slide: dict[str, Any],
    at: int,
    *,
    max_slides: int,
) -> bool:
    if len(slides) >= max_slides:
        for i in range(len(slides) - 2, 0, -1):
            if str(slides[i].get("layout") or "") in _FILLER_LAYOUTS:
                slides[i] = slide
                return True
        return False
    slides.insert(max(0, min(at, len(slides))), slide)
    return True


def ensure_deck_photos(
    deck: dict[str, Any],
    photos: list[dict[str, Any]],
    *,
    max_slides: int = 24,
) -> list[str]:
    """Place unused usr_/fig_ photos.

    A caption with «лого» becomes a ``media_hero`` right after the title.
    Other captions sit after the slide that shares their words. If nothing
    matches, they spread through the body instead of stacking before the close.
    """
    if not isinstance(deck, dict):
        return []
    slides = [s for s in (deck.get("slides") or []) if isinstance(s, dict)]
    if not slides:
        return []
    used_media = _used_media_ids(deck)
    used_ids = {str(s.get("id") or "") for s in slides}
    pending: list[tuple[str, str]] = []
    for photo in photos:
        if not isinstance(photo, dict):
            continue
        fid = str(photo.get("id") or "").strip()
        if not fid.startswith(("usr_", "fig_")) or fid in used_media:
            continue
        caption = str(photo.get("caption") or "").strip() or fid
        pending.append((fid, caption))

    injected: list[str] = []

    def _keep(fid: str, slide: dict[str, Any]) -> None:
        used_media.add(fid)
        used_ids.add(str(slide["id"]))
        injected.append(fid)

    logo_at = 1
    rest: list[tuple[str, str]] = []
    for fid, caption in pending:
        if not _is_logo(caption):
            rest.append((fid, caption))
            continue
        slide = _photo_slide(
            used_ids, fid, caption, layout="media_hero", kicker="ЛОГОТИП"
        )
        if _place_photo(slides, slide, logo_at, max_slides=max_slides):
            _keep(fid, slide)
            logo_at += 1

    unmatched: list[tuple[str, dict[str, Any]]] = []
    for fid, caption in rest:
        slide = _photo_slide(
            used_ids, fid, caption, layout="media_split", kicker="КАДР"
        )
        at, score = _insert_after_match(slides, caption)
        if score > 0 and _place_photo(slides, slide, at, max_slides=max_slides):
            _keep(fid, slide)
        elif score == 0:
            unmatched.append((fid, slide))

    slots = _content_slots(slides)
    n = len(unmatched)
    targets: list[tuple[int, str, dict[str, Any]]] = []
    for i, (fid, slide) in enumerate(unmatched):
        if slots:
            idx = min(len(slots) - 1, int(i * len(slots) / n))
            at = slots[idx] + 1
        else:
            at = len(slides)
        targets.append((at, fid, slide))
    for at, fid, slide in sorted(targets, key=lambda row: -row[0]):
        if _place_photo(slides, slide, at, max_slides=max_slides):
            _keep(fid, slide)

    deck["slides"] = slides
    return injected


def ensure_deck_diagrams(
    deck: dict[str, Any],
    diagrams: list[dict[str, Any]],
    *,
    max_slides: int = 24,
) -> list[str]:
    """Place each unused dia_* on a media_hero before the closing slide."""
    if not isinstance(deck, dict):
        return []
    slides = [s for s in (deck.get("slides") or []) if isinstance(s, dict)]
    if not slides:
        return []
    used_media = _used_media_ids(deck)
    used_ids = {str(s.get("id") or "") for s in slides}
    injected: list[str] = []
    for dia in diagrams:
        if not isinstance(dia, dict):
            continue
        did = str(dia.get("id") or "").strip()
        if not did.startswith("dia_") or did in used_media:
            continue
        title = str(dia.get("title") or did).strip() or did
        slide = _photo_slide(
            used_ids, did, title, layout="media_hero", kicker="СХЕМА"
        )
        slide["media_id"] = did
        close = next(
            (i for i, s in enumerate(slides) if str(s.get("layout") or "") == "closing"),
            len(slides),
        )
        if _place_photo(slides, slide, close, max_slides=max_slides):
            used_media.add(did)
            used_ids.add(str(slide["id"]))
            injected.append(did)
    deck["slides"] = slides
    populate_deck_bullet_node_maps(deck, diagrams)
    return injected


def populate_deck_bullet_node_maps(
    deck: dict[str, Any],
    diagrams: list[dict[str, Any]],
) -> None:
    """Pre-populate 1:1 or 1:N bullet_node_map on diagram slides in deck."""
    if not isinstance(deck, dict):
        return
    slides = deck.get("slides")
    if not isinstance(slides, list) or not diagrams:
        return

    dia_map = {str(d.get("id")): d for d in diagrams if isinstance(d, dict) and d.get("id")}

    for s in slides:
        if not isinstance(s, dict):
            continue
        mid = str(s.get("media_id") or "")
        if not mid.startswith("dia_"):
            continue
        bullets = s.get("bullets")
        if not bullets or not isinstance(bullets, list) or s.get("bullet_node_map"):
            continue

        dia = dia_map.get(mid)
        if not dia:
            continue

        mermaid = str(dia.get("mermaid") or "")
        try:
            from case3.slides_pptx_diagrams import (
                parse_mermaid_flowchart,
                parse_mermaid_mindmap,
                parse_mermaid_timeline,
            )

            node_ids: list[str] = []
            g = parse_mermaid_flowchart(mermaid)
            if g and g.nodes:
                node_ids = list(g.nodes.keys())
            else:
                tl = parse_mermaid_timeline(mermaid)
                if tl and tl.periods:
                    node_ids = [f"p_{i}" for i in range(len(tl.periods))]
                else:
                    mm = parse_mermaid_mindmap(mermaid)
                    if mm and mm.children:
                        node_ids = [c.id for c in mm.children]

            if node_ids:
                s["bullet_node_map"] = {
                    str(i): node_ids[i] for i in range(min(len(bullets), len(node_ids)))
                }
        except Exception:
            pass
