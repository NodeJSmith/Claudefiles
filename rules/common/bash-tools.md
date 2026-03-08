# Bash Tool vs Dedicated Tools

## Why This Matters

By default, Bash invocations require user approval unless the command is explicitly allow-listed in `settings.json`; dedicated tools (Read, Write, Edit, Grep, Glob) are pre-approved. `sed -i` carries additional risk: in-place file edits have no undo.

The permissions allow-list can also reject Bash commands where quoted characters appear in arguments — this is a less obvious cost:

**WRONG:** `grep "endblock" templates/base.html` → not allowed by the permissions allow-list
**RIGHT:** Use `Grep` with `pattern="endblock"` and `path="templates/base.html"`

## Tool Mapping

| Instead of... | Use... | Notes |
|---------------|--------|-------|
| `cat` / `head` / `tail` | `Read` | Use `offset`/`limit` for large files |
| `grep` / `rg` | `Grep` | Supports regex, glob filter, context lines |
| `find` / `ls` | `Glob` | Pattern matching, sorted by modification time |
| `sed` / `awk` (file edits) | `Edit` | Exact string replacement, no in-place risk |
| `echo >` / heredoc `>` | `Write` | Creates or overwrites a file |

## When Bash IS Appropriate

Use Bash for anything without a dedicated tool:

- Running builds, tests, linters: `pytest`, `make`, `npm run build`
- Git operations: `git status`, `git log`, `git diff`
- Process management: starting/stopping servers, checking ports
- CLI tools: `gh`, `az`, `jq`, `curl`, any custom scripts
- Piping and composing commands where no dedicated tool fits
