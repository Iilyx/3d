"""G2/G3: pack style-lock + brand-safe harden for Image API prompts."""

from __future__ import annotations

import re

import pytest

from case3.image_prompt import (
    ImagePromptError,
    apply_pack_style_lock,
    brand_safe_negative,
    harden_brand_safe,
    pack_style_suffix,
    prepare_image_prompt,
    sanitize_image_prompt,
)


def test_pack_style_botanical_and_atelier() -> None:
    b = pack_style_suffix("botanical")
    assert "fern" in b.lower() or "olive" in b.lower()
    assert "neon" in b.lower()
    a = pack_style_suffix("atelier")
    assert "cream" in a.lower() or "olive" in a.lower()
    assert len(a) <= 120


def test_pack_style_unknown_falls_back_atelier() -> None:
    u = pack_style_suffix("nope")
    a = pack_style_suffix("atelier")
    assert u == a


def test_apply_pack_style_lock_appends_not_replaces() -> None:
    subj = "Ceramic cup on oak desk, soft window light"
    out = apply_pack_style_lock(subj, "board")
    assert out.startswith(subj)
    assert "gray" in out.lower() or "corporate" in out.lower() or "steel" in out.lower()


def test_harden_strips_handshake_and_purple_glow() -> None:
    raw = "Business handshake in glass office with purple neon glow"
    out = harden_brand_safe(raw)
    assert "handshake" not in out.lower()
    assert "purple neon" not in out.lower()
    assert "editorial" in out.lower() or "matte" in out.lower()
    assert "violet" in out.lower() or "purple" in out.lower()  # anti-purple line
    # No orphaned preposition debris after strip
    assert " with in " not in f" {out.lower()} "
    assert not re.search(r"\bwith in\b", out, re.I)


def test_harden_stock_sentence_stays_readable() -> None:
    out = harden_brand_safe(
        "handshake meeting with purple glow in glass office"
    )
    assert "handshake" not in out.lower()
    assert "glass office" not in out.lower()
    assert not re.search(r"\bwith in\b", out, re.I)
    assert "meeting" in out.lower() or "editorial" in out.lower()


def test_harden_keeps_subject() -> None:
    subj = "Fern frond on warm paper, soft daylight"
    out = harden_brand_safe(subj)
    assert "Fern frond" in out
    assert "editorial" in out.lower() or "matte" in out.lower()


def test_brand_safe_negative_lists_stock_bans() -> None:
    neg = brand_safe_negative()
    low = neg.lower()
    assert "handshake" in low
    assert "watermark" in low
    assert "purple" in low or "violet" in low


def test_prepare_image_prompt_full_pipeline() -> None:
    out = prepare_image_prompt(
        "Warehouse aisle with cardboard boxes, natural light",
        pack_id="atelier",
    )
    assert "Warehouse aisle" in out
    assert "cream" in out.lower() or "olive" in out.lower() or "atelier" in out.lower() or "editorial" in out.lower()
    assert "Avoid:" in out or "no violet" in out.lower()
    assert len(out) <= 800


def test_prepare_rejects_cyrillic() -> None:
    with pytest.raises(ImagePromptError):
        prepare_image_prompt("Склад с коробками", pack_id="atelier")


def test_sanitize_still_alone() -> None:
    assert sanitize_image_prompt("Sharp product photo on linen").startswith("Sharp")
