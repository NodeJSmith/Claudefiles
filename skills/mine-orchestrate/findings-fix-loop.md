# Findings Fix Loop (Step 12)

**Precondition:** This loop runs when at least one of the Step 8 canonical verdict lines for the code reviewer or integration reviewer has a verdict of WARN or FAIL. A PASS verdict does not trigger the loop regardless of its findings count. The verdict is the reviewer's categorical judgment; the count is metadata. Triggering on count previously caused non-convergence: each re-review found different informational observations, producing a non-zero count on a PASS that burned fixer passes without progress. Treat verdict as authoritative, count as informational. Spec and visual findings do not trigger this loop. A spec WARN routes to the Step 10 WARN loop, a spec FAIL routes to Step 16, and visual findings feed Step 14 directly.

**Core principle — no cross-agent finding-ID matching:** The defer-vs-unresolved classification that feeds the gate must happen inside a fixer subagent that read the latest review. The orchestrator never reconstructs deferred-vs-unresolved from counts, IDs, or cross-pass comparison. Detection stays with the independent code and integration reviewers; classification stays in one fixer context that has the review in front of it. This mirrors today's orchestrator-as-fixer behavior and is the invariant that keeps the gate faithful across the dispatched-fixer split.

**Iteration budget:** The initial Step 8 review counts as iteration 1. At most **2 code-changing fixer passes** follow (3 review iterations total, matching today's limit). The loop exits in one of two ways:

- **Early exit** — a re-review after a fixer pass returns a PASS verdict on both reviewers. A PASS with informational findings is clean, regardless of findings count.
- **Budget exhausted** — both fixer passes ran and the latest re-review still has a WARN or FAIL verdict on either reviewer; a single **classify-mode** fixer pass then runs as a terminal, non-mutating dispatch to produce the final ledger. It applies no fixes and does **not** count against the 2-pass budget.

Each fixer dispatch is a single pass — do not loop inside the fixer subagent itself.

## Fixer Subagent

For each pass (normal or classify-mode), dispatch a `general-purpose` subagent with `model: sonnet`.

### Inputs

Include in the fixer's prompt:
- Path to `<dir>/<task_id>/code-review.md`
- Path to `<dir>/<task_id>/integration-review.md`
- Path to the design doc for this task
- The changed-files list (file paths, one per line — pass the list inline, not as a file path)

Pass review and design doc as **paths** so the fixer reads them in its own ephemeral context. Do not pass file contents into the orchestrator's context.

### Fix/defer policy (normal pass)

The fixer prompt must include:

> Read `${CLAUDE_CONFIG_DIR:-~/.claude}/references/common/receiving-code-review.md` and apply its posture — verify each finding against the actual code before acting (verify-before-fix), and do not add abstractions no caller needs (YAGNI). Do not re-run the task, re-capture screenshots, or expand scope beyond findings in the review files provided.
>
> **For each finding (CRITICAL, HIGH, MEDIUM, LOW — all severities):**
> - **Auto-fix** when the correct solution is unambiguous (clear bugs, missing type annotations, style violations, naming drift, orphaned code, undefined references, simple security issues)
> - **Defer** when the fix requires architectural judgment or business context

### Classify-mode pass (budget exhausted, findings remain)

When running the terminal classify-mode pass, add to the fixer prompt:

> **This is a classify-only pass. Apply no code changes.** Read the review files and classify every finding in the ledger only.

### The ledger

After processing all findings, the fixer writes `<dir>/<task_id>/fix-ledger.md`, **overwriting any previous ledger**. The ledger has one row per finding the current review reports:

```
[SEVERITY] file:line — fixed: <what was done>
[SEVERITY] file:line — deferred(<reason>)
[SEVERITY] file:line — unresolved: <brief description>
```

Rows are descriptive. They are not keyed by a cross-agent finding ID and are never matched across passes or agents. The orchestrator reads only the row classifications (`fixed`, `deferred`, `unresolved`) — it never reads a review body and never compares ledger rows against prior-pass ledgers.

The fixer ends its response with a one-line summary: `fixed: N, deferred: M, unresolved: K`

## Loop

**Iteration 1** is the Step 8 review. The canonical verdict lines and findings counts are already extracted. Proceed to iteration 2.

**Iteration 2 — Fixer pass 1:**

1. Record the fixer dispatch and capture its ID:
   ```bash
   cfl dispatch fixer <task_id> --agent-type general-purpose --model sonnet
   ```
   Parse `dispatch_id` from the JSON output. Dispatch the fixer subagent (normal pass) with the Step 8 review file paths and the current changed-files list. After the fixer completes:
   ```bash
   cfl dispatch end <dispatch_id>
   ```
2. The fixer reads the reviews in its own context, applies fixes, and writes `<dir>/<task_id>/fix-ledger.md`.
3. Re-capture changed files (the fixer may have touched additional files):
   ```bash
   git diff --name-only HEAD
   git ls-files --others --exclude-standard
   ```
   Union the result with the in-context changed-files list (deduplicated). Update `<dir>/<task_id>/changed-files.txt`.
4. Record dispatches for both re-reviewers and capture their IDs:
   ```bash
   cfl dispatch code-reviewer <task_id> --agent-type code-reviewer --model sonnet
   cfl dispatch integration-reviewer <task_id> --agent-type integration-reviewer --model sonnet
   ```
   Re-dispatch the code reviewer and integration reviewer **in parallel** with the `CONCISE-RETURN-MODE` sentinel and output file paths — using the same agent types as Step 8 (`subagent_type: "code-reviewer"` and `subagent_type: "integration-reviewer"`), not `general-purpose`:
   - Each dispatch prompt must contain the **exact literal token** `CONCISE-RETURN-MODE` (verbatim) **and** an output file path — both conditions required to activate concise return (see `verdict-line-format.md`)
   - Output paths: `<dir>/<task_id>/code-review.md` and `<dir>/<task_id>/integration-review.md` (overwrite)
   - Pass the refreshed changed-files list in each dispatch
   After both reviewers complete:
   ```bash
   cfl dispatch end <code_reviewer_dispatch_id>
   cfl dispatch end <integration_reviewer_dispatch_id>
   ```
5. Extract the canonical verdict lines from the freshened review files (last line matching `^\*\*Verdict:\*\*`, same pattern as Step 8).
6. **If both reviewers return a PASS verdict → early exit. Skip to the Gate section (terminal state A).** A PASS with informational findings counts as clean. Do not continue the loop because of a non-zero findings count on a PASS verdict.

**Iteration 3 — Fixer pass 2 (if either reviewer returned WARN or FAIL after iteration 2):**

1. Record the fixer dispatch (`cfl dispatch fixer <task_id> --agent-type general-purpose --model sonnet`), capture `dispatch_id`. Dispatch the fixer subagent (normal pass) with the freshened review file paths from the iteration 2 re-review and the updated changed-files list. After completion: `cfl dispatch end <dispatch_id>`.
2. The fixer writes `<dir>/<task_id>/fix-ledger.md` (overwrites the previous ledger).
3. Re-capture changed files (same as above). Update `<dir>/<task_id>/changed-files.txt`.
4. Record dispatches for both re-reviewers (`cfl dispatch code-reviewer/integration-reviewer <task_id>`), capture IDs. Re-dispatch in parallel (same concise dispatch as iteration 2 step 4). After completion: `cfl dispatch end` for each.
5. Extract canonical verdict lines.
6. **If both reviewers return a PASS verdict → early exit. Skip to the Gate section (terminal state A).** A PASS with informational findings counts as clean.

**Budget exhausted — classify-mode terminal pass:**

If the iteration 3 re-review still has a WARN or FAIL verdict on either reviewer:

1. Record the classify-mode fixer dispatch (`cfl dispatch fixer <task_id> --agent-type general-purpose --model sonnet`), capture `dispatch_id`. Dispatch the fixer subagent in **classify-mode** with the iteration 3 re-review file paths and the updated changed-files list. After completion: `cfl dispatch end <dispatch_id>`.
2. The fixer reads the latest reviews, classifies every remaining finding as `fixed`, `deferred(reason)`, or `unresolved`, and writes `<dir>/<task_id>/fix-ledger.md` (overwrites). **No code changes.**
3. Do not re-dispatch reviewers after the classify-mode pass. The terminal ledger now reflects the latest review's findings. Proceed to the Gate section (terminal state B).

## Gate

The loop reaches the gate in one of two terminal states.

**Terminal state A — clean re-review (early exit).** A re-review after a fixer pass returned a PASS verdict on both reviewers. The independent reviewers are authoritative for detection, so the **fixer gate result is PASS**. Informational findings attached to a PASS verdict do not affect the gate. A PASS means the reviewer judged the code acceptable. Read the latest `<dir>/<task_id>/fix-ledger.md` only to count the `fixed` rows for the `(N auto-fixed)` note and to carry forward any `deferred(reason)` rows for Step 14/15. A stale `unresolved` row left in a ledger written *before* the clean re-review does **not** FAIL the task — the independent re-review supersedes it.

**Terminal state B — budget exhausted (classify-mode ledger).** Both fixer passes ran and the latest re-review still returned a WARN or FAIL verdict on either reviewer, so the classify-mode pass wrote the terminal ledger against that latest review. Read the terminal ledger:

- **Any `unresolved` row → the fixer gate result is FAIL.**
- **No `unresolved` rows (only `fixed` and/or `deferred`, or an empty ledger) → the fixer gate result is PASS.** Count the `fixed` rows; carry a `(N auto-fixed)` note forward for Step 14/15.

In both states the orchestrator reads only the ledger (for counts and classification) and the canonical verdict lines — never a review report body, and it never matches findings across agents. The ledger is the sole input for the FAIL determination. **AC#6 holds:** every finding the latest review reported is recorded in the ledger as `fixed`, `deferred(reason)`, or (in state B) `unresolved` — none are silently skipped.

After the gate evaluation, the changed-files list in `<dir>/<task_id>/changed-files.txt` is current from the last loop re-capture. This is the list used by Step 17a (commit). The classify-mode terminal pass makes no code changes, so no additional re-capture is needed after it.

## Event Logging

After the loop completes (gate decided), emit a fix event with the counts from the terminal ledger (or from the fixer's one-line summary return). Iteration count = number of review passes run (2 after one fixer cycle, 3 after two fixer cycles):

```bash
cfl event task.fixed <task_id> --data '{"fixed": <N>, "deferred": <M>, "unresolved": <K>, "iteration": <iteration count>}'
```

Return the **fixer gate result** (PASS or FAIL, plus the `(N auto-fixed)` count or the `unresolved` reasons) to Step 12. The orchestrator continues to Step 13 regardless and folds this result into the single Step 14 verdict assembly — this loop does **not** route to Step 16 itself. The `(N auto-fixed)` note surfaces in Step 15; a FAIL fixer gate result becomes a Step 14 FAIL, which Step 16 then gates.
