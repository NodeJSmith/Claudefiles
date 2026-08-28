# CLI UX — Reference

Principles for building CLIs that humans actually want to use. Distilled from [clig.dev](https://clig.dev).

The cli-* skills own specific dimensions in detail — output formatting, affordances, clarity, hardening. This file covers the cross-cutting concerns those skills don't own: philosophy, signals (behavioral), defaults, configuration, environment variables, secrets, subcommand design, and future-proofing. For implementation details on signals and exit codes (trap patterns, SIGPIPE, exit 130), see `cli-harden/REFERENCE.md`.

---

## Philosophy

**Design for humans first.** Machines can adapt; humans are stuck with what you ship. Human-readable output, helpful errors, and sensible defaults are not polish — they are the primary deliverable.

**CLIs are conversations.** Users iterate: type a command, read the output, adjust, repeat. Every response is a turn in that conversation. Design for the whole loop: errors should suggest a fix, success should say what happened, and next steps should be obvious.

**Composability is a feature.** stdin, stdout, stderr, exit codes, and plain text work everywhere. A tool that plays well with pipes and `$?` can be used in ways you never planned for.

**The test:** a CLI that cannot be used in a script without modification is not yet done. If getting machine-readable output requires parsing human-readable formatting, or if confirmation prompts block non-interactive use, the tool is incomplete. Apply this to every new command and flag.

---

## Exit Codes

At minimum, distinguish usage errors from runtime errors — don't use `1` for everything. Map important failure modes to distinct codes so scripts can branch on `$?` without parsing output. For the full table and implementation detail, see `cli-harden/REFERENCE.md`.

---

## Signals and Control Characters

This section covers the user-facing behavior; trap patterns and exit codes live in `cli-harden/REFERENCE.md`.

**Ctrl-C exits immediately.** Don't hang on cleanup. If cleanup is running, add a timeout so the process can't get stuck.

**Second Ctrl-C skips cleanup.** Tell the user before cleanup starts: "Press Ctrl-C again to force quit." A second interrupt should force-exit even if cleanup isn't done.

**Say something before cleanup.** A silent wait after Ctrl-C looks like a freeze. Even a brief "Shutting down..." is better than silence.

---

## Defaults

**Defaults are for the majority.** Most users won't read the docs or remember flags. The default behavior should be correct for the common case without any extra flags.

**Don't require flags for common operations.** If users always pass `--format table`, make table the default. Flags override defaults; they shouldn't encode the standard path.

**Show what happened by default.** Silent success leaves users wondering if anything ran. Report state changes: what was created, updated, deleted, or left unchanged.

---

## Interactivity and TTY Detection

**Only prompt when stdin is a TTY.** When stdin is piped or redirected, fail with a clear error or require the value as a flag — never hang waiting for input that won't come.

**Support `--no-input`.** Lets users explicitly disable all interactive prompts. Commands that need input should fail with a usage message when `--no-input` is set.

**Never require prompts.** Every prompt must have a flag or argument alternative. Scripts cannot type answers.

---

## Subcommand Design

**No abbreviation prefix matching.** Allowing `mytool i` as shorthand for `mytool install` permanently blocks any future subcommand starting with `i`. Use explicit, stable aliases instead. Generated CLIs often add abbreviation matching because it feels ergonomic — argparse supports it, bash completion does it, and training data is full of it. Don't. Explicit aliases are fine; implicit prefix matching is not.

**No catch-all shortcuts.** `mytool echo` as an alias for `mytool run echo` creates two syntaxes to maintain forever and blocks `echo` ever becoming a real subcommand.

**Noun-verb or verb-noun — pick one.** `tool resource action` or `tool action resource`. Don't mix patterns across subcommands. Two levels is usually right; three is the max before the structure fights users.

---

## Configuration Precedence

From highest to lowest:

1. **Flags** — always win
2. **Environment variables** — session-level context
3. **Project config** (`.env`, `myapp.yaml`, section in `pyproject.toml`) — checked into the repo
4. **User config** (`~/.config/myapp/config.yaml`) — personal preferences
5. **System config** (`/etc/myapp/config.yaml`) — machine-wide defaults

Document this order. When a value can be set in multiple places, higher-priority sources win silently — users need to know where to look when something is unexpectedly set.

Follow the [XDG Base Directory Specification](https://specifications.freedesktop.org/basedir-spec/latest/) for file locations: config in `~/.config/myapp/`, cache in `~/.cache/myapp/`, data in `~/.local/share/myapp/`. **Generated tools almost always default to `~/.mytool` or `~/.myapprc` because that's what most tutorials show.** Use `~/.config/myapp/` instead.

---

## Environment Variables

**Names:** Uppercase, letters, numbers, underscores only. Don't start with a number. Prefix with the tool name: `MYTOOL_TIMEOUT`, not `TIMEOUT`.

**Values:** Single-line when possible. Multi-line values cause problems with `env` output and some shells.

**Respect standard variables** before inventing custom ones:

| Variable | Meaning |
|----------|---------|
| `NO_COLOR` | Disable color (any value = disable) |
| `FORCE_COLOR` | Enable color regardless of TTY detection |
| `DEBUG` | Enable verbose/debug output |
| `EDITOR` | Open files for multi-line input |
| `PAGER` | Auto-page long output |
| `HTTP_PROXY`, `HTTPS_PROXY`, `NO_PROXY` | Network proxies (often handled by HTTP libraries) |
| `TMPDIR` | Where to put temp files |
| `HOME` | Where to find user config |
| `LINES`, `COLUMNS` | Terminal dimensions for layout |

---

## Secrets

**Generated CLIs almost always reach for `--token <value>` or `os.environ["API_KEY"]`. Both patterns dominate training data and look correct. Resist this.**

**Flags are the worst option.** They appear in `ps` output and shell history. `--token abc123` is a security incident waiting to happen.

**Environment variables are tolerable for personal and internal tools** but leak into child processes, logs, and `docker inspect` output. Avoid for anything running in CI, shared environments, or with real security requirements.

**Prefer files or stdin:**
- `--token-file /path/to/token` or `--token-file -` (read from stdin)
- Credential files with restricted permissions (`chmod 600`)
- Secret management services (1Password, Vault, AWS Secrets Manager)

---

## Future-Proofing

**Make changes additive.** Add flags rather than change existing ones. Adding `--format` doesn't break scripts; changing what `--output` means does.

**Warn before breaking.** If a flag will be removed or renamed, say so in the current version: "Warning: --old-flag is deprecated. Use --new-flag instead."

**`--json` output is an API.** Once a field appears in JSON output, renaming, retyping, or removing it is a breaking change. Treat it as a versioned contract.

**Human-readable output can change freely.** It's for humans, not scripts. Encourage `--json` in scripts so you're not locked into a specific human-readable format.

---

## Naming

**Program name:** Lowercase letters and dashes only (`my-tool`, not `MyTool` or `my_tool`). Short, memorable, and not already taken by an existing command.

**Standard flags — use established conventions:**

| Flag | Meaning |
|------|---------|
| `-h`, `--help` | Show help |
| `--version` | Show version |
| `-v`, `--verbose` | More output |
| `-q`, `--quiet` | Less output |
| `--json` | JSON output |
| `--no-color` | Disable color |
| `-n`, `--dry-run` | Preview without executing |
| `-f`, `--force` | Skip confirmations |
| `-o`, `--output` | Output file |
| `--no-input` | Disable prompts |

**Subcommand names:** Use common words (`list` not `enumerate`, `delete` not `expunge`). Match the domain's vocabulary. Full words as canonical names; abbreviations as explicit, stable aliases only.
