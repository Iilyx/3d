"""Diagram edit + regenerate (figures.json only, no TeX)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from case3.diagram_edit import DiagramEditError, edit_diagram_in_run, regenerate_diagrams_in_run


def _seed_run(tmp_path: Path) -> Path:
    out = tmp_path / "out"
    out.mkdir()
    source = tmp_path / "src.txt"
    source.write_text(
        "Клиент подаёт заявку. Если КИН ок — договор, иначе отказ.\n",
        encoding="utf-8",
    )
    (out / "meta.json").write_text(
        json.dumps(
            {
                "run_id": "t1",
                "source": str(source),
                "intent": "режим схема",
                "max_diagrams": 2,
                "output_mode": "diagram",
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    (out / "figures.json").write_text(
        json.dumps(
            {
                "figures": [],
                "charts": [],
                "diagrams": [
                    {
                        "id": "dia_01",
                        "title": "Черновик",
                        "type": "flowchart",
                        "mermaid": "flowchart LR\n  A[Начало] --> B[Конец]",
                    }
                ],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    return out


def test_edit_diagram_print_failure_raises(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An explicit pdf/docx rebuild must not look saved when Docker fails."""
    from case3.render import RenderError

    out = _seed_run(tmp_path)

    def _boom(*_a, **_k):
        raise RenderError("docker down")

    monkeypatch.setattr("case3.run_rebuild.rebuild_run_docs", _boom)
    with pytest.raises(RenderError, match="docker down"):
        edit_diagram_in_run(
            out,
            "dia_01",
            mermaid="flowchart TD\nA-->B",
            title="Схема",
            formats={"pdf"},
        )


def test_edit_diagram_saves_sanitized_mermaid(tmp_path: Path) -> None:
    out = _seed_run(tmp_path)
    new_src = (
        "flowchart TD\n"
        "  A[Заявка]:::start --> B{ОК?}:::decision\n"
        "  classDef start fill:#dce8df,stroke:#6b8f76,color:#1a2e22\n"
        "  classDef decision fill:#f3e6c8,stroke:#b8893a,color:#1a2e22\n"
    )
    result = edit_diagram_in_run(out, "dia_01", mermaid=new_src, title="Заявка")
    assert result["id"] == "dia_01"
    assert ":::start" in result["mermaid"]
    assert result["title"] == "Заявка"
    fj = json.loads((out / "figures.json").read_text(encoding="utf-8"))
    assert fj["diagrams"][0]["mermaid"].startswith("flowchart")


def test_edit_diagram_updates_the_slide_title(tmp_path: Path) -> None:
    out = _seed_run(tmp_path)
    slides = out / "slides"
    slides.mkdir()
    (slides / "deck.json").write_text(
        json.dumps(
            {
                "slides": [
                    {"id": "s01", "layout": "title", "title": "Итоги"},
                    {
                        "id": "s02",
                        "layout": "media_hero",
                        "title": "Черновик",
                        "media_id": "dia_01",
                    },
                ]
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    edit_diagram_in_run(
        out,
        "dia_01",
        mermaid="flowchart TD\n  A[Заявка] --> B[Бюджет]",
        title="Поступление",
    )
    deck = json.loads((slides / "deck.json").read_text(encoding="utf-8"))
    assert deck["slides"][1]["title"] == "Поступление"
    assert deck["slides"][1]["caption"] == "Поступление"
    assert deck["slides"][0]["title"] == "Итоги"


def test_edit_diagram_rejects_unknown_id(tmp_path: Path) -> None:
    out = _seed_run(tmp_path)
    with pytest.raises(DiagramEditError, match="not found"):
        edit_diagram_in_run(out, "dia_99", mermaid="flowchart TD\nA-->B")


def test_regenerate_replaces_diagrams_with_llm(tmp_path: Path) -> None:
    out = _seed_run(tmp_path)
    payload = {
        "diagrams": [
            {
                "id": "dia_01",
                "title": "Согласование",
                "type": "flowchart",
                "mermaid": (
                    "flowchart TD\n"
                    "  A[Заявка]:::start --> B{КИН}:::decision\n"
                    "  B -->|ок| C[Договор]:::ok\n"
                    "  classDef start fill:#dce8df,stroke:#6b8f76,color:#1a2e22\n"
                    "  classDef decision fill:#f3e6c8,stroke:#b8893a,color:#1a2e22\n"
                    "  classDef ok fill:#cfe6d4,stroke:#3d7a4a,color:#1a2e22\n"
                ),
            }
        ]
    }

    class Fake:
        def __init__(self) -> None:
            self.calls = 0

        def complete(self, *, system: str, user_text: str, reasoning: str | None = None) -> str:
            self.calls += 1
            # First call = generate; may also call repair
            return "```json\n" + json.dumps(payload, ensure_ascii=False) + "\n```"

    fake = Fake()
    result = regenerate_diagrams_in_run(
        out, palette="atelier", client=fake, skip_repair=True
    )
    assert result["diagrams"][0]["title"] == "Согласование"
    assert "КИН" in result["diagrams"][0]["mermaid"]
    assert fake.calls >= 1
    assert result.get("undo") and result["undo"].get("kind") == "diagram_regen"
    fj = json.loads((out / "figures.json").read_text(encoding="utf-8"))
    assert fj["diagrams"][0]["title"] == "Согласование"
    # Pre-regen snapshot kept «Черновик»
    draft = fj.get("diagrams_draft") or []
    assert draft and draft[0]["title"] == "Черновик"


def test_edit_diagram_re_renders_png_and_updates_status(tmp_path: Path) -> None:
    from unittest.mock import patch

    out = _seed_run(tmp_path)
    new_src = "flowchart TD\n  A[Заявка] --> B[Одобрено]"

    def fake_render(mermaid, dest, **kwargs):
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(b"\x89PNG\r\n\x1a\nrendered")
        return dest

    with patch("case3.slides_media.render_mermaid_png", side_effect=fake_render):
        result = edit_diagram_in_run(out, "dia_01", mermaid=new_src, title="Одобрено")

    assert (out / "figures" / "dia_01.png").is_file()
    meta = json.loads((out / "meta.json").read_text(encoding="utf-8"))
    assert meta.get("media_status", {}).get("dia_01", {}).get("ok") is True
    assert "version" in result


def test_refine_diagram_in_run_applies_targeted_instruction(tmp_path: Path) -> None:
    from unittest.mock import patch
    from case3.diagram_edit import refine_diagram_in_run

    out = _seed_run(tmp_path)
    payload = {
        "diagram": {
            "id": "dia_01",
            "title": "Заявка с юристами",
            "type": "flowchart",
            "mermaid": (
                "flowchart TD\n"
                "  A[Заявка]:::start --> B{КИН}:::decision\n"
                "  B -->|ок| L[Юристы]:::process\n"
                "  L --> C[Договор]:::ok\n"
                "  classDef start fill:#dce8df,stroke:#6b8f76,color:#1a2e22\n"
                "  classDef decision fill:#f3e6c8,stroke:#b8893a,color:#1a2e22\n"
                "  classDef process fill:#eef3ef,stroke:#5a7a64,color:#1a2e22\n"
                "  classDef ok fill:#cfe6d4,stroke:#3d7a4a,color:#1a2e22\n"
            ),
        }
    }

    class FakeClient:
        def __init__(self) -> None:
            self.last_user = ""

        def complete(self, *, system: str, user_text: str, reasoning: str | None = None) -> str:
            self.last_user = user_text
            return "```json\n" + json.dumps(payload, ensure_ascii=False) + "\n```"

    fake = FakeClient()

    def fake_render(mermaid, dest, **kwargs):
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(b"\x89PNG\r\n\x1a\nrendered_refine")
        return dest

    with patch("case3.slides_media.render_mermaid_png", side_effect=fake_render):
        result = refine_diagram_in_run(
            out,
            "dia_01",
            instruction="добавь этап согласования с юристами",
            client=fake,
        )

    assert result["title"] == "Заявка с юристами"
    assert "Юристы" in result["mermaid"]
    assert "добавь этап согласования с юристами" in fake.last_user
    assert result.get("undo") and result["undo"].get("kind") == "diagram_refine"
    assert (out / "figures" / "dia_01.png").is_file()


def test_regenerate_diagrams_rasterizes_png_and_updates_media_status(tmp_path: Path) -> None:
    from unittest.mock import patch

    out = _seed_run(tmp_path)
    payload = {
        "diagrams": [
            {
                "id": "dia_01",
                "title": "Новый процесс",
                "type": "flowchart",
                "mermaid": "flowchart LR\n  A --> B",
            }
        ]
    }

    class FakeClient:
        def complete(self, *, system: str, user_text: str, reasoning: str | None = None) -> str:
            return "```json\n" + json.dumps(payload, ensure_ascii=False) + "\n```"

    def fake_render(mermaid, dest, **kwargs):
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(b"\x89PNG\r\n\x1a\nrendered_regen")
        return dest

    with patch("case3.slides_media.render_mermaid_png", side_effect=fake_render):
        result = regenerate_diagrams_in_run(out, palette="ocean", client=FakeClient(), skip_repair=True)

    assert len(result["diagrams"]) == 1
    dest_png = out / "figures" / "dia_01.png"
    assert dest_png.is_file()
    assert dest_png.read_bytes() == b"\x89PNG\r\n\x1a\nrendered_regen"
    meta = json.loads((out / "meta.json").read_text(encoding="utf-8"))
    assert meta.get("media_status", {}).get("dia_01", {}).get("ok") is True



