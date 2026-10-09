// Small hand-drawn icon set (24×24 grid, 1.6px strokes). Filled icons are marked.
const PATHS = {
  play: <path d="M7 4.8v14.4a.8.8 0 0 0 1.2.7l11.4-7.2a.8.8 0 0 0 0-1.4L8.2 4.1A.8.8 0 0 0 7 4.8z" />,
  pause: <><rect x="6" y="4.5" width="4" height="15" rx="1" /><rect x="14" y="4.5" width="4" height="15" rx="1" /></>,
  left: <path d="M15 18l-6-6 6-6" />,
  right: <path d="M9 18l6-6-6-6" />,
  plus: <path d="M12 5v14M5 12h14" />,
  check: <path d="M5 12.5l4.5 4.5L19 7.5" />,
  more: <><circle cx="5" cy="12" r="1.3" /><circle cx="12" cy="12" r="1.3" /><circle cx="19" cy="12" r="1.3" /></>,
  timer: <><circle cx="12" cy="13" r="8" /><path d="M12 9v4l2.5 2.5M9.5 2.5h5" /></>,
  carry: <><path d="M4 7h11a5 5 0 0 1 0 10H8" /><path d="M11 13l-4 4 4 4" /></>,
  down: <path d="M12 5v14M6 13l6 6 6-6" />,
  up: <path d="M12 19V5M6 11l6-6 6 6" />,
  cal: <><rect x="3.5" y="5" width="17" height="15" rx="2" /><path d="M3.5 10h17M8 3v4M16 3v4" /></>,
  edit: <path d="M4 20h4L19 9l-4-4L4 16z" />,
  list: <path d="M9 6h11M9 12h11M9 18h11M4.5 6h.01M4.5 12h.01M4.5 18h.01" />,
  trash: <path d="M4 7h16M9 7V4.5h6V7M6.5 7l1 13h9l1-13" />,
  x: <path d="M6 6l12 12M18 6L6 18" />,
  undo: <><path d="M9 14L4 9l5-5" /><path d="M4 9h10a6 6 0 0 1 0 12h-3" /></>,
  download: <path d="M12 4v11M7 10l5 5 5-5M5 20h14" />,
  upload: <path d="M12 16V5M7 10l5-5 5 5M5 20h14" />,
};
const FILLED = new Set(["play", "pause"]);

export default function Icon({ name, size = 16, className = "" }) {
  return (
    <svg
      className={`ico${FILLED.has(name) ? " ico-fill" : ""} ${className}`}
      width={size} height={size} viewBox="0 0 24 24" aria-hidden="true" focusable="false"
    >
      {PATHS[name]}
    </svg>
  );
}

export function Logo({ size = 20 }) {
  return (
    <svg width={size} height={size} viewBox="0 0 20 20" aria-hidden="true">
      <rect x="1" y="1" width="8.2" height="8.2" rx="2" fill="#d4512f" />
      <rect x="10.8" y="1" width="8.2" height="8.2" rx="2" fill="#1c1b19" />
      <rect x="1" y="10.8" width="8.2" height="8.2" rx="2" fill="#1c1b19" />
      <rect x="10.8" y="10.8" width="8.2" height="8.2" rx="2" fill="#1c1b19" opacity=".25" />
    </svg>
  );
}
