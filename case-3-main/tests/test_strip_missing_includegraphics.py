"""Drop \\includegraphics whose PNG is absent under the render workdir."""

from __future__ import annotations

from pathlib import Path

from case3.inject import strip_missing_media_includes


def test_strips_missing_png_keeps_present(tmp_path: Path) -> None:
    figs = tmp_path / "figures"
    figs.mkdir()
    (figs / "fig_01.png").write_bytes(b"\x89PNG\r\n\x1a\n" + b"x" * 20)
    tex = r"""\documentclass{article}
\begin{document}
\includegraphics[width=0.85\textwidth]{figures/fig_01.png}
\includegraphics[width=\linewidth]{figures/fig_02.png}
\begin{figure}[H]
\centering
\includegraphics{figures/cht_01.png}
\caption{Gone}
\end{figure}
\end{document}
"""
    out = strip_missing_media_includes(tex, tmp_path)
    assert r"{figures/fig_01.png}" in out
    assert "fig_02" not in out
    assert "cht_01" not in out
    assert r"\begin{figure}" not in out


def test_strips_missing_bare_dia_png(tmp_path: Path) -> None:
    tex = r"""\documentclass{article}
\begin{document}
\includegraphics[width=0.85\textwidth]{dia_0.png}
\end{document}
"""
    out = strip_missing_media_includes(tex, tmp_path)
    assert "dia_0" not in out
    assert r"\includegraphics" not in out


def test_strips_png_name_that_is_actually_bmp(tmp_path: Path) -> None:
    figs = tmp_path / "figures"
    figs.mkdir()
    (figs / "cht_04.png").write_bytes(b"BM" + b"\x00" * 20)
    (figs / "cht_01.png").write_bytes(b"\x89PNG\r\n\x1a\n" + b"x" * 20)
    tex = r"""\documentclass{article}
\begin{document}
\includegraphics{figures/cht_01.png}
\includegraphics{figures/cht_04.png}
\end{document}
"""
    out = strip_missing_media_includes(tex, tmp_path)
    assert "cht_01" in out
    assert "cht_04" not in out
