---
proposal: "Replace derived-from-history Phase 3 position tracking with explicit position fields in the run row"
date: 2026-09-17
status: Draft
flexibility: Exploring
motivation: "Phase 3 resume reconstructs position from gate verdicts, requiring 9 patches in PR #574 to handle derivation gaps. Auto-reset needs trustworthy position data."
constraints: "Orchestrate internals only. Auto-reset consumes whatever API is exposed but its design is out of scope."
non-goals: "Auto-reset design. Phase 1 or Phase 2 changes beyond what's needed to unify the position model."
depth: deep
---

# Research Brief: Explicit Position Tracking for mine-orchestrate

**Initiated by**: Issue #575 -- refactor mine-orchestrate's Phase 3 resume from derived-from-history to explicit position tracking, triggered by PR #574 accumulating 9 patches to close derivation gaps.

## Context

### What prompted this

PR #574 added Phase 3 resume logic -- a resume-check table mapping gate_types to completeness conditions so a resumed session could skip already-passed steps instead of unconditionally restarting at Step 1. The implementation reads gate verdicts from the DB and infers position. Nine patches followed in the same PR, each closing a derivation gap the previous patch missed:

1. Base feature: resume-check table, `gates`/`open_dispatches` on `cfl run status`
2. Missing marker: known-issues walkthrough had no gate_type at all
3. Write-back: tmpdir replacement computed but never persisted to run record
4. Fresh-entry: no-gate state fell through to resume logic instead of starting at Step 1; stale gates not invalidated after smoke-test fixes
5. Prior-phase contamination: define/plan/sketch gates made "gates is empty" check never fire
6. Staleness mechanism: replaced write-side invalidation event with read-side `reviewed_head` comparison
7. Comb fixes: smoke-test re-run range, dead config-only fast path
8. Per-gate staleness: check every gate's `reviewed_head` vs HEAD, not just the latest

Every patch is the same shape: a step or transition that did not write (or correctly persist) a durable marker, causing the derived position to be wrong. The user named this as whack-a-mole and filed issue #575 to address the root cause.

### Current state

**Phase 2** (per-task loop) has explicit position tracking via `tasks.status` (pending/executing/reviewing/fixing/done/failed/blocked/stopped). Two pure functions in `run.py` derive position on every `cfl run status` call:
- `_derive_last_completed`: last task (by array order) with `status='done'`
- `_derive_current_task`: first task with status not in (pending, done)

This works reliably because each task's state is updated atomically by guarded commands (`cfl task start`, `cfl task update`, `cfl task verdict`, `cfl task block`), and the state machine transitions are validated.

**Phase 3** (post-execution pipeline, Steps 1-7) has no explicit position tracking in the current default branch. Before PR #574, it unconditionally restarts from Step 1 on every resume. PR #574 (not yet merged) adds derived position via a resume-check table that maps gate_types to completeness conditions. The step sequence with its gates:

| Step | Name | Gate type |
|---|---|---|
| 1 | Summary | none |
| 2 | Implementation review | `impl-review` |
| 3 | Cross-file review | `cross-file-review` |
| 3.5 | Challenge | `ship-challenge` (+ event correlation) |
| 4 | Clean code | `clean-code` |
| 5 | Final review | `final-review` |
| 5.5-5.6 | Known issues walkthrough | `known-issues-walkthrough` (added by PR #574 patch 2) |
| 6 | Shipping gate | `shipping-gate` |
| 7 | Run complete | terminal action |

**The `runs` table** has: id, spec_id, base_commit, status, visual_mode, dev_server_url, tmpdir, cwd, phase, started_at, ended_at. The `phase` field tracks sketch/define/plan/orchestrate -- not sub-steps within orchestrate. There is no Phase 3 position field.

**`cfl run status`** is the only read endpoint. It returns run metadata plus tasks array with derived `last_completed`/`current_task`/`needs_intervention`. It does not query the `gates` table at all (on the default branch). PR #574 adds `gates` and `open_dispatches` to this output.

**`cfl set run`** can already modify: status, base_commit, visual_mode, dev_server_url, tmpdir, cwd, started_at, ended_at. Adding a new column to this list requires only an `ENTITY_COLUMNS["run"]` entry in `direct.py`.

**`reviewed_head`** does not exist as a stored field anywhere in the codebase. PR #574's patch 6 adds it as auto-captured data inside gate verdict JSON blobs, not as a run-level column.

### Key constraints

- The auto-reset consumer needs a single, reliable "where is this run?" answer from `cfl run status`.
- The position must survive context compaction, `/clear`, crashes, and external resets.
- Gate verdicts must remain for audit/observability regardless of their role in navigation.
- The `cfl` package owns the DB schema and the lifecycle commands; the skill files own the pipeline logic.
- Schema changes require a migration (`MIGRATIONS[9]`, `SCHEMA_VERSION` bump to 9).

## Feasibility Analysis

### What would need to change

| Area | Files affected | Effort | Risk |
|------|---------------|--------|------|
| DB schema | `packages/cfl/src/cfl/db.py` (1 file) | Low | Low -- follows established migration pattern |
| Run lifecycle | `packages/cfl/src/cfl/run.py` (1 file) | Med | Med -- `run_status` output shape changes; callers need updating |
| Direct access | `packages/cfl/src/cfl/direct.py` (1 file) | Low | Low -- add column to `ENTITY_COLUMNS` |
| Gate recording | `packages/cfl/src/cfl/gate.py` (1 file) | Low | Low -- `reviewed_head` capture already designed in PR #574 |
| CLI | `packages/cfl/src/cfl/cli.py` (1 file) | Low-Med | Low -- new command or flag for position advancement |
| Resume protocol | `skills/mine-orchestrate/resume-protocol.md` (1 file) | Med | Med -- rewrite resume logic to read position instead of deriving |
| Post-execution pipeline | `skills/mine-orchestrate/post-execution-pipeline.md` (1 file) | Med-High | Med -- add position advancement calls at every step boundary |
| Tests | `packages/cfl/tests/` (2-3 files) | Med | Low |

### What already supports this

- **Phase 2's derive pattern**: `_derive_last_completed`/`_derive_current_task` is the exact model to replicate or subsume. The infrastructure for exposing derived position through `run_status` already exists.
- **`cfl set run`**: the escape hatch for manual correction already works for any run column. A new position column would be writable via `cfl set run <id> pipeline_step=<step>` immediately.
- **Gate auto-increment**: `record_gate` already supports re-recording the same gate type with auto-incrementing iterations. This means gates can serve as an audit log without needing changes to gate infrastructure.
- **Event system**: `KNOWN_EVENT_NAMES` already has `review.*` event names that read as Phase-3-shaped. Position advancement events would follow the established pattern.
- **Migration infrastructure**: migrations 2, 3, and 7 are simple `ALTER TABLE runs ADD COLUMN` statements. Adding a new column is a well-trodden path.

### What works against this

- **Non-linear Phase 3 flow**: Steps are mostly linear but have re-entry paths (smoke-test failure reruns Steps 2-5.6, Fix now loops within steps). An explicit position must handle backward jumps, not just forward advancement.
- **Mid-step granularity**: Some steps have internal sub-loops (fixer loops, known-issues per-entry walkthrough). An explicit step field captures step-level position but not sub-step state. However, sub-step state is already handled by the steps' own idempotent re-entry logic (re-reading `known-issues.md`, re-running reviewers), so this is acceptable.
- **Two sources of position**: Phase 2 uses task statuses (per-row state machine), Phase 3 would use a run-level field. These are different mechanisms for position tracking that would need to coexist or be unified.
- **Skill file complexity**: Every step boundary in `post-execution-pipeline.md` needs a position advancement call. This is roughly 8-10 new `cfl` command invocations threaded through a long, already-complex instruction file.

## Phase/Step Inventory

Every discrete position the system needs to track across the full lifecycle:

### Phase 0 (Setup)
Not tracked in DB today. Steps: branch staleness check, feature directory discovery, design doc read, task file read, dev server check, vision check, cfl run initialization, plan snapshot. All happen in a single session before Phase 2 begins. Resume after interruption here means restarting Phase 0 from scratch -- acceptable because these steps are cheap.

### Phase 2 (Per-Task Loop)
Already tracked via `tasks.status` + `_derive_current_task`/`_derive_last_completed`. Position granularity: which task, and within a task, which sub-step (executing/reviewing/fixing). No changes needed unless unifying with Phase 3.

### Phase 3 (Post-Execution Pipeline)
The positions that need tracking, in order:

1. `phase3:summary` -- Step 1
2. `phase3:impl-review` -- Step 2 (including fixer sub-loops)
3. `phase3:cross-file-review` -- Step 3 (including fixer sub-loops)
4. `phase3:challenge` -- Step 3.5
5. `phase3:clean-code` -- Step 4
6. `phase3:final-review` -- Step 5 (including fixer sub-loops)
7. `phase3:known-issues` -- Steps 5.5-5.6
8. `phase3:shipping` -- Step 6
9. Run complete -- Step 7 (terminal)

Backward jumps: smoke-test failure resets from `phase3:shipping` back to `phase3:impl-review`. Known-issues "Fix now" triggers a final-review rerun within `phase3:known-issues`.

## Options Evaluated

### Option A: Explicit `pipeline_step` column on `runs` + `reviewed_head`

**How it works**: Add two columns to the `runs` table:
- `pipeline_step TEXT` (nullable) -- the current position within orchestrate phase. NULL before Phase 3. Values: `summary`, `impl-review`, `cross-file-review`, `challenge`, `clean-code`, `final-review`, `known-issues`, `shipping`.
- `reviewed_head TEXT` (nullable) -- the HEAD commit at the time the last step completed. Used for a single staleness check on resume.

On resume, `cfl run status` returns `pipeline_step` and `reviewed_head` directly. The resume protocol reads `pipeline_step` to know where to re-enter. If `reviewed_head` differs from current HEAD, position resets to `impl-review` (code changed since last review). Gate verdicts are recorded as today but are purely audit -- navigation reads `pipeline_step`.

Position advancement happens after a step completes: record the gate verdict first (audit), then advance `pipeline_step` to the next step and update `reviewed_head` to current HEAD. If the session dies between gate recording and position advancement, position is still at the current step -- next resume re-runs it (safe, idempotent).

A new guarded command `cfl run advance-step <step>` would enforce forward-only transitions (with an explicit backward-jump path for smoke-test failure re-runs). Or, position could be updated via `cfl set run` if transition validation is not deemed worth the complexity.

**Pros**:
- One field to read, one staleness check. Eliminates the gate-walking table and all per-gate staleness logic from PR #574.
- Position is authoritative, not inferred. No edge cases from missing markers, stale gates, or ambiguous multi-iteration gate sequences.
- External consumers (auto-reset) get a direct "where is this run?" answer from `cfl run status`.
- Follows the established migration pattern (simple `ALTER TABLE`). `cfl set run` works immediately for manual correction.
- `reviewed_head` as a run-level field is simpler than per-gate `reviewed_head` in JSON blobs (PR #574 patch 6/8).

**Cons**:
- Does not capture sub-step state (which known-issues entry in the walkthrough, which fixer iteration). Sub-step resume relies on the steps' own idempotent re-entry logic, which is the same as today.
- Adds ~8-10 position advancement calls to `post-execution-pipeline.md`, increasing instruction file length and the number of places a skill author must remember to update position.
- Phase 2 and Phase 3 use different position mechanisms (task statuses vs run column). Not unified, but they don't need to be -- they operate at different granularities.
- Backward jumps (smoke-test failure) require either a "reset" command or an escape-hatch `cfl set run` call, since a guarded `advance-step` would normally reject regressions.

**Effort estimate**: Medium. Schema migration is small, `run_status` changes are straightforward, the bulk of work is in rewriting the resume and pipeline instruction files and adding position advancement calls throughout.

**Dependencies**: None. All infrastructure exists in the cfl package.

### Option B: Derive Phase 3 position from existing `gates` table (PR #574's approach, refined)

**How it works**: Keep the current schema unchanged. Add pure derive functions to `run.py` (paralleling `_derive_last_completed`) that query run-level gates by `gate_type` and compute Phase 3 position. Surface the derived position through `run_status`. The resume-check table in `post-execution-pipeline.md` defines the completeness conditions.

This is essentially PR #574's approach but implemented at the `cfl` layer (in Python) rather than in the instruction file (in prose), making the derivation logic code-testable.

**Pros**:
- Zero schema changes. No migration needed.
- Reuses existing gate recording infrastructure without modification.
- Code-testable derivation logic (Python functions with unit tests) vs prose-defined resume table.
- Lower effort than Option A -- no migration, no new columns, no new commands.

**Cons**:
- The fundamental problem remains: position is still derived from history, not tracked explicitly. The 9-patch pattern from PR #574 demonstrates that edge cases keep appearing.
- Steps without gates (5.5/5.6 without PR #574's added `known-issues-walkthrough` gate type) require adding synthetic gates just to make derivation work -- these gates exist solely for position, not for audit.
- Multi-iteration gates and backward jumps (smoke-test failure) make "latest gate of each type" ambiguous without timestamp cross-referencing.
- External consumers still get derived, not authoritative, position data.
- `reviewed_head` must still be checked per-gate (PR #574 patches 6/8) because different gates may have been evaluated at different commits. This per-gate staleness logic is the complexity this entire issue seeks to eliminate.

**Effort estimate**: Small-Medium. Derive functions in `run.py`, wiring into `run_status`, unit tests. Resume protocol and pipeline file changes are lighter than Option A since the gate-recording call sites don't change.

**Dependencies**: None.

### Option C: Event-log position pointer

**How it works**: Use the existing `events` table as the position source. Define a new event type `pipeline.position` that records the current step as event data. On resume, the latest `pipeline.position` event for the run is the current position. No schema change to `runs`.

**Pros**:
- No schema migration. Events table already exists.
- Position history is naturally preserved (all events are append-only).
- Simple read path: `SELECT data FROM events WHERE run_id=? AND event='pipeline.position' ORDER BY id DESC LIMIT 1`.

**Cons**:
- Position is stored in JSON inside an event's `data` field rather than as a typed, CHECK-constrained column -- weaker type safety, harder to query and validate.
- Adds write overhead: every step boundary emits an event in addition to its gate verdict. Events are fire-and-forget (`record_event` never raises), which means a failed position write is silently lost.
- `run_status` must query events for position on every call, adding a join or subquery to what is currently a straightforward runs+tasks read.
- External consumers must parse JSON event data to get position, vs reading a simple top-level field.
- Less discoverable than a column: `cfl run status` would need to aggregate events into a position field, making the output shape dependent on event history correctness -- the same derivation-from-history problem at a different layer.

**Effort estimate**: Small. No migration, add one event type, write a derive function.

**Dependencies**: None.

### Option D: Simplify the derived model (fewer steps, fewer gates)

**How it works**: Instead of making position tracking more explicit, simplify Phase 3 to have fewer steps. Combine impl-review + cross-file-review into one "branch review" step. Fold clean-code into the final review pass. Remove or inline the known-issues walkthrough. Fewer steps means fewer derivation gaps.

**Pros**:
- Reduces complexity at the source. Fewer steps, fewer gates, fewer things that can go wrong.
- No schema changes, no new commands, no migration.
- Simpler instruction files.

**Cons**:
- Does not address the fundamental problem: even with fewer steps, derived position can still be wrong when a step fails to record its marker or code changes between sessions.
- Loses useful separation of concerns: impl-review catches implementation bugs, cross-file catches consistency issues, clean-code catches style. These find different things and combining them would reduce review quality.
- The known-issues walkthrough exists for a specific safety reason (Severity Gate -- preventing silent deferrals of user-impacting issues). Removing it reintroduces the risk it was built to prevent.
- Auto-reset still needs reliable position data regardless of how many steps exist.

**Effort estimate**: Medium. Fewer steps but significant instruction file rewriting, and each consolidation decision requires careful analysis of what review quality is lost.

**Dependencies**: None.

## Concerns

### Technical risks
- **Position advancement timing**: The "record gate first, advance position second" ordering is correct but every step boundary must implement it consistently. A single step that advances position before recording the gate creates a silent skip-on-resume bug -- the same class of bug this refactor aims to eliminate, now moved to a different layer.
- **Backward jumps**: Smoke-test failure requires resetting position from `shipping` back to `impl-review`. If implemented via `cfl set run` (bypassing guards), there's no state-machine validation. If implemented via a guarded command, the command must allow backward transitions selectively, which adds complexity.
- **`reviewed_head` as a run-level field**: When position resets (smoke-test failure), `reviewed_head` must also reset. The single-field model is simpler than per-gate, but the field must stay in sync with position.

### Complexity risks
- **Two position mechanisms**: Phase 2 tracks position via task statuses across N rows; Phase 3 tracks position via a single run column. These are conceptually different (per-row state machine vs single-pointer). A unified model is possible but may over-complicate Phase 2's well-working mechanism. Leaving them separate is pragmatic but means two mental models.
- **Instruction file maintenance**: Adding ~8-10 position advancement calls to `post-execution-pipeline.md` increases the surface area for instruction-following errors. Every new Phase 3 step in the future requires a matching position advancement call.

### Maintenance risks
- **Schema evolution**: Adding columns to `runs` is easy (single `ALTER TABLE`), but each new column is a permanent addition. If the position model needs to change later, it's another migration.
- **Step vocabulary coupling**: The `pipeline_step` CHECK constraint couples the DB schema to the pipeline step names. Adding a new step requires a migration to update the CHECK constraint (unless the constraint is omitted, trading type safety for flexibility).

## Open Questions

- [ ] Should `pipeline_step` have a CHECK constraint listing valid values (type safety but requires migration to add steps), or be unconstrained TEXT (flexible but no DB-level validation)?
- [ ] Should Phase 2's `current_task`/`last_completed` be unified with the new position model, or left as-is? Phase 2's per-task state machine works well; unifying would add complexity for unclear benefit.
- [ ] Should position advancement use a new guarded command (`cfl run advance-step`) with transition validation, or use `cfl set run` for simplicity? A guarded command prevents invalid transitions but adds new surface area (function, CLI command, event name).
- [ ] How should the smoke-test failure backward jump be modeled? Options: (a) a specific `cfl run reset-pipeline` command, (b) `cfl set run pipeline_step=impl-review` (escape hatch), (c) the guarded command allowing explicit backward transitions with a `--reason` flag.
- [ ] What does the auto-reset consumer specifically need beyond `pipeline_step` and `reviewed_head`? This brief covers orchestrate internals per the constraint; the auto-reset consumer's needs should be confirmed before finalizing the API shape.

## Recommendation

Option A (explicit `pipeline_step` + `reviewed_head` columns on `runs`) is the strongest fit for the stated requirements. The evidence supports this:

The fundamental problem is structural: position derived from history will always have edge cases where history does not accurately represent state. PR #574's 9-patch sequence demonstrates this concretely -- each patch closed a derivation gap, and the pattern shows no sign of converging. Option B (refining the derivation) would produce cleaner code than the current prose-based resume table but does not eliminate the derivation layer that generates these bugs.

Option A eliminates derivation entirely for Phase 3 position. The cost (one schema migration, ~8-10 position advancement calls in the pipeline file) is modest relative to the ongoing cost of patching derivation gaps. The risk (incorrect position advancement at a step boundary) is real but is a simpler, more testable failure mode than the current state (incorrect position derivation from a web of gate verdicts, iterations, timestamps, and event correlations).

For auto-reset reliability specifically: a stored `pipeline_step` field on `cfl run status` is a direct, authoritative answer to "where is this run?" that an external consumer can trust without understanding gate semantics.

One caveat: the current Phase 3 steps' own idempotent re-entry logic (re-reading files, re-running reviewers on current diff state) provides correctness safety today even without position tracking. A position tracking bug that causes a step to be skipped is worse than one that causes a step to be re-run. The "record gate first, advance position second" ordering proposed in issue #575 addresses this by defaulting to re-run on failure, but every step boundary must implement this ordering consistently.

### Suggested next steps
1. Write a design doc via `/mine-define` specifying the position model, schema migration, API changes, and instruction file updates.
2. Decide the open questions (CHECK constraint, guarded command vs `cfl set`, backward jump model) during the design interview.
3. Prototype the schema migration and `run_status` changes in a branch to validate the API shape before rewriting the instruction files.
