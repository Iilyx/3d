"""Patch figure captions in TeX after regenerate/edit."""

from __future__ import annotations

from case3.figure_edit import patch_figure_caption_in_tex


_TEX = r"""
\begin{figure}[H]
  \centering
  \includegraphics[width=0.85\textwidth]{figures/fig_02.png}
  \caption{Старая подпись}
  \label{fig:fig_02}
\end{figure}
"""


def test_patch_caption_by_label() -> None:
    out = patch_figure_caption_in_tex(_TEX, "fig_02", "Кот в синей шляпе")
    assert r"\caption{Кот в синей шляпе}" in out
    assert "Старая подпись" not in out
    assert r"\label{fig:fig_02}" in out


def test_patch_escapes_specials() -> None:
    out = patch_figure_caption_in_tex(_TEX, "fig_02", "A & B_1")
    assert r"\caption{A \& B\_1}" in out


def test_patch_unknown_id_unchanged() -> None:
    assert patch_figure_caption_in_tex(_TEX, "fig_99", "x") == _TEX
