# ADR-0010: Use a position-based JSON reply for scoring

- Status: Accepted
- Date: 2026-10-03
- Task: HK-39
- Deciders: midhun
- Area: llm output schema
- Reversibility: cheap: one parser and one prompt change; recordings must be re-made because the reply format changes the replay key

## Context

- A score needs a quote that code found in the anonymized text, or "no evidence found" (PRD domain rules). Quote matching is whitespace-normalized only.
- The gateway caps `max_tokens` at 1500 and stops at USD 8 total, so reply size matters.
- A model asked to echo criterion UUIDs can invent or garble them.

## What else was considered

| Option | Why not | Would suit |
| --- | --- | --- |
| Positions, `{"scores":[{"criterion":<1-based position>,"value":0-4,"quote":str\|null}]}` (chosen) | code must map positions back to ids | short criteria lists in a fixed order |
| Criterion UUIDs in the reply | more output tokens and invented ids | a list of criteria too long or unordered to number |
| Free text parsed by regex | fragile; fails the schema-retry path | no structured output at all |

## Decision

We will have the model reply with JSON `{"scores":[{"criterion":<1-based position>,"value":0-4,"quote":str|null}]}` and map positions to criterion ids in code, because it spends fewer output tokens and cannot invent ids.

- The "no evidence found" sentinel is a JSON null quote; the literal string "no evidence found" is accepted as an alias.
- The parser accepts a null quote with a non-zero value; the scoring handler stores it as 0. This rule is fixed in that one place.
- A quote that is a string is still checked by code against the anonymized text before it is stored.

## Consequences

- An out-of-range or duplicate position is a schema failure and follows the existing schema-retry path.
- Changing the reply shape changes the prompt and so the replay key; recordings are re-made.
- Revisit if criteria lists stop being short or fixed in order.

## Commits us to

No new technology; pydantic (already in use) for the parser.
