"""LibreOffice headless: native PPTX → PDF (Julius path).

Primary export for ``deck_pdf``. Falls back to PNG stitch when soffice is
missing or conversion fails.
"""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
import tempfile
import uuid
from pathlib import Path

from case3.procutil import run_captured

log = logging.getLogger(__name__)

_MAC_SOFFICE = Path("/Applications/LibreOffice.app/Contents/MacOS/soffice")
_LINUX_SOFFICES = (
    Path("/usr/bin/soffice"),
    Path("/usr/lib/libreoffice/program/soffice"),
    Path("/usr/bin/libreoffice"),
)
_WIN_SOFFICES = (
    Path(r"C:\Program Files\LibreOffice\program\soffice.exe"),
    Path(r"C:\Program Files (x86)\LibreOffice\program\soffice.exe"),
)
_MIN_PDF_BYTES = 500


class LibreOfficeError(RuntimeError):
    """soffice missing or conversion failed."""


def _safe_is_file(path: Path) -> bool:
    try:
        return path.is_file()
    except OSError:
        return False


def find_soffice() -> Path | None:
    """Resolve LibreOffice binary: env → PATH → known install paths."""
    for key in ("CASE3_SOFFICE", "LIBREOFFICE_PATH"):
        raw = (os.environ.get(key) or "").strip()
        if raw:
            p = Path(raw).expanduser()
            if _safe_is_file(p):
                return p.resolve()
    for name in ("soffice", "libreoffice"):
        which = shutil.which(name)
        if which:
            return Path(which).resolve()
    for cand in (_MAC_SOFFICE, *_LINUX_SOFFICES, *_WIN_SOFFICES):
        if _safe_is_file(cand):
            return cand.resolve()
    return None


def _pdf_ok(path: Path) -> bool:
    return path.is_file() and path.stat().st_size >= _MIN_PDF_BYTES


def convert_pptx_to_pdf(
    pptx: Path,
    dest: Path,
    *,
    soffice: Path | None = None,
    timeout_s: float = 120.0,
) -> Path:
    """Convert editable PPTX to PDF via LibreOffice Impress (Julius-style)."""
    pptx = Path(pptx)
    dest = Path(dest)
    if not pptx.is_file():
        raise FileNotFoundError(pptx)
    bin_path = soffice or find_soffice()
    if bin_path is None:
        raise LibreOfficeError("LibreOffice (soffice) not found")

    dest.parent.mkdir(parents=True, exist_ok=True)
    work = Path(
        tempfile.mkdtemp(prefix="case3_lo_", dir=str(dest.parent))
    )
    profile = work / "profile"
    profile.mkdir(parents=True, exist_ok=True)
    # file:// URL for UserInstallation (macOS/Linux).
    profile_uri = profile.resolve().as_uri()
    out_dir = work / "out"
    out_dir.mkdir()
    src = work / pptx.name
    shutil.copy2(pptx, src)

    cmd = [
        str(bin_path),
        "--headless",
        "--nologo",
        "--nofirststartwizard",
        "--norestore",
        f"-env:UserInstallation={profile_uri}",
        "--convert-to",
        "pdf:impress_pdf_Export",
        "--outdir",
        str(out_dir),
        str(src),
    ]
    try:
        proc = run_captured(
            cmd,
            timeout=timeout_s,
            check=False,
        )
        produced = out_dir / f"{src.stem}.pdf"
        first_ok = proc.returncode == 0 and _pdf_ok(produced)
        if not first_ok:
            # Drop stale/partial PDF before plain-filter retry.
            if produced.is_file():
                produced.unlink(missing_ok=True)
            cmd_plain = [
                str(bin_path),
                "--headless",
                "--nologo",
                "--nofirststartwizard",
                "--norestore",
                f"-env:UserInstallation={profile_uri}",
                "--convert-to",
                "pdf",
                "--outdir",
                str(out_dir),
                str(src),
            ]
            proc2 = run_captured(
                cmd_plain,
                timeout=timeout_s,
                check=False,
            )
            if not (proc2.returncode == 0 and _pdf_ok(produced)):
                err = (proc2.stderr or proc.stderr or proc.stdout or "").strip()
                raise LibreOfficeError(
                    f"soffice convert failed ({proc2.returncode}): {err[:400]}"
                )
        # Atomic-ish: write tmp then replace
        tmp = dest.with_name(f".{dest.name}.{uuid.uuid4().hex[:8]}.tmp")
        shutil.copy2(produced, tmp)
        tmp.replace(dest)
        return dest
    finally:
        shutil.rmtree(work, ignore_errors=True)


def write_deck_pdf(
    pptx: Path,
    png_paths: list[Path],
    dest: Path,
    *,
    prefer_lo: bool = True,
) -> tuple[Path, str]:
    """Write ``deck_pdf``: LibreOffice from PPTX when possible, else PNG stitch.

    Returns ``(path, mode)`` where mode is ``\"lo\"`` or ``\"png_stitch\"``.
    """
    dest = Path(dest)
    if prefer_lo and find_soffice() is not None:
        try:
            convert_pptx_to_pdf(pptx, dest)
            log.info("deck_pdf via LibreOffice: %s", dest.name)
            return dest, "lo"
        except (LibreOfficeError, OSError, subprocess.TimeoutExpired, FileNotFoundError) as exc:
            log.warning("LibreOffice deck_pdf failed (%s); PNG stitch fallback", exc)
    # Lazy: desk_health imports find_soffice without requiring python-pptx.
    from case3.slides_export import build_deck_pdf

    build_deck_pdf(png_paths, dest)
    log.info("deck_pdf via PNG stitch: %s", dest.name)
    return dest, "png_stitch"
