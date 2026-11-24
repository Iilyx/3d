"""Deck JSON buried in model prose still parses."""

from __future__ import annotations

import json

from case3.slides_job import _extract_json_object, _retry_user


def test_extract_picks_the_deck_buried_in_prose() -> None:
    deck = {
        "version": 1,
        "slides": [
            {"id": "s01", "layout": "title", "title": "Неделя"},
            {"id": "s02", "layout": "closing", "title": "Дальше"},
        ],
    }
    raw = (
        'First I would sketch {"note": "not a deck"} and then the answer.\n'
        + json.dumps(deck, ensure_ascii=False)
        + "\nThat covers the ask."
    )
    data = _extract_json_object(raw)
    assert [s["id"] for s in data["slides"]] == ["s01", "s02"]


def test_retry_keeps_the_source() -> None:
    text = _retry_user("Source: нанять двух продавцов", "no JSON", "86")
    assert "нанять двух продавцов" in text
    assert "no JSON" in text
    assert "slides" in text
