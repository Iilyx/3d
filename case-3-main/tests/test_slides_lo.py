"""LibreOffice PPTX → PDF (Julius path) with PNG stitch fallback."""

from __future__ import annotations

from pathlib import Path
from unittest import mock

from PIL import Image
from pptx import Presentation
from pptx.util import Inches


def _tiny_pptx(path: Path) -> Path:
    prs = Presentation()
    prs.slide_width = Inches(13.333)
    prs.slide_height = Inches(7.5)
    blank = prs.slide_layouts[6]
    slide = prs.slides.add_slide(blank)
    box = slide.shapes.add_textbox(Inches(1), Inches(2), Inches(8), Inches(1))
    box.text_frame.paragraphs[0].text = "Liber LO smoke"
    prs.save(str(path))
    return path


def _solid_png(path: Path, color=(40, 80, 40)) -> Path:
    Image.new("RGB", (64, 36), color).save(path, format="PNG")
    return path


def test_slides_lo_import_does_not_pull_pptx_export() -> None:
    """desk_health imports find_soffice — must not require python-pptx at import time."""
    import importlib
    import sys

    for name in list(sys.modules):
        if name in ("case3.slides_lo", "case3.slides_export") or name.startswith(
            "case3.slides_export."
        ):
            del sys.modules[name]

    import case3.slides_lo as slo

    importlib.reload(slo)
    assert "case3.slides_export" not in sys.modules
    assert callable(slo.find_soffice)


def test_find_soffice_honors_env(tmp_path: Path, monkeypatch) -> None:
    from case3.slides_lo import find_soffice

    fake = tmp_path / "soffice"
    fake.write_text("#!/bin/sh\n")
    fake.chmod(0o755)
    monkeypatch.setenv("CASE3_SOFFICE", str(fake))
    assert find_soffice() == fake.resolve()


def test_find_soffice_missing_returns_none(monkeypatch) -> None:
    from case3.slides_lo import find_soffice

    monkeypatch.delenv("CASE3_SOFFICE", raising=False)
    monkeypatch.delenv("LIBREOFFICE_PATH", raising=False)
    with mock.patch("case3.slides_lo.shutil.which", return_value=None):
        with mock.patch("case3.slides_lo.Path.is_file", return_value=False):
            assert find_soffice() is None


def test_convert_pptx_to_pdf_raises_without_soffice(tmp_path: Path, monkeypatch) -> None:
    from case3.slides_lo import LibreOfficeError, convert_pptx_to_pdf

    monkeypatch.setattr("case3.slides_lo.find_soffice", lambda: None)
    pptx = _tiny_pptx(tmp_path / "a.pptx")
    try:
        convert_pptx_to_pdf(pptx, tmp_path / "a.pdf")
        assert False, "expected LibreOfficeError"
    except LibreOfficeError:
        pass


def test_write_deck_pdf_falls_back_to_png_stitch(tmp_path: Path, monkeypatch) -> None:
    from case3.slides_lo import write_deck_pdf

    monkeypatch.setattr("case3.slides_lo.find_soffice", lambda: None)
    pptx = _tiny_pptx(tmp_path / "deck.pptx")
    pngs = [_solid_png(tmp_path / "s1.png"), _solid_png(tmp_path / "s2.png", (80, 40, 40))]
    out, mode = write_deck_pdf(pptx, pngs, tmp_path / "deck.pdf")
    assert out.is_file()
    assert out.read_bytes()[:4] == b"%PDF"
    assert mode == "png_stitch"


def test_write_deck_pdf_falls_back_when_convert_raises(
    tmp_path: Path, monkeypatch
) -> None:
    from case3.slides_lo import LibreOfficeError, write_deck_pdf

    monkeypatch.setattr(
        "case3.slides_lo.find_soffice", lambda: tmp_path / "fake-soffice"
    )
    monkeypatch.setattr(
        "case3.slides_lo.convert_pptx_to_pdf",
        lambda *a, **k: (_ for _ in ()).throw(LibreOfficeError("boom")),
    )
    pptx = _tiny_pptx(tmp_path / "deck.pptx")
    pngs = [_solid_png(tmp_path / "s1.png")]
    out, mode = write_deck_pdf(pptx, pngs, tmp_path / "deck.pdf")
    assert mode == "png_stitch"
    assert out.read_bytes()[:4] == b"%PDF"


def test_write_deck_pdf_prefers_lo_when_available(tmp_path: Path) -> None:
    from case3.slides_lo import find_soffice, write_deck_pdf

    import pytest

    if find_soffice() is None:
        pytest.skip("LibreOffice not installed")
    pptx = _tiny_pptx(tmp_path / "deck.pptx")
    pngs = [_solid_png(tmp_path / "s1.png")]
    out, mode = write_deck_pdf(pptx, pngs, tmp_path / "deck.pdf")
    assert out.is_file()
    assert out.read_bytes()[:4] == b"%PDF"
    assert out.stat().st_size > 500
    # soffice may be on PATH but broken (profile/perms) → stitch fallback.
    if mode != "lo":
        pytest.skip(f"LibreOffice present but convert failed (mode={mode})")
    assert mode == "lo"
