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

## Acceptance Criteria

- **AC#1** [Measurable, observable outcome — verifiable by running a local command]
- **AC#2** [Each entry tests one outcome; map to FR#N identifiers where relevant]

[Each AC must be verifiable by an executor running commands in the local repo.]

## Approach

[The recommended approach with rationale. Reference specific files, patterns, and existing code. Key architecture decisions go here. This replaces the full Architecture, Implementation Preferences, and Alternatives Considered sections from a full design doc — keep it focused on what matters for execution.]

## Changed Files

[List each file with its change verb (create / modify / delete) and a one-line note on what changes.]
```

## Content Rules

- Functional Requirements use canonical identifier format `FR#N` (e.g., `FR#1`, `FR#2`). Each describes exactly one testable behavior.
- Acceptance Criteria use canonical identifier format `AC#N` (e.g., `AC#1`, `AC#2`). Each must be verifiable by running a local command.
- The Approach section should reference actual file paths, class names, and patterns found during investigation.
- No `[NEEDS CLARIFICATION]` markers — if you don't know, ask before writing.
