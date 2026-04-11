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
- NAMING_EXAMPLES:
  ```
  01-dashboard-mobile-dark.png
  02-items-list-mobile-dark.png
  03-settings-mobile-dark.png
  ```

```
You are opening <APP_NAME> at <APP_URL> for the first time.

Your job is capturing screenshots of every page for other reviewers to analyze. Narrate briefly as you go.

DO NOT look at source code. Just use the app as a human would.

## Viewport & Theme

<VIEWPORT_INSTRUCTION>

## Screenshot Capture

Visit every page listed below and capture screenshots. Save to <dir>/screenshots/ using Playwright MCP tools.

### Naming Convention

Name files with a zero-padded sequence number, page name, and any active mode suffix (e.g., `-mobile`, `-dark`, `-mobile-dark`):

<NAMING_EXAMPLES>

For interactive element states, include `-interact-` after the page name:

```
20-items-list-interact-dropdown-category-open.png
21-items-list-interact-modal-delete-confirm.png
22-settings-interact-datepicker-expanded.png
```

### What to Capture

**Step 1 — Page screenshots (do this first for every page):**
- One screenshot per page in the configured viewport/theme
- If a page scrolls, scroll down one viewport height at a time and capture each fold. Name them with a `-fold2`, `-fold3` suffix. Wait briefly for lazy-loaded content before scrolling further.

**Finish capturing ALL pages before interacting with elements.** Page coverage is your most important deliverable.

**Step 2 — Interactive element states (after all pages are captured):**

Go back through the pages and trigger interactive elements to reveal visual states invisible in a static screenshot. **Budget: up to 3 interactive screenshots per page, maximum 20 total.** Prioritize the most visually significant elements.

Priority order:
1. Modals / dialogs
2. Dropdowns / selects — open to show expanded state
3. Form validation — submit empty or enter invalid data to show error states
4. Tooltips — hover to reveal
5. Accordions / collapsibles — expand
6. Date pickers / color pickers — open
7. Radio buttons / checkboxes / toggles — show selected state
8. Loading / empty states — clear a filter to show "no results"

Stop when you're reaching for low-value interactions. Narrate briefly what you triggered and what appeared.

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

After the Screenshotter completes, read its output file and glob for `<dir>/screenshots/*.png` to get the actual file list.

**Zero-screenshot gate**: If no `.png` files exist, stop. Report the failure to the user — do not launch analysis agents on nothing. Common causes: Playwright MCP disconnected, the app requires authentication, or the dev server went down. If `walkthrough.md` exists, read it for clues about what went wrong.

Launch the following `general-purpose` agents with `run_in_background: true`. Each sees the same screenshots through a different lens.

### Agent 1: First-Impressions Reviewer

**Output file**: `<dir>/page-reactions.md`
**Lens**: Per-page, gut-reaction focused. Prioritizes immediate impressions over cross-page analysis.

```
You are reviewing screenshots of <APP_NAME>, captured from a live app. Each screenshot shows one page or one interactive state.

Your job: write a reaction to each screenshot, one at a time. Focus on your immediate impression of each page — don't cross-reference or compare across pages. Write your reaction to each screenshot before moving to the next.

For each screenshot, write a `### [filename]` heading and your honest reaction. Write what actually strikes you — if the dominant impression is "this is beautiful and I have nothing to critique," say that. If it's "I can't tell what this page is for," say that. Don't force observations that aren't there.

If you're stuck on a screenshot, consider: Does it look polished or rough? What draws your eye first — is that the right thing? Is the purpose obvious? Is anything misaligned, cramped, sparse, or confusing?

Be brutally honest and specific — "the spacing between the header and the first card is 2x the spacing between cards" is better than "spacing issues."

Screenshots to review (in this order):
<list each screenshot file path, one per line>

Write your findings to: <dir>/page-reactions.md

After reviewing all screenshots, add a summary section: your top 5 issues, ranked by how much they'd bother a real user.
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
5. **Interactive element consistency**: Screenshots with `-interact-` in the filename show triggered states (open dropdowns, modals, tooltips, form errors). Do all modals share the same visual language? Do all dropdowns look alike? Are form validation styles consistent?

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

Look at ALL the screenshots. Then write what you actually think. Be specific enough that someone could act on what you say — "the spacing feels off" is useless, "the gap between the header and the first card is twice the gap between cards" is actionable. When you reference something specific, name the page or screenshot it appears on.

End with the 3 highest-leverage changes — the things that would make the biggest difference to how professional this feels.

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

If the combined findings total fewer than 3 issues, say so plainly: "The UI is in good shape. Here's what was checked and the few minor notes."

### Per-finding format

```
### [N]. [Issue title]

**Page**: <page name or "cross-page">
**What's wrong**: <direct, specific description — reference what's visible on screen>
**Found by**: <Screenshotter / Page Review / Consistency Audit / Design Narrative — or combination>
**Suggested fix**: <concrete recommendation>
```

### After presenting findings

This skill uses a skill-specific gate (per `~/.claude/skills/mine.challenge/findings-protocol.md` Skill-Specific Overrides) because resolution paths include non-fix actions.

```
AskUserQuestion:
  question: "What would you like to do with these findings?"
  multiSelect: true
  options:
    - label: "Fix issues now (Recommended)"
      description: "Auto-apply unambiguous fixes; ask per-finding for judgment calls"
    - label: "Read a specific agent's full report"
      description: "See unfiltered findings from one of the analysis agents"
    - label: "Re-run with different viewport/theme"
      description: "Run again with --mobile, --dark, or --mobile --dark"
    - label: "File as issues"
      description: "File findings as tracked issues for later"
```

When offering to read agent reports, list the temp file paths. If "Fix issues now" is selected, follow the legacy resolve flow in `~/.claude/skills/mine.challenge/findings-protocol.md`'s Skill-Specific Overrides section. (A follow-up design will migrate visual-qa to the Resolution Manifest flow; that work is explicit scope for the next design iteration and is NOT in scope here.)

## Handoffs

**Fix issues** → follow the legacy Skill-Specific Override path in `~/.claude/skills/mine.challenge/findings-protocol.md` (Resolution Manifest migration deferred to follow-up design)

**Different viewport** → re-run this skill with `--mobile` and/or `--dark`

## Principles

1. **Screenshots are evidence** — every finding must reference what the reviewer saw on screen, not what they inferred from code
2. **One browser, no contention** — a single screenshotter captures everything; analysis agents work from saved images only
3. **Cognitive diversity over checklist depth** — each agent uses a genuinely different mode: per-page gut reactions, systematic cross-page comparison, and freeform narrative. Adding a checklist item is almost never the right response to a missed finding — add a different kind of agent instead.
4. **Focused runs** — one viewport, one theme per run. Fewer screenshots means deeper attention per screenshot. Re-run with different flags for broader coverage.
5. **Don't manufacture** — if the UI looks good, say so. Padding out findings wastes everyone's time.
