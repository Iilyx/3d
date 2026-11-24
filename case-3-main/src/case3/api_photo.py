"""Standalone Liber photo edit routes (chat-only img2img)."""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import JSONResponse

from case3.image_api import ImageApiConfig, edit_png
from case3.image_prompt import ImagePromptError, ensure_english_image_prompt
from case3 import run_store
from case3.run_meta import write_meta
from case3.user_photos import UserPhotoError, save_user_photos

log = logging.getLogger("case3.api_photo")
router = APIRouter(tags=["photo"])


def _stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


async def quick_photo_edit(
    fig: dict[str, Any],
    *,
    prompt: str,
    caption: str,
) -> JSONResponse:
    """Img2img one attached photo → chat preview (no TeX/PDF)."""
    cfg = ImageApiConfig.from_env()
    if not cfg.base_url:
        raise HTTPException(400, detail="IMAGE_API_BASE_URL пуст")
    src = Path(str(fig.get("path") or ""))
    if not src.is_file():
        raise HTTPException(400, detail="upload missing on disk")
    stamp = _stamp()
    run_id = f"photo_edit_{stamp}"
    out = run_store.ROOT / "runs" / "out" / run_id
    figs = out / "figures"
    figs.mkdir(parents=True, exist_ok=True)
    dest = figs / "edited.png"
    try:
        prompt_en = await asyncio.to_thread(ensure_english_image_prompt, prompt)
    except ImagePromptError as exc:
        raise HTTPException(400, detail=str(exc)) from exc
    try:
        await asyncio.to_thread(edit_png, cfg, prompt_en, src, dest)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(502, detail=f"image edit failed: {exc}") from exc
    v = int(dest.stat().st_mtime)
    meta = {
        "run_id": run_id,
        "status": "ok",
        "stage": "ok",
        "mode": "photo_edit",
        "prompt": prompt_en[:500],
        "caption": caption,
    }
    write_meta(out, meta)
    url = f"/api/runs/{run_id}/figures/edited.png?v={v}"
    return JSONResponse(
        {
            "run_id": run_id,
            "status": "ok",
            "mode": "photo_edit",
            "prompt": prompt_en,
            "caption": caption,
            "preview_figure": {
                "id": "edited",
                "kind": "figure",
                "url": url,
                "caption": caption,
            },
            "downloads": {},
            "preview": {
                "title": caption,
                "blocks": [
                    {
                        "type": "figure",
                        "id": "edited",
                        "kind": "figure",
                        "url": url,
                        "caption": caption,
                    }
                ],
            },
            "figures_ok": 1,
            "figures_planned": ["edited"],
            "charts_ok": 0,
            "charts_planned": [],
            "warnings": [],
        }
    )


@router.post("/api/photo/edit")
async def api_photo_edit(
    image: UploadFile = File(...),
    prompt: str = Form(...),
    caption: str = Form(""),
) -> JSONResponse:
    """Standalone chat-only img2img (same as photo_mode=edit on /api/run)."""
    upload_dir = run_store.ROOT / "runs" / "uploads" / _stamp()
    upload_dir.mkdir(parents=True, exist_ok=True)
    raw = await image.read()
    try:
        figs = save_user_photos(
            upload_dir,
            [(image.filename or "photo.png", raw)],
            captions=[caption] if caption.strip() else None,
        )
    except UserPhotoError as exc:
        raise HTTPException(400, detail=str(exc)) from exc
    return await quick_photo_edit(
        figs[0],
        prompt=(prompt or "").strip(),
        caption=(caption or figs[0].get("caption") or "Правка фото"),
    )
