"""PPTX title/body fonts: role priority + Liber→Office mapping (gap audit P0)."""

from __future__ import annotations

from pathlib import Path
from zipfile import ZipFile

from case3.slides_pptx_native import _fonts_from_style, build_native_pptx


def test_fonts_prefer_body_over_fallback_pptx() -> None:
    deck = {
        "style": {
            "fonts": {
                "title": "Georgia",
                "body": "Arial",
                "fallback_pptx": "Calibri",
            }
        }
    }
    title, body = _fonts_from_style(deck)
    assert title == "Georgia"
    assert body == "Arial"


def test_fonts_fallback_pptx_only_when_body_missing() -> None:
    deck = {
        "style": {
            "fonts": {
                "title": "Georgia",
                "fallback_pptx": "Arial",
            }
        }
    }
    _title, body = _fonts_from_style(deck)
    assert body == "Arial"


def test_liber_serif_maps_to_georgia() -> None:
    deck = {
        "style": {
            "fonts": {
                "title": "Liber Serif",
                "body": "Liber Sans",
                "fallback_pptx": "Calibri",
            }
        }
    }
    title, body = _fonts_from_style(deck)
    assert title == "Georgia"
    assert body == "Calibri"


def test_aptos_display_maps_to_aptos() -> None:
    deck = {
        "style": {
            "fonts": {
                "title": "Aptos Display",
                "body": "Aptos",
                "fallback_pptx": "Calibri",
            }
        }
    }
    title, body = _fonts_from_style(deck)
    assert title == "Aptos"
    assert body == "Aptos"


def test_atelier_pack_titles_are_georgia_not_calibri() -> None:
    deck = {
        "style": {
            "fonts": {
                "title": "Liber Serif",
                "body": "Liber Sans",
                "fallback_pptx": "Calibri",
            }
        }
    }
    title, body = _fonts_from_style(deck)
    assert title == "Georgia"
    assert title != "Calibri"
    assert body == "Calibri"


def test_native_pptx_sets_title_and_body_typefaces(tmp_path: Path) -> None:
    deck = {
        "version": 1,
        "aspect": "16:9",
        "palette": "atelier",
        "language": "ru",
        "style": {
            "fonts": {
                "title": "Liber Serif",
                "body": "Liber Sans",
                "fallback_pptx": "Calibri",
            },
            "brand_mark": "LIBER · ATELIER",
        },
        "slides": [
            {
                "id": "s01",
                "layout": "title",
                "title": "Итоги Q3",
                "subtitle": "Краткий разбор",
            },
            {
                "id": "s02",
                "layout": "bullets",
                "title": "Пункты",
                "bullets": ["Один", "Два"],
            },
        ],
    }
    out = build_native_pptx(deck, tmp_path / "fonts.pptx")
    assert out.is_file()
    # OOXML: a:latin typeface must reflect mapped Office fonts (not silent Calibri titles).
    with ZipFile(out) as zf:
        slide_xml = zf.read("ppt/slides/slide1.xml").decode("utf-8")
        slide2_xml = zf.read("ppt/slides/slide2.xml").decode("utf-8")
    assert 'typeface="Georgia"' in slide_xml
    # Body / subtitle should use Calibri (mapped Liber Sans) somewhere on title or bullets slide
    assert 'typeface="Calibri"' in slide_xml or 'typeface="Calibri"' in slide2_xml
