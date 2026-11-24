"""Per-run FileHandler filter — no cross-talk on shared case3 logger."""

from __future__ import annotations

import logging
from pathlib import Path

from case3.pipeline import _PIPELINE_RUN_ID, _RunIdLogFilter, _attach_pipeline_log_handler


def test_run_id_filter_isolates_handlers(tmp_path: Path) -> None:
    a = tmp_path / "a"
    b = tmp_path / "b"
    a.mkdir()
    b.mkdir()
    ha = _attach_pipeline_log_handler(a, "run_a")
    hb = _attach_pipeline_log_handler(b, "run_b")
    root = logging.getLogger("case3")
    try:
        tok = _PIPELINE_RUN_ID.set("run_a")
        root.info("only-a")
        _PIPELINE_RUN_ID.reset(tok)
        tok = _PIPELINE_RUN_ID.set("run_b")
        root.info("only-b")
        _PIPELINE_RUN_ID.reset(tok)
    finally:
        root.removeHandler(ha)
        root.removeHandler(hb)
        ha.close()
        hb.close()

    assert "only-a" in (a / "pipeline.log").read_text(encoding="utf-8")
    assert "only-b" not in (a / "pipeline.log").read_text(encoding="utf-8")
    assert "only-b" in (b / "pipeline.log").read_text(encoding="utf-8")
    assert "only-a" not in (b / "pipeline.log").read_text(encoding="utf-8")


def test_run_id_filter_blocks_foreign() -> None:
    f = _RunIdLogFilter("run_x")
    tok = _PIPELINE_RUN_ID.set("run_y")
    try:
        rec = logging.LogRecord("case3", logging.INFO, __file__, 1, "msg", (), None)
        assert f.filter(rec) is False
    finally:
        _PIPELINE_RUN_ID.reset(tok)


def test_run_sync_playwright_preserves_pipeline_run_id(tmp_path: Path) -> None:
    from case3.charts import _run_sync_playwright

    h = _attach_pipeline_log_handler(tmp_path, "run_pw")
    root = logging.getLogger("case3")
    tok = _PIPELINE_RUN_ID.set("run_pw")
    try:
        _run_sync_playwright(
            lambda: logging.getLogger("case3.charts").info("inside-pw-worker")
        )
    finally:
        _PIPELINE_RUN_ID.reset(tok)
        root.removeHandler(h)
        h.close()

    assert "inside-pw-worker" in (tmp_path / "pipeline.log").read_text(encoding="utf-8")

