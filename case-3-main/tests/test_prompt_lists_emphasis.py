"""D6: system prompt must teach itemize/enumerate/emph as first-class."""

from __future__ import annotations

from case3.prompts import load


def test_system_tex_lists_and_emphasis_guidance() -> None:
    text = load(
        "system_tex",
        MAX_IMAGES=0,
        MAX_CHARTS=0,
        MAX_DIAGRAMS=0,
        PALETTE_TABLE="",
    )
    assert r"\begin{itemize}" in text
    assert r"\begin{enumerate}" in text
    assert r"\textbf{" in text or r"\textbf{…}" in text
    assert r"\emph{" in text or r"\emph{…}" in text
    assert "Lists & emphasis" in text or "D6" in text
