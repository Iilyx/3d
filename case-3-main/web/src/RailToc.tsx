/** Compact horizontal TOC chips from preview headings. */

import { useEffect, useRef } from "react";
import type { PreviewBlock } from "./domain/reportPreview";

export type TocItem = {
  id: string;
  level: number;
  text: string;
};

export function buildToc(blocks: PreviewBlock[] | undefined): TocItem[] {
  if (!blocks?.length) return [];
  const out: TocItem[] = [];
  let n = 0;
  for (const b of blocks) {
    if (b.type !== "heading") continue;
    n += 1;
    out.push({
      id: `rail-h-${n}`,
      level: b.level,
      text: b.text,
    });
  }
  return out;
}

type Props = {
  items: TocItem[];
  activeId?: string | null;
  onJump: (id: string) => void;
  onActiveChange?: (id: string) => void;
  /** Scroll root for IntersectionObserver (rail body). */
  root?: HTMLElement | null;
};

export function RailToc({
  items,
  activeId,
  onJump,
  onActiveChange,
  root,
}: Props) {
  const scrollerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!activeId || !scrollerRef.current) return;
    const chip = scrollerRef.current.querySelector<HTMLElement>(
      `[data-toc-id="${CSS.escape(activeId)}"]`,
    );
    chip?.scrollIntoView({
      behavior: "smooth",
      inline: "center",
      block: "nearest",
    });
  }, [activeId]);

  useEffect(() => {
    const scrollRoot =
      root ??
      (scrollerRef.current?.closest(
        ".artifact-rail-body, .rail-body",
      ) as HTMLElement | null);
    if (!scrollRoot || !onActiveChange || items.length < 2) return;
    const nodes = items
      .map((it) => scrollRoot.querySelector(`#${CSS.escape(it.id)}`))
      .filter(Boolean) as HTMLElement[];
    if (!nodes.length) return;

    const io = new IntersectionObserver(
      (entries) => {
        const visible = entries
          .filter((e) => e.isIntersecting)
          .sort((a, b) => a.boundingClientRect.top - b.boundingClientRect.top);
        const top = visible[0]?.target as HTMLElement | undefined;
        if (top?.id) onActiveChange(top.id);
      },
      // Top band under sticky TOC (~rail-toc height); root = .artifact-rail-body.
      { root: scrollRoot, rootMargin: "-12% 0px -70% 0px", threshold: [0, 0.15, 0.5, 1] },
    );
    for (const n of nodes) io.observe(n);
    return () => io.disconnect();
  }, [root, items, onActiveChange]);

  if (items.length < 2) return null;

  return (
    <nav className="rail-toc" aria-label="Содержание">
      <div className="rail-toc-scroll" ref={scrollerRef}>
        {items.map((it) => (
          <button
            key={it.id}
            type="button"
            data-toc-id={it.id}
            className={`rail-toc-chip${activeId === it.id ? " is-active" : ""}`}
            onClick={() => onJump(it.id)}
          >
            {it.text}
          </button>
        ))}
      </div>
    </nav>
  );
}
