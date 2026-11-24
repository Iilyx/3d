"""Tests for block deletion (paragraph, heading, list) and Markdown formatting in paragraphs."""

from __future__ import annotations

import pytest

from case3.heading_edit import patch_heading_in_tex
from case3.list_edit import patch_list_in_tex
from case3.paragraph_edit import format_prose_to_tex, patch_paragraph_in_tex


def test_format_prose_to_tex_markdown_bold_and_italic() -> None:
    # Standard text
    assert format_prose_to_tex("Простой текст 100%") == r"Простой текст 100\%"
    # Bold
    assert format_prose_to_tex("Это **важный** результат") == r"Это \textbf{важный} результат"
    # Italic
    assert format_prose_to_tex("Слово *акцент* здесь") == r"Слово \emph{акцент} здесь"
    # Both with special characters inside and outside
    raw = "Выручка **+15% & прибыль** выросла на *10%* в 2025_году."
    expected = r"Выручка \textbf{+15\% \& прибыль} выросла на \emph{10\%} в 2025\_году."
    assert format_prose_to_tex(raw) == expected


def test_patch_paragraph_in_tex_deletes_when_empty() -> None:
    tex = r"""\documentclass{article}
\begin{document}
\section{Введение}
Первый абзац.

Второй абзац, который надо удалить.

Третий абзац остаётся.
\end{document}
"""
    # Delete paragraph 2
    patched = patch_paragraph_in_tex(tex, 2, "", allow_delete=True)
    assert "Второй абзац" not in patched
    assert "Первый абзац." in patched
    assert "Третий абзац остаётся." in patched
    assert r"\section{Введение}" in patched


def test_patch_heading_in_tex_deletes_when_empty() -> None:
    tex = r"""\documentclass{article}
\begin{document}
\section{Раздел 1}
Текст 1.

\subsection{Подраздел для удаления}
Текст подраздела.

\section{Раздел 2}
Текст 2.
\end{document}
"""
    # Delete heading 2 (the subsection)
    patched = patch_heading_in_tex(tex, 2, "", allow_delete=True)
    assert r"\subsection{Подраздел для удаления}" not in patched
    assert r"\section{Раздел 1}" in patched
    assert r"\section{Раздел 2}" in patched
    assert "Текст подраздела." in patched


def test_patch_list_in_tex_deletes_when_empty() -> None:
    tex = r"""\documentclass{article}
\begin{document}
\section{Планы}
Перед списком.

\begin{itemize}
  \item Пункт 1
  \item Пункт 2
\end{itemize}

После списка.
\end{document}
"""
    # Delete list 1
    patched = patch_list_in_tex(tex, 1, [], allow_delete=True)
    assert r"\begin{itemize}" not in patched
    assert r"\end{itemize}" not in patched
    assert "Пункт 1" not in patched
    assert "Перед списком." in patched
    assert "После списка." in patched


def test_insert_paragraph_in_tex_after_paragraph() -> None:
    from case3.paragraph_edit import insert_paragraph_in_tex

    tex = r"""\documentclass{article}
\begin{document}
\section{Раздел}
Первый абзац.

Второй абзац.
\end{document}
"""
    patched = insert_paragraph_in_tex(
        tex, text="Новый **вставленный** абзац.", after_paragraph_index=1
    )
    assert r"Первый абзац." in patched
    assert r"Новый \textbf{вставленный} абзац." in patched
    assert r"Второй абзац." in patched
    # Check ordering
    p1 = patched.index("Первый абзац.")
    p2 = patched.index(r"Новый \textbf{вставленный} абзац.")
    p3 = patched.index("Второй абзац.")
    assert p1 < p2 < p3


def test_insert_paragraph_in_tex_after_heading() -> None:
    from case3.paragraph_edit import insert_paragraph_in_tex

    tex = r"""\documentclass{article}
\begin{document}
\section{Раздел 1}
Абзац 1.
\end{document}
"""
    patched = insert_paragraph_in_tex(
        tex, text="Абзац сразу под заголовком.", after_heading_index=1
    )
    p_h = patched.index(r"\section{Раздел 1}")
    p_new = patched.index("Абзац сразу под заголовком.")
    p_1 = patched.index("Абзац 1.")
    assert p_h < p_new < p_1


def test_insert_paragraph_api_route(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, api_client
) -> None:
    from pathlib import Path

    out = tmp_path / "runs" / "out" / "insert_test_run"
    out.mkdir(parents=True)
    tex = r"""\documentclass{article}
\title{Тест}
\begin{document}
\section{Раздел}
Первый абзац.
\end{document}
"""
    (out / "main.tex").write_text(tex, encoding="utf-8")
    (out / "meta.json").write_text("{}", encoding="utf-8")

    monkeypatch.setenv("CASE3_RUNS_DIR", str(tmp_path / "runs" / "out"))
    monkeypatch.setattr(
        "case3.paragraph_edit.rebuild_run_docs",
        lambda out_dir, formats=None: {"preview": out_dir / "preview.json"},
    )

    resp = api_client.post(
        "/api/runs/insert_test_run/paragraphs/insert",
        json={
            "text": "Второй добавленный абзац.",
            "after_paragraph_index": 1,
            "formats": "none",
        },
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["status"] == "ok"
    assert data["after_paragraph_index"] == 1
    new_tex = (out / "main.tex").read_text(encoding="utf-8")
    assert "Второй добавленный абзац." in new_tex


