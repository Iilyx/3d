import assert from "node:assert/strict";
import { describe, it } from "node:test";
import { createStreamPacer } from "./streamPacer";

function makeManualClock() {
  let nowMs = 1000;
  let nextId = 1;
  const queue = new Map<number, (ts: number) => void>();
  return {
    now: () => nowMs,
    scheduleFrame: (cb: (ts: number) => void) => {
      const id = nextId++;
      queue.set(id, cb);
      return id;
    },
    cancelFrame: (id: number) => {
      queue.delete(id);
    },
    step(ms: number) {
      nowMs += ms;
      const entries = Array.from(queue.entries());
      queue.clear();
      for (const [, cb] of entries) {
        cb(nowMs);
      }
    },
    pendingCount: () => queue.size,
  };
}

describe("streamPacer", () => {
  it("reveals text smoothly at calm reading pace instead of dumping all at once", () => {
    const clock = makeManualClock();
    const emitted: string[] = [];
    const pacer = createStreamPacer({
      baseCps: 80,
      onUpdate: (v) => emitted.push(v),
      now: clock.now,
      scheduleFrame: clock.scheduleFrame,
      cancelFrame: clock.cancelFrame,
    });

    const full = "Аналитика показывает устойчивый рост показателей за первый квартал текущего года.";
    pacer.pushTarget(full);

    // First frame after 16ms (~1-2 chars, not all 80 chars!)
    clock.step(16);
    const first = pacer.getVisible();
    assert.ok(first.length >= 1 && first.length < 10, `got ${first.length}`);
    assert.equal(full.startsWith(first), true);

    // Advance several 20ms frames — grows monotonically
    for (let i = 0; i < 15; i += 1) {
      clock.step(20);
    }
    const mid = pacer.getVisible();
    assert.ok(mid.length > first.length);
    assert.ok(mid.length < full.length);
    assert.equal(full.startsWith(mid), true);
    pacer.stop();
  });

  it("handles replaceTarget from common prefix without resetting visible text to zero", () => {
    const clock = makeManualClock();
    const emitted: string[] = [];
    const pacer = createStreamPacer({
      baseCps: 100,
      onUpdate: (v) => emitted.push(v),
      now: clock.now,
      scheduleFrame: clock.scheduleFrame,
      cancelFrame: clock.cancelFrame,
    });

    pacer.pushTarget("Выручка за январь составила 120 млн руб. Итог положительный.");
    for (let i = 0; i < 15; i += 1) {
      clock.step(25);
    }
    const beforeReplace = pacer.getVisible();
    assert.ok(beforeReplace.length > 15);

    // Grounding tweaks only the tail; prefix "Выручка за январь " stays identical.
    pacer.replaceTarget("Выручка за январь составила 125 млн руб.");
    const afterReplace = pacer.getVisible();
    assert.ok(
      afterReplace.startsWith("Выручка за январь "),
      `expected common prefix preserved, got: ${afterReplace}`,
    );
    pacer.stop();
  });

  it("drains remaining text smoothly on markDone and resolves the returned promise", async () => {
    const clock = makeManualClock();
    const emitted: string[] = [];
    const pacer = createStreamPacer({
      baseCps: 80,
      onUpdate: (v) => emitted.push(v),
      now: clock.now,
      scheduleFrame: clock.scheduleFrame,
      cancelFrame: clock.cancelFrame,
    });

    const text = "Краткий итог: план перевыполнен по всем регионам без исключения.";
    let settled = false;
    const donePromise = pacer.markDone(text).then(() => {
      settled = true;
    });

    // Not instantaneously settled on first frame
    clock.step(16);
    assert.equal(settled, false);
    assert.ok(pacer.getVisible().length < text.length);

    // Step until drained
    for (let i = 0; i < 60 && pacer.isDraining(); i += 1) {
      clock.step(30);
    }
    await donePromise;
    assert.equal(settled, true);
    assert.equal(pacer.getVisible(), text);
  });

  it("never splits UTF-16 surrogate pairs (emoji)", () => {
    const clock = makeManualClock();
    const emitted: string[] = [];
    const pacer = createStreamPacer({
      baseCps: 60, // ~1 UTF-16 unit per 16ms frame
      onUpdate: (v) => emitted.push(v),
      now: clock.now,
      scheduleFrame: clock.scheduleFrame,
      cancelFrame: clock.cancelFrame,
    });

    pacer.pushTarget("🚀📊✅");
    for (let i = 0; i < 12; i += 1) {
      clock.step(16);
      const vis = pacer.getVisible();
      if (vis.length > 0) {
        const lastCode = vis.charCodeAt(vis.length - 1);
        const isHighSurrogate = lastCode >= 0xd800 && lastCode <= 0xdbff;
        assert.equal(isHighSurrogate, false, `dangling high surrogate in ${JSON.stringify(vis)}`);
      }
    }
    pacer.stop();
  });

  it("reveals immediately when instant=true (reduced motion)", async () => {
    const clock = makeManualClock();
    const emitted: string[] = [];
    const pacer = createStreamPacer({
      instant: true,
      onUpdate: (v) => emitted.push(v),
      now: clock.now,
      scheduleFrame: clock.scheduleFrame,
      cancelFrame: clock.cancelFrame,
    });

    pacer.pushTarget("Быстрый текст");
    assert.equal(pacer.getVisible(), "Быстрый текст");
    assert.equal(clock.pendingCount(), 0);
    await pacer.markDone("Быстрый текст!");
    assert.equal(pacer.getVisible(), "Быстрый текст!");
  });

  it("reveals markdown table header+sep and each row whole without flashing partial pipes", async () => {
    const clock = makeManualClock();
    const emitted: string[] = [];
    const pacer = createStreamPacer({
      baseCps: 80,
      onUpdate: (v) => emitted.push(v),
      now: clock.now,
      scheduleFrame: clock.scheduleFrame,
      cancelFrame: clock.cancelFrame,
    });

    const tableMd = [
      "Вводная строка.",
      "",
      "| Область | Факт | План |",
      "| --- | --- | --- |",
      "| Минск | 184 520 | 180 000 |",
      "| Брест | 57 846 | 60 000 |",
      "",
      "Итог положительный.",
    ].join("\n");

    const donePromise = pacer.markDone(tableMd);
    for (let i = 0; i < 80 && pacer.isDraining(); i += 1) {
      clock.step(30);
    }
    await donePromise;
    assert.equal(pacer.getVisible(), tableMd);

    // None of the intermediate frames may expose a half-typed "| ..." table line
    for (const snap of emitted) {
      const lines = snap.split("\n");
      for (let idx = 0; idx < lines.length; idx += 1) {
        const line = lines[idx];
        if (!/^\s*\|/.test(line)) continue;
        assert.match(line, /^\s*\|.+\|\s*$/, `partial pipe line leaked: ${JSON.stringify(line)} in ${JSON.stringify(snap)}`);
      }
      const headerIdx = lines.indexOf("| Область | Факт | План |");
      if (headerIdx >= 0) {
        assert.equal(lines[headerIdx + 1], "| --- | --- | --- |", `header appeared without separator: ${JSON.stringify(snap)}`);
      }
    }

    const withHeader = emitted.findIndex((s) => s.includes("| --- | --- | --- |"));
    const withRow1 = emitted.findIndex((s) => s.includes("| Минск | 184 520 | 180 000 |"));
    const withRow2 = emitted.findIndex((s) => s.includes("| Брест | 57 846 | 60 000 |"));
    assert.ok(withHeader >= 0 && withRow1 > withHeader && withRow2 > withRow1);
  });

  it("holds incomplete SSE table row until complete line arrives, then reveals whole row", () => {
    const clock = makeManualClock();
    const emitted: string[] = [];
    const pacer = createStreamPacer({
      baseCps: 120,
      onUpdate: (v) => emitted.push(v),
      now: clock.now,
      scheduleFrame: clock.scheduleFrame,
      cancelFrame: clock.cancelFrame,
    });

    pacer.pushTarget("Данные:\n\n| Регион | Факт |\n| --- | --- |\n| Минск | 184");
    for (let i = 0; i < 20; i += 1) {
      clock.step(30);
    }
    assert.equal(pacer.getVisible(), "Данные:\n\n| Регион | Факт |\n| --- | --- |\n");

    pacer.pushTarget("Данные:\n\n| Регион | Факт |\n| --- | --- |\n| Минск | 184 520 |\n");
    for (let i = 0; i < 10; i += 1) {
      clock.step(30);
    }
    assert.equal(
      pacer.getVisible(),
      "Данные:\n\n| Регион | Факт |\n| --- | --- |\n| Минск | 184 520 |\n",
    );
    assert.equal(emitted.some((s) => s.endsWith("| Минск | 184")), false);
    pacer.stop();
  });

  it("does not stall standalone non-table pipe text on markDone", async () => {
    const clock = makeManualClock();
    const pacer = createStreamPacer({
      baseCps: 80,
      onUpdate: () => {},
      now: clock.now,
      scheduleFrame: clock.scheduleFrame,
      cancelFrame: clock.cancelFrame,
    });
    const text = "| заметка без таблицы";
    const p = pacer.markDone(text);
    for (let i = 0; i < 40 && pacer.isDraining(); i += 1) {
      clock.step(30);
    }
    await p;
    assert.equal(pacer.getVisible(), text);
  });

  it("reports draining=true while typing and draining=false when caught up", async () => {
    const clock = makeManualClock();
    const states: boolean[] = [];
    const pacer = createStreamPacer({
      baseCps: 80,
      onUpdate: (_v, meta) => {
        if (meta) states.push(meta.draining);
      },
      now: clock.now,
      scheduleFrame: clock.scheduleFrame,
      cancelFrame: clock.cancelFrame,
    });

    const text = "Короткий вывод по данным таблицы.";
    const p = pacer.markDone(text);
    for (let i = 0; i < 50 && pacer.isDraining(); i += 1) {
      clock.step(30);
    }
    await p;
    assert.ok(states.length >= 2);
    assert.equal(states[0], true);
    assert.equal(states[states.length - 1], false);
  });
});
