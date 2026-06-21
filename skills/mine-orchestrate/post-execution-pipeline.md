# Post-Execution Review Pipeline (Phase 3)

After all tasks are processed (or user chose "Stop here"), run a review pipeline. Steps 1–5.7 are automatic (no user prompts unless blocking issues are found). The user is prompted at the impl-review gate (if blocking), the implementation comb gate (if blocking), or the final shipping gate.

**All subagents in Phase 3 MUST run in foreground** (never set `run_in_background: true`). Several steps spawn their own parallel child subagents internally, which only works in foreground execution.

**Trail-logging counter rule:** every `trail-log` call below that returns non-zero increments the counter: `log_failures=$((log_failures + 1))` (same rule stated in SKILL.md).

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

Invoke `/mine-implementation-review <feature_dir>` automatically. The skill presents findings and returns — no user gate (the orchestrator handles all gate logic).

Read the review output. Extract the verdict (APPROVE, REQUEST_FIXES, or ABANDON) and any suggestions or blocking issues.

If `trail_available` is true, log the impl-review verdict immediately:
`trail-log "<trail_path>" p3 - gate "impl-review: <APPROVE|REQUEST_FIXES|ABANDON> — <brief summary>"`

**If impl-review returns APPROVE** — note any non-blocking suggestions to surface later. Continue to Step 3 automatically.

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
4. Re-run `/mine-implementation-review <feature_dir>`
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

If the integration-reviewer returns BLOCK, surface the blocking issues to the user with an "Address" / "Stop here" gate (same pattern as the impl-review gate). If APPROVE or WARN, note any suggestions and continue to Step 4 (Clean code check).

If `trail_available` is true, log the cross-file review result:
`trail-log "<trail_path>" p3 - review "cross-file consistency: <APPROVE|WARN|BLOCK> — <brief summary>"`

## Step 4: Clean code check (automatic, Opus subagent)

After the cross-file consistency review passes, run a clean code check on the entire branch diff. This catches LLM training-bias patterns, deferred-debt shortcuts, and style hygiene issues that correctness and integration reviewers don't target.

Launch a single `general-purpose` subagent with `model: opus` and this prompt:

```
You are running a comprehensive stylistic quality review on a completed feature branch.

## Branch diff

Run these commands to get the scope — do NOT use $() command substitution (it silently fails in this environment):

git-branch-base
# Note the printed result (e.g., "origin/main"), then use it in the next command:
git diff <printed-base>...HEAD --name-only

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

Wait for the subagent to complete. Read `<dir>/clean-code-summary.md` to see what was fixed and what remains. Note any unfixed findings for the shipping gate.

If `trail_available` is true, log the clean code results:
`trail-log "<trail_path>" p3 - fix "clean code: <N fixed, M unfixed — or 'all clean'>"`

## Step 4.5: Structural simplification check (gates on HIGH findings)

After clean-code fixes, run a `code-judo-reviewer` subagent on the full branch diff. This catches structural simplification opportunities that per-task reviewers miss — bolt-on patterns, ad-hoc conditionals, duplicated logic that only becomes visible across the full change.

```bash
git diff --name-only <base_commit> HEAD
```

Launch `Agent(subagent_type: "code-judo-reviewer")` with all changed files plus context:

> Review all changes on this branch for structural simplification opportunities.
>
> Run: git diff <base_commit>...HEAD
>
> You have full-branch context — read callers and siblings of changed files to find structural moves that span the whole change. Focus on: ad-hoc conditionals bolted onto unrelated flows, duplicated helpers when a canonical home exists, state machines replaceable by data transformations, and deletion opportunities that enable collapsing a layer. Propose concrete structural moves, not just observations.

If the reviewer finds HIGH findings, present them to the user:

```
AskUserQuestion:
  question: "Structural simplification check found opportunities: <summary>. Address them?"
  header: "Simplify?"
  multiSelect: false
  options:
    - label: "Address simplifications"
      description: "Dispatch a subagent to apply the structural moves"
    - label: "Note and continue"
      description: "Acknowledge findings, proceed to final review"
```

On "Address simplifications": dispatch a `general-purpose` subagent with `model: sonnet`. Pass it: the judo-reviewer's findings (full report), the affected file paths, and the design doc path (`<feature_dir>/design.md`). Prompt: "Apply only the HIGH structural simplification moves listed below. Do not expand scope beyond these findings. After applying, run the test suite to verify no regressions: `<contents of <dir>/test-command.txt>`." On "Note and continue" or if no HIGH findings: proceed to Step 5.

MEDIUM and LOW findings are noted for the shipping gate but do not block.

If `trail_available` is true, log the structural simplification result:
- If HIGH findings existed: `trail-log "<trail_path>" p3 - review "structural simplification: <N> HIGH findings; user decision: <addressed|noted and continued>"`
- If no HIGH findings: `trail-log "<trail_path>" p3 - review "structural simplification: no HIGH findings"`

## Step 5: Final review pass (automatic)

After the clean code fixes, run a final `code-reviewer` and `integration-reviewer` pass in parallel on the full branch diff to catch any issues introduced by the auto-fix subagent.

```bash
git diff --name-only <base_commit> HEAD
```

Use the `base_commit` from the checkpoint read in Step 1.

Launch both reviewers in a single message (parallel):

**Code reviewer** (`subagent_type: "code-reviewer"`): review all changed files, write to `<dir>/final-code-review.md`.

**Integration reviewer** (`subagent_type: "integration-reviewer"`): review all changed files, write to `<dir>/final-integration-review.md`.

If either reviewer finds CRITICAL or HIGH issues, fix them inline (auto-fix unambiguous issues, re-run both reviewers, max 2 iterations). MEDIUM and LOW findings are noted for the shipping gate but do not block.

If `trail_available` is true, log the final review result:
`trail-log "<trail_path>" p3 - review "final review: <clean — or N findings fixed>"`

## Step 5.5: Trail audit (automatic)

If `trail_available` is false, skip this step entirely — the trail does not exist, so there is nothing to audit. The shipping gate will show "Trail audit: skipped (trail unavailable)".

If `trail_available` is true, launch a single `general-purpose` subagent with `model: sonnet` and this prompt (substitute `<feature_dir>` with the actual feature directory path — this is the persistent spec directory, e.g. `design/specs/028-show-me-your-work/`, NOT the tmpdir `<dir>`):

```
You are auditing the structural integrity of the decision trail from an overnight orchestrate run.

Read the trail file at: <feature_dir>/trail.tsv

## Expected sequence per task

For each task, the expected sequence is: start → [dispatch] → [contested*] → [gate] → [retry*] → [review] → [fix*] → verdict. Optional steps are bracketed; * means zero or more occurrences. Flag deviations from this sequence.

## What to check

1. Missing entries: a task with a verdict but no start entry, or vice versa
2. Sequence anomalies: entries out of expected order, or unexpected gaps between start and verdict
3. Retry patterns: a retry event with no preceding gate or review event that would have triggered it
4. Timing outliers: unusually short intervals between start and verdict (suggests skipped steps)
5. Empty detail fields: entries where the detail is blank or trivially short (under 20 characters)

Do NOT attempt to verify whether the content of detail fields is accurate — you cannot cross-reference against the actual command outputs. Focus on structural patterns the trail reveals about the execution flow.

## Output format

Start your report with: ## Summary
N findings (or "no findings")

Then list each finding with: the task ID, the structural issue, and why it matters.

Write your audit report to: <feature_dir>/trail-audit.md
```

Wait for the subagent to complete. Read `<feature_dir>/trail-audit.md` and extract the finding count from the `## Summary` line (e.g., "3 findings", "no findings"). If the file is missing or unreadable, use "failed to complete" as the audit status.

Log a trail entry for the audit:
`trail-log "<trail_path>" p3 - review "trail audit: <N findings — or 'no findings' — or 'failed to complete' if report missing>"`

## Step 5.7: Implementation fine-toothed comb (final holistic pass, gates on blocking findings)

This is the last content review before shipping. Unlike impl-review's structured checklist (Step 2), this is open-ended: does the **finished implementation faithfully and thoroughly realize the design** — is every FR and AC actually implemented, did anything get silently dropped, did any behavior drift from what the design specified? Running it last means it reviews the settled code, after clean-code and structural-simplification edits.

**Compaction tip.** This is the most context-heavy subagent in the pipeline. Feed the branch diff, not full file contents — instruct the subagent to run the diff itself (keeps the diff out of the orchestrator's context). For very large diffs, chunk by file group and reconcile.

Dispatch the `fine-toothed-comb` agent (see `${CLAUDE_HOME:-~/.claude}/agents/fine-toothed-comb.md`):

```
Agent:
  subagent_type: fine-toothed-comb
  model: sonnet
  prompt: |
    Read this design file: <feature_dir>/design.md
    Read all task files in: <feature_dir>/tasks/

    Then get the full implementation diff — do NOT use $() command substitution (it silently fails in this environment):

    git-branch-base
    # Note the printed base (e.g. "origin/main"), then:
    git diff <printed-base>...HEAD

    Go over the implementation against the design with a fine-toothed comb, making sure it's consistent, accurate, and thorough — every functional requirement and acceptance criterion in the design is actually implemented, nothing was silently dropped, and no behavior drifted from what the design specified. Report anything you find.

    Define blocking as: a requirement not met, behavior that drifted from the design, or an inconsistency that makes the implementation wrong relative to the design.
```

### Comb gate

Read `${CLAUDE_HOME:-~/.claude}/skills/mine-comb/comb-gate.md` and apply it with:

- **`<header>`**: `Impl comb`
- **`minor_blocks`**: `false` — note any minor findings for the shipping gate and proceed to Step 6; a finished implementation doesn't block shipping on polish.
- **`<blocking_question>`**: "Implementation comb found blocking design-fidelity gaps: <summary>. These must be resolved before shipping."
- **`<re_review_instructions>`**: dispatch a `general-purpose` subagent with `model: sonnet`, passing the comb findings, the design doc path (`<feature_dir>/design.md`), the task files from `<feature_dir>/tasks/`, and the affected file paths. Instruct: "Fix only the listed design-fidelity gaps. Do not expand scope beyond these findings. After fixing, run the test suite: `<contents of <dir>/test-command.txt>`." After it completes, re-run this step's comb from the top.

The gate's "Stop" leaves the checkpoint in place — for this caller that means do **not** delete the checkpoint; the user can resume later.

If `trail_available` is true, log the result:
`trail-log "<trail_path>" p3 - review "impl comb: <clean — or N minor noted — or N blocking, user decision: addressed|stopped>"`

## Step 6: Shipping gate

Present the final gate with impl-review and cross-file review results:

```
AskUserQuestion:
  question: "All tasks complete. Implementation review: <APPROVE + any non-blocking suggestions summary>. Cross-file review: <APPROVE/WARN + any notes>. Clean code check: <N fixed, M unfixed — or 'all clean'>. Structural simplification: <N findings — or 'no significant simplification found'>. Final review: <clean / N findings fixed>. Trail audit: <N findings — or 'no findings' — or 'skipped (trail unavailable)' — or 'failed to complete'>. Implementation comb: <clean — or N minor noted — or N blocking resolved>.<if log_failures > 0: ' Trail logging had <log_failures> failures during this run — check disk space and file permissions.'> What next?"
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

Read `<dir>/clean-code-summary.md` to populate the `Clean code check:` field in the question above.

**On "Ship via /mine-ship":** Invoke `/mine-ship`.

**On "Challenge first":** Tell the user to run `/mine-challenge` on the changed files. After challenge completes and the user is satisfied, they can run `/mine-ship` directly.

**On "Stop here":** Leave the checkpoint in place. The user can resume later.

## Step 7: Delete checkpoint

After the user chooses "Ship via /mine-ship" (and `/mine-ship` completes), delete the checkpoint. Do NOT delete the checkpoint if the user chose "Stop here" — it must persist for future resume.

```bash
spec-helper checkpoint-delete <feature_dir_name> --json
```

This is the final cleanup step. The checkpoint is runtime state — once the orchestration run completes and the user has passed through the review results gate, it is no longer needed. If the user chose "Stop here" at any earlier gate (during Phase 2 or at the impl-review gate), the checkpoint persists for future resume.
