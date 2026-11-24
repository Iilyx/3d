"""Born-digital office/PDF → Markdown for Liber Source draft (no OCR).

Primary extractors (desk-light):
- TXT/MD — decode
- DOCX — python-docx (already in case-3)
- PDF — pypdfium2 text layer + triage gate
- DOC/RTF — LibreOffice → DOCX when soffice present

Docling is intentionally not required (heavy torch stack).
"""

from __future__ import annotations

import codecs
import re
import tempfile
import warnings
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterator, Literal

from case3.pdf_text_gate import PdfPageWarning, triage_pdf

SupportedFormat = Literal["txt", "md", "pdf", "docx", "doc", "docm", "rtf"]

_EXT_MAP: dict[str, SupportedFormat] = {
    ".txt": "txt",
    ".md": "md",
    ".markdown": "md",
    ".pdf": "pdf",
    ".docx": "docx",
    ".doc": "doc",
    ".docm": "docm",
    ".rtf": "rtf",
}

_IMAGE_EXT = frozenset(
    {".png", ".jpg", ".jpeg", ".tif", ".tiff", ".webp", ".bmp", ".gif"}
)

_BLANK_LINE = re.compile(r"\n[ \t]*\n")
_WS = re.compile(r"[ \t]+\n")

DEFAULT_MAX_MARKDOWN_BYTES = 2 * 1024 * 1024
DEFAULT_MAX_UPLOAD_BYTES = 20 * 1024 * 1024
# Wide tables: TSV for the model (UI shows native PDF, not this text).
MAX_TABLE_COLS = 12
MAX_TABLE_ROWS = 80


class SourceIngestError(Exception):
    """Base ingest failure with stable ``code`` for API mapping."""

    def __init__(self, message: str, *, code: str = "ingest_error") -> None:
        super().__init__(message)
        self.message = message
        self.code = code


class UnsupportedSourceFormatError(SourceIngestError):
    def __init__(self, message: str) -> None:
        super().__init__(message, code="unsupported_format")


class IngestDependencyError(SourceIngestError):
    """Missing optional native stack (e.g. pypdfium2)."""

    def __init__(self, message: str) -> None:
        super().__init__(message, code="ingest_dependency")


# Back-compat alias used in early tests / imports
DoclingUnavailableError = IngestDependencyError


class ScanPdfError(SourceIngestError):
    def __init__(self, message: str) -> None:
        super().__init__(message, code="scan_pdf")


class OfficeConvertError(SourceIngestError):
    def __init__(self, message: str) -> None:
        super().__init__(message, code="office_convert")


@dataclass(frozen=True)
class IngestResult:
    markdown: str
    format: SupportedFormat
    filename: str
    warnings: list[str] = field(default_factory=list)


def detect_source_format(path: Path | str) -> SupportedFormat:
    suffix = Path(path).suffix.lower()
    if suffix in _IMAGE_EXT:
        raise UnsupportedSourceFormatError(
            "Это изображение — прикрепите как фото-иллюстрацию, "
            "а не как Source. Для Source нужен PDF/DOCX/TXT/RTF с текстовым слоем."
        )
    fmt = _EXT_MAP.get(suffix)
    if fmt is None:
        raise UnsupportedSourceFormatError(
            f"Формат «{suffix or 'без расширения'}» не поддерживается. "
            "Нужны: .pdf, .docx, .doc, .rtf, .txt, .md"
        )
    return fmt


def file_to_markdown(
    path: Path | str,
    *,
    max_markdown_bytes: int = DEFAULT_MAX_MARKDOWN_BYTES,
) -> IngestResult:
    path = Path(path)
    if not path.is_file():
        raise FileNotFoundError(path)
    fmt = detect_source_format(path)
    warns: list[str] = []

    if fmt in {"txt", "md"}:
        md = _txt_to_markdown(path) if fmt == "txt" else _read_text(path)
    elif fmt == "pdf":
        md, warns = _pdf_to_markdown(path)
    elif fmt == "docx":
        md = _docx_to_markdown(path)
    elif fmt in {"doc", "rtf", "docm"}:
        md = _legacy_office_to_markdown(path, fmt)
    else:  # pragma: no cover
        raise UnsupportedSourceFormatError(f"unexpected format {fmt}")

    raw = md.encode("utf-8")
    if len(raw) > max_markdown_bytes:
        raise UnsupportedSourceFormatError(
            f"Текст Source после конвертации больше лимита 2 MiB "
            f"({len(raw)} байт). Уменьшите документ."
        )
    if not md.strip():
        raise SourceIngestError(
            "После конвертации получился пустой текст. Проверьте файл.",
            code="empty_result",
        )
    return IngestResult(
        markdown=md if md.endswith("\n") else md + "\n",
        format=fmt,
        filename=path.name,
        warnings=warns,
    )


def _read_text(path: Path) -> str:
    return _decode_txt(path.read_bytes()).replace("\r\n", "\n").replace("\r", "\n")


def _decode_txt(raw: bytes) -> str:
    if raw.startswith(codecs.BOM_UTF8):
        return raw.decode("utf-8-sig")
    if raw.startswith((codecs.BOM_UTF16_LE, codecs.BOM_UTF16_BE)):
        return raw.decode("utf-16")
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        return raw.decode("cp1251")


def _txt_to_markdown(path: Path) -> str:
    text = _read_text(path)
    paragraphs = [p.strip() for p in _BLANK_LINE.split(text) if p.strip()]
    return "\n\n".join(paragraphs) + "\n" if paragraphs else ""


def _docx_to_markdown(path: Path) -> str:
    from docx import Document
    from docx.table import Table
    from docx.text.paragraph import Paragraph

    document = Document(str(path))
    parts: list[str] = []
    for block in _iter_docx_blocks(document):
        if isinstance(block, Paragraph):
            text = (block.text or "").strip()
            if not text:
                continue
            style = (block.style.name or "").lower() if block.style else ""
            if "heading 1" in style or style == "title":
                parts.append(f"# {text}")
            elif "heading 2" in style:
                parts.append(f"## {text}")
            elif "heading 3" in style:
                parts.append(f"### {text}")
            else:
                parts.append(text)
        elif isinstance(block, Table):
            table_md = _table_to_markdown(block)
            if table_md:
                parts.append(table_md)
    # Fallback if body XML order failed but paragraphs exist
    if not parts:
        for p in document.paragraphs:
            text = (p.text or "").strip()
            if text:
                parts.append(text)
        for table in document.tables:
            table_md = _table_to_markdown(table)
            if table_md:
                parts.append(table_md)
    return "\n\n".join(parts) + ("\n" if parts else "")


def _iter_docx_blocks(document: object) -> Iterator[object]:
    """Yield paragraphs and tables in document order."""
    from docx.oxml.ns import qn
    from docx.table import Table
    from docx.text.paragraph import Paragraph

    body = document.element.body  # type: ignore[attr-defined]
    for child in body.iterchildren():
        if child.tag == qn("w:p"):
            yield Paragraph(child, document)
        elif child.tag == qn("w:tbl"):
            yield Table(child, document)


def _table_to_markdown(table: object) -> str:
    """Grid as a markdown table. Repeated neighbours stay, so columns do not shift."""
    from case3.dashboard_source import table_block

    rows: list[list[str]] = []
    for row in table.rows:  # type: ignore[attr-defined]
        rows.append([" ".join((cell.text or "").split()) for cell in row.cells])
    block, _note = table_block(rows)
    return block


def _pdf_to_markdown(path: Path) -> tuple[str, list[str]]:
    warns: list[str] = []
    try:
        triage = triage_pdf(path)
    except ImportError as exc:
        raise IngestDependencyError(
            "pypdfium2 не установлен. На desk: uv sync "
            "(пакет в основных зависимостях case-3)."
        ) from exc
    except ValueError as exc:
        raise SourceIngestError(str(exc), code="bad_pdf") from exc

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always", PdfPageWarning)
        triage.warn()
    for w in caught:
        if issubclass(w.category, PdfPageWarning):
            warns.append(str(w.message))

    if not triage.usable:
        scans = list(getattr(triage, "scan_pages", []) or [])
        detail = (
            f" страницы-сканы: {', '.join(map(str, scans))}."
            if scans
            else ""
        )
        raise ScanPdfError(
            "В PDF нет пригодного текстового слоя (похоже на скан)."
            f"{detail} OCR в Liber пока не подключён — нужен цифровой PDF/DOCX."
        )

    # Same cells as «В данные»: 64×500, repeated neighbours stay, markdown table.
    from case3.dashboard_source import DashboardSourceError, parse_dashboard

    try:
        result = parse_dashboard(pdf=path)
    except DashboardSourceError as exc:
        if exc.code == "scan_pdf":
            raise ScanPdfError(exc.message) from exc
        if exc.code == "ingest_dependency":
            raise IngestDependencyError(exc.message) from exc
        raise SourceIngestError(exc.message, code=exc.code) from exc
    md = result.markdown
    warns.extend(result.warnings)
    if not md.strip():
        raise ScanPdfError(
            "Из PDF не удалось извлечь текст (пустой текстовый слой или только "
            "картинки). OCR в Liber пока не подключён — нужен цифровой PDF/DOCX."
        )
    if triage.scan_pages:
        warns.append(
            "Часть страниц без текста пропущена (скан): "
            + ", ".join(map(str, triage.scan_pages))
        )
    return md, warns


def _is_plausible_table(rows: list[list[object | None]]) -> bool:
    """Drop chart/axis 'tables' that pdfplumber sometimes invents."""
    if not rows or len(rows) < 2:
        return False
    cells = [c for r in rows for c in r]
    nonempty = [str(c).strip() for c in cells if c is not None and str(c).strip()]
    if len(nonempty) < 4:
        return False
    multiline = sum(1 for c in nonempty if "\n" in c)
    if multiline / max(len(nonempty), 1) > 0.35:
        return False
    # Wide sparse grids (plot labels) — many empties, few real tokens
    empty = sum(1 for c in cells if c is None or not str(c).strip())
    if len(cells) >= 20 and empty / len(cells) > 0.55:
        return False
    width = max(len(r) for r in rows)
    if width >= 7 and len(rows) <= 12 and empty / max(len(cells), 1) > 0.4:
        return False
    return True


def _cells_to_tsv(rows: list[list[object | None]]) -> str:
    """Compact TSV for the model — humans see native PDF, not this block."""
    width = max((len(r) for r in rows), default=0)
    if width == 0 or not rows:
        return ""
    orig_rows, orig_cols = len(rows), width
    use_cols = min(width, MAX_TABLE_COLS)
    use_rows = rows[:MAX_TABLE_ROWS]
    norm: list[list[str]] = []
    for row in use_rows:
        cells = [
            " ".join(str(c).replace("\n", " ").replace("\t", " ").split())
            if c is not None
            else ""
            for c in row
        ]
        if len(cells) < use_cols:
            cells.extend([""] * (use_cols - len(cells)))
        cleaned: list[str] = []
        for cell in cells[:use_cols]:
            if cleaned and cleaned[-1] == cell and cell != "":
                continue
            cleaned.append(cell)
        while len(cleaned) < use_cols:
            cleaned.append("")
        norm.append(cleaned[:use_cols])
    lines = ["\t".join(r) for r in norm]
    if orig_cols > MAX_TABLE_COLS or orig_rows > MAX_TABLE_ROWS:
        lines.append(
            f"… truncated table {orig_cols}×{orig_rows} → {use_cols}×{len(norm)}"
        )
    return "\n".join(lines)


def _pdf_text_layer_markdown(path: Path) -> str:
    """Prefer pdfplumber (tables → TSV); fall back to pypdfium2 text."""
    try:
        return _pdf_via_pdfplumber(path)
    except ImportError:
        return _pdf_via_pdfium(path)


def _pdf_via_pdfplumber(path: Path) -> str:
    import pdfplumber

    parts: list[str] = []
    with pdfplumber.open(str(path)) as pdf:
        multi = len(pdf.pages) > 1
        for index, page in enumerate(pdf.pages):
            chunks: list[str] = []
            table_mds: list[str] = []
            found = page.find_tables() if hasattr(page, "find_tables") else []
            bboxes: list[tuple[float, float, float, float]] = []
            for table in found or []:
                rows = table.extract()
                if not rows or not _is_plausible_table(rows):
                    continue
                tsv = _cells_to_tsv(rows)
                if tsv:
                    table_mds.append(tsv)
                    if getattr(table, "bbox", None):
                        bboxes.append(tuple(table.bbox))  # type: ignore[arg-type]

            def _outside_tables(obj: dict) -> bool:
                x0 = float(obj.get("x0", 0))
                x1 = float(obj.get("x1", x0))
                top = float(obj.get("top", 0))
                bottom = float(obj.get("bottom", top))
                cx, cy = (x0 + x1) / 2, (top + bottom) / 2
                for x0b, topb, x1b, bottomb in bboxes:
                    if x0b <= cx <= x1b and topb <= cy <= bottomb:
                        return False
                return True

            filtered = page.filter(_outside_tables) if bboxes else page
            text = (filtered.extract_text() or "").strip()
            if text:
                cleaned = _WS.sub("\n", text.replace("\r", "")).strip()
                if cleaned:
                    chunks.append(cleaned)
            chunks.extend(table_mds)
            if not chunks:
                continue
            body = "\n\n".join(chunks)
            if multi:
                parts.append(f"## Страница {index + 1}\n\n{body}")
            else:
                parts.append(body)
    return "\n\n".join(parts) + ("\n" if parts else "")


def _pdf_via_pdfium(path: Path) -> str:
    import pypdfium2 as pdfium

    pdf = pdfium.PdfDocument(str(path))
    parts: list[str] = []
    try:
        for index in range(len(pdf)):
            page = pdf[index]
            try:
                textpage = page.get_textpage()
                try:
                    text = textpage.get_text_range()
                finally:
                    textpage.close()
            finally:
                page.close()
            cleaned = _WS.sub("\n", (text or "").replace("\r", "")).strip()
            if not cleaned:
                continue
            if len(pdf) > 1:
                parts.append(f"## Страница {index + 1}\n\n{cleaned}")
            else:
                parts.append(cleaned)
    finally:
        pdf.close()
    return "\n\n".join(parts) + ("\n" if parts else "")


def _legacy_office_to_markdown(path: Path, fmt: SupportedFormat) -> str:
    from case3.office_convert import LibreOfficeNotFoundError, convert_doc_to_docx

    with tempfile.TemporaryDirectory(prefix="case3-ingest-") as tmp:
        try:
            if fmt == "docm":
                docx = _docm_to_docx(path, Path(tmp))
            else:
                docx = convert_doc_to_docx(path, output_dir=Path(tmp))
        except LibreOfficeNotFoundError as exc:
            raise OfficeConvertError(str(exc)) from exc
        except Exception as exc:  # noqa: BLE001
            raise OfficeConvertError(str(exc)) from exc
        return _docx_to_markdown(docx)


def _docm_to_docx(src: Path, output_dir: Path) -> Path:
    import zipfile

    main_old = b"application/vnd.ms-word.document.macroEnabled.main+xml"
    main_new = (
        b"application/vnd.openxmlformats-officedocument."
        b"wordprocessingml.document.main+xml"
    )
    out = output_dir / f"{src.stem}.docx"
    with zipfile.ZipFile(src) as zin, zipfile.ZipFile(
        out, "w", zipfile.ZIP_DEFLATED
    ) as zout:
        for info in zin.infolist():
            data = zin.read(info)
            if info.filename == "[Content_Types].xml":
                data = data.replace(main_old, main_new)
            zout.writestr(info, data)
    return out
