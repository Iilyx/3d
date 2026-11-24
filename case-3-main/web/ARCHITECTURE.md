# Liber web — architecture (one screen)

React desk for case-3. Target layout (strangler): `app/` · `api/` · `domain/` · `features/*` · `shared/` · `styles/`.  
**Week 1 done:** `api/`, `domain/`, `app/` exist; flat files re-export for compatibility. Feature folders = later weeks.

## Desk layout

```text
Sidebar | Chat column              | Artifact rail
        | messages + composer      | Preview · PDF · Схема · Source · Presentation
```

Modes (`domain/liberModes`): **report** | **diagram** | **presentation** → `output_mode` on `POST /api/run`.

## Run flow

1. Composer → `app/App` `send()` → `POST /api/run` (FormData).
2. Poll `GET /api/runs/{id}/status` → thinking phrases (`domain/pipelinePhrases`).
3. While latex/docx: SSE `api/summaryStream` → bot bubble text.
4. Done → in-chat card; rail tabs via `modeSurfaces`.
5. Presentation: `POST …/slides` + poll (rail not auto-opened). Wish 6–24 via `target_slides`. Up to 5 photos. A «схема» photo is redrawn as `dia_*` before the deck LLM. Source longer than 8000 characters is briefed (`slides_source_text`).

Edits: `POST …/charts|figures|tables|diagrams/…/edit`. A diagram on a slide uses the same visual editor, then `POST …/slides/rebuild`. Cancel: `POST …/cancel`. Contract: `docs/knowledge/deck.md`.

## Where code lives (Week 1)

| Concern | Path |
|---------|------|
| Shell / wiring | `src/app/App.tsx` |
| SSE summary | `src/api/summaryStream.ts` |
| Types, modes, history, run formatters | `src/domain/*` |
| UI components (still flat) | `src/*.tsx` until Week 2+ |
| Styles | `src/styles/*` |

Root shims (`liberTypes.ts`, `liberRunHelpers.ts`, …) → prefer importing from `domain/` / `api/` / `app/` in new code.

## Print vs chat

- Report **PDF** = print truth (rail).
- Preview / live Chart.js ≈ TeX blocks (may differ).
- Mermaid diagrams → PNG via `%CASE3_DIAG:dia_NN%` in PDF/DOCX (ADR-0009; supersedes ADR-0007 UI-only). Liber rail shows the same figures + visual editor.
- Deck **PPTX** = presentation truth; Liber twin ≈ tokens.

## Angular later

Map `api/` → services, `domain/` → models/pure TS, each future `features/X` → Angular feature. See `docs/superpowers/specs/2026-10-25-liber-frontend-modules-design.md`.
