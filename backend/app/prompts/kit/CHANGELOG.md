# kit prompt changelog

## v1 (active)

- First version: 2 or 3 questions for one criterion, each with a strong and a weak answer, JSON reply per ADR-0010.
- The criterion (name, kind, rubric levels) sits inside `<criterion>` tags and is declared data; the job description is the user message. No resume or candidate text is ever part of this prompt.
- Eval: NOT RUN. evals/kit does not exist yet.
- Proposed, needs engineer confirmation (the PRD, the LLD and the schema are silent; the parser enforces them as named constants in `app/prompts/kit_parser.py`):
  - 2 to 3 questions per criterion (the handler keeps all for a kit and the first for a regenerate);
  - question at most 300 characters, strong and weak answers at most 500 characters each;
  - there is no probe field: the PRD asks only for a question with a strong and a weak answer.
