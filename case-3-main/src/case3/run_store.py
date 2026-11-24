"""Run filesystem + preview helpers shared by api / edits / slides routers.

Canonical ``ROOT`` for Liber runs. Tests monkeypatch ``case3.run_store.ROOT``
only — ``case3.api.ROOT`` is a ``__getattr__`` mirror of this value.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from fastapi import HTTPException

from case3.paths import repo_root
from case3.slides_media import load_figures_json
from case3.tex_preview import build_report_preview

ROOT = repo_root()

RUN_ID_OK = re.compile(r"^[A-Za-z0-9_.-]+$")
FILE_OK = re.compile(r"^[A-Za-z0-9_.-]+$")
_WORKSPACE_ID_RE = re.compile(r"^[A-Za-z0-9_-]{3,48}$")


def assert_run_workspace(run_dir: Path, workspace_id: str | None) -> None:
    """Enforce X-Workspace-Id ownership when a non-default workspace header is supplied."""
    raw = (workspace_id or "").strip()
    if not raw or not _WORKSPACE_ID_RE.match(raw) or raw == "default":
        return
    meta_path = run_dir if run_dir.name == "meta.json" else run_dir / "meta.json"
    if not meta_path.is_file():
        return
    try:
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return
    if not isinstance(meta, dict):
        return
    owner = str(meta.get("workspace_id") or "").strip()
    owner_clean = owner if _WORKSPACE_ID_RE.match(owner) else "default"
    if owner_clean != raw:
        raise HTTPException(404, detail="run not found")


def parse_formats_form(raw: str | None) -> set[str]:
    """Parse formats form: pdf|docx|both|none. ``none`` → no print artifacts."""
    fmt_raw = (raw or "both").strip().lower()
    if fmt_raw == "both":
        return {"pdf", "docx"}
    if fmt_raw in {"pdf", "docx"}:
        return {fmt_raw}
    if fmt_raw in {"none", "diagram", "schemas"}:
        return set()
    if "," in fmt_raw:
        parts = {p.strip() for p in fmt_raw.split(",") if p.strip()}
        if parts and parts <= {"pdf", "docx"}:
            return parts
    raise ValueError("formats must be pdf|docx|both|none")


def formats_from_edit_body(raw: str | None) -> set[str]:
    try:
        return parse_formats_form(raw)
    except ValueError as exc:
        raise HTTPException(400, detail=str(exc)) from exc


def diagram_print_formats(raw: list[str] | str | None) -> set[str]:
    """Diagram save: omitted or empty formats skip PDF/DOCX.

    ``parse_formats_form(None)`` means both. The schema pane omits the field
    and flushes print on «Готово», so None here is an empty set.
    """
    if raw is None:
        return set()
    if isinstance(raw, str):
        return formats_from_edit_body(raw)
    if not isinstance(raw, list) or any(not isinstance(item, str) for item in raw):
        raise HTTPException(400, detail="formats must be pdf|docx|both|none")
    out: set[str] = set()
    for item in raw:
        out |= formats_from_edit_body(item)
    return out


def artifact_downloads(run_id: str, out_dir: Path, version: int) -> dict[str, str]:
    """URLs for Liber downloads: report pdf/docx + deck pptx/deck_pdf.

    Matches ``api._run_payload`` mapping so edit envelopes do not wipe PPTX.
    """
    files: dict[str, str] = {}
    out_dir = Path(out_dir)
    for art in sorted(out_dir.iterdir()):
        if not art.is_file():
            continue
        suf = art.suffix.lower()
        name = art.name
        if suf == ".pdf" and not name.endswith("_deck.pdf"):
            files["pdf"] = f"/api/runs/{run_id}/files/{name}?v={version}"
        elif suf == ".docx":
            files["docx"] = f"/api/runs/{run_id}/files/{name}?v={version}"
        elif suf == ".pptx":
            files["pptx"] = f"/api/runs/{run_id}/files/{name}?v={version}"

    meta_path = out_dir / "meta.json"
    if meta_path.is_file():
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            meta = {}
        slides_art = meta.get("slides_artifacts") if isinstance(meta, dict) else None
        if isinstance(slides_art, dict):
            pptx_name = slides_art.get("pptx")
            deck_pdf_name = slides_art.get("deck_pdf")
            if isinstance(pptx_name, str) and (out_dir / pptx_name).is_file():
                files["pptx"] = f"/api/runs/{run_id}/files/{pptx_name}?v={version}"
            if isinstance(deck_pdf_name, str) and (out_dir / deck_pdf_name).is_file():
                files["deck_pdf"] = (
                    f"/api/runs/{run_id}/files/{deck_pdf_name}?v={version}"
                )
    return files


def bust_preview_figure_urls(
    preview: dict[str, Any],
    version: int,
    *needles: str,
) -> None:
    for block in preview.get("blocks") or []:
        if isinstance(block, dict) and block.get("type") == "figure" and block.get("url"):
            url = str(block["url"])
            if any(n and n in url for n in needles):
                sep = "&" if "?" in url else "?"
                block["url"] = f"{url}{sep}v={version}"


def load_diagrams_from_out(out_dir: Path) -> list[dict[str, Any]]:
    """UI-only Mermaid payloads from figures.json (no TeX inject)."""
    fj = out_dir / "figures.json"
    if not fj.is_file():
        return []
    try:
        data = json.loads(fj.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    raw = data.get("diagrams") if isinstance(data, dict) else None
    if not isinstance(raw, list):
        return []
    out: list[dict[str, Any]] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        did = str(item.get("id") or "").strip()
        mermaid = str(item.get("mermaid") or "").strip()
        if not did or not mermaid:
            continue
        out.append(
            {
                "id": did,
                "title": str(item.get("title") or item.get("caption") or did).strip()[:80],
                "type": str(item.get("type") or "").strip(),
                "mermaid": mermaid,
            }
        )
    return out


def find_out_tex(out_dir: Path) -> Path | None:
    texs = sorted(out_dir.glob("*.tex"))
    return texs[0] if texs else None


def build_preview_payload(
    run_id: str, out_dir: Path, media: dict[str, Any]
) -> dict[str, Any]:
    tex_path = find_out_tex(out_dir)
    if tex_path is None:
        return {"title": "", "blocks": []}
    try:
        tex = tex_path.read_text(encoding="utf-8")
    except OSError:
        return {"title": "", "blocks": []}
    return build_report_preview(
        tex,
        run_id=run_id,
        media_status=media,
        figures_json=load_figures_json(out_dir),
    )


def resolve_run_dir(run_id: str) -> Path:
    if not RUN_ID_OK.match(run_id):
        raise HTTPException(400, detail="invalid run_id")
    out_dir = (ROOT / "runs" / "out" / run_id).resolve()
    out_root = (ROOT / "runs" / "out").resolve()
    if not str(out_dir).startswith(str(out_root)) or not out_dir.is_dir():
        raise HTTPException(404, detail="run not found")
    return out_dir


def safe_run_file(run_id: str, *parts: str) -> Path:
    if not RUN_ID_OK.match(run_id):
        raise HTTPException(400, detail="invalid run_id")
    for part in parts:
        if not FILE_OK.match(part) or ".." in part or "/" in part or "\\" in part:
            raise HTTPException(400, detail="invalid path")
    path = (ROOT / "runs" / "out" / run_id).joinpath(*parts).resolve()
    out_root = (ROOT / "runs" / "out").resolve()
    if not str(path).startswith(str(out_root)) or not path.is_file():
        raise HTTPException(404, detail="file not found")
    return path


def edit_response_envelope(
    *,
    run_id: str,
    out_dir: Path,
    result: dict[str, Any],
    bust_needles: tuple[str, ...] = (),
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Shared post-edit JSON: preview + downloads + undo (+ caller extras)."""
    media = result.get("media_status") or {}
    if not isinstance(media, dict):
        media = {}
    preview = build_preview_payload(run_id, out_dir, media)
    v = int(result.get("version") or 0)
    if bust_needles:
        bust_preview_figure_urls(preview, v, *bust_needles)
    payload: dict[str, Any] = {
        "run_id": run_id,
        "status": "ok",
        "media_status": media,
        "downloads": artifact_downloads(run_id, out_dir, v),
        "preview": preview,
        "undo": result.get("undo"),
        "warnings": [],
    }
    if extra:
        payload.update(extra)
    return payload
