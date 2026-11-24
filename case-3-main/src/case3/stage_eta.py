"""Desk rolling averages for Liber SSE ETA (phase 2A)."""

from __future__ import annotations

import json
import logging
import re
import threading
import time
from pathlib import Path
from typing import Any

log = logging.getLogger("case3.stage_eta")

_LOCK = threading.Lock()
# stage -> last durations (seconds), newest last
_SAMPLES: dict[str, list[float]] = {}
_MAX = 12
_MIN_SAMPLES = 2
_MIN_ETA = 5.0
_MAX_ETA = 600.0

# Per-run: when current stage started
_RUN_STAGE_START: dict[str, tuple[str, float]] = {}


def reset_timings_for_tests() -> None:
    with _LOCK:
        _SAMPLES.clear()
        _RUN_STAGE_START.clear()


def _store_path(project_root: Path | None) -> Path | None:
    if project_root is None:
        return None
    return Path(project_root) / "runs" / "desk_stage_timings.json"


def load_timings(project_root: Path | None) -> None:
    path = _store_path(project_root)
    if path is None or not path.is_file():
        return
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return
    if not isinstance(raw, dict):
        return
    with _LOCK:
        for k, v in raw.items():
            if isinstance(v, list):
                nums = [float(x) for x in v if isinstance(x, (int, float))]
                if nums:
                    _SAMPLES[str(k)] = nums[-_MAX:]


def save_timings(project_root: Path | None) -> None:
    path = _store_path(project_root)
    if path is None:
        return
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with _LOCK:
            payload = {k: v[-_MAX:] for k, v in _SAMPLES.items()}
        path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    except OSError as exc:
        log.debug("desk timings save skipped: %s", exc)


def record_stage_duration(stage: str, duration_s: float) -> None:
    st = (stage or "").strip().lower()
    if not st or st in {"queued", "ok", "pipeline_ok", "error", "cancelled"}:
        return
    if duration_s < 0.4 or duration_s > 3600:
        return
    with _LOCK:
        bucket = _SAMPLES.setdefault(st, [])
        bucket.append(float(duration_s))
        del bucket[:-_MAX]


def estimate_eta_s(stage: str) -> float | None:
    st = (stage or "").strip().lower()
    with _LOCK:
        samples = list(_SAMPLES.get(st) or [])
    if len(samples) < _MIN_SAMPLES:
        return None
    avg = sum(samples) / len(samples)
    if avg < _MIN_ETA or avg > _MAX_ETA:
        return None
    return round(avg, 1)


def note_stage_enter(
    run_id: str,
    stage: str,
    *,
    project_root: Path | None = None,
) -> float | None:
    """Close previous stage timing; return ETA for the new stage (or None).

    Must not call ``record_stage_duration`` while holding ``_LOCK`` — that
    nested acquire deadlocks the pipeline on the 2nd stage (images/inject)
    after a real LLM wait (≥0.4s). Win desk: «PDF 6 min forever».
    """
    rid = (run_id or "").strip()
    st = (stage or "").strip().lower()
    now = time.time()
    prev: tuple[str, float] | None = None
    with _LOCK:
        prev = _RUN_STAGE_START.pop(rid, None)
        if st and st not in {"ok", "pipeline_ok", "error", "cancelled"}:
            _RUN_STAGE_START[rid] = (st, now)
    if prev:
        prev_stage, t0 = prev
        record_stage_duration(prev_stage, now - t0)
    if project_root is not None:
        save_timings(project_root)
    return estimate_eta_s(st)


def error_hint(exc: BaseException | str, *, stage: str | None = None) -> str:
    """One actionable line for SSE error (no stack dump)."""
    msg = str(exc or "").strip()
    low = msg.lower()
    st = (stage or "").strip().lower()
    if "tabular" in low or "latex" in low or st == "latex":
        if "tabular" in low:
            return "TeX: проверь таблицу (tabularx) · открой log"
        return "TeX: сборка PDF упала · открой latex log"
    if "image" in low or "kandinsky" in low or st == "images":
        return "Фото: Image API недоступен или пустой URL"
    if "playwright" in low or "chromium" in low or st == "charts":
        return "График: Playwright/Chromium · проверь browsers"
    if "docker" in low:
        return "Docker: образ case-3:tex не запущен"
    if "cancel" in low or "останов" in low:
        return "Остановлено"
    # First line, trimmed
    first = re.split(r"[\n\r]", msg)[0].strip()
    if len(first) > 90:
        first = first[:87] + "…"
    return first or "Ошибка пайплайна"
