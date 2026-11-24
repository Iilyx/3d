# ADR-0012: Generated photos are opt-in

## Status
Accepted

## Date
2026-11-13

## Context
With `IMAGE_MAX_IMAGES≥1`, prompts were DEFAULT-ON for Image API `fig_*` whenever Source mentioned a place/object/scene. Data-heavy reports got stock photos nobody asked for. User uploads (`usr_*`) must keep working.

## Decision
Hybrid gate:

1. Lexicon `wants_generated_images(intent, source)` (broad explicit cues; «без фото» wins).
2. Hard clamp: without opt-in, LLM `fig_*` budget = 0; uploads still merge.
3. Prompts / Intent compose: DEFAULT-OFF; when budget > 0, treat as requested and fill up to ceiling.

Charts and Mermaid stay default-on.

## Alternatives Considered

### Prompt-only DEFAULT-OFF
- Pros: small diff
- Cons: model still invents photos
- Rejected because: not reliable enough

### Mini-LLM classifier
- Pros: nuanced
- Cons: latency/cost; false negatives drop wanted photos
- Rejected for v1

## Consequences
- Positive: numeric reports stay clean; explicit asks still generate quality photos.
- Negative / follow-ups: rare synonym misses → extend lexicon in `image_opt_in.py`.
- Spec: `docs/superpowers/specs/2026-11-13-liber-image-opt-in-design.md`
