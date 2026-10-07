# ADR-0014: Host the API, Worker and web UI on one Oracle Always Free VM

- Status: Proposed
- Date: 2026-10-07
- Task: HK-85
- Deciders: midhun (to accept)
- Area: deployment
- Reversibility: cheap: systemd units and a Caddyfile; the app code is unchanged
- Relates to: ADR-0004, ADR-0007

## Context

- The product needs a long-running Worker that claims jobs from PostgreSQL (hirekit-hld.md), uploads of up to 100 MB per request, and Python 3.14.
- Vercel functions cannot run the Worker, cap request bodies near 4.5 MB and were not verified for Python 3.14. A Vercel-only attempt (branches HK-82 to HK-84) was dropped.
- The engineer has an Oracle Cloud account.

## What else was considered

| Option | Why not | Would suit |
| --- | --- | --- |
| One Oracle Always Free VM (chosen) | see Consequences | a demo or small team, no cost |
| Vercel for web and API, cron tick for the Worker | needs Pro, adds up to a minute of latency, body limit stays | a stateless API |
| Fly.io, Railway or Render | costs money; no objection otherwise | no server upkeep |

## Decision

We will run PostgreSQL, the API (`uvicorn`), the Worker (`python -m app.worker`) and Caddy on one Ubuntu VM. Caddy serves `web/dist` and proxies `/v1/*` to the API, so the browser sees one origin, as with the Vite proxy. Files and steps are in `deploy/oracle/`.

## Consequences

- No platform limits on upload size or job duration; the Worker is the unchanged process.
- One machine is one point of failure, and the engineer patches the OS, backs up the database and watches disk. Backups are not set up here.
- Oracle can reclaim idle Always Free instances, and capacity for Ampere shapes can be unavailable in a region.
- Deploys are manual (`git pull` and restart); no CI deploy job, per ground rule 2.
- Secrets live in `/etc/hirekit/backend.env` (mode 600) only.

## Commits us to

- A VM the engineer maintains, and a domain or sslip.io name for HTTPS
