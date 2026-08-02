---
task_id: "T01"
title: "Create clear-ready sentinel hook and fix orchestrate-self-reset"
status: "done"
depends_on: []
implements: ["FR#1", "FR#2", "FR#3", "AC#1", "AC#2"]
---

## Target Files

- create: `scripts/hooks/clear-ready-sentinel.sh`
- modify: `bin/orchestrate-self-reset`
- modify: `settings.json`

## Prompt

### 1. Create the sentinel hook script

Create `scripts/hooks/clear-ready-sentinel.sh` (executable). This is a SessionStart hook that fires with `matcher: "clear"` — meaning it runs only after `/clear` has fully reset the session.

The script must:
1. Read JSON payload from stdin (standard Claude Code hook contract)
2. Extract `session_id` from the payload via `jq`
3. Detect the current tmux session name via `tmux display-message -p '#{session_name}'` — the process runs inside a tmux pane, so this works
4. If inside tmux, write a sentinel file: `/tmp/claude-clear-ready-<tmux-session-name>.sentinel`
5. The sentinel file should contain the session_id and a timestamp for debugging
6. If not inside tmux or tmux command fails, exit 0 silently (best-effort, never disrupt the session)
7. Follow the same defensive patterns as other hooks in `scripts/hooks/`: no `set -e`, path-traversal guard on session_id, best-effort writes

Reference `scripts/hooks/cfl-stop-orphans.sh` or `scripts/hooks/git-session-info.sh` for the hook script conventions used in this repo. The hook receives JSON on stdin with fields like `session_id`, `hook_event_name`, etc.

### 2. Update orchestrate-self-reset

Modify `bin/orchestrate-self-reset` to replace the banner-grep polling loop (Step 2, lines 64-81) with sentinel-file polling:

1. **Before sending /clear** (before Step 1): delete any stale sentinel file for this tmux session:
   ```
   rm -f "${ORCHESTRATE_RESET_TMPDIR:-/tmp}/claude-clear-ready-${session}.sentinel"
   ```

2. **Replace Step 2** (the `while true` loop that greps for "Welcome to Claude Code" or "Claude Code v"): poll for the sentinel file instead:
   ```
   deadline=$(($(date +%s) + ORCHESTRATE_RESET_SENTINEL_TIMEOUT))
   while true; do
     if [ "$(date +%s)" -ge "$deadline" ]; then
       fail "timed out waiting for clear-ready sentinel"
     fi
     if [ -f "${ORCHESTRATE_RESET_TMPDIR:-/tmp}/claude-clear-ready-${session}.sentinel" ]; then
       break
     fi
     sleep 1
   done
   ```

3. **After sentinel detected**: clean up the sentinel file before proceeding to Step 3:
   ```
   rm -f "${ORCHESTRATE_RESET_TMPDIR:-/tmp}/claude-clear-ready-${session}.sentinel"
   ```

4. Update the log messages: change `"Welcome banner detected"` to `"Clear-ready sentinel detected"` and the timeout message similarly.

5. Update the script's header comment to describe the sentinel-based approach instead of the banner-based approach.

### 3. Register the hook in settings.json

Add a new SessionStart entry to the `"SessionStart"` array in `settings.json` with `"matcher": "clear"`:

```json
{
  "matcher": "clear",
  "hooks": [
    {
      "type": "command",
      "command": "bash -c 'f=\"${CLAUDE_CONFIG_DIR:-$HOME/.claude}/scripts/hooks/clear-ready-sentinel.sh\"; [ -x \"$f\" ] && exec \"$f\" || exit 0'",
      "timeout": 5000
    }
  ]
}
```

Add it to the existing `"SessionStart"` array alongside the other entries.

## Verify

- [ ] FR#1: `bin/orchestrate-self-reset` contains no `grep` for banner text (no "Welcome to Claude Code", no "Claude Code v")
- [ ] FR#2: `scripts/hooks/clear-ready-sentinel.sh` exists, is executable, reads session_id from stdin JSON, detects tmux session name, writes sentinel to `/tmp/claude-clear-ready-<session>.sentinel`
- [ ] FR#3: `bin/orchestrate-self-reset` polls for the sentinel file with `ORCHESTRATE_RESET_SENTINEL_TIMEOUT` as timeout, cleans up the file after detection
- [ ] AC#1: `grep -c "grep.*Claude Code\|grep.*Welcome" bin/orchestrate-self-reset` returns 0
- [ ] AC#2: `jq '.hooks.SessionStart[] | select(.matcher == "clear")' settings.json` returns the sentinel hook entry
