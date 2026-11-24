from pathlib import Path

from case3.input_validation import validate_input_heuristics
from case3.source_attach import merge_ingested_sources


def test_report_phrase_keeps_the_attached_pdf_table(tmp_path: Path):
    ingest_id = "20261124T120000Z_abcdef"
    folder = tmp_path / "runs" / "uploads" / "ingest" / ingest_id
    folder.mkdir(parents=True)
    table = (
        "# Данные дашборда\n\n"
        "## Таблица PDF\n\n"
        "| Регион | Факт |\n| --- | --- |\n| Минск | 120 |\n"
    )
    (folder / "source.txt").write_text(table, encoding="utf-8")

    merged = merge_ingested_sources(
        "сделай отчет по данным",
        [{"fileName": "PivotTableElement13.pdf", "ingestId": ingest_id, "viewMode": "document"}],
        tmp_path,
    )
    valid, msg = validate_input_heuristics(merged, "сделай отчет по данным", output_mode="report")
    assert valid, msg
    assert "120" in merged
    assert "Минск" in merged


def test_merge_leaves_a_body_that_already_has_the_table(tmp_path: Path):
    ingest_id = "20261124T120001Z_abcdef"
    folder = tmp_path / "runs" / "uploads" / "ingest" / ingest_id
    folder.mkdir(parents=True)
    table = "| Регион | Факт |\n| --- | --- |\n| Брест | 8 |\n"
    (folder / "source.txt").write_text(table, encoding="utf-8")
    body = f"===== отчёт.pdf =====\n{table}"
    assert merge_ingested_sources(body, [{"ingestId": ingest_id}], tmp_path) == body
