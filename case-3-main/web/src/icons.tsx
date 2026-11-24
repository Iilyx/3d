/** Liber stroke icons — 1.5–1.75 weight, no emoji chrome. */

type IconProps = {
  size?: number;
  className?: string;
};

function base({ size = 18, className }: IconProps) {
  return {
    width: size,
    height: size,
    viewBox: "0 0 24 24",
    fill: "none" as const,
    className,
    "aria-hidden": true as const,
  };
}

const stroke = {
  stroke: "currentColor",
  strokeWidth: 1.65,
  strokeLinecap: "round" as const,
  strokeLinejoin: "round" as const,
};

export function IconUndo(p: IconProps) {
  return (
    <svg {...base(p)}>
      <path {...stroke} d="M3 7v6h6" />
      <path {...stroke} d="M21 17a9 9 0 0 0-9-9 9 9 0 0 0-6 2.3L3 13" />
    </svg>
  );
}

export function IconRedo(p: IconProps) {
  return (
    <svg {...base(p)}>
      <path {...stroke} d="M21 7v6h-6" />
      <path {...stroke} d="M3 17a9 9 0 0 1 9-9 9 9 0 0 1 6 2.3L21 13" />
    </svg>
  );
}

export function IconPlus(p: IconProps) {
  return (
    <svg {...base(p)}>
      <path {...stroke} d="M12 5v14M5 12h14" />
    </svg>
  );
}

export function IconSend(p: IconProps) {
  return (
    <svg {...base(p)}>
      <path {...stroke} d="M12 19V5M5 12l7-7 7 7" />
    </svg>
  );
}

export function IconStop(p: IconProps) {
  return (
    <svg {...base(p)}>
      <rect
        x="3.5"
        y="3.5"
        width="17"
        height="17"
        rx="4"
        fill="currentColor"
        stroke="none"
      />
    </svg>
  );
}

export function IconPaperclip(p: IconProps) {
  return (
    <svg {...base(p)}>
      <path
        {...stroke}
        d="M21.44 11.05l-8.49 8.49a5.5 5.5 0 0 1-7.78-7.78l8.49-8.49a3.5 3.5 0 0 1 4.95 4.95l-8.5 8.49a1.5 1.5 0 0 1-2.12-2.12l7.78-7.78"
      />
    </svg>
  );
}

/** Source attach glyph — folded page + kind cue (md lines / txt lines / paste braces). */
export function IconSourceDoc({
  kind = "txt",
  size = 18,
  className,
}: IconProps & { kind?: "md" | "txt" | "paste" | "pdf" | "docx" }) {
  return (
    <svg {...base({ size, className })}>
      <path
        {...stroke}
        d="M7 3.5h7.2L19 8.3V20a1.5 1.5 0 0 1-1.5 1.5h-10A1.5 1.5 0 0 1 6 20V5A1.5 1.5 0 0 1 7.5 3.5"
      />
      <path {...stroke} d="M14 3.5V8h4.8" />
      {kind === "paste" ? (
        <>
          <path {...stroke} d="M9.2 12.2h2.2M9.2 15.2h5.6" />
          <path {...stroke} d="M10.5 10.8v6.2M13.5 10.8v6.2" opacity="0.55" />
        </>
      ) : kind === "md" ? (
        <>
          <path {...stroke} d="M9 12h6M9 15h4.5" />
          <path {...stroke} d="M9 9.2h2.2" />
        </>
      ) : kind === "pdf" || kind === "docx" ? (
        <>
          <path {...stroke} d="M9 11.2h6M9 14h6M9 16.8h4" />
          <path {...stroke} d="M16.2 11.2v5.6" opacity="0.45" />
        </>
      ) : (
        <>
          <path {...stroke} d="M9 11.5h6M9 14.2h6M9 16.9h3.8" />
        </>
      )}
    </svg>
  );
}

export function IconSettings(p: IconProps) {
  return (
    <svg {...base(p)}>
      <circle cx="12" cy="12" r="3" {...stroke} />
      <path
        {...stroke}
        d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z"
      />
    </svg>
  );
}

export function IconPin(p: IconProps) {
  return (
    <svg {...base(p)}>
      <path
        {...stroke}
        d="M12 17v5M9.2 10.2l-2.4 1.1 4.1 4.1 1.1-2.4M15.5 4.5l4 4-6.2 2.6L9.9 7.7 15.5 4.5z"
      />
    </svg>
  );
}

export function IconFolder(p: IconProps) {
  return (
    <svg {...base(p)}>
      <path
        {...stroke}
        d="M3 7.5A1.5 1.5 0 0 1 4.5 6h4.2l1.8 1.8H19.5A1.5 1.5 0 0 1 21 9.3v8.2a1.5 1.5 0 0 1-1.5 1.5h-15A1.5 1.5 0 0 1 3 17.5v-10z"
      />
    </svg>
  );
}

export function IconChevron(p: IconProps) {
  return (
    <svg {...base(p)}>
      <path {...stroke} d="M9 6l6 6-6 6" />
    </svg>
  );
}

export function IconPanelLeft(p: IconProps) {
  return (
    <svg {...base(p)}>
      <rect x="3" y="4" width="18" height="16" rx="2" {...stroke} />
      <path {...stroke} d="M9 4v16" />
    </svg>
  );
}

/** Mirror of left rail — strip on the right (close/collapse right panel). */
export function IconPanelRight(p: IconProps) {
  return (
    <svg {...base(p)}>
      <rect x="3" y="4" width="18" height="16" rx="2" {...stroke} />
      <path {...stroke} d="M15 4v16" />
    </svg>
  );
}

export function IconCopy(p: IconProps) {
  return (
    <svg {...base(p)}>
      <rect x="9" y="9" width="11" height="11" rx="1.5" {...stroke} />
      <path {...stroke} d="M5 15V5a2 2 0 0 1 2-2h10" />
    </svg>
  );
}

export function IconPalette(p: IconProps) {
  return (
    <svg {...base(p)}>
      <path
        {...stroke}
        d="M12 3a9 9 0 0 0 0 18c.7 0 1.2-.5 1.2-1.2 0-.3-.1-.6-.3-.8l-.2-.3a1.4 1.4 0 0 1 1.1-2.3H16a5 5 0 0 0 0-10H12z"
      />
      <circle cx="7.5" cy="10" r="1.1" fill="currentColor" stroke="none" />
      <circle cx="10.5" cy="7.2" r="1.1" fill="currentColor" stroke="none" />
      <circle cx="14.2" cy="7.5" r="1.1" fill="currentColor" stroke="none" />
      <circle cx="7.8" cy="13.5" r="1.1" fill="currentColor" stroke="none" />
    </svg>
  );
}

export function IconHelp(p: IconProps) {
  return (
    <svg {...base(p)}>
      <circle {...stroke} cx="12" cy="12" r="8.25" />
      <path {...stroke} d="M9.6 9.3a2.4 2.4 0 1 1 3.3 2.2c-.7.4-1.1.9-1.1 1.7" />
      <path {...stroke} d="M12 17.2h.01" />
    </svg>
  );
}

export function IconReport(p: IconProps) {
  return (
    <svg {...base(p)}>
      <path {...stroke} d="M7 3.5h7.2L19.5 9v11.5a1.5 1.5 0 0 1-1.5 1.5H7A1.5 1.5 0 0 1 5.5 20.5v-15A1.5 1.5 0 0 1 7 3.5z" />
      <path {...stroke} d="M14 3.5V9h5.5" />
      <path {...stroke} d="M8.5 13h7" />
      <path {...stroke} d="M8.5 16.5h5" />
    </svg>
  );
}

export function IconDiagram(p: IconProps) {
  return (
    <svg {...base(p)}>
      <rect {...stroke} x="3.5" y="4" width="6.2" height="4.6" rx="1.2" />
      <rect {...stroke} x="14.3" y="4" width="6.2" height="4.6" rx="1.2" />
      <rect {...stroke} x="8.9" y="15.4" width="6.2" height="4.6" rx="1.2" />
      <path {...stroke} d="M6.6 8.6v2.2a2 2 0 0 0 2 2h6.8a2 2 0 0 1 2 2V15" />
      <path {...stroke} d="M12 12.8v2.6" />
    </svg>
  );
}

export function IconSlides(p: IconProps) {
  return (
    <svg {...base(p)}>
      <rect {...stroke} x="3.5" y="5" width="17" height="11.5" rx="1.6" />
      <path {...stroke} d="M12 16.5v3" />
      <path {...stroke} d="M8.5 19.5h7" />
      <path {...stroke} d="M10 10.2l4.2 2.3-4.2 2.3z" />
    </svg>
  );
}

export function IconLiberMark({ size = 28 }: { size?: number }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 32 32"
      aria-hidden
      className="liber-mark"
    >
      <circle cx="16" cy="16" r="15" fill="var(--surface-3, #e8e8e6)" />
      <circle
        cx="16"
        cy="16"
        r="14"
        fill="none"
        stroke="var(--accent, #1a1a1a)"
        strokeWidth="1.25"
        opacity="0.35"
      />
      <text
        x="16"
        y="21"
        textAnchor="middle"
        fill="var(--accent, #1a1a1a)"
        fontFamily="Crimson Text, Georgia, serif"
        fontSize="15"
        fontWeight="600"
      >
        L
      </text>
    </svg>
  );
}
