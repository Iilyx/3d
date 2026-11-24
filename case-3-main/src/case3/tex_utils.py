"""Extract LaTeX from model output."""

from __future__ import annotations

import re

_FENCE = re.compile(r"```(\w*)\s*([\s\S]*?)```", re.I)

_MIN_PREAMBLE = r"""\documentclass[a4paper,12pt]{article}
\usepackage{fontspec}
\usepackage{polyglossia}
\usepackage{geometry}
\usepackage{booktabs}
\usepackage{tabularx}
\usepackage{longtable}
\usepackage{float}
\usepackage{graphicx}
\usepackage{setspace}
\usepackage{microtype}
\usepackage{titlesec}
\usepackage{fancyhdr}
\usepackage{caption}
\usepackage{pdflscape}
\usepackage{xcolor}
\usepackage{hyperref}
\setdefaultlanguage{russian}
\setotherlanguage{english}
\setmainfont{DejaVu Serif}
\setsansfont{DejaVu Sans}
\setmonofont{DejaVu Sans Mono}
\geometry{a4paper,margin=2.2cm}
"""


def _normalize_backslashes(text: str) -> str:
    """Models sometimes emit \\\\documentclass or unicode dashes — normalize."""
    t = text.replace("\u200b", "").replace("\ufeff", "")
    # Double-escaped TeX control words → single backslash
    t = re.sub(r"\\\\(documentclass|begin|end|usepackage|section)\b", r"\\\1", t)
    return t


def _looks_like_tex(body: str) -> bool:
    b = body or ""
    return r"\documentclass" in b or (
        r"\begin{document}" in b and r"\end{document}" in b
    )


def _ensure_documentclass(text: str) -> str:
    """If body has begin/end document but no class, prepend our preamble."""
    if r"\documentclass" in text:
        return text
    if r"\begin{document}" in text and r"\end{document}" in text:
        # Drop a leading title-only fragment before \begin{document}
        idx = text.find(r"\begin{document}")
        return _MIN_PREAMBLE + "\n" + text[idx:].lstrip()
    return text


def _drop_incomplete_trailing_envs(tex: str) -> str:
    """Cut from the last unclosed table/figure/tabular instead of emitting empty shells."""
    t = tex.rstrip()
    for env in (
        "table",
        "figure",
        "tabularx",
        "xltabular",
        "longtable",
        "landscape",
        "tabular",
        "itemize",
        "enumerate",
    ):
        begins = list(re.finditer(rf"\\begin\{{{env}\}}", t))
        if not begins:
            continue
        last = begins[-1]
        tail = t[last.start() :]
        if f"\\end{{{env}}}" not in tail:
            t = t[: last.start()].rstrip()
    return t


def _soft_close_truncated(tex: str) -> str:
    """Model often hits max tokens mid-doc: open ```latex, no \\end{document}.

    Drop incomplete trailing floats/tables, close leftover envs, then \\end{document}.
    """
    t = _drop_incomplete_trailing_envs(tex)
    last_line = t.rsplit("\n", 1)[-1]
    # Drop half-finished \\command… but never drop %CASE3_CHART / FIG slots.
    if re.search(r"\\[a-zA-Z]+$", last_line):
        t = t.rsplit("\n", 1)[0].rstrip()
    elif last_line.strip() == "%" or (
        last_line.rstrip().endswith("%")
        and "%CASE3_" not in last_line
        and len(last_line.strip()) < 3
    ):
        t = t.rsplit("\n", 1)[0].rstrip()
    for env in (
        "tabularx",
        "xltabular",
        "longtable",
        "tabular",
        "table",
        "landscape",
        "figure",
        "itemize",
        "enumerate",
    ):
        opens = len(re.findall(rf"\\begin\{{{env}\}}", t))
        closes = len(re.findall(rf"\\end\{{{env}\}}", t))
        for _ in range(max(0, opens - closes)):
            t += f"\n\\end{{{env}}}"
    if r"\end{document}" not in t:
        t += "\n\\end{document}"
    return t + "\n"


def finish_preamble_only_tex(
    tex: str,
    *,
    chart_ids: list[str] | None = None,
    figure_ids: list[str] | None = None,
    diagram_ids: list[str] | None = None,
    title: str = "Отчёт",
) -> str:
    """When the model truncates mid-preamble (has \\documentclass, no \\begin{document})."""
    from case3.tex_preamble import preamble_looks_broken

    t = (tex or "").rstrip()
    if r"\begin{document}" in t:
        return t if t.endswith("\n") else t + "\n"
    if r"\documentclass" not in t:
        raise ValueError("cannot finish preamble: no \\documentclass")
    # Truncated mid-package → discard and use the known-good min preamble.
    if preamble_looks_broken(t + "\n\\begin{document}\n\\end{document}\n"):
        t = _MIN_PREAMBLE.rstrip()
    else:
        # Drop incomplete last line (e.g. \\setotherlanguage{engl)
        last = t.rsplit("\n", 1)[-1]
        if last.count("{") != last.count("}") or re.search(r"\\[a-zA-Z]+$", last):
            t = t.rsplit("\n", 1)[0].rstrip()
    if r"\title{" not in t:
        t += f"\n\\title{{{title}}}\n\\author{{}}\n\\date{{\\today}}"
    body = ["\\begin{document}", "\\maketitle", ""]
    for fid in figure_ids or []:
        body.append(f"%CASE3_FIG:{fid}%")
        body.append("")
    for cid in chart_ids or []:
        body.append(f"%CASE3_CHART:{cid}%")
        body.append("")
    for did in diagram_ids or []:
        body.append(f"%CASE3_DIAG:{did}%")
        body.append("")
    body.append("\\end{document}")
    return t + "\n" + "\n".join(body) + "\n"


def extract_tex(raw: str) -> str:
    text = _normalize_backslashes((raw or "").strip())
    if not text:
        raise ValueError("empty model output")

    # Prefer fenced bodies that look like a full document
    candidates: list[str] = []
    for m in _FENCE.finditer(text):
        lang = (m.group(1) or "").lower()
        body = m.group(2).strip()
        if lang in ("latex", "tex") or (lang == "" and _looks_like_tex(body)):
            candidates.append(body)
        elif lang in ("",) and r"\begin{document}" in body:
            candidates.append(body)

    # Unclosed ```latex fence (truncation): take everything after the opener.
    if not candidates:
        m_open = re.match(r"```(?:latex|tex)?\s*\n([\s\S]*)", text, re.I)
        if m_open and _looks_like_tex(m_open.group(1)):
            candidates.append(m_open.group(1).strip())

    chosen = None
    for body in candidates:
        if r"\documentclass" in body:
            chosen = body
            break
    if chosen is None:
        for body in candidates:
            if r"\begin{document}" in body:
                chosen = body
                break
    if chosen is None and candidates:
        chosen = candidates[0]

    if chosen is not None:
        text = chosen
    else:
        # Unfenced: cut from first \documentclass if present
        idx = text.find(r"\documentclass")
        if idx >= 0:
            text = text[idx:]
        else:
            idx = text.find(r"\begin{document}")
            if idx >= 0:
                text = text[idx:]

    text = _ensure_documentclass(text.strip())

    if r"\documentclass" not in text:
        preview = (raw or "").strip().replace("\n", " ")[:240]
        raise ValueError(
            "no \\documentclass in model output "
            "(нужен полный LaTeX: ```latex … \\documentclass … \\end{document}```). "
            f"Начало ответа модели: {preview!r}"
        )
    if r"\begin{document}" not in text:
        raise ValueError("missing \\begin{document}")
    if r"\end{document}" not in text:
        # Truncated completion — recover instead of failing the whole run.
        text = _soft_close_truncated(text)
    return text.strip() + "\n"
