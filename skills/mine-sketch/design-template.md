# Sketch Design Template

Write the design doc to `<feature_dir>/design.md` using this template:

```markdown
# Design: <Topic>

**Date:** YYYY-MM-DD
**Status:** draft
**Mode:** sketch

## Problem

[1-2 sentences. What is broken, missing, or suboptimal — and why it matters now.]

## Goals

[What success looks like. Keep it tight — 2-4 bullets max.]

[Optional "## Non-Goals" section — only include if the user explicitly named exclusions.]

## Functional Requirements

- **FR#1** [One testable behavior — state what the system must do, not how]
  - **AC#1** [Measurable, observable outcome — verifiable by running a local command]
- **FR#2** [Each entry describes exactly one behavior]
  - **AC#2** [Each entry tests one outcome, verifiable by running a local command. An AC that verifies more than one FR sits under its primary FR and cites the others as (also FR#N)]

[Each AC must be verifiable by an executor running commands in the local repo.]

## Operational Lifecycle

[Conditional section — include only when the feature owns resumable work state across invocations, such as a background worker, batch/backfill, scheduler, queue consumer, or persistent retry state. Define completion, retry eligibility and bounds, states requiring user action and their recovery path, repeated-run convergence, visible progress/failure accounting, and a realistic local validation scenario. Omit otherwise. This section explains the model, not the requirements themselves — every applicable lifecycle outcome is its own FR#N with ACs above, so planning can trace and verify it.]

## Approach

[The recommended approach with rationale. Reference specific files, patterns, and existing code. Key architecture decisions go here. This replaces the full Architecture, Implementation Preferences, and Alternatives Considered sections from a full design doc — keep it focused on what matters for execution. Cite `## Changed Files` for the file list rather than repeating it here.]

## Dependencies and Assumptions

[Conditional section — include only when the sketch accepts an external dependency or an explicit verification gap. State the accepted risk and mitigation. For an Operational Lifecycle with no local test infrastructure, record that limitation here; otherwise omit this section.]

## Changed Files

[List each file with its change verb (create / modify / delete) and a one-line note on what changes.]

## Addendum

[Never written at creation time — appended later, only once `**Status:**` reaches a terminal value (`archived` or `abandoned`). Once terminal, treat the sections above as settled — what was approved, and for `archived`, what got built. Don't rewrite them to match reality that changed after the fact. Append a dated entry instead:

### YYYY-MM-DD: <one-line summary of what changed>
<What diverged from the design above, and why.>

Drift against a terminal-status design doc is expected, not a finding — reviewers, challenge, and comb should never propose editing the sections above to "correct" them.]
```

## Content Rules

- Functional Requirements use canonical identifier format `FR#N` (e.g., `FR#1`, `FR#2`). Each describes exactly one testable behavior.
- Acceptance Criteria use canonical identifier format `AC#N` (e.g., `AC#1`, `AC#2`). Each must be verifiable by running a local command.
- AC numbering, citation, and whole-suite-check rules follow `${CLAUDE_CONFIG_DIR:-~/.claude}/skills/mine-define/design-doc-format.md` (Nested ACs and Numbering Rules)
- When `## Operational Lifecycle` applies, the numbered requirements must cover repeated failure, retry bounds/termination, recovery or deliberately terminal behavior, and visible accounting; isolated one-transition tests are insufficient.
- The Approach section should reference actual file paths, class names, and patterns found during investigation.
- **One fact, one home** — follow `${CLAUDE_CONFIG_DIR:-~/.claude}/skills/mine-define/design-doc-format.md` (One Fact, One Home)
- No `[NEEDS CLARIFICATION]` markers — if you don't know, ask before writing.
- Once `**Status:**` is terminal (`archived` or `abandoned`), never edit body sections to reflect later reality — append a dated entry to `## Addendum` instead.
