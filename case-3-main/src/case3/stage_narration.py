"""One spoken line per craft step. The chat shows a line only after that step starts."""

from __future__ import annotations

import json
import re
from typing import Callable

_BEATS = {
    "chat": ("source", "layout"),
    "diagram": ("source", "layout", "pdf"),
    "presentation": (
        "source",
        "layout",
        "charts",
        "photos",
        "slides_plan",
        "slides_media",
        "slides_render",
        "slides_pack",
    ),
    "report": ("source", "layout", "charts", "photos", "pdf", "docx"),
}

_DONE = re.compile(r"(?i)\b(готово|собрано|pdf готов)\b")


def beats_for(mode: str) -> tuple[str, ...]:
    return _BEATS.get((mode or "").strip().lower(), _BEATS["report"])


def parse_stage_lines(raw: str, mode: str) -> dict[str, str]:
    """Keep model sentences whose id is a beat of this job. Drop the rest."""
    allowed = set(beats_for(mode))
    text = (raw or "").strip()
    start = text.find("{")
    end = text.rfind("}")
    if start < 0 or end <= start:
        return {}
    try:
        payload = json.loads(text[start : end + 1])
    except json.JSONDecodeError:
        return {}
    rows = payload.get("lines") if isinstance(payload, dict) else None
    if not isinstance(rows, list):
        return {}
    out: dict[str, str] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        step_id = str(row.get("id") or "").strip()
        sentence = " ".join(str(row.get("text") or "").split())
        if step_id not in allowed or not sentence or _DONE.search(sentence):
            continue
        if len(sentence) > 180:
            sentence = sentence[:177].rstrip() + "…"
        out[step_id] = sentence
    return out


def narrate_stages(user_text: str, mode: str, complete: Callable[..., str]) -> dict[str, str]:
    from case3.prompts import load as load_prompt

    beats = beats_for(mode)
    raw = str(
        complete(
            system=load_prompt("stage_narration"),
            user_text=(
                f"Работа: {mode or 'report'}.\n"
                f"id, которые можно использовать: {', '.join(beats)}.\n\n"
                f"Запрос:\n{(user_text or '').strip()[:1200] or '(только вложение)'}"
            ),
            reasoning="off",
        )
        or ""
    )
    return parse_stage_lines(raw, mode)
