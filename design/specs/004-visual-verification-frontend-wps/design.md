# Design: Visual Verification for Frontend Work Packages

**Date:** 2026-03-19
**Status:** draft

## Problem

When `mine.orchestrate` executes work packages that change the frontend, the review loop (spec reviewer + code reviewer + integration reviewer) catches code-level issues but never visually verifies the UI. Visual regressions — overflow, clipping, broken layouts, misaligned elements — are invisible to code review and only surface when a human opens the browser.

The existing `frontend-workflow.md` rule says "take screenshots after UI changes," but this is guidance for humans, not enforced by the orchestration pipeline. The result: frontend WPs pass all automated gates and ship with visual bugs.

### The "trivial screenshot" problem

A naive solution (screenshot the page after implementation) fails for dynamic UIs. A graph frontend screenshotted with zero data, or a dashboard with 3 rows when the WP changed pagination behavior, proves nothing. Visual verification must capture **meaningful states** — pages with realistic data, filters applied, interactive elements exercised. The agent doing the screenshotting needs to know *what state matters*, not just *which page to visit*.

## Prior Art in This Repo

| Existing piece | What it does | Gap |
|---|---|---|
| `frontend-workflow.md` rule | Says "screenshot before/after UI changes" | Guidance only — not enforced by orchestrate |
| `visual-diff` agent | Before/after regression screenshots | Static page loads only — no state setup, no interaction |
| `mine.visual-qa` skill | Full visual QA (screenshotter + 3 analysis agents) | Too heavy for per-WP gates; designed for standalone reviews |
| `mine.orchestrate` Step 3 | Selects `engineering-frontend-developer` for UI WPs | Knows WP is frontend, does nothing visual with that signal |

## Architecture

### Core principle: Specification over improvisation

Visual scenarios are authored at planning time (`mine.draft-plan`) and executed at implementation time (executor). The executor follows a spec; it doesn't improvise what to verify. The spec reviewer audits plan coverage; a dedicated visual reviewer judges the screenshots.

### Data flow

```
mine.draft-plan                    mine.orchestrate
┌─────────────────┐               ┌──────────────────────────────────────┐
│ Design doc has   │               │ Per-WP loop:                         │
│ frontend impact  │──────────────▶│                                      │
│                  │  WP spec with │ Step 4: Executor                     │
│ Generate Visual  │  Visual       │   - Reads Visual Verification        │
│ Verification     │  Verification │   - Resolves URLs at runtime         │
│ scenarios in WP  │  scenarios    │   - Captures before screenshots      │
│ body             │               │   - Implements WP                    │
└─────────────────┘               │   - Captures after screenshots       │
                                  │   - Reports visual summary           │
                                  │                                      │
                                  │ Step 5: Spec reviewer                │
                                  │   - Audits: did executor cover all   │
                                  │     scenarios from the WP spec?      │
                                  │   - Does NOT judge visual quality    │
                                  │                                      │
                                  │ Step 5.5: Visual reviewer (NEW)      │
                                  │   - Examines before/after screenshots│
                                  │   - Judges against scenario verify   │
                                  │     criteria                         │
                                  │   - Reports VERIFIED|WARN|FAIL       │
                                  │                                      │
                                  │ Steps 6-9: existing flow, now with   │
                                  │   visual verdict in summary          │
                                  └──────────────────────────────────────┘
```

### Component changes

#### 1. WP template addition (`mine.draft-plan`)

When a WP's subtasks modify UI components, pages, styles, or layouts, `mine.draft-plan` adds a `Visual Verification` section to the WP body (not frontmatter — scenarios are too rich for YAML):

```markdown
## Visual Verification

| Page | Setup | Verify |
|------|-------|--------|
| Dashboard metrics grid | Load with 50+ rows, apply date filter, sort by "Amount" descending | Grid renders without overflow, sort indicator visible, pagination controls functional |
| Dashboard mobile | Same data, 375px viewport | Grid collapses to card layout, no horizontal scroll, filter drawer accessible |
```

**Authoring rules for draft-plan:**
- Only add this section when WP subtasks clearly modify visual output
- Describe *scenarios*, not URLs — the executor resolves URLs at runtime from the codebase
- Each scenario must specify: what page, what state to put it in, what to visually verify
- Scenarios should exercise the specific behavior the WP changes, not just "page loads"
- If the design doc describes specific visual requirements, pull them into verify criteria

**When to omit:** Backend-only WPs, pure refactoring with no visual impact, test-only WPs. If unsure, omit — no structured visual verification will run for this WP. Note: `frontend-workflow.md` is a separate, general rule that applies to all frontend work regardless of whether structured scenarios exist; this section adds orchestrator-enforced verification on top of that baseline.

#### 2. Executor prompt addition (`implementer-prompt.md`)

A new "Visual Verification" section, loaded for all executors but activated only when the WP contains a `## Visual Verification` section. Instructions:

- **Before implementation:** For each scenario in the Visual Verification table, resolve the page to a URL, set up the specified state (navigate, apply filters, load data), and capture a baseline screenshot. Write a structured capture plan to the output (URLs, viewport, setup steps) so the after-capture can reproduce exactly.
- **After implementation:** Replay the capture plan. Capture after-screenshots in the same states. Note what changed visually.
- **Dev server check:** Probe common ports before first capture. If no server: report SKIPPED per-scenario (don't silently skip).
- **Output:** Structured `Visual verification` block with per-scenario results and screenshot paths.
- **Reference:** Follows `rules/common/frontend-workflow.md` for screenshot protocol.

#### 3. Spec reviewer addition (`spec-reviewer-prompt.md`)

A new step 7 "Visual verification plan audit" that checks *coverage*, not *visual quality*:

- Did the executor address every scenario in the WP's Visual Verification table?
- Did the executor report SKIPPED for any scenario? If so, is the reason valid?
- Did the executor modify the scenarios or skip any without justification?
- If the WP has no Visual Verification section but subtasks clearly modify UI files, flag as WARN.

The spec reviewer does NOT examine screenshots for visual correctness — that's the visual reviewer's job.

#### 4. Visual reviewer (`visual-reviewer-prompt.md` — NEW)

A lightweight, single-agent visual reviewer launched after the spec review for WPs that have visual verification scenarios. This is a new prompt file in `skills/mine.orchestrate/`.

- Receives: WP spec (with Visual Verification table), executor's before/after screenshots, executor's visual summary
- For each scenario: examines the after-screenshot against the scenario's "Verify" criteria
- Reports per-scenario: VERIFIED | WARN | FAIL with specific observations
- Checks for unintended regressions visible in before/after comparison
- Overall verdict: VERIFIED (all pass) | WARN (minor concerns) | FAIL (scenario criteria not met or regression detected)

This agent's sole job is looking at screenshots. It doesn't review code, doesn't check tests, doesn't verify scope. Single purpose, single cognitive mode.

#### 5. Orchestrate loop changes (`mine.orchestrate/SKILL.md`)

- **New Step 5.5:** After spec review, if the WP contains a `## Visual Verification` section: launch the visual reviewer subagent. If the WP has no visual verification section, skip this step (Visual line shows N/A in summary).
- **Step 6 update:** Visual reviewer verdict feeds into deviation classification:
  - Visual VERIFIED → no impact
  - Visual WARN → overall WP gets WARN
  - Visual FAIL → overall WP gets FAIL
  - Visual SKIPPED (no dev server) → counts as WARN (not invisible)
- **Step 9 update:** Summary gains a Visual line:
  ```
  Visual: VERIFIED (3 scenarios) | WARN | FAIL | SKIPPED | N/A
  ```

### What this design explicitly does NOT do

- **Cross-WP visual regression detection.** Per-WP visual checks verify that *this WP's* changes match *this WP's* scenarios. They do not detect regressions caused by the cumulative effect of multiple WPs. Detecting cross-WP regressions requires feature-level visual comparison — use `mine.visual-qa` after all WPs complete for that. The post-execution handoff (Phase 3) is the right place for a feature-level visual review.
- **Pixel-diff comparison.** Vision model comparison catches layout-level regressions. Pixel-perfect comparison is overkill for WP-level gates and would generate false positives from anti-aliasing and subpixel rendering differences.
- **Responsive/dark-mode testing per WP.** Scenarios can specify viewport (e.g., "375px viewport"), but systematic responsive and dark-mode testing belongs in `mine.visual-qa` runs, not per-WP gates.

## Alternatives Considered

### v1: Separate pipeline steps with visual-diff agent

Added Steps 3.5 (baseline) and 5.5 (comparison) using the `visual-diff` agent and `visual_pages` WP frontmatter. Rejected because:
- `visual_pages` URLs can't be determined at planning time
- Baseline capture as a separate step breaks without inter-WP commits
- `visual-diff` agent can't set up meaningful page state
- One-time dev server check goes stale
- New prompt file forks the visual-diff agent

### v2: Executor captures + spec reviewer audits (no new files)

Executor captures before/after and the spec reviewer judges visual quality. Rejected because:
- "Meaningful state" was undefined — executor improvises and captures trivial defaults
- Spec reviewer is the wrong agent for visual judgment (document verification, not visual critique)
- No visual scenarios in the WP spec — process without specification
- Conflicts with existing `frontend-workflow.md` without acknowledging it

### v3 (this design): Specified scenarios + dedicated visual reviewer

Combines the best of v1 and v2:
- Scenarios authored at planning time (from v1's intent, but as scenarios not URLs)
- Executor captures with deepest context (from v2's architecture)
- Dedicated visual reviewer for visual judgment (addressing v2's cognitive mode concern)
- References `frontend-workflow.md` as single source of truth for screenshot protocol

## Prerequisites

**Empirical validation required before implementation:**

1. Confirm executor subagents can call Playwright MCP tools (`browser_navigate`, `browser_take_screenshot`)
2. Confirm the visual reviewer subagent can read PNG files via the Read tool and interpret them visually
3. If either fails, the design needs rearchitecting — visual capture/review would need to happen at the orchestrator level, not in subagents

## Open Questions

1. Should `mine.visual-qa` be automatically suggested in Phase 3 (post-execution handoff) for features that had frontend WPs? This would catch cross-WP regressions that per-WP checks miss.
2. Should the visual reviewer have access to Playwright to independently re-capture screenshots, or should it only work from the executor's captures?
