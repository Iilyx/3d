# Desk health + live pipeline progress (UX note)

**Status:** owner wants both (2026-10-25). Implement after/alongside image health chip; do not treat as “poll tweak only”.  
**Related:** `GET /api/health` · ThinkingBar / action-log spec `2026-10-21-pipeline-action-log-design` (poll-only; SSE was out of scope then) · Quiet Mono chrome.

---

## 1. Desk health dashboard — **rejected** (owner 2026-10-26: не надо вообще)

~~Former **do**:~~

**One screen / panel** (Settings sheet or dedicated «Desk» strip):

| Probe | Meaning |
|-------|---------|
| Qwen / Vision | `VISION_API_BASE_URL` + optional lightweight ping |
| Image API | configured + **live** ok (same as G health chip) |
| Docker TeX | `docker_ok` / image present |
| LibreOffice | `CASE3_SOFFICE` / soffice found (deck PDF `lo` vs stitch) |
| Playwright | chromium launch probe (already in health) |

**UX:** green/amber/red dots + one-line fix hint («запусти workers/case3-image», «docker pull case-3:tex»). Not a second product — a **trust strip** so silent skips stop being mysteries.

Wire from existing `/api/health`; extend probes where missing (soffice, live image). UI: Liber Quiet Mono, no purple glow dashboard kitsch.

---

## 2. SSE / WebSocket stages — **do**, make it feel premium

### Why leave poll

Poll feels laggy and “stuck”; stage changes arrive late; ThinkingBar already wants Cursor-like steps but was capped to poll.

### Transport

Prefer **SSE** first (simpler than WS on FastAPI desk, one-way server→client):  
`GET /api/runs/{id}/events` → `text/event-stream` with events:

- `stage` — `{ stage, detail, t }`
- `step` — optional fine beats inside a stage  
- `artifact` — `{ kind: pdf|docx|chart|figure|slides, ready: true }` when a file appears  
- `done` / `error` / `cancelled`

Keep status poll as **fallback** if SSE drops (Windows proxies).

### How to show it cooler (product, not spinner)

Goal: user feels a **workshop building the artifact**, not a waiting room.

1. **Named craft steps** (RU, short), not raw stage ids:  
   «Читаю Source» → «Верстаю текст» → «Рисую графики» → «Собираю фото» → «Печатаю PDF» → «DOCX» / «Слайды».
2. **Checklist with checkmarks** (ThinkingBar expand): completed ✓, current with subtle pulse, upcoming muted. Elapsed on current only.
3. **Artifact pulses**: when PNG/PDF/PPTX lands, a small chip flashes in chat («PDF готов») *before* full run ends — honest multi-format progress.
4. **One focal line** in collapsed bar: current craft + mm:ss; expand for full list.
5. **No fake token stream** of model thoughts (action-log rule stays). Optional later: last `stage_detail` as subline («cht_02 ocean»).
6. **Motion:** Quiet Mono — 1 opacity/soft slide per step, not confetti. Respect `prefers-reduced-motion`.
7. **Slides job** uses the same event language (`slides_stage`), not a second metaphor.

### Out of scope here

- Resume failed stage (parked unless owner unparks).  
- Full desk installer/doctor (separate).  
- Replacing PipelineFlow bot bubble entirely — can stay as secondary.

### Done when (v1)

- SSE (or WS) drives ThinkingBar; poll only fallback.  
- Health dashboard shows all five probes.  
- User can tell *which* craft step is active within ~1s of server bump.

---

## 3. SSE phase 2 — cooler & smarter

**Phase 2A shipped 2026-10-26** (spec `2026-10-26-liber-sse-phase2a-design`): ETA · cht_/fig_ substeps · photo skip · cancel freeze · error hint.  
**Phase 2B shipped 2026-10-26** (spec `2026-10-26-liber-sse-phase2b-design`): film strip + click→rail · success recap · plaques removed.  
**SSE finish shipped 2026-10-26** (spec `2026-10-26-liber-sse-finish-design`): mode scripts · durable `meta.steps[]` · **no sound**.

### Smarter (signal, not noise)

- **ETA / pace:** ✅ rolling averages → `eta_s` on stage; UI «ещё ~Ns» when confident.
- **Per-artifact substeps:** ✅ SSE `step` + nested lines under charts/photos.
- **Skip awareness:** ✅ photos skipped + reason when Image API empty.
- **Cancel that feels instant:** ✅ `craftFrozen` + «Остановлено».
- **Recovery hints:** ✅ terminal `hint` → ThinkingFold line.
- **Server `meta.steps[]`:** ✅ durable step log + SSE late-join seed + status hydrate.

### Cooler (atelier craft, Quiet Mono)

- **Mini film of birth:** ✅ thumb strip; click opens media in rail.
- **Mode-aware script:** ✅ distinct templates + `effectiveCraftMode` on `slides_*`.
- **Sound:** ❌ rejected 2026-10-26 (owner: не надо).
- **Present/slides parity:** ✅ slides stages use presentation checklist.
- **Post-run recap:** ✅ success-only one-liner under fold.

### Explicit non-goals for phase 2

- Fake streaming of model chain-of-thought.  
- Gamification / streak / purple neon progress rings.  
- Replacing PDF as print truth with the progress UI.

**Unpark:** owner says «давай SSE phase 2» → brainstorm → spec under `docs/superpowers/specs/`, then plan. Until then: v1 only.

---

## 4. Related parked

- **Atelier critique** — second LLM pass, layout/clarity only, no new facts → backlog **J**.
