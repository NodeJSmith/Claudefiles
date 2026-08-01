---
task_id: "T03"
title: "Remove moved files and hook registrations from Dotfiles"
status: "planned"
depends_on: ["T02"]
implements: ["FR#7", "AC#6", "AC#7", "AC#8"]
---

## Target Files

- delete: `~/Dotfiles/tools/claude-context-writer`
- delete: `~/Dotfiles/tools/claude-status-writer`
- delete: `~/Dotfiles/tools/context-tier.sh`
- modify: `~/Dotfiles/config/claude/settings.json`

## Prompt

**IMPORTANT**: This task edits files in the **Dotfiles** repo (`~/Dotfiles/`), not in the Claudefiles worktree. Use absolute paths.

### 1. Remove the three script files

Delete these files from the Dotfiles main checkout:

```bash
rm ~/Dotfiles/tools/claude-context-writer
rm ~/Dotfiles/tools/claude-status-writer
rm ~/Dotfiles/tools/context-tier.sh
```

### 2. Remove hook registrations from Dotfiles settings.json

Edit `~/Dotfiles/config/claude/settings.json` to remove:

1. **All `claude-status-writer` hook entries** — the status-writer appears in UserPromptSubmit, PreToolUse, PostToolUse, Stop, Notification, and SessionEnd hook arrays. Remove the entry from each array. If removing an entry leaves an array empty, keep the empty array (don't remove the key — other code may check for its presence).

2. **The `context-tier.sh` PreToolUse entry** — find the PreToolUse entry with `context-tier.sh` in its command and remove it.

3. **The `statusLine` wrapper** — the current config is:
   ```json
   "statusLine": {
     "type": "command",
     "command": "claude-context-writer ~/bin/mine/starship-claude",
     "padding": 0,
     "refreshInterval": 5
   }
   ```
   
   Since `claude-context-writer` is now in Claudefiles and will be registered there, remove the statusLine entry from Dotfiles entirely. **BUT**: check whether `claude-merge-settings` handles statusLine merging correctly — if Claudefiles layer 1 has statusLine and Dotfiles layer 2 also has it, which wins? If layer 1 (Claudefiles) always wins, removing from Dotfiles is safe. If not, the Dotfiles entry would shadow the Claudefiles one. Read `~/Claudefiles/packages/merge-settings/src/merge_settings/merge.py` (the Python implementation behind the `claude-merge-settings` CLI) to understand the merge behavior for top-level keys before deciding.

   If the merge would cause a conflict, keep the Dotfiles entry but update it to point to the new Claudefiles path.

### 3. Verify the merge

Run `claude-merge-settings` and confirm the merged output contains:
- statusLine with `claude-context-writer`
- All `claude-status-writer` hook entries (from Claudefiles layer)
- `context-tier.sh` PreToolUse entry (from Claudefiles layer)
- No duplicate entries

### 4. Check the test suite

Run the Dotfiles test suite for context-tier:
```bash
cd ~/Dotfiles && uv run --script tools/test-context-tier.py
```

If the test imports or references the deleted files by path, it will fail. If it tests the installed symlink (which now points to the Claudefiles copy), it should pass. Fix any path-related test failures.

### 5. Commit in Dotfiles

This is a separate repo, so commit the Dotfiles changes separately:
```bash
git -C ~/Dotfiles add -A
git -C ~/Dotfiles commit -m "refactor: remove sidecar pipeline files moved to Claudefiles

claude-context-writer, claude-status-writer, and context-tier.sh
are now owned by Claudefiles. Hook registrations moved to
Claudefiles settings.json layer."
```

## Verify

- [ ] FR#7: `ls ~/Dotfiles/tools/claude-context-writer ~/Dotfiles/tools/claude-status-writer ~/Dotfiles/tools/context-tier.sh 2>&1` shows "No such file" for all three
- [ ] AC#6: `grep -c 'context-writer\|status-writer\|context-tier' ~/Dotfiles/config/claude/settings.json` returns 0 (or only non-hook references)
- [ ] AC#7: `claude-merge-settings 2>&1 | jq '.statusLine'` shows the context-writer command; merged hooks contain status-writer and context-tier entries from Claudefiles layer
- [ ] AC#8: `cd ~/Dotfiles && uv run --script tools/test-context-tier.py` passes (if the test still exists and tests the installed symlink)
