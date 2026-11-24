# KI: Chat memory

## What
One Liber chat is a chain of runs. The chain explains the next line. It is not a source of numbers.

## Entry
- Chain, thread, screen: `src/case3/chat_memory.py` (`load_chain`, `format_thread`, `memory_view`, `report_tex`)
- Prompt the model sees: `src/case3/chat_turn.py` (`_user_block`, `report_context`, `try_chat_answer`)
- Assembly as `/api/run`: `prior_turn.prior_block_for_form` → `insert_prior_turn` → `user_text_before_ui` → `try_chat_answer`
- Open report in a chat answer: `pipeline._finish_chat_answer` → `chat_report_block`
- Digits in a new file: `src/case3/fact_ground.py`, called from `generate_document` and `slides_job`
- Edit router: `chat_act.resolve_act`. Execution: `chat_revise.try_chat_revise`
- Screen: `GET /api/runs/{id}/memory` → `web/src/domain/priorRun.ts` → `MsgMarkdown`
- Why: ADR-0013. Allow-list: ADR-0015. New files bind the number to its word: ADR-0016. ADR-0011 keeps SSE, cancel, and the diagram ceiling only.

## Invariants
- Max 48 hops. The last 8 keep paragraphs: 2000, 1600, 1200, then 800. A turn past that is one line of 160 characters, digits stripped, and that block is cut from the front past 6000. The prompt cap is 150000 characters. A legal thread is pasted whole. A chat answer may run to 4096 tokens.
- A plain message lifts one full turn from outside the 8-turn window when a content word matches, including dialogue. «Вспомни …» does not need «про». Turns already inside the window are not lifted again.
- Question cap 6000, head plus the last paragraph. Chat source cap is 80000 characters. A dashboard table under that cap is pasted whole, with a line «Вижу все N строк.» A longer one keeps the header, the rows the question names, then as many other rows as fit, and the line says «Вижу K из M».
- `dialogue`: 12 notes, 300 characters, line breaks kept on write and on read.
- Allowed numbers: Source ∪ the current message ∪ `format_user_numbers` (user fields only, cap 40). Assistant fields and a bare thread digit stay illegal. Not the report block, not chart JSON. Spoken cardinals count as digits. «один» does not.
- In a new file a historical pair (`2 слайд`) is legal only beside that stem. Source and this message stay global. Chart `data` arrays ignore the pair. A chat answer may still repeat the value.
- A named section is included once. Two equally matching headings stay as an outline only.
- Regex order in `resolve_act` is the spec. Do not add a second model to route edits. Two clauses joined by «и» or «;» run in sentence order when each clause is its own edit. A semicolon inside one table row stays one act.

## Gotchas
- `output_mode=chat` is not a real intent mode. `build_intent_from_ui` stores `auto` and still appends `Требования UI:`. The chat path strips that suffix.
- `memory_view` used to flatten paragraphs. Reopen goes through it. Live chat does not.
- Notes saved before 2026-11-19 are already one line. Reading them cannot put the line breaks back.
- A clause whose only numbers are foreign is dropped. A clause that also has a Source number keeps that number.
- «Перепиши раздел» rewrites every paragraph under that heading and rebuilds PDF once. A named абзац still rewrites one. Supplied text replaces the section and drops the other paragraphs. «Сократи весь отчёт» rewrites every paragraph under each heading and rebuilds once.
- An in-place edit writes one dialogue note, on the chat head. The older file is not copied a second time. A file carried from another chat gets no note. Undo and a structure change open the deck when the last edit was a deck edit, including the undo after that.
- A chat can add or delete a table row (`в таблице добавь строку: …; …`, `убери из таблицы строку …`). The open report shows up to 24 table rows.
- A phrase that aims at a photo already in the chat (`на фото …`, `поправь фото usr_01: …`) calls `edit_figure_in_run` with `mode="edit"`. A caption phrase stays a caption. «сделай фото …» stays a new build.
- «убери раздел Название» deletes that heading and the body through the next heading of the same or higher level, then rebuilds PDF and DOCX once. One paragraph inside a section is still a rewrite, not a delete.
- A talk answer about an edit the router did not take is an ordinary sentence: what it cannot do, what it can do instead, and one phrase to copy. No caps heading. Chart numbers and a diagram legend are talk on purpose.
- A number with no row name may be repeated anywhere in a new file. A sentence that names one table row may use that row's cells and verifiable pairwise/3-addend arithmetic (`_verifies_math`) across rows named in the sentence or question. Two region names in one sentence each keep the number written next to them (`_owner_rows` binds numbers to the nearest left or close right entity `<= 32` chars): «Минская 94 073 и Гомельская 105 865» and «при 10 790,0 у Пинского района» do not swap. A share from «Производные» stays on its row and is not that row's sum unless the sentence says «доля» or writes `%`. A number that occurs only on an earlier user line may not move: it stays beside the same stem (ADR-0016).
- «поменяй заголовок слайда 3 на …» (or «второго слайда») routes `retitle` with `slide=3` (`_slide_number_named`). «в таблице поменяй/исправь X на Y» matches multi-word cell phrases via `_word_hit`. «распиши/разверни/дополни раздел X подробнее» routes to section `rewrite`. Prior inline chat charts/diagrams are resolved across the full chain via `reversed(load_chain_dirs(...))`.
- A `?` does not cancel a line that already has an edit verb. `почему` and `зачем` stay talk.
- A question (`?`, что, какая, сколько) stays chat even when the report plaque is on or the sentence names отчёт or слайд. «проанализируй регионы», «сравни области» and «посчитай доли» with a plaque build that artifact (ADR-0017). The same verbs without a plaque stay chat. «проанализируй отчёт» stays chat. «сделай отчёт», «сделай word», «сделай справку» and «собери ворд» build a report. «Построй график» and «нарисуй диаграмму» build a report. «Нарисуй схему» stays a scheme. A KPI turned into a ring is one slice of that number. «В данные» shows the table-truncation warning. A Word table on the paperclip is a markdown table with every column. Settings has no Stimulsoft block; the data path is «Выбрать данные» → «В данные».
- `fact_conflict` ignores a year (`2025`), a rank (`1 место`, `2 раза`), and the column words область/регион/район. A named region with a different sum still asks. The same digit on the next metric does not hide a clash (`касса 40` beside `выручка 40`). «Выросла на 7%» is a change, not a new revenue cell. «Собрано» stays in a chat answer. One foreign number drops its sentence; the rest of the answer stays. The opening line still rejects «готово».
- `105 865,2` is one number (`105865.2`). The fragments `105` and `865.2` are not allowed on their own. In a chart array `[100,40]` the comma splits, so both points stay. `[12,5]` is one point `12.5`, and so is `105 865,2`. A label that names one table row keeps only that row's cells: Гомельская cannot show Минская's sum. A month label is not a row. A chart `null` keeps its category. A markdown list marker `1.` is not a number. A four-digit year at the start of a line stays: `2024. Выручка 10` keeps 2024. `1.1` still is a number. Card text on a slide is checked the same way as the title. A horizontal bar grows with the number of regions, up to 900px.
- A Source longer than the chat cap also sends its markdown headings, capped at 1200. Under the cap the file is pasted whole and the outline is not repeated.
- A plain message lifts an old turn on one stem when that is the only content stem, and on two stems when the question has two or more.
