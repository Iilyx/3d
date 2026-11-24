# Image: brand-safe + pack style-lock (design note)

**Status:** implemented 2026-10-25 (health chip · pack lock · brand-safe).  
**Related:** KI-image-api · `image_prompt.py` · `image_api.py` · deck packs in `deck_themes/*.json` · Liber health already partial in `GET /api/health`.

---

## 1. Image worker health chip (UI)

**Problem:** Image API down → `fig_*` silently stripped; user sees report without photos.

**Do:**
- Extend or reuse `GET /api/health`: not only `image_api_configured` (env set), but **live probe** — short GET/HEAD or tiny ping to `IMAGE_API_BASE_URL` (timeout ~1–2s). Fields e.g. `image_api_ok`, `image_api_error`.
- Liber chrome: small chip near Settings / composer — `Image · ok` / `Image · down` (Quiet Mono, no purple).
- Optional: if down and run wants figures → warn before/after run («фото пропущены»), not only log.

**Don’t:** block entire report run when Image is down (soft-fail stays); just make it visible.

---

## 2. Style-lock photos to pack

**Problem:** generated photos ignore botanical/board/atelier DNA → clash with deck/report chrome.

**Do (deterministic append, not hope the LLM remembers):**
- Map each **deck pack** (and report palette if no pack) → short English **style suffix** injected after sanitize:
  - `botanical` → warm paper, fern/olive greens, soft natural light, matte, no neon
  - `board` → cool gray-blue, crisp corporate daylight, clean desks, muted steel
  - `atelier` → warm cream paper, olive ink accents, editorial still-life
  - `signal` / `voltage` / `ink` / `studio` / `relay` → 1–2 lines each from pack colors (primary/accent hex named in words + mood)
- Apply in one place: after `sanitize_image_prompt`, before `generate_png` / edit — e.g. `apply_pack_style_lock(prompt, pack_id|palette_id)`.
- Source of pack id: slides run → `meta.slides_theme_pack`; report-only → chart/report palette or default `atelier`.
- Keep suffix short (≤120 chars) so max_len 800 still fits subject.

**Don’t:** replace the subject prompt; only lock look. Don’t invent purple.

---

## 3. Stock-ban / brand-safe filter (do this properly)

### Principles

1. **Layered, not one magic string** — LLM system rules + server-side prompt harden + optional negative prompt if API supports it.
2. **Ban classes, not random words** — stock clichés and anti-Liber look.
3. **Positive craft > only negatives** — “editorial still life, natural materials…” works better than a novel of “no X”.
4. **Same path for generate and edit** — `generate_png` and `edit_png` / figure_edit.
5. **Testable** — unit tests: prompt in → must contain lock bits; must not contain banned phrases after harden (or harden strips/rewrites).

### Ban / avoid list (EN, append as negative block or strip-if-present)

Hard avoid (stock / AI-slop):
- handshake, thumbs up, generic smiling diverse team in glass office
- neon cyberpunk, purple/violet/magenta glow, hologram UI, lens flare spam
- watermark, stock photo look, Shutterstock aesthetic
- plastic 3D render people, uncanny faces (prefer no readable faces / crop hands-objects when possible)
- confetti explosion, trophy slam, rocket emoji energy

Liber-positive (always reinforce lightly):
- print editorial, matte paper, natural light, restrained color, documentary object photography
- anti-purple: no violet/purple gradients

### Implementation shape (recommended)

```text
subject (from model, sanitized)
  + pack style-lock suffix
  + brand-safe positive line
  + optional API negative_prompt = stock-ban list
```

1. **`prompt/system_tex.md`** (and slides photo rules if any): short “photo prompts MUST …” + “MUST NOT …”.
2. **`image_prompt.py`**:
   - `sanitize_image_prompt` (existing)
   - `harden_brand_safe(prompt) -> str` — append positive Liber line; optionally strip known bad n-grams
   - `pack_style_suffix(pack_id) -> str`
   - `brand_safe_negative() -> str` for API knobs if worker accepts `negative_prompt`
3. **`image_api._knobs` / POST body**: pass negative if worker supports; if not, bake compact “Avoid: …” into prompt once.
4. **Worker** (`workers/case3-image`): document whether negative is supported; if yes, wire through.

### QA

- 5–10 fixture prompts (handshake, purple glow, botanical still life, board meeting cool) → harden → visual spot-check on desk.
- Health chip visible when worker stopped.

---

## 4. Future (not this batch)

- CSV/XLSX → structured Source (owner: «можно подумать» — see backlog F).
- Photo library per thread, remove/replace without regen — parked unless unparked.
