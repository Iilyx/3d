"""User-chosen document title must win over model \\title; D3 title scaffold."""

from __future__ import annotations

from case3.api import build_intent_from_ui
from case3.generate import apply_doc_title, doc_title_from_intent, ensure_title_block


def test_intent_includes_forced_title() -> None:
    intent = build_intent_from_ui(
        chat="Сделай отчёт",
        chart_types=[],
        max_charts=0,
        max_images=0,
        forbid_charts=True,
        forbid_images=True,
        doc_title="Демография 2019–2023",
    )
    assert "Демография 2019–2023" in intent
    assert doc_title_from_intent(intent) == "Демография 2019–2023"


def test_apply_doc_title_rewrites_title() -> None:
    tex = r"""\documentclass{article}
\title{Старое}
\author{}
\begin{document}
\maketitle
Hi
\end{document}
"""
    out = apply_doc_title(tex, "Новый отчёт & co")
    assert r"\title{Новый отчёт \& co}" in out
    assert "Старое" not in out


def test_ensure_title_block_fills_missing_scaffold() -> None:
    tex = r"""\documentclass{article}
\begin{document}
Hello
\end{document}
"""
    out = ensure_title_block(tex)
    assert r"\title{" in out
    assert r"\author{}" in out
    assert r"\date{\today}" in out
    assert r"\maketitle" in out


def test_ensure_title_block_keeps_model_title() -> None:
    tex = r"""\documentclass{article}
\title{Рост выручки Q3}
\author{Иванов}
\date{1 января}
\begin{document}
Текст
\end{document}
"""
    out = ensure_title_block(tex)
    assert r"\title{Рост выручки Q3}" in out
    assert r"\author{}" in out
    assert r"\date{\today}" in out
    assert r"\maketitle" in out
    assert "Иванов" not in out


def test_empty_settings_title_does_not_force() -> None:
    intent = build_intent_from_ui(
        chat="Сделай отчёт",
        chart_types=[],
        max_charts=1,
        max_images=0,
        forbid_charts=False,
        forbid_images=True,
        doc_title="",
    )
    assert doc_title_from_intent(intent) is None
    assert "CASE3_DOC_TITLE" not in intent
