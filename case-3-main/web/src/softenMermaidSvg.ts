/** Soften Mermaid flowchart SVG toward Liber visual-editor look. */

const EDGE_SELECTORS = [
  "g.edgePaths path",
  "path.flowchart-link",
  ".edgePath path",
  "g.edgePath path",
].join(", ");

/** Corner radius for a flowchart node box (editor uses ~10–14px). */
export function softRxForBox(w: number, h: number): number {
  if (!(w > 8 && h > 8)) return 0;
  return Math.round(Math.min(14, Math.max(8, Math.min(w, h) * 0.28)) * 10) / 10;
}

/**
 * Round rect nodes + soft edge strokes (Mermaid defaults are sharp).
 * Safe to call repeatedly; skips diamonds (polygon) and tiny rects.
 */
export function softenMermaidSvg(svg: SVGSVGElement): void {
  svg.querySelectorAll("g.node rect").forEach((node) => {
    const r = node as SVGRectElement;
    let w = 0;
    let h = 0;
    try {
      w = r.width.baseVal.value;
      h = r.height.baseVal.value;
    } catch {
      w = Number(r.getAttribute("width") || 0);
      h = Number(r.getAttribute("height") || 0);
    }
    const rx = softRxForBox(w, h);
    if (rx <= 0) return;
    r.setAttribute("rx", String(rx));
    r.setAttribute("ry", String(rx));
  });

  svg.querySelectorAll(EDGE_SELECTORS).forEach((el) => {
    const p = el as SVGPathElement;
    p.setAttribute("stroke-linecap", "round");
    p.setAttribute("stroke-linejoin", "round");
    const sw = p.getAttribute("stroke-width");
    if (!sw || Number(sw) < 1.4) {
      p.setAttribute("stroke-width", "1.65");
    }
  });

  svg.querySelectorAll("marker path").forEach((el) => {
    (el as SVGElement).setAttribute("stroke-linejoin", "round");
  });
}
