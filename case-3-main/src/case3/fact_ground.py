"""Numbers in a new report or deck. Memory is not a source of them."""

from __future__ import annotations

import re
from typing import Any

from case3.chart_number import compact_chart_number_text, take_chart_number
from case3.chat_turn import _NUM, _norm_num, latest_user_line, number_norms, stray_numbers

_PROTECT = re.compile(
    r"\\includegraphics\s*(?:\[[^\]]*\])?\{[^}]*\}"
    r"|\\begin\{(?P<tbl>tabularx?\*?|xltabular|tabular\*?)\}[\s\S]*?\\end\{(?P=tbl)\}"
    r"|\\(?:begin|end)\{[^}]*\}(?:\s*\[[^\]]*\])?"
    r"|\\(?:label|ref|pageref|autoref|eqref|cite\w*)\{[^}]*\}"
    r"|(?<!\\)%[^\n]*"
    r"|\\(?:vspace|hspace|setlength|fontsize|rule)\{[^}]*\}(?:\{[^}]*\})?"
    r"|\\(?:multicolumn|multirow)\{[^}]*\}\{[^}]*\}"
    r"|\\(?:cmidrule|cline|hhline)\{[^}]*\}"
    r"|\\(?:rowcolor|cellcolor|color)\{[^}]*\}"
    r"|\\(?:href|url)\{[^}]*\}"
    r"|\\\\\[[^\]]*\]",
    re.IGNORECASE,
)
_JS_ARRAY = re.compile(
    r"(data|labels)\s*:\s*\[([^\]]*)\]",
    re.IGNORECASE,
)
_QUOTED = re.compile(r"(['\"])([^'\"]*)\1")


def fact_context(source: str, intent: str) -> tuple[set[str], list[tuple[str, str]]]:
    """Norms that may stand anywhere, and (norm, stem) pairs from earlier user lines."""
    from case3.chat_memory import _stem
    from case3.chat_turn import latest_user_line, number_norms

    message = latest_user_line(intent)
    global_ok = number_norms(source) | number_norms(message)
    bindings: list[tuple[str, str]] = []
    text = intent or ""
    mark = "Числа из реплик пользователя"
    at = text.find(mark)
    if at < 0:
        return global_ok, bindings
    rest = text[at + len(mark) :]
    body = rest.split("\n", 1)[1] if "\n" in rest else ""
    line = body.split("\n", 1)[0]
    for match in re.finditer(
        rf"({_NUM.pattern})(?:\s+([0-9A-Za-zА-Яа-яЁё]{{3,}}))?",
        line,
    ):
        norm = _norm_num(match.group(1))
        raw = match.group(2) or ""
        stem = _stem(raw) if raw else ""
        if len(stem) < 4:
            stem = ""
        if norm:
            bindings.append((norm, stem))
    return global_ok, bindings


class TableGrid:
    """Row stem → numbers that belong on that row, split by column."""

    def __init__(self) -> None:
        self.rows: dict[str, set[str]] = {}
        self.values: dict[tuple[str, str], set[str]] = {}
        self.shares: dict[tuple[str, str], set[str]] = {}
        self.ranks: dict[tuple[str, str], set[str]] = {}
        self.columns: set[str] = set()
        self.aggregates: set[str] = set()
        self.column_sums: set[str] = set()
        self.row_shares: dict[str, set[str]] = {}
        self.share_values: set[str] = set()
        self.all_row_norms: set[str] = set()
        self.phrase_norms: list[tuple[re.Pattern[str], set[str]]] = []
        self.full_phrase_norms: list[tuple[re.Pattern[str], set[str], set[str]]] = []

    def add(
        self,
        bucket: dict[tuple[str, str], set[str]],
        row: str,
        col: str,
        norms: set[str],
    ) -> None:
        clean = {norm for norm in norms if norm}
        if not clean or not row:
            return
        expanded = set(clean)
        for n in clean:
            if n.startswith("-") and len(n) > 1:
                expanded.add(n[1:])
        self.all_row_norms.update(expanded)
        if col:
            bucket.setdefault((row, col), set()).update(expanded)
            self.columns.add(col)
        else:
            bucket.setdefault((row, ""), set()).update(expanded)
        if bucket is self.values:
            self.rows.setdefault(row, set()).update(expanded)


_GENERIC_ROW = frozenset(
    {
        "область",
        "област",
        "регион",
        "район",
        "итого",
        "итог",
        "всего",
        "всег",
        "total",
        "имнс",
        "инспекц",
        "инспекци",
        "отдел",
        "управлен",
        "управлени",
        "город",
        "республик",
        "комитет",
        "департамент",
        "филиал",
    }
)
_DERIV_LINE = re.compile(
    r"^[-*]\s+(.+?)\s+[—-]\s+доля\s+(\d[\d \u00a0.,]*%?)\s*,\s*место\s+(\d+)\s*$"
)
_FP_DERIV_LINE = re.compile(
    r"^[-*]\s+(.+?):\s+откл\.\s+([+\-−]?[\d \u00a0.,]+)(?:,\s*вып\.\s+([\d \u00a0.,]+%))?\s*$"
)


def _label_key(label: str) -> str:
    return " ".join(
        re.findall(r"[0-9a-zа-я]+", (label or "").casefold().replace("ё", "е"))
    )


def _name_stems(label: str) -> set[str]:
    from case3.chat_memory import _stem

    found: set[str] = set()
    for word in re.findall(r"[0-9A-Za-zА-Яа-яЁё]{3,}", label or ""):
        if len(word) < 4 and not word.isupper():
            continue
        stem = _stem(word)
        if (len(stem) < 4 and not word.isupper()) or stem in _GENERIC_ROW:
            continue
        found.add(stem)
    return found


def table_grid(source: str) -> TableGrid:
    """One cell stays on its row and its column. Group rollups and all rows' derivatives are included."""
    from decimal import Decimal

    from case3.dashboard_source import (
        _CODE_HEADER,
        _NON_ADDITIVE_HEADER,
        _YEAR_HEADER,
        _cell_decimal,
        _ffill_groups,
        _find_fact_plan_pair,
        _fmt_num_ru,
        _fmt_share,
        _group_columns,
        _is_total_row,
        _label_column,
        _markdown_tables,
        _measure_column,
        _ranks,
        _share_tenths,
    )

    grid = TableGrid()
    row_entries: list[tuple[str, str, set[str], dict[str, set[str]]]] = []
    stem_labels: dict[str, set[str]] = {}
    for _title, rows in _markdown_tables(source or ""):
        if len(rows) < 2:
            continue
        header, body = rows[0], rows[1:]
        label_at = _label_column(body)
        width = max(len(row) for row in rows)
        col_stems: dict[int, str] = {}
        for col in range(width):
            if label_at is not None and col == label_at:
                continue
            name = header[col].strip() if col < len(header) else ""
            stems = _name_stems(name)
            if stems:
                col_stems[col] = max(stems, key=len)
        for row in body:
            label = row[label_at].strip() if label_at is not None and label_at < len(row) else ""
            text_parts: list[str] = []
            cells: dict[str, set[str]] = {}
            for col in range(width):
                cell = row[col].strip() if col < len(row) else ""
                if col == label_at:
                    if cell:
                        text_parts.append(cell)
                    continue
                norms = number_norms(cell)
                if not norms:
                    if cell and _cell_decimal(cell) is None:
                        text_parts.append(cell)
                    continue
                # «Май» is three letters, so it never becomes a column stem.
                # The number still belongs to the row.
                cells.setdefault(col_stems.get(col, ""), set()).update(norms)
            full_label = " ".join(text_parts) or label
            stems = _name_stems(full_label)
            lkey = _label_key(label or full_label)
            if lkey:
                for stem in stems:
                    stem_labels.setdefault(stem, set()).add(lkey)
            row_entries.append((label or full_label, lkey, stems, cells))

    phrase_map: dict[str, tuple[str, set[str]]] = {}
    all_phrase_map: dict[str, tuple[set[str], set[str]]] = {}
    for raw_label, lkey, stems, cells in row_entries:
        unique = {stem for stem in stems if len(stem_labels.get(stem, set())) == 1}
        keys = unique or stems
        row_all_norms: set[str] = set()
        for norms in cells.values():
            row_all_norms.update(norms)
            for n in list(norms):
                if n.startswith("-") and len(n) > 1:
                    row_all_norms.add(n[1:])
        for key in keys:
            for col, norms in cells.items():
                grid.add(grid.values, key, col, norms)
        if lkey and row_all_norms and len(stem_labels) > 0 and not unique and stems:
            prev_raw, prev_norms = phrase_map.get(lkey, (raw_label, set()))
            phrase_map[lkey] = (prev_raw, prev_norms | row_all_norms)
        if lkey and row_all_norms and stems:
            prev_vals, prev_sh = all_phrase_map.get(lkey, (set(), set()))
            all_phrase_map[lkey] = (prev_vals | row_all_norms, prev_sh)
    for lkey, (raw_label, pnorms) in phrase_map.items():
        tokens = lkey.split()
        if len(tokens) >= 2:
            pat = re.compile(
                r"\b" + r"\s+".join(re.escape(t) for t in tokens) + r"\w*",
                re.IGNORECASE,
            )
            grid.phrase_norms.append((pat, pnorms))

    has_explicit_derivatives = "## Производные" in (source or "") or bool(
        re.search(r"(?:^|\n)[-*]\s+.+?[—-]\s+доля\s+\d", source or "")
    )

    # Deterministically populate all rows' shares, ranks, group rollups, and Fact-Plan deltas
    # directly from the parsed tables so compact mode (>16 rows) never drops rows 17..500.
    for _title, rows in _markdown_tables(source or ""):
        if len(rows) < 2:
            continue
        header, body = rows[0], rows[1:]
        data = [row for row in body if not _is_total_row(row)]
        if len(data) < 2:
            continue
        label_at = _label_column(data)
        if label_at is None:
            continue
        width = max(len(row) for row in rows)
        group_cols = _group_columns(data, label_at)
        data = _ffill_groups(data, group_cols)
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
            named_col = _name_stems(name)
            cstem = max(named_col, key=len) if named_col else ""
            non_additive = is_pct or bool(_NON_ADDITIVE_HEADER.search(name))
            shares = _share_tenths(values) if (not non_additive and not has_neg) else []
            if shares:
                for idx_r, lbl in enumerate(labels):
                    lkey_r = _label_key(lbl)
                    sh_norms = number_norms(_fmt_share(shares[idx_r]))
                    grid.share_values.update(sh_norms)
                    for rstem in _name_stems(lbl):
                        grid.row_shares.setdefault(rstem, set()).update(sh_norms)
                    if lkey_r in all_phrase_map:
                        pv, ps = all_phrase_map[lkey_r]
                        all_phrase_map[lkey_r] = (pv, ps | sh_norms)
            if has_explicit_derivatives:
                for idx_r, lbl in enumerate(labels):
                    lkey_r = _label_key(lbl)
                    stems_r = _name_stems(lbl)
                    unique_r = {s for s in stems_r if len(stem_labels.get(s, set())) == 1}
                    keys_r = unique_r or stems_r
                    for rstem in keys_r:
                        if rstem not in grid.rows:
                            continue
                        grid.add(grid.ranks, rstem, cstem, {str(ranks[idx_r])})
                        if shares:
                            grid.add(grid.shares, rstem, cstem, number_norms(_fmt_share(shares[idx_r])))
                    if not unique_r and lkey_r in phrase_map and shares:
                        pr, pn = phrase_map[lkey_r]
                        phrase_map[lkey_r] = (pr, pn | number_norms(_fmt_share(shares[idx_r])))
            total = sum(values, Decimal(0))
            mean = total / Decimal(len(values))
            grid.column_sums.update(number_norms(_fmt_num_ru(total)))
            if has_explicit_derivatives:
                grid.aggregates.update(number_norms(_fmt_num_ru(total)))
                grid.aggregates.update(number_norms(_fmt_num_ru(mean)))
            if not non_additive and group_cols:
                for gcol in group_cols[:2]:
                    by_group: dict[str, Decimal] = {}
                    for r_idx, val in zip(row_indices, values):
                        gval = data[r_idx][gcol].strip() if gcol < len(data[r_idx]) else ""
                        if gval:
                            by_group[gval] = by_group.get(gval, Decimal(0)) + val
                    if len(by_group) >= 2:
                        g_items = sorted(by_group.items(), key=lambda kv: -kv[1])
                        g_shares = _share_tenths([v for _, v in g_items]) if not has_neg and total > 0 else []
                        for idx_g, (gk, gv) in enumerate(g_items):
                            gv_norms = number_norms(_fmt_num_ru(gv))
                            grid.aggregates.update(gv_norms)
                            for gstem in _name_stems(gk):
                                grid.add(grid.values, gstem, cstem, gv_norms)
                                if g_shares:
                                    gs_norms = number_norms(_fmt_share(g_shares[idx_g]))
                                    grid.add(grid.shares, gstem, cstem, gs_norms)
                                    grid.aggregates.update(gs_norms)
        pair = _find_fact_plan_pair(header)
        if pair is not None:
            fcol, pcol = pair
            gcol_fp = group_cols[0] if group_cols else None
            g_fp: dict[str, tuple[Decimal, Decimal]] = {}
            for idx_r, row in enumerate(data):
                fv = _cell_decimal(row[fcol].strip()) if fcol < len(row) else None
                pv = _cell_decimal(row[pcol].strip()) if pcol < len(row) else None
                if fv is None or pv is None:
                    continue
                lbl = (row[label_at].strip() if label_at < len(row) else "") or ""
                diff = fv - pv
                rpct = (fv * Decimal(100) / pv) if pv > 0 else None
                diff_norms = number_norms(_fmt_num_ru(diff, signed=True)) if has_explicit_derivatives else set()
                pct_norms = number_norms(_fmt_num_ru(rpct)) if rpct is not None else set()
                if pct_norms:
                    grid.share_values.update(pct_norms)
                    for rstem in _name_stems(lbl):
                        grid.row_shares.setdefault(rstem, set()).update(pct_norms)
                lkey_r = _label_key(lbl)
                if lkey_r in all_phrase_map and (diff_norms or pct_norms):
                    pv_set, ps_set = all_phrase_map[lkey_r]
                    all_phrase_map[lkey_r] = (pv_set | diff_norms, ps_set | pct_norms)
                stems_r = _name_stems(lbl)
                unique_r = {s for s in stems_r if len(stem_labels.get(s, set())) == 1}
                keys_r = unique_r or stems_r
                for rstem in keys_r:
                    if rstem in grid.rows:
                        if diff_norms:
                            grid.add(grid.values, rstem, "", diff_norms)
                        if pct_norms:
                            grid.add(grid.shares, rstem, "", pct_norms)
                if not unique_r and lkey_r in phrase_map:
                    pr, pn = phrase_map[lkey_r]
                    phrase_map[lkey_r] = (pr, pn | diff_norms | pct_norms)
                if gcol_fp is not None and gcol_fp < len(row):
                    gk = row[gcol_fp].strip()
                    if gk:
                        pf, pp = g_fp.get(gk, (Decimal(0), Decimal(0)))
                        g_fp[gk] = (pf + fv, pp + pv)
            for gk, (gf, gp) in g_fp.items():
                gdiff = gf - gp
                gpct = (gf * Decimal(100) / gp) if gp > 0 else None
                gd_norms = number_norms(_fmt_num_ru(gdiff, signed=True))
                gp_norms = number_norms(_fmt_num_ru(gpct)) if gpct is not None else set()
                grid.aggregates.update(gd_norms | gp_norms)
                for gstem in _name_stems(gk):
                    grid.add(grid.values, gstem, "", gd_norms | gp_norms)
                    if gp_norms:
                        grid.add(grid.shares, gstem, "", gp_norms)

    # Rebuild phrase_norms after adding row shares and Fact-Plan deltas
    grid.phrase_norms.clear()
    for lkey, (_raw_label, pnorms) in phrase_map.items():
        tokens = lkey.split()
        if len(tokens) >= 2:
            pat = re.compile(
                r"\b" + r"\s+".join(re.escape(t) for t in tokens) + r"\w*",
                re.IGNORECASE,
            )
            grid.phrase_norms.append((pat, pnorms))
    grid.full_phrase_norms.clear()
    for lkey, (pvals, pshares) in sorted(
        all_phrase_map.items(), key=lambda kv: -len(kv[0].split())
    ):
        tokens = lkey.split()
        if len(tokens) >= 2:
            pat = re.compile(
                r"(?<![0-9a-zа-я])"
                + r"[\s.,()\"«»-]+".join(re.escape(t) for t in tokens)
                + r"[0-9a-zа-я]*",
                re.IGNORECASE,
            )
            grid.full_phrase_norms.append((pat, pvals, pshares))

    # Also compute cross-table differences for the same entity (e.g., Feb cumulative minus Jan cumulative)
    tables_count = len(_markdown_tables(source or ""))
    if tables_count >= 2:
        for rstem, rnorms in list(grid.rows.items()):
            decs: list[Decimal] = []
            for n in rnorms:
                try:
                    decs.append(Decimal(n))
                except Exception:
                    continue
            if 2 <= len(decs) <= 24:
                cross_norms: set[str] = set()
                for i in range(len(decs)):
                    for j in range(i + 1, len(decs)):
                        a, b = decs[i], decs[j]
                        for diff_val in (a - b, b - a):
                            cross_norms.update(number_norms(_fmt_num_ru(diff_val, signed=True)))
                if cross_norms:
                    grid.add(grid.values, rstem, "", cross_norms)
        for idx_p, (pat, pnorms) in enumerate(list(grid.phrase_norms)):
            decs_p: list[Decimal] = []
            for n in pnorms:
                try:
                    decs_p.append(Decimal(n))
                except Exception:
                    continue
            if 2 <= len(decs_p) <= 24:
                cross_p: set[str] = set()
                for i in range(len(decs_p)):
                    for j in range(i + 1, len(decs_p)):
                        a, b = decs_p[i], decs_p[j]
                        for diff_val in (a - b, b - a):
                            cross_p.update(number_norms(_fmt_num_ru(diff_val, signed=True)))
                if cross_p:
                    grid.phrase_norms[idx_p] = (pat, pnorms | cross_p)

    _add_derivatives(grid, source or "")
    return grid


def _add_derivatives(grid: TableGrid, source: str) -> None:
    column = ""
    for raw in (source or "").splitlines():
        stripped = raw.strip()
        if not stripped or stripped.startswith("|") or stripped.startswith("#"):
            continue
        match = _DERIV_LINE.match(stripped)
        if match:
            label, share, rank = match.group(1), match.group(2), match.group(3)
            named = _name_stems(column)
            col = max(named, key=len) if named else ""
            for stem in _name_stems(label):
                if stem not in grid.rows:
                    continue
                grid.add(grid.shares, stem, col, number_norms(share))
                grid.add(grid.ranks, stem, col, number_norms(rank))
            continue
        fp_match = _FP_DERIV_LINE.match(stripped)
        if fp_match:
            label, diff = fp_match.group(1), fp_match.group(2)
            pct = fp_match.group(3) or ""
            for stem in _name_stems(label):
                if stem not in grid.rows:
                    continue
                grid.add(grid.values, stem, "", number_norms(diff))
                if pct:
                    grid.add(grid.values, stem, "", number_norms(pct))
                    grid.add(grid.shares, stem, "", number_norms(pct))
            continue
        if "Доли и места" in stripped:
            continue
        if stripped.startswith(
            (
                "Сумма по строкам:",
                "Среднее:",
                "По «",
                "Сводно:",
                "Отклонение и выполнение",
                "- По «",
                "Выше плана",
                "Концентрация:",
            )
        ):
            agg_part = stripped.split("; макс:", 1)[0].split("; мин:", 1)[0]
            grid.aggregates.update(number_norms(agg_part))
            continue
        if stripped.startswith(("Топ-5", "Топ-10", "Отстающие")):
            continue
        column = stripped


def _mentions_share(clause: str) -> bool:
    folded = (clause or "").casefold().replace("ё", "е")
    return "%" in (clause or "") or bool(re.search(r"\bдол[яеиюйь]", folded))


def _mentions_rank(clause: str) -> bool:
    folded = (clause or "").casefold().replace("ё", "е")
    return bool(re.search(r"\bмест[оаеу]?\b", folded))


def _row_mentions(clause: str, grid: TableGrid) -> list[tuple[int, int, str]]:
    from case3.chat_memory import _stem

    found: list[tuple[int, int, str]] = []
    for match in re.finditer(r"[0-9A-Za-zА-Яа-яЁё]{3,}", clause or ""):
        word = match.group(0)
        if len(word) < 4 and not word.isupper():
            continue
        stem = _stem(word)
        if (len(stem) < 4 and not word.isupper()) or stem not in grid.rows:
            continue
        found.append((match.start(), match.end(), stem))
    return found


def _inside_parens(text: str, pos: int) -> bool:
    before = text[:pos]
    return before.rfind("(") > before.rfind(")")


def _owner_rows(
    mentions: list[tuple[int, int, str]],
    start: int,
    clause: str = "",
    end: int | None = None,
) -> list[str]:
    """Candidate region names closest to this number (left and right if close)."""
    from case3.chat_turn import _ABBR_DOT

    num_end = end if end is not None else start
    owners: list[str] = []
    before = [item for item in mentions if item[1] <= start]
    if before:
        best = max(before, key=lambda item: item[1])
        if clause and _inside_parens(clause, best[0]):
            for item in reversed(before[:-1]):
                if _inside_parens(clause, item[0]):
                    continue
                gap = _ABBR_DOT.sub(r"\1", clause[item[1] : best[0]])
                if not re.search(r"[\d,;.]|\b(?:и|или|против|чем)\b", gap, re.IGNORECASE):
                    owners.append(item[2])
                    break
        if best[2] not in owners:
            owners.append(best[2])
    after = [item for item in mentions if item[0] >= num_end]
    if after:
        nearest_after = min(after, key=lambda item: item[0])
        if not owners:
            owners.append(nearest_after[2])
        elif clause:
            gap_right = clause[num_end : nearest_after[0]]
            # E.g. «при 10 790,0 у Пинского района» — number precedes its entity with no digit/semicolon in between
            if len(gap_right) <= 32 and not re.search(r"[\d;]", gap_right):
                if nearest_after[2] not in owners:
                    owners.append(nearest_after[2])
    return owners


def _owner_row(
    mentions: list[tuple[int, int, str]],
    start: int,
    clause: str = "",
) -> str | None:
    """The region name closest to this number. Parenthetical qualifiers defer to the entity outside."""
    owners = _owner_rows(mentions, start, clause)
    return owners[0] if owners else None


def _matched_full_phrase(
    clause: str, start: int, grid: TableGrid, share: bool
) -> set[str] | None:
    """If a full multi-word row label ends right before ``start``, return its scoped norms."""
    if not grid.full_phrase_norms or start <= 0:
        return None
    prefix = (clause[:start] or "").casefold().replace("ё", "е")
    best_end = -1
    best_norms: set[str] | None = None
    for pat, pvals, pshares in grid.full_phrase_norms:
        for m in pat.finditer(prefix):
            tail = prefix[m.end() :]
            # Only trivial punctuation/parens/words like "району" between label match and number
            if len(tail) > 16 or re.search(r"[\d,;.]|\b(?:и|или|против|чем)\b", tail):
                continue
            if m.end() > best_end:
                best_end = m.end()
                best_norms = set(pvals) | (set(pshares) if share else set())
    return best_norms


def _norms_on_row(
    grid: TableGrid,
    row: str,
    clause: str,
    columns: list[str],
    *,
    share_hint: bool = False,
) -> set[str]:
    share = share_hint or _mentions_share(clause)
    rank = _mentions_rank(clause)
    buckets = [grid.values]
    if share:
        buckets.append(grid.shares)
    if rank:
        buckets.append(grid.ranks)
    allowed: set[str] = set()
    # Any value cell on this row is valid even if prose casually names another column («перевыполнила план: 102,3%»).
    for (key, _col), norms in grid.values.items():
        if key == row:
            allowed |= norms
    for bucket in buckets[1:]:
        if columns:
            for col in columns:
                allowed |= bucket.get((row, col), set())
        else:
            for (key, _col), norms in bucket.items():
                if key == row:
                    allowed |= norms
    return allowed


def _row_allows(
    clause: str,
    norm: str,
    grid: TableGrid | None,
    *,
    table_share: bool = False,
) -> bool | None:
    """False when the sentence names a row and the number is not on it.

    Two region names in one sentence do not share a sum. A share is not a sum:
    ``52,9`` is allowed only where the sentence says «доля» or writes ``%``.
    """
    if grid is None or not grid.rows or not norm:
        return None
    if norm in grid.aggregates:
        return True
    mentions = _row_mentions(clause, grid)
    if not mentions:
        return None
    from case3.chat_memory import _stem_set

    columns = [stem for stem in _stem_set(clause) if stem in grid.columns]
    rows: list[str] = []
    for _start, _end, stem in mentions:
        if stem not in rows:
            rows.append(stem)
    spans = [
        (match.start(), match.end())
        for match in _NUM.finditer(clause)
        if _norm_num(match.group(0)) == norm
    ]
    share = table_share or _mentions_share(clause)
    if len(rows) > 1 and spans:
        for start, end in spans:
            full_norms = _matched_full_phrase(clause, start, grid, share)
            if full_norms is not None:
                if not _has_norm(full_norms, norm):
                    return False
                continue
            owners = _owner_rows(mentions, start, clause, end=end)
            if not owners or not any(
                _has_norm(_norms_on_row(grid, owner, clause, columns, share_hint=share), norm)
                for owner in owners
            ):
                # Also allow pairwise arithmetic (sum/diff/growth %) between the mentioned rows in this clause
                row_pool: set[str] = set()
                for rstem in rows:
                    row_pool |= grid.rows.get(rstem, set())
                if row_pool and _verifies_math(clause, norm, row_pool, row_pool):
                    continue
                return False
        return True
    if len(rows) > 1:
        if any(_has_norm(_norms_on_row(grid, row, clause, columns, share_hint=share), norm) for row in rows):
            return True
        row_pool = set()
        for rstem in rows:
            row_pool |= grid.rows.get(rstem, set())
        if row_pool and _verifies_math(clause, norm, row_pool, row_pool):
            return True
        return False
    if len(rows) == 1 and grid.phrase_norms:
        folded_clause = (clause or "").casefold().replace("ё", "е")
        for pat, pnorms in grid.phrase_norms:
            if pat.search(folded_clause):
                row_norms = _norms_on_row(grid, rows[0], clause, columns, share_hint=share)
                # Keep share/rank from _norms_on_row while scoping values to matched phrase.
                scoped = set(pnorms)
                for bucket in (grid.shares, grid.ranks):
                    for (k, _c), ns in bucket.items():
                        if k == rows[0]:
                            scoped |= ns
                return _has_norm(scoped & row_norms or pnorms, norm)
    return _has_norm(_norms_on_row(grid, rows[0], clause, columns, share_hint=share), norm)


def wrong_row_tokens(
    text: str | None,
    source: str | None,
    message: str | None = "",
) -> list[str]:
    """A number that exists, but on a different row from the one named here."""
    from case3.chat_turn import _ABBR_DOT, _is_list_marker

    grid = table_grid(source or "")
    if not grid.rows:
        return []
    message_ok = number_norms(message)
    source_ok = number_norms(source)
    msg_row_pool: set[str] = set()
    for _s, _e, rstem in _row_mentions(message or "", grid):
        msg_row_pool |= grid.rows.get(rstem, set())
    found: list[str] = []
    seen: set[str] = set()
    lines = (text or "").split("\n")
    active_header = ""
    for idx, line in enumerate(lines):
        stripped = line.strip()
        is_pipe = stripped.startswith("|") and stripped.endswith("|")
        if is_pipe and idx + 1 < len(lines) and re.match(r"^\s*\|[\s\-:|]+\|\s*$", lines[idx + 1]):
            active_header = stripped
        elif not is_pipe:
            active_header = ""
        table_share = bool(is_pipe and active_header and _mentions_share(active_header))
        protected = _ABBR_DOT.sub("\\1\x00", line)
        for chunk in re.split(r"[.!?]+", protected):
            chunk = chunk.replace("\x00", ".")
            chunk_row_pool = set(msg_row_pool)
            for _s, _e, rstem in _row_mentions(chunk, grid):
                chunk_row_pool |= grid.rows.get(rstem, set())
            for part in re.split(r",(?!\d)\s*", chunk):
                for match in _NUM.finditer(part):
                    if _is_list_marker(part, match.start(), match.end()):
                        continue
                    norm = _norm_num(match.group(0))
                    if not norm or norm in message_ok or norm in seen or norm not in source_ok:
                        continue
                    if _row_allows(part, norm, grid, table_share=table_share) is False:
                        if chunk_row_pool and _verifies_math(
                            chunk, norm, source_ok | message_ok | chunk_row_pool, chunk_row_pool
                        ):
                            continue
                        seen.add(norm)
                        found.append(match.group(0))
    return found


def _chart_labels(html: str) -> list[str]:
    """Category names in order. One labels array per chart."""
    match = re.search(r"labels\s*:\s*\[([^\]]*)\]", html or "", re.IGNORECASE)
    if not match:
        return []
    return [item.group(2) for item in _QUOTED.finditer(match.group(1))]


def _row_norms_for_label(label: str, grid: TableGrid | None) -> set[str] | None:
    """Numbers on the one table row this label names. None when it names none."""
    if grid is None or not grid.rows:
        return None
    hits = [stem for stem in _name_stems(label) if stem in grid.rows]
    if len(hits) != 1:
        return None
    return grid.rows[hits[0]]


def _rewrite_chart_body(kind: str, body: str, reject, slot_reject=None) -> str:
    """``[100,40]`` is two points. ``12,5`` is one point and is written with a dot."""
    empty = "null" if kind.lower() == "data" else "''"
    is_data = kind.lower() == "data"
    slot = 0
    text = compact_chart_number_text(body)
    parts: list[str] = []
    index = 0
    size = len(text)
    while index < size:
        if text[index : index + 4].lower() == "null" and (
            index == 0 or not text[index - 1].isalnum()
        ):
            parts.append("null")
            index += 4
            if is_data:
                slot += 1
            continue
        taken = take_chart_number(text, index)
        if taken:
            token, index = taken
            bad = reject(token)
            if not bad and is_data and slot_reject is not None:
                bad = slot_reject(token, slot)
            parts.append(empty if bad else token)
            if is_data:
                slot += 1
            continue
        parts.append(text[index])
        index += 1
    return f"{kind}: [{''.join(parts)}]"


_SMALL_COUNT_CLAUSE = re.compile(
    r"(?:\bтоп[-\s]?(\d{1,2})\b"
    r"|\b(\d{1,2})\s+(?:регион\w*|област\w*|район\w*|инспекц\w*|округ\w*|позиц\w*|строк\w*|категор\w*|город\w*|лидер\w*|аутсайдер\w*|квартал\w*|месяц\w*|полугоди\w*|этап\w*|уров\w*|групп\w*)"
    r"|\bна\s+(1)\s+(?:январ|феврал|март|апрел|ма[йя]|июн|июл|август|сентябр|октябр|ноябр|декабр)\w*"
    r"|(?:100)(?:\s*(?:%|\\\%))?)",
    re.IGNORECASE,
)


def _has_norm(pool: set[str], norm: str) -> bool:
    return bool(norm) and (
        norm in pool or (not norm.startswith("-") and f"-{norm}" in pool)
    )


def _is_small_cardinal_in_clause(clause: str, norm: str) -> bool:
    if norm == "100" and ("100%" in (clause or "") or "100\\%" in (clause or "")):
        return True
    if not norm.isdigit():
        return False
    val = int(norm)
    if not (1 <= val <= 50):
        return False
    for m in _SMALL_COUNT_CLAUSE.finditer(clause or ""):
        hit = m.group(1) or m.group(2) or m.group(3)
        if hit and int(hit) == val:
            return True
    return False


def _verifies_math(
    clause: str,
    norm: str,
    allowed_pool: set[str],
    extra_operands: set[str] | None = None,
) -> bool:
    """Allow arithmetic outputs derived directly from grounded operands."""
    from decimal import Decimal, InvalidOperation

    try:
        target = Decimal(norm)
    except InvalidOperation:
        return False
    clause_operands: list[Decimal] = []
    seen_op: set[str] = set()
    for match in _NUM.finditer(clause or ""):
        cand = _norm_num(match.group(0))
        if not cand or cand == norm or cand in seen_op:
            continue
        if _has_norm(allowed_pool, cand) or (extra_operands and cand in extra_operands):
            try:
                clause_operands.append(Decimal(cand))
                seen_op.add(cand)
            except InvalidOperation:
                continue
    pool_operands: list[Decimal] = list(clause_operands)
    for src_set in (extra_operands or set(),):
        for cand in sorted(src_set):
            if cand == norm or cand in seen_op:
                continue
            try:
                pool_operands.append(Decimal(cand))
                seen_op.add(cand)
            except InvalidOperation:
                continue
    if not pool_operands:
        return False

    tol = max(Decimal("0.15"), abs(target) * Decimal("0.005"))

    # 1. Unit scaling (thousands <-> millions)
    scale_match = re.search(
        r"(?:\bтыс\.?|\bтысяч|\bмлн\.?|\bмиллион|\bмлрд\.?|\bмиллиард)",
        clause or "",
        re.IGNORECASE,
    )
    if scale_match:
        has_big_scale = bool(
            re.search(
                r"(?:\bмлн\.?|\bмиллион|\bмлрд\.?|\bмиллиард)",
                clause or "",
                re.IGNORECASE,
            )
        )
        frac_len = len(norm.partition(".")[2]) if "." in norm else 0
        for val in pool_operands:
            if val == 0:
                continue
            for factor in (
                Decimal("1000"),
                Decimal("0.001"),
                Decimal("1000000"),
                Decimal("0.000001"),
            ):
                if factor < 1 and frac_len >= 3 and not has_big_scale:
                    continue
                if abs(val * factor - target) <= tol:
                    return True

    # 2. Multi-addend sum from grounded operands present in the sentence/clause or row_pool
    if len(clause_operands) >= 2:
        total = sum(clause_operands, Decimal(0))
        if abs(total - target) <= tol:
            return True

    if extra_operands and len(pool_operands) >= 2:
        # Pairwise and 3-addend combinations among grounded operands in sentence + extra (row / message)
        for i in range(len(pool_operands)):
            a = pool_operands[i]
            for j in range(i + 1, len(pool_operands)):
                b = pool_operands[j]
                cands = [a + b, a - b, b - a, abs(a - b)]
                if b != 0:
                    cands.extend([a * Decimal(100) / b, (a - b) * Decimal(100) / b])
                if a != 0:
                    cands.extend([b * Decimal(100) / a, (b - a) * Decimal(100) / a])
                for calc in cands:
                    if abs(calc - target) <= tol:
                        return True
        if 3 <= len(pool_operands) <= 24:
            for i in range(len(pool_operands)):
                a = pool_operands[i]
                for j in range(i + 1, len(pool_operands)):
                    ab = a + pool_operands[j]
                    for k in range(j + 1, len(pool_operands)):
                        if abs(ab + pool_operands[k] - target) <= tol:
                            return True
    elif len(clause_operands) >= 2:
        for i in range(len(clause_operands)):
            a = clause_operands[i]
            for j in range(i + 1, len(clause_operands)):
                b = clause_operands[j]
                cands = [a + b, a - b, b - a, abs(a - b)]
                if b != 0:
                    cands.extend([a * Decimal(100) / b, (a - b) * Decimal(100) / b])
                if a != 0:
                    cands.extend([b * Decimal(100) / a, (b - a) * Decimal(100) / a])
                for calc in cands:
                    if abs(calc - target) <= tol:
                        return True

    # 3. 2-step combinations over up to 10 operands (e.g. (fact + reserve) / plan * 100)
    ops = pool_operands[:10]
    if len(ops) >= 3:
        for i in range(len(ops)):
            a = ops[i]
            for j in range(i + 1, len(ops)):
                b = ops[j]
                mids = [a + b, a - b, b - a]
                if abs(a * b) <= Decimal("1e12"):
                    mids.append(a * b)
                if b != 0:
                    mids.append(a / b)
                if a != 0:
                    mids.append(b / a)
                for k in range(len(ops)):
                    if k == i or k == j:
                        continue
                    c = ops[k]
                    for mid in mids:
                        two_step = [mid + c, mid - c, c - mid]
                        if c != 0:
                            two_step.extend([mid * Decimal(100) / c, (mid - c) * Decimal(100) / c])
                        if mid != 0:
                            two_step.extend([c * Decimal(100) / mid, (c - mid) * Decimal(100) / mid])
                        for calc in two_step:
                            if abs(calc - target) <= tol:
                                return True
    return False


def _clause_allows(
    clause: str,
    norm: str,
    global_ok: set[str],
    bindings: list[tuple[str, str]],
    grid: TableGrid | None = None,
    message_ok: set[str] | None = None,
    extra_math_operands: set[str] | None = None,
) -> bool:
    if message_ok and _has_norm(message_ok, norm):
        return True
    if _is_small_cardinal_in_clause(clause, norm):
        return True
    metadata_ok = (
        (global_ok - grid.all_row_norms) | grid.aggregates
        if grid is not None and grid.rows
        else set()
    )
    if metadata_ok and _has_norm(metadata_ok, norm):
        return True
    on_row = _row_allows(clause, norm, grid)
    if on_row is not None:
        if on_row:
            return True
    elif _has_norm(global_ok, norm):
        return True
    from case3.chat_memory import _stem_set

    stems = _stem_set(clause)
    if any(bound == norm and stem and stem in stems for bound, stem in bindings):
        return True
    math_pool = set(global_ok) | (set(message_ok) if message_ok else set())
    row_pool: set[str] = set(extra_math_operands or set())
    if grid is not None and grid.rows:
        mentions = _row_mentions(clause, grid)
        for _s, _e, rstem in mentions:
            row_pool |= grid.rows.get(rstem, set())
    if message_ok:
        row_pool |= set(message_ok)
    if _verifies_math(clause, norm, math_pool, row_pool):
        return True
    return False


def _split_commas(chunk: str) -> list[str]:
    """Split on top-level commas outside TeX {...} groups and not inside decimals."""
    parts: list[str] = []
    start = 0
    depth = 0
    size = len(chunk)
    i = 0
    while i < size:
        ch = chunk[i]
        if ch == "\\" and i + 1 < size:
            i += 2
            continue
        if ch == "{":
            depth += 1
        elif ch == "}" and depth > 0:
            depth -= 1
        elif ch == "," and depth == 0:
            after = chunk[i + 1 : i + 2]
            if not after.isdigit():
                parts.append(chunk[start:i])
                j = i + 1
                while j < size and chunk[j].isspace():
                    j += 1
                start = j
                i = j
                continue
        i += 1
    parts.append(chunk[start:])
    return parts


def _balance_braces(text: str) -> str:
    """Close any unclosed TeX braces or drop unmatched closing braces."""
    out: list[str] = []
    depth = 0
    i = 0
    size = len(text)
    while i < size:
        ch = text[i]
        if ch == "\\" and i + 1 < size:
            out.append(text[i : i + 2])
            i += 2
            continue
        if ch == "{":
            depth += 1
            out.append(ch)
        elif ch == "}":
            if depth > 0:
                depth -= 1
                out.append(ch)
        else:
            out.append(ch)
        i += 1
    if depth > 0:
        out.append("}" * depth)
    return "".join(out)


def _scrub_bound(
    text: str,
    global_ok: set[str],
    bindings: list[tuple[str, str]],
    *,
    context: str = "",
    grid: TableGrid | None = None,
    message_ok: set[str] | None = None,
) -> str:
    """Drop a number that is not in Source, this message, or beside its own word."""
    from case3.chat_turn import _SPOKEN_NUMBER, _SPOKEN_RE

    raw_text = text or ""
    if not raw_text:
        return ""
    if not raw_text.strip():
        return raw_text
    lead_len = len(raw_text) - len(raw_text.lstrip())
    lead = raw_text[:lead_len]
    trail_start = len(raw_text.rstrip())
    trail = raw_text[trail_start:]
    core = raw_text[lead_len:trail_start]

    def spoken_norm(token: str) -> str:
        stem = token.casefold().replace("ё", "е")
        for prefix, digit in _SPOKEN_NUMBER:
            if stem.startswith(prefix):
                return digit
        return ""

    def clean_clause(clause: str, sentence_ok: set[str]) -> tuple[str, set[str]]:
        digits = [_norm_num(match.group(0)) for match in _NUM.finditer(clause)]
        words = [(match.group(0), spoken_norm(match.group(0))) for match in _SPOKEN_RE.finditer(clause)]
        norms = [norm for norm in digits + [digit for _word, digit in words] if norm]
        if not norms:
            return clause, set()
        judged = f"{context} {clause}".strip() if context else clause
        extra = set(sentence_ok)
        if message_ok:
            extra |= message_ok
        kept_here: set[str] = set()
        bad: set[str] = set()
        for norm in norms:
            if _clause_allows(
                judged,
                norm,
                global_ok,
                bindings,
                grid,
                message_ok,
                extra,
            ):
                kept_here.add(norm)
                extra.add(norm)
            else:
                bad.add(norm)
        if not bad:
            return clause, kept_here
        # One illegal number ruins the clause. Cutting it out leaves «в раза».
        return "", set()

    from case3.chat_turn import _ABBR_DOT

    kept_lines: list[str] = []
    for line in core.split("\n"):
        if not line.strip():
            if kept_lines and kept_lines[-1] != "":
                kept_lines.append("")
            continue
        protected_line = _ABBR_DOT.sub("\\1\x00", line)
        bits = re.split(r"([.!?]+(?:\s+|$))", protected_line)
        kept: list[str] = []
        index = 0
        while index < len(bits):
            chunk = bits[index].replace("\x00", ".")
            delim = bits[index + 1] if index + 1 < len(bits) else ""
            index += 2 if delim else 1
            parts = []
            cut = False
            sentence_ok: set[str] = set()
            for part in _split_commas(chunk):
                raw = part.strip()
                cleaned_raw, part_norms = clean_clause(part, sentence_ok)
                cleaned = cleaned_raw.strip()
                if not cleaned or re.fullmatch(r"[\s,.;:–—\-]+", cleaned):
                    if raw and (_NUM.search(raw) or _SPOKEN_RE.search(raw)):
                        cut = True
                    continue
                sentence_ok.update(part_norms)
                # «три месяца: март, апрель и май» leaves the lowercase tail.
                if cut and cleaned[:1].islower() and not _NUM.search(cleaned):
                    continue
                parts.append(cleaned)
            if not parts:
                continue
            kept.append(", ".join(parts))
            if delim:
                kept.append(delim)
        if kept:
            kept_lines.append(_balance_braces("".join(kept).strip()))
    while kept_lines and kept_lines[-1] == "":
        kept_lines.pop()
    result = "\n".join(kept_lines)
    result = re.sub(r"[ \t]{2,}", " ", result)
    result = re.sub(r" +([,.;:!?])", r"\1", result)
    result = re.sub(r"\n{3,}", "\n\n", result)
    if not result:
        return ""
    return f"{lead}{result}{trail}"


def allowed_fact_norms(source: str, intent: str) -> set[str]:
    """Source, this message, and numbers the user wrote earlier."""
    from case3.chat_turn import user_stated_norms

    return number_norms(source) | number_norms(latest_user_line(intent)) | user_stated_norms(intent)


def fact_number_tokens(source: str, intent: str) -> frozenset[str]:
    """Spellings a slide may repeat. ``12,5`` in Source allows ``12.5``."""
    tokens: set[str] = set()
    for norm in allowed_fact_norms(source, intent):
        if not norm:
            continue
        tokens.add(norm)
        tokens.add(norm.replace(".", ","))
        tokens.add(norm + "%")
    return frozenset(tokens)


def _has_stray(chunk: str, stray: set[str]) -> bool:
    return any(_norm_num(match.group(0)) in stray for match in _NUM.finditer(chunk))


def _has_kept(chunk: str, stray: set[str]) -> bool:
    return any(_norm_num(match.group(0)) not in stray for match in _NUM.finditer(chunk))


def _scrub_tokens(chunk: str, stray: set[str]) -> str:
    def repl(match: re.Match[str]) -> str:
        if _norm_num(match.group(0)) in stray:
            return ""
        return match.group(0)

    return _NUM.sub(repl, chunk)


def _scrub_clauses(sentence: str, stray: set[str]) -> str:
    """Drop a clause whose only numbers are foreign. A heading on its own line stays."""
    kept_lines: list[str] = []
    for line in sentence.split("\n"):
        kept: list[str] = []
        for part in re.split(r",(?!\d)\s*", line):
            if not part.strip():
                continue
            if _has_stray(part, stray) and not _has_kept(part, stray):
                continue
            if _has_stray(part, stray):
                part = _scrub_tokens(part, stray)
            if part.strip():
                kept.append(part.strip())
        if kept:
            kept_lines.append(", ".join(kept))
    return "\n".join(kept_lines)


def _scrub_region(text: str, stray: set[str]) -> str:
    """Drop the clause that carried a foreign number. Leave the next sentence."""
    if not text or not stray:
        return text or ""
    from case3.chat_turn import _ABBR_DOT

    kept_lines: list[str] = []
    for line in text.split("\n"):
        protected_line = _ABBR_DOT.sub("\\1\x00", line)
        bits = re.split(r"([.!?]+(?:\s+|$))", protected_line)
        kept: list[str] = []
        index = 0
        while index < len(bits):
            chunk = bits[index].replace("\x00", ".")
            delim = bits[index + 1] if index + 1 < len(bits) else ""
            index += 2 if delim else 1
            cleaned = _scrub_clauses(chunk, stray)
            if not cleaned.strip():
                continue
            kept.append(cleaned)
            if delim and (not _has_stray(chunk, stray) or _has_kept(chunk, stray)):
                kept.append(delim)
        if kept:
            kept_lines.append("".join(kept).strip())
    result = "\n".join(kept_lines)
    result = re.sub(r"[ \t]{2,}", " ", result)
    result = re.sub(r" +([,.;:!?])", r"\1", result)
    result = re.sub(r"\n{3,}", "\n\n", result)
    return result


def _scrub_title(
    head: str,
    global_ok: set[str],
    bindings: list[tuple[str, str]],
    *,
    grid: TableGrid | None,
    message_ok: set[str] | None,
) -> str:
    """A foreign number in ``\\title`` would print on the first page."""

    def repl(match: re.Match[str]) -> str:
        inner = _scrub_bound(
            match.group(1),
            global_ok,
            bindings,
            grid=grid,
            message_ok=message_ok,
        ).strip()
        if not re.search(r"[0-9A-Za-zА-Яа-яЁё]", inner):
            inner = "Отчёт"
        return r"\title{" + inner + "}"

    return re.sub(r"\\title\{([^{}]*)\}", repl, head or "", count=1)


def _parts(body: str) -> list[tuple[str, bool]]:
    """(text, protected). Protected spans stay byte for byte."""
    parts: list[tuple[str, bool]] = []
    pos = 0
    for match in _PROTECT.finditer(body):
        if match.start() > pos:
            parts.append((body[pos : match.start()], False))
        parts.append((match.group(0), True))
        pos = match.end()
    if pos < len(body):
        parts.append((body[pos:], False))
    return parts


def _split_document(tex: str) -> tuple[str, str, str]:
    begin = re.search(r"\\begin\{document\}", tex or "")
    if not begin:
        return tex or "", "", ""
    end = tex.find(r"\end{document}", begin.end())
    if end < 0:
        return tex[: begin.end()], tex[begin.end() :], ""
    return tex[: begin.end()], tex[begin.end() : end], tex[end:]


def _quote_is_fact(inner: str) -> bool:
    """A caption or tooltip. HTML dimensions, hex colors, and CSS '%'-options are not facts."""
    if re.search(r"[А-Яа-яЁё]", inner or ""):
        return True
    if re.search(r"тыс|млн|млрд|чел|°", inner or "", re.IGNORECASE):
        return True
    return False


def _scrub_html(html: str, stray: set[str]) -> str:
    def repl(match: re.Match[str]) -> str:
        kind = match.group(1)
        return _rewrite_chart_body(kind, match.group(2), lambda token: _norm_num(token) in stray)

    def repl_quote(match: re.Match[str]) -> str:
        if not _quote_is_fact(match.group(2)):
            return match.group(0)
        return match.group(1) + _scrub_region(match.group(2), stray) + match.group(1)

    return _QUOTED.sub(repl_quote, _JS_ARRAY.sub(repl, html or ""))


def _visible(tex: str, charts: list, figures: list, diagrams: list) -> str:
    _head, body, _tail = _split_document(tex)
    chunks = [piece for piece, protected in _parts(body) if not protected]
    for item in list(charts) + list(figures) + list(diagrams):
        if not isinstance(item, dict):
            continue
        for key in ("caption", "insight", "title", "prompt", "mermaid"):
            val = item.get(key)
            if isinstance(val, str):
                chunks.append(val)
        html = item.get("html")
        if isinstance(html, str):
            chunks.append(html)
        for row in item.get("highlights") or []:
            if isinstance(row, dict):
                chunks.extend(str(row.get(k) or "") for k in ("label", "value", "pct"))
    return "\n".join(chunks)


def ground_generated(
    tex: str,
    charts: list[dict[str, Any]] | None,
    figures: list[dict[str, Any]] | None,
    diagrams: list[dict[str, Any]] | None,
    *,
    source: str,
    intent: str,
) -> tuple[str, list, list, list, list[str]]:
    """Drop fact-numbers that are not in Source and not in the user's message."""
    charts = [dict(item) for item in (charts or []) if isinstance(item, dict)]
    figures = [dict(item) for item in (figures or []) if isinstance(item, dict)]
    diagrams = [dict(item) for item in (diagrams or []) if isinstance(item, dict)]
    global_ok, bindings = fact_context(source, intent)
    grid = table_grid(source)
    message_ok = number_norms(latest_user_line(intent))
    visible = _visible(tex, charts, figures, diagrams)
    dropped = [
        token
        for token in stray_numbers(visible, global_ok)
        if not _clause_allows(
            visible, _norm_num(token), global_ok, bindings, grid, message_ok
        )
    ]
    # A bound number can be legal in one sentence and illegal in the next.
    # Scrub per sentence even when the flat list still contains the value.
    head, body, tail = _split_document(tex)
    head = _scrub_title(
        head, global_ok, bindings, grid=grid, message_ok=message_ok
    )
    body = "".join(
        piece
        if protected
        else _scrub_bound(
            piece, global_ok, bindings, grid=grid, message_ok=message_ok
        )
        for piece, protected in _parts(body)
    )
    tex = head + body + tail
    for item in charts:
        for key in ("caption", "insight"):
            if isinstance(item.get(key), str):
                item[key] = _scrub_bound(
                    item[key], global_ok, bindings, grid=grid, message_ok=message_ok
                ).strip()
        if isinstance(item.get("html"), str):
            item["html"] = _scrub_html_bound(
                item["html"],
                global_ok,
                bindings,
                grid,
                message_ok,
                chart_type=str(item.get("type") or ""),
                caption=str(item.get("caption") or ""),
            )
        rows = []
        for row in item.get("highlights") or []:
            if not isinstance(row, dict):
                continue
            nxt = dict(row)
            label = str(nxt.get("label") or "")
            before_value = str(nxt.get("value") or "")
            for key in ("label", "value", "pct"):
                if isinstance(nxt.get(key), str):
                    nxt[key] = _scrub_bound(
                        nxt[key],
                        global_ok,
                        bindings,
                        context="" if key == "label" else label,
                        grid=grid,
                        message_ok=message_ok,
                    ).strip()
            if before_value.strip() and not str(nxt.get("value") or "").strip():
                continue
            rows.append(nxt)
        if rows:
            item["highlights"] = rows
    for item in figures:
        for key in ("caption", "prompt"):
            if isinstance(item.get(key), str):
                item[key] = _scrub_bound(
                    item[key], global_ok, bindings, grid=grid, message_ok=message_ok
                ).strip()
    for item in diagrams:
        for key in ("title", "caption"):
            if isinstance(item.get(key), str):
                item[key] = _scrub_bound(
                    item[key], global_ok, bindings, grid=grid, message_ok=message_ok
                )
        if isinstance(item.get("mermaid"), str):
            item["mermaid"] = _scrub_mermaid(
                item["mermaid"], global_ok, bindings, grid=grid, message_ok=message_ok
            )
    return tex, charts, figures, diagrams, dropped


_MERMAID_DIRECTIVE = re.compile(
    r"^\s*(?:%%|flowchart\b|graph\b|sequenceDiagram\b|classDiagram\b|stateDiagram(?:-v2)?\b|"
    r"erDiagram\b|classDef\b|class\b|style\b|linkStyle\b|click\b|direction\b|subgraph\b|end\b)",
    re.IGNORECASE,
)


def _scrub_mermaid(
    mermaid: str,
    global_ok: set[str],
    bindings: list[tuple[str, str]],
    *,
    grid: TableGrid | None = None,
    message_ok: set[str] | None = None,
) -> str:
    """Drop stray numbers in node/edge labels without mangling Mermaid directives or edges."""
    out_lines: list[str] = []
    for line in (mermaid or "").splitlines():
        if _MERMAID_DIRECTIVE.match(line):
            out_lines.append(line)
            continue

        def _clean_match(match: re.Match[str]) -> str:
            norm = _norm_num(match.group(0))
            if not norm or _clause_allows(
                line, norm, global_ok, bindings, grid, message_ok
            ):
                return match.group(0)
            return ""

        cleaned = _NUM.sub(_clean_match, line)
        cleaned = re.sub(r" {2,}", " ", cleaned)
        cleaned = re.sub(r" +([\]\)\"\|])", r"\1", cleaned)
        out_lines.append(cleaned)
    return "\n".join(out_lines)


def _kicker_chrome(value: object) -> bool:
    return bool(re.fullmatch(r"\d{1,2}(?:/\d{1,2})?", str(value or "").strip()))


def _row_shares_for_label(label: str, grid: TableGrid | None) -> set[str] | None:
    if grid is None or not grid.row_shares:
        return None
    hits = [stem for stem in _name_stems(label) if stem in grid.row_shares]
    if len(hits) != 1:
        return None
    return grid.row_shares[hits[0]]


def _scrub_html_bound(
    html: str,
    global_ok: set[str],
    bindings: list[tuple[str, str]],
    grid: TableGrid | None = None,
    message_ok: set[str] | None = None,
    *,
    chart_type: str = "",
    caption: str = "",
) -> str:
    """Chart data takes only Source, this message, and matching user bindings.

    A caption may use a bound word. A month label is not a table row, so its
    point stays when the number itself is in Source.
    """
    from case3.chat_memory import _stem_set

    labels = _chart_labels(html)
    html_stems = _stem_set(html)
    is_share_chart = (
        (chart_type or "").strip().lower() == "donut"
        or bool(re.search(r"type\s*:\s*['\"]doughnut['\"]", html or "", re.I))
        or _mentions_share(caption)
        or _mentions_share(html)
        or bool(re.search(r"(?:доля|процент|выполнен|структур)", f"{caption} {html}", re.I))
    )
    chart_row_pool: set[str] = set()
    if grid is not None:
        chart_row_pool |= grid.column_sums | grid.aggregates
        for lbl in labels:
            rn = _row_norms_for_label(lbl, grid)
            if rn:
                chart_row_pool |= rn
    if message_ok:
        chart_row_pool |= set(message_ok)

    def _bound_allows(norm: str, slot: int | None = None) -> bool:
        if not bindings:
            return False
        slot_stems = _stem_set(labels[slot]) if slot is not None and 0 <= slot < len(labels) else set()
        for b_norm, stem in bindings:
            if b_norm != norm:
                continue
            if not stem or stem in slot_stems or stem in html_stems:
                return True
        return False

    def token_reject(token: str) -> bool:
        norm = _norm_num(token)
        if not norm:
            return False
        if _has_norm(global_ok, norm) or (message_ok and _has_norm(message_ok, norm)):
            return False
        if _bound_allows(norm):
            return False
        if is_share_chart and grid is not None:
            if _has_norm(grid.share_values, norm):
                return False
            if _verifies_math(f"{caption} {html}", norm, global_ok | chart_row_pool, chart_row_pool):
                return False
        if (bindings or message_ok) and _verifies_math(
            f"{caption} {html}", norm, global_ok | chart_row_pool, chart_row_pool
        ):
            return False
        return True

    def slot_reject(token: str, slot: int) -> bool:
        norm = _norm_num(token)
        if message_ok and _has_norm(message_ok, norm):
            return False
        if _bound_allows(norm, slot):
            return False
        if slot >= len(labels):
            return False
        allowed = _row_norms_for_label(labels[slot], grid)
        if allowed is None:
            return False
        if _has_norm(allowed, norm):
            return False
        if is_share_chart:
            row_sh = _row_shares_for_label(labels[slot], grid)
            if row_sh and _has_norm(row_sh, norm):
                return False
            if _verifies_math(
                labels[slot],
                norm,
                allowed | chart_row_pool,
                allowed | chart_row_pool,
            ):
                return False
        if (bindings or message_ok) and _verifies_math(
            labels[slot],
            norm,
            allowed | chart_row_pool,
            allowed | chart_row_pool,
        ):
            return False
        return True

    def repl(match: re.Match[str]) -> str:
        kind = match.group(1)
        return _rewrite_chart_body(
            kind,
            match.group(2),
            token_reject,
            slot_reject if kind.lower() == "data" else None,
        )

    def repl_quote(match: re.Match[str]) -> str:
        if not _quote_is_fact(match.group(2)):
            return match.group(0)
        return (
            match.group(1)
            + _scrub_bound(
                match.group(2),
                global_ok,
                bindings,
                grid=grid,
                message_ok=message_ok,
            )
            + match.group(1)
        )

    return _QUOTED.sub(repl_quote, _JS_ARRAY.sub(repl, html or ""))


def bind_deck_numbers(deck: dict[str, Any], *, source: str, intent: str) -> dict[str, Any]:
    """A historical user number stays on a slide only beside its word."""
    global_ok, bindings = fact_context(source, intent)
    grid = table_grid(source)
    message_ok = number_norms(latest_user_line(intent))
    if not isinstance(deck, dict):
        return deck
    slides = []
    for slide in deck.get("slides") or []:
        if not isinstance(slide, dict):
            slides.append(slide)
            continue
        nxt = dict(slide)
        for key in ("title", "subtitle", "caption", "body", "kicker", "takeaway", "term", "definition"):
            if isinstance(nxt.get(key), str):
                if key == "kicker" and _kicker_chrome(nxt[key]):
                    continue
                nxt[key] = _scrub_bound(
                    str(nxt[key]), global_ok, bindings, grid=grid, message_ok=message_ok
                ).strip()
        if isinstance(nxt.get("bullets"), list):
            nxt["bullets"] = [
                cleaned
                for item in nxt["bullets"]
                if (
                    cleaned := _scrub_bound(
                        str(item), global_ok, bindings, grid=grid, message_ok=message_ok
                    ).strip()
                )
            ]
        if isinstance(nxt.get("rows"), list):
            raw_rows = [row for row in nxt["rows"] if isinstance(row, list)]
            had_digits = [
                any(bool(_NUM.search(str(cell))) for cell in row) for row in raw_rows
            ]
            rows: list[list[str]] = []
            row_digits: list[bool] = []
            for row, row_has_digit in zip(raw_rows, had_digits):
                cells = [
                    _scrub_bound(
                        str(cell),
                        global_ok,
                        bindings,
                        grid=grid,
                        message_ok=message_ok,
                    ).strip()
                    for cell in row
                ]
                if any(cell.strip() for cell in cells):
                    rows.append(cells)
                    row_digits.append(row_has_digit)
            if rows:
                header, data = rows[0], rows[1:]
                data_had = row_digits[1:]
                kept_data = [
                    row
                    for row, had in zip(data, data_had)
                    if not had or any(bool(_NUM.search(cell)) for cell in row)
                ]
                rows = [header] + kept_data if kept_data else []
            nxt["rows"] = rows
        if isinstance(nxt.get("cards"), list):
            cards = []
            for card in nxt["cards"]:
                if not isinstance(card, dict):
                    continue
                nxt_card = dict(card)
                for key in ("title", "body", "kicker"):
                    if isinstance(nxt_card.get(key), str):
                        if key == "kicker" and _kicker_chrome(nxt_card[key]):
                            continue
                        nxt_card[key] = _scrub_bound(
                            str(nxt_card[key]),
                            global_ok,
                            bindings,
                            grid=grid,
                            message_ok=message_ok,
                        ).strip()
                if str(nxt_card.get("title") or "").strip():
                    cards.append(nxt_card)
            nxt["cards"] = cards
        if isinstance(nxt.get("kpis"), list):
            kept = []
            for kpi in nxt["kpis"]:
                if not isinstance(kpi, dict):
                    continue
                nxt_kpi = dict(kpi)
                label = str(nxt_kpi.get("label") or "")
                value = str(nxt_kpi.get("value") or "")
                clause = f"{label} {value}"
                norms = {_norm_num(token) for token in _NUM.findall(value)}
                if norms and not all(
                    _clause_allows(clause, norm, global_ok, bindings, grid, message_ok)
                    for norm in norms
                ):
                    continue
                for extra_key in ("delta", "hint"):
                    if isinstance(nxt_kpi.get(extra_key), str):
                        nxt_kpi[extra_key] = _scrub_bound(
                            nxt_kpi[extra_key],
                            global_ok,
                            bindings,
                            context=label,
                            grid=grid,
                            message_ok=message_ok,
                        ).strip()
                kept.append(nxt_kpi)
            nxt["kpis"] = kept
        slides.append(nxt)
    out = dict(deck)
    out["slides"] = slides
    return _repass_blank_slides(out)


def _has_letters(value: object) -> bool:
    return bool(re.search(r"[0-9A-Za-zА-Яа-яЁё]", str(value or "")))


def _slide_still_visible(slide: dict[str, Any]) -> bool:
    if str(slide.get("media_id") or slide.get("chart_id") or "").strip():
        return True
    for key in (
        "title",
        "subtitle",
        "caption",
        "body",
        "kicker",
        "takeaway",
        "term",
        "definition",
    ):
        if _has_letters(slide.get(key)):
            return True
    for item in slide.get("bullets") or []:
        if _has_letters(item):
            return True
    for card in slide.get("cards") or []:
        if isinstance(card, dict) and any(
            _has_letters(card.get(key)) for key in ("title", "body", "kicker")
        ):
            return True
    for kpi in slide.get("kpis") or []:
        if isinstance(kpi, dict) and str(kpi.get("value") or "").strip():
            return True
    for row in slide.get("rows") or []:
        if isinstance(row, list) and any(str(cell).strip() and str(cell).strip() != "—" for cell in row):
            return True
    return False


def _repass_blank_slides(deck: dict[str, Any]) -> dict[str, Any]:
    """Drop a slide the number pass wiped. Never leave the deck empty."""
    kept = [
        slide
        for slide in deck.get("slides") or []
        if isinstance(slide, dict) and _slide_still_visible(slide)
    ]
    if not kept:
        kept = [{"id": "s01", "layout": "title", "title": "Итоги"}]
    out = dict(deck)
    out["slides"] = kept
    return out
