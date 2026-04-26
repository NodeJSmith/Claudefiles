---
name: mine.gap-close
description: "Use when the user says: 'close gaps in this design', 'fill gaps in the spec', 'lightweight design review', 'gap-close this doc', 'completeness review', or wants to verify a doc has all required content before implementation."
user-invocable: true
---

# mine.gap-close

Completeness review for design docs, briefs, work packages, and general-purpose docs. Finds missing required content (not flawed content), fills gaps conversationally via Edit, and signs off. Not a substitute for `/mine.challenge` (quality of existing content).

## Arguments

$ARGUMENTS — file path, feature directory, short description, or empty (will ask).

## Phase 1: Locate and Classify

Parse $ARGUMENTS. If a file path: read directly. If a directory: look for `design.md`, `brief.md`, or first `.md`. If empty:

```
AskUserQuestion:
  question: "Which artifact should I review?"
  header: "Target"
  options:
    - label: "design.md in current feature"
      description: "Use the design.md in the current or most recent feature directory"
    - label: "I'll type the path"
      description: "Specify a file path or description"
```

Read the artifact. Detect type:
- `**Status:** draft/approved` AND `## Problem` → design doc
- `## Key Decisions` OR `## Scope Boundaries` → brief
- `## Deliverables` OR first heading starts with `# WP` → work package
- None → general-purpose

Load the matching checklist from `${CLAUDE_HOME:-~/.claude}/skills/mine.gap-close/REFERENCE.md`. When type is ambiguous, confirm before surveying.

## Phase 2: Survey

Evaluate each checklist item against the artifact. Mark each **PASS**, **GAP** (severity: Blocker / Should-address / Nice-to-have), or **N/A**. Example: `DD-03 GAP [Blocker] Goals lack measurable success metrics`.

## Phase 3: Triage

Present gap counts by severity and one-line descriptions, then:

```
AskUserQuestion:
  question: "How to work through gaps?"
  header: "Scope"
  options:
    - label: "All gaps"
      description: "Walk through every gap in severity order"
    - label: "Blockers only"
      description: "Skip Should-address and Nice-to-have"
    - label: "Take the list"
      description: "Print gap list and exit — I'll handle manually"
```

## Phase 4: Conversational Loop

Iterate gaps: Blocker → Should-address → Nice-to-have. For each gap:

1. Grep the codebase for patterns relevant to that gap's domain (error handling, naming, structure). Use the most common pattern as option 1, marked "(Recommended)".
2. Ask via AskUserQuestion — one question per call, 2-3 options.
3. Convert the answer using conversion rules in REFERENCE.md, write via Edit. If the answer is vague or partial, write verbatim with `<!-- TODO: review -->`.
4. Confirm with one-line ack.

Every 3-5 gaps, checkpoint via AskUserQuestion (header: "Checkpoint") with options: "Continue", "Pause — stop here", "Skip remaining — jump to sign-off".

## Phase 5: Sign-Off

Re-run the checklist on the updated artifact.

If all Blockers resolved:

```
AskUserQuestion:
  question: "Artifact is complete."
  header: "Sign-off"
  options:
    - label: "Approve"
      description: "Mark ready — update status field if present"
    - label: "Challenge first"
      description: "Invoke /mine.challenge for deeper critique"
    - label: "Save and stop"
      description: "Leave as-is, no status change"
```

If Blockers remain: report count, then AskUserQuestion (header: "Blockers") with options: "Continue — keep filling" or "Save and stop".

On "Approve": update `**Status:**` to `approved` if present. On "Challenge first": invoke `/mine.challenge <artifact-path>`, loop back to sign-off after. On "Save and stop": confirm with "Saved. Resume with `/mine.gap-close <path>` later."
