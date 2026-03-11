# Bash Tool vs Dedicated Tools

## Why This Matters

By default, Bash invocations require user approval unless the command is explicitly allow-listed in `settings.json`; dedicated tools (Read, Write, Edit, Grep, Glob) are pre-approved. `sed -i` carries additional risk: in-place file edits have no undo.

The permissions allow-list may only match certain command/argument patterns; variations (including different quoting) can prevent auto-approval and trigger a permission prompt:

**WRONG:** `grep "endblock" templates/base.html` → may not be auto-approved by the permissions allow-list
**RIGHT:** Use `Grep` with `pattern="endblock"` and `path="templates/base.html"` → uses a dedicated, pre-approved tool

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

## Recognizing Scripting Opportunities

When writing ad-hoc bash, watch for patterns that signal a script would be more appropriate:

- **Same command written twice** in a session — on the second occurrence, flag it: "I've now written this pattern twice. Want me to wrap it in a script?"
- **Same tool called 3+ times in one block** (especially with `&` backgrounding or a for-loop) — suggests the tool needs a batch/multi-arg mode; mention it before writing the loop
- **3+ pipe stages** that post-process another tool's output (`tool | jq | python3`) — suggests a missing flag or subcommand on the upstream tool

When flagging, be specific: name the pattern, say where a script would live (`home/bin/mine/` for personal tools), and offer to create it. Don't just silently write the workaround a third time.

For retroactive discovery of recurring patterns across sessions, use `/mine.tool-gaps`.
