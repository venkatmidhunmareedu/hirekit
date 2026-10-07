# Product

<!-- impeccable:product-schema 1 -->

Distilled from `PRD.md` (product) and `Design.md` (UI rules); those stay the sources of truth.

## Platform

web

## Users

- Recruiters: define a role, approve criteria, upload resumes in bulk, review the ranked list with evidence, override scores with a note, move candidates between stages, and are the only role that can reject. They also see the gateway cost log.
- Interviewers: see only their assigned candidates, view the interview kit, submit scored feedback per criterion, and use the comparison view.

## Product Purpose

Make resume screening and interviewing consistent, evidence-backed and bias-resistant. AI proposes criteria, scores and interview kits; people make every decision. Success is a recruiter who can defend every score and compare candidates fairly.

## Positioning

Every model score points to a quote that code found in the anonymized resume, or says "no evidence found". The model only ever sees anonymized text, and no candidate is rejected, hidden or re-staged without a recruiter action.

## Operating Context

A recruiter works through a role in order: criteria, upload, ranked list, overrides and stages, interview kit, feedback and comparison. Demo and test runs use recorded model responses; live model calls are budget-capped at USD 8.

## Capabilities and Constraints

- Anonymization is a floor, not proof of fairness: schools, clubs, gendered wording and career gaps can remain. Never claim otherwise in copy.
- The 40-resume agreement eval is a consistency check (one model family wrote the resumes, labels and scores) and must be labelled that way.
- A verified quote proves the text exists in the resume, not that it supports the score; evidence copy must not imply otherwise.
- Out of scope: job board posting, calendar scheduling, retention automation.
- Open: whether the ranked list shows names or IDs (Design.md recommends IDs), whether interviewers see model scores before their own feedback, and whether a dark theme is required for launch. The palette question is closed: the cool-grey working surface with one indigo primary (Design.md section 3; HK-86), which supersedes "reading room".

## Brand Commitments

The product is named HireKit. Visual identity and UI rules live in `Design.md`.

## Evidence on Hand

Synthetic data only: 2 roles and 40 resumes (PDF and DOCX), labels, and 20 name-swap pairs. No real people, testimonials, customers or benchmarks exist; do not invent any.

## Product Principles

1. Humans decide; the model proposes.
2. No score without evidence: a checked quote or an explicit "no evidence found".
3. Identity signals never reach the model, and the UI never overstates what anonymization proves.
4. Nothing is rejected, hidden or re-staged except by a recruiter action.

## Accessibility & Inclusion

WCAG 2.2 AA.
