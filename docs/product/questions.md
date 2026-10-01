# Open questions: HireKit

PRD: PRD.md   Updated: 2026-09-30
Entries: 12   Open: 12   Needs your confirmation: 6

Basis, for every entry:
- stated: the input answers it elsewhere; the passage that wins is named.
- inferred: only one reading is consistent with the rest of the input.
- convention: the input is silent and the team's standards settle it.
- assumption: nothing settles it; a choice was made so the team is not blocked.

## Needs your confirmation

- Q-001 Which criteria weights are fixed by type and which are editable per criterion? Assumed: (c) defaults by type, editable per criterion; must-haves always reported separately. (US-00-001, US-00-002, US-00-008)
- Q-002 Should auth be a seeded login or a real identity provider for the first version? Assumed: (a) seeded logins for one recruiter and a few interviewers. (US-00-012, US-00-001)
- Q-003 Can interviewers see resume text, or only the kit, criteria and candidate ID? Assumed: (a) no resume text. (US-00-012, US-00-014)
- Q-004 Who assigns interviewers to candidates, and how? Assumed: (a) recruiter assigns per candidate. (US-00-016, US-00-012, US-00-014)
- Q-005 When criteria change after approval, what happens to an existing interview kit? Assumed: (b) kit marked stale, regenerate on request. (US-00-002, US-00-013)
- Q-006 How does a demo audience reach the app: run locally or a hosted instance? Assumed: (a) one local command first. (US-02-003)

## Register

| Q | Status | Kind | Where | Basis | Question | Readings | Decision | Why | Affects |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Q-001 | open | gap | PRD §12.4 | assumption | Which criteria weights are fixed by type and which are editable per criterion? | (a) all weights fixed by type; (b) all editable; (c) defaults by type, editable per criterion | (c) defaults by type, editable per criterion; must-haves always reported separately | the PRD only requires a weighted total (REQ-024) and separate must-haves | US-00-001, US-00-002, US-00-008 |
| Q-002 | open | open-question | PRD §12.5 | assumption | Should auth be a seeded login or a real identity provider for the first version? | (a) seeded logins; (b) a real provider | (a) seeded logins for one recruiter and a few interviewers | the PRD lists it as open and the first build needs no external accounts | US-00-012, US-00-001 |
| Q-003 | open | gap | REQ-054 | assumption | Can interviewers see resume text, or only the kit, criteria and candidate ID? | (a) no resume text; (b) anonymized text only; (c) raw and anonymized | (a) no resume text | PRD 3.1 lists only the kit, criteria and assigned candidates; raw text is recruiter-only (REQ-049) | US-00-012, US-00-014 |
| Q-004 | open | gap | PRD §3.1 | assumption | Who assigns interviewers to candidates, and how? | (a) recruiter assigns per candidate; (b) interviewers see all candidates; (c) assigned per role | (a) recruiter assigns per candidate | PRD 3.1 says interviewers see "the candidates assigned to them" but no statement creates assignments | US-00-016, US-00-012, US-00-014 |
| Q-005 | open | gap | REQ-006 | assumption | When criteria change after approval, what happens to an existing interview kit? | (a) nothing; (b) kit marked stale, regenerate on request; (c) kit deleted | (b) kit marked stale, regenerate on request | REQ-006 covers only scores, and a stale kit is the same kind of drift | US-00-002, US-00-013 |
| Q-006 | open | gap | docs/designs/hirekit-build-plan.md | assumption | How does a demo audience reach the app: run locally or a hosted instance? | (a) one local command, e.g. `make demo`; (b) a hosted instance serving the recording | (a) one local command first | the PRD names no host and the budget is USD 8 | US-02-003 |
| Q-007 | open | open-question | PRD §12.2 | stated | Should the ranked list show names or anonymized IDs by default? | (a) names; (b) IDs with a logged "Reveal identity" action | (b) IDs with a logged reveal | Design.md section 9 recommends anonymous by default | US-00-009, US-00-011, US-00-015 |
| Q-008 | open | open-question | PRD §12.1 | stated | Should interviewers see model resume scores before submitting their own feedback? | (a) yes; (b) only after submitting | (b) only after submitting | PRD 3.1 names hiding as the safe default, to avoid anchoring | US-00-014, US-00-015 |
| Q-009 | open | open-question | PRD §12.3 | stated | Is the 0 to 4 scale right, or should it be 1 to 5? | (a) 0 to 4; (b) 1 to 5 | (a) 0 to 4, where 0 means no evidence | PRD 5.4 proposes 0 to 4 and REQ-022 relies on a lowest level | US-00-006, US-00-007, US-00-008, US-00-010, US-00-014 |
| Q-010 | open | open-question | PRD §12.6 | inferred | Are human-written labels for a subset of resumes worth adding to the agreement eval? | (a) not in the first build; (b) 10 to 15 human labels | (a) not in the first build; the report says the eval is a consistency check | the build plan (docs/designs) flags model-vs-model labels and sets the wording | US-02-005 |
| Q-011 | open | gap | REQ-022 | inferred | Is "the lowest rubric level" 0 or 1? | (a) 0; (b) 1 | (a) 0 | PRD 5.4 defines 0 as no evidence | US-00-006, US-00-007 |
| Q-012 | open | open-question | REQ-061 | stated | Is the per-role data-retention setting part of the first build? | (a) yes; (b) no, stretch | (b) no; REQ-061 is out of scope for now | PRD 2.3 and build order step 10 mark it a stretch | US-00-005 |
