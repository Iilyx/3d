# Glossary

| Term | Meaning |
|------|---------|
| **Liber / Atelier** | Chat UI brand (olive/cream desk) |
| **Source** | User text/file with numbers — only factual base |
| **Intent** | UI+chat requirements (types, palette, caps) |
| **Qwen / Vision** | LLM behind `VISION_API_BASE_URL`. Attached photos are sent as images on that call |
| **Chart slot** | `%CASE3_CHART:cht_01%` → includegraphics after PNG |
| **Figure slot** | `%CASE3_FIG:fig_01%` / `usr_XX` uploads (deck: up to 5) |
| **Deck** | Presentation IR → PPTX + twin. Wish 6–24 slides. See `docs/knowledge/deck.md` |
| **Schema photo** | Upload captioned «схема» → redrawn `dia_*` on a slide, not the original PNG |
| **Diagram slot** | `%CASE3_DIAG:dia_01%` → PNG in PDF/DOCX (ADR-0009) |
| **insufficient_data** | Early finish: chat refusal, no PDF/deck. Heuristic in `input_validation.py`, or the same JSON from the model |
| **Coerce** | Force chart type HTML to match preferred type |
| **Polish** | Palette remap + geometry harden after coerce |
| **Harden (TeX)** | Repair preamble/tables before latexmk |
| **Dry-run** | Skip LLM media / or skip heavy path per flags |
| **Gold** | Few-shot TeX examples in `prompt/gold/` |
| **Image API** | Office `/generate` + `/edit` for photos |
| **case-3:tex** | Docker image with XeLaTeX + pandoc |
