/** Report print downloads (PDF + DOCX) for chat cards and rail. */

export type ReportDownloadKind = "pdf" | "docx";

export type ReportDownloadLink = {
  kind: ReportDownloadKind;
  href: string;
  /** Short UI label */
  label: string;
  /** Edit session: print files lag Preview. */
  stale?: boolean;
  title?: string;
};

/**
 * Ordered print downloads for Liber report mode.
 * Empty when surface disabled or no files.
 */
export function reportDownloadLinks(
  downloads?: Record<string, string> | null,
  opts?: { enabled?: boolean; stale?: boolean },
): ReportDownloadLink[] {
  const enabled = opts?.enabled !== false;
  if (!enabled || !downloads) return [];
  const stale = Boolean(opts?.stale);
  const title = stale
    ? "Устарели — нажмите Готово, чтобы обновить"
    : undefined;
  const out: ReportDownloadLink[] = [];
  if (downloads.pdf) {
    out.push({
      kind: "pdf",
      href: stale ? "" : downloads.pdf,
      label: stale ? "PDF · устарел" : "PDF",
      stale,
      title,
    });
  }
  if (downloads.docx) {
    out.push({
      kind: "docx",
      href: stale ? "" : downloads.docx,
      label: stale ? "DOCX · устарел" : "DOCX",
      stale,
      title,
    });
  }
  return out;
}
