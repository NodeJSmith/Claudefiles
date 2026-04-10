---
proposal: "Orchestration improvement backlog from landscape survey"
date: 2026-04-10
status: Draft
flexibility: Backlog
motivation: "Systematic survey of 10+ orchestration frameworks identified additive improvements to caliper — some cheap, some structural. Written before vacation as a return-to reference."
constraints: "All Phase 1 items must be graftable without changing caliper's core architecture (pipeline, gates, verdict assembly). Phase 2 is explicitly structural and should be treated as a separate design effort."
non-goals: "Moving toward superpowers' 'complete code in plan' model. Moving toward Ralph-style loop execution. Adding multi-provider support."
depth: deep
---

# Orchestration Improvements: Post-Survey Backlog

**Context**: On 2026-04-10, conducted a systematic survey of 10+ orchestration frameworks (obra/superpowers, steveyegge/gastown, EveryInc/compound-engineering-plugin, Priivacy-ai/spec-kitty, code-yeongyu/oh-my-opencode/Sisyphus, Ralph Loop, Garry Tan's gists, xiaobei930/cc-best, therealarthur/myrlin-workbook, coleam00/Archon, github/spec-kit) to answer "what don't I know about how others approach this problem?" Full survey brief at `/tmp/orchestration-survey.md` (session artifact, may be gone).

**Key finding**: Caliper is a *pipeline* orchestrator in a field of *loop* orchestrators. It has the deepest per-WP review pipeline of anything surveyed. The improvements below are additive to that pipeline — not replacements, not direction changes. We explicitly don't want to go toward superpowers' "complete code in the plan" model because all our code is novel and that approach just moves unvetted risk into the planning step without challenging it.

---

## Phase 1: Additive Improvements (graft-on, no architectural change)

These six items can be implemented independently and in any order. None changes caliper's core structure.

---

### P1-1: `NEEDS_CONTEXT` executor verdict

**Source**: obra/superpowers — `subagent-driven-development` skill
**Where it fits**: Executor contract (`implementer-prompt.md`), verdict handling in `mine.orchestrate` Phase 2

**What it is**:
Superpowers uses four executor terminal states: `DONE`, `DONE_WITH_CONCERNS`, `NEEDS_CONTEXT`, `BLOCKED`. We currently have three: `PASS`, `FAIL`, `BLOCKED`. The missing one is `NEEDS_CONTEXT` — meaning "I can't complete this WP because it's under-specified, not because of an architectural issue."

**Why it matters**:
Currently, any executor failure that isn't clearly a code-level problem gets escalated as BLOCKED → requires design revision. But a lot of failures are actually "the WP didn't specify which field to use" or "the WP said 'add validation' without saying what valid means." That's a *planner* problem, not a *designer* problem. The wrong escalation path forces a full design revision when you actually just need to clarify a subtask.

**How to implement**:
- Add `NEEDS_CONTEXT` as a fourth terminal state in `implementer-prompt.md` with a clear definition: "The WP is under-specified in a way that prevents implementation. This is not an architectural issue — the design is correct, but the task instructions are missing a detail the designer cannot resolve."
- Add handling in `mine.orchestrate` Phase 2 FAIL path: when verdict is `NEEDS_CONTEXT`, present to user with a focused "clarify the WP and retry" path instead of "revise the design."
- The escalation chain becomes: `NEEDS_CONTEXT` → WP clarification → retry | `BLOCKED` → design revision

**Effort**: Small. Two files: `implementer-prompt.md` and the FAIL handling section of `SKILL.md`.
**Risk**: Low. Purely additive to the executor vocabulary.

---

### P1-2: `/mine.compound` — Learning capture after ship

**Source**: EveryInc/compound-engineering-plugin — `/ce:compound` command (v2.64.0, active as of 2026-04-10, 13.9k stars, real project)
**Where it fits**: Post-ship, after `/mine.ship`. New skill in `skills/mine.compound/`.

**What it is**:
A dedicated post-ship phase that extracts durable learnings from the completed feature and writes them to persistent memory. Compound-engineering's framing: "each unit of work should make subsequent work easier." Their `/ce:compound` reads the feature artifacts after shipping and produces a learnings document.

**Why it matters**:
We have the substrate (feedback files in memory, error-tracking.md, challenge findings, research briefs) but no skill that systematically runs after a feature ships to extract "what surprised us, what should we do differently next time, what conventions should we update." Every feature is currently a fresh start from a memory standpoint. This is probably the single biggest missing piece in terms of long-term compounding value.

**How to implement**:
New skill `/mine.compound` (user-invocable, runs after `/mine.ship`). Takes the feature directory as an argument. Reads:
- `design.md` (original intent)
- `research/*.md` (what was investigated)
- `design/critiques/` (challenge findings from the run)
- Per-WP `spec-reviewer.md` and `code-review.md` files (what the reviewers caught)
- Any `feedback_*.md` files written during the session
- The git log for the feature branch (what actually shipped)

Produces a `learnings.md` file in a persistent location (e.g., `~/.claude/projects/<repo>/memory/learnings/NNN-slug.md`) with structured sections:
- What surprised us (gaps between design intent and implementation reality)
- Patterns that should become rules (things the reviewer caught repeatedly)
- Things to watch for in future features (emerging anti-patterns)
- Any CLAUDE.md or rules updates warranted

**Effort**: Medium. New skill, reads multiple artifact types, writes to persistent memory. Well-scoped but non-trivial.
**Risk**: Low. Purely additive, no pipeline changes.

**Open question**: Should `/mine.ship` prompt to run `/mine.compound` after completion, or is it always a separate manual invocation?

---

### P1-3: `/mine.next` — State-driven auto-router

**Source**: xiaobei930/cc-best — `/cc-best:iterate` command
**Where it fits**: New top-level skill. Replacement for "which command do I run now?"

**What it is**:
A single command that reads the current state of the most recent feature directory and dispatches to the right skill automatically. cc-best's `/cc-best:iterate` reads `progress.md`, determines where the project is in the pipeline (no spec → run specify; has spec, no design → run design; has design, no WPs → run draft-plan; etc.), and dispatches without asking.

**Why it matters**:
Currently the user has to know the pipeline order (specify → design → draft-plan → plan-review → orchestrate) and remember which phase they're in. After returning from vacation or after a context compaction, "where was I?" is a manual archaeology task. `/mine.next` reads state and tells you, or just runs the right thing.

**How to implement**:
New skill that checks (in order):
1. Is there a `design/specs/` directory with an active spec? If not → suggest `/mine.specify`
2. Is there a `spec.md` but no `design.md`? → dispatch `/mine.design`
3. Is `design.md` at status `approved` but no `tasks/WP*.md`? → dispatch `/mine.draft-plan`
4. Is there a `tasks/WP*.md` but no approved plan-review? → dispatch `/mine.plan-review`
5. Is there an approved plan with WPs in `planned` state? → dispatch `/mine.orchestrate`
6. Is there an active checkpoint (WPs in `doing`)? → dispatch `/mine.orchestrate` (resume)
7. Are all WPs `done`? → suggest `/mine.ship`

State detection via `spec-helper status` + checkpoint read. Show the user what state was detected and what it's about to run before dispatching.

**Effort**: Small-medium. Mostly state-reading logic, no new pipeline stages.
**Risk**: Low. Purely additive.

---

### P1-4: Hashline-style edit validation

**Source**: code-yeongyu/oh-my-opencode — "Sisyphus" orchestrator, Hashline mechanism
**Where it fits**: Executor contract, potentially a new pre-commit validation step

**What it is**:
Each line of code carries a short content hash tag inline: `11#VK| function hello() {`. When the executor makes an edit, it references these hash tags. If the file content has changed since the executor last read it (stale context — another WP modified the file, or the user edited it), the hash won't match and the edit is **rejected before execution**.

Sisyphus claims this improved edit success rate from 6.7% to 68.3% — a striking number. The source is a blog post, not a controlled study, so treat with appropriate skepticism until validated.

**Why it matters**:
Caliper currently relies on the executor correctly identifying edit targets. If a file changed since the executor read it (e.g., a previous WP modified it, or the file was touched during a retry), nothing catches the stale-context edit until a reviewer notices incorrect output. Hashline catches it at the edit site — before the damage is done. This is a prevention approach rather than a retry approach, and they're complementary.

**How to implement**:
This is the most technically novel item in the list and warrants a prototype before committing:
1. Investigate Sisyphus' actual Hashline implementation in oh-my-opencode (the README describes the pattern; the actual implementation may be in prompt files)
2. Prototype: add a "hash your edit targets before reading" instruction to `implementer-prompt.md` with a specific format
3. Validate: run a few caliper features with and without, check whether stale-context edit failures actually occur and whether Hashline would have caught them
4. If the improvement is real, formalize as a required step in the executor contract

**Effort**: Medium for prototype, potentially large for full integration.
**Risk**: Medium. If the hash format is fragile or adds too much prompt noise, it could make things worse. Prototype first.

**Open question**: Is the 6.7% → 68.3% improvement real and applicable to caliper's use pattern? Our executors are dispatched as fresh subagents per WP so stale-context risk may be lower than in a single long-running session. Worth measuring before building.

---

### P1-5: Scope Challenge gate in `/mine.plan-review`

**Source**: Garry Tan (YC president) — `plan-exit-review` gist
**Where it fits**: `skills/mine.plan-review/SKILL.md` — new Step 0 before the existing checklist

**What it is**:
Garry Tan's review framework starts with an explicit "Scope Challenge" before any review begins: "Does existing code already solve any of these sub-problems? Are we about to overengineer this? Could this be a smaller change?" Three paths: scope reduction, proceed as-is, or compressed review. The question is asked with blocking intent — not a suggestion, an actual gate.

**Why it matters**:
`/mine.plan-review` currently runs a 9-point checklist against the design + WPs. None of those 9 points is explicitly "should this be smaller?" The checklist checks coherence and completeness but not scope-appropriateness. It's possible to pass plan-review with a beautifully coherent design that's still 3x bigger than it needs to be. The scope challenge is cheap to add and catches a different failure mode.

**How to implement**:
Add a Scope Challenge section at the top of the plan-review subagent prompt:

> Before running the checklist, assess scope appropriateness. Ask: Does existing code in the repo already handle any of the sub-problems in these WPs? Are there WPs that could be deferred without blocking the core use case? Is the total WP count appropriate for the stated goal? If scope seems inflated, flag it clearly with a SCOPE-WARN finding before proceeding to the checklist. Do not suppress this finding because the design is internally coherent — coherent overengineering is still overengineering.

**Effort**: Small. Addition to the existing plan-review subagent prompt.
**Risk**: Low, but watch for false positives — a reviewer that flags scope on everything becomes noise.

---

### P1-6: Cost tracking in the checkpoint

**Source**: therealarthur/myrlin-workbook
**Where it fits**: `spec-helper checkpoint-*` schema, `mine.orchestrate` WP execution loop

**What it is**:
Myrlin tracks per-session cost. Caliper has no visibility into per-feature or per-WP cost. Given that caliper runs 5 reviewer subagents per WP plus a post-execution challenge + impl-review pipeline, feature runs are likely expensive. No numbers exist to validate or refute this.

**Why it matters**:
Can't optimize what you can't measure. Also useful for deciding when to use caliper vs a lighter approach for simpler features.

**How to implement**:
- Add a `cost_usd` field to the checkpoint schema (optional, defaults to null)
- After each subagent completes, read its token usage from the output (Claude Code exposes this in subagent results) and accumulate into the checkpoint
- Report at the end of each WP: "WP01 complete — estimated cost: $0.43"
- Report total at the end of the orchestration run

**Effort**: Small-medium. Requires understanding how Claude Code exposes token/cost data from subagent results. May require checking the claude-code API.
**Risk**: Low. Purely additive, fails gracefully if cost data isn't available.

---

## Phase 2: Worktree-based parallel execution

**Source**: Priivacy-ai/spec-kitty — lane-based worktree isolation model
**Status**: Needs its own design doc before implementation. Notes here are pre-design thinking only.

---

### Background

This is the one that's been on your mind. Caliper currently runs everything in the current working tree — one executor at a time, single writer assumption throughout. Spec-kitty's model: compute execution lanes from the WP dependency graph, assign one git worktree per lane, run WPs in parallel across lanes.

The appeal: features with independent WPs (e.g., WP01 touches the data model, WP02 adds an API endpoint, WP03 adds the frontend component — none of these strictly depend on each other) could theoretically run in parallel. A feature that takes 4 hours sequentially might take 90 minutes with lane-based parallelism.

### What spec-kitty does

- Analyzes `depends_on` frontmatter in WP files to build a dependency graph
- Computes execution lanes: sets of WPs that can run concurrently (no cross-lane dependencies)
- Creates one git worktree per lane (`git worktree add`)
- Runs one executor per worktree, isolated from others
- Merges lanes back to the main branch when each lane completes
- Uses a `claimed` lane state (between `planned` and `in_progress`) to prevent two executors from grabbing the same WP

### What this would mean for caliper

**The hard parts:**

1. **Merge conflicts on lane completion.** If WP01 and WP02 both touch `models.py` (even in different places), merging two worktrees back creates conflicts. The dependency graph catches *explicit* dependencies but not incidental file overlap. This is a real problem with no clean solution — you'd need either file-level conflict detection before launching lanes, or a merge strategy that routes conflicts to the user.

2. **Review pipeline isolation.** Each WP currently uses a per-WP tmpdir subdirectory and a shared run-level checkpoint. With parallel lanes, multiple WPs are running simultaneously — their review pipelines need to be isolated (separate tmpdirs, separate checkpoint entries) but the checkpoint needs to be writeable from multiple processes without corruption. The `spec-helper checkpoint-*` commands would need to be made concurrency-safe.

3. **Test baseline.** We capture a baseline before the first WP runs to detect regressions. With parallel execution, multiple executors are modifying code simultaneously — the baseline becomes ambiguous. The test gate can no longer simply compare "before first WP" vs "after this WP" because other WPs are also running. This is the most serious design problem.

4. **Verdict assembly across concurrent WPs.** Currently Step 8.7 assembles a verdict for one WP at a time. With parallel execution, multiple verdict assemblies are happening concurrently. The final "all WPs complete" gate needs to wait for all of them and compose across lanes.

5. **Visual verification.** Before/after screenshots assume a stable UI state. Two WPs modifying frontend code simultaneously means "before" and "after" screenshots are unreliable.

**The easier parts:**

- The `depends_on` frontmatter is already in WP files — the dependency graph is already specified
- The `spec-helper wp-move` and checkpoint commands are already abstracted — making them concurrency-safe is well-scoped
- Git worktree support exists and is well-understood (there's even a `/mine.worktree-rebase` skill)
- Lane-based execution could be opt-in: `/mine.orchestrate --parallel` while `/mine.orchestrate` stays sequential

### Pre-design questions to answer before writing a design doc

1. **How common are genuinely parallel-safe WPs in practice?** If most features have a dependency chain (WP02 depends on WP01 which depends on nothing), parallelism buys nothing. Worth auditing 5-10 recent feature WP files to see what the actual dependency graph looks like before investing in this.

2. **What's the file overlap problem?** How often do "independent" WPs in the same feature modify the same files? If the answer is "often," the merge conflict problem dominates and parallelism is more pain than gain.

3. **Can the test gate work at all in a parallel model?** The current regression detection relies on a pre-execution baseline and per-WP comparison. In parallel execution, you'd need either: (a) lane-level baselines (each lane's executor captures its own baseline before starting), (b) accept that regression detection is unavailable in parallel mode, or (c) run test gates only after all parallel lanes complete (losing per-WP granularity).

4. **Is the right abstraction "parallel WPs" or "parallel features"?** Running two completely separate features in parallel (each in their own worktree, each with their own caliper orchestration run) might deliver most of the concurrency benefit with far less complexity than parallel WPs within a single feature. This is closer to what myrlin does (managing multiple sessions) and avoids the merge/test-baseline problems entirely.

5. **What does `/mine.next` do in a parallel world?** If two worktrees are running caliper simultaneously, the state-detection logic in `/mine.next` needs to be worktree-aware.

### Suggested approach when ready to design

1. Write a separate design doc for this feature
2. Start with the simpler version: **parallel features** (not parallel WPs), using worktrees one per feature, managed from a coordinator session. This delivers concurrency without the merge/test-baseline problems.
3. If parallel features delivers most of the value, parallel WPs may not be needed.
4. If parallel WPs are still wanted after validating parallel features, treat the test-baseline problem as the primary design constraint — everything else is solvable.

---

## What we explicitly rejected (and why)

Documenting these so we don't re-evaluate them.

**Superpowers' "complete code in plan" model**: The plan contains exact code samples for the executor to apply. This eliminates executor drift by eliminating executor judgment. Rejected because: nobody vetted the code samples in the plan. The spec-reviewer checks conformance to the plan, not correctness of the plan. For novel architecture (which is most of our work), this moves unverified risk into the planning step without challenging it. Caliper's pre-execution challenge pipeline (`/mine.challenge` on the design, `/mine.plan-review` on the WPs) is the right investment instead.

**Ralph Loop model**: `while :; do cat PROMPT.md | claude-code; done` with tests as back-pressure. Good for migrations, refactoring, well-understood patterns. Not appropriate for novel code where test back-pressure isn't sufficient to catch wrong approaches. Caliper's gate-heavy model is the right trade-off for our use case.

**Gas Town multi-agent model**: 20-30 concurrent polecats with a git-backed Beads ledger. Sophisticated and interesting but solves a problem we don't currently have. Revisit if the workflow regularly involves 10+ concurrent features.

---

## Sources

- [EveryInc/compound-engineering-plugin](https://github.com/EveryInc/compound-engineering-plugin) — `/ce:compound`
- [xiaobei930/cc-best](https://github.com/xiaobei930/cc-best) — `/cc-best:iterate` auto-router
- [code-yeongyu/oh-my-opencode](https://github.com/code-yeongyu/oh-my-opencode) — Sisyphus, Hashline
- [Priivacy-ai/spec-kitty](https://github.com/Priivacy-ai/spec-kitty) — lane-based worktrees
- [obra/superpowers](https://github.com/obra/superpowers) — `NEEDS_CONTEXT` verdict
- [Garry Tan — plan-exit-review gist](https://gist.github.com/garrytan/001f9074cab1a8f545ebecbc73a813df) — Scope Challenge
- [therealarthur/myrlin-workbook](https://github.com/therealarthur/myrlin-workbook) — cost tracking
- Full survey: `/tmp/orchestration-survey.md` (session artifact — may need to regenerate)
