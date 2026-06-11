# CLI Output — Reference

Detailed dimensions for assessing CLI tool output quality. Referenced by SKILL.md.

---

## Table Formatting

**Align columns.** Unaligned columns force the eye to scan horizontally. Use fixed-width formatting or a table library.

**Right-align numbers.** Numeric columns are easier to compare when right-aligned. Left-align text columns.

**Truncate, don't wrap.** A table row that wraps to two lines destroys the table structure. Truncate long values with `…` and let users get the full value via `--verbose` or `--json`.

**Respect terminal width.** Use `$COLUMNS` or `tput cols`. If the table won't fit, either drop low-priority columns or switch to a vertical key-value layout.

**Headers and separators.** Column headers should be visually distinct (bold, uppercase, or underlined). A separator line between headers and data aids scanning. Omit headers only for single-column output.

```
NAME           STATUS    DURATION
─────────────  ────────  ────────
auth-service   passing      1.2s
data-pipeline  failing     12.4s
web-frontend   passing      0.8s

3 services: 2 passing, 1 failing
```

---

## Color Semantics

**Color conveys meaning, not decoration.** Every color choice should encode information: red = error/failure, green = success, yellow = warning, dim/gray = secondary information. If removing color loses no information, the color was decorative.

**Never rely on color alone.** Pair with symbols, prefixes, or position: `✓ passing` (green), `✗ failing` (red), `⚠ warning` (yellow). Colorblind users and `NO_COLOR` environments see only the text.

**Respect NO_COLOR.** Check `$NO_COLOR` (any value = disable). Also support `--no-color` flag and `--color=never|auto|always`. Default to `auto` (color when TTY, plain when piped).

**Limit the palette.** Stick to the base 8 ANSI colors (or their bright variants). Extended 256-color and truecolor palettes render inconsistently across terminals and themes. Use bold/dim/underline for emphasis over exotic colors.

**Dim secondary information.** IDs, timestamps, paths, and metadata that support the primary output but aren't the main message should be dimmed, not omitted. Users need them sometimes; they shouldn't compete for attention always.

---

## Human vs Machine Output

**Default to human-readable.** Optimized for scanning, with formatting, color, and structure. This is the interactive experience.

**Offer --json for scripting.** JSON output should be a complete, stable representation — not a serialization of the human format. Include fields that the human format omits or truncates.

**Keep the contract stable.** Once a field appears in JSON output, it's an API. Don't rename, retype, or remove fields without a version bump or deprecation notice.

**Other structured formats.** `--csv` for spreadsheet workflows. `--tsv` for `cut`/`awk` pipelines. Only add these if users actually need them — `--json | jq` covers most scripting cases.

**Exit codes are output too.** The exit code is the simplest machine-readable output. `0` = success, non-zero = specific failure. A script that checks `$?` shouldn't need to parse stdout.

---

## Verbosity Levels

**Three levels is usually right.** Quiet (`-q`), default, verbose (`-v`). More than three levels suggests the output design needs rethinking, not more knobs.

- **Quiet** (`-q` / `--quiet`): Only errors and the essential result. For scripting and pipelines where only the exit code and minimal output matter.
- **Default**: The information a typical user needs. Not everything — the right things.
- **Verbose** (`-v` / `--verbose`): Debug-level detail. Timestamps, request IDs, intermediate steps, full paths instead of truncated ones.

**Don't hide errors behind -v.** Errors always print at every verbosity level. Only diagnostic detail moves between levels. (Verbose/debug output goes to stderr — see stderr vs stdout below.)

---

## Progress Indication

**Show progress for anything over ~2 seconds.** Users assume a silent terminal is frozen. A spinner, counter, or progress bar tells them the tool is working. (Progress goes to stderr — see stderr vs stdout below.)

**Clear progress on completion.** Spinners and progress bars should disappear or be replaced by the final result. Don't leave "Processing... done" artifacts in the output when there's a proper result to show.

**Choose the right indicator:**
- **Spinner** — indeterminate duration, no item count
- **Counter** (`3/10`, `Processing item 5...`) — known item count, unknown per-item duration
- **Progress bar** — known total work, measurable progress
- **Elapsed time** — long operations where progress is hard to measure

**Respect non-TTY.** When stderr is not a TTY, skip spinners and progress bars entirely. Print periodic status lines instead (`Processed 1000 of 5000 items`), or nothing if the operation is fast.

---

## stderr vs stdout

**The rule is simple:** data to stdout, everything else to stderr. "Everything else" includes: errors, warnings, progress, debug output, prompts, status messages, and usage help (on error).

**Why it matters:** `mytool | jq .` breaks if status messages land on stdout. `mytool > output.txt` captures noise alongside data. `mytool 2>/dev/null` should suppress diagnostics without losing results.

**Common violations:**
- Printing "Loading..." or "Done!" to stdout
- Mixing error messages into data output
- Sending usage/help to stderr on `--help` (send to stdout — the user asked for it)
- Progress bars that overwrite data lines

---

## Timestamps, Paths, Units

**Timestamps.** Use ISO 8601 (`2024-01-15T09:30:00Z`) for machine output. Use relative time ("2 hours ago") for human output when recency matters more than precision. Always include timezone or use UTC.

**Paths.** Show relative paths when the user is likely in the relevant directory. Show absolute paths in logs, error messages, and verbose output where context may be lost.

**Units.** Always include units for durations (`1.2s`, `45ms`), sizes (`1.3 GB`, `450 KB`), and counts (`3 items`). Bare numbers are ambiguous.

---

## Anti-Patterns

- **Wall of text** — unstructured paragraph output where a table or list would serve better
- **Buried lede** — the important result appears after pages of diagnostic output
- **Color vomit** — every word a different color, no semantic meaning behind any of it
- **Silent success** — command succeeds but prints nothing; user can't tell if it worked or was a no-op
- **Noisy success** — twenty lines of output for an operation that could say "Done. 3 files updated."
- **Format instability** — human output changes shape between runs, breaking naive parsers that should be using `--json`
- **Stdout pollution** — diagnostic, progress, or error output mixed into the data stream
- **Fixed-width assumptions** — output formatted for 80 or 120 columns that overflows or wastes space on real terminals
- **Bare numbers** — `1024` instead of `1024 bytes` or `1 KB`; `3` instead of `3 items` or `3 errors`
