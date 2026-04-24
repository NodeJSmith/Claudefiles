# Design: Interactive Python Installer

**Date:** 2026-04-23
**Status:** approved
**Research:** /tmp/claude-mine-define-research-ZoY1Vx/brief.md

## Problem

New users cloning Claudefiles get everything installed with zero choice — all 48 skills, 16 agents, 7 hooks, and 4 packages. The 19 Impeccable frontend design skills are irrelevant for backend-only workflows and consume context window budget unnecessarily. The current shell-based installer has no selection mechanism, doesn't install packages, and is difficult to extend. There is no persistent record of what the user chose, so every re-run is a full reinstall with no way to skip groups.

## Goals

- Users can select which asset groups to install during a guided first-run wizard
- Choices persist so re-runs are silent unless new items appear in the repo
- The Impeccable frontend design skills are physically separated in the repo structure, making the grouping visible without running the installer
- All installable packages (`uv tool install -e`) are handled by the installer, not documented as manual steps
- The installer works non-interactively when stdin is not a TTY (uses saved config or defaults to all)

## Non-Goals

- Machine-awareness (no WHICH_COMP detection or hostname-based defaults)
- Backward compatibility with install.sh
- Modifying settings.json to add/remove hook entries dynamically (hook entries use self-guarding wrappers so missing scripts exit 0 instead of blocking tool use)
- Managing symlinks created by Dotfiles (the installer only owns Claudefiles-sourced symlinks)

## User Scenarios

### New User: First-time adopter

- **Goal:** Set up Claudefiles with only the skills relevant to their workflow
- **Context:** Just cloned the repo, running `uv run install.py` for the first time

#### First-run wizard

1. **Runs `uv run install.py`**
   - Sees: Welcome banner explaining what Claudefiles is and what the installer does
   - Decides: Nothing yet — reads the overview
   - Then: Installer detects no config file and enters wizard mode

2. **Selects skill groups**
   - Sees: Three checkbox groups with descriptions and item counts:
     - Core skills (mine.*) — 27 skills — workflow automation, code review, planning
     - Impeccable frontend design (i-*) — 19 skills — UI design, responsive layout, accessibility
     - Claude Memory (cm-*) — 3 skills — conversation memory, learnings extraction
   - Decides: Which groups are relevant (all selected by default)
   - Then: Moves to next selection step

3. **Selects agent groups**
   - Sees: Three checkbox groups:
     - Core development — architect, code-reviewer, integration-reviewer, planner, researcher, etc.
     - Engineering specialists — backend, frontend, data, SRE, technical writer
     - Claude Memory — cm-memory-auditor, cm-signal-discoverer
   - Decides: Which agent groups to install
   - Then: Moves to next selection step

4. **Selects hook groups**
   - Sees: Three checkbox groups with descriptions:
     - Pytest safety — prevents orphaned pytest processes and retry loops (6 files: 5 hooks + 1 sourced library)
     - Sudo handling — transparent sudo authentication polling (1 script)
     - Tmux — session naming reminders (1 script)
   - Decides: Which hook groups to install
   - Then: Moves to package selection

5. **Selects packages**
   - Sees: Four packages with descriptions and dependency notes:
     - ado-api — Azure DevOps CLI
     - claude-memory — conversation memory (auto-selected if cm-* skills or agents chosen)
     - merge-settings — three-layer settings merger
     - spec-helper — work package and spec directory management
   - Decides: Which packages to install (some pre-selected based on hook/skill dependencies)
   - Then: Installation begins

6. **Watches installation**
   - Sees: Progress output showing symlinks created, packages installed, any conflicts detected
   - Decides: If conflicts found (shadowed files), whether to replace them
   - Then: Config file saved (written before installation begins with user intent, updated after completion), installation complete

#### Re-run (no changes)

1. **Runs `uv run install.py`**
   - Sees: "Config loaded. No new items detected. Applying saved selections..."
   - Then: Symlinks refreshed silently per saved config, packages verified, done

#### Re-run (new items in repo)

1. **Runs `uv run install.py`**
   - Sees: "Found 1 new skill group and 1 new agent group not in your config"
   - Decides: Whether to install the new groups (prompted only for new groups)
   - Then: Config updated, symlinks created for new selections

### Returning User: Reconfiguring selections

- **Goal:** Change which groups are installed (e.g., add i-* skills for a frontend project)
- **Context:** Already has a config file from a previous run

#### Reconfigure flow

1. **Runs `uv run install.py --reconfigure`**
   - Sees: Full wizard with current selections pre-checked
   - Decides: Toggles groups on/off
   - Then: Deselected items have their symlinks removed, new selections linked, config updated

## Functional Requirements

1. The installer presents a guided wizard on first run with checkbox selection for skill groups, agent groups, hook groups, and packages
2. The installer saves user selections to a config file that persists across runs
3. On subsequent runs, the installer loads saved config and only prompts for groups not present in the config (smart diff operates at group level, not individual item level)
4. The installer creates symlinks from `~/.claude/` (or `$CLAUDE_HOME`) to repo asset directories, matching the current behavior
5. The installer runs `uv tool install -e` for each selected package
6. The installer detects and reports shadowed files (non-symlink blocking a symlink target) with interactive replacement prompt
7. The installer detects and reports stale symlinks (target no longer exists) with interactive removal prompt
8. When an asset group is deselected (via `--reconfigure`), the installer removes symlinks for items in that group — but only symlinks whose targets resolve to the Claudefiles repo directory
9. The installer falls back to non-interactive mode when stdin is not a TTY, using saved config if available or defaulting to all groups
10. Rules, learned files, bin scripts, and commands are always installed (no selection) using file-level symlinks for rules/learned and directory-level for bin/commands
11. Selecting cm-* skills or cm-* agents auto-selects the claude-memory package with a visible note
12. The installer accepts a `--reconfigure` flag that forces the full wizard regardless of existing config
13. The installer accepts a `--uninstall` flag that removes all Claudefiles-owned symlinks, runs `uv tool uninstall` for each previously-installed package (read from config), and removes the config file

## Edge Cases

1. **Config file corrupted or malformed** — installer warns and re-prompts with full wizard (treats as first run)
2. **Dotfiles symlinks in target directories** — installer must never remove symlinks whose targets resolve outside the Claudefiles repo. Ownership check: `Path(readlink(target)).is_relative_to(repo_dir)`
3. **Skill renamed in repo** — old name appears as stale symlink (removed), new name appears as new item (prompted). The smart diff compares against repo contents, not historical names
4. **Package install fails** — report the error, continue with remaining packages, exit with non-zero status
5. **No TTY and no saved config** — install everything (all groups selected) but do not save a config file, so the next interactive run still shows the wizard
6. **User runs old install.sh after switching to install.py** — not our problem (no backward compat), but install.sh could be replaced with a shim that prints "Use `uv run install.py` instead"
7. **`$CLAUDE_HOME` set to non-default location** — all paths use `$CLAUDE_HOME` with `~/.claude` fallback, matching current behavior

## Acceptance Criteria

1. A new user can clone the repo, run `uv run install.py`, and have a working setup with only their chosen skill groups installed
2. Re-running the installer with no repo changes produces no prompts and no output beyond a confirmation message
3. Adding a new skill group to the repo and re-running the installer prompts the user about the new group only (new items within an existing selected group are installed silently)
4. Running `--reconfigure` and deselecting a group removes that group's symlinks from `~/.claude/`
5. Deselecting a group does not affect symlinks created by Dotfiles or other sources
6. All four packages can be installed via the wizard without manual `uv tool install -e` commands
7. The installer works non-interactively (piped input or CI) using saved config or defaults

## Dependencies and Assumptions

- `uv` must be installed (the installer is invoked via `uv run install.py`)
- Python 3.10+ (declared via PEP 723 inline metadata)
- `rich>=13.0` and `questionary>=2.0` (declared as PEP 723 dependencies, auto-resolved by `uv`)
- The Dotfiles installer (`mklinks.py`) continues to manage its own symlinks independently
- Hook entries in `settings.json` are wrapped in self-guarding `bash -c '[ -x "$f" ] && exec "$f" || exit 0'` patterns, so missing hook scripts exit 0 (passthrough) instead of exit 127 (denial). This is a prerequisite change to settings.json that must land before the installer ships.
- Network access to PyPI is required on first run (uv downloads rich and questionary). If uv is not installed, the user sees a shell-level "command not found" error — document installation at https://docs.astral.sh/uv/getting-started/installation/ in the README
- The `skills-impeccable/` directory is created and i-* skills are moved there as a prerequisite (separate commit)

## Architecture

### Script structure

Single file `install.py` in the repo root with PEP 723 inline metadata:

```python
# /// script
# requires-python = ">=3.10"
# dependencies = [
#   "rich>=13.0",
#   "questionary>=2.0",
# ]
# ///
```

Invoked as `uv run install.py`. The `uv run --script` mechanism auto-installs dependencies into a cached venv.

### Directory layout (after i-* move)

```
Claudefiles/
├── install.py                    # New installer (replaces install.sh)
├── (config stored at ${CLAUDE_HOME}/.claudefiles-install-config.json)
├── skills/                       # Core skills (mine.*, always-available)
│   ├── mine.build/
│   ├── mine.challenge/
│   └── ...
├── skills-impeccable/            # Impeccable frontend design skills (i-*)
│   ├── i-adapt/
│   ├── i-animate/
│   └── ...
├── skills-memory/                # Claude Memory skills (cm-*)
│   ├── cm-extract-learnings/
│   ├── cm-get-token-insights/
│   └── cm-recall-conversations/
├── agents/                       # All agents (grouped in wizard, flat on disk)
├── commands/                     # All commands (always installed)
├── scripts/hooks/                # All hooks (grouped in wizard)
├── rules/common/                 # Rules (always installed, file-level symlinks)
├── bin/                          # CLI scripts (always installed)
├── packages/                     # Python packages for uv tool install -e
│   ├── ado-api/
│   ├── claude-memory/
│   ├── merge-settings/
│   └── spec-helper/
└── learned/                      # Learned files (always installed, file-level)
```

Note: `cm-*` skills also move to their own directory (`skills-memory/`) to make all three groups physically distinct. All three skill source directories symlink into the same `~/.claude/skills/` target — the runtime path is unchanged.

### Config file format

`${CLAUDE_HOME:-~/.claude}/.claudefiles-install-config.json` (stored with user runtime, not in the repo — avoids worktree divergence and gitignore pollution):

```json
{
  "version": 1,
  "skills": {
    "core": true,
    "impeccable": false,
    "memory": true
  },
  "agents": {
    "core": true,
    "engineering": true,
    "memory": true
  },
  "hooks": {
    "pytest": true,
    "sudo": true,
    "tmux": true
  },
  "packages": {
    "ado-api": false,
    "claude-memory": true,
    "merge-settings": true,
    "spec-helper": true
  }
}
```

The `version` field enables schema migration if the config format changes. Unknown keys are preserved (forward compat). Missing keys trigger prompts for those items only (smart diff).

### Asset group definitions

Defined as data structures in `install.py`:

```python
SKILL_GROUPS = {
    "core": SkillGroup(
        label="Core skills (mine.*)",
        description="Workflow automation, code review, planning, shipping",
        source_dir="skills",
        default=True,
    ),
    "impeccable": SkillGroup(
        label="Impeccable frontend design (i-*)",
        description="UI design, responsive layout, accessibility, animations",
        source_dir="skills-impeccable",
        default=True,
    ),
    "memory": SkillGroup(
        label="Claude Memory (cm-*)",
        description="Conversation memory, learnings extraction, token insights",
        source_dir="skills-memory",
        default=True,
    ),
}
```

Similar structures for hooks and packages. Hook groups map to specific filenames within `scripts/hooks/` (pytest-detect.sh is a sourced library dependency, not a hook entry point — included as an atomic member of the pytest group). Agent groups are determined by a `group:` field in each agent file's YAML frontmatter; the installer reads frontmatter to classify agents and warns about any agent file missing a group field.

### Symlink operations

The installer performs five categories of symlink operations, matching current behavior:

1. **Directory-level symlinks** (skills, agents, commands, hooks) — each item directory/file gets its own symlink in `~/.claude/<category>/`
2. **File-level symlinks** (rules) — per-file within each subdirectory, enabling multi-source coexistence with Dotfiles
3. **File-level symlinks** (learned) — same per-file approach
4. **File-level symlinks** (bin) — into `~/.local/bin/`
5. **Selective directory-level symlinks** (skill groups, agent groups, hook groups) — same as #1 but filtered by user selections

### Ownership guard

Before removing any symlink during deselection or stale cleanup, the installer verifies:

```python
target = symlink.resolve()
if not target.is_relative_to(repo_dir):
    # Not ours — skip
    continue
```

This prevents removing Dotfiles-owned symlinks that share the same target directories. Uses `Path.is_relative_to()` (Python 3.9+) instead of string prefix matching to avoid false positives from sibling directories with similar names (e.g., `Claudefiles-backup/`).

For stale symlinks (broken targets), use `os.readlink()` (raw, unresolved) to check ownership before cleanup — `Path.resolve()` on a broken symlink returns the dangling path without raising, so stale detection must be separated from ownership checking.

### Package installation

For each selected package, the installer runs:

```
uv tool install -e packages/<name>
```

This is safe to re-run — `uv tool install -e` always reinstalls entry-point executables regardless of source changes. Package failures are reported but don't block other installations.

### Non-interactive fallback

When `sys.stdin.isatty()` is `False`:
1. Load saved config if available — apply it silently
2. No saved config — default to all groups selected, but do NOT save a config file (so the next interactive run still shows the wizard)
3. Skip all interactive prompts (shadowed files, stale symlinks logged as warnings only)

### Concurrency

The installer acquires an exclusive `fcntl.flock` on the config file at startup and releases at exit, serializing concurrent installer runs.

### Config save timing

The config file is written before installation begins (recording user intent) using `tempfile` + atomic rename (`os.replace()`). After installation completes, the config is updated to record any package failures. This ensures a mid-run crash (OOM kill, Ctrl-C) preserves the user's selections for the next run.

## Alternatives Considered

### Keep install.sh, add filtering via env vars

Add `SKIP_IMPECCABLE=1` to skip i-* skills. Simple but doesn't scale to multiple groups, no config persistence, no wizard UX, no package installation. Rejected because it solves only the immediate i-* problem without improving the new-user experience.

### Python package in packages/

Make the installer a proper package with `uv tool install -e packages/installer`. Rejected because of the chicken-and-egg problem: you need the installer to install packages, but the installer is itself a package. `uv run --script` avoids this entirely.

### Keep skills in a flat directory, filter via config only

No physical directory move — the installer reads prefix patterns to group skills. Rejected because the user explicitly wanted the repo structure to reflect the grouping. Physical separation makes the intent visible without running the installer.

## Test Strategy

Unit tests for the core logic (config loading/saving, smart diff, ownership guard, symlink operations) using pytest with tmp_path fixtures. The wizard UX is tested manually. Integration test: run the installer in a temp directory with mock repo structure, verify correct symlinks are created.

## Documentation Updates

- **CLAUDE.md** — update installation section to reference `install.py` instead of `install.sh`; remove manual `uv tool install -e` instructions (handled by installer)
- **README.md** — update install instructions; document skill group directories; update the "About skill prefixes" section
- **rules/common/capabilities.md** — split into per-group fragments: `capabilities-core.md` (always installed), `capabilities-impeccable.md` (installed with i-* skills), `capabilities-memory.md` (installed with cm-* skills). Trigger phrases for deselected groups are not loaded, preventing routing to missing skills.

## Impact

### Files modified
- `install.sh` — deleted (replaced by `install.py`)
- `CLAUDE.md` — update installation section
- `README.md` — update install instructions and directory descriptions
- `settings.json` — wrap all non-guarded hook entries in self-guarding `bash -c '[ -x "$f" ] && exec "$f" || exit 0'` wrappers (prerequisite for hook deselection)
- `skills/mine.challenge/SKILL.md` — update error message at line 256 (install.sh → install.py)
- `skills/mine.write-skill/SKILL.md` — update post-creation instruction (install.sh → uv run install.py)
- `rules/common/worktrees.md` — update safety prohibition to reference the installer concept, not the filename
- `rules/common/capabilities.md` — split into `capabilities-core.md`, `capabilities-impeccable.md`, `capabilities-memory.md`

Gate implementation on `grep -rn "install\.sh" --include="*.md"` to catch any remaining references.

### Files created
- `install.py` — new installer script
- `skills-impeccable/` — new directory (all 19 i-* skills moved here, including i-frontend-design)
- `skills-memory/` — new directory (3 cm-* skills moved here)
- `rules/common/capabilities-core.md` — core skill trigger phrases (always installed)
- `rules/common/capabilities-impeccable.md` — i-* trigger phrases (installed conditionally)
- `rules/common/capabilities-memory.md` — cm-* trigger phrases (installed conditionally)

### Files moved (git mv)
- 19 `skills/i-*` directories → `skills-impeccable/i-*`
- 3 `skills/cm-*` directories → `skills-memory/cm-*`

### Blast radius
- Low for existing users: symlink targets change but symlink names (and therefore runtime paths) are unchanged
- The installer itself is a clean replacement — no gradual migration needed
- Dotfiles installer is unaffected (it doesn't reference Claudefiles skill paths)

## Open Questions

None — all design decisions resolved during discovery.
