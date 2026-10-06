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
| 2026-09-30 | password hashing library | argon2-cffi | argon2-cffi | ADR-0005 commits to argon2 and left the library to the Api design; argon2-cffi is the standard argon2id implementation and the user approved the new dependency | ADR-0005 (library confirmed here) | Accepted |
| 2026-10-03 | document text extraction | pypdf (PDF); zipfile plus defusedxml (DOCX) | pypdf; zipfile plus defusedxml | body text only by construction, permissive licences, light dependencies; rejected pdfminer.six, PyMuPDF (AGPL), python-docx, xml.etree | ADR-0009 | Accepted |
| 2026-10-03 | scoring reply schema | JSON with 1-based criterion positions and a null quote for no evidence | JSON with 1-based criterion positions | fewer output tokens and no invented ids; positions mapped to criterion ids in code | ADR-0010 | Accepted |
| 2026-10-03 | prompt storage | Versioned markdown files with frontmatter under `app/prompts/` | Versioned markdown files | explicit `<name>-v<N>` versions with model, status and fixtures; rejected bare `.txt` with a sha256[:8] version (silent change on whitespace edits) | ADR-0011 | Accepted |
| 2026-10-03 | seed data tooling | fpdf2 (PDF) and python-docx (DOCX), dev group only | fpdf2 and python-docx | realistic PDF and DOCX seed files for the extractor and evals with no runtime dependency; rejected reportlab (heavier) and a zipfile-written DOCX (too simple a test input) | ADR-0012 | Accepted |
| 2026-10-07 | web component and styling system | shadcn/ui on Tailwind v4 | shadcn/ui on Tailwind v4 | Bearing React stack; owned component source and theme tokens fix the inconsistent UI; rejected tidying the hand-written CSS (already tried) and MUI or Mantine (own theming and look) | ADR-0013 | Proposed |
