# Context: cfl — Claudefiles Orchestration Store

## Problem & Motivation

Orchestration pipeline signal is fragmented across ephemeral artifacts destroyed on ship. `trail.tsv` is deleted by `spec-helper archive`. The `.orchestrate-state.md` checkpoint file is deleted. The tools that reconstruct partial signal from JSONL transcripts (`orchestrate-cost` at 809 lines, `agent-stats` at 424 lines) use fragile regex parsing that breaks on prompt wording changes. Spec state management lives in markdown files parsed and rewritten on every update, with no concurrency safety and no cross-session durability.

`cfl` replaces both `spec-helper` and `trail-log` with a single Python CLI backed by a durable SQLite store. All orchestration state — spec lifecycle, run management, task status, gate results, dispatch records, events, and session tracking — lives in the DB.

## Visual Artifacts

None.

## Key Decisions

1. **Ground-up replacement, not incremental migration.** No compatibility shims or dual-write periods. `cfl` fully replaces `spec-helper` and `trail-log` in one change.
2. **Python package, not PEP 723 script.** Proper `src/` layout at `packages/cfl/` with tests, following the `packages/spec-helper/` convention. `setuptools` build backend (never hatchling).
3. **DB-first state.** No filesystem state files (`.orchestrate-state.md`, `trail.tsv`). Disk artifacts (task files, design.md) are inputs/outputs, not state.
4. **JSON output by default.** All commands emit JSON with `"_v": 1` schema versioning. `--text` for human-readable debugging. Callers never parse text.
5. **Two-tier commands.** Guarded commands enforce the state machine. `cfl set` bypasses guards for crash recovery. Both tiers log everything.
6. **Auto-resolution from CWD.** Active run resolved from git remote + task file glob + DB `specs.active_run_id`. No explicit run_id threading through SKILL.md.
7. **Implicit event emission.** State-mutating commands emit their own events. Callers don't need separate `cfl event` calls.
8. **Fire-and-forget events.** `cfl event` exits 0 always. DB errors go to stderr only.
9. **Unified verdict vocabulary.** PASS/WARN/FAIL/SKIPPED/BLOCKED. Nuance in `data` JSON.
10. **Session auto-join.** Every active-run command registers the current session via `INSERT OR IGNORE`. No explicit session start.

## Constraints & Anti-Patterns

- **Never use hatchling** — build backend must be `setuptools`.
- **Never use `from __future__ import annotations`** — breaks Pydantic/dataclass runtime inspection.
- **Never use `Optional[X]`** — use `X | None`.
- **Never use lazy imports** — all imports at file top.
- **No `.orchestrate-state.md` file** — all state in SQLite.
- **No `trail.tsv`** — all events in the `events` table.
- **No `--json` flag** — JSON is the default output format.
- **No `--all` flag on archive** — auto-resolves to current spec.
- **DB must not live under `~/.claude/`** or under the Claudefiles repo. Default: `~/.local/share/claudefiles/cfl.db`.
- **All multi-table writes in one `BEGIN IMMEDIATE ... COMMIT` transaction.** No partial writes.
- **Dispatch identity captured at dispatch time** — never reconstructed post-hoc from prompt substrings.
- **Use `whenever` for datetime**, not stdlib `datetime`. Boundary exception: SQLite uses `datetime('now')` internally; convert at the boundary.

## Design Doc References

- `design.md` — Problem, Goals, FRs, ACs, Architecture overview, Impact
- `cli-design.md` — Complete CLI command reference with JSON output schemas, exit code semantics, trail-log → cfl migration mapping, spec-helper → cfl migration mapping, normalization tables
- `db-design-brief.md` — Full DDL for all 7 tables + schema_version, state machines (run lifecycle, task lifecycle), entity relationship diagram, vocabulary definitions, data population tiers, active run resolution logic

## Convention Examples

### pyproject.toml (setuptools backend)

From `packages/spec-helper/pyproject.toml`:

```toml
[build-system]
requires = ["setuptools>=80"]
build-backend = "setuptools.build_meta"

[project]
name = "spec-helper"
version = "2.0.0"
requires-python = ">=3.11"
dependencies = ["python-frontmatter"]

[project.scripts]
spec-helper = "spec_helper.cli:main"

[tool.setuptools.packages.find]
where = ["src"]

[tool.pytest.ini_options]
testpaths = ["tests"]

[dependency-groups]
dev = ["pytest>=9.0.2"]
```

### CLI entry point pattern

From `packages/spec-helper/src/spec_helper/cli.py`:

```python
import argparse
import sys

def main():
    parser = argparse.ArgumentParser(description="...")
    subparsers = parser.add_subparsers(dest="command")
    # ... subcommand definitions
    args = parser.parse_args()
    if args.command is None:
        parser.print_help()
        sys.exit(2)
    # dispatch to command handler
```

### Error handling pattern

From `packages/spec-helper/src/spec_helper/errors.py`:

```python
import json
import sys

def die(message, *, code="error", hint=None, exit_code=1):
    err = {"error": message, "code": code}
    if hint:
        err["hint"] = hint
    json.dump(err, sys.stderr)
    sys.exit(exit_code)
```
