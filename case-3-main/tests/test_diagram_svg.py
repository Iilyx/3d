"""Diagram SVG export helpers (no Playwright in unit path)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from case3.diagram_svg import (
    DiagramSvgError,
    load_diagram_spec,
    normalize_svg_document,
)


def test_normalize_svg_adds_xmlns() -> None:
    raw = '<svg viewBox="0 0 10 10"><rect width="10" height="10"/></svg>'
    out = normalize_svg_document(raw)
    assert 'xmlns="http://www.w3.org/2000/svg"' in out
    assert "<rect" in out


def test_load_diagram_spec(tmp_path: Path) -> None:
    fj = {
        "diagrams": [
            {
                "id": "dia_01",
                "title": "Flow",
                "type": "flowchart",
                "mermaid": "flowchart TD\n  A-->B",
            }
        ]
    }
    (tmp_path / "figures.json").write_text(
        json.dumps(fj), encoding="utf-8"
    )
    spec = load_diagram_spec(tmp_path, "dia_01")
    assert spec["id"] == "dia_01"
    assert "flowchart" in spec["mermaid"]


def test_load_diagram_missing(tmp_path: Path) -> None:
    (tmp_path / "figures.json").write_text(
        json.dumps({"diagrams": []}), encoding="utf-8"
    )
    with pytest.raises(DiagramSvgError, match="not found"):
        load_diagram_spec(tmp_path, "dia_99")


def test_diagram_html_rendering_fills_all_18_placeholders_and_keeps_opaque_edge_label_bg() -> None:
    from case3.slides_media import render_diagram_html

    rendered = render_diagram_html(mermaid="flowchart TD\nA[Старт] -->|Да| B[Финиш]", palette="atelier")
    assert "{{" not in rendered
    assert "}}" not in rendered
    # Edge label backdrop must not be forced transparent!
    assert ".edgeLabel rect, .edgeLabel .labelBkg, g.edgeLabel rect" not in rendered or "transparent" not in rendered.split(".edgeLabel")[1].split("}")[0]
