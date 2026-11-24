"""Replace %CASE3_FIG / %CASE3_CHART slots with figure envs or strip them."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from case3.tex_preamble import ensure_document_preamble, strip_orphan_slots
from case3.tex_safe import escape_tex_text, sanitize_width

# Consume the whole line so LLM notes after the slot (`% … %  (caption hint)`) disappear.
_FIG_SLOT = re.compile(
    r"(?m)^[ \t]*%CASE3_FIG:([a-z][a-z0-9_]{0,31})%[^\n]*\r?\n?"
)
_CHART_SLOT = re.compile(
    r"(?m)^[ \t]*%CASE3_CHART:([a-z][a-z0-9_]{0,31})%[^\n]*\r?\n?"
)
_DIAG_SLOT = re.compile(
    r"(?m)^[ \t]*%CASE3_DIAG:([a-z][a-z0-9_]{0,31})%[^\n]*\r?\n?"
)
_CONCLUSION_SECTION = re.compile(
    r"(?m)^[ \t]*\\section\*?\{[^\}]*(?:заключен|вывод|итог|рекомендац|conclusion|summary)[^\}]*\}",
    re.I,
)
# Model sometimes wraps a slot in figure; after a failed chart we must drop the shell.
_EMPTY_FIGURE = re.compile(
    r"\\begin\{figure\}(?:\[[^\]]*\])?\{?\}?\s*"
    r"(?:\\centering\s*)?"
    r"(?:\\caption\{[^}]*\}\s*)?"
    r"(?:\\label\{[^}]*\}\s*)?"
    r"\\end\{figure\}\s*",
    re.S,
)
_EMPTY_FIGURE_LOOSE = re.compile(
    r"\\begin\{figure\}.*?\\end\{figure\}",
    re.S,
)
# LLM puts the slot *inside* includegraphics — TeX then treats % as comment and
# eats the closing ``}`` (Gin@ii / runaway caption cascade). Line-anchored slot
# inject misses these.
_INLINE_SLOT_INCLUDEGRAPHICS = re.compile(
    r"\\includegraphics(\[[^\]]*\])?\{%CASE3_(?:FIG|CHART|DIAG):([a-z][a-z0-9_]{0,31})%\}",
    re.I,
)
# LLM sometimes writes \includegraphics{fig_02.png} instead of a CASE3 slot.
_MEDIA_INCLUDEGRAPHICS = re.compile(
    r"\\includegraphics(\[[^\]]*\])?\{(?:figures/)?((?:fig|cht|dia|usr)_[a-z0-9_]+)\.png\}",
    re.I,
)
# Diagrams in TeX: captured with dia_ id for unapproved strip.
_DIAG_INCLUDEGRAPHICS = re.compile(
    r"\\includegraphics(\[[^\]]*\])?\{((?:figures/)?(dia_[a-z0-9_]+)\.png)\}",
    re.I,
)
# Any relative PNG include — used only for missing-file soft strip.
_ANY_PNG_INCLUDEGRAPHICS = re.compile(
    r"\\includegraphics(\[[^\]]*\])?\{([^}]+\.png)\}",
    re.I,
)


def rewrite_inline_slot_includegraphics(tex: str, *, rel_dir: str = "figures") -> str:
    """``\\includegraphics{…%CASE3_FIG:id%}`` → ``figures/id.png`` (before latexmk)."""

    def _repl(m: re.Match[str]) -> str:
        opts = m.group(1) or ""
        mid = m.group(2)
        return f"\\includegraphics{opts}{{{rel_dir}/{mid}.png}}"

    return _INLINE_SLOT_INCLUDEGRAPHICS.sub(_repl, tex or "")


def rewrite_media_includegraphics_paths(tex: str, *, rel_dir: str = "figures") -> str:
    """Force media PNG paths under ``rel_dir/`` and constrain diagram sizes."""

    def _repl(m: re.Match[str]) -> str:
        opts = m.group(1) or ""
        mid = m.group(2)
        if mid.startswith("dia_"):
            opts = r"[width=\linewidth,height=0.38\textheight,keepaspectratio]"
        return f"\\includegraphics{opts}{{{rel_dir}/{mid}.png}}"

    return _MEDIA_INCLUDEGRAPHICS.sub(_repl, tex or "")


def strip_diagram_includegraphics(tex: str, status: dict[str, Any] | None = None) -> str:
    """Drop diagram PNG includes unless explicitly marked ok in status."""
    if status is None:
        return _DIAG_INCLUDEGRAPHICS.sub("", tex or "")
    ok_ids = {
        mid
        for mid, st in status.items()
        if isinstance(st, dict) and st.get("ok")
    }

    def _repl(m: re.Match[str]) -> str:
        did = m.group(3)
        if did in ok_ids:
            return m.group(0)
        return ""

    return _DIAG_INCLUDEGRAPHICS.sub(_repl, tex or "")


def strip_failed_media_includes(tex: str, status: dict[str, Any]) -> str:
    """Remove \\includegraphics for media ids marked not ok in status."""
    failed = {
        mid
        for mid, st in (status or {}).items()
        if isinstance(st, dict) and not st.get("ok")
    }
    if not failed or not tex:
        return tex or ""

    def _repl(m: re.Match[str]) -> str:
        mid = m.group(2)
        if mid in failed:
            return ""
        return m.group(0)

    return _MEDIA_INCLUDEGRAPHICS.sub(_repl, tex)


def _drop_hollow_figures(tex: str) -> str:
    """Remove figure envs that no longer contain includegraphics / TikZ / tables."""

    def _drop(m: re.Match[str]) -> str:
        body = m.group(0)
        if r"\includegraphics" in body:
            return body
        if re.search(
            r"\\begin\{(?:tikzpicture|tabularx|tabular|minipage)\}", body
        ):
            return body
        return ""

    return _EMPTY_FIGURE_LOOSE.sub(_drop, tex or "")


def _graphic_file_ok(path: Path) -> bool:
    """True when XeLaTeX graphicx can read the file. A ``.png`` that is BMP is not."""
    try:
        head = path.read_bytes()[:8]
    except OSError:
        return False
    if head.startswith(b"\x89PNG\r\n\x1a\n"):
        return True
    if head.startswith(b"\xff\xd8\xff"):
        return True
    if head.startswith(b"%PDF"):
        return True
    return False


def strip_missing_media_includes(tex: str, work_dir: Path) -> str:
    """Remove \\includegraphics{…png} whose file is absent under ``work_dir``.

    Soft safety net before latexmk (avoids graphics Division-by-0). Covers
    fig_/cht_/usr_ and leaked dia_* / bare paths.
    """
    root = Path(work_dir)
    if not tex:
        return tex or ""

    def _repl(m: re.Match[str]) -> str:
        rel = (m.group(2) or "").strip()
        if not rel or rel.startswith("/") or rel.startswith("\\"):
            return m.group(0)
        parts = Path(rel).parts
        if ".." in parts:
            return m.group(0)
        path = root / rel
        if path.is_file() and _graphic_file_ok(path):
            return m.group(0)
        return ""

    out = _ANY_PNG_INCLUDEGRAPHICS.sub(_repl, tex)
    return _drop_hollow_figures(out)


def _includegraphics_line(
    fid: str,
    meta: dict[str, Any],
    *,
    rel_dir: str,
    label_prefix: str = "fig",
) -> str:
    path = f"{rel_dir}/{fid}.png"
    if label_prefix == "dia" or fid.startswith("dia_"):
        return f"  \\includegraphics[width=\\linewidth,height=0.38\\textheight,keepaspectratio]{{{path}}}\n"
    default_w = r"0.85\linewidth"
    width = sanitize_width(meta.get("width")) if meta.get("width") else default_w
    return f"  \\includegraphics[width={width},height=0.45\\textheight,keepaspectratio]{{{path}}}\n"


def _figure_env(
    fid: str,
    meta: dict[str, Any],
    *,
    rel_dir: str,
    label_prefix: str,
) -> str:
    caption = escape_tex_text(str(meta.get("caption") or meta.get("title") or fid))
    return (
        "\\begin{figure}[H]\n"
        "  \\centering\n"
        + _includegraphics_line(fid, meta, rel_dir=rel_dir, label_prefix=label_prefix)
        + f"  \\caption{{{caption}}}\n"
        f"  \\label{{{label_prefix}:{fid}}}\n"
        "\\end{figure}\n"
    )


def _enclosing_figure_span(tex: str, start: int) -> tuple[int, int] | None:
    """Return [begin, end_after) of the figure env containing ``start``, if any."""
    begin = tex.rfind(r"\begin{figure}", 0, start)
    end_before = tex.rfind(r"\end{figure}", 0, start)
    if begin == -1 or begin < end_before:
        return None
    end = tex.find(r"\end{figure}", start)
    if end == -1:
        return None
    return begin, end + len(r"\end{figure}")


def _slot_inside_figure(tex: str, start: int) -> bool:
    """True if match start sits between \\begin{figure} and \\end{figure}."""
    return _enclosing_figure_span(tex, start) is not None


def _inner_slot_replacement(
    tex: str,
    start: int,
    fid: str,
    meta: dict[str, Any],
    *,
    rel_dir: str,
    label_prefix: str,
) -> str:
    """Inside an existing figure: image + caption/label if the shell has none."""
    body = _includegraphics_line(fid, meta, rel_dir=rel_dir, label_prefix=label_prefix)
    span = _enclosing_figure_span(tex, start)
    if span is None:
        return body
    shell = tex[span[0] : span[1]]
    if r"\caption" in shell:
        return body
    caption = escape_tex_text(str(meta.get("caption") or meta.get("title") or fid))
    return (
        body
        + f"  \\caption{{{caption}}}\n"
        + f"  \\label{{{label_prefix}:{fid}}}\n"
    )


def inject_media(
    tex: str,
    figures: list[dict[str, Any]],
    charts: list[dict[str, Any]],
    status: dict[str, Any],
    *,
    rel_dir: str = "figures",
    diagrams: list[dict[str, Any]] | None = None,
) -> str:
    by_fig = {f["id"]: f for f in figures}
    by_chart = {c["id"]: c for c in charts}
    by_diag = {d["id"]: d for d in (diagrams or [])}

    existing_includes = {
        m.group(2)
        for m in _MEDIA_INCLUDEGRAPHICS.finditer(tex or "")
    }
    seen_fig_ids: set[str] = set(existing_includes)
    seen_chart_ids: set[str] = set(existing_includes)
    seen_diag_ids: set[str] = set(existing_includes)

    def repl_fig(m: re.Match[str]) -> str:
        fid = m.group(1)
        if fid in seen_fig_ids:
            return ""
        st = status.get(fid) or {}
        meta = by_fig.get(fid)
        if not st.get("ok") or not meta:
            return ""
        seen_fig_ids.add(fid)
        if _slot_inside_figure(tex, m.start()):
            return _inner_slot_replacement(
                tex, m.start(), fid, meta, rel_dir=rel_dir, label_prefix="fig"
            )
        return _figure_env(fid, meta, rel_dir=rel_dir, label_prefix="fig")

    out = _FIG_SLOT.sub(repl_fig, tex)

    def repl_chart(m: re.Match[str]) -> str:
        cid = m.group(1)
        if cid in seen_chart_ids:
            return ""
        st = status.get(cid) or {}
        meta = by_chart.get(cid)
        if not st.get("ok") or not meta:
            return ""
        seen_chart_ids.add(cid)
        # Positions are relative to `out` (post-figure inject), not original `tex`.
        if _slot_inside_figure(out, m.start()):
            return _inner_slot_replacement(
                out, m.start(), cid, meta, rel_dir=rel_dir, label_prefix="chart"
            )
        return _figure_env(cid, meta, rel_dir=rel_dir, label_prefix="chart")

    out = _CHART_SLOT.sub(repl_chart, out)

    def repl_diag(m: re.Match[str]) -> str:
        did = m.group(1)
        if did in seen_diag_ids:
            return ""
        st = status.get(did) or {}
        meta = by_diag.get(did)
        if not st.get("ok") or not meta:
            return ""
        seen_diag_ids.add(did)
        if _slot_inside_figure(out, m.start()):
            return _inner_slot_replacement(
                out, m.start(), did, meta, rel_dir=rel_dir, label_prefix="dia"
            )
        return _figure_env(did, meta, rel_dir=rel_dir, label_prefix="dia")

    out = _DIAG_SLOT.sub(repl_diag, out)

    # Fallback placement for diagrams that were not slotted in TeX
    fallback_envs: list[str] = []
    for diag in diagrams or []:
        did = diag.get("id")
        if not did:
            continue
        st = status.get(did) or {}
        if not st.get("ok"):
            continue
        if did in out:
            continue
        fallback_envs.append(_figure_env(did, diag, rel_dir=rel_dir, label_prefix="dia"))

    if fallback_envs:
        fallback_block = "\n" + "\n".join(fallback_envs)
        concl_match = _CONCLUSION_SECTION.search(out)
        if concl_match:
            idx = concl_match.start()
            out = out[:idx] + fallback_block + "\n" + out[idx:]
        elif r"\end{document}" in out:
            idx = out.rfind(r"\end{document}")
            out = out[:idx] + fallback_block + "\n" + out[idx:]
        else:
            out = out + "\n" + fallback_block

    # Before orphan strip: heal slots trapped inside \\includegraphics{…%…%}.
    out = rewrite_inline_slot_includegraphics(out, rel_dir=rel_dir)
    out = strip_orphan_slots(out)
    out = rewrite_media_includegraphics_paths(out, rel_dir=rel_dir)
    out = strip_failed_media_includes(out, status)
    out = strip_diagram_includegraphics(out, status)
    out = _drop_hollow_figures(out)
    out = ensure_document_preamble(out)
    return out


def write_injected(
    tex_path: Path,
    figures: list[dict[str, Any]],
    status: dict[str, Any],
    *,
    charts: list[dict[str, Any]] | None = None,
    diagrams: list[dict[str, Any]] | None = None,
) -> Path:
    backup_path = tex_path.with_name(f"{tex_path.stem}.uninjected.tex")
    if backup_path.is_file():
        raw = backup_path.read_text(encoding="utf-8")
    else:
        raw = tex_path.read_text(encoding="utf-8")
        backup_path.write_text(raw, encoding="utf-8")
    new = inject_media(raw, figures, charts or [], status, diagrams=diagrams)
    tex_path.write_text(new, encoding="utf-8")
    return tex_path
