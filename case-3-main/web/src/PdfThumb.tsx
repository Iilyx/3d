/** First PDF page → data URL thumb for ArtifactCard (cached, lazy pdf.js). */

import { useEffect, useState } from "react";

const cache = new Map<string, string>();

function cacheKey(url: string, targetW: number): string {
  return `${url}@@${targetW}`;
}

async function renderThumb(url: string, targetW: number): Promise<string> {
  const key = cacheKey(url, targetW);
  const hit = cache.get(key);
  if (hit) return hit;
  const pdfjs = await import("pdfjs-dist");
  const pdfWorker = (
    await import("pdfjs-dist/build/pdf.worker.min.mjs?url")
  ).default;
  pdfjs.GlobalWorkerOptions.workerSrc = pdfWorker;
  const doc = await pdfjs.getDocument({ url, withCredentials: false }).promise;
  try {
    const page = await doc.getPage(1);
    const base = page.getViewport({ scale: 1 });
    const scale = targetW / base.width;
    const viewport = page.getViewport({ scale });
    const canvas = document.createElement("canvas");
    canvas.width = Math.floor(viewport.width);
    canvas.height = Math.floor(viewport.height);
    const ctx = canvas.getContext("2d");
    if (!ctx) throw new Error("no canvas");
    await page.render({ canvasContext: ctx, viewport }).promise;
    const data = canvas.toDataURL("image/jpeg", 0.86);
    cache.set(key, data);
    return data;
  } finally {
    void doc.destroy();
  }
}

type Props = {
  pdfUrl?: string | null;
  fallbackUrl?: string | null;
  className?: string;
  /** Render width in CSS px (higher for Julius large cards). */
  targetWidth?: number;
};

export function PdfThumb({
  pdfUrl,
  fallbackUrl,
  className = "",
  targetWidth = 160,
}: Props) {
  const [src, setSrc] = useState<string | null>(() => {
    if (pdfUrl) {
      const hit = cache.get(cacheKey(pdfUrl, targetWidth));
      if (hit) return hit;
    }
    return fallbackUrl || null;
  });
  const [failed, setFailed] = useState(false);
  const [loading, setLoading] = useState(() => {
    if (!pdfUrl) return false;
    return !cache.has(cacheKey(pdfUrl, targetWidth));
  });

  useEffect(() => {
    let cancelled = false;
    if (!pdfUrl) {
      setSrc(fallbackUrl || null);
      setLoading(false);
      setFailed(false);
      return;
    }
    const cached = cache.get(cacheKey(pdfUrl, targetWidth));
    if (cached) {
      setSrc(cached);
      setLoading(false);
      setFailed(false);
      return;
    }
    setFailed(false);
    setLoading(true);
    setSrc(null);
    void (async () => {
      try {
        const data = await renderThumb(pdfUrl, targetWidth);
        if (!cancelled) {
          setSrc(data);
          setLoading(false);
        }
      } catch {
        if (!cancelled) {
          setFailed(true);
          setLoading(false);
          setSrc(fallbackUrl || null);
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [pdfUrl, fallbackUrl, targetWidth]);

  if (src) {
    return (
      <img
        className={`pdf-thumb-img${className ? ` ${className}` : ""}`}
        src={src}
        alt=""
      />
    );
  }

  if (loading) {
    return (
      <span
        className={`pdf-thumb-skeleton${className ? ` ${className}` : ""}`}
        aria-busy="true"
        aria-label="Загрузка превью PDF"
      >
        <span className="pdf-thumb-skeleton-shine" aria-hidden />
        <span className="pdf-thumb-skeleton-page" aria-hidden>
          <span className="pdf-thumb-skeleton-bar is-title" />
          <span className="pdf-thumb-skeleton-bar" />
          <span className="pdf-thumb-skeleton-bar is-mid" />
          <span className="pdf-thumb-skeleton-bar is-short" />
          <span className="pdf-thumb-skeleton-block" />
        </span>
      </span>
    );
  }

  return (
    <span
      className={`artifact-card-thumb-fallback${failed ? " is-soft" : ""}${className ? ` ${className}` : ""}`}
    >
      PDF
    </span>
  );
}
