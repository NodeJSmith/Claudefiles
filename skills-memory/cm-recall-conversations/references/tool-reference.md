# Tool Reference

## recent_chats.py

Retrieve recent conversation sessions with all messages.

```bash
cm-recent-chats --n 3
```

| Option                    | Effect                                                 |
| ------------------------- | ------------------------------------------------------ |
| `--n N`                   | Number of sessions (1-20, default 3)                   |
| `--sort-order`            | 'desc' (newest first, default) or 'asc'                |
| `--before DATE`           | Sessions before this datetime (ISO)                    |
| `--after DATE`            | Sessions after this datetime (ISO)                     |
| `--session UUID`          | Filter by session UUID (prefix match)                  |
| `--project NAME`          | Filter by project name(s), comma-separated             |
| `--path SUBSTR`           | Filter by cwd substring (e.g. worktree name)           |
| `--verbose`               | Include files_modified and commits                     |
| `--format`                | 'markdown' (default) or 'json'                         |
| `--include-notifications` | Include task notification messages (hidden by default) |

Use `--verbose` for lenses that need file/commit context (restore-context, review-process, run-retro).

## search_conversations.py

Search for sessions using keyword full-text search (FTS5/FTS4/LIKE cascade) fused with vector similarity via RRF when both the bge-m3 model and the sqlite-vec vector path (queryable `branch_vec`) are available. If either is missing, search degrades to keyword-only.

```bash
cm-search-conversations --query "keyword"
```


| Option | Effect |
|--------|--------|
| `--query` | Required (unless `--status`) — substantive keywords |
| `--status` | Print diagnostic info (vec extension, model path, embedded vs. total summarized (embeddable) branch count) and exit 0 |
| `--keyword-only` | Skip embedding, use keyword search only |
| `--max-results N` | Limit results (1-10, default 5) |
| `--session UUID` | Filter by session UUID (prefix match) |
| `--project NAME` | Filter by project name(s), comma-separated |
| `--path SUBSTR` | Filter by cwd substring (e.g. worktree name) |
| `--verbose` | Include files_modified and commits |
| `--format` | 'markdown' (default) or 'json' |
| `--include-notifications` | Include task notification messages (hidden by default) |

**Output**: Default markdown format (token-efficient):
```
## myproject | 2026-02-01 10:00
Session: abc123

### Conversation

**User:** ...
**Assistant:** ...
```

Use `--format json` when structured data is needed.
