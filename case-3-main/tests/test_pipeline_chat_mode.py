from __future__ import annotations

import json
from pathlib import Path

from case3.pipeline import run_pipeline


def test_chat_mode_answers_without_tex(tmp_path: Path):
    root = tmp_path / "project"
    root.mkdir()
    (root / "prompt" / "gold").mkdir(parents=True)
    src = tmp_path / "source.txt"
    src.write_text(
        "Выручка была 10, стала 12. Почему выросла, если других цифр нет?",
        encoding="utf-8",
    )

    out = run_pipeline(
        src,
        project_root=root,
        intent="Проанализируй, почему выручка выросла с 10 до 12",
        output_mode="chat",
        formats=set(),
        dry_run=True,
    )

    meta = json.loads((out / "meta.json").read_text(encoding="utf-8"))
    assert meta["output_mode"] == "chat"
    assert meta["status"] == "ok"
    assert meta.get("insufficient_data") is not True
    assert "Разбор останется в чате" in (meta.get("chat_summary") or "")
    assert not (out / "report.pdf").is_file()
    assert not list(out.glob("*.tex"))


def test_chat_mode_keeps_uploaded_photos_in_the_run(tmp_path: Path):
    root = tmp_path / "project"
    root.mkdir()
    (root / "prompt" / "gold").mkdir(parents=True)
    src = tmp_path / "source.txt"
    src.write_text("Выручка была 10, стала 12.", encoding="utf-8")
    photo = tmp_path / "shot.png"
    photo.write_bytes(b"png-bytes")

    out = run_pipeline(
        src,
        project_root=root,
        intent="Что на фото, если выручка была 10 и стала 12?",
        output_mode="chat",
        formats=set(),
        dry_run=True,
        user_figures=[
            {"id": "usr_01", "source": "upload", "path": str(photo), "caption": "Фото 1"}
        ],
    )

    assert (out / "figures" / "usr_01.png").read_bytes() == b"png-bytes"


def test_chat_mode_skips_narrate_stages_and_persists_diagram_figures_json(
    tmp_path: Path, monkeypatch
):
    from case3 import pipeline

    root = tmp_path / "project"
    root.mkdir()
    (root / "prompt" / "gold").mkdir(parents=True)
    src = tmp_path / "source.txt"
    src.write_text("Минск 120, Гомель 80.", encoding="utf-8")

    narrated = {"called": 0}

    def _spy_narrate(*args, **kwargs):
        narrated["called"] += 1
        return []

    monkeypatch.setattr("case3.stage_narration.narrate_stages", _spy_narrate)
    monkeypatch.setattr(
        "case3.chat_turn.try_chat_answer",
        lambda source, intent, **kwargs: "Минск 120, Гомель 80.",
    )

    def _fake_diag(source, intent, *, figs_dir, **kwargs):
        Path(figs_dir).mkdir(parents=True, exist_ok=True)
        p = Path(figs_dir) / "dia_01.png"
        p.write_bytes(b"dia-png")
        return (
            [{"id": "dia_01", "title": "Схема", "mermaid": "flowchart TD\nA-->B"}],
            {"dia_01": {"ok": True, "path": str(p), "kind": "diagram"}},
        )

    monkeypatch.setattr("case3.chat_turn.generate_chat_diagram", _fake_diag)

    out = run_pipeline(
        src,
        project_root=root,
        intent="построй схему по данным",
        output_mode="chat",
        formats=set(),
        dry_run=False,
    )
    assert narrated["called"] == 0
    assert (out / "figures.json").is_file()
    fj = json.loads((out / "figures.json").read_text(encoding="utf-8"))
    assert fj["diagrams"][0]["id"] == "dia_01"
    meta = json.loads((out / "meta.json").read_text(encoding="utf-8"))
    assert meta["media_status"]["dia_01"]["ok"] is True


def test_presentation_mode_skips_heavy_generate_document_and_injects_derivatives(
    tmp_path: Path, monkeypatch
):
    root = tmp_path / "project"
    root.mkdir()
    (root / "prompt" / "gold").mkdir(parents=True)
    src = tmp_path / "source.md"
    src.write_text(
        "# Данные дашборда\n\n| Регион | Факт | План |\n| --- | --- | --- |\n"
        "| Минск | 120 | 100 |\n| Гомель | 80 | 100 |\n",
        encoding="utf-8",
    )

    called_full_tex = {"count": 0}

    def _fail_if_called(*args, **kwargs):
        called_full_tex["count"] += 1
        raise AssertionError("generate_document full LaTeX should be skipped in presentation mode")

    monkeypatch.setattr("case3.pipeline.generate_document", _fail_if_called)

    out = run_pipeline(
        src,
        project_root=root,
        intent="сделай презентацию",
        output_mode="presentation",
        formats=set(),
        max_images=0,
        max_charts=0,
        dry_run=True,
    )
    assert called_full_tex["count"] == 0
    meta = json.loads((out / "meta.json").read_text(encoding="utf-8"))
    eff = Path(meta["source"]).read_text(encoding="utf-8")
    assert "## Производные" in eff


def test_prior_chat_visuals_picks_last_chart_and_skips_clarifying_edit(tmp_path: Path, monkeypatch) -> None:
    from case3 import pipeline

    assert pipeline._is_clarifying_visual_request(
        "измени мне график",
        "Да, уточните, пожалуйста, как именно изменить график: тип, цвет или показатели?",
        kind="chart",
    ) is True
    assert pipeline._is_clarifying_visual_request(
        "сделай оранжевым",
        "Делаю круговую диаграмму оранжевой.",
        kind="chart",
    ) is False

    root = tmp_path / "project"
    (root / "prompt" / "gold").mkdir(parents=True)
    prev_out = root / "runs" / "out" / "prev_run"
    prev_out.mkdir(parents=True)
    (prev_out / "meta.json").write_text(json.dumps({"run_id": "prev_run"}), encoding="utf-8")
    (prev_out / "figures.json").write_text(
        json.dumps(
            {
                "figures": [],
                "charts": [
                    {"id": "cht_01", "type": "bar", "caption": "Первый", "html": "<canvas id='c1'></canvas>"},
                    {"id": "cht_02", "type": "pie", "caption": "Последний", "html": "<canvas id='c2'></canvas>"},
                ],
                "diagrams": [],
            }
        ),
        encoding="utf-8",
    )
    src = tmp_path / "source.md"
    src.write_text("| Область | Факт |\n| --- | --- |\n| Минск | 120 |\n| Гомель | 80 |\n", encoding="utf-8")

    captured: list[dict | None] = []
    monkeypatch.setattr(
        "case3.chat_turn.try_chat_answer",
        lambda *_a, **_kw: "Уточните, как именно изменить график?",
    )
    monkeypatch.setattr(
        "case3.chat_turn.generate_chat_charts",
        lambda *_a, **kw: (captured.append(kw.get("previous_chart")) or [], {}),
    )
    # 1) Bare "измени мне график" with clarifying answer must NOT invoke generate_chat_charts
    pipeline.run_pipeline(
        src,
        project_root=root,
        intent="измени мне график",
        output_mode="chat",
        formats=set(),
        max_charts=2,
        prior_run_id="prev_run",
        dry_run=False,
    )
    assert captured == []

    # 2) Concrete "сделай оранжевым" picks the LAST chart (cht_02), not the first (cht_01)
    monkeypatch.setattr(
        "case3.chat_turn.try_chat_answer",
        lambda *_a, **_kw: "Перекрашиваю последний график в оранжевый цвет.",
    )
    pipeline.run_pipeline(
        src,
        project_root=root,
        intent="сделай оранжевым",
        output_mode="chat",
        formats=set(),
        max_charts=2,
        prior_run_id="prev_run",
        dry_run=False,
    )
    assert len(captured) == 1
    assert captured[0] and captured[0].get("id") == "cht_02"
