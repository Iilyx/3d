/** Soft premium frame around chart/photo figures in Preview. */

import type { ReactNode } from "react";

type Highlight = {
  label: string;
  value: string;
  pct?: string;
};

type Props = {
  title?: string;
  insight?: string;
  highlights?: Highlight[];
  chartType?: string;
  children: ReactNode;
};

export function ChartCard({
  title,
  insight,
  highlights,
  chartType,
  children,
}: Props) {
  const hasMeta =
    Boolean(title?.trim()) ||
    Boolean(insight?.trim()) ||
    Boolean(highlights?.length);

  return (
    <div
      className={`chart-card-ui${hasMeta ? " has-meta" : ""}`}
      data-chart-type={chartType || undefined}
    >
      {hasMeta ? (
        <header className="chart-card-ui-head">
          {title ? <h4 className="chart-card-ui-title">{title}</h4> : null}
          {insight ? (
            <p className="chart-card-ui-insight">{insight}</p>
          ) : null}
          {highlights && highlights.length > 0 ? (
            <ul className="chart-card-ui-highlights">
              {highlights.map((h, i) => (
                <li key={`${h.label}-${i}`}>
                  <span className="chart-card-ui-hl-label">{h.label}</span>
                  <span className="chart-card-ui-hl-nums">
                    {h.pct ? <strong>{h.pct}</strong> : null}
                    <span>{h.value}</span>
                  </span>
                </li>
              ))}
            </ul>
          ) : null}
        </header>
      ) : null}
      <div className="chart-card-ui-viz">{children}</div>
    </div>
  );
}
