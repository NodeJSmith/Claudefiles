---
proposal: "Suppress or filter stale/noisy LSP diagnostics in Claude Code to prevent wasted context tokens and misguided fixes"
date: 2026-04-01
status: Draft
flexibility: Exploring
motivation: "Pyright LSP diagnostics injected via <new-diagnostics> are frequently stale or wrong (unused symbol false positives, import resolution failures from missing virtualenv). They waste context tokens and cause Claude to attempt unnecessary fixes."
constraints: "Must not lose the ability to run pyright manually for real type checking. LSP navigation (goToDefinition, findReferences, hover) should remain functional."
non-goals: "Not trying to fix pyright itself or change type checking strictness for manual runs."
depth: normal
---

# Research Brief: Suppressing Stale LSP Diagnostics in Claude Code

**Initiated by**: User frustration with `<new-diagnostics>` injections from pyright-lsp that contain false positives (e.g., "not accessed" for symbols that ARE used, import resolution failures because pyright doesn't see the virtualenv), wasting context and prompting unnecessary "fixes."

## Context

### What prompted this

After every file edit, the pyright-lsp plugin pushes diagnostics into the conversation via `<new-diagnostics>` system injections. These diagnostics are frequently:

1. **Stale** -- they reflect the file state before the edit settles, not after
2. **False positives** -- hint-level `DiagnosticTag.Unnecessary` markers that pyright CLI would not report (e.g., `_`-prefixed variables flagged as unused)
3. **Environment-blind** -- import resolution failures because pyright's LSP server doesn't see the project's virtualenv

The user already has a `lsp-settle.sh` PostToolUse hook (sleeping 1s after Edit/Write on LSP-managed files) to mitigate staleness, but the core problem -- noisy diagnostics being injected into conversation context -- remains.

### Current state

**Installed plugins** (from `claude plugin list`):
- `pyright-lsp@claude-plugins-official` v1.0.0 -- **enabled**
- `typescript-lsp@claude-plugins-official` v1.0.0 -- **enabled**
- `playwright@claude-plugins-official` -- **enabled**

**Existing hooks** in `~/.claude/settings.json`:
- `PreToolUse` matcher `LSP` -> `lsp-pre-read.sh` (logging only)
- `PostToolUse` matcher `Edit|Write` -> `lsp-settle.sh` (1s sleep for LSP-managed file types)

**LSP tool usage**: The user's LSP rules (since removed) instructs Claude to use LSP for symbol navigation (goToDefinition, findReferences, hover, documentSymbol, incomingCalls, outgoingCalls). These navigation features are valuable and should be preserved.

**Manual pyright**: `Bash(pyright:*)` and `Bash(uv run pyright:*)` are pre-allowed in settings. The user wants to rely on these for real type checking, not the ambient LSP diagnostics.

### Key constraints

- LSP navigation features (goToDefinition, findReferences, hover) must continue working
- Manual `pyright` / `uv run pyright` runs must remain the source of truth for type errors
- No changes to pyright strictness for manual runs

## Feasibility Analysis

### The root cause

This is a known, acknowledged bug: [anthropics/claude-code#26634](https://github.com/anthropics/claude-code/issues/26634). The pyright-lsp plugin treats hint-level diagnostics (`severity=4`, `DiagnosticTag.Unnecessary`) identically to standard error/warning diagnostics, promoting them into `<new-diagnostics>` conversation injections. An Anthropic engineer confirmed: "I fully agree, it's annoying to use the language server while also getting these stale diagnostics constantly."

**No fix has been deployed** as of March 30, 2026. The issue is open and labeled "stale" despite community activity.

### What would need to change

| Area | Change | Effort | Risk |
|------|--------|--------|------|
| Plugin config | Disable pyright-lsp plugin | None | Loses LSP navigation |
| pyrightconfig.json | Suppress specific diagnostic rules | Low | May not affect LSP hint tags |
| Custom LSP plugin | Fork pyright-lsp with diagnostic filtering | Medium | Maintenance burden |
| CLAUDE.md instruction | Tell Claude to ignore `<new-diagnostics>` | None | Unreliable -- model may still react |
| Hook-based filtering | PostToolUse hook to intercept/nullify diagnostics | Low-Med | Diagnostics arrive via system injection, not tool output |

### What already supports this

- The user already has hook infrastructure for LSP lifecycle management (`lsp-settle.sh`, `lsp-pre-read.sh`)
- `pyright` CLI is pre-allowed and works correctly as the ground truth
- Claude Code's plugin system supports `claude plugin disable` for clean toggling
- The `.lsp.json` schema supports `settings` and `initializationOptions` fields that could pass pyright configuration

### What works against this

- **No granular diagnostic filtering in Claude Code**: There is no setting to say "use LSP for navigation but suppress diagnostics." It's all or nothing at the plugin level.
- **`<new-diagnostics>` is a system injection**: It arrives as a system message in the conversation, not as tool output that a hook could intercept. PostToolUse hooks fire after Edit/Write but cannot prevent the diagnostic injection that follows.
- **pyrightconfig.json vs LSP behavior**: Even with `diagnosticSeverityOverrides` set to suppress specific rules, pyright's LSP server may still emit hint-level `DiagnosticTag.Unnecessary` tags -- these are a separate code path from the diagnostic severity system ([microsoft/pyright#2307](https://github.com/microsoft/pyright/issues/2307)).

## Options Evaluated

### Option A: Disable pyright-lsp plugin + rely on manual pyright

**How it works**: Run `claude plugin disable pyright-lsp@claude-plugins-official`. This stops the pyright LSP server entirely. No more `<new-diagnostics>` injections. Claude uses `pyright` CLI (already pre-allowed) when type checking is needed, and falls back to Grep for symbol navigation instead of LSP goToDefinition/findReferences.

**Pros**:
- Eliminates all false-positive diagnostic noise immediately
- Zero maintenance -- no custom config, no forks, no hooks to manage
- The user's LSP rules (since removed) already documents Grep as a fallback for non-LSP cases
- Manual `pyright` runs give accurate, environment-aware results
- Can be re-enabled trivially if Claude Code fixes the upstream issue

**Cons**:
- Loses LSP navigation for Python files (goToDefinition, findReferences, hover, documentSymbol, incomingCalls, outgoingCalls)
- Grep-based navigation is slower and less precise for symbol lookups
- TypeScript LSP would still be active (which may or may not have the same noise problem)

**Effort estimate**: Small -- one command to disable.

**Dependencies**: None.

### Option B: Add pyrightconfig.json to suppress noisy rules + keep plugin enabled

**How it works**: Create a `pyrightconfig.json` at the project root (or use `pyproject.toml` `[tool.pyright]` section) with `diagnosticSeverityOverrides` to suppress the noisiest rules:

```json
{
  "reportUnusedImport": "none",
  "reportUnusedVariable": "none",
  "reportUnusedExpression": "none",
  "reportMissingImports": "warning"
}
```

This tells pyright to suppress hint-level diagnostics for unused symbols. LSP navigation continues working.

**Pros**:
- Preserves LSP navigation (goToDefinition, findReferences, hover, etc.)
- Reduces diagnostic noise without disabling the plugin
- Standard pyright configuration -- well-documented, widely used
- Per-project: different projects can have different strictness

**Cons**:
- **May not fully work**: Pyright's LSP `DiagnosticTag.Unnecessary` hints are a separate code path from `diagnosticSeverityOverrides` ([microsoft/pyright#2307](https://github.com/microsoft/pyright/issues/2307)). Setting `reportUnusedVariable: "none"` suppresses the diagnostic message but pyright may still emit the `Unnecessary` tag, which Claude Code's plugin may still inject.
- Doesn't fix staleness -- diagnostics from the previous file state still arrive before the LSP re-analyzes
- Requires maintaining pyrightconfig.json per project
- Changes pyright behavior for manual runs too (unless the manual `pyright` invocation uses a separate config)

**Effort estimate**: Small -- create one config file per project.

**Dependencies**: None new.

### Option C: CLAUDE.md instruction to ignore `<new-diagnostics>` + keep plugin enabled

**How it works**: Add an instruction to CLAUDE.md (or a rule file) telling Claude to ignore LSP diagnostic injections and only trust manually-run `pyright`:

```markdown
## LSP Diagnostics Policy

Ignore all `<new-diagnostics>` system messages from LSP. These are frequently
stale or contain false positives. When you need to check for type errors, run
`pyright` or `uv run pyright` explicitly. Do not attempt fixes based solely on
LSP diagnostic output.
```

**Pros**:
- Zero infrastructure change -- just a prompt instruction
- Preserves LSP navigation fully
- Can be combined with any other option

**Cons**:
- **Unreliable**: System injections still consume context tokens even if Claude "ignores" them. The model may still react to them, especially under context pressure or after compaction.
- Doesn't reduce token waste -- the diagnostics are still injected into every turn after an edit
- Fighting the system rather than configuring it

**Effort estimate**: Small.

**Dependencies**: None.

## Concerns

### Technical risks
- **Option B's uncertain effectiveness**: The pyright LSP `Unnecessary` tag behavior is documented as separate from `diagnosticSeverityOverrides`. Testing is needed to confirm whether suppressing rules actually prevents Claude Code from seeing the hints.
- **TypeScript LSP may have the same problem**: [anthropics/claude-code#26634](https://github.com/anthropics/claude-code/issues/26634) reports similar false positives from the TypeScript LSP plugin. Disabling pyright-lsp only addresses half the problem if TypeScript projects are also affected.

### Complexity risks
- Options B and C add per-project configuration that needs to be maintained and may interact unpredictably with future Claude Code updates that fix the upstream issue.

### Maintenance risks
- The upstream issue (#26634) may be fixed in a future Claude Code release, making any workaround unnecessary. Options A and C are trivially reversible; Option B requires removing pyrightconfig.json entries.

## Open Questions

- [ ] Does setting `reportUnusedVariable: "none"` in pyrightconfig.json actually suppress the `DiagnosticTag.Unnecessary` hint that Claude Code's plugin injects? (Needs testing)
- [ ] Can the LSP plugin's `settings` or `initializationOptions` fields in `.lsp.json` pass `diagnosticSeverityOverrides` to pyright-langserver, bypassing pyrightconfig.json? (The plugins-reference docs list these as supported fields, but no one has documented pyright-specific values)
- [ ] Is the TypeScript LSP also producing noisy diagnostics in the user's workflow, or is this pyright-specific?
- [ ] Would a custom local plugin (forking pyright-lsp with a `settings` block that suppresses hints) work as a middle ground between A and B?

## Recommendation

**Start with Option A (disable pyright-lsp)**, possibly combined with Option C (CLAUDE.md instruction as a safety net). The LSP navigation features are valuable but not critical -- the user's existing `rules/common/lsp.md` already documents Grep as a fallback, and the codebase is a config repo (skills/rules/agents), not a large Python application where LSP navigation would be essential.

The diagnostic noise is actively harmful (wasting context tokens, causing regressions from false-positive "fixes"), while the navigation benefit is marginal for this particular codebase. The plugin can be re-enabled the day the upstream issue is fixed.

If the user works on other Python projects where LSP navigation is more valuable, **test Option B first** in that project: create a `pyrightconfig.json` with aggressive suppression and see if the `<new-diagnostics>` injections actually stop. If they do, that's the better long-term solution.

### Suggested next steps

1. Run `claude plugin disable pyright-lsp@claude-plugins-official` to eliminate diagnostic noise immediately
2. Add a CLAUDE.md note about the policy: ignore `<new-diagnostics>`, use manual `pyright` for real checks
3. Optionally, in a Python-heavy project, test whether `pyrightconfig.json` with `reportUnusedVariable: "none"` actually suppresses the LSP hint injections
4. Watch [anthropics/claude-code#26634](https://github.com/anthropics/claude-code/issues/26634) for an upstream fix; re-enable the plugin when it lands

## Sources

- [pyright-lsp promotes hint-level DiagnosticTag.Unnecessary into context (Issue #26634)](https://github.com/anthropics/claude-code/issues/26634)
- [Plugins reference - Claude Code Docs](https://code.claude.com/docs/en/plugins-reference)
- [Pyright configuration documentation](https://github.com/microsoft/pyright/blob/main/docs/configuration.md)
- [pyright-langserver reports unused variables even when suppressed by config (Issue #2307)](https://github.com/microsoft/pyright/issues/2307)
- [diagnosticSeverityOverrides ignored when pyrightconfig.json present (Issue #836)](https://github.com/microsoft/pyright/issues/836)
- [pyright-lsp plugin: lspServers config not propagated (Issue #16219)](https://github.com/anthropics/claude-code/issues/16219)
- [Claude Code Changelog](https://github.com/anthropics/claude-code/blob/main/CHANGELOG.md)
- [Piebald-AI/claude-code-lsps alternative marketplace](https://github.com/Piebald-AI/claude-code-lsps)
