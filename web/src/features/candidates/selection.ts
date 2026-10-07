/** The neighbour of `current` in `ids`, clamped at both ends; with no current candidate, the first. */
export function step(ids: readonly string[], current: string | null, delta: 1 | -1): string | null {
  const first = ids[0];
  if (first === undefined) return null;
  const at = current === null ? -1 : ids.indexOf(current);
  if (at === -1) return first;
  return ids[Math.min(ids.length - 1, Math.max(0, at + delta))] ?? first;
}

/** Whether a key press belongs to a field or dialog, where j and k are text, not navigation. */
export function isTypingTarget(target: EventTarget | null): boolean {
  if (!(target instanceof Element)) return false;
  return (
    target.closest(
      "input, textarea, select, [contenteditable='true'], [role='combobox'], [role='listbox'], [role='dialog'], [role='alertdialog'], [role='menu']",
    ) !== null
  );
}

/** What the compare tray offers for a count of ticked candidates. */
export function trayState(count: number): { canCompare: boolean; hint: string } {
  if (count < 2) return { canCompare: false, hint: "Tick at least one more candidate to compare." };
  if (count > 4) {
    return { canCompare: false, hint: `Compare takes up to 4. Untick ${count - 4}.` };
  }
  return { canCompare: true, hint: "Ready to compare." };
}
