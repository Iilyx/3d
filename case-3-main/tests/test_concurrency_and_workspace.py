"""Tests for non-blocking event loop, thread-safe PPTX/run_id, and X-Workspace-Id."""

from __future__ import annotations

import asyncio
import json
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

import httpx
from fastapi.testclient import TestClient

from case3 import run_store
from case3.api import app


def test_async_routes_do_not_block_event_loop(tmp_path: Path, monkeypatch) -> None:
    """Blocking parse/ingest/revise calls must run off the asyncio event loop."""
    monkeypatch.setattr("case3.run_store.ROOT", tmp_path)

    class _Parsed:
        markdown = "# Данные дашборда\n\n## Таблица PDF\n\n| Показатель | 2025 |\n| --- | --- |\n| Выручка | 10 |\n"
        png_markdown = ""
        pdf_markdown = "| Показатель | 2025 |\n| --- | --- |\n| Выручка | 10 |\n"
        warnings: list[str] = []
        pdf_table_count = 1
        pdf_numeric_cells = 1

    def _slow_parse(**_kwargs):
        time.sleep(0.25)
        return _Parsed()

    monkeypatch.setattr("case3.api.parse_dashboard", _slow_parse)

    async def _run() -> float:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            parse_task = asyncio.create_task(
                client.post(
                    "/api/dashboard/parse",
                    files={"png": ("screen.png", b"\x89PNG\r\n", "image/png")},
                )
            )
            await asyncio.sleep(0.03)
            t0 = time.monotonic()
            fast_res = await client.get("/api/chart-types")
            fast_elapsed = time.monotonic() - t0
            assert fast_res.status_code == 200
            parse_res = await parse_task
            assert parse_res.status_code == 200
            return fast_elapsed

    elapsed = asyncio.run(_run())
    assert elapsed < 0.15, f"event loop blocked during /api/dashboard/parse: {elapsed:.3f}s"


def test_prepare_run_dirs_thread_safe_in_same_second(tmp_path: Path, monkeypatch) -> None:
    from case3 import pipeline

    class _Frozen:
        @staticmethod
        def now(tz=None):
            return datetime(2026, 11, 23, 12, 0, 0, tzinfo=timezone.utc)

    monkeypatch.setattr(pipeline, "datetime", _Frozen)
    src_dir = tmp_path / "runs" / "uploads" / "s1"
    src_dir.mkdir(parents=True)
    src = src_dir / "source.txt"
    src.write_text("Данные 10", encoding="utf-8")

    ids: list[str] = []
    lock = threading.Lock()
    barrier = threading.Barrier(6)

    def _worker() -> None:
        barrier.wait()
        rid, *_ = pipeline.prepare_run_dirs(src, project_root=tmp_path)
        with lock:
            ids.append(rid)

    threads = [threading.Thread(target=_worker) for _ in range(6)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert len(ids) == 6
    assert len(set(ids)) == 6


def test_build_native_pptx_isolates_theme_font_across_threads(tmp_path: Path, monkeypatch) -> None:
    from case3 import slides_pptx_draw as draw
    from case3 import slides_pptx_native as native
    from pptx import Presentation

    observed: dict[str, str] = {}
    barrier = threading.Barrier(2)

    orig_build = native._layout_title

    def _spy_build(slide, slide_ir, *args, **kwargs):
        if slide_ir.get("id") == "s01":
            barrier.wait(timeout=3.0)
            time.sleep(0.03)
            observed[slide_ir["title"]] = draw.active_pptx_font()
        return orig_build(slide, slide_ir, *args, **kwargs)

    monkeypatch.setattr(native, "_layout_title", _spy_build)

    def _deck(title: str, font: str) -> dict:
        return {
            "deck_title": title,
            "palette": "atelier",
            "style": {"fonts": {"body": font, "title": font}, "brand_mark": title},
            "slides": [
                {
                    "id": "s01",
                    "layout": "title",
                    "kicker": "01",
                    "title": title,
                    "subtitle": "Sub",
                }
            ],
        }

    t1 = threading.Thread(
        target=native.build_native_pptx,
        args=(_deck("DECK_MONO", "Arial"), tmp_path / "a.pptx"),
    )
    t2 = threading.Thread(
        target=native.build_native_pptx,
        args=(_deck("DECK_ATELIER", "Oswald"), tmp_path / "b.pptx"),
    )
    t1.start()
    t2.start()
    t1.join(timeout=5.0)
    t2.join(timeout=5.0)

    assert observed["DECK_MONO"] == "Arial"
    assert observed["DECK_ATELIER"] == "Oswald"
    assert draw.active_pptx_font() == draw._PPTX_FONT
    prs_a = Presentation(str(tmp_path / "a.pptx"))
    prs_b = Presentation(str(tmp_path / "b.pptx"))
    assert len(prs_a.slides) == 1
    assert len(prs_b.slides) == 1


def test_history_workspace_isolation(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(run_store, "ROOT", tmp_path)
    out = tmp_path / "runs" / "out"
    for rid, wid, title in (
        ("run_20261123T100001Z", "ws_alpha", "Чат Альфа"),
        ("run_20261123T100002Z", "ws_beta", "Чат Бета"),
    ):
        d = out / rid
        d.mkdir(parents=True)
        (d / "meta.json").write_text(
            json.dumps(
                {
                    "run_id": rid,
                    "workspace_id": wid,
                    "status": "ok",
                    "preview": {"title": title},
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

    client = TestClient(app)
    r_alpha = client.get("/api/history", headers={"X-Workspace-Id": "ws_alpha"})
    r_beta = client.get("/api/history", headers={"X-Workspace-Id": "ws_beta"})
    assert r_alpha.status_code == 200
    assert r_beta.status_code == 200
    assert [it["runId"] for it in r_alpha.json()["items"]] == ["run_20261123T100001Z"]
    assert [it["runId"] for it in r_beta.json()["items"]] == ["run_20261123T100002Z"]

    sync_a = client.post(
        "/api/history/sync",
        headers={"X-Workspace-Id": "ws_alpha"},
        json={
            "items": [{"runId": "run_20261123T100001Z", "pinned": True, "folderId": "f_a"}],
            "folders": [{"id": "f_a", "name": "Папка А", "createdAt": 1}],
        },
    )
    assert sync_a.status_code == 200
    assert client.get("/api/history", headers={"X-Workspace-Id": "ws_beta"}).json()["folders"] == []
    assert (
        client.get("/api/history", headers={"X-Workspace-Id": "ws_alpha"}).json()["items"][0][
            "pinned"
        ]
        is True
    )


def test_default_concurrency_runs_multiple_reports_in_parallel_and_queues_fifo(
    tmp_path: Path, monkeypatch
) -> None:
    """By default 3 heavy runs execute concurrently and 4th/5th queue FIFO without 409."""
    from case3.api import _release_pipeline_slot

    monkeypatch.setattr("case3.run_store.ROOT", tmp_path)
    started_ev: dict[str, threading.Event] = {}
    finish_ev = threading.Event()
    started_order: list[str] = []
    lock = threading.Lock()

    def _fake_bg(**kwargs: object) -> None:
        rid = str(kwargs["run_id"])
        gen = kwargs.get("slot_gen")
        with lock:
            started_order.append(rid)
            ev = started_ev.setdefault(rid, threading.Event())
        ev.set()
        finish_ev.wait(timeout=4.0)
        _release_pipeline_slot(rid, generation=gen if isinstance(gen, int) else None)

    monkeypatch.setattr("case3.api._bg_run_pipeline", _fake_bg)

    client = TestClient(app)
    rids: list[str] = []
    try:
        for i in range(5):
            resp = client.post(
                "/api/run",
                data={"source_text": f"Выручка {100 + i}", "intent": f"Отчёт {i}"},
            )
            assert resp.status_code == 202, resp.text
            body = resp.json()
            rids.append(body["run_id"])
            if i < 3:
                assert body["status"] == "started"
            else:
                assert body["status"] == "queued"

        # Wait until first 3 are genuinely running concurrently
        deadline = time.monotonic() + 2.0
        while time.monotonic() < deadline:
            with lock:
                if len(started_order) >= 3:
                    break
            time.sleep(0.02)
        assert len(started_order) == 3

        # Release all and verify queued 4th and 5th run cleanly in FIFO order
        finish_ev.set()
        deadline = time.monotonic() + 3.0
        while time.monotonic() < deadline:
            with lock:
                if len(started_order) == 5:
                    break
            time.sleep(0.02)
        assert started_order[3:] == rids[3:]
    finally:
        finish_ev.set()
        _release_pipeline_slot()


def test_write_meta_and_carry_preserve_workspace_id(tmp_path: Path) -> None:
    """Pipeline stage rewrites must never wipe workspace_id stamped by /api/run."""
    from case3.pipeline import _write_meta, carry_chat_prompt
    from case3.run_meta import read_meta, write_meta

    out = tmp_path / "runs" / "out" / "source_20261123T130000Z"
    logs = tmp_path / "runs" / "logs" / "source_20261123T130000Z"
    write_meta(
        out,
        {
            "run_id": "source_20261123T130000Z",
            "status": "running",
            "workspace_id": "ws_alice",
            "prior_run_id": "source_20261123T120000Z",
        },
        logs_dir=logs,
    )

    rebuilt = {"run_id": "source_20261123T130000Z", "status": "ok"}
    _write_meta(rebuilt, out, logs)
    assert read_meta(out).get("workspace_id") == "ws_alice"

    fresh: dict[str, object] = {}
    carry_chat_prompt(fresh, {"workspace_id": "ws_bob", "prior_run_id": "r0"})
    assert fresh.get("workspace_id") == "ws_bob"
    assert fresh.get("prior_run_id") == "r0"


def test_run_endpoints_enforce_workspace_isolation(
    tmp_path: Path, monkeypatch
) -> None:
    from fastapi.testclient import TestClient
    from case3.api import app

    monkeypatch.setattr("case3.run_store.ROOT", tmp_path)
    run_id = "source_20261123T140000Z"
    out = tmp_path / "runs" / "out" / run_id
    out.mkdir(parents=True)
    (out / "meta.json").write_text(
        json.dumps({"run_id": run_id, "status": "ok", "workspace_id": "ws_alpha"}),
        encoding="utf-8",
    )
    (out / "report.tex").write_text(
        r"\documentclass{article}\begin{document}Hi\end{document}",
        encoding="utf-8",
    )
    client = TestClient(app)

    assert client.get(f"/api/runs/{run_id}/status", headers={"X-Workspace-Id": "ws_alpha"}).status_code == 200
    assert client.get(f"/api/runs/{run_id}/status", headers={"X-Workspace-Id": "ws_beta"}).status_code == 404
    assert client.get(f"/api/runs/{run_id}/preview", headers={"X-Workspace-Id": "ws_beta"}).status_code == 404
    assert client.get(f"/api/runs/{run_id}/memory", headers={"X-Workspace-Id": "ws_beta"}).status_code == 404
    assert client.post(f"/api/runs/{run_id}/cancel", headers={"X-Workspace-Id": "ws_beta"}).status_code == 404
    # Omitted header (e.g. CLI / EventSource / img tag) keeps working
    assert client.get(f"/api/runs/{run_id}/status").status_code == 200
