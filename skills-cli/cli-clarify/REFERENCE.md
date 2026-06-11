# CLI Clarity — Reference

Detailed dimensions for assessing CLI tool communication quality. Referenced by SKILL.md.

---

## Error Messages

**Say what went wrong, what to do about it, and why.** A good error message answers three questions: What happened? Why? What can the user do?

```
# Bad
Error: invalid input

# Good
Error: --since requires a date (e.g., 2024-01-15 or "3 days ago")

# Bad
Permission denied

# Good
Cannot write to /etc/myapp/config: permission denied. Run with sudo or change ownership.
```

**Include the failing value.** "Invalid port number" is less useful than "Invalid port number: 99999 (must be 1-65535)."

**Don't blame the user.** "You entered an invalid email" → "Invalid email format. Expected: name@example.com."

**Distinguish user errors from system errors.** A typo in a flag is a usage error (exit 2, show relevant help). A network timeout is a runtime error (exit 1, suggest retry). The message should reflect which kind it is.

**Never print a stack trace by default.** Stack traces are for `--verbose` or `--debug`. The default error message should be one or two lines of plain language.

---

## Help Text

**--help is documentation.** For many users, `--help` is the only docs they'll read. Treat it accordingly.

**Structure:**
```
Usage: mytool <command> [options]

Commands:
  list     List all items
  create   Create a new item
  delete   Remove an item

Options:
  -v, --verbose   Show detailed output
  -q, --quiet     Suppress non-essential output
  --json          Output as JSON
  -h, --help      Show this help

Examples:
  mytool list --json
  mytool create --name "My Item"
  mytool delete 42
```

- **One-line description per flag** — a paragraph belongs in a man page.
- **Show defaults:** `--timeout SEC  Connection timeout (default: 30)`.
- **Include examples** — at least one realistic example at the bottom; two or three is better.
- **Subcommand help** shows that subcommand's flags and examples, not the top-level help again.

---

## Flag and Argument Names

**Flags should be self-documenting.** `--output-format` over `--fmt`. `--dry-run` over `-n`. Names should be real words, not abbreviations or jargon. A new user reading `--help` should understand what each flag does without consulting docs.

For flag structure conventions (short/long forms, boolean polarity, mutual exclusion), see `cli-affordances/REFERENCE.md`.

---

## Prompts and Confirmations

**State the action and consequences.** "Delete 3 files? This cannot be undone. [y/N]" not "Are you sure? [y/N]."

**Default to safe.** Destructive prompts default to No (`[y/N]`). Creative/additive prompts can default to Yes (`[Y/n]`).

**Respect --yes and --force.** Scriptable tools must allow bypassing prompts. `--yes` for all confirmations, `--force` for safety checks.

**Don't over-prompt.** If an action is easily reversible, don't confirm. Reserve prompts for destructive or expensive operations.

**Show what will happen.** Before a destructive batch operation, list the items that will be affected:
```
Will delete:
  - config/old-settings.yaml
  - data/cache/*.tmp (14 files)

Proceed? [y/N]
```

---

## Status and Progress Messages

- **Consistent verbs/tense:** "Creating..." → "Created." Don't mix "Building app" with "Deployed successfully."
- **Be specific:** "Compiling 12 source files..." over "Processing...".
- **End state clear:** after completion the user knows did it work, what changed, what next.

```
# Bad
Done.

# Good
Created project "my-app" in ./my-app
Next: cd my-app && npm install
```

---

## Consistency

- **Same concept, same words** across help, errors, output, docs (don't alternate "workspace"/"project").
- **Same format, same structure** — `tool list` and `tool list --filter active` share columns and order.
- **Same error style** — pick one format ("Error: file not found: foo.txt") and reuse it; no "ERROR —" vs "error:" drift.

---

## Anti-Patterns

- **Cryptic codes** — "Error E4012" with no explanation; codes are fine as supplements but not as the entire message
- **Developer internals leaking** — Python tracebacks, Go panics, Node stack traces as the default error output
- **Help text as error** — dumping the full `--help` output when the user makes a minor mistake; show only the relevant flag or subcommand
- **Inconsistent casing** — "Error:" vs "ERROR:" vs "error:" across the same tool
- **Missing articles and prepositions** — "cannot find file" reads like a log entry; "Cannot find the file" reads like communication
- **Jargon without context** — "ECONNREFUSED" instead of "Connection refused: is the server running?"
- **Redundant prefixes** — every line starting with the tool name when it's obvious what tool is running
- **No distinction between no-op and success** — "Done" when nothing changed vs "Done" when 50 files were updated; users need to know which
