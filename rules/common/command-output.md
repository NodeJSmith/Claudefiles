# Command Output Preservation

## Problem

Bash tool output is truncated beyond 30k characters. Using `| tail` to reduce context is good practice, but when the tail doesn't capture enough, re-running the entire command wastes time and compute. Always preserve full output in a tmp file so you can `Read` targeted sections instead.

## Pattern

Two Bash calls:

```bash
# Step 1: create the capture file (pre-allowed, no permission prompt)
get-tmp-filename
# → /tmp/claude-cmd-abc123.txt  (or $CLAUDE_CODE_TMPDIR/claude-cmd-abc123.txt under sandbox)
```

```bash
# Step 2: substitute the exact path printed by step 1 (user approves the real command)
pytest -v 2>&1 | tee /path/from/step-1 | tail -80
```

`get-tmp-filename` automatically uses `$CLAUDE_CODE_TMPDIR` when set (sandbox mode), falling back to `/tmp`.

Remember the path printed by step 1 and substitute it directly into step 2.

**Do NOT** wrap step 1 in a variable assignment like `_f=$(get-tmp-filename)`. The bare command is pre-allowed; any wrapper breaks the permission match and triggers a prompt.

## Setup

Add to `allowedTools` in `~/.claude/settings.json` for auto-approve:

```json
"allowedTools": ["Bash(get-tmp-filename)"]
```

## When to Apply

Use this pattern for any command likely to produce verbose output:

- Test suites (`pytest`, `jest`, `cargo test`, etc.)
- Builds (`make`, `npm run build`, `cargo build`)
- Linting and type checking (`ruff`, `pyright`, `eslint`, `tsc`)
- Package installs (`pip install`, `npm install`)
- Any command where you're already reaching for `| tail`

## When NOT to Apply

Skip the pattern when it adds unnecessary complexity:

- Quick commands with minimal output (`git status`, `git log --oneline -5`)
- Commands where you already need the full output and it's short
- Commands with their own output piping that would conflict
- Background tasks (use `run_in_background` parameter instead)

## Recovery

If the tail didn't capture what you need, **do not re-run the command**. Instead:

- `Read` the saved file with `offset`/`limit` to find the relevant section
- `Grep` the file for error patterns, then `Read` surrounding context

## Cleanup

Files in the system tmp directory (e.g. `/tmp`) are typically cleaned automatically by the OS or are ephemeral in sandboxed environments. If you set `$CLAUDE_CODE_TMPDIR` to a custom, non-ephemeral location, you may need to clean up old capture files manually.
