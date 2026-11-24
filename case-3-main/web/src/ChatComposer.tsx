/** Liber bottom composer: attach · textarea · send; deck style via DeckStyleSheet. */

import type { RefObject } from "react";
import { useEffect, useRef } from "react";
import { ComposerPhotoChips } from "./ComposerPhotoChips";
import { ContextPlaque } from "./ContextPlaque";
import type { DeckStyle, DeckThemePackInfo } from "./deckStyle";
import { DeckTemplateGallery } from "./DeckTemplateGallery";
import { ModeStarterGrid } from "./ModeStarterGrid";
import {
  IconDiagram,
  IconPalette,
  IconPaperclip,
  IconReport,
  IconSend,
  IconSlides,
  IconStop,
} from "./icons";
import { LIBER_MODE_PILLS, type LiberWorkMode } from "./domain/liberModes";
import { isDashboardSource } from "./domain/dashboardCapture";
import { dashboardStarterChips } from "./domain/dashboardTables";
import type { SourceDraft } from "./domain/liberTypes";
import { takeInputFiles } from "./domain/takeInputFiles";

type Props = {
  busy: boolean;
  /** Stop pressed — waiting for server cancelled. */
  stopping?: boolean;
  canSend: boolean;
  /** Stop pipeline / slides while busy (UI free + server cancel). */
  onStop?: () => void;
  chat: string;
  attachPhotos: File[];
  onPreviewPhoto?: (photo: { url: string; name: string }) => void;
  plaques: { title: string; subtitle: string; fileName?: string }[];
  sourceDraft: SourceDraft | null;
  /** Latest dashboard markdown in the chat session (even after the first message sent). */
  activeDashboardSource?: string;
  file: File | null;
  chatRef: RefObject<HTMLTextAreaElement | null>;
  fileRef: RefObject<HTMLInputElement | null>;
  photoRef: RefObject<HTMLInputElement | null>;
  workMode: LiberWorkMode;
  onWorkMode: (mode: LiberWorkMode) => void;
  /** Mode pills — empty home only (hide once chat has messages). */
  showModes: boolean;
  /** Documents, last section, and turn count for this chat. */
  memoryLine?: string;
  /** Empty chat + presentation — show template gallery. */
  showPackPresets: boolean;
  /** Empty presentation home only — palette / style sheet. */
  showDeckStyleBtn?: boolean;
  deckStyle: DeckStyle;
  deckPacks?: DeckThemePackInfo[];
  /** Apply pack + structure and fill composer with starter prompt (Julius). */
  onUseDeckTemplate?: (
    next: DeckStyle,
    meta: { title: string; arc: string; starterPrompt: string },
  ) => void;
  /** Transient status after template apply. */
  deckApplyHint?: string | null;
  onDismissDeckApplyHint?: () => void;
  /** Open DeckStyleSheet (sole style surface). */
  onOpenDeckStyle: () => void;
  deckStyleOpen?: boolean;
  onChatChange: (v: string) => void;
  onPasteCapture: (pasted: string) => boolean;
  onSend: () => void;
  onIngestFiles: (list: FileList | File[]) => void;
  onRemovePhoto: (index: number) => void;
  onOpenPlaque: (index: number) => void;
  onDismissPlaque: (index: number) => void;
  /** Fill composer from quiet starter card (report/diagram). */
  onPickStarter?: (prompt: string) => void;
  /** Open the Stimulsoft preview and attach its markdown. */
  onOpenDashboard?: () => void;
};

export function ChatComposer({
  busy,
  stopping = false,
  canSend,
  onStop,
  chat,
  attachPhotos,
  onPreviewPhoto,
  plaques,
  sourceDraft,
  activeDashboardSource = "",
  file,
  chatRef,
  fileRef,
  photoRef,
  workMode,
  onWorkMode,
  showModes,
  memoryLine = "",
  showPackPresets,
  showDeckStyleBtn = false,
  deckStyle,
  deckPacks,
  onUseDeckTemplate,
  deckApplyHint = null,
  onDismissDeckApplyHint,
  onOpenDeckStyle,
  deckStyleOpen = false,
  onChatChange,
  onPasteCapture,
  onSend,
  onIngestFiles,
  onRemovePhoto,
  onOpenPlaque,
  onDismissPlaque,
  onPickStarter,
  onOpenDashboard,
}: Props) {
  const galleryRef = useRef<HTMLDivElement>(null);
  const placeholder =
    workMode === "diagram"
      ? "Опишите процесс — или просто спросите"
      : workMode === "presentation"
        ? "Материал для презентации — или вопрос по тексту"
        : workMode === "report"
          ? "Материал для отчёта — или вопрос по тексту"
        : sourceDraft || file
          ? "Спросите по этому тексту или попросите отчёт, схему, презентацию"
          : "Напишите вопрос или попросите отчёт, схему, презентацию";

  useEffect(() => {
    if (!showPackPresets) return;
    const t = window.setTimeout(() => {
      galleryRef.current?.scrollIntoView({
        behavior: "smooth",
        block: "nearest",
      });
    }, 80);
    return () => window.clearTimeout(t);
  }, [showPackPresets]);

  /** Stable stage width: empty home (any/no pill) + never shrink mid-chat */
  const isEmptyStage = Boolean(showModes);
  const isDeckHome = Boolean(showPackPresets);
  return (
    <div
      className={`composer-wrap is-stage-wide${isEmptyStage ? " is-empty-stage" : ""}${isDeckHome ? " is-deck-home" : ""}`}
    >
      {/* Same width column as .composer — plaque/Working can't drift left of the sheet */}
      <div className="composer-stack">
        {attachPhotos.length > 0 && (
          <div className="composer-attach-row">
            <ComposerPhotoChips
              files={attachPhotos}
              busy={busy}
              onRemove={onRemovePhoto}
              onPreview={onPreviewPhoto}
            />
          </div>
        )}
        {plaques.length ? (
          <div className="composer-plaques" aria-label="Прикреплённые документы">
            {plaques.map((plaque, index) => (
              <ContextPlaque
                key={`${plaque.fileName || plaque.title}-${index}`}
                title={plaque.title}
                subtitle={plaque.subtitle}
                fileName={plaque.fileName}
                disabled={busy}
                onOpen={() => onOpenPlaque(index)}
                onDismiss={() => onDismissPlaque(index)}
              />
            ))}
          </div>
        ) : null}
        {(() => {
          const dashText = isDashboardSource(sourceDraft?.text || "")
            ? sourceDraft?.text || ""
            : isDashboardSource(activeDashboardSource)
              ? activeDashboardSource
              : "";
          if (!dashText || busy) return null;
          const chips = dashboardStarterChips(dashText);
          return (
            <div className="composer-dash-chips" aria-label="Быстрые запросы по дашборду">
              {chips.map((chip) => (
                <button
                  key={chip.label}
                  type="button"
                  className="composer-dash-chip"
                  onClick={() => onPickStarter?.(chip.prompt)}
                >
                  {chip.label}
                </button>
              ))}
            </div>
          );
        })()}

        {deckApplyHint ? (
          <div className="composer-deck-hint" role="status">
            <span>{deckApplyHint}</span>
            {onDismissDeckApplyHint ? (
              <button
                type="button"
                className="composer-deck-hint-x"
                aria-label="Скрыть"
                onClick={onDismissDeckApplyHint}
              >
                ×
              </button>
            ) : null}
          </div>
        ) : null}

        {memoryLine ? (
          <p className="chat-memory" role="status">
            {memoryLine}
          </p>
        ) : null}

        <div className="composer">
          <input
            ref={fileRef}
            className="composer-file-input"
            type="file"
            accept=".txt,.md,.pdf,.docx,.doc,.docm,.rtf,text/plain,text/markdown,application/pdf,image/png,image/jpeg,.png,.jpg,.jpeg"
            multiple
            onChange={(e) => {
              const files = takeInputFiles(e.target);
              if (files.length) onIngestFiles(files);
            }}
          />
          <input
            ref={photoRef}
            type="file"
            accept="image/*"
            multiple
            hidden
          />
          <textarea
            ref={chatRef}
            className="composer-input"
            rows={2}
            placeholder={placeholder}
            value={chat}
            disabled={busy}
            onChange={(e) => onChatChange(e.target.value)}
            onPaste={(e) => {
              const files = e.clipboardData.files;
              if (files && files.length > 0) {
                const hasMediaOrDoc = Array.from(files).some(
                  (f) =>
                    /^image\//.test(f.type) ||
                    /\.(txt|md|pdf|docx|docm|doc|rtf|png|jpe?g)$/i.test(
                      f.name,
                    ) ||
                    f.type === "text/plain" ||
                    f.type === "text/markdown" ||
                    f.type === "application/pdf",
                );
                if (hasMediaOrDoc) {
                  e.preventDefault();
                  onIngestFiles(files);
                  return;
                }
              }
              const pasted = e.clipboardData.getData("text/plain");
              if (onPasteCapture(pasted)) {
                e.preventDefault();
              }
            }}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                onSend();
              }
            }}
          />
          <div className="composer-inner-bar">
            <button
              type="button"
              className="composer-attach"
              disabled={busy}
              title="Прикрепить PDF/DOCX/TXT/MD или фото"
              aria-label="Прикрепить файл"
              onClick={() => fileRef.current?.click()}
            >
              <IconPaperclip size={18} />
            </button>
            {onOpenDashboard ? (
              <button
                type="button"
                className="composer-data"
                disabled={busy}
                title="Открыть дашборд и забрать текущий экран"
                onClick={onOpenDashboard}
              >
                Выбрать данные
              </button>
            ) : null}
            {showDeckStyleBtn ? (
              <button
                type="button"
                className={`composer-palette-btn${deckStyleOpen ? " is-on" : ""}`}
                disabled={busy}
                title="Стиль презентации"
                aria-label="Стиль презентации"
                aria-pressed={deckStyleOpen}
                onClick={onOpenDeckStyle}
              >
                <IconPalette size={18} />
              </button>
            ) : null}
            <span className="composer-inner-spacer" aria-hidden />
            {busy && onStop ? (
              <button
                className={`send is-stop${stopping ? " is-stopping" : ""}`}
                type="button"
                onClick={onStop}
                disabled={stopping}
                aria-label={stopping ? "Останавливаю" : "Остановить"}
                title={stopping ? "Останавливаю…" : "Остановить"}
              >
                <IconStop size={20} />
              </button>
            ) : (
              <button
                className="send"
                type="button"
                disabled={!canSend}
                onClick={onSend}
                aria-label={workMode ? "Собрать" : "Отправить"}
                title={workMode ? "Собрать" : "Отправить"}
              >
                <IconSend size={16} />
              </button>
            )}
          </div>
        </div>

        <div
          className={`chat-bias${showModes ? "" : " is-compact"}`}
          role="group"
          aria-label="Режим ответа"
        >
          <button
            type="button"
            className={workMode === null ? "is-on" : ""}
            disabled={busy}
            title="Свободный диалог по данным и автовыбор графика/отчёта"
            aria-pressed={workMode === null}
            onClick={() => onWorkMode(null)}
          >
            <span>Авто</span>
          </button>
          {LIBER_MODE_PILLS.map((p) => {
            const on = workMode === p.id;
            const Icon =
              p.id === "diagram"
                ? IconDiagram
                : p.id === "presentation"
                  ? IconSlides
                  : IconReport;
            return (
              <button
                key={p.id}
                type="button"
                className={on ? "is-on" : ""}
                disabled={busy}
                title={p.hint}
                aria-pressed={on}
                onClick={() => onWorkMode(on ? null : p.id)}
              >
                <Icon size={15} />
                <span>{p.label}</span>
              </button>
            );
          })}
        </div>
      </div>

      {showModes && onPickStarter && workMode ? (
        <ModeStarterGrid
          workMode={workMode}
          busy={busy}
          onPick={onPickStarter}
        />
      ) : null}

      {showPackPresets && onUseDeckTemplate ? (
        <div ref={galleryRef} className="composer-deck-gallery-anchor">
          <DeckTemplateGallery
            deckStyle={deckStyle}
            deckPacks={deckPacks}
            busy={busy}
            onApply={onUseDeckTemplate}
          />
        </div>
      ) : null}
    </div>
  );
}
