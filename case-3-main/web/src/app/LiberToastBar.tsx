/** Transient Liber toast + optional undo. */

import type { ToastTone } from "./useLiberToast";

type Props = {
  toast: string | null;
  toastTone?: ToastTone;
  undoOffer: { msgId: string; runId: string } | null;
  onUndo: () => void;
};

export function LiberToastBar({
  toast,
  toastTone = "default",
  undoOffer,
  onUndo,
}: Props) {
  if (!toast) return null;
  const warn = toastTone === "warn" || /не собралась/i.test(toast);
  return (
    <div
      className={`liber-toast${warn ? " is-warn" : ""}`}
      role="status"
      aria-live="assertive"
    >
      <span>{toast}</span>
      {undoOffer ? (
        <button
          type="button"
          className="liber-toast-undo"
          onClick={() => void onUndo()}
        >
          Отменить
        </button>
      ) : null}
    </div>
  );
}
