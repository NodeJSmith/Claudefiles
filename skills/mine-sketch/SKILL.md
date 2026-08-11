---
name: mine-sketch
description: "Use when the user says: \"sketch this out\", \"sketch this feature\", \"lightweight plan\", \"quick design and tasks\", or wants structured planning without full caliper ceremony. Produces a lightweight design.md + task files for mine-orchestrate."
user-invocable: true
---

# Sketch

Lightweight structured planning — produces a design.md with FRs/ACs and task files for mine-orchestrate, without the full ceremony of mine-define + mine-plan. For tasks that need structure but not rigor: multiple files, real design decisions, well-understood territory.

## Arguments

$ARGUMENTS — a description of what to build, or a feature directory path. Can be:
- A feature idea: `/mine-sketch "add webhook support to notifications"`
- A feature directory path: `/mine-sketch design/specs/005-webhooks/` (resumes existing sketch)
- Empty: ask the user what they want to build

---

## Phase 1: Understand & Scope

If $ARGUMENTS is empty, ask:

> What would you like to build or change?

If $ARGUMENTS does not point to an existing spec directory, paraphrase the request in one sentence to confirm understanding.

### Initialize CFL tracking

Derive a `<slug>` from the request (kebab-case, max 40 chars).

If $ARGUMENTS pointed to an existing spec directory, extract its number:

```bash
cfl spec status --spec <NNN>
```

If that succeeds, use the existing spec. If it errors with `spec_not_found`, tell the user the directory predates cfl tracking and proceed without it (skip all `cfl` calls for the rest of this run).

Otherwise, create a new spec:

```bash
cfl spec init <slug>
```

Record `dir` as the feature directory and `number` as `<spec_number>`.

### Start run

Skip this section if cfl tracking was disabled above (no `<spec_number>` set).

```bash
cfl run status --spec <spec_number>
```

- If the output has `"exists": true` — an active run exists. Record the `run_id` and continue (no new run needed).
- If the output has `"exists": false` — try resuming a stopped run:

```bash
cfl run resume --spec <spec_number>
```

If this succeeds, the stopped run is now active. If it errors with `no_stopped_run`, create a new run:

```bash
cfl run start --phase sketch --base-commit $(git rev-parse --short HEAD) --spec <spec_number>
cfl event sketch.started --spec <spec_number>
```

### Check for resume

If $ARGUMENTS pointed to an existing spec directory, check that directory for `design.md` — if present and has `**Mode:** sketch`, this is a resume. Read it before skipping Phase 2. If the feature owns resumable work state across invocations but the design lacks `## Operational Lifecycle` or any required lifecycle decision, run Phase 2's mandatory lifecycle clarification and update the design first. Otherwise skip directly to Phase 3 (task breakdown); `<spec_number>` and `run_id` are already set from the sections above, so `cfl` calls in Phases 3-5 work normally. Skip the rest of Phase 1 and all remaining Phase 2 work.

Otherwise, continue to the codebase scan below.

### Quick codebase scan

Read 3-8 files relevant to the change. Focus on:
- Files that will be modified (understand current structure)
- Adjacent files that establish conventions
- Test files that cover the area

This replaces the full researcher dispatch. Keep it fast — you're looking for conventions and constraints, not doing deep investigation.

### Escalation check

If the scan reveals more than expected, stop and ask before designing. Concrete signals:
- The change touches more services/packages than the request implied (cross-system dependencies you didn't expect).
- It requires modifying a shared or foundational module with many callers.
- It surfaces an architectural question with no single obvious answer (unclear interfaces, competing approaches).

If any apply:

```
AskUserQuestion:
  question: "The codebase scan found more complexity than expected — <one-sentence finding>. How should we proceed?"
  header: "Escalate?"
  multiSelect: false
  options:
    - label: "Upgrade to full caliper"
      description: "Stop here — invoke /mine-define for a full investigation and design"
    - label: "Continue with sketch"
      description: "Proceed with the lighter sketch despite the finding"
```

On "Upgrade to full caliper": tell the user to invoke `/mine-define` and stop.

On "Continue with sketch": proceed to Phase 2 as normal.

---

## Phase 2: Design

### Clarify (if needed)

Ask 1-2 questions **only** if something is genuinely uncertain and would change the design. Skip if the approach is obvious from the codebase scan.

One clarification is mandatory when the change owns resumable work state across invocations. Propose and confirm: completion, retry eligibility and bounds, user-action recovery or deliberately terminal states, repeated-run convergence, visible accounting, and a realistic local validation scenario. If those decisions cannot stay lightweight, upgrade to `/mine-define` rather than guessing.

### Write design.md

Read `${CLAUDE_CONFIG_DIR:-~/.claude}/skills/mine-sketch/design-template.md` and use it as the template.

Populate from the codebase scan and the user's request. Be specific — reference actual file paths and patterns found.

Skip if cfl tracking was disabled in Phase 1 (no `<spec_number>` set):

```bash
cfl event sketch.design-written --spec <spec_number>
```

---

## Phase 3: Task Breakdown

### Write context.md

Write `<feature_dir>/tasks/context.md`:

```markdown
# Context: <Feature Name>

## Problem & Motivation
<From the design doc's Problem section. 2-4 sentences.>

## Key Decisions
<Architecture decisions from the Approach section. Numbered list.>

## Constraints
<Things the executor must NOT do. Non-goals. Patterns to avoid.>
```

### Write task files

Write each task to `<feature_dir>/tasks/T{NN}-{slug}.md` using this format:

```markdown
---
task_id: "T01"
title: "<imperative description>"
status: "planned"
depends_on: []
implements: ["FR#1", "AC#1"]
---

## Target Files

- create: `path/to/new_file.py`
- modify: `path/to/existing.py`

## Prompt

<Self-contained build instructions. Name exact file paths. Reference design doc sections by heading. Must work for a fresh executor subagent with only context.md and this task file.>

## Verify

- [ ] FR#1: <concrete observable criterion>
- [ ] AC#1: <verifiable by running a local command>
```

### Task file rules

- **Minimum tasks: 1.** Let the work's complexity determine the count. Single-task sketches are fine for focused changes.
- **Every FR and AC** from the design doc must appear in at least one task's `implements` field and have a corresponding Verify criterion.
- **Operational lifecycle verification**: When the design contains `## Operational Lifecycle`, responsible tasks must verify repeated failure, bounded retry/termination, user-action recovery or deliberately terminal behavior, and visible population accounting through assembled repeated-run tests. Isolated status-transition tests are insufficient.
- **Target Files are required** — they drive the orchestrator's scope boundaries and reviewer injection.
- **Prompt must be self-contained** — a fresh subagent with only context.md and the task file must be able to execute it.
- **Task ordering**: foundational types before consumers. No task may depend on outputs from a higher-numbered task.

Skip if cfl tracking was disabled in Phase 1 (no `<spec_number>` set):

```bash
cfl event sketch.tasks-written --spec <spec_number>
```

---

## Phase 4: Comb

Run the fine-toothed comb on the design doc and task files together.

Skip the cfl dispatch/gate calls below if cfl tracking was disabled in Phase 1 (no `<spec_number>` set). The comb itself still runs regardless.

```bash
cfl dispatch sketch-comb --agent-type fine-toothed-comb --model sonnet --spec <spec_number>
```

Record the `dispatch_id`.

```
Agent:
  subagent_type: fine-toothed-comb
  model: sonnet
  prompt: |
    Read this design file and its task files:
    - Design: <design_doc_path>
    - Tasks: <feature_dir>/tasks/

    Go over them with a fine-toothed comb. Check:
    - Design and tasks are consistent (no contradictions, no drift)
    - Every FR/AC is covered by at least one task's implements + Verify
    - When Operational Lifecycle is present, tasks verify assembled repeated-run behavior, retry bounds/termination, recovery or deliberately terminal states, and visible accounting
    - Target Files are complete (no file referenced in Prompt but missing from Target Files)
    - Prompts are self-contained (no "as discussed" or assumed context)

    Define blocking as: a direct inconsistency, missing coverage, or an error that would mislead execution. A section that could be more detailed is minor, not blocking.
```

After the comb completes:

```bash
cfl dispatch end <dispatch_id>
cfl gate sketch-comb --verdict <v> --spec <spec_number> --data '{"blocking": <N>, "minor": <M>}'
```

Verdict: `blocking` = 0 → PASS, `blocking` > 0 → FAIL.

Read `${CLAUDE_CONFIG_DIR:-~/.claude}/skills/mine-comb/comb-gate.md` and apply it with:
- **`<header>`**: `Sketch comb`
- **`minor_blocks`**: `false`
- **`<re_review_instructions>`**: fix the findings in the design doc and/or task files, then re-run this phase

---

## Phase 5: Handoff

Present the design doc and task file paths to the user, then:

```
AskUserQuestion:
  question: "Sketch complete — design.md and task files are ready. What next?"
  header: "Handoff"
  multiSelect: false
  options:
    - label: "Execute via /mine-orchestrate"
      description: "Advance to orchestrate phase — run tasks with full execution gates"
    - label: "Revise — I have changes"
      description: "Tell me what to change"
    - label: "Save and stop"
      description: "Keep the sketch on disk; pick it up later"
```

### On "Execute"

Skip if cfl tracking was disabled in Phase 1 (no `<spec_number>` set):

```bash
cfl event sketch.approved --spec <spec_number>
```

Update design.md `**Status:**` from `draft` to `approved`.

Invoke `/mine-orchestrate <feature_dir>` directly — auto-continue, don't stop for the user. mine-orchestrate's resume-protocol handles the phase advance to `orchestrate` internally (with correct `--base-commit`, `--tmpdir` resolution). Do NOT call `cfl run advance-phase` here.

### On "Revise"

Ask what to change. Apply edits to design and/or tasks. Re-run Phase 4 (Comb). Present the handoff gate again.

### On "Save and stop"

Confirm: "Sketch saved at `<feature_dir>`. Resume with `/mine-sketch <feature_dir>` later."
