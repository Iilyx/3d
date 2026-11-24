"""Generate .tex (+ Image API figure prompts + HTML charts) from intent ∥ source."""

from __future__ import annotations

from case3.paths import repo_root

import json
import logging
import os
import re
from collections.abc import Callable
from pathlib import Path
from typing import Any

from case3.chart_html import CHART_TYPES
from case3.chart_style import palette_fallback_table, palette_from_intent
from case3.diagram_style import format_diagram_color_prompt
from case3.chart_coerce import (
    coerce_chart_types,
    ensure_all_charts_match_types,
    polish_charts,
)
from case3.charts import max_charts_from_env
from case3.gold_select import format_gold_appendix, select_gold
from case3.llm_client import LLMClient, LLMConfig, LLMError
from case3.parse_output import parse_model_output
from case3.tex_safe import escape_tex_text

log = logging.getLogger("case3.generate")

DEFAULT_INTENT = (
    "Оформи документ как понятный русскоязычный отчёт: "
    "структура, таблицы где уместны числа, без лишней воды."
)

SOURCE_BEGIN = "<<<CASE3_SOURCE_BEGIN>>>"
SOURCE_END = "<<<CASE3_SOURCE_END>>>"

_PREFERRED_TYPES_RE = re.compile(
    r"(?:ОБЯЗАТЕЛЬНО типы графиков по порядку[^:]*|предпочитай типы)\s*:\s*([^\n—]+)",
    re.I,
)
_DOC_TITLE_RE = re.compile(r"(?m)^- CASE3_DOC_TITLE:\s*(.+)$")


def doc_title_from_intent(intent: str) -> str | None:
    """User title from UI marker in Intent (empty → None)."""
    m = _DOC_TITLE_RE.search(intent or "")
    if not m:
        return None
    title = m.group(1).strip().strip("«»\"'")
    return title[:200] if title else None


def apply_doc_title(tex: str, title: str) -> str:
    """Force \\title{…} to the user-chosen string (escaped)."""
    safe = escape_tex_text((title or "").strip())
    if not safe:
        return tex
    if r"\title{" in (tex or ""):
        return re.sub(
            r"\\title\{[^{}]*\}",
            lambda _m: r"\title{" + safe + "}",
            tex,
            count=1,
        )
    # Insert before \begin{document} if missing
    m = re.search(r"\\begin\{document\}", tex or "")
    if not m:
        return tex
    block = f"\\title{{{safe}}}\n\\author{{}}\n\\date{{\\today}}\n"
    return tex[: m.start()] + block + tex[m.start() :]


_TITLE_CMD = re.compile(r"\\title\{([^{}]*)\}")
_AUTHOR_CMD = re.compile(r"\\author\{[^{}]*\}")
_DATE_CMD = re.compile(r"\\date\{[^{}]*\}")


def ensure_title_block(tex: str) -> str:
    """D3: hard masthead — topical \\title + empty \\author + \\date{\\today} + \\maketitle.

    Preserves a non-empty model/UI \\title. Does not invent content titles from Source.
    """
    out = tex or ""
    m_title = _TITLE_CMD.search(out)
    title_body = (m_title.group(1) if m_title else "").strip()
    if not title_body:
        # Placeholder only when completely missing/empty — model should have set one;
        # keep a neutral Russian default so PDF still builds.
        safe_title = "Отчёт"
        if m_title:
            out = _TITLE_CMD.sub(lambda _m: r"\title{" + safe_title + "}", out, count=1)
        else:
            m_begin = re.search(r"\\begin\{document\}", out)
            if not m_begin:
                return out
            block = f"\\title{{{safe_title}}}\n\\author{{}}\n\\date{{\\today}}\n"
            out = out[: m_begin.start()] + block + out[m_begin.start() :]

    if _AUTHOR_CMD.search(out):
        out = _AUTHOR_CMD.sub(lambda _m: r"\author{}", out, count=1)
    else:
        out = re.sub(
            r"(\\title\{[^{}]*\})",
            lambda m: m.group(1) + "\n\\author{}",
            out,
            count=1,
        )

    if _DATE_CMD.search(out):
        out = _DATE_CMD.sub(lambda _m: r"\date{\today}", out, count=1)
    else:
        out = re.sub(
            r"(\\author\{[^{}]*\})",
            lambda m: m.group(1) + "\n\\date{\\today}",
            out,
            count=1,
        )

    if r"\maketitle" not in out:
        out = re.sub(
            r"(\\begin\{document\})",
            lambda m: m.group(1) + "\n\\maketitle",
            out,
            count=1,
        )
    return out


def preferred_types_from_intent(intent: str) -> list[str]:
    """Parse forced chart types from Intent UI block."""
    m = _PREFERRED_TYPES_RE.search(intent or "")
    if not m:
        return []
    parts = re.split(r"[,;]+", m.group(1))
    out: list[str] = []
    for p in parts:
        t = p.strip().lower()
        # strip trailing notes like "line (foo)"
        t = re.split(r"\s+", t, maxsplit=1)[0]
        if t in CHART_TYPES and t not in out:
            out.append(t)
    return out


def _repo_root() -> Path:
    return repo_root()


def max_images_from_env() -> int:
    from case3.image_api import max_images_from_env as _img_max

    return _img_max()


def load_system_prompt(
    *,
    max_images: int,
    max_charts: int,
    max_diagrams: int = 0,
    has_user_photos: bool = False,
) -> str:
    from case3.prompts import load as load_prompt

    return load_prompt(
        "system_tex",
        MAX_IMAGES=max_images,
        MAX_CHARTS=max_charts,
        MAX_DIAGRAMS=max_diagrams,
        PALETTE_TABLE=palette_fallback_table(),
        has_user_photos=has_user_photos,
    )


def resolve_text_file(path: Path) -> Path:
    path = path.resolve()
    if path.is_file() and path.suffix.lower() in {".txt", ".md"}:
        return path
    raise FileNotFoundError(f"expected .txt/.md file: {path}")


def neutralize_source(source: str) -> str:
    text = source or ""
    text = text.replace(SOURCE_BEGIN, "[CASE3_SOURCE_BEGIN]")
    text = text.replace(SOURCE_END, "[CASE3_SOURCE_END]")
    return text


def build_user_prompt(
    *,
    intent: str,
    source: str,
    max_images: int,
    max_charts: int,
    max_diagrams: int = 0,
    user_figures: list[dict[str, Any]] | None = None,
) -> str:
    from case3.citations import citation_intent_hint
    from case3.prompts import load as load_prompt

    safe = neutralize_source(source.strip())
    cite_hint = citation_intent_hint(safe)
    intent_block = intent.strip() or DEFAULT_INTENT
    if cite_hint:
        intent_block = intent_block + "\n- " + cite_hint
    if user_figures:
        ids_str = ", ".join(f["id"] for f in user_figures if f.get("id"))
        photo_lines = [
            f"- Прикреплены реальные пользовательские изображения (ID: {ids_str}).",
            "- ВНИМАТЕЛЬНО ПОСМОТРИ на каждое прикреплённое изображение: определи, что именно на нём показано (интерфейс, схема, оборудование, документ, процесс, фото с места и т.д.).",
            "- Опиши увиденное на фото в тексте отчёта в соответствующем по смыслу разделе и абзаце (например, «Как видно на фотографии...», «В интерфейсе системы (рис. ...)...»).",
            f"- Размести слот %CASE3_FIG:id% (используй ровно id из {ids_str}) в LaTeX непосредственно рядом с тем абзацем, где это фото анализируется/обсуждается. Не собирай фото в конце документа! ВАЖНО: используй каждый слот %CASE3_FIG:id% ровно ОДИН раз во всём документе, категорически запрещено дублировать слот в разных местах.",
            "- В JSON в массиве figures[] верни объект для каждого такого id с конкретным, информативным caption на русском языке, точно описывающим содержание изображения (не абстрактное «Фото 1»!).",
            "- ВАЖНО: Прикреплённые фотографии служат иллюстрациями к отчёту, но НЕ заменяют исходные данные (Source). Если в Source и Intent нет содержательных фактов, чисел или описания предметной области — верни JSON с {\"status\": \"insufficient_data\", \"message\": \"В запросе недостаточно конкретных данных для составления отчёта.\"} (без LaTeX). НЕ выдумывай фиктивные данные.",
        ]
        intent_block = (
            intent_block
            + "\n\n### Фотографии пользователя (Vision-анализ обязателен):\n"
            + "\n".join(photo_lines)
        )
    return load_prompt(
        "user_tex",
        INTENT_BLOCK=intent_block,
        MAX_IMAGES=max_images,
        MAX_CHARTS=max_charts,
        MAX_DIAGRAMS=max_diagrams,
        DIAGRAM_COLOR_TABLE=format_diagram_color_prompt(palette_from_intent(intent)),
        SOURCE=safe,
    ).rstrip() + "\n"


def output_looks_truncated(raw: str) -> bool:
    """True when the model likely hit a length limit mid-answer."""
    text = raw or ""
    if not text.strip():
        return True
    if r"\begin{document}" in text and r"\end{document}" not in text:
        return True
    if r"\documentclass" in text and r"\begin{document}" not in text:
        return True
    if text.count("```") % 2 == 1:
        return True
    has_slots = ("%CASE3_CHART:" in text) or ("%CASE3_FIG:" in text)
    if has_slots and "```json" not in text and '"charts"' not in text:
        return True
    # Dual-fence contract: JSON fence emitted first, but LaTeX document never started/finished.
    if (
        ("```json" in text or '"charts"' in text or '"diagrams"' in text or '"figures"' in text)
        and (r"\documentclass" not in text or r"\end{document}" not in text)
    ):
        return True
    # Closed ```json fence whose body does not json.loads → cut mid-object.
    if "```json" in text or '"charts"' in text:
        from case3.parse_output import _pick_fences

        _tex, jb = _pick_fences(text)
        if jb:
            try:
                data = json.loads(jb)
            except json.JSONDecodeError:
                return True
            # Slots present but JSON says empty media → model never finished charts.
            if has_slots and isinstance(data, dict):
                charts = data.get("charts") or []
                figs = data.get("figures") or []
                if not charts and not figs:
                    return True
    return False


def _extract_loose_latex(raw: str) -> str | None:
    """Grab \\documentclass… even from an unclosed ```latex fence."""
    text = raw or ""
    m = re.search(
        r"```(?:latex|tex)?\s*\n(\\documentclass[\s\S]*)",
        text,
        re.I,
    )
    if m:
        body = m.group(1)
        # stop before a following ```json if present
        cut = re.search(r"\n```(?:json)?\s*\n", body)
        if cut:
            body = body[: cut.start()]
        return body.strip() or None
    idx = text.find(r"\documentclass")
    if idx >= 0:
        return text[idx:].strip() or None
    return None


def merge_continuation(raw: str, cont: str) -> str:
    """Attach a continuation (often ```json only or ```latex) to a truncated first reply."""
    from case3.parse_output import _pick_fences

    base = (raw or "").rstrip()
    extra = (cont or "").strip()
    if not extra:
        return base

    b_tex, b_json = _pick_fences(base)
    e_tex, e_json = _pick_fences(extra)
    if not b_tex:
        b_tex = _extract_loose_latex(base)
    if not e_tex:
        e_tex = _extract_loose_latex(extra)

    # Prefer continuation only when its LaTeX is a real document with prose
    # richer than the truncated base (avoid wiping a longer first reply).
    if (
        e_json
        and e_tex
        and r"\begin{document}" in e_tex
        and (r"\section" in e_tex or len(e_tex) > 800)
        and len(extra) >= len(base) * 0.8
    ):
        return extra

    # Prefer the longer JSON blob (continuation often truncates harder).
    json_part = e_json or b_json
    if e_json and b_json and len(b_json) > len(e_json) * 1.2:
        json_part = b_json
    if e_tex and r"\begin{document}" in e_tex and (not b_tex or len(e_tex) >= len(b_tex)):
        tex_part = e_tex
    elif b_tex and r"\begin{document}" in b_tex:
        tex_part = b_tex
    elif e_tex and r"\begin{document}" in e_tex:
        tex_part = e_tex
    else:
        tex_part = b_tex or e_tex

    chunks: list[str] = []
    if json_part:
        chunks.append("```json\n" + json_part.strip() + "\n```")
    if tex_part:
        chunks.append("```latex\n" + tex_part.strip() + "\n```")
    if chunks:
        merged = "\n\n".join(chunks)
        # Never shrink below the original truncated reply (salvage needs it).
        if len(merged) + 64 < len(base):
            return base + ("\n\n" + extra if extra else "")
        return merged

    # JSON-only truncation: do NOT close an open ```json fence — salvage needs
    # the unbroken stream to finish chart objects across the continuation.
    base_is_json = "```json" in base or '"charts"' in base
    extra_is_json = (
        "```json" in extra
        or extra.lstrip().startswith("{")
        or '"charts"' in extra
    )
    if base_is_json and extra_is_json and not b_tex and not e_tex:
        return base + "\n" + extra

    if base.count("```") % 2 == 1:
        base += "\n```"
    if "```json" in extra or extra.lstrip().startswith("{"):
        if not extra.lstrip().startswith("```"):
            extra = "```json\n" + extra + "\n```"
        return base + "\n\n" + extra
    return base + "\n" + extra


def _tex_body_prose_stats(tex: str) -> tuple[int, int, int]:
    """Return (prose_letters, media_slots_or_figures, section_count)."""
    m = re.search(r"\\begin\{document\}([\s\S]*?)\\end\{document\}", tex or "")
    if not m:
        return 0, 0, 0
    body = m.group(1)
    media = len(
        re.findall(
            r"(?m)^[ \t]*%CASE3_(?:FIG|CHART|DIAG):[a-z][a-z0-9_]{0,31}%",
            body,
        )
    )
    media += len(re.findall(r"\\begin\{figure\}", body))
    sections = len(
        re.findall(
            r"\\(?:chapter|section|subsection|subsubsection)\*?",
            body,
        )
    )
    prose = re.sub(r"\\maketitle", "", body)
    prose = re.sub(
        r"(?m)^[ \t]*%CASE3_(?:FIG|CHART|DIAG):[a-z][a-z0-9_]{0,31}%[^\n]*\r?\n?",
        "",
        prose,
    )
    prose = re.sub(r"\\begin\{figure\}[\s\S]*?\\end\{figure\}", "", prose)
    prose = re.sub(r"\\includegraphics(?:\[[^\]]*\])?\{[^}]*\}", "", prose)
    prose = re.sub(r"\\caption\{[^}]*\}", "", prose)
    prose = re.sub(r"\\label\{[^}]*\}", "", prose)
    prose = re.sub(r"\\centering", "", prose)
    prose = re.sub(
        r"\\(?:chapter|section|subsection|subsubsection|paragraph)\*?\{[^{}]*\}",
        "",
        prose,
    )
    prose = re.sub(r"%[^\n]*", "", prose)
    letters = len(re.findall(r"[A-Za-zА-Яа-яЁё]", prose))
    return letters, media, sections


def tex_body_is_sparse(tex: str) -> bool:
    """True when the document has almost no prose (charts/slots only)."""
    letters, _media, _sections = _tex_body_prose_stats(tex)
    return letters < 40


def tex_body_needs_source_fill(tex: str) -> bool:
    """Sparse OR truncated media-dump: 1 short section + many trailing slots/figs.

    Win desk 080546: finish_reason=length → JSON ok, LaTeX ~1 paragraph, then
    parse appends all fig/cht slots at EOF. Letter count >40 so sparse-fill
    skipped → PDF is «no text / all illustrations piled».
    """
    letters, media, sections = _tex_body_prose_stats(tex)
    if letters < 40:
        return True
    if media >= 4 and sections <= 1 and letters < 900:
        return True
    if media >= 6 and letters < 1200 and sections <= 2:
        return True
    return False


def _is_md_table_sep(line: str) -> bool:
    s = (line or "").strip()
    return bool(s) and "-" in s and bool(re.match(r"^\|?[\s\-:|]+\|?$", s))


def _next_nonempty(raw_lines: list[str], start: int) -> tuple[int, str]:
    j = start
    while j < len(raw_lines) and not raw_lines[j].strip():
        j += 1
    if j >= len(raw_lines):
        return j, ""
    return j, raw_lines[j].strip()


def _looks_like_md_table_start(raw_lines: list[str], i: int) -> bool:
    """Header `|…|` then (optional blanks) a markdown separator row."""
    if not raw_lines[i].strip().startswith("|"):
        return False
    j, nxt = _next_nonempty(raw_lines, i + 1)
    return bool(nxt) and _is_md_table_sep(nxt)


# One A4 page of single-line booktabs rows. Longer tables must break.
_ONE_PAGE_ROWS = 24


def _table_cells(row: list[str], ncol: int) -> str:
    cells = [escape_tex_text(c) for c in (row + [""] * ncol)[:ncol]]
    return " & ".join(cells) + r" \\"


def _emit_xltabular(rows: list[list[str]]) -> list[str]:
    """Page-breaking table. Y columns wrap; the header repeats."""
    ncol = max(len(r) for r in rows)
    spec = "Y" * max(ncol, 1)
    out = [
        rf"\begin{{xltabular}}{{\textwidth}}{{{spec}}}",
        r"\toprule",
        _table_cells(rows[0], ncol),
        r"\midrule",
        r"\endhead",
        r"\bottomrule",
        r"\endfoot",
    ]
    for row in rows[1:]:
        out.append(_table_cells(row, ncol))
    out.append(r"\end{xltabular}")
    out.append("")
    return out


def _emit_tabularx(rows: list[list[str]]) -> list[str]:
    if not rows:
        return []
    if len(rows) > _ONE_PAGE_ROWS:
        return _emit_xltabular(rows)
    ncol = max(len(r) for r in rows)
    spec = "Y" * max(ncol, 1)
    out = [
        rf"\begin{{tabularx}}{{\textwidth}}{{{spec}}}",
        r"\toprule",
    ]
    for ri, row in enumerate(rows):
        out.append(_table_cells(row, ncol))
        if ri == 0:
            out.append(r"\midrule")
    out.append(r"\bottomrule")
    out.append(r"\end{tabularx}")
    out.append("")
    return out


_EMOJI_CHARS = re.compile(
    "["
    "\U0001F300-\U0001FAFF"
    "\U00002700-\U000027BF"
    "\U00002600-\U000026FF"
    "\U0000FE0F"
    "]+"
)
_MD_BULLET = re.compile(r"^([-*•]|\d+\.)\s+(\S.*)$")
# Meta-skeleton kits (Win desk 070133) + imperative prompt lines: not report prose.
_DROP_SOURCE_LINE = re.compile(
    r"(?i)^("
    r"понял вас|ниже представлен|вот текст|конечно[,.]?|"
    r"ниже данны|скопируй|для построения график|"
    r"сгенерируй\s+фото|сделай\s+(?:полный\s+)?отч[её]т|"
    r"добавь\s+(?:фото|иллюстрац|график|схем)|вставь\s+(?:вот\s+)?это\s+фото|"
    r"нарисуй\s+схем|построй\s+график|"
    r".*полный комплект.*|"
    r".*\bскелет\b.*|"
    r".*вы можете взять.*|"
    r".*используйте эт(у|о|и).*|"
    r".*блок\s*\d+.*|"
    r".*расширенн\w+ и углубленн\w+ верси.*|"
    r"^я добавил\b.*|"
    r".*готовом? к копированию.*"
    r").*"
)
_INLINE_PROMPT_SENTENCE = re.compile(
    r"(?i)(?:^|(?<=[.!?]\s))("
    r"сгенерируй\s+фото[^.!?]*[.!?]?|"
    r"сделай\s+(?:полный\s+)?отч[её]т[^.!?]*[.!?]?|"
    r"добавь\s+(?:фото|иллюстрац|график|схем)[^.!?]*[.!?]?|"
    r"вставь\s+(?:вот\s+)?это\s+фото[^.!?]*[.!?]?"
    r")"
)


def _scrub_heading_text(text: str) -> str:
    cleaned = _EMOJI_CHARS.sub("", text or "")
    cleaned = re.sub(r"[ \t]{2,}", " ", cleaned).strip(" \t")
    return cleaned


def _source_lines_to_tex(source: str) -> list[str]:
    """Turn Source (plain / light Markdown) into TeX body lines — not raw dumps."""
    text = (source or "").replace("\r\n", "\n").strip()
    # Markdown tables often arrive with blank lines between rows — normalize.
    text = re.sub(r"(\|[^\n]*\|)\n(?:\s*\n)+(?=\s*\|)", r"\1\n", text)
    lines_out: list[str] = []
    i = 0
    raw_lines = text.split("\n")
    title: str | None = None
    while i < len(raw_lines):
        stripped = raw_lines[i].strip()
        if not stripped or stripped in {"***", "---"}:
            i += 1
            continue
        if _DROP_SOURCE_LINE.match(stripped):
            i += 1
            continue
        if stripped.startswith(">"):
            quote = stripped.lstrip("> ").strip()
            quote = re.sub(r"\*\*(.+?)\*\*", r"«\1»", quote)
            lines_out.append(r"\begin{quote}")
            lines_out.append(escape_tex_text(quote))
            lines_out.append(r"\end{quote}")
            lines_out.append("")
            i += 1
            continue
        if _looks_like_md_table_start(raw_lines, i):
            rows: list[list[str]] = []
            while i < len(raw_lines):
                row = raw_lines[i].strip()
                if not row:
                    # blank inside table: keep going if more | rows follow
                    j, nxt = _next_nonempty(raw_lines, i + 1)
                    if nxt.startswith("|"):
                        i = j
                        continue
                    break
                if not row.startswith("|"):
                    break
                i += 1
                if _is_md_table_sep(row):
                    continue
                cells = [c.strip() for c in row.strip("|").split("|")]
                rows.append(cells)
            lines_out.extend(_emit_tabularx(rows))
            continue
        # Orphan pipe-rows (no separator): still try to tabulate ≥2 consecutive.
        if stripped.startswith("|"):
            rows = []
            while i < len(raw_lines):
                row = raw_lines[i].strip()
                if not row:
                    j, nxt = _next_nonempty(raw_lines, i + 1)
                    if nxt.startswith("|"):
                        i = j
                        continue
                    break
                if not row.startswith("|"):
                    break
                i += 1
                if _is_md_table_sep(row):
                    continue
                rows.append([c.strip() for c in row.strip("|").split("|")])
            if len(rows) >= 2:
                lines_out.extend(_emit_tabularx(rows))
                continue
            # single weird pipe line → plain text
            lines_out.append(escape_tex_text(stripped.replace("|", " ").strip()))
            lines_out.append("")
            continue
        m_h = re.match(r"^(#{1,3})\s+(.+)$", stripped)
        if m_h:
            level = len(m_h.group(1))
            heading = escape_tex_text(_scrub_heading_text(m_h.group(2)))
            if level == 1 and title is None:
                title = heading
            elif level <= 2:
                lines_out.append(rf"\section{{{heading}}}")
                lines_out.append("")
            else:
                lines_out.append(rf"\subsection{{{heading}}}")
                lines_out.append("")
            i += 1
            continue
        # Markdown / outline bullets → itemize (Win desk skeleton dumps).
        m_b = _MD_BULLET.match(stripped)
        if m_b:
            items: list[str] = []
            while i < len(raw_lines):
                row = raw_lines[i].strip()
                if not row:
                    j, nxt = _next_nonempty(raw_lines, i + 1)
                    if nxt and _MD_BULLET.match(nxt):
                        i = j
                        continue
                    break
                mb = _MD_BULLET.match(row)
                if not mb:
                    break
                item = re.sub(r"\*\*(.+?)\*\*", r"«\1»", mb.group(2).strip())
                items.append(escape_tex_text(item))
                i += 1
            if items:
                lines_out.append(r"\begin{itemize}")
                for it in items:
                    lines_out.append(rf"\item {it}")
                lines_out.append(r"\end{itemize}")
                lines_out.append("")
            continue
        chunk = [stripped]
        i += 1
        while i < len(raw_lines):
            nxt = raw_lines[i].strip()
            if (
                not nxt
                or nxt.startswith("#")
                or nxt.startswith("|")
                or nxt.startswith(">")
                or _MD_BULLET.match(nxt)
                or _DROP_SOURCE_LINE.match(nxt)
                or nxt in {
                    "***",
                    "---",
                }
            ):
                break
            chunk.append(nxt)
            i += 1
        para = " ".join(chunk)
        para = _INLINE_PROMPT_SENTENCE.sub("", para).strip()
        para = re.sub(r"\*\*(.+?)\*\*", r"«\1»", para)
        para = re.sub(r"(?<!\*)\*(.+?)\*(?!\*)", r"«\1»", para)
        if not para or _DROP_SOURCE_LINE.match(para):
            continue
        lines_out.append(escape_tex_text(para))
        lines_out.append("")
        if len(lines_out) > 120:
            break

    if not lines_out:
        lines_out = [escape_tex_text(text[:2000] or "(исходный текст пуст)")]
    if title:
        lines_out.insert(0, f"%CASE3_TITLE:{title}")
    return _cap_source_tex_lines(lines_out, limit=260)


def _cap_source_tex_lines(lines: list[str], *, limit: int = 260) -> list[str]:
    """Truncate generated fallback TeX safely without leaving open environments."""
    if len(lines) <= limit:
        return lines
    out: list[str] = []
    stack: list[str] = []
    begin_re = re.compile(r"\\begin\{(xltabular|tabularx|itemize|quote)\}")
    end_re = re.compile(r"\\end\{(xltabular|tabularx|itemize|quote)\}")
    for line in lines[:limit]:
        out.append(line)
        for m in begin_re.finditer(line):
            stack.append(m.group(1))
        for m in end_re.finditer(line):
            if stack and stack[-1] == m.group(1):
                stack.pop()
    while stack:
        env = stack.pop()
        out.append(rf"\end{{{env}}}")
    return out


def fill_sparse_tex_with_source(
    tex: str,
    source: str,
    *,
    chart_ids: list[str],
    figure_ids: list[str],
    diagram_ids: list[str] | None = None,
) -> str:
    """Replace an empty body with Source prose + media slots (keeps preamble)."""
    body_lines = _source_lines_to_tex(source)
    title = "Отчёт"
    if body_lines and body_lines[0].startswith("%CASE3_TITLE:"):
        title = body_lines[0].split(":", 1)[1].strip() or title
        body_lines = body_lines[1:]

    # Insert media after the first completed section/table block — never mid-tabularx.
    mid = max(1, len(body_lines) // 2)
    for idx in range(mid, len(body_lines)):
        if body_lines[idx].strip() == r"\end{tabularx}":
            mid = idx + 1
            break
        if body_lines[idx].startswith(r"\section{"):
            mid = idx
            break
    # If mid landed inside an open tabularx, push to after \end{tabularx}.
    open_tx = 0
    for idx, ln in enumerate(body_lines):
        if r"\begin{tabularx}" in ln:
            open_tx += 1
        if r"\end{tabularx}" in ln:
            open_tx = max(0, open_tx - 1)
        if idx + 1 == mid and open_tx:
            for j in range(idx, len(body_lines)):
                if r"\end{tabularx}" in body_lines[j]:
                    mid = j + 1
                    break
            break

    parts: list[str] = [
        r"\begin{document}",
        r"\maketitle",
        "",
    ]
    # Interleave slots after section headings — never dump \\section{Иллюстрации}.
    media_slots = (
        [f"%CASE3_FIG:{fid}%" for fid in figure_ids]
        + [f"%CASE3_CHART:{cid}%" for cid in chart_ids]
        + [f"%CASE3_DIAG:{did}%" for did in (diagram_ids or [])]
    )
    section_idxs = [
        i for i, ln in enumerate(body_lines) if ln.startswith(r"\section{")
    ]
    if media_slots and section_idxs:
        # Place one slot after each section body start (round-robin extras at end).
        enriched: list[str] = []
        slot_i = 0
        for i, ln in enumerate(body_lines):
            enriched.append(ln)
            if i in section_idxs and slot_i < len(media_slots):
                # skip blank after heading, then inject
                enriched.append("")
                enriched.append(media_slots[slot_i])
                enriched.append("")
                slot_i += 1
        while slot_i < len(media_slots):
            enriched.append(media_slots[slot_i])
            enriched.append("")
            slot_i += 1
        body_lines = enriched
        parts.extend(body_lines)
    else:
        parts.extend(body_lines[:mid])
        parts.append("")
        for s in media_slots:
            parts.append(s)
            parts.append("")
        if body_lines[mid:]:
            parts.extend(body_lines[mid:])
            parts.append("")
    parts.append(r"\end{document}")

    new_body = "\n".join(parts) + "\n"
    out = tex or ""
    # Keep / set title in preamble
    if r"\title{" in out:
        out = re.sub(
            r"\\title\{[^{}]*\}",
            lambda _m: r"\title{" + title + "}",
            out,
            count=1,
        )
    else:
        out = out.replace(
            r"\begin{document}",
            r"\title{" + title + "}\n\\author{}\n\\date{\\today}\n\\begin{document}",
            1,
        )

    if re.search(r"\\begin\{document\}[\s\S]*\\end\{document\}", out):
        return re.sub(
            r"\\begin\{document\}[\s\S]*\\end\{document\}\s*",
            lambda _m: new_body,
            out,
            count=1,
        )
    return out.rstrip() + "\n" + new_body


def build_continuation_prompt(*, partial: str, source: str, max_charts: int) -> str:
    from case3.prompts import load as load_prompt

    tail = (partial or "")[-7000:]
    safe = neutralize_source((source or "").strip())
    return load_prompt(
        "continuation_tex",
        MAX_CHARTS=max_charts,
        PARTIAL_TAIL=tail,
        SOURCE=safe,
    ).rstrip() + "\n"


def _build_latex_recovery_prompt(
    *,
    raw_json_reply: str,
    intent: str,
    source: str,
) -> str:
    """Build a focused prompt when JSON media was generated but LaTeX was omitted."""
    from case3.parse_output import salvage_json_object

    salvaged = salvage_json_object(raw_json_reply) or {}
    slot_lines: list[str] = []
    for c in salvaged.get("charts") or []:
        if isinstance(c, dict) and c.get("id"):
            slot_lines.append(f"- %CASE3_CHART:{c['id']}% ({c.get('caption') or c['id']})")
    for d in salvaged.get("diagrams") or []:
        if isinstance(d, dict) and d.get("id"):
            slot_lines.append(f"- %CASE3_DIAG:{d['id']}% ({d.get('title') or d['id']})")
    for f in salvaged.get("figures") or []:
        if isinstance(f, dict) and f.get("id"):
            slot_lines.append(f"- %CASE3_FIG:{f['id']}% ({f.get('caption') or f['id']})")
    slots_block = "\n".join(slot_lines) if slot_lines else "(no media slots)"
    safe = neutralize_source((source or "").strip())
    return (
        "The JSON block with charts/diagrams/figures is already complete, "
        "but the ```latex document block is missing.\n"
        "Return ONLY ONE ```latex fence (`\\documentclass[a4paper,12pt]{article}` … `\\end{document}`).\n"
        "Do NOT output JSON and do NOT output commentary outside the fence.\n"
        "Requirements:\n"
        "- Invent a specific topical Russian `\\title{…}` from Source (never generic «Отчёт»).\n"
        "- Include numbered `\\section{…}` sections, analytical prose, and `booktabs`/`tabularx` tables for the metrics in Source.\n"
        "- Never copy imperative user instructions («Сгенерируй фото…», «Сделай отчёт…») verbatim into the document.\n"
        "- Place each of these media slots alone on its own line inside the appropriate section:\n"
        f"{slots_block}\n\n"
        f"## Intent\n{intent.strip()}\n\n"
        f"## Source\n{SOURCE_BEGIN}\n{safe}\n{SOURCE_END}\n"
    )


def _persist_raw_model(out_tex: Path, stem: str, raw: str) -> Path:
    """Write the model text before the next call or parse. Parent may vanish on Win."""
    out_tex.parent.mkdir(parents=True, exist_ok=True)
    path = out_tex.parent / f"{stem}.raw_model.txt"
    path.write_text(raw or "", encoding="utf-8")
    return path


def generate_document(
    source: Path,
    *,
    out_tex: Path,
    intent: str | None = None,
    gold_dir: Path | None = None,
    client: LLMClient | None = None,
    dry_run: bool = False,
    max_images: int | None = None,
    max_charts: int | None = None,
    max_diagrams: int | None = None,
    cancel_check: Callable[[], None] | None = None,
    user_figures: list[dict[str, Any]] | None = None,
    vision_images: list[tuple[str, str]] | None = None,
    replay_raw: str | None = None,
) -> tuple[Path, list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    """Returns (tex_path, figures, charts, diagrams).

    max_images / max_charts / max_diagrams: per-request overrides; None → env defaults.
    cancel_check: optional cooperative stop (raises between LLM attempts).
    replay_raw: saved model text. Skips the network and parses this string.
    """
    from case3.diagrams import clamp_diagram_budget

    text_path = resolve_text_file(source)
    source_text = text_path.read_text(encoding="utf-8")
    stem = text_path.stem
    root = _repo_root()
    gold_dir = gold_dir or (root / "prompt" / "gold")
    intent_text = (intent or DEFAULT_INTENT).strip()
    if max_images is None:
        max_images = max_images_from_env()
    else:
        max_images = max(0, int(max_images))
    if max_charts is None:
        max_charts = max_charts_from_env()
    else:
        max_charts = max(0, int(max_charts))
    max_diagrams = clamp_diagram_budget(max_diagrams)

    from case3.prompts import dump_prompts

    if vision_images is None and user_figures:
        from case3.user_photos import user_photos_to_vision_images

        vision_images = user_photos_to_vision_images(user_figures)

    gold_paths = select_gold(gold_dir, intent_text, max_items=3, max_images=max_images)
    system = load_system_prompt(
        max_images=max_images,
        max_charts=max_charts,
        max_diagrams=max_diagrams,
        has_user_photos=bool(user_figures),
    ) + format_gold_appendix(gold_paths)
    user = build_user_prompt(
        intent=intent_text,
        source=source_text,
        max_images=max_images,
        max_charts=max_charts,
        max_diagrams=max_diagrams,
        user_figures=user_figures,
    )
    log.info(
        "source=%s intent_len=%d gold=%s max_images=%d max_charts=%d max_diagrams=%d",
        text_path.name,
        len(intent_text),
        [p.name for p in gold_paths],
        max_images,
        max_charts,
        max_diagrams,
    )

    out_tex.parent.mkdir(parents=True, exist_ok=True)
    dump_prompts(out_tex.parent, system=system, user=user)

    if replay_raw is not None:
        raw = replay_raw
        hard_trunc = False
    elif dry_run:
        stub = Path(__file__).resolve().parent / "templates" / "article_skeleton.tex"
        # Escape specials; no verbatim (source may contain \end{verbatim}).
        lines = [
            escape_tex_text(line) for line in source_text[:2000].splitlines()
        ]
        content = "\n\n".join(lines) if lines else "(пусто)"
        body = stub.read_text(encoding="utf-8").replace("%%CONTENT%%", content)
        out_tex.write_text(body, encoding="utf-8")
        payload = {"figures": [], "charts": [], "diagrams": []}
        (out_tex.parent / "figures.json").write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        log.info("dry-run wrote %s", out_tex)
        return out_tex, [], [], []
    else:
        cfg = LLMConfig.from_env()
        # 8 charts HTML ≈ burns 4k tokens alone — Win desk still had VISION_MAX_TOKENS=4096.
        # ≥6 charts need headroom for full Chart.js HTML + TeX (16384).
        if max_charts >= 6 or (max_charts >= 4 and max_images >= 4):
            floor_tok = 16384
        elif max_charts >= 4 or max_images >= 4:
            floor_tok = 12288
        else:
            floor_tok = 8192
        if cfg.max_tokens < floor_tok:
            log.warning(
                "VISION_MAX_TOKENS=%d too low for charts=%d images=%d — bumping to %d",
                cfg.max_tokens,
                max_charts,
                max_images,
                floor_tok,
            )
            cfg = LLMConfig(
                base_url=cfg.base_url,
                api_key=cfg.api_key,
                api_keys=cfg.api_keys,
                model=cfg.model,
                timeout_s=cfg.timeout_s,
                max_retries=cfg.max_retries,
                temperature=cfg.temperature,
                reasoning=cfg.reasoning,
                max_tokens=floor_tok,
            )
        llm = client or LLMClient(cfg)
        raw = llm.complete(
            system=system, user_text=user, cancel_check=cancel_check, images=vision_images
        )
        _persist_raw_model(out_tex, stem, raw or "")
        finish = getattr(llm, "last_finish_reason", "") or ""
        if finish == "error" or (
            "\\documentclass" not in (raw or "") and "```json" not in (raw or "").lower()
        ):
            log.warning(
                "model returned no document (finish_reason=%r, %d chars) — retry once",
                finish,
                len(raw or ""),
            )
            raw = llm.complete(
                system=system,
                user_text=(
                    f"{user}\n\n"
                    "Previous answer had no JSON and no LaTeX. "
                    "Return ONLY two fenced blocks: a ```json object "
                    "(charts, then diagrams, then figures) and a ```latex document "
                    "that contains \\documentclass. No prose."
                ),
                cancel_check=cancel_check,
                images=vision_images,
            )
            _persist_raw_model(out_tex, stem, raw or "")
            finish = getattr(llm, "last_finish_reason", "") or ""
        need_cont = output_looks_truncated(raw or "") or finish == "length"
        hard_trunc = finish == "length"
        if need_cont:
            log.warning(
                "model output looks truncated (%d chars, finish_reason=%r) — continuation pass",
                len(raw or ""),
                finish,
            )
            cont_user = build_continuation_prompt(
                partial=raw or "",
                source=source_text,
                max_charts=max_charts,
            )
            dump_prompts(
                out_tex.parent, system=system, user=user, continuation=cont_user
            )
            cont = llm.complete(
                system=system,
                user_text=cont_user,
                cancel_check=cancel_check,
                images=vision_images,
            )
            cont_finish = getattr(llm, "last_finish_reason", "") or ""
            if cont_finish == "length":
                hard_trunc = True
                log.warning(
                    "continuation also truncated (finish_reason=length) — will force Source fill if TeX thin"
                )
            raw = merge_continuation(raw or "", cont or "")
            _persist_raw_model(out_tex, stem, raw or "")
            log.info("continuation merged → %d chars", len(raw or ""))
            if r"\documentclass" not in (raw or "") and (
                "```json" in (raw or "").lower() or '"charts"' in (raw or "")
            ):
                log.warning(
                    "still no \\documentclass after continuation — running LaTeX recovery pass"
                )
                tex_recovery_user = _build_latex_recovery_prompt(
                    raw_json_reply=raw or "",
                    intent=intent_text,
                    source=source_text,
                )
                tex_cont = llm.complete(
                    system=system,
                    user_text=tex_recovery_user,
                    cancel_check=cancel_check,
                    images=vision_images,
                )
                raw = merge_continuation(raw or "", tex_cont or "")
                _persist_raw_model(out_tex, stem, raw or "")
                log.info("LaTeX recovery merged → %d chars", len(raw or ""))
        else:
            hard_trunc = False

    # Re-mkdir: Win desk 073916 lost work/ during the long LLM call
    # (cleanup / sync / cancel race) → FileNotFoundError on write.
    raw_path = _persist_raw_model(out_tex, stem, raw or "")
    if not (raw or "").strip():
        raise LLMError(
            f"модель вернула пустой текст (см. {raw_path.name}). "
            "В .env поставь VISION_REASONING=off и перезапусти api.cmd"
        )

    try:
        tex, figures, charts, diagrams, diagram_drops = parse_model_output(
            raw,
            max_images=max_images,
            max_charts=max_charts,
            max_diagrams=max_diagrams,
        )
    except Exception:
        log.exception(
            "parse failed; raw saved at %s (%d chars)", raw_path, len(raw or "")
        )
        raise

    # Model often dumps all slots under \\section{Визуализация}/Иллюстрации (081536).
    from case3.tex_media_place import redistribute_gallery_slots

    before = tex
    tex = redistribute_gallery_slots(
        tex, figures=figures, charts=charts, diagrams=diagrams
    )
    if tex != before:
        log.warning(
            "redistributed trailing gallery slots into prose sections "
            "(figs=%d charts=%d)",
            len(figures),
            len(charts),
        )

    forced_title = doc_title_from_intent(intent_text)
    if forced_title:
        tex = apply_doc_title(tex, forced_title)
    tex = ensure_title_block(tex)

    # Truncation often leaves 1 short section + all slots appended (letter count >40).
    need_fill = bool(source_text.strip()) and tex_body_needs_source_fill(tex)
    if need_fill:
        log.warning(
            "TeX body thin/media-dump (hard_trunc=%s) — filling prose from Source (%d chars)",
            hard_trunc,
            len(source_text),
        )
        tex = fill_sparse_tex_with_source(
            tex,
            source_text,
            chart_ids=[c["id"] for c in charts],
            figure_ids=[f["id"] for f in figures],
            diagram_ids=[d["id"] for d in diagrams],
        )
        if forced_title:
            tex = apply_doc_title(tex, forced_title)
        tex = ensure_title_block(tex)

    # Safety: no raw Markdown pipes should remain after Source-fill.
    if re.search(r"(?m)^[ \t]*\|.+\|[ \t]*$", tex):
        log.warning("raw Markdown table pipes still in TeX — re-running table convert")
        from case3.tex_preamble import ensure_document_preamble

        # Re-fill from source only if sparse path already ran; else strip pipes.
        fixed_lines = []
        for ln in tex.splitlines():
            if re.match(r"^[ \t]*\|.+\|[ \t]*$", ln):
                continue
            fixed_lines.append(ln)
        tex = "\n".join(fixed_lines) + "\n"
        tex = ensure_document_preamble(tex)

    from case3.fact_ground import ground_generated

    tex, charts, figures, diagrams, dropped = ground_generated(
        tex,
        charts,
        figures,
        diagrams,
        source=source_text,
        intent=intent_text,
    )
    if dropped:
        log.warning(
            "fact_ground dropped ungrounded number(s): %s",
            ", ".join(dropped[:12]),
        )

    preferred = preferred_types_from_intent(intent_text)
    if preferred:
        charts = coerce_chart_types(charts, preferred)
    else:
        # Auto mode: still fix type=kpi + canvas-bar etc.
        charts = ensure_all_charts_match_types(charts)
    # Model often ignores Intent palette / emits ghostly hbar fills — enforce after grounding.
    charts = polish_charts(charts, palette_id=palette_from_intent(intent_text))
    if dropped:
        log.warning(
            "dropped fact numbers absent from Source and the user message: %s",
            ", ".join(dropped),
        )

    out_tex.write_text(tex, encoding="utf-8")
    fj_payload: dict[str, Any] = {
        "figures": figures,
        "charts": charts,
        "diagrams": diagrams,
    }
    if diagram_drops:
        fj_payload["diagrams_dropped"] = diagram_drops
    (out_tex.parent / "figures.json").write_text(
        json.dumps(fj_payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    log.info(
        "wrote %s (%d chars, %d figures, %d charts, %d diagrams, %d diagram drops)",
        out_tex,
        len(tex),
        len(figures),
        len(charts),
        len(diagrams),
        len(diagram_drops),
    )
    return out_tex, figures, charts, diagrams
