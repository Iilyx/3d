/** Live Chart.js — crisp hover preview (G12) + sheet (G9). PDF remains print truth.

 * Root cause of blur/stretch (2026-10-21):
 * 1) Print fragments use fixed canvas + responsive:false; CSS upscale → soft.
 * 2) iframe srcDoc + fractional CSS width + translateZ layer → whole frame soft
 *    (even HTML "45%" looked blurry vs parent page text).
 * Fix: mount Chart.js inline in the parent document (same DPR, no iframe layer),
 * aspect box + ResizeObserver + devicePixelRatio, never CSS-stretch the bitmap.
 */

import { useEffect, useId, useRef } from "react";

type Props = {
  html: string;
  title?: string;
  className?: string;
  showBadge?: boolean;
  compact?: boolean;
};

type ChartStatic = {
  defaults: {
    devicePixelRatio: number;
    animation: boolean | object;
    responsive: boolean;
    maintainAspectRatio: boolean;
    font: { family?: string; size?: number; weight?: string | number };
    color: string;
    plugins: Record<string, unknown>;
    elements: Record<string, unknown>;
    interaction: Record<string, unknown>;
    scale: Record<string, unknown>;
  };
  getChart?: (c: HTMLCanvasElement) => { resize: () => void; update: (m?: string) => void; destroy: () => void } | undefined;
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  new (ctx: HTMLCanvasElement, cfg: any): unknown;
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  [k: string]: any;
};

declare global {
  interface Window {
    Chart?: ChartStatic;
    __LIBER_CHART_LIVE_PATCHED__?: boolean;
  }
}

const LIVE_CSS = `
.live-chart-mount {
  width: 100%;
  margin: 0 auto;
  padding: 12px 14px 14px;
  box-sizing: border-box;
  font-family: "Segoe UI", "DejaVu Sans", sans-serif;
  color: var(--chart-ink, #0F3D3E);
  --kpi-value: var(--chart-accent, #4F6B14);
  --kpi-label: var(--chart-muted, #6A7160);
  --kpi-ink: var(--chart-ink, #2E4208);
  --chart-ink: #2E4208;
  --chart-accent: #4F6B14;
  --chart-muted: #6A7160;
  background: #fff;
  /* Tooltips must not be clipped by parent overflow. */
  overflow: visible;
}
.live-chart-mount .liber-live-box {
  position: relative;
  width: 100%;
  max-width: 100%;
  aspect-ratio: 11 / 5.6;
  margin: 0 auto;
  overflow: visible;
}
.live-chart-mount .liber-live-box.is-hbar { aspect-ratio: 11 / 4.2; }
.live-chart-mount .liber-live-box.is-donut { aspect-ratio: 1 / 1; max-width: min(100%, 360px); }
/* Parent box owns the size; Chart.js sets buffer — keep CSS box = layout box. */
.live-chart-mount .liber-live-box canvas {
  display: block;
  width: 100% !important;
  height: 100% !important;
  max-width: none;
  max-height: none;
}
.live-chart-mount .chart-card { display: flex; flex-direction: column; gap: 14px; width: 100%; }
.live-chart-mount .chart-kpi-header { display: flex; flex-direction: column; gap: 4px; padding: 0 4px 8px; }
.live-chart-mount .chart-kpi-header .eyebrow {
  font-size: 12px; font-weight: 600; letter-spacing: 0.06em; text-transform: uppercase;
  color: var(--chart-muted, #6A7160);
}
.live-chart-mount .chart-kpi-header .big {
  font-size: 34px; font-weight: 700; letter-spacing: -0.03em; line-height: 1.05;
  color: var(--kpi-value, var(--chart-accent, #5A6E28));
}
.live-chart-mount .chart-kpi-header .context {
  font-size: 14px; font-weight: 500; color: var(--kpi-label, var(--chart-muted, #6A7160));
}
.live-chart-mount .donut-layout {
  display: grid;
  grid-template-columns: minmax(160px, 280px) minmax(140px, 1fr);
  gap: 14px 22px;
  align-items: center;
  width: 100%;
}
.live-chart-mount .donut-viz {
  position: relative;
  width: 100%;
  aspect-ratio: 1 / 1;
  max-width: 280px;
  margin: 0;
  /* Canvas stays in-flow — absolute+inset stretched the bitmap and inverted hit-tests. */
}
.live-chart-mount .donut-viz > canvas {
  display: block;
  position: relative;
  z-index: 0;
  width: 100% !important;
  height: 100% !important;
  max-width: none;
  max-height: none;
}
.live-chart-mount .donut-center {
  position: absolute; inset: 0;
  display: flex; flex-direction: column; align-items: center; justify-content: center;
  pointer-events: none; text-align: center; z-index: 1;
}
.live-chart-mount .donut-center .pct {
  font-size: 30px; font-weight: 700; letter-spacing: -0.03em; line-height: 1;
  color: var(--kpi-ink, var(--chart-ink, #2E4208));
}
.live-chart-mount .donut-center .lbl {
  margin-top: 6px; font-size: 12px; font-weight: 600;
  color: var(--kpi-label, var(--chart-muted, #6A7160)); max-width: 120px;
}
.live-chart-mount .valued-legend {
  list-style: none; margin: 0; padding: 2px 0;
  display: flex; flex-direction: column; gap: 12px;
}
.live-chart-mount .valued-legend li,
.live-chart-mount .valued-legend__row {
  display: grid;
  grid-template-columns: 14px minmax(0, 1fr) auto auto;
  gap: 8px 12px; align-items: center;
  font-size: 15px; font-weight: 500; color: var(--chart-ink, #0F3D3E);
}
.live-chart-mount .valued-legend__row:first-child .valued-legend__label,
.live-chart-mount .valued-legend li:first-child .valued-legend__label {
  font-weight: 700; color: var(--chart-ink, #0F3D3E);
}
.live-chart-mount .valued-legend__swatch {
  width: 12px; height: 12px; border-radius: 999px; flex-shrink: 0;
  box-shadow: inset 0 0 0 1px rgba(15, 61, 62, 0.12);
}
.live-chart-mount .valued-legend__label {
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
  color: var(--chart-ink, #0F3D3E); opacity: 0.92;
}
.live-chart-mount .valued-legend__pct {
  font-variant-numeric: tabular-nums; font-weight: 700;
  color: var(--kpi-ink, var(--chart-ink, #2E4208)); min-width: 2.8em; text-align: right;
}
.live-chart-mount .valued-legend__abs {
  font-variant-numeric: tabular-nums; font-weight: 600;
  color: var(--chart-ink, #0F3D3E); opacity: 0.72;
  min-width: 2.6em; text-align: right;
}
.live-chart-mount .kpi {
  display: flex; flex-direction: column; justify-content: center;
  min-height: 180px; text-align: center; gap: 8px; padding: 16px 10px;
}
.live-chart-mount .kpi .value {
  font-size: 52px; font-weight: 700;
  color: var(--kpi-value, var(--chart-accent, #5A6E28));
  letter-spacing: -0.03em; line-height: 1;
}
.live-chart-mount .kpi .label {
  font-size: 15px; color: var(--kpi-label, var(--chart-muted, #3D5C60));
  margin-top: 4px; font-weight: 600;
}
.live-chart-mount .kpi-row {
  display: flex; flex-wrap: wrap; gap: 14px; justify-content: center; align-items: stretch;
}
.live-chart-mount .kpi-row .kpi { min-height: 140px; flex: 1 1 130px; }
@media (max-width: 520px) {
  .live-chart-mount .donut-layout { grid-template-columns: 1fr; }
}
`;

/** Retina: prefer 3× backing store (crisper than bare dpr=2 soft upscale). */
function liveDpr(): number {
  const dpr = typeof window !== "undefined" ? window.devicePixelRatio || 1 : 1;
  if (dpr >= 2) return 3;
  return Math.max(2, Math.ceil(dpr));
}

/** Wrap inline Chart.js script in an IIFE so top-level `const ctx` never collides. */
export function wrapChartScriptIife(code: string): string {
  const body = (code || "").trim();
  if (!body) return "";
  return `(() => {\n${body}\n})();`;
}

function prepareLiveFragment(fragment: string, uid: string): string {
  const low = (fragment || "").toLowerCase();
  let kind: "hbar" | "donut" | "plain" = "plain";
  if (low.includes("indexaxis")) kind = "hbar";
  if (
    low.includes("doughnut") ||
    low.includes("donut-layout") ||
    low.includes("donut-viz")
  ) {
    kind = "donut";
  }
  const boxClass =
    kind === "hbar"
      ? "liber-live-box is-hbar"
      : kind === "donut"
        ? "liber-live-box is-donut"
        : "liber-live-box";

  // Print fragments style `#mount { --chart-* }`; inline host is `.live-chart-mount`.
  let out = (fragment || "").replace(/#mount\b/g, ".live-chart-mount");

  // Print donuts often ship BOTH HTML .donut-center AND a canvas centerText plugin →
  // double soft labels. Keep crisp DOM center; drop the canvas plugin.
  if (kind === "donut" && /donut-center/i.test(out)) {
    out = out.replace(/const\s+centerText\s*=\s*\{[\s\S]*?\};/g, "");
    // Keep surrounding commas intact → avoid `{type:'doughnut'data:` syntax break
    out = out.replace(/,?\s*plugins\s*:\s*\[\s*centerText\s*\]/gi, "");
  }

  // Unique canvas ids — fragments all use c1/c2; multiple LiveCharts on one page
  // would otherwise all bind to the first getElementById('c1').
  const idMap = new Map<string, string>();
  let canvasN = 0;
  out = out.replace(
    /<canvas\b([^>]*)>([\s\S]*?)<\/canvas>/gi,
    (_m, attrs: string, inner: string) => {
      canvasN += 1;
      const oldId = /\bid\s*=\s*(['"])([^'"]+)\1/i.exec(attrs)?.[2];
      const newId = `${uid}-c${canvasN}`;
      if (oldId) idMap.set(oldId, newId);
      let a = String(attrs)
        .replace(/\sid\s*=\s*(['"])[^'"]*\1/gi, "")
        .replace(/\swidth\s*=\s*(['"]?)[^'"\s>]*\1/gi, "")
        .replace(/\sheight\s*=\s*(['"]?)[^'"\s>]*\1/gi, "")
        .replace(/\sstyle\s*=\s*(['"])[\s\S]*?\1/gi, "");
      a = ` id="${newId}"${a}`;
      // Donut: .donut-viz is already the aspect box — wrapping in another
      // absolute .liber-live-box often left Chart at default 300×150.
      if (kind === "donut") {
        return `<canvas${a}>${inner}</canvas>`;
      }
      return `<div class="${boxClass}"><canvas${a}>${inner}</canvas></div>`;
    },
  );
  for (const [oldId, newId] of idMap) {
    out = out.split(`getElementById('${oldId}')`).join(`getElementById('${newId}')`);
    out = out.split(`getElementById("${oldId}")`).join(`getElementById("${newId}")`);
  }
  return out;
}

let chartLoadPromise: Promise<ChartStatic> | null = null;

function ensureChartJs(): Promise<ChartStatic> {
  if (typeof window !== "undefined" && window.Chart) {
    return Promise.resolve(window.Chart);
  }
  if (chartLoadPromise) return chartLoadPromise;
  chartLoadPromise = new Promise((resolve, reject) => {
    const existing = document.querySelector(
      'script[data-liber-chart="1"]',
    ) as HTMLScriptElement | null;
    if (existing) {
      existing.addEventListener("load", () => {
        if (window.Chart) resolve(window.Chart);
        else reject(new Error("Chart.js load failed"));
      });
      existing.addEventListener("error", () => reject(new Error("Chart.js script error")));
      return;
    }
    const s = document.createElement("script");
    s.src = "/vendor/chart.umd.min.js";
    s.async = true;
    s.dataset.liberChart = "1";
    s.onload = () => {
      if (window.Chart) resolve(window.Chart);
      else reject(new Error("Chart.js missing after load"));
    };
    s.onerror = () => reject(new Error("Chart.js network error"));
    document.head.appendChild(s);
  });
  return chartLoadPromise;
}

function patchChartForLive(Chart: ChartStatic): void {
  if (window.__LIBER_CHART_LIVE_PATCHED__) {
    Chart.defaults.devicePixelRatio = liveDpr();
    return;
  }
  const dpr = liveDpr();
  Chart.defaults.devicePixelRatio = dpr;
  Chart.defaults.animation = false;
  Chart.defaults.responsive = true;
  Chart.defaults.maintainAspectRatio = false;
  Chart.defaults.font.family = '"Segoe UI", "DejaVu Sans", sans-serif';
  Chart.defaults.font.size = 12;
  Chart.defaults.font.weight = "500";
  Chart.defaults.color = "#3D5C60";
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const plugins = Chart.defaults.plugins as any;
  if (plugins.legend?.labels) {
    plugins.legend.labels.boxWidth = 12;
    plugins.legend.labels.padding = 12;
    plugins.legend.labels.usePointStyle = true;
  }
  if (plugins.tooltip) {
    plugins.tooltip.enabled = true;
    plugins.tooltip.backgroundColor = "rgba(26,52,48,0.92)";
    plugins.tooltip.titleFont = { weight: "600", size: 12 };
    plugins.tooltip.bodyFont = { size: 12 };
    plugins.tooltip.padding = 10;
    plugins.tooltip.cornerRadius = 8;
  }
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const el = Chart.defaults.elements as any;
  if (el.bar) {
    el.bar.borderRadius = 5;
    el.bar.borderSkipped = false;
  }
  if (el.line) el.line.borderWidth = 2.5;
  if (el.point) {
    el.point.radius = 5;
    el.point.hoverRadius = 8;
    el.point.hitRadius = 12;
  }
  Chart.defaults.interaction = { mode: "nearest", intersect: true };
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const scale = Chart.defaults.scale as any;
  if (scale.grid) {
    scale.grid.color = "rgba(26,74,75,0.08)";
    scale.grid.drawBorder = false;
  }

  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  function forceLiveOptions(cfg: any) {
    if (!cfg || typeof cfg !== "object") return cfg;
    cfg.options = cfg.options || {};
    cfg.options.responsive = true;
    cfg.options.maintainAspectRatio = false;
    cfg.options.animation = false;
    cfg.options.devicePixelRatio = liveDpr();
    const type = String(cfg.type || "").toLowerCase();
    const isDonut = type === "doughnut" || type === "pie";
    const isHbar = cfg.options.indexAxis === "y";
    const isScatter = type === "scatter";
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const datasets: any[] = Array.isArray(cfg.data?.datasets)
      ? cfg.data.datasets
      : [];
    // index+intersect:false maps doughnut arcs wrong (top↔bottom); bars need axis.
    if (isDonut) {
      cfg.options.interaction = { mode: "nearest", intersect: true };
    } else if (isScatter) {
      cfg.options.interaction = { mode: "nearest", intersect: true };
    } else if (isHbar) {
      cfg.options.interaction = { mode: "index", intersect: false, axis: "y" };
    } else {
      cfg.options.interaction = { mode: "index", intersect: false, axis: "x" };
    }
    if (isScatter) {
      cfg.options.elements = cfg.options.elements || {};
      cfg.options.elements.point = {
        ...(cfg.options.elements.point || {}),
        radius: 10,
        hoverRadius: 14,
        hitRadius: 16,
      };
      for (const ds of datasets) {
        const r = Number(ds.pointRadius);
        if (!Number.isFinite(r) || r < 8) ds.pointRadius = 10;
        const hr = Number(ds.pointHoverRadius);
        if (!Number.isFinite(hr) || hr < 11) ds.pointHoverRadius = 14;
        if (ds.borderWidth == null) ds.borderWidth = 2;
      }
    }
    cfg.options.plugins = cfg.options.plugins || {};
    const multiSeries = datasets.length >= 2;
    const hasNamed =
      multiSeries &&
      datasets.some(
        (d: { label?: string }) =>
          typeof d?.label === "string" && d.label.trim().length > 0,
      );
    // Donut uses HTML .valued-legend; keep Chart.js legend off. Else show series names.
    const legendPrev = cfg.options.plugins.legend || {};
    cfg.options.plugins.legend = {
      ...legendPrev,
      display: isDonut ? false : hasNamed || legendPrev.display === true,
      position: legendPrev.position || "bottom",
      labels: {
        ...(typeof legendPrev.labels === "object" ? legendPrev.labels : {}),
        usePointStyle: true,
        boxWidth: 10,
        padding: 14,
      },
    };
    cfg.options.plugins.tooltip = {
      ...(cfg.options.plugins.tooltip || {}),
      enabled: true,
      position: "nearest",
      yAlign: "bottom",
      xAlign: "center",
      caretPadding: 8,
      displayColors: true,
      callbacks: {
        ...(cfg.options.plugins.tooltip?.callbacks || {}),
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        label(ctx: any) {
          const dsLabel = ctx.dataset?.label ? String(ctx.dataset.label) : "";
          const cat = ctx.label != null ? String(ctx.label) : "";
          let raw: number | undefined;
          if (isDonut) {
            raw = typeof ctx.parsed === "number" ? ctx.parsed : Number(ctx.raw);
          } else if (ctx.parsed && typeof ctx.parsed === "object") {
            const p = ctx.parsed as { x?: number; y?: number };
            raw = typeof p.y === "number" ? p.y : p.x;
          } else if (typeof ctx.parsed === "number") {
            raw = ctx.parsed;
          }
          const num =
            raw != null && Number.isFinite(raw)
              ? String(Math.round(raw * 100) / 100)
              : String(ctx.formattedValue ?? "");
          let pct = "";
          if (isDonut && raw != null && ctx.chart?.data?.datasets?.[0]?.data) {
            const data = ctx.chart.data.datasets[0].data as number[];
            const sum = data.reduce((a, b) => a + (Number(b) || 0), 0);
            if (sum > 0) pct = ` (${Math.round((raw / sum) * 100)}%)`;
          }
          const head = dsLabel || cat;
          if (head && cat && dsLabel && cat !== dsLabel) {
            return `${dsLabel} · ${cat}: ${num}${pct}`;
          }
          if (head) return `${head}: ${num}${pct}`;
          return num + pct;
        },
      },
    };
    return cfg;
  }

  const Orig = Chart;
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  function Patched(this: unknown, ctx: HTMLCanvasElement, cfg: any) {
    return new Orig(ctx, forceLiveOptions(cfg));
  }
  Patched.prototype = Orig.prototype;
  Object.keys(Orig).forEach((k) => {
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    (Patched as any)[k] = (Orig as any)[k];
  });
  if (Orig.getChart) {
    Patched.getChart = function (c: HTMLCanvasElement) {
      return Orig.getChart!(c);
    };
  }
  window.Chart = Patched as unknown as ChartStatic;
  window.__LIBER_CHART_LIVE_PATCHED__ = true;
}

function destroyChartsIn(root: HTMLElement): void {
  const Chart = window.Chart;
  if (!Chart?.getChart) return;
  root.querySelectorAll("canvas").forEach((c) => {
    try {
      Chart.getChart!(c as HTMLCanvasElement)?.destroy();
    } catch {
      /* ignore */
    }
  });
}

function resizeChartsIn(root: HTMLElement): void {
  const Chart = window.Chart;
  if (!Chart?.getChart) return;
  root.querySelectorAll("canvas").forEach((c) => {
    const ch = Chart.getChart!(c as HTMLCanvasElement);
    if (!ch) return;
    try {
      ch.resize();
      ch.update("none");
    } catch {
      /* ignore */
    }
  });
}

export function LiveChart({
  html,
  title = "Живой график",
  className = "",
  showBadge = false,
  compact = false,
}: Props) {
  const mountRef = useRef<HTMLDivElement>(null);
  const reactId = useId().replace(/:/g, "");
  const styleId = reactId;
  const canvasUid = `liber${reactId}`;

  useEffect(() => {
    const mount = mountRef.current;
    if (!mount || !html.trim()) return;

    let cancelled = false;
    let ro: ResizeObserver | null = null;
    const timers: number[] = [];

    void (async () => {
      try {
        const Chart = await ensureChartJs();
        if (cancelled || !mountRef.current) return;
        patchChartForLive(Chart);

        destroyChartsIn(mount);
        const prepared = prepareLiveFragment(html, canvasUid);
        mount.innerHTML = prepared;

        const pending = Array.from(mount.querySelectorAll("script"));
        pending.forEach((old) => old.parentNode?.removeChild(old));

        // Layout first (aspect boxes get real size), then new Chart()
        await new Promise<void>((r) =>
          requestAnimationFrame(() => requestAnimationFrame(() => r())),
        );
        if (cancelled || !mountRef.current) return;

        // Pre-size canvases so Chart never boots at default 300×150
        mount.querySelectorAll("canvas").forEach((c) => {
          const el = c as HTMLCanvasElement;
          const box = (el.closest(".liber-live-box, .donut-viz") ||
            el.parentElement) as HTMLElement | null;
          if (!box) return;
          const r = box.getBoundingClientRect();
          if (r.width < 8 || r.height < 8) return;
          el.style.width = `${Math.round(r.width)}px`;
          el.style.height = `${Math.round(r.height)}px`;
        });

        for (const old of pending) {
          const s = document.createElement("script");
          s.text = wrapChartScriptIife(old.textContent || "");
          mount.appendChild(s);
        }

        resizeChartsIn(mount);
        timers.push(
          window.setTimeout(() => resizeChartsIn(mount), 50),
          window.setTimeout(() => resizeChartsIn(mount), 200),
          window.setTimeout(() => resizeChartsIn(mount), 500),
        );

        ro = new ResizeObserver(() => resizeChartsIn(mount));
        ro.observe(mount);
        mount
          .querySelectorAll(".liber-live-box, .donut-viz")
          .forEach((box) => ro!.observe(box));
      } catch (e) {
        if (!cancelled && mountRef.current) {
          mountRef.current.innerHTML = `<p class="live-chart-empty">${
            e instanceof Error ? e.message : "Chart.js error"
          }</p>`;
        }
      }
    })();

    return () => {
      cancelled = true;
      ro?.disconnect();
      timers.forEach((t) => clearTimeout(t));
      if (mountRef.current) destroyChartsIn(mountRef.current);
    };
  }, [html]);

  if (!html.trim()) {
    return (
      <div className={`live-chart is-empty ${className}`.trim()}>
        <p className="live-chart-empty">Нет HTML графика</p>
      </div>
    );
  }

  return (
    <div
      className={`live-chart is-inline${compact ? " is-compact" : ""} ${className}`.trim()}
      title={title}
    >
      <style id={`liber-live-css-${styleId}`}>{LIVE_CSS}</style>
      {showBadge ? (
        <div className="live-chart-badge" aria-hidden>
          <span>Интерактивный график</span>
          <span className="live-chart-badge-sep">·</span>
          <span>точная печатная копия — в PDF</span>
        </div>
      ) : null}
      <div ref={mountRef} className="live-chart-mount" />
    </div>
  );
}
