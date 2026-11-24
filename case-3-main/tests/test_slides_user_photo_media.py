"""Attached usr_* photos are deck-eligible media (PPTX / twin)."""

from __future__ import annotations

import base64
import json
from pathlib import Path

from case3.slides_chart_data import ensure_deck_photos
from case3.slides_media import collect_run_media
from case3.user_photos import save_user_photos, materialize_user_figures

_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
)


def test_collect_run_media_includes_usr(tmp_path: Path) -> None:
    out = tmp_path / "run"
    figs = out / "figures"
    figs.mkdir(parents=True)
    users = save_user_photos(tmp_path / "up", [("a.png", _PNG)], captions=["Кадр"])
    materialize_user_figures(users, figs)
    (out / "figures.json").write_text(
        json.dumps({"figures": users, "charts": []}), encoding="utf-8"
    )
    meta = {"figures_planned": ["usr_01"], "status": "ok"}
    _charts, figure_ids, _dias, png_by_id, _specs = collect_run_media(out, meta)
    assert "usr_01" in figure_ids
    assert "usr_01" in png_by_id
    assert png_by_id["usr_01"].is_file()


def test_deck_vision_sends_user_photo_not_chart(tmp_path: Path) -> None:
    from PIL import Image

    from case3.slides_job import deck_vision_images

    figs = tmp_path / "figures"
    figs.mkdir()
    Image.new("RGB", (1200, 400), (20, 40, 30)).save(figs / "usr_01.png")
    Image.new("RGB", (40, 40), (1, 2, 3)).save(figs / "cht_01.png")
    png_by_id = {"usr_01": figs / "usr_01.png", "cht_01": figs / "cht_01.png"}
    images = deck_vision_images(png_by_id, ["cht_01", "usr_01", "usr_02"])
    assert [mid for mid, _ in images] == ["usr_01"]
    url = images[0][1]
    assert url.startswith("data:image/jpeg;base64,")
    assert len(url) < 200_000


def _deck() -> dict:
    return {
        "version": 1,
        "slides": [
            {"id": "s01", "layout": "title", "title": "Итоги"},
            {"id": "s02", "layout": "section", "title": "Склад"},
            {
                "id": "s03",
                "layout": "table_hero",
                "title": "Смена 2 — наибольший брак",
            },
            {"id": "s04", "layout": "closing", "title": "Дальше", "bullets": ["ok"]},
        ],
    }


def test_photo_lands_after_the_slide_that_shares_its_caption() -> None:
    deck = _deck()
    placed = ensure_deck_photos(
        deck,
        [
            {"id": "usr_02", "caption": "Цех, смена 2"},
            {"id": "usr_01", "caption": "Линия сборки"},
        ],
    )
    assert placed == ["usr_02", "usr_01"]
    ids = [s["id"] for s in deck["slides"]]
    assert ids.index("s_photo_usr_02") == ids.index("s03") + 1
    photo = deck["slides"][ids.index("s_photo_usr_02")]
    assert photo["layout"] == "media_split"
    assert photo["media_id"] == "usr_02"
    assert "смена 2" in photo["title"].casefold()
    assert deck["slides"][-1]["layout"] == "closing"
    assert ids.index("s_photo_usr_01") < ids.index("s03")


def test_logo_sits_right_after_title() -> None:
    deck = _deck()
    placed = ensure_deck_photos(
        deck,
        [
            {"id": "usr_01", "caption": "логотип платформы"},
            {"id": "usr_02", "caption": "логотип организации"},
            {"id": "usr_03", "caption": "фотки интерфейс"},
        ],
    )
    assert placed[0] == "usr_01"
    assert deck["slides"][1]["media_id"] == "usr_01"
    assert deck["slides"][1]["layout"] == "media_hero"
    assert deck["slides"][1]["kicker"] == "ЛОГОТИП"
    assert deck["slides"][2]["media_id"] == "usr_02"
    assert deck["slides"][-1]["layout"] == "closing"
    ui = next(s for s in deck["slides"] if s.get("media_id") == "usr_03")
    assert ui["layout"] == "media_split"
    assert deck["slides"][-2].get("media_id") != "usr_03"


def test_photo_already_on_a_slide_is_not_duplicated() -> None:
    deck = _deck()
    deck["slides"].insert(
        2,
        {
            "id": "s_has",
            "layout": "media_hero",
            "title": "Линия",
            "media_id": "usr_01",
        },
    )
    placed = ensure_deck_photos(deck, [{"id": "usr_01", "caption": "Линия сборки"}])
    assert placed == []
    assert sum(1 for s in deck["slides"] if s.get("media_id") == "usr_01") == 1
