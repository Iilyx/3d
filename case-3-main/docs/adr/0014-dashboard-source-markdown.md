# ADR-0014: Dashboard numbers come from PDF cells, the screen from Qwen

## Status
Accepted

## Date
2026-11-20

## Context
The next product job is to analyse a Stimulsoft dashboard. The screen is a PNG (cards, map or chart, filters). The numbers live in a born-digital PDF pivot with many columns. Later the Stimulsoft service will POST those two files. Chat memory and the Liber buttons stay for a later pass.

`source_ingest` already turns a report PDF into TSV, but it cuts a table at 12 columns and 80 rows, drops a repeated neighbour cell, and refuses a PNG. A dashboard pivot is wider than that, and two equal facts side by side are still two facts.

## Decision
`dashboard_source.parse_dashboard(png=..., pdf=...)` returns one markdown document and the two parts separately.

- PDF: pdfplumber reads cells. Digits, spaces, commas and percents stay as printed. A pivot without vertical rules is rebuilt from word positions, so a spaced number stays one cell and a wrapped header joins. A repeated header on the next page appends rows. Cap is 64 columns and 500 rows, with a warning if a table is cut. A scan with no text layer is refused. No new env var.
- PNG: the existing Qwen client (`VISION_*`) and prompt `dashboard_png`. Temperature 0.1, reasoning off, answer cap 4096. The model reads the selected filters, the cards and the chart. It does not read the green payment table; a copied grid wider than four columns is dropped. Unreadable digits must be written «не разобрать».
- No HTTP route and no change to Liber Source ingest.

Callers treat `pdf_markdown` as the cell text and `png_markdown` as what the model read off the screen. The combined markdown says which is which.

## Alternatives Considered

### Reuse `source_ingest.file_to_markdown`
- Pros: one ingest path
- Cons: 12-column cut, dropped duplicate cells, PNG rejected
- Rejected because: the pivot would lose columns and equal neighbour numbers

### Send the PDF to Qwen as well
- Pros: one model call
- Cons: vision misreads dense digits
- Rejected because: the PDF already has a text layer

## Consequences
- Positive: a later API is one function call. Report ingest limits stay as they are.
- Negative / follow-ups: buttons, Stimulsoft POST, and feeding this markdown into chat as Source are not built. Screen digits are still in the document; the label tells the reader they were seen, not copied from cells.
