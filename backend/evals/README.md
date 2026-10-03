# Evals

Two evals score the 40 seed resumes (`seed/`) and report on them: the agreement eval (scores
against `seed/labels.csv`) and the name-swap eval (20 swapped pairs). One scoring pass of 40
calls serves both. Only scoring calls are recorded here; criteria and kit recordings come with
HK-50.

## Run the evals

    make eval                                  # replay only, prints both reports
    make eval EVAL_ARGS="--out /tmp/ev --label haiku-run-1"

It needs `make db && make migrate` (every call is logged, replays at cost 0). It never makes a
live call: with MODEL_MODE=live it refuses, and a missing recording stops the run with the
request key and exit code 2. Exit codes: 0 both pass, 1 an eval fails, 2 refused or missing
recording. `--out DIR` writes `agreement.md` and `name-swap.md`; without it nothing is written.

## Record

Recording is manual, spends money and goes through `make record`, which runs the preflight
(credit limit, budget), your command, then writes the spend ledger.

    make record RECORD_CMD="uv run python -m app.evals.record --smoke"   # 1 resume, about 1 call
    make record RECORD_CMD="uv run python -m app.evals.record"           # all 40 resumes

The command prints its plan first (calls, model id, host of MODEL_BASE_URL, recordings dir) and
the call and token counts after. If it stops part-way, the replies already recorded stay.

### Development run on a free proxy

Set in the environment (never commit a key):

- `MODEL_BASE_URL`: the OpenAI-compatible endpoint
- `MODEL_ID`: the exact model id the proxy serves
- `OPENROUTER_API_KEY`: the proxy key
- `RECORDINGS_DIR`: a scratch directory that is NOT committed
- `KEY_CREDIT_LIMIT_CONFIRMED=yes`: your statement that the key has a provider-side limit

Run `make eval` with the same `RECORDINGS_DIR`. Results from a model other than Haiku are
development only: never commit those recordings, and never quote the results as eval results.

### Evidence run

Model `anthropic/claude-haiku-4.5` via OpenRouter, with a key limited to at most USD 8, and
the default `RECORDINGS_DIR` (`backend/recordings`). Commit the recordings and the updated
`spend-ledger.json` afterwards.

Recordings are keyed by model id and prompt version (and the full prompt text), so any prompt
edit means re-recording. Freeze the prompts before the evidence run.

## Cost

The smoke run is about USD 0.005. One full scoring pass (40 calls) is about USD 0.2 to 0.3, at
the HLD's assumption of USD 0.005 per call; the smoke run prints the token counts to confirm it.

## What the results mean

The labels come from the same model family that wrote the resumes and the scores, so the
agreement eval is a consistency check, not ground truth. The name-swap eval shows that the
named signals were removed and scores held; it does not show the absence of proxy bias.
Anonymization is a floor, not proof of fairness.
