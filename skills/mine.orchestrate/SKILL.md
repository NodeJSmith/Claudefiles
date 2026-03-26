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

## Phase 0: Locate the Work Packages

### Check for existing checkpoint (resume detection)

Before anything else, determine the feature directory from `$ARGUMENTS` (using the same logic as "Find the feature directory" below — directory, WP file, or most-recently-modified glob). Do **not** present the confirmation AskUserQuestion at this point — just resolve the path silently. Then check for an existing checkpoint file:

```
Read: <feature_dir>/tasks/.orchestrate-state.md
```

**If the file does not exist** — proceed to "Find the feature directory" and continue the normal fresh-start flow.

**If the file exists** — read it and extract all key-value fields from the header and the verdicts section. Then determine staleness: parse `started_at` and compare to the current time. If `started_at` is older than 24 hours, note that in the prompt and default to "Restart fresh".

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
- Reset `warn_counter` to 0 (consecutive counter loses meaning across sessions)
- Verify `tmpdir` exists. If it does not, run `get-skill-tmpdir mine-orchestrate` to create a new one and note that subagent outputs from prior WPs are gone (code changes are in git; verdicts are in the checkpoint)
- Re-read `<feature_dir>/design.md` and all `<feature_dir>/tasks/WP*.md` files (they may have been edited between sessions)
- Skip the rest of Phase 0 (feature directory discovery, design doc read, WP file read, dev server check are all handled by the restore)
- Jump directly to Phase 2 (skip Phase 1 entirely). If `current_wp` is set in the checkpoint (meaning a WP was in progress when the session ended), resume from that WP. Otherwise, skip all WPs up to and including `last_completed_wp` and start from the next WP. Clear `current_wp` and `current_wp_status` from the checkpoint header after resuming.

**On restart:**
- Delete the checkpoint file: `<feature_dir>/tasks/.orchestrate-state.md`
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
ss -tlnp 2>/dev/null | grep -E ':(3000|3001|4200|5000|5173|8000|8080|8888) ' | head -5
# macOS fallback (if ss is unavailable)
lsof -nP -iTCP -sTCP:LISTEN 2>/dev/null | grep -E ':(3000|3001|4200|5000|5173|8000|8080|8888) ' | head -5
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

After Phase 0 completes (feature directory found, design doc and WP files read, dev server check done), record the base commit and write the initial checkpoint file at `<feature_dir>/tasks/.orchestrate-state.md`.

**Timing: capture `base_commit` BEFORE any WP execution begins.** This is the snapshot of HEAD before the orchestrator modifies any files, so that `git diff --name-only <base_commit> HEAD` after execution shows exactly what changed.

First, get the base commit:

```bash
git rev-parse --short HEAD
```

Then write the checkpoint file with this exact format:

```markdown
# Orchestration State

feature_dir: <feature_dir relative path, e.g. design/specs/008-orchestrate-resilience>
tmpdir: <tmpdir path from get-skill-tmpdir>
visual_skip: <true|false>
dev_server_url: <URL or "none">
warn_counter: 0
last_completed_wp: none
started_at: <current ISO 8601 timestamp, e.g. 2026-03-25T14:30:00>
base_commit: <short SHA from above>

## Verdicts
```

The `## Verdicts` section starts empty — verdict blocks will be appended after each WP completes.

**Gitignore the checkpoint:** Ensure `tasks/.orchestrate-state.md` is excluded from git. Check if `<feature_dir>/tasks/.gitignore` or `<feature_dir>/.gitignore` already contains this entry. If not, append `.orchestrate-state.md` to `<feature_dir>/tasks/.gitignore` (create the file if needed). This prevents `git add -A` in WIP commits from staging the checkpoint file.

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

### Step 2: Create temp directory

Run `get-skill-tmpdir mine-orchestrate` and note the directory path.

Create a per-WP subdirectory: `<dir>/<wp_id>/` (e.g., `<dir>/wp01/`). Use these paths for subagent outputs within the subdirectory:
- Executor output: `<dir>/<wp_id>/executor.md`
- Spec reviewer output: `<dir>/<wp_id>/spec-reviewer.md`
- Visual reviewer output: `<dir>/<wp_id>/visual-review.md`
- Code reviewer output: `<dir>/<wp_id>/code-review.md`
- Integration reviewer output: `<dir>/<wp_id>/integration-review.md`
- Screenshots: `<dir>/<wp_id>/before-*.png`, `<dir>/<wp_id>/after-*.png`

Per-WP subdirectories preserve evidence across the full orchestration run. This allows post-hoc review, retry debugging, and screenshot comparison across WPs.

### Step 3: Select executor agent type

Before launching the executor, read the WP's objective and tasks to determine if a specialized agent is a better fit than `general-purpose`. Match the WP content against this table:

| WP content signals | Use `subagent_type` |
|---|---|
| React, Vue, Angular, CSS, frontend components, UI implementation | `engineering-frontend-developer` |
| ML model, training pipeline, embeddings, AI integration | `engineering-ai-engineer` |
| CI/CD, Docker, Terraform, infrastructure, deployment pipeline | `engineering-devops-automator` |
| MCP server, MCP tools, Model Context Protocol | `specialized-mcp-builder` |
| API docs, README, tutorials, developer documentation | `engineering-technical-writer` |
| Security hardening, auth implementation, encryption, threat mitigation | `engineering-security-engineer` |
| Database schema, migrations, query optimization, ORM setup | `general-purpose` |
| Rapid prototype, proof of concept, MVP | `engineering-rapid-prototyper` |

If the WP doesn't clearly match any row, use `general-purpose` (the default). When in doubt, prefer `general-purpose` — a wrong specialist is worse than a capable generalist.

### Step 4: Launch executor subagent

Read these files:
- `~/.claude/skills/mine.orchestrate/phase-executor-prompt.md`
- `~/.claude/skills/mine.orchestrate/implementer-prompt.md`
- `~/.claude/skills/mine.orchestrate/tdd.md`

Launch a subagent of the type selected in Step 3 with this prompt (fill in bracketed values):

```
You are executing a single Work Package from an implementation plan.

## Work Package spec
<full WP*.md content>

## Design doc (architecture reference)
<full design.md content>

## Phase executor instructions
<full phase-executor-prompt.md content>

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

### Step 5: Launch spec reviewer subagent

Read `~/.claude/skills/mine.orchestrate/spec-reviewer-prompt.md`.

Launch a general-purpose subagent:

```
You are independently verifying a completed Work Package.

## Work Package spec
<full WP*.md content>

## Design doc (architecture reference)
<full design.md content>

## Executor result
<full executor temp file content>

## Spec reviewer instructions
<full spec-reviewer-prompt.md content>

Write your structured review to: <spec reviewer temp file path>
```

Wait for the subagent to complete. Read the spec reviewer temp file.

### Step 5.5: WARN fix loop (if spec reviewer returned WARN)

**If the spec reviewer returned WARN**, do NOT proceed to the visual reviewer or code review yet. Instead, attempt one automatic fix:

1. **Read the spec reviewer's WARN details** from the spec reviewer temp file
2. **Re-run the executor (Step 4)** with the `## Previous review feedback` section added to the executor prompt. Populate only the **Spec reviewer** section (code reviewer and visual reviewer have not run yet). Truncate feedback to 50 lines if it exceeds that length. Only include the most recent attempt's feedback (not accumulated from prior attempts).
3. **Re-run the spec reviewer (Step 5)** on the executor's updated output
4. **If PASS after retry** → continue to Step 5.7 (visual reviewer) and then Step 7 (code reviewer) as normal. The WARN retry replaces only Steps 4 and 5.
5. **If still WARN after 1 retry** → escalate to the user using the FAIL gate at Step 9.5 (same options as FAIL). One retry that can't fix a minor gap means either the gap isn't executor-fixable or the spec reviewer's bar is miscalibrated — either way, escalate.

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

This is more reliable than parsing screenshot paths from the executor's text output. If no `.png` files are found, distinguish the cause:
- If `visual_skip` is set → Visual = SKIPPED "no dev server (orchestrator)" (should not reach here — Step 5.7 short-circuits above, but defensive)
- If the executor reported all scenarios as SKIPPED → Visual = SKIPPED with the executor's reasons
- Otherwise (dev server was available, scenarios existed, but no screenshots) → Visual = WARN "executor did not capture screenshots — check executor output for errors"

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

**Fallback:** If the visual reviewer output file is empty or unparseable after the subagent completes, treat as WARN with note "visual verification inconclusive — reviewer produced no output."

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

Launch a `code-reviewer` subagent (`Agent(subagent_type: "code-reviewer")`) to review the files changed by the executor. The code-reviewer agent uses `git diff --name-only` to find changed files and runs static analysis tools (ruff, pyright, etc.) as appropriate.

**Loop until clean:**
1. Run the code-reviewer subagent. Read its output.
2. For each CRITICAL or HIGH finding:
   - **Auto-fix** when the correct solution is unambiguous (clear bugs, missing type annotations, style violations, simple security issues)
   - **Defer** when the fix requires architectural judgment or business context
3. If any auto-fixes were applied, re-run the code-reviewer (max 3 iterations total)
4. Stop when: no CRITICAL/HIGH issues remain, only deferred findings are left, or 3 iterations reached

Write the final code-reviewer output to `<dir>/<wp_id>/code-review.md`.

**Verdict impact:** If CRITICAL or HIGH issues remain after 3 iterations that could not be auto-fixed, the WP verdict becomes FAIL regardless of the spec reviewer result.

### Step 8: Integration reviewer (MANDATORY)

**This step is MANDATORY. Do NOT skip it.** Run the integration reviewer for every WP that reaches this point, regardless of how clean prior results look. A WP that skips integration review cannot proceed to Step 9.

Launch an `integration-reviewer` subagent (`Agent(subagent_type: "integration-reviewer")`) once on the same changed files. The integration-reviewer checks for duplication, convention drift, misplacement, orphaned code, and design violations.

Write the output to `<dir>/<wp_id>/integration-review.md`.

Read the integration-reviewer output. If it returns BLOCK verdict, the WP verdict becomes FAIL.

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

For FAIL/BLOCKED gate outcomes, **write a partial checkpoint update** before taking the gate action. Update the checkpoint header to set `current_wp: <WP_ID>` and `current_wp_status: retry_pending|blocked|stopped` (matching the gate choice). This ensures resume correctly returns to this WP instead of skipping it. Then:

- **Fix and retry**: lane stays `doing`; set `current_wp_status: retry_pending`. Re-run from Step 3 with the `## Previous review feedback` section added to the executor prompt. For FAIL retries, populate **all three** reviewer sections (spec reviewer, code reviewer, visual reviewer) since all reviewers have completed by this point. Truncate feedback to 50 lines if it exceeds that length. Only include the most recent attempt's feedback.
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

Stage changes and create a WIP commit. **Before committing, verify the staging area:**

```bash
git add -A
git status --short
```

Review the `git status` output. If any files appear that are clearly unrelated to this WP (scratch files, editor backups, files from other features), unstage them with `git reset HEAD <file>` before committing. When in doubt, keep the file staged — the WIP commits will be squashed before merge.

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

Update the checkpoint file at `<feature_dir>/tasks/.orchestrate-state.md`.

**Header rewrite:** Rewrite the entire key-value header section (everything from `feature_dir:` through `base_commit:`) with current values. Update `last_completed_wp` to this WP's ID. Increment `warn_counter` if the final verdict was WARN (for tracking purposes — this no longer gates behavior).

**Verdict append:** Append a new verdict block to the `## Verdicts` section. Never rewrite or modify previous verdict blocks. Use this exact format:

```markdown

### <WP ID> — <WP title>
verdict: <PASS|WARN|FAIL|BLOCKED>
commit: <short SHA from Step 10a>
```

If the verdict is WARN, add an optional `notes:` line with a brief explanation (e.g., "test coverage low", "code review had unresolved HIGH findings").

**Ordering guarantee:** The WIP commit (Step 10a) MUST complete before the checkpoint write (Step 10b). The checkpoint's `commit:` field must contain the actual SHA from the WIP commit, never a placeholder like "pending".

### Loop to next WP

After the gate, continue with the next WP in sequence. Track: done (PASS), warned (WARN), blocked (BLOCKED), failed (FAIL).

---

## Phase 3: Post-Execution Review Pipeline

After all WPs are processed (or user chose "Stop here"), run a three-step review pipeline. Steps 1-2 are automatic (no user prompts unless blocking issues are found). The user is only prompted at the impl-review gate (if blocking) or at the final challenge results gate.

### Step 1: Summary (automatic)

Print the terminal kanban:

```bash
spec-helper status <feature_dir_name>
```

Then present a verdict table. **Reconstruct this table from the verdict blocks in the checkpoint file** — read `<feature_dir>/tasks/.orchestrate-state.md` and build the table from the `## Verdicts` section:

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
1. Dispatch a fresh `general-purpose` subagent with: the impl-review findings, the relevant file paths, `<feature_dir>/design.md` content, and `implementer-prompt.md` content. Instruct: "Fix only the listed blocking issues. Do not expand scope beyond these findings."
2. After the subagent completes, re-run `code-reviewer` and `integration-reviewer` on the fix diff
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

**Dispatch the challenge as a single `general-purpose` subagent using the Opus model (`model: "opus"`).** The orchestrator passes the following to the subagent, which runs `/mine.challenge` internally (the challenge skill spawns its own three nested critic subagents):

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

Present the combined findings from implementation review and challenge:

```
AskUserQuestion:
  question: "Challenge complete: <N findings, highest severity>. Implementation review: <APPROVE + any non-blocking suggestions summary>. What next?"
  header: "Review results"
  multiSelect: false
  options:
    - label: "Address findings"
      description: "Dispatch a fresh executor subagent with the findings, then re-review"
    - label: "Accept and ship"
      description: "Findings noted — proceed to /mine.ship"
    - label: "Stop here"
      description: "Pause; I'll address findings manually"
```

**On "Address findings":**
1. Dispatch a fresh `general-purpose` subagent with: the challenge findings and any impl-review suggestions, the relevant file paths, `<feature_dir>/design.md` content, and `implementer-prompt.md` content. Instruct: "Fix only the listed findings. Do not expand scope beyond these findings."
2. After the subagent completes, re-run `code-reviewer` and `integration-reviewer` on the fix diff
3. Re-run the challenge (same dispatch pattern as Step 3)
4. Present the final gate again with updated findings
5. After 2 "Address findings" iterations, remove the "Address findings" option — only offer "Accept and ship" or "Stop here"

**On "Accept and ship":** Invoke `/mine.ship`.

**On "Stop here":** Leave the checkpoint in place. The user can resume later.

### Delete checkpoint

After the user chooses "Accept and ship" (and `/mine.ship` completes) or after the "Address findings" loop results in "Accept and ship", delete the checkpoint file. Do NOT delete the checkpoint if the user chose "Stop here" — it must persist for future resume.

```bash
rm -f <feature_dir>/tasks/.orchestrate-state.md
```

This is the final cleanup step. The checkpoint is runtime state — once the orchestration run completes and the user has passed through the review results gate, it is no longer needed. If the user chose "Stop here" at any earlier gate (during Phase 2 or at the impl-review gate), the checkpoint persists for future resume.
