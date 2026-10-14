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

- **Same command written twice** — flag it, offer to wrap in a script (repo `bin/`, symlinked to `~/.local/bin/`)
- **Same tool called 3+ times in one block** — suggest batch mode
- **3+ pipe stages** — suggests a missing flag on the upstream tool

## Sudo

Local `sudo` cannot authenticate: there is no TTY for the password prompt. Give the user the exact command to run (`! sudo <cmd>` in the CLI runs it in-session), or for multi-step work write a script via `get-tmp-filename` that logs through `tee -a` to a file created with `install -m 600` and confirms (default-N) between destructive phases. Remote `ssh host 'sudo ...'` runs normally.
