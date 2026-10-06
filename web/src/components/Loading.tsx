/** A polite status with a spinner; the text names what is loading. */
export function Loading({ label }: { label: string }) {
  return (
    <p role="status" className="loading">
      <span className="spinner" aria-hidden="true" />
      <span>{label}</span>
    </p>
  );
}
