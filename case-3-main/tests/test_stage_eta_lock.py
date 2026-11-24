"""Regression: note_stage_enter must not deadlock on 2nd stage (Lock re-entry)."""

from __future__ import annotations

import threading
import time

from case3 import stage_eta


def test_note_stage_enter_second_stage_no_deadlock(tmp_path) -> None:
    stage_eta.reset_timings_for_tests()
    # First enter records start; second must close previous without nested Lock.
    # duration must be ≥0.4s or record_stage_duration returns before Lock (false green).
    stage_eta.note_stage_enter("run_a", "llm", project_root=tmp_path)
    time.sleep(0.45)

    done = threading.Event()

    def _second() -> None:
        stage_eta.note_stage_enter("run_a", "inject", project_root=tmp_path)
        done.set()

    t = threading.Thread(target=_second, name="stage-eta-second", daemon=True)
    t.start()
    ok = done.wait(timeout=2.0)
    t.join(timeout=0.5)
    assert ok, "note_stage_enter deadlocked on second stage (nested _LOCK)"
