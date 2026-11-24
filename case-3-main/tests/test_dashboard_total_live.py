"""Real PDF: a total phrase stays out of the shares, and a cut is written in the file."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

import importlib.util

from case3.dashboard_source import parse_dashboard
from case3.source_ingest import file_to_markdown


def _write_grid_pdf(path: Path, rows: list[list[str]]) -> None:
    spec = importlib.util.spec_from_file_location(
        "dash_pdf_fixture",
        Path(__file__).with_name("test_dashboard_source.py"),
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module._write_grid_pdf(path, rows)

_HTML = """<!DOCTYPE html>
<html><head><meta charset="utf-8"></head><body>
<table border="1" cellspacing="0" cellpadding="4">
<tr><td>Область</td><td>Сумма</td></tr>
<tr><td>Минская</td><td>60</td></tr>
<tr><td>Гомельская</td><td>40</td></tr>
<tr><td>Итого по области</td><td>100</td></tr>
<tr><td>Всего по стране</td><td>100</td></tr>
</table>
</body></html>
"""


def _soffice_pdf(html: str, dest: Path) -> None:
    soffice = shutil.which("soffice")
    if not soffice:
        pytest.skip("soffice is not installed")
    work = dest.parent / "html"
    work.mkdir()
    src = work / "regions.html"
    src.write_text(html, encoding="utf-8")
    profile = (dest.parent / "lo-profile").resolve()
    subprocess.run(
        [
            soffice,
            f"-env:UserInstallation=file://{profile}",
            "--headless",
            "--norestore",
            "--convert-to",
            "pdf",
            "--outdir",
            str(dest.parent),
            str(src),
        ],
        check=True,
        timeout=60,
        capture_output=True,
    )
    made = dest.parent / "regions.pdf"
    if made != dest:
        made.replace(dest)


def test_a_real_region_pdf_does_not_share_the_total_phrase(tmp_path: Path) -> None:
    pdf = tmp_path / "regions.pdf"
    _soffice_pdf(_HTML, pdf)
    parsed = parse_dashboard(pdf=pdf)
    text = parsed.markdown
    assert "Итого по области | 100" in text
    derived = text.split("## Производные", 1)[1]
    assert "Итого" not in derived
    assert "Всего" not in derived
    assert "60%" in derived
    assert "40%" in derived
    assert "30%" not in derived
    ingested = file_to_markdown(pdf)
    assert "60%" in ingested.markdown
    assert "Итого" not in ingested.markdown.split("## Производные", 1)[1]


def test_a_real_wide_pdf_writes_the_cut_into_the_document(tmp_path: Path) -> None:
    pdf = tmp_path / "wide.pdf"
    header = [f"c{i}" for i in range(65)]
    row = [str(i) for i in range(65)]
    _write_grid_pdf(pdf, [header, row])
    parsed = parse_dashboard(pdf=pdf)
    assert "Таблица обрезана: было 65×2, осталось 64×2." in parsed.markdown
    assert parsed.warnings == ["Таблица обрезана: было 65×2, осталось 64×2."]
    assert "| c64 |" not in parsed.markdown
    ingested = file_to_markdown(pdf)
    assert "Таблица обрезана: было 65×2, осталось 64×2." in ingested.markdown
    assert "Таблица обрезана: было 65×2, осталось 64×2." in ingested.warnings
