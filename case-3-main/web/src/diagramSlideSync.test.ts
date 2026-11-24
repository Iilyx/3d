import { describe, it } from "node:test";
import assert from "node:assert/strict";
import type { DiaNode } from "./diagramIr";
import {
  matchBulletToNodeIds,
  matchNodeToBulletIndex,
} from "./diagramSlideSync";

describe("diagramSlideSync", () => {
  const sampleNodes: DiaNode[] = [
    { id: "A", label: "Подача заявки через сайт", kind: "start" },
    { id: "B", label: "Автоматический скоринг", kind: "process" },
    { id: "C", label: "Проверка безопасности и андеррайтинг", kind: "decision" },
    { id: "D", label: "Выпуск договора и выплата", kind: "ok" },
  ];

  it("matches bullet with exact substring in node label", () => {
    const bullet = "Этап 1: Первичная подача заявки через сайт";
    const matched = matchBulletToNodeIds(bullet, 0, sampleNodes, 3);
    assert.deepEqual(Array.from(matched), ["A"]);
  });

  it("matches bullet by significant keyword overlap (>3 letters)", () => {
    const bullet = "Служба безопасности проводит андеррайтинг рисков";
    const matched = matchBulletToNodeIds(bullet, 1, sampleNodes, 3);
    assert.deepEqual(Array.from(matched), ["C"]);
  });

  it("matches bullet by step number prefix if no keyword matches", () => {
    const nodes: DiaNode[] = [
      { id: "s1", label: "Инициация", kind: "start" },
      { id: "s2", label: "Обработка", kind: "process" },
      { id: "s3", label: "Завершение", kind: "ok" },
    ];
    const bullet = "1. Первый предварительный шаг";
    const matched = matchBulletToNodeIds(bullet, 0, nodes, 3);
    assert.deepEqual(Array.from(matched), ["s1"]);
  });

  it("falls back to positional index when lengths align and no direct keywords match", () => {
    const nodes: DiaNode[] = [
      { id: "n1", label: "Alpha", kind: "process" },
      { id: "n2", label: "Beta", kind: "process" },
    ];
    const bullets = ["Общий обзор", "Детальные выводы"];
    const matched0 = matchBulletToNodeIds(bullets[0], 0, nodes, 2);
    const matched1 = matchBulletToNodeIds(bullets[1], 1, nodes, 2);
    assert.deepEqual(Array.from(matched0), ["n1"]);
    assert.deepEqual(Array.from(matched1), ["n2"]);
  });

  it("reverse maps nodeId to corresponding bullet index", () => {
    const bullets = [
      "Подача заявки клиентом",
      "Скоринг и расчет лимита",
      "Выпуск и подписание договора",
    ];
    const idxA = matchNodeToBulletIndex("A", sampleNodes, bullets);
    const idxB = matchNodeToBulletIndex("B", sampleNodes, bullets);
    const idxD = matchNodeToBulletIndex("D", sampleNodes, bullets);

    assert.equal(idxA, 0);
    assert.equal(idxB, 1);
    assert.equal(idxD, 2);
  });

  it("prefers explicit bullet_node_map over keyword heuristic", () => {
    // Even if bullet text has completely arbitrary words, bullet_node_map takes priority
    const matched = matchBulletToNodeIds(
      "Совершенно другой текст без ключевых слов",
      0,
      sampleNodes,
      3,
      { "0": "B" },
    );
    assert.deepEqual(Array.from(matched), ["B"]);
  });

  it("reverse maps nodeId via bullet_node_map even with arbitrary text", () => {
    const bullets = ["Кастомный текст 1", "Кастомный текст 2"];
    const idx = matchNodeToBulletIndex("B", sampleNodes, bullets, { "1": "B" });
    assert.equal(idx, 1);
  });
});
