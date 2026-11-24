/** Liber deck style — localStorage + API payload (deck-only). */

export type DeckStyle = {
  themePack: string;
  /** Narrative structure id (board_update, investor, …) — not a color pack. */
  structureId?: string;
  /** Which gallery card is selected when two cards share a structure. */
  templateId?: string;
  primary: string;
  accent: string;
  background: string;
  text: string;
  fontTitle: string;
  fontBody: string;
  presetId?: string;
};

export type DeckThemePackInfo = {
  id: string;
  label: string;
  swatches: string[];
};

const STORAGE_KEY = "liber.deckStyle.v1";

export const DEFAULT_DECK_STYLE: DeckStyle = {
  themePack: "atelier",
  structureId: undefined,
  primary: "#233322",
  accent: "#5A7D4C",
  background: "#FAF7F0",
  text: "#233322",
  fontTitle: "Georgia",
  fontBody: "Segoe UI",
  presetId: "atelier",
};

export const FALLBACK_DECK_PACKS: DeckThemePackInfo[] = [
  {
    id: "atelier",
    label: "Atelier Olive",
    swatches: ["#233322", "#5A7D4C", "#FAF7F0", "#233322"],
  },
  {
    id: "board",
    label: "Northstar Sapphire",
    swatches: ["#172D40", "#226496", "#FAF7F2", "#122334"],
  },
  {
    id: "signal",
    label: "Bold Signal",
    swatches: ["#24211E", "#E86A33", "#181614", "#F7F2EB"],
  },
  {
    id: "relay",
    label: "Split Pastel",
    swatches: ["#5C2A24", "#C45B46", "#FDF9F6", "#2C1D1A"],
  },
  {
    id: "ink",
    label: "Relay Ink",
    swatches: ["#1D3557", "#4EA8DE", "#0F1520", "#EEF2F7"],
  },
  {
    id: "voltage",
    label: "Creative Voltage",
    swatches: ["#111823", "#38BDF8", "#E4E869", "#F3F6FA"],
  },
  {
    id: "studio",
    label: "Workshop Studio",
    swatches: ["#2D5A88", "#D47A3E", "#FBF6EE", "#23201D"],
  },
  {
    id: "botanical",
    label: "Dark Botanical",
    swatches: ["#101F19", "#C4AD7A", "#182B23", "#EDE7D9"],
  },
];

export const DECK_FONT_OPTIONS = [
  "Georgia",
  "Segoe UI",
  "Arial",
  "Calibri",
  "Times New Roman",
  "Helvetica",
] as const;

function isHex(v: unknown): v is string {
  return typeof v === "string" && /^#?[0-9A-Fa-f]{6}$/.test(v.trim());
}

function normHex(v: string): string {
  const t = v.trim();
  return t.startsWith("#") ? t.toUpperCase() : `#${t.toUpperCase()}`;
}

export function loadDeckStyle(): DeckStyle {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return { ...DEFAULT_DECK_STYLE };
    const parsed = JSON.parse(raw) as Partial<DeckStyle>;
    return {
      themePack: parsed.themePack || DEFAULT_DECK_STYLE.themePack,
      structureId: parsed.structureId || undefined,
      primary: isHex(parsed.primary)
        ? normHex(parsed.primary)
        : DEFAULT_DECK_STYLE.primary,
      accent: isHex(parsed.accent)
        ? normHex(parsed.accent)
        : DEFAULT_DECK_STYLE.accent,
      background: isHex(parsed.background)
        ? normHex(parsed.background)
        : DEFAULT_DECK_STYLE.background,
      text: isHex(parsed.text) ? normHex(parsed.text) : DEFAULT_DECK_STYLE.text,
      fontTitle: parsed.fontTitle || DEFAULT_DECK_STYLE.fontTitle,
      fontBody: parsed.fontBody || DEFAULT_DECK_STYLE.fontBody,
      presetId: parsed.presetId,
    };
  } catch {
    return { ...DEFAULT_DECK_STYLE };
  }
}

export function saveDeckStyle(style: DeckStyle): void {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(style));
  } catch {
    /* ignore quota */
  }
}

export function applyPackToStyle(
  pack: DeckThemePackInfo,
  prev: DeckStyle,
): DeckStyle {
  const [primary, accent, background, text] = pack.swatches;
  return {
    ...prev,
    themePack: pack.id,
    presetId: pack.id,
    primary: primary || prev.primary,
    accent: accent || prev.accent,
    background: background || prev.background,
    text: text || prev.text,
  };
}

/** Same Office faces as slides_pptx_draw._office_font_name. */
export function officeFace(
  name: string | undefined,
  kind: "title" | "body",
): string {
  const raw = (name || "").toLowerCase();
  if (
    /fraunces|liber serif|iowan|georgia|garamond|playfair|source serif|baskerville|newsreader|serif/.test(
      raw,
    )
  ) {
    return "Georgia";
  }
  if (
    /inter|source sans|liber sans|segoe|calibri|aptos|manrope|dm sans|sans/.test(
      raw,
    )
  ) {
    return "Calibri";
  }
  return kind === "title" ? "Georgia" : "Calibri";
}

/** Diagram legend strokes. Keep in sync with diagram_style._ROLE_MAP. */
const DIAGRAM_LEGEND_STROKES: Record<
  string,
  { start: string; decision: string; ok: string; warn: string }
> = {
  atelier: { start: "#1F6F66", decision: "#C47A3A", ok: "#2F7D4A", warn: "#C45A48" },
  editorial: { start: "#4E79A7", decision: "#F28E2B", ok: "#59A14F", warn: "#E15759" },
  ocean: { start: "#0072B2", decision: "#E69F00", ok: "#009E73", warn: "#D55E00" },
  sunset: { start: "#9A4A58", decision: "#A89830", ok: "#228833", warn: "#EE6677" },
  mono: { start: "#1A1F28", decision: "#8B7355", ok: "#2F4A38", warn: "#6B4038" },
  board: { start: "#226496", decision: "#D96B43", ok: "#2A8C72", warn: "#C9522B" },
  signal: { start: "#E86A33", decision: "#F2A93B", ok: "#38A889", warn: "#FF7B47" },
  relay: { start: "#C45B46", decision: "#D4884E", ok: "#3B7A6B", warn: "#B83B2A" },
  pastel: { start: "#C45B46", decision: "#D4884E", ok: "#3B7A6B", warn: "#B83B2A" },
  voltage: { start: "#38BDF8", decision: "#E4D48A", ok: "#34D399", warn: "#FB7185" },
  studio: { start: "#9C6644", decision: "#D48C46", ok: "#3B7A57", warn: "#C25944" },
  botanical: { start: "#52B788", decision: "#D4B475", ok: "#40916C", warn: "#E07A5F" },
  ink: { start: "#58A6FF", decision: "#E3B341", ok: "#3FB950", warn: "#F85149" },
};

export function diagramLegendStrokes(palette: string | undefined): {
  start: string;
  decision: string;
  ok: string;
  warn: string;
} {
  const key = (palette || "atelier").trim().toLowerCase();
  return DIAGRAM_LEGEND_STROKES[key] || DIAGRAM_LEGEND_STROKES.atelier;
}

/** Body for POST /api/runs/{id}/slides */
export function deckStyleToApiPayload(style: DeckStyle): {
  theme_pack: string;
  structure_id?: string;
  style_settings: Record<string, string>;
} {
  const payload: {
    theme_pack: string;
    structure_id?: string;
    style_settings: Record<string, string>;
  } = {
    theme_pack: style.themePack || "atelier",
    style_settings: {
      primary: style.primary,
      accent: style.accent,
      background: style.background,
      text: style.text,
      fontTitle: style.fontTitle,
      fontBody: style.fontBody,
    },
  };
  if (style.structureId) payload.structure_id = style.structureId;
  return payload;
}

/** Automatic deck start after a presentation run. Keeps a Stop that landed first. */
export function slidesAutoKickPayload(style: DeckStyle): {
  theme_pack: string;
  structure_id?: string;
  style_settings: Record<string, string>;
  kick_source: "api_auto";
} {
  return { ...deckStyleToApiPayload(style), kick_source: "api_auto" };
}
