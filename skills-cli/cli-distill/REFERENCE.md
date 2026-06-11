# CLI Distill — Reference

Detailed dimensions for simplifying CLI tool complexity. Referenced by SKILL.md.

---

## Flag Reduction

**Count your flags.** A command with more than 8-10 flags is asking users to read a manual before every invocation. Audit each flag: is it used in >10% of invocations? If not, it's a candidate for removal, a config file, or a subcommand.

**Merge related flags.** `--start-date`/`--end-date` → `--range "2024-01-01..2024-02-01"`; `--host`/`--port` → `--addr host:port`.

**Promote to config.** Flags that rarely change between invocations belong in a config file, env var, or profile: `--region us-east-1` on every call → `MYTOOL_REGION=us-east-1` or `region:` in `~/.mytool.yaml`.

**Remove dead flags** added for one-off debugging or edge cases nobody uses — grep usage and docs, then remove if safe.

**Boolean flag cleanup.** Consolidate multiple "skip safety" flags (`--no-verify --skip-checks --force --yes`) into one `--force`/`--yes` meaning "I know what I'm doing."

---

## Default Design

- **Zero-flag invocation should work** — `mytool deploy` does the right thing for the common case. Three required flags means the defaults are wrong.
- **Defaults safe, not timid** — the action the user most likely wants, with guardrails (`--dry-run` is not the default; destructive ops confirm).
- **Inference over configuration** — detect project type from the directory, output format from the file extension, default branch from git config rather than asking.

**Smart defaults with escape hatches.** Auto-detect, but let the user override:
```
# Infers format from extension, but allows override
mytool export data.csv              # → CSV
mytool export data.csv --format tsv # → TSV despite extension
```

---

## Cognitive Load

- **One way to do common things** — if `ls`, `list`, and `show --all` overlap, pick one and alias the rest.
- **Reduce required decisions** — every required flag is a blocking decision; minimize them.
- **Group complexity into subcommands** — `tool push --force` over `tool --sync --direction=push --remote=origin --branch=main --force`; the subcommand absorbs what would be flags.
- **Predictable behavior** — deterministic and documented, not dependent on subtle context (cwd, env vars).

---

## Pit of Success

**Easy to use correctly, hard to use incorrectly.** The most natural invocation should be the correct one.

**Typo resistance.** If common typos in flag values have dangerous meanings, add confirmation:
```
# "prod" vs "pro" — one letter from production
mytool deploy --env pro
Error: unknown environment "pro". Did you mean "prod"?
Environments: dev, staging, prod
```

**Mutual exclusion.** If two flags can't be used together, reject the combination at parse time with a clear message. Don't silently pick one.

**Boundary validation.** If `--timeout 0` means "infinite" but users type it meaning "immediate," that's a pit of failure. Either reject 0 or document the meaning clearly.

---

## Interface Compression

**Config files for stable settings.** Settings that persist across invocations: credentials, region, default output format. `mytool config set region us-east-1` or `~/.mytool.yaml`.

**Profiles for setting bundles.** `mytool --profile staging` instead of `--host staging.example.com --port 8443 --no-tls-verify --timeout 60`.

**Presets for common workflows.** `mytool init --preset minimal` instead of answering 12 interactive questions.

**Subcommand consolidation.** If three subcommands share 80% of their flags, consider whether they should be one subcommand with a mode flag or a shared option group.

---

## When NOT to Simplify

**Don't hide necessary complexity.** Some tools are complex because the domain is complex. A database migration tool needs `--dry-run`, `--rollback-on-error`, `--lock-timeout` — simplifying those away creates danger.

**Don't merge unrelated flags.** `--fast` that secretly sets three unrelated options is a convenience but also a debugging nightmare when one of those options causes problems.

**Don't remove flags that scripts depend on.** Check for usage in CI configs, Makefiles, and wrapper scripts before removing.

**Don't default away from safety.** If a flag exists for safety (`--dry-run`, `--confirm`), it should stay explicit even if it adds friction.

---

## Anti-Patterns

- **Flag creep** — every feature request becomes a new flag; eventually the tool has 40 flags and no coherent interface
- **Required optionals** — flags marked "optional" in help but the tool fails without them
- **Hidden dependencies** — `--output` only works with `--format json` but nothing says so until you try
- **Config sprawl** — settings in env vars AND config file AND flags with unclear precedence
- **Premature flexibility** — supporting 5 output formats when users only use 2
- **Convenience overload** — `--fast`, `--quick`, `--turbo` that all do slightly different combinations of other flags
- **The wizard trap** — an interactive mode that asks 15 questions when 3 would suffice with good defaults
