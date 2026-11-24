"""Put an attached PDF/DOCX extract back into Source before the report gate."""

from __future__ import annotations

import re
from pathlib import Path

_INGEST_ID_OK = re.compile(r"^[0-9]{8}T[0-9]{6}Z_[0-9a-f]{6}$")


def ingested_markdown(root: Path, ingest_id: str) -> str:
    """Markdown saved at upload time. Empty when the id or the file is missing."""
    ingest_id = (ingest_id or "").strip()
    if not _INGEST_ID_OK.match(ingest_id):
        return ""
    folder = (Path(root) / "runs" / "uploads" / "ingest" / ingest_id).resolve()
    base = (Path(root) / "runs" / "uploads" / "ingest").resolve()
    try:
        folder.relative_to(base)
    except ValueError:
        return ""
    path = folder / "source.txt"
    try:
        return path.read_text(encoding="utf-8").strip()
    except OSError:
        return ""


def merge_ingested_sources(
    source_body: str,
    attachments: list[dict] | None,
    root: Path,
) -> str:
    """The posted body plus every attached extract that is not already in it.

    A report request can arrive as only «сделай отчет», while the PDF table
    sits in the ingest folder. The gate then refuses a document that is there.
    """
    raw = source_body or ""
    body = raw.strip()
    extracts: list[str] = []
    seen: set[str] = set()
    for row in attachments or []:
        if not isinstance(row, dict):
            continue
        ingest_id = str(row.get("ingestId") or "").strip()
        if not ingest_id or ingest_id in seen:
            continue
        seen.add(ingest_id)
        text = ingested_markdown(root, ingest_id)
        if text and text not in body and text not in extracts:
            extracts.append(text)
    if not extracts:
        return raw
    if body and not any(body in text for text in extracts):
        return "\n\n".join([*extracts, body])
    return "\n\n".join(extracts)
