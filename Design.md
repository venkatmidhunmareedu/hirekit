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

**HireKit** is set as one word with a capital H and a capital K. In two-tone use, "Hire" takes the text color and "Kit" takes the accent.

### 2.2 Logo

The mark is a **briefcase with a check**: a rounded body, a handle, and a check mark. The briefcase says "hiring", the "kit" idea is in the toolbox form, and the check stands for verified evidence.

- **Wordmark:** medium weight (500), 24px at standard size.
- **Clear space:** at least the height of the briefcase handle on every side.
- **Minimum size:** mark alone 16px, mark with wordmark 96px wide.
- **Do not:** stretch, rotate, add gradients or shadows, or change the check color to something without enough contrast.

#### Mark source (SVG, 270 × 70 area, mark drawn in a 84 × 70 box)

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

The colors below are the **primary palette (emerald and near-black)**. Two alternates were explored and are recorded in section 3.4 in case the team switches. Only one palette should ship.

---

## 3. Color

### 3.1 Brand and neutral tokens (primary palette)

| Token | Hex | Use |
|---|---|---|
| `--brand` | `#3ECF8E` | Logo, primary buttons, key highlights |
| `--brand-deep` | `#24B47E` | "Kit" in the wordmark on light backgrounds, hover on primary |
| `--brand-tint` | `#E8F8F1` | Selected rows, subtle highlights (light mode) |
| `--ink` | `#1C1C1C` | Text on light, dark surfaces, text on brand |
| `--gray-700` | `#5C5C5C` | Secondary text on light |
| `--gray-500` | `#898989` | Muted text, placeholders, secondary text on dark |
| `--gray-300` | `#B4B4B4` | Borders |
| `--mist` | `#EDEDED` | Subtle fills, dividers |
| `--paper` | `#FAFAFA` | Page background (light) |
| `--white` | `#FFFFFF` | Cards and inputs (light) |

### 3.2 Semantic tokens

Semantic colors carry meaning about **state**, never about a candidate's worth. Do not color candidates red or green by score.

| Token | Hex | Use |
|---|---|---|
| `--info` | `#3B82C4` | Informational notices, links |
| `--success` | `#24B47E` | Verified quote, approved, saved |
| `--warning` | `#E0A030` | Flagged quote, stale scores, budget approaching limit |
| `--danger` | `#D64545` | Errors, budget blocked, destructive confirmation |

Pair every semantic color with an icon and a text label. Color alone is never the signal.

### 3.3 Theme mapping

| Role | Light | Dark |
|---|---|---|
| Page background | `--paper` | `#141414` |
| Card background | `--white` | `--ink` (`#1C1C1C`) |
| Primary text | `--ink` | `#EDEDED` |
| Secondary text | `--gray-700` | `--gray-500` |
| Border | `--gray-300` | `#2E2E2E` |
| Primary button fill | `--brand` | `--brand` |
| Primary button text | `--ink` | `--ink` |
| Focus ring | `--brand-deep` | `--brand` |

Text on `--brand` is always `--ink`. White on `#3ECF8E` fails contrast.

### 3.4 Alternate palettes (not active)

| Name | Primary | Accent | Neutral dark | Neutral light |
|---|---|---|---|---|
| Clay (Claude-style) | `#D97757` | `#6A9BCC` | `#141413` | `#FAF9F5` |
| Blue and amber | `#185FA5` | `#EF9F27` | `#1C1C1C` | `#FFFFFF` |

If a switch is made, replace only the brand tokens. Semantic tokens stay the same. Check contrast again for text on the new brand color.

---

## 4. Typography

| Use | Font | Weight | Size / line height |
|---|---|---|---|
| Display / page title | Inter | 500 | 24 / 32 |
| Section heading | Inter | 500 | 18 / 26 |
| Subheading | Inter | 500 | 16 / 24 |
| Body | Inter | 400 | 14 / 22 |
| Small / caption | Inter | 400 | 12 / 18 |
| Evidence quote | Inter (italic) | 400 | 14 / 22 |
| Code, IDs, hashes, cost figures | JetBrains Mono | 400 | 13 / 20 |

- Two weights only: 400 and 500.
- Sentence case everywhere. No all caps, no title case in UI copy.
- Fallback stack: `Inter, system-ui, -apple-system, "Segoe UI", sans-serif`.
- Evidence quotes are always shown in quotation marks with italic style so they read as source text, not model commentary.

---

## 5. Layout and spacing

- **Spacing scale (px):** 4, 8, 12, 16, 24, 32, 48.
- **Radii:** 8px for controls, 12px for cards, 16px for the app tile and modals.
- **Borders:** 1px `--border`. Cards use a border, not a shadow.
- **Shadows:** none, except a single subtle overlay shadow on menus and modals.
- **Grid:** 12 columns, max content width 1200px, 24px gutters. Tables can use the full width.
- **App shell:** left sidebar (roles and navigation, 240px), top bar (role name, stage filter, user), content area.
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
| Primary | `--brand` fill, `--ink` text | One per view: Approve criteria, Upload, Submit feedback |
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

- Sticky header, 44px rows, zebra off, hover row tint `--brand-tint`.
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

- WCAG 2.1 AA minimum for all text and interactive elements.
- Full keyboard navigation. Visible 2px focus ring in `--brand-deep` (light) or `--brand` (dark) with 2px offset.
- Tables use proper headers and announce sort state.
- Color is never the only signal. Every state pairs color with an icon and text.
- Score selectors are radio groups with labels, not color-only buttons.
- Dialogs trap focus, close with Escape, and return focus to the trigger.
- Respect `prefers-reduced-motion` and `prefers-color-scheme`.
- Minimum touch target 40px.

---

## 13. Motion

- Short and quiet: 120 to 200ms ease-out for hover, expand and toast transitions.
- No decorative animation. Progress indicators are the only continuous motion.
- Reduced motion mode removes all transitions except progress.

---

## 14. Assets checklist

- [ ] Logo mark and wordmark, SVG, light and dark
- [ ] App icon: mark on `--ink` tile, and mark on `--brand` tile
- [ ] Favicon (16, 32, 48) using the mark alone
- [ ] Open Graph image (1200 × 630)
- [ ] Icon set export (outline, 20px)
- [ ] Empty-state illustrations (optional, flat, brand colors only)
- [ ] Token file (CSS variables) generated from sections 3 to 5

### 14.1 Starter CSS tokens

```css
:root {
  --brand: #3ECF8E;
  --brand-deep: #24B47E;
  --brand-tint: #E8F8F1;
  --ink: #1C1C1C;
  --gray-700: #5C5C5C;
  --gray-500: #898989;
  --gray-300: #B4B4B4;
  --mist: #EDEDED;
  --paper: #FAFAFA;
  --white: #FFFFFF;

  --info: #3B82C4;
  --success: #24B47E;
  --warning: #E0A030;
  --danger: #D64545;

  --radius-control: 8px;
  --radius-card: 12px;
  --radius-modal: 16px;

  --font-sans: Inter, system-ui, -apple-system, "Segoe UI", sans-serif;
  --font-mono: "JetBrains Mono", ui-monospace, monospace;
}

@media (prefers-color-scheme: dark) {
  :root {
    --page: #141414;
    --card: #1C1C1C;
    --text: #EDEDED;
    --text-muted: #898989;
    --border: #2E2E2E;
  }
}
```

---

## 15. Open design questions

1. Final palette: the emerald and near-black primary, or one of the alternates in 3.4?
2. Should candidate identity be hidden by default in the recruiter's views (recommended)?
3. Should the interviewer see model scores before submitting feedback?
4. Is a dark theme required for launch, or a later addition?
