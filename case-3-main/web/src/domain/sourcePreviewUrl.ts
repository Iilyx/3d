/** Durable Source document preview / original URLs (survive blob revoke + send). */

export function durableSourcePreviewUrl(doc: {
  previewUrl?: string | null;
  ingestId?: string | null;
}): string | null {
  if (doc.previewUrl) return doc.previewUrl;
  if (doc.ingestId) {
    return `/api/source/files/${encodeURIComponent(doc.ingestId)}/preview`;
  }
  return null;
}

export function durableSourceOriginalUrl(doc: {
  originalUrl?: string | null;
  ingestId?: string | null;
}): string | null {
  if (doc.originalUrl) return doc.originalUrl;
  if (doc.ingestId) {
    return `/api/source/files/${encodeURIComponent(doc.ingestId)}/original`;
  }
  return null;
}
