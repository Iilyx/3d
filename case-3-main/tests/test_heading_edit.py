"""Preview heading edit — stable 1-based index + TeX section patch."""

from __future__ import annotations

from pathlib import Path

import pytest

from case3.heading_edit import (
    HeadingEditError,
    edit_heading_in_run,
    patch_heading_in_tex,
)
from case3.tex_preview import find_heading_spans, tex_to_preview_blocks

_SAMPLE = """
\\documentclass{article}
\\begin{document}
\\title{Demo}
\\section{Intro}
First paragraph about growth.

\\subsection{Details}
More detail here.

\\section{Outro}
Closing thought.
\\end{document}
"""


def test_preview_heading_order() -> None:
    preview = tex_to_preview_blocks(_SAMPLE)
    heads = [b for b in preview["blocks"] if b["type"] == "heading"]
    assert len(heads) == 3
    assert heads[0]["text"] == "Intro"
    assert heads[0]["level"] == 1
    assert heads[1]["text"] == "Details"
    assert heads[1]["level"] == 2
    assert heads[2]["text"] == "Outro"


def test_find_heading_spans_match_preview_count() -> None:
    spans = find_heading_spans(_SAMPLE)
    preview = tex_to_preview_blocks(_SAMPLE)
    heads = [b for b in preview["blocks"] if b["type"] == "heading"]
    assert len(spans) == len(heads)
    assert "Intro" in _SAMPLE[spans[0][0] : spans[0][1]]


def test_patch_heading_replaces_nth() -> None:
    out = patch_heading_in_tex(_SAMPLE, 1, "Introduction")
    assert r"\section{Introduction}" in out
    assert r"\section{Intro}" not in out
    assert r"\subsection{Details}" in out
    preview = tex_to_preview_blocks(out)
    h1 = next(b for b in preview["blocks"] if b["type"] == "heading")
    assert h1["text"] == "Introduction"


def test_patch_subsection() -> None:
    out = patch_heading_in_tex(_SAMPLE, 2, "Deep dive")
    assert r"\subsection{Deep dive}" in out
    assert r"\subsection{Details}" not in out


def test_patch_bad_index_raises() -> None:
    with pytest.raises(HeadingEditError):
        patch_heading_in_tex(_SAMPLE, 99, "x")


def test_empty_heading_raises() -> None:
    with pytest.raises(HeadingEditError):
        patch_heading_in_tex(_SAMPLE, 1, "  ")


def test_edit_heading_in_run_rebuilds(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    out = tmp_path / "runs" / "out" / "head_edit_run"
    out.mkdir(parents=True)
    (out / "demo.tex").write_text(_SAMPLE, encoding="utf-8")
    (out / "meta.json").write_text("{}", encoding="utf-8")

    monkeypatch.setattr(
        "case3.heading_edit.rebuild_run_docs",
        lambda *a, **k: {"pdf": out / "demo.pdf"},
    )
    (out / "demo.pdf").write_bytes(b"%PDF")

    result = edit_heading_in_run(out, 1, text="Renamed", formats={"pdf"})
    assert result["heading_index"] == 1
    tex = (out / "demo.tex").read_text(encoding="utf-8")
    assert r"\section{Renamed}" in tex
