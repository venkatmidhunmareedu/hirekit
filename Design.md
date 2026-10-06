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

**HireKit** is set as one word with a capital H and a capital K. In two-tone use, "Hire" takes the text color and "Kit" takes the accent, set in italic display serif (section 4).

### 2.2 Logo

The mark is a **briefcase with a check**: a rounded body, a handle, and a check mark. The briefcase says "hiring", the "kit" idea is in the toolbox form, and the check stands for verified evidence.

- **Wordmark:** Newsreader medium (500), 24px at standard size, "Kit" in italic.
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

The emerald and near-black palette is **superseded** (HK-80). One palette ships: "reading room", section 3. The two alternates formerly listed in 3.4 were dropped with it.

---

## 3. Color

**Direction: reading room.** HireKit is read for long sessions and its job is to put evidence in front of a person. The look borrows from a well-kept paper file: warm bone paper, ink-navy for action, serif headings, and one highlighter yellow that appears only on evidence (quotes and matched text). Everything else stays quiet so the yellow means "this is the proof". It is deliberately not stock neutral, not green-on-white and not a gradient SaaS dashboard.

All colors are OKLCH. Tokens live in `web/src/index.css` as shadcn role tokens (`--background`, `--primary`, ...) mapped through Tailwind's `@theme inline`. Dark follows `prefers-color-scheme`; no toggle at launch.

### 3.1 Role tokens

| Token | Light | Dark | Use |
|---|---|---|---|
| `--background` | `oklch(0.972 0.009 85)` | `oklch(0.185 0.018 262)` | Page (bone paper / ink night) |
| `--card`, `--popover` | `oklch(0.991 0.005 85)` | `oklch(0.225 0.02 262)` | Cards, dialogs, header |
| `--foreground` | `oklch(0.22 0.025 262)` | `oklch(0.935 0.01 85)` | Body text |
| `--muted-foreground` | `oklch(0.45 0.025 262)` | `oklch(0.75 0.02 262)` | Secondary text (at least 4.5:1 on page and card) |
| `--primary` | `oklch(0.37 0.085 262)` | `oklch(0.82 0.085 262)` | The one action color: primary button, links in chrome, wordmark |
| `--primary-foreground` | `oklch(0.98 0.006 85)` | `oklch(0.2 0.03 262)` | Text on primary |
| `--secondary`, `--muted` | `oklch(0.93 0.014 85)`, `oklch(0.945 0.011 85)` | `oklch(0.285 0.022 262)`, `oklch(0.26 0.02 262)` | Quiet fills |
| `--accent` | `oklch(0.915 0.025 262)` | `oklch(0.32 0.04 262)` | Current nav item, hover fills |
| `--border` | `oklch(0.87 0.014 85)` | `oklch(0.32 0.02 262)` | Dividers and card edges |
| `--input` | `oklch(0.58 0.025 262)` | `oklch(0.62 0.03 262)` | Control borders (3:1 against the page, WCAG 1.4.11) |
| `--ring` | `oklch(0.5 0.14 262)` | `oklch(0.78 0.1 262)` | Focus ring |
| `--destructive` | `oklch(0.47 0.16 27)` | `oklch(0.75 0.13 27)` | Destructive actions |

### 3.2 Evidence and state tokens

The highlighter is reserved for evidence. Do not use it for decoration, selection chrome or warnings.

| Token | Light | Dark | Use |
|---|---|---|---|
| `--mark` / `--mark-foreground` | `oklch(0.93 0.12 95)` / `oklch(0.25 0.04 80)` | `oklch(0.4 0.08 90)` / `oklch(0.96 0.03 90)` | Evidence quote background and matched text |
| `--ok` / `--ok-soft` | `oklch(0.42 0.1 160)` / `oklch(0.94 0.04 160)` | `oklch(0.8 0.1 160)` / `oklch(0.3 0.045 160)` | Verified quote, approved, saved |
| `--warn` / `--warn-soft` | `oklch(0.45 0.1 70)` / `oklch(0.95 0.06 85)` | `oklch(0.82 0.11 80)` / `oklch(0.32 0.05 80)` | Flagged quote, stale scores, budget near the limit |
| `--bad` / `--bad-soft` | `oklch(0.47 0.16 27)` / `oklch(0.945 0.03 27)` | `oklch(0.78 0.12 27)` / `oklch(0.31 0.05 27)` | Errors, budget reached, destructive confirmation |
| `--note` / `--note-soft` | `oklch(0.42 0.1 235)` / `oklch(0.945 0.025 235)` | `oklch(0.8 0.08 235)` / `oklch(0.3 0.04 235)` | Informational notices |

State tones describe the state of the work, never a candidate's worth. Do not color candidates red or green by score. Every tone pairs with an icon and a text label; color alone is never the signal. Text on a `-soft` fill uses the matching strong token and keeps 4.5:1.

### 3.3 Rules of use

- Primary is the only saturated chrome color. One primary button per view.
- The yellow `--mark` appears only behind evidence quotes and matched text.
- Surfaces are separated by borders and tone steps, not shadows. Cards are for independent objects (a role, a candidate); sections use headings and separators.
- Contrast is checked in both themes for text, control borders and the focus ring (WCAG 2.2 AA).

---

## 4. Typography

Two families plus mono, loaded from Google Fonts in `web/index.html` with `display=swap`. If the font host is unreachable the system fallbacks below apply and the layout holds.

| Role | Family | Fallback |
|---|---|---|
| Display: page titles, section headings, role names, evidence quotes | Newsreader (opsz 6 to 72) | `Iowan Old Style`, `Palatino Linotype`, Georgia, serif |
| Text: UI, tables, forms, body | Instrument Sans | `ui-sans-serif`, `system-ui`, `Segoe UI`, sans-serif |
| Code, IDs, hashes, cost figures | JetBrains Mono | `ui-monospace`, `SF Mono`, Menlo, monospace |

| Use | Family | Weight | Size / line height |
|---|---|---|---|
| Page title | Display | 500 | 30 / 36 |
| Section heading | Display | 500 | 20 / 28 |
| Subheading | Text | 600 | 16 / 24 |
| Body | Text | 400 | 14 to 16 / 22 to 24 |
| Small / caption | Text | 400 | 12 / 18 |
| Evidence quote | Display (italic) | 400 | 16 / 26, on `--mark` |
| Code, IDs, cost figures | Mono | 400 | 12 to 13 / 20 |

- Sentence case everywhere. No all caps, no title case in UI copy.
- Evidence quotes are always shown in quotation marks, in italic serif on the highlighter, so they read as source text, not model commentary.
- Line length for prose: at most 65 characters (`max-w-prose`).

---

## 5. Layout and spacing

- **Spacing scale (px):** 4, 8, 12, 16, 24, 32, 48.
- **Radii:** one `--radius` of 6px; controls and badges use it, cards and dialogs step up to 8 and 10px. Small and squared on purpose: paper-file, not pill.
- **Density:** controls 40px high (touch target), table rows 44px, comfortable reading density over compact.
- **Borders:** 1px `--border`. Cards use a hairline ring, not a shadow.
- **Shadows:** none, except a single subtle overlay shadow on menus and modals.
- **Grid:** 12 columns, max content width 1200px, 24px gutters. Tables can use the full width.
- **App shell:** one header (wordmark, main navigation, budget pill, user, sign out) over a content column of at most 1152px (`max-w-6xl`). No sidebar; the header wraps to two rows on a phone.
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

### 7.3 Evidence block

The signature component of the product.

- Quote in italic with quotation marks, on a `--mist` tinted background with a left border in `--gray-300`.
- Status tag on the right:
  - **Verified** (check icon, `--success`): quote found in the resume text.
  - **No evidence found** (dash icon, `--gray-500`): shown in plain text, no quote box.
  - **Needs a look** (triangle icon, `--warning`): the AI's quote failed the check and was downgraded. Shows a "why" line.
- Long quotes are truncated after 3 lines with a "Show more" control.

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

A small persistent pill in the top bar for recruiters: `$3.42 of $8.00`.

- Default: neutral.
- 75% and above: `--warning` with icon.
- 100%: `--danger`, and model actions show a disabled state with the reason "Budget reached".
- Click opens the call log (time, purpose, tokens, cost).

### 7.11 Toasts and banners

- Toasts for confirmations (saved, uploaded). Auto-dismiss after 5 seconds and pause on hover.
- Banners for persistent states: role is `Draft`, scores are out of date, budget blocked.

---

## 8. Key screens

### 8.1 Role list

Cards or rows per role with title, status (`Draft` or `Approved`), candidate count and last activity. Primary action: "New role".

### 8.2 Role setup and criteria approval

1. Job description text area with a "Propose criteria" button.
2. Loading state while the model responds, with a cancel option.
3. Rubric editor showing must-have and nice-to-have groups.
4. "Approve criteria" as the single primary action. Until approved, the tabs for Candidates and Interview kit are visible but locked with an explanation.

### 8.3 Candidates: upload and ranked list

- Top: upload zone (collapsible once files are processed).
- Below: ranked table with columns: rank, candidate ID (see 9), weighted score, must-have coverage, one chip per criterion, "Needs a look" count, hiring stage.
- Row click opens the candidate detail panel.
- Filter bar: hiring stage, needs a look only, changed by recruiter. One helper line states what each filter covers.
- A must-have coverage indicator shows how many must-haves have verified evidence, so a high total cannot hide a gap.

### 8.4 Candidate detail (side panel or page)

- Header: candidate ID, hiring stage control, total score.
- Criterion rows (7.4) with evidence blocks and "Change score" controls.
- Anonymized resume text on the right, with matched quotes highlighted when a criterion is selected.
- Hiring stage and score change history at the bottom.

### 8.5 Interview kit

- Grouped by criterion. Each question card shows the question, a **Strong answer** panel and a **Weak answer** panel.
- Strong uses a check icon with a neutral treatment. Weak uses a minus icon. Avoid strong red/green blocks.
- Recruiters can edit, reorder, delete and regenerate a single question.
- Interviewers get a read-only, printable view.

### 8.6 Interviewer feedback form

- One section per criterion: the question list for reference, a score selector (segmented buttons matching the rubric scale), and a comment field.
- Progress indicator: "3 of 6 criteria scored".
- Submit is disabled until every criterion has a score. After submission the form is read-only.

### 8.7 Comparison view

- Columns are candidates (2 to 4). Rows are criteria, grouped by must-have and nice-to-have.
- Each cell shows resume score chip, override if any, interviewer scores and a spread indicator.
- Disagreement between interviewers on a criterion is marked with a warning tag in the cell, not a tooltip.
- A pinned top row shows weighted totals. The candidate column headers hold stage controls.
- Cells expand to show evidence quotes and comments.

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

Motion is paper-quiet: things settle, they do not bounce.

- 120 to 200ms ease-out for hover, dialog open and close, and menu transitions (`tw-animate-css` fade and zoom on Radix dialogs and popovers).
- A button press shifts 1px. No springs, no parallax, no decorative or looping animation.
- Spinners and the progress bar are the only continuous motion.
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

The source of truth is `web/src/index.css` (sections 3 to 5 above); there is no second copy here. The legacy hand-written sheets in `web/src/styles/` still exist until HK-80 stage 4 and are being removed screen by screen.

---

## 15. Open design questions

1. ~~Final palette~~ Closed (HK-80): "reading room", section 3. The emerald palette is superseded.
2. Should candidate identity be hidden by default in the recruiter's views (recommended)?
3. Should the interviewer see model scores before submitting feedback?
4. Is a dark theme required for launch, or a later addition?
