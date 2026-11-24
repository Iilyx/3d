"""Deck structure templates — narrative arcs (Julius DNA), separate from color packs."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

STRUCTURE_IDS = (
    "board_update",
    "investor",
    "qbr",
    "performance",
    "launch",
    "survey",
    "campaign",
    "workshop",
    "hire",
    "council",
    "quarter",
)

_CACHE: dict[str, dict[str, Any]] | None = None


def _structures_dir() -> Path:
    return Path(__file__).resolve().parent / "deck_structures"


def _load_all() -> dict[str, dict[str, Any]]:
    global _CACHE
    if _CACHE is not None:
        return _CACHE
    out: dict[str, dict[str, Any]] = {}
    root = _structures_dir()
    if root.is_dir():
        for path in sorted(root.glob("*.json")):
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            sid = str(data.get("id") or path.stem).strip().lower()
            if sid:
                out[sid] = data
    _CACHE = out
    return out


def normalize_structure_id(raw: str | None) -> str | None:
    if not raw or not str(raw).strip():
        return None
    key = str(raw).strip().lower().replace("-", "_").replace(" ", "_")
    aliases = {
        "board": "board_update",
        "boardupdate": "board_update",
        "investor_update": "investor",
        "pitch": "launch",
        "product_launch": "launch",
        "perf": "performance",
        "marketing_performance": "performance",
        "paid": "campaign",
        "status": "campaign",
    }
    key = aliases.get(key, key)
    packs = _load_all()
    if key in packs:
        return key
    if key in STRUCTURE_IDS:
        return key
    return None


def list_structures() -> list[dict[str, Any]]:
    packs = _load_all()
    rows: list[dict[str, Any]] = []
    for sid in STRUCTURE_IDS:
        raw = packs.get(sid)
        if not raw:
            continue
        rows.append(
            {
                "id": sid,
                "label": str(raw.get("label") or sid),
                "blurb": str(raw.get("blurb") or ""),
                "default_pack": str(raw.get("default_pack") or "atelier"),
                "tone": str(raw.get("tone") or "light"),
                "slides": raw.get("slides") or [8, 12],
                "arc": list(raw.get("arc") or []),
            }
        )
    return rows


def structure_overlay(structure_id: str | None) -> str:
    from case3.prompts import load_theme

    sid = normalize_structure_id(structure_id)
    if not sid:
        return ""
    return load_theme("structure", sid)


def structure_meta(structure_id: str | None) -> dict[str, Any] | None:
    sid = normalize_structure_id(structure_id)
    if not sid:
        return None
    return _load_all().get(sid)
