"""Post-LLM prose harden: obvious bullet lines → itemize (PDF task 4)."""

from __future__ import annotations

import re

# LLM often closes \\textbf{…} with Markdown ** — microtype then sees \\par
# inside an unfinished argument (Runaway argument / MT@prot@check@F@).
_TEXTBF_MARKDOWN_CLOSE = re.compile(
    r"\\textbf\{([^{}\n]*?)\*\*(?!\*)",
)
_MARKDOWN_BOLD = re.compile(r"(?<!\\)\*\*([^*\n]{1,200}?)\*\*")


_ITEM_OR_END = re.compile(r"\n[ \t]*\\(item|end|begin|section|subsection|chapter)\b")


def fix_unclosed_textbf(tex: str) -> str:
    """Close ``\\textbf{…`` that never gets ``}`` before next ``\\item`` / env / EOF.

    LLM often drops the closing brace mid-question; microtype then runaway-parses
    into the rest of the document (``MT@prot@check@F@`` / fake enumerate error).
    """
    if not tex or r"\textbf{" not in tex:
        return tex
    out: list[str] = []
    i = 0
    needle = r"\textbf{"
    while i < len(tex):
        if tex.startswith(needle, i):
            out.append(needle)
            i += len(needle)
            depth = 1
            while i < len(tex) and depth > 0:
                ch = tex[i]
                if ch == "{":
                    depth += 1
                    out.append(ch)
                    i += 1
                elif ch == "}":
                    depth -= 1
                    out.append(ch)
                    i += 1
                elif ch == "\n" and depth == 1:
                    # Next structural token → close bold before it.
                    if _ITEM_OR_END.match(tex, i) or tex.startswith("\n\n", i):
                        out.append("}")
                        depth = 0
                        break
                    out.append(ch)
                    i += 1
                else:
                    out.append(ch)
                    i += 1
            if depth > 0:
                out.append("}")
        else:
            out.append(tex[i])
            i += 1
    return "".join(out)


# \\section / \\subsection go through \\@dblarg → \\@xdblarg. Missing ``}`` yields
# ``File ended while scanning use of \\@xdblarg`` (latexmk exit 12).
_HEADING_OPEN = re.compile(
    r"\\(chapter|section|subsection|subsubsection|paragraph)\*?\{"
)


def fix_unclosed_heading_args(tex: str) -> str:
    """Close ``\\section{…`` / ``\\subsection{…`` when the brace never closes.

    Titles are single-line in our reports: at depth 1, a newline ends the title.
    """
    if not tex or not _HEADING_OPEN.search(tex):
        return tex
    out: list[str] = []
    i = 0
    while i < len(tex):
        m = _HEADING_OPEN.match(tex, i)
        if not m:
            out.append(tex[i])
            i += 1
            continue
        out.append(m.group(0))
        i = m.end()
        depth = 1
        while i < len(tex) and depth > 0:
            ch = tex[i]
            if ch == "{":
                depth += 1
                out.append(ch)
                i += 1
            elif ch == "}":
                depth -= 1
                out.append(ch)
                i += 1
            elif ch == "\n" and depth == 1:
                out.append("}")
                depth = 0
                break
            else:
                out.append(ch)
                i += 1
        if depth > 0:
            out.append("}")
    return "".join(out)


# Unclosed \\caption{…} → runaway + \\Gin@iii / figure ended by \\end{document}.
_CAPTION_OPEN = re.compile(r"\\caption\*?\{")
_CAPTION_STOP = re.compile(
    r"\n[ \t]*\\"
    r"(end\{(?:figure|table|document)\}|label\{|begin\{|caption\b|"
    r"includegraphics\b|section\b|subsection\b|chapter\b)"
)


def fix_unclosed_caption_args(tex: str) -> str:
    """Close ``\\caption{…`` before float end / blank line / next structural cmd."""
    if not tex or not _CAPTION_OPEN.search(tex):
        return tex
    out: list[str] = []
    i = 0
    while i < len(tex):
        m = _CAPTION_OPEN.match(tex, i)
        if not m:
            out.append(tex[i])
            i += 1
            continue
        out.append(m.group(0))
        i = m.end()
        depth = 1
        while i < len(tex) and depth > 0:
            ch = tex[i]
            if ch == "{":
                depth += 1
                out.append(ch)
                i += 1
            elif ch == "}":
                depth -= 1
                out.append(ch)
                i += 1
            elif ch == "\n" and depth == 1:
                if tex.startswith("\n\n", i) or _CAPTION_STOP.match(tex, i):
                    out.append("}")
                    depth = 0
                    break
                out.append(ch)
                i += 1
            else:
                out.append(ch)
                i += 1
        if depth > 0:
            out.append("}")
    return "".join(out)


_FLOAT_ENVS = ("figure", "table")


def fix_unclosed_float_envs(tex: str) -> str:
    """Insert missing ``\\end{figure|table}`` immediately before ``\\end{document}``."""
    if not tex or r"\end{document}" not in tex:
        return tex
    end_doc = tex.rfind(r"\end{document}")
    head = tex[:end_doc]
    tail = tex[end_doc:]
    closes: list[str] = []
    for env in _FLOAT_ENVS:
        opens = len(re.findall(rf"\\begin\{{{env}\}}", head))
        ends = len(re.findall(rf"\\end\{{{env}\}}", head))
        for _ in range(max(0, opens - ends)):
            closes.append(f"\\end{{{env}}}")
    if not closes:
        return tex
    return head.rstrip() + "\n" + "\n".join(closes) + "\n" + tail


def fix_markdown_bold_leaks(tex: str) -> str:
    """Repair ``\\textbf{…**``, leftover ``**…**``, and unclosed ``\\textbf{``."""
    if not tex:
        return tex
    out = tex
    if "**" in out:
        out = _TEXTBF_MARKDOWN_CLOSE.sub(r"\\textbf{\1}", out)
        out = _MARKDOWN_BOLD.sub(r"\\textbf{\1}", out)
    return fix_unclosed_textbf(out)


# Environments whose body must not be rewritten.
_SKIP_ENVS = (
    "itemize",
    "enumerate",
    "description",
    "tabular",
    "tabularx",
    "table",
    "figure",
    "verbatim",
    "lstlisting",
    "minted",
    "tikzpicture",
)

# Markdown ``* `` / ``- `` / ``• `` — LLM outline dumps use asterisks a lot.
_BULLET_LINE = re.compile(r"^([ \t]*)([-•*])\s+(\S.*)$")
_BEGIN_ENV = re.compile(r"\\begin\{([a-zA-Z*]+)\}")
_END_ENV = re.compile(r"\\end\{([a-zA-Z*]+)\}")
# Emoji / dingbats in \\section titles break Liber print look (Win desk 070133).
_EMOJI_IN_TITLE = re.compile(
    "["
    "\U0001F300-\U0001FAFF"  # symbols & pictographs
    "\U00002700-\U000027BF"  # dingbats
    "\U00002600-\U000026FF"  # misc symbols
    "\U0000FE0F"  # variation selector
    "]+",
)


def scrub_emoji_from_headings(tex: str) -> str:
    """Strip emoji from ``\\section{…}`` / ``\\subsection{…}`` titles."""
    if not tex or not _HEADING_OPEN.search(tex):
        return tex
    out: list[str] = []
    i = 0
    while i < len(tex):
        m = _HEADING_OPEN.match(tex, i)
        if not m:
            out.append(tex[i])
            i += 1
            continue
        out.append(m.group(0))
        i = m.end()
        depth = 1
        title_chars: list[str] = []
        while i < len(tex) and depth > 0:
            ch = tex[i]
            if ch == "{":
                depth += 1
                title_chars.append(ch)
                i += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    cleaned = _EMOJI_IN_TITLE.sub("", "".join(title_chars))
                    cleaned = re.sub(r"[ \t]{2,}", " ", cleaned).strip(" \t")
                    out.append(cleaned)
                    out.append("}")
                    i += 1
                else:
                    title_chars.append(ch)
                    i += 1
            else:
                title_chars.append(ch)
                i += 1
        if depth > 0:
            cleaned = _EMOJI_IN_TITLE.sub("", "".join(title_chars))
            out.append(cleaned)
            out.append("}")
    return "".join(out)


def unstar_headings(tex: str) -> str:
    """``\\section*{…}`` / ``\\subsection*{…}`` → numbered (deck twin + report).

    Win desk 083615: presentation TeX used 20 starred headings → no numbers in
    print twin. Product wants numbered structure in PDF/DOCX.
    """
    if not tex or r"section*{" not in tex:
        return tex
    out = re.sub(r"\\section\*\{", r"\\section{", tex)
    out = re.sub(r"\\subsection\*\{", r"\\subsection{", out)
    out = re.sub(r"\\subsubsection\*\{", r"\\subsubsection{", out)
    return out


# ``\item [Узел] $\rightarrow$ …`` — brackets are a diagram node, not a list label.
# LaTeX paints ``\item[...]`` in the margin; the first node is clipped off the page
# (Win desk source_20261103T090626Z).
_SCHEMA_ITEM = re.compile(
    r"^([ \t]*\\item)[ \t]*\[([^\]\n]*)\]([ \t]*\S.*)$"
)
_SCHEMA_FLOW = re.compile(
    r"\\(?:rightarrow|leftarrow|downarrow|uparrow)|(?:^|[^\]])\[[^\]\n]+\]"
)

_INCLUDEGRAPHICS = re.compile(
    r"\\includegraphics(\[(?P<opts>[^\]]*)\])?\{(?P<path>[^}]+)\}"
)


def normalize_includegraphics_aspect(tex: str) -> str:
    """Drop ``height=…`` from ``\\includegraphics`` so width-only keeps aspect (PDF)."""
    if not tex or r"\includegraphics" not in tex:
        return tex

    def repl(m: re.Match[str]) -> str:
        opts = m.group("opts") or ""
        path = m.group("path")
        if not opts or "height" not in opts:
            return m.group(0)
        if "keepaspectratio" in opts:
            # Bounding box width+height+keepaspectratio is intentional for tall figures/diagrams.
            return m.group(0)
        parts = [
            p.strip()
            for p in opts.split(",")
            if p.strip() and not p.strip().startswith("height=")
        ]
        if not parts:
            return rf"\includegraphics{{{path}}}"
        return rf"\includegraphics[{','.join(parts)}]{{{path}}}"

    return _INCLUDEGRAPHICS.sub(repl, tex)


def brace_schema_item_labels(tex: str) -> str:
    """Keep ``\\item [node] → …`` nodes in the line, not in the margin label."""
    if not tex or r"\item" not in tex:
        return tex
    out: list[str] = []
    for line in tex.splitlines(keepends=True):
        nl = ""
        body = line
        if body.endswith("\n"):
            nl = "\n"
            body = body[:-1]
            if body.endswith("\r"):
                nl = "\r\n"
                body = body[:-1]
        m = _SCHEMA_ITEM.match(body)
        if m and _SCHEMA_FLOW.search(m.group(3)):
            out.append(f"{m.group(1)} {{[{m.group(2)}]}}{m.group(3)}{nl}")
        else:
            out.append(line)
    return "".join(out)


def harden_prose_lists(tex: str) -> str:
    """Turn consecutive ``- `` / ``• `` / ``* `` lines outside skip-envs into itemize.

    Leaves existing itemize/enumerate/tabular bodies untouched. Idempotent.
    """
    if not tex or (
        "- " not in tex and "* " not in tex and "•" not in tex and "• " not in tex
    ):
        # Fast path: still allow "•foo" without space? require space via regex.
        if "•" not in tex and "- " not in tex and "* " not in tex:
            return tex

    lines = tex.splitlines(keepends=True)
    out: list[str] = []
    i = 0
    depth: list[str] = []

    def in_skip() -> bool:
        return any(e.rstrip("*") in _SKIP_ENVS for e in depth)

    while i < len(lines):
        line = lines[i]
        stripped = line.strip("\n")
        # Track env stack (best-effort; nested same-name ok).
        for m in _BEGIN_ENV.finditer(stripped):
            depth.append(m.group(1))
        for m in _END_ENV.finditer(stripped):
            name = m.group(1)
            for j in range(len(depth) - 1, -1, -1):
                if depth[j] == name:
                    del depth[j]
                    break

        if in_skip():
            out.append(line)
            i += 1
            continue

        m = _BULLET_LINE.match(stripped.rstrip("\r"))
        if not m:
            out.append(line)
            i += 1
            continue

        # Collect consecutive bullet lines at this depth.
        bullets: list[str] = []
        indent = m.group(1)
        while i < len(lines):
            raw = lines[i]
            s = raw.strip("\n").rstrip("\r")
            bm = _BULLET_LINE.match(s)
            if not bm:
                break
            # Don't advance env tracking twice — peek only bullets.
            bullets.append(bm.group(3).strip())
            i += 1

        if len(bullets) < 1:
            out.append(line)
            i += 1
            continue

        block = [f"{indent}\\begin{{itemize}}\n"]
        for item in bullets:
            block.append(f"{indent}\\item {item}\n")
        block.append(f"{indent}\\end{{itemize}}\n")
        out.extend(block)

    return "".join(out)


_EMPTY_LIST = re.compile(
    r"\\begin\{(itemize|enumerate)\}(?:\[[^\]]*\])?"
    r"((?:(?!\\begin\{(?:itemize|enumerate)\})(?!\\end\{\1\}).)*?)"
    r"\\end\{\1\}",
    re.IGNORECASE | re.DOTALL,
)


def drop_empty_lists(tex: str) -> str:
    """Drop itemize/enumerate that contain no \\item.

    An empty list is a hard XeLaTeX error (``missing \\item``) and latexmk
    then throws away a PDF it already wrote.
    """
    if not tex or r"\begin{itemize}" not in tex and r"\begin{enumerate}" not in tex:
        return tex or ""

    def _repl(match: re.Match[str]) -> str:
        if re.search(r"\\item\b", match.group(2)):
            return match.group(0)
        return ""

    out = tex
    for _ in range(8):
        nxt = _EMPTY_LIST.sub(_repl, out)
        if nxt == out:
            break
        out = nxt
    return out


_RU_PREP_WORDS = (
    "в", "во", "на", "с", "со", "к", "ко", "о", "об", "обо", "по", "из",
    "изо", "до", "не", "ни", "и", "а", "но", "за", "от", "ото", "у", "под",
    "подо", "над", "надо", "при", "без", "безо", "для", "сквозь", "через"
)

_RU_PREP_REGEX = re.compile(
    rf"(?<![a-zA-Zа-яА-ЯёЁ\\])"
    rf"(\b(?:{'|'.join(_RU_PREP_WORDS)}|{'|'.join(w.capitalize() for w in _RU_PREP_WORDS)}))"
    rf"[ \t]+"
    rf"(?=[а-яА-ЯёЁa-zA-Z0-9«\"\(])",
)

_RU_UNITS_INNER = (
    r"(?:млн(?:\s+руб\.?)?|млрд(?:\s+руб\.?)?|тыс\.?(?:\s+руб\.?)?|руб\.?|коп\.?|"
    r"долл\.?|евро|шт\.?|чел\.?|экз\.?|г\.|гг\.|года|годов|лет|мес\.?|дн\.?|ч\.?|"
    r"мин\.?|сек\.?|кв\.\s*м|м²|м³|см|мм|км|кг|т|%)"
)

_RU_UNITS_REGEX = re.compile(
    rf"(\b\d+(?:[.,]\d+)?)[ \t]+({_RU_UNITS_INNER})(?![a-zA-Zа-яА-ЯёЁ])",
    re.I,
)

_STRUCTURAL_MACROS = re.compile(
    r"\\(?:label|ref|pageref|cite|citep|citet|includegraphics|documentclass|usepackage|begin|end|input|include|url|href|hypersetup|definecolor|color|setlength|geometry|bibliographystyle|bibliography)\*?(?:\[[^\]]*\])?(?:\{[^{}]*\})?",
    re.I,
)


def harden_russian_typography(tex: str) -> str:
    """Bind short Russian prepositions/conjunctions and numeric units with ~."""
    if not tex:
        return tex

    # Only process body between \begin{document} and \end{document} if present
    begin_doc = tex.find(r"\begin{document}")
    end_doc = tex.rfind(r"\end{document}")
    if begin_doc != -1 and end_doc != -1 and end_doc > begin_doc:
        prefix = tex[: begin_doc + len(r"\begin{document}")]
        body = tex[begin_doc + len(r"\begin{document}") : end_doc]
        suffix = tex[end_doc:]
    else:
        prefix = ""
        body = tex
        suffix = ""

    stashed: list[str] = []

    def _stash(m: re.Match[str]) -> str:
        stashed.append(m.group(0))
        return f"\x00TYPO{len(stashed) - 1}\x00"

    # 1. Stash display math \[ ... \]
    body = re.sub(r"\\\[[\s\S]*?\\\]", _stash, body)
    # 2. Stash inline/display math $ ... $
    body = re.sub(r"(?<!\\)\${1,2}[\s\S]*?(?<!\\)\${1,2}", _stash, body)
    # 3. Stash table environments (non-breaking ~ unit chains inside narrow cells cause overflow)
    body = re.sub(
        r"\\begin\{(?P<tenv>tabularx?\*?|xltabular|longtable\*?)\}[\s\S]*?\\end\{(?P=tenv)\}",
        _stash,
        body,
    )
    # 4. Stash TeX comments
    body = re.sub(r"%.*$", _stash, body, flags=re.M)
    # 5. Stash structural TeX macros whose content must not change
    body = _STRUCTURAL_MACROS.sub(_stash, body)
    # 6. Stash other macro heads (e.g. \centering, \section, \item, \textbf)
    body = re.sub(r"\\[a-zA-Z]+\*?", _stash, body)

    def _repl_units(m: re.Match[str]) -> str:
        num = m.group(1)
        unit = re.sub(r"[ \t]+", "~", m.group(2))
        return f"{num}~{unit}"

    # Apply typography substitutions
    body = _RU_PREP_REGEX.sub(r"\1~", body)
    body = _RU_UNITS_REGEX.sub(_repl_units, body)
    body = re.sub(r"(?<!\.)\.\.(?!\.)", ".", body)

    # Restore stashed tokens in reverse
    for idx in range(len(stashed) - 1, -1, -1):
        body = body.replace(f"\x00TYPO{idx}\x00", stashed[idx])

    body = re.sub(r"(?<!\.)\.\.(?!\.)", ".", body)
    return prefix + body + suffix


_CYR_RUN = re.compile(r"[А-Яа-яЁё]+(?:[ \t~]*[А-Яа-яЁё]+)*")
_BARE_MATH_CMD = (
    ("div", "÷"),
    ("times", "×"),
    ("cdot", "·"),
    ("pm", "±"),
    ("leq", "≤"),
    ("le", "≤"),
    ("geq", "≥"),
    ("ge", "≥"),
    ("neq", "≠"),
    ("ne", "≠"),
    ("approx", "≈"),
    ("infty", "∞"),
    ("ldots", "…"),
    ("dots", "…"),
    ("rightarrow", "→"),
    ("leftarrow", "←"),
    ("to", "→"),
    ("gets", "←"),
)


def _unmask_text(chunk: str, texts: list[str]) -> str:
    def _one(m: re.Match[str]) -> str:
        return texts[int(m.group(1))]

    return re.sub(r"\x00T(\d+)\x00", _one, chunk)


def _lift_math_inner(inner: str) -> tuple[str, str] | None:
    """Return (kind, payload). kind is ``inner`` (same delimiters) or ``flat``.

    None means the span is already safe. Cyrillic in cmmi/cmr has no glyphs.
    """
    original = inner

    def _as_text(m: re.Match[str]) -> str:
        cmd, body = m.group(1), m.group(2)
        if cmd != "text" and re.search(r"[А-Яа-яЁё]", body):
            return r"\text{" + body + "}"
        return m.group(0)

    inner = re.sub(
        r"\\(mathrm|textrm|mbox|operatorname|text)\{([^{}]*)\}",
        _as_text,
        inner,
    )
    texts: list[str] = []

    def _mask(m: re.Match[str]) -> str:
        texts.append(m.group(0))
        return f"\x00T{len(texts) - 1}\x00"

    masked = re.sub(r"\\text\{([^{}]*)\}", _mask, inner)
    if not re.search(r"[А-Яа-яЁё]", masked):
        restored = _unmask_text(masked, texts)
        if restored == original:
            return None
        return ("inner", restored)

    parts = re.split(f"({_CYR_RUN.pattern})", masked)
    chunks: list[str] = []
    for part in parts:
        if not part:
            continue
        shown = _unmask_text(part, texts)
        if re.search(r"[А-Яа-яЁё]", shown):
            piece = shown
        elif shown.strip():
            piece = f"${shown.strip()}$"
        else:
            piece = shown
        if (
            chunks
            and piece
            and not chunks[-1].endswith((" ", "\n", "~"))
            and not piece.startswith((" ", "\n", "~"))
        ):
            chunks.append(" ")
        chunks.append(piece)
    return ("flat", "".join(chunks))


def _rewrite_math_spans(body: str) -> str:
    def _apply(pattern: str, opener: str, closer: str, src: str) -> str:
        def _repl(m: re.Match[str]) -> str:
            lifted = _lift_math_inner(m.group(1))
            if lifted is None:
                return m.group(0)
            kind, payload = lifted
            if kind == "inner":
                return opener + payload + closer
            return payload

        return re.sub(pattern, _repl, src)

    body = _apply(r"\\\[([\s\S]*?)\\\]", r"\[", r"\]", body)
    body = _apply(r"(?<!\\)\$\$([\s\S]*?)(?<!\\)\$\$", "$$", "$$", body)
    body = _apply(r"\\\(([\s\S]*?)\\\)", r"\(", r"\)", body)
    return _apply(r"(?<!\\)\$(?!\$)([^$]*?)(?<!\\)\$", "$", "$", body)


def _drop_unbalanced_dollar(body: str) -> str:
    idxs = [m.start() for m in re.finditer(r"(?<!\\)\$", body)]
    if len(idxs) % 2 == 0:
        return body
    i = idxs[-1]
    return body[:i] + body[i + 1 :]


def _replace_bare_math(body: str) -> str:
    """Math-only commands in prose are an undefined control sequence."""
    stashed: list[str] = []

    def _stash(m: re.Match[str]) -> str:
        stashed.append(m.group(0))
        return f"\x00M{len(stashed) - 1}\x00"

    body = re.sub(r"\\\[[\s\S]*?\\\]", _stash, body)
    body = re.sub(r"(?<!\\)\$\$[\s\S]*?(?<!\\)\$\$", _stash, body)
    body = re.sub(r"\\\([\s\S]*?\\\)", _stash, body)
    body = re.sub(r"(?<!\\)\$(?!\$)[^$]*?(?<!\\)\$", _stash, body)
    body = re.sub(r"\\text\{([^{}]*)\}", r"\1", body)
    body = re.sub(
        r"\\(?:d?frac|tfrac)\{([^{}]*)\}\{([^{}]*)\}",
        lambda m: f"${m.group(0)}$",
        body,
    )
    for name, glyph in _BARE_MATH_CMD:
        body = re.sub(rf"\\{name}\b", glyph, body)
    for idx in range(len(stashed) - 1, -1, -1):
        body = body.replace(f"\x00M{idx}\x00", stashed[idx])
    return body


def harden_math_prose(tex: str) -> str:
    """Keep Russian out of Computer Modern math and bare \\\\div out of prose.

    cmr/cmmi have no Cyrillic, and latexmk treats those missing glyphs as a
    failed run. ``\\div`` outside ``$...$`` is an undefined control sequence.
    """
    if not tex:
        return tex
    begin_doc = tex.find(r"\begin{document}")
    end_doc = tex.rfind(r"\end{document}")
    if begin_doc != -1 and end_doc != -1 and end_doc > begin_doc:
        prefix = tex[: begin_doc + len(r"\begin{document}")]
        body = tex[begin_doc + len(r"\begin{document}") : end_doc]
        suffix = tex[end_doc:]
    else:
        prefix, body, suffix = "", tex, ""
    body = _drop_unbalanced_dollar(body)
    body = _rewrite_math_spans(body)
    body = _replace_bare_math(body)
    return prefix + body + suffix

