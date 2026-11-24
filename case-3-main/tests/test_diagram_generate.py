"""Diagram mode shares one prompt builder for the first pass and recovery."""

from __future__ import annotations

from case3.diagram_generate import DIAGRAM_SOURCE_LIMIT, complete_diagrams


class _FakeClient:
    def __init__(self) -> None:
        self.user_text = ""
        self.calls = 0

    def complete(self, *, system: str, user_text: str, cancel_check=None) -> str:  # noqa: ANN001
        self.calls += 1
        self.user_text = user_text
        assert "diagram_generate" in system or "Mermaid" in system or system
        if cancel_check is not None:
            cancel_check()
        return (
            "```json\n"
            '{"diagrams":[{"id":"dia_01","type":"flowchart","title":"Заявка",'
            '"mermaid":"flowchart TD\\n  A[Заявка] --> B[Готово]"}]}\n'
            "```"
        )


def test_complete_diagrams_clips_source_and_parses_once() -> None:
    source = "факт " * 5000
    assert len(source) > DIAGRAM_SOURCE_LIMIT
    client = _FakeClient()
    diagrams = complete_diagrams(
        intent="Схема заявки",
        source_text=source,
        max_diagrams=1,
        client=client,
        palette="atelier",
    )
    assert client.calls == 1
    assert len(diagrams) == 1
    assert diagrams[0]["id"] == "dia_01"
    source_block = client.user_text.split("## Source\n", 1)[1].split("\n\n", 1)[0]
    assert len(source_block) == DIAGRAM_SOURCE_LIMIT
    assert "1–1" in client.user_text
