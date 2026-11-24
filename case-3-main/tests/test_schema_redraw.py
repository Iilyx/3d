"""Schema photos become Mermaid diagrams, not deck photos."""

from __future__ import annotations

from case3.schema_redraw import (
    diagrams_from_schema_reply,
    schema_source_ids,
    select_schema_photos,
)
from case3.slides_chart_data import ensure_deck_diagrams, ensure_deck_photos


def test_explicit_schema_caption_is_selected() -> None:
    figs = [
        {"id": "usr_01", "caption": "логотип платформы"},
        {"id": "usr_02", "caption": "схема поступления"},
        {"id": "usr_03", "caption": "интерфейс кассы"},
    ]
    picked = select_schema_photos(figs, "сделай презу")
    assert [f["id"] for f in picked] == ["usr_02"]


def test_unlabeled_photos_redraw_when_intent_asks() -> None:
    figs = [
        {"id": "usr_01", "caption": "Фото 1"},
        {"id": "usr_02", "caption": "Фото 2"},
    ]
    intent = "перерисуй схемы нашим способом в mermaid, не вставляй исходные фото"
    assert [f["id"] for f in select_schema_photos(figs, intent)] == ["usr_01", "usr_02"]


def test_logos_stay_photos_even_if_intent_mentions_schemas() -> None:
    figs = [
        {"id": "usr_01", "caption": "логотип"},
        {"id": "usr_02", "caption": "Фото 2"},
    ]
    intent = "перерисуй схемы mermaid"
    assert select_schema_photos(figs, intent) == []


def test_schema_source_ids_accepts_missing_list() -> None:
    assert schema_source_ids(None) == set()


def test_reply_becomes_dia_and_hides_source_photo() -> None:
    raw = """{"diagrams":[{"id":"dia_99","type":"flowchart","title":"Черновик","mermaid":"flowchart TD\\n  A[Заявка] --> B[Бюджет]"}]}"""
    photos = [{"id": "usr_02", "caption": "схема поступления"}]
    dias = diagrams_from_schema_reply(raw, photos, existing_ids=["dia_01"])
    assert dias[0]["id"] == "dia_02"
    assert dias[0]["source_photo"] == "usr_02"
    assert "Заявка" in dias[0]["mermaid"]
    assert schema_source_ids(dias) == {"usr_02"}


def test_redraw_sends_only_the_schema_photo() -> None:
    seen: dict = {}

    class _Client:
        def complete(self, *, system, user_text, reasoning="off", images=None):
            seen["images"] = images
            seen["user"] = user_text
            return (
                '{"diagrams":[{"id":"x","type":"flowchart","title":"t",'
                '"mermaid":"flowchart TD\\n  A[Заявка] --> B[Бюджет]"}]}'
            )

    def _vision(png_by_id, ids, limit=3):
        return [(fid, "data:image/jpeg;base64,aa") for fid in ids if fid in png_by_id]

    from case3.schema_redraw import redraw_attached_schemas

    dias = redraw_attached_schemas(
        figures=[
            {"id": "usr_01", "caption": "логотип"},
            {"id": "usr_02", "caption": "схема поступления"},
        ],
        intent="преза",
        png_by_id={"usr_01": "a", "usr_02": "b"},
        existing_ids=[],
        client=_Client(),
        vision_images=_vision,
    )
    assert seen["images"] == [("usr_02", "data:image/jpeg;base64,aa")]
    assert dias[0]["source_photo"] == "usr_02"
    assert "usr_01" not in schema_source_ids(dias)


def test_diagram_lands_in_deck_and_source_photo_does_not() -> None:
    deck = {
        "version": 1,
        "slides": [
            {"id": "s01", "layout": "title", "title": "Итоги"},
            {"id": "s02", "layout": "closing", "title": "Дальше", "bullets": ["ok"]},
        ],
    }
    placed = ensure_deck_diagrams(
        deck, [{"id": "dia_01", "title": "Поступление в бюджет"}]
    )
    assert placed == ["dia_01"]
    assert deck["slides"][1]["layout"] == "media_hero"
    assert deck["slides"][1]["media_id"] == "dia_01"
    hidden = schema_source_ids(
        [{"id": "dia_01", "source_photo": "usr_02", "title": "Поступление"}]
    )
    again = ensure_deck_photos(
        {
            "slides": [
                {"id": "s01", "layout": "title", "title": "Итоги"},
                {"id": "s02", "layout": "closing", "title": "Дальше", "bullets": ["ok"]},
            ]
        },
        [
            f
            for f in [{"id": "usr_02", "caption": "схема поступления"}]
            if f["id"] not in hidden
        ],
    )
    assert again == []
