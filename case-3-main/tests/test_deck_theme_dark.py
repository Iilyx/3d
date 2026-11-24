"""Shared is_dark_pack helper."""

from __future__ import annotations

from case3.deck_theme import is_dark_pack


def test_is_dark_pack_by_pack_id() -> None:
    assert is_dark_pack({"pack_id": "ink"}) is True
    assert is_dark_pack({"pack_id": "atelier"}) is False
    assert is_dark_pack(None) is False


def test_is_dark_pack_by_motif_atmosphere() -> None:
    assert is_dark_pack({"pack_id": "atelier", "motif": {"atmosphere": "dark"}}) is True
    assert is_dark_pack({"motif": {"atmosphere": "light"}}) is False
