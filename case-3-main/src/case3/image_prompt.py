"""Validate / sanitize Image API prompts + Liber brand-safe / pack style-lock."""

from __future__ import annotations

import logging
import re
import unicodedata
from typing import Any, Protocol

log = logging.getLogger("case3.image_prompt")

_CYRILLIC = re.compile(r"[\u0400-\u04FF]")
_CTRL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")
# Allow common punctuation; reject most other scripts / symbols spam.
_ALLOWED = re.compile(r"[^A-Za-z0-9\s.,;:!?()\[\]{}'\"\-_/\\%@&+=*#]")

# Pack DNA → short EN look lock (≤120 chars). No purple.
_PACK_STYLE: dict[str, str] = {
    "botanical": (
        "warm paper, fern/olive greens, soft natural light, matte, no neon"
    ),
    "board": (
        "cool gray-blue, crisp corporate daylight, clean desks, muted steel"
    ),
    "atelier": (
        "warm cream paper, olive ink accents, editorial still-life"
    ),
    "signal": (
        "ink black and signal red accents, sharp daylight, restrained editorial"
    ),
    "voltage": (
        "charcoal ground, amber voltage accents, crisp studio light, matte"
    ),
    "ink": (
        "deep ink blacks, paper white, quiet documentary light, no neon"
    ),
    "studio": (
        "neutral studio gray, softbox daylight, clean product still-life"
    ),
    "relay": (
        "cool slate and teal accents, technical daylight, calm industrial"
    ),
    # Report palettes map onto nearest pack mood
    "ocean": (
        "cool sea-blue tones, clear daylight, calm coastal still-life, matte"
    ),
    "sunset": (
        "warm amber dusk light, soft shadows, editorial matte, no neon"
    ),
    "mono": (
        "monochrome gray paper, soft side light, documentary still-life"
    ),
    "editorial": (
        "warm cream paper, olive ink accents, editorial still-life"
    ),
}

_BRAND_POSITIVE = (
    "print editorial, matte paper, natural light, restrained color, "
    "documentary object photography, no violet or purple glow"
)

# Stock / AI-slop n-grams to strip if the model leaked them.
_BANNED_NGRAMS: tuple[str, ...] = (
    "handshake",
    "thumbs up",
    "smiling diverse team",
    "glass office",
    "neon cyberpunk",
    "purple neon glow",
    "purple glow",
    "violet glow",
    "magenta glow",
    "purple gradient",
    "violet gradient",
    "hologram ui",
    "hologram",
    "lens flare spam",
    "watermark",
    "stock photo look",
    "shutterstock",
    "plastic 3d render",
    "uncanny faces",
    "confetti explosion",
    "trophy slam",
    "rocket emoji",
)

_NEGATIVE = (
    "handshake, thumbs up, generic smiling team in glass office, "
    "neon cyberpunk, purple violet magenta glow, hologram UI, "
    "watermark, stock photo look, Shutterstock aesthetic, "
    "plastic 3D people, confetti explosion, trophy slam, lens flare spam"
)


class ImagePromptError(ValueError):
    """Image prompt failed validation."""


def sanitize_image_prompt(
    prompt: str,
    *,
    min_len: int = 8,
    max_len: int = 800,
) -> str:
    text = unicodedata.normalize("NFKC", prompt or "")
    text = _CTRL.sub("", text)
    text = " ".join(text.split())
    if not text:
        raise ImagePromptError("empty image prompt")
    if _CYRILLIC.search(text):
        raise ImagePromptError("image prompt must be English (no Cyrillic)")
    # Strip leftover non-Latin letters (Greek, CJK, etc.)
    cleaned = []
    for ch in text:
        if ch.isalpha() and ord(ch) > 127:
            raise ImagePromptError("image prompt must use Latin letters only")
        cleaned.append(ch)
    text = "".join(cleaned)
    text = _ALLOWED.sub(" ", text)
    text = " ".join(text.split())
    if len(text) < min_len:
        raise ImagePromptError(f"image prompt too short (<{min_len})")
    if len(text) > max_len:
        text = text[:max_len].rstrip()
    return text


def pack_style_suffix(pack_id: str | None) -> str:
    """Short EN style lock for a deck pack or report palette id."""
    key = (pack_id or "").strip().lower() or "atelier"
    return _PACK_STYLE.get(key) or _PACK_STYLE["atelier"]


def apply_pack_style_lock(prompt: str, pack_id: str | None) -> str:
    """Append pack look after subject — does not replace the subject."""
    base = " ".join((prompt or "").split())
    if not base:
        return base
    suffix = pack_style_suffix(pack_id)
    if suffix.lower() in base.lower():
        return base
    return f"{base}. Style: {suffix}"


def _cleanup_strip_debris(text: str) -> str:
    """Collapse gaps left after ban-phrase removal (e.g. ``with in``)."""
    t = " ".join((text or "").split())
    # orphaned doubled / adjacent prepositions
    t = re.sub(
        r"\b(with|in|on|at|of|for|and|or|the|a|an)\s+\1\b",
        r"\1",
        t,
        flags=re.I,
    )
    t = re.sub(r"\b(with|in|on|at|of)\s+(with|in|on|at|of)\b", " ", t, flags=re.I)
    t = " ".join(t.split())
    # dangling prep at start/end of the subject fragment
    t = re.sub(r"^(with|in|on|at|of|and|or)\b\s*", "", t, flags=re.I)
    t = re.sub(r"\s*\b(with|in|on|at|of|and|or)$", "", t, flags=re.I)
    t = re.sub(r"\s+([.,;:])", r"\1", t)
    t = re.sub(r"([.,;:]){2,}", r"\1", t)
    return t.strip(" ,.;")


def harden_brand_safe(prompt: str) -> str:
    """Strip stock/AI-slop n-grams; append Liber-positive craft line."""
    text = " ".join((prompt or "").split())
    if not text:
        return text
    low = text.lower()
    # Longer phrases first so "purple neon glow" wins over "purple glow"
    for ng in sorted(_BANNED_NGRAMS, key=len, reverse=True):
        if ng in low:
            text = re.sub(re.escape(ng), " ", text, flags=re.I)
            low = text.lower()
    text = _cleanup_strip_debris(text)
    if "editorial" not in text.lower() and "matte paper" not in text.lower():
        text = f"{text}. {_BRAND_POSITIVE}" if text else _BRAND_POSITIVE
    elif "violet" not in text.lower() and "purple glow" not in text.lower():
        text = f"{text}, no violet or purple glow"
    return " ".join(text.split())


def brand_safe_negative() -> str:
    """Compact negative list for APIs that accept ``negative_prompt``."""
    return _NEGATIVE


def prepare_image_prompt(
    prompt: str,
    *,
    pack_id: str | None = None,
    max_len: int = 800,
    bake_avoid: bool = True,
) -> str:
    """Sanitize → pack lock → brand-safe (+ optional Avoid: block).

    Same path for generate and edit. Subject preserved; look locked.
    """
    text = sanitize_image_prompt(prompt, max_len=max_len)
    text = apply_pack_style_lock(text, pack_id)
    text = harden_brand_safe(text)
    if bake_avoid:
        avoid = brand_safe_negative()
        if "Avoid:" not in text:
            text = f"{text} Avoid: {avoid}"
    if len(text) > max_len:
        # Prefer keeping subject + short lock; trim Avoid first
        text = text[:max_len].rsplit(" ", 1)[0].rstrip(" ,.;")
    return text


class _Completes(Protocol):
    def complete(self, **kwargs: Any) -> str: ...


_TRANSLATE_SYSTEM = (
    "You translate image generation or edit instructions into a concise "
    "English photo prompt for an image API.\n"
    "Rules:\n"
    "- Return ONLY the English prompt text.\n"
    "- No quotes, markdown, bullets, or explanation.\n"
    "- Keep subject, setting, lighting, and edit intent.\n"
    "- No logos, watermarks, or readable text overlays.\n"
    "- Latin letters only."
)


def needs_english_translation(prompt: str) -> bool:
    """True when prompt has Cyrillic or other non-Latin letters."""
    text = " ".join((prompt or "").split())
    if not text:
        return False
    if _CYRILLIC.search(text):
        return True
    return any(ch.isalpha() and ord(ch) > 127 for ch in text)


def ensure_english_image_prompt(
    prompt: str,
    *,
    llm: _Completes | None = None,
) -> str:
    """Pass through English; translate RU (etc.) via Qwen to EN for Image API.

    Does not apply pack/brand harden — callers still use prepare_image_prompt
    / generate_png / edit_png.
    """
    text = " ".join((prompt or "").split())
    if not text:
        raise ImagePromptError("empty image prompt")
    if not needs_english_translation(text):
        return text

    from case3.llm_client import LLMClient, LLMConfig, LLMConfigError, LLMError

    client: _Completes = llm or LLMClient(LLMConfig.from_env())
    try:
        raw = client.complete(
            system=_TRANSLATE_SYSTEM,
            user_text=text,
            reasoning="off",
        )
    except (LLMConfigError, LLMError) as exc:
        raise ImagePromptError(f"не удалось перевести промпт на English: {exc}") from exc

    out = " ".join((raw or "").split())
    # Strip accidental wrapping quotes / fences
    if out.startswith("```"):
        out = out.strip("`")
        out = " ".join(out.split())
    if len(out) >= 2 and out[0] == out[-1] and out[0] in "\"'":
        out = out[1:-1].strip()
    if not out:
        raise ImagePromptError("пустой перевод промпта на English")
    if needs_english_translation(out):
        log.warning("image prompt translation still non-Latin; stripping check deferred to sanitize")
    log.info("image prompt translated to EN len=%d", len(out))
    return out
