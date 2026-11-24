"""D11 lite: fixture TeX → PDF via Docker case-3:tex (skip if image missing)."""

from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path

import pytest

from case3.render import IMAGE, prepare_tex_source, render_tex

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "pdf_quality" / "minimal.tex"


def _tex_image_present() -> bool:
    if shutil.which("docker") is None:
        return False
    try:
        r = subprocess.run(
            ["docker", "images", "-q", IMAGE],
            capture_output=True,
            text=True,
            timeout=20,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    return r.returncode == 0 and bool((r.stdout or "").strip())


@pytest.mark.skipif(not _tex_image_present(), reason=f"Docker image {IMAGE!r} missing")
def test_pdf_quality_smoke_renders_valid_pdf() -> None:
    assert FIXTURE.is_file(), FIXTURE
    with tempfile.TemporaryDirectory(prefix="case3-pdfq-") as tmp:
        work = Path(tmp)
        tex_path = work / "minimal.tex"
        shutil.copy2(FIXTURE, tex_path)
        prepare_tex_source(tex_path)
        hardened = tex_path.read_text(encoding="utf-8")
        assert r"\CaseThreeMaketitle" in hardened or r"\rule{\textwidth}{0.35pt}" in hardened
        assert r"\titlespacing*{\section}" in hardened

        out_dir = work / "out"
        arts = render_tex(
            tex_path,
            out_dir=out_dir,
            formats={"pdf"},
            log_dir=work / "logs",
            project_root=Path(__file__).resolve().parents[1],
        )
        pdf = arts["pdf"]
        data = pdf.read_bytes()
        assert data.startswith(b"%PDF"), data[:16]
        assert len(data) > 1500
