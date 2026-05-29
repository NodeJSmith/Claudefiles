# Context: Onboarding and Incremental Adoption (Bundle Installer)

## Problem & Motivation

A colleague opening this repo sees 58 skills, 20 agents, 39 rule files, and a README that is a reference catalog — with no way to understand what matters, what to try first, or how to adopt incrementally. The installer compounds this by presenting four wizard steps organized by component type (skills, agents, hooks, packages), concepts meaningless to a newcomer. The repo's most valuable capability — the define → plan → orchestrate → ship pipeline — is invisible. This work replaces the four-step type-based wizard with a single use-case-oriented bundle prompt, makes a base bundle always install (the pipeline), and adds onboarding docs (ONBOARDING.md + REFERENCE.md) so a colleague can read one document, understand the system, and adopt pieces incrementally.

## Visual Artifacts

None.

## Key Decisions

1. **Bundle model replaces type-based groups.** A single `Bundle` frozen dataclass and `BUNDLES` dict replace `SkillGroup`/`HookGroup`/`PackageDef` and their three dicts. Each bundle declares its skills, agents, packages, and capabilities files as a unit. Trade-off accepted: no per-skill granularity — a user wanting `mine.brainstorm` but not `mine.grill` installs the whole bundle. Users who can cherry-pick individual skills are better served by manual symlinks than a 58-item wizard.
2. **Base bundle always installs, no prompt.** All `mine.*` skills (except deprecated `mine.wp`), 8 core agents, `spec-helper` + `merge-settings` packages, all rules/bin/hooks/commands. No `mine.*` skill belongs to an optional bundle — optional bundles are `i-*`, `cli-*`, and `cm-*` only.
3. **Five optional bundles:** Frontend (`i-*`), CLI (`cli-*`), Memory (`cm-*` skills + cm-memory-auditor/cm-signal-discoverer agents + claude-memory package), Engineering (engineering-* agents + testing-reality-checker), Extra agents (architect, planner, qa-specialist, visual-diff).
4. **Config records intent, not filesystem state.** v2 format: `{version: 2, bundles: {...}, packages: {...}}`. Each operation derives actions from `BUNDLES` + config. Symlink creation is idempotent, so re-running after a crash converges. Config is saved **after** `do_install` completes (current code saves before, at install.py:1075 — this must change).
5. **v1 → v2 migration is a pure function.** `migrate_v1_to_v2(v1_config) -> dict`. `load_config` stays read-only. Main flow detects `version == 1`, migrates, backs up to `.claudefiles-install-config.v1.json.bak`, then saves v2. Lossless for the common case (everything selected), best-effort for partial selections.
6. **ado-api is a standalone detected suggestion, not a bundle.** When `git-platform` detects Azure DevOps in the current repo, the installer offers `ado-api`. The choice is recorded in the config's `packages` section so `--reconfigure` pre-checks it and `do_uninstall` removes it.
7. **Capabilities files:** `capabilities-core.md` already lives in `rules/common/` and installs with the always-installed rules (no relocation). `capabilities-impeccable.md`, `capabilities-cli.md`, `capabilities-memory.md` live in their skill source dirs and symlink into `rules/common/` only when their bundle is selected; deselection removes them (guarded by `is_owned_by`).
8. **Three docs for three audiences:** README (first impressions, <50 lines), ONBOARDING.md (adoption journey, primary deliverable), REFERENCE.md (lookup tables moved from README).

## Constraints & Anti-Patterns

- **Dependency completeness (Key Constraint):** the base bundle must include every skill and agent any optional bundle's skill depends on at runtime. The dependency audit from the design conversation is the source of truth. A missed dependency means an optional skill invokes a missing skill at runtime.
- **Symlink destinations must not change:** `~/.claude/skills/<name>`, `~/.claude/agents/<name>.md`, `~/.claude/rules/common/<name>.md`, etc. Identical to v1.
- **Behavioral invariants:** `--uninstall` still removes all owned symlinks + packages; `--dry-run` makes no changes; non-interactive mode still works (CI, scripted); the worktree safety check (`_is_git_worktree`) still blocks installation from worktrees.
- **Capabilities file removal must call `is_owned_by(target, repo_dir)` before unlinking** — mirrors install.py:659-661 — to avoid destroying user-placed files.
- **Migrate callers then delete legacy in the same wave** (coding-style): do not leave old dicts alongside new `BUNDLES`. The grouping layer is tightly coupled — every consumer (`do_install`, `do_uninstall`, `run_wizard`, `_print_dry_run`, `main`, `_all_selected_config`, `find_new_groups`) references the old dicts.
- **Non-goals (do NOT implement):** plugin system, source directory restructuring, per-skill selection.
- **Do NOT touch** Claude Code runtime behavior, spec-helper, or merge-settings internals.
- `from __future__ import annotations` is banned; use `X | None`, not `Optional[X]`; all imports at top of file.

## Design Doc References

- `## Architecture` — bundle data model, skill source resolution, installation flow, config contract, wizard changes, config format, migration, onboarding doc structure, README simplification
- `## Functional Requirements` — FR#1 through FR#13 (note: FR#13 is listed out of numerical order, between FR#2 and FR#3)
- `## Acceptance Criteria` — AC#1 through AC#13
- `## Edge Cases` — migration force-install of base, capabilities file lifecycle, stale symlinks, package/symlink failures
- `## Replacement Targets` — exact symbols being removed or replaced
- `## Test Strategy` — existing tests to adapt, new coverage mapped to FRs, nothing to remove
- `## Impact` — changed files, behavioral invariants, blast radius

## Convention Examples

### Frozen dataclass for declarations
**Source:** `install.py:30-36`
```python
@dataclass(frozen=True)
class SkillGroup:
    label: str
    description: str
    source_dir: str
    default: bool = True
```

### Atomic config write
**Source:** `install.py:192-211`
```python
def save_config(path: Path, data: dict) -> None:
    data = {**data, "version": CONFIG_VERSION}
    content = json.dumps(data, indent=2) + "\n"
    fd, tmp = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
    closed = False
    try:
        os.write(fd, content.encode())
        os.fsync(fd)
        os.close(fd)
        closed = True
        os.replace(tmp, path)
    except BaseException:
        if not closed:
            os.close(fd)
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise
```

### Checkbox wizard pattern
**Source:** `install.py:544-560`
```python
def _ask_checkbox(
    message: str, choices: dict[str, str], preselected: dict[str, bool]
) -> dict[str, bool]:
    choice_list = [
        questionary.Choice(title=desc, value=key, checked=preselected.get(key, True))
        for key, desc in choices.items()
    ]
    selected = questionary.checkbox(message, choices=choice_list).ask()
    if selected is None:
        print("Aborted.")
        sys.exit(1)
    return {k: k in selected for k in choices}
```

### Symlink with shadow tracking
**Source:** `install.py:302-335`
```python
def create_symlinks_dir_level(
    source_dir: Path,
    dest_dir: Path,
    *,
    repo_dir: Path | None = None,
    shadowed_out: list[tuple[Path, Path]] | None = None,
    dirs_only: bool = False,
) -> int:
    # ... iterates source_dir, creates symlinks, tracks shadows
```

### Deselection guard (is_owned_by before unlink)
**Source:** `install.py:659-661`
```python
for md_file in sorted(group_dir.glob("*.md")):
    target = rules_common_dest / md_file.name
    if target.is_symlink() and is_owned_by(target, repo_dir):
        target.unlink()
```
