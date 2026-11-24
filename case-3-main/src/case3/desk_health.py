"""Desk probe bundle for Liber Settings health dashboard.

Quiet Mono trust strip — green/amber/red + one-line fix hints.
Image red/amber does not block report runs (caller must not gate on image_api_ok).
"""

from __future__ import annotations

import os
from typing import Any

import httpx

from case3.slides_lo import find_soffice


def probe_vision(*, timeout_s: float = 1.5) -> tuple[bool, bool, str | None]:
    """Return (configured, live_ok, error_hint)."""
    base = (os.environ.get("VISION_API_BASE_URL") or "").strip()
    if not base:
        return False, False, "Задай VISION_API_BASE_URL в .env"
    url = base.rstrip("/") + "/"
    try:
        with httpx.Client(timeout=timeout_s) as client:
            resp = client.get(url)
            if resp.status_code >= 500:
                return True, False, f"Vision HTTP {resp.status_code} — проверь Qwen/сервер"
            return True, True, None
    except Exception as exc:  # noqa: BLE001
        return True, False, f"Vision недоступен: {str(exc)[:120]}"


def probe_soffice() -> tuple[bool, str | None, str | None]:
    """Return (ok, path, hint)."""
    path = find_soffice()
    if path is None:
        return (
            False,
            None,
            "Установи LibreOffice или задай CASE3_SOFFICE (deck PDF → stitch fallback)",
        )
    return True, str(path), None


def _short_hint(text: str | None, *, limit: int = 96) -> str | None:
    if not text:
        return None
    one = " ".join(str(text).split())
    if len(one) <= limit:
        return one
    return one[: max(0, limit - 1)].rstrip() + "…"


def build_desk_probes(
    *,
    docker_ok: bool,
    docker_error: str | None,
    playwright_ok: bool,
    playwright_error: str | None = None,
    vision_configured: bool,
    vision_ok: bool,
    vision_error: str | None,
    image_configured: bool,
    image_ok: bool,
    image_error: str | None,
    soffice_ok: bool,
    soffice_path: str | None = None,
    soffice_hint: str | None = None,
) -> list[dict[str, Any]]:
    """Five Liber desk probes for Settings dashboard."""
    if vision_ok:
        vision_status = "green"
        vision_hint = None
    elif vision_configured:
        vision_status = "amber"
        vision_hint = _short_hint(
            vision_error or "Vision не отвечает — проверь VISION_API_BASE_URL / ключ"
        )
    else:
        vision_status = "red"
        vision_hint = _short_hint(vision_error or "Задай VISION_API_BASE_URL в .env")

    if image_ok:
        image_status = "green"
        image_hint = None
    elif image_configured:
        image_status = "amber"
        image_hint = _short_hint(
            "Image down — запусти workers/case3-image (отчёт без фото всё равно пойдёт)"
        )
    else:
        image_status = "amber"
        image_hint = _short_hint("IMAGE_API_BASE_URL пуст — фото пропускаются")

    if docker_ok:
        docker_hint = None
    else:
        # Prefer actionable short line over raw docker sock dump.
        raw = (docker_error or "").lower()
        if "docker.sock" in raw or "connect" in raw:
            docker_hint = "Запусти Docker Desktop, затем scripts/setup.cmd (case-3:tex)"
        else:
            docker_hint = _short_hint(
                docker_error or "docker pull case-3:tex / запусти Docker Desktop"
            )

    return [
        {
            "id": "vision",
            "label": "Qwen / Vision",
            "status": vision_status,
            "ok": vision_ok,
            "configured": vision_configured,
            "hint": vision_hint,
        },
        {
            "id": "image",
            "label": "Image API",
            "status": image_status,
            "ok": image_ok,
            "configured": image_configured,
            "hint": image_hint,
            "error": _short_hint(image_error),
        },
        {
            "id": "docker",
            "label": "Docker TeX",
            "status": "green" if docker_ok else "red",
            "ok": docker_ok,
            "hint": docker_hint,
        },
        {
            "id": "soffice",
            "label": "LibreOffice",
            "status": "green" if soffice_ok else "amber",
            "ok": soffice_ok,
            "path": soffice_path,
            "hint": None
            if soffice_ok
            else _short_hint(
                soffice_hint
                or "Установи LibreOffice / CASE3_SOFFICE (иначе PNG-stitch)"
            ),
        },
        {
            "id": "playwright",
            "label": "Playwright",
            "status": "green" if playwright_ok else "red",
            "ok": playwright_ok,
            "hint": None
            if playwright_ok
            else _short_hint(playwright_error or "playwright install chromium"),
        },
    ]
