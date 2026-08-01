---
task_id: "T02"
title: "Move sidecar producers and context-tier consumer from Dotfiles to Claudefiles"
status: "done"
depends_on: []
implements: ["FR#4", "FR#5", "FR#6", "AC#3", "AC#4", "AC#5"]
---

## Target Files

- create: `scripts/hooks/claude-context-writer`
- create: `scripts/hooks/claude-status-writer`
- create: `scripts/hooks/context-tier.sh`
- modify: `settings.json`

## Prompt

### 1. Copy the three scripts

Copy these files from the Dotfiles main checkout to this repo's `scripts/hooks/` directory. Use the Dotfiles main checkout paths (not a worktree):

- `~/Dotfiles/tools/claude-context-writer` → `scripts/hooks/claude-context-writer`
- `~/Dotfiles/tools/claude-status-writer` → `scripts/hooks/claude-status-writer`
- `~/Dotfiles/tools/context-tier.sh` → `scripts/hooks/context-tier.sh`

Read each source file, then Write to the target path. Ensure all three are executable.

**Important**: Copy the files verbatim — do not modify the script logic. The only change allowed is updating header comments to reflect the new home (e.g., "Claudefiles-owned" instead of "Dotfiles-owned"). Do NOT change any paths, thresholds, or behavior.

### 2. Add hook registrations to settings.json

Add the following to Claudefiles' `settings.json`:

#### statusLine (for claude-context-writer)

Add the `statusLine` config at the top level of settings.json (before the `"env"` key). The exact config to add (matching the current Dotfiles config verbatim, including all fields):

```json
"statusLine": {
  "type": "command",
  "command": "claude-context-writer ~/bin/mine/starship-claude",
  "padding": 0,
  "refreshInterval": 5
}
```

The command uses a bare name (`claude-context-writer`) because it's on PATH via symlink. Since the file is moving to `scripts/hooks/`, it needs to stay on PATH. Check whether `claude-context-writer` already has an entry in install.py's symlink manifest. If it does, the bare command works. If not, either add an install.py entry or use a full path in the command.

#### claude-status-writer hooks

The `claude-status-writer` uses `"async": true` (fire-and-forget, no timeout) — this is critical to preserve. It appears on 6 events in the Dotfiles config. Here is the exact registration structure to replicate:

**UserPromptSubmit** — create a new top-level entry (this event doesn't exist in Claudefiles settings yet):
```json
"UserPromptSubmit": [
  {
    "matcher": "",
    "hooks": [
      {
        "type": "command",
        "command": "bash -c 'f=\"${CLAUDE_CONFIG_DIR:-$HOME/.claude}/scripts/hooks/claude-status-writer\"; [ -x \"$f\" ] && exec \"$f\" || exit 0'",
        "async": true
      }
    ]
  }
]
```

**PreToolUse** — add the status-writer to the existing `matcher: "*"` entry's `hooks` array (the one that already has `tmux-drift-check.sh`), as a second hook command in the same array:
```json
{
  "type": "command",
  "command": "bash -c 'f=\"${CLAUDE_CONFIG_DIR:-$HOME/.claude}/scripts/hooks/claude-status-writer\"; [ -x \"$f\" ] && exec \"$f\" || exit 0'",
  "async": true
}
```

**PostToolUse** — add a new `matcher: "*"` entry to the existing PostToolUse array:
```json
{
  "matcher": "*",
  "hooks": [
    {
      "type": "command",
      "command": "bash -c 'f=\"${CLAUDE_CONFIG_DIR:-$HOME/.claude}/scripts/hooks/claude-status-writer\"; [ -x \"$f\" ] && exec \"$f\" || exit 0'",
      "async": true
    }
  ]
}
```

**Stop** — the `"Stop": []` array exists but is empty. Add:
```json
{
  "matcher": "",
  "hooks": [
    {
      "type": "command",
      "command": "bash -c 'f=\"${CLAUDE_CONFIG_DIR:-$HOME/.claude}/scripts/hooks/claude-status-writer\"; [ -x \"$f\" ] && exec \"$f\" || exit 0'",
      "async": true
    }
  ]
}
```

**SessionEnd** — the `"SessionEnd": []` array exists but is empty. Add:
```json
{
  "matcher": "",
  "hooks": [
    {
      "type": "command",
      "command": "bash -c 'f=\"${CLAUDE_CONFIG_DIR:-$HOME/.claude}/scripts/hooks/claude-status-writer\"; [ -x \"$f\" ] && exec \"$f\" || exit 0'",
      "async": true
    }
  ]
}
```

**Notification** — create a new top-level entry. Use `matcher: "permission_prompt|elicitation_dialog"` (matching the Dotfiles config exactly — this limits it to permission and elicitation events only):
```json
"Notification": [
  {
    "matcher": "permission_prompt|elicitation_dialog",
    "hooks": [
      {
        "type": "command",
        "command": "bash -c 'f=\"${CLAUDE_CONFIG_DIR:-$HOME/.claude}/scripts/hooks/claude-status-writer\"; [ -x \"$f\" ] && exec \"$f\" || exit 0'",
        "async": true
      }
    ]
  }
]
```

#### context-tier.sh hook

Add the context-tier hook to the existing `matcher: "*"` PreToolUse entry's `hooks` array (same entry as tmux-drift-check and the status-writer above). Insert it as the **first** hook in the array so it fires before the status-writer:

```json
{
  "type": "command",
  "command": "bash -c 'f=\"${CLAUDE_CONFIG_DIR:-$HOME/.claude}/scripts/hooks/context-tier.sh\"; [ -x \"$f\" ] && exec \"$f\" || exit 0'",
  "timeout": 2000
}
```

### 3. Verify no duplicate hook registrations

After editing, confirm that each hook script appears exactly once per event in the merged settings. Run:
```bash
claude-merge-settings 2>&1 | grep -c "context-writer\|status-writer\|context-tier"
```

The expected count: status-writer appears in 6 events, context-tier in 1, context-writer in statusLine = ~8 total references. Each script should appear at most once per event. If duplicates appear (from both Claudefiles and Dotfiles layers), flag it — the Dotfiles cleanup in T03 will resolve it.

## Verify

- [ ] FR#4: `scripts/hooks/claude-context-writer` exists, is executable, content matches Dotfiles source
- [ ] FR#5: `scripts/hooks/claude-status-writer` exists, is executable, content matches Dotfiles source
- [ ] FR#6: `scripts/hooks/context-tier.sh` exists, is executable, content matches Dotfiles source
- [ ] AC#3: `jq '.statusLine' settings.json` shows all four fields: type, command (referencing `claude-context-writer`), padding (0), refreshInterval (5)
- [ ] AC#4: `grep -c 'claude-status-writer' settings.json` returns 6 (one per event); all entries have `"async": true` and no `"timeout"` field
- [ ] AC#5: `jq '.hooks.PreToolUse[] | select(.hooks[].command | test("context-tier"))' settings.json` returns the context-tier entry with `"timeout": 2000`
