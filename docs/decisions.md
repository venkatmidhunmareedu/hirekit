# Decision log

One row per technology decision. The ADR holds the full reasoning; this
table is the index. `tech-decision` maintains it.

| Date | Key | Choice | Recommended | Why it was chosen | ADR | Status |
| --- | --- | --- | --- | --- | --- | --- |
| 2026-09-30 | database | PostgreSQL | PostgreSQL | constraints and roles enforce audit trail, duplicate detection and raw-text access | ADR-0001 | Accepted |
| 2026-09-30 | backend language | Python (FastAPI) | Python (FastAPI) | best libraries for PDF/DOCX parsing, the anonymizer and eval metrics | ADR-0002 | Accepted |
| 2026-09-30 | frontend | React with Vite | React with Vite | authenticated table-heavy app with a separate API; no SEO need | ADR-0003 | Accepted |
| 2026-09-30 | messaging | Postgres-backed queue | Postgres-backed queue | load is about 100 jobs per batch; enqueue commits with the upload row; no new service | ADR-0004 | Accepted |
| 2026-09-30 | auth | Own session authentication | Own session authentication | two seeded roles and an offline demo need no identity provider | ADR-0005 | Accepted |
| 2026-09-30 | api style | REST with OpenAPI | REST with OpenAPI | one React client, one FastAPI service, contract generated from the code | ADR-0006 | Accepted |
