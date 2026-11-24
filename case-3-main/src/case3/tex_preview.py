"""Parse final XeLaTeX into a Liber-friendly chat preview (blocks JSON)."""

from __future__ import annotations

import html as html_lib
import re
from typing import Any

_BEGIN_DOC = re.compile(r"\\begin\{document\}", re.I)
_END_DOC = re.compile(r"\\end\{document\}", re.I)
_TITLE = re.compile(r"\\title\{([^{}]*)\}")
_SECTION = re.compile(r"\\(sub)*section\*?\{([^{}]*)\}")
_TABLE_ENV = re.compile(
    r"\\begin\{table\*?\}.*?\\end\{table\*?\}"
    r"|\\begin\{longtable\*?\}.*?\\end\{longtable\*?\}"
    r"|\\begin\{xltabular\}.*?\\end\{xltabular\}",
    re.S,
)
_TABULAR = re.compile(
    r"\\begin\{tabularx\}\{[^}]+\}\{[^}]+\}([\s\S]*?)\\end\{tabularx\}"
    r"|\\begin\{tabular\}\{[^}]+\}([\s\S]*?)\\end\{tabular\}"
    r"|\\begin\{longtable\*?\}\{[^}]+\}([\s\S]*?)\\end\{longtable\*?\}"
    r"|\\begin\{xltabular\}\{[^}]+\}\{[^}]+\}([\s\S]*?)\\end\{xltabular\}"
)
_CAPTION = re.compile(r"\\caption\{([^{}]*)\}")
_FIGURE_ENV = re.compile(
    r"\\begin\{figure\}.*?\\end\{figure\}",
    re.S,
)
_INCLUDEGRAPHICS = re.compile(
    r"\\includegraphics(?:\[[^\]]*\])?\{(?:figures/)?([a-zA-Z0-9_]+)\.png\}"
)
_PAGE_BREAK = re.compile(r"\\(?:newpage|clearpage|pagebreak)\b")
_LABEL = re.compile(r"\\label\{[^}]*\}")


def estimate_figure_pdf_pages(tex: str) -> dict[str, int]:
    """Map figure id → 1-based PDF page guess from TeX page breaks.

    Counts ``\\newpage`` / ``\\clearpage`` / ``\\pagebreak`` before each
    ``\\includegraphics``. Same-page figures share a page number.
    """
    body = tex or ""
    m_begin = _BEGIN_DOC.search(body)
    m_end = _END_DOC.search(body)
    if m_begin:
        body = body[m_begin.end() :]
    if m_end:
        # end may still be relative to original; re-search on sliced body
        m_end2 = _END_DOC.search(body)
        if m_end2:
            body = body[: m_end2.start()]

    page = 1
    hints: dict[str, int] = {}
    events: list[tuple[int, str, str]] = []
    for m in _PAGE_BREAK.finditer(body):
        events.append((m.start(), "break", ""))
    for m in _INCLUDEGRAPHICS.finditer(body):
        events.append((m.start(), "fig", m.group(1)))
    events.sort(key=lambda t: t[0])
    for _pos, kind, fid in events:
        if kind == "break":
            page += 1
        elif fid and fid not in hints:
            hints[fid] = page
    return hints
_LIST_ENV = re.compile(
    r"\\begin\{(itemize|enumerate)\}([\s\S]*?)\\end\{\1\}",
    re.I,
)
_ITEM = re.compile(r"\\item\b", re.I)
_INLINE_EMPH = re.compile(
    r"\\(textbf|textit|emph|texttt)\{([^{}]*)\}",
)


def _plain_unescape(text: str) -> str:
    """Strip TeX to plain text (no HTML)."""
    t = text or ""
    t = t.replace(r"\%", "%")
    t = t.replace(r"\&", "&")
    t = t.replace(r"\$", "$")
    t = t.replace(r"\#", "#")
    t = t.replace(r"\_", "_")
    t = t.replace(r"\{", "{")
    t = t.replace(r"\}", "}")
    t = t.replace(r"\,", " ")
    t = t.replace(r"\ ", " ")
    t = t.replace("~", " ")
    t = t.replace("---", "—")
    t = t.replace("--", "–")
    t = re.sub(r"\{\s*,\s*\}", ",", t)
    t = re.sub(r"\$([^$]*)\$", r"\1", t)
    for _ in range(2):
        t = re.sub(
            r"\\(?:textbf|textit|emph|texttt|underline|textsc|textsf|textrm)\*?\{([^{}]*)\}",
            r"\1",
            t,
        )
        t = re.sub(r"\\(?:textcolor|href)\*?\{[^{}]*\}\{([^{}]*)\}", r"\1", t)
    t = re.sub(r"\\[a-zA-Z]+\*?(?:\[[^\]]*\])?(?:\{[^{}]*\})?", "", t)
    t = re.sub(r"\s+", " ", t).strip()
    return t


def _inline_to_html(tex_fragment: str) -> str:
    """Convert a TeX prose fragment to safe HTML with strong/em/code and math spans."""
    t = tex_fragment or ""
    t = t.replace(r"\%", "%")
    t = t.replace(r"\&", "&")
    t = t.replace(r"\$", "@@ESC_DOLLAR@@")
    t = t.replace(r"\#", "#")
    t = t.replace(r"\_", "_")
    t = t.replace(r"\{", "{")
    t = t.replace(r"\}", "}")
    t = t.replace(r"\,", " ")
    t = t.replace(r"\ ", " ")
    t = t.replace("~", " ")
    t = t.replace("---", "—")
    t = t.replace("--", "–")
    t = re.sub(r"\{\s*,\s*\}", ",", t)

    # Protect math spans and emphasis spans, escape the rest, then restore tags.
    slots: list[tuple[str, str]] = []

    def _stash_math(m: re.Match[str]) -> str:
        inner = m.group(1).strip()
        if not inner:
            return ""
        esc_attr = html_lib.escape(inner, quote=True)
        esc_text = html_lib.escape(inner)
        tag = f'<span class="tex-math" data-math="{esc_attr}">{esc_text}</span>'
        key = f"@@M{len(slots)}@@"
        slots.append((key, tag))
        return key

    t = re.sub(r"\$([^$]+)\$", _stash_math, t)

    def _stash(m: re.Match[str]) -> str:
        cmd, inner = m.group(1), m.group(2)
        plain = _plain_unescape(inner)
        esc = html_lib.escape(plain)
        if cmd == "textbf":
            tag = f"<strong>{esc}</strong>"
        elif cmd in ("textit", "emph"):
            tag = f"<em>{esc}</em>"
        else:
            tag = f"<code>{esc}</code>"
        key = f"@@H{len(slots)}@@"
        slots.append((key, tag))
        return key

    t = _INLINE_EMPH.sub(_stash, t)
    for _ in range(2):
        t = re.sub(
            r"\\(?:underline|textsc|textsf|textrm)\*?\{([^{}]*)\}",
            r"\1",
            t,
        )
        t = re.sub(r"\\(?:textcolor|href)\*?\{[^{}]*\}\{([^{}]*)\}", r"\1", t)
    t = re.sub(r"\\[a-zA-Z]+\*?(?:\[[^\]]*\])?(?:\{[^{}]*\})?", "", t)
    t = re.sub(r"\s+", " ", t).strip()
    out = html_lib.escape(t)
    out = out.replace("@@ESC_DOLLAR@@", "$")
    for key, tag in slots:
        out = out.replace(key, tag)
    return out


def _body_bounds(tex: str) -> tuple[str, int]:
    """Return (body_slice, absolute_start_offset in full tex)."""
    raw = tex or ""
    m0 = _BEGIN_DOC.search(raw)
    if not m0:
        return raw, 0
    start = m0.end()
    m1 = _END_DOC.search(raw, start)
    end = m1.start() if m1 else len(raw)
    return raw[start:end], start


def _body(tex: str) -> str:
    body, _off = _body_bounds(tex)
    return body


def _split_rows(tabular_body: str) -> list[list[str]]:
    raw = tabular_body or ""
    raw = re.sub(r"\\(?:caption|label)\*?(?:\[[^\]]*\])?\{[^{}]*\}", "", raw)
    raw = re.sub(
        r"\\(?:toprule|midrule|bottomrule|hline|endfirsthead|endhead|endfoot|endlastfoot)\s*",
        "",
        raw,
    )
    chunks = re.split(r"\\\\", raw)
    rows: list[list[str]] = []
    for chunk in chunks:
        s = chunk.strip()
        if not s or ("&" not in s and not s):
            continue
        if "&" not in s and not re.search(r"[A-Za-zА-Яа-я0-9]", s):
            continue
        cells = []
        # Split on bare & only — keep \& inside a cell
        for c in re.split(r"(?<!\\)&", s):
            plain = _plain_unescape(c).strip()
            # Liber table edit: empty cells serialize as TeX ~
            if plain == "~":
                plain = ""
            cells.append(plain)
        if any(cells):
            rows.append(cells)
    return rows


def _table_env_name(tok: str) -> str:
    if "xltabular" in tok:
        return "xltabular"
    if "longtable" in tok:
        return "longtable"
    if "tabularx" in tok:
        return "tabularx"
    return "table"


def _is_table_token(tok: str) -> bool:
    return (
        tok.startswith(r"\begin{table}")
        or tok.startswith(r"\begin{longtable}")
        or tok.startswith(r"\begin{xltabular}")
        or tok.startswith(r"\begin{tabularx}")
    )


def _parse_table_block(block: str) -> dict[str, Any] | None:
    cap_m = _CAPTION.search(block)
    caption = _plain_unescape(cap_m.group(1)) if cap_m else ""
    tab_m = _TABULAR.search(block)
    if not tab_m:
        return None
    body = next((group for group in tab_m.groups() if group is not None), "")
    rows = _split_rows(body or "")
    if not rows:
        return None
    headers = rows[0]
    data = rows[1:] if len(rows) > 1 else []
    return {
        "type": "table",
        "caption": caption,
        "headers": headers,
        "rows": data,
    }


def _parse_figure_block(block: str) -> dict[str, Any] | None:
    img = _INCLUDEGRAPHICS.search(block)
    if not img:
        return None
    fid = img.group(1)
    cap_m = _CAPTION.search(block)
    caption = _plain_unescape(cap_m.group(1)) if cap_m else ""
    if fid.startswith("cht_"):
        kind = "chart"
    elif fid.startswith("dia_"):
        kind = "diagram"
    else:
        kind = "image"
    return {
        "type": "figure",
        "id": fid,
        "kind": kind,
        "caption": caption,
    }


def _parse_list_block(env: str, inner: str) -> dict[str, Any] | None:
    parts = _ITEM.split(inner or "")
    items: list[dict[str, str]] = []
    for part in parts[1:]:  # before first \item is junk
        raw = part.strip()
        if not raw:
            continue
        # Stop at nested begin if any leaked
        raw = re.split(r"\\begin\{", raw, maxsplit=1)[0]
        text = _plain_unescape(raw.replace("\n", " "))
        if len(text) < 1:
            continue
        items.append({"text": text, "html": _inline_to_html(raw.replace("\n", " "))})
    if not items:
        return None
    return {
        "type": "list",
        "ordered": env.lower() == "enumerate",
        "items": items,
    }


_STRUCT_TOKEN = re.compile(
    r"(\\maketitle\b|"
    r"\\tableofcontents\b|"
    r"\\section\*?\{[^{}]*\}|"
    r"\\subsection\*?\{[^{}]*\}|"
    r"\\subsubsection\*?\{[^{}]*\}|"
    r"\\begin\{table\*?\}|"
    r"\\begin\{longtable\*?\}|"
    r"\\begin\{xltabular\}|"
    r"\\begin\{tabularx\}|"
    r"\\begin\{figure\}|"
    r"\\begin\{landscape\}|"
    r"\\begin\{itemize\}|"
    r"\\begin\{enumerate\})",
)


def _paragraph_parts_in_range(
    body: str, lo: int, hi: int
) -> list[tuple[int, int, str, str]]:
    """Yield (start, end, plain_text, html) for prose parts in body[lo:hi]."""
    out: list[tuple[int, int, str, str]] = []
    i = lo
    while i < hi and body[i].isspace():
        i += 1
    while i < hi:
        mblank = re.search(r"\n\s*\n", body[i:hi])
        part_end = i + mblank.start() if mblank else hi
        j = part_end
        while j > i and body[j - 1] in " \t\r\n":
            j -= 1
        if j > i:
            raw_slice = body[i:j]
            # Mirror _flush_paragraphs filters on a copy
            text = _LABEL.sub("", raw_slice)
            text = re.sub(r"\\(?:centering|hfill|vfill|noindent)\s*", "", text)
            text = _LIST_ENV.sub("", text)
            raw = text.replace("\n", " ")
            cleaned = _plain_unescape(raw)
            if (
                len(cleaned) >= 2
                and not cleaned.startswith("%")
                and not cleaned.startswith(r"\begin")
            ):
                # Skip pure command-only leftovers (maketitle already tokenized)
                if not re.fullmatch(r"\\[a-zA-Z]+\*?", cleaned.strip()):
                    out.append((i, j, cleaned, _inline_to_html(raw)))
        if not mblank:
            break
        i = i + mblank.end()
        while i < hi and body[i] in " \t":
            i += 1
    return out


def find_paragraph_spans(tex: str) -> list[tuple[int, int]]:
    """Absolute [start, end) spans in ``tex`` for each preview paragraph (para-N)."""
    body, body_off = _body_bounds(tex)
    spans: list[tuple[int, int]] = []
    pos = 0
    while pos < len(body):
        m = _STRUCT_TOKEN.search(body, pos)
        if not m:
            for a, b, _t, _h in _paragraph_parts_in_range(body, pos, len(body)):
                spans.append((body_off + a, body_off + b))
            break
        if m.start() > pos:
            for a, b, _t, _h in _paragraph_parts_in_range(body, pos, m.start()):
                spans.append((body_off + a, body_off + b))
        tok = m.group(1)
        if _is_table_token(tok):
            env = _table_env_name(tok)
            em = re.search(rf"\\end\{{{env}\*?\}}", body[m.start() :], re.S)
            pos = m.start() + em.end() if em else m.end()
            continue
        if tok.startswith(r"\begin{figure}"):
            em = re.search(r"\\end\{figure\}", body[m.start() :], re.S)
            pos = m.start() + em.end() if em else m.end()
            continue
        if tok.startswith(r"\begin{landscape}"):
            em = re.search(r"\\end\{landscape\}", body[m.start() :], re.S)
            pos = m.start() + em.end() if em else m.end()
            continue
        if tok.startswith(r"\begin{itemize}") or tok.startswith(r"\begin{enumerate}"):
            env = "itemize" if "itemize" in tok else "enumerate"
            em = re.search(rf"\\end\{{{env}\}}", body[m.start() :], re.S | re.I)
            pos = m.start() + em.end() if em else m.end()
            continue
        pos = m.end()
    return spans



def find_heading_spans(tex: str) -> list[tuple[int, int]]:
    """Absolute [start, end) spans for each preview heading (\\section / \\subsection)."""
    body, body_off = _body_bounds(tex)
    spans: list[tuple[int, int]] = []
    for m in _SECTION.finditer(body):
        spans.append((body_off + m.start(), body_off + m.end()))
    return spans


def find_list_spans(tex: str) -> list[tuple[int, int]]:
    """Absolute [start, end) spans for each top-level itemize/enumerate block."""
    body, body_off = _body_bounds(tex)
    spans: list[tuple[int, int]] = []
    pos = 0
    while pos < len(body):
        m = _STRUCT_TOKEN.search(body, pos)
        if not m:
            break
        tok = m.group(1)
        if tok.startswith(r"\begin{itemize}") or tok.startswith(r"\begin{enumerate}"):
            env = "itemize" if "itemize" in tok else "enumerate"
            em = re.search(rf"\\end\{{{env}\}}", body[m.start() :], re.S | re.I)
            if not em:
                pos = m.end()
                continue
            end = m.start() + em.end()
            spans.append((body_off + m.start(), body_off + end))
            pos = end
            continue
        if tok.startswith(r"\begin{table}"):
            em = re.search(r"\\end\{table\*?\}", body[m.start() :], re.S)
            pos = m.start() + em.end() if em else m.end()
            continue
        if tok.startswith(r"\begin{figure}"):
            em = re.search(r"\\end\{figure\}", body[m.start() :], re.S)
            pos = m.start() + em.end() if em else m.end()
            continue
        if tok.startswith(r"\begin{landscape}"):
            em = re.search(r"\\end\{landscape\}", body[m.start() :], re.S)
            pos = m.start() + em.end() if em else m.end()
            continue
        pos = m.end()
    return spans


def tex_to_preview_blocks(tex: str) -> dict[str, Any]:
    """Extract title + ordered content blocks from a full document."""
    title_m = _TITLE.search(tex or "")
    title = _plain_unescape(title_m.group(1)) if title_m else ""
    body = _body(tex)
    blocks: list[dict[str, Any]] = []
    para_n = 0
    list_n = 0

    pos = 0
    while pos < len(body):
        m = _STRUCT_TOKEN.search(body, pos)
        if not m:
            for _a, _b, cleaned, html in _paragraph_parts_in_range(
                body, pos, len(body)
            ):
                para_n += 1
                blocks.append(
                    {
                        "type": "paragraph",
                        "id": f"para-{para_n}",
                        "text": cleaned,
                        "html": html,
                    }
                )
            break

        if m.start() > pos:
            for _a, _b, cleaned, html in _paragraph_parts_in_range(
                body, pos, m.start()
            ):
                para_n += 1
                blocks.append(
                    {
                        "type": "paragraph",
                        "id": f"para-{para_n}",
                        "text": cleaned,
                        "html": html,
                    }
                )

        tok = m.group(1)
        if tok in (r"\maketitle", r"\tableofcontents"):
            pos = m.end()
            continue
        if (
            tok.startswith(r"\section")
            or tok.startswith(r"\subsection")
            or tok.startswith(r"\subsubsection")
        ):
            sm = _SECTION.match(tok)
            if sm:
                if "subsubsection" in tok:
                    level = 3
                elif "subsection" in tok:
                    level = 2
                else:
                    level = 1
                blocks.append(
                    {
                        "type": "heading",
                        "level": level,
                        "text": _plain_unescape(sm.group(2)),
                    }
                )
            pos = m.end()
            continue

        if _is_table_token(tok):
            env = _table_env_name(tok)
            em = re.search(rf"\\end\{{{env}\*?\}}", body[m.start() :], re.S)
            if not em:
                pos = m.end()
                continue
            end = m.start() + em.end()
            table = _parse_table_block(body[m.start() : end])
            if table:
                blocks.append(table)
            pos = end
            continue

        if tok.startswith(r"\begin{landscape}"):
            em = re.search(r"\\end\{landscape\}", body[m.start() :], re.S)
            if not em:
                pos = m.end()
                continue
            # Preview: unwrap landscape and parse inner table if present
            inner = body[m.end() : m.start() + em.start()]
            tm = re.search(
                r"\\begin\{table\*?\}.*?\\end\{table\*?\}|"
                r"\\begin\{xltabular\}.*?\\end\{xltabular\}",
                inner,
                re.S,
            )
            if tm:
                table = _parse_table_block(tm.group(0))
                if table:
                    table["landscape"] = True
                    blocks.append(table)
            pos = m.start() + em.end()
            continue

        if tok.startswith(r"\begin{figure}"):
            em = re.search(r"\\end\{figure\}", body[m.start() :], re.S)
            if not em:
                pos = m.end()
                continue
            end = m.start() + em.end()
            fig = _parse_figure_block(body[m.start() : end])
            if fig:
                blocks.append(fig)
            pos = end
            continue

        if tok.startswith(r"\begin{itemize}") or tok.startswith(r"\begin{enumerate}"):
            env = "itemize" if "itemize" in tok else "enumerate"
            em = re.search(rf"\\end\{{{env}\}}", body[m.start() :], re.S | re.I)
            if not em:
                pos = m.end()
                continue
            end = m.start() + em.end()
            block = body[m.start() : end]
            lm = _LIST_ENV.search(block)
            if lm:
                lst = _parse_list_block(lm.group(1), lm.group(2))
                if lst:
                    list_n += 1
                    lst["id"] = f"list-{list_n}"
                    blocks.append(lst)
            pos = end
            continue

        pos = m.end()

    return {"title": title, "blocks": blocks}


def build_report_preview(
    tex: str,
    *,
    run_id: str,
    media_status: dict[str, Any] | None = None,
    figures_json: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Attach figure URLs / captions for chat rendering."""
    media = media_status or {}
    fj = figures_json or {}
    cap_by_id: dict[str, str] = {}
    type_by_id: dict[str, str] = {}
    palette_by_id: dict[str, str] = {}
    for item in fj.get("charts") or []:
        if isinstance(item, dict) and item.get("id"):
            fid0 = str(item["id"])
            cap = str(item.get("caption") or "").strip()
            if cap:
                cap_by_id[fid0] = cap
            ctype = str(item.get("type") or "").strip()
            if ctype:
                type_by_id[fid0] = ctype
            pal = str(item.get("palette") or "").strip()
            if pal:
                palette_by_id[fid0] = pal
    for item in fj.get("figures") or []:
        if isinstance(item, dict) and item.get("id"):
            cap = str(item.get("caption") or "").strip()
            if cap:
                cap_by_id[str(item["id"])] = cap
    for item in fj.get("diagrams") or []:
        if isinstance(item, dict) and item.get("id"):
            cap = str(item.get("title") or item.get("caption") or "").strip()
            if cap:
                cap_by_id[str(item["id"])] = cap

    data = tex_to_preview_blocks(tex)
    page_hints = estimate_figure_pdf_pages(tex)
    out_blocks: list[dict[str, Any]] = []
    for b in data["blocks"]:
        if b.get("type") != "figure":
            out_blocks.append(b)
            continue
        fid = str(b.get("id") or "")
        st = media.get(fid) if isinstance(media.get(fid), dict) else {}
        kind = str(st.get("kind") or b.get("kind") or "image")
        if kind == "figure":
            kind = "image"
        caption = str(b.get("caption") or "").strip() or cap_by_id.get(fid, "")
        if kind == "chart" or fid.startswith("cht_"):
            fig_kind = "chart"
        elif kind == "diagram" or fid.startswith("dia_"):
            fig_kind = "diagram"
        else:
            fig_kind = "image"
        entry: dict[str, Any] = {
            "type": "figure",
            "id": fid,
            "kind": fig_kind,
            "caption": caption,
        }
        if fid in page_hints:
            entry["pdfPage"] = page_hints[fid]
        if fid in type_by_id:
            entry["chartType"] = type_by_id[fid]
        if fid in palette_by_id:
            entry["palette"] = palette_by_id[fid]
        # Optional Mary-style card meta from charts[] (Source-derived only).
        for item in fj.get("charts") or []:
            if not isinstance(item, dict):
                continue
            if str(item.get("id") or "") != fid:
                continue
            insight = str(item.get("insight") or "").strip()
            if insight:
                entry["insight"] = insight
            hl = item.get("highlights")
            if isinstance(hl, list) and hl:
                entry["highlights"] = hl
            if not entry.get("palette"):
                pal = str(item.get("palette") or "").strip()
                if pal:
                    entry["palette"] = pal
            break
        if st.get("ok") and fid:
            entry["url"] = f"/api/runs/{run_id}/figures/{fid}.png"
        out_blocks.append(entry)
    return {"title": data["title"], "blocks": out_blocks}
