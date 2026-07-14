# Design Document Template

Write the design doc to `<feature_dir>/design.md` using this template:

```markdown
# Design: <Topic>

**Date:** YYYY-MM-DD
**Status:** draft
**Scope-mode:** <expand|hold|reduce>
**Research:** <path to research brief, if one was used — omit if no prior research>

## Problem

[What is broken, missing, or suboptimal — and why it matters now. State the problem from the user's perspective.]

## Goals

[What success looks like. Measurable outcomes.]

[Optional "## Non-Goals" section — only insert this heading and content if the user explicitly named exclusions. Omit entirely if the user stated no non-goals.]

## User Scenarios

[Structured per-actor task flows. For each actor:]

### [Actor name]: [Role]
- **Goal:** [verb phrase]
- **Context:** [when and where]

#### [Scenario name]

1. **[Action — verb phrase]**
   - Sees: [what information must be visible]
   - Decides: [choice they make here, if any]
   - Then: [system response or next trigger]

## Functional Requirements

- **FR#1** [One testable behavior — state what the system must do, not how]
- **FR#2** [Each entry describes exactly one behavior; do not bundle multiple behaviors into a single FR]

## Edge Cases

[Boundary conditions, error states, unusual inputs.]

## Acceptance Criteria

- **AC#1** [Measurable, observable outcome — verifiable by running a local command]
- **AC#2** [Each entry tests one outcome; map to one or more FR#N identifiers where relevant]

[Each AC must be verifiable by an executor running commands in the local repo: tests, linters, grep, scripts, or hitting locally-reachable services. Criteria that require observing CI pipeline status, GitHub Actions output, post-merge behavior, or PR review state are process gates, not acceptance criteria. An executor has no way to observe these, so they get marked CONTESTED and stall the pipeline for manual resolution. Describe them in Dependencies and Assumptions instead.]

## Visual Artifacts

[Optional section — include only when visual references (mockups, screenshots, prototypes) exist for this feature. Omit this section entirely when no visual artifacts are available. When present, list each artifact with its path and what it shows.]

## Key Constraints

[Explicit anti-patterns and prohibited approaches specific to this feature, sourced from discovery. Not general coding best practices — only feature-specific prohibitions that emerged from investigation or user answers. If no feature-specific prohibitions emerged, write: "No feature-specific constraints identified during discovery."]

## Dependencies and Assumptions

[External systems, teams, data sources this depends on.]

## Architecture

[The recommended approach with rationale. Reference specific files, patterns, and abstractions from the research brief. Include data model, interface contracts, and any relevant diagrams in prose form.]

## Implementation Preferences

[Concrete tooling, framework, and convention decisions that constrain how this feature is built. These are choices the implementer would otherwise make by default — and potentially make wrong. Examples: CLI framework (cyclopts vs argparse), logging approach (structlog vs stdlib), serialization format, error handling pattern, specific libraries to use or avoid. Only include decisions explicitly surfaced during discovery; do not speculatively fill this section. If no implementation preferences were identified, state "No specific implementation preferences — follow codebase conventions."]

## Replacement Targets

[Existing code, patterns, or approaches being intentionally replaced by this change. Derived from `Replace` entries in the code leverage table. For each target: the file/pattern being replaced, what replaces it, and whether the old code should be removed outright or migrated incrementally. Implementers should remove or migrate these — not preserve them alongside the new code. If this is purely additive with no code being superseded, state "No existing code is being replaced."]

## Migration

[What happens to existing data? Schema changes, data transformations, state format migrations. Include: what changes, what the migration does, whether it's reversible, and what happens to data written by the old code. Optional section — include only when the feature involves data model changes, schema migrations, or changes to persistent state format (detected during Phase 1.5 or surfaced during discovery). Omit entirely when no data changes are involved.]

## Convention Examples

[Code examples extracted from the codebase during Phase 1.5 reconnaissance. Each example demonstrates a convention that new code for this feature should follow. 3-5 examples, each showing a different convention. Include DO/DON'T pairs only when the wrong approach is non-obvious. Omit this section if Phase 1.5 found no meaningful conventions to extract (greenfield project, no similar code).]

### [Pattern name — e.g., "Service function structure"]

**Source:** `<file_path>`

<fenced code block with language tag — the relevant function/class/block, not the whole file>

## Alternatives Considered

[What else was evaluated and why rejected. At least one alternative.]

## Test Strategy

[For repos with no test infrastructure, replace the entire Test Strategy section (including all subsection headings below) with a single line: "N/A — no test infrastructure in this repo."]

### Existing Tests to Adapt
[Test files that will break or need updating due to this change, with file paths and what specifically needs to change. Sourced from Phase 1.5 test survey. If none, state "No existing tests affected."]

### New Test Coverage
[New behaviors that need tests. Map to Functional Requirements (FR#N) where possible. Identify which testing layer (unit, integration, E2E) each behavior needs.]

### Tests to Remove
[Tests for functionality being removed or replaced. Reference Replacement Targets where applicable. If none, state "No tests to remove."]

## Documentation Updates

[Specific documentation artifacts that need updating alongside this change. Consider: README, CHANGELOG, API docs, CLI help text, configuration docs, rules files, capabilities/trigger-phrase files. List each artifact with the specific change needed. If none, state "No documentation updates required."]

## Impact

### Changed Files
[List each file with its change verb (create / modify / delete) and a one-line note on what changes. Shared or cross-cutting files first — these carry higher risk. `mine-plan` reads this inventory to seed per-task target-file lists; concrete path + verb pairs make that slicing reliable (mine-plan additionally records `read`-only references it finds during planning). This section is optional input to the plan — its absence does not block planning.]

### Behavioral Invariants
[Existing behaviors that must NOT change — downstream consumers, API contracts, CLI flags, integration points that must continue working as-is. These inform which existing tests must keep passing. If none, state "No behavioral invariants identified."]

### Blast Radius
[Who/what is affected beyond the immediate change. Other services, consumers, or workflows that depend on the changed code.]

## Open Questions

[Unresolved items that need answers before or during implementation. Must be empty before plan approval.]
```

## Content Rules

- Requirements sections (Problem, Goals, User Scenarios, Functional Requirements, Edge Cases, Acceptance Criteria) describe observable behaviors — what the system does, not how it's built. Naming the domain is fine ("pytest", "webhook", "CLI flag"); dictating implementation steps is not ("use subprocess.Popen", "add a column to the X table")
- Architecture, Implementation Preferences, Replacement Targets, Migration, Alternatives, Test Strategy, Documentation Updates, and Impact contain implementation details
- Architecture must reference existing code from the **Existing code leverage** table. For any sub-problem marked `Full — reuse as-is`, confirm reuse or justify diverging. For `Partial`, explain what was extended.

## Scope Mode Effects

| Section | Expand | Hold | Reduce |
|---|---|---|---|
| Problem | Include the broader problem, not just the immediate one | State the problem as given | State the acute problem only |
| Goals | Include stretch goals alongside core goals | Core goals only | Minimum viable goals only |
| Architecture | Include platform opportunities, extensibility points | Standard recommendation | Simplest possible approach — documents only what IS being built |
| Non-goals | Frame as "what's phase 2 vs phase 1?" | As-is | Explicitly list cut items with rationale — mine-plan uses Non-goals as exclusions |
| Implementation Preferences | Include extensibility-oriented tooling decisions; note stretch choices | Concrete decisions from discovery only | Only decisions critical to the minimum build |
| Replacement Targets | Items being replaced in this change — note candidates for future replacement in Architecture | Only items being replaced in this change | Only items being replaced — defer others to follow-up |
| Test Strategy | Include stretch coverage goals; test adjacent behaviors | Cover all FRs; adapt all affected tests | Minimum tests for core FRs; note deferred coverage |
| Alternatives | Include the ambitious alternative even if not chosen | Standard alternatives | Include "do nothing" and "manual workaround" as alternatives |

## Section Rules

- Every requirement must be testable and unambiguous
- No `[NEEDS CLARIFICATION]` markers — if you don't know, ask before writing
- Functional Requirements use canonical identifier format `FR#N` where N is a positive integer (e.g., `FR#1`, `FR#2`). Identifiers must be unique within the document. Each FR describes exactly one testable behavior — do not bundle multiple behaviors into a single entry
- Acceptance Criteria use canonical identifier format `AC#N` where N is a positive integer (e.g., `AC#1`, `AC#2`). Identifiers must be unique within the document
- Acceptance Criteria must be verifiable by running a local command (test, lint, grep, script, or hitting a locally-reachable service). Criteria that require CI pipeline status, GitHub Actions job output, post-merge observation, or PR review state are not ACs. Move them to Dependencies and Assumptions
- Visual Artifacts section is optional — include it only when visual references exist; omit the section entirely otherwise
- Key Constraints section is required — include it even if no feature-specific prohibitions emerged (mark it empty with a note rather than omitting)

## Count Handling

**Counts are not instructions.** Approximate counts are fine in Problem/Goals for framing ("a flat class with ~90 fields"). But in Architecture, Impact, and Test Strategy, never use a count as an implementation instruction — "extract the 13 fields" breaks when the real count is 20. Instead, reference the code location: "extract all fields from `config.py:31-55`" and let the implementer see the real count. File lists matter; file counts don't.

Populate each section from the research brief, discovery answers, and codebase reconnaissance. Be specific — reference actual file paths, class names, and patterns found during investigation.
