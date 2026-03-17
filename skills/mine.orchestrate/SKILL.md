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

Initialize a consecutive WARN counter at 0.

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

Use these paths for subagent outputs:
- Executor output: `<dir>/executor.md`
- Spec reviewer output: `<dir>/spec-reviewer.md`
- Code reviewer output: `<dir>/code-review.md`
- Integration reviewer output: `<dir>/integration-review.md`

These paths are **reused each WP iteration** — each WP's executor output overwrites the previous. This is safe because the files are read immediately within the same iteration before the loop advances. Per-WP output is not retained on disk after the next WP begins.

### Step 3: Select executor agent type

Before launching the executor, read the WP's objective and tasks to determine if a specialized agent is a better fit than `general-purpose`. Match the WP content against this table:

| WP content signals | Use `subagent_type` |
|---|---|
| React, Vue, Angular, CSS, frontend components, UI implementation | `Frontend Developer` |
| ML model, training pipeline, embeddings, AI integration | `AI Engineer` |
| CI/CD, Docker, Terraform, infrastructure, deployment pipeline | `DevOps Automator` |
| MCP server, MCP tools, Model Context Protocol | `MCP Builder` |
| API docs, README, tutorials, developer documentation | `Technical Writer` |
| Security hardening, auth implementation, encryption, threat mitigation | `Security Engineer` |
| Database schema, migrations, query optimization, ORM setup | `DB Auditor` |
| Rapid prototype, proof of concept, MVP | `Rapid Prototyper` |

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

Write your structured result to: <executor temp file path>
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

### Step 6: Classify deviations

Compare executor result and spec reviewer verdict:

| Condition | Action |
|-----------|--------|
| Executor PASS + Spec reviewer PASS | Proceed to code review |
| Executor auto-fix deviation noted | Log it, proceed to code review |
| Spec reviewer WARN | Proceed to code review; surface warning to user after reviews |
| Spec reviewer FAIL | Mark WP FAIL; surface to user (gate at Step 9) |
| Executor BLOCKED (any reason) | Mark WP BLOCKED; surface to user (gate at Step 9) |
| Executor BLOCKED (architectural) | Mark WP BLOCKED with architectural flag; do not retry without plan change |

### Step 7: Code reviewer loop

(Run this even if spec reviewer has WARNs — still useful to catch code issues early.)

Launch a `code-reviewer` subagent (`Agent(subagent_type: "code-reviewer")`) to review the files changed by the executor. The code-reviewer agent uses `git diff --name-only` to find changed files and runs static analysis tools (ruff, pyright, etc.) as appropriate.

**Loop until clean:**
1. Run the code-reviewer subagent. Read its output.
2. For each CRITICAL or HIGH finding:
   - **Auto-fix** when the correct solution is unambiguous (clear bugs, missing type annotations, style violations, simple security issues)
   - **Defer** when the fix requires architectural judgment or business context
3. If any auto-fixes were applied, re-run the code-reviewer (max 3 iterations total)
4. Stop when: no CRITICAL/HIGH issues remain, only deferred findings are left, or 3 iterations reached

Write the final code-reviewer output to `<dir>/code-review.md`.

**Verdict impact:** If CRITICAL or HIGH issues remain after 3 iterations that could not be auto-fixed, the WP verdict becomes FAIL regardless of the spec reviewer result.

### Step 8: Integration reviewer

Launch an `integration-reviewer` subagent (`Agent(subagent_type: "integration-reviewer")`) once on the same changed files. The integration-reviewer checks for duplication, convention drift, misplacement, orphaned code, and design violations.

Write the output to `<dir>/integration-review.md`.

Read the integration-reviewer output. If it returns BLOCK verdict, the WP verdict becomes FAIL.

### Step 9: Present results and gate

Present a summary:

```
**WP<NN>: <title> — <overall verdict>**

Spec review: PASS|WARN|FAIL
Code review: PASS|WARN|FAIL (N iterations)
Integration review: APPROVE|WARN|BLOCK

[Any deviations noted]
[Any WARN or FAIL details]
```

Then gate based on verdict:

**PASS or WARN** — auto-continue to the next WP. Display the summary but do not ask for confirmation. Move this WP to `done` and continue the loop with the next WP (starting from Step 1 — announce, set up temp dir, then execute). If WARN, increment the consecutive WARN counter; if PASS, reset it to 0.

**WARN accumulation checkpoint:** If the consecutive WARN counter reaches 3, pause and ask:
```
AskUserQuestion:
  question: "3 consecutive WPs received WARN verdicts. This may indicate a systemic issue. Continue or investigate?"
  header: "WARN accumulation"
  multiSelect: false
  options:
    - label: "Continue — warnings are acceptable"
      description: "Reset the counter and keep going"
    - label: "Stop and investigate"
      description: "Pause execution to review the pattern"
```
Post-choice behavior:
- **"Continue — warnings are acceptable"**: Reset the consecutive WARN counter to 0 and continue the loop with the next WP (the current WP is already moved to `done` before the checkpoint triggers).
- **"Stop and investigate"**: Pause the execution loop. The current WP remains in `done` (it passed, just with warnings). Return control to the user with a summary of the WARN pattern across the last 3 WPs so they can decide how to proceed (e.g., fix issues and re-run, adjust the plan, or resume as-is).

A PASS verdict resets the consecutive WARN counter to zero.

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

### Step 10: Update WP lane

After the gate decision:

- **Continue / PASS / WARN**: move to `done`
  ```bash
  spec-helper wp-move <feature_dir_name> <wp_id> done
  ```
- **Fix and retry**: lane stays `doing`; re-run from Step 3
- **Mark as blocked and skip**: move to `for_review` (signals needs human attention)
  ```bash
  spec-helper wp-move <feature_dir_name> <wp_id> for_review
  ```
- **Stop here**: leave lane as `doing`

### Loop to next WP

After the gate, continue with the next WP in sequence. Track: done (PASS), warned (WARN), blocked (BLOCKED), failed (FAIL).

---

## Phase 3: Post-Execution Handoff

After all WPs are processed (or user chose "Stop here"), print the terminal kanban:

```bash
spec-helper status <feature_dir_name>
```

Then present a summary table:

```
| WP   | Title   | Verdict |
|------|---------|---------|
| WP01 | ...     | PASS    |
| WP02 | ...     | WARN    |
...
```

Then offer:

```
AskUserQuestion:
  question: "Execution complete. Run implementation review?"
  header: "Next step"
  multiSelect: false
  options:
    - label: "Yes — run /mine.implementation-review"
      description: "Post-execution quality gate across all changed files"
    - label: "No — I'll review manually"
      description: "Stop here"
```

If "Yes": invoke `/mine.implementation-review <feature_dir>` directly.
