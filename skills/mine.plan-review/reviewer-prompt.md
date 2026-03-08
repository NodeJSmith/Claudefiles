# Plan Reviewer Checklist

You are reviewing a caliper implementation plan against a design document.
For each checklist item, output: PASS, WARN (minor issue), or FAIL (blocking issue) followed by a one-line note.

## Checklist

### 1. Dependency sequencing
Does the task order respect dependencies? Could any task fail because a prerequisite isn't done yet?
Look for: tasks that reference files not yet created, tests for code not yet written, config that references modules not yet added.

### 2. Artifact naming
Are file names, variable names, and module names consistent throughout the plan?
Look for: tasks that create `foo.py` but later steps reference `foos.py`; inconsistent class names; renamed entities mid-plan.

### 3. Design alignment
Does every task trace back to the design doc? Are there tasks for things not in the design? Are design goals left unaddressed?
Look for: scope creep (extra tasks), missing implementation of stated design goals, tasks that contradict the Non-goals section.

### 4. Test structure
Are tests specified alongside or immediately after the implementation they verify?
Look for: tests deferred to "a later task" without being explicitly paired; tasks with no verification step; done-when criteria that can't be observed without running tests.

### 5. Task completeness
Does every task have all 5 caliper fields (files, steps, verification, done-when, avoid)?
Look for: missing fields, vague steps ("update the handler"), placeholder file paths ("path/to/file"), non-runnable verification commands.

### 6. Context independence
Could each task be handed to a fresh Claude instance with only the plan and referenced files?
Look for: tasks that assume knowledge from earlier conversation, steps that say "as discussed" or "per the previous task", implicit dependencies not stated in the task.

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
