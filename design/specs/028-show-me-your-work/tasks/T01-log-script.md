---
task_id: "T01"
title: "Create bin/log.sh trail logging script"
status: "planned"
depends_on: []
implements: ["FR#1", "FR#2", "FR#3", "FR#4", "AC#2", "AC#3", "AC#7"]
---

## Summary
Create the `bin/log.sh` shell script that appends a single TSV row to a trail file. The script handles timestamping, formula-injection stripping, field sanitization, detail truncation, header row creation, and event vocabulary validation. This is the foundational component — all other tasks depend on it.

Also add the corresponding entries in REFERENCE.md and capabilities-core.md so the script is discoverable and validated by lint-cli-conventions.

## Prompt
Create `bin/log.sh` following the bin script conventions in `bin/get-skill-tmpdir` and `bin/get-tmp-filename`:
- Shebang: `#!/usr/bin/env bash`
- `--help`/`-h` handling with heredoc usage text
- `set -euo pipefail` after help handling
- Argument validation with `${N:?usage: ...}` pattern

Interface: `log.sh <trail-file> <phase> <task> <event> <detail>`

The script must:
1. Accept 5 positional arguments: trail-file (absolute path), phase (`p0`/`p1`/`p2`/`p3`), task (task ID like `T01` or `-` for phase-level), event (from fixed vocabulary), detail (free text)
2. Auto-generate an ISO 8601 timestamp via `date -u +%Y-%m-%dT%H:%M:%SZ`
3. Validate the event field against the fixed vocabulary: `start`, `dispatch`, `verdict`, `contested`, `gate`, `retry`, `review`, `fix`. If undeclared, emit a stderr warning but still write the row
4. Strip formula-injection prefixes (`=`, `+`, `@`, `;`) from the leading position of each field value (phase, task, event, detail). Do NOT strip leading `-`
5. Replace tabs, newlines, and carriage returns in field values with spaces via `tr '\n\t\r' '   '`
6. Truncate the detail field to 500 characters, appending `...` if truncated
7. If the trail file does not exist, write the header row (`timestamp\tphase\ttask\tevent\tdetail`) and data row in a single `printf` call to eliminate the two-step race window
8. If the trail file already exists, append the data row via `printf '%s\t%s\t%s\t%s\t%s\n' ... >> "$trail_file"`
9. Handle empty detail gracefully (write an empty field, not an error)

After creating the script, make it executable with `chmod +x`.

Then update documentation:
- `REFERENCE.md`: Add `log.sh` to the bin/ scripts table (between `lint-cli-conventions` and `phrase-monitor-log` alphabetically). Format: `| log.sh | Append a TSV row to a trail file with timestamping, sanitization, and event validation |`
- `rules/common/capabilities-core.md`: Add `log.sh` to the CLI Tools table. Since it's called by orchestrate (not by the user directly), the trigger phrase can be minimal: `"trail log entry"` | `log.sh`

Read `design/specs/028-show-me-your-work/design.md` section `## Architecture > bin/log.sh` for the full specification.

## Focus
- Follow the exact pattern from `bin/get-skill-tmpdir` for `--help` and `set -euo pipefail` placement
- The `phrase-monitor.sh` log_match function (lines 108-118) is the closest existing TSV append pattern — follow its `printf ... >> "$log_file"` approach but add the sanitization steps
- `lint-cli-conventions` will automatically validate the script: it checks for `--help` handling and syncs against capabilities-core.md entries. The script must pass both checks
- The REFERENCE.md bin scripts table starts at line ~197 and entries are alphabetically ordered
- The capabilities-core.md CLI Tools table starts at line ~56

## Verify
- [ ] FR#1: `log.sh /tmp/test-trail.tsv p2 T01 start "test detail"` appends a row with auto-generated ISO 8601 timestamp
- [ ] FR#2: Running `log.sh` with a detail starting with `=` strips the leading `=`; same for `+`, `@`, `;`. Leading `-` is NOT stripped
- [ ] FR#3: A detail containing literal tab, newline, or carriage return characters has those replaced with spaces in the output
- [ ] FR#4: Running `log.sh` against a nonexistent file creates it with a header row followed by the data row
- [ ] AC#2: No field value in the output begins with `=`, `+`, `@`, or `;`
- [ ] AC#3: No field value in the output contains literal tab, newline, or carriage return characters
- [ ] AC#7: A detail longer than 500 characters is truncated to 500 chars with trailing `...`
