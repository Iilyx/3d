/** Presentation print downloads (PPTX + deck PDF) for rail header. */

export type DeckDownloadKind = "pptx" | "deck_pdf";

export const DECK_DOWNLOAD_BLOCKED_LABEL = "Сначала Готово";

export const DECK_DOWNLOAD_BLOCKED_TITLE =
  "Сначала нажмите Готово — в файле ещё нет этих правок";

export type DeckDownloadLink = {
  kind: DeckDownloadKind;
  href: string;
  label: string;
  disabled?: boolean;
  title?: string;
};

export function deckDownloadLinks(
  downloads?: Record<string, string> | null,
  opts?: { blocked?: boolean },
): DeckDownloadLink[] {
  if (!downloads) return [];
  const blocked = Boolean(opts?.blocked);
  const out: DeckDownloadLink[] = [];
  if (downloads.pptx) {
    out.push(
      blocked
        ? {
            kind: "pptx",
            href: "",
            label: DECK_DOWNLOAD_BLOCKED_LABEL,
            disabled: true,
            title: DECK_DOWNLOAD_BLOCKED_TITLE,
          }
        : { kind: "pptx", href: downloads.pptx, label: "PPTX" },
    );
  }
  if (downloads.deck_pdf) {
    out.push(
      blocked
        ? {
            kind: "deck_pdf",
            href: "",
            label: DECK_DOWNLOAD_BLOCKED_LABEL,
            disabled: true,
            title: DECK_DOWNLOAD_BLOCKED_TITLE,
          }
        : { kind: "deck_pdf", href: downloads.deck_pdf, label: "PDF" },
    );
  }
  return out;
}
