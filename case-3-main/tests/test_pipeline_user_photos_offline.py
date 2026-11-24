"""Offline pipeline: mocked LLM + user uploads + mocked render (no Docker/network)."""

from __future__ import annotations

import base64
import json
from pathlib import Path
from unittest.mock import MagicMock, patch

from case3.pipeline import run_pipeline
from case3.user_photos import save_user_photos

_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
)

_FAKE_TEX = r"""
\documentclass[a4paper,12pt]{article}
\usepackage{fontspec}
\usepackage{graphicx}
\usepackage{float}
\usepackage{caption}
\begin{document}
\title{Test}
\maketitle
\section{Обзор}
Числа из Source.
%CASE3_CHART:cht_01%
\end{document}
"""

_FAKE_JSON = {
    "figures": [],
    "charts": [
        {
            "id": "cht_01",
            "type": "bar",
            "caption": "Бюджет по категориям",
            "html": (
                "<canvas id=\"c\" width=\"1100\" height=\"560\"></canvas>"
                "<script>window.__CASE3_CHART_READY=true;</script>"
            ),
            "width": "0.85\\textwidth",
        }
    ],
}


def test_pipeline_merges_user_photo_and_skips_image_api(tmp_path: Path, monkeypatch) -> None:
    root = tmp_path / "proj"
    (root / "prompt" / "gold").mkdir(parents=True)
    (root / "assets" / "docx").mkdir(parents=True)
    src = root / "source.txt"
    src.write_text("A 10, B 20, C 30\n", encoding="utf-8")
    upload = root / "uploads"
    users = save_user_photos(upload, [("mine.png", _PNG)], captions=["Моё фото"])

    def fake_generate(source, *, out_tex, intent=None, **kwargs):
        out_tex.parent.mkdir(parents=True, exist_ok=True)
        out_tex.write_text(_FAKE_TEX, encoding="utf-8")
        (out_tex.parent / "figures.json").write_text(
            json.dumps(_FAKE_JSON, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        (out_tex.parent / "source.raw_model.txt").write_text("{}", encoding="utf-8")
        return (
            out_tex,
            list(_FAKE_JSON["figures"]),
            list(_FAKE_JSON["charts"]),
            list(_FAKE_JSON.get("diagrams") or []),
        )

    def fake_charts(charts, figs_dir, **kwargs):
        figs_dir.mkdir(parents=True, exist_ok=True)
        st = {}
        for c in charts:
            p = figs_dir / f"{c['id']}.png"
            p.write_bytes(_PNG)
            st[c["id"]] = {"ok": True, "path": str(p), "kind": "chart"}
        return st

    def fake_render(tex_path, **kwargs):
        out_dir = kwargs.get("out_dir") or tex_path.parent
        pdf = Path(out_dir) / "source.pdf"
        docx = Path(out_dir) / "source.docx"
        pdf.write_bytes(b"%PDF-1.4 fake")
        docx.write_bytes(b"PK fake")
        return {"pdf": pdf, "docx": docx}

    monkeypatch.setenv("IMAGE_API_BASE_URL", "")
    monkeypatch.setenv("IMAGE_MAX_IMAGES", "2")
    monkeypatch.setenv("CASE3_MAX_CHARTS", "2")

    with (
        patch("case3.pipeline.generate_document", side_effect=fake_generate),
        patch("case3.pipeline.generate_all_charts", side_effect=fake_charts),
        patch("case3.pipeline.generate_all_figures") as gen_figs,
        patch("case3.pipeline.render_tex", side_effect=fake_render),
    ):
        out = run_pipeline(
            src,
            project_root=root,
            formats={"pdf", "docx"},
            intent="отчёт с моим фото",
            max_images=2,
            max_charts=1,
            user_figures=users,
        )
        gen_figs.assert_not_called()

    meta = json.loads((out / "meta.json").read_text(encoding="utf-8"))
    assert meta["status"] == "ok"
    assert "usr_01" in meta["figures_planned"]
    assert (out / "figures" / "usr_01.png").is_file()
    tex = (out / "source.tex").read_text(encoding="utf-8")
    assert "usr_01" in tex
    assert r"\includegraphics" in tex
    assert "%CASE3_FIG" not in tex


def test_pipeline_adopts_llm_vision_caption_for_user_photo(tmp_path: Path, monkeypatch) -> None:
    root = tmp_path / "proj"
    (root / "prompt" / "gold").mkdir(parents=True)
    (root / "assets" / "docx").mkdir(parents=True)
    src = root / "source.txt"
    src.write_text("Текст отчёта\n", encoding="utf-8")
    upload = root / "uploads"
    users = save_user_photos(upload, [("screen.png", _PNG)], captions=["Фото 1"])

    passed_kwargs = {}

    def fake_generate(source, *, out_tex, intent=None, **kwargs):
        nonlocal passed_kwargs
        passed_kwargs = dict(kwargs)
        out_tex.parent.mkdir(parents=True, exist_ok=True)
        # LLM placed the slot right in the section
        tex_with_slot = r"""
\documentclass{article}
\begin{document}
\section{Интерфейс}
На скриншоте показана панель Liber.
%CASE3_FIG:usr_01%
\end{document}
"""
        out_tex.write_text(tex_with_slot, encoding="utf-8")
        llm_figs = [
            {
                "id": "usr_01",
                "caption": "Панель управления Liber с активными метриками",
                "width": r"0.85\textwidth",
            }
        ]
        (out_tex.parent / "figures.json").write_text(
            json.dumps({"figures": llm_figs, "charts": []}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return out_tex, llm_figs, [], []

    def fake_render(tex_path, **kwargs):
        out_dir = kwargs.get("out_dir") or tex_path.parent
        pdf = Path(out_dir) / "source.pdf"
        docx = Path(out_dir) / "source.docx"
        pdf.write_bytes(b"%PDF-1.4 fake")
        docx.write_bytes(b"PK fake")
        return {"pdf": pdf, "docx": docx}

    monkeypatch.setenv("IMAGE_API_BASE_URL", "")

    with (
        patch("case3.pipeline.generate_document", side_effect=fake_generate),
        patch("case3.pipeline.generate_all_charts", return_value={}),
        patch("case3.pipeline.generate_all_figures"),
        patch("case3.pipeline.render_tex", side_effect=fake_render),
    ):
        out = run_pipeline(
            src,
            project_root=root,
            formats={"pdf", "docx"},
            intent="проанализируй скриншот",
            max_images=1,
            max_charts=0,
            user_figures=users,
        )

    assert "user_figures" in passed_kwargs
    assert passed_kwargs["user_figures"][0]["id"] == "usr_01"

    fj = json.loads((out / "figures.json").read_text(encoding="utf-8"))
    assert fj["figures"][0]["id"] == "usr_01"
    # LLM descriptive caption adopted!
    assert fj["figures"][0]["caption"] == "Панель управления Liber с активными метриками"
    # Placed in the section where LLM put it
    tex = (out / "source.tex").read_text(encoding="utf-8")
    assert "Панель управления Liber" in tex
    assert r"\caption{Панель управления Liber" in tex
    assert r"\section{Интерфейс}" in tex


def test_pipeline_refuses_insufficient_data_with_user_photo(tmp_path: Path) -> None:
    root = tmp_path / "proj"
    (root / "prompt" / "gold").mkdir(parents=True)
    (root / "assets" / "docx").mkdir(parents=True)
    src = root / "source.txt"
    src.write_text("ывафыавфа\n", encoding="utf-8")
    upload = root / "uploads"
    users = save_user_photos(upload, [("mine.png", _PNG)], captions=["Моё фото"])

    out = run_pipeline(
        src,
        project_root=root,
        formats={"pdf", "docx"},
        intent="ывафыавфа",
        max_images=1,
        max_charts=0,
        user_figures=users,
    )
    meta = json.loads((out / "meta.json").read_text(encoding="utf-8"))
    assert meta.get("insufficient_data") is True
    assert "недостаточно данных" in (meta.get("chat_summary") or "").lower()


