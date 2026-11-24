/** Pure scroll state & smooth damped follower helpers for chat transcript. */

export type ScrollMetrics = {
  scrollHeight: number;
  scrollTop: number;
  clientHeight: number;
};

const REENGAGE_GAP_PX = 24;
const UPWARD_DELTA_PX = 2;

export function computeScrollGap(m: ScrollMetrics): number {
  return Math.max(0, m.scrollHeight - m.scrollTop - m.clientHeight);
}

export function isNearBottom(m: ScrollMetrics, threshold = REENGAGE_GAP_PX): boolean {
  return computeScrollGap(m) <= threshold;
}

export function nextStickOnWheel(deltaY: number, prevStick: boolean): boolean {
  if (deltaY < 0) return false;
  return prevStick;
}

export function nextStickOnScroll(
  prevStick: boolean,
  metrics: ScrollMetrics,
  prevScrollTop: number,
): { stick: boolean; scrollTop: number } {
  const gap = computeScrollGap(metrics);
  if (metrics.scrollTop < prevScrollTop - UPWARD_DELTA_PX && gap > 2) {
    return { stick: false, scrollTop: metrics.scrollTop };
  }
  if (!prevStick) {
    return {
      stick: gap <= REENGAGE_GAP_PX,
      scrollTop: metrics.scrollTop,
    };
  }
  return { stick: true, scrollTop: metrics.scrollTop };
}

export function stepSmoothScroll(
  currentTop: number,
  targetTop: number,
  dtMs: number,
): number {
  const diff = targetTop - currentTop;
  if (Math.abs(diff) <= 1) return targetTop;
  const dt = Math.min(50, Math.max(4, dtMs));
  const alpha = 1 - Math.exp(-dt / 85);
  const rawStep = diff * alpha;
  const minStep = Math.sign(diff) * Math.min(Math.abs(diff), 0.75);
  const step = Math.abs(rawStep) < Math.abs(minStep) ? minStep : rawStep;
  const next = currentTop + step;
  return diff > 0 ? Math.min(targetTop, next) : Math.max(targetTop, next);
}
