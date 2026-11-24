"""Detect explicit Source references for Liber footnotes (C2)."""

from __future__ import annotations

import re

_URL = re.compile(
    r"https?://[^\s<>\)\]\"']+",
    re.I,
)
_SEE = re.compile(
    r"(?i)(?:\bсм\.|\bсм\b|\bsee\b|\bcf\.|\bсогласно\b|\bпо данным\b|"
    r"\bисточник(?:ам|и|у)?\b|\bbibliograph|\bссылк)",
)
_BRACKET_YEAR = re.compile(
    r"\[[^\]]{2,80}\d{4}[^\]]{0,40}\]",
)


def extract_source_refs(source: str) -> list[str]:
    """Return explicit ref strings found in Source (URLs + see-phrases snippets)."""
    text = source or ""
    out: list[str] = []
    for m in _URL.finditer(text):
        out.append(m.group(0).rstrip(".,;:)"))
    for m in _BRACKET_YEAR.finditer(text):
        out.append(m.group(0))
    if _SEE.search(text) and not out:
        # Phrase-only: signal that footnotes are allowed, no concrete URL list.
        out.append("(see-phrase)")
    # Dedupe preserve order
    seen: set[str] = set()
    uniq: list[str] = []
    for r in out:
        if r in seen:
            continue
        seen.add(r)
        uniq.append(r)
    return uniq


def source_allows_citations(source: str) -> bool:
    return bool(extract_source_refs(source))


def citation_intent_hint(source: str) -> str | None:
    """Extra Intent line for the model when Source has refs; else None."""
    refs = extract_source_refs(source)
    if not refs:
        return (
            "Цитаты/сноски: в Source нет явных ссылок (URL / «см. …» / библио) — "
            "НЕ добавляй \\footnote и \\cite; не выдумывай источники."
        )
    urls = [r for r in refs if r.startswith("http")]
    bits = ", ".join(urls[:6]) if urls else "явные отсылки в Source"
    return (
        "Цитаты/сноски: разрешены ТОЛЬКО по Source. "
        f"Допустимые опоры: {bits}. "
        "Оформляй \\footnote{…} с текстом/URL из Source; не изобретай авторов и годы."
    )
