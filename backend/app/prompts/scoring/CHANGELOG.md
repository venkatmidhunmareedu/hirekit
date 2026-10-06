# scoring prompt changelog

## v1 (active)

- First version: scores each numbered criterion 0 to 4 with a verbatim quote or null, JSON reply per ADR-0010.
- Resume is the user message and is declared data; criteria sit inside `<criteria>` tags.
- Eval: NOT RUN. evals/scoring does not exist yet; the replay recordings and the 40-resume eval come with the engine gate tasks.
