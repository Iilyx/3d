# ADR-0004: Office Image API for photos

## Status
Accepted

## Date
2026-10-21

## Context
Раньше фото завязывались на Kandinsky. На рабочем контуре доступен кастомный Image API (`/generate`, `/edit`). Нужна единая абстракция и режим «только правка фото» в чате без полного отчёта.

## Decision
`IMAGE_API_BASE_URL` (+ совместимость со старым `KANDINSKY_*` alias в health). `image_api.py` — generate/edit, SSRF guards на URL download. Uploads → `usr_XX` slots. Chat-only: `photo_mode=edit` / `POST /api/photo/edit`. Worker `workers/case3-image` — опциональный Cloudflare/local bridge.

## Alternatives Considered

### Keep Kandinsky-only
- Pros: меньше кода
- Cons: не совпадает с офисом
- Rejected as sole backend

### Always call worker
- Pros: единый edge
- Cons: лишняя infra на desk
- Optional only

## Consequences
- Health отдаёт `image_api_configured` + alias `kandinsky_configured` для старого UI.
- Edit fallback generate может игнорировать reference — следить в worker.
- Specs: `docs/superpowers/specs/2026-10-20-image-api-design.md`, user-photos.
