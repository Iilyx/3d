"""Shared pytest fixtures for Liber API tests."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterator

import pytest
from fastapi.testclient import TestClient


@pytest.fixture(autouse=True)
def _reset_shared_runtime_state() -> Iterator[None]:
    """Prevent pipeline slot/waiter or LLM key cooldown state leaking across tests."""
    from case3 import api as api_mod
    from case3.llm_client import clear_key_cooldowns

    def _clear() -> None:
        with api_mod._PIPELINE_ACTIVE_GUARD:
            api_mod._PIPELINE_ACTIVE.clear()
            api_mod._PIPELINE_WAITERS.clear()
            api_mod._PIPELINE_WAITER = None
            api_mod._WAITER_RESERVED = False
            api_mod._WAITER_RESERVED_COUNT = 0
        clear_key_cooldowns()

    _clear()
    try:
        yield
    finally:
        _clear()


@pytest.fixture()
def repo_root(tmp_path: Path) -> Path:
    """Isolated fake repo root with runs/{out,work,logs,uploads}."""
    for sub in ("out", "work", "logs", "uploads"):
        (tmp_path / "runs" / sub).mkdir(parents=True)
    return tmp_path


@pytest.fixture()
def api_client(repo_root: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    """TestClient with ``api.ROOT`` and ``run_store.ROOT`` both pointed at ``repo_root``."""
    from case3 import api as api_mod
    from case3 import run_store

    # Canonical root — api.ROOT is a __getattr__ mirror of run_store.ROOT.
    monkeypatch.setattr(run_store, "ROOT", repo_root)
    yield TestClient(api_mod.app)


def seed_ok_run(
    root: Path,
    run_id: str = "seed_20260101T000000Z",
    *,
    meta: dict[str, Any] | None = None,
    tex: str | None = None,
) -> Path:
    """Create ``runs/out/<run_id>`` with demo.tex + meta.json (+ empty figures.json)."""
    out = root / "runs" / "out" / run_id
    out.mkdir(parents=True, exist_ok=True)
    (out / "demo.tex").write_text(
        tex
        or (
            r"\documentclass{article}\begin{document}Hello\end{document}"
        ),
        encoding="utf-8",
    )
    (out / "figures.json").write_text("{}", encoding="utf-8")
    payload = {"run_id": run_id, "status": "ok", **(meta or {})}
    (out / "meta.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    logs = root / "runs" / "logs" / run_id
    logs.mkdir(parents=True, exist_ok=True)
    (logs / "meta.json").write_text(
        (out / "meta.json").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    return out
