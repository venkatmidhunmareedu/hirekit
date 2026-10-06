# ADR-0009: Extract resume text with pypdf and zipfile with defusedxml

- Status: Accepted
- Date: 2026-10-03
- Task: HK-39
- Deciders: midhun
- Area: document text extraction
- Reversibility: cheap: extraction sits behind one function that returns a string, so a library can be swapped without touching callers

## Context

- The Worker extracts text from uploaded PDF and DOCX files (ADR-0008) before the anonymizer runs.
- The anonymizer cannot catch a name held in document metadata (for example a PDF Author field or a DOCX core property). The extractor must therefore return body text only, by construction.
- Uploads are untrusted input: a hostile file can be a decompression bomb, a page flood or crafted XML.
- ADR-0002 chose Python partly for PDF and DOCX libraries.

## What else was considered

| Option | Why not | Would suit |
| --- | --- | --- |
| PDF: pypdf (chosen; BSD-3, pure Python) | slower and less exact layout than the heavier tools | text-only extraction of ordinary resumes |
| PDF: pdfminer.six | heavier and pulls in cryptography | complex layouts needing positional analysis |
| PDF: PyMuPDF | AGPL licence | a project that accepts AGPL or buys a commercial licence |
| DOCX: stdlib zipfile plus defusedxml, reading `word/document.xml` only (chosen) | we parse the XML ourselves | body text only, few dependencies |
| DOCX: python-docx | pulls in lxml and skips tables | a need to edit or build DOCX files |
| DOCX: stdlib xml.etree | ruff S314 flags parsing untrusted XML and AGENTS rule 6 bans suppressions | trusted XML only |

## Decision

We will extract PDF text with pypdf and DOCX text with zipfile and defusedxml, because both keep to body text, stay light on dependencies and keep a permissive licence.

- PDF: cap pages at about 20, check a deadline between pages, read page text only and never document metadata.
- DOCX: open the archive, read `word/document.xml` only, enforce an uncompressed-size cap before reading, parse with defusedxml. Core properties and other parts are never opened.
- The extractor returns body text only; metadata never enters the pipeline.

## Consequences

- Dependency policy: pypdf and defusedxml are pinned in `backend/pyproject.toml`, resolved in `backend/uv.lock`, and scanned by pip-audit in CI (`make check`). Both are permissive licences (pypdf BSD-3; defusedxml PSF). They are added by a later task, not this one.
- Harder: text in headers, footers or text boxes may be missed in DOCX, and scanned PDFs yield no text and fail as already planned (ADR-0008 retry).
- Anonymization stays a floor, not proof of fairness; this ADR only closes the metadata route.
- Revisit if extraction quality on the eval resumes is poor or pip-audit flags either library.

## Commits us to

pypdf, defusedxml (outside the standard stack); the Python stdlib zipfile module
