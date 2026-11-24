"""Validate DOCX is a readable OOXML package (Word-safe gate)."""

from __future__ import annotations

import logging
import zipfile
from pathlib import Path

log = logging.getLogger("case3.docx_validate")


def docx_charts_word_safe(path: Path | str) -> bool:
    """True when native chart parts (if any) are cache-only — no xlsx embeds.

    MS Word refuses DOCX packages that point charts at ``word/embeddings/*.xlsx``
    (python-pptx style). Liber must ship ChartML with strCache/numCache only.
    """
    p = Path(path)
    if not p.is_file():
        return False
    try:
        with zipfile.ZipFile(p) as zf:
            names = zf.namelist()
            charts = [n for n in names if n.startswith("word/charts/") and n.endswith(".xml")]
            if not charts:
                return True
            embeds = [n for n in names if n.startswith("word/embeddings/")]
            if embeds:
                log.debug("docx chart embeds present: %s", embeds[:5])
                return False
            for cf in charts:
                if "/_rels/" in cf:
                    continue
                xml = zf.read(cf).decode("utf-8", errors="replace")
                if "externalData" in xml:
                    log.debug("docx chart has externalData: %s", cf)
                    return False
                if "numCache" not in xml and "strCache" not in xml:
                    log.debug("docx chart missing cache: %s", cf)
                    return False
    except (OSError, zipfile.BadZipFile) as exc:
        log.debug("docx_charts_word_safe failed: %s", exc)
        return False
    return True


def docx_package_ok(path: Path | str) -> bool:
    """True if path is a zip with word/document.xml and testzip clean."""
    p = Path(path)
    if not p.is_file() or p.stat().st_size < 64:
        return False
    if p.read_bytes()[:2] != b"PK":
        return False
    try:
        with zipfile.ZipFile(p) as zf:
            names = set(zf.namelist())
            if "[Content_Types].xml" not in names or "word/document.xml" not in names:
                return False
            if zf.testzip() is not None:
                return False
    except (OSError, zipfile.BadZipFile):
        return False
    try:
        from docx import Document  # type: ignore

        Document(str(p))
    except Exception as exc:  # noqa: BLE001
        log.debug("python-docx open failed: %s", exc)
        return False
    if not docx_charts_word_safe(p):
        return False
    return True
