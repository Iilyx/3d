"""Tests for fast presentation branch, live token streaming, and chart follow-up refinement."""

from __future__ import annotations

import json
import threading
from pathlib import Path
from unittest.mock import patch

from case3.pipeline import run_pipeline
from case3.summary_bus import SummaryBus


def test_presentation_skips_generate_document_even_when_formats_not_cleared(
    tmp_path: Path, monkeypatch
) -> None:
    root = tmp_path / "project"
    root.mkdir()
    (root / "prompt" / "gold").mkdir(parents=True)
    src = tmp_path / "source.md"
    src.write_text(
        "# Данные\n\n| Регион | Факт | План |\n| --- | --- | --- |\n| Минск | 120 | 100 |\n",
        encoding="utf-8",
    )

    def _forbid_tex(*_a, **_kw):
        raise AssertionError("generate_document must not run in presentation mode")

    def _fake_diagrams(**_kw):
        return [{"id": "dia_01", "title": "Процесс", "mermaid": "flowchart TD\nA[Start] --> B[End]"}]

    monkeypatch.setattr("case3.pipeline.generate_document", _forbid_tex)
    monkeypatch.setattr("case3.diagram_generate.complete_diagrams", _fake_diagrams)

    out = run_pipeline(
        src,
        project_root=root,
        intent="Собери презентацию",
        output_mode="presentation",
        formats=None,  # default formats must not force LaTeX build
        max_charts=0,
        max_images=0,
        max_diagrams=1,
        dry_run=False,
    )
    fj = json.loads((out / "figures.json").read_text(encoding="utf-8"))
    assert fj["diagrams"][0]["id"] == "dia_01"


def test_summary_bus_streams_deltas_and_supports_replace() -> None:
    bus = SummaryBus()
    bus.start("run_stream")
    seen: list[dict] = []

    def _consumer() -> None:
        for ev in bus.subscribe("run_stream", timeout_s=2.0):
            seen.append(ev)

    t = threading.Thread(target=_consumer, daemon=True)
    t.start()
    bus.publish("run_stream", "Привет, ")
    bus.publish("run_stream", "выручка 10.")
    bus.replace("run_stream", "Привет, выручка 12.")
    bus.finish("run_stream", "Привет, выручка 12.", "ok")
    t.join(timeout=2.0)

    assert [e["event"] for e in seen] == ["delta", "delta", "replace", "done"]
    assert seen[-1]["text"] == "Привет, выручка 12."


def test_chat_turn_streams_tokens_before_completion(tmp_path: Path, monkeypatch) -> None:
    from case3.chat_turn import try_chat_answer
    from case3.summary_bus import BUS

    class _StreamClient:
        last_finish_reason = "stop"

        def stream(self, **_kw):
            yield "Выручка "
            yield "составила "
            yield "120."

        def complete(self, **_kw):
            raise AssertionError("complete should not run when stream succeeded")

    chunks: list[str] = []
    BUS.start("run_tok")
    ans = try_chat_answer(
        "| Показатель | Значение |\n| --- | --- |\n| Выручка | 120 |\n",
        "Какая выручка?",
        client=_StreamClient(),  # type: ignore[arg-type]
        on_delta=lambda d: (chunks.append(d), BUS.publish("run_tok", d)),
        on_replace=lambda full: BUS.replace("run_tok", full),
    )
    BUS.finish("run_tok", ans, "ok")
    assert ans == "Выручка составила 120."
    assert len(chunks) >= 3
    assert "".join(chunks) == "Выручка составила 120."


def test_chat_follow_up_chart_refinement_receives_previous_chart(
    tmp_path: Path, monkeypatch
) -> None:
    from case3.chat_turn import generate_chat_charts
    from case3.turn_route import wants_chat_chart

    assert wants_chat_chart("сделай горизонтальным", has_prior_chart=True) is True
    assert wants_chat_chart("убери Итого", has_prior_chart=True) is True
    assert wants_chat_chart("сделай горизонтальным", has_prior_chart=False) is False

    seen_prompts: list[str] = []

    class _ChartClient:
        def complete(self, *, system: str, user_text: str, **_kw) -> str:
            seen_prompts.append(user_text)
            return (
                '```json\n{"charts": [{"id": "cht_01", "type": "horizontal_bar", '
                '"caption": "Выручка", "html": "<canvas id=\'c\'></canvas>'
                '<script>new Chart(document.getElementById(\'c\'),{type:\'bar\',data:{labels:[\'Минск\'],datasets:[{data:[120]}]}});</script>"}]}\n```'
            )

    monkeypatch.setattr(
        "case3.charts.render_charts_batch",
        lambda items: {cid: {"ok": True} for cid, *_ in items},
    )
    charts, _st = generate_chat_charts(
        "| Регион | Выручка |\n| --- | --- |\n| Минск | 120 |\n",
        "сделай горизонтальным",
        max_charts=1,
        figs_dir=tmp_path / "figs",
        charts_dir=tmp_path / "charts",
        client=_ChartClient(),  # type: ignore[arg-type]
        previous_chart={
            "id": "cht_01",
            "type": "bar",
            "caption": "Выручка",
            "html": "<canvas id='c'></canvas><script>/* old chart */</script>",
        },
    )
    assert charts
    assert "/* old chart */" in seen_prompts[0]
