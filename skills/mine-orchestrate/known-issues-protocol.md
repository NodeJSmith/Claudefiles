# Known Issues Protocol

Use this protocol when orchestration discovers a real issue that should not be fixed during the current run. The goal is to preserve intentional deferrals as durable feature context, not to create a dumping ground for every reviewer note.

## Durable Artifact

Record known issues in the feature directory:

```text
<feature_dir>/known-issues.md
```

This protocol is the canonical source for the artifact name, entry ID format, status field, source labels, and qualifying reasons. Other orchestration files should reference this protocol instead of redefining the schema.

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

Even when an issue otherwise qualifies above, check user impact before recording it as a silent deferral. A known issue is read by a human who chooses to open the file later — an issue with severe, immediate user impact cannot depend on someone remembering to look.

**Disqualified from `deferred(reason)` — classify as `unresolved` instead** when any of these hold:

- User-visible breakage with no explanation surfaced to the user (the app appears hung, broken, or non-functional with no error message, log, or status indicating why).
- Silent data loss or corruption.
- A security or auth exposure.
- The core workflow is blocked entirely, for all users — not an edge case or a degraded-but-usable path.

`unresolved` is not a demand to fix it in this pass — it means an agent cannot be the one to decide this gets silently deferred. What happens next depends on where the trip occurs:

- **Fixer-loop classify-mode pass, WP scope** (`findings-fix-loop.md`, invoked from `SKILL.md` Step 12): the `unresolved` row FAILs the fixer gate, which folds into the Step 14 verdict and the Step 16 gate — `AskUserQuestion` with "Fix review findings" / "Mark as blocked and skip" / "Stop here". This is the required checkpoint; a human decides explicitly, including the option to ship without fixing it now.
- **Fixer-loop classify-mode pass, final scope** (`post-execution-pipeline.md` Step 5): the `unresolved` row FAILs the `final-review` gate. There is no "proceed anyway" option at this gate (see Step 5) — the pipeline halts before the shipping gate until the user addresses it directly in conversation.
- **Direct-suggestion sites that don't go through the fixer loop at all** (`post-execution-pipeline.md` Steps 2, 3, and 4 — impl-review suggestions, cross-file-review suggestions, and clean-code findings): these have no ledger and no existing gate to fall back on, so use the **Severity Escalation** prompt below instead of writing a plain summary note.

This check runs everywhere a finding is about to be written to `known-issues.md` as a plain deferral — not only the classify-mode pass. The qualifying reasons above (`faithful-port`, `out-of-scope`, etc.) still apply normally to findings that don't trip this gate — including faithful-port findings, unless the port bug itself is severe enough to trip it.

## Severity Escalation

For call sites with no existing fixer-loop gate to route through (`post-execution-pipeline.md` Steps 2, 3, and 4), a Severity Gate trip gets asked immediately, in the same turn it's found — not batched into the end-of-run known issues walkthrough, which is exactly the "wrote it to a file and moved on" failure mode this gate exists to prevent:

```
AskUserQuestion:
  question: "This finding is too severe to defer silently: <one-line description>. <which Severity Gate condition it trips>. What next?"
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

A subagent (e.g. the Step 4 clean-code-executor) cannot ask this question itself — it flags the trip distinctly in its output (do not silently record it as a plain deferral) and the orchestrator raises this prompt after reading that output.

**On "Fix now":**
1. Record the dispatch and capture its ID: `cfl dispatch severity-fixer --agent-type general-purpose --model sonnet`
2. Dispatch a `general-purpose` subagent (`model: sonnet`, `cfl_dispatch_id: <dispatch_id>`) scoped to only this one finding — its description, affected files, and the instruction "fix only this; do not expand scope."
3. After it completes: `cfl dispatch end <dispatch_id>`
4. Record a reviewer dispatch (`cfl dispatch severity-review --agent-type code-reviewer --model sonnet`), capture `review_dispatch_id`, and run `code-reviewer` once on the changed files with `cfl_dispatch_id: <review_dispatch_id>`; after it completes: `cfl dispatch end <review_dispatch_id>`. (Single-pass `code-reviewer` only, not the full `findings-fix-loop.md` rigor — this fix targets one already-identified, already-scoped issue rather than an open-ended review, so the cross-file consistency check `integration-reviewer` adds isn't needed.) **FAIL or WARN:** tell the user the fix attempt failed and re-raise this same Severity Escalation prompt rather than silently proceeding — do not loop automatically. **PASS:** re-run the project test suite (`<dir>/test-command.txt`) and, unless it contains the "no lint tools" sentinel, lint (`<dir>/lint-command.txt`). If both pass, the finding is resolved and nothing gets recorded in `known-issues.md` — resume the pipeline step that raised this prompt. If either fails, treat this the same as a code-reviewer FAIL: tell the user the fix attempt introduced a regression and re-raise this same Severity Escalation prompt rather than silently proceeding.

**On "Stop here":** Leave the run active; do not call `cfl run complete`. The pipeline step that raised this prompt does not continue automatically — the user resumes later via `/mine-orchestrate`.

**On "Ship anyway":** record the finding in `known-issues.md` with `Run: <run_id>` (same requirement as every other entry — see Entry Format below) and note in its `Why deferred:` field that the user explicitly accepted the risk after being shown the Severity Gate trip. Only after this choice may the finding be recorded at all; the pipeline step that raised this prompt then continues automatically.

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

`Status:` starts as `open` and moves to one of: `resolved — fixed during known issues walkthrough` (Step 5.6 "Fix now" in `post-execution-pipeline.md`), `filed (#<issue-number>)` (Step 5.6 "File as GitHub issue"), or stays `open` (Step 5.6 "Leave deferred", or no walkthrough decision yet).

Keep entries concise. They should be detailed enough for a later agent to act without reconstructing the orchestration context.

`Run: <run_id>` is the `run_id` field from `cfl run status` (also returned by `cfl run start` / `cfl run advance-phase orchestrate`) — the same run persists across the automatic context-reset/`/clear` cycle described in `SKILL.md`'s "Context reset check", so this field, not conversational memory, is what the Step 5.6 walkthrough uses to tell entries recorded in this orchestration run apart from backlog left over from an earlier run on the same feature. Every writer of a known-issues entry (fixer subagents and the orchestrator's own direct recordings) must read the current `run_id` and include it.

## Gate Rule

Before a task or final review treats a real unfixed issue as acceptable, it must be in one of these states:

- Fixed in code.
- Rejected as invalid with rationale in the relevant review/fix summary.
- Deferred only to a later task that still owns the relevant files.
- Recorded in `<feature_dir>/known-issues.md`.

An intentional deferral recorded in `known-issues.md` does not by itself downgrade a task from PASS to WARN. WARN remains reserved for unresolved execution conditions such as visual uncertainty, regressions, or lint/test issues that still need attention in this run.

## Shipping Summary

Before the shipping gate, `post-execution-pipeline.md` Step 5.5/5.6 reads `<feature_dir>/known-issues.md`, splits `Status: open` entries into "recorded this run" (`Run:` matches the current `run_id`) versus backlog from an earlier run, and walks the user through each this-run entry individually (Fix now / File as GitHub issue / Leave deferred) plus an opt-in rollup for the backlog — see that file for the full walkthrough. The Step 6 shipping prompt then surfaces the post-walkthrough open count and titles so the user can choose whether to ship with whatever follow-ups remain.
