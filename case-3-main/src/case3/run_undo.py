"""Session undo/redo stack for Liber in-run edits.

Snapshots live under ``out/.undo/``; each successful edit pushes a pre-edit
snapshot. Undo restores and parks the live state on a redo branch; a new edit
clears redo. Cap ``MAX_UNDO_DEPTH``. ``clear_undo`` wipes the session
(«Готово»).
"""

from __future__ import annotations

from case3.paths import repo_root

import json
import logging
import shutil
import time
import uuid
from pathlib import Path
from typing import Any

log = logging.getLogger("case3.run_undo")

MAX_UNDO_DEPTH = 40
_UNDO_DIR = ".undo"
_INDEX = "index.json"


class UndoError(RuntimeError):
    pass


def _undo_root(out_dir: Path) -> Path:
    return Path(out_dir).resolve() / _UNDO_DIR


def _index_path(out_dir: Path) -> Path:
    return _undo_root(out_dir) / _INDEX


def _read_json(path: Path) -> dict[str, Any]:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return raw if isinstance(raw, dict) else {}


def _write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _empty_index() -> dict[str, Any]:
    return {"stack": [], "redo": []}


def _load_index(out_dir: Path) -> dict[str, Any]:
    """Load stack index; migrate legacy one-slot ``manifest.json`` if present."""
    out = Path(out_dir).resolve()
    root = _undo_root(out)
    idx_path = _index_path(out)
    if idx_path.is_file():
        data = _read_json(idx_path)
        stack = data.get("stack")
        redo = data.get("redo")
        if not isinstance(stack, list):
            stack = []
        if not isinstance(redo, list):
            redo = []
        return {"stack": stack, "redo": redo}

    # Legacy B21: .undo/manifest.json + .undo/files/
    legacy_man = root / "manifest.json"
    legacy_files = root / "files"
    if legacy_man.is_file() and legacy_files.is_dir():
        man = _read_json(legacy_man)
        slot_id = "legacy"
        slot_dir = root / "slots" / slot_id
        if slot_dir.exists():
            shutil.rmtree(slot_dir, ignore_errors=True)
        slot_dir.mkdir(parents=True)
        shutil.move(str(legacy_files), str(slot_dir / "files"))
        _write_json(slot_dir / "manifest.json", man)
        try:
            legacy_man.unlink()
        except OSError:
            pass
        entry = {
            "id": slot_id,
            "kind": man.get("kind") or "edit",
            "target": str(man.get("target") or ""),
            "ts": int(man.get("ts") or time.time()),
        }
        idx = {"stack": [entry], "redo": []}
        _write_json(idx_path, idx)
        return idx
    return _empty_index()


def _save_index(out_dir: Path, index: dict[str, Any]) -> None:
    _write_json(_index_path(out_dir), index)


def _sync_meta_undo(out_dir: Path, index: dict[str, Any] | None = None) -> dict[str, Any] | None:
    """Write ``meta.undo`` public descriptor; return it (or None)."""
    out = Path(out_dir).resolve()
    if index is None:
        index = _load_index(out)
    stack = index.get("stack") or []
    redo = index.get("redo") or []
    can_undo = len(stack) > 0
    can_redo = len(redo) > 0
    from case3.run_meta import update_meta

    if not can_undo and not can_redo:
        meta_path = out / "meta.json"
        if meta_path.is_file():
            update_meta(out, lambda m: m.pop("undo", None))
        return None
    top = stack[-1] if can_undo else {}
    desc = {
        "kind": top.get("kind") if can_undo else None,
        "target": top.get("target") if can_undo else None,
        "ts": top.get("ts") if can_undo else None,
        "ready": can_undo,
        "can_undo": can_undo,
        "can_redo": can_redo,
        "depth": len(stack),
    }
    update_meta(out, lambda m: m.__setitem__("undo", desc))
    return desc


def undo_meta(out_dir: Path) -> dict[str, Any] | None:
    """Public undo/redo descriptor for API/UI."""
    out = Path(out_dir).resolve()
    index = _load_index(out)
    stack = index.get("stack") or []
    redo = index.get("redo") or []
    if not stack and not redo:
        # Prefer live meta if present
        meta = _read_json(out / "meta.json") if (out / "meta.json").is_file() else {}
        slot = meta.get("undo")
        if isinstance(slot, dict) and (
            slot.get("can_undo") or slot.get("can_redo") or slot.get("kind")
        ):
            # Stale — clear
            return _sync_meta_undo(out, index)
        return None
    return _sync_meta_undo(out, index)


def clear_undo(out_dir: Path) -> bool:
    """Remove undo/redo session + meta.undo. Returns True if something cleared."""
    out = Path(out_dir).resolve()
    root = _undo_root(out)
    had = root.is_dir()
    if root.is_dir():
        shutil.rmtree(root, ignore_errors=True)
    meta_path = out / "meta.json"
    if meta_path.is_file():
        meta = _read_json(meta_path)
        if "undo" in meta:
            meta.pop("undo", None)
            _write_json(meta_path, meta)
            had = True
    return bool(had)


# Alias for callers that prefer the session name.
clear_edit_history = clear_undo


def _rel_files_to_snapshot(out: Path) -> list[str]:
    rels: list[str] = []
    for name in ("figures.json", "meta.json", "diagrams.json"):
        if (out / name).is_file():
            rels.append(name)
    for tex in sorted(out.glob("*.tex")):
        if tex.is_file():
            rels.append(tex.name)
    figs = out / "figures"
    if figs.is_dir():
        for png in sorted(figs.glob("*.png")):
            if png.is_file() and png.stat().st_size > 0:
                rels.append(f"figures/{png.name}")
    slides = out / "slides"
    if slides.is_dir():
        for name in ("deck.json", "deck_ir.json"):
            p = slides / name
            if p.is_file():
                rels.append(f"slides/{name}")
        for sub in ("charts", "diagrams"):
            sub_dir = slides / sub
            if sub_dir.is_dir():
                for png in sorted(sub_dir.glob("*.png")):
                    if png.is_file() and png.stat().st_size > 0:
                        rels.append(f"slides/{sub}/{png.name}")
    return rels


def _write_snapshot(
    out: Path,
    slot_dir: Path,
    *,
    kind: str,
    target: str,
) -> dict[str, Any]:
    """Copy live out/ into slot_dir/files + manifest. Returns entry dict."""
    meta_live = _read_json(out / "meta.json") if (out / "meta.json").is_file() else {}
    meta_snap = dict(meta_live)
    meta_snap.pop("undo", None)

    if slot_dir.exists():
        shutil.rmtree(slot_dir, ignore_errors=True)
    files_dir = slot_dir / "files"
    files_dir.mkdir(parents=True)

    saved: list[str] = []
    for rel in _rel_files_to_snapshot(out):
        if rel == "meta.json":
            continue
        src = out / rel
        if not src.is_file():
            continue
        dest = files_dir / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dest)
        saved.append(rel)

    if meta_snap or (out / "meta.json").is_file():
        _write_json(files_dir / "meta.json", meta_snap)
        saved.append("meta.json")

    manifest = {
        "kind": (kind or "edit").strip() or "edit",
        "target": str(target or ""),
        "ts": int(time.time()),
        "files": saved,
    }
    _write_json(slot_dir / "manifest.json", manifest)
    return {
        "id": slot_dir.name,
        "kind": manifest["kind"],
        "target": manifest["target"],
        "ts": manifest["ts"],
    }


def _restore_slot(out: Path, slot_dir: Path) -> dict[str, Any]:
    man = _read_json(slot_dir / "manifest.json")
    files_dir = slot_dir / "files"
    rels = man.get("files")
    if not isinstance(rels, list) or not rels:
        raise UndoError("пустой undo snapshot")
    for rel in rels:
        if not isinstance(rel, str) or ".." in rel or rel.startswith(("/", "\\")):
            continue
        src = files_dir / rel
        if not src.is_file():
            continue
        dest = out / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dest)
    return {
        "kind": man.get("kind"),
        "target": man.get("target"),
        "ts": man.get("ts"),
    }


def _rm_slot(root: Path, entry: dict[str, Any]) -> None:
    sid = str(entry.get("id") or "")
    if not sid or ".." in sid:
        return
    slot = root / "slots" / sid
    if slot.is_dir():
        shutil.rmtree(slot, ignore_errors=True)


def _clear_branch(root: Path, entries: list[Any]) -> None:
    for e in entries:
        if isinstance(e, dict):
            _rm_slot(root, e)


def _maybe_rebuild(out: Path, info: dict[str, Any], *, rebuild: bool) -> None:
    artifacts: dict[str, Any] = {}
    if rebuild:
        from case3.render import RenderError, render_tex

        texs = sorted(out.glob("*.tex"))
        if texs:
            figs_dir = out / "figures"
            try:
                artifacts = render_tex(
                    texs[0],
                    out_dir=out,
                    formats={"pdf", "docx"},
                    extra_dirs=[figs_dir] if figs_dir.is_dir() else None,
                    log_dir=out / "logs",
                    force=True,
                    project_root=repo_root(),
                )
            except RenderError as exc:
                log.warning("undo restore ok but rebuild failed: %s", exc)
                info["rebuild_error"] = str(exc)

    # Twin/PPTX stay put unless this call asked to rebuild (Готово / rebuild=1).
    # Session undo passes rebuild=False and only restores the snapshotted files.
    if rebuild and (out / "slides" / "deck.json").is_file():
        try:
            from case3.deck_refresh import refresh_deck_from_ir

            if refresh_deck_from_ir(out):
                info["deck_refreshed"] = True
        except Exception as exc:  # noqa: BLE001
            log.warning("undo restore ok but deck refresh failed: %s", exc)
            info["deck_refresh_error"] = str(exc)

    info["artifacts"] = {k: str(v) for k, v in artifacts.items()} if artifacts else {}


def capture_before_edit(
    out_dir: Path,
    *,
    kind: str,
    target: str,
) -> dict[str, Any]:
    """Push a pre-edit snapshot; clear redo branch; trim to ``MAX_UNDO_DEPTH``."""
    out = Path(out_dir).resolve()
    if not out.is_dir():
        raise UndoError("run out_dir missing")

    root = _undo_root(out)
    root.mkdir(parents=True, exist_ok=True)
    index = _load_index(out)

    # New edit invalidates redo.
    _clear_branch(root, list(index.get("redo") or []))
    index["redo"] = []

    slot_id = uuid.uuid4().hex[:12]
    slot_dir = root / "slots" / slot_id
    entry = _write_snapshot(out, slot_dir, kind=kind, target=target)
    stack = list(index.get("stack") or [])
    stack.append(entry)

    while len(stack) > MAX_UNDO_DEPTH:
        old = stack.pop(0)
        _rm_slot(root, old)

    index["stack"] = stack
    _save_index(out, index)
    desc = _sync_meta_undo(out, index)
    log.info(
        "undo captured kind=%s target=%s depth=%d",
        kind,
        target,
        len(stack),
    )
    return {
        "kind": entry["kind"],
        "target": entry["target"],
        "ts": entry["ts"],
        **(desc or {}),
    }


def apply_undo(out_dir: Path, *, rebuild: bool = True) -> dict[str, Any]:
    """Pop stack → restore; park live state on redo."""
    out = Path(out_dir).resolve()
    root = _undo_root(out)
    index = _load_index(out)
    stack = list(index.get("stack") or [])
    if not stack:
        raise UndoError("нечего отменять")

    entry = stack.pop()
    slot_dir = root / "slots" / str(entry["id"])
    if not (slot_dir / "manifest.json").is_file():
        raise UndoError("нечего отменять")

    # Park current live on redo.
    redo_id = uuid.uuid4().hex[:12]
    redo_dir = root / "slots" / redo_id
    redo_entry = _write_snapshot(
        out,
        redo_dir,
        kind=str(entry.get("kind") or "edit"),
        target=str(entry.get("target") or ""),
    )
    redo = list(index.get("redo") or [])
    redo.append(redo_entry)

    info = _restore_slot(out, slot_dir)
    _rm_slot(root, entry)

    index["stack"] = stack
    index["redo"] = redo
    _save_index(out, index)
    _sync_meta_undo(out, index)
    _maybe_rebuild(out, info, rebuild=rebuild)
    # Re-sync after rebuild may rewrite meta.json
    _sync_meta_undo(out, index)
    log.info("undo applied kind=%s target=%s", info.get("kind"), info.get("target"))
    return info


def apply_redo(out_dir: Path, *, rebuild: bool = True) -> dict[str, Any]:
    """Pop redo → restore; push live onto undo stack."""
    out = Path(out_dir).resolve()
    root = _undo_root(out)
    index = _load_index(out)
    redo = list(index.get("redo") or [])
    if not redo:
        raise UndoError("нечего вернуть")

    entry = redo.pop()
    slot_dir = root / "slots" / str(entry["id"])
    if not (slot_dir / "manifest.json").is_file():
        raise UndoError("нечего вернуть")

    # Current live becomes a new undo snapshot (state before redo).
    stack_id = uuid.uuid4().hex[:12]
    stack_dir = root / "slots" / stack_id
    stack_entry = _write_snapshot(
        out,
        stack_dir,
        kind=str(entry.get("kind") or "edit"),
        target=str(entry.get("target") or ""),
    )
    stack = list(index.get("stack") or [])
    stack.append(stack_entry)
    while len(stack) > MAX_UNDO_DEPTH:
        old = stack.pop(0)
        _rm_slot(root, old)

    info = _restore_slot(out, slot_dir)
    _rm_slot(root, entry)

    index["stack"] = stack
    index["redo"] = redo
    _save_index(out, index)
    _sync_meta_undo(out, index)
    _maybe_rebuild(out, info, rebuild=rebuild)
    _sync_meta_undo(out, index)
    log.info("redo applied kind=%s target=%s", info.get("kind"), info.get("target"))
    return info
