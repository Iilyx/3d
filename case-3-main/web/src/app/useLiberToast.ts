/** Short Liber toast messages (status + optional clear timer). */

import { useCallback, useRef, useState } from "react";

export type ToastTone = "default" | "warn";

export function useLiberToast() {
  const [toast, setToastRaw] = useState<string | null>(null);
  const [toastTone, setToastTone] = useState<ToastTone>("default");
  const timerRef = useRef<number | null>(null);

  const clearToast = useCallback(() => {
    if (timerRef.current != null) {
      window.clearTimeout(timerRef.current);
      timerRef.current = null;
    }
    setToastRaw(null);
    setToastTone("default");
  }, []);

  const setToast = useCallback(
    (value: string | null | ((prev: string | null) => string | null)) => {
      setToastRaw((prev) => {
        const next = typeof value === "function" ? value(prev) : value;
        if (next == null) setToastTone("default");
        else if (/не собралась/i.test(next)) setToastTone("warn");
        return next;
      });
    },
    [],
  );

  const showToast = useCallback(
    (message: string, ms = 2800, tone: ToastTone = "default") => {
      const nextTone =
        tone !== "default"
          ? tone
          : /не собралась/i.test(message)
            ? "warn"
            : "default";
      setToastTone(nextTone);
      setToastRaw(message);
      if (timerRef.current != null) window.clearTimeout(timerRef.current);
      timerRef.current = window.setTimeout(() => {
        timerRef.current = null;
        setToastRaw(null);
        setToastTone("default");
      }, ms);
    },
    [],
  );

  return { toast, toastTone, setToast, showToast, clearToast };
}
