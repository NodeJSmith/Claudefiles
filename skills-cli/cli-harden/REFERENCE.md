# CLI Hardening — Reference

Detailed dimensions for assessing CLI tool resilience. Referenced by SKILL.md.

---

## Output Handling

**Empty results**: Every command that can return zero results must handle it gracefully — not silent exit, not a stack trace. Print a short message to stderr and exit 0 (empty is not an error) or exit 1 with explanation if emptiness indicates a problem.

**Huge output**: If a command can produce thousands of lines, consider whether it should paginate interactively (`$PAGER` or `less`) or stream unbuffered when piped. Never buffer unbounded output into memory.

**Piped vs interactive (isatty)**: Detect whether stdout is a terminal. Color, progress bars, and interactive prompts go to TTY only. When piped, emit clean parseable output. Check `[ -t 1 ]` (bash) or `sys.stdout.isatty()` (Python).

**stderr vs stdout**: Data goes to stdout. Status messages, progress, errors go to stderr. Never mix diagnostic output into stdout — it breaks pipes.

**Machine-readable output**: If the tool has human-readable output, consider `--json` or structured output for scripting. Exit codes should be meaningful even without parsing output.

---

## Input Resilience

**Missing/invalid arguments**: Fail fast with a clear message and usage hint. Don't proceed with partial input hoping it works.

**Special characters in arguments**: Filenames with spaces, quotes, glob characters, leading dashes (`-file.txt`), unicode. Quote all variable expansions in shell (`"$var"` not `$var`). Use `--` to separate flags from positional args.

**Extremely long arguments**: Arguments near `ARG_MAX`, deeply nested paths, multi-megabyte stdin. Set sane limits and report them clearly.

**Unexpected stdin**: If the tool reads stdin, handle binary data, empty input, and encoding mismatches without crashing.

---

## Signal Handling

**SIGINT (Ctrl-C)**: Clean up temp files, release locks, restore terminal state. Don't leave partial output or corrupt state. Exit with 128+2 (130).

**SIGTERM**: Same cleanup as SIGINT. Scripts running under process managers receive SIGTERM first.

**SIGPIPE**: When piped to `head` or similar, don't print "broken pipe" errors. In Python: `signal.signal(signal.SIGPIPE, signal.SIG_DFL)`. In bash, this is usually handled automatically.

**Trap cleanup pattern** (bash):
```bash
cleanup() { rm -f "$tmpfile"; }
trap cleanup EXIT
```

**Trap cleanup pattern** (Python):
```python
import atexit, os, tempfile
tmp = tempfile.NamedTemporaryFile(delete=False)
tmp.close()
atexit.register(lambda: os.unlink(tmp.name))
```

---

## Permission & Environment

**Missing permissions**: Check before acting, not after. If a file needs write access, test upfront and fail with a specific message ("Cannot write to /etc/foo: permission denied") not a stack trace.

**Missing dependencies**: If the tool shells out to external commands, check they exist before invoking. `command -v jq >/dev/null || { echo "requires jq" >&2; exit 1; }`.

**Environment variables**: Validate required env vars at startup. Distinguish "not set" from "set to empty." Provide defaults where sensible.

**PATH issues**: Use absolute paths for critical system commands in scripts that might run in minimal environments (cron, CI, containers).

---

## Partial Failures

**Batch operations**: When processing N items and some fail, report what succeeded, what failed, and why. Don't stop on first failure unless the user asked for `--fail-fast`. Exit with non-zero if any item failed.

**Atomic writes**: Write to a temp file, then `mv` to the final path. Never write directly to the target — interrupted writes corrupt the file. In Python: `tempfile.NamedTemporaryFile(dir=target_dir, delete=False)` + `os.rename`.

**Network operations**: Timeouts on every network call. Retry with backoff for transient failures. Report which endpoint failed, not just "network error."

---

## Exit Codes

- `0` — success
- `1` — general error
- `2` — usage/argument error (matches bash convention for `getopts`)
- `128+N` — killed by signal N

Document non-obvious exit codes in `--help`. Be consistent across subcommands. Never exit 0 on failure.

---

## Long-Running Operations

**Progress**: Show progress to stderr when output is a TTY. Minimum: a spinner or `Processing N of M...`. For long operations, show elapsed time or ETA.

**Cancellation**: SIGINT should abort cleanly, not leave half-written output.

**Timeouts**: Provide `--timeout` for operations that could hang. Default to a sane value rather than infinite.

---

## Terminal Compatibility

**Narrow terminals**: Don't assume 80+ columns. Use `$COLUMNS` or `tput cols` for dynamic width. Truncate or wrap gracefully. Tables that overflow are unreadable.

**NO_COLOR**: Respect `$NO_COLOR` (https://no-color.org/). Also support `--no-color` flag. Test that output is readable without color.

**TERM=dumb / non-interactive**: No ANSI escapes, no cursor movement, no progress bars. Detect with `$TERM` and isatty.

**Locale**: Set `LC_ALL=C` for predictable sorting/matching in scripts that parse output. Use `locale.getpreferredencoding()` or explicit UTF-8 in Python.

---

## Concurrency

**Lock files**: If only one instance should run, use a lock file. Don't use PID files — they go stale.

```bash
exec 9>/tmp/mytool.lock
flock -n 9 || { echo "already running" >&2; exit 1; }
```

```python
import fcntl
lock = open("/tmp/mytool.lock", "w")
try:
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
except BlockingIOError:
    sys.exit("already running")
```

**Race conditions**: If multiple invocations can write to the same file, use atomic writes. If they share state, use file locking.

---

## Anti-Patterns

- `set -e` without `trap` — exits on error but leaves temp files, locks, partial output
- Parsing `ls` output — breaks on filenames with spaces/newlines; use `find` or globs
- `cat file | grep` — useless use of cat; `grep pattern file`
- Unquoted `$variables` in bash — word splitting and glob expansion
- Bare `except:` or `except Exception` in Python — swallows KeyboardInterrupt
- Writing to stdout from a function that also returns data via stdout — mix corrupts both
- `exit 0` in an error handler — caller can't detect the failure
- Hardcoded terminal width (80, 120) — breaks on actual terminals
- Color codes without isatty check — garbles output when piped
