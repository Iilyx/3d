"""Pipeline meta stage helpers stay writable without LLM/Docker."""

from __future__ import annotations

from pathlib import Path

from case3.pipeline import _set_stage, _write_meta, prepare_run_dirs


def test_prepare_run_dirs_and_stages(tmp_path: Path) -> None:
    src = tmp_path / "source.txt"
    src.write_text("hello\n", encoding="utf-8")
    # Fake project root with runs/
    root = tmp_path / "proj"
    (root / "runs").mkdir(parents=True)

    run_id, text_path, work, out, logs = prepare_run_dirs(src, project_root=root)
    assert run_id.startswith("source_")
    assert text_path == src.resolve()
    assert work.is_dir() and out.is_dir() and logs.is_dir()

    meta = {"run_id": run_id, "status": "running", "stage": "queued"}
    _write_meta(meta, out, logs)
    assert (out / "meta.json").is_file()
    assert (logs / "meta.json").is_file()

    _set_stage(meta, out, logs, "charts", detail="cht_01")
    loaded = (out / "meta.json").read_text(encoding="utf-8")
    assert '"stage": "charts"' in loaded
    assert '"stage_detail": "cht_01"' in loaded
    assert meta["status"] == "running"
