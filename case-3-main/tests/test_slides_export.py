"""Image PPTX + deck PDF builders."""

from __future__ import annotations

from pathlib import Path

from PIL import Image


def _solid_png(path: Path, size: tuple[int, int] = (64, 36), color=(40, 80, 40)) -> Path:
    Image.new("RGB", size, color).save(path, format="PNG")
    return path


def test_pptx_has_one_slide_per_png(tmp_path: Path) -> None:
    from case3.slides_export import build_image_pptx
    from pptx import Presentation
    from pptx.util import Emu

    pngs = [_solid_png(tmp_path / f"{i}.png") for i in range(2)]
    out = build_image_pptx(pngs, tmp_path / "d.pptx")
    assert out.is_file()
    prs = Presentation(str(out))
    assert len(prs.slides) == 2
    # 16:9 — 13.333" × 7.5"
    assert abs(prs.slide_width - Emu(13.333 * 914400)) < 2000
    assert abs(prs.slide_height - Emu(7.5 * 914400)) < 2000
    for slide in prs.slides:
        pics = [s for s in slide.shapes if s.shape_type is not None]
        assert len(slide.shapes) >= 1
        assert any(getattr(s, "image", None) is not None for s in slide.shapes) or len(pics) >= 1


def test_deck_pdf_written(tmp_path: Path) -> None:
    from case3.slides_export import build_deck_pdf

    pngs = [_solid_png(tmp_path / f"{i}.png", color=(i * 40, 60, 80)) for i in range(2)]
    out = build_deck_pdf(pngs, tmp_path / "d.pdf")
    assert out.is_file()
    assert out.stat().st_size > 100
    # PDF magic
    assert out.read_bytes()[:4] == b"%PDF"


def test_empty_png_list_raises(tmp_path: Path) -> None:
    from case3.slides_export import build_deck_pdf, build_image_pptx

    try:
        build_image_pptx([], tmp_path / "x.pptx")
        assert False
    except ValueError:
        pass
    try:
        build_deck_pdf([], tmp_path / "x.pdf")
        assert False
    except ValueError:
        pass
