"""Deck soft-refresh after Liber media edits."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

from case3.deck_refresh import refresh_deck_from_ir


def test_refresh_noop_without_deck(tmp_path: Path) -> None:
    assert refresh_deck_from_ir(tmp_path) is False


def test_refresh_calls_rebuild(tmp_path: Path) -> None:
    slides = tmp_path / "slides"
    slides.mkdir()
    (slides / "deck.json").write_text(
        json.dumps({"slides": [{"id": "s1", "layout": "bullets", "title": "Hi"}]}),
        encoding="utf-8",
    )
    rebuild = MagicMock()
    with patch("case3.slides_job.rebuild_slides_from_deck", rebuild):
        assert refresh_deck_from_ir(tmp_path) is True
    rebuild.assert_called_once()
    assert rebuild.call_args[0][0] == tmp_path.name
