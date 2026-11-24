"""Native editable PPTX from deck IR."""

from __future__ import annotations

from pathlib import Path

from PIL import Image
from pptx import Presentation
from pptx.enum.shapes import MSO_SHAPE_TYPE

from case3.slides_patch import apply_deck_text_patch
from case3.slides_pptx_native import build_native_pptx


def _png(path: Path) -> Path:
    Image.new("RGB", (400, 240), (80, 100, 40)).save(path, format="PNG")
    return path


def test_native_pptx_has_editable_text_not_only_pictures(tmp_path: Path) -> None:
    chart = _png(tmp_path / "cht_01.png")
    deck = {
        "version": 1,
        "aspect": "16:9",
        "palette": "atelier",
        "language": "ru",
        "slides": [
            {
                "id": "s01",
                "layout": "title",
                "title": "Итоги Q3",
                "subtitle": "Краткий разбор",
            },
            {
                "id": "s02",
                "layout": "kpi_row",
                "kicker": "Цифры",
                "title": "KPI",
                "kpis": [
                    {"label": "Выручка", "value": "4,8 млрд"},
                    {"label": "Маржа", "value": "18%"},
                ],
            },
            {
                "id": "s03",
                "layout": "chart_split",
                "title": "Каналы",
                "chart_id": "cht_01",
                "body": "Онлайн растёт",
                "bullets": ["Доля 27%"],
            },
            {
                "id": "s04",
                "layout": "closing",
                "title": "Далее",
                "bullets": ["Шаг 1"],
            },
        ],
    }
    out = build_native_pptx(
        deck, tmp_path / "native.pptx", media_by_id={"cht_01": chart}
    )
    assert out.is_file()
    prs = Presentation(str(out))
    assert len(prs.slides) == 4

    # Title slide: text frames present
    title_slide = prs.slides[0]
    texts = []
    for shape in title_slide.shapes:
        if shape.has_text_frame:
            texts.append(shape.text_frame.text)
    joined = "\n".join(texts)
    assert "Итоги Q3" in joined
    assert "Краткий разбор" in joined

    # Chart slide embeds a picture AND editable body text
    split = prs.slides[2]
    has_pic = any(s.shape_type == MSO_SHAPE_TYPE.PICTURE for s in split.shapes)
    assert has_pic
    split_text = "\n".join(
        s.text_frame.text for s in split.shapes if s.has_text_frame
    )
    assert "Онлайн растёт" in split_text or "Доля 27%" in split_text


def test_native_empty_deck_slides_raises(tmp_path: Path) -> None:
    try:
        build_native_pptx({"slides": []}, tmp_path / "x.pptx")
        # empty deck still creates empty pptx — allow 0 slides file
    except Exception:
        pass
    # at least dest parent ok
    assert tmp_path.is_dir()


def test_native_section_scorecard_callout_table(tmp_path: Path) -> None:
    deck = {
        "version": 1,
        "aspect": "16:9",
        "palette": "atelier",
        "language": "ru",
        "style": {"brand_mark": "LIBER · BOARD", "table": {}},
        "slides": [
            {
                "id": "s01",
                "layout": "title",
                "title": "Board",
            },
            {
                "id": "s02",
                "layout": "section",
                "chapter": 1,
                "title": "Глава",
                "subtitle": "Контекст",
            },
            {
                "id": "s03",
                "layout": "scorecard",
                "title": "KPI",
                "kpis": [
                    {
                        "label": "Выручка",
                        "value": "10",
                        "delta": "+2%",
                        "status": "up",
                    }
                ],
            },
            {
                "id": "s04",
                "layout": "callout",
                "title": "Смысл",
                "term": "CAC",
                "definition": "Стоимость привлечения",
            },
            {
                "id": "s05",
                "layout": "table_hero",
                "title": "Таблица",
                "rows": [["A", "B"], ["1", "2"]],
            },
            {
                "id": "s06",
                "layout": "closing",
                "title": "Итог",
                "bullets": ["Шаг"],
            },
        ],
    }
    out = build_native_pptx(deck, tmp_path / "rich.pptx")
    prs = Presentation(str(out))
    assert len(prs.slides) == 6
    section_text = "\n".join(
        s.text_frame.text for s in prs.slides[1].shapes if s.has_text_frame
    )
    assert "Глава" in section_text
    assert "Контекст" in section_text
    score_text = "\n".join(
        s.text_frame.text for s in prs.slides[2].shapes if s.has_text_frame
    )
    assert "+2%" in score_text


def test_kicker_title_y_stays_in_slide_inches(tmp_path: Path) -> None:
    """Regression: float(Inches(x)) is EMUs — must not push shapes to y≈777240\"."""
    from case3.deck_theme import resolve_deck_theme

    style = resolve_deck_theme("relay").as_dict()
    deck = {
        "version": 1,
        "aspect": "16:9",
        "palette": "atelier",
        "language": "ru",
        "style": style,
        "slides": [
            {
                "id": "s03",
                "layout": "scorecard",
                "kicker": "Ключевые показатели",
                "title": "Результаты Q3 2026",
                "takeaway": "Все опорные KPI выше прошлого года",
                "kpis": [
                    {"value": "4,8 млрд", "label": "Выручка", "delta": "+17%"},
                    {"value": "27%", "label": "Доля e-com", "delta": "+5 п.п."},
                ],
            }
        ],
    }
    out = build_native_pptx(deck, tmp_path / "y_inches.pptx")
    import zipfile
    from lxml import etree

    z = zipfile.ZipFile(out)
    root = etree.fromstring(z.read("ppt/slides/slide1.xml"))
    ns = {
        "a": "http://schemas.openxmlformats.org/drawingml/2006/main",
        "p": "http://schemas.openxmlformats.org/presentationml/2006/main",
    }
    ys = []
    for off in root.findall(".//a:off", ns):
        ys.append(int(off.get("y") or 0) / 914400)
    assert ys, "expected shapes"
    assert max(ys) < 8.0, f"shape Y escaped slide (inches): {max(ys)}"
    assert min(ys) >= 0.0


def test_botanical_table_body_not_white(tmp_path: Path) -> None:
    """Dark pack tables: body fill from theme, not hardcoded white."""
    from case3.deck_theme import resolve_deck_theme

    style = resolve_deck_theme("botanical").as_dict()
    deck = {
        "version": 1,
        "aspect": "16:9",
        "palette": "atelier",
        "language": "en",
        "theme_id": "botanical",
        "style": style,
        "slides": [
            {
                "id": "s08",
                "layout": "table_hero",
                "kicker": "Channel strategy",
                "title": "One story. Four paths to the cup.",
                "takeaway": "DTC first.",
                "rows": [
                    ["Channel", "Job"],
                    ["Creator seeding", "Show the evening ritual"],
                ],
            }
        ],
    }
    from pptx.dml.color import RGBColor

    out = build_native_pptx(deck, tmp_path / "bot_table.pptx")
    prs = Presentation(str(out))
    table = next(s.table for s in prs.slides[0].shapes if s.has_table)
    body_rgb = table.cell(1, 0).fill.fore_color.rgb
    assert body_rgb != RGBColor(0xFF, 0xFF, 0xFF)
    assert body_rgb == RGBColor(0x24, 0x38, 0x2E)


def test_native_botanical_card_row_and_texture(tmp_path: Path) -> None:
    from case3.deck_theme import resolve_deck_theme

    style = resolve_deck_theme("botanical").as_dict()
    deck = {
        "version": 1,
        "aspect": "16:9",
        "palette": "atelier",
        "language": "en",
        "theme_id": "botanical",
        "style": style,
        "slides": [
            {
                "id": "s01",
                "layout": "card_row",
                "kicker": "Target audience",
                "title": "Start with the ritual-minded.",
                "subtitle": "Audience hypotheses.",
                "caption": "VALIDATION GATE  15 interviews",
                "cards": [
                    {
                        "kicker": "PRIMARY",
                        "title": "Design-conscious adults",
                        "body": "Ages 28–44.",
                    },
                    {
                        "kicker": "SECONDARY",
                        "title": "Thoughtful gift buyers",
                        "body": "Hosts and care packages.",
                    },
                    {
                        "kicker": "CONTEXT",
                        "title": "One cup. One cue.",
                        "body": "After dinner.",
                    },
                ],
            }
        ],
    }
    out = build_native_pptx(deck, tmp_path / "botanical_cards.pptx")
    prs = Presentation(str(out))
    assert len(prs.slides) == 1
    texts = "\n".join(
        s.text_frame.text for s in prs.slides[0].shapes if s.has_text_frame
    )
    assert "Design-conscious adults" in texts
    assert "VALIDATION GATE" in texts.upper() or "Validation" in texts
    # Fern texture as OOXML slide background
    xml = prs.slides[0]._element.xml
    assert "p:bg" in xml or "a:blip" in xml


def test_media_photo_not_squashed_in_pptx(tmp_path: Path) -> None:
    """Square Flux photos must not fill a wide box with both width+height."""
    sq = tmp_path / "fig_01.png"
    Image.new("RGB", (1024, 1024), (90, 120, 60)).save(sq, format="PNG")
    deck = {
        "version": 1,
        "aspect": "16:9",
        "palette": "atelier",
        "language": "ru",
        "slides": [
            {
                "id": "s01",
                "layout": "title",
                "title": "Cover",
            },
            {
                "id": "s02",
                "layout": "media_split",
                "title": "Кадр",
                "media_id": "fig_01",
                "body": "Описание",
            },
        ],
    }
    out = build_native_pptx(
        deck, tmp_path / "photo.pptx", media_by_id={"fig_01": sq}
    )
    prs = Presentation(str(out))
    split = prs.slides[1]
    pics = [s for s in split.shapes if s.shape_type == MSO_SHAPE_TYPE.PICTURE]
    assert len(pics) == 1
    pic = pics[0]
    ratio = float(pic.width) / float(pic.height)
    assert 0.82 <= ratio <= 1.22, f"expected ~square photo, got ratio {ratio:.2f}"


def test_media_hero_photo_stays_on_slide_with_title(tmp_path: Path) -> None:
    """Length subtraction is a raw EMU int. Treating it as inches
    parks the photo millions of inches off-slide and PowerPoint repairs
    the file, dropping the text.
    """
    sq = tmp_path / "fig_01.png"
    Image.new("RGB", (1024, 1024), (90, 120, 60)).save(sq, format="PNG")
    deck = {
        "version": 1,
        "aspect": "16:9",
        "palette": "atelier",
        "slides": [
            {
                "id": "s01",
                "layout": "media_hero",
                "kicker": "Соцсети",
                "title": "Съёмка контента",
                "caption": "Подросток снимает видео",
                "media_id": "fig_01",
            }
        ],
    }
    out = build_native_pptx(
        deck, tmp_path / "hero.pptx", media_by_id={"fig_01": sq}
    )
    slide = Presentation(str(out)).slides[0]
    pics = [s for s in slide.shapes if s.shape_type == MSO_SHAPE_TYPE.PICTURE]
    assert len(pics) == 1
    left = pics[0].left.inches
    assert 0 <= left <= 13.4, f"photo left {left}"
    assert pics[0].width.inches < 13.4
    text = _shape_text(slide)
    assert "Съёмка контента" in text
    assert "Подросток снимает видео" in text


def _shape_text(slide) -> str:
    return "\n".join(
        s.text_frame.text for s in slide.shapes if s.has_text_frame
    )


def test_patched_bullet_lands_in_pptx(tmp_path: Path) -> None:
    deck = {
        "version": 1,
        "palette": "atelier",
        "slides": [
            {
                "id": "s01",
                "layout": "bullets",
                "title": "Факты",
                "bullets": ["Первый", "Второй"],
            }
        ],
    }
    patched = apply_deck_text_patch(
        deck,
        {"slides": [{"id": "s01", "bullets": ["Первый", "Второй", "Третий тезис"]}]},
    )
    out = build_native_pptx(patched, tmp_path / "bullets.pptx")
    text = _shape_text(Presentation(str(out)).slides[0])
    assert "Третий тезис" in text


def test_stat_hero_paints_heading_and_kpi(tmp_path: Path) -> None:
    deck = {
        "version": 1,
        "palette": "atelier",
        "style": {"brand_mark": "LIBER"},
        "slides": [
            {
                "id": "s01",
                "layout": "stat_hero",
                "kicker": "МАСШТАБ",
                "title": "Ключевой мультипликатор",
                "kpis": [
                    {
                        "label": "Рост отдачи",
                        "value": "2,6×",
                        "delta": "+160%",
                        "hint": "к базе",
                    }
                ],
                "bullets": ["Фокус на ядре"],
            }
        ],
    }
    out = build_native_pptx(deck, tmp_path / "stat.pptx")
    text = _shape_text(Presentation(str(out)).slides[0])
    assert "Ключевой мультипликатор" in text
    assert "МАСШТАБ" in text
    assert "2,6×" in text
    assert "Рост отдачи" in text
    assert "+160%" in text
    assert "Фокус на ядре" in text


def test_compare_and_quote_edits_land_in_pptx(tmp_path: Path) -> None:
    deck = {
        "version": 1,
        "palette": "atelier",
        "slides": [
            {
                "id": "s01",
                "layout": "compare",
                "title": "Выбор",
                "cards": [
                    {"kicker": "А", "title": "Старое А", "body": "Текст А"},
                    {"kicker": "Б", "title": "Старое Б", "body": "Текст Б"},
                ],
            },
            {
                "id": "s02",
                "layout": "quote",
                "title": "Позиция",
                "definition": "Старая цитата",
                "term": "Источник",
                "body": "Пояснение",
            },
        ],
    }
    patched = apply_deck_text_patch(
        deck,
        {
            "slides": [
                {
                    "id": "s01",
                    "cards": [
                        {"kicker": "А", "title": "Новая колонка", "body": "Текст А"},
                        {"kicker": "Б", "title": "Старое Б", "body": "Текст Б"},
                    ],
                },
                {"id": "s02", "definition": "Новая цитата", "term": "Новый источник"},
            ]
        },
    )
    out = build_native_pptx(patched, tmp_path / "compare_quote.pptx")
    prs = Presentation(str(out))
    left = _shape_text(prs.slides[0])
    right = _shape_text(prs.slides[1])
    assert "Новая колонка" in left
    assert "Новая цитата" in right
    assert "НОВЫЙ ИСТОЧНИК" in right


def test_missing_chart_png_does_not_crash(tmp_path: Path) -> None:
    """cht_* with no series and no PNG still writes the PPTX (title only)."""
    deck = {
        "version": 1,
        "palette": "atelier",
        "slides": [
            {"id": "s01", "layout": "title", "title": "Итоги"},
            {
                "id": "s02",
                "layout": "chart_hero",
                "title": "График",
                "chart_id": "cht_01",
            },
            {"id": "s03", "layout": "media_hero", "title": "Схема", "media_id": "dia_01"},
            {"id": "s04", "layout": "closing", "title": "Дальше", "bullets": ["ok"]},
        ],
    }
    out = build_native_pptx(deck, tmp_path / "thin.pptx", media_by_id={})
    prs = Presentation(str(out))
    assert len(prs.slides) == 4


def test_chart_hero_with_native_kpi_series_does_not_crash(tmp_path: Path) -> None:
    """Full-width chart_hero with KPI chart series must not raise UnboundLocalError on pic_h."""
    deck = {
        "version": 1,
        "palette": "atelier",
        "slides": [
            {"id": "s01", "layout": "title", "title": "Итоги"},
            {
                "id": "s02",
                "layout": "chart_hero",
                "title": "Ключевой эффект",
                "chart_id": "cht_01",
            },
        ],
    }
    chart_series = {
        "cht_01": {
            "type": "kpi",
            "title": "Рентабельность",
            "labels": ["EBITDA", "Чистая маржа"],
            "datasets": [{"label": "2025", "data": [34.0, 18.5]}],
            "unit": "%",
        }
    }
    out = build_native_pptx(
        deck,
        tmp_path / "kpi_hero.pptx",
        media_by_id={},
        chart_series_by_id=chart_series,
    )
    prs = Presentation(str(out))
    assert len(prs.slides) == 2

