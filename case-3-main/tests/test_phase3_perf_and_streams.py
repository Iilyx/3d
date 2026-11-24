"""Phase 3 tests: Playwright batch render, /api/health TTL cache, async SSE + TTL eviction, cooperative cancel."""

from __future__ import annotations

import asyncio
import inspect
import json
import threading
import time
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from case3 import api as api_mod
from case3 import api_stream, charts
from case3.image_api import ImageApiConfig, generate_all_figures
from case3.run_cancel import RunCancelled, mark_cancel_requested, raise_if_cancelled
from case3.run_events import RunEventBus
from case3.summary_bus import SummaryBus

FAKE_PNG = b"\x89PNG\r\n\x1a\n" + (b"\x00" * 900)


def test_render_charts_batch_shares_single_browser_instance(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Batch rendering 3 charts launches Chromium only once instead of 3 times."""
    launch_count = 0
    context_count = 0

    class _FakeLocator:
        def screenshot(self, *, path: str, type: str = "png") -> None:
            Path(path).write_bytes(FAKE_PNG)

    class _FakePage:
        def goto(self, *_a: Any, **_kw: Any) -> None:
            pass

        def evaluate(self, script: str, arg: Any = None) -> Any:
            if "window.__CASE3_CHART_ERROR" in script and arg is None:
                return None
            if "painted" in script:
                return {"ok": True, "reason": "canvas painted=100", "painted": 100}
            return None

        def wait_for_function(self, *_a: Any, **_kw: Any) -> None:
            pass

        def wait_for_timeout(self, *_a: Any, **_kw: Any) -> None:
            pass

        def locator(self, _sel: str) -> _FakeLocator:
            return _FakeLocator()

    class _FakeContext:
        def route(self, *_a: Any, **_kw: Any) -> None:
            pass

        def new_page(self) -> _FakePage:
            return _FakePage()

        def close(self) -> None:
            pass

    class _FakeBrowser:
        def new_context(self, **_kw: Any) -> _FakeContext:
            nonlocal context_count
            context_count += 1
            return _FakeContext()

        def close(self) -> None:
            pass

    class _FakeChromium:
        def launch(self, **_kw: Any) -> _FakeBrowser:
            nonlocal launch_count
            launch_count += 1
            return _FakeBrowser()

    class _FakePlaywright:
        chromium = _FakeChromium()

        def __enter__(self) -> _FakePlaywright:
            return self

        def __exit__(self, *_a: Any) -> None:
            pass

    import playwright.sync_api as pw_mod

    monkeypatch.setattr(pw_mod, "sync_playwright", lambda: _FakePlaywright())

    figs_dir = tmp_path / "figures"
    chart_items = [
        {"id": "cht_01", "type": "bar", "html": "<canvas id='c1'></canvas>"},
        {"id": "cht_02", "type": "line", "html": "<canvas id='c2'></canvas>"},
        {"id": "cht_03", "type": "donut", "html": "<canvas id='c3'></canvas>"},
    ]
    progress_seen: list[str] = []
    status = charts.generate_all_charts(
        chart_items,
        figs_dir,
        work_root=tmp_path / "chart_work",
        max_charts=3,
        on_progress=progress_seen.append,
    )
    assert launch_count == 1, f"Expected 1 browser launch for 3 charts, got {launch_count}"
    assert context_count == 3
    assert progress_seen == ["cht_01", "cht_02", "cht_03"]
    for cid in ("cht_01", "cht_02", "cht_03"):
        assert status[cid]["ok"] is True
        assert (figs_dir / f"{cid}.png").is_file()


def test_render_chart_png_accepts_str_html_and_optional_work_dir(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """render_chart_png accepts raw HTML str and defaults work_dir when omitted."""

    class _FakeLocator:
        def screenshot(self, *, path: str, type: str = "png") -> None:
            Path(path).write_bytes(FAKE_PNG)

    class _FakePage:
        def goto(self, *_a: Any, **_kw: Any) -> None:
            pass

        def evaluate(self, script: str, arg: Any = None) -> Any:
            if "window.__CASE3_CHART_ERROR" in script and arg is None:
                return None
            if "painted" in script:
                return {"ok": True, "reason": "kpi/text"}
            return None

        def wait_for_function(self, *_a: Any, **_kw: Any) -> None:
            pass

        def wait_for_timeout(self, *_a: Any, **_kw: Any) -> None:
            pass

        def locator(self, _sel: str) -> _FakeLocator:
            return _FakeLocator()

    class _FakeContext:
        def route(self, *_a: Any, **_kw: Any) -> None:
            pass

        def new_page(self) -> _FakePage:
            return _FakePage()

        def close(self) -> None:
            pass

    class _FakeBrowser:
        def new_context(self, **_kw: Any) -> _FakeContext:
            return _FakeContext()

        def close(self) -> None:
            pass

    class _FakeChromium:
        def launch(self, **_kw: Any) -> _FakeBrowser:
            return _FakeBrowser()

    class _FakePlaywright:
        chromium = _FakeChromium()

        def __enter__(self) -> _FakePlaywright:
            return self

        def __exit__(self, *_a: Any) -> None:
            pass

    import playwright.sync_api as pw_mod

    monkeypatch.setattr(pw_mod, "sync_playwright", lambda: _FakePlaywright())

    dest = tmp_path / "figures" / "cht_01.png"
    charts.render_chart_png("<div class='kpi'>42%</div>", dest)
    assert dest.is_file()


def test_health_uses_fast_playwright_probe_and_ttl_cache(
    api_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """GET /api/health caches results for 60s and uses probe_playwright_chromium."""
    api_mod.clear_health_cache()
    calls = {"docker": 0, "pw": 0, "vision": 0}

    def _fake_docker() -> None:
        calls["docker"] += 1

    def _fake_pw() -> tuple[bool, str | None]:
        calls["pw"] += 1
        return True, None

    def _fake_vision(*, timeout_s: float = 1.5) -> tuple[bool, bool, str | None]:
        calls["vision"] += 1
        return True, True, None

    monkeypatch.setattr(api_mod, "ensure_image", _fake_docker)
    monkeypatch.setattr(api_mod, "probe_playwright_chromium", _fake_pw)
    monkeypatch.setattr(api_mod, "probe_vision", _fake_vision)

    r1 = api_client.get("/api/health")
    assert r1.status_code == 200
    assert r1.json()["playwright_ok"] is True
    assert calls == {"docker": 1, "pw": 1, "vision": 1}

    # Second call within TTL uses cache — no new subprocess / HTTP probes
    r2 = api_client.get("/api/health")
    assert r2.status_code == 200
    assert calls == {"docker": 1, "pw": 1, "vision": 1}

    # ?fresh=1 bypasses cache
    r3 = api_client.get("/api/health?fresh=1")
    assert r3.status_code == 200
    assert calls == {"docker": 2, "pw": 2, "vision": 2}
    api_mod.clear_health_cache()


def test_event_bus_and_summary_bus_evict_stale_runs() -> None:
    """Completed runs older than max_age_s are evicted; active runs are kept."""
    ev_bus = RunEventBus()
    ev_bus.start("old_done")
    ev_bus.publish_terminal("old_done", "ok")

    ev_bus.start("active_old")
    ev_bus._runs["active_old"].started_at = time.time() - 3600.0

    ev_bus.start("recent_done")
    ev_bus.publish_terminal("recent_done", "ok")

    # Backdate old_done after start() calls so we test explicit evict_stale() directly
    ev_bus._runs["old_done"].started_at = time.time() - 3600.0
    ev_bus._runs["old_done"].finished_at = time.time() - 3600.0

    removed = ev_bus.evict_stale(max_age_s=1800.0)
    assert removed == 1
    assert "old_done" not in ev_bus._runs
    assert "active_old" in ev_bus._runs
    assert "recent_done" in ev_bus._runs

    # Also verify automatic eviction on start()
    ev_bus._runs["recent_done"].finished_at = time.time() - 3600.0
    ev_bus.start("brand_new")
    assert "recent_done" not in ev_bus._runs

    sum_bus = SummaryBus()
    sum_bus.start("sum_old_done")
    sum_bus.finish("sum_old_done", "text", "ok")
    sum_bus.start("sum_active")
    sum_bus._runs["sum_old_done"].finished_at = time.time() - 3600.0

    removed_s = sum_bus.evict_stale(max_age_s=1800.0)
    assert removed_s == 1
    assert "sum_old_done" not in sum_bus._runs
    assert "sum_active" in sum_bus._runs


def test_event_bus_and_summary_bus_subscribe_async() -> None:
    """subscribe_async streams live events without blocking the asyncio loop."""
    assert inspect.iscoroutinefunction(api_stream.stream_run_events)
    assert inspect.iscoroutinefunction(api_stream.stream_run_summary)

    async def _run() -> None:
        ev_bus = RunEventBus()
        ev_bus.start("async_r1")
        ev_bus.publish_stage("async_r1", "llm")

        def _delayed_finish() -> None:
            time.sleep(0.05)
            ev_bus.publish_artifact("async_r1", "pdf")
            ev_bus.publish_terminal("async_r1", "ok")

        threading.Thread(target=_delayed_finish, daemon=True).start()

        collected: list[dict[str, Any]] = []
        async for ev in ev_bus.subscribe_async("async_r1", timeout_s=2.0):
            collected.append(ev)
            if ev.get("event") in {"done", "error", "cancelled"}:
                break

        kinds = [e["event"] for e in collected]
        assert kinds == ["stage", "artifact", "done"]

        sum_bus = SummaryBus()
        sum_bus.start("async_s1")
        sum_bus.publish("async_s1", "Привет, ")

        def _delayed_sum() -> None:
            time.sleep(0.05)
            sum_bus.publish("async_s1", "мир!")
            sum_bus.finish("async_s1", "Привет, мир!", "ok")

        threading.Thread(target=_delayed_sum, daemon=True).start()

        s_events: list[dict[str, Any]] = []
        async for sev in sum_bus.subscribe_async("async_s1", timeout_s=2.0):
            s_events.append(sev)
            if sev.get("event") == "done":
                break

        assert [e["event"] for e in s_events] == ["delta", "delta", "done"]
        assert s_events[-1]["text"] == "Привет, мир!"

    asyncio.run(_run())


def test_cooperative_cancel_in_charts_and_figures(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """generate_all_charts and generate_all_figures propagate RunCancelled immediately."""
    out_dir = tmp_path / "out"
    out_dir.mkdir(parents=True)
    (out_dir / "meta.json").write_text(
        json.dumps({"run_id": "r_cancel", "status": "running"}), encoding="utf-8"
    )
    mark_cancel_requested(out_dir)

    with pytest.raises(RunCancelled):
        charts.generate_all_charts(
            [{"id": "cht_01", "type": "bar", "html": "<div class='kpi'>1</div>"}],
            tmp_path / "figs",
            max_charts=1,
            cancel_check=lambda: raise_if_cancelled(out_dir),
        )

    from dataclasses import replace

    monkeypatch.setattr("case3.image_api.probe_image_api", lambda **_kw: (True, None))
    cfg = replace(
        ImageApiConfig.from_env(), base_url="http://127.0.0.1:9999", max_images=2
    )
    with pytest.raises(RunCancelled):
        generate_all_figures(
            [{"id": "fig_01", "prompt": "a cat"}],
            tmp_path / "figs",
            cfg=cfg,
            cancel_check=lambda: raise_if_cancelled(out_dir),
        )
