# ADR-0015: Numbers the user wrote are allowed

## Status
Accepted. Amends the allow-list bullet of [ADR-0013](0013-chat-memory-chain.md). Amended by [ADR-0016](0016-number-beside-its-word.md): in a new file the historical number stays beside its word. Chat answers still use the flat line.

## Date
2026-11-21

## Context
ADR-0013 keeps assistant digits out of the next PDF. It also drops a number the user wrote on an earlier turn. The model can see that number in the thread window and is then forbidden to repeat it.

The plan dated this decision ADR-0014. That number is already [ADR-0014](0014-dashboard-source-markdown.md) (dashboard markdown). This decision is 0015.

## Decision
- Allowed numbers are Source, the current message before the memory markers, and the tokens in `format_user_numbers`.
- That line is built from `chat_prompt` and `dialogue.user` only, oldest first, at most 40 distinct values. Text after `Разговор этого чата`, `Карточка этого чата`, `Один прошлый ход`, `Предыдущий ход этого чата`, `Числа из реплик пользователя`, or `Требования UI:` is not scanned.
- `chat_summary`, `chat_opening`, `dialogue.assistant`, the open-report block, and chart JSON stay off the list.
- A thread digit that is not on this line is still illegal. `test_old_request_number_does_not_enter_the_answer` stays.
- Section rewrite (`draft_section`) does not read the line.
- When the model repeats a forbidden number, the chat answer is the existing gate question. That question names the rejected number so the user can confirm it. The model sentence itself is not shown.

## Alternatives Considered

### Treat the verbatim window as Source
- Pros: the model may quote what it just said.
- Cons: a hallucinated digit becomes printable.
- Rejected.

## Consequences
- Positive: «сколько я называл» can repeat the user’s own figure.
- Negative: a chat answer may still repeat the value without the original word. A new file no longer does; see ADR-0016.
