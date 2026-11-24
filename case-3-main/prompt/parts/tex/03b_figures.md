## Image API `figures` (photos / illustrations) — **opt-in only**

`{{MAX_IMAGES}}` is a **ceiling** for generated `fig_*` (Image API). **Default OFF.**
Do **not** invent stock photos just because Source mentions a place, office, product, or scene.

### When to emit generated `fig_*` ({{MAX_IMAGES}} ≥ 1)

Emit only if Intent **or** Source **explicitly** asks for a picture / illustration / appearance visual, e.g.:

- фото / фотка / иллюстрация / рисунок / картинка / изображение;
- «внешний вид…», «покажи здание/офис/продукт…»;
- photo / photograph / illustration / picture of / image of / visual of / show the appearance.

If the budget is ≥ 1, that already means the desk detected opt-in — **prefer filling up to {{MAX_IMAGES}} strong photos** with rich English prompts (do not soft-skip to empty).

Skip generated photos (`"figures": []` for `fig_*`) when budget is 0, Intent says «без фото», or there is no explicit picture ask (user uploads `usr_*` are separate — always place those when attached).

- If Intent says «сгенерируй фото…» → emit up to {{MAX_IMAGES}} with rich English prompts matching that request.
- `caption`: Russian, what the reader sees.
- `prompt`: **English only**, photographic subject + setting + lighting + lens feel; no Cyrillic; no tiny text overlays; no charts/tables of numbers; no logos unless Source requires.
- Photo prompts **MUST**: print-editorial / matte / natural light / documentary object or place; one clear subject; suitable for A4 print.
- Photo prompts **MUST NOT**: handshake, stock smiling team in glass office, purple/violet/magenta neon glow, hologram UI, watermark / Shutterstock look, plastic 3D people, confetti/trophy slam energy.
- Prefer photorealistic clarity; avoid readable faces of real people when possible. Server also hardens brand-safe + pack style-lock.
- Never use figures for KPI/number comparisons — those are `charts`.
- Place each `%CASE3_FIG:id%` slot near the prose it illustrates. **Never** gather photos into a final `\section{Иллюстрации}` (or similar) — one slot beside the matching paragraph.
- If {{MAX_IMAGES}} is 0 → `"figures": []`, no `%CASE3_FIG:%` slots.
