---
task_id: "T03"
title: "Create SessionStart and SessionEnd hooks"
status: "planned"
depends_on: ["T01", "T02"]
implements: ["FR#3", "FR#4", "FR#5", "FR#11", "AC#4", "AC#5", "AC#6", "AC#12"]
---

## Summary
Create two hook scripts: `cass-session-start.sh` (background indexing, background update check, synchronous context injection) and `cass-clear-handoff.sh` (clear-handoff file writer). Wire both into settings.json. Add hook tests to test_hooks.py.

## Target Files
- create: `scripts/hooks/cass-session-start.sh`
- create: `scripts/hooks/cass-clear-handoff.sh`
- modify: `settings.json`
- modify: `tests/test_hooks.py`
- read: `scripts/hooks/tmux-remind.sh` (convention example for hook structure)
- read: `design/specs/1000-ccrecall-to-cass-migration/design.md` (§ Architecture > Hook architecture)

## Prompt
### cass-session-start.sh (SessionStart hook)

Create `scripts/hooks/cass-session-start.sh` following the hook pattern from Convention Examples:

```bash
#!/usr/bin/env bash
```

No `set -euo pipefail` — hook failures must not block session start.

**Guard:** Check `command -v cass >/dev/null 2>&1`. If not found, exit 0 silently.

**Step 1: Background update check (FR#11)**
Spawn `cass-update --if-stale` in a fully detached background process (`nohup ... >/dev/null 2>&1 &` or `setsid`). This checks the 24h timestamp and exits early if not stale.

**Step 2: Background indexing (FR#3)**
Spawn `cass index` in a fully detached background process. Incremental — cass discovers new JSONL files and updates the index.

**Step 3: Synchronous context injection (FR#4)**
Run `cass search --robot --workspace "$(pwd)" --days 7 --limit 3 --fields minimal` with a 3-second timeout (`timeout 3`). Parse the JSON output and emit a context summary to stdout. If the command times out, returns non-zero, or produces empty results, emit nothing and exit 0. Context injection is best-effort.

The stdout output should be a concise summary suitable for Claude Code's SessionStart additional context. Format it as a brief section with session topics and dates.

### cass-clear-handoff.sh (SessionEnd hook)

Create `scripts/hooks/cass-clear-handoff.sh`:

```bash
#!/usr/bin/env bash
```

No `set -euo pipefail`.

**Purpose:** Write a handoff marker file so `/cass-resume` can identify the prior session after `/clear`.

**Steps:**
1. Create directory `~/.local/share/claudefiles-cass/clear-handoff/` if it doesn't exist.
2. Derive a project key from the current working directory (e.g., hash or sanitized path).
3. Write a JSON file at `~/.local/share/claudefiles-cass/clear-handoff/<project-key>.json` containing:
   - `session_id`: from `$CLAUDE_SESSION_ID` if available, otherwise omit
   - `timestamp`: current ISO 8601 timestamp
   - `project_path`: current working directory
4. Exit 0 always.

### settings.json changes

Add the two hooks to the existing hook arrays. Follow the Convention Examples pattern for hook wiring:

**SessionStart** — add a new entry to the existing array (alongside the tmux-remind hook):
```json
{
  "type": "command",
  "command": "bash -c 'f=\"${CLAUDE_CONFIG_DIR:-$HOME/.claude}/scripts/hooks/cass-session-start.sh\"; [ -x \"$f\" ] && exec \"$f\" || exit 0'",
  "timeout": 10000
}
```

Use a 10-second timeout to accommodate the synchronous context injection (3s) plus startup overhead.

**SessionEnd** — add an entry to the currently empty array:
```json
{
  "hooks": [
    {
      "type": "command",
      "command": "bash -c 'f=\"${CLAUDE_CONFIG_DIR:-$HOME/.claude}/scripts/hooks/cass-clear-handoff.sh\"; [ -x \"$f\" ] && exec \"$f\" || exit 0'",
      "timeout": 5000
    }
  ]
}
```

### test_hooks.py changes

Add tests following the existing hook test patterns (subprocess invocation, JSON stdin/stdout, exit code 0):

**SessionStart hook tests:**
- `test_exits_silently_when_cass_not_installed`: Set PATH to exclude cass → hook exits 0 with empty stdout
- `test_spawns_background_cass_index`: Verify the hook attempts to spawn `cass index` (can check via a mock cass script that logs invocations to a temp file)
- `test_triggers_cass_update_if_stale`: Verify `cass-update --if-stale` is spawned in background
- `test_context_injection_produces_output`: Provide a mock cass that returns JSON search results → verify stdout contains context
- `test_context_injection_exits_zero_on_timeout`: Use a mock cass that sleeps longer than 3s → verify exit 0 and empty stdout

**SessionEnd hook tests:**
- `test_writes_handoff_file`: Run the hook in a temp directory → verify the handoff JSON file exists with expected keys

## Focus
- The SessionStart hook does THREE things: update check, index, and context injection. The first two are background (must not block); the third is synchronous with a timeout.
- Use `timeout 3 cass search ...` for the synchronous call. The `timeout` command is available on all Linux systems.
- Background processes must be fully detached — use `nohup ... >/dev/null 2>&1 &` or `(setsid ... &)` to prevent orphan adoption issues.
- The hook receives JSON on stdin (hook context from Claude Code). The SessionStart hook doesn't need to read stdin; the SessionEnd hook may want to for session metadata.
- `tests/test_hooks.py` already has helper infrastructure (`run_hook()`, temp directory patterns) — extend it rather than adding new infrastructure.
- The handoff file's project key should be deterministic from the working directory path so `/cass-resume` can look it up without scanning.

## Verify
- [ ] FR#3: SessionStart hook spawns background `cass index` process
- [ ] FR#4: SessionStart hook emits context summary to stdout from `cass search --robot`
- [ ] FR#5: SessionEnd hook writes handoff file with session ID, timestamp, and project path
- [ ] FR#11: SessionStart hook triggers `cass-update --if-stale` in background
- [ ] AC#4: Starting a session triggers background `cass index`
- [ ] AC#5: Starting a session in a project with indexed history produces context output
- [ ] AC#6: Running `/clear` writes a handoff file readable by `/cass-resume`
- [ ] AC#12: SessionStart hook refreshes the update-check timestamp file when >24h old
