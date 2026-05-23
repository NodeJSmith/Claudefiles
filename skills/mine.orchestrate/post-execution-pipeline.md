# Post-Execution Review Pipeline (Phase 3)

After all tasks are processed (or user chose "Stop here"), run a review pipeline. Steps 1–6 are automatic (no user prompts unless blocking issues are found). The user is prompted at the impl-review gate (if blocking) or at the final shipping gate.

**All subagents in Phase 3 MUST run in foreground** (never set `run_in_background: true`). Several steps spawn their own parallel child subagents internally, which only works in foreground execution.

## Step 1: Summary (automatic)

Present a verdict table. **Read the checkpoint via `spec-helper checkpoint-read <feature_dir_name> --json`** and build the table from the `verdicts` array:

```
| Task | Title   | Verdict              |
|------|---------|----------------------|
| T01  | ...     | PASS                 |
| T02  | ...     | PASS (3 auto-fixed)  |
| T03  | ...     | WARN (visual skipped)|
...
```

Include the parenthetical notes from the checkpoint `verdicts` array. PASS with a note means findings were raised and resolved. WARN means something genuinely unresolved remains.

## Step 2: Implementation review (automatic, gates on blocking issues)

Invoke `/mine.implementation-review <feature_dir>` automatically. The skill presents findings and returns — no user gate (the orchestrator handles all gate logic).

Read the review output. Extract the verdict (APPROVE, REQUEST_FIXES, or ABANDON) and any suggestions or blocking issues.

**If impl-review returns APPROVE** — note any non-blocking suggestions to surface later. Continue to Step 3 automatically.

**If impl-review returns ABANDON** — hard stop. ABANDON means the implementation is unrecoverable and requires a design rethink, not a code fix. Do not offer "Address fixes":

```
AskUserQuestion:
  question: "Implementation review rated this ABANDON (unrecoverable — design rethink needed): <summary of blocking issues>."
  header: "Impl-review: ABANDON"
  multiSelect: false
  options:
    - label: "Stop and revise the design"
      description: "Return to /mine.define or /mine.plan to update the tasks"
    - label: "Stop here for now"
      description: "Pause execution; resume after the design is updated"
```

**If impl-review returns REQUEST_FIXES** — prompt the user:

```
AskUserQuestion:
  question: "Implementation review found blocking issues: <summary of blocking issues>. What next?"
  header: "Impl-review gate"
  multiSelect: false
  options:
    - label: "Address fixes"
      description: "Dispatch a fresh executor subagent with the findings, then re-run reviewers"
    - label: "Stop here"
      description: "Pause; I'll address findings manually"
```

**On "Address fixes":**
1. Dispatch a fresh `general-purpose` subagent with `model: sonnet` and: the impl-review findings, the relevant file paths, the design doc path (`<feature_dir>/design.md` — instruct the subagent to read it directly), all task files from `<feature_dir>/tasks/` (for per-task constraints and Review Guidance), accumulated spec-reviewer outputs, `implementer-prompt.md` content (as `## Implementer instructions`), `retry-prompt.md` content (as `## Retry instructions`), and `tdd.md` content. Populate the `## Previous review feedback` template with: "Impl-review: <absolute path to impl-review findings file>". Instruct: "Fix only the listed blocking issues. Do not expand scope beyond these findings. Respect the Review Guidance constraints from each task."
2. After the subagent completes, re-run the project test suite (using `<dir>/test-command.txt`). If tests fail: surface the failure prominently in the next gate prompt (which offers "Address fixes" or "Stop here" — there is no "Accept and ship" option at this gate) with a note identifying the test failures.
3. Re-run `code-reviewer` and `integration-reviewer` on the fix diff in parallel (both in a single message)
4. Re-run `/mine.implementation-review <feature_dir>`
5. If it now returns APPROVE, continue to Step 3
6. "Address fixes" remains available across iterations — the user decides when to stop. Starting with the 3rd round, prepend a warning to the gate question: "Multiple rounds have not resolved the blocking issues — consider stopping to investigate the root cause before continuing." Do not remove the option; the user may have context (e.g., knowing the next iteration targets a different layer) that justifies continuing.

**On "Stop here":** Leave the checkpoint in place. The user can resume later. Do not delete the checkpoint.

## Step 3: Cross-file consistency review (automatic)

After impl-review passes, run an `integration-reviewer` subagent on the **full branch diff** (not per-task). This catches cross-file consistency issues that per-task reviews miss because they only see one task's changes at a time.

```bash
git diff --name-only <base_commit> HEAD
```

Use the `base_commit` from the checkpoint read in Step 1.

Launch `Agent(subagent_type: "integration-reviewer")` with all changed files. Add this focus instruction to the prompt:

> In addition to your standard checklist (duplication, convention drift, misplacement, orphaned code, design violations), pay special attention to **cross-file consistency** across the full diff:
> - **Terminology drift**: same concept described with different words across files (e.g., "verb" vs "execution outcome" for the same trigger condition)
> - **Stale cross-references**: section numbers, file paths, or artifact names that point to the wrong target after edits
> - **Format/schema coverage**: tables, enumerations, or format specs that don't cover all variants actually used in other files
> - **Stated principles violated by implementation details**: rules declared in one file but contradicted by logic in another
> - **Hard-coded values that should be parameterized**: artifact names or paths that appear as literals but should vary by context (e.g., iteration suffixes)
> - **Worked examples using invalid contract values**: examples that show values not in the canonical vocabulary

If the integration-reviewer returns BLOCK, surface the blocking issues to the user with an "Address" / "Stop here" gate (same pattern as the impl-review gate). If APPROVE or WARN, note any suggestions and continue to Step 4 (WTF check).

## Step 4: WTF check (automatic, Opus subagent)

After the cross-file consistency review passes, run a full WTF check on the entire branch diff. This catches readability debt, dead code, naming inconsistencies, API ergonomics issues, and other hygiene problems that correctness and integration reviewers don't target.

Launch a single `general-purpose` subagent with `model: opus` and this prompt:

```
You are running a comprehensive code quality review on a completed feature branch.

## Branch diff

Run these commands to get the scope — do NOT use $() command substitution (it silently fails in this environment):

git-branch-base
# Note the printed result (e.g., "origin/main"), then use it in the next command:
git diff <printed-base>...HEAD --name-only

## Task

Run /mine.wtf on this branch. This dispatches three parallel reviewers (code-reviewer, integration-reviewer, wtf-reviewer) and consolidates their findings.

After the findings are reported:

1. Read every finding carefully
2. Fix ALL findings that have unambiguous solutions — dead code removal, naming improvements, missing type annotations, redundant parameters, magic numbers, API ergonomics improvements, etc.
3. For findings that require architectural judgment or could change behavior in subtle ways, leave them unfixed and note them in your summary
4. After fixing, run the project's test suite to verify no regressions: <contents of <dir>/test-command.txt>
5. If tests pass, run lint using <contents of <dir>/lint-command.txt>. If that file contains the sentinel "no lint tools", skip this step.

## Design doc path
<absolute path to <feature_dir>/design.md>

Read for architecture context when evaluating whether a fix is safe.

Write a summary of what you fixed and what you left unfixed to: <dir>/wtf-summary.md
```

Wait for the subagent to complete. Read `<dir>/wtf-summary.md` to see what was fixed and what remains. Note any unfixed findings for the shipping gate.

## Step 5: Nitpick check (automatic, Opus subagent)

After the WTF check, run a nitpick pass on the branch diff. This catches finer-grained style and hygiene issues — scattered constants, magic numbers, naming inconsistencies, messy formatting, dead code — that the WTF pass may not have fully addressed.

Launch a single `general-purpose` subagent with `model: opus` and this prompt:

```
You are running a style and hygiene review on a completed feature branch.

## Branch diff

Run these commands to get the scope — do NOT use $() command substitution (it silently fails in this environment):

git-branch-base
# Note the printed result (e.g., "origin/main"), then use it in the next command:
git diff <printed-base>...HEAD --name-only

## Task

Run /mine.nitpick on this branch. This dispatches a hyper-critical style reviewer who flags every organization and hygiene issue with no severity filter.

After the findings are reported:

1. Read every finding carefully
2. When asked "What would you like to do with these findings?", choose "Fix them all"
3. Work through every finding top to bottom, making edits directly
4. For findings that require architectural judgment or could change behavior, leave them unfixed and note them in your summary
5. After fixing, run the project's test suite to verify no regressions: <contents of <dir>/test-command.txt>
6. If tests pass, run lint using <contents of <dir>/lint-command.txt>. If that file contains the sentinel "no lint tools", skip this step.

## Design doc path
<absolute path to <feature_dir>/design.md>

Read for architecture context when evaluating whether a fix is safe.

Write a summary of what you fixed and what you left unfixed to: <dir>/nitpick-summary.md
```

Wait for the subagent to complete. Read `<dir>/nitpick-summary.md` to see what was fixed and what remains. Note any unfixed findings for the shipping gate.

## Step 6: Final review pass (automatic)

After WTF and nitpick fixes, run a final `code-reviewer` and `integration-reviewer` pass in parallel on the full branch diff to catch any issues introduced by the auto-fix subagents.

```bash
git diff --name-only <base_commit> HEAD
```

Use the `base_commit` from the checkpoint read in Step 1.

Launch both reviewers in a single message (parallel):

**Code reviewer** (`subagent_type: "code-reviewer"`): review all changed files, write to `<dir>/final-code-review.md`.

**Integration reviewer** (`subagent_type: "integration-reviewer"`): review all changed files, write to `<dir>/final-integration-review.md`.

If either reviewer finds CRITICAL or HIGH issues, fix them inline (same pattern as Step 12's fix loop — max 2 iterations). MEDIUM and LOW findings are noted for the shipping gate but do not block.

## Step 7: Shipping gate

Present the final gate with impl-review and cross-file review results:

```
AskUserQuestion:
  question: "All tasks complete. Implementation review: <APPROVE + any non-blocking suggestions summary>. Cross-file review: <APPROVE/WARN + any notes>. WTF check: <N fixed, M unfixed — or 'all clean'>. Nitpick: <N fixed, M unfixed — or 'all clean'>. Final review: <clean / N findings fixed>. What next?"
  header: "Ship"
  multiSelect: false
  options:
    - label: "Ship via /mine.ship"
      description: "Commit, push, and open a PR"
    - label: "Challenge first"
      description: "Run /mine.challenge on the branch diff before shipping"
    - label: "Stop here"
      description: "Pause; I'll review manually"
```

**On "Ship via /mine.ship":** Invoke `/mine.ship`.

**On "Challenge first":** Tell the user to run `/mine.challenge` on the changed files. After challenge completes and the user is satisfied, they can run `/mine.ship` directly.

**On "Stop here":** Leave the checkpoint in place. The user can resume later.

## Step 8: Delete checkpoint

After the user chooses "Ship via /mine.ship" (and `/mine.ship` completes), delete the checkpoint. Do NOT delete the checkpoint if the user chose "Stop here" — it must persist for future resume.

```bash
spec-helper checkpoint-delete <feature_dir_name> --json
```

This is the final cleanup step. The checkpoint is runtime state — once the orchestration run completes and the user has passed through the review results gate, it is no longer needed. If the user chose "Stop here" at any earlier gate (during Phase 2 or at the impl-review gate), the checkpoint persists for future resume.
