# ADR-0013: Chat memory is a chain, not Source

## Status
Accepted. Supersedes the prior-turn bullet of [ADR-0011](0011-prior-turn-and-live-desk-signals.md). Amended 2026-11-21: the verbatim window is 8 turns, not the whole chain.

## Date
2026-11-19

## Context
One clipped previous answer was not enough for a real chat. The model needs the thread, and a question about the open report needs that report. Old answers also contain digits. If those digits sit in the allow-list, the next PDF prints them.

## Decision
- A chat is a `prior_run_id` chain, oldest first, at most 48 hops (`chat_memory.load_chain`).
- An in-place edit does not start a run. It appends `dialogue` on the same `meta.json` (12 notes, 300 characters, paragraphs kept) and `last_edit`.
- The prompt is three blocks: the current message, `ТЕКСТ` (Source), then the thread. The thread is cut from the front. The last 8 turns keep paragraphs. Older turns are one digit-free line. A legal 48-hop paste stays under 150000 characters.
- The block is labeled not Source. Allowed numbers are the Source plus the user's own latest message. Memory, the open-report block, and chart JSON are not an allow-list.
- A chat answer about the open report also receives the outline and the one named section (`report_context`). That text is still not Source.
- A new TeX or deck drops a number that is not in that allow-list (`fact_ground`). Image width and the preamble stay. A real TeX comment stays. An escaped percent does not hide the rest of the line.
- Edits from a message use the same functions as the rail. The router is the ordered regexes in `resolve_act`, not a second model.
- Reopening a chat returns paragraphs (`memory_view` via `_clip_prose`). The bubble already renders markdown.

## Alternatives Considered

### Keep one prior turn
- Pros: small prompt, no old digits.
- Cons: the model cannot continue a real conversation.
- Rejected. The chain is capped, and digits are checked on the way out.

### Embeddings or a second model to route edits
- Pros: looser phrasing.
- Cons: a second failure mode, and the regex order is already the spec.
- Rejected.

## Consequences
- Positive: the latest answer, a recall, and the named section reach the model. A memory digit does not survive into PDF or a slide caption. The verbatim window is eight turns. Older turns stay as one digit-free line each, and a matching older turn is pasted in full when the new message names it.
- Negative / follow-ups: Source in the chat prompt is still capped at 6000 characters: the opening, matching paragraphs, and the end. «Сократи весь отчёт» rewrites every paragraph and rebuilds once. A foreign number drops its clause. A chat can replace a cell and add or delete a table row. A diagram legend is not its own edit. Photo pixel edit stays off the desk. A Source number may be repeated in a new place: the check is the value. `docs/MEMORY.md` is the map agents read first; this ADR is the why.
