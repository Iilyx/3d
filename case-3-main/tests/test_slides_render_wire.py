"""chart_split must receive chart PNG like chart_hero."""

from __future__ import annotations

from pathlib import Path

from case3.slides_render import render_deck_pngs


def test_chart_split_copies_chart_png(tmp_path: Path, monkeypatch) -> None:
    chart = tmp_path / "cht_01.png"
    chart.write_bytes(
        b"\x89PNG\r\n\x1a\n" + b"\x00" * 2400
    )  # fake but file exists

    captured: list[Path] = []

    def _fake_capture(html_dir: Path, dest_png: Path) -> None:
        dest_png.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x01" * 2400)
        captured.append(html_dir)

    monkeypatch.setattr("case3.slides_render.capture_slide_png", _fake_capture)

    deck = {
        "version": 1,
        "aspect": "16:9",
        "palette": "ocean",
        "language": "ru",
        "slides": [
            {
                "id": "s01",
                "layout": "title",
                "title": "T",
                "subtitle": "S",
            },
            {
                "id": "s02",
                "layout": "chart_split",
                "title": "Split",
                "chart_id": "cht_01",
                "body": "Body",
                "bullets": ["A"],
            },
            {
                "id": "s03",
                "layout": "closing",
                "title": "End",
                "bullets": ["X"],
            },
        ],
    }
    # parse not required here — render uses raw dict layouts
    pngs = render_deck_pngs(
        deck,
        work_root=tmp_path / "work",
        out_dir=tmp_path / "out",
        chart_png_by_id={"cht_01": chart},
    )
    assert len(pngs) == 3
    split_work = tmp_path / "work" / "s02"
    assert (split_work / "media.png").is_file()
    html = (split_work / "index.html").read_text(encoding="utf-8")
    assert 'src="media.png"' in html
    assert "Chart unavailable" not in html
    assert "unavailable" not in html.lower() or "Chart unavailable" not in html


def test_render_deck_pngs_cleans_stale_pngs(tmp_path: Path, monkeypatch) -> None:
    def _fake_capture(html_dir: Path, dest_png: Path) -> None:
        dest_png.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x01" * 2400)

    monkeypatch.setattr("case3.slides_render.capture_slide_png", _fake_capture)

    out = tmp_path / "out"
    out.mkdir(parents=True)
    # Pre-existing 5 slides
    for i in range(1, 6):
        (out / f"slide_{i:02d}.png").write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x01" * 2400)

    # Now deck only has 3 slides
    deck = {
        "version": 1,
        "slides": [
            {"id": "s01", "layout": "title", "title": "1"},
            {"id": "s02", "layout": "bullets", "title": "2"},
            {"id": "s03", "layout": "closing", "title": "3"},
        ],
    }
    pngs = render_deck_pngs(
        deck,
        work_root=tmp_path / "work",
        out_dir=out,
    )
    assert len(pngs) == 3
    remaining = sorted(p.name for p in out.glob("slide_*.png"))
    assert remaining == ["slide_01.png", "slide_02.png", "slide_03.png"]

