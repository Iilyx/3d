"""Theme pack resolve for Liber decks (Julius parity)."""

from __future__ import annotations

import pytest

from case3.deck_theme import PACK_IDS, ThemeTokens, resolve_deck_theme


def test_resolve_default_atelier() -> None:
    tok = resolve_deck_theme(None)
    assert tok.pack_id == "atelier"
    assert tok.colors["primary"].startswith("#")
    assert tok.fonts["fallback_pptx"]


def test_resolve_unknown_falls_back_atelier() -> None:
    tok = resolve_deck_theme("not-a-pack")
    assert tok.pack_id == "atelier"


def test_resolve_board_pack() -> None:
    tok = resolve_deck_theme("board")
    assert tok.pack_id == "board"
    assert tok.colors["primary"].upper() in {"#172D40", "#142C40", "#17324D", "#1B3A4B"}
    assert "teal" in tok.label.lower() or "board" in tok.label.lower() or tok.colors["accent"]


def test_style_settings_override_accent() -> None:
    tok = resolve_deck_theme(
        "atelier",
        style_settings={"accent": "#FF5B23", "fontTitle": "Arial"},
    )
    assert tok.colors["accent"].upper() == "#FF5B23"
    assert tok.fonts["title"] == "Arial"
    assert tok.fonts["fallback_pptx"]  # still present


def test_tokens_to_css_vars() -> None:
    tok = resolve_deck_theme("atelier")
    css = tok.css_vars()
    assert "--deck-primary:" in css
    assert "--deck-accent:" in css


def test_pack_ids_include_board_and_signal() -> None:
    assert "atelier" in PACK_IDS
    assert "board" in PACK_IDS
    assert "signal" in PACK_IDS


def test_resolve_botanical_vesper_alias() -> None:
    tok = resolve_deck_theme("vesper")
    assert tok.pack_id == "botanical"
    assert tok.motif.get("atmosphere") == "dark"
    assert tok.motif.get("hero_bleed") is True
    assert tok.colors["sheet"].upper() == "#101F19"
    assert tok.colors["foil"].upper() == "#C4AD7A"


def test_theme_tokens_frozen_dict() -> None:
    tok = resolve_deck_theme("signal")
    assert isinstance(tok, ThemeTokens)
    d = tok.as_dict()
    assert d["pack_id"] == "signal"
    assert "colors" in d and "fonts" in d
