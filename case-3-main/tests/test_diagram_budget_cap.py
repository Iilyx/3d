"""Diagram ceiling is DIAGRAMS_HARD_MAX (5), not a leftover clamp of 3."""

from __future__ import annotations

import inspect

from case3.diagrams import DIAGRAMS_HARD_MAX, clamp_diagram_budget
from case3.intent_compose import build_intent_from_ui


def test_clamp_diagram_budget_honors_hard_max() -> None:
    assert DIAGRAMS_HARD_MAX == 5
    assert clamp_diagram_budget(5) == 5
    assert clamp_diagram_budget(99) == 5
    assert clamp_diagram_budget(0) == 0
    assert clamp_diagram_budget(-2) == 0
    assert clamp_diagram_budget(None) <= DIAGRAMS_HARD_MAX


def test_call_sites_do_not_clamp_diagrams_to_three() -> None:
    from case3 import generate, pipeline

    for src in (
        inspect.getsource(pipeline.run_pipeline),
        inspect.getsource(generate.generate_document),
        inspect.getsource(build_intent_from_ui),
    ):
        assert "min(int(max_diagrams), 3)" not in src
    assert "1–3" not in inspect.getsource(build_intent_from_ui)


def test_intent_tells_the_model_the_real_diagram_budget() -> None:
    intent = build_intent_from_ui(
        chat="процесс",
        chart_types=[],
        max_charts=0,
        max_images=0,
        max_diagrams=5,
        forbid_charts=True,
        forbid_images=True,
        output_mode="report",
    )
    assert "до 5 Mermaid" in intent
    assert "до 3 Mermaid" not in intent
