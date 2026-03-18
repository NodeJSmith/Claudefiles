# Bash Tool vs Dedicated Tools

## Tool Mapping

| Instead of... | Use... |
|---------------|--------|
| `cat` / `head` / `tail` | `Read` |
| `grep` / `rg` | `Grep` |
| `find` / `ls` | `Glob` |
| `sed` / `awk` (edits) | `Edit` |
| `echo >` / heredoc | `Write` |

## Scripting Opportunities

- **Same command written twice** — flag it, offer to wrap in a script (`~/bin/mine/`)
- **Same tool called 3+ times in one block** — suggest batch mode
- **3+ pipe stages** — suggests a missing flag on the upstream tool

For retroactive discovery, use `/mine.tool-gaps`.
