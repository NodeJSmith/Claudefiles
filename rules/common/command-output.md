# Command Output Preservation

Bash output truncates at 30k chars. Preserve full output in a tmp file.

## When to Capture

**Always** capture to a tmp file when running commands that produce large output or take a long time — test suites, builds, linters, database queries, log tails. Do not rely on increasing `tail -n` arguments across retries; capture once, then read from the file.

**Anti-pattern**: Running `pytest -v | tail -80`, then `pytest -v | tail -200`, then `pytest -v | tail -500` to see progressively more output. Each re-run wastes time and tokens. Capture to a file on the first run, then `Read`/`Grep` the file as needed.

## Pattern

```bash
# Step 1: create capture file (pre-allowed)
get-tmp-filename
# → /tmp/claude-cmd-abc123.txt  (or $CLAUDE_CODE_TMPDIR/... under sandbox)
```

```bash
# Step 2: use the path from step 1
pytest -v 2>&1 | tee /path/from/step-1 | tail -80
```

**Do NOT** wrap step 1 in a variable assignment (`_f=$(get-tmp-filename)`). The bare command is pre-allowed; wrappers break permission matching.

For skill-specific temp files, use `get-skill-tmpdir` instead (see CLAUDE.md).

## Recovery

If tail missed content, `Read`/`Grep` the saved file — do not re-run the command.
