/** Liber desk: regenerate, img2img-edit, or upload one photo. */

import { useEffect, useRef, useState, type ChangeEvent, type DragEvent } from "react";
import { useConfirm } from "./ConfirmModal";
import { useFocusTrap } from "./useFocusTrap";

export type ImageEditMode = "generate" | "edit" | "upload";

export type ImageEditRequest = {
  figureId: string;
  mode: "generate" | "edit";
  prompt: string;
  caption: string;
};

type Props = {
  open: boolean;
  /** When false, skip focus trap (multi-open edit desk). */
  trapFocus?: boolean;
  figureId: string;
  caption?: string;
  previewUrl?: string;
  busy?: boolean;
  error?: string | null;
  onCancel: () => void;
  onSubmit: (req: ImageEditRequest) => void;
  onUpload?: (file: File, caption?: string) => void;
  onDelete?: () => void;
};

export function ImageEditModal({
  open,
  trapFocus = true,
  figureId,
  caption: initialCaption,
  previewUrl,
  busy,
  error,
  onCancel,
  onSubmit,
  onUpload,
  onDelete,
}: Props) {
  const confirm = useConfirm();
  const [mode, setMode] = useState<ImageEditMode>("generate");
  const [prompt, setPrompt] = useState("");
  const [caption, setCaption] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [filePreview, setFilePreview] = useState<string | null>(null);
  const [dragOver, setDragOver] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const sheetRef = useRef<HTMLDivElement>(null);
  useFocusTrap(sheetRef, { active: open && trapFocus });

  useEffect(() => {
    if (!open) return;
    setMode(previewUrl ? "edit" : "generate");
    setPrompt("");
    setCaption((initialCaption || "").trim());
    setFile(null);
    setFilePreview(null);
  }, [open, figureId, initialCaption, previewUrl]);

  useEffect(() => {
    return () => {
      if (filePreview) URL.revokeObjectURL(filePreview);
    };
  }, [filePreview]);

  if (!open) return null;

  function onSelectFile(selected: File | null) {
    if (!selected) return;
    if (!selected.type.startsWith("image/")) return;
    if (filePreview) URL.revokeObjectURL(filePreview);
    setFile(selected);
    setFilePreview(URL.createObjectURL(selected));
  }

  function handleFileInput(e: ChangeEvent<HTMLInputElement>) {
    const f = e.target.files?.[0] || null;
    onSelectFile(f);
  }

  function handleDrop(e: DragEvent) {
    e.preventDefault();
    setDragOver(false);
    const f = e.dataTransfer.files?.[0] || null;
    onSelectFile(f);
  }

  function apply() {
    if (busy) return;
    const cap = caption.trim();

    if (mode === "upload") {
      if (file && onUpload) {
        onUpload(file, cap);
      }
      return;
    }

    const p = prompt.trim();
    if (!p) return;
    onSubmit({ figureId, mode, prompt: p, caption: cap });
  }

  const canApply =
    !busy &&
    ((mode === "upload" && Boolean(file)) ||
      ((mode === "generate" || mode === "edit") && Boolean(prompt.trim())));

  return (
    <div
      ref={sheetRef}
      className="chart-edit-sheet img-edit-sheet"
      role="region"
      aria-label="Изменить фото"
    >
      <header className="chart-edit-head">
        <div>
          <p className="chart-edit-eyebrow">живая правка · фото</p>
          <h3 className="chart-edit-title">{(initialCaption || "").trim() || "Иллюстрация"}</h3>
        </div>
        <button
          type="button"
          className="chart-edit-x"
          onClick={onCancel}
          disabled={busy}
          aria-label="Закрыть"
        >
          ×
        </button>
      </header>

      {previewUrl && mode !== "upload" ? (
        <div className="img-edit-preview-current">
          <img
            src={previewUrl}
            alt="Текущее фото"
            className="img-edit-thumb"
            loading="lazy"
          />
          <div className="img-edit-preview-meta">
            <span className="img-edit-preview-label">Текущее изображение</span>
          </div>
        </div>
      ) : null}

      <section className="chart-edit-block">
        <label className="field">Режим замены</label>
        <div className="chips img-edit-modes" role="group" aria-label="Режим">
          <button
            type="button"
            className={`chip${mode === "generate" ? " on" : ""}`}
            disabled={busy}
            onClick={() => setMode("generate")}
          >
            Новая генерация
          </button>
          <button
            type="button"
            className={`chip${mode === "edit" ? " on" : ""}`}
            disabled={busy}
            onClick={() => setMode("edit")}
          >
            Изменить детали
          </button>
          {onUpload ? (
            <button
              type="button"
              className={`chip${mode === "upload" ? " on" : ""}`}
              disabled={busy}
              onClick={() => setMode("upload")}
            >
              Загрузить файл
            </button>
          ) : null}
        </div>
        <p className="chart-edit-foot-hint" style={{ marginTop: "0.45rem" }}>
          {mode === "generate" && "Сервис создаст новое изображение по вашему описанию"}
          {mode === "edit" && "Сервис изменит детали поверх текущего изображения"}
          {mode === "upload" && "Загрузить своё изображение с компьютера (.png, .jpg, .webp)"}
        </p>
      </section>

      {mode === "upload" ? (
        <section className="chart-edit-block">
          <label className="field">Файл изображения</label>
          <div
            className={`img-edit-dropzone${dragOver ? " is-drag" : ""}${file ? " has-file" : ""}`}
            onDragOver={(e) => {
              e.preventDefault();
              setDragOver(true);
            }}
            onDragLeave={() => setDragOver(false)}
            onDrop={handleDrop}
            onClick={() => fileInputRef.current?.click()}
          >
            <input
              ref={fileInputRef}
              type="file"
              accept="image/png,image/jpeg,image/webp,image/avif"
              style={{ display: "none" }}
              onChange={handleFileInput}
              disabled={busy}
            />
            {filePreview ? (
              <div className="img-edit-file-selected">
                <img
                  src={filePreview}
                  alt="Превью"
                  className="img-edit-file-thumb"
                  loading="lazy"
                />
                <div className="img-edit-file-meta">
                  <span className="img-edit-file-name">{file?.name}</span>
                  <span className="img-edit-file-size">
                    {Math.round((file?.size || 0) / 1024)} КБ
                  </span>
                  <span className="img-edit-file-change">Нажмите для выбора другого файла</span>
                </div>
              </div>
            ) : (
              <div className="img-edit-drop-prompt">
                <span className="img-edit-drop-icon" aria-hidden>📁</span>
                <span className="img-edit-drop-text">Перетащите сюда фото или нажмите для выбора</span>
                <span className="img-edit-drop-sub">PNG, JPEG, WebP</span>
              </div>
            )}
          </div>
        </section>
      ) : (
        <section className="chart-edit-block">
          <label className="field" htmlFor={`img-prompt-${figureId}`}>
            {mode === "generate" ? "Описание нового фото" : "Что изменить на фото"}
          </label>
          <textarea
            id={`img-prompt-${figureId}`}
            rows={3}
            className="img-edit-textarea"
            placeholder={
              mode === "generate"
                ? "современный офисный холл, дневной свет, без текста на кадре…"
                : "сделай свет теплее, добавь графики на экраны, убери лишнее…"
            }
            value={prompt}
            disabled={busy}
            onChange={(e) => setPrompt(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && (e.metaKey || e.ctrlKey) && canApply) {
                e.preventDefault();
                apply();
              }
            }}
          />
        </section>
      )}

      <section className="chart-edit-block">
        <label className="field" htmlFor={`img-cap-${figureId}`}>
          Подпись к фото
        </label>
        <input
          id={`img-cap-${figureId}`}
          type="text"
          placeholder="краткая подпись на русском…"
          value={caption}
          disabled={busy}
          onChange={(e) => setCaption(e.target.value)}
        />
      </section>

      {error && <p className="err">{error}</p>}

      <footer className="chart-edit-foot">
        <p className="chart-edit-foot-hint">
          {mode === "upload"
            ? "Файл сохранится на слайд и обновит презентацию и превью."
            : "Изображение будет обновлено и сохранено в документе."}
        </p>
        <div className="chart-edit-actions">
          {onDelete && (
            <button
              type="button"
              className="chart-edit-delete"
              disabled={busy}
              onClick={async () => {
                const ok = await confirm({
                  title: "Удалить фото?",
                  eyebrow: "отчёт · иллюстрация",
                  message: `Удалить иллюстрацию «${(initialCaption || "").trim() || "Иллюстрация"}»? Она будет удалена из документа.`,
                  confirmLabel: "Удалить фото",
                  danger: true,
                });
                if (ok) {
                  onDelete();
                }
              }}
              style={{
                background: "transparent",
                border: "1px solid color-mix(in srgb, #c92a2a 40%, transparent)",
                color: "#c92a2a",
                borderRadius: "8px",
                padding: "0.4rem 0.75rem",
                cursor: "pointer",
                marginRight: "auto",
                fontSize: "0.82rem",
              }}
            >
              Удалить фото
            </button>
          )}
          <button
            type="button"
            className="chart-edit-apply"
            disabled={!canApply}
            onClick={apply}
          >
            {busy
              ? "Обновляю…"
              : mode === "upload"
                ? "Загрузить фото"
                : mode === "generate"
                  ? "Сгенерировать"
                  : "Применить правки"}
          </button>
          <button
            type="button"
            className="chart-edit-cancel"
            disabled={busy}
            onClick={onCancel}
          >
            Отмена
          </button>
        </div>
      </footer>
    </div>
  );
}
