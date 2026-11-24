"""artifact_downloads must keep PPTX / deck_pdf after Liber edits."""

from __future__ import annotations

import json
from pathlib import Path

from case3.run_store import artifact_downloads


def test_artifact_downloads_includes_pptx_and_deck_pdf(tmp_path: Path) -> None:
    out = tmp_path
    (out / "report.pdf").write_bytes(b"%PDF")
    (out / "report.docx").write_bytes(b"PK")
    (out / "deck.pptx").write_bytes(b"PK")
    (out / "deck_deck.pdf").write_bytes(b"%PDF")
    (out / "meta.json").write_text(
        json.dumps(
            {
                "slides_artifacts": {
                    "pptx": "deck.pptx",
                    "deck_pdf": "deck_deck.pdf",
                }
            }
        ),
        encoding="utf-8",
    )
    files = artifact_downloads("run1", out, version=9)
    assert "pdf" in files and "report.pdf" in files["pdf"]
    assert "docx" in files
    assert files["pptx"].endswith("deck.pptx?v=9")
    assert files["deck_pdf"].endswith("deck_deck.pdf?v=9")
    assert "_deck.pdf" not in files.get("pdf", "")


def test_artifact_downloads_without_meta_still_finds_pptx(tmp_path: Path) -> None:
    out = tmp_path
    (out / "deck.pptx").write_bytes(b"PK")
    files = artifact_downloads("run1", out, version=1)
    assert "pptx" in files
