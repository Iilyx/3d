/** Adaptive frame-paced text revealer for smooth, flicker-free SSE streaming. */

export type StreamPacerUpdateMeta = {
  draining: boolean;
};

export type StreamPacerOptions = {
  /** Base reading speed in UTF-16 chars/sec (default ~68 for calm editorial feel). */
  baseCps?: number;
  /** Skip animation and reveal immediately (e.g. prefers-reduced-motion). */
  instant?: boolean;
  onUpdate: (visibleText: string, meta?: StreamPacerUpdateMeta) => void;
  now?: () => number;
  scheduleFrame?: (cb: (ts: number) => void) => number;
  cancelFrame?: (id: number) => void;
};

export type StreamPacer = {
  pushTarget: (fullText: string) => void;
  replaceTarget: (fullText: string) => void;
  markDone: (finalText?: string) => Promise<void>;
  flush: () => void;
  stop: () => void;
  getVisible: () => string;
  isDraining: () => boolean;
};

function commonPrefixLen(a: string, b: string): number {
  const max = Math.min(a.length, b.length);
  let i = 0;
  while (i < max && a.charCodeAt(i) === b.charCodeAt(i)) {
    i += 1;
  }
  return i;
}

function safeSliceEnd(text: string, rawEnd: number): number {
  const clamped = Math.max(0, Math.min(text.length, Math.floor(rawEnd)));
  if (clamped === 0 || clamped === text.length) return clamped;
  const prev = text.charCodeAt(clamped - 1);
  if (prev >= 0xd800 && prev <= 0xdbff) {
    const next = text.charCodeAt(clamped);
    if (next >= 0xdc00 && next <= 0xdfff) {
      return clamped + 1;
    }
    return clamped - 1;
  }
  return clamped;
}

const TABLE_ROW_RE = /^\s*\|.+\|\s*$/;
const TABLE_SEP_RE = /^\s*\|[\s:|-]+\|\s*$/;
const PIPE_START_RE = /^\s*\|/;
const PARTIAL_SEP_RE = /^\s*\|?[\s:|-]*$/;

function isInsideCodeFence(text: string, pos: number): boolean {
  let count = 0;
  let idx = 0;
  while (idx < pos) {
    const hit = text.indexOf("```", idx);
    if (hit < 0 || hit >= pos) break;
    count += 1;
    idx = hit + 3;
  }
  return count % 2 === 1;
}

function lineBounds(
  text: string,
  pos: number,
): { start: number; nl: number; endWithNl: number; line: string } {
  const prevNl = pos > 0 ? text.lastIndexOf("\n", pos - 1) : -1;
  const start = prevNl + 1;
  const nl = text.indexOf("\n", start);
  const endWithNl = nl >= 0 ? nl + 1 : text.length;
  const line = text.slice(start, nl >= 0 ? nl : text.length);
  return { start, nl, endWithNl, line };
}

function hasSeparatorAbove(target: string, lineStart: number): boolean {
  let pos = lineStart;
  while (pos > 0) {
    const nl = pos - 1;
    const prevStart = nl > 0 ? target.lastIndexOf("\n", nl - 1) + 1 : 0;
    const line = target.slice(prevStart, nl);
    if (!PIPE_START_RE.test(line)) return false;
    if (TABLE_SEP_RE.test(line)) return true;
    pos = prevStart;
  }
  return false;
}

function stepTableBoundary(
  target: string,
  currentEnd: number,
  candidateEnd: number,
  done: boolean,
): { end: number; tableAction: "none" | "hold" | "snap" } {
  if (candidateEnd <= currentEnd) {
    return { end: candidateEnd, tableAction: "none" };
  }
  const curLine = lineBounds(target, currentEnd);
  let pipeStart = -1;
  if (PIPE_START_RE.test(curLine.line) && !isInsideCodeFence(target, curLine.start)) {
    pipeStart = curLine.start;
  } else {
    let scan = curLine.nl;
    while (scan >= 0 && scan + 1 < candidateEnd) {
      const nextLine = lineBounds(target, scan + 1);
      if (PIPE_START_RE.test(nextLine.line) && !isInsideCodeFence(target, nextLine.start)) {
        pipeStart = nextLine.start;
        break;
      }
      scan = nextLine.nl;
    }
  }
  if (pipeStart < 0) {
    return { end: candidateEnd, tableAction: "none" };
  }
  if (pipeStart > currentEnd) {
    return { end: pipeStart, tableAction: "none" };
  }
  if (currentEnd > pipeStart) {
    return { end: candidateEnd, tableAction: "none" };
  }

  const row1 = lineBounds(target, pipeStart);
  if (hasSeparatorAbove(target, pipeStart)) {
    if (row1.nl >= 0) {
      return TABLE_ROW_RE.test(row1.line)
        ? { end: row1.endWithNl, tableAction: "snap" }
        : { end: candidateEnd, tableAction: "none" };
    }
    if (done) {
      return TABLE_ROW_RE.test(row1.line)
        ? { end: target.length, tableAction: "snap" }
        : { end: candidateEnd, tableAction: "none" };
    }
    return { end: currentEnd, tableAction: "hold" };
  }

  if (row1.nl < 0) {
    return done
      ? { end: candidateEnd, tableAction: "none" }
      : { end: currentEnd, tableAction: "hold" };
  }
  if (!TABLE_ROW_RE.test(row1.line)) {
    return { end: candidateEnd, tableAction: "none" };
  }

  const row2 = lineBounds(target, row1.nl + 1);
  if (row2.nl < 0) {
    if (done) {
      return TABLE_SEP_RE.test(row2.line)
        ? { end: target.length, tableAction: "snap" }
        : { end: candidateEnd, tableAction: "none" };
    }
    return PARTIAL_SEP_RE.test(row2.line)
      ? { end: currentEnd, tableAction: "hold" }
      : { end: candidateEnd, tableAction: "none" };
  }

  if (TABLE_SEP_RE.test(row2.line)) {
    return { end: row2.endWithNl, tableAction: "snap" };
  }
  return { end: candidateEnd, tableAction: "none" };
}

export function createStreamPacer(opts: StreamPacerOptions): StreamPacer {
  const baseCps = Math.max(20, opts.baseCps ?? 68);
  const instant = Boolean(opts.instant);
  const now = opts.now ?? (() => (typeof performance !== "undefined" ? performance.now() : Date.now()));
  const scheduleFrame =
    opts.scheduleFrame ??
    ((cb: (ts: number) => void) => window.requestAnimationFrame(cb));
  const cancelFrame =
    opts.cancelFrame ?? ((id: number) => window.cancelAnimationFrame(id));

  let target = "";
  let floatRevealed = 0;
  let lastEmit = "";
  let lastDraining: boolean | null = null;
  let done = false;
  let stopped = false;
  let rafId: number | null = null;
  let lastTs: number | null = null;
  let rowHoldUntilTs = 0;
  const waiters: Array<() => void> = [];

  const resolveWaiters = () => {
    while (waiters.length > 0) {
      const resolve = waiters.shift();
      resolve?.();
    }
  };

  const emitIfChanged = (next: string, draining = floatRevealed < target.length) => {
    if (next === lastEmit && draining === lastDraining) return;
    lastEmit = next;
    lastDraining = draining;
    opts.onUpdate(next, { draining });
  };

  const cancelScheduled = () => {
    if (rafId !== null) {
      cancelFrame(rafId);
      rafId = null;
    }
    lastTs = null;
  };

  const tick = (ts: number) => {
    rafId = null;
    if (stopped) return;

    const prevTs = lastTs ?? ts - 16;
    lastTs = ts;
    const dtMs = Math.min(50, Math.max(8, ts - prevTs));
    const backlog = Math.max(0, target.length - floatRevealed);

    if (backlog <= 0) {
      floatRevealed = target.length;
      emitIfChanged(target);
      if (done) resolveWaiters();
      return;
    }

    const prevEnd = safeSliceEnd(target, floatRevealed);
    if (ts < rowHoldUntilTs && prevEnd < target.length) {
      const peek = stepTableBoundary(target, prevEnd, Math.min(target.length, prevEnd + 1), done);
      if (peek.tableAction === "snap") {
        rafId = scheduleFrame(tick);
        return;
      }
      if (peek.tableAction === "hold") {
        lastTs = null;
        return;
      }
      rowHoldUntilTs = 0;
    }

    const cps = done
      ? backlog > 300
        ? Math.min(1200, Math.max(baseCps * 1.6, backlog))
        : Math.max(baseCps * 1.5, backlog * 2.2)
      : baseCps + Math.min(260, backlog * 0.4);

    const nextFloat = Math.min(target.length, floatRevealed + (cps * dtMs) / 1000);
    const candidateEnd = safeSliceEnd(target, nextFloat);
    const step = stepTableBoundary(target, prevEnd, candidateEnd, done);
    const end = step.end;

    if (step.tableAction === "snap") {
      floatRevealed = end;
      const rowDelayMs = done ? (backlog > 300 ? 55 : 85) : 115;
      rowHoldUntilTs = ts + rowDelayMs;
    } else if (step.tableAction === "hold") {
      floatRevealed = end;
      emitIfChanged(target.slice(0, end), false);
      lastTs = null;
      return;
    } else {
      floatRevealed = end === candidateEnd ? Math.max(nextFloat, end) : end;
      rowHoldUntilTs = 0;
    }
    const stillDraining = end < target.length;
    if (!stillDraining) {
      floatRevealed = target.length;
    }
    emitIfChanged(target.slice(0, end), stillDraining);

    if (stillDraining) {
      rafId = scheduleFrame(tick);
    } else {
      floatRevealed = target.length;
      lastTs = null;
      if (done) resolveWaiters();
    }
  };

  const ensureRunning = () => {
    if (stopped || rafId !== null) return;
    if (floatRevealed >= target.length) {
      if (done) resolveWaiters();
      return;
    }
    lastTs = now();
    rafId = scheduleFrame(tick);
  };

  return {
    pushTarget(fullText: string) {
      if (stopped) return;
      target = fullText || "";
      if (instant) {
        floatRevealed = target.length;
        emitIfChanged(target);
        return;
      }
      if (floatRevealed > target.length) {
        floatRevealed = safeSliceEnd(target, target.length);
        emitIfChanged(target.slice(0, floatRevealed));
      }
      ensureRunning();
    },

    replaceTarget(fullText: string) {
      if (stopped) return;
      const next = fullText || "";
      const visible = target.slice(0, safeSliceEnd(target, floatRevealed));
      const keep = commonPrefixLen(visible, next);
      target = next;
      rowHoldUntilTs = 0;
      if (instant) {
        floatRevealed = target.length;
        emitIfChanged(target);
        return;
      }
      floatRevealed = Math.min(floatRevealed, keep);
      const end = safeSliceEnd(target, floatRevealed);
      emitIfChanged(target.slice(0, end));
      ensureRunning();
    },

    markDone(finalText?: string) {
      if (stopped) return Promise.resolve();
      if (typeof finalText === "string") {
        const next = finalText;
        if (next && next !== target) {
          const visible = target.slice(0, safeSliceEnd(target, floatRevealed));
          const keep = commonPrefixLen(visible, next);
          target = next;
          floatRevealed = Math.min(floatRevealed, keep);
        }
      }
      done = true;
      if (instant || floatRevealed >= target.length) {
        cancelScheduled();
        floatRevealed = target.length;
        emitIfChanged(target);
        return Promise.resolve();
      }
      return new Promise<void>((resolve) => {
        waiters.push(resolve);
        ensureRunning();
      });
    },

    flush() {
      cancelScheduled();
      floatRevealed = target.length;
      emitIfChanged(target);
      if (done) resolveWaiters();
    },

    stop() {
      stopped = true;
      cancelScheduled();
      resolveWaiters();
    },

    getVisible() {
      return target.slice(0, safeSliceEnd(target, floatRevealed));
    },

    isDraining() {
      return floatRevealed < target.length;
    },
  };
}
