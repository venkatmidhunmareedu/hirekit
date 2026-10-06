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
| N-W09 | HK-68 | The contract has no call that lists users or a candidate's assignments, so the assign form takes a raw interviewer user id and shows only assignments made in this visit | Recruiters cannot pick an interviewer by name or see who is assigned; needs GET /v1/users?role=interviewer and assignments on CandidateDetail | unassigned | open |
| N-W10 | HK-68 | CandidateDetail has no weighted total, and Comparison has no totals, stage, quote or weight | Design.md 8.4 and 8.7 ask for a total in the header, a pinned totals row, stage controls in compare headers and expandable evidence; none are possible from the contract | unassigned | open |
| N-W11 | HK-68 | Feedback rows carry only interviewer_id, no name | Recruiters see "Interviewer 1f3a9c2b" (id prefix) instead of a name | unassigned | open |
| N-W12 | HK-68 | GET /v1/candidates/{id}/text returns raw_text (personal data) to the browser even though the UI never shows it | An anonymized-only variant or a query flag would keep PII out of the client | unassigned | open |
| N-W13 | HK-68 | Role criteria are read through `getRoleCriteria` in features/kit/api.ts; HK-67 will have its own role reader | Two readers of GET /v1/roles/{id}; merge into features/roles when both land | unassigned | open |
| N-W14 | HK-68 | Nothing links to /compare or to /candidates/$id yet; the ranked list (HK-67) must pass `ids` (comma separated, 2 to 4) | The screens are reachable only by URL until then | HK-67 | open |
| N-W15 | HK-68 | Interviewers have no landing page of their own: "/" is the Roles page, which GET /v1/roles forbids them | An interviewer lands on a 403; send them to /me/candidates | unassigned | open |
