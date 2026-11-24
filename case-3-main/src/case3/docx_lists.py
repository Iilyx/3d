"""Post-pandoc DOCX: promote TeX-like lists to Liber List Bullet / List Number (C7)."""

from __future__ import annotations

import logging
import re
from pathlib import Path

log = logging.getLogger("case3.docx_lists")

_BULLET = re.compile(r"^([ \t]*)([-*•∙▪◦]|–|—)\s+(.*)$", re.DOTALL)
_ORDERED = re.compile(r"^([ \t]*)(\d+)[.)]\s+(.*)$", re.DOTALL)

_BULLET_STYLES = ("List Bullet", "List Bullet 2", "List Paragraph")
_NUMBER_STYLES = ("List Number", "List Number 2")


def _qn(tag: str):
    from docx.oxml.ns import qn

    return qn(tag)


def _ensure_num_pr(paragraph, *, ilvl: int) -> None:  # noqa: ANN001
    """Attach numPr if missing so Word shows a marker (style alone is not enough)."""
    from docx.oxml import OxmlElement

    pPr = paragraph._p.get_or_add_pPr()
    numPr = pPr.find(_qn("w:numPr"))
    if numPr is not None:
        ilvl_el = numPr.find(_qn("w:ilvl"))
        if ilvl_el is not None:
            ilvl_el.set(_qn("w:val"), str(max(0, min(ilvl, 1))))
        return
    numPr = OxmlElement("w:numPr")
    ilvl_el = OxmlElement("w:ilvl")
    ilvl_el.set(_qn("w:val"), str(max(0, min(ilvl, 1))))
    numId = OxmlElement("w:numId")
    # 1 = typically bullets, 2 = numbering in default Word templates / pandoc refs.
    # Style association usually wins; numId 1 is a safe default for both Liber styles.
    numId.set(_qn("w:val"), "1")
    numPr.append(ilvl_el)
    numPr.append(numId)
    pPr.append(numPr)


def _set_style(paragraph, name: str) -> None:  # noqa: ANN001
    try:
        paragraph.style = name
    except KeyError:
        # Fallback if reference.docx styles missing (bare Document()).
        try:
            paragraph.style = "List Paragraph"
        except KeyError:
            pass


def _replace_paragraph_text(paragraph, text: str) -> None:  # noqa: ANN001
    if paragraph.runs:
        paragraph.runs[0].text = text
        for run in paragraph.runs[1:]:
            run.text = ""
        return
    paragraph.add_run(text)


def _indent_level(prefix_ws: str) -> int:
    if not prefix_ws:
        return 0
    # 2+ spaces or a tab → nested (cap ilvl 1).
    if "\t" in prefix_ws or len(prefix_ws.replace("\t", "  ")) >= 2:
        return 1
    return 0


def _classify_plain(text: str) -> tuple[str, str, int] | None:
    """Return (kind, body, ilvl) for plain-text list markers, else None."""
    raw = text or ""
    m = _BULLET.match(raw)
    if m:
        return "bullet", m.group(3).strip(), _indent_level(m.group(1))
    m = _ORDERED.match(raw)
    if m:
        return "number", m.group(3).strip(), _indent_level(m.group(1))
    return None


def _already_list_style(name: str) -> str | None:
    n = (name or "").strip()
    if n in _BULLET_STYLES or n.startswith("List Bullet"):
        return "bullet"
    if n in _NUMBER_STYLES or n.startswith("List Number"):
        return "number"
    return None


def fix_docx_lists(path: Path | str) -> Path:
    """Promote bullet/numbered paragraphs to Liber list styles + numPr."""
    try:
        from docx import Document
    except ImportError as exc:
        raise RuntimeError("python-docx required for DOCX list fix") from exc

    path = Path(path)
    doc = Document(str(path))
    fixed = 0
    for p in doc.paragraphs:
        style_name = getattr(getattr(p, "style", None), "name", "") or ""
        kind = _already_list_style(style_name)
        ilvl = 0
        body = (p.text or "").strip()

        if kind is None:
            classified = _classify_plain(p.text or "")
            if classified is None:
                continue
            kind, body, ilvl = classified
            _replace_paragraph_text(p, body)

        target = "List Bullet" if kind == "bullet" else "List Number"
        if ilvl >= 1:
            target = f"{target} 2"
        _set_style(p, target)
        # Prefer level-1 Liber style; if missing, keep base + ilvl numPr.
        if ilvl >= 1 and (getattr(p.style, "name", "") or "") == "List Paragraph":
            _set_style(p, "List Bullet" if kind == "bullet" else "List Number")
        _ensure_num_pr(p, ilvl=ilvl)
        # Distinct numId for ordered lists when possible (Word default abstract nums).
        if kind == "number":
            pPr = p._p.get_or_add_pPr()
            numPr = pPr.find(_qn("w:numPr"))
            if numPr is not None:
                numId = numPr.find(_qn("w:numId"))
                if numId is not None:
                    numId.set(_qn("w:val"), "2")
        fixed += 1

    doc.save(str(path))
    log.info("fixed DOCX lists (%s paragraphs) → %s", fixed, path)
    return path


def try_fix_docx_lists(path: Path | str) -> bool:
    """Best-effort list fix; never raise into render."""
    try:
        fix_docx_lists(path)
        return True
    except Exception as exc:  # noqa: BLE001 — soft-fail
        log.warning("docx list fix skipped: %s", exc)
        return False
