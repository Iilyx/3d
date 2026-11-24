/** Floating chrome over focused deck text (Julius-like). Format B/I not persisted in IR. */

type Props = {
  visible: boolean;
  anchor: DOMRect | null;
  label: string;
  saving?: boolean;
};

export function DeckEditToolbar({
  visible,
  anchor,
  label,
  saving = false,
}: Props) {
  if (!visible || !anchor) return null;
  const top = Math.max(8, anchor.top - 44);
  const left = Math.min(
    window.innerWidth - 280,
    Math.max(8, anchor.left + anchor.width / 2 - 120),
  );
  return (
    <div
      className="deck-edit-toolbar"
      style={{ top, left }}
      role="toolbar"
      aria-label="Поле текста"
      onMouseDown={(e) => e.preventDefault()}
    >
      <span className="deck-edit-toolbar-chip">Текст</span>
      <span className="deck-edit-toolbar-label">{label}</span>
      {saving ? (
        <>
          <span className="deck-edit-toolbar-sep" aria-hidden />
          <span className="deck-edit-toolbar-hint">Сохраняю…</span>
        </>
      ) : null}
    </div>
  );
}
