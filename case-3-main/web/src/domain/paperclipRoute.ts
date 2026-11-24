/** Where a composer paperclip file goes before the model sees it. */

import { isOfficeSourceFile } from "./sourceOfficeIngest";

export type PaperclipAction = "text" | "office" | "dashboard-png" | "photo";

export function paperclipAction(file: {
  name: string;
  type: string;
}): PaperclipAction | "ignore" {
  const name = file.name || "";
  const type = (file.type || "").toLowerCase();
  if (
    /\.(txt|md)$/i.test(name) ||
    type === "text/plain" ||
    type === "text/markdown"
  ) {
    return "text";
  }
  if (type === "image/png" || /\.png$/i.test(name)) return "dashboard-png";
  if (type.startsWith("image/") || /\.(jpe?g)$/i.test(name)) return "photo";
  if (isOfficeSourceFile(file as File)) return "office";
  return "ignore";
}
