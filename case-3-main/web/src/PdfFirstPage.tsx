/** PDF page slider (pdf.js). Figure→PDF jump: load → optional text find → render (no races). */

import { useCallback, useEffect, useRef, useState } from "react";
import * as pdfjs from "pdfjs-dist";
import type { PDFDocumentProxy, RenderTask } from "pdfjs-dist";
import pdfWorker from "pdfjs-dist/build/pdf.worker.min.mjs?url";
import { bestPageForNeedles } from "./pdfFindPage";

pdfjs.GlobalWorkerOptions.workerSrc = pdfWorker;

type Props = {
  url: string;
  /** Jump to this page when it changes (1-based). */
  page?: number;
  /** Caption / id needles from figure→PDF click. */
  findNeedles?: string[] | null;
  /** Bumps on each jump so same figure re-searches. */
  findToken?: number | null;
  onPageChange?: (page: number, pageCount: number) => void;
};

async function findPageByNeedles(
  doc: PDFDocumentProxy,
  needles: string[],
): Promise<number | null> {
  const list = needles.map((n) => n.trim()).filter((n) => n.length >= 3);
  if (!list.length) return null;
  const pageTexts: string[] = [];
  for (let i = 1; i <= doc.numPages; i++) {
    const pdfPage = await doc.getPage(i);
    const tc = await pdfPage.getTextContent();
    pageTexts.push(
      tc.items
        .map((it) =>
          typeof it === "object" && it && "str" in it
            ? String((it as { str: string }).str)
            : "",
        )
        .join(" "),
    );
  }
  return bestPageForNeedles(pageTexts, list);
}

export function PdfFirstPage({
  url,
  page: pageProp,
  findNeedles,
  findToken,
  onPageChange,
}: Props) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const docRef = useRef<PDFDocumentProxy | null>(null);
  const renderTaskRef = useRef<RenderTask | null>(null);
  const [page, setPage] = useState(1);
  const [pageCount, setPageCount] = useState(0);
  const [err, setErr] = useState<string | null>(null);
  const [ready, setReady] = useState(false);
  const [drawing, setDrawing] = useState(false);
  const renderGen = useRef(0);
  const onPageChangeRef = useRef(onPageChange);
  onPageChangeRef.current = onPageChange;
  const findNeedlesRef = useRef(findNeedles);
  findNeedlesRef.current = findNeedles;
  const findTokenRef = useRef(findToken);
  findTokenRef.current = findToken;
  const pagePropRef = useRef(pageProp);
  pagePropRef.current = pageProp;
  /** Last findToken already applied (cold load or live jump). */
  const appliedFindRef = useRef<number | null>(null);

  const cancelRender = useCallback(() => {
    const task = renderTaskRef.current;
    renderTaskRef.current = null;
    if (task) {
      try {
        task.cancel();
      } catch {
        /* ignore */
      }
    }
  }, []);

  const renderPage = useCallback(
    async (doc: PDFDocumentProxy, n: number) => {
      const canvas = canvasRef.current;
      if (!canvas) return;
      const gen = ++renderGen.current;
      cancelRender();
      setDrawing(true);
      try {
        const pdfPage = await doc.getPage(n);
        if (gen !== renderGen.current) return;
        const base = pdfPage.getViewport({ scale: 1 });
        const stage = canvas.parentElement;
        // Leave room for prev/next nav buttons inside .report-pdf-stage
        const navSlack = stage?.querySelectorAll(".report-pdf-nav").length
          ? 56
          : 0;
        const parentW = Math.max(
          320,
          (stage?.clientWidth || canvas.parentElement?.clientWidth || 680) -
            navSlack,
        );
        // Fit container width; no artificial 840px soft-cap (blurred upscale).
        const cssScale = Math.max(0.85, parentW / base.width);
        const dpr = Math.min(
          typeof window !== "undefined" ? window.devicePixelRatio || 1 : 1,
          3,
        );
        // Render denser than CSS pixels so Retina stays sharp.
        let renderScale = cssScale * dpr;
        const maxPx = 4096;
        if (base.width * renderScale > maxPx) {
          renderScale = maxPx / base.width;
        }
        const viewport = pdfPage.getViewport({ scale: renderScale });
        const cssW = Math.floor(base.width * cssScale);
        const cssH = Math.floor(base.height * cssScale);
        const ctx = canvas.getContext("2d", { alpha: false });
        if (!ctx) throw new Error("no canvas");
        canvas.width = Math.floor(viewport.width);
        canvas.height = Math.floor(viewport.height);
        canvas.style.width = `${cssW}px`;
        canvas.style.height = `${cssH}px`;
        ctx.imageSmoothingEnabled = true;
        ctx.imageSmoothingQuality = "high";
        const task = pdfPage.render({
          canvasContext: ctx,
          viewport,
          // intent improves glyph hinting in recent pdf.js
          intent: "display",
        } as Parameters<typeof pdfPage.render>[0]);
        renderTaskRef.current = task;
        await task.promise;
        if (gen !== renderGen.current) return;
        setReady(true);
        setErr(null);
      } catch (e) {
        // pdf.js cancel → RenderingCancelledException — not a real failure
        const name = e && typeof e === "object" && "name" in e ? String((e as { name: string }).name) : "";
        const msg = e instanceof Error ? e.message : String(e);
        if (
          name.includes("Cancel") ||
          /cancel/i.test(msg) ||
          gen !== renderGen.current
        ) {
          return;
        }
        throw e;
      } finally {
        if (gen === renderGen.current) {
          renderTaskRef.current = null;
          setDrawing(false);
        }
      }
    },
    [cancelRender],
  );

  // Load document once per URL. If mount came from a figure jump, find page
  // before the first paint (avoids render↔getTextContent races).
  useEffect(() => {
    let cancelled = false;
    setErr(null);
    setReady(false);
    setPage(1);
    setPageCount(0);
    appliedFindRef.current = null;
    cancelRender();
    const prev = docRef.current;
    docRef.current = null;
    if (prev) void prev.destroy();
    if (!url) return;

    (async () => {
      try {
        const doc = await pdfjs
          .getDocument({ url, withCredentials: false })
          .promise;
        if (cancelled) {
          void doc.destroy();
          return;
        }
        docRef.current = doc;
        const nPages = doc.numPages;
        setPageCount(nPages);

        let start =
          pagePropRef.current && pagePropRef.current >= 1
            ? Math.min(pagePropRef.current, nPages)
            : 1;

        const token = findTokenRef.current;
        const needles = findNeedlesRef.current;
        if (token != null && needles?.length) {
          try {
            const found = await findPageByNeedles(doc, needles);
            if (!cancelled && found != null) start = found;
            if (!cancelled) appliedFindRef.current = token;
          } catch {
            /* keep hint */
          }
        }

        if (cancelled) return;
        setPage(start);
        onPageChangeRef.current?.(start, nPages);
      } catch (e) {
        if (!cancelled) {
          setErr(e instanceof Error ? e.message : "PDF preview failed");
        }
      }
    })();

    return () => {
      cancelled = true;
      cancelRender();
      const d = docRef.current;
      docRef.current = null;
      if (d) void d.destroy();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps -- reload only on url
  }, [url]);

  // Jump while PDF tab already open: search without reloading the document.
  // (Do NOT sync pageProp→page after load — TeX hints are often «1» and would
  // clobber a successful caption find that landed on page 2+.)
  useEffect(() => {
    if (findToken == null || !findNeedles?.length || pageCount < 1) return;
    if (appliedFindRef.current === findToken) return;
    const doc = docRef.current;
    if (!doc) return;
    let cancelled = false;
    (async () => {
      try {
        const found = await findPageByNeedles(doc, findNeedles);
        if (cancelled) return;
        appliedFindRef.current = findToken;
        if (found == null) return;
        setPage(found);
        onPageChangeRef.current?.(found, pageCount);
      } catch {
        /* keep current */
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [findToken, findNeedles, pageCount]);

  useEffect(() => {
    const doc = docRef.current;
    if (!doc || pageCount < 1) return;
    let cancelled = false;
    (async () => {
      try {
        await renderPage(doc, page);
      } catch (e) {
        if (!cancelled) {
          setErr(e instanceof Error ? e.message : "PDF page failed");
        }
      }
    })();
    return () => {
      cancelled = true;
      cancelRender();
    };
  }, [page, pageCount, renderPage, cancelRender]);

  // Re-render sharp when the rail / Source pane is resized (HiDPI fit).
  useEffect(() => {
    const canvas = canvasRef.current;
    const stage = canvas?.parentElement;
    if (!stage || pageCount < 1) return;
    let timer: number | null = null;
    const ro = new ResizeObserver(() => {
      if (timer != null) window.clearTimeout(timer);
      timer = window.setTimeout(() => {
        const doc = docRef.current;
        if (!doc) return;
        void renderPage(doc, page).catch(() => {
          /* keep last frame */
        });
      }, 120);
    });
    ro.observe(stage);
    return () => {
      ro.disconnect();
      if (timer != null) window.clearTimeout(timer);
    };
  }, [page, pageCount, renderPage]);

  const go = useCallback(
    (delta: number) => {
      setPage((p) => {
        if (pageCount < 1) return p;
        const next = Math.min(pageCount, Math.max(1, p + delta));
        onPageChangeRef.current?.(next, pageCount);
        return next;
      });
    },
    [pageCount],
  );

  useEffect(() => {
    if (pageCount < 2) return;
    const onKey = (e: KeyboardEvent) => {
      const t = e.target as HTMLElement | null;
      if (
        t &&
        (t.tagName === "INPUT" ||
          t.tagName === "TEXTAREA" ||
          t.isContentEditable)
      ) {
        return;
      }
      if (e.key === "ArrowLeft") {
        e.preventDefault();
        go(-1);
      } else if (e.key === "ArrowRight") {
        e.preventDefault();
        go(1);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [go, pageCount]);

  const multi = pageCount > 1;

  return (
    <figure className={`report-pdf-page${ready ? " is-ready" : ""}`}>
      <div className="report-pdf-stage">
        {!ready && !err && (
          <div className="pdf-skeleton" aria-hidden>
            <div className="pdf-skeleton-shine" />
            <div className="pdf-skeleton-lines">
              <i style={{ width: "48%" }} />
              <i style={{ width: "92%" }} />
              <i style={{ width: "78%" }} />
              <i style={{ width: "86%" }} />
              <i style={{ width: "64%" }} />
            </div>
          </div>
        )}
        {multi && (
          <button
            type="button"
            className="report-pdf-nav prev"
            onClick={() => go(-1)}
            disabled={page <= 1 || drawing}
            aria-label="Предыдущая страница"
          >
            ‹
          </button>
        )}
        <canvas
          ref={canvasRef}
          className={ready ? "is-shown" : "is-hidden"}
          aria-label={`Страница ${page} из ${pageCount || "…"} PDF`}
        />
        {multi && (
          <button
            type="button"
            className="report-pdf-nav next"
            onClick={() => go(1)}
            disabled={page >= pageCount || drawing}
            aria-label="Следующая страница"
          >
            ›
          </button>
        )}
      </div>
      <figcaption className="report-pdf-cap">
        {err ? (
          "Превью PDF недоступно — скачайте файл"
        ) : pageCount ? (
          <div className="report-pdf-toolbar">
            <span className="report-pdf-counter">
              Стр. {page} / {pageCount} · как в PDF
            </span>
          </div>
        ) : (
          "Загрузка PDF…"
        )}
      </figcaption>
    </figure>
  );
}
