"""G2: preview blocks expose per-chart palette for edit sheet seed."""

from __future__ import annotations

from case3.tex_preview import build_report_preview


def test_preview_includes_chart_palette() -> None:
    tex = r"""
\documentclass{article}
\begin{document}
\section{A}
\begin{figure}[H]
\centering
\includegraphics[width=0.85\textwidth]{figures/cht_01.png}
\caption{Клиенты}
\end{figure}
\end{document}
"""
    fj = {
        "charts": [
            {
                "id": "cht_01",
                "type": "bar",
                "palette": "ocean",
                "caption": "Клиенты",
                "html": "<canvas></canvas>",
            }
        ]
    }
    media = {"cht_01": {"ok": True, "kind": "chart"}}
    preview = build_report_preview(
        tex,
        run_id="r1",
        figures_json=fj,
        media_status=media,
    )
    figs = [b for b in preview["blocks"] if b.get("type") == "figure"]
    assert figs
    assert figs[0]["chartType"] == "bar"
    assert figs[0]["palette"] == "ocean"
