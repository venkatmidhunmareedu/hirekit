# ADR-0007: Use one repository with separate backend and web folders

- Status: Accepted
- Date: 2026-09-30
- Task: HK-1
- Deciders: midhun
- Area: repository layout
- Reversibility: awkward: splitting later means moving one folder into a new repository, keeping its history with a filter, and re-pointing the CI and the generated API client

## Context

- ADR-0002 picks Python (FastAPI) and ADR-0003 picks React with Vite. The kit scaffolds one stack per repository (`new-repo`, `onboard-repo --stack`).
- The onboarding on 2026-09-30 put the python-api template at the repository root and planned React in `web/`.
- The demo needs the API, the worker and the web app running together, from one clone (docs/designs/hirekit-build-plan.md).
- The recommendation shown to the user was two repositories, `HireKitApi` and `HireKitClient`. The user chose one repository with the backend and the web app kept separate inside it.

## What else was considered

| Option | Why not | Would suit |
| --- | --- | --- |
| One repository, `backend/` and `web/` folders (chosen) | the repo plan holds one stack per entry, so this repository is planned with `stack: none` and two apps; the root Makefile must delegate to two gates | a solo maintainer or small team that wants one clone and one demo command |
| Two repositories, one per stack | two clones, the generated API client crosses repositories, and the demo needs both running | separate teams or release cadences for the API and the client |
| One repository, backend at the root and `web/` beside it | mixes the Python tooling with the root, so the root Makefile is both a gate and a delegator | a repository that will only ever have a thin web folder |

## Decision

We will keep one repository, `HireKitApp`, with the Python service in `backend/` and the React app in `web/`, each with its own gate, and a root Makefile that runs both, because one clone and one demo command matter more here than the kit's one-stack-per-repository scaffolding.

## Consequences

- The Makefile and Python files now at the repository root move into `backend/`; the root Makefile delegates `check` to `backend/` and `web/`. AGENTS.md and CLAUDE.md are amended to match.
- `new-repo` cannot create this repository from the plan; each folder is adopted with `onboard-repo --stack python-api` and `--stack react-web`, to be confirmed on the first task.
- CI, hooks and the Claude settings stay at the root and cover both folders.
- Revisit if the API and the client get separate owners or release cadences.

## Commits us to

A root Makefile that delegates to `backend/` and `web/`; stack ids python-api and react-web
