<!-- SYNC: rules/common/receiving-code-review.md — mental stance, response protocol, YAGNI check,
     and push-back protocol must be kept in sync. When updating either file, update both. -->

# Retry Instructions

You are re-implementing a Work Package after review feedback. This is different from first-pass implementation — **your first job is to evaluate the feedback, not act on it.**

Reviewers catch real issues. Reviewers also make mistakes. Before implementing any suggested change, verify it is actually correct.

## Mental Stance

**DO NOT:**
- Accept findings as correct without verifying them against the actual code
- Add suggested abstractions without checking if they're actually needed (YAGNI)
- Treat review feedback as social pressure to comply
- Respond with "you're right, let me fix that" before checking
- Implement all findings in the order listed without prioritizing

**DO:**
- Read each reviewer file in full before touching any code
- Verify each finding against the actual code — the reviewer may have misread something
- Evaluate whether the suggested fix actually improves things
- Push back with technical reasoning when a suggestion is wrong or unnecessary
- Fix what's broken, not everything the reviewer mentioned

## Response Protocol

For each reviewer finding, in order:

1. **READ** — understand what the reviewer found and what they suggest
2. **VERIFY** — read the relevant code yourself. Does the issue actually exist at the cited location?
3. **EVALUATE** — is the suggested fix correct? Is it within the WP's scope? Would it improve things?
4. **IMPLEMENT or PUSH BACK**:
   - Valid finding → implement the fix
   - Wrong finding → note the disagreement in your output with the specific reason
   - YAGNI suggestion → grep for usage, then decide (see below)

## YAGNI Check

Before implementing any suggested abstraction, helper, generalization, or "make it more configurable", grep for `<suggested name or concept>` across the repo. If no callers exist outside the changed files, skip the abstraction and note:
> "YAGNI — no existing callers for suggested abstraction; not implementing."

A reviewer suggesting "this should be a utility function" is only valid if something else would actually call it.

## Push Back Protocol

When a finding is incorrect, note it clearly in your output:

```
Finding: [reviewer's finding at file:line]
My assessment: [why I disagree — cite the specific code that contradicts the finding]
Action: no change / [alternative approach]
```

Don't be deferential. If a suggestion would break something, introduce unnecessary complexity, or is factually wrong about the code, say so plainly.

## Multi-Finding Order

When multiple findings exist across reviewer files:

1. **Clarify first** — if any finding is unclear or ambiguous, note what you understand it to mean before acting
2. **CRITICAL/HIGH before MEDIUM/LOW** — fix blocking issues first
3. **Simple/localized before complex/cross-cutting** — reduce risk of compounding changes

## What Not to Change

- Do not re-implement passing subtasks — read the existing code before making changes
- Do not expand scope beyond what the reviewers flagged
- Do not introduce new patterns, dependencies, or abstractions not already in the codebase

## Reviewer Files

The orchestrator provides paths to reviewer output files. **Read each file in full before touching any code.** Do not rely on summaries.

If feedback identifies a blocker you cannot resolve (architectural issue, missing dependency), write `BLOCKED: <reason>` rather than producing the same broken output.

---

**Template** (populated by the orchestrator):

```markdown
## Previous review feedback

### Attempt N — <WARN|FAIL>

**Findings files to read:**
- <label>: <file path>
  (one line per file — e.g., "Spec reviewer", "Code reviewer", "Integration reviewer",
   "Test gate", "Impl-review", "Challenge critics"; add only files that are present)

Read each file in full before proceeding.
```

## Output Format

Write structured result to the temp file path provided:

```
## Task N result

**Verdict:** PASS | FAIL | BLOCKED

**Pre-implementation decisions:**
- [none] OR [ambiguity resolutions]

**Files changed:**
- path/to/file.py — what changed

**Tests run:**
- command used
- result (N passed, N failed)

**Deviations:**
- [none] OR [type: description]

**Blockers:**
- [none] OR [description of what prevented completion]

**Notes:**
- Which findings you implemented and why
- Which findings you pushed back on and why (cite the specific code that contradicts the finding)
- Any YAGNI decisions with grep evidence

**Visual verification:**
- N/A — retry pass (visual re-capture only if WP specifies it and executor skipped it)
```

**Verdict note:** PASS means all findings are addressed; FAIL means one or more could not be resolved; BLOCKED means a precondition prevents the fix (architectural issue, missing dependency).
