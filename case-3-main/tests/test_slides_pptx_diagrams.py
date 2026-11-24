"""Tests for PPTX native diagram shapes, layout, and fail-safe fallback."""

from __future__ import annotations

import pytest


def test_parse_mermaid_flowchart_td():
    from case3.slides_pptx_diagrams import parse_mermaid_flowchart

    mermaid = """flowchart TD
    A([Начало]) --> B[Сбор метрик]
    B --> C{Критерии ок?}
    C -->|Да| D[Формирование отчёта]
    C -->|Нет| E[План корректировок]
    class A start
    class C decision
    class D ok
    class E warn
    """
    g = parse_mermaid_flowchart(mermaid)
    assert g is not None
    assert g.direction == "TD"
    assert len(g.nodes) == 5
    assert g.nodes["A"].shape == "capsule"
    assert g.nodes["A"].role == "start"
    assert g.nodes["A"].label == "Начало"
    assert g.nodes["B"].shape == "rect"
    assert g.nodes["C"].shape == "diamond"
    assert g.nodes["C"].role == "decision"
    assert len(g.edges) == 4
    yes_edge = next(e for e in g.edges if e.src == "C" and e.dst == "D")
    assert yes_edge.label == "Да"


def test_parse_mermaid_rejects_non_flowchart():
    from case3.slides_pptx_diagrams import parse_mermaid_flowchart

    assert parse_mermaid_flowchart("sequenceDiagram\nAlice->>Bob: Hello") is None
    assert parse_mermaid_flowchart("mindmap\n  root((Idea))") is None
    assert parse_mermaid_flowchart("timeline\n  title 2026") is None
    assert parse_mermaid_flowchart("stateDiagram-v2\n  [*] --> State1") is None


def test_parse_mermaid_flowchart_lr_and_classes():
    from case3.slides_pptx_diagrams import parse_mermaid_flowchart

    mermaid = """flowchart LR
    In[(БД Заказов)] --> Process[Обработка]:::process
    Process --> Out([Успешно отправлено]):::ok
    """
    g = parse_mermaid_flowchart(mermaid)
    assert g is not None
    assert g.direction == "LR"
    assert g.nodes["In"].shape == "cylinder"
    assert g.nodes["In"].role == "data"
    assert g.nodes["Process"].role == "process"
    assert g.nodes["Out"].shape == "capsule"
    assert g.nodes["Out"].role == "ok"


def test_layout_computes_valid_bounds():
    from case3.slides_pptx_diagrams import compute_diagram_layout, parse_mermaid_flowchart

    mermaid = """flowchart TD
    A([Начало]) --> B[Этап 1]
    B --> C[Этап 2]
    """
    g = parse_mermaid_flowchart(mermaid)
    assert g is not None
    layout = compute_diagram_layout(g, left=1.0, top=1.0, width=6.0, height=4.0)
    assert len(layout.boxes) == 3
    for nid, box in layout.boxes.items():
        assert box.x >= 1.0 - 1e-4
        assert box.y >= 1.0 - 1e-4
        assert box.x + box.w <= 7.0 + 1e-4
        assert box.y + box.h <= 5.0 + 1e-4
    # Vertical ordering in TD: y(A) < y(B) < y(C)
    assert layout.boxes["A"].y < layout.boxes["B"].y < layout.boxes["C"].y


def test_layout_handles_cycles_and_branching():
    from case3.slides_pptx_diagrams import compute_diagram_layout, parse_mermaid_flowchart

    mermaid = """flowchart TD
    A([Старт]) --> B{Проверка}
    B -->|Ок| C([Финиш])
    B -->|Ошибка| D[Доработка]
    D --> B
    """
    g = parse_mermaid_flowchart(mermaid)
    assert g is not None
    layout = compute_diagram_layout(g, left=0.5, top=0.5, width=7.0, height=5.0)
    assert len(layout.boxes) == 4
    # All boxes within bounds
    for nid, box in layout.boxes.items():
        assert box.x >= 0.5 - 1e-4
        assert box.y >= 0.5 - 1e-4
        assert box.x + box.w <= 7.5 + 1e-4
        assert box.y + box.h <= 5.5 + 1e-4
    # B and D should have valid positions without crashing from cycle D -> B
    assert layout.boxes["A"].y < layout.boxes["B"].y


def test_add_native_diagram_success():
    from pptx import Presentation
    from pptx.enum.shapes import MSO_SHAPE
    from pptx.util import Inches
    from case3.slides_pptx_diagrams import add_native_diagram

    prs = Presentation()
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    spec = {
        "id": "dia_01",
        "type": "flowchart",
        "title": "Процесс аудита",
        "mermaid": """flowchart TD
        A([Старт]) --> B[Анализ данных]
        B --> C{Соответствие?}
        C -->|Да| D([Успех])
        """,
    }
    placed = add_native_diagram(
        slide,
        spec,
        left=Inches(1),
        top=Inches(1),
        width=Inches(6),
        height=Inches(4),
        colors={"ink": "1a2e22", "paper": "ffffff"},
        palette="editorial",
    )
    assert placed is True
    # Verify shapes were created
    shape_types = []
    for s in slide.shapes:
        try:
            shape_types.append(s.auto_shape_type)
        except (ValueError, AttributeError):
            pass
    assert MSO_SHAPE.ROUNDED_RECTANGLE in shape_types
    assert MSO_SHAPE.DIAMOND in shape_types
    # Nodes + connectors + labels
    assert len(slide.shapes) >= 4


def test_add_native_diagram_fallback_on_unsupported():
    from pptx import Presentation
    from pptx.util import Inches
    from case3.slides_pptx_diagrams import add_native_diagram

    prs = Presentation()
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    spec = {"id": "dia_02", "type": "sequence", "mermaid": "sequenceDiagram\nA->>B: ping"}
    placed = add_native_diagram(
        slide,
        spec,
        left=Inches(1),
        top=Inches(1),
        width=Inches(5),
        height=Inches(4),
        colors={},
    )
    assert placed is False
    assert len(slide.shapes) == 0


def test_add_native_diagram_fallback_on_over_capacity():
    from pptx import Presentation
    from pptx.util import Inches
    from case3.slides_pptx_diagrams import add_native_diagram

    prs = Presentation()
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    # 12 nodes > 10 limit
    nodes = " --> ".join([f"N{i}" for i in range(12)])
    spec = {"id": "dia_03", "type": "flowchart", "mermaid": f"flowchart TD\n{nodes}"}
    placed = add_native_diagram(
        slide,
        spec,
        left=Inches(1),
        top=Inches(1),
        width=Inches(5),
        height=Inches(4),
        colors={},
    )
    assert placed is False
    assert len(slide.shapes) == 0


def test_build_native_pptx_with_diagram(tmp_path):
    from pptx import Presentation
    from case3.slides_pptx_native import build_native_pptx

    deck = {
        "title": "Тестовый отчёт",
        "style": {"theme_pack": "atelier"},
        "slides": [
            {
                "id": "s1",
                "layout": "media_hero",
                "title": "Схема согласования",
                "media_id": "dia_01",
            }
        ],
    }
    diagrams_by_id = {
        "dia_01": {
            "id": "dia_01",
            "type": "flowchart",
            "title": "Схема согласования",
            "mermaid": "flowchart TD\nA([Вход]) --> B[Проверка] --> C([Выход])",
        }
    }
    out_pptx = tmp_path / "deck.pptx"
    res = build_native_pptx(deck, out_pptx, diagrams_by_id=diagrams_by_id)
    assert res.is_file()
    prs = Presentation(str(res))
    assert len(prs.slides) == 1
    # Check that shapes were created (nodes + connectors) rather than single picture or empty
    assert len(prs.slides[0].shapes) >= 5


def _make_dummy_png(path) -> None:
    from PIL import Image

    im = Image.new("RGB", (100, 100), color=(220, 220, 220))
    im.save(str(path))


@pytest.mark.parametrize(
    ("dtype", "mermaid_body"),
    [
        ("sequence", "sequenceDiagram\nAlice->>Bob: Ping\nBob-->>Alice: Pong"),
        ("stateDiagram", "stateDiagram-v2\n  [*] --> Active\n  Active --> [*]"),
    ],
)
def test_non_supported_diagrams_fallback_to_raster(tmp_path, dtype, mermaid_body):
    from pptx import Presentation
    from pptx.enum.shapes import MSO_SHAPE_TYPE
    from case3.slides_pptx_native import build_native_pptx

    png_path = tmp_path / f"dia_{dtype}.png"
    _make_dummy_png(png_path)

    deck = {
        "title": "Тест фоллбэка",
        "style": {"theme_pack": "atelier"},
        "slides": [
            {
                "id": "s1",
                "layout": "media_hero",
                "title": f"Диаграмма {dtype}",
                "media_id": f"dia_{dtype}",
            }
        ],
    }
    diagrams_by_id = {
        f"dia_{dtype}": {
            "id": f"dia_{dtype}",
            "type": dtype,
            "title": f"Диаграмма {dtype}",
            "mermaid": mermaid_body,
        }
    }
    media_by_id = {f"dia_{dtype}": png_path}

    out_pptx = tmp_path / f"deck_{dtype}.pptx"
    res = build_native_pptx(
        deck,
        out_pptx,
        media_by_id=media_by_id,
        diagrams_by_id=diagrams_by_id,
    )
    assert res.is_file()
    prs = Presentation(str(res))
    slide = prs.slides[0]
    # In fallback, slide contains a PICTURE shape for the raster PNG
    picture_shapes = [s for s in slide.shapes if s.shape_type == MSO_SHAPE_TYPE.PICTURE]
    assert len(picture_shapes) == 1


@pytest.mark.parametrize(
    ("dtype", "mermaid_body"),
    [
        ("mindmap", "mindmap\n  root((Цели))\n    Маркетинг\n    Продажи"),
        ("timeline", "timeline\n  title История\n  2024 : Старт\n  2025 : Рост"),
    ],
)
def test_native_diagram_timeline_and_mindmap_in_deck(tmp_path, dtype, mermaid_body):
    from pptx import Presentation
    from pptx.enum.shapes import MSO_SHAPE_TYPE
    from case3.slides_pptx_native import build_native_pptx

    png_path = tmp_path / f"dia_{dtype}.png"
    _make_dummy_png(png_path)

    deck = {
        "title": "Тест нативных диаграмм",
        "style": {"theme_pack": "atelier"},
        "slides": [
            {
                "id": "s1",
                "layout": "media_hero",
                "title": f"Нативная диаграмма {dtype}",
                "media_id": f"dia_{dtype}",
            }
        ],
    }
    diagrams_by_id = {
        f"dia_{dtype}": {
            "id": f"dia_{dtype}",
            "type": dtype,
            "title": f"Нативная диаграмма {dtype}",
            "mermaid": mermaid_body,
        }
    }
    media_by_id = {f"dia_{dtype}": png_path}

    out_pptx = tmp_path / f"deck_native_{dtype}.pptx"
    res = build_native_pptx(
        deck,
        out_pptx,
        media_by_id=media_by_id,
        diagrams_by_id=diagrams_by_id,
    )
    assert res.is_file()
    prs = Presentation(str(res))
    slide = prs.slides[0]
    # Native diagrams place vector shapes and connectors; no PICTURE fallback
    picture_shapes = [s for s in slide.shapes if s.shape_type == MSO_SHAPE_TYPE.PICTURE]
    assert len(picture_shapes) == 0
    assert len(slide.shapes) >= 3


def test_mixed_deck_has_native_and_raster_slides(tmp_path):
    from pptx import Presentation
    from pptx.enum.shapes import MSO_SHAPE, MSO_SHAPE_TYPE
    from case3.slides_pptx_native import build_native_pptx

    png_seq = tmp_path / "dia_seq.png"
    _make_dummy_png(png_seq)

    deck = {
        "title": "Смешанная презентация",
        "style": {"theme_pack": "ocean"},
        "slides": [
            {
                "id": "s1",
                "layout": "media_hero",
                "title": "Нативный процесс",
                "media_id": "dia_flow",
            },
            {
                "id": "s2",
                "layout": "media_hero",
                "title": "Растровый sequence",
                "media_id": "dia_seq",
            },
        ],
    }
    diagrams_by_id = {
        "dia_flow": {
            "id": "dia_flow",
            "type": "flowchart",
            "title": "Нативный процесс",
            "mermaid": "flowchart LR\nStart([Старт]) --> Check{Проверка} --> End([Финиш])",
        },
        "dia_seq": {
            "id": "dia_seq",
            "type": "sequence",
            "title": "Растровый sequence",
            "mermaid": "sequenceDiagram\nClient->>Server: Request",
        },
    }
    media_by_id = {"dia_seq": png_seq}

    out_pptx = tmp_path / "mixed_deck.pptx"
    res = build_native_pptx(
        deck,
        out_pptx,
        media_by_id=media_by_id,
        diagrams_by_id=diagrams_by_id,
    )
    assert res.is_file()
    prs = Presentation(str(res))
    assert len(prs.slides) == 2

    # Slide 1 (flowchart): has native shapes (diamond, rounded rect, connectors), no pictures
    s1_pics = [s for s in prs.slides[0].shapes if s.shape_type == MSO_SHAPE_TYPE.PICTURE]
    assert len(s1_pics) == 0
    s1_auto = []
    for s in prs.slides[0].shapes:
        try:
            s1_auto.append(s.auto_shape_type)
        except (ValueError, AttributeError):
            pass
    assert MSO_SHAPE.DIAMOND in s1_auto

    # Slide 2 (sequence): has picture shape
    s2_pics = [s for s in prs.slides[1].shapes if s.shape_type == MSO_SHAPE_TYPE.PICTURE]
    assert len(s2_pics) == 1


def test_parse_mermaid_with_subgraphs():
    from case3.slides_pptx_diagrams import parse_mermaid_flowchart
    mermaid = """flowchart TD
    subgraph TeamA [Команда Аналитики]
        A[Сбор данных] --> B[Анализ]
    end
    subgraph TeamB [Команда Разработки]
        C[Разработка] --> D[Релиз]
    end
    B --> C
    """
    g = parse_mermaid_flowchart(mermaid)
    assert g is not None
    assert len(g.subgraphs) == 2
    assert g.subgraphs[0].title == "Команда Аналитики"
    assert g.subgraphs[0].node_ids == ["A", "B"]
    assert g.subgraphs[1].title == "Команда Разработки"
    assert g.subgraphs[1].node_ids == ["C", "D"]


def test_add_native_diagram_renders_subgraph_frames():
    from pptx import Presentation
    from pptx.util import Inches
    from case3.slides_pptx_diagrams import add_native_diagram

    prs = Presentation()
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    spec = {
        "id": "dia_sub",
        "type": "flowchart",
        "title": "Процесс с командами",
        "mermaid": """flowchart TD
        subgraph Alpha [Отдел Маркетинга]
            A[Лид] --> B[Квалификация]
        end
        subgraph Beta [Отдел Продаж]
            C[Звонок] --> D[Сделка]
        end
        B --> C
        """,
    }
    placed = add_native_diagram(
        slide, spec, left=Inches(1), top=Inches(1), width=Inches(8), height=Inches(5), colors={"muted": "#687564"}
    )
    assert placed is True
    # In addition to 4 nodes + 3 connectors, there should be 2 subgraph container shapes
    assert len(slide.shapes) >= 9


def test_add_native_diagram_timeline():
    from pptx import Presentation
    from pptx.util import Inches
    from case3.slides_pptx_diagrams import add_native_diagram

    prs = Presentation()
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    spec = {
        "id": "dia_tl",
        "type": "timeline",
        "title": "Дорожная карта",
        "mermaid": """timeline
        title Дорожная карта 2024-2026
        2024 : Исследование : MVP
        2025 : Масштабирование : B2B пилоты
        2026 : Лидерство на рынке
        """,
    }
    placed = add_native_diagram(
        slide, spec, left=Inches(1), top=Inches(1), width=Inches(8), height=Inches(4), colors={"accent": "#275035"}
    )
    assert placed is True
    # At least spine line + 3 period badges + event cards
    assert len(slide.shapes) >= 4


def test_add_native_diagram_mindmap():
    from pptx import Presentation
    from pptx.util import Inches
    from case3.slides_pptx_diagrams import add_native_diagram

    prs = Presentation()
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    spec = {
        "id": "dia_mm",
        "type": "mindmap",
        "title": "Карта целей",
        "mermaid": """mindmap
          root((Стратегия))
            Маркетинг
              Лидогенерация
            Продажи
              Enterprise
        """,
    }
    placed = add_native_diagram(
        slide, spec, left=Inches(1), top=Inches(1), width=Inches(8), height=Inches(5), colors={"accent": "#275035"}
    )
    assert placed is True
    # Central root + 2 level-1 branches + 2 level-2 leaves + connectors
    assert len(slide.shapes) >= 5


def test_parse_mermaid_chained_and_ampersand_edges():
    from case3.slides_pptx_diagrams import parse_mermaid_flowchart

    mermaid = """flowchart LR
    A([Вход]) --> B[Проверка] --> C{Решение}
    C -->|Ок| D[Отчёт] & E[Архив]
    """
    g = parse_mermaid_flowchart(mermaid)
    assert g is not None
    pairs = [(e.src, e.dst) for e in g.edges]
    assert ("A", "B") in pairs
    assert ("B", "C") in pairs
    assert ("C", "D") in pairs
    assert ("C", "E") in pairs








