/** Hide the document chip. The attached text and file stay for the next send. */

export function hideSourcePlaque<TDraft, TFile>(state: {
  sourceDraft: TDraft | null;
  file: TFile | null;
}): {
  plaqueDismissed: true;
  sourceDraft: TDraft | null;
  file: TFile | null;
} {
  return {
    plaqueDismissed: true,
    sourceDraft: state.sourceDraft,
    file: state.file,
  };
}

export function removeAttachedSource(): {
  plaqueDismissed: false;
  sourceDraft: null;
  file: null;
} {
  return {
    plaqueDismissed: false,
    sourceDraft: null,
    file: null,
  };
}

/** Clear any attached document/file from composer once the server accepts a send. */
export function detachSourceAfterSend(opts: {
  startedOnServer: boolean;
  hidden: boolean;
}): ReturnType<typeof removeAttachedSource> | null {
  if (!opts.startedOnServer || opts.hidden) return null;
  return removeAttachedSource();
}
