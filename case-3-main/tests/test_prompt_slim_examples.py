"""JSON schema example + chart visual guidance stay short."""

from __future__ import annotations

from case3.prompts import load, prompt_dir


def test_01_output_json_example_is_compact() -> None:
    md = (prompt_dir() / "parts/tex/01_output.md").read_text(encoding="utf-8")
    schema = md[md.index("JSON schema") :]
    start = schema.index("```json")
    end = schema.index("\n```", start)
    fence = schema[start:end]
    assert '"charts"' in fence and '"diagrams"' in fence and '"figures"' in fence
    assert "__CASE3_CHART_READY" in fence
    # Pre-slim example html was ~400+ chars; stub should stay small.
    assert "new Chart(" not in fence
    assert len(fence) < 950


def test_02_visual_freedom_is_compact() -> None:
    md = (prompt_dir() / "parts/tex/02_charts.md").read_text(encoding="utf-8")
    assert "### Visual freedom" in md
    assert "### Hard rails" in md
    # Full taste guide was ~1.6k; keep a short bullet set.
    vf = md[md.index("### Visual freedom") : md.index("### Type → Chart.js")]
    assert len(vf) < 900
    assert "Purple" in vf or "purple" in vf.lower()


def test_system_tex_still_has_playbook_and_rails() -> None:
    text = load(
        "system_tex",
        MAX_IMAGES=0,
        MAX_CHARTS=2,
        MAX_DIAGRAMS=0,
        PALETTE_TABLE="| p |",
    )
    assert "horizontal_bar" in text
    assert "animation = false" in text or "animation=false" in text
    assert "__CASE3_CHART_READY" in text
