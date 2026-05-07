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

**One-line description per flag.** If a flag needs a paragraph, it belongs in a man page, not `--help`.

**Show defaults.** `--timeout SEC  Connection timeout (default: 30)`. Users shouldn't have to guess the default behavior.

**Include examples.** At least one realistic example at the bottom. Two or three is better. Examples teach faster than descriptions.

**Subcommand help.** `mytool create --help` should show create-specific flags and examples, not the top-level help again.

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

**Use consistent verbs.** Pick a tense and stick with it: "Creating..." → "Created." or "Create... done." Don't mix "Building app" with "Deployed successfully" with "Tests have been run."

**Be specific.** "Processing..." is almost never useful. "Compiling 12 source files..." tells the user what's happening and how much work remains.

**End state should be clear.** After a command completes, the user should know: did it work? what changed? what do I do next?

```
# Bad
Done.

# Good
Created project "my-app" in ./my-app
Next: cd my-app && npm install
```

---

## Consistency

**Same concept, same words.** If you call it "workspace" in one command, don't call it "project" in another. Pick one term and use it everywhere — help text, errors, output, docs.

**Same format, same structure.** If `tool list` outputs a table with NAME, STATUS, UPDATED columns, then `tool list --filter active` should output the same columns in the same order, not a different format.

**Same error style.** If one command says "Error: file not found: foo.txt", another shouldn't say "ERROR — Cannot locate foo.txt" or "foo.txt: No such file or directory". Pick a format and reuse it.

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
