---
proposal: "Configure Claude Code's pyright-lsp plugin globally to suppress diagnostics while keeping LSP navigation features"
date: 2026-04-01
status: Draft
flexibility: Exploring
motivation: "The prior research brief identified an open question: can the .lsp.json settings/initializationOptions fields pass diagnosticSeverityOverrides to pyright-langserver to suppress noisy diagnostics without disabling the plugin entirely?"
constraints: "Must apply globally (not per-project). Must preserve goToDefinition, findReferences, hover, documentSymbol navigation. Must not require forking or maintaining custom plugin code."
non-goals: "Not trying to fix the upstream issue (anthropics/claude-code#26634). Not trying to change pyright strictness for manual CLI runs."
depth: normal
---

# Research Brief: Global pyright-lsp Plugin Configuration for Diagnostic Suppression

**Initiated by**: Follow-up to open question #2 in `2026-04-01-lsp-diagnostics-noise.md` -- can `.lsp.json` `settings` or `initializationOptions` fields suppress diagnostics globally?

## Context

### What prompted this

The prior research brief identified four options for dealing with noisy LSP diagnostics. Option B (pyrightconfig.json) had uncertain effectiveness and required per-project files. The open questions specifically asked:

> Can the LSP plugin's `settings` or `initializationOptions` fields in `.lsp.json` pass `diagnosticSeverityOverrides` to pyright-langserver, bypassing pyrightconfig.json?

This research answers that question definitively.

### How Claude Code's pyright-lsp plugin is configured

The plugin has a surprisingly thin on-disk presence. Here is the complete picture:

**Marketplace definition** (`~/.claude/plugins/marketplaces/claude-plugins-official/.claude-plugin/marketplace.json`, line 983):
```json
{
  "name": "pyright-lsp",
  "description": "Python language server (Pyright) for type checking and code intelligence",
  "version": "1.0.0",
  "source": "./plugins/pyright-lsp",
  "category": "development",
  "strict": false,
  "lspServers": {
    "pyright": {
      "command": "pyright-langserver",
      "args": ["--stdio"],
      "extensionToLanguage": {
        ".py": "python",
        ".pyi": "python"
      }
    }
  }
}
```

**Plugin directory** (`~/.claude/plugins/marketplaces/claude-plugins-official/plugins/pyright-lsp/`):
- `README.md` -- installation instructions only
- `LICENSE` -- Apache 2.0
- No `.lsp.json` file
- No `.claude-plugin/plugin.json` file
- No `settings.json` file

**Installed cache** (`~/.claude/plugins/cache/claude-plugins-official/pyright-lsp/1.0.0/`):
- `README.md` -- that is literally the only file

**Key finding**: The pyright-lsp plugin has **no `.lsp.json` file at all**. The LSP server configuration comes entirely from the `lspServers` field in `marketplace.json`. The plugin directory is just a README and a license. There are no `settings`, `initializationOptions`, or any other configuration fields set.

### The .lsp.json schema

From the [official plugins reference](https://code.claude.com/docs/en/plugins-reference), the `.lsp.json` format supports these optional fields:

| Field | Description |
|-------|-------------|
| `initializationOptions` | Options passed to the server during initialization |
| `settings` | Settings passed via `workspace/didChangeConfiguration` |
| `startupTimeout` | Max time to wait for server startup (ms) |
| `shutdownTimeout` | Max time to wait for graceful shutdown (ms) |
| `restartOnCrash` | Whether to auto-restart on crash |
| `maxRestarts` | Maximum restart attempts |

Both `initializationOptions` and `settings` accept arbitrary JSON objects -- their contents are language-server-specific.

### How pyright-langserver consumes settings

From [Pyright's own documentation](https://github.com/microsoft/pyright/blob/main/docs/settings.md) and the Neovim/LSP community:

- **`settings`** (via `workspace/didChangeConfiguration`): Pyright expects settings under the key `python.analysis`, including `python.analysis.diagnosticSeverityOverrides`. This is the standard way editors like VS Code and Neovim configure pyright.
- **`initializationOptions`**: Pyright also accepts initialization options but the documentation focuses on `settings` as the primary configuration path.
- **`diagnosticSeverityOverrides`**: A map of rule names to severity levels (`"none"`, `"information"`, `"warning"`, `"error"`). Setting a rule to `"none"` suppresses it entirely.

The Piebald-AI/claude-code-lsps alternative marketplace shows a pyright `.lsp.json` with empty `initializationOptions: {}` and `settings: {}` -- confirming these fields are recognized but unused by default.

## Feasibility Analysis

### Can we create a custom .lsp.json with settings?

**Yes, in theory. The schema supports it.** A `.lsp.json` with diagnostic suppression would look like:

```json
{
  "python": {
    "command": "pyright-langserver",
    "args": ["--stdio"],
    "extensionToLanguage": {
      ".py": "python",
      ".pyi": "python"
    },
    "settings": {
      "python": {
        "analysis": {
          "diagnosticSeverityOverrides": {
            "reportUnusedImport": "none",
            "reportUnusedVariable": "none",
            "reportUnusedExpression": "none",
            "reportUnusedClass": "none",
            "reportUnusedFunction": "none",
            "reportMissingImports": "none",
            "reportMissingModuleSource": "none",
            "reportGeneralTypeIssues": "none"
          }
        }
      }
    }
  }
}
```

### Three paths to deploy this

#### Path 1: Modify the marketplace's pyright-lsp plugin in-place

Edit the `lspServers` entry in `~/.claude/plugins/marketplaces/claude-plugins-official/.claude-plugin/marketplace.json` to add `settings`. Or add a `.lsp.json` file directly to `~/.claude/plugins/marketplaces/claude-plugins-official/plugins/pyright-lsp/`.

**Problem**: Marketplace plugins are fetched from a remote git repo and cached locally. Plugin updates (`claude plugin update`) would overwrite local edits. The marketplace directory is managed by Claude Code, not by the user.

**Verdict**: Fragile. Not suitable for a persistent global config.

#### Path 2: Create a standalone local plugin with `claude --plugin-dir`

Create a custom plugin directory (e.g., `~/.claude/custom-plugins/pyright-quiet/`) containing:
- `.claude-plugin/plugin.json` with `{"name": "pyright-quiet"}`
- `.lsp.json` with the settings-enriched pyright config

Then launch Claude Code with `claude --plugin-dir ~/.claude/custom-plugins/pyright-quiet/`.

**Problem**: `--plugin-dir` only applies to that session. There is no persistent equivalent in `settings.json`. You would need to alias `claude` or use a wrapper script.

**Verdict**: Workable but clunky. Requires a shell alias or wrapper.

#### Path 3: Disable the official plugin, create a replacement local plugin

1. `claude plugin disable pyright-lsp@claude-plugins-official`
2. Create `~/.claude/custom-plugins/pyright-quiet/` with `.lsp.json` including settings
3. Install the local plugin: `claude plugin install --plugin-dir ~/.claude/custom-plugins/pyright-quiet/ --scope user`

**Problem**: `claude plugin install` works with marketplace names, not local directories. There is no documented way to install a local directory as a persistent plugin without a marketplace. The `--plugin-dir` flag is session-scoped only.

**Verdict**: Not supported by the current plugin system.

### The blocking gap

**There is no way to persistently override LSP server settings for a marketplace plugin.** The configuration comes from `marketplace.json` and is not user-editable in a way that survives updates. The plugin system does not support:

1. User-level `.lsp.json` overrides (there is no `~/.claude/lsp.json` or similar)
2. Per-project `.lsp.json` that merges with plugin config
3. `pluginConfigs` in `settings.json` for LSP settings (only `userConfig` values declared by the plugin, and pyright-lsp declares none)
4. Persistent local plugins without a marketplace

### What about pyrightconfig.json?

Pyright-langserver does read `pyrightconfig.json` from the workspace root. But this is per-project, not global. And as noted in the prior brief, the `DiagnosticTag.Unnecessary` hints may be emitted on a separate code path from `diagnosticSeverityOverrides`.

### What about `settings.json` env vars?

Claude Code settings support `env` for environment variables. Pyright-langserver does not consume diagnostic configuration from environment variables.

## Options Evaluated

### Option A: Shell alias to inject `--plugin-dir` globally

**How it works**: Create a custom plugin at `~/.claude/custom-plugins/pyright-quiet/` with a `.lsp.json` that includes diagnostic suppression settings. Add a shell alias:

```bash
alias claude='claude --plugin-dir ~/.claude/custom-plugins/pyright-quiet/'
```

Disable the official plugin to avoid a duplicate LSP server:
```bash
claude plugin disable pyright-lsp@claude-plugins-official
```

**Pros**:
- Full control over pyright-langserver settings
- Global -- applies to every session
- Preserves LSP navigation
- Clean separation: official plugin disabled, custom plugin loaded via alias

**Cons**:
- Fragile: the alias must be present in every shell profile (bash, zsh, tmux)
- `--plugin-dir` may conflict with other flags or future Claude Code changes
- Cannot combine multiple `--plugin-dir` flags if other custom plugins are needed
- Unclear if `--plugin-dir` plugins can coexist with marketplace plugins

**Effort estimate**: Small -- a few files and a shell alias.

**Dependencies**: None new.

### Option B: Create a personal plugin marketplace

**How it works**: Create a git repository (local or on GitHub) that acts as a private plugin marketplace. It contains a single plugin: a pyright-lsp replacement with the desired `.lsp.json` settings. Register the marketplace:

```bash
claude plugin marketplace add file:///path/to/my-marketplace
# or
claude plugin marketplace add https://github.com/user/my-claude-plugins
```

Install the custom pyright plugin from it:
```bash
claude plugin disable pyright-lsp@claude-plugins-official
claude plugin install pyright-quiet@my-marketplace --scope user
```

**Pros**:
- Persistent, survives Claude Code updates
- Proper plugin lifecycle (install, update, uninstall)
- Can host multiple custom plugins
- Settings are version-controlled
- The user already has a personal config repo (Claudefiles) that could serve as the marketplace

**Cons**:
- Requires understanding the marketplace schema (`marketplace.json`)
- Maintenance burden: when pyright-lsp gets an upstream fix, need to update or retire the custom plugin
- More infrastructure than the problem warrants

**Effort estimate**: Medium -- set up marketplace repo, create plugin, register it.

**Dependencies**: Git repository (local or remote).

### Option C: Global pyrightconfig.json + CLAUDE.md instruction (compromise)

**How it works**: Place a `pyrightconfig.json` at `~/pyrightconfig.json` (or a common parent directory). Pyright walks up the directory tree looking for config files, so this would apply to any project under `~/`. Combine with a CLAUDE.md instruction to ignore remaining noise.

```json
{
  "reportUnusedImport": "none",
  "reportUnusedVariable": "none",
  "reportUnusedExpression": "none",
  "reportMissingImports": "warning",
  "reportMissingModuleSource": "none"
}
```

**Pros**:
- Simple -- one file, no plugin changes
- Preserves LSP navigation fully
- Standard pyright configuration
- Also affects manual `pyright` runs (could be pro or con)

**Cons**:
- **Uncertain effectiveness for LSP hints**: `DiagnosticTag.Unnecessary` may still be emitted even with rules set to `"none"` (this is the pyright-specific behavior noted in microsoft/pyright#2307)
- Also suppresses these rules for manual `pyright` CLI runs (may mask real issues)
- Pyright only walks up from the workspace root, so if Claude Code sets the workspace to the project dir, `~/pyrightconfig.json` may not be found
- Does not address staleness

**Effort estimate**: Small -- one config file.

**Dependencies**: None.

### Option D: Wait for upstream fix + disable plugin now

**How it works**: Disable the plugin today. Monitor [anthropics/claude-code#26634](https://github.com/anthropics/claude-code/issues/26634) for a fix that adds severity-based filtering or a configurable minimum threshold. Re-enable when fixed.

**Pros**:
- Zero maintenance
- No workarounds that might interfere with the eventual fix
- The codebase (Claudefiles) is a config repo where LSP navigation adds marginal value

**Cons**:
- Loses LSP navigation for Python files
- No timeline for the upstream fix (issue open since Feb 2026, labeled "stale")
- If working on Python-heavy projects, the loss of navigation is more painful

**Effort estimate**: Small -- one command.

**Dependencies**: None.

## Concerns

### Technical risks

- **`settings` field propagation is untested**: No one in the Claude Code community has documented passing `diagnosticSeverityOverrides` via `.lsp.json` `settings`. The field exists in the schema but its interaction with pyright-langserver is unverified. It may be passed correctly, or Claude Code may not send `workspace/didChangeConfiguration` at all.
- **Duplicate LSP server registration**: If both the official plugin and a custom plugin try to register a pyright server for `.py` files, behavior is undefined. The official plugin must be disabled first.
- **Marketplace plugin update race**: If the official pyright-lsp plugin is updated to include settings, and the user has a custom replacement, the configurations could conflict when re-enabling the official plugin.

### Complexity risks

- Options A and B add infrastructure (aliases, marketplaces) for what is fundamentally a workaround for a bug. The complexity may not be justified for a config repo where Python files are scripts and package code, not a large application.

### Maintenance risks

- Any workaround creates something to maintain and eventually remove. The simpler the workaround, the easier the cleanup.
- A personal marketplace (Option B) is the most maintainable long-term but the most setup up front.

## Open Questions

- [ ] Does Claude Code actually send `workspace/didChangeConfiguration` with the `settings` from `.lsp.json`? This is the critical technical question. If it does, Options A and B become viable. If it does not, only Option C (pyrightconfig.json) can influence pyright behavior.
- [ ] Can `--plugin-dir` be combined with marketplace plugins, or does it replace them?
- [ ] Does pyright-langserver respect `diagnosticSeverityOverrides` passed via `initializationOptions` (as opposed to `settings`)? Some LSP servers prefer one over the other.
- [ ] What is the `workspaceFolder` that Claude Code passes to pyright-langserver? If it is the project root, then a `pyrightconfig.json` in that root will be found; if it is something else, the config may not be discovered.

## Recommendation

**The plugin system does not currently support persistent global LSP settings overrides.** None of the paths for deploying a custom `.lsp.json` with `settings` are clean:

- `--plugin-dir` is session-scoped only
- Marketplace plugin files are managed/overwritten by updates
- There is no user-level LSP config file
- `pluginConfigs` in `settings.json` only handles declared `userConfig` values

**For this codebase (Claudefiles)**, the right answer remains **Option D: disable the plugin now, re-enable when upstream fixes it**. The LSP navigation benefit is marginal for a config repo.

**For Python-heavy projects**, the most promising path is **Option C (pyrightconfig.json)** as a quick test: create one in the project root with aggressive suppression and check if `<new-diagnostics>` injections actually stop. If they do, it solves the problem per-project with minimal infrastructure.

**If pyrightconfig.json does not work** (because `DiagnosticTag.Unnecessary` is a separate code path), then **Option B (personal marketplace)** is the cleanest long-term solution, but it requires verifying that Claude Code actually sends `settings` from `.lsp.json` to the language server -- which is the critical untested assumption.

### Suggested next steps

1. **Immediate**: Disable pyright-lsp plugin for Claudefiles (already recommended by prior brief)
2. **Quick experiment**: In a Python project, create `pyrightconfig.json` with `reportUnusedVariable: "none"` and observe whether `<new-diagnostics>` injections for unused variables stop
3. **If pyrightconfig.json works**: Use it per-project; no plugin changes needed
4. **If pyrightconfig.json does not work**: Test a custom `.lsp.json` with `settings` via `claude --plugin-dir` to verify Claude Code sends `workspace/didChangeConfiguration`
5. **Long-term**: If custom settings work, consider creating a personal marketplace in Claudefiles (the repo already has plugin/config infrastructure)
6. **Watch**: [anthropics/claude-code#26634](https://github.com/anthropics/claude-code/issues/26634) for upstream fix

## Sources

- [Claude Code Plugins Reference](https://code.claude.com/docs/en/plugins-reference) -- authoritative `.lsp.json` schema
- [pyright-lsp promotes hint-level DiagnosticTag.Unnecessary (Issue #26634)](https://github.com/anthropics/claude-code/issues/26634)
- [lspServers config from marketplace.json not propagated (Issue #16219)](https://github.com/anthropics/claude-code/issues/16219)
- [Pyright Language Server Settings](https://github.com/microsoft/pyright/blob/main/docs/settings.md)
- [diagnosticSeverityOverrides has no effect (Neovim discourse)](https://neovim.discourse.group/t/the-diagnosticseverityoverrides-setting-of-pyright-has-no-effect/2287)
- [Piebald-AI/claude-code-lsps alternative marketplace](https://github.com/Piebald-AI/claude-code-lsps) -- shows `.lsp.json` with empty `settings` and `initializationOptions`
- [anthropics/claude-plugins-official marketplace.json](https://github.com/anthropics/claude-plugins-official/blob/main/.claude-plugin/marketplace.json) -- official pyright-lsp definition
