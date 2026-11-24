"""Second-pass Mermaid enrichment for Liber output_mode=diagram."""

from __future__ import annotations

import json
import logging
import re
from typing import Any, Protocol

from case3.diagrams import parse_diagrams

log = logging.getLogger("case3.diagram_repair")

_GENERIC_LABEL = re.compile(
    r"(?i)\b("
    r"начало|завершение|конец|финиш|"
    r"этап\s*\d+|шаг\s*\d+|step\s*\d+|stage\s*\d+|"
    r"процесс|универсальн\w*"
    r")\b"
)
_DECISION = re.compile(r"\{[^{}\n]+\}")
_FENCE_JSON = re.compile(r"```(?:json)?\s*\n([\s\S]*?)\n?```", re.I)
_RECT_NODE = re.compile(r"\[[^\]\n]+\]")


class _Completer(Protocol):
    def complete(
        self, *, system: str, user_text: str, reasoning: str | None = None
    ) -> str: ...


def load_repair_system(palette: str | None = None) -> str:
    from case3.diagram_style import format_diagram_color_prompt
    from case3.prompts import load as load_prompt

    return load_prompt(
        "diagram_repair",
        DIAGRAM_COLOR_TABLE=format_diagram_color_prompt(palette),
    )


def looks_like_linear_slop(mermaid: str) -> bool:
    """True when diagram is a generic linear stage chain without decisions."""
    src = (mermaid or "").strip()
    if not src:
        return True
    if _DECISION.search(src):
        return False
    # sequence / mindmap / timeline / state usually not this failure mode
    from case3.diagrams import first_meaningful_line

    head = first_meaningful_line(src).lower()
    if head.startswith(("sequencediagram", "mindmap", "timeline", "statediagram")):
        return False
    labels = _RECT_NODE.findall(src)
    if len(labels) < 3:
        return False
    generic = sum(1 for lab in labels if _GENERIC_LABEL.search(lab))
    # mostly generic rect labels + no diamond → slop
    return generic >= max(2, (len(labels) + 1) // 2)


def parse_repair_response(raw: str, *, max_diagrams: int) -> list[dict[str, Any]]:
    """Extract diagrams[] from repair LLM text; soft-empty on failure."""
    text = (raw or "").strip()
    if not text:
        return []
    body = text
    m = _FENCE_JSON.search(text)
    if m:
        body = m.group(1).strip()
    else:
        # Check if bare JSON array or object
        s_arr = text.find("[")
        e_arr = text.rfind("]")
        s_obj = text.find("{")
        e_obj = text.rfind("}")
        if s_arr >= 0 and e_arr > s_arr and (s_obj < 0 or s_arr < s_obj):
            body = text[s_arr : e_arr + 1]
        elif s_obj >= 0 and e_obj > s_obj:
            body = text[s_obj : e_obj + 1]
    try:
        data = json.loads(body)
    except json.JSONDecodeError:
        log.warning("diagram_repair: invalid JSON")
        return []
    if isinstance(data, list):
        return parse_diagrams(data, max_diagrams=max_diagrams)
    if not isinstance(data, dict):
        return []
    if data.get("status") == "insufficient_data":
        from case3.input_validation import InsufficientDataError

        msg = str(data.get("message") or "В запросе недостаточно конкретных данных для составления схемы.")
        raise InsufficientDataError(msg)
    if "diagrams" in data and isinstance(data["diagrams"], list):
        return parse_diagrams(data["diagrams"], max_diagrams=max_diagrams)
    if "mermaid" in data:
        return parse_diagrams([data], max_diagrams=max_diagrams)
    return parse_diagrams(data.get("diagrams"), max_diagrams=max_diagrams)


def build_repair_user(
    *,
    source: str,
    intent: str,
    drafts: list[dict[str, Any]],
    max_diagrams: int,
) -> str:
    draft_json = json.dumps({"diagrams": drafts}, ensure_ascii=False, indent=2)
    src = (source or "").strip()
    if len(src) > 12000:
        src = src[:12000] + "\n…[truncated]"
    return (
        f"Budget: at most {max_diagrams} diagram(s).\n\n"
        f"## Intent\n{(intent or '').strip() or '(none)'}\n\n"
        f"## Source\n{src}\n\n"
        f"## Draft diagrams (enrich — kill linear slop)\n```json\n{draft_json}\n```\n"
    )


def repair_diagrams(
    drafts: list[dict[str, Any]],
    *,
    source: str,
    intent: str,
    max_diagrams: int,
    client: _Completer,
    palette: str | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Always attempt enrichment when drafts non-empty. Soft-fail → drafts.

    Returns (diagrams, meta) where meta has diagrams_repaired: bool.
    """
    meta: dict[str, Any] = {
        "diagrams_repaired": False,
        "diagrams_draft_slop": any(
            looks_like_linear_slop(str(d.get("mermaid") or "")) for d in drafts
        ),
    }
    if not drafts or max_diagrams <= 0:
        return list(drafts), meta

    try:
        system = load_repair_system(palette)
        user = build_repair_user(
            source=source,
            intent=intent,
            drafts=drafts,
            max_diagrams=max_diagrams,
        )
        raw = client.complete(system=system, user_text=user)
    except Exception as exc:
        log.warning("diagram_repair LLM failed: %s", exc)
        return list(drafts), meta

    enriched = parse_repair_response(raw or "", max_diagrams=max_diagrams)
    if not enriched:
        log.warning("diagram_repair: empty/invalid — keeping draft")
        return list(drafts), meta

    meta["diagrams_repaired"] = True
    return enriched, meta
