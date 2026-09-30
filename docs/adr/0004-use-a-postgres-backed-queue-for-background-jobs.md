# ADR-0004: Use a Postgres-backed queue for background jobs

- Status: Accepted
- Date: 2026-09-30
- Task: HK-1
- Deciders: midhun
- Area: messaging
- Reversibility: awkward: a broker needs an outbox to keep enqueue in the same transaction as the upload and the stale-marking (corrected on 2026-09-30 after the HLD review; the first text said cheap)

## Context

- Scoring runs in the background. PRD section 10 requires that uploading 100 resumes does not block the UI, with per-file progress and a visible queue (REQ-050, REQ-053).
- Load is small: about 100 jobs per batch, one model call per resume, a few seconds each (assumption: one call per resume scores all criteria).
- PostgreSQL is already chosen (ADR-0001), so a jobs table adds no service.
- A batch can run for minutes, so jobs must survive a restart.

## What else was considered

| Option | Why not | Would suit |
| --- | --- | --- |
| Postgres-backed queue (chosen) | claim, retry and dead-letter logic are ours to write | (chosen) |
| RabbitMQ | a second service to run and secure; enqueue is not in the database transaction | many independent consumers, routing, or hundreds of jobs a second |
| Redis Streams | another store to run, and persistence to configure or jobs vanish on restart | very high rates with several consumer groups |
| In-process background tasks | jobs die with the process, so a restart silently drops a batch | throwaway scripts with no durability need |

## Decision

We will use a Postgres jobs table, claimed with a row lock that skips locked rows, because the enqueue commits with the upload row, per-file status is a column, and the load is far below what Postgres handles.

## Consequences

- Retries, dead letters and a deadline per job are written here, with the `background-jobs` skill.
- Workers multiply the model call rate; the gateway budget (REQ-043) stays the ceiling.
- Revisit if job volume passes a few hundred a second or a second consumer team needs the events.

## Commits us to

PostgreSQL (jobs table, `FOR UPDATE SKIP LOCKED`)
