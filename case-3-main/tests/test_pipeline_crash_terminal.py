"""A crash outside PipelineError must still close the SSE stream."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from case3.api import _bg_run_pipeline
from case3.run_events import EVENTS


def test_background_crash_publishes_error_terminal(tmp_path: Path) -> None:
    run_id = "crash_pub_terminal"

    def _boom(*args, **kwargs):  # noqa: ANN002, ANN003
        raise RuntimeError("disk fell over")

    EVENTS.start(run_id)
    with patch("case3.api.run_pipeline", side_effect=_boom):
        with patch("case3.api.run_store.ROOT", tmp_path):
            _bg_run_pipeline(
                Path("source.txt"),
                run_id=run_id,
                formats=set(),
                dry_run=True,
                intent="",
                max_images=0,
                max_charts=0,
                max_diagrams=0,
                output_mode="report",
            )
    snap = EVENTS.snapshot(run_id)
    assert snap["done"] is True
    assert snap["terminal"] == "error"
    meta = (tmp_path / "runs" / "out" / run_id / "meta.json").read_text(encoding="utf-8")
    assert "pipeline crashed" in meta
