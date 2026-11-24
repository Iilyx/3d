"""Trailing gallery dumps / EOF media piles must be scattered into prose."""

from case3.tex_media_place import (
    media_slots_pile_at_eof,
    redistribute_gallery_slots,
)


def test_081536_signature_slots_leave_gallery() -> None:
    tex = r"""\documentclass{article}
\begin{document}
\section{Введение и контекст}
Текст про экономику и рынок ИИ в Беларуси.

\section{Секторальный анализ внедрения}
\subsection{Промышленность и ЗПК}
Заводы и цифровые двойники.

\subsection{Сельское хозяйство}
Дроны и посевы.

\section{Визуализация данных}
\subsection{Динамика рынка ИИ}
%CASE3_CHART:cht_01%
\subsection{Бюджет по секторам}
%CASE3_CHART:cht_02%
\section{Иллюстрации}
\subsection{Роботизированный цех}
%CASE3_FIG:fig_02%
\subsection{Дроны в поле}
%CASE3_FIG:fig_03%
\end{document}
"""
    charts = [
        {"id": "cht_01", "caption": "Динамика рынка ИИ в РБ (2020–2030)"},
        {"id": "cht_02", "caption": "Распределение бюджета на ИИ по секторам"},
    ]
    figures = [
        {"id": "fig_02", "caption": "Роботизированный цех промышленности"},
        {"id": "fig_03", "caption": "Умное сельское хозяйство с дронами"},
    ]
    out = redistribute_gallery_slots(tex, figures=figures, charts=charts)
    assert r"\section{Визуализация" not in out
    assert r"\section{Иллюстрации}" not in out
    # slots survive
    assert "%CASE3_CHART:cht_01%" in out
    assert "%CASE3_FIG:fig_02%" in out
    # charts/figs appear before former gallery — inside earlier sections
    viz_gone_body = out.split(r"\begin{document}", 1)[-1]
    assert viz_gone_body.index("%CASE3_CHART:cht_01%") < viz_gone_body.index(
        r"\section{Секторальный"
    ) or "%CASE3_CHART:cht_01%" in out.split(r"\section{Введение", 1)[-1].split(
        r"\section{Секторальный", 1
    )[0]
    # factory fig near industry, drone near agriculture
    ind = out.split(r"\subsection{Промышленность", 1)[-1]
    assert "%CASE3_FIG:fig_02%" in ind.split(r"\subsection{", 1)[0]
    ag = out.split(r"\subsection{Сельское", 1)[-1]
    assert "%CASE3_FIG:fig_03%" in ag.split(r"\subsection{", 1)[0]


def test_no_gallery_untouched() -> None:
    tex = r"""\documentclass{article}
\begin{document}
\section{A}
Текст.
%CASE3_CHART:cht_01%
\section{B}
Ещё текст.
\end{document}
"""
    out = redistribute_gallery_slots(
        tex,
        figures=[],
        charts=[{"id": "cht_01", "caption": "X"}],
    )
    assert out == tex


def test_082722_appendix_subsection_grafiki_with_figure_envs() -> None:
    """Win desk 082722: appendix + \\subsection{Графики} wraps slots in figure envs."""
    tex = r"""\documentclass{article}
\begin{document}
\section{Введение}
Контекст цифровизации.

\section{Секторальный анализ}
\subsection{Промышленность и ЗПК}
Заводы и ЗПК.

\subsection{Финансовый сектор}
Банки и ROI.

\section{Приложение: Детализированные данные для визуализации}
\subsection{Графики}
\textbf{График 2: Распределение бюджета}
\begin{figure}[H]
\centering
%CASE3_CHART:cht_03%
\caption{Дефицит кадров ИИ-специалистов}
\end{figure}
\begin{figure}[H]
\centering
%CASE3_CHART:cht_07%
\caption{ROI от внедрения ИИ в банках}
\end{figure}
\end{document}
"""
    charts = [
        {"id": "cht_03", "caption": "Дефицит кадров ИИ-специалистов"},
        {"id": "cht_07", "caption": "ROI от внедрения ИИ в банках"},
    ]
    out = redistribute_gallery_slots(tex, figures=[], charts=charts)
    assert r"\subsection{Графики}" not in out
    assert r"\section{Приложение" not in out
    assert "%CASE3_CHART:cht_03%" in out
    assert "%CASE3_CHART:cht_07%" in out
    # figure wrappers from dump must not survive as empty shells
    assert out.count(r"\begin{figure}") == 0
    fin = out.split(r"\subsection{Финансовый", 1)[-1]
    assert "%CASE3_CHART:cht_07%" in fin.split(r"\section{", 1)[0]


def test_synonym_match_factory_to_industry() -> None:
    tex = r"""\documentclass{article}
\begin{document}
\section{Обзор}
Текст.

\section{Отрасли}
\subsection{Промышленность}
Цифровые двойники на заводах.

\subsection{Логистика}
Цепочки поставок.

\section{Иллюстрации}
\subsection{Цех}
%CASE3_FIG:fig_01%
\end{document}
"""
    figures = [{"id": "fig_01", "caption": "Роботизированный заводской цех"}]
    out = redistribute_gallery_slots(tex, figures=figures, charts=[])
    ind = out.split(r"\subsection{Промышленность", 1)[-1]
    assert "%CASE3_FIG:fig_01%" in ind.split(r"\subsection{", 1)[0]


def test_eof_media_pile_force_redistribute() -> None:
    """Slots piled in last 20% without a named gallery still get scattered."""
    prose = (
        "\\section{A}\n"
        + ("Параграф про рынок и бюджет. " * 40)
        + "\n\\section{B}\n"
        + ("Текст про промышленность и заводы. " * 40)
        + "\n"
    )
    pile = (
        "%CASE3_CHART:cht_01%\n"
        "%CASE3_CHART:cht_02%\n"
        "%CASE3_FIG:fig_01%\n"
        "%CASE3_FIG:fig_02%\n"
    )
    tex = (
        "\\documentclass{article}\n\\begin{document}\n"
        + prose
        + pile
        + "\\end{document}\n"
    )
    assert media_slots_pile_at_eof(tex) is True
    out = redistribute_gallery_slots(
        tex,
        figures=[
            {"id": "fig_01", "caption": "Цех промышленности"},
            {"id": "fig_02", "caption": "Склад логистики"},
        ],
        charts=[
            {"id": "cht_01", "caption": "Рынок ИИ"},
            {"id": "cht_02", "caption": "Бюджет"},
        ],
    )
    body = out.split(r"\begin{document}", 1)[-1]
    # not all four still glued at the very end
    tail = body[-200:]
    assert tail.count("%CASE3_") < 4
    assert "%CASE3_CHART:cht_01%" in body


def test_schedule_section_with_grafik_title_preserves_prose_and_following_sections() -> None:
    """Section 'График реализации проекта' (schedule) must not wipe prose or later sections."""
    tex = r"""\documentclass{article}
\begin{document}
\section{Введение}
Обзор инвестпроекта модернизации линии.

\section{График реализации проекта и платежей}
Проект разделён на три этапа: проектирование в Q1, поставка оборудования в Q2 и пусконаладка в Q3.
Общий бюджет этапа составляет 120 млн руб.
%CASE3_CHART:cht_01%

\section{Заключение и ключевые выводы}
Итоговый срок окупаемости составляет 2,4 года при сохранении текущей загрузки.
\end{document}
"""
    out = redistribute_gallery_slots(
        tex,
        figures=[],
        charts=[{"id": "cht_01", "caption": "План-график финансирования по кварталам"}],
    )
    assert "Проект разделён на три этапа" in out
    assert "Общий бюджет этапа составляет 120 млн руб." in out
    assert r"\section{Заключение и ключевые выводы}" in out
    assert "Итоговый срок окупаемости составляет 2,4 года" in out
    assert "%CASE3_CHART:cht_01%" in out

