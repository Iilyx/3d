/** G12: fetch chart HTML and render live Chart.js with hover (PNG/PDF remain print truth). */

import { useEffect, useState } from "react";
import { LiveChart } from "./LiveChart";

type Props = {
  runId: string;
  chartId: string;
  caption?: string;
  /** Static PNG fallback while loading / on error. */
  fallbackUrl?: string;
  /** Cache-bust from preview URL (?v=) — refetch HTML after Apply. */
  version?: string | number | null;
  /** G9 draft HTML while edit sheet is open (replaces fetched HTML in-place). */
  htmlOverride?: string | null;
  onJumpToPdf?: () => void;
  disabled?: boolean;
};

function bustFromUrl(url?: string): string {
  if (!url) return "";
  try {
    const u = new URL(url, window.location.origin);
    return u.searchParams.get("v") || "";
  } catch {
    const m = /[?&]v=([^&]+)/.exec(url);
    return m?.[1] || "";
  }
}

export function ChartLivePane({
  runId,
  chartId,
  caption,
  fallbackUrl,
  version,
  htmlOverride = null,
  onJumpToPdf,
  disabled,
}: Props) {
  const [html, setHtml] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const rev = version ?? bustFromUrl(fallbackUrl);
  const shown = (htmlOverride && htmlOverride.trim()) || html;

  useEffect(() => {
    let cancelled = false;
    setHtml(null);
    setErr(null);
    void (async () => {
      try {
        const r = await fetch(
          `/api/runs/${encodeURIComponent(runId)}/charts/${encodeURIComponent(chartId)}`,
        );
        if (!r.ok) throw new Error(`chart ${r.status}`);
        const data = (await r.json()) as { html?: string; type?: string };
        if (cancelled) return;
        if (!data.html) throw new Error("empty html");
        setHtml(data.html);
      } catch (e) {
        if (!cancelled) {
          setErr(e instanceof Error ? e.message : "load failed");
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [runId, chartId, rev]);

  if (shown) {
    return (
      <div className="chart-live-pane">
        <LiveChart
          html={shown}
          title={caption || chartId}
          showBadge={false}
        />
        {htmlOverride?.trim() ? (
          <div className="chart-live-chrome">
            <span className="live-chart-draft" aria-hidden>
              черновик до сохранения
            </span>
          </div>
        ) : null}
      </div>
    );
  }

  if (fallbackUrl) {
    return (
      <button
        type="button"
        className="report-fig-link"
        onClick={() => onJumpToPdf?.()}
        aria-label={caption ? `Открыть ${caption} в PDF` : "Открыть в PDF"}
        disabled={disabled}
        title={err ? `PNG · ${err}` : "PNG · переход в PDF"}
      >
        <img src={fallbackUrl} alt={caption || chartId} loading="lazy" />
      </button>
    );
  }

  return (
    <div className="report-fig-missing">
      {chartId} — {err || "загрузка…"}
    </div>
  );
}
