# Design: Reduce Mid-Execution Subagent Compaction in Workflow Skills

**Date:** 2026-06-15
**Status:** archived
**Scope-mode:** hold

> **Revision note (post-challenge):** `/mine.challenge` (workflow-ux, agent-definition,
> systems-architect) found one CRITICAL factual error (the Lever 2 mapping was inverted —
> `mine.challenge` has no diff mode) and one CRITICAL smuggled behavior change (a blanket
> "don't re-read after editing" rule that broke the TDD/Verify contract). It also challenged
> the file-count *threshold* as fighting `mine.define`'s own "file counts don't matter" rule.
> This revision drops the count threshold (keeps the target-file *list*), narrows the executor
> discipline to the safe wins, corrects the Lever 2 skill mapping, and fixes clean-code
> chunking to preserve cross-lens coverage. See `## Alternatives Considered` for what was cut
> and why.

## Problem

Subagents launched by the workflow skills (`mine.orchestrate` executors, and the critics
dispatched by `mine.review` / `mine.clean-code`) run on a ~200k-token context window and
auto-compact at ~167k (~83% of the window). They start each run already carrying a ~44k fixed
baseline (subagent system prompt + tool schemas + inherited rules/CLAUDE.md), leaving only
**~115k tokens of real working budget**. When that budget is exhausted mid-task the harness
compacts the subagent, dropping file references, prior decisions, and test output — exactly the
context the subagent needs to finish correctly.

This is not hypothetical. Across four active `hassette` worktrees there are **15 observed
compaction events** (the `subagent-compaction-check.sh` hook records them from
`compact_boundary` entries in the subagent JSONLs). Every event fired in a narrow band
(167k–176k tokens), confirming the cause is budget exhaustion, not anything random. Two distinct
failure modes appear in the data:

- **Mode A — review surface sprawl.** Critics read the *entire* changed-file surface and
  reconstruct the diff themselves via many shell calls. One "senior engineer critic" ran
  **80 Bash calls** doing git archaeology; a `nitpicker` did **38 full-file reads** and compacted
  in 46 turns with zero edits. The review skills tell critics `Run: <diff command>` rather than
  handing them the diff, so each critic re-derives the changeset; and a large changed-file set is
  read in full by every checker at once.
- **Mode B — executor iteration churn.** `mine.orchestrate` executors churn long edit→test→verify
  loops. One executor ran **178 turns** (53 Bash, 37 Read, 27 Edit), repeatedly re-running the
  full test suite and dumping full output into context — verification work the orchestration's own
  Step 9 gate and parallel reviewers already perform independently.

The root arithmetic is the same: ~115k working budget, consumed by tool output that accumulates
in context. The fix is to stop wasting that budget on avoidable work (re-deriving diffs,
re-running the full suite mid-task, dumping full output inline) and to give the planner the
information it needs to scope a task's exploration footprint.

**What this design deliberately does NOT do** (per the challenge): it does not introduce a
file-*count* split threshold (file count tracks neither measured failure mode and contradicts a
`mine.define` rule), and it does not ban an executor from re-reading a file it just edited (that
re-read is load-bearing for TDD self-correction; only the *full-suite* re-run is waste).

## Goals

- Cut per-subagent working-budget consumption in the two measured failure modes so routine review
  and execution tasks finish without hitting the ~167k compaction wall.
- Give the planner an explicit per-task target-file list so executors read targeted rather than
  exploring the surface from scratch (the cheap, uncontested half of the planning lever).
- Hand `mine.review` critics a pre-computed diff artifact, and chunk `mine.clean-code`'s full-file
  reads, so critics stop re-deriving and over-reading the changeset.
- Tighten the `mine.orchestrate` executor contract to stop duplicating the *full-suite*
  verification the Step 9 gate already performs, without weakening the TDD/Verify contract.
- Scope — but do not implement — a research task for the dominant ~44k baseline tax, including a
  prior-art survey, since the deep fix depends on external platform behavior.

## Non-Goals

- **No file-count split threshold.** Dropped after challenge — file count measures neither failure
  mode and contradicts `mine.define/SKILL.md:523` ("File lists matter; file counts don't"). The
  target-file *list* is kept; the numeric "split if >12" rule is not.
- **No edits for the baseline-trim lever (Lever 4).** Research-only this round, now including a
  prior-art run. The deep fix depends on platform features broken at last investigation.
- **No change to what critics/executors look for.** Severity rules, checklist categories, review
  dimensions, and the TDD red/green/refactor + Verify contract are unchanged. This is a
  context-budget change. (See AC#8 — this is an explicit guardrail, since prose edits to subagent
  instructions *can* silently change behavior.)
- **No new hook or runtime enforcement mechanism.** Changes are to skill/rule prose and the
  diff-artifact plumbing the review skills already have access to via `scope-detection.md`.

## User Scenarios

### Plan author (the agent running `mine.plan`): turns a design into task files
- **Goal:** produce task files whose target files are explicit, so executors read targeted
- **Context:** after `mine.define` has produced a design.md with a Changed Files inventory — OR
  working from a hand-written design with no inventory

#### Recording each task's target files

1. **Populate the target-file list per task**
   - Sees: the design's Changed Files inventory if present; otherwise the Phase 2 codebase
     exploration `mine.plan` already performs
   - Decides: which files each task creates, reads, modifies, or deletes
   - Then: each task records that explicit list as a required field — sourced from the inventory
     when available, derived during planning when not (no hard dependency on `mine.define`)
2. **Plan reviewer checks presence**
   - Sees: each task's target-file field
   - Decides: nothing automatic about size — only whether the field is present and concrete
   - Then: a task missing the field is flagged; there is no numeric split threshold to trip

### Review orchestrator (`mine.review`): dispatches critics against a diff
1. **Compute the diff once and persist it with its HEAD SHA**
   - Sees: the resolved diff command from `scope-detection.md`
   - Decides: nothing — the orchestrator runs it, writes output to a temp file, records the SHA
   - Then: each critic prompt references the artifact path and is told not to re-derive the
     changeset; the artifact lives in the skill tmpdir and is cleaned with it

### Clean-code orchestrator (`mine.clean-code`): chunks a large surface
1. **Chunk within each checker above ~10 files**
   - Sees: the changed-file count from `scope-detection.md`
   - Decides: above ~10 files, split the file set into batches and dispatch *each* checker
     (llm/lazy/nitpick) once per batch, so every file still receives all three lenses
   - Then: per-checker findings are merged across batches; at or below the threshold, behavior is
     unchanged (one dispatch per checker over the full set)

### Executor (the `mine.orchestrate` subagent): implements one task
1. **Verify without duplicating the gate**
   - Sees: a capture-to-log instruction and a narrowed re-run rule
   - Decides: run its TDD targeted tests, capture output to a log file, and re-read the file it
     just edited to confirm the edit landed
   - Then: does NOT re-run the *full suite* mid-task to "verify" — the Step 9 gate and the parallel
     reviewers do that. The executor's own targeted red/green/refactor loop is unchanged.

## Functional Requirements

- **FR#1** A `mine.plan` task file must carry an explicit, required field listing every target
  file it will create, read, modify, or delete — sourced from `mine.define`'s inventory when
  present, otherwise derived during `mine.plan`'s own codebase exploration.
- **FR#2** The `mine.plan` plan-reviewer checklist must verify the target-file field is present and
  concrete. It must NOT enforce a file-count threshold.
- **FR#3** `mine.define`'s design.md must expose a per-change target-file inventory (via the
  existing `## Impact` → Changed Files section) that `mine.plan` can consume — as input, not as a
  gate that fails when absent.
- **FR#4** `decomposition-discipline.md` must name the per-task target-file / context-footprint
  consideration, without introducing a file-count threshold, and must respect the existing
  `SYNC: invariants.md` contract at the top of the file.
- **FR#5** `mine.review` must compute the review diff once and pass it to each critic as a
  file-artifact path (stamped with the HEAD SHA it was computed against), and instruct critics to
  read the artifact rather than re-run the diff command to reconstruct the changeset.
- **FR#6** `mine.clean-code` must, above ~10 changed files, batch the changed-file set and dispatch
  *each* checker once per batch so every file is still reviewed by all three checkers; per-checker
  findings are merged across batches. At or below the threshold, behavior is unchanged.
- **FR#7** The `mine.orchestrate` executor prompt must instruct the executor to capture test/lint
  output to a log file in the task temp directory rather than inlining full output into its result.
- **FR#8** The `mine.orchestrate` executor prompt must instruct the executor not to re-run the
  *full test suite* mid-task to verify an edit; targeted verification — re-reading the just-edited
  file, running the specific test for the change — remains expected per the TDD contract.
- **FR#9** The executor Self-Review checklist line that currently says "All tests pass (run the
  test command, confirm output)" must be reworded to match FR#7/FR#8 (targeted TDD run +
  capture-to-log), not appended to, so the contract does not contradict itself.
- **FR#10** The design must record a scoped, no-edit research task for the ~44k baseline tax,
  including a prior-art survey (run `/mine.prior-art`, incorporating the repos from the Claude Code
  digest) and the three baseline sub-questions below.

## Edge Cases

- **`mine.plan` runs standalone with no `mine.define` inventory** (hand-written design, or an
  existing spec predating this change). The target-file field is still required, but its *source*
  falls back to `mine.plan`'s Phase 2 exploration — no hard dependency, no failure. (FR#1)
- **A task legitimately touches many files** (e.g., a mechanical rename). With the count threshold
  dropped, this is no longer a problem — the task simply lists all its files; there is no split
  gate to trip and no justification field to invent.
- **Diff is empty or scope is path-mode in `mine.review`.** The diff-artifact step applies only to
  diff mode; path mode already passes a file list. Empty diff → skip the artifact, use existing
  behavior.
- **Working tree changes between artifact creation and a critic reading it.** The artifact records
  the HEAD SHA it was computed against; if a critic detects HEAD has moved, it falls back to the
  live diff command. (FR#5)
- **Two `mine.review` runs collide.** Each run computes its artifact under its own
  `get-skill-tmpdir` directory, so paths don't clash. (FR#5)
- **`mine.clean-code` with ≤10 changed files.** No chunking — one dispatch per checker over the
  full set, current behavior. (FR#6)
- **An uneven changed-file set** (one directory holds most churn). Batch by changed-file *count*
  balanced across batches; never leave a batch empty. Every file still gets all three lenses. (FR#6)
- **Executor can't tell which targeted test covers its change.** It falls back to the provided test
  command but still captures output to a log file; FR#8 forbids the redundant *full-suite re-run to
  verify*, not running tests at all. (FR#8)

## Acceptance Criteria

- **AC#1** A task file generated by `mine.plan` contains a populated, concrete target-file field; a
  task without one is flagged by the plan reviewer. No reviewer item enforces a file count. (FR#1, FR#2)
- **AC#2** `mine.plan` run on a design with no Changed Files inventory still produces the
  target-file field (derived during planning) without erroring. (FR#1)
- **AC#3** `mine.define`'s design.md template/flow produces a target-file inventory `mine.plan` can
  read, and `mine.plan` treats it as optional input. (FR#3)
- **AC#4** `decomposition-discipline.md` includes the target-file/context-footprint consideration,
  with no file-count threshold, and its `SYNC: invariants.md` block is updated if the change
  warrants. (FR#4)
- **AC#5** In diff mode, `mine.review` critic prompts reference a HEAD-SHA-stamped diff artifact
  path, instruct critics not to re-derive the changeset, and the artifact's create/cleanup
  lifecycle is specified. `mine.challenge` is NOT modified. (FR#5)
- **AC#6** `mine.clean-code` above ~10 changed files dispatches each checker once per file-batch so
  every file is covered by all three checkers, merges per-checker findings, and retains
  single-dispatch behavior at or below the threshold. (FR#6)
- **AC#7** The `mine.orchestrate` executor prompt and `implementer-prompt.md` contain capture-to-log
  and no-full-suite-re-run instructions, and the Self-Review test line is reworded (not appended) to
  match. (FR#7, FR#8, FR#9)
- **AC#8** Behavior-preservation guard: critic checklists, review dimensions, severity rules, and
  the TDD red/green/refactor + Verify (file:line evidence) contract are unchanged. Verified by
  re-reading the edited executor/critic prompts against the existing contract clauses
  (`implementer-prompt.md`, `tdd.md`) — not by diff inspection alone, since prose edits to subagent
  instructions are themselves behavior. (FR#7–FR#9)
- **AC#9** The Lever 4 research section names the ~44k baseline, the prior research docs, the
  blocking platform issues, the three baseline sub-questions, and a `/mine.prior-art` run that
  incorporates the Claude Code digest repos. (FR#10)

## Key Constraints

- **The TDD/Verify contract is load-bearing — do not weaken it.** `implementer-prompt.md:82,86,165`
  (confirm test output, re-read reviewer files on retry, Verify requires file:line evidence) and
  `tdd.md:30–36` (GREEN/REFACTOR re-runs) all require the executor to re-read/re-run after editing.
  FR#8 forbids only the *full-suite* re-run, never the targeted verify. A blanket "don't re-read"
  rule (the original FR#10) would make the executor emit evidence-free DONE verdicts.
- **`mine.challenge` has no diff mode.** It is an artifact critic that reads a target by
  `target_type` (`mine.challenge/SKILL.md:144`); it does not share `scope-detection.md`. Lever 2
  applies to `mine.review` (and the chunking half to `mine.clean-code`) — NOT `mine.challenge`.
- **clean-code's three checkers are orthogonal lenses, not redundant.** Chunking must split *within*
  each checker (each checker still sees every file, in batches), never *across* checkers — splitting
  across would drop each file from three lenses to one and break the design's own coverage promise.
- **File lists, not file counts.** The chosen planning signal is the explicit target-file *list*.
  Do not reintroduce a count threshold or a token formula — both were challenged and cut.
- **Don't headline scaffolding-trim.** Passing `tdd.md` by path instead of inlining recovers only
  ~3–4k tokens; it is a minor item folded into Lever 4 research, not its own lever.

## Dependencies and Assumptions

- Assumes subagents run on a ~200k window with auto-compact near ~167k — confirmed empirically from
  15 `compact_boundary` events. **This is a platform parameter, not a contract** (see Open
  Questions): the design avoids hardcoding it into anything user-facing precisely because it can
  move; the target-file list and capture-to-log changes are valuable regardless of the exact
  window size.
- Assumes `mine.review` and `mine.clean-code` share `scope-detection.md`, which resolves a diff
  command and a changed-file count. **Verified true for review and clean-code; verified FALSE for
  `mine.challenge`** — which is why challenge is out of scope.
- Assumes `mine.orchestrate` writes per-task temp directories (`<dir>/<task_id>/`) — the executor's
  captured logs land there alongside `executor.md` and `changed-files.txt`.
- Lever 4 research depends on external platform behavior (Claude Code `paths:` frontmatter and
  PreToolUse `additionalContext` injection) that may have changed since June 2026, and on the
  Claude Code digest repo list as a prior-art source — both resolved during the research, not
  assumed here.

## Architecture

Prose edits to skill/rule files plus minor diff-artifact plumbing in `mine.review`. No code
modules, no new mechanisms. Sequenced lowest-risk-first: **Lever 3 → Lever 2 → Lever 1 → Lever 4
(research)**.

### Lever 3 — Executor runtime discipline (`mine.orchestrate`) — narrowed post-challenge

Insertion points confirmed by reconnaissance:
- `skills/mine.orchestrate/SKILL.md` executor launch prompt (~lines 305–343), after the `## Lint
  command` slot: add a `## Output capture` block — capture raw test/lint output to
  `<dir>/<task_id>/test-output.log` / `lint-output.log` rather than inlining (FR#7), and a narrowed
  re-run rule: do not re-run the *full suite* mid-task to verify an edit (the Step 9 gate does
  that); the targeted TDD run and re-reading the just-edited file remain expected (FR#8).
- `skills/mine.orchestrate/implementer-prompt.md`: mirror the same points, and **reword** the
  existing Self-Review line "All tests pass (run the test command, confirm output)" to "Targeted
  tests for this change pass (TDD run); full-suite verification is the Step 9 gate's job" (FR#9,
  M5) — a reword,
  not an append, so the contract is internally consistent.
- Do NOT add a blanket "don't re-read files" rule. Do NOT add a "run targeted tests not the full
  suite" rule without a targeting mechanism (there is none; the executor is handed one canonical
  test command). Both were cut after challenge.

### Lever 2 — `mine.review` diff artifact + `mine.clean-code` within-checker chunking — mapping corrected

- `skills/mine.review/SKILL.md`: after `scope-detection.md` resolves the diff command, the
  orchestrator runs it once, writes output to a `get-skill-tmpdir` temp file, records the HEAD SHA,
  and each critic prompt says: "A pre-computed diff (against `<SHA>`) is at `<path>` — read it;
  read changed files in full only for surrounding context; do not re-run the diff command to
  reconstruct the changeset. If HEAD has moved past `<SHA>`, fall back to the live diff." Lifecycle:
  created by the orchestrator, lives in the run's tmpdir, cleaned with it (FR#5, M2, M3).
- `skills/mine.clean-code/SKILL.md`: keep the "read each file IN FULL" mandate. Above ~10 changed
  files, batch the file set and dispatch *each* of `llm-checker` / `lazy-checker` / `nitpicker` once
  per batch (e.g., 3 checkers × 2 batches = 6 dispatches), each reading its batch in full; merge
  each checker's findings across batches. Every file keeps all three lenses (FR#6, M1). At/below the
  threshold, unchanged.
- `mine.challenge` is **not** touched (it has no diff mode). The earlier inclusion was a factual
  error caught by all three critics.

### Lever 1 — Planning target-file list (`mine.plan`, `mine.define`, `decomposition-discipline.md`) — threshold dropped

- `skills/mine.plan/SKILL.md`: promote the existing soft "Name exact file paths" guidance
  (~line 288) into a **required task field** (target files: create/read/modify/delete). Source it
  from `mine.define`'s Changed Files inventory when present, else derive it during Phase 2
  exploration. Do NOT add a file-count sizing axis (cut after challenge).
- `skills/mine.plan/reviewer-prompt.md` (item #8): extend the self-containment check to also assert
  the target-file field is present and concrete. No threshold check.
- `skills/mine.define/SKILL.md`: the design.md `## Impact` → Changed Files section already exists;
  ensure the per-sub-problem file mapping is concrete enough for `mine.plan` to slice into per-task
  target-file lists. Treated as input to the plan, not a hard upstream gate.
- `rules/common/decomposition-discipline.md`: add a per-task target-file / context-footprint
  consideration to the four-questions framing (no count threshold), and update the
  `SYNC: invariants.md` block if the addition warrants a promoted invariant.

### Lever 4 — Baseline trim (RESEARCH ONLY — no edits this round)

The ~44k floor is the dominant tax, paid by every subagent regardless of job. Prior art:
`design/research/2026-03-16-hot-cold-architecture/` and
`design/research/2026-06-08-conditional-rule-loading/`; partial fix already shipped in PR #366
(−46% always-loaded rule lines). The deeper per-subagent scoping fix was blocked on broken platform
features: `paths:` frontmatter (issues #16299/#16853) and PreToolUse `additionalContext` injection
(issues #19432/#55889).

Scope a research task (no skill edits) to answer:
1. **Prior art** — run `/mine.prior-art`, **incorporating the repos surfaced in the Claude Code
   digest**, to find how others have reduced per-subagent baseline context since June 2026. (Pointer
   to the digest source to be supplied at run time — see Open Questions.)
2. Have the blocking platform bugs (`paths:` frontmatter, `additionalContext` injection) moved?
3. What is the *actual* baseline composition? Measure empirically from subagent JSONLs — split
   system-prompt vs tool schemas vs rules vs scaffolding — rather than estimating. Evaluate
   scaffolding-trim (passing `tdd.md`/other scaffolding by path instead of inlining) as the one
   lever actionable today, against the ~3–4k it recovers.

## Replacement Targets

No code is replaced. Within `mine.review`'s diff-mode critic prompts, the per-critic
`Run: <diff command>` instruction is superseded by the diff-artifact reference — an instruction
change within one skill, not a module removal. `mine.clean-code` keeps its scope instruction and
gains batching. No other instruction is removed.

## Convention Examples

Not applicable — the changed artifacts are skill `SKILL.md` / supporting `.md` / rule files
(instruction prose), not application code with reusable code-shape conventions. The relevant
conventions live in CLAUDE.md (path refs via `${CLAUDE_HOME:-~/.claude}`, temp files via
`get-skill-tmpdir`) and the existing structure of the target skills, which the edits follow.

## Alternatives Considered

- **File-count split threshold (a planning split rule of "more than a dozen target files →
  split/justify," unrelated to clean-code's ~10-file chunking trigger).** *Cut after challenge.*
  File count tracks neither measured failure mode (Mode A was a critic's read volume, Mode B was
  iteration churn) and contradicts `mine.define/SKILL.md:523` ("File lists matter; file counts
  don't"). It also needed an unenforceable justification escape hatch. The target-file *list* is
  kept; the count threshold is gone.
- **Blanket "don't re-read files after editing" (original FR#10).** *Cut after challenge.* It
  contradicted `implementer-prompt.md:82,86,165` and `tdd.md:30–36` and would have produced
  evidence-free DONE verdicts. Narrowed to "no full-suite re-run mid-task."
- **"Run targeted tests not the full suite" (original FR#8).** *Cut after challenge.* The executor
  is handed one canonical test command with no targeting mechanism; "prefer targeted" would degrade
  to guessing and risk false-green loops. The real win — not dumping full output and not re-running
  the *full suite to verify* — is kept via FR#7/FR#8.
- **Diff artifact for `mine.challenge` / for all review skills uniformly.** *Cut.* `mine.challenge`
  has no diff mode; `mine.clean-code` deliberately reads every file in full (chunking is its lever).
- **Token-estimate sizing formula.** *Cut earlier.* Inputs are guesses; adds ceremony without
  accuracy.
- **A PreToolUse hook injecting a per-subagent trimmed rule set.** *Deferred to Lever 4 research.*
  The `additionalContext` injection path is the platform feature documented as broken (#19432/#55889).
- **Do nothing / raise the compaction threshold.** Not available — the threshold is
  harness-controlled, and doing nothing leaves measured degradation in every multi-task run.

## Test Strategy

N/A — no executable test infrastructure covers skill-prose behavior. "Tests" are structural and
manual:

### Existing Tests to Adapt
- No unit tests affected. `tests/test_hooks.py` covers hook scripts; `subagent-compaction-check.sh`
  is unchanged.

### New Test Coverage
- `agnix-check` (skill schema validation) must pass on every edited skill.
- FR verification is by re-reading the edited prompts against the existing contract (AC#8), plus a
  dogfood check: re-run a representative `mine.review` and `mine.orchestrate` flow and confirm no
  `compact_boundary` event in the subagent JSONLs for a task/critic that previously compacted.

### Tests to Remove
- None.

## Documentation Updates

- `REFERENCE.md` — only if a skill's described behavior changes materially; these are internal
  mechanics, so likely a no-op. Confirm during plan.
- Capabilities files — no trigger-phrase changes; no update expected.
- No CHANGELOG entry for the design itself; the implementing PR adds one per repo convention.

## Impact

### Changed Files
- `skills/mine.orchestrate/SKILL.md` — executor prompt: output-capture + no-full-suite-re-run (Lever 3)
- `skills/mine.orchestrate/implementer-prompt.md` — mirror + reword Self-Review test line (Lever 3)
- `skills/mine.review/SKILL.md` — diff-artifact plumbing with HEAD-SHA + lifecycle (Lever 2)
- `skills/mine.clean-code/SKILL.md` — within-checker batching above ~10 files (Lever 2)
- `skills/mine.plan/SKILL.md` — required target-file field, no count threshold (Lever 1)
- `skills/mine.plan/reviewer-prompt.md` — checklist item: target-file present & concrete (Lever 1)
- `skills/mine.define/SKILL.md` — ensure Changed Files inventory is plan-consumable input (Lever 1)
- `rules/common/decomposition-discipline.md` — target-file/footprint consideration + SYNC (Lever 1)
- `skills/mine.challenge/SKILL.md` — **NOT modified** (corrected from the pre-challenge draft)
- (Lever 4: no files edited — research artifact written under `design/research/` later)

### Behavioral Invariants
- Critic checklists, review dimensions, severity filters, and the TDD red/green/refactor + Verify
  (file:line evidence) contract behave identically. This is a context-budget change, not a behavior
  change (AC#8 is the guard, verified against the contract clauses, not by diff inspection alone).
- Path-mode review behavior unchanged; only diff mode gains the artifact.
- `mine.orchestrate`'s Step 9 test/lint gate and parallel review steps are unchanged and remain the
  verification source of truth.
- `mine.challenge` behavior is entirely unchanged.

### Blast Radius
- Every future run of `mine.plan`, `mine.orchestrate`, `mine.review`, and `mine.clean-code` across
  all projects using this Claudefiles install. Prose/instruction-level and reversible per file, but
  it touches the core build/review loop — the dogfood verification (re-run a real flow, confirm no
  compaction, confirm no TDD-contract regression) matters.

## Open Questions

- **Claude Code digest source for the Lever 4 prior-art run.** The research task must incorporate
  the digest's repo list; the pointer to that digest (location/format) needs to be supplied when
  the Lever 4 research runs. Not a blocker for Levers 1–3.
