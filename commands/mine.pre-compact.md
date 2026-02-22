---
description: Context preservation around compaction — now automated via hooks.
---

# Pre-Compact (Automated)

Context preservation is now handled automatically by two hooks in `~/Dotfiles/config/claude/settings.json`:

1. **PreCompact hook** (`pre-compact-save.py`) — fires before compaction, extracts file paths, task state, and error tracking entries from the transcript, saves to `/tmp/claude-precompact-{session_id}.md`
2. **SessionStart `compact` hook** (`post-compact-inject.sh`) — fires after compaction, re-injects the saved context as `additionalContext` so it survives

No manual action needed. Both manual `/compact` and auto-compaction are covered.

## What Gets Preserved

The hooks mechanically extract:
- **File paths** from Write/Edit/Read tool calls (last 20 unique, excluding /tmp and .claude)
- **Active tasks** (pending/in-progress items from TaskCreate/TaskUpdate)
- **Error tracking** entries from `/tmp/claude-errors-{session_id}.md`
- **Compaction guidance** (PRESERVE/SUMMARIZE/DROP classification rules)

## Scripts

- `~/Dotfiles/home/bin/mine/pre-compact-save.py` — transcript parser
- `~/Dotfiles/home/bin/mine/post-compact-inject.sh` — context re-injector
