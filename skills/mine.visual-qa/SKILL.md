---
name: mine.visual-qa
description: "Use when the user says: \"visual QA\", \"screenshot review\", \"review the UI visually\", \"take screenshots and find issues\", or \"UX review\". Screenshots a live app via Playwright, then analysis agents review the captures — first impressions, cross-page consistency, and unstructured design narrative."
user-invocable: true
---

# Visual QA

Screenshot-based review of a live UI. A screenshotter navigates the app via Playwright and captures every page, then analysis agents review the screenshots under genuinely different viewing conditions — one processes each screenshot sequentially without cross-referencing (first impressions), one sees all screenshots simultaneously (cross-page consistency), and one narrates a freeform reaction to the whole app (design storytelling).

## How This Differs From Other Skills

| Skill | What it does |
|-------|-------------|
| `mine.ux-antipatterns` | Static code scan for UX anti-patterns — no live app, no screenshots |
| `ui-auditor` agent | Code-level a11y and consistency grep — no visual verification |
| `visual-diff` agent | Before/after regression screenshots — compares two states |
| **`mine.visual-qa`** | **Live app screenshots + analysis agents with separated viewing conditions** |

## Arguments

$ARGUMENTS — optional:
- URL: `/mine.visual-qa http://localhost:3000`
- URL + pages: `/mine.visual-qa http://localhost:3000 /dashboard /settings /users`
- Empty: attempt to detect a running dev server, then ask

### Viewport & Theme Modifiers

By default, the skill captures **desktop viewport in light mode only**. This keeps screenshot count low and agent attention focused. To review other configurations, re-run the skill with a modifier:

- `/mine.visual-qa http://localhost:3000 --mobile` — mobile viewport (375px) only
- `/mine.visual-qa http://localhost:3000 --dark` — dark mode only
- `/mine.visual-qa http://localhost:3000 --mobile --dark` — mobile dark

Each run is independent. This is intentional — fewer screenshots per run means deeper analysis per screenshot.

When parsing $ARGUMENTS, extract `--mobile` and `--dark` flags separately from URL and page paths.

## Phase 1: Detect Target & Pages

### If URL and pages provided in $ARGUMENTS

Use them directly.

### If only URL provided

Navigate to the URL with Playwright, take a snapshot, identify main pages/views from navigation links. Auto-include all discovered pages. Only ask the user if more than 10 pages are found — in that case, present the list and ask which to include.

### If nothing provided

1. Check for a running dev server:
   ```bash
   # Linux
   ss -tlnp 2>/dev/null | grep -E ':(3000|3001|4200|5000|5173|8000|8080|8888) ' | head -5
   # macOS fallback (if ss is unavailable)
   lsof -nP -iTCP -sTCP:LISTEN 2>/dev/null | grep -E ':(3000|3001|4200|5000|5173|8000|8080|8888) ' | head -5
   ```
2. If found, confirm the URL with the user
3. If not found, ask the user for the URL
4. Then discover pages as above

## Phase 2: Screenshotter (Playwright Capture)

Create a unique temp directory:

1. Run: `get-skill-tmpdir mine-visual-qa`
2. Note the directory path (e.g., `/tmp/claude-mine-visual-qa-a8Kx3Q`)

Launch a single `general-purpose` agent. Its job is capturing screenshots — page views first, then interactive element states. Nothing else.

**Agent type**: `general-purpose`
**Output file**: `<dir>/walkthrough.md`
**Screenshot directory**: `<dir>/screenshots/`
**Run in background**: `true`

Substitute `<VIEWPORT_INSTRUCTION>` and `<NAMING_EXAMPLES>` based on the flags:

**Default (desktop light):**
- VIEWPORT_INSTRUCTION: `Use the default desktop viewport. Do not resize to mobile or toggle dark mode.`
- NAMING_EXAMPLES:
  ```
  01-dashboard.png
  02-items-list.png
  03-settings.png
  ```

**--mobile:**
- VIEWPORT_INSTRUCTION: `Resize the browser to 375px width before capturing any screenshots. Stay in mobile viewport for the entire session.`
- NAMING_EXAMPLES:
  ```
  01-dashboard-mobile.png
  02-items-list-mobile.png
  03-settings-mobile.png
  ```

**--dark:**
- VIEWPORT_INSTRUCTION: `If the app has a visible dark mode toggle, activate it before capturing. If not, use Playwright's emulateMedia to set colorScheme to 'dark'. Stay in dark mode for the entire session.`
- NAMING_EXAMPLES:
  ```
  01-dashboard-dark.png
  02-items-list-dark.png
  03-settings-dark.png
  ```

**--mobile --dark:** Combine both instructions.

```
You are opening <APP_NAME> at <APP_URL> for the first time.

Your job is capturing screenshots of every page for other reviewers to analyze. Narrate briefly as you go.

DO NOT look at source code. Just use the app as a human would.

## Viewport & Theme

<VIEWPORT_INSTRUCTION>

## Screenshot Capture

Visit every page listed below and capture screenshots. Save to <dir>/screenshots/ using Playwright MCP tools.

### Naming Convention

Name files with a zero-padded sequence number and page name:

<NAMING_EXAMPLES>

For interactive element states, add an `interact-` prefix:

```
20-interact-dropdown-category-open.png
21-interact-modal-delete-confirm.png
22-interact-datepicker-expanded.png
```

### What to Capture

**Step 1 — Page screenshots (do this first for every page):**
- One screenshot per page in the configured viewport/theme
- If a page scrolls, scroll down one viewport height at a time and capture each fold. Name them with a `-fold2`, `-fold3` suffix. Wait briefly for lazy-loaded content before scrolling further.

**Finish capturing ALL pages before interacting with elements.** Page coverage is your most important deliverable.

**Step 2 — Interactive element states (after all pages are captured):**

Go back through the pages and trigger interactive elements to reveal visual states invisible in a static screenshot. **Budget: up to 15 interactive screenshots total**, prioritizing the most visually significant elements.

Priority order:
1. Modals / dialogs
2. Dropdowns / selects — open to show expanded state
3. Form validation — submit empty or enter invalid data to show error states
4. Tooltips — hover to reveal
5. Accordions / collapsibles — expand
6. Date pickers / color pickers — open
7. Radio buttons / checkboxes / toggles — show selected state
8. Loading / empty states — clear a filter to show "no results"

After exhausting this list, use `browser_snapshot` to inspect the accessibility tree of each page. Any element with `role=button`, `role=tab`, `role=menu`, `role=dialog`, or `aria-haspopup` that you haven't already triggered — trigger it and screenshot the result (still within the 15-screenshot budget).

Narrate briefly what you triggered and what appeared.

## Pages to Visit
<PAGES>

## Output

Write a brief walkthrough log to: <dir>/walkthrough.md

Include:
1. What you observed on each page — especially interactive elements that revealed unexpected visual states
2. Any elements you couldn't trigger or pages you couldn't reach
3. Any places where you got confused or something looked broken
4. Any links within the app that led to errors or 404 pages
```

## Phase 3: Launch Analysis Agents

After the Screenshotter completes, read its output file and confirm screenshots were captured. Glob for `<dir>/screenshots/*.png` to get the actual file list.

Launch the following `general-purpose` agents with `run_in_background: true`. Each sees the same screenshots through a different lens.

### Agent 1: Isolated Page Reviewer

**Output file**: `<dir>/page-reactions.md`
**Lens**: Sequential, isolated — reacts to each screenshot before seeing the next. No cross-referencing.

```
You are reviewing screenshots of <APP_NAME>, captured from a live app. Each screenshot shows one page or one interactive state.

Your job: read each screenshot ONE AT A TIME. After reading each one, immediately write your reaction BEFORE looking at the next screenshot. Do not go back and revise earlier reactions. Do not compare to other screenshots — react only to what's in front of you right now.

For each screenshot, write:

### [filename]
- **Gut reaction**: Does this look polished or rough?
- **Eye draw**: What draws your eye first — is that the right thing?
- **Clarity**: Is the purpose of this page immediately obvious?
- **What's wrong**: Anything misaligned, cramped, sparse, confusing, or ugly? Be specific about location.

Be brutally honest. "This looks like a prototype" or "I have no idea what this page is for" — that kind of candor. Be specific — "the spacing between the header and the first card is 2x the spacing between cards" is better than "spacing issues."

Screenshots to review (in this order):
<list each screenshot file path, one per line>

Write your findings to: <dir>/page-reactions.md

After reviewing all screenshots, add a summary section at the end: your top 5 issues across all pages, ranked by how much they'd bother a real user.
```

### Agent 2: Cross-Page Consistency Auditor

**Output file**: `<dir>/consistency-audit.md`
**Lens**: Simultaneous, comparative — sees all screenshots at once, looks for drift.

```
You are reviewing screenshots of <APP_NAME>, captured from a live app. You have the COMPLETE set of screenshots.

Your job: look at ALL the screenshots together and evaluate the app as a SYSTEM. You are checking whether this feels like one cohesive app or a collection of unrelated pages.

Read every screenshot first, then write your findings:

1. **Element consistency**: Do elements that should look the same actually match across pages? (buttons, cards, headers, tables, spacing, icons, border radii)
2. **Terminology**: Does the same concept have the same name everywhere? Are labels consistent?
3. **Navigation patterns**: Is the sidebar/header/nav the same on every page? Any pages that break the pattern?
4. **Page structure**: Do similar pages follow the same layout? (Do all list pages look alike? All detail pages?)
5. **Interactive element consistency**: Screenshots prefixed with `interact-` show triggered states (open dropdowns, modals, tooltips, form errors). Do all modals share the same visual language? Do all dropdowns look alike? Are form validation styles consistent?

You are looking for DRIFT — things that are inconsistent between pages that should be consistent.

Screenshots:
<list all screenshot file paths>

Write your findings to: <dir>/consistency-audit.md

Prioritize by visibility — inconsistencies on primary pages matter more than edge cases. If the app is genuinely consistent, say so. Don't manufacture findings.
```

### Agent 3: Design Storyteller

**Output file**: `<dir>/design-narrative.md`
**Lens**: Simultaneous, unstructured — sees all screenshots, reacts as a person with taste. No checklist, no sections, no template.

```
You are a designer who has spent your career making beautiful, functional interfaces. You know what good looks like — not because you memorized rules, but because you've developed taste through years of building and critiquing real products.

Someone just handed you screenshots of <APP_NAME> and asked "what do you think?"

Look at ALL the screenshots. Then write what you actually think.

No template. No sections. No checklist. Just talk — the way you'd talk to a colleague over coffee. Stream of consciousness is fine. Jump between observations. Circle back. Contradict yourself if your opinion changes as you look more carefully.

What strikes you first? What bothers you the more you look? What's actually good? Where did someone clearly care, and where did they phone it in? Does this feel like a real product or a tutorial project? What would you change first if this landed on your desk tomorrow?

Compare it to the apps you use every day. Not abstractly — specifically. "This reminds me of early-stage [X] before they figured out [Y]" is more useful than "the spacing could be improved."

If something is genuinely well done, say so with the same specificity you'd use for criticism. "The card elevation system is doing real work here — surface hierarchy is clear without being heavy" is better than "looks nice."

The one thing you MUST do: end with the 3 things that would make the biggest difference to how professional this feels. Not the 3 worst things — the 3 highest-leverage changes.

Screenshots:
<list all screenshot file paths>

Write to: <dir>/design-narrative.md
```

## Phase 4: Synthesize & Present

Read all report files from `<dir>/`:
- `walkthrough.md` — screenshotter's observations and any issues encountered during capture
- `page-reactions.md` — isolated per-page reactions
- `consistency-audit.md` — cross-page consistency issues
- `design-narrative.md` — unstructured design critique

Merge and deduplicate findings. Prioritize by user impact. When agents disagree about the same element, present both assessments with attribution — don't silently pick one.

If the combined findings total fewer than 3 issues, say so plainly: "The UI is in good shape. Here's what was checked and the few minor notes." Skip the backlog flow.

### Per-finding format

```
### [N]. [Issue title]

**Page**: <page name or "cross-page">
**What's wrong**: <direct, specific description — reference what's visible on screen>
**Found by**: <Screenshotter / Page Review / Consistency Audit / Design Narrative — or combination>
**Suggested fix**: <concrete recommendation>
```

### Save the backlog first

If there are 3 or more actionable findings, invoke the backlog save flow from `rules/common/backlog.md` before presenting action options.

### After presenting findings

```
AskUserQuestion:
  question: "What would you like to do with these findings?"
  multiSelect: true
  options:
    - label: "Fix issues now (/mine.build)"
      description: "Start implementing fixes for selected findings"
    - label: "Read a specific agent's full report"
      description: "See unfiltered findings from one of the analysis agents"
    - label: "Re-run with different viewport/theme"
      description: "Run again with --mobile, --dark, or --mobile --dark"
    - label: "Create issues for later"
      description: "File findings as tracked issues"
```

When offering to read agent reports, list the temp file paths.

## Handoffs

**Fix issues** → `/mine.build`

**Track without acting** → create issues via `gh-issue create`

**Different viewport** → re-run this skill with `--mobile` and/or `--dark`

## Principles

1. **Screenshots are evidence** — every finding must reference what the reviewer saw on screen, not what they inferred from code
2. **One browser, no contention** — a single screenshotter captures everything; analysis agents work from saved images only
3. **Cognitive diversity over checklist depth** — each agent uses a genuinely different viewing mode (sequential vs simultaneous, structured vs unstructured). Adding a checklist item is almost never the right response to a missed finding — add a different kind of agent instead.
4. **Focused runs** — one viewport, one theme per run. Fewer screenshots means deeper attention per screenshot. Re-run with different flags for broader coverage.
5. **Don't manufacture** — if the UI looks good, say so. Padding out findings wastes everyone's time.
