"""Patch one TeX prose paragraph from Liber Preview edit, then rebuild docs."""

from __future__ import annotations

import json
import logging
import re
import time
from pathlib import Path
from typing import Any

from case3.render import RenderError
from case3.run_rebuild import rebuild_run_docs
from case3.tex_preview import find_heading_spans, find_paragraph_spans
from case3.tex_safe import escape_tex_text

log = logging.getLogger("case3.paragraph_edit")

_MAX_CHARS = 12_000
_MD_BOLD = re.compile(r"\*\*([^*]+)\*\*")
_MD_ITALIC = re.compile(r"(?<!\*)\*([^*]+)\*(?!\*)")
_INLINE_MATH = re.compile(r"(?<!\\)\$([^$\n]+)\$")


class ParagraphEditError(RuntimeError):
    pass


def format_prose_to_tex(text: str) -> str:
    """Format plain prose to TeX, preserving inline math $...$, converting **bold** to \\textbf and *italic* to \\emph."""
    if not text:
        return ""
    stashed: list[str] = []

    def repl_math(m: re.Match[str]) -> str:
        idx = len(stashed)
        inner = m.group(1)
        stashed.append(f"${inner}$")
        return f"\x00MD{idx}\x00"

    def repl_bold(m: re.Match[str]) -> str:
        idx = len(stashed)
        inner = escape_tex_text(m.group(1))
        stashed.append(rf"\textbf{{{inner}}}")
        return f"\x00MD{idx}\x00"

    def repl_italic(m: re.Match[str]) -> str:
        idx = len(stashed)
        inner = escape_tex_text(m.group(1))
        stashed.append(rf"\emph{{{inner}}}")
        return f"\x00MD{idx}\x00"

    s = _INLINE_MATH.sub(repl_math, text)
    s = _MD_BOLD.sub(repl_bold, s)
    s = _MD_ITALIC.sub(repl_italic, s)
    escaped = escape_tex_text(s)
    for idx, repl in enumerate(stashed):
        escaped = escaped.replace(f"\x00MD{idx}\x00", repl)
    return escaped


def validate_paragraph_text(text: str, *, allow_empty: bool = False) -> str:
    t = (text or "").strip()
    if not allow_empty and len(t) < 1:
        raise ParagraphEditError("текст абзаца пуст")
    if len(t) > _MAX_CHARS:
        raise ParagraphEditError(f"слишком длинный абзац (макс. {_MAX_CHARS})")
    return t


def serialize_paragraph_tex(text: str, *, allow_empty: bool = False) -> str:
    """Plain Liber prose → TeX (blank lines → separate paragraphs, or empty string to delete)."""
    t = validate_paragraph_text(text, allow_empty=allow_empty)
    if not t:
        return ""
    parts = [p.strip() for p in re.split(r"\n\s*\n", t) if p.strip()]
    if not parts:
        return ""
    return "\n\n".join(format_prose_to_tex(p) for p in parts)


def patch_paragraph_in_tex(
    tex: str, paragraph_index: int, text: str, *, allow_delete: bool = False
) -> str:
    """Replace the ``paragraph_index``-th (1-based) preview paragraph."""
    new_tex_body = serialize_paragraph_tex(text, allow_empty=allow_delete)
    spans = find_paragraph_spans(tex)
    if paragraph_index < 1 or paragraph_index > len(spans):
        raise ParagraphEditError(
            f"абзац {paragraph_index} не найден (всего {len(spans)})"
        )
    start, end = spans[paragraph_index - 1]
    if not new_tex_body:
        if not allow_delete:
            raise ParagraphEditError("текст абзаца пуст")
        tail = tex[end:]
        head = tex[:start]
        if tail.startswith("\n\n"):
            tail = tail[2:]
        elif tail.startswith("\n") and head.endswith("\n"):
            tail = tail[1:]
        return head + tail
    return tex[:start] + new_tex_body + tex[end:]


def insert_paragraph_in_tex(
    tex: str,
    *,
    text: str,
    after_paragraph_index: int | None = None,
    after_heading_index: int | None = None,
) -> str:
    """Insert a new prose paragraph in TeX after a given paragraph or heading."""
    body = serialize_paragraph_tex(text, allow_empty=False)
    if not body:
        raise ParagraphEditError("текст абзаца пуст")

    if after_paragraph_index is not None and after_paragraph_index > 0:
        spans = find_paragraph_spans(tex)
        if after_paragraph_index > len(spans):
            raise ParagraphEditError(
                f"абзац {after_paragraph_index} не найден (всего {len(spans)})"
            )
        _, end = spans[after_paragraph_index - 1]
        return tex[:end] + "\n\n" + body + tex[end:]

    if after_heading_index is not None and after_heading_index > 0:
        hspans = find_heading_spans(tex)
        if after_heading_index > len(hspans):
            raise ParagraphEditError(
                f"заголовок {after_heading_index} не найден (всего {len(hspans)})"
            )
        _, end = hspans[after_heading_index - 1]
        return tex[:end] + "\n\n" + body + tex[end:]

    if r"\end{document}" in tex:
        idx = tex.rfind(r"\end{document}")
        return tex[:idx].rstrip() + "\n\n" + body + "\n\n" + tex[idx:]

    return tex.rstrip() + "\n\n" + body + "\n"


def insert_paragraph_in_run(
    out_dir: Path,
    *,
    text: str,
    after_paragraph_index: int | None = None,
    after_heading_index: int | None = None,
    formats: set[str] | None = None,
) -> dict[str, Any]:
    """Insert a new paragraph in TeX and rebuild PDF/DOCX."""
    out_dir = out_dir.resolve()
    validate_paragraph_text(text, allow_empty=False)

    texs = sorted(out_dir.glob("*.tex"))
    if not texs:
        raise ParagraphEditError("no .tex in run")
    from case3.run_undo import capture_before_edit

    target_str = (
        f"p:{after_paragraph_index}"
        if after_paragraph_index
        else f"h:{after_heading_index}"
        if after_heading_index
        else "eof"
    )
    capture_before_edit(out_dir, kind="paragraph_insert", target=target_str)
    tex_path = texs[0]
    tex_bak = tex_path.read_text(encoding="utf-8")

    meta_path = out_dir / "meta.json"
    meta_bak = meta_path.read_text(encoding="utf-8") if meta_path.is_file() else None

    try:
        patched = insert_paragraph_in_tex(
            tex_bak,
            text=text,
            after_paragraph_index=after_paragraph_index,
            after_heading_index=after_heading_index,
        )
        tex_path.write_text(patched, encoding="utf-8")
    except ParagraphEditError:
        raise
    except Exception as exc:  # noqa: BLE001
        raise ParagraphEditError(f"insert failed: {exc}") from exc

    from case3.run_events import write_meta_atomic
    from case3.run_meta import update_meta

    def _mut_para_ins(m: dict[str, Any]) -> None:
        m["last_paragraph_insert"] = {
            "after_p": after_paragraph_index,
            "after_h": after_heading_index,
            "chars": len(text or ""),
            "preview": (text or "")[:240],
            "ts": int(time.time()),
        }

    meta = update_meta(out_dir, _mut_para_ins)

    try:
        artifacts = rebuild_run_docs(out_dir, formats=formats)
    except FileNotFoundError as exc:
        raise ParagraphEditError(str(exc)) from exc
    except RenderError as exc:
        tex_path.write_text(tex_bak, encoding="utf-8")
        if meta_bak is not None:
            write_meta_atomic(meta_path, meta_bak)
        from case3.run_undo import clear_undo

        clear_undo(out_dir)
        raise ParagraphEditError(f"document rebuild failed: {exc}") from exc

    v = int(time.time())
    from case3.run_undo import undo_meta

    return {
        "after_paragraph_index": after_paragraph_index,
        "after_heading_index": after_heading_index,
        "text": text,
        "artifacts": {k: str(p) for k, p in artifacts.items()},
        "version": v,
        "media_status": meta.get("media_status") or {},
        "undo": undo_meta(out_dir),
    }


def edit_paragraph_in_run(
    out_dir: Path,
    paragraph_index: int,
    *,
    text: str,
    formats: set[str] | None = None,
) -> dict[str, Any]:
    """Patch TeX paragraph and rebuild PDF/DOCX."""
    out_dir = out_dir.resolve()
    validate_paragraph_text(text, allow_empty=True)

    texs = sorted(out_dir.glob("*.tex"))
    if not texs:
        raise ParagraphEditError("no .tex in run")
    from case3.run_undo import capture_before_edit

    capture_before_edit(out_dir, kind="paragraph", target=str(paragraph_index))
    tex_path = texs[0]
    tex_bak = tex_path.read_text(encoding="utf-8")

    meta_path = out_dir / "meta.json"
    meta_bak = meta_path.read_text(encoding="utf-8") if meta_path.is_file() else None

    try:
        patched = patch_paragraph_in_tex(
            tex_bak, paragraph_index, text, allow_delete=True
        )
        tex_path.write_text(patched, encoding="utf-8")
    except ParagraphEditError:
        raise
    except Exception as exc:  # noqa: BLE001
        raise ParagraphEditError(f"patch failed: {exc}") from exc

    from case3.run_events import write_meta_atomic
    from case3.run_meta import update_meta

    def _mut_para_edit(m: dict[str, Any]) -> None:
        m["last_paragraph_edit"] = {
            "index": paragraph_index,
            "chars": len(text or ""),
            "preview": (text or "")[:240],
            "ts": int(time.time()),
        }

    meta = update_meta(out_dir, _mut_para_edit)

    try:
        artifacts = rebuild_run_docs(out_dir, formats=formats)
    except FileNotFoundError as exc:
        raise ParagraphEditError(str(exc)) from exc
    except RenderError as exc:
        tex_path.write_text(tex_bak, encoding="utf-8")
        if meta_bak is not None:
            write_meta_atomic(meta_path, meta_bak)
        from case3.run_undo import clear_undo

        clear_undo(out_dir)
        raise ParagraphEditError(f"document rebuild failed: {exc}") from exc

    v = int(time.time())
    from case3.run_undo import undo_meta

    return {
        "paragraph_index": paragraph_index,
        "text": text,
        "artifacts": {k: str(p) for k, p in artifacts.items()},
        "version": v,
        "media_status": meta.get("media_status") or {},
        "undo": undo_meta(out_dir),
    }
