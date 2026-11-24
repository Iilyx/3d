"""Charts/diagrams must beat soft «≤2» and JSON figure-first token steal."""

from case3 import prompts
from case3.generate import build_user_prompt, load_system_prompt


def test_system_prompt_puts_charts_before_figures_in_schema() -> None:
    text = load_system_prompt(max_images=5, max_charts=5, max_diagrams=2)
    schema = text[text.index("JSON schema") :]
    fence = schema[schema.index("```json") : schema.index("\n```", schema.index("```json") + 1)]
    assert fence.index('"charts"') < fence.index('"diagrams"') < fence.index('"figures"')
    assert "≤2 charts" not in text
    assert "Aim for up to 5 charts" in text
    assert "opt-in only" in text.lower()
    assert "Image API `figures`" in text or "opt-in only" in text.lower()


def test_user_prompt_does_not_cap_at_two_charts() -> None:
    user = build_user_prompt(
        source="Выручка 10; 20; 30",
        intent="5 графиков",
        max_images=5,
        max_charts=5,
        max_diagrams=2,
    )
    assert "≤2 charts" not in user
    assert "chart budget first" in user.lower()


def test_composed_parts_load() -> None:
    text = prompts.load(
        "system_tex",
        MAX_IMAGES=5,
        MAX_CHARTS=5,
        MAX_DIAGRAMS=2,
        PALETTE_TABLE="| x |",
    )
    assert "≤2 charts" not in text
    assert text.index('"charts"') < text.index('"figures"')
