# Plan Reviewer Checklist

You are reviewing a caliper implementation plan against a design document.
For each checklist item, output: PASS, WARN (minor issue), or FAIL (blocking issue) followed by a one-line note.

**WP format note**: WPs no longer carry a `plan_section` frontmatter field. Verify design and spec coverage semantically — read WP Subtasks and Objectives against design.md and spec.md sections, do not attempt to match a metadata field.

## Checklist

### 1. Dependency sequencing
Does the task order respect dependencies? Could any task fail because a prerequisite isn't done yet?
Look for: tasks that reference files not yet created, tests for code not yet written, config that references modules not yet added.

### 2. Artifact naming
Are file names, variable names, and module names consistent throughout the plan?
Look for: tasks that create `foo.py` but later steps reference `foos.py`; inconsistent class names; renamed entities mid-plan.

### 3. Forward traceability
Does every task trace back to a section of the design doc?
Look for: tasks with no clear design origin, tasks that appear to be invented by the planner rather than derived from the design. (For reverse coverage — design → task — see items 7-8. For scope containment and non-goal violations, see item 9.)

### 4. Test structure
Are tests specified alongside or immediately after the implementation they verify?
Look for: tests deferred to "a later task" without being explicitly paired; tasks with no verification step; done-when criteria that can't be observed without running tests.

### 5. Task completeness
Does every WP have all required sections: Objectives & Success Criteria, Subtasks, Test Strategy, and Review Guidance?
Look for: missing sections, vague subtasks ("update the handler"), placeholder file paths ("path/to/file"), Objectives that aren't observable without reading code, Test Strategy that omits test function names or defers unit tests to a later WP without justification.

### 6. Context independence
Could each task be handed to a fresh Claude instance with only the plan and referenced files?
Look for: tasks that assume knowledge from earlier conversation, steps that say "as discussed" or "per the previous task", implicit dependencies not stated in the task.

### 7. Spec coverage
Does every functional requirement in spec.md map to at least one WP?
Look for: requirements with no corresponding task, acceptance criteria with no verification step in any WP.

### 8. Design coverage
Does every architecture section in design.md have corresponding WPs?
Look for: design sections (API contracts, data models, integrations) with no WP that implements them, design decisions referenced but never acted on.
Note: WPs no longer carry a `plan_section` frontmatter field — verify design coverage semantically by reading WP Subtasks and Objectives against design.md sections, not by matching a metadata field.

### 9. Scope containment
Do any WPs implement things not in the design or explicitly listed as non-goals?
Look for: WPs that add features, endpoints, or components not traceable to the design doc; scope creep disguised as "nice to have" additions.

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
