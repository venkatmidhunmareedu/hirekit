export interface ResumeBlock {
  kind: "header" | "heading" | "bullet" | "paragraph";
  /** [start, end) in the original text; the span excludes surrounding whitespace and any bullet marker. */
  start: number;
  end: number;
  /** A bullet that began with "1." or "1)". */
  ordered?: boolean;
}

const SECTIONS = new RegExp(
  `^(?:professional |executive |career )?(?:summary|profile|objective|about me|(?:work |professional |relevant )?experience|employment(?: history)?|work history|education|(?:technical |key |core )?skills|projects|certifications?|achievements|awards|publications|languages|contact(?: information| details)?|interests|references|volunteering)$`,
  "i",
);
const BULLET = /^(?:[•▪●◦·]\s*|[-*–]\s+|(\d+)[.)]\s+)/;
const HEADER_MAX_LINES = 4;
const HEADER_MAX_LINE = 60;

function isHeading(line: string): boolean {
  if (line.length > 40 || /[.;,!?]$/.test(line)) return false;
  const name = line.replace(/:$/, "");
  if (SECTIONS.test(name)) return true;
  return /[A-Z]/.test(name) && name === name.toUpperCase() && !BULLET.test(line);
}

/**
 * Turn extracted resume text into display blocks. Whitespace between blocks is the only thing left
 * out, so a quote that crosses blocks is still found in the original string by offset.
 */
export function resumeBlocks(text: string): ResumeBlock[] {
  const blocks: ResumeBlock[] = [];
  let open: ResumeBlock | null = null;
  let pos = 0;
  for (const raw of text.split("\n")) {
    const lineStart = pos;
    pos += raw.length + 1;
    const line = raw.trim();
    if (line === "") {
      open = null;
      continue;
    }
    const start = lineStart + raw.indexOf(line);
    const end = start + line.length;
    const bullet = BULLET.exec(line);
    if (bullet) {
      open = {
        kind: "bullet",
        start: start + bullet[0].length,
        end,
        ...(bullet[1] !== undefined && { ordered: true }),
      };
      blocks.push(open);
    } else if (isHeading(line)) {
      open = null;
      blocks.push({ kind: "heading", start, end });
    } else if (open) {
      open.end = end;
    } else {
      open = { kind: "paragraph", start, end };
      blocks.push(open);
    }
  }
  const first = blocks[0];
  if (first?.kind === "paragraph") {
    const rows = text.slice(first.start, first.end).split("\n");
    if (rows.length > 1 && rows.length <= HEADER_MAX_LINES) {
      if (rows.every((r) => r.trim().length <= HEADER_MAX_LINE)) first.kind = "header";
    }
  }
  return blocks;
}
