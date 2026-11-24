/** Quiet system-prompt cards under sheet composer (all Liber modes). */

import { startersForMode } from "./modeStarters";
import type { LiberWorkMode } from "./domain/liberModes";

type Props = {
  workMode: LiberWorkMode;
  busy?: boolean;
  onPick: (prompt: string) => void;
};

export function ModeStarterGrid({ workMode, busy = false, onPick }: Props) {
  const items = startersForMode(workMode);
  if (!items.length) return null;

  const heading =
    workMode === "diagram"
      ? "Идеи для схемы"
      : workMode === "presentation"
        ? "Идеи для презентации"
        : "Идеи для отчёта";

  return (
    <div className="mode-starter-grid" aria-label={heading}>
      <div className="mode-starter-grid-head">
        <h3>{heading}</h3>
      </div>
      <ul className="mode-starter-list">
        {items.map((s) => (
          <li key={s.id}>
            <button
              type="button"
              className="mode-starter-card"
              disabled={busy}
              onClick={() => onPick(s.prompt)}
            >
              <span className="mode-starter-title">{s.title}</span>
              <span className="mode-starter-hint">{s.blurb}</span>
            </button>
          </li>
        ))}
      </ul>
    </div>
  );
}
