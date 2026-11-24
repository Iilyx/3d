"""DOC/RTF → DOCX via LibreOffice (optional). Slimmed from bam convert_doc."""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

_SOFFICE_PATHS = (
    "/Applications/LibreOffice.app/Contents/MacOS/soffice",
    "/opt/homebrew/bin/soffice",
    "/usr/local/bin/soffice",
    "/usr/bin/soffice",
    "/usr/lib/libreoffice/program/soffice",
)


class LibreOfficeNotFoundError(RuntimeError):
    """soffice is not installed or not on PATH."""


def _windows_paths() -> list[str]:
    roots: list[str] = []
    for var in ("PROGRAMFILES", "PROGRAMW6432", "PROGRAMFILES(X86)"):
        root = os.environ.get(var)
        if root and root not in roots:
            roots.append(root)
    for default in (r"C:\Program Files", r"C:\Program Files (x86)"):
        if os.name == "nt" and default not in roots:
            roots.append(default)
    return [str(Path(r) / "LibreOffice" / "program" / "soffice.exe") for r in roots]


def _runnable(path: str) -> bool:
    return Path(path).is_file() and (
        path.lower().endswith(".exe") or os.access(path, os.X_OK)
    )


def find_soffice() -> str | None:
    for var in ("LIBREOFFICE_PATH", "SOFFICE"):
        override = os.environ.get(var)
        if override and _runnable(override):
            return override
    found = (
        shutil.which("soffice.exe")
        or shutil.which("soffice")
        or shutil.which("libreoffice")
    )
    if found:
        return found
    return next((p for p in (*_windows_paths(), *_SOFFICE_PATHS) if _runnable(p)), None)


def convert_doc_to_docx(src: Path, *, output_dir: Path) -> Path:
    return _soffice_convert(src, "docx", output_dir)


def convert_to_pdf(src: Path, *, output_dir: Path) -> Path:
    """DOCX/DOC/RTF → PDF for Liber Source preview."""
    return _soffice_convert(src, "pdf", output_dir)


def _soffice_convert(src: Path, target: str, output_dir: Path) -> Path:
    soffice = find_soffice()
    if soffice is None:
        raise LibreOfficeNotFoundError(
            "LibreOffice (soffice) не найден — нужен для .doc/.rtf и PDF-превью DOCX. "
            "Установите LibreOffice или сохраните файл как .docx / .pdf."
        )
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    cmd = [
        soffice,
        "--headless",
        "--nologo",
        "--nofirststartwizard",
        "--convert-to",
        target,
        "--outdir",
        str(output_dir),
        str(src),
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
    out = output_dir / f"{src.stem}.{target}"
    if proc.returncode != 0 or not out.is_file():
        detail = (proc.stderr or proc.stdout or "").strip()[:400]
        raise RuntimeError(
            f"LibreOffice не смог конвертировать {src.name} → {target}"
            + (f": {detail}" if detail else "")
        )
    return out
