# ADR-0006: Liber soft-premium shell (Mary anatomy + Julius behavior)

## Status
Accepted

## Date
2026-10-21

## Context
Chat-first Liber (ADR-0003) + Artifact rail worked functionally but looked dense (foil/noise, emoji attach, no sidebar). Mary (maryrose.by) shows soft-premium patterns; Julius-style RHS verify remains the right artifact model.

## Decision
Adopt **Mary shell anatomy** on Liber brand:

- Soft-premium shell anatomy (sidebar / chat / rail); chrome palette evolved to **Quiet Mono** (see `docs/superpowers/specs/2026-10-23-liber-quiet-mono-ui-design.md`) — was sage/olive, now ink/paper editorial
- Pill composer + stroke icons; empty hero with ≤3 prompts
- Thinking bar above composer; AI messages without bubble
- Chart PNGs stay print-truth via Playwright; premium layouts in `chart_frame` + optional `insight`/`highlights` on ChartCard
- PDF remains print truth; rail shows explicit Preview ≠ PDF hint
- Export stays one-click (`ExportMenu`), never a second agent turn

## Alternatives Considered

### Full Mary salon IA
- Pros: familiar SaaS nav
- Cons: wrong product (automations/employees); rejected

### Live Chart.js in chat for v1
- Pros: hover legend↔segment
- Cons: Preview≠PDF drift; deferred (roadmap G12)

## Consequences
- UI surface language shifts from “print desk luxury” toward soft premium; Crimson+DM Sans retained
- History is sessionStorage-only until a runs API exists
- Chart recipes/prompt must keep Source-only numbers for insight/highlights
