# CLI Affordances — Reference

Detailed dimensions for assessing CLI tool discoverability and usability. Referenced by SKILL.md.

---

## Command Structure

**Flat vs nested.** A tool with 3-5 actions works well as `tool action`. A tool with 15+ actions needs subcommand groups: `tool group action`. More than two levels deep (`tool group subgroup action`) is almost always too much.

**Verb-noun vs noun-verb.** Pick one and be consistent. `git commit` (verb-noun) and `docker container ls` (noun-verb) both work — mixing them doesn't.

**Default action.** Running `tool` with no arguments should show help or a useful default, not an error. Running `tool subcommand` with no arguments should show that subcommand's help.

**Aliases for common operations.** `tool ls` → `tool list`, `tool rm` → `tool remove`. Aliases reduce friction for experienced users but shouldn't appear in primary help text (they clutter it for newcomers).

---

## Flag Design

**Short flags for frequent operations.** `-v`, `-q`, `-f`, `-o` — these are muscle memory. Reserve single letters for operations users type daily.

**Long flags for everything.** Every flag should have a `--long-form`. Short flags are a convenience, not a replacement.

**Boolean flags should be positive.** `--color` (default on) with `--no-color` to disable. Not `--no-color` (default off) with `--color` to enable. The bare form should be the common case.

**Flag values should be obvious.** `--format json` or `--format=json`, not `--json-format` (is that a format called "json" or a flag that formats JSON?).

**Mutually exclusive flags.** If `--json` and `--csv` can't both be used, say so in help and error clearly: "Cannot use --json and --csv together."

**Don't overload flags.** `-v` should not mean "verbose" in one subcommand and "version" in another. `--version` is always `--version`.

---

## Progressive Disclosure

**Beginner path.** A new user should be able to accomplish the most common task with minimal flags. `tool create "My Thing"` not `tool create --type standard --format default --name "My Thing" --no-dry-run`.

**Sensible defaults.** Every flag should have a default that works for the common case. The user only adds flags to override the default. Document what the defaults are.

**Complexity on demand.** The simple version works. The advanced version is available. The user discovers advanced features when they need them, not on first use.

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

**Use common words.** `list` not `enumerate`. `delete` not `expunge`. `show` not `describe` (unless the domain uses "describe" — e.g., AWS CLI).

**Be specific.** `create-user` not `create` (when there are multiple things to create). But if there's only one thing to create, just `create`.

**Match the domain.** If users think in "deployments," don't call them "releases." If the API says "workspace," the CLI should say "workspace" too.

**Avoid abbreviations.** `--configuration` not `--conf` or `--cfg` as the primary form. Abbreviations can be aliases for power users but shouldn't be the canonical name.

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
