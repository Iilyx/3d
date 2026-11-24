"""Preview list edit — stable list-N ids + TeX itemize/enumerate patch."""

from __future__ import annotations

from pathlib import Path

import pytest

from case3.list_edit import (
    ListEditError,
    edit_list_in_run,
    patch_list_in_tex,
)
from case3.tex_preview import find_list_spans, tex_to_preview_blocks

_SAMPLE = r"""
\documentclass{article}
\begin{document}
\title{Demo}
\section{Intro}
Prose before.

\begin{itemize}
  \item Alpha one
  \item Beta two
\end{itemize}

Middle paragraph.

\begin{enumerate}
  \item First step
  \item Second step
  \item Third step
\end{enumerate}

Closing.
\end{document}
"""


def test_preview_assigns_stable_list_ids() -> None:
    preview = tex_to_preview_blocks(_SAMPLE)
    lists = [b for b in preview["blocks"] if b["type"] == "list"]
    assert len(lists) == 2
    assert lists[0]["id"] == "list-1"
    assert lists[0]["ordered"] is False
    assert [it["text"] for it in lists[0]["items"]] == ["Alpha one", "Beta two"]
    assert lists[1]["id"] == "list-2"
    assert lists[1]["ordered"] is True
    assert len(lists[1]["items"]) == 3


def test_find_list_spans_match_preview_count() -> None:
    spans = find_list_spans(_SAMPLE)
    preview = tex_to_preview_blocks(_SAMPLE)
    lists = [b for b in preview["blocks"] if b["type"] == "list"]
    assert len(spans) == len(lists)
    assert "itemize" in _SAMPLE[spans[0][0] : spans[0][1]]
    assert "enumerate" in _SAMPLE[spans[1][0] : spans[1][1]]


def test_patch_list_replaces_items() -> None:
    out = patch_list_in_tex(_SAMPLE, 1, ["Gamma", "Delta", "Epsilon"])
    assert "Alpha one" not in out
    assert r"\item Gamma" in out
    assert r"\item Delta" in out
    assert r"\item Epsilon" in out
    assert "enumerate" in out  # second list intact
    preview = tex_to_preview_blocks(out)
    l1 = next(b for b in preview["blocks"] if b.get("id") == "list-1")
    assert [it["text"] for it in l1["items"]] == ["Gamma", "Delta", "Epsilon"]


def test_patch_enumerate_preserves_env() -> None:
    out = patch_list_in_tex(_SAMPLE, 2, ["A", "B"], ordered=True)
    assert r"\begin{enumerate}" in out
    assert r"\item A" in out
    assert "First step" not in out


def test_patch_bad_index_raises() -> None:
    with pytest.raises(ListEditError):
        patch_list_in_tex(_SAMPLE, 99, ["x"])


def test_empty_items_raises() -> None:
    with pytest.raises(ListEditError):
        patch_list_in_tex(_SAMPLE, 1, [])


def test_edit_list_in_run_rebuilds(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    out = tmp_path / "runs" / "out" / "list_edit_run"
    out.mkdir(parents=True)
    (out / "demo.tex").write_text(_SAMPLE, encoding="utf-8")
    (out / "meta.json").write_text("{}", encoding="utf-8")

    monkeypatch.setattr(
        "case3.list_edit.rebuild_run_docs",
        lambda *a, **k: {"pdf": out / "demo.pdf"},
    )
    (out / "demo.pdf").write_bytes(b"%PDF")

    result = edit_list_in_run(
        out, 1, items=["New A", "New B"], formats={"pdf"}
    )
    assert result["list_index"] == 1
    tex = (out / "demo.tex").read_text(encoding="utf-8")
    assert r"\item New A" in tex
    assert "Alpha one" not in tex
