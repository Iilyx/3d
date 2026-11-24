"""Win desk 073916: work/ vanished during LLM → FileNotFoundError on raw_model write."""

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from case3.generate import generate_document
from case3.llm_client import LLMClient


def test_write_raw_model_recreates_missing_parent(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """mkdir once at start is not enough — parent must exist again after LLM."""
    source = tmp_path / "source.txt"
    source.write_text("Выручка 10 и 20.\n", encoding="utf-8")
    out_tex = tmp_path / "work" / "run1" / "source.tex"
    out_tex.parent.mkdir(parents=True)

    class _FakeLLM(LLMClient):
        def __init__(self) -> None:
            pass

        last_finish_reason = "stop"

        def complete(self, *args, **kwargs) -> str:  # noqa: ANN002, ANN003
            # Simulate concurrent cleanup / OneDrive / cancel wiping work mid-call.
            import shutil

            if out_tex.parent.exists():
                shutil.rmtree(out_tex.parent)
            return (
                "```json\n"
                '{"charts":[],"diagrams":[],"figures":[]}\n'
                "```\n"
                "```latex\n"
                r"\documentclass{article}"
                "\n"
                r"\begin{document}"
                "\nHi\n"
                r"\end{document}"
                "\n"
                "```\n"
            )

    monkeypatch.setenv("VISION_API_BASE_URL", "http://127.0.0.1:9")
    monkeypatch.setenv("VISION_MODEL", "test")
    generate_document(
        source,
        out_tex=out_tex,
        intent="тест",
        dry_run=False,
        max_images=0,
        max_charts=0,
        max_diagrams=0,
        client=_FakeLLM(),  # type: ignore[arg-type]
    )
    raw = out_tex.parent / "source.raw_model.txt"
    assert raw.is_file()
    assert "documentclass" in raw.read_text(encoding="utf-8")
    assert out_tex.is_file()


def test_replay_raw_does_not_call_model(tmp_path: Path) -> None:
    source = tmp_path / "source.txt"
    source.write_text("Выручка 10.\n", encoding="utf-8")
    out_tex = tmp_path / "work" / "source.tex"

    class _Boom:
        def complete(self, *_a: object, **_k: object) -> str:
            raise AssertionError("replay must not call the model")

    raw = (
        "```json\n"
        '{"charts":[],"diagrams":[],"figures":[]}\n'
        "```\n"
        "```latex\n"
        "\\documentclass{article}\n"
        "\\begin{document}\nHi\n\\end{document}\n"
        "```\n"
    )
    generate_document(
        source,
        out_tex=out_tex,
        intent="тест",
        dry_run=False,
        max_images=0,
        max_charts=0,
        max_diagrams=0,
        client=_Boom(),  # type: ignore[arg-type]
        replay_raw=raw,
    )
    text = out_tex.read_text(encoding="utf-8")
    assert "documentclass" in text
    assert "Выручка" in text


def test_raw_is_on_disk_before_continuation_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "source.txt"
    source.write_text("Выручка 10.\n", encoding="utf-8")
    out_tex = tmp_path / "work" / "source.tex"
    out_tex.parent.mkdir(parents=True)

    class _Partial:
        last_finish_reason = "stop"

        def complete(self, *_a: object, **_k: object) -> str:
            self.last_finish_reason = "length"
            if getattr(self, "n", 0):
                raise RuntimeError("continuation failed")
            self.n = 1
            return (
                "```latex\n"
                "\\documentclass{article}\n"
                "\\begin{document}\nHi\n"
            )

    monkeypatch.setenv("VISION_API_BASE_URL", "http://127.0.0.1:9")
    monkeypatch.setenv("VISION_MODEL", "test")
    with pytest.raises(RuntimeError, match="continuation failed"):
        generate_document(
            source,
            out_tex=out_tex,
            intent="тест",
            dry_run=False,
            max_images=0,
            max_charts=0,
            max_diagrams=0,
            client=_Partial(),  # type: ignore[arg-type]
        )
    saved = (out_tex.parent / "source.raw_model.txt").read_text(encoding="utf-8")
    assert "documentclass" in saved
