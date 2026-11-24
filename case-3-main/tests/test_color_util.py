"""color_util hex round-trip."""

from case3.color_util import expand_hex, hex_to_rgb, norm_hex


def test_expand_short():
    assert expand_hex("#abc") == "#AABBCC"


def test_norm_hex_valid():
    assert norm_hex("2e4208") == "#2E4208"
    assert norm_hex("#fff") == "#FFFFFF"


def test_norm_hex_fallback():
    assert norm_hex("nope", "#14161A") == "#14161A"
    assert norm_hex(None, "#abc") == "#AABBCC"


def test_hex_to_rgb():
    assert hex_to_rgb("#2E4208") == (0x2E, 0x42, 0x08)
    assert hex_to_rgb("#abc") == (0xAA, 0xBB, 0xCC)
    assert hex_to_rgb("nope") is None
    assert hex_to_rgb("#gg0000") is None
