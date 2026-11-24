# ADR-0017: A plaque wins over a bare analyze line

## Status
Accepted

## Date
2026-11-22

## Context
«проанализируй регионы» with the report plaque stayed in chat. The chat prompt forbids new arithmetic, so the demo produced no PDF. The same verbs plus a noun («проанализируй отчёт») are a reading request and must stay chat. A question and a negated plaque («без схемы, расскажи») must stay chat too.

## Decision
`resolve_turn`: if the line is analyze, names no live artifact, and the plaque was not negated, return the plaque. A named make-action still wins. No plaque still means chat.

## Alternatives Considered

### Plaque always wins, even over «проанализируй отчёт»
- Pros: one rule.
- Cons: a request to read the open report would rebuild it.
- Rejected because the existing tests treat that sentence as chat.

### Leave the router and teach the demo phrase «сделай отчёт»
- Pros: no code change.
- Cons: the pressed plaque looks like it does nothing.
- Rejected because the handoff script uses «проанализируй».

## Consequences
- Positive: report, diagram, and presentation plaques build a file from «проанализируй», «сравни», «посчитай» when the sentence names no artifact.
- Negative / follow-ups: «какая доля?» is still chat. The chat answer still does not invent percentages.
