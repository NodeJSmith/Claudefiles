# Design: Orchestrate Resilience

**Date:** 2026-03-25
**Status:** archived
**Research:** design/research/2026-03-25-orchestrate-checkpoint/research.md

## Problem

The orchestrator (`mine.orchestrate`) has four quality gaps:

1. **No persistent state.** If context compacts or a session ends mid-run, the orchestrator loses its loop index, WARN counter, visual_mode flag, verdict history, tmpdir path, and dev server URL. WP lane state in frontmatter survives, but everything else is gone. A resumed run can't recover the full picture.

2. **Shallow integration gap detection.** The implementation review's checklist item #6 ("Do the tasks wire together correctly?") is too vague to catch real-world failures like "all WPs done but nothing wired up to the frontend." The reviewer needs more specific heuristics.

3. **No automatic challenge gate.** The user manually runs `/mine.challenge` after every orchestration run. This should be built into the flow so it happens automatically before declaring done.

4. **WARNs are auto-continued past.** When the spec reviewer returns WARN, the orchestrator increments a counter and continues. This ships known issues. WARNs should trigger a fix loop, not a shrug.

## Non-Goals

- **Guardrails file** (Ralph-inspired learned constraints). Deferred — no evidence of cross-WP failure propagation. Revisit after collecting real orchestration failure data.
- **Per-WP integration sniff test.** Deferred — grep-based function call checking is insufficient for the motivating failure (route registration, config wiring, DI containers are not detectable this way).
- **spec-helper checkpoint I/O.** ~~Start with SKILL.md Read/Write calls.~~ Implemented in spec-helper after challenge review flagged LLM text parsing as highest-confidence fragility (3/3 critics). See `checkpoint-*` subcommands.
- **Full Ralph loop architecture.** Not restructuring the orchestrator's execution model.

## Architecture

### 1. Checkpoint File

**Location:** `<feature_dir>/tasks/.orchestrate-state.md`

**Role:** Volatile cache. WP frontmatter (`lane` field) is the authoritative source of truth. If the checkpoint is missing or stale, the orchestrator degrades gracefully — it can reconstruct partial state from WP frontmatter (done = completed, for_review = BLOCKED, doing = interrupted) but loses verdict granularity (PASS vs WARN), the WARN counter, tmpdir path, and visual_mode flag.

**Format:**

```markdown
# Orchestration State

feature_dir: design/specs/008-orchestrate-resilience
tmpdir: /tmp/claude-mine-orchestrate-a8Kx3Q
visual_mode: enabled
dev_server_url: http://localhost:3000
warn_counter: 1
last_completed_wp: WP03
started_at: 2026-03-25T14:30:00
base_commit: a1b2c3d

## Verdicts

### WP01 — Set up data model
verdict: PASS
commit: d4e5f6a

### WP02 — Implement service layer
verdict: WARN
commit: b7c8d9e
notes: test coverage low

### WP03 — Write integration tests
verdict: PASS
commit: f0a1b2c
```

**Key fields:**
- `base_commit` — the commit SHA recorded at orchestration start, before any WP execution. Used by the end-of-orchestration challenge to scope its diff precisely to what the orchestrator changed.
- `warn_counter` — consecutive WARN count (resets on PASS, gates at 3). Reset to 0 on resume — it detects within-session quality degradation, which is reset by fresh context.
- `last_completed_wp` — the last WP that passed the review gate and was moved to `done`.
- Verdicts section — append-only blocks, one per completed WP. Each block has `verdict`, `commit` (WIP commit SHA), and optional `notes`. The orchestrator only appends new blocks — it never rewrites previous verdicts. This eliminates formatting drift over 4-8 iterations. A display table is reconstructed from these blocks for the Phase 3 summary.

**Write points:**
1. After Phase 0 completes — initial state (feature_dir, tmpdir, visual_mode, dev_server_url, base_commit, started_at)
2. After each WP verdict — update last_completed_wp, verdicts table (including commit SHA), warn_counter
3. After user gate decisions — if user chose "stop here", record the reason

**Per-WP commit stamping:** After a WP passes all review gates, the WIP commit (Section 3) is created first, then the commit SHA is recorded in the verdict block. The commit column always captures a unique SHA per WP thanks to the WIP commit.

**Write strategy:** The key-value header section is rewritten in full on every write (~10 lines, stable). The verdicts section is append-only — each WP verdict is appended as a new block. The orchestrator never rewrites previous verdict blocks. This hybrid approach keeps the header current while eliminating formatting drift in the growing verdicts section.

**Staleness detection:** On startup, if a checkpoint exists and `started_at` is older than 24 hours, default to "restart" in the resume prompt.

**Cleanup:** Delete the checkpoint file after the user chooses at the post-orchestration review results gate (the very last step). If the user chose "Stop here" at any point, the checkpoint persists for resume.

**Gitignore:** Add `tasks/.orchestrate-state.md` to `.gitignore` conventions. This is runtime state, not a design artifact.

#### Resume flow

At the top of Phase 0, before the normal flow:

1. Check for `<feature_dir>/tasks/.orchestrate-state.md`
2. If not found → proceed with normal fresh-start flow
3. If found → read the file, then prompt:

```
AskUserQuestion:
  question: "Found orchestration state from <started_at>. <N> of <M> WPs completed (<verdicts summary>). Resume or restart?"
  header: "Resume"
  options:
    - label: "Resume from <next WP>"
      description: "Continue where we left off — tmpdir: <path>, visual_mode: <value>"
    - label: "Restart fresh"
      description: "Delete the checkpoint and start from the beginning"
```

On resume:
- Restore all key-value fields from the checkpoint
- Verify tmpdir exists. If not, create a new one and note the old one is lost (subagent outputs from prior WPs are gone, but code changes are in git and verdicts are in the checkpoint)
- Reset `warn_counter` to 0 (consecutive counter loses meaning across sessions)
- Skip to the next WP after `last_completed_wp`
- Re-read the design doc and all WP files (they may have been edited between sessions)

On restart:
- Delete the checkpoint file
- Proceed with the normal Phase 0 flow

### 2. Strengthen Implementation Review Integration Gap Detection

**File changed:** `skills/mine.implementation-review/reviewer-prompt.md`

**Current state:** Item #6 is three lines:
```
Do the tasks wire together correctly? Are there missing glue pieces?
Look for: a function defined in task 2 that task 3 was supposed to call,
but the call isn't present; config values that task 1 added but task 4
never reads; module-level registration that was deferred and forgotten.
```

**Proposed change:** Expand item #6 with specific integration heuristics that match common "not wired up" failure patterns:

```markdown
### 6. Integration gaps

Do the tasks wire together correctly? Are there missing glue pieces?

**Verification method:** For each new public function, class, component, route handler, or
config key introduced by any WP, grep the codebase for at least one consumer (import, call,
reference, or registration). A definition with zero consumers is a gap.

Look for:
- Functions or classes defined but never imported or called outside their own module
- API route handlers defined but never registered in the router/URL configuration
- Config keys or environment variables defined but never read by the consuming code
- Components or templates created but never mounted, imported, or included by a parent
- Event handlers written but never subscribed to an event bus or dispatcher
- Database models or migrations created but no corresponding repository/service integration
- DI/service registrations missing for newly defined services
- Frontend components created but not referenced in any route, page, or layout
- Shared types or interfaces defined but not imported by the modules that should use them

When checking, distinguish between:
- **True gap** (defined, zero consumers anywhere) → FAIL
- **Test-only consumer** (only used in test files, never in production code) → WARN
- **Properly wired** (at least one production consumer) → PASS
```

This transforms item #6 from "look for missing glue" (vague) to a concrete verification method (grep for consumers) with an enumerated list of integration patterns.

### 3. WIP Commits Per WP

After each WP passes all review gates (Step 9 verdict is PASS or WARN-then-fixed), create a WIP commit before updating the checkpoint:

```bash
git add -A && git commit -m "WIP: WP<NN> — <title>"
```

This serves three purposes:
- **Per-WP traceability**: the checkpoint's `Commit` column captures a unique SHA per WP
- **Rollback points**: `git revert` or `git reset` can target a specific WP's changes
- **Auto-challenge scoping**: `git diff base_commit..HEAD` returns meaningful results (without WIP commits, all changes are uncommitted and the diff is empty)

WIP commits are squashed or rebased before merge — they're execution artifacts, not final history.

### 4. Streamlined Post-Orchestration Flow

After all WPs are processed, the orchestrator runs a three-step review pipeline:

#### Step 1: Phase 3 summary (automatic)
Print the kanban (`spec-helper status`) and verdict table (reconstructed from checkpoint verdict blocks).

#### Step 2: Implementation-review (automatic, gates on blocking issues)
Invoke `/mine.implementation-review` automatically (skip the current "Run it?" prompt).

**If impl-review returns APPROVE** — continue to Step 3 automatically. Surface any non-blocking suggestions alongside challenge findings later.

**If impl-review returns REQUEST_FIXES or ABANDON** — stop and prompt the user immediately:

```
AskUserQuestion:
  question: "Implementation review found blocking issues: <summary>. What next?"
  header: "Impl-review gate"
  options:
    - label: "Address fixes"
      description: "Dispatch a fresh executor subagent with the findings, then re-run reviewers"
    - label: "Stop here"
      description: "Pause; I'll address findings manually"
```

On "Address fixes": dispatch a **fresh executor subagent** with the impl-review findings, the relevant file paths, and a "fix these issues" instruction. After the subagent completes, re-run code-reviewer + integration-reviewer on the fix diff, then re-run implementation-review. If it passes, continue to Step 3.

**Rationale for gating here**: Blocking impl-review issues should be fixed *before* the challenge runs. The challenge would likely raise the same concerns, wasting three Opus critics on problems the user already knows about.

#### Step 3: Auto-challenge (automatic, always presents findings)
Invoke `/mine.challenge` scoped to the orchestrator's changes.

**Challenge scope:** Diff against `base_commit` (recorded in checkpoint at orchestration start):

```bash
git diff --name-only <base_commit> HEAD
```

Pass the changed file list to `/mine.challenge` as the target. The challenge runs its standard three-critic flow against the code diff. If no files changed (all WPs were no-ops), skip the challenge.

**Challenge results prompt:** Present findings to the user (this is the primary user interaction point):

```
AskUserQuestion:
  question: "Challenge complete: <N findings, highest severity>. Implementation review: <APPROVE + any suggestions>. What next?"
  header: "Review results"
  options:
    - label: "Address findings"
      description: "Dispatch a fresh executor subagent with the findings, then re-review"
    - label: "Accept and ship"
      description: "Findings noted — proceed to /mine.ship"
    - label: "Stop here"
      description: "Pause; I'll address findings manually"
```

On "Address findings": dispatch a **fresh executor subagent** (not the orchestrator inline) with the challenge findings, the relevant file paths, and a "fix these issues" instruction. The subagent gets clean context. After the subagent completes, re-run code-reviewer + integration-reviewer on the fix diff, then re-run the challenge. Loop until the user is satisfied.

On "Accept and ship": invoke `/mine.ship`.

On "Stop here": leave the checkpoint in place. The user can resume later.

**Why a fresh subagent for fixes**: The orchestrator at this point has maximum context from the full WP run. The challenge skill's own contract says "findings only, no fixes." Delegating fixes to a fresh subagent gives clean context for code writing and keeps the orchestrator as a coordinator, not a code writer.

**Checkpoint note:** The checkpoint enables clean resume of the execution loop but does not preserve cross-WP context accumulated during execution. A resumed run operates with the same quality as a fresh run starting from the next WP.

**Cleanup:** Delete the checkpoint file after the user chooses at the review results gate (the very last step). If the user chose "Stop here" at any point, the checkpoint persists for resume.

### 5. WARN = Fix, Not Skip

**Current behavior** (`SKILL.md:341`): PASS or WARN → auto-continue. WARN increments a consecutive counter; 3 consecutive WARNs trigger a checkpoint.

**New behavior:** WARN triggers a fix loop, similar to the FAIL retry flow but automatic (no user gate needed).

**Flow when spec reviewer returns WARN:**

1. Read the spec reviewer's WARN details
2. Re-run the executor with feedback:
   - Add a `## Previous review feedback` section to the executor prompt
   - Include the spec reviewer's WARN verdict and specific issues
   - Instruction: "The spec reviewer found these issues. Fix them before proceeding."
3. Re-run the spec reviewer on the executor's updated output
4. If still WARN after 1 retry attempt → escalate to the user (same gate as FAIL)
5. If PASS → continue to Step 7 (code reviewer) as normal. The WARN retry replaces only Steps 4 and 5 — Steps 7 (code reviewer), 8 (integration reviewer), and 8.5 (review gate) still run on the fixed code.

**Retry budget:** Max 1 automatic retry per WP for WARN. On the second WARN, present the user with the FAIL gate options (fix and retry / mark as blocked / stop here). WARN means "minor gaps" — if one retry can't fix a minor gap, either the gap isn't executor-fixable (it's a WP-level spec issue) or the spec reviewer's bar is miscalibrated. Either way, escalate.

**Checkpoint interaction:** The WARN fix loop happens within a single WP's execution. The checkpoint is not updated during retries — it only updates after the final verdict (PASS after fix, or user decision after escalation).

**Previous review feedback section (also applies to FAIL retries):**

This addresses challenge finding #2 from the orchestrator challenge (stateless retries). On any retry (WARN or FAIL), the executor prompt gets:

```markdown
## Previous review feedback

### Attempt N — <WARN|FAIL>

**Spec reviewer:**
<full spec reviewer verdict and details>

**Code reviewer** (FAIL retries only — empty for WARN retries):
<unresolved CRITICAL/HIGH findings>

**Visual reviewer** (FAIL retries only — empty for WARN retries):
<FAIL/WARN details>

Fix these issues before proceeding. Do not repeat the same approach that caused them.
```

**Timing note:** For WARN retries (spec reviewer loop at Step 5), only the spec reviewer section is populated — code reviewer and visual reviewer haven't run yet. For FAIL retries (after Step 9), all reviewer sections are populated since all reviewers have completed. Only include the most recent attempt's feedback (not accumulated). Truncate to 50 lines if the feedback exceeds that length.

## Alternatives Considered

### Guardrails file (Ralph-inspired)
Deferred. The Ralph pattern's guardrails are designed for repeated execution of the same task. The orchestrator runs different WPs sequentially — lessons from WP02's failure rarely generalize to WP05. No evidence exists of cross-WP failure propagation. Revisit after collecting real data.

### Per-WP integration sniff test
Deferred. "Grep for functions and check if called" is insufficient for the motivating failure. Route registration, config consumption, DI containers, and event subscriptions are not detectable by function-call grepping. The spec reviewer also has WP-scoped context only — it can't verify cross-WP integration. Strengthening the implementation review (which sees all changed files) is more effective.

### spec-helper checkpoint I/O
~~Deferred.~~ **Implemented** — challenge review (3/3 critics) flagged LLM-parsed markdown as the highest-confidence fragility. Added `checkpoint-*` subcommands to spec-helper with schema validation, version field, and atomic writes. The abstraction boundary concern was outweighed by the reliability benefit of deterministic I/O.

### New "challenge gate" mechanism
Rejected in favor of invoking the existing `/mine.challenge` skill. Defining a new gate mechanism with its own prompt, verdict vocabulary, and failure path would overlap with both `/mine.challenge` and `mine.implementation-review`. Using the existing skill is simpler and well-understood.

## Open Questions

- [ ] **Should the auto-challenge use a lighter model?** Running full `/mine.challenge` (three Opus critics) after every orchestration is expensive. Consider whether Sonnet critics are sufficient for the post-orchestration pass, or whether the user should choose the model tier.
- [ ] **Context budget for auto-challenge.** After a full orchestration run, the orchestrator's context is deep. The challenge's synthesis phase runs in the orchestrator's context. Consider dispatching the full challenge (including synthesis) as a single subagent that writes its findings file — the orchestrator just reads the file and presents. This keeps the challenge's context separate from the orchestrator's accumulated state.

## Impact

**Files changed:**

| File | Change | Risk |
|------|--------|------|
| `skills/mine.orchestrate/SKILL.md` | Checkpoint writes/reads, resume flow, base_commit stamping, WIP commits, WARN fix loop, streamlined post-orchestration flow (auto impl-review + auto challenge), previous review feedback on retry | Medium — adds ~80-100 lines of instructions to a 444-line file |
| `skills/mine.orchestrate/implementer-prompt.md` | Add `## Previous review feedback` section placeholder | Low — additive |
| `skills/mine.implementation-review/reviewer-prompt.md` | Expand item #6 with specific integration heuristics | Low — prompt improvement |
| `skills/mine.implementation-review/SKILL.md` | Made non-user-invocable; removed Phase 4 gate — orchestrator owns all post-execution UX | Low — simplification |
| `packages/spec-helper/src/spec_helper/checkpoint.py` | New module for checkpoint read/write with schema validation, atomic writes, frozen dataclasses | Medium — new module scoped to checkpoint I/O |
| `packages/spec-helper/src/spec_helper/{cli,commands}.py` | Wire `checkpoint-{init,read,update,verdict,delete}` subcommands | Low — additive CLI surface |

**Blast radius:** Changes affect the orchestrator, implementation-review, and spec-helper (new checkpoint subcommands). No changes to the caliper v2 file format or other skills in the pipeline. The checkpoint file is a new artifact in the feature directory but is gitignored and deleted on completion.

**Dependencies:** None beyond existing tools. Checkpoint I/O moved from LLM text manipulation to `spec-helper` CLI after challenge review flagged parsing fragility.
