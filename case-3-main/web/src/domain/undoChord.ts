/** Undo hint follows the keyboard. A Mac sees ⌘. Windows and Linux see Ctrl. */

function platformOf(platform?: string): string {
  if (platform) return platform;
  if (typeof navigator !== "undefined" && navigator.platform) return navigator.platform;
  return "";
}

export function isMacPlatform(platform?: string): boolean {
  return /Mac|iPhone|iPad/i.test(platformOf(platform));
}

export function undoChord(platform?: string): string {
  return isMacPlatform(platform) ? "⌘Z" : "Ctrl+Z";
}

export function redoChord(platform?: string): string {
  return isMacPlatform(platform) ? "⌘⇧Z" : "Ctrl+Shift+Z";
}

export function submitChord(platform?: string): string {
  return isMacPlatform(platform) ? "⌘↵" : "Ctrl+Enter";
}
