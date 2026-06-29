---
task_id: "T10"
title: "Update documentation, installation, and remove replaced tools"
status: "planned"
depends_on: ["T01", "T08", "T09"]
implements: ["FR#1", "FR#27"]
---

## Summary

Update REFERENCE.md, capabilities-core.md, install.py, and settings.json to register cfl and remove spec-helper/trail-log. Delete `bin/trail-log` and `packages/spec-helper/`. This is the cleanup task that makes cfl the only tool.

## Target Files

- modify: `REFERENCE.md`
- modify: `rules/common/capabilities-core.md`
- modify: `install.py`
- modify: `settings.json`
- delete: `bin/trail-log`
- delete: `packages/spec-helper/`

## Prompt

### REFERENCE.md

Read the full file. Find the CLI tools tables (there are multiple — one for personal CLI tools, one for bin/ scripts).

1. **Add cfl** to the CLI tools table with these entries:
   - `cfl spec init/validate/status` — "spec lifecycle management"
   - `cfl run start/status/complete/stop/resume` — "orchestration run lifecycle"
   - `cfl task start/update/verdict/block` — "task state management"
   - `cfl gate` — "record gate evaluation results"
   - `cfl dispatch` — "record subagent dispatches"
   - `cfl event` — "append to audit trail"
   - `cfl archive` — "archive completed specs"
   - `cfl set` — "direct field access (bypass guards)"

2. **Remove** `spec-helper` and `trail-log` entries from the table.

3. **Remove** `orchestrate-cost` and `agent-stats` from their current descriptions — they still exist but their descriptions should note they query the cfl database.

### rules/common/capabilities-core.md

1. **Add cfl trigger phrases** to the CLI Tools table:
   - "query orchestration data", "pipeline effectiveness", "gate blocking rate" → `cfl` (or `cfl query` when implemented)
   - "archive completed specs", "clean up old WPs" → `cfl archive`
   - "spec status", "run status", "orchestration status" → `cfl spec status` / `cfl run status`

2. **Remove** spec-helper and trail-log trigger phrases. Currently the archive row says `spec-helper archive --all` — update to `cfl archive`.

3. **Update** the mine-orchestrate skill trigger descriptions if they reference spec-helper or trail-log.

### install.py

Read the file. Find the `packages` tuple in the base bundle (line ~126):
```python
packages=("spec-helper", "merge-settings"),
```

Replace `"spec-helper"` with `"cfl"`. The installation mechanism (`uv tool install -e packages/<name>`) works the same way.

### settings.json

Check if any `allowedTools` entries reference `spec-helper` or `trail-log`. If so, replace with `cfl`. If not, add `Bash(cfl:*)` if appropriate for reducing permission prompts during orchestration.

### Delete bin/trail-log

Remove the file. It's replaced by `cfl event` + implicit events from state commands.

### Delete packages/spec-helper/

Remove the entire directory. It's replaced by `packages/cfl/`. The existing spec-helper tests are no longer relevant — cfl has its own test suite.

## Focus

- `install.py` has a `packages` tuple that lists base-bundle packages. The replacement is a single string change, but verify the package name matches the `pyproject.toml` name in `packages/cfl/`.
- REFERENCE.md is a large file — use targeted edits rather than rewriting sections.
- The `spec-helper` uninstall path in install.py should still work for users who have spec-helper installed — `uv tool uninstall spec-helper` is idempotent.
- Deleting `packages/spec-helper/` is a `git rm -r` operation. Make sure no other file imports from it.

## Verify

- [ ] FR#1: `install.py` registers `cfl` package for installation via `uv tool install -e`
- [ ] FR#27: REFERENCE.md, capabilities-core.md list cfl; no references to spec-helper or trail-log remain in documentation or installation files
