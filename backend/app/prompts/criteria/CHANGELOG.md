# criteria prompt changelog

## v1 (active)

- First version: proposes 4 to 6 criteria (at most 8) with a kind, an integer weight 1 to 5 and five rubric levels 0 to 4, JSON reply per ADR-0010.
- The job description is the user message and is declared data. The prompt takes no variables and never mentions candidates.
- Eval: NOT RUN. evals/criteria does not exist yet.
- Proposed, needs engineer confirmation (the PRD, the LLD and the schema are silent; the parser enforces them as named constants in `app/prompts/criteria_parser.py`):
  - criteria count 1 to 8 (the prompt asks for 4 to 6); an empty list is rejected;
  - weight is an integer 1 to 5, default 3 for must_have and 1 for nice_to_have (the schema only requires 0 < weight < 1000; no sum is required);
  - name at most 80 characters, descriptor at most 200 characters, both single-line, names unique ignoring case and spacing.
