# Command Output Preservation

Bash output truncates at 30k chars. Preserve full output in a tmp file.

## Pattern

```bash
# Step 1: create capture file (pre-allowed)
get-tmp-filename
# → /tmp/claude-cmd-abc123.txt
```

```bash
# Step 2: use the path from step 1
pytest -v 2>&1 | tee /path/from/step-1 | tail -80
```

**Do NOT** wrap step 1 in a variable assignment (`_f=$(get-tmp-filename)`). The bare command is pre-allowed; wrappers break permission matching.

For skill-specific temp files, use `get-skill-tmpdir` instead (see CLAUDE.md).

## Recovery

If tail missed content, `Read`/`Grep` the saved file — do not re-run the command.
