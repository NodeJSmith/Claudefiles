# CLI Affordances — Reference

Detailed dimensions for assessing CLI tool discoverability and usability. Referenced by SKILL.md.

---

## Command Structure

- **Flat vs nested.** 3-5 actions → `tool action`. 15+ actions → `tool group action`. More than two levels deep is almost always too much.
- **Verb-noun vs noun-verb.** Pick one and be consistent. `git commit` and `docker container ls` both work — mixing them doesn't.
- **Default action.** `tool` with no args shows help or a useful default, not an error. `tool subcommand` with no args shows that subcommand's help.
- **Aliases for common operations.** `ls` → `list`, `rm` → `remove`. Keep them out of primary help text so they don't clutter it for newcomers.

---

## Flag Design

- **Short flags for frequent operations** (`-v`, `-q`, `-f`, `-o`); every flag also gets a `--long-form`.
- **Boolean flags positive.** `--color` (default on) with `--no-color` to disable, so the bare form is the common case.
- **Flag values obvious.** `--format json`, not `--json-format` (a format called "json" or a flag that formats JSON?).
- **Mutually exclusive flags** stated in help and rejected clearly: "Cannot use --json and --csv together."
- **Don't overload flags.** `-v` is verbose everywhere; `--version` is always `--version`.

---

## Progressive Disclosure

The simple version works with minimal flags; complexity is available on demand. Every flag has a documented default for the common case, so users only add flags to override.

```
# Beginner: works with zero config
mytool deploy

# Intermediate: override what matters
mytool deploy --env staging

# Advanced: full control
mytool deploy --env staging --strategy canary --timeout 300 --rollback-on-error
```

**Help depth.** `tool --help` shows commands and common flags. `tool command --help` shows command-specific detail. `tool command --help-all` or a man page shows everything. Don't dump everything at the top level.

---

## Learnability

**Consistent patterns across subcommands.** If `tool users list` supports `--json` and `--filter`, then `tool projects list` should too. Users extrapolate from one subcommand to others — reward that instinct.

**Error messages as teaching moments.** When a user makes a mistake, show the correct usage:
```
Error: unknown command "lst"
Did you mean "list"?

Usage: mytool list [--filter STATUS]
```

**Suggest next steps.** After a successful operation, suggest what the user might do next:
```
Created project "my-app" (id: 42)
View:   mytool projects show 42
Deploy: mytool deploy --project 42
```

**Tab completion.** If the tool has subcommands or known flag values, generate shell completions. Most argument parsers (argparse, click, cobra, clap) support this. A completion script is cheap to generate and massively improves discoverability.

---

## Naming

- **Common words:** `list` not `enumerate`, `delete` not `expunge`, `show` not `describe` (unless the domain uses "describe", e.g. AWS CLI).
- **Be specific** only when ambiguous: `create-user` when there are several things to create; plain `create` when there's one.
- **Match the domain.** If the API says "workspace," the CLI says "workspace" — don't rename to "release"/"project".
- **Avoid abbreviations as the canonical name** (`--configuration`, not `--conf`); abbreviations can be power-user aliases.

---

## Argument Validation

**Fail fast, fail specific.** Validate all arguments before starting work. Don't process three items, fail on the fourth, and leave the user wondering what happened to the first three.

**Suggest corrections.** For typos in subcommands or enum flag values, suggest the closest match:
```
Error: unknown format "yaml"
Available formats: json, csv, table
```

**Validate combinations.** If `--start-date` without `--end-date` is meaningless, catch it at parse time:
```
Error: --start-date requires --end-date (or use --last 7d for relative ranges)
```

**Type errors should name the type.** "Expected integer, got 'abc'" not "Invalid value for --port."

---

## Anti-Patterns

- **Flag soup** — 30+ flags on a single command; split into subcommands or use config files
- **Hidden functionality** — features only documented in a README, not in `--help`
- **Positional overload** — `tool a b c d` where the meaning of each position is non-obvious
- **Inconsistent subcommand depth** — `tool list` alongside `tool config set key value`; some actions are one level, others are three
- **Required flags** — if it's required, it should be a positional argument, not `--name NAME`
- **Silent flag ignore** — accepting `--json` without error but producing non-JSON output
- **Version in wrong place** — `tool version` as a subcommand instead of `tool --version`; wastes a subcommand slot for a global concern
- **No help on error** — printing just "Error" with no pointer to `--help` or the correct usage
- **Requiring exact order** — `tool --flag command` works but `tool command --flag` doesn't; flags should work in any position relative to their scope
