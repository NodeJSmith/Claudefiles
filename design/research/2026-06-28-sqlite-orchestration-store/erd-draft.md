# ERD Draft: cfl Database

## Entities

### specs

The feature/spec registry. Replaces filesystem scanning for `next-number`. One row per feature, persists across runs.

| Column | Type | Notes |
|---|---|---|
| id | INTEGER PK | Auto-increment |
| number | INTEGER NOT NULL UNIQUE | The NNN in `design/specs/NNN-slug/` |
| slug | TEXT NOT NULL | The slug portion |
| repo | TEXT NOT NULL | Repo root path (for multi-repo disambiguation) |
| created_at | TEXT NOT NULL | ISO 8601 UTC |

**Replaces:** `spec-helper next-number` filesystem scan.

### runs

One orchestration run. Replaces the checkpoint header.

| Column | Type | Notes |
|---|---|---|
| id | INTEGER PK | Auto-increment, becomes the run_id |
| spec_id | INTEGER REFERENCES specs(id) | Which spec this run executes |
| feature_dir | TEXT NOT NULL | Relative path: `design/specs/035-sqlite-store` |
| base_commit | TEXT NOT NULL | HEAD before any executor ran |
| status | TEXT NOT NULL DEFAULT 'running' | `running`, `completed`, `crashed`, `stopped` |
| visual_mode | TEXT | `enabled`, `skipped_no_server`, `skipped_no_vision` |
| dev_server_url | TEXT | URL or NULL |
| tmpdir | TEXT | Path to ephemeral run tmpdir |
| started_at | TEXT NOT NULL | ISO 8601 UTC |
| ended_at | TEXT | NULL until run completes or stops |

**Replaces:** checkpoint header fields (feature_dir, base_commit, started_at, visual_mode, dev_server_url, tmpdir, version). The `current_wp` and `current_wp_status` move to the tasks table as task-level state.

### tasks

One task within a run. Replaces checkpoint verdict blocks AND the in-progress tracking.

| Column | Type | Notes |
|---|---|---|
| id | INTEGER PK | Auto-increment |
| run_id | INTEGER NOT NULL REFERENCES runs(id) | |
| task_id | TEXT NOT NULL | "T01", "T02" — from the task file |
| title | TEXT NOT NULL | Human-readable title |
| status | TEXT NOT NULL DEFAULT 'pending' | See task state machine below |
| started_at | TEXT | NULL until task begins |
| ended_at | TEXT | NULL until verdict |
| verdict | TEXT | PASS, WARN, FAIL, BLOCKED, SKIPPED — NULL until decided |
| verdict_detail | TEXT | Parenthetical: "(3 auto-fixed)", "(visual skipped)" |
| commit_sha | TEXT | WIP commit SHA, or "no-changes" |
| UNIQUE(run_id, task_id) | | |

**Replaces:** checkpoint's `current_wp`, `current_wp_status`, `last_completed_wp`, and the `## Verdicts` blocks.

### gates

A gate evaluation — a decision point that produces a structured result. One row per gate execution. Multiple gates per task (spec review, code review, test gate, etc.). Multiple executions of the same gate type per task (re-reviews after fix loops).

| Column | Type | Notes |
|---|---|---|
| id | INTEGER PK | Auto-increment |
| run_id | INTEGER NOT NULL REFERENCES runs(id) | |
| task_id | TEXT | NULL for run-level gates (impl-review, cross-file, etc.) |
| gate_type | TEXT NOT NULL | See gate type vocabulary below |
| iteration | INTEGER NOT NULL DEFAULT 1 | Which pass (1 = initial, 2 = after first fix, etc.) |
| verdict | TEXT NOT NULL | Gate-specific: PASS/FAIL/WARN, APPROVE/BLOCK, etc. |
| detail | TEXT | Human-readable summary |
| data | TEXT | JSON — structured gate-specific data |
| created_at | TEXT NOT NULL | ISO 8601 UTC |

**Replaces:** verdict lines extracted from review files, test-gate.md, lint-gate.md, fixer gate result (currently in-memory only).

### dispatches

A subagent dispatch. One row per subagent launched. Captures identity at dispatch time (not post-hoc).

| Column | Type | Notes |
|---|---|---|
| id | INTEGER PK | Auto-increment |
| run_id | INTEGER NOT NULL REFERENCES runs(id) | |
| task_id | TEXT | NULL for run-level dispatches (Phase 3) |
| gate_id | INTEGER REFERENCES gates(id) | Which gate this dispatch serves (NULL for executor) |
| role | TEXT NOT NULL | Canonical role: `executor`, `spec-reviewer`, `code-reviewer`, etc. |
| agent_type | TEXT NOT NULL | Subagent type: `general-purpose`, `code-reviewer`, `engineering-frontend-developer` |
| model | TEXT | `sonnet`, `haiku`, `opus` |
| routing_reason | TEXT | Why this agent type was selected (from agent-routing.md) |
| dispatched_at | TEXT NOT NULL | ISO 8601 UTC |
| completed_at | TEXT | NULL until subagent returns |
| verdict | TEXT | Subagent's verdict (if applicable) |
| detail | TEXT | Human-readable result summary |
| data | TEXT | JSON — structured result data |
| output_path | TEXT | Path to the subagent's output file (ephemeral) |

**Replaces:** trail-log dispatch entries, agent_dispatches table from the old design, GP_SIGNATURES post-hoc matching.

### events

Audit trail. Every significant thing that happens. The general-purpose log.

| Column | Type | Notes |
|---|---|---|
| id | INTEGER PK | Auto-increment |
| run_id | INTEGER NOT NULL REFERENCES runs(id) | |
| task_id | TEXT | NULL for run-level events |
| event | TEXT NOT NULL | Dotted name: `run.started`, `task.verdict`, etc. |
| detail | TEXT | Human-readable description |
| data | TEXT | JSON — structured event data, queryable via json_extract() |
| created_at | TEXT NOT NULL | ISO 8601 UTC |

**Replaces:** trail.tsv rows. Same information, but `data` column makes it queryable without parsing `detail` strings.

## Relationships

```text
specs 1──────* runs
              │
runs  1──────* tasks
              │
runs  1──────* gates
tasks 1──────* gates      (task_id on gates)
              │
runs  1──────* dispatches
tasks 1──────* dispatches (task_id on dispatches)
gates 1──────* dispatches (gate_id on dispatches — which gate the dispatch serves)
              │
runs  1──────* events
tasks 1──────* events     (task_id on events)
```

```text
┌────────┐       ┌────────┐       ┌────────┐
│ specs  │1─────*│  runs  │1─────*│ tasks  │
└────────┘       └───┬────┘       └───┬────┘
                     │                │
                     │1               │1
                     │                │
              ┌──────┼────────────────┼──────┐
              │      │                │      │
              *      *                *      *
          ┌───┴───┐ ┌┴──────────┐ ┌──┴───┐  │
          │events │ │dispatches │ │gates │──┘
          └───────┘ └─────┬─────┘ └──┬───┘
                          │          │
                          *──────────1
                    (gate_id on dispatches)
```

## State Machines

### Run states

```text
running ──→ completed    (all tasks done + shipped)
running ──→ stopped      (user chose "Stop here")
running ──→ crashed      (session died, inferred from stale running + no recent events)
stopped ──→ running      (resume)
```

### Task states

```text
pending ──→ executing     (Step 1: task announced)
executing ──→ reviewing   (Step 8: reviews dispatched)
reviewing ──→ fixing      (Step 10/12: fix loop entered)
fixing ──→ reviewing      (re-review after fix)
reviewing ──→ done        (Step 17: verdict PASS/WARN, WIP committed)
executing ──→ blocked     (executor returned BLOCKED)
reviewing ──→ failed      (Step 16: verdict FAIL, user chose action)
failed ──→ executing      (Step 16: user chose "Fix and retry")
failed ──→ blocked        (Step 16: user chose "Mark as blocked")
failed ──→ stopped        (Step 16: user chose "Stop here")
blocked ──→ pending       (resume with updated plan)
```

### Gate type vocabulary

Task-level gates (one or more per task):

| Gate type | Produces | Iterations |
|---|---|---|
| `spec-review` | PASS, WARN, FAIL | 1 (+ 1 WARN re-review) |
| `code-review` | APPROVE, WARN, BLOCK + findings count | 1–3 (fix loop) |
| `integration-review` | APPROVE, WARN, BLOCK + findings count | 1–3 (fix loop) |
| `test-gate` | PASS, FAIL (regressions), SKIPPED | 1 per review cycle |
| `lint-gate` | PASS, WARN (regressions), SKIPPED | 1 per review cycle |
| `visual-review` | VERIFIED, WARN, FAIL, SKIPPED | 0–1 |
| `verdict-assembly` | PASS, WARN, FAIL | 1 (the single authoritative verdict) |

Run-level gates (Phase 3, task_id = NULL):

| Gate type | Produces | Iterations |
|---|---|---|
| `impl-review` | APPROVE, REQUEST_FIXES, ABANDON | 1 (+ fix cycles) |
| `cross-file-review` | APPROVE, WARN, BLOCK | 1 |
| `clean-code` | N fixed, M unfixed | 1 |
| `final-review` | clean, N findings | 1–3 |
| `trail-audit` | N findings, no findings | 0–1 |
| `impl-comb` | clean, N minor, N blocking | 1 (+ fix cycles) |
| `shipping-gate` | ship, challenge, stop | 1 |

### Event vocabulary

```text
cfl.invoked          — standalone cfl command invocation (run_id = NULL)

run.started          — orchestration begins
run.completed        — after mine-ship succeeds
run.stopped          — user chose "Stop here"
run.resumed          — resumed from checkpoint

task.started         — task execution begins
task.dispatched      — subagent launched (executor)
task.contested       — CONTESTED criterion resolved
task.gated           — test/lint gate result
task.retried         — WARN fix loop or FAIL retry
task.reviewed        — review pass completed
task.fixed           — findings fix loop completed
task.verdict         — final task verdict assembled

review.started       — Phase 3 review step begins
review.gated         — Phase 3 gate result (impl-review, cross-file, etc.)
review.fixed         — Phase 3 fix applied (clean-code, comb fix)
review.completed     — Phase 3 review step completed
```

## What .cfl-run-id Contains

Written by `cfl run start` to `<feature_dir>/.cfl-run-id`. Contains just the integer run ID.

Subsequent `cfl` commands auto-resolve: read `.cfl-run-id` from the feature dir (auto-detected from CWD or `--feature` flag), look up the run in the DB. If the file doesn't exist or the run_id doesn't match a `running` run, error with a clear message.

Cleaned up by `cfl run complete` or `cfl archive`.

## What Gets Deleted from Disk

With this schema, these files are no longer needed:

| Current artifact | Replaced by |
|---|---|
| `tasks/.orchestrate-state.md` | `runs` + `tasks` tables |
| `tasks/.gitignore` (for checkpoint) | `.cfl-run-id` is simpler, still needs gitignore |
| `trail.tsv` | `events` table |
| `trail-audit.md` | Gate record in `gates` table |
| `.gitignore` (for trail.tsv, trail-audit.md) | Only need to gitignore `.cfl-run-id` |

Still on disk (ephemeral in /tmp): review files, executor output, screenshots, test/lint logs, changed-files lists, clean-code summary.

Still on disk (git-versioned): design.md, T*.md task files, context.md.

## Open Questions

1. **Should `specs` track design.md status (draft/approved/archived)?** Currently status is in design.md frontmatter. Having it in the DB too enables queries like "how many specs are in-flight?" without scanning files.

2. **Should `gates.data` have a defined schema per gate type, or is it freeform JSON?** Defined schemas enable type-safe queries but require schema evolution. Freeform is flexible but queries are stringly-typed.

3. **Should the `dispatches` table capture cost/token data?** The old design had tiers (synchronous vs post-hoc). If we're going all-in, we could add columns for cost but populate them post-hoc via `cfl ingest-cost`.

4. **Archive behavior**: `cfl archive` replaces `spec-helper archive`. Does it also remove `tasks/` via git rm, or does that stay as a git-workflow-level operation?

5. **Should `events` be append-only (audit trail, never updated) while `gates`/`dispatches`/`tasks` are mutable?** This gives a clean separation: events are the immutable log, everything else is current state.
