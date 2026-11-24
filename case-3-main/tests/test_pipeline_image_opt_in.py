"""Pipeline clamps generated fig_* budget without opt-in; uploads still merge."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

from case3.pipeline import run_pipeline

_FAKE_TEX = (
    "\\documentclass{article}\\begin{document}x\\end{document}\n"
)


def _stub_generate(source, *, out_tex, intent=None, **kwargs):
    out_tex.parent.mkdir(parents=True, exist_ok=True)
    out_tex.write_text(_FAKE_TEX, encoding="utf-8")
    (out_tex.parent / "figures.json").write_text(
        json.dumps({"figures": [], "charts": [], "diagrams": []}),
        encoding="utf-8",
    )
    (out_tex.parent / "source.raw_model.txt").write_text("{}", encoding="utf-8")
    return out_tex, [], [], []


def _fake_render(tex_path, **kwargs):
    out_dir = Path(kwargs.get("out_dir") or tex_path.parent)
    pdf = out_dir / "source.pdf"
    pdf.write_bytes(b"%PDF-1.4 fake")
    return {"pdf": pdf}


def test_pipeline_meta_images_opt_in_false_on_numbers(tmp_path: Path) -> None:
    root = tmp_path / "proj"
    (root / "prompt" / "gold").mkdir(parents=True)
    src = root / "src.txt"
    src.write_text("Выручка 2023: 10; 2024: 20; 2025: 30\n", encoding="utf-8")
    seen: dict = {}

    def fake_generate(source, *, out_tex, intent=None, **kwargs):
        seen["max_images"] = kwargs.get("max_images", -1)
        return _stub_generate(source, out_tex=out_tex, intent=intent, **kwargs)

    with (
        patch("case3.pipeline.generate_document", side_effect=fake_generate),
        patch("case3.pipeline.generate_all_figures") as gen_figs,
        patch("case3.pipeline.generate_all_charts", return_value={}),
        patch("case3.pipeline.render_tex", side_effect=_fake_render),
        patch("case3.pipeline.try_generate_chat_summary", return_value="ok"),
    ):
        out = run_pipeline(
            src,
            project_root=root,
            formats={"pdf"},
            intent="Сделай отчёт",
            max_images=2,
            max_charts=0,
            max_diagrams=0,
        )
        gen_figs.assert_not_called()

    meta = json.loads((out / "meta.json").read_text(encoding="utf-8"))
    assert meta.get("images_opt_in") is False
    assert meta.get("max_images") == 0
    assert seen.get("max_images") == 0


def test_pipeline_opt_in_keeps_gen_budget(tmp_path: Path) -> None:
    root = tmp_path / "proj"
    (root / "prompt" / "gold").mkdir(parents=True)
    src = root / "src.txt"
    src.write_text("Завод на окраине\n", encoding="utf-8")
    seen: dict = {}

    def fake_generate(source, *, out_tex, intent=None, **kwargs):
        seen["max_images"] = kwargs.get("max_images", -1)
        return _stub_generate(source, out_tex=out_tex, intent=intent, **kwargs)

    with (
        patch("case3.pipeline.generate_document", side_effect=fake_generate),
        patch("case3.pipeline.generate_all_figures", return_value={}),
        patch("case3.pipeline.generate_all_charts", return_value={}),
        patch("case3.pipeline.render_tex", side_effect=_fake_render),
        patch("case3.pipeline.try_generate_chat_summary", return_value="ok"),
    ):
        out = run_pipeline(
            src,
            project_root=root,
            formats={"pdf"},
            intent="добавь фото завода",
            max_images=2,
            max_charts=0,
            max_diagrams=0,
        )

    meta = json.loads((out / "meta.json").read_text(encoding="utf-8"))
    assert meta.get("images_opt_in") is True
    assert seen.get("max_images") == 2
    assert meta.get("max_images") == 2
