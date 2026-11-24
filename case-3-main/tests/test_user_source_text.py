"""History restore reads the file the user sent, not the expanded intent."""

from pathlib import Path

from case3.api import _user_source_text
from case3 import run_store


def test_user_source_text_prefers_chat_prompt(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(run_store, "ROOT", tmp_path)
    src = tmp_path / "runs" / "uploads" / "stamp" / "source.txt"
    src.parent.mkdir(parents=True)
    src.write_text("Длинный файл данных на 100 строк...\n", encoding="utf-8")
    meta = {
        "source": str(src),
        "chat_prompt": "Сделай отчёт с 2 графиками",
    }
    assert _user_source_text(meta) == "Сделай отчёт с 2 графиками"


def test_user_source_text_reads_upload(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(run_store, "ROOT", tmp_path)
    src = tmp_path / "runs" / "uploads" / "stamp" / "source.txt"
    src.parent.mkdir(parents=True)
    src.write_text("Собери презу про найм.\n", encoding="utf-8")
    assert _user_source_text({"source": str(src)}) == "Собери презу про найм."


def test_user_source_text_rejects_paths_outside_runs(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(run_store, "ROOT", tmp_path)
    outside = tmp_path / "secret.txt"
    outside.write_text("nope", encoding="utf-8")
    assert _user_source_text({"source": str(outside)}) == ""
    assert _user_source_text({}) == ""
