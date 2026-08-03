# Findings Fix Loop

**Scope-agnostic:** This loop runs identically whether the scope is a single task (Step 12) or the whole branch diff (Step 5 of the post-execution pipeline, the "final" pass). The invoker supplies:

- `<scope_id>` — a short label used only in prose/paths below: the task ID (e.g. `T04`) for a task, or `final` for the branch-wide pass
- `<scope_dir>` — where review/ledger files live: `<dir>/<task_id>` for a task, `<dir>/final` for the branch-wide pass
- How to (re)capture the changed-files list: WP scope unions executor + fixer changes incrementally in `<scope_dir>/changed-files.txt`; final scope recomputes fresh each iteration by unioning `git diff --name-only <base_commit> HEAD` (committed per-task work) with `git diff --name-only HEAD` and `git ls-files --others --exclude-standard` (the current fixer pass's edits, which stay uncommitted in the working tree until shipping — same two commands SKILL.md:353-354 uses for WP scope's initial capture)
- Whether the "Task scope boundary" block and the `later-task` deferral bucket apply — **WP scope only**. The final scope has no later task to bound against; every finding is in-scope, and every final-scope deferral must qualify as a known issue in the terminal pass.

Everywhere below, `<task_id>` in a path means `<scope_id>`/`<scope_dir>` generically. **`cfl dispatch`/`cfl event` calls are different** — they take an *optional* `task_id` positional, and its presence vs. absence is what selects `task.*` vs `review.*` event names (cfl's own convention, already used by Step 3's cross-file-reviewer dispatch). WP scope passes the task ID as that positional; final scope **omits the positional entirely** — it is not passed as the literal string `final`. Each `cfl dispatch`/`cfl event` line below is written for both scopes explicitly.

**Precondition:** This loop runs when at least one canonical verdict line from the scope's initial review pass (Step 8 for a task; Step 5's initial code-reviewer/integration-reviewer dispatch for the final pass) has a verdict of WARN or FAIL. A PASS verdict does not trigger the loop regardless of its findings count. The verdict is the reviewer's categorical judgment; the count is metadata. Triggering on count previously caused non-convergence: each re-review found different informational observations, producing a non-zero count on a PASS that burned fixer passes without progress. Treat verdict as authoritative, count as informational. Spec and visual findings do not trigger this loop — WP scope only; the final pass has no spec or visual review. A spec FAIL routes to the Step 10 spec fix loop, and visual findings feed Step 14 directly.

**Core principle — no cross-agent finding-ID matching:** The defer-vs-unresolved classification that feeds the gate must happen inside a fixer subagent that read the latest review. The orchestrator never reconstructs deferred-vs-unresolved from counts, IDs, or cross-pass comparison. Detection stays with the independent code and integration reviewers; classification stays in one fixer context that has the review in front of it. This mirrors today's orchestrator-as-fixer behavior and is the invariant that keeps the gate faithful across the dispatched-fixer split.

**Iteration budget:** The scope's initial review pass (already completed by the invoker before this loop starts) counts as iteration 1. At most **2 code-changing fixer passes** follow (3 review iterations total). The loop exits in one of two ways:

- **Early exit** — a re-review after a fixer pass returns a PASS verdict on both reviewers. A PASS with informational findings is clean, regardless of findings count.
- **Budget exhausted** — both fixer passes ran and the latest re-review still has a WARN or FAIL verdict on either reviewer; a single **classify-mode** fixer pass then runs as a terminal, non-mutating dispatch to produce the final ledger. It applies no fixes and does **not** count against the 2-pass budget.

Each fixer dispatch is a single pass — do not loop inside the fixer subagent itself.

**Telemetry:** Every subagent prompt in this loop (fixers and re-reviewers) must include `cfl_dispatch_id: <dispatch_id>` (the ID from the `cfl dispatch` call that preceded it). This enables automatic token/compaction tracking via a PostToolUse hook.

## Fixer Subagent

For each pass (normal or classify-mode), dispatch a `general-purpose` subagent with `model: sonnet`.

### Inputs

Include in the fixer's prompt:
- `cfl_dispatch_id: <dispatch_id>` (the ID from the preceding `cfl dispatch` call)
- `run_id` — the `run_id` field from `cfl run status`, so any known-issues.md entry the fixer records carries `Run: <run_id>` (see `${CLAUDE_CONFIG_DIR:-~/.claude}/skills/mine-orchestrate/known-issues-protocol.md`). **WP scope:** call `cfl run status` fresh right before assembling these inputs, every time — do not reuse a value read earlier in the task loop. This loop is invoked once per task across potentially many tasks, and a session boundary (resume after context compaction, a manual `/clear`, or a crash/restart) can land between any two of them, so a value carried in conversational memory cannot be trusted; a fresh `cfl run status` call is a cheap DB read that is always correct regardless of reset history. **Final scope:** reuse the `run_id` from Step 1's `cfl run status` call in `post-execution-pipeline.md` — the final pass runs once, with no reset boundary inside it, so re-querying isn't necessary.
- Path to `<scope_dir>/code-review.md`
- Path to `<scope_dir>/integration-review.md`
- Path to the design doc for this feature
- **WP scope:** path to the actual current task spec file discovered in Phase 0 (do not reconstruct it from `task_id`; task filenames may include descriptive suffixes) — so the fixer can verify whether findings contradict a task instruction without spelunking. **Final scope:** paths to all task files under `<feature_dir>/tasks/` instead, since a finding at this point can touch any task's scope.
- Path to the durable known issues file (`<feature_dir>/known-issues.md`) — create only when needed
- Path to `${CLAUDE_CONFIG_DIR:-~/.claude}/skills/mine-orchestrate/known-issues-protocol.md`
- The changed-files list (file paths, one per line — pass the list inline, not as a file path)
- **WP scope only:** the task scope boundary (same block passed to reviewers in Step 8 — remaining task IDs, titles, and target files). Omit entirely for the final scope.

Pass review and design doc as **paths** so the fixer reads them in its own ephemeral context. Do not pass file contents into the orchestrator's context.

### Fix/defer policy (normal pass)

The fixer prompt must include:

> Read `${CLAUDE_CONFIG_DIR:-~/.claude}/references/common/receiving-code-review.md` and apply its posture — verify each finding against the actual code before acting (verify-before-fix), and do not add abstractions no caller needs (YAGNI). Do not re-run the task, re-capture screenshots, or expand scope beyond findings in the review files provided.
>
> **For each finding (CRITICAL, HIGH, MEDIUM, LOW — all severities):**
> - **Auto-fix** when the correct solution is unambiguous (clear bugs, missing type annotations, style violations, naming drift, orphaned code, undefined references, simple security issues)
> - **Defer** when the fix requires architectural judgment or business context
> - **Defer** when the finding targets code/files explicitly listed in a later task's scope boundary — mark as `deferred(later-task: <task_id>)`. **WP scope only** — this category does not exist in the final scope; there is no later task to defer to.
>
> During normal fixer passes, do not write `<feature_dir>/known-issues.md` yet. Mark non-later-task deferrals as `deferred(<reason>; pending terminal classification)` and let the independent re-review decide whether the finding still exists. Durable known-issue recording happens only in the terminal classify-mode pass, against the latest review.

### Classify-mode pass (budget exhausted, findings remain)

When running the terminal classify-mode pass, add to the fixer prompt:

> **This is a classify-only pass. Apply no code changes.** Read the review files and classify every finding in the ledger only.
>
> For every deferred finding that is **not** `deferred(later-task: <task_id>)`, read `${CLAUDE_CONFIG_DIR:-~/.claude}/skills/mine-orchestrate/known-issues-protocol.md` and check the qualifying criteria first. If the finding doesn't qualify — invalid after verify-before-fix, already fixed, or one of the protocol's "Do not record" cases — classify it as `rejected(<one-line reason>)`; this is a complete outcome, not a gate failure. If it qualifies, check the Severity Gate before recording the issue in `<feature_dir>/known-issues.md`: if it trips the gate (user-visible breakage with no explanation, silent data loss, security exposure, or the core workflow blocked entirely), classify it as `unresolved` instead of silently deferring it — the invoker's gate (Step 16 for WP scope, the `final-review` gate for the final scope) is what puts the decision in front of the user, not this pass. Faithful-port bugs are valid known issues when fixing them would break port fidelity, unless the bug is itself severe enough to trip the Severity Gate. When an issue qualifies and clears the Severity Gate, include `Run: <run_id>` (the value passed into this prompt) in the entry.

### The ledger

After processing all findings, the fixer writes `<scope_dir>/fix-ledger.md`, **overwriting any previous ledger**. The ledger has one row per finding the current review reports:

```
[SEVERITY] file:line — fixed: <what was done>
[SEVERITY] file:line — deferred(<reason>; known-issue: KI-###)
[SEVERITY] file:line — deferred(<reason>; pending terminal classification)
[SEVERITY] file:line — deferred(later-task: <task_id>)   # WP scope only
[SEVERITY] file:line — rejected(<reason>)
[SEVERITY] file:line — unresolved: <brief description>
```

Rows are descriptive. They are not keyed by a cross-agent finding ID and are never matched across passes or agents. The orchestrator reads only the row classifications (`fixed`, `deferred`, `rejected`, `unresolved`) and any `known-issue: KI-###` references for the task/final summary — it never reads a review body and never compares ledger rows against prior-pass ledgers.

In terminal state B, non-later-task deferred rows must include a `known-issue: KI-###` reference. A terminal deferred row without either `later-task: <task_id>` (WP scope only) or `known-issue: KI-###` is invalid and counts as `unresolved` for the gate. `pending terminal classification` is allowed only in ledgers from normal fixer passes that are followed by re-review.

The fixer ends its response with a one-line summary: `fixed: N, deferred: M, rejected: R, unresolved: K`

## Loop

**Iteration 1** is the scope's initial review pass, already completed by the invoker before this loop starts. The canonical verdict lines and findings counts are already extracted. Proceed to iteration 2.

**Iteration 2 — Fixer pass 1:**

1. Record the fixer dispatch and capture its ID:
   ```bash
   cfl dispatch fixer <task_id> --agent-type general-purpose --model sonnet   # WP scope
   cfl dispatch fixer --agent-type general-purpose --model sonnet            # final scope — no task_id positional
   ```
   Parse `dispatch_id` from the JSON output. Dispatch the fixer subagent (normal pass) with the iteration-1 review file paths and the current changed-files list. After the fixer completes:
   ```bash
   cfl dispatch end <dispatch_id>
   ```
2. The fixer reads the reviews in its own context, applies fixes, and writes `<scope_dir>/fix-ledger.md`.
3. Re-capture changed files using the scope's defined method (see Scope-agnostic above). Update `<scope_dir>/changed-files.txt` (WP scope) or recompute fresh (final scope).
4. Record dispatches for both re-reviewers and capture their IDs:
   ```bash
   cfl dispatch code-reviewer <task_id> --agent-type code-reviewer --model sonnet             # WP scope
   cfl dispatch integration-reviewer <task_id> --agent-type integration-reviewer --model sonnet  # WP scope
   cfl dispatch code-reviewer --agent-type code-reviewer --model sonnet                        # final scope
   cfl dispatch integration-reviewer --agent-type integration-reviewer --model sonnet           # final scope
   ```
   Re-dispatch the code reviewer and integration reviewer **in parallel** with the `CONCISE-RETURN-MODE` sentinel and output file paths — using the same agent types as the initial pass (`subagent_type: "code-reviewer"` and `subagent_type: "integration-reviewer"`), not `general-purpose`:
   - Each dispatch prompt must contain the **exact literal token** `CONCISE-RETURN-MODE` (verbatim) **and** an output file path — both conditions required to activate concise return (see `verdict-line-format.md`)
   - Each dispatch prompt must include `cfl_dispatch_id: <dispatch_id>` (the ID from its preceding `cfl dispatch` call)
   - Output paths: `<scope_dir>/code-review.md` and `<scope_dir>/integration-review.md` (overwrite)
   - Pass the refreshed changed-files list in each dispatch
   - **WP scope only:** pass the same "Task scope boundary" block used in the initial pass (remaining task IDs, titles, targets)
   After both reviewers complete:
   ```bash
   cfl dispatch end <code_reviewer_dispatch_id>
   cfl dispatch end <integration_reviewer_dispatch_id>
   ```
5. Extract the canonical verdict lines from the freshened review files (last line matching `^\*\*Verdict:\*\*`, same pattern as the initial pass).
6. **If both reviewers return a PASS verdict → early exit. Skip to the Gate section (terminal state A).** A PASS with informational findings counts as clean. Do not continue the loop because of a non-zero findings count on a PASS verdict.

**Iteration 3 — Fixer pass 2 (if either reviewer returned WARN or FAIL after iteration 2):**

1. Record the fixer dispatch (`cfl dispatch fixer <task_id> --agent-type general-purpose --model sonnet` for WP scope, `cfl dispatch fixer --agent-type general-purpose --model sonnet` for final scope), capture `dispatch_id`. Dispatch the fixer subagent (normal pass) with the freshened review file paths from the iteration 2 re-review and the updated changed-files list. After completion: `cfl dispatch end <dispatch_id>`.
2. The fixer writes `<scope_dir>/fix-ledger.md` (overwrites the previous ledger).
3. Re-capture changed files (same method as iteration 2 step 3).
4. Record dispatches for both re-reviewers (`cfl dispatch code-reviewer/integration-reviewer <task_id>` for WP scope, omitting `<task_id>` for final scope), capture IDs. Re-dispatch in parallel (same concise dispatch as iteration 2 step 4, including the scope boundary block for WP scope). After completion: `cfl dispatch end <id>` for each.
5. Extract canonical verdict lines.
6. **If both reviewers return a PASS verdict → early exit. Skip to the Gate section (terminal state A).** A PASS with informational findings counts as clean.

**Budget exhausted — classify-mode terminal pass:**

If the iteration 3 re-review still has a WARN or FAIL verdict on either reviewer:

1. Record the classify-mode fixer dispatch (`cfl dispatch fixer <task_id> --agent-type general-purpose --model sonnet` for WP scope, `cfl dispatch fixer --agent-type general-purpose --model sonnet` for final scope), capture `dispatch_id`. Dispatch the fixer subagent in **classify-mode** with the iteration 3 re-review file paths and the updated changed-files list. After completion: `cfl dispatch end <dispatch_id>`.
2. The fixer reads the latest reviews, classifies every remaining finding as `fixed`, `deferred(reason)` with required known-issue recording for non-later-task deferrals, `rejected(reason)` for findings that don't qualify per `known-issues-protocol.md`, or `unresolved`, and writes `<scope_dir>/fix-ledger.md` (overwrites). **No code changes.** It may edit `<feature_dir>/known-issues.md` because that is documentation of the classification, not a code fix.
3. Do not re-dispatch reviewers after the classify-mode pass. The terminal ledger now reflects the latest review's findings. Proceed to the Gate section (terminal state B).

## Gate

The loop reaches the gate in one of two terminal states.

**Terminal state A — clean re-review (early exit).** A re-review after a fixer pass returned a PASS verdict on both reviewers. The independent reviewers are authoritative for detection, so the **fixer gate result is PASS**. Informational findings attached to a PASS verdict do not affect the gate. A PASS means the reviewer judged the code acceptable. Read the latest `<scope_dir>/fix-ledger.md` only to count the `fixed` rows for the `(N auto-fixed)` note. Do **not** carry forward deferred rows or known-issue IDs from this stale ledger; the clean re-review supersedes the earlier finding set. A stale `unresolved` row left in a ledger written *before* the clean re-review does **not** FAIL the gate.

**Terminal state B — budget exhausted (classify-mode ledger).** Both fixer passes ran and the latest re-review still returned a WARN or FAIL verdict on either reviewer, so the classify-mode pass wrote the terminal ledger against that latest review. Read the terminal ledger:

- **Any `unresolved` row → the fixer gate result is FAIL.**
- **No `unresolved` rows and every non-later-task deferred row includes an artifact-backed `known-issue: KI-###` reference (only `fixed`, `rejected`, and/or valid `deferred`, or an empty ledger) → the fixer gate result is PASS.** For each referenced ID, read `<feature_dir>/known-issues.md` and verify the ID exists as an entry that records the corresponding finding. Missing, malformed, or fabricated IDs do not satisfy the row; classify that row as `unresolved`, making the fixer gate result FAIL. Count the `fixed` rows; carry a `(N auto-fixed)` note forward.

In both states the orchestrator reads only the ledger (for counts, classification, and known-issue IDs) and the canonical verdict lines — never a review report body, and it never matches findings across agents. The ledger is the sole input for the FAIL determination. **AC#6 holds** (originally a WP-scope acceptance criterion in spec 034; the same discipline now applies at the final scope too): every finding the latest review reported is recorded in the ledger as `fixed`, valid `deferred(reason)`, `rejected(reason)`, or (in state B) `unresolved` — none are silently skipped, at any severity, in any scope.

After the gate evaluation, the changed-files list is current from the last loop re-capture (`<scope_dir>/changed-files.txt` for WP scope; the last `git diff` for final scope). WP scope: this is the list used by Step 17a (commit). The classify-mode terminal pass makes no code changes, so no additional re-capture is needed after it.

## Event Logging

After the loop completes (gate decided), emit a fix event with the counts from the terminal ledger (or from the fixer's one-line summary return). For terminal state A, count only fixed rows; deferred/rejected/unresolved rows in the stale ledger do not carry forward. Iteration count = number of review passes run (2 after one fixer cycle, 3 after two fixer cycles):

```bash
cfl event task.fixed <task_id> --data '{"fixed": <N>, "deferred": <M>, "rejected": <R>, "unresolved": <K>, "iteration": <iteration count>}'   # WP scope
cfl event review.fixed --data '{"fixed": <N>, "deferred": <M>, "rejected": <R>, "unresolved": <K>, "iteration": <iteration count>}'             # final scope — no task_id; this is a run-level event
```

Return the **fixer gate result** (PASS or FAIL, plus the `(N auto-fixed)` count or the `unresolved` reasons) to the invoker. WP scope: the orchestrator continues to Step 13 regardless and folds this result into the single Step 14 verdict assembly (the single authoritative gate); this loop does **not** route to Step 16 itself — the `(N auto-fixed)` note surfaces in Step 15, and a FAIL fixer gate result becomes a Step 14 FAIL, which Step 16 then gates. Final scope: the invoker (Step 5) records the fixer gate result directly as the `final-review` gate verdict.
