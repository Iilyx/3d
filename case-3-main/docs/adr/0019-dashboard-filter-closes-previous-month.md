# ADR-0019: A February filter is the January receipts

## Status
Accepted

## Date
2026-11-23

## Context
The receipts dashboard closes the previous month. Filter «на 1 февраля 2025» shows the title «Поступления за январь 2025 года (с нарастающим итогом)» and the January figures. That is the data for the February filter. The chat model read the title, decided February was missing, and refused to answer.

## Decision
`note_closed_month` writes one sentence when the title month is the previous month of the filter (or of the question, if the screen text has no filter). The same year, or December against 1 January of the next year. `chat_answer` tells the model to discuss those figures and not to refuse. A later month or a different year is still a mismatch. The screen prompt keeps the filter date and the title month as printed.

## Alternatives Considered

### Tell the model only in the prompt
- Pros: no parser.
- Cons: Qwen already refused a title that said January. A sentence inside the document is what it treats as source.
- Rejected because the prompt stays as the second line, not the only one.

### Rewrite the title to February
- Pros: the months would match the question.
- Cons: the screen really says January, and February figures are not on it.
- Rejected because the numbers would be relabeled.

## Consequences
- Positive: a February question over a January receipts screen is answered from the figures on screen.
- Negative / follow-ups: the note is for this receipts dashboard. Another dashboard that shows two months side by side does not get it.
