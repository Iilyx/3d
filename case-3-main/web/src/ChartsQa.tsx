/** Visual QA: all CHART_TYPES via LiveChart (?preview=charts-qa). */

import { useEffect, useState } from "react";
import { LiveChart } from "./LiveChart";

const TYPES = [
  "bar",
  "grouped_bar",
  "stacked_bar",
  "line",
  "horizontal_bar",
  "donut",
  "kpi",
  "area",
  "scatter",
] as const;

type FixtureMap = Partial<Record<(typeof TYPES)[number], string>>;

export function ChartsQa() {
  const [fixtures, setFixtures] = useState<FixtureMap>({});
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    void (async () => {
      try {
        const r = await fetch("/qa-chart-fixtures.json");
        if (!r.ok) throw new Error(`fixtures ${r.status}`);
        setFixtures((await r.json()) as FixtureMap);
      } catch (e) {
        setErr(e instanceof Error ? e.message : "load failed");
      }
    })();
  }, []);

  return (
    <div className="charts-qa" data-testid="charts-qa">
      <header className="charts-qa-head">
        <h1>Liber live charts QA</h1>
        <p>
          Все whitelist-типы · inline Chart.js · DPR≥2 (retina → 3) · PDF — истина
          печати
        </p>
        {err ? <p className="charts-qa-err">{err}</p> : null}
      </header>
      <div className="charts-qa-grid">
        {TYPES.map((t) => {
          const html = fixtures[t];
          return (
            <section key={t} className="charts-qa-card" data-chart-type={t}>
              <h2>{t}</h2>
              {html ? (
                <LiveChart html={html} title={t} compact />
              ) : (
                <p className="charts-qa-miss">нет fixture</p>
              )}
            </section>
          );
        })}
      </div>
    </div>
  );
}
