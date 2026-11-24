"""Parse LLM reply: ```latex ... ``` then ```json ... ``` (figures + charts + diagrams)."""

from __future__ import annotations

import json
import logging
import re
from typing import Any

from case3.chart_html import CHART_TYPES, ChartHtmlError, sanitize_chart_html
from case3.diagrams import parse_diagrams
from case3.image_prompt import ImagePromptError, sanitize_image_prompt
from case3.tex_safe import sanitize_width
from case3.tex_utils import extract_tex, finish_preamble_only_tex

log = logging.getLogger("case3.parse")

# Legacy whole-fence matcher (tests / simple cases). Prefer _iter_lang_fences —
# models often omit the closing ``` before the next ```json / ```latex opener.
_FENCE = re.compile(r"```(\w*)\s*([\s\S]*?)```", re.I)
_LANG_OPEN = re.compile(r"```(\w+)\s*\n", re.I)
_LONE_CLOSE = re.compile(r"(?m)^```[ \t]*\r?$")
_ID_OK = re.compile(r"^[a-z][a-z0-9_]{0,31}$")
# Slot at line start; tolerate LLM trailing notes: `%CASE3_CHART:cht_01%  (SLA)`.
# Strict `$` after the slot missed those lines → false "no slots" → dump before \end{document}.
_FIG_SLOT = re.compile(
    r"(?m)^[ \t]*%CASE3_FIG:([a-z][a-z0-9_]{0,31})%[^\n]*\r?\n?"
)
_CHART_SLOT = re.compile(
    r"(?m)^[ \t]*%CASE3_CHART:([a-z][a-z0-9_]{0,31})%[^\n]*\r?\n?"
)
_CHART_SLOT_LINE = _CHART_SLOT
_DIAG_SLOT = re.compile(
    r"(?m)^[ \t]*%CASE3_DIAG:([a-z][a-z0-9_]{0,31})%[^\n]*\r?\n?"
)
_DIAG_SLOT_LINE = _DIAG_SLOT


class ParseError(ValueError):
    """Model output does not satisfy the dual-fence / slot contract."""


def _ids(pattern: re.Pattern[str], tex: str) -> list[str]:
    seen: list[str] = []
    for m in pattern.finditer(tex or ""):
        fid = m.group(1)
        if fid not in seen:
            seen.append(fid)
    return seen


def _strip_chart_slots(tex: str, keep: set[str]) -> str:
    def repl(m: re.Match[str]) -> str:
        return m.group(0) if m.group(1) in keep else ""

    return _CHART_SLOT_LINE.sub(repl, tex)


def _strip_diag_slots(tex: str, keep: set[str]) -> str:
    def repl(m: re.Match[str]) -> str:
        return m.group(0) if m.group(1) in keep else ""

    return _DIAG_SLOT_LINE.sub(repl, tex)


def _append_missing_slots(
    tex: str,
    *,
    chart_ids: list[str],
    figure_ids: list[str],
    diagram_ids: list[str] | None = None,
) -> str:
    """If JSON has media but the LaTeX forgot slots, append them before \\end{document}."""
    have_c = set(_ids(_CHART_SLOT, tex))
    have_f = set(_ids(_FIG_SLOT, tex))
    have_d = set(_ids(_DIAG_SLOT, tex))
    lines: list[str] = []
    for fid in figure_ids:
        if fid and fid not in have_f:
            lines.append(f"%CASE3_FIG:{fid}%")
    for cid in chart_ids:
        if cid and cid not in have_c:
            lines.append(f"%CASE3_CHART:{cid}%")
    for did in diagram_ids or []:
        if did and did not in have_d:
            lines.append(f"%CASE3_DIAG:{did}%")
    if not lines:
        return tex
    block = "\n" + "\n".join(lines) + "\n"
    if r"\end{document}" in (tex or ""):
        return tex.replace(r"\end{document}", block + r"\end{document}", 1)
    return (tex or "").rstrip() + block


def _strip_trailing_fence(body: str) -> str:
    text = (body or "").strip()
    if text.endswith("```"):
        text = text[:-3].rstrip()
    return text


def _first_json_object(text: str) -> str | None:
    """Return the leading JSON object substring, or None."""
    start = (text or "").find("{")
    if start < 0:
        return None
    depth = 0
    in_str = False
    esc = False
    for j, ch in enumerate(text[start:], start):
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
            continue
        if ch == '"':
            in_str = True
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return text[start : j + 1]
    return None


def _iter_lang_fences(raw: str) -> list[tuple[str, str]]:
    """Split ```lang blocks; next ```lang opener ends the previous body if close omitted."""
    text = raw or ""
    opens = list(_LANG_OPEN.finditer(text))
    out: list[tuple[str, str]] = []
    for i, m in enumerate(opens):
        lang = (m.group(1) or "").lower()
        body_start = m.end()
        limit = opens[i + 1].start() if i + 1 < len(opens) else len(text)
        region = text[body_start:limit]
        close = _LONE_CLOSE.search(region)
        body = region[: close.start()] if close else region
        out.append((lang, body.strip()))
    return out


def _json_candidates(raw: str) -> list[str]:
    """All JSON-looking blobs (closed fences + trailing unclosed ```json)."""
    out: list[str] = []
    seen: set[str] = set()

    def _add(body: str) -> None:
        body = _strip_trailing_fence(body)
        if not body or body in seen:
            return
        seen.add(body)
        out.append(body)
        obj = _first_json_object(body)
        if obj and obj not in seen:
            seen.add(obj)
            out.append(obj)

    for lang, body in _iter_lang_fences(raw):
        if lang == "json" or (not lang and body.lstrip().startswith("{")):
            _add(body)
    for m in _FENCE.finditer(raw or ""):
        lang = (m.group(1) or "").lower()
        body = m.group(2).strip()
        if lang == "json" or (lang == "" and body.lstrip().startswith("{")):
            _add(body)
    # Trailing unclosed ```json … (continuation cut mid-object)
    m_open = re.search(r"```json\s*\n([\s\S]*)$", raw or "", re.I)
    if m_open:
        _add(m_open.group(1))
    # Unfenced root JSON objects (e.g. {"charts": [...]} before ```latex ... ```)
    outside = re.sub(r"```[\s\S]*?```", "\n", raw or "")
    pos = 0
    while pos < len(outside):
        obj = _first_json_object(outside[pos:])
        if not obj:
            break
        _add(obj)
        pos = outside.find(obj, pos) + len(obj)
    return out


def _pick_fences(raw: str) -> tuple[str | None, str | None]:
    fences = _iter_lang_fences(raw)
    # Fallback for rare ```\n…``` without a language tag
    if not any(lang in ("latex", "tex", "json") for lang, _ in fences):
        fences = [
            ((m.group(1) or "").lower(), m.group(2).strip())
            for m in _FENCE.finditer(raw or "")
        ]
    tex_body = None
    json_body = None
    # Prefer a latex/tex fence that actually contains \documentclass
    for lang, body in fences:
        if lang in ("latex", "tex") and r"\documentclass" in body:
            tex_body = body
            break
    if tex_body is None:
        for lang, body in fences:
            if lang in ("latex", "tex") and tex_body is None:
                tex_body = body
            elif lang in ("",) and r"\documentclass" in body and tex_body is None:
                tex_body = body
    # Prefer the longest JSON that json.loads accepts; else longest candidate.
    best_ok: str | None = None
    best_any: str | None = None
    for body in _json_candidates(raw):
        if best_any is None or len(body) > len(best_any):
            best_any = body
        try:
            json.loads(body)
        except json.JSONDecodeError:
            continue
        if best_ok is None or len(body) > len(best_ok):
            best_ok = body
    json_body = best_ok or best_any
    return tex_body, json_body


_INVALID_JSON_SINGLE_QUOTE = re.compile(r"(?<!\\)((?:\\\\)*)\\'")


def _loads_json_lenient(raw_json: str) -> Any:
    """Parse JSON and retry once when a model wrote invalid \\' escapes inside HTML/JS strings."""
    try:
        return json.loads(raw_json)
    except json.JSONDecodeError:
        fixed = _INVALID_JSON_SINGLE_QUOTE.sub(r"\1'", raw_json)
        if fixed != raw_json:
            return json.loads(fixed)
        raise


def salvage_json_object(raw: str) -> dict[str, Any] | None:
    """Recover figures/charts/diagrams from truncated or multi-fence JSON.

    Keeps only complete chart/figure/diagram objects (valid JSON object substrings).
    """
    figures: list[Any] = []
    charts: list[Any] = []
    diagrams: list[Any] = []
    seen_fig: set[str] = set()
    seen_cht: set[str] = set()
    seen_dia: set[str] = set()

    blobs = _json_candidates(raw)
    if not blobs and (raw or "").lstrip().startswith("{"):
        blobs = [(raw or "").strip()]
    # Also scan the full raw (fence markers ignored by brace walker) so a chart
    # completed only after a premature ``` close is still recovered.
    if raw and raw not in blobs:
        blobs.append(raw)

    for blob in blobs:
        try:
            data = _loads_json_lenient(blob)
        except json.JSONDecodeError:
            data = None
        if isinstance(data, dict):
            for item in data.get("figures") or []:
                if isinstance(item, dict) and str(item.get("id", "")) not in seen_fig:
                    figures.append(item)
                    seen_fig.add(str(item.get("id", "")))
            for item in data.get("charts") or []:
                if isinstance(item, dict) and str(item.get("id", "")) not in seen_cht:
                    charts.append(item)
                    seen_cht.add(str(item.get("id", "")))
            for item in data.get("diagrams") or []:
                if isinstance(item, dict) and str(item.get("id", "")) not in seen_dia:
                    diagrams.append(item)
                    seen_dia.add(str(item.get("id", "")))
            continue

        # Truncated root: scan every `{`; skip unclosed spans (advance by 1).
        i = 0
        while i < len(blob):
            start = blob.find("{", i)
            if start < 0:
                break
            depth = 0
            in_str = False
            esc = False
            end = None
            for j, ch in enumerate(blob[start:], start):
                if in_str:
                    if esc:
                        esc = False
                    elif ch == "\\":
                        esc = True
                    elif ch == '"':
                        in_str = False
                    continue
                if ch == '"':
                    in_str = True
                elif ch == "{":
                    depth += 1
                elif ch == "}":
                    depth -= 1
                    if depth == 0:
                        end = j + 1
                        break
            if end is None:
                i = start + 1
                continue
            chunk = blob[start:end]
            i = end
            try:
                obj = _loads_json_lenient(chunk)
            except json.JSONDecodeError:
                continue
            if not isinstance(obj, dict) or "id" not in obj:
                if isinstance(obj, dict):
                    for item in obj.get("figures") or []:
                        if isinstance(item, dict) and str(item.get("id", "")) not in seen_fig:
                            figures.append(item)
                            seen_fig.add(str(item.get("id", "")))
                    for item in obj.get("charts") or []:
                        if isinstance(item, dict) and str(item.get("id", "")) not in seen_cht:
                            charts.append(item)
                            seen_cht.add(str(item.get("id", "")))
                    for item in obj.get("diagrams") or []:
                        if isinstance(item, dict) and str(item.get("id", "")) not in seen_dia:
                            diagrams.append(item)
                            seen_dia.add(str(item.get("id", "")))
                continue
            oid = str(obj.get("id", ""))
            if "html" in obj and oid and oid not in seen_cht:
                charts.append(obj)
                seen_cht.add(oid)
            elif "prompt" in obj and oid and oid not in seen_fig:
                figures.append(obj)
                seen_fig.add(oid)
            elif "mermaid" in obj and oid and oid not in seen_dia:
                diagrams.append(obj)
                seen_dia.add(oid)

    if not figures and not charts and not diagrams:
        return None
    return {"figures": figures, "charts": charts, "diagrams": diagrams}


def _parse_figures_list(raw_figs: Any, *, max_images: int) -> list[dict[str, Any]]:
    figures: list[dict[str, Any]] = []
    if not isinstance(raw_figs, list):
        return figures
    gen_count = 0
    for item in raw_figs:
        if not isinstance(item, dict):
            continue
        fid = str(item.get("id", "")).strip()
        if not _ID_OK.match(fid):
            continue
        if fid.startswith("usr_"):
            caption = str(item.get("caption", "")).strip()
            if caption and caption != fid:
                figures.append(
                    {
                        "id": fid,
                        "caption": caption,
                        "width": sanitize_width(str(item.get("width", "")) or None),
                    }
                )
            continue
        if max_images <= 0 or gen_count >= max_images:
            continue
        prompt_raw = str(item.get("prompt", "")).strip()
        if not prompt_raw:
            continue
        try:
            prompt = sanitize_image_prompt(prompt_raw)
        except ImagePromptError as exc:
            log.warning("drop figure %s: bad prompt (%s)", fid, exc)
            continue
        figures.append(
            {
                "id": fid,
                "caption": str(item.get("caption", "")).strip() or "Иллюстрация",
                "prompt": prompt,
                "width": sanitize_width(str(item.get("width", "")) or None),
            }
        )
        gen_count += 1
    return figures


def _parse_charts_list(raw_charts: Any, *, max_charts: int) -> list[dict[str, Any]]:
    charts: list[dict[str, Any]] = []
    if not isinstance(raw_charts, list) or max_charts <= 0:
        return charts
    for item in raw_charts:
        if not isinstance(item, dict):
            continue
        cid = str(item.get("id", "")).strip()
        ctype = str(item.get("type", "")).strip().lower()
        if ctype == "doughnut":
            ctype = "donut"
        if ctype == "pie":
            ctype = "donut"
        html_raw = str(item.get("html", "")).strip()
        if not _ID_OK.match(cid) or ctype not in CHART_TYPES or not html_raw:
            continue
        try:
            html = sanitize_chart_html(html_raw)
        except ChartHtmlError as exc:
            log.warning("drop chart %s: bad html (%s)", cid, exc)
            continue
        entry: dict[str, Any] = {
            "id": cid,
            "type": ctype,
            "caption": str(item.get("caption", "")).strip() or cid,
            "html": html,
            "width": sanitize_width(str(item.get("width", "")) or None),
        }
        insight = str(item.get("insight", "") or "").strip()
        if insight:
            entry["insight"] = insight[:400]
        raw_hl = item.get("highlights")
        if isinstance(raw_hl, list):
            highlights: list[dict[str, str]] = []
            for h in raw_hl[:8]:
                if not isinstance(h, dict):
                    continue
                label = str(h.get("label", "")).strip()
                value = str(h.get("value", "")).strip()
                if not label or not value:
                    continue
                row: dict[str, str] = {"label": label[:80], "value": value[:40]}
                pct = str(h.get("pct", "") or "").strip()
                if pct:
                    row["pct"] = pct[:16]
                highlights.append(row)
            if highlights:
                entry["highlights"] = highlights
        charts.append(entry)
        if len(charts) >= max_charts:
            break
    return charts


def _merge_media_lists(primary: list[Any], extra: list[Any]) -> list[Any]:
    """Union by id; prefer the entry with longer html/prompt/mermaid."""
    by_id: dict[str, Any] = {}
    for item in list(primary or []) + list(extra or []):
        if not isinstance(item, dict):
            continue
        oid = str(item.get("id", "")).strip()
        if not oid:
            continue
        prev = by_id.get(oid)
        if prev is None:
            by_id[oid] = item
            continue
        prev_len = len(
            str(prev.get("html") or prev.get("prompt") or prev.get("mermaid") or "")
        )
        new_len = len(
            str(item.get("html") or item.get("prompt") or item.get("mermaid") or "")
        )
        if new_len > prev_len:
            by_id[oid] = item
    return list(by_id.values())


def _load_media_payload(raw: str, json_body: str | None) -> dict[str, Any]:
    """Load figures/charts dict; salvage complete objects if JSON is truncated."""
    data: dict[str, Any] = {}
    if json_body:
        try:
            parsed = _loads_json_lenient(json_body)
            if isinstance(parsed, dict):
                data = parsed
        except json.JSONDecodeError:
            pass
    salvaged = salvage_json_object(raw)
    if salvaged:
        charts = _merge_media_lists(data.get("charts") or [], salvaged.get("charts") or [])
        figures = _merge_media_lists(
            data.get("figures") or [], salvaged.get("figures") or []
        )
        diagrams = _merge_media_lists(
            data.get("diagrams") or [], salvaged.get("diagrams") or []
        )
        if charts or figures or diagrams:
            if not (
                data.get("charts") or data.get("figures") or data.get("diagrams")
            ):
                log.warning(
                    "salvaged truncated JSON → %d charts, %d figures, %d diagrams",
                    len(charts),
                    len(figures),
                    len(diagrams),
                )
            elif (
                len(charts) > len(data.get("charts") or [])
                or len(figures) > len(data.get("figures") or [])
                or len(diagrams) > len(data.get("diagrams") or [])
            ):
                log.warning(
                    "merged salvage into JSON → %d charts, %d figures, %d diagrams",
                    len(charts),
                    len(figures),
                    len(diagrams),
                )
            return {"figures": figures, "charts": charts, "diagrams": diagrams}
    return data if isinstance(data, dict) else {}


def _chart_ids_from_data(data: dict[str, Any], *, max_charts: int) -> list[str]:
    if max_charts <= 0:
        return []
    charts = _parse_charts_list(data.get("charts"), max_charts=max_charts)
    return [c["id"] for c in charts]


def _figure_ids_from_data(data: dict[str, Any], *, max_images: int) -> list[str]:
    if max_images <= 0:
        return []
    figs = _parse_figures_list(data.get("figures"), max_images=max_images)
    return [f["id"] for f in figs]


def parse_model_output(
    raw: str,
    *,
    max_images: int,
    max_charts: int = 0,
    max_diagrams: int = 0,
) -> tuple[
    str,
    list[dict[str, Any]],
    list[dict[str, Any]],
    list[dict[str, Any]],
    list[dict[str, str]],
]:
    tex_body, json_body = _pick_fences(raw)
    data = _load_media_payload(raw, json_body)

    if isinstance(data, dict) and data.get("status") == "insufficient_data":
        from case3.input_validation import InsufficientDataError

        msg = str(data.get("message") or "В запросе недостаточно конкретных данных для составления отчёта.")
        raise InsufficientDataError(msg)

    # Peek media ids early so we can rebuild a body if preamble was truncated.
    early_charts = _chart_ids_from_data(data, max_charts=max_charts)
    early_figs = _figure_ids_from_data(data, max_images=max_images)
    early_dias: list[str] = []
    if max_diagrams > 0 and isinstance(data, dict):
        early_dias = [
            str(d.get("id") or "")
            for d in (
                parse_diagrams(data.get("diagrams"), max_diagrams=max_diagrams) or []
            )
            if isinstance(d, dict) and d.get("id")
        ]

    try:
        if tex_body is None:
            tex = extract_tex(raw)
        else:
            if (
                r"\documentclass" in tex_body
                and r"\begin{document}" not in tex_body
            ):
                log.warning(
                    "LaTeX fence is preamble-only — synthesizing \\begin{document} "
                    "with slots for charts=%s figures=%s diagrams=%s",
                    early_charts,
                    early_figs,
                    early_dias,
                )
                tex_body = finish_preamble_only_tex(
                    tex_body,
                    chart_ids=early_charts,
                    figure_ids=early_figs,
                    diagram_ids=early_dias,
                )
            tex = extract_tex("```latex\n" + tex_body + "\n```")
    except ValueError as exc:
        # Last resort: valid JSON media but unusable TeX → minimal document.
        # Diagram-only mode often gets thinking + ```json diagrams[] without LaTeX.
        if early_charts or early_figs or early_dias:
            log.warning(
                "extract_tex failed (%s) — building minimal doc "
                "(charts=%s figs=%s dias=%s)",
                exc,
                early_charts,
                early_figs,
                early_dias,
            )
            from case3.tex_utils import _MIN_PREAMBLE

            tex = finish_preamble_only_tex(
                _MIN_PREAMBLE.rstrip() + "\n",
                chart_ids=early_charts,
                figure_ids=early_figs,
                diagram_ids=early_dias,
            )
        else:
            raise ParseError(str(exc)) from exc

    fig_slots = _ids(_FIG_SLOT, tex) if max_images > 0 else []
    chart_slots = _ids(_CHART_SLOT, tex) if max_charts > 0 else []
    diag_slots = _ids(_DIAG_SLOT, tex) if max_diagrams > 0 else []
    # If caps are 0, ignore leftover slots (inject will strip unknown? we strip via empty status)
    if max_images <= 0:
        fig_slots = []
    if max_charts <= 0:
        chart_slots = []
    if max_diagrams <= 0:
        diag_slots = []

    need_json = bool(
        [s for s in fig_slots if not s.startswith("usr_")] or chart_slots or diag_slots
    )
    if need_json and not data:
        # Truncated model output often has slots but no ```json — drop slots and
        # still return TeX so PDF can build (charts/figures/diagrams empty this run).
        log.warning(
            "missing ```json with slots figures=%s charts=%s diagrams=%s — stripping slots",
            fig_slots,
            chart_slots,
            diag_slots,
        )
        tex = re.sub(
            r"(?m)^[ \t]*%CASE3_FIG:(?!usr_)[a-z][a-z0-9_]{0,31}%[ \t]*\r?\n?",
            "",
            tex,
        )
        tex = _CHART_SLOT_LINE.sub("", tex)
        tex = _DIAG_SLOT_LINE.sub("", tex)
        fig_slots = [s for s in fig_slots if s.startswith("usr_")]
        chart_slots = []
        diag_slots = []

    figures: list[dict[str, Any]] = []
    charts: list[dict[str, Any]] = []
    diagrams: list[dict[str, Any]] = []
    diagram_drops: list[dict[str, str]] = []
    if isinstance(data, dict) and data:
        figures = _parse_figures_list(data.get("figures"), max_images=max_images)
        charts = _parse_charts_list(data.get("charts"), max_charts=max_charts)
        diagrams, diagram_drops = parse_diagrams(
            data.get("diagrams"), max_diagrams=max_diagrams, with_drops=True
        )

    # Id collision across figures, charts, and diagrams
    fig_ids = {f["id"] for f in figures}
    chart_ids = {c["id"] for c in charts}
    dia_ids = {d["id"] for d in diagrams}
    clash = (fig_ids & chart_ids) | (fig_ids & dia_ids) | (chart_ids & dia_ids)
    if clash:
        raise ParseError(
            f"id collision between figures/charts/diagrams: {sorted(clash)}"
        )

    from case3.user_photos import deduplicate_slots_in_tex

    tex = deduplicate_slots_in_tex(tex)
    fig_slots = _ids(_FIG_SLOT, tex)
    chart_slots = _ids(_CHART_SLOT, tex)
    diag_slots = _ids(_DIAG_SLOT, tex)

    if max_images > 0 and figures:
        user_figs_only = [f for f in figures if str(f.get("id") or "").startswith("usr_")]
        gen_figs = [f for f in figures if not str(f.get("id") or "").startswith("usr_")]
        missing_slots = [
            f["id"]
            for f in gen_figs[:max_images]
            if isinstance(f, dict)
            and f.get("id")
            and f["id"] not in fig_slots
            and f"figures/{f['id']}.png" not in tex
        ]
        if missing_slots:
            log.warning(
                "JSON figures without slots — appending %s",
                missing_slots,
            )
            tex = _append_missing_slots(
                tex,
                chart_ids=[],
                figure_ids=missing_slots,
            )
            tex = deduplicate_slots_in_tex(tex)
            fig_slots = _ids(_FIG_SLOT, tex)
        by_fig = {f["id"]: f for f in gen_figs}
        aligned_figs = [by_fig[s] for s in fig_slots if s in by_fig][:max_images]
        missing_figs = [
            s for s in fig_slots if s not in by_fig and not s.startswith("usr_")
        ]
        if missing_figs:
            log.warning("stripping figure slots without valid JSON: %s", missing_figs)
            tex = re.sub(
                r"(?m)^[ \t]*%CASE3_FIG:("
                + "|".join(re.escape(s) for s in missing_figs)
                + r")%[^\n]*\r?\n?",
                "",
                tex,
            )
        figures = aligned_figs + user_figs_only
    else:
        if _ids(_FIG_SLOT, tex):
            tex = re.sub(
                r"(?m)^[ \t]*%CASE3_FIG:(?!usr_)[a-z][a-z0-9_]{0,31}%[^\n]*\r?\n?",
                "",
                tex,
            )
        figures = [f for f in figures if str(f.get("id") or "").startswith("usr_")]

    # Charts: soft-fail — drop invalid slots from TeX instead of aborting the run.
    # Critical: if JSON has charts missing slots in LaTeX, APPEND slots (do not wipe charts).
    if max_charts > 0 and charts:
        missing_chart_slots = [
            c["id"]
            for c in charts[:max_charts]
            if isinstance(c, dict) and c.get("id") and c["id"] not in chart_slots
        ]
        if missing_chart_slots:
            log.warning(
                "JSON charts without slots — appending %s",
                missing_chart_slots,
            )
            tex = _append_missing_slots(
                tex,
                chart_ids=missing_chart_slots,
                figure_ids=[],
            )
            tex = deduplicate_slots_in_tex(tex)
            chart_slots = _ids(_CHART_SLOT, tex)
        by_id = {c["id"]: c for c in charts}
        aligned = [by_id[s] for s in chart_slots if s in by_id][:max_charts]
        missing = [s for s in chart_slots if s not in by_id]
        if missing:
            log.warning("stripping chart slots without valid JSON/html: %s", missing)
        keep = {c["id"] for c in aligned}
        tex = _strip_chart_slots(tex, keep)
        charts = aligned
    else:
        if chart_slots or _ids(_CHART_SLOT, tex):
            tex = _strip_chart_slots(tex, set())
        charts = []

    # Diagrams: soft-fail — drop invalid slots from TeX instead of aborting the run.
    # If JSON has diagrams missing slots in LaTeX, append slots.
    if max_diagrams > 0 and diagrams:
        missing_diag_slots = [
            d["id"]
            for d in diagrams[:max_diagrams]
            if isinstance(d, dict) and d.get("id") and d["id"] not in diag_slots
        ]
        if missing_diag_slots:
            log.warning(
                "JSON diagrams without slots — appending %s",
                missing_diag_slots,
            )
            tex = _append_missing_slots(
                tex,
                chart_ids=[],
                figure_ids=[],
                diagram_ids=missing_diag_slots,
            )
            tex = deduplicate_slots_in_tex(tex)
            diag_slots = _ids(_DIAG_SLOT, tex)
        by_did = {d["id"]: d for d in diagrams}
        aligned_diags = [by_did[s] for s in diag_slots if s in by_did][:max_diagrams]
        missing_diags = [s for s in diag_slots if s not in by_did]
        if missing_diags:
            log.warning("stripping diagram slots without valid JSON/mermaid: %s", missing_diags)
        keep_diags = {d["id"] for d in aligned_diags}
        tex = _strip_diag_slots(tex, keep_diags)
        diagrams = aligned_diags
    else:
        if diag_slots or _ids(_DIAG_SLOT, tex):
            tex = _strip_diag_slots(tex, set())
        diagrams = []
        diagram_drops = []

    return tex, figures, charts, diagrams, diagram_drops
