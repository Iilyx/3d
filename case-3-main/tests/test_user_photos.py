"""User-attached photos → usr_* figures."""

from __future__ import annotations

import base64
from pathlib import Path

import pytest

from case3.user_photos import (
    UserPhotoError,
    bytes_to_png,
    captions_from_intent,
    clip_photo_files,
    ensure_user_slots_in_tex,
    materialize_user_figures,
    merge_user_figures,
    save_user_photos,
    split_image_budget,
    user_photos_to_vision_images,
)
from case3.generate import generate_document
from case3.llm_client import LLMClient

_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
)


def test_bytes_to_png_rejects_huge_pixel_count(monkeypatch) -> None:
    class _Huge:
        size = (10_000, 10_000)

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

    monkeypatch.setattr("PIL.Image.open", lambda *_a, **_k: _Huge())
    with pytest.raises(UserPhotoError, match="pixel"):
        bytes_to_png(_PNG)


def test_save_and_materialize(tmp_path: Path) -> None:
    figs = save_user_photos(tmp_path, [("shot.png", _PNG)], captions=["Мой кадр"])
    assert figs[0]["id"] == "usr_01"
    assert figs[0]["source"] == "upload"
    assert figs[0]["caption"] == "Мой кадр"
    dest = tmp_path / "out_figs"
    st = materialize_user_figures(figs, dest)
    assert st["usr_01"]["ok"]
    assert (dest / "usr_01.png").read_bytes().startswith(b"\x89PNG")


def test_merge_user_first() -> None:
    users = [{"id": "usr_01", "source": "upload"}]
    llm = [{"id": "fig_01"}, {"id": "fig_02"}]
    assert [f["id"] for f in merge_user_figures(llm, users, max_images=2)] == [
        "usr_01",
        "fig_01",
    ]


def test_ensure_slots() -> None:
    tex = r"\begin{document}Hi\end{document}"
    out = ensure_user_slots_in_tex(tex, [{"id": "usr_01"}])
    assert "%CASE3_FIG:usr_01%" in out
    assert out.index("%CASE3_FIG:usr_01%") < out.index(r"\end{document}")


def test_ensure_slots_after_first_section() -> None:
    """Fallback must land near body prose, not only as appendix before \\end{document}."""
    tex = (
        r"\begin{document}"
        r"\maketitle"
        r"\section{Обзор}"
        r"Текст про продукт."
        r"\section{Вывод}"
        r"Итог."
        r"\end{document}"
    )
    out = ensure_user_slots_in_tex(tex, [{"id": "usr_01"}])
    assert "%CASE3_FIG:usr_01%" in out
    # Prefer first section body over trailing dump before \end{document}
    assert out.index("%CASE3_FIG:usr_01%") < out.index(r"\section{Вывод}")
    assert out.index(r"\section{Обзор}") < out.index("%CASE3_FIG:usr_01%")


def test_five_user_photos_are_kept(tmp_path: Path) -> None:
    figs = save_user_photos(tmp_path, [(f"p{i}.png", _PNG) for i in range(5)])
    assert [f["id"] for f in figs] == [f"usr_{i:02d}" for i in range(1, 6)]


def test_clip_photo_files_keeps_five() -> None:
    files = [f"p{i}" for i in range(6)]
    assert clip_photo_files(files) == files[:5]


def test_captions_from_numbered_photo_list() -> None:
    intent = (
        "сделай презентацию и вставь фото\n"
        "1. файл логотип платформы\n"
        "2. файл логотип организации\n"
        "3. 4. 5. фотки интерфейс\n"
        "\n"
        "Требования:\n"
        "- не больше 8 графиков\n"
    )
    caps = captions_from_intent(intent, 5)
    assert caps == [
        "логотип платформы",
        "логотип организации",
        "фотки интерфейс",
        "фотки интерфейс",
        "фотки интерфейс",
    ]


def test_captions_include_schema_lines() -> None:
    intent = "1. схема поступления\n2. логотип платформы"
    assert captions_from_intent(intent, 2) == [
        "схема поступления",
        "логотип платформы",
    ]


def test_captions_ignore_numbered_source_without_photo_words() -> None:
    intent = "1. Выручка выросла\n2. Брак 3.4%\n3. План на квартал"
    assert captions_from_intent(intent, 3) == []


def test_presentation_with_uploads_does_not_invent_figures() -> None:
    llm, merge = split_image_budget(5, 2, mode="presentation")
    assert llm == 0
    assert merge == 2
    llm_r, merge_r = split_image_budget(5, 2, mode="report")
    assert (llm_r, merge_r) == (3, 5)


def test_reject_too_many(tmp_path: Path) -> None:
    with pytest.raises(UserPhotoError, match="5"):
        save_user_photos(
            tmp_path,
            [("a.png", _PNG)] * 6,
        )


def test_bytes_to_png_rejects_garbage() -> None:
    with pytest.raises(UserPhotoError):
        bytes_to_png(b"not-an-image")


def test_user_photos_to_vision_images(tmp_path: Path) -> None:
    p = tmp_path / "usr_01.png"
    p.write_bytes(_PNG)
    user_figs = [{"id": "usr_01", "path": str(p), "source": "upload"}]
    images = user_photos_to_vision_images(user_figs)
    assert len(images) == 1
    assert images[0][0] == "usr_01"
    assert images[0][1].startswith("data:image/jpeg;base64,")


def test_merge_user_figures_adopts_llm_caption() -> None:
    users = [{"id": "usr_01", "source": "upload", "caption": "Фото 1", "path": "/tmp/u1.png"}]
    llm = [{"id": "usr_01", "caption": "Схема архитектуры микросервисов", "width": r"0.90\textwidth"}]
    merged = merge_user_figures(llm, users, max_images=2)
    assert len(merged) == 1
    assert merged[0]["id"] == "usr_01"
    assert merged[0]["caption"] == "Схема архитектуры микросервисов"
    assert merged[0]["source"] == "upload"
    assert merged[0]["path"] == "/tmp/u1.png"
    assert merged[0]["width"] == r"0.90\textwidth"


def test_merge_user_figures_keeps_specific_user_caption_over_generic_llm() -> None:
    users = [{"id": "usr_01", "source": "upload", "caption": "Архитектурная схема v2", "path": "/tmp/u1.png"}]
    llm = [{"id": "usr_01", "caption": "Фото 1"}]
    merged = merge_user_figures(llm, users, max_images=2)
    assert merged[0]["caption"] == "Архитектурная схема v2"


def test_generate_document_passes_user_figures_and_vision_images(tmp_path: Path, monkeypatch) -> None:
    source = tmp_path / "source.txt"
    source.write_text("Выручка 10 и 20.\n", encoding="utf-8")
    out_tex = tmp_path / "work" / "run_vision" / "source.tex"
    out_tex.parent.mkdir(parents=True)
    photo_png = tmp_path / "usr_01.png"
    photo_png.write_bytes(_PNG)

    captured_kwargs = {}

    class _VisionTestLLM(LLMClient):
        def __init__(self) -> None:
            pass

        last_finish_reason = "stop"

        def complete(self, *args, **kwargs) -> str:  # noqa: ANN002, ANN003
            nonlocal captured_kwargs
            captured_kwargs = dict(kwargs)
            return (
                "```json\n"
                '{"charts":[],"diagrams":[],"figures":[{"id":"usr_01","caption":"Вид интерфейса"}]}\n'
                "```\n"
                "```latex\n"
                r"\documentclass{article}"
                "\n"
                r"\begin{document}"
                "\n"
                r"\section{Обзор}"
                "\nИнтерфейс показан ниже.\n"
                "%CASE3_FIG:usr_01%\n"
                r"\end{document}"
                "\n"
                "```\n"
            )

    monkeypatch.setenv("VISION_API_BASE_URL", "http://127.0.0.1:9")
    monkeypatch.setenv("VISION_MODEL", "test")

    user_figs = [{"id": "usr_01", "path": str(photo_png), "source": "upload", "caption": "Фото 1"}]

    generate_document(
        source,
        out_tex=out_tex,
        intent="отчёт с фото",
        dry_run=False,
        max_images=1,
        max_charts=0,
        max_diagrams=0,
        user_figures=user_figs,
        client=_VisionTestLLM(),  # type: ignore[arg-type]
    )

    assert "images" in captured_kwargs
    images = captured_kwargs["images"]
    assert len(images) == 1
    assert images[0][0] == "usr_01"
    assert images[0][1].startswith("data:image/jpeg;base64,")

    user_prompt = captured_kwargs["user_text"]
    assert "usr_01" in user_prompt
    assert "Vision" in user_prompt


