# HireKit: Design Guide

Version 0.1 (draft) · Companion to `PRD.md`

---

## 1. Design principles

1. **Evidence first.** Every score sits next to its proof. A score without a quote (or an explicit "no evidence found") never appears alone.
2. **Humans decide.** The interface makes overriding easy and makes it impossible to reject by accident. Model output is always labelled as a suggestion.
3. **Calm and fair.** Neutral surfaces, restrained color, no red-for-bad shortcuts that pre-judge candidates.
4. **Scannable.** Recruiters review many candidates. Dense but ordered tables, clear hierarchy, keyboard-friendly.
5. **Honest states.** Loading, failed, flagged, stale and budget-blocked states are all designed, not left as afterthoughts.

---

## 2. Brand

### 2.1 Name

**HireKit** is set as one word with a capital H and a capital K. In two-tone use, "Hire" takes the text color and "Kit" takes the accent, set in Source Serif 4 with "Kit" in italic (section 4).

### 2.2 Logo

The mark is a **briefcase with a check**: a rounded body, a handle, and a check mark. The briefcase says "hiring", the "kit" idea is in the toolbox form, and the check stands for verified evidence.

- **Wordmark:** Source Serif 4 medium (500), 24px at standard size, "Kit" in italic.
- **Clear space:** at least the height of the briefcase handle on every side.
- **Minimum size:** mark alone 16px, mark with wordmark 96px wide.
- **Do not:** stretch, rotate, add gradients or shadows, or change the check color to something without enough contrast.

#### Mark source (SVG, 270 × 70 area, mark drawn in a 84 × 70 box)

The shape is unchanged. The emerald fills below are **superseded**: in the app the case and handle take `currentColor` set to `--primary` and the check takes `--primary-foreground` (section 3).

```svg
<svg width="96" height="80" viewBox="88 58 96 80" xmlns="http://www.w3.org/2000/svg" role="img">
  <title>HireKit</title>
  <path d="M116 76V70a6 6 0 0 1 6-6h26a6 6 0 0 1 6 6v6"
        fill="none" stroke="#3ECF8E" stroke-width="6" stroke-linecap="round"/>
  <rect x="93" y="76" width="84" height="58" rx="10" fill="#3ECF8E"/>
  <polyline points="116,106 129,119 154,92"
            fill="none" stroke="#1C1C1C" stroke-width="7"
            stroke-linecap="round" stroke-linejoin="round"/>
</svg>
```

Swap the two colors for other treatments (see section 3.3).

### 2.3 Palette status

Two earlier palettes are superseded: the emerald and near-black one (HK-80) and "reading room", the warm bone paper with ink-navy (HK-80), which HK-86 replaces. One palette ships: the working surface in section 3.

---

## 3. Color

**Direction: working surface (HK-86, supersedes "reading room").** HireKit is a tool people work in for long sessions, so the page is a cool grey surface, panels are white, text is ink-black, and one saturated indigo marks the action. The only other loud colour is the highlighter yellow, which appears only on evidence (quotes and matched text), so yellow means "this is the proof". It is deliberately not warm paper, not a gradient SaaS dashboard and not stock neutral.

All colors are OKLCH. Tokens live in `web/src/index.css` as shadcn role tokens (`--background`, `--primary`, ...) mapped through Tailwind's `@theme inline`. Dark follows `prefers-color-scheme`; no toggle at launch. Contrast is computed, not eyeballed: text 4.5:1 or better, control borders and the focus ring 3:1 or better, in both themes.

### 3.1 Role tokens

| Token | Light | Dark | Use |
|---|---|---|---|
| `--background` | `oklch(0.958 0.006 258)` | `oklch(0.17 0.012 265)` | Page: the cool-grey working surface |
| `--card`, `--popover` | `oklch(0.995 0.002 258)` | `oklch(0.225 0.014 265)` | Panels, dialogs, header: a clear step above the page |
| `--foreground` | `oklch(0.2 0.02 265)` | `oklch(0.95 0.006 265)` | Body text |
| `--muted-foreground` | `oklch(0.46 0.02 265)` | `oklch(0.74 0.015 265)` | Secondary text (at least 4.5:1 on page and panel) |
| `--primary` | `oklch(0.5 0.22 275)` | `oklch(0.74 0.14 275)` | The one action color: primary button, current nav item, wordmark "Kit" |
| `--primary-foreground` | `oklch(0.99 0.004 275)` | `oklch(0.18 0.03 275)` | Text on primary |
| `--secondary`, `--muted` | `oklch(0.92 0.008 260)`, `oklch(0.94 0.006 258)` | `oklch(0.28 0.014 265)`, `oklch(0.26 0.012 265)` | Quiet fills |
| `--accent` | `oklch(0.925 0.04 275)` | `oklch(0.31 0.06 275)` | Hover and selected fills |
| `--border` | `oklch(0.88 0.008 260)` | `oklch(0.32 0.014 265)` | Dividers and panel edges |
| `--input` | `oklch(0.6 0.015 262)` | `oklch(0.6 0.02 265)` | Control borders (3:1 against page and panel, WCAG 1.4.11) |
| `--ring` | `oklch(0.55 0.2 275)` | `oklch(0.74 0.14 275)` | Focus ring |
| `--destructive` | `oklch(0.47 0.16 27)` | `oklch(0.78 0.12 27)` | Destructive actions |

### 3.2 Evidence and state tokens

The highlighter is reserved for evidence. Do not use it for decoration, selection chrome or warnings.

| Token | Light | Dark | Use |
|---|---|---|---|
| `--mark` / `--mark-foreground` | `oklch(0.93 0.12 95)` / `oklch(0.25 0.04 80)` | `oklch(0.4 0.08 90)` / `oklch(0.96 0.03 90)` | Evidence quote background and matched text |
| `--ok` / `--ok-soft` | `oklch(0.42 0.1 160)` / `oklch(0.94 0.04 160)` | `oklch(0.8 0.1 160)` / `oklch(0.3 0.045 160)` | Verified quote, approved, saved |
| `--warn` / `--warn-soft` | `oklch(0.45 0.1 70)` / `oklch(0.955 0.045 85)` | `oklch(0.82 0.11 80)` / `oklch(0.32 0.05 80)` | Flagged quote, stale scores, budget near the limit |
| `--bad` / `--bad-soft` | `oklch(0.47 0.16 27)` / `oklch(0.945 0.03 27)` | `oklch(0.78 0.12 27)` / `oklch(0.31 0.05 27)` | Errors, budget reached, destructive confirmation |
| `--note` / `--note-soft` | `oklch(0.42 0.1 235)` / `oklch(0.945 0.025 235)` | `oklch(0.8 0.08 235)` / `oklch(0.3 0.04 235)` | Informational notices |

State tones describe the state of the work, never a candidate's worth. Do not color candidates red or green by score. Every tone pairs with an icon and a text label; color alone is never the signal. Text on a `-soft` fill uses the matching strong token and keeps 4.5:1.

### 3.3 Rules of use

- Primary is the only saturated chrome color. One primary button per view.
- The yellow `--mark` appears only behind evidence quotes and matched text.
- Surfaces are separated by borders and tone steps, not shadows. Panels are for independent objects (a role, a candidate); sections use a heading and spacing, with no rule above each one.
- Contrast is checked in both themes for text, control borders and the focus ring (WCAG 2.2 AA).

---

## 4. Typography

Three families, self-hosted through `@fontsource-variable` packages (no font host at runtime, so the type never falls back to Times). Fallbacks apply only while the files load.

| Role | Family | Fallback |
|---|---|---|
| UI text: navigation, tables, forms, body, section headings | Hanken Grotesk | `ui-sans-serif`, `system-ui`, `Segoe UI`, sans-serif |
| Serif: the wordmark, page titles and evidence quotes (italic) only | Source Serif 4 | `Iowan Old Style`, `Palatino Linotype`, Georgia, serif |
| Code, IDs, scores, cost figures | JetBrains Mono | `ui-monospace`, `SF Mono`, Menlo, monospace |

| Use | Family | Weight | Size / line height |
|---|---|---|---|
| Page title (`h1`) | Serif | 500 | 32 / 38 |
| Section heading (`h2`) | Text | 600 | 18 / 26 |
| Subheading (`h3`) | Text | 600 | 16 / 24 |
| Body | Text | 400 | 14 to 16 / 22 to 24 |
| Small / caption | Text | 400 | 12 / 18 |
| Evidence quote | Serif (italic) | 400 | 16 / 26, on `--mark` |
| Code, IDs, scores, cost figures | Mono | 400 | 12 to 13 / 20 |

The scale is set once in `@theme` and `h1` to `h3` take it from the base layer.

- Sentence case everywhere. No all caps, no title case in UI copy.
- Evidence quotes are always shown in quotation marks, in italic serif on the highlighter, so they read as source text, not model commentary.
- Line length for prose: at most 65 characters (`max-w-prose`).

---

## 5. Layout and spacing

- **Spacing scale (px):** 4, 8, 12, 16, 24, 32, 48.
- **Radii:** one `--radius` of 6px; controls use it, panels and dialogs step up to 8 and 10px. Status tags and the budget pill are fully rounded so they read as labels, not buttons.
- **Density:** controls 40px high (touch target), table rows 44px, comfortable reading density over compact.
- **Borders:** 1px `--border`. Panels use a hairline ring on a white fill over the grey page, not a shadow.
- **Shadows:** none, except a single subtle overlay shadow on menus and modals.
- **Grid:** 12 columns, 24px gutters. Content is at most 1280px wide (`max-w-7xl`); prose stays at 65 characters. Tables can use the full width.
- **App shell:** a collapsible sidebar on the left (shadcn Sidebar: a 16rem panel that folds to a 3rem icon rail, an off-canvas sheet below 768px; open by default, no cookie is read) with the wordmark at the top, a Main nav (recruiters: Dashboard, Roles; interviewers: Dashboard, My candidates) and, for recruiters, a Recent roles group of up to five roles (approved roles open their candidates, drafts their criteria). A slim sticky top bar (3.5rem) holds the sidebar trigger, a breadcrumb (the current page alone on a phone), the budget pill and the user menu. Content is at most 1280px (`max-w-7xl`) inside the main landmark; a skip link comes first. The current item carries `aria-current="page"` and a primary-colored mark that slides between items. Sticky panes sit under the 3.5rem bar (`lg:top-20`, `review-rail`). One primary button per view.
- **Breakpoints:** 640, 1024, 1440. The comparison view and the ranked table are desktop-first and scroll horizontally on small screens. Never truncate scores.

---

## 6. Iconography

- One outline icon set, 1.5px stroke, 20px default and 16px inline.
- Icons always sit next to text or carry an aria-label.
- Suggested set: check (verified), alert-triangle (flagged), pencil (override), lock (approved and locked), eye (reveal identity), upload, clock (stale), users (comparison).

---

## 7. Components

### 7.1 Buttons

| Type | Style | Use |
|---|---|---|
| Primary | `--primary` fill, `--primary-foreground` text | One per view: Approve criteria, Upload, Submit feedback |
| Secondary | White fill, `--gray-300` border, `--ink` text | Cancel, Edit, Export |
| Ghost | No fill, `--gray-700` text | Low emphasis actions |
| Destructive | `--danger` text with `--danger` border | Reject candidate, Delete criterion |

Reject is never a primary button, is never in a row hover shortcut, and always opens a confirmation.

### 7.2 Score chip

A compact chip showing a score on the rubric scale, for example `3 / 4`.

- Neutral gray fill, `--ink` text, mono numerals.
- Scores changed by a recruiter show the new value with a small pencil icon, and the original AI value as a smaller struck-through number beside it.
- No red or green fills. Optional subtle bar length to show the value.
- The chip does not say where the score came from. "Scores are AI suggestions" appears once per section (the ranked list, the Scores section); only a changed row adds "Changed by recruiter", next to the chip that carries the struck-through AI value. Chips live in the candidate detail, not in the ranked list.

### 7.3 Evidence block

The signature component of the product.

- Quote in italic with quotation marks, on a `--mist` tinted background with a left border in `--gray-300`.
- Status tag on the right:
  - **Verified** (check icon, `--success`): quote found in the resume text.
  - **No evidence found** (dash icon, `--gray-500`): shown in plain text, no quote box.
  - **Needs a look** (triangle icon, `--warning`): the AI's quote failed the check and was downgraded. Shows a "why" line.
- Long quotes are truncated after 3 lines with a "Show more" control.
- Review mode shows these blocks in the detail pane beside the list, so a recruiter reads evidence without leaving the ranking (8.3).

### 7.4 Criterion row

Criterion name, type tag (`Must-have` or `Nice-to-have`), weight, rubric summary, score chip, evidence block, and a "Change score" control. Must-have and nice-to-have criteria are grouped under separate headers.

### 7.5 Rubric editor

A table of criteria with inline-editable fields. Each criterion expands to show rubric descriptors per score level. A sticky footer holds "Save draft" and "Approve criteria". Approving opens a confirmation summarizing what will unlock (upload, scoring, kit).

### 7.6 Change score dialog

Fields: new score, required note (minimum 10 characters). Shows the AI suggestion and its evidence for reference. The save button is disabled until the note is filled. On save, the row shows "Changed by recruiter" immediately.

### 7.7 Hiring stage control

A dropdown per candidate, labelled "Hiring stage", showing the current stage with the same capitalised names as the filter, table and history. Changing the stage writes to the history immediately. The `Rejected` option is grouped separately at the bottom and needs a confirmation dialog with an optional reason.

### 7.8 Upload zone

Drag-and-drop area with a file picker. Shows per-file rows: name, type, size, status (queued, parsing, anonymizing, scoring, done, failed) with a progress indicator. Failed files stay in the list with a plain reason and a retry action.

### 7.9 Tables

- Sticky header, 44px rows, zebra off, hover row tint `--accent`.
- Numeric columns right-aligned in mono.
- Sortable columns show a direction icon. The active sort is announced to screen readers.

### 7.10 Budget indicator

A small persistent pill in the top bar for recruiters: `Budget USD 3.42 of 8.00` (on a phone only `USD 3.42` shows; the full text stays for screen readers). The Dashboard repeats it as a bar with the percentage.

- Default: neutral.
- 75% and above: `--warning` with icon.
- 100%: `--danger`, and model actions show a disabled state with the reason "Budget reached".
- Not clickable yet: no call log screen exists (N-W24).

**User menu.** An initials circle, the name and a chevron open a menu with the name, email, a role badge (shield for recruiter, speech bubble for interviewer, always with the word) and Sign out. A failed sign-out shows an alert under the bar.

### 7.11 Toasts and banners

- Toasts for confirmations (saved, uploaded). Auto-dismiss after 5 seconds and pause on hover.
- Banners for persistent states: role is `Draft`, scores are out of date, budget blocked.

---

## 8. Key screens

### 8.1 Role list

One row per role: title, status (`Draft` or `Approved`) and a single action that carries the same label as the role's next-up (8.2). Candidate counts appear in the row only when the roles API returns them (it does not yet). "New role" is the one primary button.

### 8.2 Role workspace: header and criteria

Every role screen (criteria, candidates, interview kit) shares one header:

- Title and status tag.
- **Next up**: one action computed from state by `nextUp` (`features/roles/nextUp.ts`): Draft with no criteria "Propose criteria"; Draft with criteria "Approve criteria"; Approved with no candidates "Upload resumes"; resumes processing "Processing N resumes" (status text, not a button); otherwise "Review candidates". It is a primary button only when it leads to another step and the screen has no primary of its own; on its own step it is plain text, because the screen's own primary does the work. Out-of-date scores are a warning banner with "Re-score", never the next-up.
- A progress strip of four steps (Criteria, Candidates, Interview kit, Compare), each with its real state and counts (for example "14 scored, 3 need a look, 2 processing", "Ready", "Needs approval"). The current step has `aria-current="step"`; a locked step is plain text with a one-phrase reason ("Approve criteria first"). A count that is not loaded is left out.

Criteria screen: the job description sits beside the editor in a collapsible region. Must-have and Nice-to-have are separate groups; each criterion shows its weight and its share of the total. A sticky footer holds "Save draft" and the single primary "Approve criteria" (with the confirmation before it takes effect); the Propose button is primary only while there are no criteria.

### 8.3 Candidates: upload and ranked list

- Top: while there are no candidates, a full upload block with a primary button. Once there are some, the zone collapses: the role header carries an "Upload resumes" outline button (`aria-expanded`) that opens the one-row zone, and the zone keeps its upload results while closed. At 1440x900 the list and the open candidate start about 300px from the top of the page.
- Below: review mode (from 1024px wide). Left, a compact ranked list in a rail that scrolls inside the viewport: select box, rank, candidate ID in mono, weighted total, must-have coverage ("3 of 3 must-haves"), hiring stage and, only where true, the markers Needs a look, Changed by recruiter and Out of date (icon and words). No per-criterion chips, no colour by score, every candidate stays listed. Right, the open candidate (8.4), with Previous and Next buttons and "3 of 14 on this page".
- The open candidate is the `c` search param of `/roles/$roleId/candidates` (reload and back work); with none it is the top-ranked one. `/candidates/$candidateId` still renders the same detail as its own page, for deep links and interviewers.
- Below 1024px the list is the whole screen and a row opens the candidate page.
- Keyboard: `j` and `k` (and the arrow keys while a row has focus) move the open candidate; keys are ignored in fields, selects and dialogs, and focus is never trapped. A visible hint says "j and k move between candidates". The open row carries `aria-current`, and a polite status says "Showing C-014, 3 of 14". The shortcuts move through the loaded page (up to 100); at its end the pane says so and points to Next page.
- Toolbar above the list is one row (its heading is for assistive tech only): the slim out-of-date bar with Re-score, the hiring stage filter, Needs a look only and Changed by recruiter. Under it one small line says scores are AI suggestions and hiding names reduces some bias but does not remove it, and that the stage covers every candidate while the checkboxes cover the loaded page.
- Compare tray: while one or more rows are ticked, a bar fixed to the bottom of the viewport (a labelled region, with bottom padding so it never covers content) says "N selected", gives a hint at the wrong count, enables Compare at 2 to 4 and offers Clear. Compare is its one primary action; the selection count is announced by a polite status.
- A must-have coverage indicator shows how many must-haves have verified evidence, so a high total cannot hide a gap.

### 8.4 Candidate detail (review pane or page)

- Header: candidate ID, weighted total and must-haves covered, hiring stage control (a select; Reject asks first, 7.7), show candidate name, Previous and Next in review mode.
- Scores section: "Scores are AI suggestions" once, then criterion rows (7.4) with evidence blocks and "Change score" controls.
- Anonymized resume text beside the scores (wide screens), with the matched quote highlighted when a criterion is selected.
- Interviewer feedback, assigned interviewers (the picker is hidden when everyone is assigned) and history in readable wording at the bottom.
- Interviewers never get this screen: they see the focused feedback screen in 8.6 (no identity reveal, stage control, cost or other interviewers' feedback).

### 8.5 Interview kit

- Grouped by criterion. Each question card shows the question, a **Strong answer** panel and a **Weak answer** panel.
- Both panels are neutral: Strong has a check icon on a quiet filled panel, Weak a minus icon on a dashed outline. No red or green blocks.
- Recruiters can edit, reorder, delete and regenerate a single question.
- Interviewers get a read-only view with a "Back to My candidates" link; "Print interview kit" stays available as a quiet ghost button, not a primary action.

### 8.6 Interviewer flow

Interviewers land on `/me/candidates` (recruiter-only routes redirect there, never a 403) and see only anonymized ids.

- **My candidates** is a queue: "N of M submitted" with a progress bar (text and bar, never colour alone, announced politely), the next unsubmitted candidate as the one primary action ("Start feedback" with nothing submitted, "Continue with C-005" after), and the list below with a Submitted or Not started tag (icon and text). With everything submitted the primary is replaced by an "All feedback submitted" tag.
- **Feedback screen** (lg and up, two columns). Left: a progress strip pinned under the header ("3 of 6 criteria scored" with a bar), then one block per criterion: the questions to ask for reference, a segmented 0 to 4 score (native radios in a labelled radio group, 40px targets, the chosen level also marked with a check beside its rubric descriptor) and a comment. Submit is disabled until every criterion has a score and a comment, and says why. Right: the interview kit with the Strong and Weak answer panels (8.5) in a sticky region that scrolls on its own. Below lg the columns stack and the strip pins at the top.
- **After submit**: a success notice "Feedback submitted. Thank you." with one primary, "Next candidate", or "Back to My candidates" when none are left; the form becomes read-only and the AI scores appear. The notice shows only for a submit made in this visit. A revisit shows the read-only form labelled "Submitted", with no notice.
- Unsaved input asks before the interviewer leaves the page.

### 8.7 Comparison view

- A grid in one scroll region (focusable, labelled, scrolls both ways inside the viewport). The header row and the criterion column are sticky, so no score loses its heading on a small screen.
- Columns are candidates (2 to 4), each header a link to that candidate. Rows are criteria in two groups, Must-have then Nice-to-have, each with a group row.
- Each cell shows the resume score chip, "Changed by recruiter" (pencil icon and words) when the score was changed, the interviewer scores and their comments.
- Disagreement between interviewers on a criterion is an icon-and-text tag in the cell ("Interviewers disagree"), not a tooltip.
- Not built, because the comparison endpoint does not return them: a pinned weighted-totals row, stage controls in the headers and expandable evidence quotes (N-W17).

### 8.0 Dashboard

"/" for both roles. It uses only existing calls (role list, queue and first ranked page per approved role, cost log, my candidates); nothing is invented.

- Recruiter: six stat tiles (roles by status, candidates scored, need a look, changed by recruiter, out of date, processing now), a Roles at a glance list (progress bar, counts, the same next-up button as the role list), the budget as a bar, then for one role (a select when several have candidates) a stage bar list and a histogram of weighted totals.
- Counts and charts come from the first page of up to 100 candidates per role. The page says so whenever a role has more, and each chart note states its scope.
- Charts are CSS bars with printed counts and a visually hidden table for the histogram. One primary hue; no bar is colored by score or by stage quality (rule 9). Bars and tiles grow once on load (one orchestrated moment, 250 to 300ms) and not at all under reduced motion.
- Interviewer: assigned, submitted and remaining tiles, a progress bar, one primary button for the next candidate, and the assigned list. Anonymized ids only.
- States: skeletons while loading, an error with Try again, an empty state per case.

### 8.8 Cost log

A table of calls: time, purpose, model, input tokens, output tokens, cost, running total, and a `Replayed` tag for recorded responses. Only visible to recruiters.

---

## 9. Bias-aware interface rules

These rules exist because the product's purpose is fairness.

- **Anonymous by default.** Lists and comparison headers show candidate IDs (for example `C-014`) instead of names. A recruiter can use an explicit "Show candidate name" action on the detail view, which is logged. This is a recommendation and is listed as an open question in the PRD.
- **No photos** anywhere in the UI.
- **No score-based coloring** of candidate rows or names.
- **Low-ranked candidates stay visible.** The list never hides or collapses candidates below a cutoff.
- **Model output is labelled.** Use the label "AI suggestion" beside AI scores, and "Changed by recruiter" beside changed scores.
- **Ranking rationale is inspectable.** Every total links to the per-criterion scores and evidence that produced it.

---

## 10. Content and tone

- Plain, direct and calm. No exclamation marks, no hype.
- Explain limits honestly: "This quote could not be found in the resume, so it was marked as no evidence found."
- Buttons use verbs: "Approve criteria", "Upload resumes", "Submit feedback", "Move to interview".
- Errors say what happened and what to do next.
- Avoid words that imply automated judgment, such as "rejected by AI", "best candidate" or "top talent". Use "highest ranked" and "AI suggestion".

### 10.1 Example copy

| Situation | Copy |
|---|---|
| Role is draft | "Approve the criteria to start uploading and scoring resumes." |
| Needs a look | "The AI's quote was not found in the resume. It was replaced with no evidence found." |
| Reject confirm | "Reject this candidate? This is recorded under your name and can be reversed by a recruiter." |
| Budget reached | "The AI budget of $8.00 has been reached. No new AI calls can be made." |
| Empty state | "No resumes yet. Upload PDF or DOCX files to see a ranked list." |

### 10.2 Glossary

One word per idea, used in labels, headings, buttons, notices, aria labels, history text and tests. Each screen gets one short helper line, not tooltips or stacked disclaimers.

| Use | Not |
|---|---|
| Hiring stage (values capitalised: New, Screened, Interview, Offer, Hired, Rejected, Withdrawn) | Stage, lowercase values |
| Show candidate name (logged in the history) | Reveal identity |
| Scores are out of date, Re-score | Stale, Re-run scoring |
| Change score (a note is required), Changed by recruiter | Override, Recruiter override |
| Needs a look | Flagged |
| AI suggestion, AI | Model suggestion, model |
| Interview kit | Kit |
| Readable processing steps (Waiting to start, Reading the resume, Removing identity details, Scoring, Ready, Could not process) and numbered interviewers | Raw status values, id slices |

Product-rule copy is never softened by this glossary: a score points to a checked quote or says "No evidence found", a verified quote proves the text exists and not that it supports the score, anonymization is a floor and not proof of fairness, and nothing is rejected or hidden except by a recruiter action.

---

## 11. States

Every screen and component needs these states designed:

- **Loading:** skeletons for tables, an inline progress bar for model calls.
- **Empty:** short explanation and a single next action.
- **Error:** plain message, cause if known, retry action.
- **Partial:** batch uploads where some files failed.
- **Out of date:** criteria changed after scoring. Banner "Scores are out of date" plus a "Re-score" action.
- **Blocked:** role in draft, or budget reached. Explain why and what unlocks it.
- **Read-only:** submitted feedback, and any view for an interviewer where editing is not allowed.

---

## 12. Accessibility

- WCAG 2.2 AA minimum for all text and interactive elements.
- Full keyboard navigation. Visible focus ring in `--ring` (3px at 50 percent plus a solid `--ring` border), in both themes.
- Tables use proper headers and announce sort state.
- Color is never the only signal. Every state pairs color with an icon and text.
- Score selectors are radio groups with labels, not color-only buttons.
- Dialogs trap focus, close with Escape, and return focus to the trigger.
- Respect `prefers-reduced-motion` and `prefers-color-scheme`.
- Minimum touch target 40px.

---

## 13. Motion

Motion is quiet: things settle, they do not bounce.

- 120 to 200ms ease-out for hover, dialog open and close, and menu transitions (`tw-animate-css` fade and zoom on Radix dialogs and popovers).
- A button press shifts 1px. No springs, no parallax, no decorative or looping animation.
- Spinners and the progress bar are the only continuous motion.
- Motion (`motion/react`, wrapped in `MotionConfig reducedMotion="user"`): a 200ms fade and 6px rise for page content on a route change, a sliding active mark in the sidebar, a one-time stagger and grow on the dashboard, list items entering, and the compare tray sliding in. 150 to 300ms, ease-out, no springs. Tests set `MotionGlobalConfig.skipAnimations`.
- Scrollbars are thin with a rounded thumb (3:1 against its surface), a transparent track and a stronger thumb on hover, in both themes.
- `prefers-reduced-motion`: transitions are removed and spinners stop spinning (their label stays); progress remains.

---

## 14. Assets checklist

- [ ] Logo mark and wordmark, SVG, light and dark
- [ ] App icon: mark on a `--primary` tile, check in `--primary-foreground`
- [ ] Favicon (16, 32, 48) using the mark alone
- [ ] Open Graph image (1200 × 630)
- [ ] Icon set export (outline, 20px)
- [ ] Empty-state illustrations (optional, flat, theme tokens only)
- [ ] Token file (CSS variables) generated from sections 3 to 5

### 14.1 Tokens

The source of truth is `web/src/index.css` (sections 3 to 5 above); there is no second copy here. The legacy hand-written sheets are gone.

---

## 15. Open design questions

1. ~~Final palette~~ Closed (HK-86): the cool-grey working surface with one indigo primary, section 3. It supersedes "reading room" (HK-80) and the emerald palette.
2. Should candidate identity be hidden by default in the recruiter's views (recommended)?
3. Should the interviewer see model scores before submitting feedback?
4. Is a dark theme required for launch, or a later addition?
