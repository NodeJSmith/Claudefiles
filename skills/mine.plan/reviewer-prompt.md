# Plan Reviewer Checklist

You are reviewing a caliper implementation plan against a design document.
For each checklist item, output: PASS, WARN (minor issue), or FAIL (blocking issue) followed by a one-line note.

## Checklist

### 1. FR/AC coverage completeness
Does every FR#N and AC#N in the design doc appear in at least one task's `implements` field AND have a corresponding Verify criterion in that task?
Look for: identifiers present in the design doc but absent from all `implements` fields; identifiers listed in `implements` with no matching `- [ ] FR#N:` or `- [ ] AC#N:` item in the Verify section.

### 2. Contradiction detection
Do any task Prompt or Focus sections contradict the design doc's requirements?
Look for: tasks that describe behavior incompatible with the FR/AC they claim to implement; tasks that use different data types, return codes, fonts, or structures than specified in the design; tasks that say "skip X" when the design requires X.

### 3. Dependency sequencing
Does the task order respect dependencies? Could any task fail because a prerequisite isn't done yet?
Look for: tasks that reference files not yet created by earlier tasks; tasks that implement against interfaces defined in a task with a higher ID; `depends_on` fields that are empty when they should name a prerequisite task.

### 4. Context file completeness
Does `context.md` have all five required sections, each with non-empty content?
Required sections: `## Problem & Motivation`, `## Visual Artifacts`, `## Key Decisions`, `## Constraints & Anti-Patterns`, `## Design Doc References`.
Look for: missing section headings; sections that contain only a placeholder or the heading itself; Key Decisions that don't match the design doc's Architecture section.

### 5. Verify section quality
Are Verify criteria concrete and binary? Can each item be verified without reading the code?
Look for: vague items like "the feature works", "tests pass", "renders correctly"; items that describe intent rather than observable outcome; Verify items that reference FR/AC identifiers not in the task's `implements` field.

### 6. Summary accuracy
Does each task's Summary accurately describe what the task builds — consistent with its Prompt and the design doc?
Look for: summaries that describe a different feature than the Prompt; summaries that overstate or understate scope; summaries that omit a major component the Prompt will build; interpretive drift between Summary and the FRs listed in `implements`.

### 7. Scope containment
Do any tasks implement things not in the design doc or explicitly listed as non-goals?
Look for: tasks that add features, endpoints, or components not traceable to any FR or AC; scope creep disguised as "nice to have" additions; tasks implementing items from the Non-goals section.
Note: tasks may include Focus items from the Phase 2 gap check that address unlisted reverse dependencies — these are expected and not scope violations.

### 8. Prompt self-containment
Could each task's Prompt be handed to a fresh executor subagent with only context.md and this task file?
Look for: prompts that say "as discussed", "per the previous task", or "you know what to do"; prompts that omit the file paths to touch; prompts that assume context from the planner's session; references to design doc sections without naming which section.

### 9. Visual artifact coverage
If the design doc references visual artifacts (mockups, screenshots, linked images), do the relevant tasks reference those artifacts in their Prompt or Focus sections AND have visual verification criteria in their Verify sections?
Look for: tasks that implement UI described by a mockup but never reference the mockup path; tasks with UI changes but no visual Verify criterion; Verify sections that say "looks correct" rather than naming specific visual elements.

### 10. Identifier format compliance
Do all FR#N and AC#N identifiers in task files match the format `^FR#\d+$` and `^AC#\d+$` respectively?
Look for: identifiers using dashes (FR-1), underscores (FR_1), spelled-out words (Requirement 1), or wrong prefixes; `implements` fields containing non-conforming identifiers; Verify items with malformed identifier prefixes.

## Output format

For each item: `N. <name>: PASS|WARN|FAIL — <one-line note>`

Then:

```
## Verdict: APPROVE | REQUEST_REVISIONS | ABANDON

### Summary
[2-3 sentences]

### Blocking issues (if any)
- [Issue 1]
- [Issue 2]

### Suggestions (non-blocking)
- [Suggestion 1]
```

**Verdict rules**:
- `APPROVE` — zero FAIL items. WARN items may exist.
- `REQUEST_REVISIONS` — one or more FAIL items that can be fixed by editing task files.
- `ABANDON` — fundamental mismatch between the design doc and the plan that requires restarting from design.
