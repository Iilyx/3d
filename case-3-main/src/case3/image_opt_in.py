"""Opt-in gate for Image API generated photos (fig_*).

User uploads (usr_*) are independent — always place when attached.
Generated fig_* only when Intent or Source explicitly asks for a picture.
"""

from __future__ import annotations

import re

from case3.input_validation import current_turn_user_text
from case3.user_photos import split_image_budget

# Negative wins over any positive cue.
_NEGATIVE = re.compile(
    r"(?:"
    r"без\s+фото|"
    r"без\s+иллюстрац\w*|"
    r"без\s+картин\w*|"
    r"без\s+изображен\w*|"
    r"\bno\s+photos?\b|"
    r"\bwithout\s+images?\b|"
    r"\bno\s+illustrations?\b"
    r")",
    re.IGNORECASE,
)

# Strip data-viz phrases so «визуализация данных» alone does not opt in.
_DATA_VIZ = re.compile(
    r"визуализац\w*\s+(?:данных|графика|графиков|диаграмм\w*|charts?|данных)",
    re.IGNORECASE,
)

_POSITIVE = re.compile(
    r"(?:"
    r"фото|"
    r"фотк\w*|"
    r"иллюстрац\w*|"
    r"рисун\w*|"
    r"картинк\w*|"
    r"изображен\w*|"
    r"внешн(?:ий|его|ем|им)?\s+вид|"
    r"\bphotos?\b|"
    r"\bphotographs?\b|"
    r"\billustrations?\b|"
    r"\bpicture\s+of\b|"
    r"\bimage\s+of\b|"
    r"\bvisual\s+of\b|"
    r"show\s+the\s+appearance|"
    r"\brender\s+of\b|"
    r"визуализац\w*"
    r")",
    re.IGNORECASE,
)

_SHOW_VISUAL = re.compile(
    r"покаж(?:и|ите)\s+.{0,48}(?:"
    r"здани\w*|офис\w*|продукт\w*|интерфейс\w*|устройств\w*|фасад\w*|"
    r"цех\w*|лобби|lobby|building|product|interface|device"
    r")|"
    r"(?:"
    r"здани\w*|офис\w*|продукт\w*|интерфейс\w*|устройств\w*|фасад\w*"
    r")\s+.{0,48}покаж(?:и|ите)",
    re.IGNORECASE | re.DOTALL,
)


def wants_generated_images(intent: str | None, source: str | None) -> bool:
    """True when chat/Source explicitly asks for a generated photo/illustration."""
    chat = current_turn_user_text(intent)
    src = (source or "").strip()
    blob = f"{chat}\n{src}".strip()
    if not blob:
        return False
    if _NEGATIVE.search(blob):
        return False
    scrubbed = _DATA_VIZ.sub(" ", blob)
    if _POSITIVE.search(scrubbed):
        return True
    if _SHOW_VISUAL.search(scrubbed):
        return True
    return False


def apply_gen_image_budget(
    images_budget: int,
    n_user: int,
    *,
    mode: str,
    opt_in: bool,
) -> tuple[int, int]:
    """Return ``(llm_max_images, merge_max_images)`` after opt-in clamp.

    Without opt-in, LLM may not plan ``fig_*`` (budget 0) but uploads still
    merge into the report. With opt-in, same split as ``split_image_budget``.
    """
    llm, merge = split_image_budget(images_budget, n_user, mode=mode)
    if not opt_in:
        return 0, max(0, int(n_user)) if n_user else 0
    return llm, merge
