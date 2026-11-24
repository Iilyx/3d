# ADR-0009: Inclusion of Diagrams in PDF and DOCX Reports

## Status
Accepted (supersedes ADR-0007 "UI-only" restriction)

## Date
2026-11-07

## Context
ADR-0007 historically placed diagrams exclusively into Liber's React UI rail and excluded them from PDF and DOCX documents. Over time, user feedback required complete standalone documentation: reports exported as PDF or DOCX must contain the generated process flows, sequence charts, and architecture diagrams alongside charts and photos. Furthermore, user manual edits made in the visual editor must update the rasterized graphics and be reflected in rebuilt documents.

## Decision
1. **Rasterization Pipeline:** Diagrams from `figures.json` (`diagrams[]`) are rasterized to retina PNGs (`figures/dia_NN.png`) using the Playwright headless renderer and local `mermaid.min.js`, styled in harmony with the document theme pack (atelier / editorial / ocean / sunset / etc.).
2. **TeX Slot Injection:**
   - In LaTeX, the slot `%CASE3_DIAG:dia_NN%` is replaced with `\begin{figure}[H] \centering \includegraphics[width=0.92\linewidth]{figures/dia_NN.png} \caption{...} \label{dia:dia_NN} \end{figure}`.
   - If the model wraps the slot in an existing figure shell, the inner image line and caption/label are properly placed without duplicate shells.
   - If the LLM omits the slot, a smart fallback places unslotted valid diagrams immediately before the conclusion/summary section (`\section{Заключение}` / `\section{Выводы}`) or before `\end{document}`.
3. **Soft-Fail Guarantee:** If a diagram fails rendering or syntax validation, its slot is cleanly stripped without leaving broken LaTeX commands or hollow figure environments, ensuring LaTeX and Pandoc compilation never fails.
4. **Visual-Only Guarantee:** Raw Mermaid code editors and developer syntax indicators are completely removed from the UI. Users interact only with the visual React Flow diagram editor.
5. **In-Run Edits & Rebuild:** Visual diagram edits via `POST /api/runs/{run_id}/diagrams/{id}/edit` re-render `figures/dia_NN.png` and update `meta.media_status`, supporting deferred or immediate PDF/DOCX rebuild via `rebuild_run_docs`.

## Consequences
- Reports in PDF and DOCX now natively contain all generated and user-edited diagrams.
- DOCX export automatically ingests the rasterized diagram images via Pandoc without custom OOXML manipulation.
- ADR-0007's UI-only restriction is officially superseded.
