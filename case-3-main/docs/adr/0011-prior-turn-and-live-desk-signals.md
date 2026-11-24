# ADR-0011: Prior turn, idle SSE, cancel flag, diagram ceiling

## Status
Accepted. The prior-turn bullet is superseded by [ADR-0013](0013-chat-memory-chain.md). SSE, cancel, and the diagram ceiling stay here.

## Date
2026-11-10

## Context
Liber looks like a chat, but each send was a fresh run with no previous turn.
The progress socket also died 1200s after connect even while keepalives flowed,
stage writes could drop `cancel_requested`, and the diagram budget was clamped
to 3 while the desk ceiling is 5.

## Decision
- SSE `timeout_s` is an idle budget. A yielded ping or pipeline event arms it again.
- Pipeline and slides meta snapshots copy `cancel_requested` off disk before replace.
  A pipeline write that would store `status=ok` over a live cancel becomes `cancelled`.
  `LLMClient.complete` polls the cancel check during the HTTP call and shuts the socket.
- Diagram budget uses `clamp_diagram_budget` (`DIAGRAMS_HARD_MAX`, default 5).
- Image URL downloads are the Image API host only. `IMAGE_ALLOW_URL_DOWNLOAD=1` adds public https. Redirects stay off.
- A pipeline crash outside `PipelineError` publishes an SSE `error`. The desk poll settles on `error` / `cancelled` / report `ok` (a presentation waits until the deck is terminal).
- The next `POST /api/run` may send `prior_run_id`. Superseded by ADR-0013:
  the chain is up to 48 turns, not one clipped prompt and summary.
  `chat_prompt` is still carried when the pipeline rebuilds `meta.json`.

## Alternatives Considered

### Full transcript in the prompt
- Pros: the model sees every turn.
- Cons: unbounded tokens, and old numbers start to look like Source.
- Rejected because one clipped turn is enough for «короче» / «добавь».

### Wall-clock SSE cap of 20 minutes
- Pros: a forgotten socket always closes.
- Cons: a healthy long report is reported as `events timeout` while the job continues.
- Rejected. The pipeline already has its own LLM and image timeouts.

## Consequences
- Positive: follow-up in the same chat quotes the previous result. Stop survives the next stage write. Five diagrams match Settings.
- Negative / follow-ups: the one-turn quote is replaced by ADR-0013. A client that disconnects still holds the server generator until the run ends or the idle budget passes with no keepalive.
