# Command Output Preservation

Bash output truncates at 30k chars. Preserve full output in a tmp file.

## Temp Files

Temp files go under the scratchpad directory the harness names in your environment. Where a skill, agent, or rule writes `<scratchpad>`, substitute that path. If no scratchpad is named, use `/tmp`.

The scratchpad is one directory shared by the session and every subagent, so never put fixed filenames directly in it: parallel reviewers or a second run of the same skill would overwrite each other. Give each run its own directory with `mktemp -d <scratchpad>/<name>-XXXXXX` and use fixed filenames inside that.

## When to Capture

**Always** capture to a tmp file when running commands that produce large output or take a long time — test suites, builds, linters, database queries, log tails. Do not rely on increasing `tail -n` arguments across retries; capture once, then read from the file.

**Anti-pattern**: Running `pytest -v | tail -80`, then `pytest -v | tail -200`, then `pytest -v | tail -500` to see progressively more output. Each re-run wastes time and tokens. Capture to a file on the first run, then `Read`/`Grep` the file as needed.

## Pattern

```bash
# Step 1: create capture file
mktemp <scratchpad>/cmd-XXXXXX
```

```bash
# Step 2: use the path from step 1
pytest -v 2>&1 | tee /path/from/step-1 | tail -80
```

**Do NOT** wrap step 1 in a variable assignment (`f=$(mktemp ...)`) — a shell variable set in one Bash call is gone in the next, so step 2 can't use it. Run it bare and reuse the printed path as a literal.

## Recovery

If tail missed content, `Read`/`Grep` the saved file — do not re-run the command.
