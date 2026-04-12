---
description: Manage conversation memory database
allowed-tools: [Bash, Read]
argument-hint: "<subcommand: search|stats|import>"
---

# Memory Management Command

You are handling the `/cm-manage-memory` command for managing the conversation memory database.

## Available Subcommands

| Subcommand | Description |
|------------|-------------|
| `search <query>` | Quick FTS search, return snippets |
| `stats` | Show DB size, project/session/message counts |
| `import` | Re-import all conversations from ~/.claude/projects |

Session syncing is handled automatically by the Stop hook (`cm-memory-sync`) — no manual sync subcommand is needed or possible, since the session ID is only available to hook machinery, not Bash tool calls.

## Implementation

Based on the user's subcommand, execute the appropriate action:

### search <query>

Search conversations using full-text search:

```bash
cm-search-conversations --query "<query>" --max-results 5
```

Display the results in a readable format.

### stats

Show database statistics:

```bash
cm-import-conversations --stats
```

Display the stats including database size, number of projects, sessions, and messages.

### import

Re-import all conversations:

```bash
cm-import-conversations
```

Report the import results.

## User Arguments

The user provided: `$ARGUMENTS`

Parse the subcommand and any additional arguments, then execute the appropriate action. If no subcommand is provided or an unknown subcommand is given, show the available subcommands.
