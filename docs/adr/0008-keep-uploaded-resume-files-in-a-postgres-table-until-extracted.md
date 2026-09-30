# ADR-0008: Keep uploaded resume files in a Postgres table until extracted

- Status: Accepted
- Date: 2026-09-30
- Task: HK-1
- Deciders: midhun
- Area: object storage
- Reversibility: cheap: the file is read and written through two functions, so a volume or a bucket can replace the table without touching callers

## Context

- The Api receives an upload and the Worker, a separate process, extracts the text (HLD sections 2 and 3). Job payloads hold ids only (tenet 7, ADR-0004), so the bytes need a place both can reach.
- Extraction can fail (scanned image, corrupt file); US-00-003 requires a retry action, which needs the original file to survive the failure.
- Size: batches of up to 100 files of about 200 KB (assumption) is about 20 MB (REQ-050).
- PostgreSQL is already chosen (ADR-0001) and the HLD review found this gap as a BLOCKER (docs/design/hirekit-hld.md, section 16).

## What else was considered

| Option | Why not | Would suit |
| --- | --- | --- |
| Postgres table with a bytea column (chosen) | large objects bloat backups if files are ever kept long; fine at 20 MB | small files, short lifetime, one database |
| Shared docker volume | outside the transaction, so a candidate row can exist without its file; outside database backups | one host with a durable volume and a cleanup job |
| Object storage (S3-compatible bucket) | a new service, credentials and network dependency for a local demo | hosted deployment with large or long-lived files |

## Decision

We will write each uploaded file into a `resume_file` table in the same transaction as its candidate row and its job, and delete the row after extraction succeeds, because it keeps the upload atomic, needs no new service, and lets a failed extraction be retried.

## Consequences

- Personal data lives in the database for as long as extraction has not succeeded; a failed file stays until a person retries or deletes it.
- The table is added to docs/design/data-model.md (not written yet).
- Revisit if files are kept after extraction, exceed a few megabytes each, or the app is hosted.

## Commits us to

PostgreSQL (bytea column)
