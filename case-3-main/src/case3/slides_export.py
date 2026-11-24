"""Build image-only PPTX and multipage PDF from slide PNGs."""

from __future__ import annotations

from pathlib import Path

from PIL import Image
from pptx import Presentation
from pptx.util import Inches

# Standard 16:9 widescreen (inches).
_DEFAULT_W_IN = 13.333
_DEFAULT_H_IN = 7.5


def build_image_pptx(
    png_paths: list[Path],
    dest: Path,
    *,
    width_in: float = _DEFAULT_W_IN,
    height_in: float = _DEFAULT_H_IN,
) -> Path:
    """One blank 16:9 slide per PNG; picture covers the full slide."""
    if not png_paths:
        raise ValueError("png_paths must be non-empty")
    dest = Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)

    prs = Presentation()
    prs.slide_width = Inches(width_in)
    prs.slide_height = Inches(height_in)
    blank = prs.slide_layouts[6]  # blank

    for png in png_paths:
        p = Path(png)
        if not p.is_file():
            raise FileNotFoundError(p)
        slide = prs.slides.add_slide(blank)
        slide.shapes.add_picture(
            str(p),
            Inches(0),
            Inches(0),
            width=Inches(width_in),
            height=Inches(height_in),
        )

    prs.save(str(dest))
    return dest


def build_deck_pdf(png_paths: list[Path], dest: Path) -> Path:
    """Multipage PDF: one page per PNG (RGB)."""
    if not png_paths:
        raise ValueError("png_paths must be non-empty")
    dest = Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)

    images: list[Image.Image] = []
    try:
        for png in png_paths:
            p = Path(png)
            if not p.is_file():
                raise FileNotFoundError(p)
            im = Image.open(p)
            if im.mode != "RGB":
                im = im.convert("RGB")
            else:
                im.load()
            images.append(im)
        first, rest = images[0], images[1:]
        first.save(
            dest,
            format="PDF",
            save_all=bool(rest),
            append_images=rest,
            resolution=150.0,
        )
    finally:
        for im in images:
            im.close()
    return dest
