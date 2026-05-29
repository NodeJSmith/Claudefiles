# Design: Onboarding and Incremental Adoption

**Date:** 2026-05-29
**Status:** draft (challenged)
**Scope-mode:** hold

## Problem

A colleague opens this repo and sees 58 skills, 20 agents, 39 rule files, and a README that is a reference catalog. There is no way to understand what matters, what to try first, or how to adopt pieces incrementally. The installer compounds this by presenting four separate wizard steps organized by component type (skills, agents, hooks, packages) — concepts that mean nothing to someone who hasn't used the system yet.

The repo's most valuable capability — the define → plan → orchestrate → ship pipeline — is invisible unless you already know to look for it. A colleague who could benefit from just the code review workflow has no path to install that without also getting 50 other things they don't understand yet.

## Goals

- A colleague can read one document and understand what this repo does, what's worth trying first, and how to adopt incrementally
- The installer supports incremental adoption: a base bundle that always installs (the pipeline), plus optional bundles a user adds as they grow into the system
- Three audiences served by distinct files: README for first impressions ("is this for me?"), ONBOARDING.md for adoption ("what should I try and how?"), REFERENCE.md for lookup ("what can I invoke for X?")
- A single wizard prompt organized by use case, not component type

## Non-Goals

- Plugin system (evaluated and deferred — rules can't be pluginized, namespace changes break muscle memory)
- Restructuring source directories (bundles are a distribution concern, not a source layout concern)
- Individual skill-level selection (bundles are the right granularity — per-skill is too fine)

## User Scenarios

### Curious Colleague: browsing the repo for the first time
- **Goal:** understand whether this is worth trying and what to try first
- **Context:** received a link from Jessica, opened the GitHub page

#### First visit
1. **Reads README**
   - Sees: 3-sentence description, "what's here and why," link to ONBOARDING.md
   - Decides: whether to read further
   - Then: clicks through to ONBOARDING.md or closes the tab

#### Reading the onboarding doc
1. **Reads ONBOARDING.md**
   - Sees: Key Concepts (what skills/agents/rules are), then Choose Your Path
   - Decides: Path A (pick specific pieces) or Path B (try the full pipeline)
   - Then: follows install instructions for their chosen path

### New Adopter: installing for the first time
- **Goal:** install the base and maybe one optional bundle to try for a week
- **Context:** read the onboarding doc, ready to install

#### First install
1. **Runs `uv run install.py`**
   - Sees: panel explaining the base always installs, then a single checkbox list of optional bundles
   - Decides: selects none (just the base) or one bundle they read about
   - Then: installer creates symlinks, reports summary

#### Adding a bundle after a week
1. **Runs `uv run install.py --reconfigure`**
   - Sees: current selections pre-checked, new bundles unchecked
   - Decides: checks "Research & ideation" after using `/mine.challenge` and wanting `/mine.brainstorm`
   - Then: installer adds the new symlinks

### Jessica: existing v1 config
- **Goal:** migrate to the new format
- **Context:** the only user with a v1 config

#### Config migration
1. **Runs `uv run install.py`**
   - Sees: "Migrating config from v1 to v2..." with bundle mapping summary
   - Then: installer writes new config and proceeds normally

### Package failure
- **Goal:** understand what went wrong
- **Context:** network is down or uv is misconfigured

#### Package failure during install
1. **Runs `uv run install.py` and selects Memory bundle**
   - Sees: symlinks created, then "Failed to install claude-memory" with error detail
   - Then: installer completes with non-zero exit code; symlinks in place, only the package is missing

## Functional Requirements

- **FR#1** The installer always installs the base bundle without prompting: all `mine.*` skills except the deprecated `mine.wp` (no `mine.*` skill belongs to an optional bundle — optional bundles are `i-*`, `cli-*`, and `cm-*` only), 8 agents (code-reviewer, integration-reviewer, wtf-reviewer, researcher, llm-checker, lazy-checker, nitpicker, issue-refiner), spec-helper and merge-settings packages, all rules, all bin scripts, all hooks, and all commands
- **FR#2** The installer presents optional bundles in a single checkbox prompt, where each bundle includes its skills, agents, and packages as a unit
- **FR#3** The optional bundles are: Frontend design (all i-* skills), CLI design (all cli-* skills), Memory (all cm-* skills, cm-memory-auditor and cm-signal-discoverer agents, claude-memory package), Engineering specialists (all engineering-* agents, testing-reality-checker agent), Extra agents (architect, planner, qa-specialist, visual-diff)
- **FR#13** When `git-platform` detects Azure DevOps in the current repo, the installer offers `ado-api` as a standalone package install with a contextual prompt ("This repo uses Azure DevOps. Install ado-api?"). It is not a bundle — just a detected suggestion. The choice is recorded in the config's `packages` section so `--reconfigure` pre-checks it and `do_uninstall` removes it
- **FR#4** Deselecting an optional bundle removes its symlinks and uninstalls its packages
- **FR#5** The installer detects a v1 config and migrates it to v2 format by mapping old selections to the closest bundle equivalents
- **FR#6** The installer detects bundles added to the repo since the last install and prompts for them (existing smart-diff behavior, applied to bundles)
- **FR#7** Non-interactive mode applies saved config or installs everything if no config exists (existing behavior preserved)
- **FR#8** The `--dry-run` flag shows what would be installed per bundle (existing behavior adapted)
- **FR#9** All `mine.*` skills install as part of the base — there is no "standalone vs core" distinction. This includes specialized tooling (mutation-test, visual-qa, audit, decompose, worktree-rebase, write-skill, mockup, tool-gaps), research (brainstorm, grill, prior-art, eval-repo), and issues (create-issue, issues-triage) skills; all are core workflow, not optional. The deprecated `mine.wp` is the sole exclusion — it redirects to `/mine.status` and is not installed
- **FR#10** `capabilities-core.md` already lives in `rules/common/` and requires no relocation — it installs as part of the always-installed rules with no installer changes needed
- **FR#11** An onboarding document (ONBOARDING.md) replaces the reference tables in README with a journey-oriented guide structured around user personas
- **FR#12** README.md is trimmed to project description, install command, link to ONBOARDING.md, requirements, and license

## Edge Cases

- User has v1 config with "core" agents deselected — migration must still install the 8 base agents since they're now mandatory. The migration summary should name which items are being force-installed so the user is informed, but no confirmation prompt is needed — the base bundle is the product's value proposition and is non-negotiable in v2
- User has v1 config with `skills.core = false` — migration installs base (now mandatory, includes former research and issues skills). User is informed via migration summary
- Non-interactive mode with no config defaults to all bundles installed (existing behavior)
- A bundle's package is already installed by another means (e.g., user manually `uv tool install`'d claude-memory) — installer skips without error (existing behavior via `_get_installed_packages`)
- Optional bundle capabilities files (capabilities-impeccable.md, capabilities-memory.md, capabilities-cli.md) only install when their bundle is selected; deselection removes them from rules/common/
- Stale symlinks from skills that moved between bundles (e.g., eval-repo was in research, moved to base) — handled by existing stale symlink cleanup
- Package installation fails (network error, uv misconfigured): installer logs the error, continues with remaining work, exits with non-zero status (existing behavior preserved)
- A skill name in a bundle doesn't match any directory in the skill source dirs: `find_skill_source` raises `FileNotFoundError`, installer logs the error and continues — this is a repo bug, not a user error
- Symlink creation fails (permission denied on `~/.claude/`): installer logs the error and continues; user sees which symlinks failed

## Acceptance Criteria

- **AC#1** Running `uv run install.py` on a fresh machine with no config produces: base symlinks + all-bundles prompt → selected bundle symlinks (FR#1, FR#2)
- **AC#2** Running `uv run install.py` with a v1 config produces the correct bundle selections inferred from old groups (FR#5)
- **AC#3** Running `uv run install.py --reconfigure` shows all bundles with current state pre-checked (FR#2)
- **AC#4** Deselecting the Memory bundle removes cm-* skill symlinks, cm-* agent symlinks, and uninstalls claude-memory (FR#4)
- **AC#5** `--dry-run` output lists bundles with install/remove/skip status (FR#8)
- **AC#6** After reading ONBOARDING.md Path A, a colleague can name which bundle to install for their specific need (e.g., "I want code review" → base is enough) (FR#11)
- **AC#7** After reading ONBOARDING.md Path B, a colleague can describe the define → plan → orchestrate → ship sequence and knows which skill to invoke for each step (FR#11)
- **AC#8** REFERENCE.md contains the full component tables (skills, agents, commands, hooks, bin scripts) currently in README (FR#11)
- **AC#9** README.md is under 50 lines (FR#12)
- **AC#10** Running the installer after a new bundle is added to BUNDLES prompts the user for the new bundle only, preserving existing selections (FR#6)
- **AC#11** Running the installer non-interactively with a v2 config applies saved bundle selections without prompting; with no config, installs all bundles (FR#7)
- **AC#12** Every `mine.*` skill except `mine.wp` is present after a base-only install with no optional bundles selected; `mine.wp` is not symlinked (FR#9)
- **AC#13** capabilities-core.md is present in rules/common/ regardless of bundle selections (FR#10)

## Key Constraints

- The base bundle must include every skill and agent that any optional bundle's skill depends on. If a dependency is missed, an optional skill will invoke a missing skill at runtime. The dependency graph audit from this conversation is the source of truth.
- Config migration from v1 to v2 must be lossless for the common case (user had everything selected) and best-effort for partial selections.

## Dependencies and Assumptions

- Assumes `spec-helper` and `merge-settings` are the only packages needed by the base (verified by dependency audit; `merge-settings` provides `claude-merge-settings`, core setup tooling)
- Assumes all hooks are lightweight enough to always install (no user has requested granular hook selection)
- `capabilities-core.md` already lives in `rules/common/` — no relocation needed
- Several base skills assume GitHub CLI tooling (`gh-issue`, `gh-pr-create`, `gh-pr-threads`, `gh-pr-reply`). ADO support exists in some skills via `git-platform` detection but is incomplete. A platform audit is needed before colleagues on ADO can use the full pipeline. This audit is out of scope for this design — tracked separately

## Architecture

### Bundle data model

Replace `SkillGroup`, `HookGroup`, `PackageDef`, and `SKILL_GROUPS`/`HOOK_GROUPS`/`PACKAGE_DEFS` with a single `Bundle` dataclass and `BUNDLES` dict:

```python
@dataclass(frozen=True)
class Bundle:
    label: str
    description: str
    skills: tuple[str, ...] = ()
    agents: tuple[str, ...] = ()
    packages: tuple[str, ...] = ()
    capabilities_files: tuple[str, ...] = ()
    always_installed: bool = False
```

The bundle model optimizes for onboarding simplicity (one decision per use case) at the cost of per-skill granularity — a user who wants `mine.brainstorm` but not `mine.grill` must install the full Research bundle. This trade-off is intentional: users who know individual skills well enough to cherry-pick are better served by manual symlinks than a 58-item wizard.

Each skill name maps to its source directory via a resolver function that checks `skills/`, `skills-impeccable/`, `skills-cli/`, `skills-memory/` in order. Each agent name maps to `agents/<name>.md`.

The `capabilities_files` field lists `.md` files from skill group directories that should be symlinked into `rules/common/` when the bundle is installed. This handles `capabilities-impeccable.md`, `capabilities-memory.md`, `capabilities-cli.md`. The base bundle's `capabilities-core.md` is relocated to `rules/common/` directly (no longer needs conditional symlinking).

### Skill source resolution

A function `find_skill_source(skill_name, repo_dir)` searches the skill directories for a matching subdirectory:

```python
SKILL_DIRS = ["skills", "skills-impeccable", "skills-cli", "skills-memory"]

def find_skill_source(skill_name: str, repo_dir: Path) -> Path:
    for dir_name in SKILL_DIRS:
        candidate = repo_dir / dir_name / skill_name
        if candidate.is_dir():
            return candidate
    raise FileNotFoundError(f"Skill not found: {skill_name}")
```

### Installation flow

`do_install` changes from category-based to bundle-based:

1. **Always install** (unchanged): rules, learned, bin, commands, hooks — bulk symlink entire directories
2. **Always-installed bundles**: iterate all bundles where `b.always_installed` is true, symlink each bundle's skills and agents by name
3. **Selected optional bundles**: iterate each bundle's skills, agents, packages, and capabilities_files
4. **Deselected optional bundles**: remove owned symlinks for each deselected bundle's items

Capabilities file removal for deselected bundles must call `is_owned_by(target, repo_dir)` before unlinking, mirroring the current deselection path at install.py:659-661. This prevents destroying user-placed files.

The per-item symlink function is simpler than the bulk variant — it takes a source path and destination path directly, with the same shadow-tracking signature:

```python
def create_symlink(
    source: Path,
    dest: Path,
    *,
    repo_dir: Path | None = None,
    shadowed_out: list[tuple[Path, Path]] | None = None,
) -> bool:
    """Create a single symlink. Returns True if created."""
```

### Config contract

The config file records **intent** — which bundles the user selected. It does not record filesystem state. Each operation derives what to do from `BUNDLES` + config:

- **`do_install`**: for each bundle where `cfg["bundles"][key]` is true, iterate `BUNDLES[key].skills`, `.agents`, `.packages`, `.capabilities_files` and create symlinks / install packages. Symlink creation is idempotent (re-linking an existing symlink is safe), so re-running after a crash converges to the correct state without special recovery logic.
- **`do_uninstall`**: derive the full package list by iterating all bundles where `cfg["bundles"][key]` is true and collecting `.packages`. Also always include the base bundle's packages, and any package flagged true in `cfg["packages"]` (e.g. `ado-api`). Then uninstall each. Symlink removal uses the existing `remove_owned_symlinks` scan, which is config-independent.
- **Config save timing**: save config **after** `do_install` completes successfully, not before. This ensures config always reflects completed state. If the installer crashes mid-install, the next run detects the stale config and re-applies. The current code saves before install (install.py:1075); this must change.

### Wizard changes

`run_wizard` collapses to one `_ask_checkbox` call for optional bundles. No prompt for base, hooks, rules, bin, or commands.

### Config format

Version bumped from 1 to 2:

```json
{
  "version": 2,
  "bundles": {
    "frontend": false,
    "cli": false,
    "memory": true,
    "engineering": false,
    "extra-agents": false
  },
  "packages": {
    "ado-api": false
  }
}
```

The `packages` section records standalone package choices that are not part of any bundle — currently just `ado-api` (FR#13). It is what lets `--reconfigure` pre-check a previously-installed standalone package and lets `do_uninstall` remove it. Bundle packages are never listed here; they are derived from `bundles` + `BUNDLES`.

### Config migration (v1 → v2)

Migration is handled by a pure function `migrate_v1_to_v2(v1_config: dict) -> dict` that takes the raw v1 config and returns a v2-format dict. `load_config` stays pure (read-only). The main flow detects `version == 1`, calls `migrate_v1_to_v2`, backs up the v1 config to `.claudefiles-install-config.v1.json.bak`, then calls `save_config` with the v2 result. The backup path is included in the migration summary shown to the user. Note: the current `CONFIG_VERSION` comment at install.py:26 documents the opposite strategy ("bump = full re-wizard, no migration"); this design reverses that decision, so that comment must be updated to describe the migration path.

Package names in `Bundle.packages` must exactly match their directory names under `packages/`. `install_package(repo_dir, pkg_name)` resolves `repo_dir / "packages" / pkg_name` directly, removing the need for `PACKAGE_DEFS` and `dir_name`.

The migration maps old selections to bundles:

| v1 field | Maps to v2 bundle |
|---|---|
| `skills.core = true` | base (always installed — includes research and issues skills) |
| `skills.core = false` | base (always installed — research and issues skills are now mandatory in base) |
| `skills.impeccable` | `frontend` |
| `skills.cli` | `cli` |
| `skills.memory` | `memory` |
| `agents.core` | base agents (including issue-refiner) always installed; `extra-agents` = true if agents.core was true |
| `agents.engineering` | `engineering` |
| `agents.memory` | (covered by `memory` bundle) |
| `packages.ado-api` | v2 `packages.ado-api` (preserved if v1 had it true; otherwise offered separately via ADO detection prompt) |
| `packages.claude-memory` | (covered by `memory` bundle) |
| `packages.spec-helper` | base (always installed) |
| `packages.merge-settings` | base (always installed) |
| `hooks.*` | (hooks always installed in v2, no mapping needed) |

### Onboarding doc structure

`ONBOARDING.md` at repo root. The primary deliverable — this is what a colleague reads before deciding to install.

**1. What This Is** (2 paragraphs)
- What Claudefiles does in plain language: "a set of skills, rules, and agents that make Claude Code better at planning, reviewing, and shipping code"
- Who it's for: "anyone using Claude Code who wants more structure than raw prompting." Assumes basic Claude Code familiarity (can run `claude`, knows what a slash command is)

**2. Install** (short)
- `git clone` + `uv run install.py`
- One sentence on `--reconfigure` and `--uninstall`
- Note: "The base (pipeline workflow) always installs. The wizard asks about optional add-ons."

**3. Key Concepts** (must precede paths)
- **Skills** — reusable prompts invoked by name (`/mine.challenge`, `/mine.research`). The main interface.
- **Commands** — lightweight slash commands for daily tasks (`/mine.status`, `/mine.end-of-day`)
- **Agents** — specialized subagents dispatched by skills (code-reviewer, researcher). You don't invoke these directly.
- **Rules** — coding guidelines loaded automatically. Shape how Claude writes code, handles git, runs tests. Always active.
- **Hooks** — event-driven scripts (pytest safety, sudo handling, tmux naming). Run in the background.
- **Bundles** — use-case packages. The base bundle gives you the pipeline. Optional bundles add capabilities (research, frontend design, memory, etc.)

**4. Choose Your Path** (readers pick one)

- **Path A: Pick and Choose** — for someone who has a specific need. Organized by problem:
  - "I want better code review" → the base is enough (`/mine.review`, `/mine.clean-code`, automatic pre-commit review)
  - "I want structured planning for complex features" → the base is enough (`/mine.define` → `/mine.plan` → `/mine.orchestrate`)
  - "I want to brainstorm and challenge ideas" → base is enough (`/mine.brainstorm`, `/mine.grill`, `/mine.challenge`)
  - "I want to manage issues" → base is enough (`/mine.create-issue`, `/mine.issues-triage`)
  - "I want frontend design help" → add Frontend bundle (19 Impeccable skills for UI audit, layout, typography, etc.)
  - "I want conversation memory across sessions" → add Memory bundle
  - Each entry: what you get, one example invocation, which bundle to select (or "included in base")

- **Path B: The Full Pipeline** — for someone willing to try the whole workflow. End-to-end walkthrough:
  1. Start with an idea → `/mine.grill` sharpens it or `/mine.define` shapes it (both in base)
  2. Define produces a `design.md` → `/mine.plan` generates task files
  3. `/mine.orchestrate` executes tasks with reviewer loops
  4. `/mine.ship` commits, pushes, creates a PR
  - Concrete example using a small feature. Show what each step produces.

- **Path C: Everything** — for someone who wants the full picture. What you get when all bundles are installed, how skills/agents/rules/hooks interact, daily workflow patterns (`/mine.good-morning` → work → `/mine.end-of-day`), worktree-based development.

**5. Customizing** (short)
- Writing your own rules: drop a `.md` in `rules/common/`
- Writing your own skills: `/mine.write-skill`
- Settings: `settings.json` + `claude-merge-settings`
- Removing things: just deselect the bundle or delete the rule file

**6. Reference** — one line: "See [REFERENCE.md](REFERENCE.md) for the full list of skills, agents, commands, hooks, and scripts."

### README simplification

README.md keeps: project description (3 sentences), install section, link to ONBOARDING.md, requirements, local dev section, license. Reference tables move to `REFERENCE.md`.

## Replacement Targets

- `SkillGroup` dataclass and `SKILL_GROUPS` dict → replaced by `Bundle` dataclass and `BUNDLES` dict
- `HookGroup` dataclass and `HOOK_GROUPS` dict → removed (hooks always installed)
- `PackageDef` dataclass and `PACKAGE_DEFS` dict → packages declared inline in bundles; `install_package`/`uninstall_package` functions kept
- `discover_agent_groups` and `_parse_agent_group` → removed (agents declared explicitly in bundles, not discovered from frontmatter); the now-vestigial `group:` frontmatter in every `agents/*.md` should be removed in the same change
- `run_wizard` 4-prompt structure → replaced with single-prompt bundle selection
- `do_install` category-based loop → replaced with bundle-based loop
- `_preselected_keys` and `_all_selected_config` → simplified for bundle model
- Config format v1 → v2 with migration function
- `capabilities-core.md` — already in `rules/common/`, no change needed
- README.md reference tables → moved to `REFERENCE.md`

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
        questionary.Choice(
            title=desc,
            value=key,
            checked=preselected.get(key, True),
        )
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

## Alternatives Considered

**Plugin system**: Evaluated in this conversation. Rejected because rules can't be pluginized (39 rule files, the most valuable part of the repo), skill namespacing changes UX (`/mine.challenge` → `/claudefiles:mine.challenge`), and the system is premature for a repo that hasn't proven external adoption yet.

**Per-skill selection**: Individual checkboxes for each of 58 skills. Rejected as too granular — users don't know which skills they need until they've used them. Bundles are the right level of abstraction.

**Directory restructuring**: Move optional mine.* skills into separate source directories (e.g., `skills-research/`). Rejected because the bundle manifest achieves the same result without reorganizing files. Source layout is an organizational concern; distribution is a separate concern.

## Test Strategy

### Existing Tests to Adapt

```
tests/test_install.py
```

Needs updating for: new Bundle dataclass, single-wizard flow, bundle-based do_install, config v2 format, v1→v2 migration. The test structure (parametrized install/uninstall/reconfigure scenarios) stays; the assertions change from category-based to bundle-based.

### New Test Coverage

- **Config migration** (FR#5): v1 config with various selection combinations → correct v2 bundle mapping
- **Bundle dependency completeness** (FR#1, FR#3): verify every skill in every bundle can resolve via `find_skill_source`
- **Base always installs** (FR#1): verify base skills/agents are installed regardless of bundle selections
- **Bundle deselection** (FR#4): verify symlinks removed and packages uninstalled when a bundle is deselected
- **Capabilities file handling** (FR#10): verify capabilities-core.md installs from rules/common/, optional capabilities files install/remove with their bundles

### Tests to Remove

No tests to remove — existing tests are adapted, not deleted.

## Documentation Updates

- **ONBOARDING.md** — new file, the primary deliverable alongside the installer changes
- **README.md** — trimmed to minimal project description + install + link to onboarding + requirements + license
- **CLAUDE.md** — update "Making Changes" section: change "Always update `README.md`" instruction to reference `ONBOARDING.md` and `REFERENCE.md` as the maintenance targets for skill/agent/command changes
- **CHANGELOG.md** — entry for the installer redesign and onboarding doc

## Impact

<!-- Gap check 2026-05-29: clean. Only code dependent on install.py internals is tests/test_install.py (already listed). Doc references (CLAUDE.md, README.md) already listed. FR#13 needs net-new bin/git-platform subprocess integration → T03 Focus. CI lints packages/ and tests/ only, not install.py → T01 Focus. -->

### Changed Files

- `install.py` — major rewrite of grouping layer; symlink plumbing preserved
- `ONBOARDING.md` — new file
- `REFERENCE.md` — new file (component reference tables moved from README)
- `README.md` — trimmed from ~268 lines to ~50
- `tests/test_install.py` — updated for bundle model
- `CLAUDE.md` — update "Making Changes" to reference ONBOARDING.md and REFERENCE.md
- `CHANGELOG.md` — new entry

### Behavioral Invariants

- All existing symlink destinations must remain the same: `~/.claude/skills/<name>`, `~/.claude/agents/<name>.md`, `~/.claude/rules/common/<name>.md`, etc.
- `--uninstall` must still remove all owned symlinks and packages
- `--dry-run` must still show what would happen without making changes
- Non-interactive mode must still work (CI, scripted installs)
- The worktree safety check must still block installation from worktrees

### Blast Radius

- Jessica's v1 config will migrate on next `uv run install.py` (one-time, one user)
- No impact on Claude Code runtime behavior — symlink destinations are identical
- No impact on other Claudefiles tooling (spec-helper, merge-settings, etc.)
- New adopters (colleagues) get a clean v2 experience with no migration

## Open Questions

None — all questions resolved during discovery.
