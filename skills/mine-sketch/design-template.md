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
- **FR#2** [Each entry describes exactly one behavior]

## Operational Lifecycle

[Conditional section — include only when the feature owns resumable work state across invocations, such as a background worker, batch/backfill, scheduler, queue consumer, or persistent retry state. Define completion, retry eligibility and bounds, states requiring user action and their recovery path, repeated-run convergence, visible progress/failure accounting, and a realistic local validation scenario. Omit otherwise. Express every applicable lifecycle outcome as an FR#N or AC#N so planning can trace and verify it.]

## Acceptance Criteria

- **AC#1** [Measurable, observable outcome — verifiable by running a local command]
- **AC#2** [Each entry tests one outcome; map to FR#N identifiers where relevant]

[Each AC must be verifiable by an executor running commands in the local repo.]

## Approach

[The recommended approach with rationale. Reference specific files, patterns, and existing code. Key architecture decisions go here. This replaces the full Architecture, Implementation Preferences, and Alternatives Considered sections from a full design doc — keep it focused on what matters for execution.]

## Dependencies and Assumptions

[Conditional section — include only when the sketch accepts an external dependency or an explicit verification gap. State the accepted risk and mitigation. For an Operational Lifecycle with no local test infrastructure, record that limitation here; otherwise omit this section.]

## Smoke Test

[Conditional section — include when the feature has a runnable surface (CLI, API, pipeline, UI, background service). Omit for library code, refactors, or internal restructuring. Describe: what you will observe, a concrete scenario (input → expected output), and what success looks like. Commands may be approximate — describe the shape rather than guessing flags.]

## Changed Files

[List each file with its change verb (create / modify / delete) and a one-line note on what changes.]
```

## Content Rules

- Functional Requirements use canonical identifier format `FR#N` (e.g., `FR#1`, `FR#2`). Each describes exactly one testable behavior.
- Acceptance Criteria use canonical identifier format `AC#N` (e.g., `AC#1`, `AC#2`). Each must be verifiable by running a local command.
- When `## Operational Lifecycle` applies, the numbered requirements must cover repeated failure, retry bounds/termination, recovery or deliberately terminal behavior, and visible accounting; isolated one-transition tests are insufficient.
- The Approach section should reference actual file paths, class names, and patterns found during investigation.
- No `[NEEDS CLARIFICATION]` markers — if you don't know, ask before writing.
