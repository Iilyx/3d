/** Helpers: Mermaid SVG node hit-testing + role highlight. */

/** Mermaid flowchart node group ids look like `flowchart-A-0` or `flowchart-n1-12`. */
export function mermaidNodeIdFromElement(el: Element | null): string | null {
  const g = el?.closest?.("g.node") as SVGGElement | null;
  if (!g) return null;
  const raw = g.id || g.getAttribute("id") || "";
  // Mermaid may prefix: `mmd_xxx-flowchart-A-0` (not always `flowchart-A-0`).
  const m = raw.match(/flowchart-([A-Za-z][\w]*)-/i);
  if (m) return m[1];
  // Fallback: title/text content is unreliable; try data-id
  const dataId = g.getAttribute("data-id");
  if (dataId && /^[A-Za-z][\w]*$/.test(dataId)) return dataId;
  return null;
}

function idKey(id: string): string {
  return id.toLowerCase();
}

export function applyMermaidRoleHighlight(
  svg: SVGSVGElement | null,
  nodeIds: Set<string> | null,
): void {
  if (!svg) return;
  const want =
    nodeIds && nodeIds.size > 0
      ? new Set([...nodeIds].map(idKey))
      : null;
  const nodes = svg.querySelectorAll("g.node");
  nodes.forEach((g) => {
    const el = g as SVGElement;
    const id = mermaidNodeIdFromElement(g);
    el.classList.remove("is-role-hot", "is-role-dim");
    el.style.removeProperty("opacity");
    el.style.removeProperty("filter");
    if (!want) return;
    const hit = Boolean(id && want.has(idKey(id)));
    if (hit) {
      el.classList.add("is-role-hot");
      el.style.opacity = "1";
      el.style.filter =
        "drop-shadow(0 0 6px rgba(107, 143, 118, 0.65))";
    } else {
      el.classList.add("is-role-dim");
      el.style.opacity = "0.22";
      el.style.filter = "grayscale(0.35)";
    }
  });
}
