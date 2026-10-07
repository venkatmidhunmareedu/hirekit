# ADR-0015: Use Tiptap for job description editing

- Status: Accepted
- Date: 2026-10-08
- Task: HK-86
- Deciders: midhun (decided in the HK-86 session)
- Area: frontend
- Reversibility: easy: the stored value is a markdown string in the same `job_description` field, so the editor can be swapped without touching the API or the data
- Relates to: ADR-0003, ADR-0013

## Context

- The New role dialog took the job description in a plain textarea, and the role page showed it as plain text.
- Real job descriptions are pasted with `- ` bullets and `## ` headings, which showed as raw characters.
- The backend stores `job_description` as a plain string and must not change.

## What else was considered

| Option | Why not | Would suit |
| --- | --- | --- |
| Keep the plain textarea | pasted structure stays raw and hard to read | a UI where structure does not matter |
| Tiptap (chosen) | four new packages (about 49 with transitive ones) | a rich editor with a markdown round trip and an accessible DOM |
| A markdown textarea plus a renderer (such as react-markdown) | the recruiter edits syntax rather than the result | technical users who write markdown |

## Decision

We will use Tiptap 3 (`@tiptap/react`, `@tiptap/pm`, `@tiptap/starter-kit`, `@tiptap/markdown`, all MIT, pinned exactly) in `web/src/components/RichText.tsx`. `MarkdownEditor` edits and `Markdown` shows read-only. The value stored in `job_description` is markdown text.

## Consequences

- No API, schema or backend change. Old plain-text descriptions are valid markdown and render as paragraphs.
- The model receives the markdown text. `job_description_text` in `backend/app/jobs/job_description.py` embeds the description as it is, without parsing it, so markdown does not break it. Recordings for existing roles are unchanged because their text is unchanged.
- Anonymization is unaffected: job descriptions are recruiter-authored, not resumes, and the resume anonymizer never sees them.
- Links, images, code and raw HTML are switched off in the editor schema, and the view renders no HTML string, so there is no HTML injection path.
- Pasted plain text is read as markdown by a small paste handler; pasted HTML is handled by Tiptap as usual.
- Typing into a list is not covered by jsdom tests, which cannot drive ProseMirror keystrokes there; the browser behaviour is not unit tested.
- The `pnpm audit` gate must stay clean with the new packages.

## Commits us to

- `@tiptap/react`, `@tiptap/pm`, `@tiptap/starter-kit` and `@tiptap/markdown` 3.31.4
