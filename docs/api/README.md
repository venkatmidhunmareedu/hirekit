# HireKit API documentation

- **Contract:** `backend/api/openapi.yaml` (OpenAPI 3.1), committed. The React client is generated
  from it (ADR-0006). It was written from `docs/design/api-lld.md`, section 3, and is the promise
  the handlers keep.
- **Readable design:** `docs/api/API.md`, generated from the contract. Never edit it by hand;
  change the spec and rerun:
  `uv run --quiet --with pyyaml==6.0.3 python <bearing>/skills/openapi-spec/scripts/api_doc.py --spec backend/api/openapi.yaml --style <bearing>/skills/openapi-spec/references/api-style.md --out docs/api/API.md`
- **Served docs:** the running service serves `/docs` (Swagger UI) and `/openapi.json` (the schema
  FastAPI builds from the code) when `ENV` is not `production` (`backend/app/main.py`). The committed
  file and the served schema must agree: `backend/tests/test_openapi_drift.py` fails `make check`
  when the code serves a route the committed spec does not list.
- **Lint:** `npx @redocly/cli@2.54.3 lint backend/api/openapi.yaml`. Valid, with three accepted
  warnings: no `info.license` (the project licence is not decided), the localhost server URL, and no
  4xx on the two health routes.
- **Drift is one way for now:** the spec is ahead of the code (the design is written first). Routes in
  the spec and not yet in the code are expected until each work item of the Api design lands.

## Style, and where this API differs from the kit's defaults

The rules are in the openapi-spec skill's `references/api-style.md`. HireKit follows them except as
recorded, with the reason, in the spec's `info.x-conventions`:

| Rule | HireKit | Why |
| --- | --- | --- |
| Bearer JWT | Session cookie `hirekit_session` plus an `X-CSRF-Token` header on every POST, PUT and DELETE | ADR-0005: two seeded roles need no identity provider |
| `Idempotency-Key` on creating POSTs | Not used | Duplicates are stopped in the database (unique open-job indexes, hash duplicate flags, idempotent assignment, 409 on a repeat feedback submit); only `POST /v1/roles` can double-create |
| Cursor pagination on every list | Cursor on the cost log; limit and offset on the ranked list and the queue view | The ranked order is a computed weighted total; a role holds at most about 1,200 candidates |
| `X-API-Version`, rate-limit headers | Not in the first build | One client, one maintainer, local demo (HLD section 1) |
| Record not visible is 404 | Yes, including an interviewer's unassigned candidate | Existence is not leaked (AC-US-00-012-3) |

## What an interviewer never receives

Resume text (raw or anonymized), evidence quotes, override notes, flag reasons, audit history, file
names, identity names, another interviewer's feedback, or a model score before they submit their own
feedback. The field-visibility table is in `docs/design/api-lld.md` section 3.
