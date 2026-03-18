---
name: mine.visual-qa
description: "Use when the user says: \"visual QA\", \"screenshot review\", \"review the UI visually\", or \"take screenshots and find issues\". Screenshots a live app via Playwright, walks task flows, then two agents analyze the captured screenshots for visual and consistency issues."
user-invocable: true
---

# Visual QA

Screenshot-based review of a live UI in two phases: a Flow Walker navigates the app via Playwright (capturing screenshots and testing task flows), then two analysis agents review the saved screenshots from distinct angles — first impressions and cross-page consistency.

## How This Differs From Other Skills

| Skill | What it does |
|-------|-------------|
| `mine.ux-antipatterns` | Static code scan for UX anti-patterns — no live app, no screenshots |
| `ui-auditor` agent | Code-level a11y and consistency grep — no visual verification |
| `visual-diff` agent | Before/after regression screenshots — compares two states |
| **`mine.visual-qa`** | **Live app screenshots + task walkthrough + parallel visual analysis** |

## Arguments

$ARGUMENTS — optional:
- URL: `/mine.visual-qa http://localhost:3000`
- URL + pages: `/mine.visual-qa http://localhost:3000 /dashboard /settings /users`
- Empty: attempt to detect a running dev server, then ask

## Phase 1: Detect Target

### If URL provided in $ARGUMENTS

Use it directly. If specific pages were listed, note them for the Flow Walker.

### If no URL provided

1. Check for a running dev server:
   ```bash
   ss -tlnp 2>/dev/null | grep -E ':(3000|3001|4200|5000|5173|8000|8080|8888) ' | head -5
   ```
2. If a server is found, confirm the URL with the user
3. If nothing found, ask the user for the URL

## Phase 2: Discover Pages

If no specific pages were listed in $ARGUMENTS:

1. Use Playwright to navigate to the base URL
2. Take a snapshot of the page to find navigation links
3. Identify the main pages/views (look for nav menus, sidebars, route links)
4. Present the discovered pages and ask the user which to review:

```
AskUserQuestion:
  question: "I found these pages. Which should I review?"
  header: "Pages"
  multiSelect: true
  options:
    - label: "All pages"
      description: "Review everything I found"
    - label: "<page 1>"
      description: "<url path>"
    - label: "<page 2>"
      description: "<url path>"
    - label: "<page 3>"
      description: "<url path>"
```

## Phase 3: Flow Walker (Screenshot Capture + Task Walkthrough)

Before launching, create a unique temp directory:

1. Run: `get-skill-tmpdir mine-visual-qa`
2. Note the directory path (e.g., `/tmp/claude-mine-visual-qa-a8Kx3Q`)

Launch a single `general-purpose` agent with Playwright access. This agent does two things at once: captures a complete screenshot library AND tests task flows by actually using the app.

**Agent type**: `general-purpose`
**Output file**: `<dir>/flow-walkthrough.md`
**Screenshot directory**: `<dir>/screenshots/`
**Run in background**: `true`

```
You are a first-time user opening <APP_NAME> at <APP_URL>. The app has real data in it.

You have two jobs:
1. CAPTURE SCREENSHOTS of every page for other reviewers to analyze later
2. TEST TASK FLOWS by actually trying to use the app

DO NOT look at source code. Just use the app as a human would.

## Screenshot Capture

For every page you visit, save screenshots to <dir>/screenshots/ using Playwright MCP tools:
- Desktop viewport: take a screenshot of each page
- Mobile viewport: resize to 375px width and screenshot each page again
- Dark/light mode: if the app has a theme toggle, switch modes and screenshot each page in both
- Scrolled content: if a page scrolls, scroll down and capture additional screenshots

Name files descriptively: `dashboard-desktop.png`, `dashboard-mobile.png`, `settings-dark.png`, etc.

## Task Walkthrough

Navigate through the app and try to complete real tasks. Narrate moment-by-moment:
1. "I want to [goal]. I look at the screen. I see [what's visible]. I think I should click [element]."
2. "I clicked it. Now I see [result]. I expected [what you expected]. This is [clear/confusing/wrong]."
3. "The next step should be [X]. I can/can't find how to do it."
4. Continue until the task is complete or you get stuck.

Tasks to attempt:
- Find and view an existing item from a list
- Create a new item (fill out the form, submit it)
- Edit an existing item
- Delete something — is there confirmation? Can you undo it?
- Use search or filter to find something specific
- Navigate from any page back to the starting page
<Add any app-specific tasks based on what the PAGES suggest>

Screenshot each step as you go.

After completing all tasks, also check:
- Do you always know where you are in the app?
- After each action, is there clear feedback that it worked?
- Are there dead ends — pages where you can't figure out what to do next?
- Does the browser back button work sensibly?

## Pages to Visit
<PAGES>

## Output

Write your walkthrough findings to: <dir>/flow-walkthrough.md

Prioritize by severity of getting stuck — "I literally could not figure out how to delete an item" ranks above "the success message disappeared too quickly."
```

## Phase 4: Launch Two Analysis Agents

After the Flow Walker completes, read its output file to confirm screenshots were captured. Then launch two `general-purpose` agents in parallel with `run_in_background: true`.

These agents receive the screenshot file paths — they do NOT use Playwright. They analyze the saved images from two distinct tasks.

### Agent 1: First-Impression Reactor

**Agent type**: `general-purpose`
**Output file**: `<dir>/first-impressions.md`
**Task**: Go through each screenshot one at a time and give an honest gut reaction.

```
You are looking at screenshots of <APP_NAME>, captured from a live app.

Your job: go through each screenshot one at a time and react honestly. For each one, answer:
1. What's your gut reaction? Does it look polished or rough?
2. What draws your eye — is it the right thing?
3. Does the visual hierarchy make sense? Can you tell what's important?
4. Is anything misaligned, too cramped, too sparse, or visually "off"?
5. Is the purpose of this page immediately clear?
6. Would anything confuse a regular person?

Be brutally honest. "This looks like a prototype" or "I have no idea what this page is for" — that kind of candor. Be specific about location — "the spacing between the header and the first card is 2x the spacing between cards" is better than "spacing issues."

Screenshots are at: <dir>/screenshots/
Read each screenshot file and react to it.

Write your findings to: <dir>/first-impressions.md

Prioritize by what hurts the most — put the worst things at the top.
```

### Agent 2: Cross-Page Consistency Auditor

**Agent type**: `general-purpose`
**Output file**: `<dir>/consistency-audit.md`
**Task**: Compare ALL screenshots against each other — find inconsistencies across the app.

```
You are looking at screenshots of <APP_NAME>, captured from a live app.

Your job: look at ALL the screenshots together and compare across pages. You are checking whether this app feels like ONE app or a collection of unrelated pages.

For each concern, answer:
1. Do elements that should look the same actually look the same? (buttons, cards, headers, tables, spacing, icons)
2. Is terminology consistent? (Does the same concept have the same name on every page?)
3. Do navigation patterns match across pages? (Is the sidebar/header the same everywhere?)
4. Are similar pages structured the same way? (Do all list pages look alike? Do all detail pages?)
5. Do mobile screenshots maintain the same relative quality as desktop, or do some pages break?
6. If dark/light mode screenshots exist — do both modes look intentional, or is one clearly an afterthought?

You are specifically looking for DRIFT — things that are inconsistent between pages that should be consistent. A single page looking bad is someone else's job. You care about whether page A and page B agree.

Screenshots are at: <dir>/screenshots/
Read all screenshots and compare them.

Write your findings to: <dir>/consistency-audit.md

Prioritize by visibility — inconsistencies on primary pages matter more than edge cases.
```

## Phase 5: Synthesize & Present

Read all three report files:
- `<dir>/flow-walkthrough.md` — task flow issues
- `<dir>/first-impressions.md` — per-page visual/UX reactions
- `<dir>/consistency-audit.md` — cross-page consistency issues

Merge and deduplicate findings. Prioritize by user impact — "users can't complete the primary task" ranks above "button border radius varies."

### Per-finding format

```
### [N]. [Issue title]

**Page**: <page name or "cross-page">
**What's wrong**: <direct, specific description — reference what's visible on screen>
**Found by**: <Flow Walker / First Impressions / Consistency Audit — or combination>
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
      description: "See unfiltered findings from the flow walker, first impressions, or consistency audit"
    - label: "Create issues for later"
      description: "File findings as tracked issues"
```

When offering to read agent reports, list the three temp file paths.

## Handoffs

**Fix issues** → `/mine.build`

**Track without acting** → create issues via `gh-issue create`

## Principles

1. **Screenshots are evidence** — every finding must reference what the reviewer saw on screen, not what they inferred from code
2. **One browser, no contention** — a single Flow Walker captures all screenshots serially; analysis agents work from saved images only
3. **Task-based differentiation** — agents do different *activities* (react to each page vs. compare across pages), not different *lenses* on the same activity. No IGNORE instructions needed.
4. **Don't manufacture** — if the UI looks good, say so. Padding out findings wastes everyone's time
5. **Actionable fixes** — every finding includes a concrete recommendation, not just a complaint
