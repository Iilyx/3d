"""One Mermaid JSON call shared by diagram mode and its empty-draft recovery."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, Protocol

DIAGRAM_SOURCE_LIMIT = 12_000


class _DiagramClient(Protocol):
    def complete(
        self,
        *,
        system: str,
        user_text: str,
        cancel_check: Callable[[], None] | None = None,
    ) -> str: ...


def diagram_prompts(
    *,
    intent: str | None,
    source_text: str,
    max_diagrams: int,
    palette: str,
) -> tuple[str, str]:
    """System + user text. Source is clipped to ``DIAGRAM_SOURCE_LIMIT``."""
    from case3.diagram_edit import _load_generate_system

    budget = max(1, int(max_diagrams))
    system = _load_generate_system(max_diagrams=budget, palette=palette)
    clipped = (source_text or "")[:DIAGRAM_SOURCE_LIMIT]
    user = (
        f"## Intent\n{(intent or '').strip() or '(none)'}\n\n"
        f"## Source\n{clipped}\n\n"
        "Return ONLY one ```json fence with a diagrams array "
        f"(1–{budget} Mermaid). No prose before the fence."
    )
    return system, user


def complete_diagrams(
    *,
    intent: str | None,
    source_text: str,
    max_diagrams: int,
    client: _DiagramClient,
    palette: str,
    cancel_check: Callable[[], None] | None = None,
) -> list[dict[str, Any]]:
    """Call ``client`` once and parse a diagrams array. May raise InsufficientDataError."""
    from case3.diagram_repair import parse_repair_response

    system, user = diagram_prompts(
        intent=intent,
        source_text=source_text,
        max_diagrams=max_diagrams,
        palette=palette,
    )
    raw = client.complete(system=system, user_text=user, cancel_check=cancel_check)
    return parse_repair_response(raw or "", max_diagrams=max(1, int(max_diagrams)))
