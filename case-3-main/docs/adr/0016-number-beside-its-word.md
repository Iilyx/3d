# ADR-0016: A historical user number stays beside its word

## Status
Accepted. Amends [ADR-0015](0015-user-stated-numbers.md) for new files. Chat answers stay as 0015.

## Date
2026-11-21

## Context
ADR-0015 puts every number the user wrote on one allow-list. «слайд 2» then lets a new report print 2 next to выручка. A spoken cardinal («двенадцать») never entered the list, so the same fact written in words was dropped, and a model could also hide an invented 12 as a word.

## Decision
- Source and the current message still allow a number anywhere, digits or spoken cardinals. «один / одна / одно» are not cardinals.
- `format_user_numbers` stores pairs: `2 слайд`, `77 выручк`. Cap stays 40 distinct values. The stem is the word next to the number, at least 4 letters after the usual ending strip.
- A new TeX file, chart caption, highlight, or slide may use that pair only when the same stem is in the clause. A KPI is judged as label plus value. Chart `data` arrays take Source and the current message only. A word binding does not license `data: [2]`.
- A chat answer may still repeat any value from that line. The gate question is unchanged.
- `draft_section` still does not read the line.

## Alternatives Considered

### Keep the flat allow-list
- Pros: one set, no stemmer.
- Cons: an index the user typed becomes a fact in a new file.
- Rejected.

### Bind chat answers the same way
- Pros: the model cannot quote «2» except beside «слайд».
- Cons: «сколько я называл» would fail when the answer has no stem.
- Rejected. 0015 stays for talk.

## Consequences
- Positive: «слайд 2» no longer prints as выручка. «двенадцать» in Source allows 12.
- Negative: a bare historical «77» with no nearby word is not printable until the user writes it again beside the fact.
