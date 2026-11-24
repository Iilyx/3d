"""Turn an attached schema photo into a Liber Mermaid diagram.

Logos and UI screenshots stay photos. A schema photo is redrawn from the
boxes and arrows that are actually visible, then the source PNG is left
out of the deck.
"""

from __future__ import annotations

import re
from typing import Any

from case3.diagrams import DIAGRAMS_HARD_MAX, parse_diagrams

_SCHEMA_WORD = re.compile(r"схем|диаграм|flowchart|mermaid|блок-схем", re.IGNORECASE)
_REDRAW = re.compile(r"перерис|mermaid|мермай|нашим способом", re.IGNORECASE)
_LOGO = re.compile(r"лог|logo", re.IGNORECASE)
_UI = re.compile(r"интерфейс|скрин|экран|screenshot|(?:^|\s)ui(?:\s|$)", re.IGNORECASE)
_GENERIC = re.compile(r"^фото\s+\d+$", re.IGNORECASE)

SCHEMA_MAX = 3

_SYSTEM = """You redraw photographs of diagrams as Liber Mermaid.
Return only one JSON object:
{"diagrams":[{"id":"dia_01","type":"flowchart","title":"...","mermaid":"flowchart TD\\n  A[Label] --> B[Label]"}]}

Rules:
- One diagram per attached image, same order as the image ids.
- Copy only boxes, arrows, and labels you can see. Do not add steps.
- Keep the image language in labels. Node ids are ASCII.
- type flowchart and a first line `flowchart TD` or `flowchart LR`.
- No code fences, no click, no purple.
"""


def select_schema_photos(
    figures: list[dict[str, Any]],
    intent: str,
) -> list[dict[str, Any]]:
    """Uploads that should be redrawn. Logos and UI shots never qualify."""
    users = [
        f
        for f in figures
        if isinstance(f, dict) and str(f.get("id") or "").startswith("usr_")
    ]
    explicit = [
        f for f in users if _SCHEMA_WORD.search(str(f.get("caption") or ""))
    ]
    if explicit:
        return explicit[:SCHEMA_MAX]
    text = intent or ""
    if not (_SCHEMA_WORD.search(text) and _REDRAW.search(text)):
        return []
    captions = [str(f.get("caption") or "") for f in users]
    if any(_LOGO.search(c) or _UI.search(c) for c in captions):
        return []
    generics = [
        f
        for f in users
        if _GENERIC.match(str(f.get("caption") or "").strip())
        or not str(f.get("caption") or "").strip()
    ]
    if len(generics) != len(users) or not generics:
        return []
    return generics[:SCHEMA_MAX]


def diagrams_from_schema_reply(
    raw: str,
    photos: list[dict[str, Any]],
    *,
    existing_ids: list[str] | None = None,
) -> list[dict[str, Any]]:
    """Parse the vision reply and bind each diagram to its source photo."""
    parsed = _parse_object(raw)
    taken = {str(x) for x in (existing_ids or [])}
    out: list[dict[str, Any]] = []
    n = 1
    for dia, photo in zip(parsed, photos):
        while True:
            did = f"dia_{n:02d}"
            n += 1
            if did not in taken:
                break
        taken.add(did)
        caption = str(photo.get("caption") or "").strip()
        title = caption if _SCHEMA_WORD.search(caption) else str(dia.get("title") or caption)
        out.append(
            {
                "id": did,
                "type": dia.get("type") or "flowchart",
                "title": (title or did)[:120],
                "mermaid": dia.get("mermaid") or "",
                "source_photo": str(photo.get("id") or ""),
            }
        )
        if len(out) >= min(SCHEMA_MAX, DIAGRAMS_HARD_MAX):
            break
    return [d for d in out if d.get("mermaid")]


def schema_source_ids(diagrams: list[dict[str, Any]] | None) -> set[str]:
    return {
        str(d.get("source_photo") or "")
        for d in (diagrams or [])
        if isinstance(d, dict) and d.get("source_photo")
    }


def redraw_attached_schemas(
    *,
    figures: list[dict[str, Any]],
    intent: str,
    png_by_id: dict[str, Any],
    existing_ids: list[str],
    client: Any,
    vision_images: Any,
) -> list[dict[str, Any]]:
    """Ask the vision model to redraw schema uploads. Empty if nothing qualifies."""
    photos = select_schema_photos(figures, intent)
    if not photos or client is None:
        return []
    images = vision_images(
        png_by_id, [str(p.get("id") or "") for p in photos], limit=SCHEMA_MAX
    )
    if not images:
        return []
    raw = client.complete(
        system=_SYSTEM,
        user_text=schema_redraw_prompt(photos),
        reasoning="off",
        images=images,
    )
    by_id = {str(p.get("id") or ""): p for p in photos}
    ordered = [by_id[mid] for mid, _url in images if mid in by_id]
    return diagrams_from_schema_reply(raw or "", ordered, existing_ids=existing_ids)


def schema_redraw_prompt(photos: list[dict[str, Any]]) -> str:
    lines = [
        "Redraw each attached image as Mermaid, in this order.",
        "Use only labels visible in that image.",
    ]
    for photo in photos:
        lines.append(f"- {photo.get('id')}: {photo.get('caption') or 'схема'}")
    return "\n".join(lines)


def _parse_object(raw: str) -> list[dict[str, Any]]:
    import json

    text = (raw or "").strip()
    start = text.find("{")
    end = text.rfind("}")
    if start < 0 or end <= start:
        return []
    try:
        data = json.loads(text[start : end + 1])
    except json.JSONDecodeError:
        return []
    if not isinstance(data, dict):
        return []
    return parse_diagrams(data.get("diagrams"), max_diagrams=SCHEMA_MAX)
