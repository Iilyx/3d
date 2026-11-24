/** Liber deck viewer: Julius-like live twin + filmstrip + fullscreen. */

import { AnimatePresence, motion, useReducedMotion } from "framer-motion";
import { lazy, Suspense, useCallback, useEffect, useRef, useState } from "react";
import {
  ChartEditSheet,
  type ChartEditRequest,
  type PaletteInfo,
} from "./ChartEditSheet";
import { DeckCanvas, mediaUrl, type DeckMediaKind } from "./DeckCanvas";
import { redoChord, undoChord } from "./domain/undoChord";
import { DeckGallery, type DeckGalleryItem } from "./DeckGallery";
import type { DeckIR, DeckSlide } from "./deckTypes";
import {
  addedSlideIndex,
  bindSlidePngs,
  retargetSlidePngs,
} from "./domain/slideStrip";
import { recallDeckPlace, rememberDeckPlace, type DeckPlace } from "./domain/deckPlace";
import { slideIndexForUndoTarget } from "./domain/deckUndo";
import {
  parseEditHistory,
  shouldIgnoreDeckHotkey,
  type EditHistoryDesc,
} from "./domain/reportEditMode";
import {
  ImageEditModal,
  type ImageEditRequest,
} from "./ImageEditModal";
import { useConfirm } from "./ConfirmModal";
import {
  chartNumberEditConfirm,
  numberChangeFromEditError,
} from "./domain/chartTypeFit";
import { IconUndo, IconRedo } from "./icons";
const DiagramVisualEditor = lazy(() =>
  import("./DiagramVisualEditor").then((m) => ({
    default: m.DiagramVisualEditor,
  })),
);
import { DiagramFullscreen, type DiagramInfo } from "./DiagramFullscreen";
import type { DiagramResult } from "./domain/liberTypes";
import { PresentationFullscreen } from "./PresentationFullscreen";
import { LayoutPickerModal } from "./LayoutPickerModal";

/** Survive tab switches: PresentationPane unmounts on Preview/PDF. */
const slidesTimerStartedAt = new Map<string, number>();

function useElapsedSeconds(active: boolean, runId: string): number {
  const [sec, setSec] = useState(() => {
    if (!active || !runId) return 0;
    const t0 = slidesTimerStartedAt.get(runId);
    return t0 ? Math.floor((Date.now() - t0) / 1000) : 0;
  });
  useEffect(() => {
    if (!active || !runId) {
      if (runId) slidesTimerStartedAt.delete(runId);
      setSec(0);
      return;
    }
    let t0 = slidesTimerStartedAt.get(runId);
    if (t0 == null) {
      t0 = Date.now();
      slidesTimerStartedAt.set(runId, t0);
    }
    const tick = () => setSec(Math.floor((Date.now() - t0!) / 1000));
    tick();
    const id = window.setInterval(tick, 500);
    return () => window.clearInterval(id);
  }, [active, runId]);
  return sec;
}

type Props = {
  runId: string;
  slidePngs: string[];
  deck?: DeckIR | null;
  status?: string | null;
  stage?: string | null;
  error?: string | null;
  downloads?: Record<string, string>;
  deckPdfMode?: string | null;
  making?: boolean;
  onDeckUpdated?: (
    deck: DeckIR,
    slidePngs: string[],
    extras?: { downloads?: Record<string, string>; diagrams?: DiagramResult[] },
  ) => void;
  palettes?: PaletteInfo[];
  catalogTypes?: string[];
  defaultPalette?: string;
  editingFigureId?: string | null;
  editError?: string | null;
  editErrorFigureId?: string | null;
  editHistory?: EditHistoryDesc | null;
  onEditFigure?: (req: ChartEditRequest) => Promise<boolean> | boolean;
  onEditImage?: (req: ImageEditRequest) => Promise<boolean> | boolean;
  /** Mermaid specs for dia_* slides. Save writes figures.json, then rebuilds the deck. */
  diagrams?: DiagramResult[];
  onHistoryUndo?: () => void | Promise<void>;
  onHistoryRedo?: () => void | Promise<void>;
  onClearEditHistory?: () => void | Promise<void>;
  onEditHistory?: (h: EditHistoryDesc) => void;
  /** Controlled edit mode when chrome lives in ArtifactRail. */
  editing?: boolean;
  onEditingChange?: (on: boolean) => void;
  /** Hide in-pane Edit / history when rail owns chrome. */
  showEditChrome?: boolean;
  /** Notify parent that twin/PPTX need flush on Готово. */
  onDocsDirtyChange?: (dirty: boolean) => void;
  /** Parent copy of the unsaved-edit flag. Survives this pane unmounting. */
  downloadsBlocked?: boolean;
  /** Click on a file that is behind the screen (PNG / copy). */
  onStaleDownload?: () => void;
};

export function PresentationPane({
  runId,
  slidePngs,
  deck: deckProp = null,
  status,
  stage,
  error,
  downloads: _downloads,
  deckPdfMode: _deckPdfMode = null,
  making = false,
  onDeckUpdated,
  palettes = [],
  catalogTypes = [],
  defaultPalette = "atelier",
  editingFigureId = null,
  editError = null,
  editErrorFigureId = null,
  editHistory = null,
  onEditFigure,
  onEditImage,
  diagrams: diagramsProp,
  onEditHistory,
  editing: editingProp,
  onEditingChange,
  showEditChrome = true,
  onDocsDirtyChange,
  downloadsBlocked = false,
  onStaleDownload,
}: Props) {
  const confirm = useConfirm();
  const reduce = useReducedMotion();
  const [idx, setIdx] = useState(0);
  const [dir, setDir] = useState(0);
  const [full, setFull] = useState(false);
  /**
   * Julius gallery contract:
   * - a different run → grid, editing=false
   * - same run remount (tab switch) → the slide of the last edit or undo
   * - gallery thumbnail click → Slide + editing=false (never Edit)
   * - Edit only via Edit segment or E key
   * - leaving Edit → Slide turns editing off
   * - twin/PPTX rebuild only on «Готово», not on each IR edit
   */
  const [editingLocal, setEditingLocal] = useState(false);
  const controlledEdit = editingProp !== undefined;
  const editing = controlledEdit ? Boolean(editingProp) : editingLocal;
  const setEditing = useCallback(
    (on: boolean) => {
      if (!controlledEdit) setEditingLocal(on);
      onEditingChange?.(on);
    },
    [controlledEdit, onEditingChange],
  );
  const [view, setView] = useState<"grid" | "slide">("grid");
  const [deck, setDeck] = useState<DeckIR | null>(deckProp);
  const [saving, setSaving] = useState(false);
  const [saveFlash, setSaveFlash] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [docsDirty, setDocsDirty] = useState(false);
  const [dragFrom, setDragFrom] = useState<number | null>(null);
  const [openMediaId, setOpenMediaId] = useState<string | null>(null);
  const [openMediaKind, setOpenMediaKind] = useState<DeckMediaKind | null>(
    null,
  );
  const [diagrams, setDiagrams] = useState<DiagramResult[]>(diagramsProp ?? []);
  const [diagramError, setDiagramError] = useState<string | null>(null);
  const [mediaVersion, setMediaVersion] = useState(0);
  const [chartIndex, setChartIndex] = useState<
    Record<string, { type?: string; palette?: string; style_user?: boolean }>
  >({});
  const [chartPreview, setChartPreview] = useState<string | null>(null);
  const [pickerOpen, setPickerOpen] = useState(false);
  const [pickerAfterId, setPickerAfterId] = useState<string | null>(null);
  const [zoomDiagram, setZoomDiagram] = useState<DiagramInfo | null>(null);
  const [copiedPng, setCopiedPng] = useState(false);
  const pngKey = `${runId}\n${slidePngs.join("\n")}`;
  const [pngSession, setPngSession] = useState<{
    key: string;
    map: Record<string, string | null>;
  } | null>(null);
  const dirtyRef = useRef(false);
  const n = Math.max(slidePngs.length, deck?.slides?.length || 0);
  const safeIdx = n ? Math.min(idx, n - 1) : 0;
  const live = Boolean(deck?.slides?.length);
  const pngById =
    pngSession && pngSession.key === pngKey
      ? pngSession.map
      : bindSlidePngs(deck?.slides || [], slidePngs);
  const currentSlideId = deck?.slides?.[safeIdx]?.id;
  const currentPng =
    live && currentSlideId
      ? (pngById[currentSlideId] ?? null)
      : slidePngs[safeIdx] || null;
  const slideTitle =
    deck?.slides?.[safeIdx]?.title ||
    (n ? `Слайд ${safeIdx + 1}` : "Презентация");

  const prevDeckPropRef = useRef(deckProp);
  useEffect(() => {
    const externalChange = prevDeckPropRef.current !== deckProp;
    prevDeckPropRef.current = deckProp;
    if (dirtyRef.current && !externalChange) return;
    dirtyRef.current = false;
    setDeck(deckProp);
  }, [deckProp]);

  const runSeen = useRef<string | null>(null);
  /** undefined = not read yet; null = nothing to restore. */
  const pendingPlace = useRef<DeckPlace | null | undefined>(undefined);
  useEffect(() => {
    const switched = runSeen.current != null && runSeen.current !== runId;
    runSeen.current = runId;
    if (!switched) return;
    pendingPlace.current = undefined;
    setIdx(0);
    setDir(0);
    setEditing(false);
    setView("grid");
    setSaveError(null);
    setDocsDirty(false);
    dirtyRef.current = false;
    onDocsDirtyChange?.(false);
    setOpenMediaId(null);
    setOpenMediaKind(null);
    setChartPreview(null);
    setChartIndex({});
    // eslint-disable-next-line react-hooks/exhaustive-deps -- reset on run only
  }, [runId]);

  useEffect(() => {
    if (pendingPlace.current === undefined) {
      pendingPlace.current = recallDeckPlace(runId);
    }
    const place = pendingPlace.current;
    if (!place) return;
    const slides = deck?.slides;
    if (!slides?.length) return;
    const i = slides.findIndex((s) => s.id === place.slideId);
    if (i < 0) {
      pendingPlace.current = null;
      return;
    }
    if (i !== idx || view !== place.view || editing !== place.editing) {
      setDir(i >= idx ? 1 : -1);
      setIdx(i);
      setView(place.view);
      setEditing(place.editing);
      return;
    }
    pendingPlace.current = null;
  }, [deck, editing, idx, runId, setEditing, view]);

  useEffect(() => {
    if (pendingPlace.current) return;
    const id = deck?.slides?.[safeIdx]?.id;
    if (!id) return;
    rememberDeckPlace(runId, { slideId: id, view, editing });
  }, [deck, editing, runId, safeIdx, view]);

  useEffect(() => {
    setDiagrams(diagramsProp ?? []);
  }, [diagramsProp]);

  useEffect(() => {
    let cancelled = false;
    void fetch(`/api/runs/${encodeURIComponent(runId)}/slides`)
      .then((r) => r.json())
      .then(
        (body: {
          charts?: Record<string, { type?: string; palette?: string }>;
          diagrams?: DiagramResult[];
        }) => {
          if (!cancelled && body?.charts && typeof body.charts === "object") {
            setChartIndex(body.charts);
          }
          if (!cancelled && Array.isArray(body?.diagrams) && body.diagrams.length > 0) {
            setDiagrams(body.diagrams);
          }
        },
      )
      .catch(() => {
        /* sheet falls back to the default palette */
      });
    return () => {
      cancelled = true;
    };
  }, [runId]);

  const refreshSlidesNow = useCallback(async (): Promise<DeckIR | null> => {
    const g = await fetch(`/api/runs/${encodeURIComponent(runId)}/slides`);
    const gBody = await g.json().catch(() => ({}));
    if (!g.ok) return null;
    const pngs = Array.isArray(gBody.slide_pngs)
      ? (gBody.slide_pngs as string[])
      : [];
    const nextDeck =
      gBody.deck && typeof gBody.deck === "object"
        ? (gBody.deck as DeckIR)
        : null;
    if (nextDeck) setDeck(nextDeck);
    if (gBody.charts && typeof gBody.charts === "object") {
      setChartIndex(gBody.charts);
    }
    if (pngs.length || gBody.deck) {
      const dl =
        gBody.downloads && typeof gBody.downloads === "object"
          ? (gBody.downloads as Record<string, string>)
          : undefined;
      onDeckUpdated?.(gBody.deck as DeckIR, pngs, {
        downloads: dl,
        diagrams,
      });
    }
    if (gBody.undo) {
      onEditHistory?.(
        parseEditHistory(
          gBody.undo as Parameters<typeof parseEditHistory>[0],
        ),
      );
    }
    setMediaVersion(Date.now());
    return nextDeck;
  }, [diagrams, onDeckUpdated, onEditHistory, runId]);

  const jumpToUndoTarget = useCallback((deckNow: DeckIR | null, target: unknown) => {
    const idx = slideIndexForUndoTarget(
      deckNow?.slides,
      typeof target === "string" ? target : "",
    );
    if (idx < 0) return;
    setView("slide");
    setDir(idx >= safeIdx ? 1 : -1);
    setIdx(idx);
  }, [safeIdx]);

  const markDirty = useCallback(() => {
    setDocsDirty(true);
    onDocsDirtyChange?.(true);
  }, [onDocsDirtyChange]);

  const postDeckHistory = useCallback(
    async (path: "undo" | "redo") => {
      setSaveError(null);
      try {
        const r = await fetch(
          `/api/runs/${encodeURIComponent(runId)}/${path}?rebuild=0`,
          { method: "POST" },
        );
        const data = await r.json().catch(() => ({}));
        if (!r.ok) {
          throw new Error(
            typeof data.detail === "string" ? data.detail : `${path} ${r.status}`,
          );
        }
        const hist = parseEditHistory(
          data.undo as Parameters<typeof parseEditHistory>[0],
        );
        onEditHistory?.(hist);
        const action = path === "undo" ? data.undone : data.redone;
        const target =
          action && typeof action === "object"
            ? (action as { target?: unknown }).target
            : "";
        // IR moved. PPTX stays until «Готово».
        if (hist.canUndo || hist.canRedo) {
          dirtyRef.current = true;
          markDirty();
        }
        const next = await refreshSlidesNow();
        jumpToUndoTarget(next, target);
      } catch (err) {
        setSaveError(err instanceof Error ? err.message : String(err));
      }
    },
    [jumpToUndoTarget, markDirty, onEditHistory, refreshSlidesNow, runId],
  );

  const historyUndo = useCallback(async () => {
    await postDeckHistory("undo");
  }, [postDeckHistory]);

  const historyRedo = useCallback(async () => {
    await postDeckHistory("redo");
  }, [postDeckHistory]);

  // Safety net: rail opened with pptx downloads but empty twin/deck (old status).
  useEffect(() => {
    if (deckProp?.slides?.length) return;
    if (status !== "ok" && slidePngs.length === 0) return;
    let cancelled = false;
    void (async () => {
      try {
        const g = await fetch(`/api/runs/${encodeURIComponent(runId)}/slides`);
        const gBody = await g.json().catch(() => ({}));
        if (cancelled || !g.ok) return;
        const pngs = Array.isArray(gBody.slide_pngs)
          ? (gBody.slide_pngs as string[])
          : [];
        if (gBody.deck) setDeck(gBody.deck as DeckIR);
        if (gBody.charts && typeof gBody.charts === "object") {
          setChartIndex(gBody.charts);
        }
        if (pngs.length || gBody.deck) {
          onDeckUpdated?.(gBody.deck as DeckIR, pngs);
        }
      } catch {
        /* keep empty */
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [runId, status, slidePngs.length, deckProp, onDeckUpdated]);

  useEffect(() => {
    const el = document.querySelector(
      `.presentation-thumb:nth-child(${safeIdx + 1})`,
    );
    el?.scrollIntoView({ inline: "center", block: "nearest", behavior: "smooth" });
  }, [safeIdx]);

  const go = useCallback(
    (delta: number) => {
      if (!n) return;
      setDir(delta);
      setIdx((i) => (i + delta + n) % n);
    },
    [n],
  );

  const waitPatchRebuild = useCallback(
    async (optimisticDeck?: DeckIR) => {
      if (optimisticDeck) setDeck(optimisticDeck);
      let done = false;
      for (let i = 0; i < 120; i++) {
        await new Promise((res) => setTimeout(res, 500));
        const g = await fetch(`/api/runs/${encodeURIComponent(runId)}/slides`);
        const gBody = await g.json().catch(() => ({}));
        if (gBody.slides_status === "ok") {
          const pngs = (gBody.slide_pngs as string[]) || [];
          if (gBody.deck) setDeck(gBody.deck as DeckIR);
          const dl =
            gBody.downloads && typeof gBody.downloads === "object"
              ? (gBody.downloads as Record<string, string>)
              : undefined;
          onDeckUpdated?.(gBody.deck as DeckIR, pngs, {
            downloads: dl,
            diagrams,
          });
          setMediaVersion(Date.now());
          setSaveFlash(true);
          window.setTimeout(() => setSaveFlash(false), 1600);
          done = true;
          break;
        }
        if (gBody.slides_status === "cancelled") {
          throw new Error("Остановлено");
        }
        if (gBody.slides_status === "error") {
          throw new Error(
            String(gBody.slides_error || "Не удалось сохранить слайды"),
          );
        }
      }
      if (!done) {
        throw new Error("Сохранение заняло слишком долго — попробуйте ещё раз");
      }
    },
    [diagrams, onDeckUpdated, runId],
  );

  useEffect(() => {
    if (downloadsBlocked) return;
    dirtyRef.current = false;
    setDocsDirty(false);
  }, [downloadsBlocked]);

  const inFlightPatchRef = useRef<Promise<void> | null>(null);

  const flushDeckRebuild = useCallback(async () => {
    setSaving(true);
    setSaveError(null);
    try {
      const r = await fetch(
        `/api/runs/${encodeURIComponent(runId)}/slides/rebuild`,
        { method: "POST" },
      );
      const body = await r.json().catch(() => ({}));
      if (!r.ok) {
        throw new Error(
          typeof body.detail === "string" ? body.detail : `rebuild ${r.status}`,
        );
      }
      await waitPatchRebuild(body.deck as DeckIR | undefined);
      dirtyRef.current = false;
      setDocsDirty(false);
      onDocsDirtyChange?.(false);
    } catch (err) {
      setSaveError(err instanceof Error ? err.message : String(err));
      throw err;
    } finally {
      setSaving(false);
    }
  }, [onDocsDirtyChange, runId, waitPatchRebuild]);

  const leaveEdit = useCallback(async () => {
    try {
      if (
        typeof document !== "undefined" &&
        document.activeElement instanceof HTMLElement &&
        document.activeElement.classList.contains("deck-ed")
      ) {
        document.activeElement.blur();
      }
      await Promise.resolve();
      if (inFlightPatchRef.current) {
        await inFlightPatchRef.current;
      }
      if (docsDirty || dirtyRef.current || downloadsBlocked) await flushDeckRebuild();
      setOpenMediaId(null);
      setOpenMediaKind(null);
      setChartPreview(null);
      setEditing(false);
    } catch {
      /* stay in edit — error already shown */
    }
  }, [docsDirty, downloadsBlocked, flushDeckRebuild, setEditing]);

  const stopEditing = useCallback(async () => {
    if (
      typeof document !== "undefined" &&
      document.activeElement instanceof HTMLElement &&
      document.activeElement.classList.contains("deck-ed")
    ) {
      document.activeElement.blur();
    }
    await Promise.resolve();
    if (inFlightPatchRef.current) {
      await inFlightPatchRef.current;
    }
    setOpenMediaId(null);
    setOpenMediaKind(null);
    setChartPreview(null);
    setEditing(false);
  }, [setEditing]);

  useEffect(() => {
    if (full) return;
    const onKey = (e: KeyboardEvent) => {
      // Escape blurs active text input so single-key hotkeys work immediately
      if (e.key === "Escape") {
        if (
          typeof document !== "undefined" &&
          document.activeElement instanceof HTMLElement &&
          (document.activeElement.classList.contains("deck-ed") ||
            document.activeElement.tagName === "INPUT" ||
            document.activeElement.tagName === "TEXTAREA")
        ) {
          document.activeElement.blur();
        }
        return;
      }
      // PageUp / PageDown and Alt+Arrows always navigate slides, even when focused in an input
      if (e.key === "PageUp" || (e.altKey && e.key === "ArrowLeft")) {
        e.preventDefault();
        go(-1);
        return;
      }
      if (e.key === "PageDown" || (e.altKey && e.key === "ArrowRight")) {
        e.preventDefault();
        go(1);
        return;
      }
      // Undo / Redo in presentation editing (catches Cmd+Z / Ctrl+Z cleanly, incl. RU layout)
      if (
        editing &&
        (e.metaKey || e.ctrlKey) &&
        !e.altKey &&
        (e.code === "KeyZ" || e.key.toLowerCase() === "z")
      ) {
        e.preventDefault();
        if (
          typeof document !== "undefined" &&
          document.activeElement instanceof HTMLElement &&
          (document.activeElement.classList.contains("deck-ed") ||
            document.activeElement.tagName === "INPUT" ||
            document.activeElement.tagName === "TEXTAREA")
        ) {
          document.activeElement.blur();
        }
        if (e.shiftKey) void historyRedo();
        else void historyUndo();
        return;
      }
      const hasModal =
        typeof document !== "undefined" &&
        Boolean(
          document.querySelector(
            ".modal-backdrop, [role='dialog']:not(.artifact-rail-backdrop)",
          ),
        );
      if (shouldIgnoreDeckHotkey(e.target, hasModal)) return;
      if (e.key === "ArrowLeft") go(-1);
      if (e.key === "ArrowRight") {
        e.preventDefault();
        go(1);
      }
      if (e.metaKey || e.ctrlKey || e.altKey) {
        // no plain-letter shortcuts with modifiers
      } else if ((e.key === "g" || e.key === "G") && n > 0) {
        setView("grid");
        if (editing) void stopEditing();
        return;
      } else if (e.key === "s" || e.key === "S") {
        setView("slide");
        if (editing) void stopEditing();
        return;
      }
      if (!e.metaKey && !e.ctrlKey && !e.altKey && (e.key === "f" || e.key === "F")) {
        setFull(true);
      }
      if (!e.metaKey && !e.ctrlKey && !e.altKey && (e.key === "e" || e.key === "E")) {
        setView("slide");
        if (editing) void leaveEdit();
        else setEditing(true);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [full, go, editing, leaveEdit, stopEditing, historyUndo, historyRedo, setEditing, n]);

  const patchSlides = useCallback(
    async (slides: (Partial<DeckSlide> & { id: string })[]) => {
      setSaveError(null);
      const task = (async () => {
        try {
          const r = await fetch(
            `/api/runs/${encodeURIComponent(runId)}/slides/ir?rebuild=0`,
            {
              method: "PATCH",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({ slides }),
            },
          );
          const body = await r.json().catch(() => ({}));
          if (!r.ok) {
            throw new Error(
              typeof body.detail === "string" ? body.detail : `patch ${r.status}`,
            );
          }
          if (body.deck) {
            const next = body.deck as DeckIR;
            setDeck(next);
            onDeckUpdated?.(next, slidePngs);
          }
          if (body.undo) {
            onEditHistory?.(
              parseEditHistory(
                body.undo as Parameters<typeof parseEditHistory>[0],
              ),
            );
          }
          dirtyRef.current = true;
          markDirty();
        } catch (err) {
          setSaveError(err instanceof Error ? err.message : String(err));
          // Server rejected the shape (or the write failed). Drop the
          // optimistic table/text so the slide matches deck.json.
          await refreshSlidesNow();
        }
      })();
      inFlightPatchRef.current = task;
      await task;
      if (inFlightPatchRef.current === task) {
        inFlightPatchRef.current = null;
      }
    },
    [markDirty, onDeckUpdated, onEditHistory, refreshSlidesNow, runId, slidePngs],
  );

  const mediaSheetRef = useRef<HTMLDivElement | null>(null);
  const [imageUploading, setImageUploading] = useState(false);
  const [imageUploadError, setImageUploadError] = useState<string | null>(null);

  useEffect(() => {
    if (openMediaId && mediaSheetRef.current) {
      mediaSheetRef.current.scrollIntoView({
        behavior: "smooth",
        block: "nearest",
      });
    }
  }, [openMediaId]);

  const onMediaClick = useCallback((id: string, kind: DeckMediaKind) => {
    setOpenMediaId(id);
    setOpenMediaKind(kind);
    setImageUploadError(null);
  }, []);

  const handleDiagramZoom = useCallback((dia: DiagramInfo) => {
    setZoomDiagram(dia);
  }, []);

  const closeMediaSheet = useCallback(() => {
    setOpenMediaId(null);
    setOpenMediaKind(null);
    setChartPreview(null);
    setImageUploadError(null);
  }, []);

  const submitChart = useCallback(
    async (req: ChartEditRequest) => {
      if (onEditFigure) {
        const ok = await onEditFigure(req);
        if (ok) {
          setMediaVersion((v) => v + 1);
          await refreshSlidesNow();
          closeMediaSheet();
        }
        return;
      }
      setSaving(true);
      setSaveError(null);
      try {
        let accepted = req.acceptedHtml || "";
        for (let attempt = 0; attempt < 2; attempt++) {
          const res = await fetch(
            `/api/runs/${encodeURIComponent(runId)}/charts/${encodeURIComponent(req.figureId)}/edit`,
            {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({
                chart_type: req.chartType,
                palette: req.palette,
                style: req.styleNotes,
                accepted_html: accepted,
              }),
            },
          );
          const data = await res.json().catch(() => ({}));
          if (!res.ok) {
            const changed =
              attempt === 0
                ? numberChangeFromEditError({ detail: data.detail })
                : null;
            if (changed) {
              const ask = chartNumberEditConfirm(changed.message);
              const ok = ask ? await confirm(ask) : false;
              if (!ok) return;
              accepted = changed.html;
              continue;
            }
            const detail = data.detail;
            const message =
              typeof detail === "string"
                ? detail
                : detail && typeof detail === "object" && typeof detail.message === "string"
                  ? detail.message
                  : `chart edit ${res.status}`;
            throw new Error(message);
          }
          if (data.undo) {
            onEditHistory?.(
              parseEditHistory(
                data.undo as Parameters<typeof parseEditHistory>[0],
              ),
            );
          }
          setMediaVersion(Date.now());
          await refreshSlidesNow();
          closeMediaSheet();
          return;
        }
      } catch (err) {
        setSaveError(err instanceof Error ? err.message : String(err));
      } finally {
        setSaving(false);
      }
    },
    [closeMediaSheet, confirm, onEditFigure, onEditHistory, refreshSlidesNow, runId],
  );

  const submitImage = useCallback(
    async (req: ImageEditRequest) => {
      if (onEditImage) {
        const ok = await onEditImage(req);
        if (ok) {
          setMediaVersion((v) => v + 1);
          await refreshSlidesNow();
          closeMediaSheet();
        }
        return;
      }
      setSaving(true);
      setSaveError(null);
      try {
        const res = await fetch(
          `/api/runs/${encodeURIComponent(runId)}/figures/${encodeURIComponent(req.figureId)}/edit`,
          {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              mode: req.mode,
              prompt: req.prompt,
              caption: req.caption,
            }),
          },
        );
        const data = await res.json().catch(() => ({}));
        if (!res.ok) {
          throw new Error(
            typeof data.detail === "string"
              ? data.detail
              : `image edit ${res.status}`,
          );
        }
        if (data.undo) {
          onEditHistory?.(
            parseEditHistory(
              data.undo as Parameters<typeof parseEditHistory>[0],
            ),
          );
        }
        setMediaVersion(Date.now());
        await refreshSlidesNow();
        closeMediaSheet();
      } catch (err) {
        setSaveError(err instanceof Error ? err.message : String(err));
      } finally {
        setSaving(false);
      }
    },
    [closeMediaSheet, onEditHistory, onEditImage, refreshSlidesNow, runId],
  );

  const submitImageUpload = useCallback(
    async (file: File, caption?: string) => {
      if (!openMediaId) return;
      setImageUploading(true);
      setImageUploadError(null);
      try {
        const form = new FormData();
        form.append("image", file);
        form.append("file", file);
        if (caption) {
          form.append("caption", caption);
        }
        const res = await fetch(
          `/api/runs/${encodeURIComponent(runId)}/figures/${encodeURIComponent(openMediaId)}/upload`,
          {
            method: "POST",
            body: form,
          },
        );
        const data = await res.json().catch(() => ({}));
        if (!res.ok) {
          throw new Error(
            typeof data.detail === "string"
              ? data.detail
              : `upload failed (${res.status})`,
          );
        }
        if (data.undo) {
          onEditHistory?.(
            parseEditHistory(
              data.undo as Parameters<typeof parseEditHistory>[0],
            ),
          );
        }
        setMediaVersion(Date.now());
        await refreshSlidesNow();
        closeMediaSheet();
      } catch (err) {
        setImageUploadError(err instanceof Error ? err.message : String(err));
      } finally {
        setImageUploading(false);
      }
    },
    [closeMediaSheet, onEditHistory, openMediaId, refreshSlidesNow, runId],
  );

  const openDiagram = diagrams.find((d) => d.id === openMediaId) || null;

  useEffect(() => {
    if (openMediaKind !== "diagram" || !openMediaId || openDiagram) return;
    let cancelled = false;
    void fetch(`/api/runs/${encodeURIComponent(runId)}/status`)
      .then((r) => r.json())
      .then((body: { diagrams?: DiagramResult[] }) => {
        if (cancelled || !Array.isArray(body.diagrams)) return;
        setDiagrams(body.diagrams);
      })
      .catch(() => {
        if (!cancelled) setDiagramError("Не удалось открыть схему");
      });
    return () => {
      cancelled = true;
    };
  }, [openDiagram, openMediaId, openMediaKind, runId]);

  const saveDiagram = useCallback(
    async (mermaid: string, title: string) => {
      if (!openMediaId) return;
      setSaving(true);
      setDiagramError(null);
      setSaveError(null);
      try {
        const res = await fetch(
          `/api/runs/${encodeURIComponent(runId)}/diagrams/${encodeURIComponent(openMediaId)}/edit`,
          {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ mermaid, title }),
          },
        );
        const data = await res.json().catch(() => ({}));
        if (!res.ok) {
          throw new Error(
            typeof data.detail === "string" ? data.detail : `edit ${res.status}`,
          );
        }
        if (data.diagram && typeof data.diagram === "object") {
          const saved = data.diagram as DiagramResult;
          setDiagrams((prev) => {
            const rest = prev.filter((d) => d.id !== saved.id);
            return [...rest, saved];
          });
        }
        if (data.undo) {
          onEditHistory?.(
            parseEditHistory(
              data.undo as Parameters<typeof parseEditHistory>[0],
            ),
          );
        }
        dirtyRef.current = true;
        markDirty();
        closeMediaSheet();
      } catch (err) {
        setDiagramError(err instanceof Error ? err.message : String(err));
      } finally {
        setSaving(false);
      }
    },
    [closeMediaSheet, markDirty, onEditHistory, openMediaId, runId],
  );

  const structureOp = useCallback(
    async (payload: {
      op: "reorder" | "duplicate" | "delete" | "insert";
      id?: string;
      order?: string[];
      layout?: string;
    }) => {
      if (!deck?.slides?.length) {
        setSaveError("Нет данных презентации — соберите презентацию");
        return;
      }
      const before = deck.slides;
      setSaveError(null);
      try {
        const r = await fetch(
          `/api/runs/${encodeURIComponent(runId)}/slides/structure?rebuild=0`,
          {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload),
          },
        );
        const body = await r.json().catch(() => ({}));
        if (!r.ok) {
          throw new Error(
            typeof body.detail === "string"
              ? body.detail
              : `structure ${r.status}`,
          );
        }
        const next = body.deck as DeckIR | undefined;
        if (next?.slides) {
          setDeck(next);
          setPngSession({
            key: pngKey,
            map: retargetSlidePngs(pngById, before, next.slides, payload.op),
          });
          onDeckUpdated?.(next, slidePngs);
          if (payload.op === "delete") {
            setIdx((i) => Math.min(i, Math.max(0, next.slides.length - 1)));
            setView("slide");
          }
          if (payload.op === "duplicate" || payload.op === "insert") {
            const at = addedSlideIndex(before, next.slides);
            if (at >= 0) {
              setIdx(at);
              setView("slide");
              if (payload.op === "insert") setEditing(true);
            }
          }
        }
        if (body.undo) {
          onEditHistory?.(
            parseEditHistory(
              body.undo as Parameters<typeof parseEditHistory>[0],
            ),
          );
        }
        dirtyRef.current = true;
        markDirty();
      } catch (err) {
        setPngSession(null);
        setSaveError(err instanceof Error ? err.message : String(err));
        await refreshSlidesNow();
      }
    },
    [
      deck,
      markDirty,
      onDeckUpdated,
      onEditHistory,
      pngById,
      pngKey,
      refreshSlidesNow,
      runId,
      setEditing,
      slidePngs,
    ],
  );

  const onReorderIndices = useCallback(
    (from: number, to: number) => {
      if (!deck?.slides?.length || from === to || saving) return;
      const slides = [...deck.slides];
      if (from < 0 || to < 0 || from >= slides.length || to >= slides.length) {
        return;
      }
      const [moved] = slides.splice(from, 1);
      slides.splice(to, 0, moved);
      setPngSession({
        key: pngKey,
        map: retargetSlidePngs(pngById, deck.slides, slides, "reorder"),
      });
      setDeck({ ...deck, slides });
      setIdx(to);
      void structureOp({ op: "reorder", order: slides.map((s) => s.id) });
    },
    [deck, pngById, pngKey, saving, structureOp],
  );

  const fileBehind = docsDirty || downloadsBlocked;

  const handleDownloadPng = useCallback(async () => {
    if (fileBehind || !currentPng) return;
    try {
      const res = await fetch(currentPng);
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      const slideNum = String(safeIdx + 1).padStart(2, "0");
      const safeTitle = (deck?.slides?.[safeIdx]?.title || "slide")
        .slice(0, 30)
        .replace(/[^\wа-яА-ЯёЁ0-9-_]+/gi, "_");
      a.download = `slide_${slideNum}_${safeTitle}.png`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    } catch (err) {
      setSaveError(
        `Не удалось скачать PNG: ${err instanceof Error ? err.message : String(err)}`,
      );
    }
  }, [currentPng, deck, fileBehind, safeIdx]);

  const handleCopyPng = useCallback(async () => {
    if (fileBehind || !currentPng) return;
    try {
      const res = await fetch(currentPng);
      const blob = await res.blob();
      await navigator.clipboard.write([
        new ClipboardItem({ "image/png": blob }),
      ]);
      setCopiedPng(true);
      setTimeout(() => setCopiedPng(false), 2000);
    } catch (err) {
      setSaveError(
        `Не удалось скопировать PNG в буфер: ${err instanceof Error ? err.message : String(err)}`,
      );
    }
  }, [currentPng, fileBehind]);

  const pending =
    status === "running" ||
    status === "queued" ||
    status === "starting" ||
    making;
  const elapsed = useElapsedSeconds(pending, runId);
  const elapsedLabel = `${Math.floor(elapsed / 60)}:${String(elapsed % 60).padStart(2, "0")}`;

  if (pending) {
    const stageLabel = (() => {
      switch (stage) {
        case "patch":
          return "Сохраняю правки в PPTX";
        case "queued":
          return "В очереди";
        case "llm":
        case "llm_retry":
        case "plan":
        case "ir":
          return "Пишу структуру слайдов";
        case "diagrams":
        case "media":
        case "charts":
          return "Готовлю графики и медиа";
        case "render":
          return "Рисую слайды";
        case "pptx":
        case "pdf":
          return "Собираю презентацию";
        default:
          return making && !stage ? "Запускаю сборку" : "Собираю презентацию";
      }
    })();
    const stepKey =
      stage === "llm" ||
      stage === "llm_retry" ||
      stage === "plan" ||
      stage === "ir" ||
      stage === "queued" ||
      !stage
        ? "ir"
        : stage === "diagrams" || stage === "media" || stage === "charts"
          ? "media"
          : stage === "render"
            ? "render"
            : "pptx";
    const stages = ["ir", "media", "render", "pptx"] as const;
    const stageIdx = Math.max(0, stages.indexOf(stepKey));
    return (
      <div className="presentation-pane is-pending">
        <div className="presentation-pending-card" aria-busy="true">
          <div className="presentation-pending-pulse" />
          <p className="presentation-pending">
            <span className="presentation-pending-working" aria-live="polite">
              Собираю
              <span className="presentation-pending-time">{elapsedLabel}</span>
            </span>
            <span className="presentation-pending-stage">{stageLabel}</span>
          </p>
          <ol className="presentation-pending-steps" aria-label="Этапы">
            {["Структура", "Медиа", "Слайды", "Презентация"].map((label, i) => (
              <li
                key={label}
                className={
                  i < stageIdx ? "is-done" : i === stageIdx ? "is-now" : ""
                }
              >
                {label}
              </li>
            ))}
          </ol>
          <p className="presentation-pending-hint">
            Обычно полторы–две минуты. Вкладка остаётся открытой — превью
            появится, когда готово.
          </p>
        </div>
      </div>
    );
  }

  if (status === "cancelled") {
    return (
      <div className="presentation-pane is-cancelled">
        <p className="presentation-empty-kicker">Презентация</p>
        <h3 className="presentation-empty-title">Остановлено</h3>
        <p className="presentation-empty-copy">
          Сборку прервали. Отправьте запрос снова в режиме Презентация.
        </p>
      </div>
    );
  }

  if (status === "error") {
    return (
      <div className="presentation-pane is-error">
        <p className="presentation-error">{error || "Не удалось собрать деку"}</p>
        <p className="presentation-empty-copy">
          Отправьте запрос снова — сборка стартует сама, без кнопки.
        </p>
      </div>
    );
  }

  if (!n && !live) {
    // No «Сделать презентацию» — deck kicks on send; wait or open chat cards.
    return (
      <div className="presentation-pane is-empty">
        <p className="presentation-empty-kicker">Презентация</p>
        <h3 className="presentation-empty-title">Превью появится здесь</h3>
        <p className="presentation-empty-copy">
          После сборки в чате появятся два файла — PPTX и PDF. Нажмите карточку,
          чтобы открыть просмотр и редактор слайдов.
        </p>
      </div>
    );
  }

  const slideVariants = reduce
    ? { enter: { opacity: 1 }, center: { opacity: 1 }, exit: { opacity: 1 } }
    : {
        enter: (d: number) => ({
          x: d >= 0 ? 28 : -28,
          opacity: 0,
          scale: 0.985,
        }),
        center: { x: 0, opacity: 1, scale: 1 },
        exit: (d: number) => ({
          x: d >= 0 ? -22 : 22,
          opacity: 0,
          scale: 0.985,
        }),
      };

  const galleryItems: DeckGalleryItem[] =
    live && deck?.slides?.length
      ? deck.slides.map((s) => ({
          id: s.id,
          url: pngById[s.id] ?? null,
          title: s.title || "",
        }))
      : slidePngs.map((url, i) => ({
          id: `png-${i}`,
          url,
          title: deck?.slides?.[i]?.title || "",
        }));

  return (
    <div
      className={`presentation-pane is-ready${editing ? " is-editing" : ""}${
        openMediaId ? " has-media-sheet" : ""
      }`}
    >
      <header className="presentation-chrome">
        <div className="presentation-chrome-left">
          <span className="presentation-chrome-kicker">
            {editing && view === "slide" ? "Редактирование" : "Презентация"}
          </span>
          <span className="presentation-chrome-title" title={slideTitle}>
            {slideTitle}
          </span>
        </div>
        <div className="presentation-chrome-tools">
          <div className="presentation-seg" role="group" aria-label="Режим">
            {slidePngs.length > 0 ? (
              <button
                type="button"
                className={`presentation-seg-btn${view === "grid" ? " is-on" : ""}`}
                onClick={() => {
                  setView("grid");
                  if (editing) void stopEditing();
                  else setEditing(false);
                }}
                title="Сетка слайдов (G)"
              >
                Сетка
              </button>
            ) : null}
            <button
              type="button"
              className={`presentation-seg-btn${view === "slide" && !editing ? " is-on" : ""}`}
              onClick={() => {
                setView("slide");
                if (editing) void stopEditing();
                else setEditing(false);
              }}
              title="Просмотр слайда (S)"
            >
              Слайд
            </button>
            {live && showEditChrome ? (
              <button
                type="button"
                className={`presentation-seg-btn presentation-seg-edit${
                  view === "slide" && editing ? " is-on" : ""
                }`}
                disabled={saving}
                onClick={() => {
                  if (editing) {
                    void leaveEdit();
                    setView("slide");
                  } else {
                    setView("slide");
                    setEditing(true);
                  }
                }}
                title={editing ? "Завершить редактирование (E)" : "Редактировать слайд (E)"}
              >
                {saving && editing
                  ? "Сохраняю…"
                  : editing
                    ? "Готово"
                    : "Редактировать"}
              </button>
            ) : null}
          </div>
          {showEditChrome &&
          (editing || editHistory?.canUndo || editHistory?.canRedo) ? (
            <div className="presentation-history" role="group" aria-label="История">
              <button
                type="button"
                className="presentation-history-btn"
                aria-label="Отменить"
                title={`Отменить (${undoChord()})`}
                disabled={!editHistory?.canUndo || saving}
                onClick={() => void historyUndo()}
              >
                <IconUndo size={14} />
              </button>
              <button
                type="button"
                className="presentation-history-btn"
                aria-label="Вернуть"
                title={`Вернуть (${redoChord()})`}
                disabled={!editHistory?.canRedo || saving}
                onClick={() => void historyRedo()}
              >
                <IconRedo size={14} />
              </button>
            </div>
          ) : null}
          <button
            type="button"
            className="presentation-tool"
            onClick={() => setFull(true)}
            title="F — на весь экран"
          >
            Предпросмотр
          </button>
        </div>
        <div className="presentation-chrome-actions">
          {n > 1 ? (
            <div
              className="presentation-header-nav"
              role="group"
              aria-label="Переключение слайдов"
            >
              <button
                type="button"
                className="presentation-hdr-arrow"
                onClick={() => go(-1)}
                disabled={saving}
                title="Предыдущий слайд (←, PageUp, Alt+←)"
                aria-label="Предыдущий слайд"
              >
                ‹
              </button>
              <span className="deck-slides-film-count" aria-live="polite">
                {safeIdx + 1}
                <span aria-hidden> / </span>
                {n}
              </span>
              <button
                type="button"
                className="presentation-hdr-arrow"
                onClick={() => go(1)}
                disabled={saving}
                title="Следующий слайд (→, PageDown, Alt+→)"
                aria-label="Следующий слайд"
              >
                ›
              </button>
            </div>
          ) : n === 1 ? (
            <span className="deck-slides-film-count" aria-live="polite">
              1 / 1
            </span>
          ) : null}
        </div>
      </header>

      {view === "grid" && galleryItems.length > 0 ? (
        <DeckGallery
          items={galleryItems}
          activeIndex={safeIdx}
          canStructure={Boolean(live) && !saving}
          onSelect={(i) => {
            // Gallery → Slide only (never Edit). Edit is the Edit segment.
            setDir(i > safeIdx ? 1 : -1);
            setIdx(i);
            setView("slide");
            setEditing(false);
          }}
          onReorder={onReorderIndices}
          onDuplicate={
            live
              ? (i) => {
                  const id = deck?.slides?.[i]?.id;
                  if (id) void structureOp({ op: "duplicate", id });
                }
              : undefined
          }
          onDelete={
            live
              ? async (i) => {
                  const id = deck?.slides?.[i]?.id;
                  if (!id) return;
                  if (deck!.slides.length <= 1) {
                    setSaveError("Нельзя удалить единственный слайд");
                    return;
                  }
                  const title = deck?.slides?.[i]?.title || `Слайд ${i + 1}`;
                  const ok = await confirm({
                    title: "Удалить слайд?",
                    eyebrow: "презентация · структура",
                    message: `Удалить слайд «${title}»? PPTX и превью пересоберутся на столе.`,
                    confirmLabel: "Удалить слайд",
                    danger: true,
                  });
                  if (!ok) return;
                  void structureOp({ op: "delete", id });
                }
              : undefined
          }
          onAddSlide={
            live
              ? () => {
                  const lastId =
                    deck?.slides?.[deck.slides.length - 1]?.id || null;
                  setPickerAfterId(lastId);
                  setPickerOpen(true);
                }
              : undefined
          }
        />
      ) : (
        <>
          <div className="presentation-stage">
            <AnimatePresence mode="wait" custom={dir}>
              <motion.div
                key={
                  live
                    ? `live-${safeIdx}-${deck?.slides?.[safeIdx]?.id}`
                    : `png-${currentPng}`
                }
                className="presentation-stage-frame"
                custom={dir}
                variants={slideVariants}
                initial="enter"
                animate="center"
                exit="exit"
                transition={{ duration: 0.28, ease: [0.22, 1, 0.36, 1] }}
              >
                {live && deck ? (
                  <DeckCanvas
                    runId={runId}
                    deck={deck}
                    index={safeIdx}
                    editing={editing}
                    saving={saving}
                    mediaVersion={mediaVersion}
                    openMediaId={openMediaId}
                    onMediaClick={editing ? onMediaClick : undefined}
                    onDiagramZoom={handleDiagramZoom}
                    onDeckChange={setDeck}
                    onPatch={patchSlides}
                    previewHtml={chartPreview}
                    diagramMermaid={
                      diagrams.find((d) => d.id === deck?.slides?.[safeIdx]?.media_id)
                        ?.mermaid ||
                      diagrams.find((d) => d.id === deck?.slides?.[safeIdx]?.chart_id)
                        ?.mermaid ||
                      null
                    }
                    diagramPalette={deck?.palette || defaultPalette}
                  />
                ) : currentPng ? (
                  <img
                    className="presentation-slide-img"
                    src={
                      mediaVersion
                        ? `${currentPng}${currentPng.includes("?") ? "&" : "?"}mv=${mediaVersion}`
                        : currentPng
                    }
                    alt={`Слайд ${safeIdx + 1} из ${n}`}
                  />
                ) : null}
              </motion.div>
            </AnimatePresence>
            <AnimatePresence>
              {(saving || saveFlash) && !saveError && (
                <motion.div
                  className={`presentation-save-pill${saving ? " is-busy" : " is-ok"}`}
                  initial={reduce ? false : { opacity: 0, y: 8 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, y: 6 }}
                  transition={{ duration: 0.2 }}
                >
                  {saving ? "Сохраняю…" : "Сохранено"}
                </motion.div>
              )}
              {saveError ? (
                <motion.div
                  className="presentation-save-pill is-err"
                  initial={reduce ? false : { opacity: 0, y: 8 }}
                  animate={{ opacity: 1, y: 0 }}
                  role="alert"
                >
                  {saveError}
                  <button
                    type="button"
                    className="presentation-save-dismiss"
                    onClick={() => setSaveError(null)}
                  >
                    OK
                  </button>
                </motion.div>
              ) : null}
            </AnimatePresence>
            {live ? (
              <p className="presentation-font-honesty">
                Шрифты и разметка в скачанном файле PPTX могут незначительно отличаться от веб-превью.
              </p>
            ) : null}
          </div>

          <div
            className="presentation-progress"
            role="progressbar"
            aria-valuenow={safeIdx + 1}
            aria-valuemin={1}
            aria-valuemax={Math.max(n, 1)}
          >
            <span
              style={{
                width: n ? `${((safeIdx + 1) / n) * 100}%` : "0%",
              }}
            />
          </div>

          {live && deck?.slides?.length ? (
            <div
              className="presentation-filmstrip"
              role="tablist"
              aria-label="Слайды"
            >
              {deck.slides.map((s, i) => {
                const t = (s.title || "").trim();
                const url = pngById[s.id];
                const label = t || `Слайд ${i + 1}`;
                return (
                  <div
                    key={s.id}
                    role="tab"
                    tabIndex={0}
                    draggable={!saving}
                    aria-selected={i === safeIdx}
                    className={`presentation-thumb${i === safeIdx ? " is-active" : ""}${!url ? " is-ghost" : ""}${dragFrom === i ? " is-dragging" : ""}`}
                    title={`${label} · перетащите для порядка`}
                    onDragStart={(e) => {
                      if (saving) return;
                      e.dataTransfer.effectAllowed = "move";
                      e.dataTransfer.setData("text/plain", String(i));
                      setDragFrom(i);
                    }}
                    onDragEnd={() => setDragFrom(null)}
                    onDragOver={(e) => {
                      if (!saving) e.preventDefault();
                    }}
                    onDrop={(e) => {
                      e.preventDefault();
                      const raw = e.dataTransfer.getData("text/plain");
                      const from =
                        raw !== "" && Number.isFinite(Number(raw))
                          ? Number(raw)
                          : dragFrom;
                      if (from != null) onReorderIndices(from, i);
                      setDragFrom(null);
                    }}
                    onClick={() => {
                      setDir(i > safeIdx ? 1 : -1);
                      setIdx(i);
                    }}
                    onKeyDown={(e) => {
                      if (e.key === "Enter" || e.key === " ") {
                        e.preventDefault();
                        setDir(i > safeIdx ? 1 : -1);
                        setIdx(i);
                      }
                    }}
                  >
                    {url ? (
                      <img
                        src={
                          mediaVersion
                            ? `${url}${url.includes("?") ? "&" : "?"}mv=${mediaVersion}`
                            : url
                        }
                        alt=""
                        draggable={false}
                      />
                    ) : (
                      <span className="presentation-thumb-ghost">{label}</span>
                    )}
                    <span>{String(i + 1).padStart(2, "0")}</span>
                  </div>
                );
              })}
            </div>
          ) : slidePngs.length > 0 ? (
            <div
              className="presentation-filmstrip"
              role="tablist"
              aria-label="Слайды"
            >
              {slidePngs.map((url, i) => {
                const t = (deck?.slides?.[i]?.title || "").trim();
                return (
                  <button
                    key={url}
                    type="button"
                    role="tab"
                    aria-selected={i === safeIdx}
                    className={`presentation-thumb${i === safeIdx ? " is-active" : ""}`}
                    title={t || `Слайд ${i + 1}`}
                    onClick={() => {
                      setDir(i > safeIdx ? 1 : -1);
                      setIdx(i);
                    }}
                  >
                    <img src={url} alt="" draggable={false} />
                    <span>{String(i + 1).padStart(2, "0")}</span>
                  </button>
                );
              })}
            </div>
          ) : null}
        </>
      )}

      {view === "slide" ? (
        <div className="presentation-toolbar">
          <button
            type="button"
            className="presentation-nav"
            onClick={() => go(-1)}
            aria-label="Назад"
          >
            ←
          </button>
          <span className="presentation-count">
            {safeIdx + 1} / {n}
          </span>
          <button
            type="button"
            className="presentation-nav"
            onClick={() => go(1)}
            aria-label="Вперёд"
          >
            →
          </button>
          <button
            type="button"
            className="presentation-nav"
            onClick={() => setView("grid")}
          >
            Все слайды
          </button>
          {live ? (
            <>
              <button
                type="button"
                className="presentation-nav"
                disabled={saving}
                onClick={() => {
                  const id = deck?.slides?.[safeIdx]?.id || null;
                  setPickerAfterId(id);
                  setPickerOpen(true);
                }}
                title="Добавить новый слайд после текущего"
              >
                + Слайд
              </button>
              <button
                type="button"
                className="presentation-nav"
                disabled={saving}
                onClick={() => {
                  const id = deck?.slides?.[safeIdx]?.id;
                  if (id) void structureOp({ op: "duplicate", id });
                }}
              >
                Дублировать
              </button>
              <button
                type="button"
                className="presentation-nav is-danger"
                disabled={saving || (deck?.slides?.length || 0) <= 1}
                onClick={async () => {
                  const id = deck?.slides?.[safeIdx]?.id;
                  if (!id) return;
                  const title =
                    deck?.slides?.[safeIdx]?.title || `Слайд ${safeIdx + 1}`;
                  const ok = await confirm({
                    title: "Удалить слайд?",
                    eyebrow: "презентация · структура",
                    message: `Удалить слайд «${title}»? PPTX и превью пересоберутся на столе.`,
                    confirmLabel: "Удалить слайд",
                    danger: true,
                  });
                  if (!ok) return;
                  void structureOp({ op: "delete", id });
                }}
              >
                Удалить
              </button>
            </>
          ) : null}
          {currentPng ? (
            <>
              <span className="presentation-toolbar-sep" aria-hidden />
              <button
                type="button"
                className="presentation-nav"
                onClick={() => {
                  if (fileBehind) {
                    onStaleDownload?.();
                    return;
                  }
                  void handleCopyPng();
                }}
                title={
                  fileBehind
                    ? "Сначала сохраните или отмените изменения"
                    : "Скопировать PNG слайда в буфер обмена"
                }
              >
                {copiedPng ? "Скопировано ✓" : "Копировать PNG"}
              </button>
              <button
                type="button"
                className="presentation-nav"
                onClick={() => {
                  if (fileBehind) {
                    onStaleDownload?.();
                    return;
                  }
                  void handleDownloadPng();
                }}
                title={
                  fileBehind
                    ? "Сначала сохраните или отмените изменения"
                    : "Скачать текущий слайд как PNG"
                }
              >
                {fileBehind ? "Сначала Готово" : "Скачать PNG"}
              </button>
            </>
          ) : null}
        </div>
      ) : null}

      {editing &&
      view === "slide" &&
      openMediaId &&
      openMediaKind === "chart" ? (
        <div className="presentation-media-sheet is-below-film" ref={mediaSheetRef}>
          <ChartEditSheet
            open
            trapFocus
            figureId={openMediaId}
            caption={
              deck?.slides?.[safeIdx]?.caption ||
              deck?.slides?.[safeIdx]?.title ||
              "График"
            }
            runId={runId}
            palettes={palettes}
            catalogTypes={catalogTypes}
            initialPalette={
              (openMediaId && chartIndex[openMediaId]?.palette) ||
              deck?.palette ||
              defaultPalette
            }
            initialType={(openMediaId && chartIndex[openMediaId]?.type) || ""}
            busy={editingFigureId === openMediaId || saving}
            onPreviewHtml={setChartPreview}
            error={editErrorFigureId === openMediaId ? editError : saveError}
            onCancel={closeMediaSheet}
            onSubmit={(req) => void submitChart(req)}
          />
        </div>
      ) : null}
      {editing &&
      view === "slide" &&
      openMediaId &&
      openMediaKind === "diagram" &&
      !openDiagram ? (
        <p className="presentation-media-wait">Открываю схему…</p>
      ) : null}
      {editing &&
      view === "slide" &&
      openMediaId &&
      openMediaKind === "diagram" &&
      openDiagram ? (
        <Suspense fallback={null}>
          <DiagramVisualEditor
            open
            diagramId={openDiagram.id}
            title={openDiagram.title}
            mermaid={openDiagram.mermaid}
            busy={saving}
            error={diagramError}
            onCancel={closeMediaSheet}
            onSave={(mermaid, title) => void saveDiagram(mermaid, title)}
          />
        </Suspense>
      ) : null}
      {editing &&
      view === "slide" &&
      openMediaId &&
      openMediaKind === "photo" ? (
        <div className="presentation-media-sheet is-below-film" ref={mediaSheetRef}>
          <ImageEditModal
            open
            trapFocus
            figureId={openMediaId}
            caption={
              deck?.slides?.[safeIdx]?.caption ||
              deck?.slides?.[safeIdx]?.title ||
              "Иллюстрация"
            }
            previewUrl={mediaUrl(runId, openMediaId, mediaVersion) || undefined}
            busy={editingFigureId === openMediaId || imageUploading || saving}
            error={
              imageUploadError ||
              (editErrorFigureId === openMediaId ? editError : saveError)
            }
            onCancel={closeMediaSheet}
            onSubmit={(req) => void submitImage(req)}
            onUpload={(file, caption) => void submitImageUpload(file, caption)}
          />
        </div>
      ) : null}

      {full ? (
        <PresentationFullscreen
          slides={slidePngs.length ? slidePngs : []}
          index={safeIdx}
          onIndex={(i) => {
            setDir(i > safeIdx ? 1 : -1);
            setIdx(i);
          }}
          onClose={() => setFull(false)}
          deck={live ? deck : null}
          runId={runId}
          diagramMermaid={
            diagrams.find((d) => d.id === deck?.slides?.[safeIdx]?.media_id)
              ?.mermaid || null
          }
          diagramPalette={deck?.palette || defaultPalette}
        />
      ) : null}

      {zoomDiagram ? (
        <DiagramFullscreen
          diagram={zoomDiagram}
          onClose={() => setZoomDiagram(null)}
        />
      ) : null}

      <LayoutPickerModal
        open={pickerOpen}
        onClose={() => setPickerOpen(false)}
        afterSlideNum={
          pickerAfterId && deck?.slides
            ? deck.slides.findIndex((s) => s.id === pickerAfterId) + 1
            : undefined
        }
        onPick={(layout) => {
          void structureOp({
            op: "insert",
            id: pickerAfterId || undefined,
            layout,
          });
        }}
      />
    </div>
  );
}
