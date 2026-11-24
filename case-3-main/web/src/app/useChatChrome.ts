/** Document title, stick-to-bottom chat scroll, composer autosize, last-report flag. */

import {
  useCallback,
  useEffect,
  useRef,
  useState,
  type Dispatch,
  type MutableRefObject,
  type RefObject,
  type SetStateAction,
} from "react";
import {
  computeScrollGap,
  nextStickOnScroll,
  nextStickOnWheel,
  stepSmoothScroll,
} from "../domain/chatScroll";
import type { Msg, RunResult } from "../domain/liberTypes";

type Deps = {
  chatTitle: string | null;
  msgs: Msg[];
  chat: string;
  messagesRef: RefObject<HTMLDivElement | null>;
  bottomRef: RefObject<HTMLDivElement | null>;
  chatRef: RefObject<HTMLTextAreaElement | null>;
  stickBottom: MutableRefObject<boolean>;
  setHasStoredReport: Dispatch<SetStateAction<boolean>>;
};

export function useChatChrome({
  chatTitle,
  msgs,
  chat,
  messagesRef,
  bottomRef,
  chatRef,
  stickBottom,
  setHasStoredReport,
}: Deps) {
  const [showScrollBottom, setShowScrollBottom] = useState(false);
  const rafRef = useRef<number | null>(null);
  const lastScrollTopRef = useRef(0);
  const programmaticScrollRef = useRef(false);
  const prevMsgCountRef = useRef(msgs.length);
  const touchStartYRef = useRef<number | null>(null);

  useEffect(() => {
    document.title = chatTitle ? `${chatTitle} · Liber` : "Liber";
  }, [chatTitle]);

  const stopScrollLoop = useCallback(() => {
    if (rafRef.current !== null) {
      window.cancelAnimationFrame(rafRef.current);
      rafRef.current = null;
    }
  }, []);

  const syncScrollBottomFlag = useCallback(
    (el: HTMLDivElement) => {
      const gap = computeScrollGap(el);
      const show = !stickBottom.current && gap > 160 && msgs.length > 0;
      setShowScrollBottom((prev) => (prev === show ? prev : show));
    },
    [msgs.length, stickBottom],
  );

  const startSmoothFollow = useCallback(
    (instant = false) => {
      const el = messagesRef.current;
      if (!el) return;
      const targetTop = Math.max(0, el.scrollHeight - el.clientHeight);
      if (
        instant ||
        window.matchMedia?.("(prefers-reduced-motion: reduce)").matches
      ) {
        stopScrollLoop();
        programmaticScrollRef.current = true;
        el.scrollTop = targetTop;
        lastScrollTopRef.current = el.scrollTop;
        programmaticScrollRef.current = false;
        syncScrollBottomFlag(el);
        return;
      }
      if (rafRef.current !== null) return;
      let prevTs = performance.now();
      const step = (ts: number) => {
        rafRef.current = null;
        const node = messagesRef.current;
        if (!node || !stickBottom.current) return;
        const dt = ts - prevTs;
        prevTs = ts;
        const maxTop = Math.max(0, node.scrollHeight - node.clientHeight);
        if (Math.abs(maxTop - node.scrollTop) <= 1) {
          programmaticScrollRef.current = true;
          node.scrollTop = maxTop;
          lastScrollTopRef.current = node.scrollTop;
          programmaticScrollRef.current = false;
          syncScrollBottomFlag(node);
          return;
        }
        const nextTop = stepSmoothScroll(node.scrollTop, maxTop, dt);
        programmaticScrollRef.current = true;
        node.scrollTop = nextTop;
        lastScrollTopRef.current = node.scrollTop;
        programmaticScrollRef.current = false;
        if (Math.abs(maxTop - node.scrollTop) > 1 && stickBottom.current) {
          rafRef.current = window.requestAnimationFrame(step);
        } else {
          syncScrollBottomFlag(node);
        }
      };
      rafRef.current = window.requestAnimationFrame(step);
    },
    [messagesRef, stickBottom, stopScrollLoop, syncScrollBottomFlag],
  );

  const scrollToBottom = useCallback(() => {
    stickBottom.current = true;
    setShowScrollBottom(false);
    startSmoothFollow(false);
  }, [stickBottom, startSmoothFollow]);

  useEffect(() => {
    const el = messagesRef.current;
    if (!el) return;
    lastScrollTopRef.current = el.scrollTop;

    const disengage = () => {
      if (stickBottom.current) {
        stickBottom.current = false;
      }
      stopScrollLoop();
      syncScrollBottomFlag(el);
    };

    const onWheel = (e: WheelEvent) => {
      if (!nextStickOnWheel(e.deltaY, stickBottom.current)) {
        disengage();
      }
    };

    const onTouchStart = (e: TouchEvent) => {
      touchStartYRef.current = e.touches[0]?.clientY ?? null;
    };

    const onTouchMove = (e: TouchEvent) => {
      const y = e.touches[0]?.clientY;
      if (y == null || touchStartYRef.current == null) return;
      // Dragging finger downward scrolls content upward.
      if (y - touchStartYRef.current > 4) {
        disengage();
      }
      touchStartYRef.current = y;
    };

    const onScroll = () => {
      if (programmaticScrollRef.current) {
        lastScrollTopRef.current = el.scrollTop;
        return;
      }
      const next = nextStickOnScroll(
        stickBottom.current,
        {
          scrollHeight: el.scrollHeight,
          scrollTop: el.scrollTop,
          clientHeight: el.clientHeight,
        },
        lastScrollTopRef.current,
      );
      lastScrollTopRef.current = next.scrollTop;
      if (!next.stick) {
        stickBottom.current = false;
        stopScrollLoop();
      } else {
        stickBottom.current = true;
      }
      syncScrollBottomFlag(el);
    };

    el.addEventListener("wheel", onWheel, { passive: true });
    el.addEventListener("touchstart", onTouchStart, { passive: true });
    el.addEventListener("touchmove", onTouchMove, { passive: true });
    el.addEventListener("scroll", onScroll, { passive: true });
    return () => {
      el.removeEventListener("wheel", onWheel);
      el.removeEventListener("touchstart", onTouchStart);
      el.removeEventListener("touchmove", onTouchMove);
      el.removeEventListener("scroll", onScroll);
    };
  }, [messagesRef, stickBottom, stopScrollLoop, syncScrollBottomFlag]);

  // Follow async height changes (inline charts, PDF thumbs, rail resize) only when pinned to bottom.
  useEffect(() => {
    const el = messagesRef.current;
    if (!el) return;
    let lastHeight = el.scrollHeight;
    const onMediaLoad = () => {
      if (stickBottom.current) {
        startSmoothFollow(false);
      } else {
        syncScrollBottomFlag(el);
      }
    };
    el.addEventListener("load", onMediaLoad, true);
    const ro =
      typeof ResizeObserver !== "undefined"
        ? new ResizeObserver(() => {
            if (el.scrollHeight !== lastHeight) {
              lastHeight = el.scrollHeight;
              if (stickBottom.current) {
                startSmoothFollow(false);
              } else {
                syncScrollBottomFlag(el);
              }
            }
          })
        : null;
    ro?.observe(el);
    return () => {
      el.removeEventListener("load", onMediaLoad, true);
      ro?.disconnect();
    };
  }, [messagesRef, stickBottom, startSmoothFollow, syncScrollBottomFlag]);

  useEffect(() => {
    const el = messagesRef.current;
    // Re-stick when user starts a new turn or opens a fresh thread.
    const prevCount = prevMsgCountRef.current;
    prevMsgCountRef.current = msgs.length;
    if (msgs.length === 0) {
      stickBottom.current = true;
      setShowScrollBottom(false);
      stopScrollLoop();
      return;
    }
    if (msgs.length > prevCount) {
      const added = msgs.slice(prevCount);
      if (added.some((m) => m.role === "user")) {
        stickBottom.current = true;
        setShowScrollBottom(false);
      }
    }

    if (/preview=(artifact|deck)/.test(window.location.search)) {
      stickBottom.current = true;
      startSmoothFollow(true);
      const t1 = window.setTimeout(() => startSmoothFollow(true), 120);
      const t2 = window.setTimeout(() => startSmoothFollow(true), 480);
      return () => {
        window.clearTimeout(t1);
        window.clearTimeout(t2);
      };
    }

    if (stickBottom.current) {
      startSmoothFollow(false);
    } else if (el) {
      syncScrollBottomFlag(el);
    }
    void bottomRef;
  }, [
    msgs,
    messagesRef,
    bottomRef,
    stickBottom,
    startSmoothFollow,
    stopScrollLoop,
    syncScrollBottomFlag,
  ]);

  useEffect(() => () => stopScrollLoop(), [stopScrollLoop]);

  useEffect(() => {
    const el = chatRef.current;
    if (!el) return;
    el.style.height = "0px";
    const next = Math.min(Math.max(el.scrollHeight, 44), 112);
    el.style.height = `${next}px`;
  }, [chat, chatRef]);

  useEffect(() => {
    try {
      const raw = sessionStorage.getItem("liber-last-report");
      if (!raw) {
        setHasStoredReport(false);
        return;
      }
      const result = JSON.parse(raw) as RunResult;
      setHasStoredReport(Boolean(result?.preview?.blocks?.length));
    } catch {
      setHasStoredReport(false);
    }
  }, [msgs, setHasStoredReport]);

  return { showScrollBottom, scrollToBottom };
}
