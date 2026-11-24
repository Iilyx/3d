/** Client-side SVG → PNG download for Liber diagrams. */

export function slugDiagramFilename(
  title: string,
  id: string,
  ext: "png" | "svg" = "png",
): string {
  const base = (title || id || "diagram")
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9а-яё_-]+/gi, "-")
    .replace(/-+/g, "-")
    .replace(/^-|-$/g, "")
    .slice(0, 48);
  const safe = base || id || "diagram";
  const suffix = `.${ext}`;
  return safe.endsWith(suffix) ? safe : `${safe}${suffix}`;
}

function intrinsicSize(svgEl: SVGSVGElement): { w: number; h: number } {
  const vb = svgEl.viewBox?.baseVal;
  if (vb && vb.width > 0 && vb.height > 0) {
    return { w: Math.ceil(vb.width), h: Math.ceil(vb.height) };
  }
  const attrW = Number(svgEl.getAttribute("width"));
  const attrH = Number(svgEl.getAttribute("height"));
  if (attrW > 0 && attrH > 0) {
    return { w: Math.ceil(attrW), h: Math.ceil(attrH) };
  }
  try {
    const b = svgEl.getBBox();
    if (b.width > 0 && b.height > 0) {
      return { w: Math.ceil(b.width + Math.abs(b.x)), h: Math.ceil(b.height + Math.abs(b.y)) };
    }
  } catch {
    /* not in DOM yet */
  }
  const rect = svgEl.getBoundingClientRect();
  return {
    w: Math.max(1, Math.ceil(rect.width || 800)),
    h: Math.max(1, Math.ceil(rect.height || 600)),
  };
}

/** Prepare a standalone SVG clone that rasterizes reliably (fonts + xmlns). */
function prepareClone(svgEl: SVGSVGElement): { xml: string; w: number; h: number } {
  const clone = svgEl.cloneNode(true) as SVGSVGElement;
  clone.setAttribute("xmlns", "http://www.w3.org/2000/svg");
  clone.setAttribute("xmlns:xlink", "http://www.w3.org/1999/xlink");
  const { w, h } = intrinsicSize(svgEl);
  const pad = 24;
  const outW = w + pad * 2;
  const outH = h + pad * 2;
  clone.setAttribute("width", String(outW));
  clone.setAttribute("height", String(outH));
  const vb = svgEl.viewBox?.baseVal;
  if (vb && vb.width > 0 && vb.height > 0) {
    clone.setAttribute(
      "viewBox",
      `${vb.x - pad} ${vb.y - pad} ${vb.width + pad * 2} ${vb.height + pad * 2}`,
    );
  } else {
    clone.setAttribute("viewBox", `${-pad} ${-pad} ${outW} ${outH}`);
  }
  // Opaque background so transparent PNG doesn't look "broken"
  const bg = document.createElementNS("http://www.w3.org/2000/svg", "rect");
  bg.setAttribute("x", String(-pad * 2));
  bg.setAttribute("y", String(-pad * 2));
  bg.setAttribute("width", String(outW + pad * 4));
  bg.setAttribute("height", String(outH + pad * 4));
  bg.setAttribute("fill", "#ffffff");
  clone.insertBefore(bg, clone.firstChild);
  const xml = new XMLSerializer().serializeToString(clone);
  return { xml, w: outW, h: outH };
}

function loadImageFromSvgXml(xml: string): Promise<HTMLImageElement> {
  // data: URI is more reliable than blob: for Mermaid SVG (+ foreignObject).
  const url = `data:image/svg+xml;charset=utf-8,${encodeURIComponent(xml)}`;
  return new Promise((resolve, reject) => {
    const img = new Image();
    img.onload = () => resolve(img);
    img.onerror = () => reject(new Error("svg image load failed"));
    img.src = url;
  });
}

/** Download the live Mermaid SVG (vector) — no raster. */
export async function downloadDiagramSvg(
  svgEl: SVGSVGElement,
  filename: string,
): Promise<void> {
  const { xml } = prepareClone(svgEl);
  const a = document.createElement("a");
  const blob = new Blob([xml], { type: "image/svg+xml;charset=utf-8" });
  const href = URL.createObjectURL(blob);
  a.href = href;
  const name = filename.endsWith(".svg") ? filename : `${filename}.svg`;
  a.download = name;
  a.rel = "noopener";
  document.body.appendChild(a);
  a.click();
  a.remove();
  window.setTimeout(() => URL.revokeObjectURL(href), 2500);
}

export async function downloadDiagramPng(
  svgEl: SVGSVGElement,
  filename: string,
): Promise<void> {
  const { xml, w, h } = prepareClone(svgEl);
  const maxEdge = 2800;
  const scale = Math.min(2.25, maxEdge / Math.max(w, h));
  const outW = Math.max(1, Math.round(w * scale));
  const outH = Math.max(1, Math.round(h * scale));

  let img: HTMLImageElement;
  try {
    img = await loadImageFromSvgXml(xml);
  } catch {
    // Fallback: blob URL (some WebViews choke on huge data URIs)
    const blob = new Blob([xml], { type: "image/svg+xml;charset=utf-8" });
    const blobUrl = URL.createObjectURL(blob);
    try {
      img = await new Promise<HTMLImageElement>((resolve, reject) => {
        const i = new Image();
        i.onload = () => resolve(i);
        i.onerror = () => reject(new Error("Не удалось растеризовать SVG"));
        i.src = blobUrl;
      });
    } finally {
      URL.revokeObjectURL(blobUrl);
    }
  }

  const canvas = document.createElement("canvas");
  canvas.width = outW;
  canvas.height = outH;
  const ctx = canvas.getContext("2d");
  if (!ctx) throw new Error("canvas unsupported");
  ctx.fillStyle = "#ffffff";
  ctx.fillRect(0, 0, outW, outH);
  ctx.drawImage(img, 0, 0, outW, outH);

  const png = await new Promise<Blob | null>((resolve) =>
    canvas.toBlob((b) => resolve(b), "image/png"),
  );
  if (!png) throw new Error("png encode failed");

  const a = document.createElement("a");
  const href = URL.createObjectURL(png);
  a.href = href;
  const name = filename.endsWith(".png") ? filename : `${filename}.png`;
  a.download = name;
  a.rel = "noopener";
  document.body.appendChild(a);
  a.click();
  a.remove();
  // Revoke after the click has a chance to start the download.
  window.setTimeout(() => URL.revokeObjectURL(href), 2500);
}
