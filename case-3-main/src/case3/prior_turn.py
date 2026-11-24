"""One previous Liber run, quoted into the next Intent.

This is dialogue context for a follow-up («короче», «добавь раздел»).
Numbers and facts still come only from the new Source.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from case3.run_store import RUN_ID_OK

_PROMPT_MAX = 400
_SUMMARY_MAX = 900


def _clip(value: object, limit: int) -> str:
    text = " ".join(str(value or "").split())
    if len(text) <= limit:
        return text
    if limit <= 1:
        return ""
    return text[: limit - 1].rstrip() + "…"


def format_prior_turn(meta: dict[str, Any] | None) -> str:
    data = meta or {}
    prompt = _clip(data.get("chat_prompt"), _PROMPT_MAX)
    if not prompt:
        intent = str(data.get("intent") or "")
        head = intent.split("\n\nТребования UI:", 1)[0]
        head = head.split("\n\nПредыдущий ход этого чата", 1)[0]
        prompt = _clip(head, _PROMPT_MAX)
    summary = _clip(data.get("chat_summary"), _SUMMARY_MAX)
    if not prompt and not summary:
        return ""
    lines = [
        "Предыдущий ход этого чата (контекст диалога, не Source):",
        "Числа и факты бери только из Source этого запроса. "
        "Прошлый ход нужен, чтобы понять правку относительно уже собранного результата.",
    ]
    if prompt:
        lines.append(f"Прошлый запрос: {prompt}")
    if summary:
        lines.append(f"Прошлый итог: {summary}")
    return "\n".join(lines)


def insert_prior_turn(intent: str, block: str) -> str:
    text = (block or "").strip()
    if not text:
        return intent
    marker = "\n\nТребования UI:"
    if marker in intent:
        head, tail = intent.split(marker, 1)
        return f"{head.rstrip()}\n\n{text}{marker}{tail}"
    base = (intent or "").rstrip()
    if not base:
        return text
    return f"{base}\n\n{text}"


def prior_block_for_form(
    raw: str | None,
    *,
    root: Path,
    user_text: str = "",
) -> str:
    """Load the prior block. Missing runs yield an empty string.

    A malformed id is a client bug and raises ValueError (API → 400).
    A deleted run must not block the new request.
    """
    rid = (raw or "").strip()
    if not rid:
        return ""
    if not RUN_ID_OK.match(rid):
        raise ValueError("invalid prior_run_id")
    out = (Path(root) / "runs" / "out" / rid).resolve()
    out_root = (Path(root) / "runs" / "out").resolve()
    if not str(out).startswith(str(out_root)):
        raise ValueError("invalid prior_run_id")
    meta_path = out / "meta.json"
    if not meta_path.is_file():
        return ""
    try:
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return ""
    if not isinstance(meta, dict):
        return ""
    from case3.chat_memory import (
        _source_file,
        format_card,
        format_thread,
        format_user_numbers,
        load_chain,
        memory_card,
        recall_block,
    )

    chain = load_chain(root, rid)
    source = ""
    for turn in reversed(chain):
        source = _source_file(root, turn)
        if source.strip():
            break
    parts = [
        format_user_numbers(chain),
        format_card(memory_card(chain, source)),
        format_thread(chain) or format_prior_turn(meta),
        recall_block(chain, user_text),
    ]
    return "\n\n".join(part for part in parts if part)
