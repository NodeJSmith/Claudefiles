# Post-Execution Review Pipeline (Phase 3)

After all tasks are processed (or user chose "Stop here"), run a review pipeline. Steps 1–5 are automatic (no user prompts unless blocking issues are found). The user is prompted at the impl-review gate (if blocking) or the final shipping gate.

**All subagents in Phase 3 MUST run in foreground** (never set `run_in_background: true`). Several steps spawn their own parallel child subagents internally, which only works in foreground execution.

**Telemetry:** Every subagent prompt in Phase 3 must include `cfl_dispatch_id: <dispatch_id>` (the ID from the `cfl dispatch` call that preceded it). This enables automatic token/compaction tracking via a PostToolUse hook.

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

Use `tasks[].verdict` and `tasks[].verdict_detail` fields. PASS with a detail note means findings were raised and either resolved or recorded as durable known issues. WARN means something genuinely unresolved remains.

## Step 2: Implementation review (automatic, gates on blocking issues)

Invoke `/mine-implementation-review <feature_dir>` automatically. The skill presents findings and returns — no user gate (the orchestrator handles all gate logic).

Read the review output. Extract the verdict (PASS, FAIL, or ABANDON) and any suggestions or blocking issues. Record the gate result (ABANDON maps to FAIL):

```bash
cfl gate impl-review --verdict <PASS|FAIL> --detail "<brief summary>"
```

**If impl-review returns PASS** — note any non-blocking suggestions to surface later. If a suggestion identifies a real issue that should not be fixed in this run, read `${CLAUDE_CONFIG_DIR:-~/.claude}/skills/mine-orchestrate/known-issues-protocol.md`, check the qualifying criteria and the Severity Gate, and record it (with `Run: <run_id>`, using the `run_id` read in Step 1) only if it passes both. If it trips the Severity Gate, raise the protocol's **Severity Escalation** `AskUserQuestion` right now instead of recording and moving on — follow that prompt's own "Fix now"/"Stop here"/"Ship anyway" mechanics. Continue to Step 3 automatically only if no escalation was needed, or the escalation resolved via "Fix now" or "Ship anyway" — not if the user chose "Stop here".

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
   cfl dispatch impl-fixer --agent-type general-purpose --model sonnet
   ```
2. Dispatch a fresh `general-purpose` subagent with `model: sonnet` and: `cfl_dispatch_id: <dispatch_id>` (from the preceding `cfl dispatch` call), the impl-review findings, the relevant file paths, the design doc path (`<feature_dir>/design.md` — instruct the subagent to read it directly), all task files from `<feature_dir>/tasks/` (for per-task constraints and Review Guidance), accumulated spec-reviewer outputs, `implementer-prompt.md` content (as `## Implementer instructions`), `retry-prompt.md` content (as `## Retry instructions`), and `tdd.md` content. Populate the `## Previous review feedback` template with: "Impl-review: <absolute path to impl-review findings file>". Instruct: "Fix only the listed blocking issues. Do not expand scope beyond these findings. Respect the Review Guidance constraints from each task."
3. After the subagent completes: `cfl dispatch end <dispatch_id>`
4. Re-run the project test suite (using `<dir>/test-command.txt`; skip and treat as passing if that file contains the sentinel `no test suite`). If tests fail: surface the failure prominently in the next gate prompt (which offers "Address fixes" or "Stop here" — there is no "Accept and ship" option at this gate) with a note identifying the test failures.
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
cfl dispatch cross-file-reviewer --agent-type integration-reviewer --model sonnet
```

Launch `Agent(subagent_type: "integration-reviewer")` with all changed files. Include `cfl_dispatch_id: <dispatch_id>` (from the preceding `cfl dispatch` call) and the design doc path (`<feature_dir>/design.md`) so the reviewer can verify terminology and pattern choices against design decisions. Add this focus instruction to the prompt:

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
cfl gate cross-file-review --verdict <PASS|WARN|FAIL> --data '{"findings": <N>, "critical": <C>, "high": <H>, "medium": <M>, "low": <L>}'
```

If the integration-reviewer returns FAIL, surface the blocking issues to the user with an "Address" / "Stop here" gate. On "Address": record a fresh fixer dispatch and capture its ID:

```bash
cfl dispatch cross-file-fixer --agent-type general-purpose --model sonnet
```

Then dispatch a `general-purpose` fixer with `model: sonnet`, `cfl_dispatch_id: <cross_file_fixer_dispatch_id>`, the cross-file review findings, changed file paths, design doc path, task files, and the instruction: "Fix only the listed cross-file consistency issues; do not expand scope." After it completes:

```bash
cfl dispatch end <cross_file_fixer_dispatch_id>
```

Then re-run the project test suite using `<dir>/test-command.txt` (skip and treat as passing if that file contains the sentinel `no test suite`), re-run the cross-file integration review, and record the updated `cross-file-review` gate. Repeat with the same warning-after-3-rounds policy as the impl-review gate, or stop if the user chooses "Stop here". If PASS or WARN, note any suggestions. If a suggestion identifies a real issue that should not be fixed in this run, read `${CLAUDE_CONFIG_DIR:-~/.claude}/skills/mine-orchestrate/known-issues-protocol.md`, check the qualifying criteria and the Severity Gate, and record it (with `Run: <run_id>` from Step 1) only if it passes both — raise the protocol's **Severity Escalation** `AskUserQuestion` right now if it trips the gate, same as Step 2, and follow its "Fix now"/"Stop here"/"Ship anyway" mechanics. Continue to Step 4 (Clean code check) only if no escalation was needed, or it resolved via "Fix now" or "Ship anyway" — not if the user chose "Stop here".

## Step 4: Clean code check (automatic)

After the cross-file consistency review passes, run a clean code check on the entire branch diff. This catches LLM training-bias patterns, deferred-debt shortcuts, and style hygiene issues that correctness and integration reviewers don't target.

Record the dispatch and capture its ID:

```bash
cfl dispatch clean-code-executor --agent-type general-purpose --model sonnet
```

Launch a single `general-purpose` subagent with `model: sonnet` and this prompt. (The analysis is done by `mine-clean-code`'s three Sonnet checkers; this wrapper only invokes the skill and applies the unambiguous fixes — leaving anything that needs architectural judgment noted, not fixed — so it does not need Opus.)

```
You are running a comprehensive stylistic quality review on a completed feature branch.

## Branch diff

Run this to get the scope. Use the orchestration run's recorded base commit from Step 1, not the branch base:

git diff --name-only <base_commit> HEAD

## Task

Run /mine-clean-code on this branch. This dispatches three parallel checkers (llm-checker, lazy-checker, nitpicker) and consolidates their findings.

After the findings are reported:

1. When mine-clean-code asks "What would you like to do with these findings?", choose "Fix all"
2. Fix ALL findings that have unambiguous solutions — obvious-comment removal, dead helper removal, naming improvements, scattered constants, hardcoded values that should be configurable, copy-paste extraction, etc.
3. For findings that require architectural judgment or could change behavior in subtle ways (e.g., collapsing an abstraction stack, restructuring an error hierarchy), leave them unfixed and note them in your summary
4. For every real unfixed finding that should not be fixed in this orchestration run, read `${CLAUDE_CONFIG_DIR:-~/.claude}/skills/mine-orchestrate/known-issues-protocol.md`, check the qualifying criteria. If it doesn't qualify, explain why in the summary instead (rejected as invalid/non-actionable) so it isn't silently dropped.
5. For every finding that qualifies, also check the Severity Gate. If it passes, append an entry to `<feature_dir>/known-issues.md` with `Run: <run_id>` (the value passed into this prompt). **You cannot ask the user directly — do not record an entry for a finding that trips the Severity Gate (user-visible breakage with no explanation, silent data loss, security exposure, or the core workflow blocked entirely).** Instead, add it to a `## SEVERE — needs immediate attention` section at the top of the summary with the same detail a known-issues entry would have; the orchestrator raises the protocol's Severity Escalation prompt to the user after reading this file.
6. After fixing, run the project's test suite to verify no regressions: <contents of <dir>/test-command.txt>. If that file contains the sentinel "no test suite", skip this step.
7. If tests pass or were skipped, run lint using <contents of <dir>/lint-command.txt>. If that file contains the sentinel "no lint tools", skip this step.

## Design doc path
<absolute path to <feature_dir>/design.md>

Read for architecture context when evaluating whether a fix is safe.

Write a summary of what you fixed and what you left unfixed to: <dir>/clean-code-summary.md

The first line of the summary file MUST be: `<!-- HEAD: <git rev-parse --short HEAD> -->` — this allows mine-ship to detect that the clean-code check already ran at this commit.

cfl_dispatch_id: <dispatch_id>
run_id: <run_id read in Step 1>
```

Wait for the subagent to complete. Mark the dispatch done:

```bash
cfl dispatch end <dispatch_id>
```

Read `<dir>/clean-code-summary.md` to see what was fixed and what remains. Note any unfixed findings for the shipping gate. If the summary has a `## SEVERE — needs immediate attention` section, raise the `${CLAUDE_CONFIG_DIR:-~/.claude}/skills/mine-orchestrate/known-issues-protocol.md` **Severity Escalation** `AskUserQuestion` for each item in it now, before recording the gate result below, and follow its "Fix now"/"Stop here"/"Ship anyway" mechanics — do not record the gate result or continue to Step 5 if the user chose "Stop here". Record the gate result:

```bash
cfl gate clean-code --verdict <PASS|WARN> --data '{"fixed": <N>, "unfixed": <M>}'
```

## Step 5: Final review pass (automatic)

After the clean code fixes, run a final `code-reviewer` and `integration-reviewer` pass in parallel on the full branch diff — to catch issues introduced by the auto-fix subagent, and to catch anything a per-task review couldn't see (a review scoped to one task at a time can miss issues that only appear across the full diff).

```bash
git diff --name-only <base_commit> HEAD
```

Use the `base_commit` from the run status read in Step 1.

Record both dispatches and capture their IDs:

```bash
cfl dispatch final-code-reviewer --agent-type code-reviewer --model sonnet
cfl dispatch final-integration-reviewer --agent-type integration-reviewer --model sonnet
```

Launch both reviewers in a single message (parallel), with the `CONCISE-RETURN-MODE` sentinel and output file paths (same activation contract used by the findings fix loop — see `verdict-line-format.md`):

**Code reviewer** (`subagent_type: "code-reviewer"`): include `cfl_dispatch_id: <final_code_reviewer_dispatch_id>`, review all changed files, write to `<dir>/final/code-review.md`.

**Integration reviewer** (`subagent_type: "integration-reviewer"`): include `cfl_dispatch_id: <final_integration_reviewer_dispatch_id>`, review all changed files, write to `<dir>/final/integration-review.md`.

After both complete, mark dispatches done:

```bash
cfl dispatch end <final_code_reviewer_dispatch_id>
cfl dispatch end <final_integration_reviewer_dispatch_id>
```

Extract the canonical verdict lines (last line matching `^\*\*Verdict:\*\*` in each file).

**If both reviewers return PASS:** no fixer loop needed — a PASS with informational findings is clean regardless of count. Treat this as `fixed: 0, deferred: 0, rejected: 0, unresolved: 0` and go straight to the retest step below.

**If either reviewer returns WARN or FAIL:** read `${CLAUDE_CONFIG_DIR:-~/.claude}/skills/mine-orchestrate/findings-fix-loop.md` and follow it with:
- `<scope_id>` = `final`
- `<scope_dir>` = `<dir>/final` (this step's review files already live here)
- Changed-files method: recompute fresh each iteration by unioning `git diff --name-only <base_commit> HEAD` with `git diff --name-only HEAD` and `git ls-files --others --exclude-standard` (uncommitted fixer edits stay in the working tree until shipping) — no `changed-files.txt`
- No "Task scope boundary" block — every finding is in scope; there is no later task to defer to
- Design doc path: `<feature_dir>/design.md`
- Task file paths: all files under `<feature_dir>/tasks/`

This applies the same fix/defer policy to every finding regardless of severity (CRITICAL, HIGH, MEDIUM, LOW) that the WP-time loop uses at Step 12 — nothing is allowed to just sit as an informational note at this point either. The loop's own Gate section determines the fixer gate result: FAIL if any `unresolved` row remains in the terminal ledger, PASS otherwise (every finding fixed, or deferred with a recorded known-issue ID). Use that result as-is below — do not re-derive it from a fresh ledger read. Pass `run_id` (from Step 1) into the fixer's inputs per `findings-fix-loop.md`, so any entry it records carries `Run: <run_id>`.

**Retest (both branches):** After the loop resolves (or immediately, if both initial reviewers passed), re-run the project test suite using `<dir>/test-command.txt` (skip and record `SKIPPED: no test suite` if that file contains the sentinel `no test suite`) and lint using `<dir>/lint-command.txt` (skip and record `SKIPPED: no lint tools` if that file contains the sentinel `no lint tools`). Append a `Final-review retest` section to `<dir>/clean-code-summary.md` with the refreshed HEAD, test result, and lint result — Step 6 reads that summary for the shipping prompt. A test or lint failure makes the `final-review` gate **FAIL** regardless of the ledger outcome — a fixer pass that leaves the suite broken is not a clean final state.

Record the gate result:

```bash
cfl gate final-review --verdict <PASS|FAIL> --data '{"fixed": <N>, "deferred": <M>, "rejected": <R>, "unresolved": <K>}'
```

`fixed`/`deferred`/`rejected`/`unresolved` come from the terminal ledger (`0/0/0/0` if no loop ran). Any `unresolved` finding at any severity, or a retest failure, makes this gate FAIL — there is no "proceed anyway" here, same as the WP-time gate. Surface the specifics (unresolved findings, or the test/lint failure) to the user and do not proceed to the shipping gate.

## Step 5.5: Known issues summary (automatic)

Read the known-issues artifact defined by `${CLAUDE_CONFIG_DIR:-~/.claude}/skills/mine-orchestrate/known-issues-protocol.md` if it exists. Capture every entry's ID, title, status, and `Run:` field. If the file does not exist, there is nothing to summarize or walk through — skip Step 5.6 and treat the shipping gate's known issues field as `0 open`.

Split entries with `Status: open` into two groups by comparing each entry's `Run:` field against the current `run_id` (from `cfl run status`, read fresh here — durable across a mid-run session boundary, unlike an in-context list):

- **New this run** — open entries whose `Run:` matches the current `run_id`. Because `run_id` is the same across a mid-run session boundary (resume after context compaction, a manual `/clear`, or a crash/restart — the resumed session is still the same orchestrate run, just a fresh conversation), this correctly includes entries recorded in an earlier session of this run before the boundary — Step 5.6 runs exactly once, at the true end of Phase 3, so those entries reach the individual walkthrough here rather than skipping it.
- **Backlog** — open entries whose `Run:` doesn't match: recorded during a genuinely earlier, already-completed orchestrate run on this same feature.

## Step 5.6: Known issues walkthrough (automatic gate)

Do not treat this as optional bookkeeping — this is the checkpoint that keeps deferred issues from becoming invisible. Run it before the shipping gate, not folded into it.

**New-this-run entries:** for each one, ask individually (never batch these — see the "new this run" list from Step 5.5):

```
AskUserQuestion:
  question: "<KI-ID>: <title>. <one-line issue summary from the entry's 'Issue:' field>. What next?"
  header: "Known issue"
  multiSelect: false
  options:
    - label: "Fix now"
      description: "Dispatch a fixer for just this issue, re-review, re-test, then mark it resolved"
    - label: "File as GitHub issue"
      description: "Create a tracked issue via gh-issue and mark this entry filed"
    - label: "Leave deferred"
      description: "Keep it recorded in known-issues.md as open for later"
```

- **Fix now:** record the dispatch (`cfl dispatch known-issue-fixer --agent-type general-purpose --model sonnet`), capture `dispatch_id`, then dispatch a `general-purpose` subagent (`model: sonnet`, `cfl_dispatch_id: <dispatch_id>`) scoped to only this entry's `Affected files` and `Recommended follow-up`. After it completes: `cfl dispatch end <dispatch_id>`. Then record a reviewer dispatch (`cfl dispatch known-issue-review --agent-type code-reviewer --model sonnet`), capture `review_dispatch_id`, and run `code-reviewer` once on the changed files with `cfl_dispatch_id: <review_dispatch_id>`; after it completes: `cfl dispatch end <review_dispatch_id>`. (Single-pass `code-reviewer` only, not the full `findings-fix-loop.md` rigor — this fix targets one already-identified, already-scoped issue rather than an open-ended review, so the cross-file consistency check `integration-reviewer` adds isn't needed.) On FAIL or WARN, or if a subsequent test/lint retest fails, treat the fix attempt as failed: tell the user what went wrong, leave the entry's `Status:` as `open`, and re-raise this same three-option `AskUserQuestion` for the entry (Fix now / File as GitHub issue / Leave deferred) rather than silently stalling — do not proceed to Step 6 until the user responds again. A retried "Fix now" dispatches a fresh subagent scoped the same way; it sees the current (possibly still-broken) state of the affected files and can build on or revert the prior attempt as it judges appropriate. On a clean code-reviewer PASS, re-run the project test suite using `<dir>/test-command.txt` (skip and treat as passing if that file contains the sentinel `no test suite`) and lint using `<dir>/lint-command.txt` (skip and treat as passing if that file contains the sentinel `no lint tools`) — the same rigor bar Step 4's clean-code fixer uses. If both pass (or are skipped via their sentinels), update the entry's `Status:` line to `resolved — fixed during known issues walkthrough` and leave the rest of the entry as history.
- **File as GitHub issue:** run `gh-issue create` (see `${CLAUDE_CONFIG_DIR:-~/.claude}/rules/common/git-workflow.md` — Issue Creation Conventions) using the entry's title and body content, then update the entry's `Status:` line to `filed (#<issue-number>)`.
- **Leave deferred:** no change; `Status: open` stands.

**Backlog entries:** do not walk through these individually every run — that trains the user to reflexively dismiss the prompt. Instead, ask once:

```
AskUserQuestion:
  question: "<N> known issues from earlier runs on this feature are still open: <KI-001 title>, <KI-002 title>, ... . Review them now?"
  header: "Known issues backlog"
  multiSelect: false
  options:
    - label: "Not now"
      description: "Leave the backlog as-is; it stays visible in the shipping gate's known issues count"
    - label: "Review them"
      description: "Walk through each backlog entry the same way as new-this-run entries"
```

If "Review them," walk through each backlog entry with the same three-option AskUserQuestion used for new-this-run entries above.

## Step 6: Shipping gate

Re-read `<feature_dir>/known-issues.md` (statuses may have changed in Step 5.6) and recount entries with `Status: open` for the shipping gate's known issues field.

Present the final gate with impl-review and cross-file review results:

```
AskUserQuestion:
  question: "All tasks complete. Implementation review: <PASS + any non-blocking suggestions summary>. Cross-file review: <PASS/WARN + any notes>. Clean code check: <N fixed, M unfixed — or 'all clean'>. Final review: <PASS — N fixed, M deferred to known issues, R rejected — or 'all clean'>. Known issues: <0 open | N still open: KI-001 title; KI-002 title>. What next?"
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

Use the `fixed`/`deferred`/`rejected`/`unresolved` counts recorded in the `cfl gate final-review` call above to populate the `Final review:` field — by the time this step runs, that gate is PASS (a FAIL would have stopped the pipeline before reaching here). If `<dir>/clean-code-summary.md` contains a `Final-review retest` section, include its refreshed test/lint status in the `Final review:` field so the shipping prompt reflects the gates that ran after final-review auto-fixes.

Use the post-walkthrough recount from the start of this step (not the pre-walkthrough Step 5.5 split) to populate the `Known issues:` field.

**On "Ship via /mine-ship":** Invoke `/mine-ship`.

**On "Challenge first":** Tell the user to run `/mine-challenge` on the changed files. After challenge completes and the user is satisfied, they can run `/mine-ship` directly.

**On "Stop here":** Leave the run active. The user can resume later.

## Step 7: Complete the run

After the user chooses "Ship via /mine-ship" (and `/mine-ship` completes), mark the run as completed. Do NOT complete the run if the user chose "Stop here" — it must remain active for future resume.

```bash
cfl run complete
```

This marks the run terminal in the DB. The spec's `active_run_id` is cleared. If the user chose "Stop here" at any earlier gate (during Phase 2 or at the impl-review gate), the run remains active for future resume.
