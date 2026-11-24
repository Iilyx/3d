"""D10: palette_public swatches ≡ _PALETTES; prompt table stays in sync."""

from __future__ import annotations

from case3.chart_style import _PALETTES, palette_fallback_table, palette_public
from case3.generate import load_system_prompt


def test_palette_public_matches_palettes() -> None:
    by_id = {p["id"]: p for p in palette_public()}
    assert "auto" in by_id
    for pid, spec in _PALETTES.items():
        entry = by_id[pid]
        assert entry["label"] == spec["label"]
        assert entry["swatches"][0] == spec["primary"]
        assert entry["swatches"][1:] == list(spec["accents"][:3])


def test_system_prompt_embeds_live_palette_hexes() -> None:
    text = load_system_prompt(max_images=0, max_charts=2, max_diagrams=0)
    table = palette_fallback_table()
    # Every named preset primary must appear (single source of truth).
    for pid, spec in _PALETTES.items():
        assert spec["primary"] in text
        assert spec["primary"] in table
        assert pid in table.lower() or spec["label"].lower() in table.lower()
