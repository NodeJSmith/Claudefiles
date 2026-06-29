# Orchestration Workflow: Complete Inventory

Everything that happens during a mine-orchestrate run — every artifact, process, data flow, and piece of state — documented as it actually exists today.

## 1. Persistent Artifacts (survive across sessions)

### Spec artifacts (created by mine-define / mine-plan, consumed by orchestrate)

| Artifact | Path | Created by | Consumed by | Cleaned up by |
|---|---|---|---|---|
| Feature directory | `design/specs/NNN-slug/` | `spec-helper init` via mine-define | mine-orchestrate (Phase 0) | — (preserved) |
| Design doc | `design/specs/NNN-slug/design.md` | mine-define (Phase 4) | Every subagent (executor, reviewers, fixers) | `spec-helper archive` sets Status to archived |
| Task files | `design/specs/NNN-slug/tasks/T*.md` | mine-plan (Phase 2) | Executor (prompt), spec reviewer (reference) | `spec-helper archive` (git rm -r tasks/) |
| Master context | `design/specs/NNN-slug/tasks/context.md` | mine-plan (Step 3a) | Executor (shared cross-task context) | `spec-helper archive` (removed before git rm) |

### Orchestration scaffolding (created and consumed within orchestrate, cleaned up on ship)

| Artifact | Path | Created by | Consumed by | Cleaned up by |
|---|---|---|---|---|
| Checkpoint | `…/tasks/.orchestrate-state.md` | Phase 0 (`spec-helper checkpoint-init`) | Resume protocol, verdict assembly, Phase 3 summary | `spec-helper checkpoint-delete` (Phase 3 Step 7, on ship) |
| Tasks .gitignore | `…/tasks/.gitignore` | Phase 0 (manual append) | git (excludes checkpoint) | `spec-helper archive` |
| Feature .gitignore | `…/NNN-slug/.gitignore` | Phase 0 (manual append) | git (excludes trail.tsv, trail-audit.md) | `spec-helper archive` |
| Trail log | `…/NNN-slug/trail.tsv` | Phase 0 (`trail-log` probe call) | Trail audit (Phase 3 Step 5.5) | `spec-helper archive` |
| Trail audit report | `…/NNN-slug/trail-audit.md` | Phase 3 Step 5.5 (subagent) | Shipping gate (finding count) | `spec-helper archive` |

### Git artifacts (commits)

| Artifact | Created by | Notes |
|---|---|---|
| WIP commits | Step 17a (`git commit -m "WIP: T01 -- title"`) | One per task, on PASS/WARN only |
| Task frontmatter update | Step 17a (`status: planned` → `status: done`) | Written to task file before WIP commit |
| Final squash/ship | `/mine-ship` (Phase 3 Step 6) | Squashes WIP commits into conventional commit |

## 2. Ephemeral Artifacts (in /tmp, lost on reboot)

### Run-level (one per orchestration run)

| Artifact | Path | Created by | Consumed by |
|---|---|---|---|
| Run tmpdir | `/tmp/claude-mine-orchestrate-*` | Phase 0 (`get-skill-tmpdir`) | All per-task artifacts live under this |
| Test command | `<tmpdir>/test-command.txt` | Phase 2 Step 2 (user-confirmed) | Every test gate, every executor, Phase 3 clean-code |
| Lint command | `<tmpdir>/lint-command.txt` | Phase 2 Step 2 (user-confirmed) | Every lint gate, Phase 3 clean-code |
| Test baseline | `<tmpdir>/test-baseline.md` | Phase 2 Step 2 (pre-execution capture) | Test gate regression comparison |
| Lint baseline | `<tmpdir>/lint-baseline.md` | Phase 2 Step 2 (pre-execution capture) | Lint gate regression comparison |

### Per-task (one set per task, under `<tmpdir>/<task_id>/`)

| Artifact | Filename | Created by | Consumed by |
|---|---|---|---|
| Executor output | `executor.md` | Step 5 (executor subagent) | CONTESTED check (Step 7), spec reviewer (Step 8), visual reviewer (Step 11) |
| Spec review | `spec-review.md` | Step 8 (spec reviewer subagent) | WARN fix loop (Step 10), verdict assembly (Step 14) |
| Code review | `code-review.md` | Step 8 (code reviewer subagent) | Findings fix loop (Step 12), verdict assembly |
| Integration review | `integration-review.md` | Step 8 (integration reviewer subagent) | Findings fix loop (Step 12), verdict assembly |
| Visual review | `visual-review.md` | Step 11 (visual reviewer subagent) | Verdict assembly (Step 14) |
| Test gate report | `test-gate.md` | Step 9 (orchestrator) | Verdict assembly (Step 14) |
| Lint gate report | `lint-gate.md` | Step 9 (orchestrator) | Verdict assembly (Step 14) |
| Fix ledger | `fix-ledger.md` | Step 12 (fixer subagent) | Findings fix loop gate, verdict assembly |
| Test output log | `test-output.log` | Steps 5, 9 (executor, test gate) | Debugging, not consumed by verdict |
| Lint output log | `lint-output.log` | Steps 5, 9 (executor, lint gate) | Debugging, not consumed by verdict |
| Changed files | `changed-files.txt` | Step 6, updated by fix loops | Reviewers (Step 8), fix loop re-reviews |
| Committed files | `committed-files.txt` | Step 17a (pre-commit re-capture) | `git add --pathspec-from-file` |
| Before screenshots | `before-*.png` | Step 5 (executor) | Visual reviewer (Step 11) |
| After screenshots | `after-*.png` | Step 5 (executor) | Visual reviewer (Step 11) |

### Phase 3 (run-level, under `<tmpdir>/`)

| Artifact | Filename | Created by | Consumed by |
|---|---|---|---|
| Clean code summary | `clean-code-summary.md` | Step 4 (clean-code subagent) | Shipping gate, mine-ship (HEAD marker check) |
| Final code review | `final-code-review.md` | Step 5 (code reviewer) | Phase 3 auto-fix loop |
| Final integration review | `final-integration-review.md` | Step 5 (integration reviewer) | Phase 3 auto-fix loop |

## 3. In-Memory State (orchestrator LLM context only — not persisted anywhere)

These values exist only in the orchestrator's context window. If context compacts, they are lost unless the resume protocol can reconstruct them.

| State | Set at | Used by | Survives compaction? |
|---|---|---|---|
| `trail_available` (bool) | Phase 0 trail probe | Every `trail-log` call | No — resume re-probes |
| `log_failures` (counter) | Phase 0 (init to 0) | Shipping gate display | **No — lost on compaction, reset to 0 on resume** |
| `visual_mode` | Phase 0 | Executor prompts, visual reviewer gating | Yes — stored in checkpoint |
| `dev_server_url` | Phase 0 | Executor prompts | Yes — stored in checkpoint |
| Per-reviewer verdict lines | Step 8 (extracted from files) | Steps 12, 13, 14 | No — re-extractable from files |
| Fixer gate result (PASS/FAIL) | Step 12 | Step 14 verdict assembly | **No — not written anywhere** |
| `(N auto-fixed)` count | Step 12 fix ledger | Step 14/15 verdict note | No — re-extractable from ledger |
| Iteration count in fix loop | Step 12 | Budget enforcement | No — re-derivable from trail-log entries |
| Test/lint command strings | Step 2 | Steps 5, 9 | No — re-readable from tmpdir files |
| Non-blocking suggestions from Phase 3 | Steps 2, 3 | Shipping gate | **No — lost on compaction** |

**Bolded entries are genuine data-loss risks on compaction.** The rest can be reconstructed from persistent artifacts.

## 4. Checkpoint Schema (the cross-session state machine)

The checkpoint (`tasks/.orchestrate-state.md`) is the only structured state that survives across sessions. Its fields:

### Header fields

| Field | Mutable? | Set by | Purpose |
|---|---|---|---|
| `version` | Immutable | checkpoint-init | Schema version (currently 2) |
| `feature_dir` | Immutable | checkpoint-init | Relative path to feature directory |
| `base_commit` | Immutable | checkpoint-init | HEAD before any executor ran |
| `started_at` | Immutable | checkpoint-init | ISO 8601 UTC timestamp |
| `tmpdir` | Mutable | checkpoint-init, checkpoint-update | Path to run-level temp directory |
| `visual_mode` | Mutable | checkpoint-init, checkpoint-update | `enabled`, `skipped_no_server`, `skipped_no_vision` |
| `dev_server_url` | Set once | checkpoint-init | URL or `"none"` |
| `last_completed_wp` | Mutable | Step 17b | Task ID of last PASS/WARN task |
| `current_wp` | Mutable | Steps 1, 16, 17b | Task currently executing (cleared on resume) |
| `current_wp_status` | Mutable | Steps 1, 10, 16, 17b | `executing`, `warn_retry`, `retry_pending`, `blocked`, `stopped` |

### Verdict blocks (append-only)

One block per completed task:
- `wp_id` — task ID (T01, T02, etc.)
- `title` — task title
- `verdict` — PASS, WARN, FAIL, BLOCKED
- `commit` — WIP commit SHA (or `no-changes`)
- `notes` — optional parenthetical ("3 auto-fixed", "visual skipped")

## 5. Trail Log Schema (event record)

The trail log (`trail.tsv`) records one row per significant orchestration event. Five columns:

| Column | Values | Example |
|---|---|---|
| `timestamp` | ISO 8601 UTC | `2026-06-28T14:30:00Z` |
| `phase` | `p0`, `p1`, `p2`, `p3` | `p2` |
| `task` | Task ID or `-` for phase-level | `T01` |
| `event` | `start`, `dispatch`, `verdict`, `contested`, `gate`, `retry`, `review`, `fix` | `verdict` |
| `detail` | Free text, max 500 chars | `PASS (3 auto-fixed) \| spec: PASS \| code: APPROVE` |

**Known vocabulary (8 event types):**

| Event | Emitted at | Detail pattern |
|---|---|---|
| `start` | Phase 0 init, Phase 2 per-task, resume | `"orchestrate run started"`, `"T01: Set up data model"` |
| `dispatch` | Step 4 (agent routing) | `"agent type: engineering-frontend-developer; routing match: React"` |
| `verdict` | Step 14 (verdict assembly) | `"PASS (3 auto-fixed) \| spec: PASS \| code: APPROVE \| integration: APPROVE \| test: PASS \| lint: PASS"` |
| `contested` | Step 7 (per criterion) | `"<criterion text>: accept — <rationale>"` |
| `gate` | Step 9 (test/lint gate), Phase 3 impl-review | `"test: PASS \| lint: WARN (2 regressions)"`, `"impl-review: APPROVE"` |
| `retry` | Step 10 (WARN fix loop) | `"WARN classification: fixable; retry decision: retried; iteration count: 2"` |
| `review` | Phase 3 (cross-file, trail audit, comb) | `"cross-file consistency: APPROVE"`, `"trail audit: no findings"` |
| `fix` | Step 12 (findings fix loop), Phase 3 clean-code | `"fixed: 3; deferred: 1; unresolved: 0; iterations: 2"` |

## 6. Process Steps (complete lifecycle)

### Pre-orchestration (other skills)

| Step | Skill | Output |
|---|---|---|
| Discovery interview | mine-define | `design.md` (Status: draft) |
| Codebase investigation | mine-define | Convention examples in design.md |
| Task generation | mine-plan | `T*.md` files, `context.md` |
| Task validation | mine-plan | `spec-helper validate` pass |
| Design approval | mine-define/mine-plan | `design.md` Status: approved |

### Phase 0: Setup (11 steps)

| # | Step | Human decision? | Artifact produced |
|---|---|---|---|
| 0.1 | Resume detection | Yes (resume vs restart) | — |
| 0.2 | Branch staleness pre-flight | Yes (on stale) | — |
| 0.3 | Feature directory discovery | Yes (confirm if auto-found) | — |
| 0.4 | Read design doc | — | — (in-memory) |
| 0.5 | Read all task files | — | — (in-memory) |
| 0.6 | Dev server port scan | Yes (if not found) | — |
| 0.7 | Vision capability check | — | — |
| 0.8 | Capture base_commit | — | — (in-memory, then checkpoint) |
| 0.9 | Create checkpoint | — | `.orchestrate-state.md` |
| 0.10 | Create .gitignore files | — | `tasks/.gitignore`, `NNN-slug/.gitignore` |
| 0.11 | Trail log probe | — | `trail.tsv` (with header row) |

### Phase 1: Parse and select (2 steps)

| # | Step | Human decision? | Artifact produced |
|---|---|---|---|
| 1.1 | Present task list | — | — |
| 1.2 | Auto-select start point | — (auto from checkpoint) | — |

### Phase 2: Per-task loop (17 steps, repeated per task)

| # | Step | Human decision? | Artifact produced |
|---|---|---|---|
| 2.1 | Announce task | — | Checkpoint update (current_wp) |
| 2.2 | Discover test/lint commands | Yes (confirm commands) | `test-command.txt`, `lint-command.txt`, baselines |
| 2.3 | Create per-task tmpdir | — | `<tmpdir>/<task_id>/` |
| 2.4 | Agent type routing | — | Trail log entry |
| 2.5 | Executor dispatch | — | `executor.md`, `test-output.log`, `lint-output.log`, screenshots |
| 2.6 | Capture changed files | — | `changed-files.txt` |
| 2.7 | CONTESTED criteria | Yes (per criterion) | Task file edits, trail log entries |
| 2.8 | Parallel review pass | — | `spec-review.md`, `code-review.md`, `integration-review.md` |
| 2.9 | Test and lint gates | — | `test-gate.md`, `lint-gate.md` |
| 2.10 | WARN fix loop | Yes (if persistent WARN) | Updated executor/review files, trail log |
| 2.11 | Visual reviewer | — | `visual-review.md` |
| 2.12 | Review findings fix loop | — | `fix-ledger.md`, updated review files |
| 2.13 | Review gate | — | — (presence check only) |
| 2.14 | Verdict assembly | — | Trail log entry |
| 2.15 | Present results | Yes (on FAIL/BLOCKED) | — |
| 2.16 | Gate decision | Yes (on FAIL/BLOCKED) | Checkpoint update |
| 2.17 | WIP commit + checkpoint update | — | Git commit, checkpoint verdict block |

### Phase 3: Post-execution (7 steps)

| # | Step | Human decision? | Artifact produced |
|---|---|---|---|
| 3.1 | Verdict summary table | — | — (displayed from checkpoint) |
| 3.2 | Implementation review | Yes (on REQUEST_FIXES) | Trail log, potential fix commits |
| 3.3 | Cross-file consistency review | Yes (on BLOCK) | Trail log |
| 3.4 | Clean code check | — (auto-fix) | `clean-code-summary.md`, fix commit |
| 3.5 | Final review pass | — (auto-fix, max 2 iterations) | `final-code-review.md`, `final-integration-review.md` |
| 3.5.5 | Trail audit | — | `trail-audit.md`, trail log |
| 3.5.7 | Implementation fine-toothed comb | Yes (on blocking) | Trail log |
| 3.6 | Shipping gate | **Yes** | — |
| 3.7 | Checkpoint deletion | — (on ship only) | — (deletes checkpoint) |

### Post-orchestration (other skills)

| Step | Skill/Tool | Output |
|---|---|---|
| Ship | `/mine-ship` | Squash commit, push, PR |
| Archive | `spec-helper archive` | Removes tasks/, context.md, trail files, .gitignore files; stamps design.md as archived |

## 7. Subagent Types Dispatched

| Role | Agent type | Model | Phase | Dispatch count per task |
|---|---|---|---|---|
| Executor | Routed (see agent-routing.md) | sonnet | P2 | 1 (+ retries) |
| Spec reviewer | general-purpose | sonnet | P2 | 1 (+ WARN re-review) |
| Code reviewer | code-reviewer | sonnet | P2 | 1–3 (fix loop iterations) |
| Integration reviewer | integration-reviewer | sonnet | P2 | 1–3 (fix loop iterations) |
| Visual reviewer | general-purpose | sonnet | P2 | 0–1 |
| Fixer | general-purpose | sonnet | P2 | 0–3 (2 normal + 1 classify) |
| Impl reviewer | (via /mine-implementation-review) | sonnet | P3 | 1 (+ fix cycles) |
| Cross-file reviewer | integration-reviewer | sonnet | P3 | 1 |
| Clean code wrapper | general-purpose | sonnet | P3 | 1 |
| Final code reviewer | code-reviewer | sonnet | P3 | 1–3 |
| Final integration reviewer | integration-reviewer | sonnet | P3 | 1–3 |
| Trail auditor | general-purpose | sonnet | P3 | 0–1 |
| Implementation comb | fine-toothed-comb | sonnet | P3 | 1 (+ fix cycles) |

## 8. Implicit Processes (not written to a file or structured data)

These are things that happen during orchestration but have no persistent, structured representation. They exist only as instructions in SKILL.md and LLM context.

### 8.1 Verdict assembly logic

The PASS/WARN/FAIL computation at Step 14 is entirely instruction-following — there's no function, no tool, no deterministic code. The orchestrator LLM reads verdict lines from files, applies priority rules from SKILL.md text, and produces the verdict. If the LLM misreads a verdict line or misapplies the priority, there's no check.

### 8.2 Fixer gate result

The PASS/FAIL determination from the findings fix loop (terminal state A vs B, unresolved row detection) is produced in the orchestrator's context and consumed at Step 14. It's never written to a file. On compaction, it's lost — there's no way to reconstruct "did the loop exit via early clean re-review (state A) or budget exhaustion (state B)?" from disk artifacts alone. The ledger on disk doesn't record which terminal state produced it.

### 8.3 Log failure counter

`log_failures` counts trail-log call failures during the run. It's incremented in-memory and displayed at the shipping gate. On compaction, it resets to 0. A run that had 5 trail-log failures before compaction shows 0 at the shipping gate.

### 8.4 Non-blocking suggestions accumulation

Phase 3 steps 2 and 3 produce non-blocking suggestions that should appear at the shipping gate. These are held in context only. On compaction, they're lost.

### 8.5 Iteration tracking in fix loops

The findings fix loop enforces a 2-pass budget. The orchestrator tracks which iteration it's on in context. There's no file that records "this is fixer pass 2 of 2." The trail-log detail string includes the iteration count, but it's free text — not queryable or resumable.

### 8.6 "Clean code already ran" protocol

Phase 3 Step 4 writes `<!-- HEAD: <sha> -->` as the first line of `clean-code-summary.md`. mine-ship checks this marker to avoid re-running clean-code. This is an implicit cross-skill contract with no documentation beyond the two SKILL.md files.

### 8.7 Changed files list accumulation

`changed-files.txt` starts at Step 6 and gets unioned with additional files from fix loops (Steps 10, 12). The union logic is instruction-level, not code. On retry (Step 16 "Fix and retry"), the file is recaptured. The distinction between "files the executor changed" and "files that were actually committed" exists (changed-files.txt vs committed-files.txt) but the relationship isn't formalized.

### 8.8 Agent dispatch identity

When the orchestrator dispatches a subagent (Step 4 routing), the routing decision (which agent type, why) is recorded only in a trail-log detail string. There's no structured record of "for task T01, the executor was engineering-frontend-developer because the task matched the React row." orchestrate-cost reconstructs this post-hoc from GP_SIGNATURES — substring matching against prompt text in JSONL transcripts.

### 8.9 Cost and token data

Not captured during execution at all. orchestrate-cost and agent-stats mine JSONL transcripts after the fact. Token usage, cost-per-agent, and model selection are only knowable through transcript archaeology.

### 8.10 Compaction events

When a subagent auto-compacts during execution, a PostToolUse hook reports it. But there's no structured record of how many compactions occurred per agent or per task. agent-stats reconstructs this from JSONL scanning.

## 9. Data Flows Between Steps

```
mine-define → design.md → mine-plan → T*.md + context.md
                                              ↓
                                      mine-orchestrate
                                              ↓
Phase 0:  design.md + T*.md → checkpoint → (persists across sessions)
          base_commit ──────→ checkpoint → Phase 3 diffs
          tmpdir ───────────→ checkpoint → all temp artifacts
                                              ↓
Phase 2:  T*.md ───→ executor ───→ executor.md
          (per task)              ↓
                    changed-files ───→ reviewers (parallel) ───→ review files
                                  ↓                                   ↓
                    CONTESTED ───→ user decision              verdict lines
                                                                      ↓
                    test/lint gates ──────────────────────→ gate results
                                                                      ↓
                    [WARN fix loop] ←── spec WARN                     ↓
                    [findings fix loop] ←── code/integ findings       ↓
                    [visual reviewer] ←── visual scenarios            ↓
                                                                      ↓
                    verdict assembly ←── all verdict inputs ←─────────┘
                              ↓
                    PASS/WARN → WIP commit → checkpoint verdict
                    FAIL      → user decision → retry or skip
                                              ↓
Phase 3:  checkpoint verdicts → summary table
          base_commit diff ───→ impl-review → cross-file → clean-code → final-review
                                                                              ↓
          trail.tsv ──────────→ trail audit                                   ↓
          design.md + diff ───→ impl comb                                     ↓
                                              ↓                               ↓
                              shipping gate ←── all Phase 3 results ←─────────┘
                                              ↓
                              /mine-ship → spec-helper archive
```

## 10. What spec-helper Owns Today

| Subcommand | Used by | Purpose |
|---|---|---|
| `init` | mine-define, mine-grill | Create feature directory with next number |
| `validate` | mine-plan | Validate task file schema |
| `archive` | mine-ship, mine-commit-push, mine-create-pr | Remove tasks/, clean scaffolding, stamp design.md |
| `next-number` | (internal to init) | Get next feature number |
| `checkpoint-init` | mine-orchestrate Phase 0 | Create orchestration state file |
| `checkpoint-read` | mine-orchestrate resume, Phase 3 | Read orchestration state |
| `checkpoint-update` | mine-orchestrate Steps 1, 10, 16, 17b | Update in-progress/completed state |
| `checkpoint-verdict` | mine-orchestrate Step 17b | Append task verdict to checkpoint |
| `checkpoint-delete` | mine-orchestrate Phase 3 Step 7 | Remove checkpoint on ship |

## 11. What trail-log Owns Today

A 115-line Bash script. Accepts 5 positional args, writes one TSV row. Handles:
- Timestamp generation (UTC)
- Formula-injection stripping
- Field sanitization (tabs/newlines → spaces)
- Detail truncation (500 chars)
- Header row creation (on first write)
- Event vocabulary validation (warns on unknown, still writes)
- Relative path resolution (anchors to git worktree root)

Does NOT handle:
- SQLite (proposed in spec 035)
- Run identity
- Structured event data beyond free-text detail
- Any query or reporting
