---
name: mine-plan
description: "Use when the user says: \"draft a plan\", \"create work packages\", \"generate WPs\", \"review this plan\", or \"check the plan\". Turns a design doc into task files and validates them against a traceability-focused checklist."
user-invocable: true
opencode-command: true
---

# Plan

Turn an approved design doc into a set of task files, validate them against a traceability checklist, and gate on user approval. Combines task generation with plan review in a single flow.

## Arguments

$ARGUMENTS — path to a `design.md` or the feature directory (`design/specs/NNN-<slug>/`). If empty, find the most recently modified `design/specs/*/design.md` and confirm with the user before proceeding.

---

## Branch staleness pre-flight

Task files encode literal file paths and pointers. If the branch is behind the default branch — e.g. a docs rewrite moved files since you branched — the task files get authored against stale paths, and the error only surfaces during orchestrate, forcing a rewrite of every affected task file. Catch it before generating: read `${CLAUDE_CONFIG_DIR:-~/.claude}/references/common/staleness-preflight.md` and follow it in **gate** mode, with this stakes sentence: "Task files generated now will reference paths from stale code."

---

## Initialize Plan Tracking

### Locate the design doc

If $ARGUMENTS points to a feature directory (`design/specs/NNN-*/`), read `design.md` from that directory.

If $ARGUMENTS is a direct path to a file, use it.

If $ARGUMENTS is empty:

```
Glob: design/specs/*/design.md
```

Sort by modification time, take the most recent. Then confirm (topic: `design-doc`):

```
AskUserQuestion:
  question: "Found design.md at <path>. Generate task files from this?"
  header: "Design doc"
  multiSelect: false
  options:
    - label: "Yes — use this design doc"
    - label: "No — let me specify the path"
      description: "Tell me the correct path and I'll use that"
```

### Identify the feature directory

The feature directory is `design/specs/NNN-<slug>/` containing the design.md. All task files will be written to `<feature_dir>/tasks/`. Create the `tasks/` subdirectory if it doesn't exist. Extract `<spec_number>` (`NNN`, without zero-padding) from the directory name — every `cfl` call in this skill from here on threads it through.

### Initialize plan tracking

Check whether cfl already tracks this spec:

```bash
cfl spec status --spec <spec_number>
```

- If this succeeds (spec data is returned), cfl tracking is available for this spec. Continue below.
- If this errors with `spec_not_found`, this directory predates cfl lifecycle tracking (created before cfl existed, or by a `mine-define` run that itself predates tracking) and cfl cannot adopt it after the fact. Tell the user: "This directory predates cfl lifecycle tracking — proceeding without cfl tracking for this session." **cfl tracking is inactive for this run** — skip every `cfl` call for the remainder of this run (the rest of this section, and every dispatch/event/gate call in Phases 3 through 6). Each of those sections notes this same condition — re-check it before running any `cfl` command, since a resumed session may re-enter at any phase.

**Why `<spec_number>` must be threaded through:** `cfl` commands resolve the current spec from the working directory by default — they glob `design/specs/*/tasks/T*.md` first, falling back to bare `design/specs/*/` only when no repo-wide task files exist at all. Until Phase 3 writes task files, this spec has no `tasks/` directory, so it's invisible to that glob; if any *other* spec directory in the repo still has task files — a common state, not an edge case — CWD-based resolution silently attaches to that unrelated spec instead, misattributing this run's entire lifecycle history. Passing `--spec <spec_number>` on every subsequent `cfl` call removes the ambiguity. From here on, every `cfl spec`, `cfl run`, `cfl gate`, `cfl dispatch`, and `cfl event` call in this skill appends `--spec <spec_number>` (the one exception is `cfl dispatch end <id>`, which resolves entirely from the dispatch id and takes no `--spec`) — unless cfl tracking is inactive per the branch above, in which case all such calls are skipped instead.

Determine the run state for this spec:

```bash
cfl run status --spec <spec_number>
```

Branch on the result:

- `"exists": true` and `"phase": "define"` — advance to plan phase:

```bash
cfl run advance-phase plan --spec <spec_number>
cfl event plan.started --spec <spec_number>
```

- `"exists": true` and `"phase": "plan"` — already in plan phase. Resume; no new run needed. Emit `cfl event plan.started --spec <spec_number>` only on the first entry into mine-plan for this run — skip it on subsequent invocations (e.g., a new session resuming an in-progress plan run).

- `"exists": true` and `"phase": "orchestrate"` — the run has already advanced past plan. This shouldn't happen in normal flow (phase advances are forward-only and orchestrate never hands back to plan). Warn the user: "This spec's run has already advanced to the orchestrate phase — proceeding without further plan-phase tracking." **cfl tracking is inactive for the remainder of this run** — apply the same skip rule as the "predates cfl tracking" branch above.

- `"exists": false` — no active run. Try resuming a stopped run:

```bash
cfl run resume --spec <spec_number>
```

If resume succeeds, run `cfl run status --spec <spec_number>` to read the resumed run's phase (the resume response itself doesn't include it), then branch as above: if the phase is `define`, advance to `plan` (as above, including the `plan.started` event); if already `plan`, proceed without re-emitting the event.

If resume errors with `no_stopped_run`, create a new run:

```bash
cfl run start --phase plan --base-commit $(git rev-parse --short HEAD) --spec <spec_number>
cfl event plan.started --spec <spec_number>
```

### Record design doc selection

Record (skip if $ARGUMENTS was provided directly, or if cfl tracking is inactive): `cfl question mine-plan design-doc --status <asked|skipped> --answer "<selected option>" --spec <spec_number>`

---

## Phase 1: Read the Design Doc

### Extract key information

Read the doc fully. Extract and record:

- **Problem** — what is being solved
- **Architecture / Proposed approach** — the recommended direction and design decisions
- **Non-goals** — explicit exclusions (tasks must NOT implement these). This section is optional in design docs — if absent, the user stated no explicit exclusions; proceed without scope constraints from this field.
- **Impact / Changed Files** — modules and files named in the design (under the `### Changed Files` subsection of `## Impact`). Also note any `### Behavioral Invariants` — existing behaviors that must not change.
- **Replacement Targets** — code or patterns being intentionally replaced (if section exists). Tasks should remove or migrate these, not preserve them alongside new code.
- **Open questions** — collect any that are non-empty
- **Test Strategy** — testing approach, structured as four subsections: `### Required Test Types` (which testing layers this change needs, with justification and infrastructure gaps), `### Existing Tests to Adapt` (test files that will break), `### New Test Coverage` (behaviors needing tests, mapped to FR#N), and `### Tests to Remove` (obsolete tests). Required Test Types constrains each task's Verify section — a task producing integration-test-worthy changes must include integration tests, not just unit tests. If the design doc's Test Strategy states N/A (no test infrastructure), tasks should use "N/A — no test infrastructure in this repo" for their Verify sections rather than inventing test requirements.
- **Numbered FRs** — every functional requirement with identifier format `FR#N` (e.g., `FR#1`, `FR#13`). Record the complete list of FR identifiers.
- **Numbered ACs** — every acceptance criterion with identifier format `AC#N` (e.g., `AC#1`, `AC#19`). Record the complete list of AC identifiers.
- **Visual Artifacts** — any mockup paths, screenshot references, or linked visual assets mentioned in the doc.
- **Key Constraints** — explicit technical or design constraints named in the doc.

**FR/AC identifier format**: Identifiers must match `^FR#\d+$` and `^AC#\d+$` respectively. If the design doc uses a different format (e.g., "FR-1" or "Requirement 1"), note this — the validation gate will flag format non-compliance.

If open questions exist, walk through each one interactively before proceeding. First, count all open questions and record the total as M — you need this before asking the first one.

Entries already marked `**Deferred to implementation**` were handled by an earlier run of this phase; do not re-prompt on them and do not count them toward M. They are waiting on Phase 3, not on the user.

**Every question must leave this phase with an owner**, written into a file rather than into the conversation. Most clear out of Open Questions here; ones deferred to implementation stay in the section, marked, until Phase 3 hands them to a task file. Either way the section is empty by plan approval, and Phase 6 checks.

Owned does not mean confidently answered. A risk taken deliberately and a question that cannot be settled until the code exists are both legitimate outcomes; they just land in different places. What is not allowed is an entry nobody handled, which is what happens when a resolution is recorded in conversation and never written back to the doc.

For each open question:

1. **Analyze the question** — read the surrounding context in the design doc to infer the most reasonable answer. Identify exactly 2 substantive resolution options and pick the one you'd recommend.

2. **Prompt the user** using AskUserQuestion, one question at a time:

```
AskUserQuestion:
  question: "<Quote the open question verbatim, then add a one-sentence summary of what's at stake>"
  header: "Q{N} of {M}"
  multiSelect: false
  options:
    - label: "<Option A — your recommendation>"
      description: "RECOMMENDED — <one sentence why>"
    - label: "<Option B>"
      description: "<tradeoff or implication>"
    - label: "Defer to implementation"
      description: "Can't be settled until the code exists; attach it to the task that hits it"
    - label: "Stop — I'll update the design doc first"
      description: "Exit now so you can revise the doc before generating tasks"
```

If the honest choice is to accept the uncertainty rather than resolve it, say so in one of the two substantive options ("Accept <X> as a known risk, mitigated by <Y>") rather than offering a bare skip. An accepted risk is a decision with an owner; a skip is an entry nobody handled.

3. **Discharge it in the doc** — edit `design.md` immediately, before moving to the next question. Do not batch this to the end; a question answered but not written down is the failure this step exists to prevent.

   - **Resolved** (Option A or B, an answer): write the decision into the design section it affects — Architecture, Test Strategy, Implementation Preferences, whichever the question was about. Then delete the entry from Open Questions.
   - **Accepted** (Option A or B, a risk taken): write it into `## Dependencies and Assumptions` with its mitigation. Then delete the entry from Open Questions.
   - **Deferred**: rewrite the entry in place as `**Deferred to implementation** — <what the implementer must determine, and what to do with each answer>`. **Do not delete it yet.** It stays in Open Questions until Phase 3 writes it into the owning task's `## Focus`, because until that task file exists there is nowhere durable for it to live, and Phase 2 sits in between. Deleting it here would lose it if the session is interrupted — the same failure this step exists to prevent, one phase later.

   Never delete an entry before its destination exists. Resolved and Accepted write into `design.md` in the same edit, so they clear immediately; Deferred cannot.

   If cfl tracking is active, record each question (topic: `open-question`) with the disposition matching where you just landed it:

```bash
cfl question mine-plan open-question --status asked --disposition <resolved|accepted|deferred> \
    --answer "<selected option>" --spec <spec_number>
```

Status is always `asked` here — every path through this flow, including "Defer to implementation", is the user answering. `--answer` carries which one they chose. (`skipped` means a question was never put to them, which no longer happens in this phase.)

`--disposition` is the separate question of which file the answer went into, so it must name the edit you just made: `resolved` for a decision written into a design section, `accepted` for a risk written into Dependencies and Assumptions, `deferred` for an entry left marked in Open Questions for Phase 3. Record it in the same step as the edit rather than from memory afterward — the disposition is a claim about the doc, and the two disagreeing is worse than no record at all.

If the user selected "Stop", omit `--disposition` — nothing was written anywhere — then record the answer and exit. The doc keeps its Open Questions section intact for them to revise.

When every question has been handled, re-read `design.md` rather than assuming the edits landed. Open Questions should now contain nothing except entries marked `**Deferred to implementation**`, which Phase 3 clears. Then summarize before continuing to Phase 2:
> Handled all open questions: Q1 → resolved into Architecture, Q2 → accepted as a known risk in Dependencies and Assumptions, Q3 → deferred to whichever task touches the parser. One deferred entry remains in the doc until its task file exists. Proceeding to generate task files.

---

## Phase 2: Explore the Codebase Concretely

Read `${CLAUDE_CONFIG_DIR:-~/.claude}/skills/mine-plan/exploration-protocol.md` and follow it.

---

## Phase 3: Write Task Files

Read `${CLAUDE_CONFIG_DIR:-~/.claude}/skills/mine-plan/task-format.md` for the context.md template, task file template, field rules, decomposition rules, and scope rules. Write context.md first, then all T*.md files.

### Land the deferred open questions

If Phase 1 left any entry in Open Questions marked `**Deferred to implementation**`, finish the handoff now that task files exist. For each one:

1. Pick the task whose Target Files cover the affected area.
2. Write it into that task's `## Focus`: what the implementer must determine, and what to do with each answer.
3. Delete the entry from the design doc's Open Questions.

Do this in that order — the entry only leaves `design.md` once it exists in a task file.

**Record nothing in cfl for this path.** Phase 1 already recorded the deferral, and a task claiming the question is that decision being carried out, not a new one. Adding a second `--disposition deferred` row here would count the same deferral twice and inflate the only number the disposition column exists to produce. The unowned branch below does record a row, because there the Phase 1 decision turned out to be wrong and a new one gets made.

If no task plausibly owns a deferred question, do not force it into the nearest one and do not drop it. That means either the plan is missing work or the question was misfiled during Phase 1. Stop and ask:

```
AskUserQuestion:
  question: "<Quote the deferred question> — no task in this plan covers it. How should it land?"
  header: "Unowned Q"
  multiSelect: false
  options:
    - label: "Add a task for it"
      description: "The plan is missing work; I'll write a task that owns this and re-run validation"
    - label: "Accept it as a known risk"
      description: "Not implementation work after all; record it in Dependencies and Assumptions and clear the entry"
    - label: "Stop — I'll revise the design"
      description: "Exit so you can rework the doc before planning continues"
```

Apply the choice before continuing to Phase 3.5: a new task means re-running task generation for it, an accepted risk means writing it into `## Dependencies and Assumptions` and deleting the entry. Do not proceed with the entry still sitting in Open Questions — Phase 6 would block on it anyway, several phases later.

Phase 1 already recorded this question as `deferred`, which was true then. Where it ends up now is a second fact, so record it as its own row. Skip if cfl tracking is inactive for this run (see Initialize Plan Tracking):

```bash
cfl question mine-plan open-question --status asked --disposition <accepted|deferred> \
    --answer "Unowned in Phase 3 — <selected option>" --spec <spec_number>
```

Use `deferred` again if a new task took it, `accepted` if it became a known risk, and omit `--disposition` on exit. Both rows stand — the table records decisions as they were made, not a current state per question.

### Record tasks written

After context.md and all `T*.md` files are written to disk. Skip if cfl tracking is inactive for this run (see Initialize Plan Tracking):

```bash
cfl event plan.tasks-written --data '{"task_count": <N>}' --spec <spec_number>
```

Where `<N>` is the number of task files generated.

---

## Phase 3.5: Validation Gate

After writing all task files and context.md, dispatch a validation subagent with fresh context to independently verify traceability and correctness. This subagent does NOT inherit the planner's interpretation.

### Dispatch the validator

Before dispatching, record the dispatch. Skip this call (and the dispatch-end call below) if cfl tracking is inactive for this run (see Initialize Plan Tracking):

```bash
cfl dispatch plan-validator --agent-type general-purpose --model sonnet --spec <spec_number>
```

Record the `dispatch_id` from the output.

Read `${CLAUDE_CONFIG_DIR:-~/.claude}/skills/mine-plan/validator-prompt.md` to get the validator instructions.

Launch a `general-purpose` subagent with `model: sonnet`. Pass this prompt (fill in the bracketed values):

```
You are a plan validation agent. Your job is to independently verify that a set of task files correctly and completely covers the requirements in a design document.

## Your instructions
<full validator-prompt.md content>

## Paths to read
- Design doc: <absolute path to design.md>
- Task files directory: <absolute path to tasks/ directory>
- context.md: <absolute path to tasks/context.md>

## Output path
Write your validation report to: <absolute path to tasks/.validation-report.md>
```

The subagent reads the design doc and all task files independently (fresh context). It writes the report to `<feature_dir>/tasks/.validation-report.md`.

### Record validator dispatch end

After the validator subagent completes. Skip if cfl tracking is inactive for this run:

```bash
cfl dispatch end <dispatch_id>
```

**Cross-check:** After the subagent completes, verify that the traceability matrix row count matches the FR/AC identifier count from Phase 1. If the counts diverge, re-run the validator — the subagent may have dropped or hallucinated identifiers.

### Present validation results

Read the validation report. Then present:

1. **Validation verdict** — PASS or FAIL (bold, prominent)
2. **Coverage summary** — e.g., "22/22 FRs mapped, 10/10 ACs mapped" (counts only — the full matrix is in `.validation-report.md` if needed)
3. **Coverage gaps** — any FRs/ACs with no implementing task (only the gaps, not the full matrix)
4. **Contradictions** — any conflicts between task prompts and the design doc
5. **Non-local criteria** — any Verify items requiring CI, post-merge, or external-pipeline observation (these should not be ACs)
6. **Warnings** — vague criteria, weak references, format issues

Note the path to `.validation-report.md` so the user can inspect the full traceability matrix if desired.

### Record validation gate

Skip if cfl tracking is inactive for this run:

```bash
cfl gate plan-validation --verdict <PASS|FAIL> --spec <spec_number>
```

If verdict is FAIL, ask the user:

```
AskUserQuestion:
  question: "Validation found issues (see report above). How to proceed?"
  header: "Validation"
  multiSelect: false
  options:
    - label: "Fix and re-validate"
      description: "I'll describe corrections; re-run the validation gate after"
    - label: "Proceed anyway"
      description: "I understand the gaps; proceed to review"
    - label: "Regenerate tasks"
      description: "Significant gaps — regenerate with corrections"
```

If PASS (with or without warnings), proceed to Phase 4 automatically.

---

## Phase 4: Commit Task Files

After the validation gate passes, commit the task files together with the design doc — Phases 1 and 3 both edited `design.md` while discharging open questions, and those edits belong in the same commit as the tasks that now own them:

```bash
git add design/specs/<feature>/tasks/ design/specs/<feature>/design.md
git commit -m "feat: add task files for NNN-<slug>"
```

If git operations fail (not a repo, nothing to commit), note it and continue.

---

## Phase 5: Review

### Dispatch reviewer subagent

Before dispatching, record the dispatch. Skip this call (and the dispatch-end call below) if cfl tracking is inactive for this run:

```bash
cfl dispatch plan-reviewer --agent-type general-purpose --model sonnet --spec <spec_number>
```

Record the `dispatch_id` from the output.

Run `get-skill-tmpdir mine-plan` and use `<dir>/review.md` for the review output.

Read `${CLAUDE_CONFIG_DIR:-~/.claude}/skills/mine-plan/reviewer-prompt.md` to get the checklist content.

Launch a general-purpose subagent with `model: sonnet`. Pass this prompt (fill in the bracketed values from the files you read):

```
You are reviewing an implementation design and its task files.

## Design doc content
<full design.md content>

## context.md content
<full tasks/context.md content>

## Task files
<full content of each T*.md, in order, separated by file headers showing the absolute path to each file>

## Your instructions
<full reviewer-prompt.md content>

Write your complete structured review to: <temp file path>
```

The subagent will write the review to the temp file.

### Record reviewer dispatch end

After the reviewer subagent completes. Skip if cfl tracking is inactive for this run:

```bash
cfl dispatch end <dispatch_id>
```

### Present findings

Read the temp file. Format the results clearly:

1. **Checklist results** — one line per item: `N. <name>: PASS|WARN|FAIL — note`
2. **Verdict** — PASS, FAIL, or ABANDON (bold, prominent)
3. **Summary** — 2-3 sentences from the subagent
4. **Blocking issues** — if verdict is FAIL or ABANDON
5. **Suggestions** — non-blocking notes, if any

### Record review gate

Skip if cfl tracking is inactive for this run:

```bash
cfl gate plan-review --verdict <v> --spec <spec_number>
```

Verdict mapping: reviewer PASS → PASS, reviewer FAIL → FAIL, reviewer ABANDON → FAIL.

---

## Phase 5.5: Fine-Toothed Comb Review

The task files are now the plan's output. Comb the design doc and the task files **together** one last time — an open-ended pass, no checklist, no rubric. This is distinct from the Phase 3.5 traceability gate and the Phase 5 review checklist: it catches the design and tasks reading as inconsistent, inaccurate, or thin once taken in as a whole (a task that drifted from the design's intent, a design decision no task honors, terminology that diverged between the two).

Before dispatching, record the dispatch. Skip this call (and the dispatch-end/gate calls below) if cfl tracking is inactive for this run:

```bash
cfl dispatch plan-comb --agent-type fine-toothed-comb --model sonnet --spec <spec_number>
```

Record the `dispatch_id` from the output.

Dispatch the `fine-toothed-comb` agent (see `${CLAUDE_CONFIG_DIR:-~/.claude}/agents/fine-toothed-comb.md`):

```
Agent:
  subagent_type: fine-toothed-comb
  model: sonnet
  prompt: |
    Read this design file: <design_doc_path>
    Read all task files in: <feature_dir>/tasks/

    Go over the design file and the corresponding tasks with a fine-toothed comb, making sure that they are all consistent, accurate, and thorough. Report anything you find.

    Define blocking as: a direct inconsistency or inaccuracy between the design and tasks that would mislead implementation. A task that could be more detailed is minor, not blocking — only flag a gap as blocking when the missing information has no reasonable default and would force the implementer to guess.
```

After the comb completes, record the dispatch end and the gate. This verdict reflects the comb subagent's own findings classification, recorded immediately from its report — not the user's downstream proceed/re-review decision, which the "Comb gate" step below handles separately:

```bash
cfl dispatch end <dispatch_id>
cfl gate plan-comb --verdict <v> --spec <spec_number> --data '{"blocking": <N>, "minor": <M>}'
```

Verdict mapping — apply mechanically from the `blocking` count in the comb's summary, do not downgrade based on your own severity assessment: `blocking` = 0 and no minor → PASS, `blocking` = 0 and minor > 0 → WARN, `blocking` > 0 → FAIL.

### Comb gate

Read `${CLAUDE_CONFIG_DIR:-~/.claude}/skills/mine-comb/comb-gate.md` and apply it with:

- **`<header>`**: `Plan comb`
- **`minor_blocks`**: `false` — minor findings are noted for the gate but do not block
- **`<re_review_instructions>`**: apply the fixes to the design doc and/or task files, then re-run this phase from the top. Restrict task file edits to the same cosmetic-vs-substantive rule as Phase 6's "Approve with suggestions" — substantive task changes require re-running task generation from Phase 2.

Phase 6 does not begin until the comb gate resolves. The "No findings" path proceeds to Phase 6 silently.

---

## Phase 6: Gate

### Open Questions check

Before presenting the gate, re-read the design doc's `## Open Questions` section. It must be empty — every entry was discharged in Phase 1 (resolved into a design section, accepted as a risk, or deferred onto a task's `## Focus`).

If entries remain, do not present the approval options yet. Either something between Phase 1 and here failed to write back, or a question was added after Phase 1 ran. Show the user what is still sitting there, then clear each one — noting that task files already exist and are committed by this point, so the routes differ slightly from Phase 1:

- **Resolved or Accepted** — same as Phase 1: write it into the design section it affects or into `## Dependencies and Assumptions`, then delete the entry.
- **Deferred** — the owning task file already exists, so edit its `## Focus` directly rather than waiting on Phase 3, then delete the entry. Commit the task-file edit alongside the design-doc edit.

Every gate before this one has already inspected the previous contents, so a late edit ships unchecked unless you re-check it. How far back to go depends on what the edit changed, not which route it took:

- **It changed what a task must do** — a new or altered FR/AC, or a design section tasks implement. This is the usual shape of a late Resolved entry, and it can also come from an Accepted one whose mitigation is real work. Task files were generated against the old text, so treat it as a revision: re-run from Phase 2 exactly as the "Revise the plan" option does.
- **It changed nothing tasks must do** — a decision the existing tasks already satisfy, or a risk recorded in `## Dependencies and Assumptions` with no work attached. Nothing downstream depends on it; proceed.
- **It added a Focus line** — re-read that one task's `## Focus` against the design doc and check the three things the gates check there: that it contradicts nothing in the requirements the task implements, that it adds no work outside the task's scope, and that if it references a visual artifact, the task's `## Verify` has a criterion covering it. Those are the checks the gates make on `Focus` text: `validator-prompt.md` does contradiction and visual-artifact coverage, `reviewer-prompt.md` adds scope containment. Only the first two are usually in play, but a deferred question about appearance is exactly the case that pulls `Verify` into scope — add the criterion rather than assuming `Verify` is untouched. If all three clear, proceed; nothing else in the suite has new input, since `implements` and `Target Files` are unchanged.
- **The Focus re-check fails** — the deferred question does not belong on that task. Do not edit the line until it passes. Take it to the routes in Phase 3's unowned-question prompt: they were written for a question no task owns, but the outcome space is the same one you need here for a question owned by the wrong task — add a task for it, accept it as a risk, or stop and revise the design.

This is the only enforcement point for the invariant, which is why it re-reads the file rather than trusting Phase 1 and Phase 3 did their jobs. Historically the section was never empty at approval precisely because resolutions lived in conversation and no step ever checked the doc.

### Approval options

If the reviewer's output includes non-blocking suggestions, present "Approve with suggestions" as the first (recommended) option. If there are no suggestions (clean PASS), omit it and show "Approve as-is" first.

**When suggestions exist:**

```
AskUserQuestion:
  question: "Review complete. What would you like to do?"
  header: "Plan verdict"
  multiSelect: false
  options:
    - label: "Approve with suggestions (Recommended)"
      description: "Apply the reviewer's non-blocking suggestions, then proceed"
    - label: "Approve as-is"
      description: "Skip suggestions; proceed to execution"
    - label: "Revise the plan"
      description: "Blocking issues found — regenerate task files with reviewer notes"
    - label: "Abandon"
      description: "Mark the design as abandoned and stop"
```

**When no suggestions exist:**

```
AskUserQuestion:
  question: "Review complete. What would you like to do?"
  header: "Plan verdict"
  multiSelect: false
  options:
    - label: "Approve as-is"
      description: "Plan is good; proceed to execution"
    - label: "Revise the plan"
      description: "Blocking issues found — regenerate task files with reviewer notes"
    - label: "Abandon"
      description: "Mark the design as abandoned and stop"
```

### Record approval question and gate

After the user's choice above. Skip all `cfl` calls below if cfl tracking is inactive for this run.

Record the question (topic: `plan-approval`):

```bash
cfl question mine-plan plan-approval --status asked --answer "<selected option>" --spec <spec_number>
```

Record the gate:

```bash
cfl gate plan-approval --verdict <v> --spec <spec_number>
```

Verdict mapping:
- "Approve as-is" / "Approve with suggestions" → PASS
- "Revise the plan" → WARN (loop continues; re-emit on each revision cycle)
- "Abandon" → FAIL

Only when the verdict is PASS, also emit:

```bash
cfl event plan.approved --spec <spec_number>
```

### On "Approve as-is"

Update the `design.md` `**Status:**` field from `draft` to `approved`.

**If invoked inline by `mine-build`** (the user chose "Full caliper workflow" or "Accelerated"), skip the gate below and invoke `/mine-orchestrate <feature_dir>` directly — `mine-build` handles the flow.

**Otherwise**, ask:

```
AskUserQuestion:
  question: "Plan approved. Begin implementation?"
  header: "Next step"
  multiSelect: false
  options:
    - label: "Yes — start execution"
      description: "Invoke /mine-orchestrate for this feature"
    - label: "No — I'll start later"
      description: "Stop here; the plan is approved and saved"
```

If "Yes": invoke `/mine-orchestrate <feature_dir>` directly.

### On "Approve with suggestions"

Apply the reviewer's non-blocking suggestions to `design.md` and/or `T*.md` files. Restrict task file edits to cosmetic changes (wording, clarifications, review guidance) — substantive task changes require re-running the task generation phases. Show the user a brief summary of what was changed (absolute file path + one-line description per change). Update the `design.md` `**Status:**` field from `draft` to `approved`.

Then follow the same gate as "Approve as-is" above (invoke `/mine-orchestrate` on approval).

### On "Revise the plan"

Surface the reviewer's blocking issues as a numbered list. Loop back to Phase 2 — re-explore the codebase and regenerate task files with the reviewer's notes as context. Tell the user:
> Regenerating task files with the reviewer's notes.

### On "Abandon"

Update the `design.md` `**Status:**` field from `draft` to `abandoned`.

Confirm: "Design saved as abandoned at `<path>`."
