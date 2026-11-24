/** Paste-long-text + file/photo ingest + drop for Liber composer. */

import {
  useCallback,
  useRef,
  type Dispatch,
  type DragEvent,
  type SetStateAction,
} from "react";
import { LONG_TEXT_CHARS } from "../domain/liberConstants";
import type { SourceDraft } from "../domain/liberTypes";
import { ATTACHED_TOAST, sourceCameFromScreen } from "../domain/sourceCopy";
import { mergeSourcePack } from "../domain/sourcePack";
import { readTextFile } from "../domain/runHelpers";
import { failedDashboardSnapshot, parseDashboard } from "../domain/dashboardParse";
import { paperclipAction } from "../domain/paperclipRoute";
import { ingestOfficeSource } from "../domain/sourceOfficeIngest";

type Deps = {
  setFile: Dispatch<SetStateAction<File | null>>;
  setSourceDraft: Dispatch<SetStateAction<SourceDraft | null>>;
  setPlaqueDismissed: Dispatch<SetStateAction<boolean>>;
  setDeckApplyHint: Dispatch<SetStateAction<string | null>>;
  setAttachPhotos: Dispatch<SetStateAction<File[]>>;
  setForbidImages: Dispatch<SetStateAction<boolean>>;
  setMaxImages: Dispatch<SetStateAction<number>>;
  setDrag: Dispatch<SetStateAction<boolean>>;
  showToast: (message: string, ms?: number) => void;
};

export function useSourceIngest({
  setFile,
  setSourceDraft,
  setPlaqueDismissed,
  setDeckApplyHint,
  setAttachPhotos,
  setForbidImages,
  setMaxImages,
  setDrag,
  showToast,
}: Deps) {
  const blobUrlRef = useRef<string | null>(null);

  const revokeBlob = useCallback(() => {
    if (blobUrlRef.current) {
      URL.revokeObjectURL(blobUrlRef.current);
      blobUrlRef.current = null;
    }
  }, []);

  const applySourceDraft = useCallback(
    (draft: SourceDraft) => {
      setFile(null);
      setSourceDraft((current) => {
        const merged = mergeSourcePack(current, draft);
        return { ...merged, fromScreen: sourceCameFromScreen(merged.text) };
      });
      setPlaqueDismissed(false);
      setDeckApplyHint(null);
    },
    [setFile, setSourceDraft, setPlaqueDismissed, setDeckApplyHint],
  );

  const capturePastedSource = useCallback(
    (text: string) => {
      const trimmed = text.trim();
      if (trimmed.length <= LONG_TEXT_CHARS) return false;
      revokeBlob();
      applySourceDraft({
        title: "Документ",
        text: trimmed,
        viewMode: "text",
      });
      return true;
    },
    [applySourceDraft, revokeBlob],
  );

  const ingestFiles = useCallback(
    (list: FileList | File[]) => {
      const arr = Array.from(list);
      for (const f of arr) {
        const action = paperclipAction(f);
        if (action === "text") {
          revokeBlob();
          setPlaqueDismissed(false);
          setDeckApplyHint(null);
          void (async () => {
            try {
              const out = await ingestOfficeSource(f);
              applySourceDraft({
                title: out.filename || f.name,
                text: out.markdown,
                fileName: out.filename || f.name,
                viewMode: "text",
                originalUrl: out.original_url || null,
                ingestId: out.ingest_id,
                format: out.format,
              });
              showToast(ATTACHED_TOAST, 2800);
            } catch {
              try {
                const text = await readTextFile(f);
                applySourceDraft({
                  title: f.name,
                  text,
                  fileName: f.name,
                  viewMode: "text",
                });
                showToast(ATTACHED_TOAST, 2800);
              } catch (err) {
                showToast(
                  err instanceof Error
                    ? err.message
                    : "Не удалось прочитать файл",
                );
              }
            }
          })();
          continue;
        }
        if (action === "office") {
          showToast(`Читаю ${f.name}…`, 8000);
          void (async () => {
            try {
              const out = await ingestOfficeSource(f);
              applySourceDraft({
                title: out.filename,
                text: out.markdown,
                fileName: out.filename,
                viewMode: "document",
                previewUrl: out.preview_url || null,
                originalUrl: out.original_url || null,
                ingestId: out.ingest_id,
                format: out.format,
              });
              if (out.warnings?.length) {
                showToast(out.warnings[0], 5000);
              } else {
                showToast(`Документ: ${out.filename}`, 2800);
              }
            } catch (err) {
              showToast(
                err instanceof Error
                  ? err.message
                  : "Не удалось разобрать документ",
                6000,
              );
            }
          })();
          continue;
        }
        if (action === "dashboard-png") {
          showToast(`Читаю ${f.name}…`, 8000);
          void (async () => {
            try {
              const out = await parseDashboard(f, null);
              applySourceDraft({
                title: f.name,
                text: out.markdown,
                fileName: f.name,
                viewMode: "text",
              });
              if (out.warnings.length) {
                showToast(out.warnings[0], 5000);
              } else {
                showToast(ATTACHED_TOAST, 2800);
              }
            } catch (err) {
              const message =
                err instanceof Error
                  ? err.message
                  : "Не удалось прочитать снимок.";
              showToast(failedDashboardSnapshot(message), 6000);
            }
          })();
          continue;
        }
        if (action === "photo") {
          setAttachPhotos((prev) => [...prev, f].slice(0, 5));
          setForbidImages(false);
          setMaxImages((n) => Math.max(n, 5));
        }
      }
    },
    [
      applySourceDraft,
      revokeBlob,
      setPlaqueDismissed,
      setDeckApplyHint,
      setAttachPhotos,
      setForbidImages,
      setMaxImages,
      showToast,
    ],
  );

  const onDrop = useCallback(
    (e: DragEvent) => {
      e.preventDefault();
      setDrag(false);
      if (e.dataTransfer.files?.length) ingestFiles(e.dataTransfer.files);
    },
    [ingestFiles, setDrag],
  );

  return { capturePastedSource, ingestFiles, onDrop };
}
