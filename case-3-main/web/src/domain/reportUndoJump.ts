/** DOM id of the report block an undo/redo just touched. */

const INDEX_KIND: Record<string, string> = {
  paragraph: "report-para-",
  heading: "rail-h-",
  list: "report-list-",
  table: "report-table-",
};

const FIGURE_KIND = new Set(["chart", "figure", "figure_delete", "diagram"]);

function positiveIndex(raw: string): string | null {
  if (!/^[1-9]\d*$/.test(raw)) return null;
  return raw;
}

export function reportUndoElementId(
  kind: string,
  target: string,
): string | null {
  const k = (kind || "").trim();
  const t = (target || "").trim();
  if (!k) return null;
  if (k === "title") return "report-doc-title";
  if (k === "paragraph_insert") {
    const para = /^p:(\d+)$/.exec(t);
    if (para) {
      const n = positiveIndex(para[1]);
      return n ? `report-para-${n}` : null;
    }
    const head = /^h:(\d+)$/.exec(t);
    if (head) {
      const n = positiveIndex(head[1]);
      return n ? `rail-h-${n}` : null;
    }
    return null;
  }
  const prefix = INDEX_KIND[k];
  if (prefix) {
    const n = positiveIndex(t);
    return n ? `${prefix}${n}` : null;
  }
  if (FIGURE_KIND.has(k) && /^[\w.-]+$/.test(t)) return `report-fig-${t}`;
  return null;
}

/** Scroll the changed block into view after React paints the restored preview. */
export function scrollReportUndo(kind: string, target: string): void {
  const id = reportUndoElementId(kind, target);
  const find = (): HTMLElement | null => {
    if (id) {
      const el = document.getElementById(id);
      if (el) return el;
    }
    if (kind === "batch_recolor") {
      const fig = document.querySelector(".report-fig");
      if (fig instanceof HTMLElement) return fig;
    }
    return null;
  };
  const go = (tries: number) => {
    const el = find();
    if (!el) {
      if (tries > 0) window.setTimeout(() => go(tries - 1), 40);
      return;
    }
    el.scrollIntoView({ block: "center", behavior: "smooth" });
    el.classList.remove("is-undo-flash");
    void el.offsetWidth;
    el.classList.add("is-undo-flash");
    window.setTimeout(() => el.classList.remove("is-undo-flash"), 1400);
  };
  window.setTimeout(() => go(8), 0);
}
