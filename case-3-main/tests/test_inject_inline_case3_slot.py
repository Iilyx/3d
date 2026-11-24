"""LLM puts %CASE3_FIG:id% inside \\includegraphics{…} — % comments out the closing brace."""

from case3.inject import inject_media, rewrite_inline_slot_includegraphics


def test_rewrite_inline_fig_slot_to_path() -> None:
    raw = r"\includegraphics[width=\linewidth]{%CASE3_FIG:fig_02%}"
    assert (
        rewrite_inline_slot_includegraphics(raw)
        == r"\includegraphics[width=\linewidth]{figures/fig_02.png}"
    )


def test_inject_heals_inline_slot_before_latex() -> None:
    tex = r"""\documentclass{article}
\begin{document}
\begin{figure}[H]
\centering
\includegraphics[width=\linewidth]{%CASE3_FIG:fig_02%}
\caption{Современный завод}
\end{figure}
\end{document}
"""
    status = {"fig_02": {"ok": True, "kind": "figure"}}
    figures = [
        {"id": "fig_02", "caption": "Современный завод", "width": r"0.85\textwidth"}
    ]
    out = inject_media(tex, figures, [], status)
    assert r"%CASE3_FIG:" not in out
    assert r"\includegraphics[width=\linewidth]{figures/fig_02.png}" in out
    assert r"\caption{Современный завод}" in out


def test_failed_inline_slot_stripped() -> None:
    tex = (
        r"\begin{figure}[H]"
        r"\includegraphics{%CASE3_FIG:fig_01%}"
        r"\caption{X}\end{figure}"
    )
    out = inject_media(
        tex,
        [{"id": "fig_01", "caption": "X", "width": r"0.85\textwidth"}],
        [],
        {"fig_01": {"ok": False, "error": "api", "kind": "figure"}},
    )
    assert "%CASE3_FIG" not in out
    assert r"\includegraphics" not in out
