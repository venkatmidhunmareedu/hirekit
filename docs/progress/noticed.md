# Noticed ledger

Things seen in passing or left undone while building, kept so they are not lost when a session ends.

Rule: every task appends its "Noticed" and "Not done" items here, in the same commit as the task. Open items are reviewed when a task starts. Status is `open`, `done` (name the fixing task) or `dropped` (say why).

This file was created on branch HK-52 because it was absent there; the same ledger exists on the HK-51 branch with other rows. Keep both sets of rows when the branches meet.

| ID | Source | Item | Why it matters | Owner | Status |
| --- | --- | --- | --- | --- | --- |
| N-W01 | HK-52 | typescript is held at 6.0.3 and eslint at 9.39.5 because typescript-eslint 8 and eslint-plugin-jsx-a11y do not yet accept 7 and 10 | A later bump needs those plugins first; `pnpm peers check` shows it | unassigned | open |
| N-W02 | HK-52 | Inter and JetBrains Mono are named in the tokens but not bundled | Screens render in the system-ui fallback until fonts are self-hosted | unassigned | open |
| N-W03 | HK-52 | The `/v1` proxy target defaults to `http://localhost:8080` (backend default PORT); override with `API_PROXY_TARGET` | A backend started on another port needs the variable | unassigned | open |
| N-W04 | HK-52 | Signed-in landing page is a placeholder "Roles" heading; no role list, top-bar stage filter or budget pill yet | Design.md sections 5 and 7.10 describe them | unassigned | open |
| N-W05 | HK-52 | No CI config exists in the repo, so nothing runs `make check` for web/ in CI | The gate is local only | unassigned | open |
| N-W06 | HK-52 | `make help` at the root lists only the backend targets, not `dev-web` and `build-web` | A new contributor will not see them | unassigned | open |
| N-W07 | HK-52 | Root `make check` runs backend then web; both write `../.bearing/state/.check-passed`, and web removes it at its start | The marker means both passed only because web runs last | unassigned | open |
| N-W08 | HK-52 | No Playwright end-to-end test against the real API through the proxy | The unit tests stub fetch; the cookie and CSRF round trip is unproven in a browser | unassigned | open |
| N-W09 | HK-67 | `HomePage` in `web/src/app/AppShell.tsx` is now unused (the role list replaced it on `/`) | Dead export; left so the HK-68 branch does not conflict on AppShell | unassigned | open |
| N-W10 | HK-67 | Stale-scores banner has no "Re-run scoring" action (`POST /v1/roles/{id}:rescore` not wired) | Design.md section 11 asks for banner plus action | unassigned | open |
| N-W11 | HK-67 | Ranked list lacks the "flagged only" and "has overrides" filters, row click to the candidate detail, and the budget pill | Design.md 8.3 and 7.10; detail is another task | unassigned | open |
| N-W12 | HK-67 | The upload zone shows one result per file from the 207 response only; the queue view has no file names, so after a reload per-file status is not shown, only waiting and running counts | Design.md 7.8 per-file status rows cannot be rebuilt from the API | unassigned | open |
| N-W13 | HK-67 | A criteria proposal that lands while the recruiter has unsaved edits replaces the editor draft | Edits can be lost; needs a warning or a disabled Propose button | unassigned | open |
| N-W14 | HK-67 | Response guards in `web/src/lib/guards.ts` are hand-written (no Zod, rule 7); `RankedCandidate` ignores `quote`, `source` and `override_note` which the detail task will need | Replace with generated types once more routes land | unassigned | open |
| N-W15 | HK-67 | Role edit after approval: the API says PUT criteria returns an approved role to Draft; no copy tells the recruiter which scores that makes stale beyond the editor note | Confirm the wording with the product owner | unassigned | open |
