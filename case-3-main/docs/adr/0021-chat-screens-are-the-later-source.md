# ADR-0021: Later turns and files use the chat's screens

## Status
Accepted. Narrows [ADR-0013](0013-chat-memory-chain.md): the thread stays not an allow-list, and the chat's dashboard documents do.

## Date
2026-11-23

## Context
After a dashboard screen, the next message and the next report saw only the new sentence. The previous answer had the figures, and the prompt forbids treating that answer as Source. A made-up digit in an answer must still not enter a PDF. The figures on the saved screens are the figures the user wants in the conversation and in the file.

## Decision
A later chat answer, report, diagram, or presentation uses every dashboard snapshot saved in this chat, unless this message attached a different long document. A number from a previous answer may be repeated only when that number is in those snapshots or the user wrote it. The thread block stays labeled not Source.

## Alternatives Considered

### Put every previous answer on the allow-list
- Pros: a computed sentence could be copied into the file.
- Cons: a digit the model invented would print in the PDF. ADR-0013 exists to stop that.
- Rejected because the screens already hold the figures.

### Leave artifacts on the new sentence only
- Pros: no change to report grounding.
- Cons: «сделай отчёт по этим данным» builds an empty file after a real screen.
- Rejected because the same screens are already the chat document.

## Consequences
- Positive: a question, a chart, a report, a diagram, and a presentation in this chat can use a figure from any saved snapshot.
- Negative / follow-ups: a figure that appears only in a previous answer, and not on a snapshot or in the user's words, still does not enter a file.
