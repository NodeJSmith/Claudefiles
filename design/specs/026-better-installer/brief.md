# Brief: Better Installer

**Date:** 2026-06-02
**Status:** explored

## Idea

Rebuild the Claudefiles installer as a proper package with a Textual TUI, cyclopts CLI framework, external override awareness, and granular per-file rule selection. The current installer works but feels utilitarian — questionary checkboxes are ugly, rule selection is all-or-nothing per category, and there's no way to layer personal configs (like Dotfiles) on top without the installer treating them as conflicts.

## Key Decisions Made

- **Textual replaces questionary** for all interactive prompts. Full-screen TUI with tree views, nested checkboxes, mouse support. Rich stays (Textual depends on it).
- **cyclopts replaces argparse** for CLI parsing. Brings built-in shell completions (bash/zsh/fish) and room to grow subcommands.
- **Override detection shows the owning repo/path.** When a non-Claudefiles symlink already exists at a target location, resolve its target and group by source repo. End-of-install summary: "3 skills overridden by ~/Dotfiles, 1 by ~/other-repo" with per-item detail available.
- **Nested rule selection in the wizard.** Rule categories are top-level checkboxes in a tree view; expanding a category shows its individual files as sub-items. Users can deselect specific rules within a category. The dangling cross-reference warning still fires.
- **Package structure under `packages/claudefiles-installer/`.** Thin `install.py` shim at repo root forwards to the package via `uv run --directory`. Entry point registered in pyproject.toml.
- **Single file splits into modules** — rough split: cli.py (cyclopts app, flags, completions), tui.py (Textual screens), symlinks.py (link creation, ownership, stale detection), config.py (persistence, migration), installer.py (orchestration logic).

## Open Questions

- **Non-interactive mode:** The current installer handles `--reconfigure` in non-interactive mode (no TTY). Textual requires a terminal. Cyclopts can handle the flag parsing, but the TUI can't run. Keep the current fallback (install everything / apply saved config) or add a `--yes` flag that skips the TUI entirely?
- **Config schema:** Does granular per-file rule selection need a config version bump (v2 → v3)? Currently `rule_categories` stores `{category_key: bool}`. Per-file needs something like `{category_key: true | list[str]}` where `true` means all files and a list means specific files. Might be backward-compatible if `true` is the default.
- **Install progress:** Should the install phase (symlinking, package installation) render inside the Textual TUI as a live progress view, or should the TUI exit after selection and the install phase print rich output to the normal terminal?
- **Shim mechanism:** Does `install.py` shell out to `uv run --directory packages/claudefiles-installer claudefiles-install ...`, or does it add the package to `sys.path` and import directly? Subprocess is cleaner but adds a uv invocation.

## Scope Boundaries

**In scope:**
- Textual TUI for bundle + rule selection (with nested tree for rules)
- cyclopts CLI with shell completion generation
- Override detection with source-path resolution and grouped summary
- Package structure under `packages/claudefiles-installer/`
- Shim `install.py` at repo root
- Config migration from v2 to v3 (if needed for per-file rules)
- Existing test suite ported to new structure

**Explicitly out:**
- No new bundles or rule categories (just the selection mechanism changes)
- No changes to what gets symlinked or how (symlink logic stays the same)
- No auto-detection of Dotfiles repo or other override sources (just resolve what's there)
- No plugin/extension system for third-party skill repos

**Deferred:**
- Subcommands beyond install/uninstall/reconfigure (e.g., `status`, `list`, `diff`)
- Remote skill installation (installing skills from GitHub URLs)
- Lock file for reproducible installs

## Risks and Concerns

- **Textual full-screen takeover** changes the feel from "quick CLI" to "TUI app." If the installer is run frequently (safe to re-run), the full-screen mode might feel heavy for a no-changes-detected pass. Mitigation: fast-path that skips the TUI when config is current and no new items detected.
- **Test surface grows.** The current test suite tests config, ownership, and symlink logic. Adding Textual means either testing the TUI (Textual has a test framework but it's involved) or keeping TUI thin enough that the logic layer is testable without it.
- **cyclopts is newer and less widely adopted than click/typer.** If it has rough edges, we're committed. Mitigation: the CLI layer is thin (a few flags), so switching frameworks later is cheap.
- **Config migration v2→v3** needs the same care as v1→v2: backup, summary panel, no data loss.

## Codebase Context

- **Current installer:** `install.py` at repo root, 1411 lines. Uses `questionary` (5 calls: 1 checkbox, 4 confirm) and `rich` (Console, Panel). Inline uv script deps.
- **Shadow detection already exists** (lines 489-545) — `is_owned_by()` checks if a symlink resolves within the repo. `shadowed_out` collects conflicts. The override feature reframes this from "conflict" to "intentional override" and adds source resolution.
- **Config system:** JSON at `~/.claude/.claudefiles-install-config.json`, version-stamped, with atomic writes and flock. Migration from v1→v2 already implemented.
- **Test suite:** `tests/test_install.py` covers config, ownership, symlink, migration, and rule cross-reference logic. CI runs via GitHub Actions.
- **Dotfiles overlay pattern:** `~/Dotfiles/config/claude/` has rules/personal/, settings.json, commands, and learned files that are already symlinked into `~/.claude/` independently. The installer's shadow detection encounters these today.
- **Existing packages:** `packages/` contains `merge-settings`, `claude-memory`, `spec-helper`, `ado-api` — all installed via `uv tool install -e`. The installer package follows the same pattern.
