/** Liber chat transcript — Julius column DNA (user panel + document bot). */

import { useEffect, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { ArtifactCard } from "./ArtifactCard";
import { DashboardChatCard } from "./DashboardChatCard";
import { shotsSource } from "./domain/dashboardCapture";
import { dashboardStarterChips } from "./domain/dashboardTables";
import { ContextPlaque } from "./ContextPlaque";
import { EmptyState } from "./EmptyState";
import { IconCopy, IconLiberMark } from "./icons";
import { LONG_TEXT_CHARS } from "./domain/liberConstants";
import type { LiberWorkMode } from "./domain/liberModes";
import type { CraftFilmFrame } from "./domain/craftSteps";
import type { Msg, RunResult, SourceAttachment, UserPhotoThumb } from "./domain/liberTypes";
import { reportThumb, reportTitle } from "./domain/runHelpers";
import { MsgMarkdown } from "./lightMd";
import { ThinkingFold } from "./ThinkingFold";

function ChatTurnNote({
  msg,
  onNewChat,
}: {
  msg: Msg;
  onNewChat?: (kind: "empty" | "documents") => void;
}) {
  if (msg.role !== "bot") return null;
  const notice = (msg.result?.chat_notice || "").trim();
  if (!notice && !(msg.offerNewChat && onNewChat)) return null;
  return (
    <>
      {notice ? <p className="chat-notice">{notice}</p> : null}
      {msg.offerNewChat && onNewChat ? (
        <div className="chat-next-row">
          <button type="button" className="chat-next" onClick={() => onNewChat("empty")}>
            Пустой
          </button>
          <button
            type="button"
            className="chat-next is-quiet"
            onClick={() => onNewChat("documents")}
          >
            С этими документами
          </button>
        </div>
      ) : null}
    </>
  );
}

type Props = {
  msgs: Msg[];
  reduceMotion: boolean | null;
  hasStoredReport: boolean;
  /** Julius-style session rename — chat column only (not sidebar). */
  sessionTitle?: string | null;
  thinkingLabel?: string;
  workMode?: LiberWorkMode;
  downloadsPulseMsgId: string | null;
  messagesRef: React.RefObject<HTMLDivElement | null>;
  bottomRef: React.RefObject<HTMLDivElement | null>;
  onRestore: () => void;
  onOpenSource: (draft: SourceAttachment) => void;
  onOpenIntent: (text: string) => void;
  onOpenReport: (msgId: string, result: RunResult) => void;
  onOpenDiagram: (msgId: string, result: RunResult, diagramId: string) => void;
  onOpenPresentation: (msgId: string, result: RunResult) => void;
  onOpenDeckSlides: (msgId: string, result: RunResult) => void;
  onOpenFilm?: (msgId: string, frame: CraftFilmFrame) => void;
  onOpenPhoto?: (photo: UserPhotoThumb) => void;
  /** Continue failed pipeline from failed_stage (same run_id). */
  onResumeRun?: (msgId: string, runId: string) => void;
  /** Starts the next chat. Documents can come along; the old transcript does not. */
  onNewChat?: (kind: "empty" | "documents") => void;
  /** Message whose deck file lags the screen. Its PPTX/PDF stay closed. */
  deckDownloadsBlockedMsgId?: string | null;
  /** Finished report card → POST /slides for this run. */
  onMakePresentation?: (msgId: string, result: RunResult) => void;
  /** Open the saved dashboard card again. */
  onOpenDashboardCard?: (msgId: string) => void;
  /** Full-screen table of the shots already on the card. */
  onReadDashboard?: (card: import("./domain/dashboardCapture").DashboardCard) => void;
  onOpenDashboard?: () => void;
  onPickFile?: () => void;
  onPickStarter?: (prompt: string) => void;
  onRefineVisual?: (preview: { id: string; kind: string; url: string }) => void;
};

export function ChatMessages({
  msgs,
  reduceMotion,
  hasStoredReport,
  sessionTitle = null,
  workMode = null,
  downloadsPulseMsgId,
  messagesRef,
  bottomRef,
  onRestore,
  onOpenSource,
  onOpenIntent,
  onOpenReport,
  onOpenDiagram,
  onOpenPresentation,
  onOpenDeckSlides,
  onOpenFilm,
  onOpenPhoto,
  onResumeRun,
  onNewChat,
  deckDownloadsBlockedMsgId = null,
  onMakePresentation,
  onOpenDashboardCard,
  onReadDashboard,
  onOpenDashboard,
  onPickFile,
  onPickStarter,
  onRefineVisual,
}: Props) {
  const showSessionHead = Boolean(sessionTitle && msgs.length > 0);
  const [openChart, setOpenChart] = useState<{ url: string; title: string } | null>(null);
  useEffect(() => {
    if (!openChart) return;
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") setOpenChart(null);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [openChart]);
  return (
    <>
    <div className="messages" ref={messagesRef}>
      {showSessionHead ? (
        <header className="chat-session-head">
          <h1 className="chat-session-title" title={sessionTitle || undefined}>
            {sessionTitle}
          </h1>
        </header>
      ) : null}
      <AnimatePresence initial={false}>
        {msgs.length === 0 &&
          !/preview=(artifact|deck|deck-busy|flow)/.test(window.location.search) && (
            <EmptyState
              hasStoredReport={hasStoredReport}
              onRestore={onRestore}
              workMode={workMode}
              onOpenDashboard={onOpenDashboard}
              onPickFile={onPickFile}
            />
          )}
        {msgs.map((m, mi) => {
          const hasArtifact =
            m.role === "bot" &&
            Boolean(
              m.result?.preview?.blocks?.length ||
                m.result?.downloads?.pdf ||
                m.result?.downloads?.pptx ||
                m.result?.downloads?.deck_pdf ||
                (m.result?.diagrams && m.result.diagrams.length > 0),
            );
          const slidesLive =
            m.role === "bot" &&
            (Boolean(m.pending && m.pendingStage?.startsWith("slides_")) ||
              m.result?.slides_status === "running" ||
              m.result?.slides_status === "queued");
          const userLong =
            m.role === "user" &&
            !m.attachment &&
            m.text.length > LONG_TEXT_CHARS;
          const userCollapseIntent =
            m.role === "user" && m.text.length > 140 && !m.attachment;
          return (
            <motion.div
              key={m.id}
              className={`msg ${m.role}${hasArtifact ? " has-artifact" : ""}`}
              initial={reduceMotion ? false : { opacity: 0, y: 12 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{
                duration: 0.35,
                delay: Math.min(mi * 0.03, 0.18),
                ease: [0.22, 1, 0.36, 1],
              }}
            >
              {m.role === "user" ? (
                <>
                  {m.photos?.length ? (
                    <div className="msg-photos" aria-label="Прикреплённые фото">
                      {m.photos.map((photo, pi) => (
                        <button
                          key={`${photo.url}-${pi}`}
                          type="button"
                          className="msg-photo-btn"
                          onClick={() => onOpenPhoto?.(photo)}
                          title={photo.name ? `Открыть ${photo.name}` : "Открыть фото"}
                          aria-label={photo.name ? `Открыть фото ${photo.name}` : "Открыть фото"}
                        >
                          <img
                            src={photo.url}
                            alt={photo.name || "Фото"}
                          />
                        </button>
                      ))}
                    </div>
                  ) : null}
                  {(() => {
                    const userDocs = m.attachments?.length
                      ? m.attachments
                      : m.attachment
                        ? [m.attachment]
                        : [];
                    if (!userDocs.length) return null;
                    return (
                      <div className="msg-attach-row" aria-label="Прикреплённые документы">
                        {userDocs.map((doc, di) => (
                          <ContextPlaque
                            key={`${doc.fileName || doc.title}-${di}`}
                            title={doc.title}
                            subtitle={
                              doc.viewMode === "document"
                                ? "Документ · открыть"
                                : `${doc.text.length.toLocaleString("ru-RU")} символов`
                            }
                            fileName={doc.fileName}
                            onOpen={() => onOpenSource(doc)}
                          />
                        ))}
                      </div>
                    );
                  })()}
                  {userLong ? (
                    <button
                      type="button"
                      className="msg-body msg-plaque-trigger"
                      onClick={() => onOpenIntent(m.text)}
                    >
                      Запрос · {m.text.length} символов — открыть
                    </button>
                  ) : userCollapseIntent ? (
                    <details className="msg-intent-fold">
                      <summary className="msg-intent-summary">
                        <span className="msg-intent-label">Запрос</span>
                        <span className="msg-intent-preview">
                          {m.text.slice(0, 72).trim()}
                          {m.text.length > 72 ? "…" : ""}
                        </span>
                      </summary>
                      <div className="msg-body msg-pre">{m.text}</div>
                    </details>
                  ) : (
                    <div className="msg-body msg-pre">{m.text}</div>
                  )}
                </>
              ) : m.role === "bot" && hasArtifact && m.result ? (
                <div className="msg-row">
                  <span className="msg-avatar">
                    <IconLiberMark size={28} />
                  </span>
                  <div className="msg-bot-stack">
                    {(m.lead || "").trim() ? (
                      <MsgMarkdown text={m.lead || ""} />
                    ) : null}
                    {m.thinking?.length ||
                    m.craftFilm?.length ||
                    m.craftSubsteps?.length ||
                    m.craftRecap ||
                    m.errorHint ? (
                      <ThinkingFold
                        lines={m.thinking || []}
                        live={slidesLive}
                        stage={m.pendingStage || m.result?.slides_stage}
                        stageLines={m.stageLines}
                        thinkingMode={m.thinkingMode || "report"}
                        reduceMotion={reduceMotion}
                        craftSubsteps={m.craftSubsteps}
                        craftSkipped={m.craftSkipped}
                        craftFilm={m.craftFilm}
                        craftRecap={m.craftRecap}
                        onOpenFilm={
                          onOpenFilm
                            ? (frame) => onOpenFilm(m.id, frame)
                            : undefined
                        }
                        etaSec={m.etaSec}
                        craftFrozen={m.craftFrozen}
                        errorHint={m.errorHint}
                        elapsedSec={
                          slidesLive && m.thinkingStartedAt
                            ? Math.max(
                                0,
                                Math.round(
                                  (Date.now() - m.thinkingStartedAt) / 1000,
                                ),
                              )
                            : m.thinkingElapsedSec
                        }
                      />
                    ) : null}
                    {(m.lead || "").trim() &&
                    (m.lead || "").trim() !== (m.text || "").trim() ? null : (
                      <MsgMarkdown text={m.text || "Отчёт готов"} />
                    )}
                    <ArtifactCard
                      title={reportTitle(m.result)}
                      thumbUrl={reportThumb(m.result)}
                      pdfUrl={m.result.downloads?.pdf}
                      downloads={m.result.downloads}
                      pulse={downloadsPulseMsgId === m.id}
                      updated={downloadsPulseMsgId === m.id}
                      diagrams={m.result.diagrams}
                      slidesStatus={m.result.slides_status}
                      slidesStage={m.result.slides_stage}
                      slidePngs={m.result.slide_pngs}
                      deck={m.result.deck}
                      runId={m.result.run_id}
                      outputMode={m.result.output_mode}
                      deckDownloadsBlocked={m.id === deckDownloadsBlockedMsgId}
                      onView={() => {
                        const r = m.result!;
                        const diagramOnly =
                          r.output_mode === "diagram" ||
                          (!r.downloads?.pdf && Boolean(r.diagrams?.length));
                        if (diagramOnly && r.diagrams?.[0]) {
                          onOpenDiagram(m.id, r, r.diagrams[0].id);
                        } else if (r.output_mode === "presentation") {
                          onOpenPresentation(m.id, r);
                        } else {
                          onOpenReport(m.id, r);
                        }
                      }}
                      onOpenDiagram={
                        m.result.output_mode === "presentation"
                          ? undefined
                          : (id) => onOpenDiagram(m.id, m.result!, id)
                      }
                      onOpenPresentation={
                        m.result.output_mode === "presentation" ||
                        m.result.slides_status === "ok"
                          ? () => onOpenPresentation(m.id, m.result!)
                          : undefined
                      }
                      onOpenDeckSlides={
                        m.result.output_mode === "presentation" ||
                        m.result.slides_status === "ok"
                          ? () => onOpenDeckSlides(m.id, m.result!)
                          : undefined
                      }
                      onMakePresentation={
                        onMakePresentation
                          ? () => onMakePresentation(m.id, m.result!)
                          : undefined
                      }
                    />
                    {(m.lead || "").trim() &&
                    (m.text || "").trim() &&
                    (m.lead || "").trim() !== (m.text || "").trim() ? (
                      <MsgMarkdown text={m.text} />
                    ) : null}
                    <ChatTurnNote msg={m} onNewChat={onNewChat} />
                    {(() => {
                      const displayWarns = (m.result.warnings || []).filter(
                        (w) =>
                          !/charts? (?:failed|skipped)|фото пропущены|Image API|Часть медиа|skipped/i.test(
                            w
                          )
                      );
                      return displayWarns.length ? (
                        <div className="warns">
                          {displayWarns.join(" · ")}
                        </div>
                      ) : null;
                    })()}
                    <div className="msg-actions">
                      <button
                        type="button"
                        className="msg-action"
                        title="Копировать"
                        aria-label="Копировать текст"
                        onClick={() => {
                          void navigator.clipboard?.writeText(
                            m.text || "Отчёт готов",
                          );
                        }}
                      >
                        <IconCopy size={14} />
                      </button>
                    </div>
                  </div>
                </div>
              ) : m.role === "bot" && m.pending ? (
                <div className="msg-row">
                  <span className="msg-avatar">
                    <IconLiberMark size={28} />
                  </span>
                  <div className="msg-bot-stack">
                    {(m.lead || "").trim() ? (
                      <MsgMarkdown
                        text={m.lead || ""}
                        streaming={!m.text.trim() && m.streamingSummary}
                      />
                    ) : !m.text.trim() ? (
                      <p className="agent-wait">{m.waitLabel || "Отвечаю…"}</p>
                    ) : null}
                    <ThinkingFold
                      lines={m.thinking || []}
                      live
                      stage={m.pendingStage}
                      stageLines={m.stageLines}
                      thinkingMode={m.thinkingMode || "report"}
                      reduceMotion={reduceMotion}
                      craftSubsteps={m.craftSubsteps}
                      craftSkipped={m.craftSkipped}
                      craftFilm={m.craftFilm}
                      craftRecap={m.craftRecap}
                      onOpenFilm={
                        onOpenFilm
                          ? (frame) => onOpenFilm(m.id, frame)
                          : undefined
                      }
                      etaSec={m.etaSec}
                      craftFrozen={m.craftFrozen}
                      errorHint={m.errorHint}
                      elapsedSec={
                        m.thinkingStartedAt
                          ? Math.max(
                              0,
                              Math.round(
                                (Date.now() - m.thinkingStartedAt) / 1000,
                              ),
                            )
                          : undefined
                      }
                    />
                    {m.text.trim() &&
                    m.text.trim() !== (m.lead || "").trim() ? (
                      <div className="msg-stream-wrap">
                        <MsgMarkdown
                          text={m.text}
                          streaming={Boolean(
                            m.streamingSummary && m.streamTyping !== false,
                          )}
                        />
                        {m.streamingSummary && m.streamTyping === false ? (
                          <div
                            className="msg-visual-wait"
                            role="status"
                            aria-live="polite"
                          >
                            <span
                              className="msg-visual-spinner"
                              aria-hidden="true"
                            />
                            <span>
                              {m.pendingDetail ||
                                (m.pendingStage === "charts"
                                  ? "Строю визуализацию…"
                                  : "Готовлю ответ…")}
                            </span>
                          </div>
                        ) : null}
                      </div>
                    ) : null}
                  </div>
                </div>
              ) : (
                <div className="msg-row">
                  <span className="msg-avatar">
                    <IconLiberMark size={28} />
                  </span>
                  <div className="msg-bot-stack">
                    {m.role === "bot" &&
                    (m.thinking?.length ||
                      m.craftFilm?.length ||
                      m.craftSubsteps?.length ||
                      m.craftRecap ||
                      m.errorHint) ? (
                      <ThinkingFold
                        lines={m.thinking || []}
                        live={false}
                        stage={m.pendingStage}
                        stageLines={m.stageLines}
                        thinkingMode={m.thinkingMode || "report"}
                        reduceMotion={reduceMotion}
                        craftSubsteps={m.craftSubsteps}
                        craftSkipped={m.craftSkipped}
                        craftFilm={m.craftFilm}
                        craftRecap={m.craftRecap}
                        onOpenFilm={
                          onOpenFilm
                            ? (frame) => onOpenFilm(m.id, frame)
                            : undefined
                        }
                        etaSec={m.etaSec}
                        craftFrozen={m.craftFrozen}
                        errorHint={m.errorHint}
                        elapsedSec={m.thinkingElapsedSec}
                      />
                    ) : null}
                    {m.role === "bot" && !m.error ? (
                      <>
                        {(m.lead || "").trim() ? (
                          <MsgMarkdown text={m.lead || ""} />
                        ) : null}
                        {(m.text || "").trim() &&
                        (m.text || "").trim() !== (m.lead || "").trim() ? (
                          <MsgMarkdown text={m.text} />
                        ) : !(m.lead || "").trim() ? (
                          <MsgMarkdown text={m.text} />
                        ) : null}
                        {m.dashboard && onOpenDashboardCard ? (
                          <>
                            <DashboardChatCard
                              card={m.dashboard}
                              onOpen={() => onOpenDashboardCard(m.id)}
                              onRead={
                                m.dashboard.shots.length && onReadDashboard
                                  ? () => onReadDashboard(m.dashboard!)
                                  : undefined
                              }
                            />
                            {m.dashboard.shots.length > 0 && onPickStarter ? (
                              <div
                                className="composer-dash-chips msg-dash-chips"
                                aria-label="Быстрые запросы по дашборду"
                              >
                                {dashboardStarterChips(
                                  shotsSource(m.dashboard.shots),
                                  m.dashboard.shots.length,
                                ).map((chip) => (
                                  <button
                                    key={chip.label}
                                    type="button"
                                    className="composer-dash-chip"
                                    onClick={() => onPickStarter(chip.prompt)}
                                  >
                                    {chip.label}
                                  </button>
                                ))}
                              </div>
                            ) : null}
                          </>
                        ) : null}
                        <ChatTurnNote msg={m} onNewChat={onNewChat} />
                        {m.result &&
                          !(
                            m.result.downloads?.pdf || m.result.downloads?.docx
                          ) &&
                          (m.result.previews || []).some(
                            (p) =>
                              p.kind === "chart" ||
                              p.kind === "diagram" ||
                              p.id.startsWith("cht_") ||
                              p.id.startsWith("dia_"),
                          ) && (
                            <div className="msg-inline-charts">
                              {(m.result.previews || [])
                                .filter(
                                  (p) =>
                                    p.kind === "chart" ||
                                    p.kind === "diagram" ||
                                    p.id.startsWith("cht_") ||
                                    p.id.startsWith("dia_"),
                                )
                                .map((p) => (
                                  <figure key={p.id} className="msg-inline-chart-card">
                                    <button
                                      type="button"
                                      className="msg-inline-chart-open"
                                      onClick={() =>
                                        setOpenChart({
                                          url: p.url,
                                          title:
                                            p.kind === "diagram" || p.id.startsWith("dia_")
                                              ? "Схема"
                                              : "График",
                                        })
                                      }
                                    >
                                      <img src={p.url} alt="" />
                                    </button>
                                    <figcaption>
                                      {onRefineVisual ? (
                                        <button
                                          type="button"
                                          className="msg-inline-chart-refine"
                                          onClick={() => onRefineVisual(p)}
                                        >
                                          Уточнить
                                        </button>
                                      ) : null}
                                      <a
                                        href={p.url}
                                        download={
                                          p.kind === "diagram" || p.id.startsWith("dia_")
                                            ? "diagram.png"
                                            : "chart.png"
                                        }
                                      >
                                        Скачать PNG
                                      </a>
                                    </figcaption>
                                  </figure>
                                ))}
                            </div>
                          )}
                      </>
                    ) : (
                      <div className="msg-body">{m.text}</div>
                    )}
                    {m.role === "bot" && m.error && (
                      <div className="msg-error-block">
                        <p className="err">{m.error}</p>
                        {m.canResume && m.failedRunId && onResumeRun ? (
                          <button
                            type="button"
                            className="btn-resume-run"
                            onClick={() =>
                              onResumeRun(m.id, m.failedRunId as string)
                            }
                          >
                            Продолжить
                          </button>
                        ) : null}
                      </div>
                    )}
                    {m.role === "bot" &&
                      m.result &&
                      (m.result.downloads?.pdf ||
                        m.result.downloads?.docx) && (
                        <ArtifactCard
                          title={reportTitle(m.result)}
                          thumbUrl={reportThumb(m.result)}
                          pdfUrl={m.result.downloads?.pdf}
                          downloads={m.result.downloads}
                          pulse={downloadsPulseMsgId === m.id}
                          updated={downloadsPulseMsgId === m.id}
                          onView={() => onOpenReport(m.id, m.result!)}
                          onMakePresentation={
                            onMakePresentation
                              ? () => onMakePresentation(m.id, m.result!)
                              : undefined
                          }
                        />
                      )}
                  </div>
                </div>
              )}
            </motion.div>
          );
        })}
      </AnimatePresence>
      <div className="messages-end-anchor" ref={bottomRef} />
    </div>
    {openChart ? (
      <div className="chat-chart-lightbox" role="dialog" aria-modal="true" aria-label="График">
        <button
          type="button"
          className="chat-chart-lightbox-back"
          aria-label="Закрыть"
          onClick={() => setOpenChart(null)}
        />
        <figure className="chat-chart-lightbox-sheet">
          <img src={openChart.url} alt="" />
          <figcaption>
            <a href={openChart.url} download>
              Скачать PNG
            </a>
            <button type="button" onClick={() => setOpenChart(null)}>
              Закрыть
            </button>
          </figcaption>
        </figure>
      </div>
    ) : null}
    </>
  );
}
