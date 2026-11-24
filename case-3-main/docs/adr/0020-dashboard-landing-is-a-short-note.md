# ADR-0020: Closing a dashboard writes a short note, not an essay

## Status
Accepted

## Date
2026-11-23

## Context
Closing the Stimulsoft screen sent one chat turn that asked for a full analysis. The chat prompt also asks for several paragraphs, and the answer may use 4096 tokens. A second call writes the step lines before that. On a small screen the user waited, then received a long writeup. The next question did not keep those figures as the document.

## Decision
The automatic line after «В данные» asks for at most four sentences and is capped at 320 tokens. That line is the chat reply and `dashboard_note` on the run (`dashboard_note.md`). Step lines are not requested for this turn. A later message in the same chat reads every saved snapshot as its document, not only the newest one, unless this message attached a different long document. A full retelling happens only when the user asks for a detailed or full analysis.

## Alternatives Considered

### Keep generating the essay and hide it
- Pros: the deep text would exist immediately.
- Cons: the wait is the generation. Hiding it does not make the turn short.
- Rejected because the user is waiting on that call.

### Treat the previous answer as the number source
- Pros: no need to reload the screen file.
- Cons: ADR-0013 says the chat chain is not Source. A later answer would copy its own figures.
- Rejected because the screen markdown is the document.

## Consequences
- Positive: closing a screen returns a short reply. The next question still has the screen numbers and the note.
- Negative / follow-ups: the first reply is not a full briefing. «Подробно» or «полный разбор» is the long answer.
