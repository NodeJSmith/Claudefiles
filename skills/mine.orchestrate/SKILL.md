---
name: mine.orchestrate
description: "Use when the user says: \"execute the plan\", \"orchestrate implementation\", or \"start executing\". Runs work packages task-by-task with implementer + reviewer subagent loop."
user-invocable: true
---

# Orchestrate

Execute an approved set of Work Packages. Runs each WP through an executor → spec reviewer → code reviewer → integration reviewer loop. Gates on deviations. Updates WP lane state via `spec-helper` after each WP completes.

## Arguments

$ARGUMENTS — path to a feature directory (`design/specs/NNN-feature/`) or a specific `WP*.md` file. If empty, find the most recently modified `design/specs/*/tasks/WP*.md` and locate its feature directory.

---

## Resuming after context compaction

If context compaction occurs mid-orchestration (new session, context window reset), resume by:

1. Run `/mine.status` for quick orientation (branch, last commit, errors)
2. Run `spec-helper checkpoint-read <feature_dir_name> --json` to recover full orchestration state (completed WPs, current WP, tmpdir, base commit)
3. Re-invoke `/mine.orchestrate <feature_dir>` — the checkpoint detection in Phase 0 will pick up where you left off

The checkpoint file (`tasks/.orchestrate-state.md`) persists across sessions. Per-WP temp artifacts (executor output, review files, screenshots) may be lost if `/tmp` was cleared between sessions — the resume path handles this gracefully by skipping review-file checks for already-completed WPs.

---

## Phase 0: Locate the Work Packages

### Check for existing checkpoint (resume detection)

Before anything else, determine the feature directory from `$ARGUMENTS` (using the same logic as "Find the feature directory" below — directory, WP file, or most-recently-modified glob). Do **not** present the confirmation AskUserQuestion at this point — just resolve the path silently. Then check for an existing checkpoint:

```bash
spec-helper checkpoint-read <feature_dir_name> --json
```

**If it returns `{"exists": false}`** — proceed to "Find the feature directory" and continue the normal fresh-start flow.

**If it returns checkpoint data** — extract all fields from the JSON. Then determine staleness: parse `started_at` and compare to the current time. If `started_at` is older than 24 hours, note that in the prompt and default to "Restart fresh".

Count the completed WPs from the verdicts section and the total WPs from the feature directory.

Present the resume prompt:

```
AskUserQuestion:
  question: "Found orchestration state from <started_at>. <N> of <M> WPs completed (<comma-separated list of verdict WP IDs and their verdicts, e.g. 'WP01: PASS, WP02: WARN'>). Resume or restart?"
  header: "Resume"
  multiSelect: false
  options:
    - label: "Resume from <next WP ID after last_completed_wp>"
      description: "Continue where we left off — tmpdir: <tmpdir>, visual_skip: <visual_skip>"
    - label: "Restart fresh"
      description: "Delete the checkpoint and start from the beginning"
```

If `started_at` is older than 24 hours, append " (checkpoint is over 24 hours old)" to the "Restart fresh" label.

**On resume:**
- Restore all key-value fields from the checkpoint: `feature_dir`, `tmpdir`, `visual_skip`, `dev_server_url`, `base_commit`, `started_at`
- Verify `tmpdir` exists. If it does not, run `get-skill-tmpdir mine-orchestrate` to create a new one and note that subagent outputs from prior WPs are gone (code changes are in git; verdicts are in the checkpoint)
- Re-read `<feature_dir>/design.md` and all `<feature_dir>/tasks/WP*.md` files (they may have been edited between sessions)
- **Stale verdict check**: For each completed WP (those with verdicts in the checkpoint), check whether the WP file was modified after the checkpoint's `started_at` timestamp: `git log --since="<started_at>" --oneline -- <feature_dir>/tasks/<WP_ID>.md`. If the file was modified, surface a warning: "WP<NN> was edited since the orchestration started — its prior PASS verdict may no longer be valid." This does not require a hard stop, just visibility before proceeding.
- Skip the rest of Phase 0 (feature directory discovery, design doc read, WP file read, dev server check are all handled by the restore)
- Jump directly to Phase 2 (skip Phase 1 entirely). If `current_wp` is set in the checkpoint (meaning a WP was in progress when the session ended), resume from that WP. Otherwise, skip all WPs up to and including `last_completed_wp` and start from the next WP.
- Clear the in-progress WP marker after resuming:
  ```bash
  spec-helper checkpoint-update <feature_dir_name> --current-wp "" --current-wp-status "" --json
  ```

**On restart:**
- Delete the checkpoint: `spec-helper checkpoint-delete <feature_dir_name> --json`
- Proceed with the normal Phase 0 flow below

### Find the feature directory

If $ARGUMENTS points to a `design/specs/NNN-*/` directory, use it directly.

If $ARGUMENTS points to a `WP*.md` file, the feature directory is two levels up.

If $ARGUMENTS is empty:

```
Glob: design/specs/*/tasks/WP*.md
```

Sort by modification time, take the most recent. The feature directory is two levels up from that file. Confirm:

```
AskUserQuestion:
  question: "Found work packages in <feature_dir>/tasks/. Execute these?"
  header: "Confirm feature"
  multiSelect: false
  options:
    - label: "Yes — execute it"
    - label: "No — let me specify the path"
      description: "Tell me the correct feature directory and I'll use that"
```

### Read the design doc

Read `<feature_dir>/design.md` to understand the overall architecture and constraints. This is the spec reviewer's reference document.

### Read all WP files

Read all `<feature_dir>/tasks/WP*.md` files in order. For each WP, extract:
- `work_package_id`
- `title`
- `lane`
- `depends_on`

Check WP statuses — warn if any WPs with `lane: done` or `lane: doing` appear ahead of `lane: planned` WPs (unexpected ordering).

### Dev server check (visual verification)

If any WP contains a `## Visual Verification` section, check for a running dev server:

```bash
# Linux
ss -tlnp 2>/dev/null | grep -E ':(3000|3001|3002|3003|4173|4200|4321|5000|5001|5173|5174|8000|8001|8080|8443|8888|9000) ' | head -5
# macOS fallback (if ss is unavailable)
lsof -nP -iTCP -sTCP:LISTEN 2>/dev/null | grep -E ':(3000|3001|3002|3003|4173|4200|4321|5000|5001|5173|5174|8000|8001|8080|8443|8888|9000) ' | head -5
```

If a server is found, derive the URL from the matched port (e.g., `http://localhost:3000`). If multiple ports match, prefer the first one and note the others.

If no server is found:
```
AskUserQuestion:
  question: "<N> WPs have visual verification scenarios but no dev server was detected. Visual checks require a running app."
  header: "Dev server"
  multiSelect: false
  options:
    - label: "I'll start the server now"
      description: "Pause while I start the dev server, then re-check"
    - label: "Skip visual verification for this run"
      description: "Execute WPs without visual checks — Visual line will show SKIPPED"
```

If the user starts the server, re-probe and confirm. If skipping, set a `visual_skip` flag for the run — executors will skip all visual capture and report SKIPPED.

### Write initial checkpoint

After Phase 0 completes (feature directory found, design doc and WP files read, dev server check done), record the base commit and create the checkpoint via `spec-helper`.

**Timing: capture `base_commit` BEFORE any WP execution begins.** This is the snapshot of HEAD before the orchestrator modifies any files, so that `git diff --name-only <base_commit> HEAD` after execution shows exactly what changed.

First, get the base commit:

```bash
git rev-parse --short HEAD
```

Then create the checkpoint:

```bash
spec-helper checkpoint-init <feature_dir_name> --tmpdir <tmpdir> --base-commit <sha> [--visual-skip] [--dev-server-url <url>] --json
```

The checkpoint is written to `<feature_dir>/tasks/.orchestrate-state.md` with validated schema.

**Gitignore the checkpoint:** Ensure `tasks/.orchestrate-state.md` is excluded from git. Check if `<feature_dir>/tasks/.gitignore` or `<feature_dir>/.gitignore` already contains this entry. If not, append `.orchestrate-state.md` to `<feature_dir>/tasks/.gitignore` (create the file if needed). This prevents the checkpoint file from being accidentally staged in WIP commits.

---

## Phase 1: Parse WPs and Select Start Point

Present the WP list to the user with IDs, titles, and current lanes:

```
WP01  planned  Set up data model
WP02  planned  Implement service layer
WP03  done     Write integration tests
```

**Auto-select the start point.** If any WP is in `lane: doing`, resume that WP first (it was left in progress); otherwise start from the first WP in `lane: planned`. Only ask the user if the state is genuinely ambiguous — e.g., multiple WPs in `doing`, a mix of `done` and `planned` WPs in unexpected order, or all WPs already `done`.

Skip WPs that are already in `lane: done`.

---

## Phase 2: Per-WP Execution Loop

For each WP from the start point to the last WP:

### Step 1: Announce the WP

Tell the user:
> **WP<NN>: <title>**
> Plan section: `<plan_section>`
> Depends on: `<depends_on or "none">`

Move this WP to `doing`:

```bash
spec-helper wp-move <feature_dir_name> <wp_id> doing
```

Where `<feature_dir_name>` is the directory name (e.g., `001-user-auth`), not the full path.

### Step 2: Create per-WP subdirectory

Use the run-level tmpdir from the checkpoint (`tmpdir` field from Phase 0's `checkpoint-init`). Do NOT call `get-skill-tmpdir` here — it creates a new directory each time, orphaning previous WP evidence.

Create a per-WP subdirectory: `<dir>/<wp_id>/` (e.g., `<dir>/wp01/`). Use these paths for subagent outputs within the subdirectory:
- Executor output: `<dir>/<wp_id>/executor.md`
- Spec reviewer output: `<dir>/<wp_id>/spec-reviewer.md`
- Visual reviewer output: `<dir>/<wp_id>/visual-review.md`
- Code reviewer output: `<dir>/<wp_id>/code-review.md`
- Integration reviewer output: `<dir>/<wp_id>/integration-review.md`
- Screenshots: `<dir>/<wp_id>/before-*.png`, `<dir>/<wp_id>/after-*.png`

Per-WP subdirectories preserve evidence across the full orchestration run. This allows post-hoc review, retry debugging, and screenshot comparison across WPs.

### Step 3: Select executor agent type

Before launching the executor, read the WP's objective and tasks to determine if a specialized agent is a better fit than `general-purpose`. Match the WP content against this table (more-specific rows are listed first and take priority):

<!-- PARALLEL: rules/common/agents.md also routes to these agents by user intent (not WP content) — add new agents to both, but signal wording differs intentionally -->
| WP content signals | Use `subagent_type` |
|---|---|
| FastAPI endpoint reading from Databricks via `databricks-sql-connector` | `engineering-backend-developer` |
| React, Vue, Angular, CSS, frontend components, UI implementation | `engineering-frontend-developer` |
| PySpark, Delta Lake, DeltaTable, cloudFiles/Auto Loader, medallion layers (raw/bronze/silver/gold), dbt models, Databricks workflows | `engineering-data-engineer` |
| FastAPI, REST API endpoints, Pydantic request/response models, async backend service | `engineering-backend-developer` |
| API docs, README, tutorials, developer documentation | `engineering-technical-writer` |
| Database schema, migrations, query optimization, ORM setup | `general-purpose` |

If the WP doesn't clearly match any row, use `general-purpose` (the default). When in doubt, prefer `general-purpose` — a wrong specialist is worse than a capable generalist.

### Step 4: Launch executor subagent

Read these files:
- `~/.claude/skills/mine.orchestrate/implementer-prompt.md`
- `~/.claude/skills/mine.orchestrate/tdd.md`

Launch a subagent of the type selected in Step 3 with this prompt (fill in bracketed values):

```
You are executing a single Work Package from an implementation plan.

## Work Package spec
<full WP*.md content>

## Design doc (architecture reference)
<full design.md content>

## Implementer instructions
<full implementer-prompt.md content>

## TDD reference
<full tdd.md content>

## Visual verification status
<If visual_skip is set>: Visual verification is SKIPPED for this run (no dev server). Do not attempt screenshot capture. Report "SKIPPED — no dev server (orchestrator)" in your visual verification output.
<Otherwise>: Dev server detected at <URL>. Proceed with visual verification if the WP specifies scenarios.

Write your structured result to: <executor temp file path>
Save screenshots to: <dir>/<wp_id>/
```

Wait for the subagent to complete. Read the executor temp file.

### Step 4.5: Capture changed files

After the executor completes, capture the list of files it changed. This list is used by the reviewers (Steps 7-8) and the commit step (Step 10).

```bash
git diff --name-only HEAD
git ls-files --others --exclude-standard
```

Always run both commands — the first catches modified/deleted tracked files, the second catches newly created untracked files. Combine both lists (deduped) and write to `<dir>/<wp_id>/changed-files.txt` (one path per line). This file is used by the reviewers (Steps 7-8) and the commit step (Step 10a). If both commands return empty, the executor may not have made any file changes — proceed to the spec reviewer, which will catch this if unexpected.

### Step 5: Launch spec reviewer subagent

Read `~/.claude/skills/mine.orchestrate/spec-reviewer-prompt.md`.

Launch a general-purpose subagent:

```
You are independently verifying a completed Work Package.

## Work Package spec
<full WP*.md content>

## Design doc (supplemental architecture reference)
<full design.md content>

## Changed files
<contents of changed-files.txt from Step 4.5>

## Executor result
<full executor temp file content>

## Spec reviewer instructions
<full spec-reviewer-prompt.md content>

Write your structured review to: <spec reviewer temp file path>
```

Wait for the subagent to complete. Read the spec reviewer temp file.

### Step 5.3: Test gate (independent test re-run)

After the spec reviewer completes (regardless of verdict), re-run the project's test suite independently. This separates test execution from the spec reviewer's code-inspection role.

1. **Discover the test command** using the discovery order from `rules/common/testing.md` (CLAUDE.md → CI config → task runners → documentation → ask user → fallback). Run from the repository root. If the executor's output includes the test command it used, prefer that command to avoid discovery drift between the executor and the test gate.
2. **Run the test command** and capture output.
3. **If tests fail**: note the failures. This does not override the spec reviewer's verdict — if the spec reviewer returned PASS but tests fail, record the test failure for the Step 9 summary. If the spec reviewer returned FAIL, the test failure reinforces the FAIL.
4. **Record the test result** in the per-WP temp directory: `<dir>/<wp_id>/test-gate.md` with the command used and output summary.

This step is informational — it provides independent test evidence for the Step 9 summary. The spec reviewer's verdict remains the primary gate for Step 5.5.

### Step 5.5: WARN fix loop (if spec reviewer returned WARN)

**If the spec reviewer returned WARN**, do NOT proceed to the visual reviewer or code review yet. Instead, attempt one automatic fix:

1. **Read the spec reviewer's WARN details** from the spec reviewer temp file
2. **Re-run the executor (Step 4)** with the `## Previous review feedback` section added to the executor prompt. Provide the **spec reviewer file path only** (code reviewer and visual reviewer have not run yet). Instruct the executor: "Fix only the gap identified by the spec reviewer. Read the spec reviewer file at the path below. Do not re-implement passing subtasks — read the existing code before making changes." If the WP has visual scenarios, add: "Re-capture baseline before-screenshots as if starting fresh — do not re-use before-screenshots from the prior attempt."
3. **Re-capture changed files (Step 4.5)** — the retry executor may have modified different files than the original run.
4. **Re-run the spec reviewer (Step 5)** on the executor's updated output
5. **Re-run the test gate (Step 5.3)** on the updated code
6. **If PASS after retry** → continue to Step 5.7 (visual reviewer) and then Step 7 (code reviewer) as normal. The WARN retry replaces only Steps 4, 4.5, 5, and 5.3.
7. **If still WARN after 1 retry** → escalate to the user with a distinct prompt that signals this is a persistent minor gap, not a hard failure:

```
AskUserQuestion:
  question: "WP<NN> has a minor gap that couldn't be resolved automatically: <WARN summary from spec reviewer>. The spec reviewer returned WARN on both the original and retry run."
  header: "WARN persist"
  multiSelect: false
  options:
    - label: "Fix and retry this WP"
      description: "Re-run the executor with the reviewer's notes (final attempt — if WARN persists, only 'Mark as blocked' or 'Stop here' will be offered)"
    - label: "Mark as blocked and skip"
      description: "Record the gap and move to the next WP"
    - label: "Stop here"
      description: "Pause execution; resume later with /mine.orchestrate"
```

If the user chose "Fix and retry" from the WARN persistence prompt, run one more executor cycle (Steps 4, 4.5, 5, 5.3). If the spec reviewer returns WARN again, present only "Mark as blocked and skip" and "Stop here" — do not offer another retry.

The WARN retry happens within a single WP's execution. The checkpoint is not updated during retries — it only updates after the final verdict.

**If the spec reviewer returned PASS** — continue to Step 5.7 (visual reviewer).

**If the spec reviewer returned FAIL** — skip to Step 9 to present the FAIL verdict.

### Step 5.7: Visual reviewer (conditional)

**Only run this step if the WP contains a `## Visual Verification` section with scenarios.** If the WP has no visual verification section, skip to Step 6 (the Visual line in Step 9 will show N/A).

**If `visual_skip` is set** (no dev server, decided in Phase 0), skip the Glob and visual reviewer entirely. Set Visual to SKIPPED with note "no dev server (orchestrator)" and proceed to Step 6. Do not launch the visual reviewer — there are no screenshots to review.

Read `~/.claude/skills/mine.orchestrate/visual-reviewer-prompt.md`.

Before launching the visual reviewer, discover screenshots by Globbing the per-WP temp directory:

```
Glob: <dir>/<wp_id>/*.png
```

This is more reliable than parsing screenshot paths from the executor's text output.

**Pre-launch vision check**: Before launching the visual reviewer subagent, read one of the discovered PNG files in the orchestrator's own context using the Read tool. If the image renders (you can describe its contents), vision is available — proceed. If the Read fails or returns uninterpretable binary data, set Visual to SKIPPED with note "no vision-capable model available" and proceed to Step 6.

If no `.png` files are found, distinguish the cause:
- If `visual_skip` is set → Visual = SKIPPED "no dev server (orchestrator)" (should not reach here — Step 5.7 short-circuits above, but defensive)
- If the executor reported all scenarios as SKIPPED → Visual = SKIPPED with the executor's reasons
- Otherwise (dev server was available, scenarios existed, but no screenshots) → Visual = FAIL "executor did not capture screenshots despite dev server being available — check executor output for errors"

Launch a `general-purpose` subagent:

```
You are reviewing screenshots from a frontend Work Package implementation.

## Work Package spec
<full WP*.md content — especially the Visual Verification table>

## Executor visual output
<the Visual verification section from the executor's result>

## Screenshot files to examine
<list each .png file path discovered by Glob>

## Visual reviewer instructions
<full visual-reviewer-prompt.md content>

Write your review to: <dir>/<wp_id>/visual-review.md
```

Wait for the subagent to complete. Read the visual reviewer output file.

**Fallback:** If the visual reviewer output file is empty or unparseable after the subagent completes: if the dev server was available and screenshots exist on disk, treat as FAIL with note "visual reviewer failed to produce output despite available screenshots." If no screenshots exist (executor reported SKIPPED), treat as WARN with note "visual verification inconclusive — no screenshots and no reviewer output."

**Visual verdict mapping:**

| Visual reviewer result | Impact on WP |
|------------------------|-------------|
| VERIFIED | No impact — proceed to code review |
| WARN | WP gets WARN; surface in Step 9 summary |
| FAIL | WP gets FAIL; surface to user at Step 9 gate |
| All scenarios SKIPPED (no dev server) | WP gets WARN (visual verification was unavailable) |

### Step 6: Classify deviations

Compare executor result, spec reviewer verdict, and visual reviewer verdict (if applicable):

| Condition | Action |
|-----------|--------|
| Executor PASS + Spec reviewer PASS (+ Visual VERIFIED or N/A) | Proceed to code review |
| Executor auto-fix deviation noted | Log it, proceed to code review |
| Visual WARN or Visual SKIPPED | Proceed to code review; surface warning to user after reviews |
| Spec reviewer FAIL or Visual FAIL | Mark WP FAIL; surface to user (gate at Step 9) |
| Executor BLOCKED (any reason) | Mark WP BLOCKED; surface to user (gate at Step 9) |
| Executor BLOCKED (architectural) | Mark WP BLOCKED with architectural flag; do not retry without plan change |

### Step 7: Code reviewer loop (MANDATORY)

**This step is MANDATORY. Do NOT skip it.** Run the code reviewer for every WP that reaches this point, regardless of how clean the executor or spec reviewer results look. A WP that skips code review cannot proceed to Step 9.

Launch a `code-reviewer` subagent (`Agent(subagent_type: "code-reviewer")`). Pass the changed file list from Step 4.5 in the prompt so the reviewer doesn't need to discover files itself:

```
Review these changed files: <changed file list from Step 4.5>
```

**Loop until clean:**
1. Run the code-reviewer subagent. Read its output.
2. For each CRITICAL or HIGH finding:
   - **Auto-fix** when the correct solution is unambiguous (clear bugs, missing type annotations, style violations, simple security issues)
   - **Defer** when the fix requires architectural judgment or business context
3. If any auto-fixes were applied, re-run the code-reviewer (max 3 iterations total)
4. Stop when: no CRITICAL/HIGH issues remain, only deferred findings are left, or 3 iterations reached

Write the final code-reviewer output to `<dir>/<wp_id>/code-review.md`.

**After the code-reviewer loop completes** (whether after 1 or 3 iterations), re-capture the changed file list — auto-fixes may have modified additional files:

```bash
git diff --name-only HEAD
git ls-files --others --exclude-standard
```

Update the WP's changed file list with the refreshed result. This updated list is used by Step 8 (integration reviewer) and Step 10a (commit).

**Verdict impact:** If CRITICAL or HIGH issues remain after 3 iterations that could not be auto-fixed, the WP verdict becomes FAIL regardless of the spec reviewer result.

### Step 8: Integration reviewer (MANDATORY)

**This step is MANDATORY. Do NOT skip it.** Run the integration reviewer for every WP that reaches this point, regardless of how clean prior results look. A WP that skips integration review cannot proceed to Step 9.

Launch an `integration-reviewer` subagent (`Agent(subagent_type: "integration-reviewer")`) once on the same changed files. Pass the refreshed changed file list (updated after the code-reviewer loop in Step 7) in the prompt:

```
Review these changed files: <refreshed changed file list>
```

The integration-reviewer checks for duplication, convention drift, misplacement, orphaned code, and design violations.

Write the output to `<dir>/<wp_id>/integration-review.md`.

Read the integration-reviewer output. Verdict routing: APPROVE and WARN both allow the WP to proceed (WARN is surfaced in the Step 9 summary as a note); only BLOCK triggers a WP FAIL verdict.

### Step 8.5: Review gate (GATE)

Before proceeding to Step 9, verify that both review output files exist:

```
Read: <dir>/<wp_id>/code-review.md
Read: <dir>/<wp_id>/integration-review.md
```

If either file is missing or empty, **do NOT proceed to Step 9**. Go back and run the missing reviewer. A WP summary without both reviews is invalid — the verdict will be overridden to FAIL with note "review step skipped."

### Step 9: Present results and gate

Present a summary:

```
**WP<NN>: <title> — <overall verdict>**

Spec review: PASS|WARN|FAIL
Visual: VERIFIED (N scenarios)|WARN|FAIL|SKIPPED|N/A
Code review: PASS|WARN|FAIL (N iterations) — NEVER "N/A" or "skipped"
Integration review: APPROVE|WARN|BLOCK — NEVER "N/A" or "skipped"

[Any deviations noted]
[Any WARN or FAIL details]
```

### Step 9.5: Gate decision and WP lane update

Gate based on verdict:

**PASS or WARN** — auto-continue to the next WP. Display the summary but do not ask for confirmation. Move this WP to `done`:

```bash
spec-helper wp-move <feature_dir_name> <wp_id> done
```

Note: by this point, any WARN from the spec reviewer has already been addressed by the fix loop at Step 5.5. A WARN verdict here means the fix loop succeeded (spec reviewer passed after retry) but other reviewers (code, integration, visual) raised minor concerns.

**FAIL or non-architectural BLOCKED** — ask the user:
```
AskUserQuestion:
  question: "WP<NN> failed. What next?"
  header: "WP<NN> gate"
  multiSelect: false
  options:
    - label: "Fix and retry this WP"
      description: "Re-run the executor with the reviewer's notes"
    - label: "Mark as blocked and skip"
      description: "Record the blocker and move to the next WP"
    - label: "Stop here"
      description: "Pause execution; resume later with /mine.orchestrate"
```

For FAIL/BLOCKED gate outcomes, **write a partial checkpoint update** before taking the gate action:

```bash
spec-helper checkpoint-update <feature_dir_name> --current-wp <WP_ID> --current-wp-status <retry_pending|blocked|stopped> --json
```

This ensures resume correctly returns to this WP instead of skipping it. Then:

- **Fix and retry**: lane stays `doing`; set `current_wp_status: retry_pending`. Re-run from Step 3 (which includes Step 4 executor + Step 4.5 file capture) with the `## Previous review feedback` section added to the executor prompt. For FAIL retries, provide **all three** reviewer file paths (spec reviewer, code reviewer, visual reviewer) since all reviewers have completed by this point. The executor reads these files directly — do not inline or truncate the reviewer output. Only provide the most recent attempt's reviewer file paths.
- **Mark as blocked and skip**: set `current_wp_status: blocked`. Move to `for_review` (signals needs human attention)
  ```bash
  spec-helper wp-move <feature_dir_name> <wp_id> for_review
  ```
- **Stop here**: set `current_wp_status: stopped`. Leave lane as `doing`.

**Architectural BLOCKED verdict only:**
```
AskUserQuestion:
  question: "WP<NN> is blocked on an architectural issue not covered by the plan. This requires a design change before retrying."
  header: "Architectural block"
  multiSelect: false
  options:
    - label: "Stop and revise the design"
      description: "Return to /mine.design or /mine.draft-plan to update the work packages"
    - label: "Stop here for now"
      description: "Pause execution; resume after the plan is updated"
```

Do not offer "Fix and retry" or "skip" for architectural blocks — retrying without a plan change will produce the same result.

### Step 10: WIP commit and checkpoint update

**This step runs only for PASS or WARN verdicts** (i.e., when the WP was moved to `done` in Step 9.5). For FAIL, BLOCKED, or user-chosen "Stop here" / "Fix and retry" outcomes, skip this step entirely — the checkpoint is not updated and no WIP commit is created.

#### 10a: Create WIP commit

Re-capture the changed file list immediately before staging to ensure it includes any files modified by the code-reviewer auto-fix loop or integration-reviewer feedback:

```bash
git diff --name-only HEAD
git ls-files --others --exclude-standard
```

Combine both lists (deduped) and write to `<dir>/<wp_id>/changed-files.txt` (overwriting the previous version). Do **not** use `git add -A` — it stages unrelated files (scratch files, editor backups, files from other features).

Stage using `--pathspec-from-file` to avoid shell argument limits:

```bash
git add --all --pathspec-from-file=<dir>/<wp_id>/changed-files.txt
git status --short
```

The `--all` flag ensures deletions and renames in the file list are staged correctly (without it, deleted paths would error). The `--pathspec-from-file` scopes the operation to only the listed paths, so `--all` does not stage unrelated files.

Review the `git status` output to confirm only expected files are staged.

```bash
git commit -m "WIP: <WP_ID> -- <WP title>"
```

If the commit succeeds, capture the new HEAD SHA:

```bash
git rev-parse --short HEAD
```

Store this SHA — it goes into the checkpoint verdict block below.

**If `git commit` fails** (e.g., nothing to commit because the WP made no file changes), note the failure and use `no-changes` as the commit value in the verdict block. This is not an error — some WPs may be documentation-only or configuration changes that were already committed by a subprocess.

#### 10b: Update checkpoint file

Update the checkpoint via `spec-helper` commands. The WIP commit (Step 10a) MUST complete before this step — the commit SHA goes into the verdict.

**Update header:**

```bash
spec-helper checkpoint-update <feature_dir_name> --last-completed-wp <WP_ID> --json
```

**Append verdict:**

```bash
spec-helper checkpoint-verdict <feature_dir_name> --wp-id <WP_ID> --title "<WP title>" --verdict <PASS|WARN> --commit <SHA from Step 10a> [--notes "<explanation>"] --json
```

Add `--notes` if the verdict is WARN (e.g., "test coverage low", "code review had unresolved HIGH findings").

### Loop to next WP

After the gate, continue with the next WP in sequence. Track: done (PASS), warned (WARN), blocked (BLOCKED), failed (FAIL).

---

## Phase 3: Post-Execution Review Pipeline

After all WPs are processed (or user chose "Stop here"), run a three-step review pipeline. Steps 1-2 are automatic (no user prompts unless blocking issues are found). The user is only prompted at the impl-review gate (if blocking) or at the final challenge results gate.

**All subagents in Phase 3 MUST run in foreground** (never set `run_in_background: true`). Several steps spawn their own parallel child subagents internally, which only works in foreground execution.

### Step 1: Summary (automatic)

Print the terminal kanban:

```bash
spec-helper status <feature_dir_name>
```

Then present a verdict table. **Read the checkpoint via `spec-helper checkpoint-read <feature_dir_name> --json`** and build the table from the `verdicts` array:

```
| WP   | Title   | Verdict |
|------|---------|---------|
| WP01 | ...     | PASS    |
| WP02 | ...     | WARN    |
...
```

### Step 2: Implementation review (automatic, gates on blocking issues)

Invoke `/mine.implementation-review <feature_dir>` automatically. The skill presents findings and returns — no user gate (the orchestrator handles all gate logic).

Read the review output. Extract the verdict (APPROVE, REQUEST_FIXES, or ABANDON) and any suggestions or blocking issues.

**If impl-review returns APPROVE** — note any non-blocking suggestions to surface later. Continue to Step 3 automatically.

**If impl-review returns REQUEST_FIXES or ABANDON** — prompt the user immediately:

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
1. Dispatch a fresh `general-purpose` subagent with: the impl-review findings, the relevant file paths, `<feature_dir>/design.md` content, `implementer-prompt.md` content, and `tdd.md` content. Instruct: "Fix only the listed blocking issues. Do not expand scope beyond these findings."
2. After the subagent completes, re-run `code-reviewer` and `integration-reviewer` on the fix diff in parallel (both in a single message)
3. Re-run `/mine.implementation-review <feature_dir>`
4. If it now returns APPROVE, continue to Step 3
5. If it still returns REQUEST_FIXES/ABANDON after 2 fix attempts, remove "Address fixes" from the gate — only offer "Stop here"

**On "Stop here":** Leave the checkpoint in place. The user can resume later. Do not delete the checkpoint.

### Step 3: Auto-challenge (automatic, always presents findings)

Determine the changed file list by diffing against `base_commit` (from the checkpoint):

```bash
git diff --name-only <base_commit> HEAD
```

If no files changed (all WPs were no-ops), skip the challenge and go directly to the final gate with a note that no files were changed.

**Dispatch the challenge as a single `general-purpose` subagent.** The orchestrator passes the following to the subagent, which runs `/mine.challenge` internally (the challenge skill spawns parallel critic subagents internally):

- `base_commit` from the checkpoint
- The changed file list from `git diff --name-only`
- Path to `<feature_dir>/design.md`
- Output path for findings (use `<tmpdir>/challenge-findings.md`)

The subagent prompt:

```
Run /mine.challenge --findings-out=<tmpdir>/challenge-findings.md --target-type=code <list of changed file paths as space-separated arguments>

The challenge will write structured findings to the specified path. The files were changed between commit <base_commit> and HEAD as part of executing work packages in <feature_dir>. The design doc is at <feature_dir>/design.md.
```

After the subagent completes, read `<tmpdir>/challenge-findings.md`.

### Final gate: Combined review results

Present the combined findings from implementation review and challenge. **The options presented depend on finding severity:**

**If challenge findings include CRITICAL or HIGH severity:** suppress "Accept and ship" — only offer "Address findings" and "Stop here" until no CRITICAL/HIGH remain.

```
AskUserQuestion:
  question: "Challenge complete: <N findings, highest severity>. Implementation review: <APPROVE + any non-blocking suggestions summary>. What next?"
  header: "Review results"
  multiSelect: false
  options:
    - label: "Address findings"
      description: "Dispatch a fresh executor subagent with the findings, then re-review"
    - label: "Accept and ship"
      description: "Findings noted — proceed to /mine.ship (only shown when no CRITICAL/HIGH findings remain)"
    - label: "Stop here"
      description: "Pause; I'll address findings manually"
```

**On "Address findings":**
1. Dispatch a fresh `general-purpose` subagent with: the challenge findings and any impl-review suggestions, the relevant file paths, `<feature_dir>/design.md` content, `implementer-prompt.md` content, and `tdd.md` content. Instruct: "Fix only the listed findings. Do not expand scope beyond these findings."
2. After the subagent completes, re-run `code-reviewer` and `integration-reviewer` on the fix diff in parallel (both in a single message)
3. Re-run the challenge (same dispatch pattern as Step 3)
4. Present the final gate again with updated findings (re-evaluate severity for option suppression)
5. After 2 "Address findings" iterations, remove the "Address findings" option — only offer "Accept and ship" (if no CRITICAL/HIGH) or "Stop here"

**On "Accept and ship":** Invoke `/mine.ship`.

**On "Stop here":** Leave the checkpoint in place. The user can resume later.

### Delete checkpoint

After the user chooses "Accept and ship" (and `/mine.ship` completes) or after the "Address findings" loop results in "Accept and ship", delete the checkpoint. Do NOT delete the checkpoint if the user chose "Stop here" — it must persist for future resume.

```bash
spec-helper checkpoint-delete <feature_dir_name> --json
```

This is the final cleanup step. The checkpoint is runtime state — once the orchestration run completes and the user has passed through the review results gate, it is no longer needed. If the user chose "Stop here" at any earlier gate (during Phase 2 or at the impl-review gate), the checkpoint persists for future resume.
