"""system_slides JSON example is a short IR sketch; layout table is the authority."""

from __future__ import annotations

from case3.prompts import load, prompt_dir


def test_system_slides_schema_example_is_compact() -> None:
    md = (prompt_dir() / "system_slides.md").read_text(encoding="utf-8")
    schema = md[md.index("# JSON schema") : md.index("# Layout guide")]
    assert '"slides"' in schema
    assert '"layout": "title"' in schema
    assert '"layout": "closing"' in schema
    # Pre-slim had ~9 slide objects; keep a short sketch.
    assert schema.count('"layout"') <= 5
    assert len(schema) < 2200


def test_system_slides_keeps_layout_table_and_rules() -> None:
    text = load(
        "system_slides",
        PALETTE="atelier",
        THEME_OVERLAY="(theme)",
        STRUCTURE_OVERLAY="(structure)",
        CHART_IDS="cht_01",
        FIGURE_IDS="(none)",
        DIAGRAM_IDS="(none)",
        MEDIA_CATALOG="(none)",
        INTENT="intent",
        SOURCE="source",
    )
    assert "# Layout guide" in text
    assert "scorecard" in text
    assert "insufficient_data" in text
    assert "(theme)" in text
