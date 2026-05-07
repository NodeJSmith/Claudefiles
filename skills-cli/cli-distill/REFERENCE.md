# CLI Distill — Reference

Detailed dimensions for simplifying CLI tool complexity. Referenced by SKILL.md.

---

## Flag Reduction

**Count your flags.** A command with more than 8-10 flags is asking users to read a manual before every invocation. Audit each flag: is it used in >10% of invocations? If not, it's a candidate for removal, a config file, or a subcommand.

**Merge related flags.** `--start-date` and `--end-date` can become `--range "2024-01-01..2024-02-01"`. `--host` and `--port` can become `--addr host:port`. Fewer flags, same capability.

**Promote to config.** Flags that rarely change between invocations belong in a config file, environment variable, or profile. `--region us-east-1` on every call → `MYTOOL_REGION=us-east-1` in the environment or `region: us-east-1` in `~/.mytool.yaml`.

**Remove dead flags.** Flags added for one-off debugging, backward compatibility, or edge cases that nobody uses. Grep usage, check if any docs reference them, and remove if safe.

**Boolean flag cleanup.** `--no-verify --skip-checks --force --yes` — if a tool has multiple "skip safety" flags, consolidate. `--force` (or `--yes`) should be one flag that means "I know what I'm doing."

---

## Default Design

**The zero-flag invocation should work.** `mytool deploy` should do the right thing for the common case. If the tool requires three flags before it does anything useful, the defaults are wrong.

**Defaults should be safe.** `--dry-run` should not be the default (users expect action), but destructive operations should confirm. The default should be the action the user most likely wants, with guardrails.

**Inference over configuration.** If the tool can figure out the right answer, don't make the user specify it. Detect the project type from the directory. Infer the output format from the file extension. Read the default branch from git config.

**Smart defaults with escape hatches.** Auto-detect, but let the user override:
```
# Infers format from extension, but allows override
mytool export data.csv              # → CSV
mytool export data.csv --format tsv # → TSV despite extension
```

---

## Cognitive Load

**One way to do common things.** If `tool ls`, `tool list`, and `tool show --all` all do the same thing, pick one and alias the rest. Don't document three paths to the same destination.

**Reduce required decisions.** Every flag is a decision. Every required flag is a blocking decision. Minimize the number of things users must decide before the tool runs.

**Group complexity into subcommands.** Instead of `tool --sync --direction=push --remote=origin --branch=main --force`, offer `tool push --force`. The subcommand absorbs the context that would otherwise be flags.

**Predictable behavior.** A tool that does different things depending on subtle context (working directory, env vars, time of day) feels complex even if it has few flags. Make behavior deterministic and documented.

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
