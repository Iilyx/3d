/** Intent posted with a run. The model brief is applied later in generate.py. */

export function userIntentForRun(chatTrim: string): string {
  return chatTrim.trim();
}
