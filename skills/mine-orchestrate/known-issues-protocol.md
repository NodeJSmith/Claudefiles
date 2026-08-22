# Known Issues Protocol

Use this when orchestration confirms a real issue and intentionally leaves it unfixed in the current run.

## Durable Artifact

Record known issues in the feature directory:

```text
<feature_dir>/known-issues.md
```

This file is the canonical source for the artifact name, entry ID format, status field, source labels, qualifying reasons, Severity Gate, and entry schema.

Create the file on first use. Use this header:

```md
# Known Issues

Durable issues discovered during orchestration that were intentionally not fixed in this run.
```

## What Qualifies

Record an issue only when all are true:

- The issue is real after verify-before-fix review.
- The issue should not be fixed during this orchestration run.
- The reason for not fixing it is durable context someone will need later.
- There is a plausible follow-up action or decision.
Common qualifying reasons:

- `faithful-port`: fixing it would make the port diverge from the source behavior.
- `out-of-scope`: fixing it would expand beyond the approved task/design scope.
- `behavior-change`: fixing it could change externally visible behavior.
- `needs-decision`: fixing it requires product, architecture, or business context.
- `blocked`: fixing it depends on an external dependency, upstream change, or migration.
Do **not** record:

- Findings rejected as invalid after checking the code.
- Findings that were fixed in the run.
- Temporary later-task handoffs already covered by an unexecuted task.
- Generic improvements with no concrete follow-up.
- Infrastructure flakes with no product or implementation consequence.

## Severity Gate

Before recording a silent deferral, check user impact.

**Disqualified from `deferred(reason)` — classify as `unresolved` instead** when any of these hold:

- User-visible breakage with no explanation surfaced to the user (the app appears hung, broken, or non-functional with no user-visible error message or status indicating why — an internal log the user never sees does not count as an explanation).
- Silent data loss or corruption.
- A security or auth exposure.
- The core workflow is blocked entirely, for all users — not an edge case or a degraded-but-usable path.

`unresolved` means an agent cannot silently defer the issue. Route it based on the call site:

- **WP-scope fixer-loop classify pass** (`findings-fix-loop.md`, invoked from `SKILL.md` Step 12): an `unresolved` row FAILs the fixer gate and flows into Step 14 and Step 16, where the user chooses `Try again`, `Mark as blocked and skip`, or `Stop here`.
- **Final-scope fixer-loop classify pass** (`post-execution-pipeline.md` Step 5): an `unresolved` row FAILs the `final-review` gate. There is no proceed-anyway path here.
- **Direct-suggestion sites outside the fixer loop** (`post-execution-pipeline.md` Steps 2, 3, and 4): raise the Severity Escalation prompt below instead of writing a plain deferral.
Run this check everywhere a finding is about to be written as a plain deferral.

## Severity Escalation

For call sites with no fixer-loop gate (`post-execution-pipeline.md` Steps 2, 3, and 4), ask
immediately. This is a major gate (known issues walkthrough, see `interaction.md`) — run
`context-pct` and prepend the result to the question:

```
AskUserQuestion:
  question: "[Context: N%] This finding is too severe to defer silently: <one-line description>. <which Severity Gate condition it trips>. What next?"
  header: "Severe issue"
  multiSelect: false
  options:
    - label: "Fix now"
      description: "Dispatch a fixer for just this issue before continuing the pipeline"
    - label: "Stop here"
      description: "Pause the run; I'll handle this myself"
    - label: "Ship anyway"
      description: "I understand the risk — record it as a known issue and continue (this is now an explicit human decision, not a silent deferral)"
```

A subagent cannot ask this question itself. It must flag the trip distinctly in its output, and the orchestrator raises the prompt.

**On "Fix now":**
1. Record the dispatch and capture its ID: `cfl dispatch severity-fixer --agent-type standard-worker`
2. Dispatch a `standard-worker` subagent (`cfl_dispatch_id: <dispatch_id>`) scoped to only this finding, its description, affected files, and the instruction `fix only this; do not expand scope.`
3. After it completes: `cfl dispatch end <dispatch_id>`
4. Record a reviewer dispatch (`cfl dispatch severity-review --agent-type code-reviewer`), capture `review_dispatch_id`, and run `code-reviewer` once on the changed files with `cfl_dispatch_id: <review_dispatch_id>`; after it completes: `cfl dispatch end <review_dispatch_id>`. **FAIL or WARN:** tell the user the fix attempt failed and re-raise this same prompt; do not loop automatically. **PASS:** re-run the project test suite (`<dir>/test-command.txt`, skip and treat as passing if it contains `no test suite`) and lint (`<dir>/lint-command.txt`, skip and treat as passing if it contains `no lint tools`). If both pass or are skipped, the finding is resolved, nothing is recorded in `known-issues.md`, and the pipeline resumes at the step that raised this prompt. That call site owns any broader gate rerun required after the change. If either targeted check fails, treat it like a code-reviewer FAIL and re-raise this prompt.
**On "Stop here":** Leave the run active; do not call `cfl run complete`.
**On "Ship anyway":** record the finding in `known-issues.md` with `Run: <run_id>` and note in `Why deferred:` that the user explicitly accepted the risk after seeing the Severity Gate trip. Only after this choice may the finding be recorded.

## Entry Format

Append entries in this format. Use the next numeric ID already present in the file (`KI-001`, `KI-002`, ...). If no entries exist, start at `KI-001`.

```md
## KI-001: <short title>

Status: open
Run: <run_id>
Source: <task_id | impl-review | cross-file-review | clean-code | final-review | other>
Reason not fixed now: <faithful-port | out-of-scope | behavior-change | needs-decision | blocked>
Observed in: <task_id and/or commit sha if available>
Affected files:
- <path>

Issue:
<what is wrong>

Why deferred:
<why fixing it now would be incorrect, risky, or out of scope>

Recommended follow-up:
<what should happen later>

Acceptance criteria:
- <how to know the follow-up resolved it>
```

`Status:` starts as `open` and moves to one of: `resolved — fixed during known issues walkthrough`, `filed (<issue-key>)`, or stays `open`.
Keep entries concise but actionable.
`Run: <run_id>` comes from `cfl run status`. Every known-issues writer must read the current `run_id` and include it so Step 5.6 can distinguish entries recorded in this run from backlog left by earlier runs on the same feature.

## Gate Rule

Before a task or final review treats a real unfixed issue as acceptable, it must be in one of these states:

- Fixed in code.
- Rejected as invalid with rationale in the relevant review/fix summary; the fixer-loop ledger's formal `rejected(reason)` row (`findings-fix-loop.md`) is this state.
- Deferred only to a later task that still owns the relevant files.
- Recorded in `<feature_dir>/known-issues.md`.

An intentional deferral recorded in `known-issues.md` does not by itself downgrade a task from PASS to WARN.

## Shipping Summary

Before the shipping gate, `post-execution-pipeline.md` Step 5.5/5.6 reads `<feature_dir>/known-issues.md`, splits `Status: open` entries into this-run vs backlog using `Run:`, walks each this-run entry individually, and then surfaces the remaining open count and titles at the shipping gate.
