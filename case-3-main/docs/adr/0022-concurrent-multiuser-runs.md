# ADR-0022: Multi-user concurrent execution & per-browser workspace isolation

## Status
Accepted, 2026-11-23 (supersedes ADR-0010 single-slot ceiling)

## Context
Liber previously serialized all report/diagram/presentation builds through a single `_PIPELINE_SLOT` lock with one on-disk waiter (`ADR-0010`), ran heavy operations inside `async def` routes directly on the asyncio event loop, mutated module-level `_PPTX_FONT` globals during PPTX generation, shared one global `user_history.json`, and broke Stimulsoft `/filters` + `/open` on `.mrt` files without filters or when two browsers opened different dashboards.

## Decision
1. **Concurrent multi-worker execution (`CASE3_MAX_CONCURRENT_RUNS`, default `3`, clamped `1..8`)** and **FIFO on-disk queue (`CASE3_MAX_QUEUED_RUNS`, default `8`, clamped `1..32`)** backed by `runs/pipeline_queue.json` (`append_waiter` / `load_waiters` while preserving single-dict compatibility and `CASE3_MAX_CONCURRENT_RUNS=1` test support).
2. **Non-blocking asyncio routes**: heavy work inside `async def` handlers (`api_dashboard_phrase`, `api_dashboard_parse`, `api_source_ingest`, and `continue_or_limit` in `api_run`) runs via `await asyncio.to_thread(...)`.
3. **Thread-safe IDs, Playwright & PPTX**: `pipeline.prepare_run_dirs` allocates unique IDs atomically under `_RUN_DIR_LOCK`; `slides_pptx_draw` scopes active theme font & brand mark via `ContextVar` (`use_pptx_theme`); `charts._run_sync_playwright` caps parallel Chromium spawns via `CASE3_MAX_PLAYWRIGHT` (default `4`).
4. **Zero-login browser isolation (`X-Workspace-Id`)**: frontend attaches a `localStorage` `ws_*` id to `/api/*` calls; `api_history` scopes `user_history.json` (`runs/workspaces/<wid>/user_history.json`) and `/api/history` filtering when present, keeping `"default"` fallback for CLI/tests.
5. **Stimulsoft concurrency & 0-filter support**: `dashboard_remote` accepts `filters: []` and bounded `_phrase_has` numbers; `stimulsoft-preview/view_dashboard.py` handles empty JSON filters on `POST /open?open=0`, returns scoped `/open?mrt=...&rf=...` paths, and scopes `/shot` per `mrt` when provided.
