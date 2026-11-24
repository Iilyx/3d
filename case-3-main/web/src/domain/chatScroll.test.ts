import assert from "node:assert/strict";
import { describe, it } from "node:test";
import {
  computeScrollGap,
  nextStickOnScroll,
  nextStickOnWheel,
  stepSmoothScroll,
} from "./chatScroll";

describe("chatScroll", () => {
  it("disengages stickBottom immediately on any upward wheel input", () => {
    assert.equal(nextStickOnWheel(-12, true), false);
    assert.equal(nextStickOnWheel(-1, true), false);
    assert.equal(nextStickOnWheel(24, true), true);
    assert.equal(nextStickOnWheel(24, false), false);
  });

  it("disengages stickBottom when user scrolls up even by 30px (less than old 96px trap)", () => {
    const res = nextStickOnScroll(
      true,
      { scrollHeight: 2000, scrollTop: 970, clientHeight: 1000 },
      1000,
    );
    assert.equal(res.stick, false);
    assert.equal(computeScrollGap({ scrollHeight: 2000, scrollTop: 970, clientHeight: 1000 }), 30);
  });

  it("re-engages stickBottom only when scrolled back close to bottom (<= 24px)", () => {
    const stillUp = nextStickOnScroll(
      false,
      { scrollHeight: 2000, scrollTop: 940, clientHeight: 1000 },
      900,
    );
    assert.equal(stillUp.stick, false);

    const atBottom = nextStickOnScroll(
      false,
      { scrollHeight: 2000, scrollTop: 982, clientHeight: 1000 },
      940,
    );
    assert.equal(atBottom.stick, true);
  });

  it("converges smoothly toward targetTop without overshooting", () => {
    let top = 500;
    const target = 620;
    const steps: number[] = [];
    for (let i = 0; i < 30 && top < target; i += 1) {
      top = stepSmoothScroll(top, target, 16);
      steps.push(top);
    }
    assert.ok(steps.length > 3, "should take multiple frames instead of snapping in 1 frame");
    assert.equal(top, target);
    for (let i = 1; i < steps.length; i += 1) {
      assert.ok(steps[i] >= steps[i - 1]);
      assert.ok(steps[i] <= target);
    }
  });
});
