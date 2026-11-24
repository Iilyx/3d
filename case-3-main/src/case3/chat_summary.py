"""Short Liber chat summary from a document outline (facts only)."""

from __future__ import annotations

import logging
import re
from dataclasses import replace
from typing import Any

from case3.llm_client import LLMClient, LLMConfig, LLMConfigError, LLMError
from case3.prompts import load as load_prompt
from case3.tex_preview import tex_to_preview_blocks

log = logging.getLogger(__name__)

# Chat blurb must not stall print UX for a full VISION_TIMEOUT_S (often 300s).
_SUMMARY_TIMEOUT_S = 90.0
_SUMMARY_RETRIES = 1

SUMMARY_SYSTEM = load_prompt("summary_system").strip()
_MAX_PARAS = 6
_MAX_HEADINGS = 12
_MAX_FIGS = 8
_MAX_TABLES = 4
_MAX_TABLE_ROWS = 4
_MAX_TABLE_COLS = 6


def build_outline(tex: str) -> str:
    """Compact outline for the summary LLM (no preamble noise)."""
    data = tex_to_preview_blocks(tex or "")
    lines: list[str] = []
    title = str(data.get("title") or "").strip()
    if title:
        lines.append(f"TITLE: {title}")

    headings = 0
    paras = 0
    figs = 0
    tables = 0
    for block in data.get("blocks") or []:
        if not isinstance(block, dict):
            continue
        kind = block.get("type")
        if kind == "heading" and headings < _MAX_HEADINGS:
            level = int(block.get("level") or 1)
            text = str(block.get("text") or "").strip()
            if text:
                prefix = "#" * min(max(level, 1), 3)
                lines.append(f"{prefix} {text}")
                headings += 1
        elif kind == "paragraph" and paras < _MAX_PARAS:
            text = str(block.get("text") or "").strip()
            if text:
                snippet = text if len(text) <= 220 else text[:217].rstrip() + "…"
                lines.append(f"PARA: {snippet}")
                paras += 1
        elif kind == "figure" and figs < _MAX_FIGS:
            cap = str(block.get("caption") or "").strip()
            fid = str(block.get("id") or "").strip()
            label = cap or fid or "figure"
            # Chart slots use cht_*; photo/API figures use fig_* / usr_*
            tag = "CHART" if fid.startswith("cht_") else "FIGURE"
            lines.append(f"{tag}: {label}")
            figs += 1
        elif kind == "table" and tables < _MAX_TABLES:
            cap = str(block.get("caption") or "").strip()
            headers = block.get("headers") or []
            if cap:
                lines.append(f"TABLE: {cap}")
            elif headers:
                lines.append("TABLE: " + " | ".join(str(h) for h in headers[:6]))
            else:
                lines.append("TABLE: (без подписи)")
            for row in (block.get("rows") or [])[:_MAX_TABLE_ROWS]:
                cells = [" ".join(str(cell).split()) for cell in row[:_MAX_TABLE_COLS]]
                cells = [cell for cell in cells if cell]
                if cells:
                    lines.append("ROW: " + " | ".join(cells))
            tables += 1

    return "\n".join(lines).strip() or "(пустой документ)"


def _first_table_fact(data: dict[str, Any]) -> str:
    """One data row so a fallback blurb can name a real cell."""
    for block in data.get("blocks") or []:
        if not isinstance(block, dict) or block.get("type") != "table":
            continue
        for row in block.get("rows") or []:
            cells = [" ".join(str(cell).split()) for cell in row[:_MAX_TABLE_COLS]]
            cells = [cell for cell in cells if cell]
            text = ", ".join(cells)
            if re.search(r"\d", text):
                return text
    return ""


def format_media_delivered(media: dict[str, Any] | None) -> str:
    """Explicit delivered counts so the summary cannot invent charts/photos."""
    m = media or {}
    charts_ok = int(m.get("charts_ok") or 0)
    figures_ok = int(m.get("figures_ok") or 0)
    charts_planned = int(m.get("charts_planned") or 0)
    figures_planned = int(m.get("figures_planned") or 0)
    return (
        "MEDIA_DELIVERED:\n"
        f"charts_ok: {charts_ok}\n"
        f"figures_ok: {figures_ok}\n"
        f"charts_planned: {charts_planned}\n"
        f"figures_planned: {figures_planned}"
    )


def build_summary_user(
    outline: str,
    *,
    intent: str | None = None,
    media: dict[str, Any] | None = None,
) -> str:
    parts = ["OUTLINE:", outline.strip() or "(пусто)"]
    parts.append("\n" + format_media_delivered(media))
    intent_s = (intent or "").strip()
    if intent_s:
        parts.append(
            "\nINTENT (пожелание, не факт доставки):\n" + intent_s[:1200]
        )
    parts.append(
        "\nНапиши сообщение для чата Liber. Только текст ответа, без преамбулы. "
        "Не преувеличивай MEDIA_DELIVERED."
    )
    return "\n".join(parts)


def missing_chart_note(media: dict[str, Any] | None) -> str:
    """Spoken line when a planned chart never became a file."""
    planned = int((media or {}).get("charts_planned") or 0)
    ok = int((media or {}).get("charts_ok") or 0)
    missed = planned - ok
    if missed <= 0:
        return ""
    if missed == 1:
        return "Один график не собрался и в файл не попал."
    return f"Графиков не собралось: {missed} из {planned}."


def seal_chat_summary(
    text: str,
    media: dict[str, Any] | None,
    *,
    render_error: str = "",
) -> str:
    """Publish a ready line only after print. A TeX failure replaces it."""
    err = (render_error or "").strip()
    if err:
        bang = next((line.strip() for line in err.splitlines() if line.startswith("!")), "")
        loc = next(
            (line.strip() for line in err.splitlines() if line.strip().startswith("l.")),
            "",
        )
        shown = " ".join(part for part in (bang, loc) if part) or err.splitlines()[0][:240]
        return f"PDF не собрался. {shown}"
    note = missing_chart_note(media)
    body = (text or "").strip()
    if note and note not in body:
        body = (body + "\n\n" + note).strip()
    return body


def local_summary_blurb(
    tex: str,
    *,
    media: dict[str, Any] | None = None,
) -> str:
    """Deterministic fallback when the summary LLM times out or fails."""
    data = tex_to_preview_blocks(tex or "")
    title = str(data.get("title") or "").strip() or "Отчёт"
    n_tables = sum(
        1 for b in (data.get("blocks") or []) if isinstance(b, dict) and b.get("type") == "table"
    )
    n_heads = sum(
        1
        for b in (data.get("blocks") or [])
        if isinstance(b, dict) and b.get("type") == "heading"
    )
    m = media or {}
    charts_ok = int(m.get("charts_ok") or 0)
    figures_ok = int(m.get("figures_ok") or 0)
    bits: list[str] = [f"Готов: **{title}**."]
    parts: list[str] = []
    if n_heads:
        parts.append(f"разделов: {n_heads}")
    if n_tables:
        parts.append(f"таблиц: {n_tables}")
    if charts_ok:
        parts.append(f"графиков: {charts_ok}")
    if figures_ok:
        parts.append(f"иллюстраций: {figures_ok}")
    if parts:
        bits.append("Внутри — " + ", ".join(parts) + ".")
    note = missing_chart_note(m)
    if note:
        bits.append(note)
    fact = _first_table_fact(data)
    if fact:
        bits.append(fact + ".")
    bits.append("Подробности — в превью и PDF.")
    return "\n\n".join(bits)


def _summary_client(client: LLMClient | None) -> LLMClient:
    if client is not None:
        return client
    cfg = LLMConfig.from_env()
    return LLMClient(
        replace(
            cfg,
            timeout_s=min(float(cfg.timeout_s), _SUMMARY_TIMEOUT_S),
            max_retries=_SUMMARY_RETRIES,
            max_tokens=min(int(cfg.max_tokens), 2048),
        )
    )


_REASONING_LEAK_REGEX = re.compile(
    r"(?i)\b("
    r"the user wants|"
    r"the user says|"
    r"the user asks|"
    r"we need to|"
    r"let me check|"
    r"let me draft|"
    r"let me write|"
    r"let's check|"
    r"let's analyze|"
    r"let's look|"
    r"thinking process|"
    r"based on the outline|"
    r"from the outline|"
    r"from media_delivered|"
    r"i need to write|"
    r"i will write|"
    r"the instruction:|"
    r"first paragraph:|"
    r"second paragraph:|"
    r"structure:|"
    r"constraints:"
    r")\b"
)


def is_clean_chat_summary(text: str, *, intent: str | None = None) -> bool:
    """Return False if text leaks English CoT / reasoning / meta-planning."""
    t = (text or "").strip()
    if not t:
        return False
    if _REASONING_LEAK_REGEX.search(t):
        return False
    cyrillic_chars = len(re.findall(r"[\u0400-\u04FF]", t))
    latin_chars = len(re.findall(r"[A-Za-z]", t))
    if cyrillic_chars < 10 and latin_chars > 30:
        return False
    if latin_chars > 120 and latin_chars > cyrillic_chars * 1.5:
        return False
    return True


def generate_chat_summary(
    tex: str,
    *,
    intent: str | None = None,
    media: dict[str, Any] | None = None,
    client: LLMClient | None = None,
    on_delta: Any | None = None,
) -> str:
    """Complete (optionally streaming via on_delta) a chat summary. Raises LLMError."""
    outline = build_outline(tex)
    user = build_summary_user(outline, intent=intent, media=media)
    llm = _summary_client(client)
    text = ""
    if on_delta is not None and hasattr(llm, "stream"):
        chunks: list[str] = []
        for piece in llm.stream(
            system=SUMMARY_SYSTEM,
            user_text=user,
            reasoning="off",
            max_tokens=2048,
        ):
            if piece:
                chunks.append(piece)
                on_delta(piece)
        text = "".join(chunks).strip()
    else:
        text = llm.complete(
            system=SUMMARY_SYSTEM,
            user_text=user,
            reasoning="off",
        )
    text = (text or "").strip()
    if hasattr(llm, "last_finish_reason") and llm.last_finish_reason == "length":
        if len(text) < 80 or not text.endswith((".", "!", "?", "»", ")")):
            log.warning("chat summary truncated by length — rejecting")
            return ""
    if not is_clean_chat_summary(text, intent=intent):
        log.warning("chat summary failed clean check (leaked reasoning/English) — rejecting: %s", text[:80])
        return ""
    return text


def try_generate_chat_summary(
    tex: str,
    *,
    intent: str | None = None,
    media: dict[str, Any] | None = None,
    client: LLMClient | None = None,
    on_delta: Any | None = None,
) -> tuple[str, str]:
    """Return (text, status) where status is ok|error|skipped. Never raises.

    On LLM failure returns a local outline blurb with status ``error`` so the
    chat is not empty after a long OpenRouter stall.
    """
    try:
        if client is None:
            try:
                LLMConfig.from_env()
            except LLMConfigError:
                return local_summary_blurb(tex, media=media), "skipped"
        text = generate_chat_summary(
            tex,
            intent=intent,
            media=media,
            client=client,
            on_delta=on_delta,
        )
        if not text:
            blurb = local_summary_blurb(tex, media=media)
            if on_delta:
                on_delta(blurb)
            return blurb, "error"
        return text, "ok"
    except (LLMError, LLMConfigError, OSError, ValueError):
        blurb = local_summary_blurb(tex, media=media)
        if on_delta:
            try:
                on_delta(blurb)
            except Exception:  # noqa: BLE001
                pass
        return blurb, "error"
