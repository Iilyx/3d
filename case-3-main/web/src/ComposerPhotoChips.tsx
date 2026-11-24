/** Thumbnail chips for photos attached to the Liber composer. */

import { useEffect, useState } from "react";

export function ComposerPhotoChips({
  files,
  busy,
  onRemove,
  onPreview,
}: {
  files: File[];
  busy: boolean;
  onRemove: (index: number) => void;
  onPreview?: (photo: { url: string; name: string }) => void;
}) {
  const [urls, setUrls] = useState<string[]>([]);
  useEffect(() => {
    const next = files.map((f) => URL.createObjectURL(f));
    setUrls(next);
    return () => {
      for (const u of next) URL.revokeObjectURL(u);
    };
  }, [files]);
  return (
    <div className="composer-photos" aria-label="Прикреплённые фото">
      {files.map((p, i) => (
        <div key={`${p.name}-${i}-${p.size}`} className="composer-photo-chip">
          <button
            type="button"
            className="composer-photo-thumb-btn"
            onClick={() => onPreview?.({ url: urls[i], name: p.name })}
            title={`Открыть ${p.name}`}
            aria-label={`Открыть фото ${p.name}`}
          >
            <img src={urls[i]} alt={p.name} />
          </button>
          <button
            type="button"
            className="composer-photo-x"
            aria-label="Убрать фото"
            disabled={busy}
            onClick={() => onRemove(i)}
          >
            ×
          </button>
        </div>
      ))}
    </div>
  );
}
