/** Liber desk: edit one report list → TeX itemize/enumerate patch. */

export type ListEditRequest = {
  listIndex: number;
  items: string[];
  ordered?: boolean;
};
