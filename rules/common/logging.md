---
tool: claude, antigravity
---

# Logging

<!-- SYNC: rules/common/invariants.md — update the "Library Code Never Configures Logging" invariant entry when changing this section. -->

This rule loads into every session, so it applies to whatever project is open: a personal-apis package, a homelab systemd service, a one-shot CLI. The right logging approach depends on the role the code is playing, not the project it lives in. Ask which of the three roles below applies before reaching for `print` or the `logging` module. A single file can play more than one role at different times (a script with both a library-style function and a `__main__` block). When that happens, apply rule 1 to the importable parts and rule 2 or 3 to the standalone-run entry point. Don't let the standalone path skip logging setup just because the same file is sometimes imported.

## 1. Library Code: `getLogger` Only, Never Configure

Diagnostic: would another project's `import` statement ever pull this module in, not just invoke it as a CLI subprocess? A shared internal package counts as much as a published one.

If yes:

- `log = logging.getLogger(__name__)` at module level. Nothing else.
- Never call `logging.basicConfig()`, never add a handler, never call `setLevel()`. Configuring logging is the importing application's decision, made once, at its own entry point. A library that configures logging on import can silently break or duplicate whatever the importing app already set up.
- A package can be both a library and an application: its CLI's `main()` configures logging once; every other module in the package just calls `getLogger()` and lets that configuration apply. ccrecall's internal modules use a shared package-level logger name (`logging.getLogger(LOGGER_NAME)` where `LOGGER_NAME = "ccrecall"`) rather than per-module `__name__`. Either approach satisfies this rule. The constraint is that library modules never touch handlers or levels, not which string they pass to `getLogger()`. Only `config.py`'s `setup_logging()` (see rule 3b) ever touches a handler.

## 2. CLI Tools: Print, Not Logging

If the process runs once and the invoker reads its result from stdout (`paperless-api tag ...`, `otf-api classes`, any package-owned CLI), print calls *are* the logging. See `${CLAUDE_CONFIG_DIR:-~/.claude}/skills/cli-output/REFERENCE.md` for the full convention (stdout = data, stderr = everything else). Don't introduce the `logging` module here. It adds handler/formatter ceremony for output nobody reads as a log file. The terminal is the log.

## 3. Unattended Processes: Configure Once at the Entry Point, `getLogger` Everywhere Else

Anything running without a person watching in real time (a systemd service, a Docker container, a Claude Code hook subprocess) needs a persisted log, because there's no terminal to catch the output when something breaks. Configure logging once, centrally, at the process's actual entry point (`main()`, the hook's top-level function). Every module it calls still follows rule 1: `getLogger(__name__)`, no configuration of its own. Then pick 3a or 3b below for where that one-time configuration sends output.

### 3a. stdout is free — systemd services, Docker containers, and anything else with a supervisor that captures stdout for you

Test: does something *other than this process* already read, persist, and rotate whatever it prints to stdout? Systemd (via journald) and Docker (via its log driver) both do. If so, log to stdout/stderr with a JSON formatter: one object per line (timestamp, level, logger name, message, plus structured context via `extra=`). Don't write to an app-managed log file and don't build rotation into the app. That infrastructure already exists. The `log-opts.max-size`/`max-file` pattern already used for hassette's `daemon.json` is where Docker's side of that rotation is configured, not in application code. Reinventing capture/rotation in the app duplicates it.

### 3b. stdout is claimed, or nothing captures it — hook subprocesses, anything whose stdout a caller parses, or a bare unsupervised process (a `nohup`'d script, a cron job with no output redirection)

A Claude Code hook's stdout is the hook response the harness reads and acts on. Logging there corrupts the protocol. A `nohup`'d or cron-launched script has no protocol conflict, but also has no journald/Docker underneath it. Print to stdout there and the output is simply gone. Both cases need the same fix: route logs to a dedicated file instead, via a `RotatingFileHandler` wired up once at the entry point:

- One log file per process identity when more than one instance can run concurrently. A single shared file races on rotation between concurrent writers.
- ccrecall's `setup_logging()` (`src/ccrecall/config.py`) is the reference shape: one `RotatingFileHandler` per `process_name`, handlers cleared and rebuilt on each call so re-invoking the setup is idempotent, an optional `--verbose` `StreamHandler` to stderr layered on top for interactive debugging, level driven by a settings value rather than hardcoded.
- Plain-text formatting is fine here — nothing outside the process reads these files as structured data, unlike 3a's supervisor-captured streams.

## What to Log

<!-- SYNC: rules/common/invariants.md — update the "No Dark Operations" invariant entry when changing this section. -->

An operation that can fail but emits no signal when it does is a **dark operation**: invisible in production until someone notices the downstream symptom and has to reverse-engineer the cause. The coverage points below exist to prevent dark operations, not to encourage logging every line.

Before writing error handling, ask: **"if this fails in production, how will I know?"** If the answer is "I won't," or "only by noticing something downstream broke," you're missing a log statement. This ties directly to `verification.md`'s "Name Observability Gaps": a silent failure path is an observability gap.

### Mandatory coverage

These are the places where a log statement is required, not optional:

- **External I/O boundaries** — API calls, database queries, file reads/writes, network requests. Log the outcome on failure (ERROR or `exception()`). On success, INFO or DEBUG depending on whether a production operator would care about the throughput.
- **Error recovery paths** — every `except` block that doesn't re-raise must log what it caught and what the code did instead (returned a default, skipped the item, retried). A bare `except: pass` or `except SomeError: return None` with no log statement is a dark operation.
- **State transitions** — when a long-running process changes phase, mode, or status (a test moves from setup to execution, an import pipeline advances to the next batch, a service connects or reconnects). INFO level.
- **Entry/exit of expensive operations** — at DEBUG, so it's off by default but available when reproducing a problem. Includes durations when meaningful.

### What not to log

- Routine state reads that just echo a variable's current value.
- Every iteration of a loop — log the summary (count, duration) after, not each step during.
- Anything already visible from the code path or the caller's own logging.

## Choosing a Level

The definitions below are standard, but knowing what each level *means* doesn't help you choose. Use the decision tree after the table.

| Level | Meaning |
|---|---|
| **DEBUG** | Fine-grained diagnostic detail, off by default |
| **INFO** | An action was taken or a milestone reached — normal-operation events |
| **WARNING** | Something unexpected happened but was handled |
| **ERROR** | An operation failed; the process continues but the caller sees a failure or degraded result |
| **CRITICAL** | The process cannot continue |

### Decision tree

1. **Is the process about to exit because of this?** → CRITICAL
2. **Did an operation fail, and will the caller see a failure or degraded result?** → ERROR (or `logging.exception()` inside an `except` block — see below)
3. **Did something unexpected happen, but the code handled it?** (retry succeeded, fallback used, deprecated path taken, input was weird but parseable) → WARNING
4. **Did something happen that a production operator would want to see in normal operation?** (started processing, completed a batch, connected to a service, user action taken) → INFO
5. **Is this detail only useful when actively debugging a problem?** (input values, intermediate results, cache hit/miss, timing of internal steps) → DEBUG

### `exception()` vs `error()`

`logging.exception()` logs at ERROR level and auto-attaches the current exception's traceback. Use it as the default inside `except` blocks — the traceback is almost always the most useful part of the log entry. Use `logging.error()` for failures that aren't from a caught exception (a validation that returned `False`, a response with an unexpected status code, a file that doesn't exist).

```python
# inside an except block — use exception() for the traceback
try:
    resp = client.get(url)
except httpx.TimeoutException:
    log.exception("request timed out", extra={"url": url})
    return fallback_value

# not from a caught exception — use error()
if resp.status_code == 404:
    log.error("resource not found", extra={"url": url, "status": resp.status_code})
```

## Structured Context

Use `extra=` (stdlib) or equivalent (structlog's `bind()`/keyword args) to attach machine-readable context (IDs, counts, durations, entity names) as structured fields rather than interpolating them into the message string. The message says *what happened*; the fields say *to what* and *how much*.

```python
# good — structured fields, message is greppable
log.info("batch import complete", extra={"count": len(items), "duration_s": elapsed})

# avoid — context buried in the string, harder to filter/aggregate
log.info(f"imported {len(items)} items in {elapsed}s")
```

This matters most for JSON-formatted output (rule 3a) where fields become queryable keys, but it's good practice everywhere. Even in plain-text logs, a consistent `extra=` pattern makes `grep` and `jq` more useful than parsing free-form strings.

## Never Log Secrets

Never log secrets, tokens, or credentials, not even at DEBUG level. If one leaks into a log, treat it as compromised and rotate immediately. Full detail: `references/common/security.md` (Secrets, Error Leakage).
