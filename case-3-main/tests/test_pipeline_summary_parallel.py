"""Pipeline runs chat summary in parallel with render; failures don't sink PDF."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

from case3.pipeline import run_pipeline
from case3.summary_bus import BUS

_FAKE_TEX = r"""
\documentclass[a4paper,12pt]{article}
\usepackage{fontspec}
\begin{document}
\title{Параллельный отчёт}
\maketitle
\section{Итоги}
Выручка 42.
\end{document}
"""


def _setup(tmp_path: Path) -> tuple[Path, Path]:
    root = tmp_path / "proj"
    (root / "prompt" / "gold").mkdir(parents=True)
    src = root / "source.txt"
    src.write_text("Выручка 42\n", encoding="utf-8")
    return root, src


def _fake_generate(source, *, out_tex, intent=None, **kwargs):
    out_tex.parent.mkdir(parents=True, exist_ok=True)
    out_tex.write_text(_FAKE_TEX, encoding="utf-8")
    (out_tex.parent / "figures.json").write_text(
        json.dumps({"figures": [], "charts": [], "diagrams": []}), encoding="utf-8"
    )
    (out_tex.parent / "source.raw_model.txt").write_text("{}", encoding="utf-8")
    return out_tex, [], [], []


def _fake_render(tex_path, **kwargs):
    out_dir = kwargs.get("out_dir") or tex_path.parent
    pdf = Path(out_dir) / "source.pdf"
    pdf.write_bytes(b"%PDF-1.4 fake")
    return {"pdf": pdf}


def test_pipeline_writes_chat_summary_and_publishes_bus(tmp_path: Path, monkeypatch) -> None:
    root, src = _setup(tmp_path)
    monkeypatch.setenv("IMAGE_API_BASE_URL", "")
    monkeypatch.setenv("CASE3_MAX_CHARTS", "0")
    monkeypatch.setenv("IMAGE_MAX_IMAGES", "0")

    def fake_summary(tex, *, intent=None, media=None, client=None, on_delta=None):
        if on_delta:
            on_delta("Собрал ")
            on_delta("отчёт про выручку.")
        return "Собрал отчёт про выручку.\n\nПодробности — в полном документе.", "ok"

    with (
        patch("case3.pipeline.generate_document", side_effect=_fake_generate),
        patch("case3.pipeline.render_tex", side_effect=_fake_render),
        patch("case3.pipeline.try_generate_chat_summary", side_effect=fake_summary),
    ):
        out = run_pipeline(
            src,
            project_root=root,
            formats={"pdf"},
            intent="краткий отчёт",
            max_images=0,
            max_charts=0,
            run_id="sum_parallel_1",
        )

    meta = json.loads((out / "meta.json").read_text(encoding="utf-8"))
    assert meta["status"] == "ok"
    assert meta["summary_status"] == "ok"
    assert "выручк" in meta["chat_summary"].lower()
    snap = BUS.snapshot("sum_parallel_1")
    assert snap["done"] is True
    assert snap["status"] == "ok"


def test_stage_bumps_to_summary_after_render(tmp_path: Path, monkeypatch) -> None:
    """After PDF is written, meta.stage becomes summary (not stuck on docx)."""
    import time

    root, src = _setup(tmp_path)
    monkeypatch.setenv("IMAGE_API_BASE_URL", "")
    monkeypatch.setenv("CASE3_MAX_CHARTS", "0")
    monkeypatch.setenv("IMAGE_MAX_IMAGES", "0")
    stages: list[str] = []

    def fake_summary(tex, *, intent=None, media=None, client=None, on_delta=None):
        # Stay busy until render finishes and pipeline bumps to summary.
        time.sleep(0.25)
        meta_path = root / "runs" / "out" / "sum_stage_1" / "meta.json"
        if meta_path.is_file():
            stages.append(json.loads(meta_path.read_text(encoding="utf-8")).get("stage"))
        return "ok text", "ok"

    def fake_render(tex_path, **kwargs):
        on_format = kwargs.get("on_format")
        if on_format:
            on_format("pdf")
        time.sleep(0.05)
        return _fake_render(tex_path, **kwargs)

    with (
        patch("case3.pipeline.generate_document", side_effect=_fake_generate),
        patch("case3.pipeline.render_tex", side_effect=fake_render),
        patch("case3.pipeline.try_generate_chat_summary", side_effect=fake_summary),
    ):
        out = run_pipeline(
            src,
            project_root=root,
            formats={"pdf"},
            max_images=0,
            max_charts=0,
            run_id="sum_stage_1",
        )

    meta = json.loads((out / "meta.json").read_text(encoding="utf-8"))
    assert meta["status"] == "ok"
    assert "summary" in stages, stages


def test_summary_error_still_ok_pdf(tmp_path: Path, monkeypatch) -> None:
    root, src = _setup(tmp_path)
    monkeypatch.setenv("IMAGE_API_BASE_URL", "")
    monkeypatch.setenv("CASE3_MAX_CHARTS", "0")
    monkeypatch.setenv("IMAGE_MAX_IMAGES", "0")

    def boom(*_a, **_k):
        return "", "error"

    with (
        patch("case3.pipeline.generate_document", side_effect=_fake_generate),
        patch("case3.pipeline.render_tex", side_effect=_fake_render),
        patch("case3.pipeline.try_generate_chat_summary", side_effect=boom),
    ):
        out = run_pipeline(
            src,
            project_root=root,
            formats={"pdf"},
            max_images=0,
            max_charts=0,
            run_id="sum_fail_1",
        )

    meta = json.loads((out / "meta.json").read_text(encoding="utf-8"))
    assert meta["status"] == "ok"
    assert meta["summary_status"] == "error"
    assert (out / "source.pdf").is_file()


def test_dry_run_skips_summary(tmp_path: Path, monkeypatch) -> None:
    root, src = _setup(tmp_path)
    monkeypatch.setenv("IMAGE_API_BASE_URL", "")
    monkeypatch.setenv("CASE3_MAX_CHARTS", "0")
    monkeypatch.setenv("IMAGE_MAX_IMAGES", "0")

    with (
        patch("case3.pipeline.generate_document", side_effect=_fake_generate),
        patch("case3.pipeline.render_tex", side_effect=_fake_render),
        patch("case3.pipeline.try_generate_chat_summary") as summ,
    ):
        out = run_pipeline(
            src,
            project_root=root,
            formats={"pdf"},
            dry_run=True,
            max_images=0,
            max_charts=0,
            run_id="sum_dry_1",
        )

    summ.assert_not_called()
    meta = json.loads((out / "meta.json").read_text(encoding="utf-8"))
    assert meta["summary_status"] == "skipped"


def test_parallel_render_and_summary_logs_reach_pipeline_log(
    tmp_path: Path, monkeypatch
) -> None:
    import logging

    root, src = _setup(tmp_path)
    monkeypatch.setenv("IMAGE_API_BASE_URL", "")
    monkeypatch.setenv("CASE3_MAX_CHARTS", "0")
    monkeypatch.setenv("IMAGE_MAX_IMAGES", "0")

    def fake_render_logging(tex_path, **kwargs):
        logging.getLogger("case3.render").info("render-worker-marker-123")
        return _fake_render(tex_path, **kwargs)

    def fake_summary_logging(tex, *, intent=None, media=None, client=None, on_delta=None):
        logging.getLogger("case3.chat_summary").info("summary-worker-marker-456")
        return "ok summary", "ok"

    with (
        patch("case3.pipeline.generate_document", side_effect=_fake_generate),
        patch("case3.pipeline.render_tex", side_effect=fake_render_logging),
        patch("case3.pipeline.try_generate_chat_summary", side_effect=fake_summary_logging),
    ):
        run_pipeline(
            src,
            project_root=root,
            formats={"pdf"},
            max_images=0,
            max_charts=0,
            run_id="sum_log_ctx_1",
        )

    log_text = (root / "runs" / "logs" / "sum_log_ctx_1" / "pipeline.log").read_text(
        encoding="utf-8"
    )
    assert "render-worker-marker-123" in log_text
    assert "summary-worker-marker-456" in log_text


def test_pipeline_preserves_docx_native_charts_written_by_render(
    tmp_path: Path, monkeypatch
) -> None:
    root, src = _setup(tmp_path)
    monkeypatch.setenv("IMAGE_API_BASE_URL", "")
    monkeypatch.setenv("CASE3_MAX_CHARTS", "0")
    monkeypatch.setenv("IMAGE_MAX_IMAGES", "0")

    def fake_render_with_native_charts(tex_path, **kwargs):
        out_dir = Path(kwargs.get("out_dir") or tex_path.parent)
        meta_p = out_dir / "meta.json"
        if meta_p.is_file():
            m = json.loads(meta_p.read_text(encoding="utf-8"))
            m["docx_native_charts"] = ["cht_01"]
            meta_p.write_text(json.dumps(m), encoding="utf-8")
        return _fake_render(tex_path, **kwargs)

    with (
        patch("case3.pipeline.generate_document", side_effect=_fake_generate),
        patch("case3.pipeline.render_tex", side_effect=fake_render_with_native_charts),
        patch("case3.pipeline.try_generate_chat_summary", return_value=("ok", "ok")),
    ):
        out = run_pipeline(
            src,
            project_root=root,
            formats={"pdf", "docx"},
            max_images=0,
            max_charts=0,
            run_id="sum_native_charts_1",
        )

    meta = json.loads((out / "meta.json").read_text(encoding="utf-8"))
    assert meta.get("docx_native_charts") == ["cht_01"]


def test_a_failed_pdf_does_not_publish_a_ready_summary(tmp_path: Path, monkeypatch) -> None:
    from case3.render import RenderError

    root, src = _setup(tmp_path)
    monkeypatch.setenv("IMAGE_API_BASE_URL", "")
    monkeypatch.setenv("CASE3_MAX_CHARTS", "0")
    monkeypatch.setenv("IMAGE_MAX_IMAGES", "0")

    def fake_summary(tex, *, intent=None, media=None, client=None, on_delta=None):
        return "Готов: отчёт.\n\nПодробности — в полном документе.", "ok"

    def boom_render(*_a, **_k):
        raise RenderError("! Undefined control sequence.\nl.42 \\bad")

    with (
        patch("case3.pipeline.generate_document", side_effect=_fake_generate),
        patch("case3.pipeline.render_tex", side_effect=boom_render),
        patch("case3.pipeline.try_generate_chat_summary", side_effect=fake_summary),
    ):
        try:
            run_pipeline(
                src,
                project_root=root,
                formats={"pdf"},
                max_images=0,
                max_charts=0,
                run_id="sum_hold_1",
            )
        except Exception:
            pass
        else:
            raise AssertionError("render failure must surface")

    snap = BUS.snapshot("sum_hold_1")
    assert snap["done"] is True
    assert "Готов" not in (snap.get("text") or "")
    assert "! Undefined control sequence." in (snap.get("text") or "")


def test_pipeline_presentation_writes_meta_ok_before_pipeline_ok_event(
    tmp_path: Path, monkeypatch
) -> None:
    from case3.run_events import EVENTS

    root, src = _setup(tmp_path)
    monkeypatch.setenv("IMAGE_API_BASE_URL", "")
    monkeypatch.setenv("CASE3_MAX_CHARTS", "0")
    monkeypatch.setenv("IMAGE_MAX_IMAGES", "0")
    observed_status_on_pipeline_ok: list[str] = []
    orig_pub = EVENTS.publish_stage

    def spy_publish_stage(run_id: str, stage: str, **kwargs):
        if stage == "pipeline_ok":
            meta_p = root / "runs" / "out" / run_id / "meta.json"
            m = json.loads(meta_p.read_text(encoding="utf-8"))
            observed_status_on_pipeline_ok.append(str(m.get("status")))
        return orig_pub(run_id, stage, **kwargs)

    monkeypatch.setattr(EVENTS, "publish_stage", spy_publish_stage)
    with patch("case3.pipeline.generate_document", side_effect=_fake_generate):
        run_pipeline(
            src,
            project_root=root,
            formats=set(),
            output_mode="presentation",
            max_images=0,
            max_charts=0,
            run_id="pres_meta_order_1",
        )

    assert observed_status_on_pipeline_ok == ["ok"]


