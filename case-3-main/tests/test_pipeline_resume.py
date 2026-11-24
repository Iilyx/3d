"""Resume failed pipeline stage (same run_id, skip LLM, regen missing media only)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest

from case3.pipeline import (
    RESUME_STAGES,
    can_resume_run,
    prepare_run_dirs,
    resume_pipeline,
)


def _seed_failed_run(
    root: Path,
    *,
    failed_stage: str = "latex",
    media: dict[str, Any] | None = None,
) -> str:
    src = root / "src" / "brief.txt"
    src.parent.mkdir(parents=True)
    src.write_text("маржа 12%\n", encoding="utf-8")
    (root / "runs").mkdir(parents=True, exist_ok=True)
    run_id, _text, work, out, logs = prepare_run_dirs(src, project_root=root)
    tex = work / "brief.tex"
    tex.write_text(
        r"\documentclass{article}\begin{document}Hi\end{document}",
        encoding="utf-8",
    )
    (out / "brief.tex").write_text(tex.read_text(encoding="utf-8"), encoding="utf-8")
    fj = {
        "figures": [{"id": "fig_01", "prompt": "x", "source": "api"}],
        "charts": [
            {"id": "cht_01", "type": "bar", "html": "<html></html>"},
            {"id": "cht_02", "type": "line", "html": "<html></html>"},
        ],
        "diagrams": [],
    }
    (work / "figures.json").write_text(json.dumps(fj), encoding="utf-8")
    (out / "figures.json").write_text(json.dumps(fj), encoding="utf-8")
    media = media or {
        "cht_01": {"ok": True, "kind": "chart"},
        "cht_02": {"ok": False, "error": "boom", "kind": "chart"},
        "fig_01": {"ok": False, "error": "api", "kind": "figure"},
    }
    (work / "status.json").write_text(json.dumps(media), encoding="utf-8")
    figs = work / "figures"
    figs.mkdir(parents=True, exist_ok=True)
    (figs / "cht_01.png").write_bytes(b"\x89PNG\r\n\x1a\n" + b"ok")
    meta = {
        "run_id": run_id,
        "source": str(src.resolve()),
        "status": "error",
        "stage": "error",
        "failed_stage": failed_stage,
        "formats": ["pdf"],
        "intent": "test",
        "max_images": 2,
        "max_charts": 4,
        "max_diagrams": 0,
        "output_mode": "report",
        "media_status": media,
        "charts_planned": ["cht_01", "cht_02"],
        "figures_planned": ["fig_01"],
        "dry_run": False,
    }
    (out / "meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    (logs / "meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    return run_id


def test_resume_stages_constant() -> None:
    assert RESUME_STAGES == frozenset(
        {"llm", "images", "charts", "inject", "latex", "docx"}
    )


def test_can_resume_true(tmp_path: Path) -> None:
    run_id = _seed_failed_run(tmp_path, failed_stage="latex")
    out = tmp_path / "runs" / "out" / run_id
    work = tmp_path / "runs" / "work" / run_id
    meta = json.loads((out / "meta.json").read_text(encoding="utf-8"))
    assert can_resume_run(meta, work=work, out=out) is True


def test_can_resume_llm_when_raw_model_saved(tmp_path: Path) -> None:
    run_id = _seed_failed_run(tmp_path, failed_stage="llm")
    out = tmp_path / "runs" / "out" / run_id
    work = tmp_path / "runs" / "work" / run_id
    for p in list(work.glob("*.tex")) + list(out.glob("*.tex")):
        p.unlink()
    (work / "figures.json").unlink()
    (out / "figures.json").unlink()
    (work / "brief.raw_model.txt").write_text(
        "```latex\n\\documentclass{article}\n\\begin{document}x\\end{document}\n```\n",
        encoding="utf-8",
    )
    meta = json.loads((out / "meta.json").read_text(encoding="utf-8"))
    assert can_resume_run(meta, work=work, out=out) is True


def test_can_resume_false_llm_without_raw(tmp_path: Path) -> None:
    run_id = _seed_failed_run(tmp_path, failed_stage="llm")
    out = tmp_path / "runs" / "out" / run_id
    work = tmp_path / "runs" / "work" / run_id
    for p in work.glob("*.raw_model.txt"):
        p.unlink()
    meta = json.loads((out / "meta.json").read_text(encoding="utf-8"))
    assert can_resume_run(meta, work=work, out=out) is False


def test_can_resume_false_wrong_stage(tmp_path: Path) -> None:
    run_id = _seed_failed_run(tmp_path, failed_stage="summary")
    out = tmp_path / "runs" / "out" / run_id
    work = tmp_path / "runs" / "work" / run_id
    meta = json.loads((out / "meta.json").read_text(encoding="utf-8"))
    assert can_resume_run(meta, work=work, out=out) is False


def test_can_resume_false_no_tex(tmp_path: Path) -> None:
    run_id = _seed_failed_run(tmp_path, failed_stage="charts")
    out = tmp_path / "runs" / "out" / run_id
    work = tmp_path / "runs" / "work" / run_id
    for p in list(work.glob("*.tex")) + list(out.glob("*.tex")):
        p.unlink()
    meta = json.loads((out / "meta.json").read_text(encoding="utf-8"))
    assert can_resume_run(meta, work=work, out=out) is False


def test_resume_pipeline_skips_ok_charts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    run_id = _seed_failed_run(tmp_path, failed_stage="charts")
    called: dict[str, Any] = {"charts": None, "figures": None}

    def fake_charts(charts, figures_dir, **kwargs):  # noqa: ANN001
        called["charts"] = [c["id"] for c in charts]
        status = {}
        for c in charts:
            cid = c["id"]
            dest = figures_dir / f"{cid}.png"
            dest.write_bytes(b"png")
            status[cid] = {"ok": True, "path": str(dest), "kind": "chart"}
        return status

    def fake_figures(figures, figures_dir, **kwargs):  # noqa: ANN001
        called["figures"] = [f["id"] for f in figures]
        status = {}
        for f in figures:
            fid = f["id"]
            dest = figures_dir / f"{fid}.png"
            dest.write_bytes(b"png")
            status[fid] = {"ok": True, "path": str(dest), "kind": "figure"}
        return status

    def fake_render(tex_path, **kwargs):  # noqa: ANN001
        out_dir = kwargs["out_dir"]
        pdf = out_dir / f"{tex_path.stem}.pdf"
        pdf.write_bytes(b"%PDF")
        return {"pdf": pdf}

    monkeypatch.setattr("case3.pipeline.generate_all_charts", fake_charts)
    monkeypatch.setattr("case3.pipeline.generate_all_figures", fake_figures)
    monkeypatch.setattr("case3.pipeline.render_tex", fake_render)
    monkeypatch.setattr(
        "case3.pipeline.materialize_user_figures",
        lambda *a, **k: {},
    )
    monkeypatch.setattr(
        "case3.pipeline.write_injected",
        lambda *a, **k: None,
    )
    monkeypatch.setattr(
        "case3.pipeline.try_generate_chat_summary",
        lambda *a, **k: ("ok", "ok"),
    )
    # Image API path: avoid empty-base skip by stubbing config
    from dataclasses import dataclass

    @dataclass
    class _Cfg:
        base_url: str = "http://test"
        max_images: int = 8

        @classmethod
        def from_env(cls):
            return cls()

    monkeypatch.setattr("case3.pipeline.ImageApiConfig", _Cfg)

    out = resume_pipeline(run_id, project_root=tmp_path)
    assert (out / "meta.json").is_file()
    meta = json.loads((out / "meta.json").read_text(encoding="utf-8"))
    assert meta["status"] == "ok"
    assert meta.get("resumed_from_stage") == "charts"
    assert called["charts"] == ["cht_02"]
    assert called["figures"] == ["fig_01"]
    # ok PNG kept
    assert (tmp_path / "runs" / "work" / run_id / "figures" / "cht_01.png").is_file()


def test_resume_reinjects_slots_erased_by_prior_write_injected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """When write_injected already ran before latex failed, resume must still inject recovered media."""
    from case3.inject import write_injected

    run_id = _seed_failed_run(tmp_path, failed_stage="latex")
    work = tmp_path / "runs" / "work" / run_id
    out = tmp_path / "runs" / "out" / run_id
    tex = work / "brief.tex"
    raw_tex = (
        "\\documentclass{article}\n\\begin{document}\n"
        "Раздел 1.\n\n%CASE3_CHART:cht_01%\n\n%CASE3_CHART:cht_02%\n"
        "\\end{document}\n"
    )
    tex.write_text(raw_tex, encoding="utf-8")
    fj = json.loads((work / "figures.json").read_text(encoding="utf-8"))
    media = json.loads((work / "status.json").read_text(encoding="utf-8"))

    # Simulate initial run's write_injected which strips failed cht_02 slot in-place
    write_injected(
        tex,
        fj["figures"],
        media,
        charts=fj["charts"],
        diagrams=fj["diagrams"],
    )
    assert "%CASE3_CHART:cht_02%" not in tex.read_text(encoding="utf-8")

    def fake_charts(charts, figures_dir, **kwargs):  # noqa: ANN001
        status = {}
        for c in charts:
            cid = c["id"]
            dest = figures_dir / f"{cid}.png"
            dest.write_bytes(b"\x89PNG\r\n\x1a\nok")
            status[cid] = {"ok": True, "path": str(dest), "kind": "chart"}
        return status

    def fake_render(tex_path, **kwargs):  # noqa: ANN001
        out_dir = kwargs["out_dir"]
        pdf = out_dir / f"{tex_path.stem}.pdf"
        pdf.write_bytes(b"%PDF")
        return {"pdf": pdf}

    monkeypatch.setattr("case3.pipeline.generate_all_charts", fake_charts)
    monkeypatch.setattr("case3.pipeline.generate_all_figures", lambda *a, **k: {})
    monkeypatch.setattr("case3.pipeline.render_tex", fake_render)
    monkeypatch.setattr("case3.pipeline.materialize_user_figures", lambda *a, **k: {})
    monkeypatch.setattr(
        "case3.pipeline.try_generate_chat_summary",
        lambda *a, **k: ("ok", "ok"),
    )

    resume_pipeline(run_id, project_root=tmp_path)
    final_tex = (out / "brief.tex").read_text(encoding="utf-8")
    assert "figures/cht_02.png" in final_tex


def test_resume_llm_replays_saved_raw_without_calling_model(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    run_id = _seed_failed_run(tmp_path, failed_stage="llm")
    work = tmp_path / "runs" / "work" / run_id
    out = tmp_path / "runs" / "out" / run_id
    for p in list(work.glob("*.tex")) + list(out.glob("*.tex")):
        p.unlink()
    (work / "figures.json").unlink()
    (out / "figures.json").unlink()
    raw = (
        "```json\n"
        '{"charts":[],"diagrams":[],"figures":[]}\n'
        "```\n"
        "```latex\n"
        "\\documentclass{article}\n"
        "\\begin{document}\nМаржа 12\\%.\n\\end{document}\n"
        "```\n"
    )
    (work / "brief.raw_model.txt").write_text(raw, encoding="utf-8")

    def _boom(*_a, **_k):  # noqa: ANN001
        raise AssertionError("LLM must not be called on llm resume")

    monkeypatch.setattr("case3.llm_client.LLMClient.complete", _boom)

    def fake_render(tex_path, **kwargs):  # noqa: ANN001
        out_dir = kwargs["out_dir"]
        pdf = out_dir / f"{tex_path.stem}.pdf"
        pdf.write_bytes(b"%PDF")
        return {"pdf": pdf}

    monkeypatch.setattr("case3.pipeline.render_tex", fake_render)
    monkeypatch.setattr("case3.pipeline.generate_all_charts", lambda *a, **k: {})
    monkeypatch.setattr("case3.pipeline.generate_all_figures", lambda *a, **k: {})
    monkeypatch.setattr("case3.pipeline.materialize_user_figures", lambda *a, **k: {})
    monkeypatch.setattr(
        "case3.pipeline.try_generate_chat_summary",
        lambda *a, **k: ("ok", "ok"),
    )

    resume_pipeline(run_id, project_root=tmp_path)
    meta = json.loads((out / "meta.json").read_text(encoding="utf-8"))
    assert meta["status"] == "ok"
    assert meta.get("resumed_from_stage") == "llm"
    # Thin replay is filled from Source; the model is not called.
    assert "12" in (out / "brief.tex").read_text(encoding="utf-8")

