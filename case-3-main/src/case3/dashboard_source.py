"""Stimulsoft dashboard → markdown.

PNG goes through the existing Qwen vision client. A born-digital PDF table
is read cell by cell (pdfplumber) so digits stay as printed. No HTTP route:
later the Stimulsoft service calls ``parse_dashboard``.
"""

from __future__ import annotations

import base64
import logging
import re
import tempfile
from decimal import Decimal, InvalidOperation
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Callable, Protocol

from case3 import prompts
from case3.pdf_text_gate import triage_pdf

log = logging.getLogger(__name__)

MAX_PDF_BYTES = 20 * 1024 * 1024
MAX_PNG_BYTES = 15 * 1024 * 1024
MAX_TABLE_COLS = 64
MAX_TABLE_ROWS = 500

_NUM = re.compile(r"\d")
_UNIT_TAIL = r"(?:\s*(?:тыс\.?|млн\.?|млрд\.?|руб\.?|коп\.?|₽|\$|€|шт\.?|чел\.?|п\.?\s*п\.?|ед\.?))*"
_COMPLETE_NUM = re.compile(
    rf"^[+\-−]?\s*(?:\d{{1,3}}(?:[ \u00a0\u202f]\d{{3}})+|\d+)(?:[.,]\d+)?(?:\s*%|{_UNIT_TAIL})?$",
    re.IGNORECASE,
)
_SHORT_NUM = re.compile(r"^[+\-−]?\d{1,3}$")
_THOUSANDS_TAIL = re.compile(r"^\d{3}(?:[.,]\d+)?%?$")
_NUM_TOKEN = re.compile(r"[+\-−]?\d{1,3}(?:[ \u00a0\u202f]\d{3})*(?:[.,]\d+)?%?")
_FENCE = re.compile(r"^```(?:markdown|md)?[^\n]*\n(.*)\n?```$", re.DOTALL)
_WORD_GAP = 8.0
_LINE_BAND = 3.0

_LINE_SETTINGS = {
    "vertical_strategy": "lines",
    "horizontal_strategy": "lines",
    "snap_tolerance": 3,
    "join_tolerance": 3,
    "intersection_tolerance": 3,
}
_TEXT_SETTINGS = {
    "vertical_strategy": "text",
    "horizontal_strategy": "text",
    "snap_tolerance": 4,
    "join_tolerance": 4,
}


class DashboardSourceError(Exception):
    """Stable ``code`` for a later API mapping."""

    def __init__(self, message: str, *, code: str) -> None:
        super().__init__(message)
        self.message = message
        self.code = code


class _VisionClient(Protocol):
    def complete(
        self,
        *,
        system: str,
        user_text: str,
        images: list[tuple[str, str]] | None = None,
    ) -> str: ...


@dataclass(frozen=True)
class DashboardSource:
    markdown: str
    png_markdown: str
    pdf_markdown: str
    warnings: list[str] = field(default_factory=list)
    pdf_table_count: int = 0
    pdf_numeric_cells: int = 0


def parse_dashboard(
    *,
    png: bytes | Path | None = None,
    pdf: bytes | Path | None = None,
    vision: Callable[[bytes], str] | None = None,
) -> DashboardSource:
    """One markdown document from a dashboard screenshot and/or a table PDF."""
    png_bytes = _as_bytes(png) if png is not None else None
    pdf_bytes = _as_bytes(pdf) if pdf is not None else None
    if png_bytes is None and pdf_bytes is None:
        raise DashboardSourceError(
            "Нужен PNG дашборда или PDF с таблицей.",
            code="missing_input",
        )

    png_md = ""
    pdf_md = ""
    warnings: list[str] = []
    table_count = 0
    numeric_cells = 0
    png_error: DashboardSourceError | None = None
    pdf_error: DashboardSourceError | None = None
    if pdf_bytes is not None:
        try:
            pdf_md, table_count, numeric_cells, warnings = _pdf_markdown(pdf_bytes)
        except DashboardSourceError as exc:
            pdf_error = exc
    if png_bytes is not None:
        try:
            png_md = _screen_markdown(png_bytes, vision, keep_table=not pdf_md)
        except DashboardSourceError as exc:
            png_error = exc
    if not png_md and not pdf_md:
        if png_error and pdf_error:
            raise DashboardSourceError(
                f"{png_error.message} {pdf_error.message}",
                code=pdf_error.code,
            )
        if png_error or pdf_error:
            raise png_error or pdf_error

    parts = ["# Данные дашборда", ""]
    if png_md and pdf_md:
        parts += [
            "Числа в разделе «Таблица PDF» скопированы из ячеек файла. "
            "Раздел «Экран» — фильтры, карточки и график. Строки таблицы модель не читает.",
            "",
        ]
    elif pdf_md:
        parts += ["Числа скопированы из ячеек PDF.", ""]
    else:
        parts += [
            "Текст ниже — чтение снимка. Где цифра не читается, стоит «не разобрать».",
            "",
        ]
    if png_error is not None:
        warnings.append(png_error.message)
    if pdf_error is not None:
        warnings.append(pdf_error.message)
    if png_md:
        parts += ["## Экран", "", png_md.rstrip(), ""]
    if pdf_md:
        parts += ["## Таблица PDF", "", pdf_md.rstrip(), ""]
    derived = derivative_block(pdf_md or png_md)
    if derived:
        parts += ["## Производные", "", derived.rstrip(), ""]
    return DashboardSource(
        markdown="\n".join(parts).rstrip() + "\n",
        png_markdown=png_md,
        pdf_markdown=pdf_md,
        warnings=warnings,
        pdf_table_count=table_count,
        pdf_numeric_cells=numeric_cells,
    )


def read_dashboard_png(
    png: bytes,
    *,
    client: _VisionClient | None = None,
    keep_table: bool = False,
) -> str:
    """Ask Qwen for a markdown reading of one dashboard screenshot."""
    _check_png(png)
    if len(png) > MAX_PNG_BYTES:
        raise DashboardSourceError(
            "Снимок больше 15 МБ. Сожмите PNG без сильного даунскейла.",
            code="too_large",
        )
    reader = client if client is not None else _qwen_client()
    system = prompts.load("dashboard_png_only" if keep_table else "dashboard_png")
    data_url = "data:image/png;base64," + base64.b64encode(png).decode("ascii")
    try:
        text = reader.complete(
            system=system,
            user_text="Сними этот дашборд в markdown.",
            images=[("dashboard", data_url)],
        )
    except DashboardSourceError:
        raise
    except Exception as exc:
        raise DashboardSourceError(
            f"Модель не прочитала снимок: {exc}",
            code="vision_failed",
        ) from exc
    cleaned = _finish_screen(text or "", keep_table=keep_table)
    if not cleaned.strip():
        raise DashboardSourceError(
            "Модель ничего не вернула по снимку дашборда.",
            code="empty_screen",
        )
    return cleaned


def table_block(rows: list[list[object | None]]) -> tuple[str, str | None]:
    """One markdown table. A single filled first cell becomes a heading."""
    cleaned = _clean_rows(rows)
    if not cleaned:
        return "", None
    title = ""
    body = cleaned
    if _is_span_title(cleaned[0]):
        title = next(cell for cell in cleaned[0] if cell)
        body = cleaned[1:]
    if not body:
        return (f"## {title}\n" if title else ""), None

    orig_cols = max(len(row) for row in body)
    orig_rows = len(body)
    if len(body) >= 3:
        non_total = [row for row in body[1:] if not _is_total_row(row)]
        hdr_lbl = _label_column(non_total) if non_total else None
        if hdr_lbl is not None:
            gcols = _group_columns(non_total, hdr_lbl)
            if gcols:
                filled_data: list[list[str]] = []
                last_vals = {gc: "" for gc in gcols}
                for row in body[1:]:
                    if _is_total_row(row):
                        last_vals = {gc: "" for gc in gcols}
                        filled_data.append(list(row))
                        continue
                    cur = list(row)
                    for gc in gcols:
                        if gc >= len(cur):
                            continue
                        val = cur[gc].strip()
                        if val:
                            last_vals[gc] = val
                        elif last_vals[gc]:
                            cur[gc] = last_vals[gc]
                    filled_data.append(cur)
                body = [body[0], *filled_data]
    use_cols = min(orig_cols, MAX_TABLE_COLS)
    use_rows = body[:MAX_TABLE_ROWS]
    note = None
    if orig_cols > MAX_TABLE_COLS or orig_rows > MAX_TABLE_ROWS:
        note = (
            f"Таблица обрезана: было {orig_cols}×{orig_rows}, "
            f"осталось {use_cols}×{len(use_rows)}."
        )

    def fmt(row: list[str]) -> str:
        cells = row[:use_cols]
        if len(cells) < use_cols:
            cells = cells + [""] * (use_cols - len(cells))
        return "| " + " | ".join(cells) + " |"

    lines: list[str] = []
    if title:
        lines += [f"## {title}", ""]
    lines.append(fmt(use_rows[0]))
    lines.append("| " + " | ".join("---" for _ in range(use_cols)) + " |")
    for row in use_rows[1:]:
        lines.append(fmt(row))
    text = "\n".join(lines) + "\n"
    if note:
        text = text.rstrip() + "\n\n" + note + "\n"
    return text, note


_TOTAL_LABEL = re.compile(
    r"(?:^|\b)(?:итого|всего|промежуточн\w*\s+итог|в\s+том\s+числе|из\s+них|total|subtotal|grand\s+total|sum|сумма)(?!\w)",
    re.IGNORECASE,
)
_YEAR_HEADER = re.compile(r"^(год|года|year|years)$", re.IGNORECASE)
_CODE_HEADER = re.compile(
    r"(?:^|\b)(?:код\w*|номер\w*|№|id|инн|унп|кпп|окпо|окато|огрн|бик|имнс|ид|сч[её]т\w*)\b",
    re.IGNORECASE,
)
_COMPACT_DERIV_AT = 16
_NON_ADDITIVE_HEADER = re.compile(
    r"(?:средн|ср\.|индекс|на\s+душу|рентаб|марж|темп|прирост|динамик|yoy|nps|ранг|место)",
    re.IGNORECASE,
)
_MD_SEP = re.compile(r"^\|?[\s\-:|]+\|?$")


def _fmt_num_ru(value: Decimal, *, signed: bool = False) -> str:
    """Format Decimal cleanly for Russian analytical summaries."""
    q = value.quantize(Decimal("0.1")) if value != value.to_integral_value() else value.to_integral_value()
    sign = "+" if signed and q > 0 else ("-" if q < 0 else "")
    abs_s = f"{abs(q)}"
    if "." in abs_s:
        whole, frac = abs_s.split(".", 1)
        frac = frac.rstrip("0")
    else:
        whole, frac = abs_s, ""
    chunks = []
    while len(whole) > 3:
        chunks.append(whole[-3:])
        whole = whole[:-3]
    chunks.append(whole)
    grouped = " ".join(reversed(chunks))
    return f"{sign}{grouped},{frac}" if frac else f"{sign}{grouped}"


def derivative_block(markdown: str) -> str:
    """Shares, ranks, totals, group rollups, and Fact-vs-Plan deltas from tables.

    One decimal. The tenths are handed out so a column sums to 100%.
    Total/subtotal rows and year/code columns stay out of sums.
    """
    blocks: list[str] = []
    for title, rows in _markdown_tables(markdown):
        lines = _column_shares(rows)
        if not lines:
            continue
        if title and title not in {"Таблица PDF", "Экран"}:
            blocks.append(title)
        blocks.extend(lines)
        blocks.append("")
    if not blocks:
        return ""
    head = "Доли, суммы и отклонения посчитаны из ячеек. Копируй их как здесь."
    return head + "\n\n" + "\n".join(blocks).rstrip() + "\n"


def _markdown_tables(markdown: str) -> list[tuple[str, list[list[str]]]]:
    lines = (markdown or "").splitlines()
    found: list[tuple[str, list[list[str]]]] = []
    title = ""
    index = 0
    while index < len(lines):
        stripped = lines[index].strip()
        if stripped.startswith("## "):
            title = stripped[3:].strip()
            index += 1
            continue
        if _looks_like_table(lines, index):
            rows: list[list[str]] = []
            while index < len(lines) and lines[index].strip().startswith("|"):
                row = lines[index].strip()
                index += 1
                if _MD_SEP.match(row) and "-" in row:
                    continue
                inner = row[1:] if row.startswith("|") else row
                if inner.endswith("|") and not inner.endswith(r"\|"):
                    inner = inner[:-1]
                cells = [
                    cell.strip().replace(r"\|", "|")
                    for cell in re.split(r"(?<!\\)\|", inner)
                ]
                rows.append(cells)
            if len(rows) >= 2:
                found.append((title, rows))
            continue
        index += 1
    return found


def _looks_like_table(lines: list[str], index: int) -> bool:
    if not lines[index].strip().startswith("|"):
        return False
    nxt = index + 1
    while nxt < len(lines) and not lines[nxt].strip():
        nxt += 1
    if nxt >= len(lines):
        return False
    sep = lines[nxt].strip()
    return bool(_MD_SEP.match(sep) and "-" in sep)


def _group_columns(rows: list[list[str]], label_at: int) -> list[int]:
    """Text columns distinct from label_at that repeat or have merged blanks."""
    width = max(len(row) for row in rows)
    groups: list[int] = []
    for col in range(width):
        if col == label_at:
            continue
        cells = [row[col].strip() if col < len(row) else "" for row in rows]
        filled = [c for c in cells if c]
        if not filled:
            continue
        text = sum(1 for c in filled if _cell_decimal(c) is None)
        if text * 2 < len(filled):
            continue
        uniq = len(set(filled))
        if len(filled) >= 2 and 2 <= uniq and (uniq < len(filled) or len(filled) < len(rows)):
            groups.append(col)
        elif col < label_at and uniq == 1 and len(filled) < len(rows):
            groups.append(col)
    return groups


def _ffill_groups(rows: list[list[str]], group_cols: list[int]) -> list[list[str]]:
    """Forward-fill empty cells in merged group columns."""
    if not group_cols:
        return rows
    out = [list(row) for row in rows]
    for col in group_cols:
        current = ""
        for row in out:
            if col >= len(row):
                continue
            val = row[col].strip()
            if val:
                current = val
            elif current:
                row[col] = current
    return out


def _find_fact_plan_pair(header: list[str]) -> tuple[int, int] | None:
    fact_col = None
    plan_col = None
    for idx, raw in enumerate(header):
        low = (raw or "").strip().casefold()
        if not low or "%" in low or "выполн" in low or "откл" in low or "доля" in low:
            continue
        if fact_col is None and re.search(r"\bфакт\b", low):
            fact_col = idx
        elif plan_col is None and re.search(r"\bплан\b", low):
            plan_col = idx
    if fact_col is not None and plan_col is not None and fact_col != plan_col:
        return fact_col, plan_col
    return None


def _column_shares(rows: list[list[str]]) -> list[str]:
    header, body = rows[0], rows[1:]
    data = [row for row in body if not _is_total_row(row)]
    if len(data) < 2:
        return []
    label_at = _label_column(data)
    if label_at is None:
        return []
    width = max(len(row) for row in rows)
    lines: list[str] = []
    group_cols = _group_columns(data, label_at)
    data = _ffill_groups(data, group_cols)
    compact = len(data) > _COMPACT_DERIV_AT

    for col in range(width):
        if col == label_at:
            continue
        name = header[col].strip() if col < len(header) else ""
        if not name or _YEAR_HEADER.match(name) or _CODE_HEADER.search(name):
            continue
        parsed = _measure_column(data, col, label_at)
        if parsed is None:
            continue
        labels, values, is_pct, has_neg, row_indices = parsed
        ranks = _ranks(values)
        heading = "Позиции (%)" if is_pct and "дол" in name.casefold() else name
        lines.append(heading)
        non_additive = is_pct or bool(_NON_ADDITIVE_HEADER.search(name))
        shares = _share_tenths(values) if (not non_additive and not has_neg) else []
        if not compact:
            if shares:
                for label, tenths, rank in zip(labels, shares, ranks):
                    lines.append(f"- {label} — доля {_fmt_share(tenths)}, место {rank}")
            else:
                for label, rank in zip(labels, ranks):
                    lines.append(f"- {label} — место {rank}")
        else:
            unit_sfx = "%" if is_pct else ""
            top_n = 10 if len(values) > 20 else 5
            top_idx = sorted(range(len(values)), key=lambda i: (-values[i], i))[:top_n]
            bot_idx = sorted(range(len(values)), key=lambda i: (values[i], i))[:top_n]

            def _fmt_item(idx: int) -> str:
                v_s = f"{_fmt_num_ru(values[idx])}{unit_sfx}"
                if shares:
                    return f"{labels[idx]} — {v_s} (доля {_fmt_share(shares[idx])}, место {ranks[idx]})"
                return f"{labels[idx]} — {v_s} (место {ranks[idx]})"

            lines.append(f"Топ-{top_n}: " + "; ".join(_fmt_item(i) for i in top_idx))
            lines.append(f"Отстающие (мин-{top_n}): " + "; ".join(_fmt_item(i) for i in bot_idx))
            if shares:
                top3_t = sum(shares[i] for i in top_idx[:3])
                top5_t = sum(shares[i] for i in top_idx[:5])
                lines.append(
                    f"Концентрация: Топ-3 — {_fmt_share(top3_t)}, Топ-5 — {_fmt_share(top5_t)}"
                )

        total = sum(values, Decimal(0))
        mean = total / Decimal(len(values))
        max_idx = max(range(len(values)), key=lambda i: values[i])
        min_idx = min(range(len(values)), key=lambda i: values[i])
        if not is_pct and not bool(_NON_ADDITIVE_HEADER.search(name)):
            lines.append(
                f"Сумма по строкам: {_fmt_num_ru(total)}; среднее: {_fmt_num_ru(mean)}; "
                f"макс: {_fmt_num_ru(values[max_idx])} ({labels[max_idx]}); "
                f"мин: {_fmt_num_ru(values[min_idx])} ({labels[min_idx]})"
            )
        else:
            lines.append(
                f"Среднее: {_fmt_num_ru(mean)}; "
                f"макс: {_fmt_num_ru(values[max_idx])} ({labels[max_idx]}); "
                f"мин: {_fmt_num_ru(values[min_idx])} ({labels[min_idx]})"
            )

        if not non_additive and group_cols:
            for gcol in group_cols[:2]:
                gname = header[gcol].strip() if gcol < len(header) else "Группа"
                by_group: dict[str, Decimal] = {}
                for r_idx, val in zip(row_indices, values):
                    gval = data[r_idx][gcol].strip() if gcol < len(data[r_idx]) else ""
                    if gval:
                        by_group[gval] = by_group.get(gval, Decimal(0)) + val
                if len(by_group) >= 2:
                    g_items = sorted(by_group.items(), key=lambda kv: -kv[1])
                    g_shares = _share_tenths([v for _, v in g_items]) if not has_neg and total > 0 else []
                    parts = []
                    for idx_g, (gk, gv) in enumerate(g_items):
                        if g_shares:
                            parts.append(f"{gk}: {_fmt_num_ru(gv)} ({_fmt_share(g_shares[idx_g])})")
                        else:
                            parts.append(f"{gk}: {_fmt_num_ru(gv)}")
                    lines.append(f"По «{gname}»: " + "; ".join(parts))
        lines.append("")

    pair = _find_fact_plan_pair(header)
    if pair is not None:
        fcol, pcol = pair
        paired: list[tuple[str, str, Decimal, Decimal]] = []
        gcol_fp = group_cols[0] if group_cols else None
        for idx, row in enumerate(data):
            f_val = _cell_decimal(row[fcol].strip()) if fcol < len(row) else None
            p_val = _cell_decimal(row[pcol].strip()) if pcol < len(row) else None
            if f_val is None or p_val is None:
                continue
            lbl = (row[label_at].strip() if label_at < len(row) else "") or f"строка {idx + 1}"
            gkey = (row[gcol_fp].strip() if gcol_fp is not None and gcol_fp < len(row) else "")
            paired.append((lbl, gkey, f_val, p_val))
        if paired:
            tot_f = sum((x[2] for x in paired), Decimal(0))
            tot_p = sum((x[3] for x in paired), Decimal(0))
            tot_diff = tot_f - tot_p
            tot_pct = (tot_f * Decimal(100) / tot_p) if tot_p > 0 else None
            pct_s = f", вып. {_fmt_num_ru(tot_pct)}%" if tot_pct is not None else ""
            lines.append("Отклонение и выполнение (Факт − План, база 100%):")
            lines.append(
                f"Сводно: факт {_fmt_num_ru(tot_f)} vs план {_fmt_num_ru(tot_p)}, "
                f"откл. {_fmt_num_ru(tot_diff, signed=True)}{pct_s}"
            )
            if gcol_fp is not None:
                gname_fp = header[gcol_fp].strip() if gcol_fp < len(header) else "Группа"
                g_fp: dict[str, tuple[Decimal, Decimal]] = {}
                for _lbl, gk, fv, pv in paired:
                    if not gk:
                        continue
                    prev_f, prev_p = g_fp.get(gk, (Decimal(0), Decimal(0)))
                    g_fp[gk] = (prev_f + fv, prev_p + pv)
                if len(g_fp) >= 2:
                    for gk, (gf, gp) in g_fp.items():
                        gdiff = gf - gp
                        gpct = (gf * Decimal(100) / gp) if gp > 0 else None
                        gpct_s = f", вып. {_fmt_num_ru(gpct)}%" if gpct is not None else ""
                        lines.append(
                            f"- По «{gname_fp}» ({gk}): факт {_fmt_num_ru(gf)} vs план {_fmt_num_ru(gp)}, "
                            f"откл. {_fmt_num_ru(gdiff, signed=True)}{gpct_s}"
                        )
            if not compact:
                for lbl, _gk, fv, pv in paired:
                    diff = fv - pv
                    rpct = (fv * Decimal(100) / pv) if pv > 0 else None
                    rpct_s = f", вып. {_fmt_num_ru(rpct)}%" if rpct is not None else ""
                    lines.append(f"- {lbl}: откл. {_fmt_num_ru(diff, signed=True)}{rpct_s}")
            else:
                above = sum(1 for _lbl, _gk, fv, pv in paired if fv >= pv)
                below = len(paired) - above
                lines.append(
                    f"Выше плана (>=100%): {above} из {len(paired)}; ниже плана: {below} из {len(paired)}"
                )
                top_surplus = sorted(paired, key=lambda x: (-(x[2] - x[3]), x[0]))[:5]
                bot_deficit = sorted(
                    paired,
                    key=lambda x: (
                        (x[2] / x[3]) if x[3] > 0 else Decimal(0),
                        x[2] - x[3],
                        x[0],
                    ),
                )[:5]

                def _fmt_fp(entry: tuple[str, str, Decimal, Decimal]) -> str:
                    lbl, _gk, fv, pv = entry
                    diff = fv - pv
                    rpct = (fv * Decimal(100) / pv) if pv > 0 else None
                    rpct_s = f", вып. {_fmt_num_ru(rpct)}%" if rpct is not None else ""
                    return f"{lbl} (откл. {_fmt_num_ru(diff, signed=True)}{rpct_s})"

                lines.append("Топ-5 по отклонению: " + "; ".join(_fmt_fp(e) for e in top_surplus))
                lines.append("Отстающие по выполнению: " + "; ".join(_fmt_fp(e) for e in bot_deficit))
            lines.append("")
    return lines


def _is_total_row(row: list[str]) -> bool:
    for cell in row:
        if _TOTAL_LABEL.search(cell.strip()):
            return True
    return False


def _label_column(rows: list[list[str]]) -> int | None:
    width = max(len(row) for row in rows)
    best: tuple[int, int] | None = None
    for col in range(width):
        cells = [row[col].strip() if col < len(row) else "" for row in rows]
        filled = [cell for cell in cells if cell]
        if not filled:
            continue
        text = sum(1 for cell in filled if _cell_decimal(cell) is None)
        if text * 2 < len(filled):
            continue
        uniq = len(set(filled))
        score = (uniq, -col)
        if best is None or score > best:
            best = score
    return -best[1] if best is not None else None


def _measure_column(
    rows: list[list[str]], col: int, label_at: int
) -> tuple[list[str], list[Decimal], bool, bool, list[int]] | None:
    labels: list[str] = []
    values: list[Decimal] = []
    raw: list[str] = []
    row_indices: list[int] = []
    for index, row in enumerate(rows):
        cell = row[col].strip() if col < len(row) else ""
        if not cell or cell in {"—", "-", "–", "н/д", "Н/Д"}:
            continue
        raw.append(cell)
        number = _cell_decimal(cell)
        if number is None:
            return None
        raw_label = row[label_at].strip() if label_at < len(row) else ""
        label = raw_label or f"строка {index + 1}"
        labels.append(label)
        values.append(number)
        row_indices.append(index)
    if len(values) < 2:
        return None
    if all(_is_year(value) for value in values):
        return None
    is_pct = any("%" in cell for cell in raw)
    has_neg = any(v < 0 for v in values)
    return labels, values, is_pct, has_neg, row_indices


def _cell_decimal(cell: str) -> Decimal | None:
    text = re.sub(r"^([+\-])\s+", r"\1", cell.strip().replace("−", "-"))
    if not _COMPLETE_NUM.match(text):
        return None
    # Strip trailing % or unit suffixes matched by _COMPLETE_NUM
    num_m = re.match(r"^([+\-]?(?:\d{1,3}(?:[ \u00a0\u202f]\d{3})+|\d+)(?:[.,]\d+)?)", text)
    if not num_m:
        return None
    compact = (
        num_m.group(1)
        .replace(" ", "")
        .replace("\u00a0", "")
        .replace("\u202f", "")
        .replace(",", ".")
    )
    try:
        return Decimal(compact)
    except InvalidOperation:
        return None


def _is_year(value: Decimal) -> bool:
    if value != value.to_integral_value():
        return False
    year = int(value)
    return 1900 <= year <= 2099


def _share_tenths(values: list[Decimal]) -> list[int]:
    total = sum(values, Decimal(0))
    if total <= 0:
        return []
    raw = [value * Decimal(1000) / total for value in values]
    floors = [int(piece) for piece in raw]
    left = 1000 - sum(floors)
    order = sorted(
        range(len(raw)),
        key=lambda index: (-(raw[index] - Decimal(floors[index])), index),
    )
    for index in order[:left]:
        floors[index] += 1
    return floors


def _ranks(values: list[Decimal]) -> list[int]:
    order = sorted(range(len(values)), key=lambda index: (-values[index], index))
    ranks = [0] * len(values)
    for place, index in enumerate(order):
        if place > 0 and values[index] == values[order[place - 1]]:
            ranks[index] = ranks[order[place - 1]]
        else:
            ranks[index] = place + 1
    return ranks


def _fmt_share(tenths: int) -> str:
    whole, frac = divmod(tenths, 10)
    if frac == 0:
        return f"{whole}%"
    return f"{whole},{frac}%"


def prefer_ruled_tables(
    line_rows: list[list[list[object | None]]],
    text_rows: list[list[list[object | None]]],
) -> list[list[list[object | None]]]:
    """Ruled lines win a noisy split of the same width.

    A text grid with more columns wins when the lines glued several
    headers into one cell. Stimulsoft does that on the numeric side.
    """
    line_nums = sum(_numeric_cells(table) for table in line_rows)
    text_nums = sum(_numeric_cells(table) for table in text_rows)
    if line_nums <= 0:
        return text_rows
    if text_nums <= 0:
        return line_rows
    if _width(text_rows) >= _width(line_rows) + 1 and _row_count(text_rows) >= max(
        2, _row_count(line_rows) // 2
    ):
        return text_rows
    return line_rows


def _width(tables: list[list[list[object | None]]]) -> int:
    return max((len(row) for table in tables for row in table), default=0)


def _row_count(tables: list[list[list[object | None]]]) -> int:
    return sum(len(table) for table in tables)


def _row_has_numbers(row: list[str]) -> bool:
    return any(_cell_decimal(cell) is not None for cell in row)


def _trim_trailing_blank_cols(rows: list[list[str]]) -> list[list[str]]:
    if not rows:
        return rows
    last_nonempty = 0
    for row in rows:
        for idx, cell in enumerate(row):
            if cell.strip():
                last_nonempty = max(last_nonempty, idx + 1)
    width = max(1, last_nonempty)
    return [row[:width] + [""] * max(0, width - len(row)) for row in rows]


def join_page_tables(
    pages: list[list[list[list[object | None]]]],
) -> list[list[list[str]]]:
    """Append a later page when its header repeats or it continues without a header."""
    joined: list[list[list[str]]] = []
    for page in pages:
        for raw in page:
            rows = _trim_trailing_blank_cols(_clean_rows(raw))
            if not rows:
                continue
            header, data = _header_and_body(rows)
            if joined:
                prev_w = len(joined[-1][0])
                cur_w = len(rows[0])
                prev_header, _prev_data = _header_and_body(joined[-1])
                if header and prev_header[:cur_w] == header[:prev_w] and abs(cur_w - prev_w) <= 1 and len(rows) >= 2:
                    padded = [r[:prev_w] + [""] * max(0, prev_w - len(r)) for r in data]
                    joined[-1].extend(padded)
                    continue
                if cur_w <= prev_w + 1 and (
                    len(rows) == 1 or _row_has_numbers(rows[0]) or _is_total_row(rows[0])
                ):
                    padded = [r[:prev_w] + [""] * max(0, prev_w - len(r)) for r in rows]
                    joined[-1].extend(padded)
                    continue
            if not header or len(rows) < 2:
                continue
            joined.append(rows)
    return joined


def _screen_markdown(
    png: bytes,
    vision: Callable[[bytes], str] | None,
    *,
    keep_table: bool,
) -> str:
    if len(png) > MAX_PNG_BYTES:
        raise DashboardSourceError(
            "Снимок больше 15 МБ. Сожмите PNG без сильного даунскейла.",
            code="too_large",
        )
    _check_png(png)
    if vision is None:
        return read_dashboard_png(png, keep_table=keep_table)
    try:
        text = vision(png)
    except DashboardSourceError:
        raise
    except Exception as exc:
        raise DashboardSourceError(
            f"Модель не прочитала снимок: {exc}",
            code="vision_failed",
        ) from exc
    cleaned = _finish_screen(text or "", keep_table=keep_table)
    if not cleaned.strip():
        raise DashboardSourceError(
            "Модель ничего не вернула по снимку дашборда.",
            code="empty_screen",
        )
    return cleaned


def _pdf_markdown(data: bytes) -> tuple[str, int, int, list[str]]:
    if len(data) > MAX_PDF_BYTES:
        raise DashboardSourceError(
            "PDF больше 20 МБ. Выгрузите таблицу отдельным файлом.",
            code="too_large",
        )
    if not data.startswith(b"%PDF"):
        raise DashboardSourceError(
            "Это не PDF. Для таблицы нужен цифровой PDF.",
            code="bad_pdf",
        )
    path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            tmp.write(data)
            path = Path(tmp.name)
        triage = triage_pdf(path)
        if not triage.usable:
            raise DashboardSourceError(
                "В PDF нет текстового слоя. Нужен цифровой экспорт таблицы, не скан.",
                code="scan_pdf",
            )
        return _extract_pdf(path)
    finally:
        if path is not None:
            path.unlink(missing_ok=True)


def _extract_pdf(path: Path) -> tuple[str, int, int, list[str]]:
    try:
        import pdfplumber
    except ImportError as exc:
        raise DashboardSourceError(
            "Не установлен pdfplumber, таблицу PDF разобрать нельзя.",
            code="ingest_dependency",
        ) from exc

    page_tables: list[list[list[list[object | None]]]] = []
    loose: list[str] = []
    with pdfplumber.open(str(path)) as pdf:
        for index, page in enumerate(pdf.pages):
            tables, boxes = _page_tables(page)
            page_tables.append(tables)
            outside = _text_outside(page, boxes)
            if outside:
                loose.append(outside)
            log.info(
                "dashboard pdf page=%s tables=%s",
                index + 1,
                len(tables),
            )

    joined = join_page_tables(page_tables)
    blocks: list[str] = []
    notes: list[str] = []
    numeric = 0
    for rows in joined:
        block, note = table_block(rows)
        if block.strip():
            blocks.append(block.rstrip())
        if note:
            notes.append(note)
        numeric += _numeric_cells(rows)
    if blocks:
        parts = [text for text in loose if text]
        parts.extend(blocks)
        return "\n\n".join(parts).rstrip() + "\n", len(blocks), numeric, notes

    text = "\n\n".join(text for text in loose if text).strip()
    if not text:
        raise DashboardSourceError(
            "Из PDF не удалось извлечь текст.",
            code="empty_pdf",
        )
    notes.append("Таблица не разбилась на ячейки, оставлен текст страницы.")
    return text + "\n", 0, _numeric_in_text(text), notes


def choose_grids(
    line_rows: list[list[list[object | None]]],
    word_rows: list[list[list[object | None]]],
    text_rows: list[list[list[object | None]]],
) -> list[list[list[object | None]]]:
    """Prefer the grid that keeps a printed number whole.

    A Stimulsoft pivot often has no vertical rules. The text strategy then
    puts ``105`` and ``865,2`` in different columns. Word positions put them
    back. A real ruled grid still wins a tie.
    """
    best = line_rows
    best_score = _grid_score(line_rows)
    for candidate in (word_rows, text_rows):
        score = _grid_score(candidate)
        if score > best_score:
            best = candidate
            best_score = score
    return best


def words_to_rows(words: list[dict[str, object]]) -> list[list[str]]:
    """One grid from word boxes. A short gap is a space inside a cell."""
    if not words:
        return []
    lines = _word_lines(words)
    cell_lines = [_join_word_gaps(line) for line in lines]
    body = [
        cells
        for cells in cell_lines
        if any(_COMPLETE_NUM.fullmatch(cell["text"]) for cell in cells)
    ]
    if not body:
        return []
    edges = _column_edges(body)
    if len(edges) < 3:
        return []
    assigned = [_assign_cells(cells, edges) for cells in cell_lines]
    tops = [float(line[0]["top"]) for line in lines]
    return _clean_rows(_merge_wrapped(assigned, tops))


def _page_tables(page: object) -> tuple[list[list[list[object | None]]], list[tuple[float, float, float, float]]]:
    line_rows, line_boxes = _tables_for(page, _LINE_SETTINGS)
    word_rows, word_boxes = _word_tables(page)
    text_rows, text_boxes = _tables_for(page, _TEXT_SETTINGS)
    chosen = choose_grids(line_rows, word_rows, text_rows)
    if chosen is word_rows:
        return word_rows, word_boxes
    if chosen is text_rows:
        return text_rows, text_boxes
    return line_rows, line_boxes


def _word_tables(
    page: object,
) -> tuple[list[list[list[str]]], list[tuple[float, float, float, float]]]:
    words = page.extract_words(x_tolerance=1, y_tolerance=1) or []  # type: ignore[attr-defined]
    rows = words_to_rows(words)
    if not _plausible(rows):
        return [], []
    return [rows], [_word_bbox(words)]


def _grid_score(tables: list[list[list[object | None]]]) -> int:
    if not tables:
        return -10_000
    complete = glued = splits = 0
    for table in tables:
        for row in table:
            cells = [_clean_cell(cell) for cell in row]
            for index, cell in enumerate(cells):
                if not cell:
                    continue
                if _COMPLETE_NUM.fullmatch(cell):
                    complete += 1
                if len(_NUM_TOKEN.findall(cell)) >= 2:
                    glued += 1
                nxt = cells[index + 1] if index + 1 < len(cells) else ""
                if _SHORT_NUM.fullmatch(cell) and _THOUSANDS_TAIL.fullmatch(nxt):
                    splits += 1
    return complete - 4 * glued - 4 * splits


def _word_lines(words: list[dict[str, object]]) -> list[list[dict[str, object]]]:
    ordered = sorted(words, key=lambda word: (float(word["top"]), float(word["x0"])))
    lines: list[list[dict[str, object]]] = []
    for word in ordered:
        if lines and abs(float(word["top"]) - float(lines[-1][0]["top"])) <= _LINE_BAND:
            lines[-1].append(word)
        else:
            lines.append([word])
    return lines


def _join_word_gaps(words: list[dict[str, object]]) -> list[dict[str, float | str]]:
    cells: list[dict[str, float | str]] = []
    for word in sorted(words, key=lambda item: float(item["x0"])):
        text = str(word["text"])
        x0 = float(word["x0"])
        x1 = float(word["x1"])
        if cells and x0 - float(cells[-1]["x1"]) < _WORD_GAP:
            cells[-1]["text"] = str(cells[-1]["text"]) + " " + text
            cells[-1]["x1"] = max(float(cells[-1]["x1"]), x1)
            continue
        cells.append({"text": text, "x0": x0, "x1": x1})
    return cells


def _column_edges(body: list[list[dict[str, float | str]]]) -> list[float]:
    cells = [cell for line in body for cell in line]
    parent = list(range(len(cells)))

    def find(index: int) -> int:
        while parent[index] != index:
            parent[index] = parent[parent[index]]
            index = parent[index]
        return index

    for left in range(len(cells)):
        for right in range(left + 1, len(cells)):
            if _same_column(cells[left], cells[right]):
                parent[find(left)] = find(right)
    groups: dict[int, list[dict[str, float | str]]] = {}
    for index, cell in enumerate(cells):
        groups.setdefault(find(index), []).append(cell)
    columns = []
    for group in groups.values():
        columns.append(
            {
                "x0": min(float(cell["x0"]) for cell in group),
                "x1": max(float(cell["x1"]) for cell in group),
                "n": len(group),
                "numeric": sum(
                    1 for cell in group if _COMPLETE_NUM.fullmatch(str(cell["text"]))
                ),
            }
        )
    columns.sort(key=lambda column: column["x0"])
    edges = [columns[0]["x0"] - 1]
    for prev, column in zip(columns, columns[1:]):
        if column["numeric"] * 2 >= column["n"]:
            edges.append(prev["x1"] + 0.5)
        else:
            edges.append((prev["x1"] + column["x0"]) / 2)
    edges.append(columns[-1]["x1"] + 40)
    return edges


def _same_column(left: dict[str, float | str], right: dict[str, float | str]) -> bool:
    overlap = min(float(left["x1"]), float(right["x1"])) - max(
        float(left["x0"]), float(right["x0"])
    )
    if overlap > 0:
        return True
    return bool(
        _COMPLETE_NUM.fullmatch(str(left["text"]))
        and _COMPLETE_NUM.fullmatch(str(right["text"]))
        and abs(float(left["x1"]) - float(right["x1"])) <= _WORD_GAP
    )


def _assign_cells(cells: list[dict[str, float | str]], edges: list[float]) -> list[str]:
    row = [""] * (len(edges) - 1)
    for cell in cells:
        center = (float(cell["x0"]) + float(cell["x1"])) / 2
        index = len(edges) - 2
        for slot in range(len(edges) - 1):
            if edges[slot] <= center < edges[slot + 1]:
                index = slot
                break
        text = str(cell["text"])
        row[index] = f"{row[index]} {text}".strip() if row[index] else text
    return row


def _has_number(row: list[str]) -> bool:
    return any(_COMPLETE_NUM.fullmatch(cell) for cell in row if cell)


def _merge_wrapped(rows: list[list[str]], tops: list[float]) -> list[list[str]]:
    """Join a wrapped header with the line above it.

    The second line of «Выполнение / плана (%)» sits closer to the first
    header line than to the first sum. A full data row does not.
    """
    if not rows:
        return []
    first_num = next((index for index, row in enumerate(rows) if _has_number(row)), len(rows))
    diffs = [b - a for a, b in zip(tops, tops[1:]) if b > a]
    pitch = sorted(diffs)[len(diffs) // 2] if diffs else 999.0
    merged = [list(rows[0])]
    prev_top = tops[0]
    for index, (row, top) in enumerate(zip(rows[1:], tops[1:]), start=1):
        gap = top - prev_top
        prev_top = top
        if _has_number(row):
            merged.append(list(row))
            continue
        distance_to_data = (
            tops[first_num] - top if first_num < len(tops) else pitch
        )
        preamble = index < first_num and gap < distance_to_data
        if preamble or gap < pitch * 0.75:
            previous = merged[-1]
            for slot, cell in enumerate(row):
                if cell:
                    previous[slot] = (
                        f"{previous[slot]} {cell}".strip() if previous[slot] else cell
                    )
            continue
        merged.append(list(row))
    return merged


def _word_bbox(words: list[dict[str, object]]) -> tuple[float, float, float, float]:
    return (
        min(float(word["x0"]) for word in words),
        min(float(word["top"]) for word in words),
        max(float(word["x1"]) for word in words),
        max(float(word["bottom"]) for word in words),
    )


def _tables_for(
    page: object,
    settings: dict[str, object],
) -> tuple[list[list[list[object | None]]], list[tuple[float, float, float, float]]]:
    found = page.find_tables(settings) or []  # type: ignore[attr-defined]
    rows: list[list[list[object | None]]] = []
    boxes: list[tuple[float, float, float, float]] = []
    for table in found:
        extracted = table.extract()
        if not extracted or not _plausible(extracted):
            continue
        rows.append(extracted)
        bbox = getattr(table, "bbox", None)
        if bbox:
            boxes.append(tuple(bbox))  # type: ignore[arg-type]
    return rows, boxes


def _plausible(rows: list[list[object | None]]) -> bool:
    if len(rows) < 2:
        return False
    width = max((len(row) for row in rows), default=0)
    if width < 2:
        return False
    nonempty = [
        _clean_cell(cell)
        for row in rows
        for cell in row
        if _clean_cell(cell)
    ]
    if len(nonempty) < 4:
        return False
    return sum(1 for cell in nonempty if _NUM.search(cell)) >= 2


def _text_outside(
    page: object,
    boxes: list[tuple[float, float, float, float]],
) -> str:
    def _outside(obj: dict) -> bool:
        x0 = float(obj.get("x0", 0))
        x1 = float(obj.get("x1", x0))
        top = float(obj.get("top", 0))
        bottom = float(obj.get("bottom", top))
        cx, cy = (x0 + x1) / 2, (top + bottom) / 2
        for left, upper, right, lower in boxes:
            if left <= cx <= right and upper <= cy <= lower:
                return False
        return True

    filtered = page.filter(_outside) if boxes else page  # type: ignore[attr-defined]
    text = (filtered.extract_text() or "").strip()
    return "\n".join(line.rstrip() for line in text.splitlines() if line.strip())


def _header_and_body(rows: list[list[str]]) -> tuple[list[str], list[list[str]]]:
    if not rows:
        return [], []
    body = rows[1:] if _is_span_title(rows[0]) else list(rows)
    if not body:
        return [], []
    return list(body[0]), [list(row) for row in body[1:]]


def _is_span_title(row: list[str]) -> bool:
    return len(row) >= 2 and len([cell for cell in row if cell]) == 1


def _clean_rows(rows: list[list[object | None]]) -> list[list[str]]:
    if not rows:
        return []
    width = max(len(row) for row in rows)
    cleaned: list[list[str]] = []
    for row in rows:
        cells = [_clean_cell(cell) for cell in row]
        if len(cells) < width:
            cells.extend([""] * (width - len(cells)))
        else:
            cells = cells[:width]
        if any(cells):
            cleaned.append(cells)
    return cleaned


def _clean_cell(value: object) -> str:
    if value is None:
        return ""
    text = str(value).replace("\r", " ").replace("\n", " ").replace("|", "\\|")
    return " ".join(text.split())


def _numeric_cells(rows: list[list[object]]) -> int:
    return sum(1 for row in rows for cell in row if _NUM.search(_clean_cell(cell)))


def _numeric_in_text(text: str) -> int:
    return len(re.findall(r"\d+(?:[ \u00a0]\d{3})*(?:[.,]\d+)?%?", text))


_MONTH_STEMS: tuple[tuple[int, str, str], ...] = (
    (0, "январ", "январь"),
    (1, "феврал", "февраль"),
    (2, "март", "март"),
    (3, "апрел", "апрель"),
    (4, "мая", "май"),
    (4, "май", "май"),
    (5, "июн", "июнь"),
    (6, "июл", "июль"),
    (7, "август", "август"),
    (8, "сентябр", "сентябрь"),
    (9, "октябр", "октябрь"),
    (10, "ноябр", "ноябрь"),
    (11, "декабр", "декабрь"),
)
_MONTH_WORD = (
    r"(?:январ|феврал|апрел|сентябр|октябр|ноябр|декабр|август|март|июн|июл|ма[йя])[а-яё]*"
)
_MONTH_RE = re.compile(_MONTH_WORD, re.IGNORECASE)
_AS_OF_RE = re.compile(rf"на\s+1\s+({_MONTH_WORD})", re.IGNORECASE)
_TITLE_MONTH_RE = re.compile(rf"поступлени\w*\s+за\s+({_MONTH_WORD})", re.IGNORECASE)
_ZA_MONTH_RE = re.compile(rf"(?<![а-яё])за\s+({_MONTH_WORD})", re.IGNORECASE)
_CLOSED_MARK = "закрывает предыдущий месяц"


class _MonthHit:
    def __init__(self, index: int, name: str, year: int | None, label: str) -> None:
        self.index = index
        self.name = name
        self.year = year
        self.label = label


_SKIP_HEADS = {
    "данные дашборда",
    "экран",
    "таблица pdf",
    "производные",
    "фильтры",
    "карточки",
    "график или карта",
    "заголовок",
}


def dashboard_title(markdown: str) -> str:
    """Short name from the screen heading, not the file stamp."""
    text = (markdown or "").replace("\r\n", "\n")
    found = re.search(
        r"^##[ \t]+Заголовок[ \t]*\n+([^\n#|][^\n]*)",
        text,
        re.MULTILINE | re.IGNORECASE,
    )
    raw = found.group(1).strip() if found else ""
    if not raw:
        for line in text.splitlines():
            head = re.match(r"^#{1,3}[ \t]+(.+?)\s*$", line.strip())
            if not head:
                continue
            title = head.group(1).strip()
            if title.casefold().replace("ё", "е") in _SKIP_HEADS:
                continue
            raw = title
            break
    return _clean_dashboard_title(raw)


def _clean_dashboard_title(raw: str) -> str:
    text = " ".join((raw or "").split())
    text = re.sub(r"\s*\([^)]*\)\s*$", "", text).strip()
    text = re.sub(r"[\\/:*?\"<>|]+", " ", text)
    text = " ".join(text.split())
    if len(text) > 72:
        text = text[:69].rstrip() + "…"
    return text


def note_closed_month(markdown: str, question: str = "") -> str:
    """Say that a February filter is the January receipts already on screen.

    This dashboard closes the previous month: «на 1 февраля» shows «за январь».
    The chat model was refusing that pair as the wrong period.
    """
    text = (markdown or "").strip()
    if not text or _CLOSED_MARK in text:
        return text
    title = _title_hit(text)
    if title is None:
        return text
    chosen = _filter_hit(text)
    if chosen is not None:
        if _is_closed_pair(title, chosen):
            return _closed_sentence(title, chosen) + "\n\n" + text
        return text
    asked = _question_hit(question)
    if asked is not None and _looks_like_receipts(text) and _is_closed_pair(title, asked):
        return _closed_sentence(title, asked) + "\n\n" + text
    return text


def _looks_like_receipts(text: str) -> bool:
    folded = text.casefold().replace("ё", "е")
    return "поступлен" in folded or "нарастающ" in folded


def _month_of(word: str) -> tuple[int, str] | None:
    folded = word.casefold().replace("ё", "е")
    for index, stem, name in _MONTH_STEMS:
        if folded.startswith(stem):
            return index, name
    return None


def _year_after(text: str, end: int) -> int | None:
    found = re.search(r"20\d\d", text[end : end + 24])
    if not found:
        return None
    return int(found.group(0))


def _lone_year(text: str) -> int | None:
    years = {int(item) for item in re.findall(r"20\d\d", text)}
    if len(years) == 1:
        return next(iter(years))
    return None


def _hit(word: str, text: str, end: int, label: str) -> _MonthHit | None:
    parsed = _month_of(word)
    if parsed is None:
        return None
    index, name = parsed
    return _MonthHit(index, name, _year_after(text, end), label)


def _hits(text: str) -> list[_MonthHit]:
    found: list[_MonthHit] = []
    for match in _MONTH_RE.finditer(text or ""):
        hit = _hit(match.group(0), text, match.end(), match.group(0))
        if hit is not None:
            found.append(hit)
    return found


def _filters_section(text: str) -> str:
    match = re.search(r"^##[ \t]+Фильтры[ \t]*$", text, re.MULTILINE | re.IGNORECASE)
    if not match:
        return ""
    rest = text[match.end() :]
    nxt = re.search(r"^##[ \t]+", rest, re.MULTILINE)
    return rest[: nxt.start()] if nxt else rest


def _before_filters(text: str) -> str:
    match = re.search(r"^##[ \t]+Фильтры[ \t]*$", text, re.MULTILINE | re.IGNORECASE)
    if match:
        return text[: match.start()]
    return text[:1200]


def _title_hit(text: str) -> _MonthHit | None:
    match = _TITLE_MONTH_RE.search(text)
    if match:
        return _hit(match.group(1), text, match.end(), match.group(1))
    found = []
    for item in _ZA_MONTH_RE.finditer(_before_filters(text)):
        hit = _hit(item.group(1), text, item.end(), item.group(1))
        if hit is not None:
            found.append(hit)
    indexes = {item.index for item in found}
    if len(indexes) != 1:
        return None
    return found[0]


def _with_section_year(hit: _MonthHit, section: str, label: str) -> _MonthHit:
    year = hit.year if hit.year is not None else _lone_year(section)
    shown = label
    if year is not None and str(year) not in shown:
        shown = f"{shown} {year}"
    return _MonthHit(hit.index, hit.name, year, shown)


def _filter_hit(text: str) -> _MonthHit | None:
    section = _filters_section(text)
    if not section:
        return None
    as_of = _AS_OF_RE.search(section)
    if as_of:
        hit = _hit(as_of.group(1), section, as_of.end(), as_of.group(0))
        if hit is None:
            return None
        return _with_section_year(hit, section, as_of.group(0))
    found = _hits(section)
    indexes = {item.index for item in found}
    if len(indexes) != 1:
        return None
    hit = found[0]
    return _with_section_year(hit, section, hit.name)


def _question_hit(question: str) -> _MonthHit | None:
    found = _hits(question or "")
    indexes = {item.index for item in found}
    if len(indexes) != 1:
        return None
    years = {item.year for item in found if item.year is not None}
    if len(years) > 1:
        return None
    hit = found[0]
    year = next(iter(years)) if years else hit.year
    label = hit.name if year is None else f"{hit.name} {year}"
    return _MonthHit(hit.index, hit.name, year, label)


def _is_closed_pair(title: _MonthHit, chosen: _MonthHit) -> bool:
    if chosen.index != (title.index + 1) % 12:
        return False
    if title.year is None or chosen.year is None:
        return True
    if title.index == 11 and chosen.index == 0:
        return chosen.year == title.year + 1
    return chosen.year == title.year


def _closed_sentence(title: _MonthHit, chosen: _MonthHit) -> str:
    shown = title.name if title.year is None else f"{title.name} {title.year}"
    return (
        f"Фильтр «{chosen.label}» закрывает предыдущий месяц. "
        f"Поступления за {shown} в этом тексте — это данные того фильтра. "
        f"Разбирай эти числа."
    )


def _finish_screen(text: str, *, keep_table: bool) -> str:
    """A lone screenshot keeps its grid. Beside a PDF the grid is the PDF's."""
    stripped = _strip_fence(text)
    body = stripped.strip() if keep_table else strip_screen_table(stripped)
    if not body:
        return ""
    return note_closed_month(body)


def strip_screen_table(markdown: str) -> str:
    """Drop the green pivot if the screen model copied it.

    Cards and the filter table stay: they have at most four columns.
    A wider grid is the payment table, and that text comes from the PDF.
    """
    lines = markdown.replace("\r\n", "\n").split("\n")
    kept: list[str] = []
    skipping = False
    index = 0
    while index < len(lines):
        line = lines[index]
        heading = re.match(r"^#{1,3}\s+(.+?)\s*$", line.strip())
        if heading and _screen_table_title(heading.group(1)):
            skipping = True
            index += 1
            continue
        if skipping:
            if heading:
                skipping = False
            else:
                index += 1
                continue
        if _pipe_row(line) and _pipe_width(line) > 4:
            while index < len(lines) and (
                _pipe_row(lines[index]) or not lines[index].strip()
            ):
                index += 1
            continue
        kept.append(line)
        index += 1
    return "\n".join(kept).strip()


def _screen_table_title(title: str) -> bool:
    folded = title.casefold().replace("ё", "е")
    return "таблиц" in folded and "экран" in folded


def _pipe_row(line: str) -> bool:
    stripped = line.strip()
    return stripped.startswith("|") and stripped.endswith("|") and stripped.count("|") >= 2


def _pipe_width(line: str) -> int:
    return len([cell for cell in line.strip().strip("|").split("|")])


def _strip_fence(text: str) -> str:
    stripped = text.strip()
    match = _FENCE.match(stripped)
    if match:
        return match.group(1).strip()
    return stripped


def _check_png(png: bytes) -> None:
    if not png.startswith(b"\x89PNG"):
        raise DashboardSourceError(
            "Снимок должен быть PNG.",
            code="bad_png",
        )


def _as_bytes(value: bytes | Path) -> bytes:
    if isinstance(value, (bytes, bytearray)):
        return bytes(value)
    path = Path(value)
    if not path.is_file():
        raise DashboardSourceError(
            f"Файл не найден: {path.name}",
            code="missing_file",
        )
    return path.read_bytes()


def _qwen_client() -> _VisionClient:
    from case3.llm_client import LLMClient, LLMConfig

    cfg = LLMConfig.from_env()
    cfg = replace(
        cfg,
        temperature=0.1,
        max_tokens=min(4096, int(cfg.max_tokens)),
        reasoning="off",
    )
    return LLMClient(cfg)
