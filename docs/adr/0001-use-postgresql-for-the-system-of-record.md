# ADR-0001: Use PostgreSQL for the system of record

- Status: Accepted
- Date: 2026-09-30
- Task: none yet (pre-scaffold)
- Deciders: midhun
- Area: database
- Reversibility: awkward: schema, migrations and role setup are written for Postgres; moving to SQLite means rewriting the access-control layer and constraints

## Context

- HireKit stores roles, criteria, candidates, raw and anonymized resume text, scores with overrides, stage history, feedback and a model call log (PRD.md section 7).
- Scale is small: about 40 seeded resumes, 2 roles, batches up to 100 (PRD.md sections 10 and 14).
- Data needs constraints: content-hash uniqueness for duplicate uploads (I-4), an append-only audit trail for stage moves and overrides (K-6), and raw text visible to recruiters only (PRD.md section 10).
- The repository has no code yet, so nothing else constrains the choice.

## What else was considered

| Option | Why not | Would suit |
| --- | --- | --- |
| PostgreSQL (chosen) | needs a running server, so local runs need Docker | (chosen) |
| SQLite | no database roles, so the raw-text access rule lives only in app code; weaker fit if the app is later hosted | a demo that must run from a single file with no Docker |
| MongoDB | the data is relational with constraints (score per candidate per criterion), not document-shaped | document-shaped data with no joins |

## Decision

We will use PostgreSQL, because constraints and roles should enforce the audit trail, duplicate detection and raw-text access, and because it is the catalogue default for a small team.

## Consequences

- Local development and the demo need Docker (or a local Postgres).
- Migrations are written for Postgres and each has a tested down step.
- Revisit if the demo must run with zero installs: SQLite becomes the option, and the raw-text access rule moves into application code.

## Commits us to

PostgreSQL
