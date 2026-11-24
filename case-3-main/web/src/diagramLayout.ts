/** Simple BFS layout for Liber DiagramIR → React Flow positions. */

import type { DiagramIR } from "./diagramIr";

const GAP_X = 240;
const GAP_Y = 110;

export function layoutPositions(
  ir: DiagramIR,
): Record<string, { x: number; y: number }> {
  const ids = ir.nodes.map((n) => n.id);
  const outs = new Map<string, string[]>();
  const indeg = new Map<string, number>();
  for (const id of ids) {
    outs.set(id, []);
    indeg.set(id, 0);
  }
  for (const e of ir.edges) {
    if (!outs.has(e.source) || !indeg.has(e.target)) continue;
    outs.get(e.source)!.push(e.target);
    indeg.set(e.target, (indeg.get(e.target) || 0) + 1);
  }
  const roots = ids.filter((id) => (indeg.get(id) || 0) === 0);
  const start = roots.length ? roots : ids.slice(0, 1);
  const level = new Map<string, number>();
  const q = [...start];
  for (const r of start) level.set(r, 0);
  while (q.length) {
    const cur = q.shift()!;
    const lv = level.get(cur) || 0;
    for (const nxt of outs.get(cur) || []) {
      if (!level.has(nxt)) {
        level.set(nxt, lv + 1);
        q.push(nxt);
      }
    }
  }
  for (const id of ids) {
    if (!level.has(id)) level.set(id, 0);
  }
  const buckets = new Map<number, string[]>();
  for (const id of ids) {
    const lv = level.get(id) || 0;
    if (!buckets.has(lv)) buckets.set(lv, []);
    buckets.get(lv)!.push(id);
  }
  const pos: Record<string, { x: number; y: number }> = {};
  const td = ir.direction !== "LR";
  for (const [lv, bucket] of [...buckets.entries()].sort((a, b) => a[0] - b[0])) {
    bucket.forEach((id, i) => {
      const offset = (i - (bucket.length - 1) / 2) * (td ? GAP_X : GAP_Y);
      pos[id] = td
        ? { x: offset + 400, y: lv * GAP_Y + 40 }
        : { x: lv * GAP_X + 40, y: offset + 200 };
    });
  }
  return pos;
}
