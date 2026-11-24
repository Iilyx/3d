/** Full-screen Stimulsoft preview. «В данные» in the viewer attaches markdown. */

import { useEffect, useId, useRef, useState } from "react";
import { parseDashboard } from "./domain/dashboardParse";
import {
  captureOriginOk,
  documentsFromService,
  fileFromCapture,
  filesFromCapture,
  type CaptureFile,
} from "./domain/dashboardCapture";
import { useFocusTrap } from "./useFocusTrap";

type Doc = { name: string; markdown: string; warnings?: string[] };

type Dash = { name: string; title: string; preview?: string };

function previewUrl(name: string): string {
  return `/api/dashboard/preview?mrt=${encodeURIComponent(name)}`;
}

type Props = {
  onClose: () => void;
  onShot: (docs: Doc[]) => void;
  /** How many screens from this opening are already in the chat. */
  shotCount?: number;
  /** Captured screen titles so user can inspect/remove inside the modal. */
  shots?: { name: string }[];
  onRemoveShot?: (index: number) => void;
  /** /open after the API POSTed the filter body. The button path leaves this empty. */
  viewerUrl?: string | null;
  /** The chosen /open page, so the card can reopen the same dashboard. */
  onOpened?: (viewer: string, mrt: string) => void;
};

async function parseFiles(files: CaptureFile[]): Promise<Doc[]> {
  const pngFile = files.find((f) => f.ext === "png") ?? null;
  const pdfFiles = files.filter((f) => f.ext === "pdf");
  const restFiles = files.filter((f) => f !== pngFile && !pdfFiles.includes(f));
  const docs: Doc[] = [];
  if (pngFile || pdfFiles.length) {
    const pngBin = pngFile ? fileFromCapture(pngFile) : null;
    const firstPdf = pdfFiles[0] ? fileFromCapture(pdfFiles[0]) : null;
    const parsed = await parseDashboard(pngBin, firstPdf);
    docs.push({
      name: pngFile?.name || pdfFiles[0]!.name,
      markdown: parsed.markdown,
      warnings: parsed.warnings,
    });
    for (const extraPdf of pdfFiles.slice(1)) {
      const bin = fileFromCapture(extraPdf);
      const extraParsed = await parseDashboard(null, bin);
      docs.push({
        name: extraPdf.name,
        markdown: extraParsed.markdown,
        warnings: extraParsed.warnings,
      });
    }
  }
  for (const file of restFiles) {
    const bin = fileFromCapture(file);
    const parsed = await parseDashboard(
      file.ext === "png" ? bin : null,
      file.ext === "pdf" ? bin : null,
    );
    docs.push({
      name: file.name,
      markdown: parsed.markdown,
      warnings: parsed.warnings,
    });
  }
  return docs;
}

export function DashboardPickModal({
  onClose,
  onShot,
  shotCount = 0,
  shots = [],
  onRemoveShot,
  viewerUrl: viewerOverride,
  onOpened,
}: Props) {
  const titleId = useId();
  const dialogRef = useRef<HTMLDivElement>(null);
  const [viewerUrl, setViewerUrl] = useState(viewerOverride || "");
  const [openedUrl, setOpenedUrl] = useState(viewerOverride || "");
  const [list, setList] = useState<Dash[] | null>(null);
  const [listNonce, setListNonce] = useState(0);
  const [opening, setOpening] = useState("");
  const [lit, setLit] = useState("");
  const [phase, setPhase] = useState<"idle" | "shot" | "attach">("idle");
  const [error, setError] = useState("");
  const busy = phase !== "idle" || Boolean(opening);
  const viewing = Boolean(openedUrl);
  useFocusTrap(dialogRef, { active: true });

  useEffect(() => {
    if (!viewerOverride) return;
    setOpenedUrl(viewerOverride);
    setViewerUrl(viewerOverride);
  }, [viewerOverride]);

  useEffect(() => {
    if (openedUrl) return;
    let cancelled = false;
    setError("");
    void fetch("/api/dashboard/dashboards")
      .then(async (res) => {
        const body: { dashboards?: Dash[]; detail?: string } | null = await res
          .json()
          .catch(() => null);
        if (!res.ok) {
          throw new Error(
            body?.detail || `Сервис дашбордов вернул HTTP ${res.status}`,
          );
        }
        return body;
      })
      .then((body) => {
        if (cancelled) return;
        const rows = Array.isArray(body?.dashboards) ? body.dashboards : [];
        setList(
          rows
            .filter(
              (row) => row && typeof row.name === "string" && row.name.trim(),
            )
            .map((row) => ({
              name: row.name.trim(),
              title: (row.title || row.name).trim(),
              preview: typeof row.preview === "string" ? row.preview.trim() : "",
            })),
        );
      })
      .catch((exc: unknown) => {
        if (cancelled) return;
        setList(null);
        setError(
          exc instanceof Error ? exc.message : "Сервис дашбордов не ответил.",
        );
      });
    return () => {
      cancelled = true;
    };
  }, [openedUrl, listNonce]);

  async function choose(name: string) {
    setOpening(name);
    setError("");
    try {
      const res = await fetch("/api/dashboard/open", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ mrt: name }),
      });
      const body: { viewer?: string; detail?: string } | null = await res
        .json()
        .catch(() => null);
      if (!res.ok || !body?.viewer) {
        setError(body?.detail || "Не удалось открыть дашборд.");
        return;
      }
      setOpenedUrl(body.viewer);
      setViewerUrl(body.viewer);
      onOpened?.(body.viewer, name);
    } catch (exc: unknown) {
      setError(exc instanceof Error ? exc.message : "Сервис дашборда недоступен.");
    } finally {
      setOpening("");
    }
  }

  async function takeFromService() {
    setPhase("shot");
    setError("");
    try {
      let activeMrt = "";
      try {
        const parsed = new URL(openedUrl || viewerUrl || "", window.location.origin);
        activeMrt = parsed.searchParams.get("mrt") || "";
      } catch {
        activeMrt = "";
      }
      const res = await fetch("/api/dashboard/service-capture", {
        method: "POST",
        headers: activeMrt ? { "Content-Type": "application/json" } : undefined,
        body: activeMrt ? JSON.stringify({ mrt: activeMrt }) : undefined,
      });
      const body: unknown = await res.json().catch(() => null);
      if (!res.ok) {
        const detail =
          body && typeof body === "object" && typeof (body as { detail?: unknown }).detail === "string"
            ? (body as { detail: string }).detail
            : "Сервис снимка не ответил.";
        setError(detail);
        return;
      }
      const docs = documentsFromService(body);
      if (!docs.length) {
        setError("Сервис не вернул файлы.");
        return;
      }
      setPhase("attach");
      await new Promise((resolve) => setTimeout(resolve, 600));
      onShot(docs);
    } catch (exc: unknown) {
      setError(exc instanceof Error ? exc.message : "Сервис снимка недоступен.");
    } finally {
      setPhase("idle");
    }
  }

  useEffect(() => {
    function onMessage(event: MessageEvent) {
      if (!captureOriginOk(event.origin, viewerUrl)) return;
      const files = filesFromCapture(event.data);
      if (!files.length || busy) return;
      setPhase("attach");
      setError("");
      void parseFiles(files)
        .then((docs) => {
          if (!docs.length) {
            setError("Парсер вернул пустой текст.");
            return;
          }
          onShot(docs);
        })
        .catch((exc: unknown) => {
          setError(exc instanceof Error ? exc.message : "Не удалось разобрать.");
        })
        .finally(() => setPhase("idle"));
    }
    window.addEventListener("message", onMessage);
    return () => window.removeEventListener("message", onMessage);
  }, [busy, onShot, viewerUrl]);

  useEffect(() => {
    function onKey(event: KeyboardEvent) {
      if (event.key === "Escape") onClose();
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  const litRow = (list || []).find((row) => row.name === lit && row.preview);

  if (!viewing) {
    return (
      <div
        ref={dialogRef}
        className="stimul-modal"
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
      >
        <div className="stimul-sheet is-pick">
          <header className="settings-modal-head">
            <div>
              <p className="settings-modal-eyebrow">данные · стимулсофт</p>
              <h2 id={titleId} className="settings-modal-title">
                Какой дашборд
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
          <p className="dash-viewer-note">
            {error
              ? "Не удалось загрузить список дашбордов."
              : list === null
                ? "Загружаю список доступных отчётов…"
                : "Выберите дашборд, чтобы открыть его экран и фильтры."}
          </p>
          {error ? (
            <div className="dash-viewer-error">
              <span>{error}</span>{" "}
              <button
                type="button"
                className="dash-list-retry"
                onClick={() => setListNonce((n) => n + 1)}
              >
                Повторить
              </button>
            </div>
          ) : null}
          <div className="dash-pick-list">
            {(list || []).map((row, index) => (
              <button
                key={row.name}
                type="button"
                className={`dash-pick-item is-sketch-${index % 3}`}
                disabled={busy}
                onMouseEnter={() => {
                  if (row.preview) setLit(row.name);
                }}
                onMouseLeave={() => setLit("")}
                onClick={() => void choose(row.name)}
              >
                <span
                  className={`dash-pick-stage${row.preview ? " has-photo" : ""}`}
                  aria-hidden="true"
                >
                  {row.preview ? (
                    <img
                      className="dash-pick-photo"
                      src={previewUrl(row.name)}
                      alt=""
                    />
                  ) : (
                    <>
                      <span className="dash-pick-kpis">
                        <i />
                        <i />
                        <i />
                      </span>
                      <span className="dash-pick-bars">
                        <i />
                        <i />
                        <i />
                        <i />
                      </span>
                    </>
                  )}
                </span>
                <span className="dash-pick-copy">
                  <span className="dash-pick-kicker">Дашборд</span>
                  <span className="dash-pick-title">{row.title || row.name}</span>
                  {opening === row.name ? (
                    <span className="dash-pick-file">Открываю</span>
                  ) : null}
                </span>
              </button>
            ))}
            {list && !list.length && !error ? (
              <p className="dash-viewer-note">Доступных дашбордов пока нет.</p>
            ) : null}
          </div>
        </div>
        {litRow ? (
          <div className="dash-pick-lightbox" aria-hidden="true">
            <figure className="dash-pick-lightbox-sheet">
              <img src={previewUrl(litRow.name)} alt="" />
              <figcaption>{litRow.title || litRow.name}</figcaption>
            </figure>
          </div>
        ) : null}
      </div>
    );
  }

  return (
    <div
      ref={dialogRef}
      className="stimul-modal"
      role="dialog"
      aria-modal="true"
      aria-labelledby={titleId}
    >
      <div className="stimul-sheet is-viewer">
        <header className="settings-modal-head">
          <div>
            <p className="settings-modal-eyebrow">данные · стимулсофт</p>
            <h2 id={titleId} className="settings-modal-title">
              Выбрать данные
            </h2>
          </div>
          <div className="dash-viewer-actions">
            <button
              type="button"
              className="dash-viewer-back"
              disabled={busy}
              onClick={() => {
                setError("");
                setOpenedUrl("");
                setViewerUrl("");
              }}
            >
              ← Все дашборды
            </button>
            <button
              type="button"
              className="dash-viewer-take"
              onClick={() => void takeFromService()}
              disabled={busy}
            >
              {phase === "shot"
                ? "Снимаю срез…"
                : phase === "attach"
                  ? "Прикрепляю…"
                  : "В данные"}
            </button>
            {shotCount > 0 || shots.length > 0 ? (
              <button
                type="button"
                className="dash-viewer-done"
                disabled={busy}
                onClick={onClose}
              >
                Прикрепить ({shots.length || shotCount})
              </button>
            ) : null}
            <button
              type="button"
              className="settings-modal-x"
              onClick={onClose}
              aria-label="Закрыть"
            >
              ×
            </button>
          </div>
        </header>
        <p className="dash-viewer-note">
          {phase === "shot"
            ? "Снимаю текущий экран и таблицу дашборда. Окно не закроется."
            : phase === "attach"
              ? "Сохраняю срез данных. Окно не закроется."
            : shotCount
              ? `Срезов в буфере: ${shotCount}. Можно выбрать другой фильтр и нажать «В данные» ещё раз, либо нажать «Прикрепить (${shots.length || shotCount})».`
              : "Выберите нужные фильтры на дашборде и нажмите «В данные»."}
        </p>
        {shots.length > 0 ? (
          <div className="dash-viewer-shots" aria-label="Снятые экраны">
            {shots.map((shot, idx) => (
              <span key={`${shot.name}-${idx}`} className="dash-viewer-shot-chip">
                <span>{shot.name}</span>
                {onRemoveShot ? (
                  <button
                    type="button"
                    aria-label={`Убрать экран ${shot.name}`}
                    onClick={() => onRemoveShot(idx)}
                  >
                    ×
                  </button>
                ) : null}
              </span>
            ))}
          </div>
        ) : null}
        {error ? <p className="dash-viewer-error">{error}</p> : null}
        <div className="dash-viewer-frame-wrap">
          <iframe
            className="dash-viewer-frame"
            title="Превью Stimulsoft"
            src={viewerUrl}
          />
          {busy ? (
            <div className="dash-viewer-loader" role="status">
              <span className="dash-viewer-spinner" />
              <p>{phase === "attach" ? "Прикрепляю данные в чат" : "Снимаю скрин"}</p>
            </div>
          ) : null}
        </div>
      </div>
    </div>
  );
}
