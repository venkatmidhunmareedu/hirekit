# ADR-0003: Use React with Vite for the frontend

- Status: Accepted
- Date: 2026-09-30
- Task: none yet (pre-scaffold)
- Deciders: midhun
- Area: frontend
- Reversibility: cheap: the API is a separate FastAPI service, so the client can be rewritten without touching the backend

## Context

- Design.md describes an authenticated, desktop-first app of dense tables, a candidate detail panel, a comparison view and dialogs.
- No public or marketing pages, so search indexing does not matter.
- The backend is a separate service (ADR-0002).

## What else was considered

| Option | Why not | Would suit |
| --- | --- | --- |
| React with Vite SPA (chosen) | client-side rendering only, which is fine because nothing needs indexing | (chosen) |
| Next.js | adds a second server runtime next to FastAPI and its rendering strengths go unused | a public marketing site or content pages that need SEO |
| SvelteKit | fewer matching Bearing skills, and the design-system and accessibility checks target React first | a team already on Svelte |

## Decision

We will use React with Vite as a single-page app, because the product is an authenticated table-heavy tool talking to a separate API, and Bearing's React skills apply directly.

## Consequences

- Needs the `bearing-apps` plugin for React stack skills and templates.
- Design tokens from Design.md become the app's CSS variables.
- Revisit if a public marketing site is added.

## Commits us to

React, Vite
