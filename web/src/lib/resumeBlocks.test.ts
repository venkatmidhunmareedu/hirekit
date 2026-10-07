import { describe, expect, it } from "vitest";

import { resumeBlocks } from "./resumeBlocks";

const TEXT = `Pune, India
a@b.com

PROFESSIONAL SUMMARY
Built APIs and led
a small team.

Experience
- Shipped billing
  on time
* Cut costs
1. First
2) Second

Skills:
Python is fun.`;

describe("resumeBlocks", () => {
  const blocks = resumeBlocks(TEXT);
  const slice = (i: number) => TEXT.slice(blocks[i]?.start, blocks[i]?.end);

  it("finds header, headings, paragraphs and bullets", () => {
    expect(blocks.map((b) => b.kind)).toEqual([
      "header",
      "heading",
      "paragraph",
      "heading",
      "bullet",
      "bullet",
      "bullet",
      "bullet",
      "heading",
      "paragraph",
    ]);
    expect(slice(1)).toBe("PROFESSIONAL SUMMARY");
    expect(slice(2)).toBe("Built APIs and led\na small team.");
    expect(slice(4)).toBe("Shipped billing\n  on time");
    expect(slice(6)).toBe("First");
    expect(blocks[6]?.ordered).toBe(true);
    expect(slice(8)).toBe("Skills:");
  });

  it("keeps every word, in order", () => {
    const words = (s: string) => s.split(/\s+/).filter(Boolean);
    const kept = blocks.flatMap((b) => words(TEXT.slice(b.start, b.end)));
    // Only the list markers are left out.
    expect(kept.join(" ")).toBe(
      words(TEXT)
        .filter((w) => !["-", "*", "1.", "2)"].includes(w))
        .join(" "),
    );
  });

  it("does not make a long sentence a heading", () => {
    expect(resumeBlocks("Worked at Acme.\n")[0]?.kind).toBe("paragraph");
  });
});
