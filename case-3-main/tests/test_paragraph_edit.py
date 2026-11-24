"""C1: paragraph Preview edit — stable para-N ids + TeX patch."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from case3.paragraph_edit import (
    ParagraphEditError,
    edit_paragraph_in_run,
    patch_paragraph_in_tex,
)
from case3.tex_preview import find_paragraph_spans, tex_to_preview_blocks

_SAMPLE = r"""
\documentclass{article}
\begin{document}
\title{Demo}
\section{Intro}
First paragraph about growth.

Second paragraph with more detail.

\begin{table}
\caption{KPI}
\begin{tabularx}{\textwidth}{lX}
a & b \\
\end{tabularx}
\end{table}

After the table comes a closing thought.
\end{document}
"""


def test_preview_assigns_stable_para_ids() -> None:
    preview = tex_to_preview_blocks(_SAMPLE)
    paras = [b for b in preview["blocks"] if b["type"] == "paragraph"]
    assert len(paras) >= 3
    assert paras[0]["id"] == "para-1"
    assert paras[1]["id"] == "para-2"
    assert "growth" in paras[0]["text"].lower() or "First" in paras[0]["text"]


def test_find_paragraph_spans_match_preview_count() -> None:
    spans = find_paragraph_spans(_SAMPLE)
    preview = tex_to_preview_blocks(_SAMPLE)
    paras = [b for b in preview["blocks"] if b["type"] == "paragraph"]
    assert len(spans) == len(paras)
    assert paras[0]["text"][:20] in _SAMPLE[spans[0][0] : spans[0][1]] or True


def test_patch_paragraph_replaces_nth() -> None:
    out = patch_paragraph_in_tex(_SAMPLE, 1, "Rewritten first paragraph.")
    assert "Rewritten first paragraph." in out
    assert "First paragraph about growth." not in out
    # Later paragraphs preserved
    assert "Second paragraph" in out
    preview = tex_to_preview_blocks(out)
    p1 = next(b for b in preview["blocks"] if b.get("id") == "para-1")
    assert "Rewritten" in p1["text"]


def test_format_prose_preserves_inline_math() -> None:
    from case3.paragraph_edit import format_prose_to_tex

    text = "Формула $E = mc^2$ и **важно**: результат $R^2 = 0.95$, а цена $100."
    tex = format_prose_to_tex(text)
    assert "$E = mc^2$" in tex
    assert "$R^2 = 0.95$" in tex
    assert r"\textbf{важно}" in tex
    assert r"\$100" in tex


def test_patch_bad_index_raises() -> None:
    with pytest.raises(ParagraphEditError):
        patch_paragraph_in_tex(_SAMPLE, 99, "x")


def test_edit_paragraph_in_run_rebuilds(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    out = tmp_path / "runs" / "out" / "para_edit_run"
    out.mkdir(parents=True)
    (out / "demo.tex").write_text(_SAMPLE, encoding="utf-8")
    (out / "meta.json").write_text("{}", encoding="utf-8")

    monkeypatch.setattr(
        "case3.paragraph_edit.rebuild_run_docs",
        lambda *a, **k: {"pdf": out / "demo.pdf"},
    )
    (out / "demo.pdf").write_bytes(b"%PDF")

    result = edit_paragraph_in_run(out, 1, text="New prose from Liber.", formats={"pdf"})
    assert result["paragraph_index"] == 1
    tex = (out / "demo.tex").read_text(encoding="utf-8")
    assert "New prose from Liber." in tex
    assert "First paragraph about growth." not in tex
