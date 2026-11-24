"""Tests for document title editing in LaTeX and API."""

from __future__ import annotations

import json
from pathlib import Path
from fastapi.testclient import TestClient

from case3.heading_edit import HeadingEditError, patch_title_in_tex


def test_patch_title_in_tex_replaces_existing_title() -> None:
    tex = r"""\documentclass{article}
\title{Старое Название Документа}
\author{}
\date{\today}
\begin{document}
\maketitle
\section{Раздел 1}
Текст.
\end{document}
"""
    new_title = "Новое Крутое Название: Анализ 2026"
    res = patch_title_in_tex(tex, new_title)
    assert r"\title{Новое Крутое Название: Анализ 2026}" in res
    assert "Старое Название Документа" not in res
    assert r"\maketitle" in res


def test_patch_title_in_tex_escapes_special_chars() -> None:
    tex = r"""\documentclass{article}
\title{Обычный Заголовок}
\begin{document}
\maketitle
\end{document}
"""
    new_title = "Отчёт 100% & Прибыль #1 _тест_"
    res = patch_title_in_tex(tex, new_title)
    assert r"\title{Отчёт 100\% \& Прибыль \#1 \_тест\_}" in res


def test_patch_title_in_tex_validates_length_and_empty() -> None:
    tex = r"""\documentclass{article}
\title{Заголовок}
\begin{document}
\end{document}
"""
    import pytest

    with pytest.raises(HeadingEditError, match="пуст"):
        patch_title_in_tex(tex, "")

    with pytest.raises(HeadingEditError, match="пуст"):
        patch_title_in_tex(tex, "   ")

    with pytest.raises(HeadingEditError, match="слишком длинный"):
        patch_title_in_tex(tex, "A" * 401)


def test_api_title_edit_updates_preview_and_undo(
    api_client: TestClient, tmp_path: Path, monkeypatch
) -> None:
    from case3 import run_store

    monkeypatch.setattr(run_store, "ROOT", tmp_path)
    run_id = "test_run_title_01"
    out = tmp_path / "runs" / "out" / run_id
    out.mkdir(parents=True)

    tex = r"""\documentclass{article}
\title{Первоначальный Заголовок}
\author{}
\date{\today}
\begin{document}
\maketitle
\section{Введение}
Текст введения.
\end{document}
"""
    (out / "report.tex").write_text(tex, encoding="utf-8")
    meta = {
        "run_id": run_id,
        "status": "ok",
        "formats": ["pdf"],
        "media_status": {},
    }
    (out / "meta.json").write_text(json.dumps(meta), encoding="utf-8")
    (out / "figures.json").write_text(json.dumps({}), encoding="utf-8")

    resp = api_client.post(
        f"/api/runs/{run_id}/title/edit",
        json={"text": "Новый Обновленный Заголовок", "formats": "none"},
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()

    assert data["status"] == "ok"
    assert data["preview"]["title"] == "Новый Обновленный Заголовок"
    assert data["undo"] is not None
    assert data["undo"]["can_undo"] is True

    # Verify updated TeX on disk
    updated_tex = (out / "report.tex").read_text(encoding="utf-8")
    assert r"\title{Новый Обновленный Заголовок}" in updated_tex
