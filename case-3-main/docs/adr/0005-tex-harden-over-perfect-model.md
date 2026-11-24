# ADR-0005: Harden TeX after the model (don't trust perfect LaTeX)

## Status
Accepted

## Date
2026-10-21

## Context
Qwen часто ломает preamble (`titlespec`), `tabularx` colspec junk, cell-per-line tables, sparse body, truncated JSON. Полностью «вылечить» prompt недостаточно для прод-надёжности.

## Decision
Слой post-LLM: `parse_output` salvage → `coerce_chart_types` / `polish_charts` → `ensure_document_preamble` (packages, fonts, report style, `fix_tabularx_*`, `repair_tabularx_row_breaks`, wide→tabularx) → inject → latexmk. Ошибки latex — в meta/logs.

## Alternatives Considered

### Only better prompting / gold shots
- Pros: less code
- Cons: live audits still fail (e.g. wide tables before repair)
- Insufficient alone

### Reject document on first TeX error
- Pros: fail-fast
- Cons: плохой UX на desk
- Softened: repair first, then fail with log

## Consequences
- Тесты harden обязательны (`tests/test_repair_*`, `test_harden_*`).
- Prompt + gold всё ещё важны, но не единственная линия обороны.
- Chat preview парсит уже hardened/injected TeX — списки/emphasis ещё дырявые (UX roadmap C1/C2).
