"""Deck job must catch model refusal and bad JSON without a NameError."""

from __future__ import annotations

import json
from pathlib import Path

from case3.slides_job import run_slides_job


class _Replies:
    def __init__(self, *texts: str) -> None:
        self.texts = list(texts)

    def complete(self, **_kwargs: object) -> str:
        if not self.texts:
            raise AssertionError("LLM called more times than scripted")
        return self.texts.pop(0)


def _seed(tmp_path: Path, run_id: str) -> None:
    out = tmp_path / "runs" / "out" / run_id
    out.mkdir(parents=True)
    src = tmp_path / "runs" / "uploads" / run_id / "source.txt"
    src.parent.mkdir(parents=True)
    src.write_text("Выручка: Минск 120, Гродно 80, Брест 40.", encoding="utf-8")
    (out / "meta.json").write_text(
        json.dumps(
            {
                "run_id": run_id,
                "status": "ok",
                "stage": "ok",
                "source": str(src),
                "intent": "",
                "output_mode": "presentation",
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )


def test_slides_insufficient_data_is_a_quiet_ok(tmp_path: Path) -> None:
    run_id = "slides_thin"
    _seed(tmp_path, run_id)
    run_slides_job(
        run_id,
        root=tmp_path,
        llm=_Replies(
            '{"status":"insufficient_data","message":"Мало фактов для деки."}'
        ),
    )
    meta = json.loads(
        (tmp_path / "runs" / "out" / run_id / "meta.json").read_text()
    )
    assert meta["slides_status"] == "ok"
    assert "Мало фактов" in (meta.get("chat_summary") or "")
    assert "not defined" not in json.dumps(meta, ensure_ascii=False)


def test_slides_bad_json_records_the_parse_error(tmp_path: Path) -> None:
    run_id = "slides_nojson"
    _seed(tmp_path, run_id)
    run_slides_job(
        run_id,
        root=tmp_path,
        llm=_Replies("не json", "тоже не json"),
    )
    meta = json.loads(
        (tmp_path / "runs" / "out" / run_id / "meta.json").read_text()
    )
    err = meta.get("slides_error") or ""
    assert meta["slides_status"] == "error"
    assert "JSON" in err
    assert "not defined" not in err
