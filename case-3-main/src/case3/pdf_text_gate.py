"""PDF text-layer gate: digital vs scan. pypdfium2 only — no OCR.

Logic aligned with bam `ingest_parse.pdf_triage` (born-digital path).
"""

from __future__ import annotations

import warnings
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

PageKind = Literal["digital", "hybrid", "full_scan", "blank"]

MIN_CHARS = 20
SCAN_COVERAGE = 0.5
GARBAGE_SHARE = 0.3
INVISIBLE_SHARE = 0.8


class PdfPageWarning(UserWarning):
    """Page without a usable text layer."""


@dataclass(frozen=True)
class PageInfo:
    number: int
    kind: PageKind
    chars: int
    image_coverage: float
    vector_only: bool = False


@dataclass(frozen=True)
class TriageResult:
    pages: list[PageInfo]

    @property
    def usable(self) -> bool:
        # Vector-only pages are tagged "digital" with 0 chars — not enough to extract.
        return any(
            p.kind in ("digital", "hybrid") and p.chars >= MIN_CHARS
            for p in self.pages
        )

    @property
    def scan_pages(self) -> list[int]:
        return [p.number for p in self.pages if p.kind == "full_scan"]

    def warn(self) -> None:
        for p in self.pages:
            if p.kind == "hybrid":
                warnings.warn(
                    f"pdf page {p.number} classified as hybrid "
                    "(scan with OCR text layer); text layer used as is",
                    PdfPageWarning,
                    stacklevel=2,
                )
            elif p.kind == "blank":
                warnings.warn(
                    f"pdf page {p.number} classified as blank; skipped",
                    PdfPageWarning,
                    stacklevel=2,
                )
            elif p.vector_only:
                warnings.warn(
                    f"pdf page {p.number} has only vector graphics, no text",
                    PdfPageWarning,
                    stacklevel=2,
                )


def triage_pdf(path: Path | str) -> TriageResult:
    import pypdfium2 as pdfium
    import pypdfium2.raw as pdfium_c

    try:
        pdf = pdfium.PdfDocument(str(path))
    except pdfium.PdfiumError as exc:
        if "password" in str(exc).lower():
            raise ValueError(
                f"{path}: PDF is password-protected; remove the password and retry"
            ) from exc
        raise ValueError(f"Cannot open PDF {path}: {exc}") from exc

    pages: list[PageInfo] = []
    try:
        for index in range(len(pdf)):
            page = pdf[index]
            try:
                kind, chars, coverage = _classify(page, pdfium_c)
            finally:
                page.close()
            vector_only = kind == "digital" and chars == 0 and coverage == 0
            pages.append(
                PageInfo(
                    number=index + 1,
                    kind=kind,
                    chars=chars,
                    image_coverage=round(coverage, 3),
                    vector_only=vector_only,
                )
            )
    finally:
        pdf.close()
    return TriageResult(pages=pages)


def _classify(page: object, pdfium_c: object) -> tuple[PageKind, int, float]:
    width, height = page.get_size()  # type: ignore[attr-defined]
    area = max(width * height, 1.0)
    covered = 0.0
    drawn = False
    texts = 0
    invisible = 0
    for obj in page.get_objects():  # type: ignore[attr-defined]
        if obj.type == pdfium_c.FPDF_PAGEOBJ_TEXT:  # type: ignore[attr-defined]
            texts += 1
            mode = pdfium_c.FPDFTextObj_GetTextRenderMode(obj.raw)  # type: ignore[attr-defined]
            invisible += mode == pdfium_c.FPDF_TEXTRENDERMODE_INVISIBLE  # type: ignore[attr-defined]
            continue
        drawn = True
        if obj.type == pdfium_c.FPDF_PAGEOBJ_IMAGE:  # type: ignore[attr-defined]
            left, bottom, right, top = obj.get_bounds()
            w = min(right, width) - max(left, 0.0)
            h = min(top, height) - max(bottom, 0.0)
            covered += max(w, 0.0) * max(h, 0.0)
    coverage = min(covered / area, 1.0)

    textpage = page.get_textpage()  # type: ignore[attr-defined]
    try:
        text = textpage.get_text_range()
    finally:
        textpage.close()
    chars = sum(not c.isspace() for c in text)
    garbage = text.count("\ufffd")

    if chars >= MIN_CHARS:
        if garbage / chars >= GARBAGE_SHARE:
            return "full_scan", chars, coverage
        ocr_layer = coverage >= SCAN_COVERAGE and invisible >= INVISIBLE_SHARE * texts
        return ("hybrid" if ocr_layer else "digital"), chars, coverage
    if coverage >= SCAN_COVERAGE:
        return "full_scan", chars, coverage
    if chars == 0 and not drawn:
        return "blank", chars, coverage
    return "digital", chars, coverage
