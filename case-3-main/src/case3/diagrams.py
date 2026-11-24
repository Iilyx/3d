"""Sanitize / parse Mermaid diagrams (Liber UI-only; never TeX-injected)."""

from __future__ import annotations

from case3.color_util import hex_to_rgb

import logging
import os
import re
from typing import Any, Literal, overload

log = logging.getLogger("case3.diagrams")


# Product ceiling for Mermaid Liber UI schemas (API + Settings max).
# Tuned via CASE3_MAX_DIAGRAMS (default 5); code never allows above this constant.
DIAGRAMS_HARD_MAX = 5


def max_diagrams_from_env() -> int:
    """CASE3_MAX_DIAGRAMS — sole diagrams budget/ceiling; default 5; clamp 0–5."""
    raw = (os.environ.get("CASE3_MAX_DIAGRAMS") or "5").strip()
    try:
        n = int(raw)
    except ValueError:
        n = 5
    return max(0, min(n, DIAGRAMS_HARD_MAX))


def clamp_diagram_budget(value: int | None) -> int:
    """Per-request diagram ceiling. None follows the env default. Never a hidden 3."""
    if value is None:
        return max_diagrams_from_env()
    try:
        n = int(value)
    except (TypeError, ValueError):
        n = 0
    return max(0, min(n, DIAGRAMS_HARD_MAX))


DIAGRAM_TYPES = frozenset(
    {"flowchart", "sequence", "mindmap", "timeline", "stateDiagram"}
)

# First-line keywords allowed for each diagrams[].type (after normalize).
_TYPE_HEADERS: dict[str, frozenset[str]] = {
    "flowchart": frozenset({"flowchart", "graph"}),
    "sequence": frozenset({"sequencediagram", "sequence"}),
    "mindmap": frozenset({"mindmap"}),
    "timeline": frozenset({"timeline"}),
    "stateDiagram": frozenset({"statediagram-v2", "statediagram", "state"}),
}

_ID_OK = re.compile(r"^[a-z][a-z0-9_]{0,31}$")
_FENCE = re.compile(r"^```(?:mermaid)?\s*\n([\s\S]*?)\n?```\s*$", re.I)
_MAX_BODY = 6000
_MAX_TITLE = 80
_FIRST_TOKEN = re.compile(r"^([A-Za-z][A-Za-z0-9_-]*)")
_HEX_COLOR = re.compile(r"#([0-9a-fA-F]{3}|[0-9a-fA-F]{6})\b")
_CLICK_LINE = re.compile(r"(?im)^\s*click\s+.*$")
# LLM writes ``Node]::role`` (two colons). Mermaid class suffix is ``:::role``.
_SHORT_ROLE_SUFFIX = re.compile(r"(?<=[\]\)\}>])::(?!:)(?=[A-Za-z])")
# `class A,B foo` is valid; `class A,B foo bar baz` (N names) is not — LLM leak.
# Also catches space-separated nodes: `class A B C process`.
_CLASS_ASSIGN_LINE = re.compile(
    r"(?im)^([ \t]*)class(?!Def\b)[ \t]+(.+?)\s*$"
)
# LLM writes style on `class` instead of `classDef`: `class start fill:#abc,...`
_CLASS_AS_CLASSDEF = re.compile(
    r"(?im)^([ \t]*)class(?!Def\b)[ \t]+([A-Za-z][\w-]*)[ \t]+(fill\s*:.*)$"
)
# Spaces inside edge labels: `B -- |Да| C` → `B -->|Да| C`.
_EDGE_LABEL_SPACES = re.compile(r"([-=.~]{2,})\s+\|([^|]+)\|\s+")

# Sequence diagram alias repair (LLM emits `Actor as Label` missing participant keyword)
_SEQ_KEYWORDS = re.compile(
    r"^(participant|actor|note|box|create|destroy|activate|deactivate|rect|loop|alt|opt|par|critical|break|end|autonumber|links?|title|accTitle|accDescr)\b",
    re.I,
)
_SEQ_ARROW = re.compile(r"->|-->|->>|-->>|-x|--x|-\)|--\)")
_SEQ_KEYWORD_AS = re.compile(
    r"^([ \t]*)(participant|actor)\s+(.+?)\s+as\s+(.+)$", re.I
)
_AS_LINE = re.compile(r"^([ \t]*)(.+?\s+as\s+.+)$", re.I)

# Liber soft-premium fallbacks (atelier) — never purple neon.
_SAFE_FILL = "#dce8df"
_SAFE_STROKE = "#6b8f76"


class DiagramError(ValueError):
    """Invalid Mermaid diagram payload."""


def _is_purple_hex(hex_color: str) -> bool:
    """Reject purple / violet neon (product: no нейрослоп)."""
    rgb = hex_to_rgb(hex_color)
    if rgb is None:
        return True
    r, g, b = rgb
    # High R+B with suppressed G → purple/magenta family.
    if b >= 110 and r >= 90 and g <= min(r, b) * 0.78 and ((r + b) / 2 - g) >= 36:
        return True
    # Saturated violet: B dominant, R mid, G low.
    if b > r >= g and (b - g) >= 70 and r >= 60:
        return True
    return False


def _rewrite_unsafe_colors(mermaid: str) -> str:
    """Swap purple fills/strokes in style/classDef to Liber sage."""

    def repl(m: re.Match[str]) -> str:
        full = m.group(0)
        if not _is_purple_hex(full):
            return full
        before = mermaid[max(0, m.start() - 16) : m.start()].lower()
        return _SAFE_STROKE if "stroke" in before else _SAFE_FILL

    return _HEX_COLOR.sub(repl, mermaid)


def _repair_class_assign_lines(mermaid: str) -> str:
    """Fix LLM class / classDef leaks.

    - ``class start fill:#…`` → ``classDef start fill:#…``
    - ``class A,B,C start decision process`` → one class per node (zip)
    - ``class A B C process`` (space-separated nodes, one class) → ``class A,B,C process``
    """
    out: list[str] = []
    for line in (mermaid or "").splitlines():
        as_def = _CLASS_AS_CLASSDEF.match(line)
        if as_def:
            indent, name, style = as_def.group(1), as_def.group(2), as_def.group(3).strip()
            out.append(f"{indent}classDef {name} {style}")
            continue
        m = _CLASS_ASSIGN_LINE.match(line)
        if not m:
            out.append(line)
            continue
        indent, rest = m.group(1), m.group(2).strip()
        tokens = [t.lstrip(":") for t in rest.split()]
        if len(tokens) < 2:
            out.append(line)
            continue
        # Comma-joined first token(s): `A,B,C start decision process`
        if "," in tokens[0]:
            nodes = [n.strip() for n in tokens[0].split(",") if n.strip()]
            names = tokens[1:]
            if len(names) <= 1:
                # `class A,B,C process` — valid Mermaid (one class, many nodes)
                out.append(f"{indent}class {','.join(nodes)} {names[0]}")
                continue
            if len(names) == len(nodes) and all(
                re.match(r"^[A-Za-z][\w-]*$", n) for n in names
            ):
                for node, cls in zip(nodes, names):
                    out.append(f"{indent}class {node} {cls}")
                continue
            log.warning(
                "dropped invalid mermaid class line (%d nodes / %d names): %s",
                len(nodes),
                len(names),
                line.strip()[:120],
            )
            continue
        # Space-separated: `class A B C process` or `class A start`
        if len(tokens) == 2 and re.match(r"^[A-Za-z][\w-]*$", tokens[0]) and re.match(r"^[A-Za-z][\w-]*$", tokens[1]):
            out.append(f"{indent}class {tokens[0]} {tokens[1]}")
            continue
        if len(tokens) >= 3 and all(
            re.match(r"^[A-Za-z][\w-]*$", t) for t in tokens
        ):
            nodes, cls = tokens[:-1], tokens[-1]
            out.append(f"{indent}class {','.join(nodes)} {cls}")
            continue
        log.warning(
            "dropped invalid mermaid class line: %s",
            line.strip()[:120],
        )
    return "\n".join(out)


def _normalize_edge_label_spaces(mermaid: str) -> str:
    """``B -- |Да| C`` → ``B -->|Да| C`` (tolerant of LLM spacing)."""
    return _EDGE_LABEL_SPACES.sub(r"\1|\2| ", mermaid or "")


def _repair_sequence_diagram_lines(mermaid: str) -> str:
    """Prepends ``participant `` to ``Alias as Label`` lines and quotes multi-word IDs."""
    lines = (mermaid or "").splitlines()
    if not any(re.match(r"^\s*sequenceDiagram\b", l, re.I) for l in lines):
        return mermaid
    out: list[str] = []
    for line in lines:
        trimmed = line.strip()
        if (
            not trimmed
            or trimmed.startswith("%%")
            or _SEQ_ARROW.search(trimmed)
        ):
            out.append(line)
            continue
        kw_m = _SEQ_KEYWORD_AS.match(line)
        if kw_m:
            indent, kw, ident, alias = kw_m.group(1), kw_m.group(2), kw_m.group(3).strip(), kw_m.group(4).strip()
            if " " in ident and not (ident.startswith('"') and ident.endswith('"')):
                ident = f'"{ident}"'
            out.append(f"{indent}{kw} {ident} as {alias}")
            continue
        if _SEQ_KEYWORDS.match(trimmed):
            out.append(line)
            continue
        m = _AS_LINE.match(line)
        if m:
            indent, rest = m.group(1), m.group(2).strip()
            parts = re.split(r"\s+as\s+", rest, maxsplit=1, flags=re.I)
            if len(parts) == 2:
                ident, alias = parts[0].strip(), parts[1].strip()
                if " " in ident and not (ident.startswith('"') and ident.endswith('"')):
                    ident = f'"{ident}"'
                out.append(f"{indent}participant {ident} as {alias}")
            else:
                out.append(f"{indent}participant {rest}")
        else:
            out.append(line)
    return "\n".join(out)


_FLOW_HDR = re.compile(r"^\s*(?:flowchart|graph)\b", re.IGNORECASE)
_META_LINE = re.compile(
    r"^\s*(?:%%|classDef\b|class\s|style\s|linkStyle\b|subgraph\b|end\b|direction\b|click\b)",
    re.IGNORECASE,
)
_NODE_OPEN = {"[": "]", "{": "}", "(": ")"}


def _quote_flowchart_nodes(mermaid: str) -> str:
    """Auto-quote flowchart node labels containing (), :, \", or %."""
    lines = (mermaid or "").splitlines()
    first = ""
    for ln in lines:
        s = ln.strip()
        if s and not s.startswith("%%") and not s.startswith("---"):
            first = s
            break
    if not _FLOW_HDR.match(first):
        return mermaid
    out_lines: list[str] = []
    for line in lines:
        if _META_LINE.match(line) or _FLOW_HDR.match(line):
            out_lines.append(line)
            continue
        buf: list[str] = []
        i = 0
        n = len(line)
        while i < n:
            ch = line[i]
            # Preserve quoted strings & edge labels |...|
            if ch == '"':
                end = line.find('"', i + 1)
                if end < 0:
                    buf.append(line[i:])
                    break
                buf.append(line[i : end + 1])
                i = end + 1
                continue
            if ch == "|":
                end = line.find("|", i + 1)
                if end < 0:
                    buf.append(line[i:])
                    break
                buf.append(line[i : end + 1])
                i = end + 1
                continue
            if ch in _NODE_OPEN and i > 0 and (line[i - 1].isalnum() or line[i - 1] in "_-"):
                close = _NODE_OPEN[ch]
                # Skip double delimiters [[...]], {{...}}, ((...)), ([...]), [(...)]
                if i + 1 < n and line[i + 1] in "[]{}()/\\":
                    buf.append(ch)
                    i += 1
                    continue
                depth = 1
                j = i + 1
                while j < n and depth > 0:
                    if line[j] == ch:
                        depth += 1
                    elif line[j] == close:
                        depth -= 1
                    j += 1
                if depth == 0:
                    inner = line[i + 1 : j - 1]
                    stripped = inner.strip()
                    if (
                        stripped
                        and not (stripped.startswith('"') and stripped.endswith('"'))
                        and any(c in inner for c in ('(', ')', ':', '"', '%'))
                    ):
                        safe = inner.replace('"', "#quot;")
                        buf.append(f'{ch}"{safe}"{close}')
                        i = j
                        continue
            buf.append(ch)
            i += 1
        out_lines.append("".join(buf))
    return "\n".join(out_lines)


def sanitize_mermaid(text: str) -> str:
    """Strip optional fences; reject empty / oversized bodies; normalize graph→flowchart.

    Keeps model ``classDef`` / ``:::role`` / ``style`` coloring. Strips ``click``
    lines; rewrites purple hex fills to Liber sage; repairs broken ``class`` lines.
    """
    raw = (text or "").strip()
    if not raw:
        raise DiagramError("empty mermaid")
    if "\n" not in raw and ("\\n" in raw or "\\r\\n" in raw):
        raw = raw.replace("\\r\\n", "\n").replace("\\n", "\n")
    m = _FENCE.match(raw)
    if m:
        raw = m.group(1).strip()
    # Also strip a leading ```mermaid line if model left an open fence fragment
    if raw.lower().startswith("```mermaid"):
        raw = re.sub(r"^```mermaid\s*\n?", "", raw, count=1, flags=re.I).strip()
        if raw.endswith("```"):
            raw = raw[: -3].rstrip()
    if not raw:
        raise DiagramError("empty mermaid after fence strip")
    if len(raw) > _MAX_BODY:
        raise DiagramError(f"mermaid too long ({len(raw)} > {_MAX_BODY})")
    # Mermaid accepts `graph` as alias of flowchart — normalize for Liber + type gate.
    raw = re.sub(r"(?im)^(\s*)graph(\s+)", r"\1flowchart\2", raw, count=1)
    raw = _CLICK_LINE.sub("", raw)
    raw = _SHORT_ROLE_SUFFIX.sub(":::", raw)
    raw = _repair_class_assign_lines(raw)
    raw = _repair_sequence_diagram_lines(raw)
    raw = _normalize_edge_label_spaces(raw)
    raw = _quote_flowchart_nodes(raw)
    raw = re.sub(r"\n{3,}", "\n\n", raw).strip()
    raw = _rewrite_unsafe_colors(raw)
    return raw


def first_meaningful_line(mermaid: str) -> str:
    """Return the first non-empty, non-comment line, skipping frontmatter blocks."""
    lines = (mermaid or "").splitlines()
    in_frontmatter = False
    for raw in lines:
        stripped = raw.strip()
        if not stripped:
            continue
        if stripped == "---":
            in_frontmatter = not in_frontmatter
            continue
        if in_frontmatter:
            continue
        if stripped.startswith("%%"):
            continue
        return stripped
    return ""


def _first_keyword(mermaid: str) -> str:
    line = first_meaningful_line(mermaid)
    m = _FIRST_TOKEN.match(line)
    return (m.group(1) if m else "").lower()


def _normalize_type(dtype: str) -> str:
    t = (dtype or "").strip()
    aliases = {
        "state": "stateDiagram",
        "statediagram": "stateDiagram",
        "statediagram-v2": "stateDiagram",
        "sequencediagram": "sequence",
        "flow": "flowchart",
        "graph": "flowchart",
    }
    key = t.lower()
    return aliases.get(key, t)


def header_matches_type(dtype: str, mermaid: str) -> bool:
    """True when first Mermaid keyword matches diagrams[].type whitelist."""
    kw = _first_keyword(mermaid)
    allowed = _TYPE_HEADERS.get(dtype)
    if not allowed:
        return False
    return kw in allowed


@overload
def parse_diagrams(
    raw: Any, *, max_diagrams: int, with_drops: Literal[False] = False
) -> list[dict[str, Any]]: ...


@overload
def parse_diagrams(
    raw: Any, *, max_diagrams: int, with_drops: Literal[True]
) -> tuple[list[dict[str, Any]], list[dict[str, str]]]: ...


def parse_diagrams(
    raw: Any, *, max_diagrams: int, with_drops: bool = False
) -> list[dict[str, Any]] | tuple[list[dict[str, Any]], list[dict[str, str]]]:
    """Validate LLM diagrams[]; drop bad entries (soft-fail).

    When with_drops=True, also return [{id, reason}, ...] for meta/UI later.
    """
    out: list[dict[str, Any]] = []
    drops: list[dict[str, str]] = []
    if not isinstance(raw, list) or max_diagrams <= 0:
        return (out, drops) if with_drops else out
    for item in raw:
        if not isinstance(item, dict):
            continue
        did = str(item.get("id", "")).strip()
        dtype = _normalize_type(str(item.get("type", "")).strip())
        title = str(item.get("title", "") or item.get("caption", "") or "").strip()
        mermaid_raw = str(item.get("mermaid", "")).strip()
        if not _ID_OK.match(did):
            drops.append({"id": did or "?", "reason": "bad id"})
            continue
        if dtype not in DIAGRAM_TYPES:
            drops.append({"id": did, "reason": f"unknown type {dtype!r}"})
            continue
        if not mermaid_raw:
            drops.append({"id": did, "reason": "empty mermaid"})
            continue
        try:
            mermaid = sanitize_mermaid(mermaid_raw)
        except DiagramError as exc:
            log.warning("drop diagram %s: %s", did, exc)
            drops.append({"id": did, "reason": str(exc)})
            continue
        if not header_matches_type(dtype, mermaid):
            reason = (
                f"type/header mismatch: type={dtype} "
                f"first={_first_keyword(mermaid)!r}"
            )
            log.warning("drop diagram %s: %s", did, reason)
            drops.append({"id": did, "reason": reason})
            continue
        if not title:
            title = did
        out.append(
            {
                "id": did,
                "title": title[:_MAX_TITLE],
                "type": dtype,
                "mermaid": mermaid,
            }
        )
        if len(out) >= max_diagrams:
            break
    return (out, drops) if with_drops else out
