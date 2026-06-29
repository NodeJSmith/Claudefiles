---
task_id: "T08"
title: "Migrate mine-orchestrate to cfl commands"
status: "planned"
depends_on: ["T04", "T05", "T06"]
implements: ["FR#26"]
---

## Summary

Replace all `trail-log` and `spec-helper` call sites in the mine-orchestrate skill files with their `cfl` equivalents. This is the primary consumer migration — 6 files with ~25 call sites total. Each replacement follows the mapping table in cli-design.md.

## Target Files

- modify: `skills/mine-orchestrate/SKILL.md`
- modify: `skills/mine-orchestrate/post-execution-pipeline.md`
- modify: `skills/mine-orchestrate/resume-protocol.md`
- modify: `skills/mine-orchestrate/findings-fix-loop.md`
- modify: `skills/mine-orchestrate/warn-fix-loop.md`
- modify: `skills/mine-orchestrate/wip-commit-protocol.md`
- read: `design/specs/035-sqlite-orchestration-store/cli-design.md`
- read: `design/specs/035-sqlite-orchestration-store/db-design-brief.md`

## Prompt

Replace every `trail-log` and `spec-helper` call in the mine-orchestrate skill files with the corresponding `cfl` command. Use the mapping tables in `cli-design.md` §Trail-log → cfl Event Migration and §spec-helper → cfl Migration as the authoritative reference.

### SKILL.md call sites (read the full file first):

**Phase 0:**
- Line ~22: `spec-helper checkpoint-read <feature_dir_name> --json` → `cfl run status`
  - The JSON output fields change: `verdicts` → `tasks`, `verdicts[].wp_id` → `tasks[].task_id`, `last_completed_wp` → `last_completed`, `current_wp` → `current_task`. See cli-design.md §Caller Field Mapping for the complete list.
- Line ~128: `spec-helper checkpoint-init ... --json` → `cfl run start --base-commit <sha> --tmpdir <path> [--visual-mode ...] [--dev-server-url ...]`
- Line ~139: `trail-log "<path>" p0 - start "orchestrate run started"` → REMOVE (cfl run start emits `run.started` internally)

**Phase 2 (per task):**
- Line ~172: `spec-helper checkpoint-update ... --current-wp <task_id> --current-wp-status executing --json` → `cfl task start <task_id>`
- Line ~178: `trail-log "<path>" p2 <task_id> start "<task_id>: <title>"` → REMOVE (cfl task start emits `task.started` internally)
- Line ~255: `trail-log "<path>" p2 <task_id> dispatch "..."` → `cfl dispatch <role> <task_id> --agent-type <type> --routing-reason "<rule>"`
- Line ~335: `trail-log "<path>" p2 <task_id> contested "..."` → `cfl event task.contested <task_id> --data '{"criterion": "...", "decision": "...", "rationale": "..."}'`
- Line ~433: `trail-log "<path>" p2 <task_id> gate "test: ... | lint: ..."` → `cfl gate test-gate <task_id> --verdict <v> --data '...'` + `cfl gate lint-gate <task_id> --verdict <v> --data '...'`
- Line ~440: `trail-log "<path>" p2 <task_id> retry "..."` → `cfl event task.retried <task_id> --data '{"reason": "...", "iteration": N}'`
- Line ~447: `trail-log "<path>" p2 <task_id> review "visual: ..."` → `cfl gate visual-review <task_id> --verdict <v> --data '{"scenarios": N, ...}'`
- Line ~492: `trail-log "<path>" p2 <task_id> verdict "..."` → `cfl task verdict <task_id> --verdict <v> --detail "..." --data '{"spec": "...", "code": "...", ...}'`
- Line ~538: `spec-helper checkpoint-update ... --current-wp-status <status> --json` → `cfl task update <task_id> --status <status>`

**Also add NEW call sites** (no trail-log predecessor — see cli-design.md §New Calls):
- After spec review: `cfl gate spec-review <task_id> --verdict <v>`
- After code review: `cfl gate code-review <task_id> --verdict <v> --data '{"findings": N}'`
- After integration review: `cfl gate integration-review <task_id> --verdict <v> --data '{"findings": N}'`
- After reading executor result: `cfl dispatch end <dispatch_id>`

### post-execution-pipeline.md call sites:

- Line ~11: `spec-helper checkpoint-read` → `cfl run status`
- Line ~31: `trail-log ... p3 - gate "impl-review: ..."` → `cfl gate impl-review --verdict <v> --detail "summary"`
- Line ~96: `trail-log ... p3 - review "cross-file consistency: ..."` → `cfl gate cross-file-review --verdict <v>`
- Line ~138: `trail-log ... p3 - fix "clean code: ..."` → `cfl gate clean-code --verdict <v> --data '...'`
- Line ~159: `trail-log ... p3 - review "final review: ..."` → `cfl gate final-review --verdict <v>`
- Line ~199: `trail-log ... p3 - review "trail audit: ..."` → `cfl gate trail-audit --verdict <v>`
- Line ~238: `trail-log ... p3 - review "impl comb: ..."` → `cfl gate impl-comb --verdict <v> --data '...'`
- Line ~271: `spec-helper checkpoint-delete` → `cfl run complete`
- Add NEW: `cfl gate shipping-gate --verdict <v> --data '{"choice": "..."}'` at the shipping gate
- Add NEW: `cfl dispatch <role> --agent-type <type>` for each Phase 3 subagent dispatch

### resume-protocol.md call sites:

- Line ~8: `spec-helper checkpoint-read` → `cfl run status`
- Line ~44: `spec-helper checkpoint-update ... --current-wp "" --current-wp-status ""` → REMOVE (current_task is derived, not stored)
- Line ~50: `spec-helper checkpoint-delete` → REMOVE (run stays active; no checkpoint to delete)
- Trail-log resume entry → `cfl run resume` (emits `run.resumed` internally)

### findings-fix-loop.md:

- `trail-log ... p2 <task_id> fix "fixed: N; deferred: M; ..."` → `cfl event task.fixed <task_id> --data '{"fixed": N, "deferred": M, "unresolved": K, "iteration": I}'`

### warn-fix-loop.md:

- Line ~11: `spec-helper checkpoint-update ... --current-wp-status warn_retry --json` → `cfl task update <task_id> --status fixing`

### wip-commit-protocol.md:

- Line ~50: `spec-helper checkpoint-update ... --last-completed-wp <task_id> --json` → REMOVE (last_completed is derived from task statuses)
- Line ~56: `spec-helper checkpoint-verdict ... --wp-id <task_id> --verdict ... --commit ... --notes "..." --json` → `cfl task verdict <task_id> --verdict <v> --commit <sha> --detail "..."`

### Cleanup:

- Remove `trail_available`, `log_failures` variables and all conditional branches that gate on them. These are dead code with cfl (see cli-design.md §Key Improvements Over trail-log point 5).
- Remove trail-log writability probe logic.
- Remove the trail_path variable and all references to it.
- Update field name references per the Caller Field Mapping table in cli-design.md: `verdicts` → `tasks`, `wp_id` → `task_id`, `last_completed_wp` → `last_completed`, `current_wp` → `current_task`, etc.
- Apply verdict vocabulary normalization: APPROVE → PASS, BLOCK → FAIL, VERIFIED → PASS, etc. (see cli-design.md §Normalization).

## Focus

- This is the highest-blast-radius task. Read each file fully before editing.
- The trail-log path argument disappears entirely — cfl resolves the active run from context.
- The `p0`/`p2`/`p3` phase prefixes disappear — event names carry the phase semantically.
- Some calls become REMOVALS (implicit events, derived fields). Don't just replace 1:1 — remove what's no longer needed.
- The checkpoint JSON output field names change. Every place that reads checkpoint output needs updating.
- The `spec-helper checkpoint-update ... --current-wp "" --current-wp-status ""` pattern (clearing the current pointer) is eliminated entirely — `current_task` is derived from task statuses.
- New `cfl dispatch` calls must capture the dispatch_id from the JSON output and pass it to `cfl dispatch end` after the Agent tool returns.
- New `cfl gate` calls for spec-review, code-review, and integration-review don't have trail-log predecessors — they're genuinely new audit trail entries.

## Verify

- [ ] FR#26: All trail-log and spec-helper calls in SKILL.md are replaced with cfl equivalents — zero references to `trail-log` or `spec-helper` remain in any mine-orchestrate file
