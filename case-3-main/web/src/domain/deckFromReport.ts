/** A finished report can start a deck. A deck that already exists does not. */

export function reportCanMakeDeck(args: {
  outputMode?: string | null;
  pdfUrl?: string | null;
  slidesStatus?: string | null;
}): boolean {
  const mode = args.outputMode || "auto";
  if (mode === "presentation" || mode === "diagram" || mode === "chat") return false;
  if (!args.pdfUrl) return false;
  const status = args.slidesStatus || "";
  if (
    status === "ok" ||
    status === "running" ||
    status === "queued" ||
    status === "starting"
  ) {
    return false;
  }
  return true;
}
