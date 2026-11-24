/** Report chat preview blocks (TeX → Liber UI). Domain-owned to avoid UI ↔ type cycles. */

export type PreviewBlock =
  | { type: "heading"; level: number; text: string }
  | { type: "paragraph"; id?: string; text: string; html?: string }
  | {
      type: "list";
      id?: string;
      ordered?: boolean;
      items: { text: string; html?: string }[];
    }
  | {
      type: "table";
      caption?: string;
      headers: string[];
      rows: string[][];
      /** Wide table that prints on a landscape page. */
      landscape?: boolean;
    }
  | {
      type: "figure";
      id: string;
      kind: string;
      caption?: string;
      url?: string;
      chartType?: string;
      /** G2: last applied / run palette id for edit sheet seed. */
      palette?: string;
      /** C10: 1-based PDF page hint from TeX breaks. */
      pdfPage?: number;
      insight?: string;
      highlights?: { label: string; value: string; pct?: string }[];
    };

export type ReportPreview = {
  title?: string;
  blocks: PreviewBlock[];
};
