"""Regenerate / img2img figure edit → PNG + docs (+ deck if present)."""

from __future__ import annotations

import base64
import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from case3.figure_edit import FigureEditError, edit_figure_in_run
from case3.image_api import ImageApiConfig

_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
)
_PNG2 = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAIAAAACCAYAAABytg0kAAAAEklEQVR42mNk+M9Qz0AEYBxVSF+FAP5FDvcfRYLwAAAAAElFTkSuQmCC"
)


def _cfg() -> ImageApiConfig:
    return ImageApiConfig(
        base_url="http://127.0.0.1:9",
        timeout_s=5,
        max_images=2,
        width=64,
        height=64,
        steps=4,
        guidance=3.0,
        seed=0,
        allow_url_download=False,
    )


def _seed_run(root: Path, *, with_deck: bool = False) -> Path:
    out = root / "runs" / "out" / "fig_edit_20260101T000000Z"
    out.mkdir(parents=True)
    figs = out / "figures"
    figs.mkdir()
    (figs / "fig_01.png").write_bytes(_PNG)
    (figs / "usr_01.png").write_bytes(_PNG)
    fj = {
        "figures": [
            {
                "id": "fig_01",
                "caption": "Старое",
                "prompt": "old prompt",
            },
            {
                "id": "usr_01",
                "caption": "Моё фото",
                "prompt": "user upload",
                "source": "upload",
            },
        ],
        "charts": [],
    }
    (out / "figures.json").write_text(json.dumps(fj), encoding="utf-8")
    (out / "demo.tex").write_text(
        r"\documentclass{article}\begin{document}"
        r"\includegraphics{figures/fig_01.png}"
        r"\caption{Старое}\label{fig:fig_01}"
        r"\end{document}",
        encoding="utf-8",
    )
    (out / "meta.json").write_text(
        json.dumps({"status": "ok", "figures_planned": ["fig_01", "usr_01"]}),
        encoding="utf-8",
    )
    if with_deck:
        slides = out / "slides"
        slides.mkdir()
        (slides / "deck.json").write_text(
            json.dumps(
                {
                    "slides": [
                        {
                            "id": "s1",
                            "layout": "media_hero",
                            "title": "Photo",
                            "media_id": "fig_01",
                        }
                    ],
                    "style": {"pack_id": "atelier"},
                }
            ),
            encoding="utf-8",
        )
    return out


def test_generate_rewrites_png_and_caption(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    out = _seed_run(tmp_path)
    monkeypatch.chdir(tmp_path)

    def fake_gen(cfg, prompt, dest, pack_id=None):
        dest.write_bytes(_PNG2)

    with (
        patch("case3.figure_edit.generate_png", side_effect=fake_gen) as gen,
        patch("case3.figure_edit.ensure_english_image_prompt", side_effect=lambda p: p),
        patch(
            "case3.figure_edit.rebuild_run_docs",
            return_value={"pdf": out / "demo.pdf"},
        ) as reb,
        patch("case3.run_undo.capture_before_edit"),
        patch("case3.run_undo.undo_meta", return_value={"can_undo": True}),
        patch("case3.run_undo.clear_undo"),
    ):
        result = edit_figure_in_run(
            out,
            "fig_01",
            mode="generate",
            prompt="a blue ceramic cup on oak table",
            caption="Чашка",
            formats={"pdf"},
            cfg=_cfg(),
        )

    gen.assert_called_once()
    reb.assert_called_once()
    assert (out / "figures" / "fig_01.png").read_bytes() == _PNG2
    fj = json.loads((out / "figures.json").read_text(encoding="utf-8"))
    assert fj["figures"][0]["caption"] == "Чашка"
    assert "cup" in fj["figures"][0]["prompt"]
    tex = (out / "demo.tex").read_text(encoding="utf-8")
    assert "Чашка" in tex
    assert result["mode"] == "generate"


def test_edit_mode_requires_existing_png_and_calls_edit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    out = _seed_run(tmp_path)
    monkeypatch.chdir(tmp_path)

    def fake_edit(cfg, prompt, src, dest, pack_id=None):
        dest.write_bytes(_PNG2)

    with (
        patch("case3.figure_edit.edit_png", side_effect=fake_edit) as ed,
        patch("case3.figure_edit.ensure_english_image_prompt", side_effect=lambda p: p),
        patch(
            "case3.figure_edit.rebuild_run_docs",
            return_value={"pdf": out / "demo.pdf"},
        ),
        patch("case3.run_undo.capture_before_edit"),
        patch("case3.run_undo.undo_meta", return_value={}),
    ):
        edit_figure_in_run(
            out,
            "usr_01",
            mode="edit",
            prompt="warmer daylight",
            caption="Моё фото",
            formats=set(),
            cfg=_cfg(),
        )

    ed.assert_called_once()
    assert (out / "figures" / "usr_01.png").read_bytes() == _PNG2


def test_edit_without_png_fails(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    out = _seed_run(tmp_path)
    (out / "figures" / "fig_01.png").unlink()
    monkeypatch.chdir(tmp_path)
    with (
        patch("case3.figure_edit.ensure_english_image_prompt", side_effect=lambda p: p),
        patch("case3.run_undo.capture_before_edit"),
        pytest.raises(FigureEditError, match="нет исходного PNG"),
    ):
        edit_figure_in_run(
            out,
            "fig_01",
            mode="edit",
            prompt="x",
            cfg=_cfg(),
        )


def test_generate_refreshes_existing_deck(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    out = _seed_run(tmp_path, with_deck=True)
    monkeypatch.chdir(tmp_path)

    def fake_gen(cfg, prompt, dest, pack_id=None):
        dest.write_bytes(_PNG2)

    rebuild = MagicMock(return_value={"status": "ok"})
    with (
        patch("case3.figure_edit.generate_png", side_effect=fake_gen),
        patch("case3.figure_edit.ensure_english_image_prompt", side_effect=lambda p: p),
        patch(
            "case3.figure_edit.rebuild_run_docs",
            return_value={"pdf": out / "demo.pdf"},
        ),
        patch("case3.run_undo.capture_before_edit"),
        patch("case3.run_undo.undo_meta", return_value={}),
        patch(
            "case3.deck_refresh.refresh_deck_from_ir",
            rebuild,
        ),
    ):
        edit_figure_in_run(
            out,
            "fig_01",
            mode="generate",
            prompt="fresh photo of a workshop bench",
            caption="Верстак",
            formats={"pdf"},
            cfg=_cfg(),
        )

    rebuild.assert_called_once()
    assert rebuild.call_args[0][0] == out


def test_rebuild_run_docs_no_tex_in_presentation(tmp_path: Path) -> None:
    from case3.run_rebuild import rebuild_run_docs
    out = tmp_path / "deck_run"
    out.mkdir()
    slides_dir = out / "slides"
    slides_dir.mkdir()
    (slides_dir / "deck.json").write_text("{}", encoding="utf-8")

    # Should return empty dict instead of FileNotFoundError
    res = rebuild_run_docs(out, formats=set())
    assert res == {}
    res_none = rebuild_run_docs(out, formats={"none"})
    assert res_none == {}


def test_upload_figure_endpoint(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from fastapi.testclient import TestClient
    from case3.api import app
    from io import BytesIO
    from PIL import Image

    out = _seed_run(tmp_path, with_deck=True)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("case3.run_store.ROOT", tmp_path)

    # create a small test image
    img = Image.new("RGB", (32, 32), color=(255, 0, 0))
    buf = BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)

    client = TestClient(app)
    run_id = out.name
    with patch("case3.deck_refresh.refresh_deck_from_ir"):
        resp = client.post(
            f"/api/runs/{run_id}/figures/usr_01/upload",
            files={"image": ("test.png", buf.getvalue(), "image/png")},
            data={"caption": "Загруженное фото"},
        )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["figure_id"] == "usr_01"
    assert data["mode"] == "upload"
    assert (out / "figures" / "usr_01.png").is_file()


def test_upload_figure_endpoint_rejects_oversized_payload(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from fastapi.testclient import TestClient
    from case3.api import app

    out = _seed_run(tmp_path, with_deck=False)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("case3.run_store.ROOT", tmp_path)
    monkeypatch.setattr("case3.user_photos._MAX_BYTES", 512)

    client = TestClient(app)
    run_id = out.name
    resp = client.post(
        f"/api/runs/{run_id}/figures/usr_01/upload",
        files={"image": ("huge.png", b"x" * 1024, "image/png")},
    )
    assert resp.status_code == 400
    assert "слишком большой" in str(resp.json().get("detail") or "").lower() or "too large" in str(resp.json().get("detail") or "").lower()



def test_delete_figure_in_tex() -> None:
    from case3.figure_edit import delete_figure_in_tex

    tex = (
        r"\section{Введение}" "\n"
        r"Текст до." "\n\n"
        r"\begin{figure}[H]" "\n"
        r"  \centering" "\n"
        r"  \includegraphics{figures/fig_01.png}" "\n"
        r"  \caption{Фото}" "\n"
        r"\end{figure}" "\n\n"
        r"Текст после."
    )
    res = delete_figure_in_tex(tex, "fig_01")
    assert "fig_01" not in res
    assert r"\begin{figure}" not in res
    assert "Текст до." in res
    assert "Текст после." in res

    # Standalone slot
    tex2 = "Параграф 1.\n\n%CASE3_CHART:cht_01%\n\nПараграф 2."
    res2 = delete_figure_in_tex(tex2, "cht_01")
    assert "cht_01" not in res2
    assert "Параграф 1." in res2
    assert "Параграф 2." in res2


def test_delete_figure_endpoint(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from fastapi.testclient import TestClient
    from case3.api import app

    out = _seed_run(tmp_path, with_deck=True)
    tex_path = out / "report.tex"
    tex_path.write_text(
        r"\documentclass{article}" "\n"
        r"\begin{document}" "\n"
        r"\begin{figure}[H]" "\n"
        r"\includegraphics{figures/fig_01.png}" "\n"
        r"\caption{Старое}" "\n"
        r"\end{figure}" "\n"
        r"\end{document}",
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("case3.run_store.ROOT", tmp_path)

    client = TestClient(app)
    run_id = out.name
    with patch("case3.deck_refresh.refresh_deck_from_ir"):
        resp = client.post(
            f"/api/runs/{run_id}/figures/fig_01/delete",
            json={"formats": "none"},
        )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["status"] == "ok"
    assert "fig_01" not in tex_path.read_text(encoding="utf-8")
    fj = json.loads((out / "figures.json").read_text(encoding="utf-8"))
    assert not any(f.get("id") == "fig_01" for f in fj.get("figures", []))
