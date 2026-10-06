/** The HireKit mark and two-tone wordmark (Design.md section 2). */
export function Logo() {
  return (
    <span className="logo">
      <svg width="28" height="24" viewBox="88 58 96 80" aria-hidden="true" focusable="false">
        <path
          d="M116 76V70a6 6 0 0 1 6-6h26a6 6 0 0 1 6 6v6"
          fill="none"
          stroke="var(--brand)"
          strokeWidth="6"
          strokeLinecap="round"
        />
        <rect x="93" y="76" width="84" height="58" rx="10" fill="var(--brand)" />
        <polyline
          points="116,106 129,119 154,92"
          fill="none"
          stroke="var(--ink)"
          strokeWidth="7"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
      </svg>
      <span className="logo-word">
        Hire<span className="logo-accent">Kit</span>
      </span>
    </span>
  );
}
