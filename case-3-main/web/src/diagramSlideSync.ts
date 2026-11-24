/** Utilities to synchronize presentation slide bullets with diagram nodes. */

import type { DiaNode } from "./diagramIr";

function normalizeText(text: string): string {
  return (text || "")
    .toLowerCase()
    .replace(/[«»""''.,:;!?()[\]{}\\/—–-]/g, " ")
    .replace(/\s+/g, " ")
    .trim();
}

function extractKeywords(text: string): string[] {
  const norm = normalizeText(text);
  return norm
    .split(" ")
    .map((w) => w.trim())
    .filter((w) => w.length >= 3);
}

function extractLeadingNumber(text: string): number | null {
  const m = (text || "").trim().match(/^(?:этап|шаг|step)?\s*(\d+)[\.\):\s]/i);
  if (m) {
    const num = parseInt(m[1], 10);
    if (!Number.isNaN(num) && num > 0) return num;
  }
  return null;
}

/**
 * Finds which diagram nodes relate to a given slide bullet.
 */
export function matchBulletToNodeIds(
  bullet: string,
  bulletIndex: number,
  nodes: DiaNode[],
  totalBullets: number = 0,
  bulletNodeMap?: Record<string, string | string[]>,
): Set<string> {
  if (!nodes || nodes.length === 0) return new Set();

  // 0. Explicit persistent mapping priority (survives copy edits)
  if (bulletNodeMap) {
    const key = String(bulletIndex);
    const mapped = bulletNodeMap[key];
    if (mapped) {
      if (Array.isArray(mapped)) {
        const found = mapped.filter((id) => nodes.some((n) => n.id === id));
        if (found.length > 0) return new Set(found);
      } else if (nodes.some((n) => n.id === mapped)) {
        return new Set([mapped]);
      }
    }
  }

  const bulletNorm = normalizeText(bullet);
  const bulletKeywords = extractKeywords(bullet);
  const leadNum = extractLeadingNumber(bullet);

  let bestScore = 0;
  const scores = new Map<string, number>();

  for (let i = 0; i < nodes.length; i++) {
    const node = nodes[i];
    const nodeNorm = normalizeText(node.label || "");
    const nodeKeywords = extractKeywords(node.label || "");
    let score = 0;

    // Direct substring match
    if (nodeNorm.length >= 4 && bulletNorm.includes(nodeNorm)) {
      score += 15;
    } else if (bulletNorm.length >= 4 && nodeNorm.includes(bulletNorm)) {
      score += 10;
    }

    // Significant keyword overlap
    for (const bk of bulletKeywords) {
      for (const nk of nodeKeywords) {
        if (bk === nk) {
          score += 4;
        } else if (
          (bk.length >= 4 && nk.startsWith(bk.slice(0, 4))) ||
          (nk.length >= 4 && bk.startsWith(nk.slice(0, 4)))
        ) {
          score += 2;
        }
      }
    }

    // Step/ordinal number match (e.g. "Этап 1" vs node at index 0)
    if (leadNum !== null && leadNum === i + 1) {
      score += 3;
    }

    scores.set(node.id, score);
    if (score > bestScore) {
      bestScore = score;
    }
  }

  // If we found a confident match (score >= 3)
  if (bestScore >= 3) {
    const matched = new Set<string>();
    for (const [id, score] of scores) {
      if (score >= bestScore - 1) {
        matched.add(id);
      }
    }
    return matched;
  }

  // Positional fallback when structure counts roughly align
  const count = totalBullets || nodes.length;
  if (Math.abs(nodes.length - count) <= 1 && bulletIndex < nodes.length) {
    return new Set([nodes[bulletIndex].id]);
  }

  return new Set();
}

/**
 * Reverse lookup: finds which bullet index corresponds to a clicked or hovered diagram node.
 */
export function matchNodeToBulletIndex(
  nodeId: string,
  nodes: DiaNode[],
  bullets: string[],
  bulletNodeMap?: Record<string, string | string[]>,
): number | null {
  if (!bullets || bullets.length === 0 || !nodeId) return null;

  // 0. Explicit persistent mapping priority
  if (bulletNodeMap) {
    for (const [idxStr, mapped] of Object.entries(bulletNodeMap)) {
      const idx = parseInt(idxStr, 10);
      if (!Number.isNaN(idx) && idx >= 0 && idx < bullets.length) {
        if (Array.isArray(mapped) && mapped.includes(nodeId)) {
          return idx;
        }
        if (mapped === nodeId) {
          return idx;
        }
      }
    }
  }

  // 1. Direct check using matchBulletToNodeIds
  for (let i = 0; i < bullets.length; i++) {
    const matched = matchBulletToNodeIds(bullets[i], i, nodes, bullets.length, bulletNodeMap);
    if (matched.has(nodeId)) {
      return i;
    }
  }

  // 2. Keyword scoring of node against each bullet
  const node = nodes.find((n) => n.id === nodeId);
  if (node) {
    const nodeKeywords = extractKeywords(node.label || "");
    let bestIdx: number | null = null;
    let maxOverlap = 0;

    for (let i = 0; i < bullets.length; i++) {
      const bKeywords = extractKeywords(bullets[i]);
      let count = 0;
      for (const nk of nodeKeywords) {
        if (bKeywords.some((bk) => bk === nk || bk.startsWith(nk.slice(0, 4)))) {
          count++;
        }
      }
      if (count > maxOverlap) {
        maxOverlap = count;
        bestIdx = i;
      }
    }

    if (bestIdx !== null && maxOverlap > 0) {
      return bestIdx;
    }
  }

  // 3. Positional fallback
  const nodeIdx = nodes.findIndex((n) => n.id === nodeId);
  if (nodeIdx >= 0 && nodeIdx < bullets.length) {
    return nodeIdx;
  }

  return null;
}
