import type { RunResult } from "./liberTypes";

/** One line above the composer. Empty parts stay off the line. */

export function memoryStripLine(input: {
  documents: number;
  section: string;
  turn: number;
  max?: number;
}): string {
  const parts: string[] = [];
  const documents = Math.max(0, input.documents);
  if (documents > 0) {
    parts.push(`${documents} ${documentWord(documents)}`);
  }
  const section = input.section.trim();
  if (section) parts.push(`правили ${section}`);
  return parts.join(" · ");
}

export function carriedArtifactId(
  msgs: Array<{ role: string; result?: RunResult | null }>,
): string {
  for (let i = msgs.length - 1; i >= 0; i -= 1) {
    const result = msgs[i]?.role === "bot" ? msgs[i]?.result : null;
    if (!result?.run_id || result.isolated) continue;
    const hasFile = Boolean(
      result.preview?.blocks?.length ||
        result.deck?.slides?.length ||
        result.downloads?.pdf ||
        result.downloads?.pptx ||
        result.downloads?.deck_pdf ||
        result.slide_pngs?.length,
    );
    if (hasFile) return result.run_id;
  }
  return "";
}

function documentWord(count: number): string {
  const ten = count % 10;
  const hundred = count % 100;
  if (ten === 1 && hundred !== 11) return "документ";
  if (ten >= 2 && ten <= 4 && (hundred < 12 || hundred > 14)) return "документа";
  return "документов";
}
