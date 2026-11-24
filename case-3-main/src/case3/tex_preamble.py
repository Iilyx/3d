"""Ensure XeLaTeX documents have the packages and report style we need."""

from __future__ import annotations

import re

# Order matches prompt/system_tex.md — inject after \\documentclass if missing.
# hyperref stays last among these; style packages before it.
REQUIRED_PACKAGES = (
    "fontspec",
    "polyglossia",
    "geometry",
    "booktabs",
    "array",  # >{…} col types for wrapping tabularx
    "tabularx",
    "longtable",
    "xltabular",  # long markdown tables: X columns that break across pages
    "float",
    "graphicx",
    "setspace",
    "microtype",
    "titlesec",
    "fancyhdr",
    "caption",
    "pdflscape",  # C4: landscape page for wide tables only
    "amsmath",  # \text{литров} inside formulas; without it XeLaTeX exits 1
    "xcolor",  # before hyperref; LLM often emits \definecolor / \color
    "hyperref",
)

# Match \documentclass[...]{name} even when the next token is on the same line.
_DOCCLASS = re.compile(r"(\\documentclass(?:\[[^\]]*\])?\{[^}]+\})")
_GEOMETRY = re.compile(r"\\geometry\{[^}]*\}")
_A4_GEOMETRY = r"\geometry{a4paper,margin=2.2cm}"
_BEGIN_DOC = re.compile(r"\\begin\{document\}")

# Plain l/c/r tabulars with ≥3 columns overflow A4 — promote to tabularx.
_TABULAR_BLOCK = re.compile(
    r"\\begin\{tabular\}\{([^}]*)\}([\s\S]*?)\\end\{tabular\}",
    re.M,
)

_BRAND = re.compile(r"case[\s\-]?3", re.I)

# Safe titlesec — no \color (needs xcolor) and numbered sections.
# Chrome 2.0: slightly more air before/after section headings.
_SAFE_TITLEFORMAT = r"""\titleformat{\section}{\large\bfseries\raggedright}{\thesection.}{0.6em}{}
\titleformat{\subsection}{\normalsize\bfseries\raggedright}{\thesubsection.}{0.5em}{}
\titlespacing*{\section}{0pt}{1.8ex plus .3ex}{0.9ex plus .15ex}
\titlespacing*{\subsection}{0pt}{1.25ex plus .2ex}{0.55ex plus .08ex}
"""

# D4 + chrome 2.0: title rule, float air, modest par/list rhythm.
_LIBER_PRINT_CHROME = r"""
% --- Liber print chrome (D4) ---
\setlength{\textfloatsep}{16pt plus 2pt minus 2pt}
\setlength{\floatsep}{14pt plus 2pt minus 2pt}
\setlength{\intextsep}{14pt plus 2pt minus 2pt}
\setlength{\abovecaptionskip}{8pt}
\setlength{\belowcaptionskip}{4pt}
\setlength{\parskip}{0.35em plus 0.1em minus 0.05em}
\setlength{\itemsep}{0.28em}
\setlength{\parsep}{0.2em}
\setlength{\topsep}{0.45em}
\let\CaseThreeMaketitle\maketitle
\renewcommand{\maketitle}{%
  \CaseThreeMaketitle
  \vspace{-0.55em}%
  \noindent\rule{\textwidth}{0.35pt}%
  \vspace{1.05em}%
}
"""

# Injected once before \begin{document} if fancyhdr style missing.
REPORT_STYLE_BLOCK = r"""
% --- report style: typography + running header ---
\setstretch{1.15}
\setlength{\headheight}{15pt}
\captionsetup{font=small,labelfont=bf,skip=6pt,justification=centering}
\captionsetup[figure]{name={Рис.}}
\captionsetup[table]{name={Таблица}}
""" + _SAFE_TITLEFORMAT + _LIBER_PRINT_CHROME + r"""
\pagestyle{fancy}
\fancyhf{}
\fancyhead[L]{\footnotesize\itshape\leftmark}
\fancyhead[R]{\footnotesize\thepage}
\renewcommand{\headrulewidth}{0.35pt}
\renewcommand{\footrulewidth}{0pt}
\fancypagestyle{plain}{%
  \fancyhf{}%
  \fancyhead[R]{\footnotesize\thepage}%
  \renewcommand{\headrulewidth}{0pt}%
}
"""

# Drop LLM titleformat/titlespacing for section/subsection (often broken).
_TITLEFORMAT_BLOCK = re.compile(
    r"\\titleformat\{\\(?:sub)?section\}[\s\S]*?"
    r"(?=\\titleformat\{|\\titlespacing|\\pagestyle|\\begin\{document\}|\\setcounter|\\captionsetup|\\onehalfspacing|\\setstretch|\\setlength|\\fancy|\\renewcommand|\\fancypagestyle|\\hypersetup|\\definecolor|%)",
    re.M,
)
_TITLESPACING_BLOCK = re.compile(
    r"\\titlespacing\*?\{\\(?:sub)?section\}(?:\{[^{}]*\}){3}\s*",
    re.M,
)


class TexStructureError(ValueError):
    """Document is missing required LaTeX structure."""


def _simple_lcr_count(colspec: str) -> int | None:
    """Return # of l/c/r columns, or None if spec already uses p/X/etc."""
    spec = (colspec or "").strip()
    if not spec:
        return None
    if re.search(r"[pXmbsS\*]|@{|!{", spec):
        return None
    cols = re.findall(r"[lcr]", spec)
    return len(cols) if cols else None


_TABULARX_BLOCK = re.compile(
    r"\\begin\{tabularx\}\{\\textwidth\}\{([^}]*)\}([\s\S]*?)\\end\{tabularx\}",
    re.M,
)


def harden_wide_tables(tex: str) -> str:
    """Rewrite wide ``tabular{lll…}`` into ``tabularx{\\textwidth}{lXX…}``."""

    def _repl(m: re.Match[str]) -> str:
        spec, body = m.group(1), m.group(2)
        # Nested tabular: non-greedy match would break the outer env — skip.
        if r"\begin{tabular}" in body or r"\begin{tabularx}" in body:
            return m.group(0)
        n = _simple_lcr_count(spec)
        if n is None or n < 3:
            return m.group(0)
        # Only plain l/c/r (no | @{} etc.) — preserve ruled specs.
        if not re.fullmatch(r"[lcr\s]+", (spec or "").strip()):
            return m.group(0)
        letters = re.findall(r"[lcr]", spec)
        new_spec = "Y" * len(letters)
        return (
            rf"\begin{{tabularx}}{{\textwidth}}{{{new_spec}}}"
            + body
            + r"\end{tabularx}"
        )

    return _TABULAR_BLOCK.sub(_repl, tex)


_TABLE_ENV_BLOCK = re.compile(
    r"\\begin\{table\*?\}.*?\\end\{table\*?\}",
    re.S,
)
_COL_SPEC = re.compile(
    r"\\begin\{(tabularx?\*?|xltabular)\}(?:\s*\[[^\]]*\])?",
)


def _take_brace_group(text: str, pos: int) -> tuple[str, int] | None:
    """Read a balanced ``{...}`` group starting at/after ``pos`` (skipping spaces)."""
    n = len(text)
    while pos < n and text[pos].isspace():
        pos += 1
    if pos >= n or text[pos] != "{":
        return None
    depth = 0
    start = pos + 1
    i = pos
    while i < n:
        ch = text[i]
        if ch == "\\" and i + 1 < n:
            i += 2
            continue
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return text[start:i], i + 1
        i += 1
    return None


def _extract_table_spec_and_body(block: str) -> tuple[str, str] | None:
    """Return ``(colspec, body)`` for ``tabular*``, ``tabularx*``, or ``xltabular``."""
    m = _COL_SPEC.search(block or "")
    if not m:
        return None
    env = m.group(1)
    pos = m.end()
    if env != "tabular":
        width_grp = _take_brace_group(block, pos)
        if width_grp is None:
            return None
        pos = width_grp[1]
    spec_grp = _take_brace_group(block, pos)
    if spec_grp is None:
        return None
    spec, body_start = spec_grp
    end_tok = rf"\end{{{env}}}"
    end_at = block.rfind(end_tok, body_start)
    body = block[body_start:end_at] if end_at >= 0 else block[body_start:]
    return spec, body


def _col_count_from_spec(spec: str) -> int:
    s = (spec or "").strip()
    # Strip @{...}, >{...}, <{...}, !{...} payloads so letters inside them aren't counted.
    stripped = re.sub(r"[@><!]\{(?:[^{}]|\{[^{}]*\})*\}", "", s)
    fixed_cols = re.findall(r"[pmb]\{[^}]*\}", stripped)
    stripped = re.sub(r"[pmb]\{[^}]*\}", "", stripped)
    return len(re.findall(r"[XYZlcr]", stripped)) + len(fixed_cols)


def table_needs_landscape(table_block: str) -> bool:
    """True when a table is too wide for portrait A4 even as tabularx."""
    if r"\begin{landscape}" in (table_block or ""):
        return False
    extracted = _extract_table_spec_and_body(table_block or "")
    if not extracted:
        return False
    spec, body = extracted
    ncols = _col_count_from_spec(spec)
    if ncols >= 6:
        return True
    # Long average cell text with ≥4 cols
    if ncols < 4:
        return False
    cells = [
        c.strip()
        for row in re.split(r"\\\\", body)
        for c in row.split("&")
        if c.strip() and not re.match(r"^\\(?:top|mid|bottom)rule$", c.strip())
    ]
    if len(cells) < 4:
        return False
    avg = sum(len(c) for c in cells) / len(cells)
    return avg >= 28 and ncols >= 5


def _plain_cell_len(cell: str) -> int:
    s = re.sub(r"\\[a-zA-Z]+\*?(?:\[[^\]]*\])?\{([^{}]*)\}", r"\1", cell or "")
    s = re.sub(r"\\[,\s]", " ", s)
    s = re.sub(r"\\[a-zA-Z]+\*?", "", s)
    return len(" ".join(s.split()))


def _cell_looks_numeric_tex(cell: str) -> bool:
    s = re.sub(r"\\[a-zA-Z]+\*?(?:\[[^\]]*\])?\{([^{}]*)\}", r"\1", cell or "")
    s = s.replace(r"\%", "%").replace(r"\,", "").replace("~", "").replace(" ", "").strip()
    if not s or s in {"—", "-", "–"}:
        return False
    return bool(re.fullmatch(r"[+\-−]?\d[\d.,]*(?:%|тыс\.?|млн\.?|руб\.?)*", s, re.I))


def _proportional_colspec(spec: str, body: str) -> str:
    """Turn equal-width YYYYYY into compact l/r for narrow code/number cols + Y for wide text cols."""
    clean_spec = (spec or "").strip()
    if not re.fullmatch(r"[lcrXYZ\s]+", clean_spec):
        return clean_spec
    letters = re.findall(r"[lcrXYZ]", clean_spec)
    ncols = len(letters)
    if ncols < 2:
        return clean_spec
    data_rows: list[list[str]] = []
    for chunk in re.split(r"\\\\", body or ""):
        s = chunk.strip()
        if not s or "&" not in s:
            continue
        s = re.sub(r"^\\(?:toprule|midrule|bottomrule|hline|endhead|endfoot|endfirsthead|endlastfoot)\s*", "", s)
        if "&" not in s:
            continue
        cells = [c.strip() for c in re.split(r"(?<!\\)&", s)]
        if len(cells) >= ncols:
            data_rows.append(cells[:ncols])
    if len(data_rows) < 2:
        return clean_spec
    header_row = data_rows[0]
    body_only = data_rows[1:] if len(data_rows) > 1 else data_rows
    max_lens: list[int] = [0] * ncols
    new_cols: list[str] = []
    for ci in range(ncols):
        col_cells = [r[ci] for r in body_only if ci < len(r)]
        mlen = max((_plain_cell_len(c) for c in col_cells), default=0)
        hlen = _plain_cell_len(header_row[ci]) if ci < len(header_row) else 0
        max_lens[ci] = max(mlen, hlen)
        num_cnt = sum(1 for c in col_cells if _cell_looks_numeric_tex(c))
        non_empty = sum(1 for c in col_cells if _plain_cell_len(c) > 0)
        is_num = non_empty > 0 and (num_cnt / non_empty >= 0.6)
        if is_num and mlen <= 18:
            if hlen <= 16:
                new_cols.append("r")
            elif ncols >= 8:
                new_cols.append("Y")
            else:
                new_cols.append("Z")
        elif ci == 0 and mlen <= 10 and hlen <= 12:
            new_cols.append("l")
        elif (
            mlen <= 10
            and hlen <= 12
            and not any(" " in c.strip() for c in col_cells if _plain_cell_len(c) > 8)
        ):
            new_cols.append("l")
        else:
            new_cols.append("Y")
    if "Y" not in new_cols:
        widest = max(range(ncols), key=lambda idx: max_lens[idx])
        new_cols[widest] = "Y"
    return "".join(new_cols)


def _landscape_table_upgrade(chunk: str) -> str:
    """Inside landscape, convert [H]/long wide tabularx into page-breaking xltabular with smart cols."""
    s = (chunk or "").strip()
    # Unwrap outer landscape if called on an already-landscaped block
    had_land = s.startswith(r"\begin{landscape}") and s.endswith(r"\end{landscape}")
    inner = s
    if had_land:
        inner = re.sub(r"^\\begin\{landscape\}\s*", "", inner)
        inner = re.sub(r"\s*\\end\{landscape\}$", "", inner).strip()

    tm = re.search(
        r"\\begin\{table\*?\}(?:\s*\[([^\]]*)\])?(.*?)\\end\{table\*?\}",
        inner,
        re.S,
    )
    if not tm:
        xm_bare = re.search(
            r"\\begin\{(tabularx|xltabular)\}\{([^}]*)\}\{([^}]*)\}([\s\S]*?)\\end\{\1\}",
            inner,
        )
        if not xm_bare:
            return chunk
        env_b, _w_b, spec_b, tbody_b = (
            xm_bare.group(1),
            xm_bare.group(2),
            xm_bare.group(3),
            xm_bare.group(4),
        )
        smart_b = _proportional_colspec(spec_b, tbody_b)
        ncols_b = len(re.findall(r"[lcrXYZ]", smart_b))
        size_cmd_b = r"\footnotesize" if ncols_b >= 10 else r"\small"
        colsep_b = "2.5pt" if ncols_b >= 10 else "4pt"
        inner_b = (
            inner[: xm_bare.start()]
            + f"{{{size_cmd_b}\n\\setlength{{\\tabcolsep}}{{{colsep_b}}}\n"
            + rf"\begin{{{env_b}}}{{\linewidth}}{{{smart_b}}}{tbody_b}\end{{{env_b}}}"
            + "\n}"
            + inner[xm_bare.end() :]
        )
        return f"\\begin{{landscape}}\n{inner_b.strip()}\n\\end{{landscape}}"
    float_opt = (tm.group(1) or "").strip()
    table_body = tm.group(2)
    xm = re.search(
        r"\\begin\{(tabularx|xltabular)\}\{([^}]*)\}\{([^}]*)\}([\s\S]*?)\\end\{\1\}",
        table_body,
    )
    if not xm:
        return chunk
    env, _width, spec, tbody = xm.group(1), xm.group(2), xm.group(3), xm.group(4)
    smart_spec = _proportional_colspec(spec, tbody)
    row_count = len([c for c in re.split(r"\\\\", tbody) if "&" in c])
    should_xltabular = (
        env == "xltabular"
        or float_opt.upper() == "H"
        or row_count >= 10
    )
    if not should_xltabular:
        if smart_spec != spec:
            updated = (
                table_body[: xm.start()]
                + rf"\begin{{{env}}}{{\linewidth}}{{{smart_spec}}}{tbody}\end{{{env}}}"
                + table_body[xm.end() :]
            )
            inner_new = (
                inner[: tm.start()]
                + rf"\begin{{table}}[{float_opt or 'htbp'}]{updated}\end{{table}}"
                + inner[tm.end() :]
            )
            return f"\\begin{{landscape}}\n{inner_new}\n\\end{{landscape}}"
        return chunk

    cap_m = re.search(r"\\caption\*?\{([^{}]*(?:\{[^{}]*\}[^{}]*)*)\}", table_body)
    caption_line = rf"\caption{{{cap_m.group(1).strip()}}} \\" if cap_m else ""
    # Split header (up to \midrule) and body rows
    clean_body = tbody.strip()
    clean_body = re.sub(r"^\\toprule\s*", "", clean_body)
    clean_body = re.sub(r"\s*\\bottomrule\s*$", "", clean_body)
    if r"\midrule" in clean_body:
        head_part, data_part = clean_body.split(r"\midrule", 1)
    else:
        parts = re.split(r"\\\\", clean_body, maxsplit=1)
        head_part = (parts[0] + r" \\") if parts else ""
        data_part = parts[1] if len(parts) > 1 else ""
    head_part = head_part.strip()
    data_part = re.sub(r"^\s*\\end(?:first)?head\s*", "", data_part).strip()
    data_part = re.sub(r"\s*\\(?:bottomrule|end(?:last)?foot)\s*", "\n", data_part).strip()

    ncols_xl = len(re.findall(r"[lcrXYZ]", smart_spec))
    size_cmd_xl = r"\footnotesize" if ncols_xl >= 10 else r"\small"
    colsep_xl = "2.5pt" if ncols_xl >= 10 else "4pt"
    xl_lines = [
        f"{{{size_cmd_xl}",
        rf"\setlength{{\tabcolsep}}{{{colsep_xl}}}",
        rf"\begin{{xltabular}}{{\linewidth}}{{{smart_spec}}}",
    ]
    if caption_line:
        xl_lines.append(caption_line)
    xl_lines.extend(
        [
            r"\toprule",
            head_part,
            r"\midrule",
            r"\endhead",
            r"\bottomrule",
            r"\endfoot",
            data_part,
            r"\end{xltabular}",
            r"}",
        ]
    )
    xl_block = "\n".join(line for line in xl_lines if line)
    inner_new = inner[: tm.start()] + xl_block + inner[tm.end() :]
    return f"\\begin{{landscape}}\n{inner_new.strip()}\n\\end{{landscape}}"


def maybe_landscape_wide_tables(tex: str) -> str:
    """Wrap overly wide ``table`` / ``xltabular`` envs in ``pdflscape`` landscape (once)."""
    parts: list[str] = []
    pos = 0
    for m in re.finditer(
        r"\\begin\{landscape\}.*?\\end\{landscape\}|"
        r"\\begin\{table\*?\}.*?\\end\{table\*?\}|"
        r"\\begin\{xltabular\}.*?\\end\{xltabular\}",
        tex or "",
        re.S,
    ):
        parts.append(tex[pos : m.start()])
        chunk = m.group(0)
        if chunk.lstrip().startswith(r"\begin{landscape}"):
            parts.append(_landscape_table_upgrade(chunk))
        elif table_needs_landscape(chunk):
            parts.append(
                _landscape_table_upgrade(
                    "\\begin{landscape}\n" + chunk.strip() + "\n\\end{landscape}"
                )
            )
        else:
            parts.append(chunk)
        pos = m.end()
    parts.append(tex[pos:] if tex else "")
    return "".join(parts)


_CITE_CMD = re.compile(r"\\cite\{([^}]*)\}")
_FOOTNOTE_CMD = re.compile(r"\\footnote\{([^{}]*(?:\{[^{}]*\}[^{}]*)*)\}")


def strip_invented_cites(tex: str, *, allowed_keys: set[str] | None = None) -> str:
    """Drop ``\\cite{key}`` when key is not allowed; keep URL-like footnotes."""
    allowed = allowed_keys or set()

    def _cite_repl(m: re.Match[str]) -> str:
        key = (m.group(1) or "").strip()
        if key in allowed:
            return m.group(0)
        return ""

    out = _CITE_CMD.sub(_cite_repl, tex or "")
    # Collapse leftover double spaces from cite removal
    out = re.sub(r"[ \t]+\n", "\n", out)
    out = re.sub(r"  +", " ", out)
    return out



_Y_COLUMNTYPE = (
    r"\newcolumntype{Y}{>{\hspace{0pt}\raggedright\arraybackslash}X}"
)
_Z_COLUMNTYPE = (
    r"\newcolumntype{Z}{>{\hspace{0pt}\raggedleft\arraybackslash}p{2.5cm}}"
)


def ensure_wrap_columntype(tex: str) -> str:
    """Define wrapping tabularx columns ``Y`` (ragged text) and ``Z`` (numeric + wrapped header)."""
    out = tex or ""
    need_y = r"\newcolumntype{Y}" not in out
    need_z = r"\newcolumntype{Z}" not in out
    if not need_y and not need_z:
        return out
    defs = "\n".join(
        line
        for flag, line in ((need_y, _Y_COLUMNTYPE), (need_z, _Z_COLUMNTYPE))
        if flag
    )
    # Prefer right after array or tabularx package.
    for needle in (r"\usepackage{array}", r"\usepackage{tabularx}"):
        if needle in out:
            return out.replace(needle, needle + "\n" + defs, 1)
    parts = _split_preamble(out)
    if not parts:
        return out
    head, body = parts
    return head.rstrip() + "\n" + defs + "\n" + body


def harden_tabularx_wrap_cols(tex: str) -> str:
    """Rewrite plain ``l/c/r/X`` tabularx/xltabular specs to wrapping ``Y`` columns.

    ``{lXXXX}`` lets the first ``l`` steal width (e.g. «LibreOffice Calc»),
    then long words in narrow ``X`` cells overflow into the next column.
    """

    def _repl(m: re.Match[str]) -> str:
        env, width, spec, body = m.group(1), m.group(2), m.group(3), m.group(4)
        # Already uses Y/Z or p{…} / >{…} — leave alone.
        if "Y" in spec or "Z" in spec or "p{" in spec or ">{" in spec:
            return m.group(0)
        letters = re.findall(r"[lcrX]", spec)
        if len(letters) < 2:
            return m.group(0)
        # Only rewrite simple letter specs (no | @{} etc. beyond spaces).
        if not re.fullmatch(r"[lcrX\s]+", (spec or "").strip()):
            return m.group(0)
        new_spec = "Y" * len(letters)
        return (
            rf"\begin{{{env}}}{{{width}}}{{{new_spec}}}"
            + body
            + rf"\end{{{env}}}"
        )

    return re.sub(
        r"\\begin\{(tabularx|xltabular)\}\{([^}]*)\}\{([^}]*)\}([\s\S]*?)\\end\{\1\}",
        _repl,
        tex or "",
    )



def harden_tabularx_colcount(tex: str) -> str:
    """Fix ``tabularx{…}{lrrrr}`` when the header has more ``&`` than columns."""

    def _repl(m: re.Match[str]) -> str:
        spec, body = m.group(1), m.group(2)
        if r"\begin{tabular" in body:
            return m.group(0)
        # Split on \\ row terminators (body may be one long line).
        ncol_body = 0
        chunks = re.split(r"\\\\", body)
        for chunk in chunks:
            s = chunk.strip()
            if not s or "&" not in s:
                continue
            s = re.sub(
                r"^\\(?:toprule|midrule|bottomrule|hline)\s*",
                "",
                s,
            )
            s = re.sub(
                r"\\(?:toprule|midrule|bottomrule|hline)\s*",
                " ",
                s,
            ).strip()
            if "&" not in s:
                continue
            ncol_body = s.count("&") + 1
            break
        if ncol_body < 2:
            return m.group(0)
        letters = re.findall(r"[lcrX]", spec)
        if len(letters) == ncol_body:
            return m.group(0)
        # rebuild: all wrapping Y (equal share of textwidth)
        new_spec = "Y" * ncol_body
        return (
            rf"\begin{{tabularx}}{{\textwidth}}{{{new_spec}}}"
            + body
            + r"\end{tabularx}"
        )

    return _TABULARX_BLOCK.sub(_repl, tex)


def ensure_font_aliases(tex: str) -> str:
    """Model often emits font names missing in the Docker image."""
    repls = (
        (r"\setmonofont{DejaVu Mono}", r"\setmonofont{DejaVu Sans Mono}"),
        (r"\setmainfont{Times New Roman}", r"\setmainfont{DejaVu Serif}"),
        (r"\setsansfont{Arial}", r"\setsansfont{DejaVu Sans}"),
    )
    out = tex
    for a, b in repls:
        out = out.replace(a, b)
    return out


def scrub_package_typos(tex: str) -> str:
    """Rewrite common LLM package typos (titlespec → titlesec, …)."""
    out = tex or ""
    # Drop bogus package; real titlesec is injected via REQUIRED_PACKAGES if missing.
    out = re.sub(r"\\usepackage\{titlespec\}\s*", "", out)
    return out


def fix_tabularx_colspec_junk(tex: str) -> str:
    """Remove garbage after colspec until \\toprule / \\midrule / \\hline.

    Models emit both ``{lXX}X r X}`` and
    ``{lXXXX}\\raggedright...}p{2.4cm}…`` — anything between the real
    colspec ``}`` and the first booktabs rule must go, while preserving nested
    ``@{}`` / ``>{...}`` / ``p{...}`` inside the real colspec.
    """
    src = tex or ""
    out: list[str] = []
    pos = 0
    for m in re.finditer(r"\\begin\{(?:tabularx|xltabular)\}", src):
        if m.start() < pos:
            continue
        width_grp = _take_brace_group(src, m.end())
        if width_grp is None:
            continue
        spec_grp = _take_brace_group(src, width_grp[1])
        if spec_grp is None:
            continue
        spec_end = spec_grp[1]
        env_end = re.search(r"\\end\{(?:tabularx|xltabular)\}", src[spec_end:])
        scope = src[spec_end : spec_end + env_end.start()] if env_end else src[spec_end:]
        rule_m = re.search(r"\\(?:toprule|midrule|hline|bottomrule)", scope)
        if not rule_m:
            continue
        gap = src[spec_end : spec_end + rule_m.start()]
        if not gap.strip():
            continue
        out.append(src[pos:spec_end])
        out.append("\n")
        pos = spec_end + rule_m.start()
    out.append(src[pos:])
    return "".join(out)


def fix_tabularx_end_mismatch(tex: str) -> str:
    """``\\begin{tabularx}…\\end{tabular}`` → close with ``tabularx``."""
    pattern = re.compile(
        r"\\begin\{tabularx\}|\\end\{tabularx\}|\\end\{tabular\}(?!x)"
    )
    depth = 0
    parts: list[str] = []
    last = 0
    for m in pattern.finditer(tex or ""):
        parts.append(tex[last : m.start()])
        tok = m.group(0)
        if tok == r"\begin{tabularx}":
            depth += 1
            parts.append(tok)
        elif tok == r"\end{tabularx}":
            depth = max(0, depth - 1)
            parts.append(tok)
        else:
            if depth > 0:
                parts.append(r"\end{tabularx}")
                depth -= 1
            else:
                parts.append(tok)
        last = m.end()
    parts.append((tex or "")[last:])
    return "".join(parts)


_RULE_LINE = re.compile(
    r"^\\(?:toprule|midrule|bottomrule|hline)\b",
)


def _repair_tabular_body_rows(body: str) -> str:
    """Join cell-per-line bodies (``Excel &\\nBSD &\\n...\\\\``) into rows."""
    lines = (body or "").splitlines()
    # Trigger only when the model put one cell per line ending with &.
    amp_ends = sum(
        1
        for ln in lines
        if re.search(r"&\s*$", ln.strip())
        and not re.search(r"\\\\\s*$", ln.strip())
    )
    # One trailing-& line is enough (2-col: ``A &\\nB \\\\``) — D12.
    if amp_ends < 1:
        return body

    out: list[str] = []
    cells: list[str] = []

    def _flush() -> None:
        nonlocal cells
        if not cells:
            return
        out.append(" & ".join(cells) + r" \\")
        cells = []

    for ln in lines:
        s = ln.strip()
        if not s:
            continue
        if _RULE_LINE.match(s):
            _flush()
            out.append(s)
            continue
        row_end = bool(re.search(r"\\\\\s*$", s))
        s = re.sub(r"\\\\\s*$", "", s).strip()
        parts = [p.strip() for p in s.split("&")]
        if parts and parts[-1] == "":
            parts = parts[:-1]
        cells.extend(parts)
        if row_end:
            _flush()
    _flush()
    return ("\n".join(out) + "\n") if out else body


def repair_tabularx_row_breaks(tex: str) -> str:
    """Fix tabularx bodies where each cell sits on its own line ending with ``&``."""

    def _repl(m: re.Match[str]) -> str:
        spec, body = m.group(1), m.group(2)
        fixed = _repair_tabular_body_rows(body)
        if fixed and not fixed.startswith("\n"):
            fixed = "\n" + fixed
        return rf"\begin{{tabularx}}{{\textwidth}}{{{spec}}}" + fixed + r"\end{tabularx}"

    return _TABULARX_BLOCK.sub(_repl, tex or "")


def scrub_project_branding(tex: str) -> str:
    """Remove project codename from title/author (must not appear in PDF)."""

    def _author(m: re.Match[str]) -> str:
        return r"\author{}" if _BRAND.search(m.group(1) or "") else m.group(0)

    def _title(m: re.Match[str]) -> str:
        body = m.group(1) or ""
        if not _BRAND.search(body):
            return m.group(0)
        cleaned = _BRAND.sub("", body)
        cleaned = re.sub(r"\s{2,}", " ", cleaned).strip(" -:|")
        return r"\title{" + (cleaned or "Отчёт") + "}"

    out = re.sub(r"\\author\{([^{}]*)\}", _author, tex)
    out = re.sub(r"\\title\{([^{}]*)\}", _title, out)
    return out


_CYRILLIC_FONTS = r"""
\setdefaultlanguage{russian}
\setotherlanguage{english}
\setmainfont{DejaVu Serif}
\setsansfont{DejaVu Sans}
\setmonofont{DejaVu Sans Mono}
""".strip()


def ensure_cyrillic_fonts(tex: str) -> str:
    """XeLaTeX without \\setmainfont falls back to Latin Modern → blank Cyrillic."""
    if r"\setmainfont{" in (tex or ""):
        return tex
    m = _BEGIN_DOC.search(tex or "")
    if not m:
        return tex
    # Prefer right after polyglossia / fontspec if present.
    insert_at = m.start()
    for anchor in (
        r"\usepackage{polyglossia}",
        r"\usepackage{fontspec}",
        r"\documentclass",
    ):
        idx = tex.find(anchor)
        if idx >= 0:
            # after end of that line
            nl = tex.find("\n", idx)
            insert_at = (nl + 1) if nl >= 0 else idx + len(anchor)
            break
    block = _CYRILLIC_FONTS + "\n"
    return tex[:insert_at] + block + tex[insert_at:]


def _split_preamble(tex: str) -> tuple[str, str] | None:
    m = _BEGIN_DOC.search(tex or "")
    if not m:
        return None
    return tex[: m.start()], tex[m.start() :]


def sanitize_titleformat(tex: str) -> str:
    """Replace LLM \\titleformat / \\titlespacing with a safe numbered style.

    Models often emit ``\\color{black}`` inside titleformat (needs xcolor) and
    empty number args that make titlesec fail with «Entered in horizontal mode».
    """
    parts = _split_preamble(tex)
    if not parts:
        return tex
    head, body = parts
    head = _TITLEFORMAT_BLOCK.sub("", head)
    head = _TITLESPACING_BLOCK.sub("", head)
    # Any leftover color switches in the preamble (not body prose).
    head = re.sub(r"\\color\{[^}]+\}", "", head)
    if r"\titleformat{\section}" not in head:
        # Insert safe block just before \begin{document} side (end of head).
        head = head.rstrip() + "\n" + _SAFE_TITLEFORMAT.strip() + "\n"
    return head + body


def ensure_headheight(tex: str) -> str:
    """fancyhdr warns when \\headheight < ~14.5pt — pin 15pt once."""
    if r"\setlength{\headheight}" in (tex or ""):
        return tex
    parts = _split_preamble(tex)
    if not parts:
        return tex
    head, body = parts
    head = head.rstrip() + "\n\\setlength{\\headheight}{15pt}\n"
    return head + body


def ensure_russian_captions(tex: str) -> str:
    """D2: figure/table labels «Рис.» / «Таблица» (idempotent)."""
    out = tex or ""
    if r"name={Рис.}" not in out and r"name={Рис}" not in out:
        # After generic captionsetup or before \begin{document}.
        needle = r"\captionsetup{font=small,labelfont=bf,skip=6pt,justification=centering}"
        insert = (
            needle
            + "\n\\captionsetup[figure]{name={Рис.}}\n"
            + "\\captionsetup[table]{name={Таблица}}"
        )
        if needle in out:
            out = out.replace(needle, insert, 1)
        else:
            parts = _split_preamble(out)
            if parts:
                head, body = parts
                out = (
                    head.rstrip()
                    + "\n\\captionsetup[figure]{name={Рис.}}\n"
                    + "\\captionsetup[table]{name={Таблица}}\n"
                    + body
                )
    elif r"name={Таблица}" not in out:
        parts = _split_preamble(out)
        if parts:
            head, body = parts
            out = head.rstrip() + "\n\\captionsetup[table]{name={Таблица}}\n" + body
    return out


def ensure_liber_print_chrome(tex: str) -> str:
    """D4: title rule + float spacing even when fancyhdr already present."""
    out = tex or ""
    if r"\CaseThreeMaketitle" in out and r"\setlength{\textfloatsep}" in out:
        return out
    parts = _split_preamble(out)
    if not parts:
        return out
    head, body = parts
    chrome = _LIBER_PRINT_CHROME.strip() + "\n"
    # Drop a prior partial inject (rule without let, or vice versa).
    if r"\CaseThreeMaketitle" in head:
        return out
    return head.rstrip() + "\n" + chrome + "\n" + body


def ensure_report_style(tex: str) -> str:
    """Typography + fancyhdr; always sanitize titlesec even if fancy already set."""
    out = sanitize_titleformat(tex)
    out = ensure_headheight(out)
    if r"\pagestyle{fancy}" in out and r"\setstretch{" in out:
        return ensure_liber_print_chrome(ensure_russian_captions(out))
    parts = _split_preamble(out)
    if not parts:
        return out
    head, body = parts
    block = REPORT_STYLE_BLOCK.strip() + "\n\n"
    # Avoid duplicating titleformat we just injected.
    if r"\titleformat{\section}" in head:
        # Inject stretch/fancyhdr pieces only.
        extra = []
        if r"\setstretch{" not in head:
            extra.append(r"\setstretch{1.15}")
        if r"\pagestyle{fancy}" not in head:
            extra.append(
                r"""\pagestyle{fancy}
\fancyhf{}
\fancyhead[L]{\footnotesize\itshape\leftmark}
\fancyhead[R]{\footnotesize\thepage}
\renewcommand{\headrulewidth}{0.35pt}
\renewcommand{\footrulewidth}{0pt}
\fancypagestyle{plain}{%
  \fancyhf{}%
  \fancyhead[R]{\footnotesize\thepage}%
  \renewcommand{\headrulewidth}{0pt}%
}"""
            )
        if not extra:
            return ensure_liber_print_chrome(ensure_russian_captions(out))
        return ensure_liber_print_chrome(
            ensure_russian_captions(
                head.rstrip() + "\n" + "\n".join(extra) + "\n" + body
            )
        )
    return ensure_liber_print_chrome(ensure_russian_captions(head + block + body))

def assert_tex_structure(tex: str) -> None:
    if r"\documentclass" not in tex:
        raise TexStructureError("missing \\documentclass")
    if r"\begin{document}" not in tex:
        raise TexStructureError("missing \\begin{document}")
    if r"\end{document}" not in tex:
        raise TexStructureError("missing \\end{document}")


def _ensure_a4_documentclass(tex: str) -> str:
    """Force a4paper into \\documentclass options (default page size)."""

    def _fix(m: re.Match[str]) -> str:
        opts = (m.group(1) or "").strip()
        name = m.group(2)
        parts = [p.strip() for p in opts.split(",") if p.strip()] if opts else []
        parts = [
            p
            for p in parts
            if p.lower()
            not in {
                "a4paper",
                "a5paper",
                "letterpaper",
                "legalpaper",
                "executivepaper",
                "b5paper",
                "landscape",
            }
        ]
        parts.insert(0, "a4paper")
        if not any(re.fullmatch(r"\d+pt", p) for p in parts):
            parts.append("12pt")
        return rf"\documentclass[{','.join(parts)}]{{{name}}}"

    return re.sub(
        r"\\documentclass(?:\[([^\]]*)\])?\{([^}]+)\}",
        _fix,
        tex,
        count=1,
    )


def ensure_a4_layout(tex: str) -> str:
    """Pin page to A4 portrait with comfortable margins."""
    out = _ensure_a4_documentclass(tex)
    if _GEOMETRY.search(out):
        # callable repl — avoid re.sub treating \g in \geometry as a group
        return _GEOMETRY.sub(lambda _m: _A4_GEOMETRY, out, count=1)
    if r"\usepackage{geometry}" in out:
        return out.replace(
            r"\usepackage{geometry}",
            r"\usepackage{geometry}" + "\n" + _A4_GEOMETRY,
            1,
        )
    return out


def preamble_looks_broken(tex: str) -> bool:
    """True if preamble is truncated / unbalanced (unsafe for latexmk)."""
    t = tex or ""
    m = _BEGIN_DOC.search(t)
    head = t[: m.start()] if m else t
    if not head.strip():
        return True
    if head.count("{") != head.count("}"):
        return True
    last = head.rstrip().rsplit("\n", 1)[-1].strip()
    if re.search(r"\\[a-zA-Z]+$", last):
        return True
    # Truncated \usepackage{geom  or \setotherlanguage{engl
    if re.search(r"\\(?:usepackage|set(?:main|sans|mono)font|set(?:default|other)language|geometry)\{[^}]*$", head):
        return True
    if re.search(r"\\usepackage\{[a-zA-Z]*$", head, re.M):
        return True
    return False


def _replace_preamble(tex: str, new_preamble: str) -> str:
    m = _BEGIN_DOC.search(tex or "")
    if not m:
        return new_preamble.rstrip() + "\n"
    body = tex[m.start() :]
    return new_preamble.rstrip() + "\n" + body.lstrip()


def order_definecolor_before_hypersetup(tex: str) -> str:
    """Move \\definecolor{…} blocks above \\hypersetup that references them."""
    parts = _split_preamble(tex)
    if not parts:
        return tex
    head, body = parts
    defines = re.findall(r"\\definecolor\{[^}]+\}\{[^}]+\}\{[^}]+\}\s*", head)
    if not defines or r"\hypersetup" not in head:
        return tex
    head_wo = re.sub(r"\\definecolor\{[^}]+\}\{[^}]+\}\{[^}]+\}\s*", "", head)
    # Insert defines right after last \usepackage{xcolor} (or before first hypersetup).
    anchor = r"\usepackage{xcolor}"
    if anchor in head_wo:
        idx = head_wo.index(anchor) + len(anchor)
        nl = head_wo.find("\n", idx)
        at = (nl + 1) if nl >= 0 else idx
    else:
        at = head_wo.index(r"\hypersetup")
    block = "".join(defines)
    if not block.endswith("\n"):
        block += "\n"
    head_wo = head_wo[:at] + block + head_wo[at:]
    return head_wo + body



def ensure_black_hyperref_links(tex: str) -> str:
    """Force black TOC/section links — never default hyperref blue."""
    out = tex or ""
    setup = (
        r"\hypersetup{colorlinks=true,linkcolor=black,"
        r"urlcolor=black,citecolor=black,filecolor=black}"
    )

    def _blacken(m: re.Match[str]) -> str:
        body = m.group(1)
        for key in ("linkcolor", "urlcolor", "citecolor", "filecolor"):
            body = re.sub(
                rf"{key}\s*=\s*[^,}}\s]+",
                f"{key}=black",
                body,
                flags=re.I,
            )
        if "linkcolor=" not in body.lower():
            body = body.rstrip(",") + ",linkcolor=black"
        if "colorlinks" not in body.lower():
            body = "colorlinks=true," + body
        return r"\hypersetup{" + body + "}"

    if r"\hypersetup" in out:
        out = re.sub(r"\\hypersetup\s*\{([^}]*)\}", _blacken, out)
    else:
        needle = r"\usepackage{hyperref}"
        if needle in out:
            out = out.replace(needle, needle + "\n" + setup, 1)
        else:
            parts = _split_preamble(out)
            if parts:
                head, body = parts
                out = head.rstrip() + "\n" + setup + "\n" + body
    return out



def tex_for_pandoc(tex: str) -> str:
    """Simplify Liber TeX so pandoc can build DOCX tables.

    Custom ``Y`` wrap columns are PDF-only; pandoc dumps them as literal text.
    """
    out = tex or ""
    # Strip \newcolumntype{Y|Z}{…} even with nested braces inside >{…}.
    while True:
        m_y = re.search(r"\\newcolumntype\{[YZ]\}\{", out)
        if not m_y:
            break
        i = m_y.end()
        depth = 1
        while i < len(out) and depth:
            if out[i] == "{":
                depth += 1
            elif out[i] == "}":
                depth -= 1
            i += 1
        out = out[: m_y.start()] + out[i:].lstrip("\n")

    parts: list[str] = []
    pos = 0
    for m in re.finditer(r"\\begin\{(?:tabularx|xltabular)\}", out):
        if m.start() < pos:
            continue
        w_grp = _take_brace_group(out, m.end())
        if w_grp is None:
            continue
        s_grp = _take_brace_group(out, w_grp[1])
        if s_grp is None:
            continue
        width, spec, end_pos = w_grp[0], s_grp[0], s_grp[1]
        clean_spec = spec.replace("Y", "X").replace("Z", "r")
        parts.append(out[pos : m.start()])
        parts.append(rf"\begin{{tabularx}}{{{width}}}{{{clean_spec}}}")
        pos = end_pos
    parts.append(out[pos:])
    out = "".join(parts)
    out = re.sub(r"\\(?:endfirsthead|endhead|endfoot|endlastfoot)\s*", "", out)
    out = out.replace(r"\end{xltabular}", r"\end{tabularx}")
    return out



def ensure_document_preamble(tex: str) -> str:
    """Packages + Cyrillic fonts + A4 + report style + branding scrub + tables."""
    from case3.tex_utils import _MIN_PREAMBLE

    out = scrub_project_branding(tex)
    if preamble_looks_broken(out):
        out = _replace_preamble(out, _MIN_PREAMBLE)
    m = _DOCCLASS.search(out)
    if m:
        missing = [p for p in REQUIRED_PACKAGES if rf"\usepackage{{{p}}}" not in out]
        if missing:
            block = "".join(rf"\usepackage{{{p}}}" + "\n" for p in missing)
            insert_at = m.end()
            out = out[:insert_at] + "\n" + block + out[insert_at:].lstrip("\n")
    out = scrub_package_typos(out)
    out = ensure_cyrillic_fonts(out)
    out = ensure_font_aliases(out)
    out = ensure_a4_layout(out)
    out = ensure_report_style(out)
    out = order_definecolor_before_hypersetup(out)
    out = ensure_black_hyperref_links(out)
    out = fix_tabularx_colspec_junk(out)
    out = fix_tabularx_end_mismatch(out)
    out = repair_tabularx_row_breaks(out)
    out = harden_wide_tables(out)
    out = harden_tabularx_colcount(out)
    out = ensure_wrap_columntype(out)
    out = harden_tabularx_wrap_cols(out)
    out = maybe_landscape_wide_tables(out)
    out = strip_orphan_table_markup(out)
    out = strip_invented_cites(out, allowed_keys=set())
    from case3.tex_prose import (
        brace_schema_item_labels,
        fix_markdown_bold_leaks,
        fix_unclosed_caption_args,
        fix_unclosed_float_envs,
        fix_unclosed_heading_args,
        harden_math_prose,
        drop_empty_lists,
        harden_prose_lists,
        harden_russian_typography,
        normalize_includegraphics_aspect,
        scrub_emoji_from_headings,
        unstar_headings,
    )
    from case3.tex_tables import harden_table_rules

    out = fix_markdown_bold_leaks(out)
    out = fix_unclosed_heading_args(out)
    out = unstar_headings(out)
    out = scrub_emoji_from_headings(out)
    out = fix_unclosed_caption_args(out)
    out = fix_unclosed_float_envs(out)
    out = harden_prose_lists(out)
    out = drop_empty_lists(out)
    out = brace_schema_item_labels(out)
    out = normalize_includegraphics_aspect(out)
    out = harden_math_prose(out)
    out = harden_russian_typography(out)
    return harden_table_rules(out)


def ensure_preamble(tex: str) -> str:
    """Public alias used by tests / callers."""
    return ensure_document_preamble(tex)


def strip_orphan_slots(tex: str) -> str:
    """Remove leftover CASE3 media slots (FIG/CHART/DIAG) before latexmk.

    DIAG is Liber UI-only — models still leak ``%CASE3_DIAG:…%`` into TeX figures.
    Also handles escaped `\\%CASE3_...\\%` and inline leftover mentions.
    """
    if not tex:
        return tex
    # Full lines with slot markers (escaped or unescaped)
    tex = re.sub(
        r"(?m)^[ \t]*\\?%?CASE3_(?:FIG|CHART|DIAG):[a-z0-9_]{0,31}\\?%?[^\n]*\r?\n?",
        "",
        tex,
        flags=re.I,
    )
    # Inline leftover slot markers anywhere in text
    return re.sub(
        r"\\?%?CASE3_(?:FIG|CHART|DIAG):[a-z0-9_]{0,31}\\?%?",
        "",
        tex,
        flags=re.I,
    )


_ORPHAN_RULE = re.compile(
    r"^[ \t]*\\(?:toprule|midrule|bottomrule|hline)\b.*$",
    re.M,
)


def strip_orphan_table_markup(tex: str) -> str:
    """Escape bare ``&`` and drop booktabs/hline rules outside tabular bodies.

    Prevents Misplaced ``&`` / ``\\noalign`` when the model leaks table chrome
    into prose (D12 / home_doc_audit T_line).
    """
    if not tex:
        return tex
    parts: list[str] = []
    pos = 0
    depth = 0
    for m in re.finditer(
        r"\\begin\{(xltabular|tabularx?\*?|longtable\*?)\}|\\end\{(xltabular|tabularx?\*?|longtable\*?)\}",
        tex,
        flags=re.I,
    ):
        chunk = tex[pos : m.start()]
        if depth == 0:
            chunk = _sanitize_orphan_chunk(chunk)
        parts.append(chunk)
        token = m.group(0)
        parts.append(token)
        if token.lower().startswith(r"\begin"):
            depth += 1
        else:
            depth = max(0, depth - 1)
        pos = m.end()
    tail = tex[pos:]
    if depth == 0:
        tail = _sanitize_orphan_chunk(tail)
    parts.append(tail)
    return "".join(parts)


def _sanitize_orphan_chunk(chunk: str) -> str:
    chunk = _ORPHAN_RULE.sub("", chunk)
    # Escape bare & only (keep already-escaped \&).
    return re.sub(r"(?<!\\)&", r"\\&", chunk)
