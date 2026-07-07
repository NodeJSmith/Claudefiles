# Post-Execution Review Pipeline (Phase 3)

After all tasks are processed (or user chose "Stop here"), run a review pipeline. Steps 1–5.5 are automatic (no user prompts unless blocking issues are found). The user is prompted at the impl-review gate (if blocking), the implementation comb gate (if blocking), or the final shipping gate.

**All subagents in Phase 3 MUST run in foreground** (never set `run_in_background: true`). Several steps spawn their own parallel child subagents internally, which only works in foreground execution.

## Step 1: Summary (automatic)

Present a verdict table. **Read the run state via `cfl run status`** and build the table from the `tasks` array:

```
| Task | Title   | Verdict              |
|------|---------|----------------------|
| T01  | ...     | PASS                 |
| T02  | ...     | PASS (3 auto-fixed)  |
| T03  | ...     | WARN (visual skipped)|
...
```

Use `tasks[].verdict` and `tasks[].verdict_detail` fields. PASS with a detail note means findings were raised and resolved. WARN means something genuinely unresolved remains.

## Step 2: Implementation review (automatic, gates on blocking issues)

Invoke `/mine-implementation-review <feature_dir>` automatically. The skill presents findings and returns — no user gate (the orchestrator handles all gate logic).

Read the review output. Extract the verdict (PASS, FAIL, or ABANDON) and any suggestions or blocking issues. Record the gate result (ABANDON maps to FAIL):

```bash
cfl gate impl-review --verdict <PASS|FAIL> --detail "<brief summary>"
```

**If impl-review returns PASS** — note any non-blocking suggestions to surface later. Continue to Step 3 automatically.

**If impl-review returns ABANDON** — hard stop. ABANDON means the implementation is unrecoverable and requires a design rethink, not a code fix. Do not offer "Address fixes":

```
AskUserQuestion:
  question: "Implementation review rated this ABANDON (unrecoverable — design rethink needed): <summary of blocking issues>."
  header: "Impl-review: ABANDON"
  multiSelect: false
  options:
    - label: "Stop and revise the design"
      description: "Return to /mine-define or /mine-plan to update the tasks"
    - label: "Stop here for now"
      description: "Pause execution; resume after the design is updated"
```

**If impl-review returns FAIL** — prompt the user:

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
1. Record the dispatch and capture its ID:
   ```bash
   cfl dispatch impl-fixer --agent-type general-purpose
   ```
2. Dispatch a fresh `general-purpose` subagent with `model: sonnet` and: the impl-review findings, the relevant file paths, the design doc path (`<feature_dir>/design.md` — instruct the subagent to read it directly), all task files from `<feature_dir>/tasks/` (for per-task constraints and Review Guidance), accumulated spec-reviewer outputs, `implementer-prompt.md` content (as `## Implementer instructions`), `retry-prompt.md` content (as `## Retry instructions`), and `tdd.md` content. Populate the `## Previous review feedback` template with: "Impl-review: <absolute path to impl-review findings file>". Instruct: "Fix only the listed blocking issues. Do not expand scope beyond these findings. Respect the Review Guidance constraints from each task."
3. After the subagent completes: `cfl dispatch end <dispatch_id>`
4. Re-run the project test suite (using `<dir>/test-command.txt`). If tests fail: surface the failure prominently in the next gate prompt (which offers "Address fixes" or "Stop here" — there is no "Accept and ship" option at this gate) with a note identifying the test failures.
5. Re-run `code-reviewer` and `integration-reviewer` on the fix diff in parallel (both in a single message)
6. Re-run `/mine-implementation-review <feature_dir>`
7. If it now returns PASS, record the updated gate and continue to Step 3:
   ```bash
   cfl gate impl-review --verdict PASS --detail "<summary>"
   ```
8. "Address fixes" remains available across iterations — the user decides when to stop. Starting with the 3rd round, prepend a warning to the gate question: "Multiple rounds have not resolved the blocking issues — consider stopping to investigate the root cause before continuing." Do not remove the option; the user may have context (e.g., knowing the next iteration targets a different layer) that justifies continuing.

**On "Stop here":** Leave the run active. The user can resume later. Do not call `cfl run complete`.

## Step 3: Cross-file consistency review (automatic)

After impl-review passes, run an `integration-reviewer` subagent on the **full branch diff** (not per-task). This catches cross-file consistency issues that per-task reviews miss because they only see one task's changes at a time.

```bash
git diff --name-only <base_commit> HEAD
```

Use the `base_commit` from the run status read in Step 1.

Record the dispatch and capture its ID:

```bash
cfl dispatch cross-file-reviewer --agent-type integration-reviewer
```

Launch `Agent(subagent_type: "integration-reviewer")` with all changed files. Add this focus instruction to the prompt:

> In addition to your standard checklist (duplication, convention drift, misplacement, orphaned code, design violations), pay special attention to **cross-file consistency** across the full diff:
> - **Terminology drift**: same concept described with different words across files (e.g., "verb" vs "execution outcome" for the same trigger condition)
> - **Stale cross-references**: section numbers, file paths, or artifact names that point to the wrong target after edits
> - **Format/schema coverage**: tables, enumerations, or format specs that don't cover all variants actually used in other files
> - **Stated principles violated by implementation details**: rules declared in one file but contradicted by logic in another
> - **Hard-coded values that should be parameterized**: artifact names or paths that appear as literals but should vary by context (e.g., iteration suffixes)
> - **Worked examples using invalid contract values**: examples that show values not in the canonical vocabulary

After the reviewer completes: `cfl dispatch end <dispatch_id>`

Record the gate result:

```bash
cfl gate cross-file-review --verdict <PASS|WARN|FAIL> --data '{"findings": <N>}'
```

If the integration-reviewer returns FAIL, surface the blocking issues to the user with an "Address" / "Stop here" gate (same pattern as the impl-review gate). If PASS or WARN, note any suggestions and continue to Step 4 (Clean code check).

## Step 4: Clean code check (automatic)

After the cross-file consistency review passes, run a clean code check on the entire branch diff. This catches LLM training-bias patterns, deferred-debt shortcuts, and style hygiene issues that correctness and integration reviewers don't target.

Record the dispatch and capture its ID:

```bash
cfl dispatch clean-code-executor --agent-type general-purpose
```

Launch a single `general-purpose` subagent with `model: sonnet` and this prompt. (The analysis is done by `mine-clean-code`'s three Sonnet checkers; this wrapper only invokes the skill and applies the unambiguous fixes — leaving anything that needs architectural judgment noted, not fixed — so it does not need Opus.)

```
You are running a comprehensive stylistic quality review on a completed feature branch.

## Branch diff

Run this to get the scope:

git diff "$(git-branch-base)"...HEAD --name-only

## Task

Run /mine-clean-code on this branch. This dispatches three parallel checkers (llm-checker, lazy-checker, nitpicker) and consolidates their findings.

After the findings are reported:

1. When mine-clean-code asks "What would you like to do with these findings?", choose "Fix all"
2. Fix ALL findings that have unambiguous solutions — obvious-comment removal, dead helper removal, naming improvements, scattered constants, hardcoded values that should be configurable, copy-paste extraction, etc.
3. For findings that require architectural judgment or could change behavior in subtle ways (e.g., collapsing an abstraction stack, restructuring an error hierarchy), leave them unfixed and note them in your summary
4. After fixing, run the project's test suite to verify no regressions: <contents of <dir>/test-command.txt>
5. If tests pass, run lint using <contents of <dir>/lint-command.txt>. If that file contains the sentinel "no lint tools", skip this step.

## Design doc path
<absolute path to <feature_dir>/design.md>

Read for architecture context when evaluating whether a fix is safe.

Write a summary of what you fixed and what you left unfixed to: <dir>/clean-code-summary.md

The first line of the summary file MUST be: `<!-- HEAD: <git rev-parse --short HEAD> -->` — this allows mine-ship to detect that the clean-code check already ran at this commit.
```

Wait for the subagent to complete. Mark the dispatch done:

```bash
cfl dispatch end <dispatch_id>
```

Read `<dir>/clean-code-summary.md` to see what was fixed and what remains. Note any unfixed findings for the shipping gate. Record the gate result:

```bash
cfl gate clean-code --verdict <PASS|WARN> --data '{"fixed": <N>, "unfixed": <M>}'
```

## Step 5: Final review pass (automatic)

After the clean code fixes, run a final `code-reviewer` and `integration-reviewer` pass in parallel on the full branch diff to catch any issues introduced by the auto-fix subagent.

```bash
git diff --name-only <base_commit> HEAD
```

Use the `base_commit` from the run status read in Step 1.

Record both dispatches and capture their IDs:

```bash
cfl dispatch final-code-reviewer --agent-type code-reviewer
cfl dispatch final-integration-reviewer --agent-type integration-reviewer
```

Launch both reviewers in a single message (parallel):

**Code reviewer** (`subagent_type: "code-reviewer"`): review all changed files, write to `<dir>/final-code-review.md`.

**Integration reviewer** (`subagent_type: "integration-reviewer"`): review all changed files, write to `<dir>/final-integration-review.md`.

After both complete, mark dispatches done:

```bash
cfl dispatch end <final_code_reviewer_dispatch_id>
cfl dispatch end <final_integration_reviewer_dispatch_id>
```

If either reviewer finds CRITICAL or HIGH issues, fix them inline (auto-fix unambiguous issues, re-run both reviewers, max 2 iterations). MEDIUM and LOW findings are noted for the shipping gate but do not block.

Record the gate result:

```bash
cfl gate final-review --verdict <PASS|WARN|FAIL> --data '{"findings_fixed": <N>}'
```

## Step 5.5: Implementation fine-toothed comb (final holistic pass, gates on blocking findings)

This is the last content review before shipping. Unlike impl-review's structured checklist (Step 2), this is open-ended: does the **finished implementation faithfully and thoroughly realize the design** — is every FR and AC actually implemented, did anything get silently dropped, did any behavior drift from what the design specified? Running it last means it reviews the settled code, after clean-code edits.

**Scope tip.** This is the most context-heavy subagent in the pipeline. Feed the branch diff, not full file contents — instruct the subagent to run the diff itself (keeps the diff out of the orchestrator's context). For very large diffs, chunk by file group and reconcile.

Record the dispatch and capture its ID:

```bash
cfl dispatch impl-comb --agent-type fine-toothed-comb
```

Dispatch the `fine-toothed-comb` agent (see `${CLAUDE_CONFIG_DIR:-~/.claude}/agents/fine-toothed-comb.md`):

```
Agent:
  subagent_type: fine-toothed-comb
  model: sonnet
  prompt: |
    Read this design file: <feature_dir>/design.md
    Read all task files in: <feature_dir>/tasks/

    Then get the full implementation diff:

    git diff "$(git-branch-base)"...HEAD

    Go over the implementation against the design with a fine-toothed comb, making sure it's consistent, accurate, and thorough — every functional requirement and acceptance criterion in the design is actually implemented, nothing was silently dropped, and no behavior drifted from what the design specified. Report anything you find.

    Define blocking as: a requirement not met, behavior that drifted from the design, or an inconsistency that makes the implementation wrong relative to the design.
```

After the agent completes: `cfl dispatch end <dispatch_id>`

### Comb gate

Read `${CLAUDE_CONFIG_DIR:-~/.claude}/skills/mine-comb/comb-gate.md` and apply it with:

- **`<header>`**: `Impl comb`
- **`minor_blocks`**: `false` — note any minor findings for the shipping gate and proceed to Step 6; a finished implementation doesn't block shipping on polish.
- **`<blocking_question>`**: "Implementation comb found blocking design-fidelity gaps: <summary>. These must be resolved before shipping."
- **`<re_review_instructions>`**: dispatch a `general-purpose` subagent with `model: sonnet`, passing the comb findings, the design doc path (`<feature_dir>/design.md`), the task files from `<feature_dir>/tasks/`, and the affected file paths. Instruct: "Fix only the listed design-fidelity gaps. Do not expand scope beyond these findings. After fixing, run the test suite: `<contents of <dir>/test-command.txt>`." After it completes, re-run this step's comb from the top.

The gate's "Stop" leaves the run active — for this caller that means do **not** call `cfl run complete`; the user can resume later.

Record the gate result:

```bash
cfl gate impl-comb --verdict <PASS|WARN|FAIL> --data '{"blocking": <N>, "minor": <N>}'
```

## Step 6: Shipping gate

Present the final gate with impl-review and cross-file review results:

```
AskUserQuestion:
  question: "All tasks complete. Implementation review: <PASS + any non-blocking suggestions summary>. Cross-file review: <PASS/WARN + any notes>. Clean code check: <N fixed, M unfixed — or 'all clean'>. Final review: <clean / N findings fixed>. Implementation comb: <clean — or N minor noted — or N blocking resolved>. What next?"
  header: "Ship"
  multiSelect: false
  options:
    - label: "Ship via /mine-ship"
      description: "Commit, push, and open a PR"
    - label: "Challenge first"
      description: "Run /mine-challenge on the branch diff before shipping"
    - label: "Stop here"
      description: "Pause; I'll review manually"
```

After the user selects, record the shipping gate result:

```bash
cfl gate shipping-gate --verdict <PASS|WARN|FAIL> --data '{"choice": "<ship|challenge|stop>"}'
```

(PASS for "Ship via /mine-ship", WARN for "Challenge first", FAIL for "Stop here")

Read `<dir>/clean-code-summary.md` to populate the `Clean code check:` field in the question above.

**On "Ship via /mine-ship":** Invoke `/mine-ship`.

**On "Challenge first":** Tell the user to run `/mine-challenge` on the changed files. After challenge completes and the user is satisfied, they can run `/mine-ship` directly.

**On "Stop here":** Leave the run active. The user can resume later.

## Step 7: Complete the run

After the user chooses "Ship via /mine-ship" (and `/mine-ship` completes), mark the run as completed. Do NOT complete the run if the user chose "Stop here" — it must remain active for future resume.

```bash
cfl run complete
```

This marks the run terminal in the DB. The spec's `active_run_id` is cleared. If the user chose "Stop here" at any earlier gate (during Phase 2 or at the impl-review gate), the run remains active for future resume.
