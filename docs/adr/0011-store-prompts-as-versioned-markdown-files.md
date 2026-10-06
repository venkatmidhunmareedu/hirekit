# ADR-0011: Store prompts as versioned markdown files

- Status: Accepted
- Date: 2026-10-03
- Task: HK-40
- Deciders: midhun
- Area: llm prompts
- Reversibility: cheap: prompts are a handful of text files and one loader; moving to another store means re-keying `prompt_version` and re-making recordings

## Context

- The Worker sends a scoring, a criteria and a kit prompt through one gateway; each reply is checked by code and each recording is keyed by the request, so a silent prompt change breaks replay or hides a quality change.
- A prompt can be edited without anyone noticing unless its version is explicit; a score belongs to the pair (prompt text, model).
- Prompts take values that can be resume text, so rendering must validate inputs and never echo them in an error (tenet 7).
- The gateway caps `max_tokens` at 1500; the model, effort and cap should travel with the prompt, not sit in handler code.

## What else was considered

| Option | Why not | Would suit |
| --- | --- | --- |
| Markdown files `app/prompts/<name>/v<N>.md` with frontmatter, explicit versions, per-prompt fixtures and changelog (chosen) | needs a small loader and a frontmatter parser | prompts that are scored and changed over time |
| Bare `.txt` files with a `sha256[:8]` of the text as the version | a whitespace edit changes the version silently; no model, status or score is attached | one prompt that never changes |

## Decision

We will keep each prompt as `backend/app/prompts/<name>/v<N>.md` with YAML-style frontmatter (exact model id, effort, `max_tokens`, typed variables with `max_chars` and `enum`, owner, `eval_set`, status `draft`, `active` or `retired`), a `fixtures.json` and a `CHANGELOG.md`, loaded by `app.prompts`, because the version, model and status are then explicit and reviewable.

- `prompt_version` is `<name>-v<N>`. An `active` version is never edited; a change is a new file.
- `load_prompt(name)` serves the highest `active` version; a draft or retired one is loaded only with its explicit version.
- The loader substitutes `{{name}}` in one pass, validates variables before any call, and returns the text and frontmatter so callers take model, effort and `max_tokens` from the prompt.
- `app.prompts` is the only importer of `mint_prompt`, so a rendered prompt is the only way to build a `PromptText`.

## Consequences

- Every prompt change is a new file and a changelog line; a score is written beside it.
- The frontmatter is a strict YAML subset parsed in the loader, because PyYAML is only a transitive dependency; a richer need means adding it deliberately.
- A content edit under an unchanged active version is not yet caught by a test (a committed hash lock was left out).
- Revisit if prompts need per-tenant overrides or runtime editing.

## Commits us to

No new technology; the Python standard library only.
