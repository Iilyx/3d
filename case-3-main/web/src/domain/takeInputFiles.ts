/** Copy a file input's selection, then clear it so the same file can be picked again.

The FileList is live: setting value to "" empties it. Snapshot first.
*/
export function takeInputFiles(input: {
  files: FileList | null;
  value: string;
}): File[] {
  const files = input.files ? Array.from(input.files) : [];
  input.value = "";
  return files;
}
