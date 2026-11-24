"""TSV table extract caps for wide office tables."""

from case3.source_ingest import MAX_TABLE_COLS, MAX_TABLE_ROWS, _cells_to_tsv


def test_tsv_basic() -> None:
    out = _cells_to_tsv([["A", "B"], ["1", "2"]])
    assert out == "A\tB\n1\t2"


def test_tsv_truncates_wide_and_tall() -> None:
    header = [f"c{i}" for i in range(MAX_TABLE_COLS + 5)]
    rows = [header] + [[str(i)] * len(header) for i in range(MAX_TABLE_ROWS + 10)]
    out = _cells_to_tsv(rows)
    lines = out.splitlines()
    assert lines[0].count("\t") == MAX_TABLE_COLS - 1
    assert any(line.startswith("… truncated") for line in lines)
    assert len([l for l in lines if not l.startswith("…")]) == MAX_TABLE_ROWS
