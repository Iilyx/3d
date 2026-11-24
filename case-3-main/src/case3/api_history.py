"""Session history and folder persistence router."""

from __future__ import annotations

import json
import logging
import re
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Header
from pydantic import BaseModel, Field

from case3 import run_store
from case3.run_store import RUN_ID_OK

log = logging.getLogger("case3.api_history")
router = APIRouter(tags=["history"])

_HISTORY_FILE = "user_history.json"
_INDEX_FILE = "history_index.json"
UNPINNED_HISTORY_CAP = 24
_WORKSPACE_ID_RE = re.compile(r"^[A-Za-z0-9_-]{3,48}$")


def sanitize_workspace_id(raw: str | None) -> str:
    val = (raw or "").strip()
    if val and _WORKSPACE_ID_RE.match(val):
        return val
    return "default"


def _history_path(workspace_id: str = "default") -> Path:
    wid = sanitize_workspace_id(workspace_id)
    if wid == "default":
        return run_store.ROOT / "runs" / _HISTORY_FILE
    return run_store.ROOT / "runs" / "workspaces" / wid / _HISTORY_FILE


_history_lock = threading.RLock()


def _load_user_history(workspace_id: str = "default") -> dict[str, Any]:
    hp = _history_path(workspace_id)
    if not hp.is_file():
        return {"pinned": [], "folders": [], "item_folders": {}}
    with _history_lock:
        for attempt in range(4):
            try:
                data = json.loads(hp.read_text(encoding="utf-8"))
                if isinstance(data, dict):
                    return data
            except (OSError, json.JSONDecodeError):
                time.sleep(0.02 * (attempt + 1))
    return {"pinned": [], "folders": [], "item_folders": {}}


def _save_user_history(data: dict[str, Any], workspace_id: str = "default") -> None:
    hp = _history_path(workspace_id)
    hp.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(data, ensure_ascii=False, indent=2)
    with _history_lock:
        temp_p = hp.with_suffix(".tmp")
        last_err: OSError | None = None
        for attempt in range(6):
            try:
                temp_p.write_text(payload, encoding="utf-8")
                temp_p.replace(hp)
                last_err = None
                break
            except OSError as exc:
                last_err = exc
                time.sleep(0.04 * (attempt + 1))
        if last_err is not None:
            # Fallback for Windows file lock / anti-virus handle collisions
            try:
                hp.write_text(payload, encoding="utf-8")
            except OSError as fallback_err:
                log.warning("failed to save history: %s (fallback: %s)", last_err, fallback_err)


_GENERIC_HISTORY_TITLES = re.compile(
    r"^(?:(?:сделай|собери|собрать|подготовь|напиши|создай|построй|нарисуй|покажи)\s+)?"
    r"(?:новый\s+|новую\s+)?(?:отч[её]т|документ|справк[уа]|презентаци[юя]|през[уа]|схем[уа]|график|word|ворд|pdf|docx|pptx)[.!? ]*$",
    re.IGNORECASE,
)


def _title_from_meta(meta: dict[str, Any], run_id: str) -> str:
    prev = meta.get("preview")
    if isinstance(prev, dict) and prev.get("title"):
        t = str(prev.get("title")).strip()
        if t and not _GENERIC_HISTORY_TITLES.match(t):
            return t[:64]
    if meta.get("title"):
        t = str(meta.get("title")).strip()
        if t and not _GENERIC_HISTORY_TITLES.match(t):
            return t[:64]
    for key in ("source_title", "source_name"):
        val = str(meta.get(key) or "").strip()
        if val and not _GENERIC_HISTORY_TITLES.match(val):
            return val[:64]
    if meta.get("intent"):
        intent_line = str(meta.get("intent")).strip().split("\n")[0].strip()
        if intent_line and not _GENERIC_HISTORY_TITLES.match(intent_line):
            return intent_line[:60]
    summary = str(meta.get("chat_summary") or "").strip()
    if summary:
        first_line = next(
            (ln.strip() for ln in summary.splitlines() if ln.strip() and not ln.strip().startswith("|")),
            "",
        )
        first_line = re.sub(r"[*_`#]+", "", first_line).strip()
        if first_line and not _GENERIC_HISTORY_TITLES.match(first_line):
            return first_line[:60]
    return run_id


def _index_path() -> Path:
    return run_store.ROOT / "runs" / _INDEX_FILE


def _load_history_index() -> dict[str, Any]:
    hp = _index_path()
    if not hp.is_file():
        return {}
    try:
        data = json.loads(hp.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    entries = data.get("entries") if isinstance(data, dict) else None
    return entries if isinstance(entries, dict) else {}


def _save_history_index(entries: dict[str, Any]) -> None:
    hp = _index_path()
    hp.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps({"entries": entries}, ensure_ascii=False, indent=2)
    with _history_lock:
        temp_p = hp.with_suffix(".tmp")
        try:
            temp_p.write_text(payload, encoding="utf-8")
            temp_p.replace(hp)
        except OSError:
            hp.write_text(payload, encoding="utf-8")


def _sync_history_index(out_dir: Path) -> dict[str, Any]:
    """Refresh run rows from meta mtime. Unchanged meta.json files are not re-read."""
    with _history_lock:
        entries = _load_history_index()
        seen: set[str] = set()
        changed = False
        if out_dir.is_dir():
            for run_dir in out_dir.iterdir():
                if not run_dir.is_dir() or not RUN_ID_OK.match(run_dir.name):
                    continue
                meta_path = run_dir / "meta.json"
                if not meta_path.is_file():
                    continue
                seen.add(run_dir.name)
                try:
                    mtime_ns = meta_path.stat().st_mtime_ns
                    mtime = meta_path.stat().st_mtime
                except OSError:
                    continue
                prev = entries.get(run_dir.name)
                if (
                    isinstance(prev, dict)
                    and str(prev.get("meta_mtime_ns")) == str(mtime_ns)
                    and "prior_run_id" in prev
                    and "workspace_id" in prev
                ):
                    continue
                try:
                    meta = json.loads(meta_path.read_text(encoding="utf-8"))
                except (OSError, json.JSONDecodeError):
                    continue
                if not isinstance(meta, dict):
                    continue
                entries[run_dir.name] = {
                    "title": _title_from_meta(meta, run_dir.name),
                    "savedAt": _parse_timestamp(meta.get("started_at"), fallback=mtime),
                    "status": meta.get("status", "ok"),
                    "prior_run_id": str(meta.get("prior_run_id") or ""),
                    "workspace_id": sanitize_workspace_id(meta.get("workspace_id")),
                    "meta_mtime_ns": str(mtime_ns),
                }
                changed = True
        for stale in list(entries):
            if stale not in seen:
                entries.pop(stale, None)
                changed = True
        if changed:
            _save_history_index(entries)
        return dict(entries)


def collapse_chat_heads(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """One sidebar row per chat: the latest run in a prior_run_id chain."""
    by_id = {str(item.get("runId") or ""): item for item in items}
    continued = {
        str(item.get("priorRunId") or "")
        for item in items
        if str(item.get("priorRunId") or "")
    }
    heads: list[dict[str, Any]] = []
    for item in items:
        run_id = str(item.get("runId") or "")
        if run_id in continued:
            continue
        head = dict(item)
        seen: set[str] = set()
        cursor: dict[str, Any] | None = item
        while cursor and str(cursor.get("runId") or "") not in seen:
            seen.add(str(cursor.get("runId") or ""))
            if cursor.get("pinned"):
                head["pinned"] = True
            parent = str(cursor.get("priorRunId") or "")
            cursor = by_id.get(parent)
        heads.append(head)
    return heads


def _cap_history_items(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """All pinned rows, plus the newest unpinned rows up to the desk cap."""
    pinned = [it for it in items if it.get("pinned")]
    unpinned = [it for it in items if not it.get("pinned")]
    unpinned.sort(key=lambda x: x["savedAt"], reverse=True)
    kept = pinned + unpinned[:UNPINNED_HISTORY_CAP]
    kept.sort(
        key=lambda x: (
            1 if x["pinned"] else 0,
            x["savedAt"],
        ),
        reverse=True,
    )
    return kept


def _parse_timestamp(raw: str | None, fallback: float) -> int:
    if not raw:
        return int(fallback * 1000)
    # Check format: YYYYMMDDTHHMMSSZ
    try:
        dt = datetime.strptime(raw.strip(), "%Y%m%dT%H%M%SZ").replace(
            tzinfo=timezone.utc
        )
        return int(dt.timestamp() * 1000)
    except ValueError:
        pass
    # Check ISO format
    try:
        dt = datetime.fromisoformat(raw.strip())
        return int(dt.timestamp() * 1000)
    except (ValueError, TypeError):
        pass
    return int(fallback * 1000)


class HistorySyncItem(BaseModel):
    runId: str
    pinned: bool | None = None
    folderId: str | None = None


class HistoryFolderModel(BaseModel):
    id: str
    name: str
    createdAt: int | None = None


class HistorySyncBody(BaseModel):
    items: list[HistorySyncItem] = Field(default_factory=list)
    folders: list[HistoryFolderModel] | None = None


@router.get("/api/history")
def get_history(
    x_workspace_id: str | None = Header(default=None, alias="X-Workspace-Id"),
) -> dict[str, Any]:
    """Scan disk for runs and merge with user pins and folders."""
    wid = sanitize_workspace_id(x_workspace_id)
    out_dir = run_store.ROOT / "runs" / "out"
    user_data = _load_user_history(wid)
    pinned_set = set(user_data.get("pinned", []))
    item_folders = user_data.get("item_folders", {})
    folders = user_data.get("folders", [])

    items: list[dict[str, Any]] = []
    entries = _sync_history_index(out_dir)
    for run_id, ent in entries.items():
        if not isinstance(ent, dict):
            continue
        if wid != "default" and sanitize_workspace_id(ent.get("workspace_id")) != wid:
            continue
        is_pinned = run_id in pinned_set
        items.append(
            {
                "id": run_id,
                "runId": run_id,
                "title": str(ent.get("title") or run_id),
                "savedAt": int(ent.get("savedAt") or 0),
                "pinned": is_pinned,
                "folderId": item_folders.get(run_id),
                "status": ent.get("status", "ok"),
                "priorRunId": str(ent.get("prior_run_id") or ""),
            }
        )

    return {
        "items": _cap_history_items(collapse_chat_heads(items)),
        "folders": folders,
    }


@router.post("/api/history/sync")
def sync_history(
    body: HistorySyncBody,
    x_workspace_id: str | None = Header(default=None, alias="X-Workspace-Id"),
) -> dict[str, Any]:
    """Persist user organization (pinned status, folders) across sessions."""
    wid = sanitize_workspace_id(x_workspace_id)
    with _history_lock:
        current = _load_user_history(wid)
        pinned_set = set(current.get("pinned", []))
        item_folders = dict(current.get("item_folders", {}))

        for it in body.items:
            if it.pinned is True:
                pinned_set.add(it.runId)
            elif it.pinned is False:
                pinned_set.discard(it.runId)

            if it.folderId is not None:
                if it.folderId:
                    item_folders[it.runId] = it.folderId
                else:
                    item_folders.pop(it.runId, None)

        if body.folders is not None:
            folders_list = [f.model_dump() for f in body.folders]
            valid_folder_ids = {f["id"] for f in folders_list}
            item_folders = {k: v for k, v in item_folders.items() if v in valid_folder_ids}
        else:
            folders_list = current.get("folders", [])

        new_data = {
            "pinned": sorted(pinned_set),
            "folders": folders_list,
            "item_folders": item_folders,
        }
        _save_user_history(new_data, wid)

    return {"ok": True}
