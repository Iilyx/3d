import assert from "node:assert/strict";
import { test } from "node:test";
import {
  renderLightMd,
  renderLightMdBlocks,
  spaceAnswer,
  stabilizeStreamingMd,
} from "./lightMd";

test("a glued numbered conclusion becomes separate paragraphs", () => {
  const raw =
    "Выводы: план выполнен. 1. Период — январь. 2. Выполнение плана 112%.";
  const spaced = spaceAnswer(raw);
  assert.match(spaced, /\n\n1\. Период/);
  assert.match(spaced, /\n\n2\. Выполнение/);
  const html = renderLightMd(raw);
  assert.equal((html.match(/<p class="src-p">/g) || []).length, 3);
});

test("tables wrap in scrollable container and query highlight never touches HTML tags", () => {
  const md = "| Поле | Описание |\n| --- | --- |\n| table | строка class |\n";
  const html = renderLightMd(md, "table");
  assert.match(html, /<div class="msg-table-wrap"><table class="msg-table">/);
  assert.match(html, /<\/table><\/div>/);
  assert.match(html, /<mark class="src-hit">table<\/mark>/);
  // Attribute class="msg-table" must stay intact!
  assert.match(html, /class="msg-table"/);
});

test("stabilizeStreamingMd prevents unclosed bold/headings/code fences from flickering", () => {
  // Trailing bare heading marker doesn't flash raw "###"
  assert.equal(stabilizeStreamingMd("Итоги\n\n### "), "Итоги");
  // Unclosed bold renders as bold instead of literal "**Вывод"
  const boldHtml = renderLightMd(stabilizeStreamingMd("Текст\n\n**Вывод"));
  assert.match(boldHtml, /<strong>Вывод<\/strong>/);
  // Unclosed code fence closes cleanly
  const codeHtml = renderLightMd(stabilizeStreamingMd("Пример:\n\n```ts\nconst x = 1;"));
  assert.match(codeHtml, /<pre class="src-code"><code>/);
});

test("renderLightMdBlocks splits top-level blocks and keeps code fences intact", () => {
  const md = "## Заголовок\n\nПервый абзац.\n\n```py\na = 1\n\nb = 2\n```\n\n- раз\n- два";
  const blocks = renderLightMdBlocks(md);
  assert.equal(blocks.length, 4);
  assert.match(blocks[0], /^<h3 class="src-h">/);
  assert.match(blocks[1], /^<p class="src-p">/);
  assert.match(blocks[2], /^<pre class="src-code">/);
  assert.match(blocks[3], /^<ul class="src-ul">/);
});

test("stabilizeStreamingMd hides partial table rows and unconfirmed headers during streaming", () => {
  assert.equal(
    stabilizeStreamingMd("| Регион | Факт |\n| --- | --- |\n| Минск | 184"),
    "| Регион | Факт |\n| --- | --- |",
  );
  assert.equal(stabilizeStreamingMd("Итоги\n\n| Регион | Факт |"), "Итоги");
  assert.equal(
    stabilizeStreamingMd("Итоги\n\n| Регион | Факт |\n| ---"),
    "Итоги",
  );
});
