"""Win desk 080546: truncated LaTeX (1 short section) + all media appended at end."""

from case3.generate import tex_body_is_sparse, tex_body_needs_source_fill


def test_one_paragraph_plus_appended_slots_needs_fill() -> None:
    """Letter count >40 so not sparse — still a media dump, must fill from Source."""
    tex = r"""\documentclass{article}
\begin{document}
\maketitle
\section{Введение и контекст}
Мировая экономика переживает беспрецедентную трансформацию, где искусственный интеллект перестал быть технологической новинкой и стал критическим фактором производства для Республики Беларусь.
%CASE3_FIG:fig_01%
%CASE3_FIG:fig_02%
%CASE3_FIG:fig_03%
%CASE3_FIG:fig_04%
%CASE3_CHART:cht_01%
%CASE3_CHART:cht_02%
%CASE3_CHART:cht_03%
%CASE3_CHART:cht_04%
\end{document}
"""
    assert not tex_body_is_sparse(tex)
    assert tex_body_needs_source_fill(tex)


def test_real_report_with_interleaved_media_untouched() -> None:
    tex = r"""\documentclass{article}
\begin{document}
\section{Введение}
Подробный абзац про экономику Беларуси и искусственный интеллект с достаточным объёмом текста для отчёта.
%CASE3_CHART:cht_01%
\section{Сектора}
Ещё один полный абзац про банки, промышленность и государственное управление с цифрами и выводами.
%CASE3_FIG:fig_01%
\section{Риски}
Третий развёрнутый абзац про кадровый дефицит, импорт чипов и регуляторные барьеры в регионе.
\end{document}
"""
    assert not tex_body_needs_source_fill(tex)


def test_charts_only_still_needs_fill() -> None:
    tex = r"""\documentclass{article}
\begin{document}
\maketitle
%CASE3_CHART:cht_01%
%CASE3_CHART:cht_02%
\end{document}
"""
    assert tex_body_is_sparse(tex)
    assert tex_body_needs_source_fill(tex)
