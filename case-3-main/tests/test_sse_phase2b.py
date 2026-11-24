"""SSE phase 2B: film frames + success recap."""

from __future__ import annotations

from pathlib import Path

from case3.run_events import RunEventBus, build_success_recap


def test_publish_film_frame_and_recap_on_done(tmp_path: Path) -> None:
    bus = RunEventBus()
    bus.start("r2b")
    out = tmp_path / "out"
    figs = out / "figures"
    figs.mkdir(parents=True)
    (figs / "cht_01.png").write_bytes(b"\x89PNG" + b"\x00" * 80)
    (figs / "fig_01.png").write_bytes(b"\x89PNG" + b"\x00" * 80)
    (out / "report.pdf").write_bytes(b"%PDF" + b"\x00" * 120)
    (out / "report.docx").write_bytes(b"PK" + b"\x00" * 120)

    bus.scan_artifacts("r2b", out)
    bus.publish_terminal(
        "r2b",
        "ok",
        recap=build_success_recap(
            elapsed_s=134,
            artifacts_seen={"pdf", "docx", "chart", "figure"},
            charts=1,
            figures=1,
        ),
    )
    events = list(bus.subscribe("r2b", timeout_s=1.0))
    films = [e for e in events if e.get("event") == "film"]
    assert len(films) >= 2
    ids = {e.get("id") for e in films}
    assert "cht_01" in ids
    assert "fig_01" in ids
    assert all("/api/runs/r2b/figures/" in str(e.get("url") or "") for e in films)
    done = next(e for e in events if e.get("event") == "done")
    recap = done.get("recap") or {}
    assert int(recap.get("elapsed_s") or 0) == 134
    assert recap.get("charts") == 1
    assert "pdf" in (recap.get("formats") or [])


def test_build_recap_from_scan() -> None:
    recap = build_success_recap(
        elapsed_s=75.2,
        artifacts_seen={"pdf", "docx", "chart", "figure"},
        charts=2,
        figures=1,
    )
    assert recap["elapsed_s"] == 75
    assert recap["charts"] == 2
    assert recap["figures"] == 1
    assert recap["formats"] == ["pdf", "docx"]


def test_no_recap_on_error() -> None:
    bus = RunEventBus()
    bus.start("r2b-err")
    bus.publish_terminal("r2b-err", "error", error="boom", hint="TeX")
    events = list(bus.subscribe("r2b-err", timeout_s=1.0))
    err = next(e for e in events if e.get("event") == "error")
    assert err.get("recap") is None
