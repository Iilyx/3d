/** Liber deck IR types (subset used by live canvas). */

export type DeckKpi = {
  label?: string;
  value?: string;
  hint?: string;
  delta?: string;
  status?: string;
};

export type DeckCard = {
  kicker?: string;
  title?: string;
  body?: string;
};

export type DeckSlide = {
  id: string;
  layout: string;
  title?: string;
  subtitle?: string;
  kicker?: string;
  takeaway?: string;
  body?: string;
  caption?: string;
  term?: string;
  definition?: string;
  bullets?: string[];
  kpis?: DeckKpi[];
  cards?: DeckCard[];
  rows?: string[][];
  chart_id?: string;
  media_id?: string;
  chapter?: number;
  bullet_node_map?: Record<string, string | string[]>;
};

export type DeckStyle = {
  pack_id?: string;
  brand_mark?: string;
  colors?: Record<string, string>;
  fonts?: Record<string, string>;
  motif?: {
    split?: number;
    panels?: string[];
    panel_key?: string;
    atmosphere?: string;
    hero_bleed?: boolean;
    card_fill?: string;
  };
};

export type DeckIR = {
  version?: number;
  aspect?: string;
  palette?: string;
  language?: string;
  style?: DeckStyle;
  slides: DeckSlide[];
};
