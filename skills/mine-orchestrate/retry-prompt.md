<!-- SYNC: references/common/receiving-code-review.md — this isolated retry prompt's
     verify-before-fix, YAGNI, and push-back guidance must remain compatible with the canonical
     protocol. Update both when those shared rules change. -->

# Retry Instructions

You are retrying after review feedback. First verify the feedback against the current code; then fix only valid, in-scope gaps.

## Finding Disposition

Read every supplied reviewer file in full before editing. For each finding, read the cited code,
confirm the issue and scope, then implement or push back with evidence. Prioritize unclear or
critical findings, then localized changes before cross-cutting ones. Fix defects, not every suggestion.

## Scope Limits

Do not re-implement passing work, expand scope, or introduce new patterns, dependencies, or
abstractions. For a proposed abstraction, search for callers across the repository first; without
an existing caller, record: `YAGNI — no existing callers for suggested abstraction; not implementing.`
If a blocker is architectural or dependency-related, write `BLOCKED: <reason>` and stop.

When a finding is incorrect, note it clearly in your output:

```
Finding: [reviewer's finding at file:line]
My assessment: [why I disagree — cite the specific code that contradicts the finding]
Action: no change / [alternative approach]
```

Do not be deferential: explain plainly when a suggestion is wrong, unsafe, or unnecessary.

---

**Template** (populated by the orchestrator):

```markdown
## Previous review feedback

### Attempt N — <WARN|FAIL>

**Findings files to read:**
- <label>: <file path>
  (one line per file; add only files that are present)
   Known labels: "Spec reviewer", "Code reviewer", "Integration reviewer", "Visual reviewer",
  "Test gate", "Impl-review", "Challenge critics (filtered)" (challenge findings per findings-protocol.md)

Read each file in full before proceeding.
```

## Output Schema

`implementer-prompt.md` owns the executor result schema. Use that schema; this file supplies only
retry posture, finding disposition, scope limits, and the populated feedback template below.
