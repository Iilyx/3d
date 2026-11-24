"""Tests for diagram materialization in the report pipeline."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from case3.pipeline import _pipeline_materialize_media


@pytest.fixture
def run_dir(tmp_path: Path) -> tuple[Path, Path, Path]:
    work = tmp_path / "work"
    work.mkdir()
    figs = work / "figures"
    figs.mkdir()
    fj_path = work / "figures.json"
    return work, figs, fj_path


def test_materialize_diagrams_renders_png_and_updates_status(
    run_dir: tuple[Path, Path, Path],
) -> None:
    work, figs, fj_path = run_dir
    diagrams = [{"id": "dia_01", "mermaid": "graph TD\nA-->B", "title": "Схема"}]
    fj = {"diagrams": diagrams, "figures": [], "charts": []}
    fj_path.write_text(json.dumps(fj), encoding="utf-8")
    status: dict = {}
    meta: dict = {}
    bump = MagicMock()

    # Create dummy PNG file to simulate renderer output
    dia_png = figs / "dia_01.png"

    def fake_render(specs, dest_dir, **kwargs):
        dia_png.write_bytes(b"\x89PNG\r\n\x1a\nfake")
        return {"dia_01": dia_png}

    with patch("case3.slides_media.ensure_diagram_pngs", side_effect=fake_render):
        _pipeline_materialize_media(
            status=status,
            figures=[],
            charts=[],
            diagrams=diagrams,
            fj=fj,
            fj_path=fj_path,
            figs_dir=figs,
            work=work,
            images_budget=0,
            charts_budget=0,
            dry_run=False,
            intent=None,
            meta=meta,
            bump=bump,
            run_id="test_run",
        )

    assert status.get("dia_01", {}).get("ok") is True
    assert status.get("dia_01", {}).get("kind") == "diagram"


def test_materialize_diagrams_soft_fails_on_render_error(
    run_dir: tuple[Path, Path, Path],
) -> None:
    work, figs, fj_path = run_dir
    diagrams = [{"id": "dia_01", "mermaid": "graph TD\nBAD SYNTAX", "title": "Схема"}]
    fj = {"diagrams": diagrams, "figures": [], "charts": []}
    fj_path.write_text(json.dumps(fj), encoding="utf-8")
    status: dict = {}
    meta: dict = {}
    bump = MagicMock()

    def fake_render(specs, dest_dir, **kwargs):
        return {}  # Render failed, no output file

    with patch("case3.slides_media.ensure_diagram_pngs", side_effect=fake_render):
        _pipeline_materialize_media(
            status=status,
            figures=[],
            charts=[],
            diagrams=diagrams,
            fj=fj,
            fj_path=fj_path,
            figs_dir=figs,
            work=work,
            images_budget=0,
            charts_budget=0,
            dry_run=False,
            intent=None,
            meta=meta,
            bump=bump,
            run_id="test_run",
        )

    assert status.get("dia_01", {}).get("ok") is False


def test_materialize_diagrams_skips_when_only_missing_and_on_disk(
    run_dir: tuple[Path, Path, Path],
) -> None:
    work, figs, fj_path = run_dir
    dia_png = figs / "dia_01.png"
    dia_png.write_bytes(b"\x89PNG\r\n\x1a\nfake")
    diagrams = [{"id": "dia_01", "mermaid": "graph TD\nA-->B", "title": "Схема"}]
    fj = {"diagrams": diagrams, "figures": [], "charts": []}
    fj_path.write_text(json.dumps(fj), encoding="utf-8")
    status = {"dia_01": {"ok": True, "kind": "diagram"}}
    meta: dict = {}
    bump = MagicMock()

    render_mock = MagicMock()
    with patch("case3.slides_media.ensure_diagram_pngs", render_mock):
        _pipeline_materialize_media(
            status=status,
            figures=[],
            charts=[],
            diagrams=diagrams,
            fj=fj,
            fj_path=fj_path,
            figs_dir=figs,
            work=work,
            images_budget=0,
            charts_budget=0,
            dry_run=False,
            intent=None,
            meta=meta,
            bump=bump,
            run_id="test_run",
            only_missing=True,
        )

    render_mock.assert_not_called()
    assert status.get("dia_01", {}).get("ok") is True


def test_pipeline_e2e_renders_and_injects_diagram(tmp_path: Path, monkeypatch) -> None:
    from case3.pipeline import run_pipeline

    root = tmp_path / "repo"
    root.mkdir()
    (root / "prompt" / "gold").mkdir(parents=True)
    src = tmp_path / "source.txt"
    src.write_text("Процесс регистрации пользователей.", encoding="utf-8")

    tex_content = (
        r"\documentclass{article}" "\n"
        r"\begin{document}" "\n"
        r"\section{Процесс}" "\n"
        r"%CASE3_DIAG:dia_01%" "\n"
        r"\section{Заключение}" "\n"
        r"Итоги." "\n"
        r"\end{document}" "\n"
    )

    def _fake_generate(*args, **kwargs):
        out_tex = kwargs.get("out_tex")
        if out_tex:
            Path(out_tex).write_text(tex_content, encoding="utf-8")
        diagrams = [{"id": "dia_01", "mermaid": "flowchart TD\nA-->B", "title": "Регистрация"}]
        return "raw", [], [], diagrams

    def _fake_render_diagram(specs, dest_dir, **kwargs):
        p = Path(dest_dir) / "dia_01.png"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(b"\x89PNG\r\n\x1a\nrendered_dia")
        return {"dia_01": p}

    def _fake_render_tex(tex_path, out_dir, **kwargs):
        pdf = Path(out_dir) / "report.pdf"
        pdf.write_bytes(b"%PDF-1.4")
        return {"pdf": pdf}

    monkeypatch.setenv("IMAGE_API_BASE_URL", "")
    monkeypatch.setenv("CASE3_MAX_CHARTS", "0")
    monkeypatch.setenv("IMAGE_MAX_IMAGES", "0")

    with (
        patch("case3.pipeline.generate_document", side_effect=_fake_generate),
        patch("case3.slides_media.ensure_diagram_pngs", side_effect=_fake_render_diagram),
        patch("case3.pipeline.render_tex", side_effect=_fake_render_tex),
        patch("case3.pipeline.try_generate_chat_summary", return_value=("Готово", "ok")),
    ):
        out = run_pipeline(
            src,
            project_root=root,
            formats={"pdf"},
            intent="схема процесса",
            max_images=0,
            max_charts=0,
            max_diagrams=1,
            run_id="diag_e2e_1",
        )

    # Diagram PNG copied to out/figures
    assert (out / "figures" / "dia_01.png").is_file()

    # Injected TeX contains diagram figure and includegraphics
    injected = (out / f"{src.stem}.tex").read_text(encoding="utf-8")
    assert r"\includegraphics[width=\linewidth,height=0.38\textheight,keepaspectratio]{figures/dia_01.png}" in injected
    assert r"\label{dia:dia_01}" in injected
    assert "%CASE3_DIAG" not in injected

    # Meta records diagram status
    meta = json.loads((out / "meta.json").read_text(encoding="utf-8"))
    assert meta["status"] == "ok"
    assert meta["media_status"]["dia_01"]["ok"] is True


def test_pipeline_e2e_diagram_fallback_before_conclusion(tmp_path: Path, monkeypatch) -> None:
    from case3.pipeline import run_pipeline

    root = tmp_path / "repo"
    root.mkdir()
    (root / "prompt" / "gold").mkdir(parents=True)
    src = tmp_path / "source.txt"
    src.write_text("Процесс регистрации пользователей.", encoding="utf-8")

    # No %CASE3_DIAG slot in TeX
    tex_content = (
        r"\documentclass{article}" "\n"
        r"\begin{document}" "\n"
        r"\section{Процесс}" "\n"
        r"Описание шагов без явного слота." "\n"
        r"\section{Заключение}" "\n"
        r"Итоги." "\n"
        r"\end{document}" "\n"
    )

    def _fake_generate(*args, **kwargs):
        out_tex = kwargs.get("out_tex")
        if out_tex:
            Path(out_tex).write_text(tex_content, encoding="utf-8")
        diagrams = [{"id": "dia_01", "mermaid": "flowchart TD\nA-->B", "title": "Регистрация"}]
        return "raw", [], [], diagrams

    def _fake_render_diagram(specs, dest_dir, **kwargs):
        p = Path(dest_dir) / "dia_01.png"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(b"\x89PNG\r\n\x1a\nrendered_dia")
        return {"dia_01": p}

    def _fake_render_tex(tex_path, out_dir, **kwargs):
        pdf = Path(out_dir) / "report.pdf"
        pdf.write_bytes(b"%PDF-1.4")
        return {"pdf": pdf}

    monkeypatch.setenv("IMAGE_API_BASE_URL", "")
    monkeypatch.setenv("CASE3_MAX_CHARTS", "0")
    monkeypatch.setenv("IMAGE_MAX_IMAGES", "0")

    with (
        patch("case3.pipeline.generate_document", side_effect=_fake_generate),
        patch("case3.slides_media.ensure_diagram_pngs", side_effect=_fake_render_diagram),
        patch("case3.pipeline.render_tex", side_effect=_fake_render_tex),
        patch("case3.pipeline.try_generate_chat_summary", return_value=("Готово", "ok")),
    ):
        out = run_pipeline(
            src,
            project_root=root,
            formats={"pdf"},
            intent="схема процесса",
            max_images=0,
            max_charts=0,
            max_diagrams=1,
            run_id="diag_fallback_1",
        )

    # Injected TeX placed diagram before \section{Заключение}
    injected = (out / f"{src.stem}.tex").read_text(encoding="utf-8")
    assert r"\includegraphics[width=\linewidth,height=0.38\textheight,keepaspectratio]{figures/dia_01.png}" in injected
    diag_pos = injected.find(r"figures/dia_01.png")
    concl_pos = injected.find(r"\section{Заключение}")
    assert diag_pos != -1 and concl_pos != -1
    assert diag_pos < concl_pos


