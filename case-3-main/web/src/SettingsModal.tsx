/** Liber Atelier — report limits + desk health (chart type/style live in edit sheet). */

import { useEffect, useId, useRef } from "react";
import { FALLBACK_PALETTES } from "./domain/liberConstants";
import { useFocusTrap } from "./useFocusTrap";

export type DeskProbeSnapshot = {
  id: string;
  label: string;
  status: string;
  hint?: string | null;
};

export type HealthSnapshot = {
  docker_ok: boolean;
  playwright_ok: boolean;
  vision_configured: boolean;
  vision_ok?: boolean;
  image_api_configured?: boolean;
  kandinsky_configured?: boolean;
  image_api_ok?: boolean;
  image_api_error?: string | null;
  docker_error?: string | null;
  soffice_ok?: boolean;
  soffice_hint?: string | null;
  probes?: DeskProbeSnapshot[];
};

type Props = {
  open: boolean;
  onClose: () => void;
  maxCharts: number;
  onMaxCharts: (n: number) => void;
  maxImages: number;
  onMaxImages: (n: number) => void;
  maxDiagrams: number;
  onMaxDiagrams: (n: number) => void;
  /** Hard ceiling from API ``defaults.max_diagrams_cap`` (CASE3_MAX_DIAGRAMS). */
  maxDiagramsCap?: number;
  targetSlides: number;
  onTargetSlides: (n: number) => void;
  forbidCharts: boolean;
  onForbidCharts: (v: boolean) => void;
  forbidImages: boolean;
  onForbidImages: (v: boolean) => void;
  /** From `/api/health` chart_palettes. Falls back to the offline catalog. */
  palettes?: Array<{ id: string; label: string; swatches: string[] }>;
  chartPalette?: string;
  onChartPalette?: (p: string) => void;
  dryRun: boolean;
  onDryRun: (v: boolean) => void;
  health: HealthSnapshot | null;
  paradeHint: string;
};

export function SettingsModal({
  open,
  onClose,
  maxCharts,
  onMaxCharts,
  maxImages,
  onMaxImages,
  maxDiagrams,
  onMaxDiagrams,
  maxDiagramsCap = 5,
  targetSlides,
  onTargetSlides,
  forbidCharts,
  onForbidCharts,
  forbidImages,
  onForbidImages,
  palettes,
  chartPalette = "atelier",
  onChartPalette,
  dryRun,
  onDryRun,
  health,
  paradeHint,
}: Props) {
  const titleId = useId();
  const dialogRef = useRef<HTMLDivElement>(null);
  useFocusTrap(dialogRef, { active: open });

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key !== "Escape") return;
      onClose();
    };
    window.addEventListener("keydown", onKey);
    const prev = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      window.removeEventListener("keydown", onKey);
      document.body.style.overflow = prev;
    };
  }, [open, onClose]);

  if (!open) return null;

  return (
    <div
      ref={dialogRef}
      className="settings-modal"
      role="dialog"
      aria-modal="true"
      aria-labelledby={titleId}
      onMouseDown={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div className="settings-modal-sheet">
        <header className="settings-modal-head">
          <div>
            <p className="settings-modal-eyebrow">Настройки</p>
            <h2 id={titleId} className="settings-modal-title">
              Как собрать отчёт
            </h2>
          </div>
          <button
            type="button"
            className="settings-modal-x"
            onClick={onClose}
            aria-label="Закрыть"
          >
            ×
          </button>
        </header>

        <div className="settings-modal-body">
          <section className="settings-block" aria-labelledby="set-limits">
            <h3 className="settings-block-title" id="set-limits">
              Лимиты
            </h3>
            <div className="row settings-limits-row">
              <div>
                <label className="field" htmlFor="set-max-c">
                  Графиков ≤
                </label>
                <input
                  id="set-max-c"
                  type="number"
                  min={0}
                  max={8}
                  value={maxCharts}
                  disabled={forbidCharts}
                  onChange={(e) => onMaxCharts(Number(e.target.value))}
                />
              </div>
              <div>
                <label className="field" htmlFor="set-max-i">
                  Картинок ≤
                </label>
                <input
                  id="set-max-i"
                  type="number"
                  min={0}
                  max={8}
                  value={maxImages}
                  disabled={forbidImages}
                  onChange={(e) => onMaxImages(Number(e.target.value))}
                />
              </div>
              <div>
                <label className="field" htmlFor="set-max-d">
                  Схем ≤
                </label>
                <input
                  id="set-max-d"
                  type="number"
                  min={0}
                  max={maxDiagramsCap}
                  value={maxDiagrams}
                  onChange={(e) => onMaxDiagrams(Number(e.target.value))}
                />
              </div>
            </div>
            <div className="row settings-limits-row">
              <div>
                <label className="field" htmlFor="set-slides">
                  Слайдов в презентации
                </label>
                <input
                  id="set-slides"
                  type="number"
                  min={6}
                  max={24}
                  value={targetSlides}
                  onChange={(e) => onTargetSlides(Number(e.target.value))}
                />
              </div>
            </div>
            <p className="hint">
              Желаемая длина 6–24. Если в тексте мало фактов, презентация будет короче — цифры не выдумываются. Шаблон повторяет свои раскладки, чтобы длинный документ поместился.
            </p>
            <label className="check">
              <input
                type="checkbox"
                checked={forbidCharts}
                onChange={(e) => onForbidCharts(e.target.checked)}
              />
              Без графиков
            </label>
            <label className="check">
              <input
                type="checkbox"
                checked={forbidImages}
                onChange={(e) => onForbidImages(e.target.checked)}
              />
              Без генерации фото
            </label>
            <label className="check">
              <input
                type="checkbox"
                checked={dryRun}
                onChange={(e) => onDryRun(e.target.checked)}
              />
              Тестовый прогон (без ИИ)
            </label>
          </section>

          <section className="settings-block" aria-labelledby="set-palette">
            <h3 className="settings-block-title" id="set-palette">
              Палитра графиков по умолчанию
            </h3>
            <div className="settings-palette-grid">
              {(palettes?.length ? palettes : FALLBACK_PALETTES)
                .filter((pal) => pal.id !== "auto")
                .map((pal) => {
                const selected = (chartPalette || "atelier") === pal.id;
                return (
                  <button
                    key={pal.id}
                    type="button"
                    className={`settings-palette-chip${selected ? " is-selected" : ""}`}
                    onClick={() => onChartPalette?.(pal.id)}
                    aria-pressed={selected}
                  >
                    <span className="settings-palette-swatches">
                      {pal.swatches.map((color, idx) => (
                        <span
                          key={idx}
                          className="settings-palette-dot"
                          style={{ backgroundColor: color }}
                        />
                      ))}
                    </span>
                    <span className="settings-palette-label">{pal.label}</span>
                  </button>
                );
              })}
            </div>
            <p className="hint">
              Применяется к графикам в новых отчётах. В готовом отчёте палитру можно изменить для каждого графика отдельно.
            </p>
          </section>

          <section
            className="settings-block settings-health"
            aria-labelledby="set-health"
          >
            <h3 className="settings-block-title" id="set-health">
              Состояние сервисов
            </h3>
            {!health && <p className="hint">Проверка сервисов…</p>}
            {health && (
              <ul className="desk-health-list">
                {(
                  health.probes || [
                    {
                      id: "vision",
                      label: "Языковая модель",
                      status: health.vision_ok
                        ? "green"
                        : health.vision_configured
                          ? "amber"
                          : "red",
                      hint: health.vision_configured
                        ? null
                        : "Сервис модели не настроен",
                    },
                    {
                      id: "image",
                      label: "Генерация фото",
                      status: health.image_api_ok
                        ? "green"
                        : "amber",
                      hint: health.image_api_ok ? null : "Сервис изображений не подключён",
                    },
                    {
                      id: "docker",
                      label: "Сборка PDF",
                      status: health.docker_ok ? "green" : "red",
                      hint: health.docker_ok ? null : "Модуль печати PDF недоступен",
                    },
                    {
                      id: "soffice",
                      label: "Конвертация офисных файлов",
                      status: health.soffice_ok ? "green" : "amber",
                      hint: health.soffice_ok ? null : "Офисный конвертер недоступен",
                    },
                    {
                      id: "playwright",
                      label: "Отрисовка графиков и слайдов",
                      status: health.playwright_ok ? "green" : "red",
                      hint: health.playwright_ok ? null : "Компонент отрисовки недоступен",
                    },
                  ]
                ).map((p) => {
                  const friendlyLabel: Record<string, string> = {
                    vision: "Языковая модель",
                    image: "Генерация фото",
                    docker: "Сборка PDF",
                    soffice: "Конвертация офисных файлов",
                    playwright: "Отрисовка графиков и слайдов",
                  };
                  const friendlyHint: Record<string, string> = {
                    vision: "Сервис языковой модели недоступен или не настроен",
                    image: "Иллюстрации не подключены — отчёты и слайды собираются без них",
                    docker: "Модуль печати PDF недоступен",
                    soffice: "Офисный конвертер недоступен — слайды собираются как изображения",
                    playwright: "Компонент отрисовки графиков недоступен",
                  };
                  const label = friendlyLabel[p.id] || p.label;
                  const hint =
                    p.status === "green"
                      ? null
                      : friendlyHint[p.id] || p.hint;
                  return (
                    <li key={p.id} className="desk-health-row">
                      <span
                        className={`desk-health-dot is-${p.status}`}
                        aria-hidden
                      />
                      <span className="desk-health-label">{label}</span>
                      <span className={`desk-health-val is-${p.status}`}>
                        {p.status === "green"
                          ? "готово"
                          : p.status === "amber"
                            ? "внимание"
                            : "нет"}
                      </span>
                      {hint ? (
                        <span className="desk-health-hint">{hint}</span>
                      ) : null}
                    </li>
                  );
                })}
              </ul>
            )}
            <p className="health-foot">{paradeHint}</p>
          </section>
        </div>

        <footer className="settings-modal-foot">
          <button
            type="button"
            className="settings-modal-done"
            onClick={onClose}
          >
            Готово
          </button>
        </footer>
      </div>
    </div>
  );
}
