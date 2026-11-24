/** Mini Liber-desk chart glyphs + hover card for type chips. */

import {
  useCallback,
  useId,
  useRef,
  useState,
  type ReactNode,
} from "react";
import { createPortal } from "react-dom";

const INK = "#121212";
const OLIVE = "#1a1a1a";
const MOSS = "#4a4a4a";
const CREAM = "#ececeb";
const PAPER = "#f7f7f5";
const ACCENT = "#8a8a86";
const MUTED = "#6b6b6b";

export type ChartTypeId =
  | "area"
  | "bar"
  | "donut"
  | "grouped_bar"
  | "horizontal_bar"
  | "kpi"
  | "line"
  | "scatter"
  | "stacked_bar"
  | "auto";

const META: Record<
  ChartTypeId,
  { title: string; chip: string; blurb: string; Glyph: () => ReactNode }
> = {
  auto: {
    title: "На усмотрение",
    chip: "авто",
    blurb: "Автоматический подбор под данные",
    Glyph: GlyphAuto,
  },
  area: {
    title: "Область",
    chip: "область",
    blurb: "Тренд с заливкой под линией",
    Glyph: GlyphArea,
  },
  bar: {
    title: "Столбцы",
    chip: "столбцы",
    blurb: "Сравнение категорий по высоте",
    Glyph: GlyphBar,
  },
  donut: {
    title: "Кольцо",
    chip: "кольцо",
    blurb: "Доли и структура целого",
    Glyph: GlyphDonut,
  },
  grouped_bar: {
    title: "Группы",
    chip: "группы",
    blurb: "Несколько серий рядом",
    Glyph: GlyphGrouped,
  },
  horizontal_bar: {
    title: "Горизонт",
    chip: "горизонт",
    blurb: "Рейтинг / топ‑N слева направо",
    Glyph: GlyphHBar,
  },
  kpi: {
    title: "KPI",
    chip: "KPI",
    blurb: "Одна крупная цифра с подписью",
    Glyph: GlyphKpi,
  },
  line: {
    title: "Линия",
    chip: "линия",
    blurb: "Динамика во времени",
    Glyph: GlyphLine,
  },
  scatter: {
    title: "Точки",
    chip: "точки",
    blurb: "Связь двух числовых осей",
    Glyph: GlyphScatter,
  },
  stacked_bar: {
    title: "Стек",
    chip: "стек",
    blurb: "Состав столбца по слоям",
    Glyph: GlyphStacked,
  },
};

/** Short Liber label for type chips / badges. */
export function chartTypeChipLabel(typeId: string): string {
  return metaFor(typeId).chip;
}

function Frame({ children }: { children: ReactNode }) {
  return (
    <svg
      viewBox="0 0 160 96"
      width="160"
      height="96"
      aria-hidden
      className="chart-preview-svg"
    >
      <rect x="0" y="0" width="160" height="96" rx="10" fill={PAPER} />
      <rect
        x="0.5"
        y="0.5"
        width="159"
        height="95"
        rx="9.5"
        fill="none"
        stroke="rgba(25,25,25,0.06)"
      />
      {children}
    </svg>
  );
}

function GlyphLine() {
  return (
    <Frame>
      <polyline
        points="18,72 42,58 66,62 90,40 114,48 142,28"
        fill="none"
        stroke={OLIVE}
        strokeWidth="2.4"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      {[
        [18, 72],
        [42, 58],
        [66, 62],
        [90, 40],
        [114, 48],
        [142, 28],
      ].map(([x, y]) => (
        <circle key={`${x}-${y}`} cx={x} cy={y} r="3.2" fill={ACCENT} />
      ))}
    </Frame>
  );
}

function GlyphArea() {
  return (
    <Frame>
      <path
        d="M18,74 L42,56 L66,60 L90,38 L114,46 L142,26 L142,78 L18,78 Z"
        fill={CREAM}
        opacity="0.95"
      />
      <polyline
        points="18,74 42,56 66,60 90,38 114,46 142,26"
        fill="none"
        stroke={OLIVE}
        strokeWidth="2.2"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </Frame>
  );
}

function GlyphBar() {
  const bars = [
    [28, 52, 18],
    [56, 38, 18],
    [84, 28, 18],
    [112, 44, 18],
  ];
  return (
    <Frame>
      {bars.map(([x, y, w], i) => (
        <rect
          key={x}
          x={x}
          y={y}
          width={w}
          height={78 - y}
          rx="3"
          fill={i === 2 ? ACCENT : OLIVE}
          opacity={i === 1 ? 0.75 : 1}
        />
      ))}
    </Frame>
  );
}

function GlyphHBar() {
  const rows = [
    [22, 22, 110],
    [22, 42, 82],
    [22, 62, 58],
  ];
  return (
    <Frame>
      {rows.map(([x, y, w], i) => (
        <rect
          key={y}
          x={x}
          y={y}
          width={w}
          height="12"
          rx="3"
          fill={i === 0 ? ACCENT : i === 1 ? OLIVE : MOSS}
        />
      ))}
    </Frame>
  );
}

function GlyphGrouped() {
  const groups = [32, 68, 104];
  return (
    <Frame>
      {groups.map((x) => (
        <g key={x}>
          <rect x={x} y={40} width="10" height="38" rx="2" fill={OLIVE} />
          <rect x={x + 12} y={28} width="10" height="50" rx="2" fill={ACCENT} />
        </g>
      ))}
    </Frame>
  );
}

function GlyphStacked() {
  const cols = [
    { x: 34, parts: [20, 16, 22] },
    { x: 68, parts: [14, 24, 18] },
    { x: 102, parts: [18, 12, 28] },
  ];
  const colors = [OLIVE, ACCENT, CREAM];
  return (
    <Frame>
      {cols.map(({ x, parts }) => {
        let y = 78;
        return parts.map((h, i) => {
          y -= h;
          return (
            <rect
              key={`${x}-${i}`}
              x={x}
              y={y}
              width="18"
              height={h}
              fill={colors[i]}
              stroke={PAPER}
              strokeWidth="0.8"
            />
          );
        });
      })}
    </Frame>
  );
}

function GlyphDonut() {
  return (
    <Frame>
      <circle cx="80" cy="48" r="30" fill="none" stroke={CREAM} strokeWidth="14" />
      <circle
        cx="80"
        cy="48"
        r="30"
        fill="none"
        stroke={OLIVE}
        strokeWidth="14"
        strokeDasharray="58 130"
        strokeLinecap="butt"
        transform="rotate(-90 80 48)"
      />
      <circle
        cx="80"
        cy="48"
        r="30"
        fill="none"
        stroke={ACCENT}
        strokeWidth="14"
        strokeDasharray="36 152"
        strokeDashoffset="-58"
        transform="rotate(-90 80 48)"
      />
      <circle cx="80" cy="48" r="16" fill={PAPER} />
    </Frame>
  );
}

function GlyphScatter() {
  const pts = [
    [36, 62],
    [52, 48],
    [68, 54],
    [84, 36],
    [100, 42],
    [116, 28],
    [48, 70],
    [90, 58],
    [128, 46],
  ];
  return (
    <Frame>
      <line x1="22" y1="78" x2="142" y2="78" stroke={MUTED} strokeWidth="1" />
      <line x1="22" y1="78" x2="22" y2="18" stroke={MUTED} strokeWidth="1" />
      {pts.map(([x, y], i) => (
        <circle
          key={`${x}-${y}`}
          cx={x}
          cy={y}
          r="6"
          fill={i % 3 === 0 ? ACCENT : OLIVE}
          opacity="0.9"
        />
      ))}
    </Frame>
  );
}

function GlyphKpi() {
  return (
    <Frame>
      <text
        x="80"
        y="52"
        textAnchor="middle"
        fontFamily="Georgia, 'Crimson Text', serif"
        fontSize="36"
        fontWeight="700"
        fill={ACCENT}
      >
        28
      </text>
      <text
        x="80"
        y="72"
        textAnchor="middle"
        fontFamily="system-ui, sans-serif"
        fontSize="9"
        fontWeight="600"
        fill={OLIVE}
        letterSpacing="0.04em"
      >
        КЛИЕНТЫ 2025
      </text>
    </Frame>
  );
}

function GlyphAuto() {
  return (
    <Frame>
      <polyline
        points="18,40 30,32 42,36 54,24"
        fill="none"
        stroke={OLIVE}
        strokeWidth="1.8"
        strokeLinecap="round"
      />
      <rect x="68" y="22" width="10" height="28" rx="2" fill={ACCENT} />
      <rect x="80" y="30" width="10" height="20" rx="2" fill={OLIVE} />
      <circle cx="122" cy="36" r="14" fill="none" stroke={CREAM} strokeWidth="7" />
      <circle
        cx="122"
        cy="36"
        r="14"
        fill="none"
        stroke={OLIVE}
        strokeWidth="7"
        strokeDasharray="22 66"
        transform="rotate(-90 122 36)"
      />
      <text
        x="80"
        y="78"
        textAnchor="middle"
        fontFamily="system-ui, sans-serif"
        fontSize="8"
        fill={INK}
        opacity="0.45"
      >
        auto · mix
      </text>
    </Frame>
  );
}

type Props = {
  typeId: ChartTypeId;
  children: ReactNode;
  className?: string;
  disabled?: boolean;
  onClick?: () => void;
};

type CardPos = { left: number; top: number; place: "above" | "below" };

/** G1: never crash on unknown catalog ids from API/LLM. */
function metaFor(typeId: string): (typeof META)[ChartTypeId] {
  if (typeId in META) return META[typeId as ChartTypeId];
  return {
    title: typeId || "Chart",
    chip: typeId || "chart",
    blurb: "Тип из каталога Liber",
    Glyph: GlyphBar,
  };
}

export function ChartTypeChip({
  typeId,
  children,
  className = "",
  disabled,
  onClick,
  preview = true,
}: Props & { /** Hover glyph card; off inside dense edit sheets. */ preview?: boolean }) {
  const meta = metaFor(typeId);
  const Glyph = meta.Glyph;
  const tipId = useId();
  const btnRef = useRef<HTMLButtonElement>(null);
  const hideTimer = useRef<number | null>(null);
  const [open, setOpen] = useState(false);
  const [pos, setPos] = useState<CardPos | null>(null);

  const place = useCallback(() => {
    const el = btnRef.current;
    if (!el) return;
    const r = el.getBoundingClientRect();
    const cardW = 188;
    const cardH = 168;
    const gap = 10;
    let left = r.left + r.width / 2 - cardW / 2;
    left = Math.max(8, Math.min(left, window.innerWidth - cardW - 8));
    const spaceAbove = r.top;
    const placeAbove = spaceAbove >= cardH + gap + 8;
    const top = placeAbove ? r.top - cardH - gap : r.bottom + gap;
    setPos({ left, top, place: placeAbove ? "above" : "below" });
  }, []);

  const clearHide = useCallback(() => {
    if (hideTimer.current != null) {
      window.clearTimeout(hideTimer.current);
      hideTimer.current = null;
    }
  }, []);

  const show = useCallback(() => {
    if (disabled || !preview) return;
    clearHide();
    place();
    setOpen(true);
  }, [disabled, preview, place, clearHide]);

  const hide = useCallback(() => {
    clearHide();
    // Bridge gap to portal card (pointer-events:auto) without flicker.
    hideTimer.current = window.setTimeout(() => setOpen(false), 140);
  }, [clearHide]);

  return (
    <span className={`chip-preview-wrap${disabled ? " is-disabled" : ""}`}>
      <button
        ref={btnRef}
        type="button"
        className={className}
        disabled={disabled}
        onClick={onClick}
        onMouseEnter={show}
        onMouseLeave={hide}
        onFocus={show}
        onBlur={hide}
        aria-describedby={open ? tipId : undefined}
      >
        {children}
      </button>
      {open &&
        pos &&
        createPortal(
          <span
            className={`chip-preview-card is-open place-${pos.place}`}
            id={tipId}
            role="tooltip"
            style={{ left: pos.left, top: pos.top }}
            onMouseEnter={show}
            onMouseLeave={hide}
          >
            <span className="chip-preview-glyph">
              <Glyph />
            </span>
            <span className="chip-preview-copy">
              <span className="chip-preview-title">{meta.title}</span>
              <span className="chip-preview-blurb">{meta.blurb}</span>
            </span>
          </span>,
          document.body,
        )}
    </span>
  );
}
