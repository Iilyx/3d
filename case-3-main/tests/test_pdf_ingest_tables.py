"""PDF born-digital: tables → markdown, numbers preserved."""

from __future__ import annotations

from pathlib import Path

import pytest

from case3.source_ingest import file_to_markdown

_PZ4_PDF = Path(
    "/Volumes/Samsung970/old_projects/bam-bam-bam/examples/input/"
    "пз4_таблицы_график_export.pdf"
)
_PZ4_DOCX = Path(
    "/Volumes/Samsung970/old_projects/bam-bam-bam/examples/input/"
    "пз4_таблицы_график.docx"
)


@pytest.mark.skipif(not _PZ4_PDF.is_file(), reason="bam fixture PDF not mounted")
def test_pz4_pdf_has_tsv_tables_and_key_numbers() -> None:
    result = file_to_markdown(_PZ4_PDF)
    md = result.markdown
    for needle in (
        "4,093938",
        "4,046577",
        "4,000034",
        "3,846154",
        "3,666667",
        "22,61428571",
        "21,75",
    ):
        assert needle in md, f"missing {needle}"


@pytest.mark.skipif(
    not (_PZ4_PDF.is_file() and _PZ4_DOCX.is_file()),
    reason="bam fixtures not mounted",
)
def test_pz4_pdf_keeps_all_docx_number_literals() -> None:
    import re

    docx_md = file_to_markdown(_PZ4_DOCX).markdown
    pdf_md = file_to_markdown(_PZ4_PDF).markdown
    keys = re.findall(r"\d+,\d+|\d+\.\d+", docx_md)
    assert keys
    missing = [
        k
        for k in keys
        if k not in pdf_md
        and k.replace(",", ".") not in pdf_md
        and k.replace(".", ",") not in pdf_md
    ]
    assert missing == [], f"lost numbers vs docx: {missing[:20]}"


def test_plausible_table_rejects_chart_junk() -> None:
    from case3.source_ingest import _is_plausible_table

    good = [
        ["Периоды", "Товар 1", "k=2"],
        ["1", "25", ""],
        ["2", "31", "#Н/Д"],
    ]
    junk = [
        ["", None, "", "", "", "", "3", "6\n35", ""],
        ["", None, "", "", "", "3\n29", "1\n29", "3", "2\n31"],
        ["2", "4", "25", "27\n2", "2\n24\n3", "7", "", "", ""],
    ]
    assert _is_plausible_table(good) is True
    assert _is_plausible_table(junk) is False
