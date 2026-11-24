"""Patch one TeX section/subsection title from Liber Preview edit."""

from __future__ import annotations

import json
import logging
import re
import time
from pathlib import Path
from typing import Any

from case3.render import RenderError
from case3.run_rebuild import rebuild_run_docs
from case3.tex_preview import find_heading_spans
from case3.tex_safe import escape_tex_text

log = logging.getLogger("case3.heading_edit")

_MAX_CHARS = 400
_CMD = re.compile(r"^\\((?:sub)*section\*?)\{\s*([^{}]*)\}")
_TITLE_CMD = re.compile(r"(\\title\{)([^{}]*)(\})")


class HeadingEditError(RuntimeError):
    pass


def validate_heading_text(text: str, *, allow_empty: bool = False) -> str:
    t = (text or "").strip()
    if not allow_empty and len(t) < 1:
        raise HeadingEditError("заголовок пуст")
    if len(t) > _MAX_CHARS:
        raise HeadingEditError(f"слишком длинный заголовок (макс. {_MAX_CHARS})")
    if "\n" in t:
        raise HeadingEditError("заголовок должен быть одной строкой")
    return t


def patch_title_in_tex(tex: str, text: str) -> str:
    """Replace \\title{...} in document preamble."""
    title = validate_heading_text(text, allow_empty=False)
    if not _TITLE_CMD.search(tex or ""):
        raise HeadingEditError("команда \\title не найдена в документе")
    esc = escape_tex_text(title)
    return _TITLE_CMD.sub(rf"\g<1>{esc}\g<3>", tex, count=1)



def patch_heading_in_tex(
    tex: str, heading_index: int, text: str, *, allow_delete: bool = False
) -> str:
    """Replace the ``heading_index``-th (1-based) preview heading title, or delete if empty and allow_delete=True."""
    title = validate_heading_text(text, allow_empty=allow_delete)
    spans = find_heading_spans(tex)
    if heading_index < 1 or heading_index > len(spans):
        raise HeadingEditError(
            f"заголовок {heading_index} не найден (всего {len(spans)})"
        )
    start, end = spans[heading_index - 1]
    if not title:
        if not allow_delete:
            raise HeadingEditError("заголовок пуст")
        tail = tex[end:]
        head = tex[:start]
        if tail.startswith("\n\n"):
            tail = tail[1:]
        elif tail.startswith("\n") and head.endswith("\n"):
            tail = tail[1:]
        return head + tail
    old = tex[start:end]
    m = _CMD.match(old)
    if not m:
        raise HeadingEditError("не удалось разобрать команду заголовка")
    cmd = m.group(1)
    new_tok = "\\" + cmd + "{" + escape_tex_text(title) + "}"
    return tex[:start] + new_tok + tex[end:]


def edit_heading_in_run(
    out_dir: Path,
    heading_index: int,
    *,
    text: str,
    formats: set[str] | None = None,
) -> dict[str, Any]:
    """Patch TeX heading and rebuild PDF/DOCX."""
    out_dir = out_dir.resolve()
    validate_heading_text(text, allow_empty=True)

    texs = sorted(out_dir.glob("*.tex"))
    if not texs:
        raise HeadingEditError("no .tex in run")
    from case3.run_undo import capture_before_edit

    capture_before_edit(out_dir, kind="heading", target=str(heading_index))
    tex_path = texs[0]
    tex_bak = tex_path.read_text(encoding="utf-8")

    meta_path = out_dir / "meta.json"
    meta_bak = meta_path.read_text(encoding="utf-8") if meta_path.is_file() else None

    try:
        patched = patch_heading_in_tex(
            tex_bak, heading_index, text, allow_delete=True
        )
        tex_path.write_text(patched, encoding="utf-8")
    except HeadingEditError:
        raise
    except Exception as exc:  # noqa: BLE001
        raise HeadingEditError(f"patch failed: {exc}") from exc

    from case3.run_events import write_meta_atomic
    from case3.run_meta import update_meta

    def _mut_heading(m: dict[str, Any]) -> None:
        m["last_heading_edit"] = {
            "index": heading_index,
            "chars": len(text or ""),
            "preview": (text or "")[:240],
            "ts": int(time.time()),
        }

    meta = update_meta(out_dir, _mut_heading)

    try:
        artifacts = rebuild_run_docs(out_dir, formats=formats)
    except FileNotFoundError as exc:
        raise HeadingEditError(str(exc)) from exc
    except RenderError as exc:
        tex_path.write_text(tex_bak, encoding="utf-8")
        if meta_bak is not None:
            write_meta_atomic(meta_path, meta_bak)
        from case3.run_undo import clear_undo

        clear_undo(out_dir)
        raise HeadingEditError(f"document rebuild failed: {exc}") from exc

    v = int(time.time())
    from case3.run_undo import undo_meta

    return {
        "heading_index": heading_index,
        "text": text,
        "artifacts": {k: str(p) for k, p in artifacts.items()},
        "version": v,
        "media_status": meta.get("media_status") or {},
        "undo": undo_meta(out_dir),
    }


def edit_title_in_run(
    out_dir: Path,
    *,
    text: str,
    formats: set[str] | None = None,
) -> dict[str, Any]:
    """Patch \\title in document preamble and rebuild PDF/DOCX."""
    out_dir = out_dir.resolve()
    validate_heading_text(text)

    texs = sorted(out_dir.glob("*.tex"))
    if not texs:
        raise HeadingEditError("no .tex in run")
    from case3.run_undo import capture_before_edit

    capture_before_edit(out_dir, kind="title", target="doc")
    tex_path = texs[0]
    tex_bak = tex_path.read_text(encoding="utf-8")

    meta_path = out_dir / "meta.json"
    meta_bak = meta_path.read_text(encoding="utf-8") if meta_path.is_file() else None

    try:
        patched = patch_title_in_tex(tex_bak, text)
        tex_path.write_text(patched, encoding="utf-8")
    except HeadingEditError:
        raise
    except Exception as exc:  # noqa: BLE001
        raise HeadingEditError(f"patch failed: {exc}") from exc

    from case3.run_events import write_meta_atomic
    from case3.run_meta import update_meta

    def _mut_title(m: dict[str, Any]) -> None:
        m["last_title_edit"] = {
            "text": (text or "")[:240],
            "ts": int(time.time()),
        }

    meta = update_meta(out_dir, _mut_title)

    try:
        artifacts = rebuild_run_docs(out_dir, formats=formats)
    except FileNotFoundError as exc:
        raise HeadingEditError(str(exc)) from exc
    except RenderError as exc:
        tex_path.write_text(tex_bak, encoding="utf-8")
        if meta_bak is not None:
            write_meta_atomic(meta_path, meta_bak)
        from case3.run_undo import clear_undo

        clear_undo(out_dir)
        raise HeadingEditError(f"document rebuild failed: {exc}") from exc

    v = int(time.time())
    from case3.run_undo import undo_meta

    return {
        "title": text,
        "artifacts": {k: str(p) for k, p in artifacts.items()},
        "version": v,
        "media_status": meta.get("media_status") or {},
        "undo": undo_meta(out_dir),
    }

