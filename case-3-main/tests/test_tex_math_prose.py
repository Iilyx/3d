"""Cyrillic inside math and bare math commands must not fail XeLaTeX."""

from __future__ import annotations

from case3.tex_preamble import ensure_document_preamble
from case3.tex_prose import harden_math_prose


def test_lifts_cyrillic_out_of_inline_math() -> None:
    tex = r"Каждому достанется $50 \div 4 = 13 литров$, маме оставить 17."
    out = harden_math_prose(tex)
    assert r"$50 \div 4 = 13$" in out
    assert "литров" in out
    assert "$50 \\div 4 = 13 литров$" not in out


def test_mathrm_cyrillic_uses_text_font() -> None:
    tex = r"Остаток $17~\mathrm{литров}$."
    out = harden_math_prose(tex)
    assert r"\mathrm{литров}" not in out
    assert r"\text{литров}" in out


def test_bare_div_outside_math_becomes_unicode() -> None:
    tex = r"Делёж: 50 \div 4 = 13 литров."
    out = harden_math_prose(tex)
    assert r"\div" not in out
    assert "50 ÷ 4 = 13 литров" in out


def test_text_command_outside_math_is_unwrapped() -> None:
    tex = r"Оставить \text{маме с папой} 17 литров."
    out = harden_math_prose(tex)
    assert r"\text" not in out
    assert "маме с папой" in out


def test_real_formula_stays() -> None:
    tex = r"Формула $E = mc^2$ не трогается."
    assert harden_math_prose(tex) == tex


def test_odd_dollar_does_not_swallow_the_rest() -> None:
    tex = r"Цена $100 и дальше обычный текст про масло."
    out = harden_math_prose(tex)
    assert out.count("$") % 2 == 0


def test_preamble_loads_amsmath_before_hyperref() -> None:
    raw = r"\documentclass{article}" "\n" r"\begin{document}" "\n" r"Hi" "\n" r"\end{document}"
    out = ensure_document_preamble(raw)
    assert r"\usepackage{amsmath}" in out
    assert out.index("amsmath") < out.index("hyperref")
