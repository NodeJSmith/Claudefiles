---
name: mine.visual-qa
description: "Use when the user says: \"visual QA\", \"screenshot review\", \"review the UI visually\", or \"take screenshots and find issues\". Screenshots a live app via Playwright, then two agents analyze the captures — one sees each screenshot in isolation, the other sees all of them at once."
user-invocable: true
---

# Visual QA

Screenshot-based review of a live UI. A screenshotter navigates the app via Playwright and captures every page, then two analysis agents review the screenshots with structurally different access — one sees each screenshot in isolation (forced first impressions), the other sees all screenshots simultaneously (cross-page consistency). The structural constraint on what each agent can see produces genuinely different findings.

## How This Differs From Other Skills

| Skill | What it does |
|-------|-------------|
| `mine.ux-antipatterns` | Static code scan for UX anti-patterns — no live app, no screenshots |
| `ui-auditor` agent | Code-level a11y and consistency grep — no visual verification |
| `visual-diff` agent | Before/after regression screenshots — compares two states |
| **`mine.visual-qa`** | **Live app screenshots + structurally separated visual analysis** |

## Arguments

$ARGUMENTS — optional:
- URL: `/mine.visual-qa http://localhost:3000`
- URL + pages: `/mine.visual-qa http://localhost:3000 /dashboard /settings /users`
- Empty: attempt to detect a running dev server, then ask

## Phase 1: Detect Target & Pages

### If URL and pages provided in $ARGUMENTS

Use them directly.

### If only URL provided

Navigate to the URL with Playwright, take a snapshot, identify main pages/views from navigation links. Auto-include all discovered pages. Only ask the user if more than 10 pages are found — in that case, present the list and ask which to include.

### If nothing provided

1. Check for a running dev server:
   ```bash
   ss -tlnp 2>/dev/null | grep -E ':(3000|3001|4200|5000|5173|8000|8080|8888) ' | head -5
   ```
2. If found, confirm the URL with the user
3. If not found, ask the user for the URL
4. Then discover pages as above

## Phase 2: Screenshotter (Playwright Capture)

Create a unique temp directory:

1. Run: `get-skill-tmpdir mine-visual-qa`
2. Note the directory path (e.g., `/tmp/claude-mine-visual-qa-a8Kx3Q`)

Launch a single `general-purpose` agent with Playwright access. Its primary job is capturing a complete screenshot library — both static page views AND interactive element states (dropdowns, modals, tooltips, etc.). Page coverage comes first, then it goes back to trigger interactive elements.

**Agent type**: `general-purpose`
**Output file**: `<dir>/walkthrough.md`
**Screenshot directory**: `<dir>/screenshots/`
**Run in background**: `true`

```
You are opening <APP_NAME> at <APP_URL> for the first time.

Your PRIMARY job is capturing screenshots of every page for other reviewers to analyze. Your secondary job is narrating your experience as you go.

DO NOT look at source code. Just use the app as a human would.

## Screenshot Capture (do this first)

Visit every page listed below and capture screenshots. Save to <dir>/screenshots/ using Playwright MCP tools.

### Naming Convention

Name files with a zero-padded sequence number, page name, viewport, and theme:

```
01-dashboard-desktop-light.png
02-dashboard-desktop-dark.png
03-dashboard-mobile-light.png
04-items-list-desktop-light.png
05-items-list-desktop-dark.png
06-items-list-mobile-light.png
```

For interactive element states, use an `interact-` prefix with the element type:

```
20-interact-dropdown-category-open.png
21-interact-datepicker-expanded.png
22-interact-modal-delete-confirm.png
23-interact-tooltip-status-hover.png
24-interact-accordion-details-open.png
```

The leading number gives global ordering. The `interact-` prefix tells reviewers this is a triggered state, not a default page view.

### What to Capture

**Step 1 — Page screenshots (do this first for every page):**
- Desktop viewport screenshot
- Mobile viewport (resize to 375px width) screenshot
- If the app has a dark/light toggle: screenshot in both modes
- If the page scrolls: scroll down and capture additional screenshots

**Finish capturing ALL pages before interacting with elements.** Page coverage is your most important deliverable.

**Step 2 — Interactive element states (after all pages are captured):**

Go back through the pages and trigger every interactive element you can find. The goal is to reveal visual states that are invisible in a static screenshot:
- **Dropdowns / selects**: click to open, screenshot the expanded state
- **Modals / dialogs**: trigger any modal (delete confirmation, create form, etc.), screenshot it
- **Tooltips**: hover over elements with tooltips, screenshot
- **Accordions / collapsibles**: expand them, screenshot
- **Radio buttons / checkboxes / toggles**: click them to show selected state
- **Date pickers / color pickers**: open them, screenshot
- **Form validation**: submit an empty form or enter invalid data, screenshot error states
- **Loading / empty states**: if you can trigger them (clear a filter to show "no results"), screenshot

Narrate briefly what you triggered and what appeared. The screenshots are the main deliverable.

## Pages to Visit
<PAGES>

## Output

Write a brief walkthrough log to: <dir>/walkthrough.md

Include:
1. A manifest section listing every screenshot captured and which page/viewport/theme/interaction it covers
2. Brief narration of what you observed — especially interactive elements that revealed unexpected visual states
3. Any elements you couldn't trigger or pages you couldn't reach
```

## Phase 3: Launch Two Analysis Agents

After the Screenshotter completes, read its output file and confirm screenshots were captured. Glob for `<dir>/screenshots/*.png` to get the actual file list.

Launch two `general-purpose` agents with `run_in_background: true`. The key design: **Agent 1 sees one screenshot at a time. Agent 2 sees all of them at once.** This structural constraint — not prompt instructions — is what produces different findings.

### Agent 1: Isolated Page Reviewer

**Agent type**: `general-purpose`
**Output file**: `<dir>/page-reactions.md`
**Structure**: Invoked ONCE, but instructed to read and react to each screenshot individually, writing its reaction before moving to the next. It must not reference other screenshots in its reactions.

```
You are reviewing screenshots of <APP_NAME>, captured from a live app. Each screenshot shows one page or one step of a task flow.

Your job: read each screenshot ONE AT A TIME. After reading each one, immediately write your reaction BEFORE looking at the next screenshot. Do not go back and revise earlier reactions. Do not compare to other screenshots — react only to what's in front of you right now.

For each screenshot, write:

### [filename]
- **Gut reaction**: Does this look polished or rough?
- **Eye draw**: What draws your eye first — is that the right thing?
- **Clarity**: Is the purpose of this page immediately obvious?
- **Issues**: Anything misaligned, cramped, sparse, confusing, or ugly? Be specific about location.
- **Labels/copy**: Do the words on screen make sense? Any jargon or unclear terms?

Be brutally honest. "This looks like a prototype" or "I have no idea what this page is for" — that kind of candor. Be specific — "the spacing between the header and the first card is 2x the spacing between cards" is better than "spacing issues."

Screenshots to review (in this order):
<list each screenshot file path, one per line>

Write your findings to: <dir>/page-reactions.md

After reviewing all screenshots, add a summary section at the end: your top 5 issues across all pages, ranked by how much they'd bother a real user.
```

### Agent 2: Cross-Page Consistency Auditor

**Agent type**: `general-purpose`
**Output file**: `<dir>/consistency-audit.md`
**Structure**: Reads ALL screenshots at once, then compares across the full set.

```
You are reviewing screenshots of <APP_NAME>, captured from a live app. You have the COMPLETE set of screenshots — every page, in desktop and mobile viewports, in light and dark modes.

Your job: look at ALL the screenshots together and evaluate the app as a SYSTEM. You are checking whether this feels like one cohesive app or a collection of unrelated pages.

Read every screenshot first, then write your findings:

1. **Element consistency**: Do elements that should look the same actually match across pages? (buttons, cards, headers, tables, spacing, icons, border radii)
2. **Terminology**: Does the same concept have the same name everywhere? Are labels consistent?
3. **Navigation patterns**: Is the sidebar/header/nav the same on every page? Any pages that break the pattern?
4. **Page structure**: Do similar pages follow the same layout? (Do all list pages look alike? All detail pages?)
5. **Mobile quality**: Do mobile screenshots maintain the same relative quality as desktop, or do some pages break?
6. **Dark/light mode**: If both modes were captured — do both look intentional, or is one clearly an afterthought?
7. **Flow coherence**: For task flow screenshots — do the steps feel like a smooth progression, or do screens feel disconnected?

You are looking for DRIFT — things that are inconsistent between pages that should be consistent.

Screenshots:
<list all screenshot file paths>

Write your findings to: <dir>/consistency-audit.md

Prioritize by visibility — inconsistencies on primary pages matter more than edge cases. If the app is genuinely consistent, say so. Don't manufacture findings.
```

## Phase 4: Synthesize & Present

Read all three report files:
- `<dir>/walkthrough.md` — screenshotter's manifest and narration of interactive element states
- `<dir>/page-reactions.md` — isolated per-page reactions
- `<dir>/consistency-audit.md` — cross-page consistency issues

Merge and deduplicate findings. Prioritize by user impact.

If the combined findings total fewer than 3 issues, say so plainly: "The UI is in good shape. Here's what was checked and the few minor notes." Skip the backlog flow.

### Per-finding format

```
### [N]. [Issue title]

**Page**: <page name or "cross-page">
**What's wrong**: <direct, specific description — reference what's visible on screen>
**Found by**: <Screenshotter / Page Review / Consistency Audit — or combination>
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
      description: "See unfiltered findings from the screenshotter, page reviewer, or consistency auditor"
    - label: "Create issues for later"
      description: "File findings as tracked issues"
```

When offering to read agent reports, list the three temp file paths.

## Handoffs

**Fix issues** → `/mine.build`

**Track without acting** → create issues via `gh-issue create`

## Principles

1. **Screenshots are evidence** — every finding must reference what the reviewer saw on screen, not what they inferred from code
2. **One browser, no contention** — a single screenshotter captures everything; analysis agents work from saved images only
3. **Structural separation** — Agent 1 sees one screenshot at a time (forced isolation), Agent 2 sees all of them (forced comparison). The constraint is on what the agent can *see*, not what it's told to focus on.
4. **Screenshots first** — the screenshotter prioritizes complete page coverage over deep task exploration. Incomplete screenshots mean incomplete analysis.
5. **Don't manufacture** — if the UI looks good, say so. Padding out findings wastes everyone's time.
