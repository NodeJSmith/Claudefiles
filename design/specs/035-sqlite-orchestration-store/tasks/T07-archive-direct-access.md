---
task_id: "T07"
title: "Implement archive and direct access commands"
status: "planned"
depends_on: ["T03", "T04"]
implements: ["FR#11", "FR#24", "AC#11", "AC#23"]
---

## Summary

Implement `cfl archive` (full archive workflow: git rm tasks, remove scaffolding, stamp design.md, close run, mark spec archived) and `cfl set` (direct-access tier for arbitrary field writes bypassing the state machine). Both are important for the operational lifecycle — archive for shipping, `cfl set` for crash recovery.

## Target Files

- create: `packages/cfl/src/cfl/archive.py`
- create: `packages/cfl/src/cfl/direct.py`
- create: `packages/cfl/tests/test_archive.py`
- create: `packages/cfl/tests/test_direct.py`
- modify: `packages/cfl/src/cfl/cli.py`
- read: `design/specs/035-sqlite-orchestration-store/cli-design.md`
- read: `packages/spec-helper/src/spec_helper/commands.py`

## Prompt

**src/cfl/archive.py:**

Implement `archive_spec(conn, *, spec_override=None, dry_run=False)` following `cli-design.md` §cfl archive:

1. Resolve spec (auto or `--spec`). Uses `resolve_spec()` with `require_active_run=False`.
2. Verify all tasks have `status='done'` in the DB (query `tasks` table, not frontmatter). Error `tasks_not_done` if any aren't done, listing the non-done tasks.
3. If `dry_run`: return `{"status": "would_archive", ...}` and exit.
4. Run `git rm -r <feature_dir>/tasks/` via `subprocess.run`.
5. Remove legacy scaffolding if present: `git rm --ignore-unmatch <feature_dir>/trail.tsv <feature_dir>/trail-audit.md <feature_dir>/.gitignore` (these are from pre-cfl runs).
6. Stamp `**Status:** archived` in `<feature_dir>/design.md` — read the file, replace the Status line, write it back.
7. If `specs.active_run_id IS NOT NULL`: close the run (`UPDATE runs SET status='completed', ended_at=datetime('now')`) + INSERT `run.completed` event with `via='archive'`.
8. `UPDATE specs SET status='archived', active_run_id=NULL`.
9. Output JSON with `spec_id`, `slug`, `status='archived'`, `task_count`.

Read `packages/spec-helper/src/spec_helper/commands.py` (the `archive_feature` and `archive_all` functions) to understand the existing archive workflow being replaced.

**src/cfl/direct.py:**

Implement `set_field(conn, entity, entity_id, fields)` following `cli-design.md` §cfl set:

1. Validate `entity` is one of: `task`, `run`, `spec`, `session`.
2. Map entity to table. For `task`, the ID is the `task_id` string within the active run. For others, the ID is the primary key.
3. Verify the target row exists. Error `not_found` if missing.
4. Read current field values (the "before" state).
5. Apply updates with no state machine validation. Handle `field=null` as SQL NULL.
6. Validate field names against the actual table columns. Error on unknown fields (exit 2).
7. Log a `set.applied` event with `{"entity": "...", "id": "...", "fields": {...}, "previous": {...}}`.
8. Output JSON with `entity`, `id`, `updated`, `previous`, `event_id`.

**Wire into cli.py:** Replace stubs for `archive` and `set`.

**Tests:**

`test_archive.py`:
- Test archive with all tasks done: git rm called, design.md stamped, spec set to archived.
- Test archive with non-done tasks: error listing the non-done ones.
- Test `--dry-run` returns would_archive without modifying anything.
- Test archive closes active run if present.
- Test archive removes legacy scaffolding files.

`test_direct.py`:
- Test `cfl set task T03 status=pending` updates the field.
- Test `cfl set task T03 started_at=null` sets NULL.
- Test before/after state is logged in `set.applied` event.
- Test error on unknown entity.
- Test error on unknown field name.
- Test error on non-existent row.

## Focus

- Archive runs `git rm` via subprocess — mock or use a temp git repo in tests.
- The design.md status stamp must handle both `**Status:** draft` and `**Status:** in_progress` patterns. Use a regex replacement: `r'\*\*Status:\*\*\s*\w+'` → `**Status:** archived`.
- `cfl set` deliberately has NO state machine validation. That's the point — it's the escape hatch. But it DOES validate that the field name is a real column on the table.
- For `cfl set task`, the entity_id is the `task_id` string (e.g., "T03"), not the integer PK. The query needs to scope to the active run: `WHERE run_id=? AND task_id=?`.

## Verify

- [ ] FR#11: `cfl archive` with all tasks done removes tasks directory, stamps design.md, marks spec archived, clears active_run_id
- [ ] FR#24: `cfl set task T03 status=pending started_at=null` updates fields bypassing state machine and logs `set.applied` event with before/after state
- [ ] AC#11: `cfl archive` with all tasks done: `git rm -r tasks/` succeeds, design.md gets `**Status:** archived`, specs row gets `status='archived'`, `active_run_id` cleared
- [ ] AC#23: `cfl set task T03 status=pending started_at=null` updates task bypassing guards and logs `set.applied` event with `previous` state
