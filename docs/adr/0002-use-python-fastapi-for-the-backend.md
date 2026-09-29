# ADR-0002: Use Python (FastAPI) for the backend

- Status: Accepted
- Date: 2026-09-30
- Task: none yet (pre-scaffold)
- Deciders: midhun
- Area: backend language
- Reversibility: awkward: the anonymizer, quote checker and evals are written against Python libraries and would be rewritten in another language

## Context

- The core work is text: PDF and DOCX extraction (PRD.md I-1, I-2), an anonymizer that removes names and other identity signals (A-1 to A-8), quote verification (S-2) and eval metrics including weighted kappa (PRD.md section 8.2).
- The model call is a plain HTTP call to OpenRouter with `claude-haiku-4-5` (PRD.md G-1); the provider is settled by the PRD, so it is not decided here.
- No existing code or stated team preference.

## What else was considered

| Option | Why not | Would suit |
| --- | --- | --- |
| Python with FastAPI (chosen) | weaker static typing, and batch scoring needs a worker | (chosen) |
| TypeScript (Node) | thinner NLP and document-parsing libraries, so more of the anonymizer would be hand-written | one language end to end, with the team happy to write the anonymizer rules by hand |
| Go | weakest ecosystem for PDF, NLP and eval tooling | a service where deployment simplicity outweighs text-processing libraries |

## Decision

We will use Python with FastAPI, because the anonymizer and the evals carry the product's fairness claim and Python has the strongest libraries for both.

## Consequences

- Needs the `bearing-backend` plugin for Python stack skills and templates.
- Batch scoring of up to 100 resumes needs a background worker, designed with the `background-jobs` skill.
- Revisit if a single-language stack becomes a hard requirement.

## Commits us to

Python, FastAPI
