import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useId,
  useRef,
  useState,
  type ReactNode,
} from "react";
import { useFocusTrap } from "./useFocusTrap";

export interface ConfirmOptions {
  title: string;
  eyebrow?: string;
  message: string;
  confirmLabel?: string;
  cancelLabel?: string;
  danger?: boolean;
}

export interface NormalizedConfirmOptions {
  title: string;
  eyebrow: string;
  message: string;
  confirmLabel: string;
  cancelLabel: string;
  danger: boolean;
}

export function normalizeConfirmOptions(
  raw: ConfirmOptions,
): NormalizedConfirmOptions {
  const isDanger =
    raw.danger !== undefined
      ? Boolean(raw.danger)
      : /удалить|delete|remove/i.test(
          `${raw.title} ${raw.message} ${raw.confirmLabel || ""}`,
        );

  return {
    title: raw.title,
    eyebrow: raw.eyebrow?.trim() || "liber · подтверждение",
    message: raw.message,
    confirmLabel:
      raw.confirmLabel?.trim() || (isDanger ? "Удалить" : "Подтвердить"),
    cancelLabel: raw.cancelLabel?.trim() || "Отмена",
    danger: isDanger,
  };
}

interface ConfirmState {
  options: NormalizedConfirmOptions;
  resolve: (value: boolean) => void;
}

const ConfirmContext = createContext<
  ((opts: ConfirmOptions) => Promise<boolean>) | null
>(null);

export function useConfirm(): (opts: ConfirmOptions) => Promise<boolean> {
  const ctx = useContext(ConfirmContext);
  if (!ctx) {
    // Graceful fallback for isolated tests/contexts
    return (opts: ConfirmOptions) =>
      Promise.resolve(
        typeof window !== "undefined" && typeof window.confirm === "function"
          ? window.confirm(`${opts.title}\n\n${opts.message}`)
          : true,
      );
  }
  return ctx;
}

export function ConfirmProvider({ children }: { children: ReactNode }) {
  const [active, setActive] = useState<ConfirmState | null>(null);

  const confirm = useCallback((opts: ConfirmOptions): Promise<boolean> => {
    const normalized = normalizeConfirmOptions(opts);
    return new Promise<boolean>((resolve) => {
      setActive({ options: normalized, resolve });
    });
  }, []);

  const handleCancel = useCallback(() => {
    if (active) {
      active.resolve(false);
      setActive(null);
    }
  }, [active]);

  const handleConfirm = useCallback(() => {
    if (active) {
      active.resolve(true);
      setActive(null);
    }
  }, [active]);

  return (
    <ConfirmContext.Provider value={confirm}>
      {children}
      {active && (
        <ConfirmDialog
          options={active.options}
          onConfirm={handleConfirm}
          onCancel={handleCancel}
        />
      )}
    </ConfirmContext.Provider>
  );
}

interface ConfirmDialogProps {
  options: NormalizedConfirmOptions;
  onConfirm: () => void;
  onCancel: () => void;
}

export function ConfirmDialog({
  options,
  onConfirm,
  onCancel,
}: ConfirmDialogProps) {
  const titleId = useId();
  const dialogRef = useRef<HTMLDivElement>(null);
  const cancelBtnRef = useRef<HTMLButtonElement>(null);

  useFocusTrap(dialogRef, { active: true });

  useEffect(() => {
    const prev = document.body.style.overflow;
    document.body.style.overflow = "hidden";

    // Auto-focus the cancel button for safety
    cancelBtnRef.current?.focus();

    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        e.preventDefault();
        onCancel();
      } else if (e.key === "Enter" && document.activeElement !== cancelBtnRef.current) {
        e.preventDefault();
        onConfirm();
      }
    };

    window.addEventListener("keydown", onKey);
    return () => {
      window.removeEventListener("keydown", onKey);
      document.body.style.overflow = prev;
    };
  }, [onCancel, onConfirm]);

  return (
    <div
      ref={dialogRef}
      className="liber-confirm-modal"
      role="dialog"
      aria-modal="true"
      aria-labelledby={titleId}
      onMouseDown={(e) => {
        if (e.target === e.currentTarget) onCancel();
      }}
    >
      <div className="liber-confirm-sheet" role="document">
        <header className="liber-confirm-head">
          <p className="liber-confirm-eyebrow">{options.eyebrow}</p>
          <h3 id={titleId} className="liber-confirm-title">
            {options.title}
          </h3>
        </header>

        <div className="liber-confirm-body">
          <p className="liber-confirm-message">{options.message}</p>
        </div>

        <footer className="liber-confirm-actions">
          <button
            ref={cancelBtnRef}
            type="button"
            className="liber-confirm-btn is-cancel"
            onClick={onCancel}
          >
            {options.cancelLabel}
          </button>
          <button
            type="button"
            className={`liber-confirm-btn ${options.danger ? "is-danger" : "is-primary"}`}
            onClick={onConfirm}
          >
            {options.confirmLabel}
          </button>
        </footer>
      </div>
    </div>
  );
}
