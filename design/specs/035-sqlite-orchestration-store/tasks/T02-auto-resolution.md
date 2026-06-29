---
task_id: "T02"
title: "Implement auto-resolution and session tracking"
status: "done"
depends_on: ["T01"]
implements: ["FR#8", "FR#22", "FR#23", "AC#8", "AC#22", "AC#26"]
---

## Summary

Implement the auto-resolution chain that every active-run command uses to find the current spec and run from CWD, and the session tracking that registers the current Claude Code session on every active-run command. These are cross-cutting concerns used by most subsequent commands.

## Target Files

- create: `packages/cfl/src/cfl/resolve.py`
- create: `packages/cfl/src/cfl/session.py`
- create: `packages/cfl/tests/test_resolve.py`
- create: `packages/cfl/tests/test_session.py`
- modify: `packages/cfl/src/cfl/cli.py`
- read: `design/specs/035-sqlite-orchestration-store/cli-design.md`
- read: `design/specs/035-sqlite-orchestration-store/db-design-brief.md`

## Prompt

**src/cfl/resolve.py — Auto-resolution:**

Implement the resolution chain from `cli-design.md` §Auto-resolution:

1. `resolve_repo_url()` — run `git remote get-url origin`. If no remote, fall back to hash of root commit SHA (`git rev-list --max-parents=0 HEAD`). Return the URL string.

2. `resolve_spec(conn, *, spec_override=None, require_active_run=True)` — returns `(spec_id, spec_number, spec_slug, active_run_id, feature_dir)` or calls `emit_error()`.
   - If `spec_override` is set, query `specs` by `(repo_url, number)` directly.
   - Otherwise: glob `design/specs/*/tasks/T*.md` from CWD. If no matches, fall back to `design/specs/NNN-*/` directory pattern. Extract spec numbers from paths. Query `specs` by `(repo_url, number IN (...))`.
   - If `require_active_run`: filter to `active_run_id IS NOT NULL`. Exactly one = resolved. Zero = error `no_active_run`. Multiple = error with "use --spec NNN".
   - If not `require_active_run`: return spec without filtering on active_run_id. Still error on zero or ambiguous.

3. `resolve_run(conn, spec_id)` — returns run row dict. Verifies `runs.status = 'running'`. Errors if status mismatch.

4. `resolve_context(conn, *, spec_override=None, require_active_run=True)` — convenience wrapper. Calls `resolve_repo_url()`, `resolve_spec()`, optionally `resolve_run()`, then `auto_join_session()`. Returns a context dict with all resolved fields.

Also update `repo_path` on the spec row each invocation: `UPDATE specs SET repo_path=? WHERE id=?` with the current git root path.

**Wire into cli.py:** Replace the stub implementations for `session end` and `session compacted` with calls to `end_session()` and `record_compaction()`. Parse CLI arguments: `cfl session end [--reason <clear|exit>]` and `cfl session compacted [--context-pct <n>]`.

**src/cfl/session.py — Session tracking:**

1. `auto_join_session(conn, run_id)` — reads `$CLAUDE_CODE_SESSION_ID`. If unset, return None. Otherwise: `INSERT OR IGNORE INTO sessions (run_id, session_id, model, context_pct_start, started_at) VALUES (?, ?, ?, ?, datetime('now'))`. `model` from env or None. `context_pct_start` from sidecar file. Returns session_id.

2. `read_context_pct()` — reads `/tmp/claude-context-<session_id>.meta`, extracts `pct=N`. Returns int or None if file missing/malformed.

3. `end_session(conn, session_id, reason=None)` — `UPDATE sessions SET ended_at=datetime('now'), context_pct_end=? WHERE session_id=?`. Read `context_pct_end` from sidecar.

4. `record_compaction(conn, run_id, session_id, context_pct_before)` — insert a `session.compacted` event with data JSON.

**Tests:**

`test_resolve.py`:
- Test repo URL resolution from git remote (create a temp git repo with a remote).
- Test repo URL fallback when no remote (root commit hash).
- Test spec resolution from task file glob (create temp spec directory with task files).
- Test spec resolution from directory fallback (spec dir without task files).
- Test `--spec` override bypasses disk glob.
- Test error cases: no spec found, multiple specs without override, no active run.

`test_session.py`:
- Test auto-join creates session row when `$CLAUDE_CODE_SESSION_ID` is set.
- Test auto-join is idempotent (second call is a no-op).
- Test auto-join skips when env var unset.
- Test `end_session` sets `ended_at`.
- Test `record_compaction` creates event row.

## Focus

- Auto-resolution runs `git` commands via `subprocess.run`. Handle `subprocess.CalledProcessError` gracefully — if not in a git repo, error with a clear message.
- The sidecar file path uses `$CLAUDE_CODE_SESSION_ID`, not a hardcoded session ID. If the env var is missing, all session-related work is silently skipped.
- `resolve_spec()` must handle both `--spec NNN` (just the number) and `--spec NNN-slug` (number extracted from prefix). Parse the number from the prefix.
- The `specs` table uses `UNIQUE(repo_url, number)` — this is the identity key. Don't confuse with `specs.id` (autoincrement PK).

## Verify

- [ ] FR#8: In a worktree with one spec's task files, `resolve_context()` auto-resolves to that spec without `--spec`
- [ ] FR#22: After `auto_join_session()` with `$CLAUDE_CODE_SESSION_ID` set, sessions table has a row for that session
- [ ] FR#23: `cfl session end` sets `ended_at` and `context_pct_end`; `cfl session compacted --context-pct 78` creates a `session.compacted` event — both commands work end-to-end through the CLI
- [ ] AC#8: In a worktree with one spec's task files, `cfl run status` auto-resolves to that spec without `--spec`
- [ ] AC#22: After any `cfl` active-run command with `$CLAUDE_CODE_SESSION_ID` set, sessions table has a matching row
- [ ] AC#26: `cfl session end` sets `ended_at` and `context_pct_end`; `cfl session compacted --context-pct 78` creates `session.compacted` event with `context_pct_before=78`
