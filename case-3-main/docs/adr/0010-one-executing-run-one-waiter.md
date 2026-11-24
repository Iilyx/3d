# ADR-0010: One executing run, one waiter

## Status
Accepted, amended 2026-11-22

## Date
2026-11-10

## Context
Parallel pipeline threads on the Windows desk shared log handlers and `meta.json` and left zombies. The API rejected every second `POST /api/run` with 409. A stuck slot could also be cleared by `POST /api/pipeline/slot/reset` while the pipeline thread was still alive.

## Decision
The desk still executes one pipeline. A second `POST /api/run` is accepted as `202` with `status: queued`. The waiter is `runs/pipeline_queue.json` (one job). A third request is 409 and writes nothing. When the executing run releases the slot, the waiter starts on the same lock. After an API restart, `recover_persisted_pipeline` starts that file if `meta.status` is still `queued` and the run was not cancelled. `POST /api/pipeline/slot/reset` returns 409 while that run's thread (or the `pending` start window) is alive.

SSE replays `meta.steps[]` first (`RunEventBus.merge_durable_steps`). The in-memory bus is only the live tail. A restart does not invent progress that was not written to `meta.json`.

History list reads `runs/history_index.json` and skips unchanged `meta.json`. The response is every pinned run plus the 24 newest unpinned runs. Run folders are not deleted.

Diagram mode builds its Mermaid prompt in `diagram_generate.complete_diagrams` for both the first pass and the empty-draft recovery.

## Alternatives Considered

### Option A — keep 409 for the second run
- Pros: no queued state in the UI
- Cons: the user must retry by hand after every overlap
- Rejected because the desk can hold one request without a second thread

### Option B — unbounded queue
- Pros: no 409
- Cons: uploads pile up and the single-thread invariant gets harder to see
- Rejected because one waiter is enough for a single desk

## Consequences
- Positive: one extra report is kept; reset cannot cut a live thread; history GET does not re-read every meta
- Negative / follow-ups: a run that was `status=running` when the process died is not resumed automatically (no second pipeline thread). On the next start `settle_orphaned_runs` marks it `error`, keeps `failed_stage`, and Liber can offer «Продолжить». A cancelled run becomes `cancelled`. A deck left in `slides_status=running` becomes `error`. Artifact retention is still parked. The queue file is a single JSON object, not a log.
