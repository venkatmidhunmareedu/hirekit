# ADR-0013: Use shadcn/ui on Tailwind v4 for the web UI

- Status: Proposed
- Date: 2026-10-07
- Task: HK-80
- Deciders: midhun (to accept)
- Area: frontend
- Reversibility: costly: every screen would be restyled, though the API, routing and data layers are untouched
- Relates to: ADR-0003, ADR-0007

## Context

- `web/` styles itself with hand-written CSS in `styles/app.css`, `styles/screens.css` and `styles/tokens.css`.
- After the first HK-80 pass, users and the engineer judged the UI still inconsistent and generic.
- ADR-0003 chose React with Vite but not a component or styling system.
- The Bearing React stack is shadcn/ui on Tailwind v4.

## What else was considered

| Option | Why not | Would suit |
| --- | --- | --- |
| Keep the hand-written CSS and tidy it | already tried in the first HK-80 pass; the engineer rejected the result | a small UI with one author and few screens |
| shadcn/ui on Tailwind v4 (chosen) | several new dependencies; generated component code lives in the repository and must be kept patched | an app that wants owned component source and a design system built from tokens |
| Another component library such as MUI or Mantine | brings its own theming system and look, which cuts against the fresh theme in Design.md, and it is not the Bearing React stack | a team that wants a packaged library and accepts its default look |

## Decision

We will use shadcn/ui components, copied into `web/src/components/ui` with the shadcn CLI (pinned 4.21.0), on Tailwind v4 with the theme tokens in `src/index.css`, because the stack is the Bearing React default and owned component source lets us fix the inconsistency. The fresh theme is recorded in Design.md.

New dependencies:

- Runtime: `tailwindcss`, `@tailwindcss/vite`, `class-variance-authority`, `clsx`, `tailwind-merge`, `lucide-react`, `radix-ui`, `tw-animate-css`.
- Dev: `prettier-plugin-tailwindcss`.

## Consequences

- Generated files in `web/src/components/ui` are excluded from ESLint and coverage and are never hand-edited. Extend them with `className` and `cva` in our own components.
- Tailwind arbitrary values (for example `w-[137px]`) are avoided; use theme tokens.
- The `pnpm audit` gate must stay clean with the new packages.
- The old CSS files (`app.css`, `screens.css`, `tokens.css`) are deleted at the end of HK-80.
- TanStack Router and Query, Zod and vitest are unchanged. There is no API change.
- Supersedes nothing. ADR-0003 stays in force for React with Vite.
- Revisit if the shadcn CLI or Tailwind changes break the generated components.

## Commits us to

- Tailwind v4 and `@tailwindcss/vite`
- shadcn/ui via the shadcn CLI 4.21.0
- radix-ui, class-variance-authority, clsx, tailwind-merge, lucide-react, tw-animate-css
- prettier-plugin-tailwindcss (dev)
