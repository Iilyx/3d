# KI: Image API / photos

## What
Generate and edit report photos via office HTTP API; optional user uploads; chat-only edit mode.

## Entry
- Config: `ImageApiConfig.from_env()` — `IMAGE_API_BASE_URL` (alias Kandinsky env)
- Gen: `generate_all_figures` in pipeline images stage
- Edit in report: `figure_edit.edit_figure_in_run`
- Chat-only: `api` `photo_mode=edit` / `POST /api/photo/edit`
- Worker: `workers/case3-image` (optional)

## Invariants
- Upload budget **5** PNG/JPEG, 4 MB each (`user_photos._MAX_COUNT` / `_MAX_BYTES`). API used to slice at 2 — do not bring that back
- SSRF: no private IP redirects on remote image fetch
- User figures `source=upload` skip API generate
- **Generated `fig_*` are opt-in** (ADR-0012): `image_opt_in.wants_generated_images(intent, source)` + hard llm budget clamp. Uploads alone do not unlock Image API `/generate`. When opt-in, fill up to ceiling with rich prompts — do not soft-abandon
- Vision: `user_photos_to_vision_images` (max edge 768) goes into the LLM call so placement can follow the picture. Photos illustrate; they do not satisfy the data gate
- Report: each `usr_*` slot at most once (`deduplicate_slots_in_tex` + `ensure_user_slots_in_tex`). Deck: `ensure_deck_photos` places `usr_*` (`media_hero` / `media_split`)
- Health: `image_api_configured` + **live** `image_api_ok` / `image_api_error` via `probe_image_api` (~1.5s)
- Prompts: `sanitize` → `apply_pack_style_lock` → `harden_brand_safe` (+ `Avoid:`) in `prepare_image_prompt` on generate **and** edit
- User edit prompts may be RU: `ensure_english_image_prompt` (Qwen) before Image API in `figure_edit` + `api_photo.quick_photo_edit`; already-EN passthrough
- Pack id: report → `palette_from_intent` / `meta.image_style_pack`; slides → `slides_theme_pack`

## Gotchas
- Loopback URL rewrite for Docker/Windows host access
- Worker may fall back edit→generate silently; `negative_prompt` ignored by case3-image worker (baked into prompt)
- Empty / down Image API → soft-fail strip `fig_*`; report run not blocked. Soft media-failure toasts were removed 2026-11-10 (`fcd443b`) — do not add them back. Click a composer/chat photo chip to preview it

## See
ADR-0004 · ADR-0012 · `docs/superpowers/specs/2026-10-20-image-api-design.md` · `2026-11-13-liber-image-opt-in-design.md` · `user-photos` spec  
Brand-safe + pack lock + health chip: `docs/knowledge/image-brand-safe-and-pack-lock.md`
