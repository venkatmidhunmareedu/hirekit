# ADR-0012: Build seed resumes with fpdf2 and python-docx as dev dependencies

- Status: Accepted
- Date: 2026-10-03
- Task: HK-47
- Deciders: midhun
- Area: seed data tooling
- Reversibility: cheap: the builder is one script and the output files are committed, so dropping a library means rewriting the script and rebuilding the files

## Context

- US-02-007 and REQ-060 need 40 synthetic resumes in PDF and DOCX with varied formats; the repository has no writer for either type. `pypdf` and `defusedxml` only read (ADR-0009).
- The resumes are generated from text sources in `seed/resumes/` and the built files are committed, so the seed command and the runtime never import a builder library.
- The engineer chose both libraries when asked (from the request): fpdf2 for PDF, python-docx for DOCX.
- Real-world DOCX files carry tables, runs and styles; the extractor must be tested on files like those, not on a minimal zip.
- ADR-0009 rejected python-docx for reading text from uploads, because it hides text-box and nested content. This ADR uses it only to write files, which does not touch that reasoning.

## What else was considered

| Option | Why not | Would suit |
| --- | --- | --- |
| fpdf2 and python-docx in the dev group (chosen) | two new dev dependencies to pin and audit | seed files that must look like real PDF and DOCX resumes |
| reportlab for PDF, python-docx for DOCX | larger dependency; layout power the seed does not need | resumes with complex columns and embedded fonts |
| fpdf2 for PDF, DOCX written with `zipfile` and hand-made XML | DOCX would be a minimal file, so the extractor would be tested on easy input only | a seed where only plain text matters |

## Decision

We will build the seed PDF and DOCX files with fpdf2 and python-docx, both in the `dev` dependency group, run by one script in `backend/scripts/`, with the output committed under `seed/`, because the extractor and the evals then meet realistic files and the runtime gains no dependency.

- The `dev` group is the only place either library appears; `app/` must not import them (a test checks this).
- The builder is deterministic (fixed metadata and dates) so a rebuild gives the same bytes and review diffs stay small.
- Both packages are pinned through `uv.lock` and pass `pip-audit` in `make check`.

## Consequences

- Two more packages to keep patched; a vulnerable release blocks the gate like any other.
- A rebuild after a library upgrade may change the file bytes and so the candidate `content_hash` values; the seed data must be rebuilt and committed together.
- Revisit if the seed needs fonts or layouts fpdf2 cannot do, or if the dev group is installed in production images.

## Commits us to

- fpdf2 (outside the standard stack)
- python-docx (outside the standard stack)
- pillow, lxml and fonttools, pulled in transitively by the two (dev group only)
