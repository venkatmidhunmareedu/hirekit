const PATHS = {
  check: "M5 12.5l4.5 4.5L19 7.5",
  dash: "M6 12h12",
  triangle: "M12 4l9 16H3zM12 10v4.5M12 17.5h.01",
  pencil: "M4 20l1-4L16 5l3 3L8 19zM14 7l3 3",
  lock: "M7 11V8a5 5 0 0 1 10 0v3M6 11h12v9H6z",
  eye: "M2 12s4-7 10-7 10 7 10 7-4 7-10 7-10-7-10-7zM12 9.5a2.5 2.5 0 1 0 0 5 2.5 2.5 0 0 0 0-5z",
  minus: "M6 12h12",
} as const;

/** Outline icon, 1.5px stroke, 16px inline (Design.md section 6); always beside text. */
export function Icon({
  name,
  color = "currentColor",
}: {
  name: keyof typeof PATHS;
  color?: string;
}) {
  return (
    <svg
      width="16"
      height="16"
      viewBox="0 0 24 24"
      fill="none"
      stroke={color}
      strokeWidth="1.5"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      focusable="false"
    >
      <path d={PATHS[name]} />
    </svg>
  );
}
