import assert from "node:assert/strict";
import test from "node:test";
import {
  botHistoryResult,
  messagesFromMemory,
  priorRunIdFromMessages,
} from "./priorRun";

test("priorRunIdFromMessages uses the latest bot run, skipping an empty pending bubble", () => {
  const id = priorRunIdFromMessages([
    { role: "user", text: "первый" },
    { role: "bot", text: "готово", result: { run_id: "run_a" } },
    { role: "user", text: "короче" },
    { role: "bot", text: "жду", pending: true },
  ]);
  assert.equal(id, "run_a");
});

test("priorRunIdFromMessages stays on the chat head after the rail shows an older file", () => {
  const id = priorRunIdFromMessages([
    {
      role: "bot",
      result: { run_id: "report_run", chain_head: "chat_head" },
    },
  ]);
  assert.equal(id, "chat_head");
});

test("an isolated carried file does not become the next chat", () => {
  assert.equal(
    priorRunIdFromMessages([
      {
        role: "bot",
        result: { run_id: "source_old", isolated: true },
      },
    ]),
    null,
  );
});

test("priorRunIdFromMessages is empty on a fresh chat", () => {
  assert.equal(priorRunIdFromMessages([]), null);
  assert.equal(
    priorRunIdFromMessages([{ role: "user", text: "только вопрос" }]),
    null,
  );
});

test("messagesFromMemory keeps the chat in order, including a later edit", () => {
  let n = 0;
  const lines = messagesFromMemory(
    [
      {
        run_id: "a",
        chat_prompt: "первый",
        chat_summary: "ответ 1",
      },
      {
        run_id: "b",
        chat_prompt: "переделай введение",
        chat_summary: "Переписал",
        dialogue: [
          { user: "ещё точнее", assistant: "Переписал раздел «Введение»" },
        ],
      },
    ],
    () => `id${(n += 1)}`,
  );
  assert.deepEqual(
    lines.map((line) => line.text),
    [
      "первый",
      "ответ 1",
      "переделай введение",
      "Переписал",
      "ещё точнее",
      "Переписал раздел «Введение»",
    ],
  );
  assert.equal(lines[0].role, "user");
  assert.equal(lines.at(-1)?.role, "bot");
});

test("messagesFromMemory keeps paragraph breaks for the screen", () => {
  let n = 0;
  const lines = messagesFromMemory(
    [
      {
        chat_prompt: "Первая мысль.\n\nВторая мысль.",
        chat_summary: "Касса держится.\n\n- пункт один\n- пункт два",
        chat_opening: "Соберу ответ.\nБез новых чисел.",
      },
    ],
    () => `id${(n += 1)}`,
  );
  assert.equal(lines[0].text, "Первая мысль.\n\nВторая мысль.");
  assert.equal(lines[1].text, "Касса держится.\n\n- пункт один\n- пункт два");
  assert.equal(lines[1].lead, "Соберу ответ.\nБез новых чисел.");
});

test("messagesFromMemory restores the dashboard card from the saved screen", () => {
  let n = 0;
  const lines = messagesFromMemory(
    [
      {
        chat_prompt: "разбери",
        chat_summary: "Выручка 12.",
        dashboard_source:
          "# Данные дашборда\n\n## Заголовок\nПоступления за январь\n\n| А | Б |\n| --- | --- |\n| Минск | 12 |\n",
      },
    ],
    () => `id${(n += 1)}`,
  );
  assert.equal(lines[1].role, "bot");
  assert.equal(lines[1].dashboard?.shots[0]?.name, "Поступления за январь");
  assert.match(lines[1].dashboard?.shots[0]?.markdown || "", /Минск/);
});

test("messagesFromMemory keeps uploaded photos on the user line", () => {
  let n = 0;
  const lines = messagesFromMemory(
    [
      {
        chat_prompt: "смотри",
        chat_summary: "вижу",
        photos: [{ name: "usr_01", url: "/api/runs/a/figures/usr_01.png" }],
      },
    ],
    () => `id${(n += 1)}`,
  );
  assert.equal(lines[0].role, "user");
  assert.deepEqual(lines[0].photos, [
    { name: "usr_01", url: "/api/runs/a/figures/usr_01.png" },
  ]);
  assert.equal(lines[1].photos, undefined);
});

test("messagesFromMemory and botHistoryResult restore inline chart/diagram previews", () => {
  let n = 0;
  const lines = messagesFromMemory(
    [
      {
        run_id: "run_chart",
        output_mode: "chat",
        chat_prompt: "Построй график по лидерам",
        chat_summary: "Построил график.",
        previews: [
          {
            url: "/api/runs/run_chart/previews/cht_01.png",
          },
          {
            id: "dia_01",
            kind: "diagram",
            url: "/api/runs/run_chart/previews/dia_01.png",
          },
        ],
      },
    ],
    () => `id${(n += 1)}`,
  );
  const botLine = lines[1];
  assert.equal(botLine?.role, "bot");
  assert.equal(botLine?.runId, "run_chart");
  assert.equal(botLine?.outputMode, "chat");
  assert.equal(botLine?.previews?.[0]?.id, "cht_01");
  assert.equal(botLine?.previews?.[0]?.kind, "chart");

  const res = botHistoryResult(botLine!, "fallback_run");
  assert.equal(res?.run_id, "run_chart");
  assert.equal(res?.output_mode, "chat");
  assert.equal(res?.previews?.length, 2);
  assert.equal(res?.charts_ok, 1);
});

test("messagesFromMemory restores attached documents on user turns", () => {
  let n = 0;
  const lines = messagesFromMemory(
    [
      {
        run_id: "run_doc",
        chat_prompt: "Сравни отчёт и заметку",
        chat_summary: "Сравнил.",
        attachments: [
          {
            name: "отчёт.pdf",
            title: "отчёт.pdf",
            fileName: "отчёт.pdf",
            text: "Текст PDF",
            viewMode: "document",
            previewUrl: "/api/source/files/ing_1/preview",
            originalUrl: "/api/source/files/ing_1/original",
            format: "pdf",
          },
          {
            name: "заметка.txt",
            text: "Текст заметки",
          },
        ],
      },
    ],
    () => `id${(n += 1)}`,
  );
  assert.equal(lines[0].role, "user");
  assert.equal(lines[0].attachments?.length, 2);
  assert.equal(lines[0].attachments?.[0]?.viewMode, "document");
  assert.equal(lines[0].attachments?.[0]?.previewUrl, "/api/source/files/ing_1/preview");
  assert.equal(lines[0].attachments?.[1]?.fileName, "заметка.txt");
});
