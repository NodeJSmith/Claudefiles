---
task_id: "T01"
title: "Convert installer to bundle model (engine, wizard, flow)"
status: "planned"
depends_on: []
implements: ["FR#1", "FR#2", "FR#3", "FR#4", "FR#6", "FR#7", "FR#8", "FR#9", "FR#10", "AC#1", "AC#3", "AC#4", "AC#5", "AC#10", "AC#11", "AC#12", "AC#13"]
---

## Summary

Replace the type-based grouping layer in `install.py` (skills/agents/hooks/packages, four wizard steps) with a single `Bundle` dataclass and `BUNDLES` dict, and rewrite every consumer to be bundle-based. After this task the installer performs fresh installs, `--reconfigure`, `--dry-run`, `--uninstall`, and smart-diff for newly-added bundles — all driven by bundles — and leaves a fully working v2-format installer. v1→v2 config migration (T02) and ado-api ADO detection (T03) layer on top of this. This is the core rewrite; the module is tightly coupled, so the model swap and all caller updates must land together (no partial conversion leaves the module importable).

## Prompt

Work in `install.py` (repo root) and its tests `tests/test_install.py`. Implement the design's `## Architecture` sections: "Bundle data model", "Skill source resolution", "Installation flow", "Config contract", "Wizard changes", "Config format" (the `bundles` portion only — the `packages` section is added in T03).

**1. Data model.** Add the `Bundle` frozen dataclass exactly as in the design ("Bundle data model"):
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
Define `BUNDLES: dict[str, Bundle]`. There is exactly one always-installed bundle (`always_installed=True`) — the base — plus five optional bundles keyed `frontend`, `cli`, `memory`, `engineering`, `extra-agents`. Populate from FR#1 (base), FR#3 (optional bundles), and FR#9 (all `mine.*` skills in base except `mine.wp`). The base bundle's `skills` is every directory under `skills/` except `mine.wp`; its `agents` are the 8 named in FR#1; its `packages` are `("spec-helper", "merge-settings")`. The memory bundle's `capabilities_files` is `("capabilities-memory.md",)`, frontend's is `("capabilities-impeccable.md",)`, cli's is `("capabilities-cli.md",)`. Base does NOT list `capabilities-core.md` — it already lives in `rules/common/` and installs with the always-installed rules (FR#10, AC#13).

**2. Resolution helpers.** Add `SKILL_DIRS = ["skills", "skills-impeccable", "skills-cli", "skills-memory"]` and `find_skill_source(skill_name, repo_dir) -> Path` exactly as in the design's "Skill source resolution" (raises `FileNotFoundError` if not found). Add a per-item `create_symlink(source, dest, *, repo_dir=None, shadowed_out=None) -> bool` with the signature in the design's "Installation flow" — single source→dest, same shadow-tracking semantics as `create_symlinks_dir_level` (install.py:302-335) but for one link. Agents resolve to `agents/<name>.md`.

**3. Package resolution.** Change `install_package(repo_dir, pkg_name)` to resolve `repo_dir / "packages" / pkg_name` directly (remove the `PACKAGE_DEFS[pkg_name].dir_name` lookup at install.py:414). Package names in `Bundle.packages` match directory names under `packages/` exactly. Keep `uninstall_package` and `_get_installed_packages` as-is.

**4. Rewrite `do_install`** (install.py:588) per "Installation flow":
   1. Always install (unchanged): rules, learned, bin, commands, hooks — bulk dir/file-level symlinks. Hooks move from selective `HOOK_GROUPS` iteration to an unconditional bulk symlink of `scripts/hooks` (all hooks always install).
   2. Always-installed bundles: for each bundle with `always_installed`, symlink its skills (via `find_skill_source` + `create_symlink`) and agents by name.
   3. Selected optional bundles: symlink skills, agents, install packages, and symlink `capabilities_files` into `rules/common/`.
   4. Deselected optional bundles: remove owned symlinks for skills/agents, uninstall packages, and remove capabilities files — guarding each capabilities-file unlink with `is_owned_by(target, repo_dir)` (mirror install.py:659-661).

**5. Rewrite `do_uninstall`** (install.py:806): derive the package list by iterating bundles where `cfg["bundles"][key]` is true and collecting `.packages`, always including the base bundle's packages. (The `packages`-section contribution is added in T03.) Symlink removal keeps the existing `remove_owned_symlinks` scan.

**6. Rewrite `run_wizard`** (install.py:474) to a single `_ask_checkbox` call over the optional bundles only — no prompt for base, skills, agents, hooks, packages categories. Returns `{"bundles": {key: bool}}`.

**7. Rewrite `_print_dry_run`** (install.py:861), `_all_selected_config` (install.py:573), and `find_new_groups` usage in `main` (install.py:982-985) to operate on bundles. Dry-run lists each optional bundle with install/remove/skip/install(new) status (AC#5) and shows "Always installed: base bundle, rules, learned, bin, commands, hooks". `_all_selected_config` returns `{"version": 2, "bundles": {k: True for optional bundles}}`. Smart-diff (`find_new_groups`) detects optional bundles added to `BUNDLES` since last install and prompts for those only, preserving existing selections (FR#6, AC#10).

**8. Bump `CONFIG_VERSION = 2`** (install.py:26) and update its comment (currently documents "bump = full re-wizard, no migration" — that strategy is reversed; migration arrives in T02, so phrase the comment to reflect v2 with migration).

**9. Save-after-install.** Move the `save_config` call so config is written **after** `do_install` succeeds, not before (currently install.py:1075). See "Config contract — Config save timing".

**10. Remove replaced symbols** (design "Replacement Targets"): `SkillGroup`, `HookGroup`, `PackageDef`, `SKILL_GROUPS`, `HOOK_GROUPS`, `PACKAGE_DEFS`, `discover_agent_groups`, `_parse_agent_group`. Update `main` and `do_install`/`do_uninstall` signatures that take `agent_groups` (no longer discovered — agents are explicit in bundles). Then remove the now-vestigial `group:` frontmatter line from every file in `agents/*.md`.

Adapt `tests/test_install.py` so the suite is green against the bundle model (see Focus for which tests change). Add new co-located coverage for: `find_skill_source` resolution across all four skill dirs; bundle dependency completeness (every skill in every bundle resolves via `find_skill_source`); base installs regardless of bundle selection; bundle deselection removes symlinks + uninstalls packages; capabilities-core.md present always while optional capabilities files install/remove with their bundle.

## Focus

- `install.py` is ~1090 lines and tightly coupled: the three group dicts are referenced by `do_install` (630, 690, 776), `run_wizard` (497, 518, 537), `_print_dry_run` (882, 890, 894), `do_uninstall` (838), `_all_selected_config` (576-579), and `main` (982-1062). All must convert in this one task — a partial swap leaves the module non-importable. This is why the task is large; proceed model-first, then each consumer, running the test suite as you go.
- The existing `create_symlinks_dir_level` (302-335), `create_symlinks_file_level` (338), `is_owned_by` (279), `remove_owned_symlinks` (378), `find_stale_symlinks` (291) are the symlink plumbing — preserve them, reuse them. `create_symlink` is a new per-item sibling.
- The hooks change is a simplification: `HOOK_GROUPS` selective install (690-712) becomes an unconditional bulk symlink of the `scripts/hooks` directory. Hooks are always installed in v2.
- Memory auto-selection logic in the old wizard (install.py:524-525, claude-memory auto-added when memory skills/agents selected) is now implicit: claude-memory is a package inside the memory bundle, so selecting the memory bundle installs it. Drop the auto-select special case.
- Tests that change: `TestRunWizard`/non-interactive tests (658-756) assert on `config["skills"]`/`config["agents"]` shape — rewrite to `config["bundles"]`. `test_install_creates_correct_symlinks` (313), `test_deselected_group_removes_rule_fragments` (381), `test_deselection_preserves_unowned_rule_fragments` (439), and the package tests (500-610) all reference the old config shape. `test_discovers_groups`/`test_skips_no_group` (287-310) test `discover_agent_groups` which is being removed — delete those two tests.
- **CI does not lint `install.py`** — `.github/workflows/test.yml` runs `ruff check packages/ tests/` only. Keep `install.py` clean anyway (the repo's Python rules apply), but know that only the test suite gates it in CI.
- Test command (from `.github/workflows/test.yml`): `timeout 300 uv run --with pytest --with python-frontmatter --with rich --with questionary --find-links packages/spec-helper pytest tests/ -v`.
- The base skill list is derived, not hand-enumerated: glob `skills/*/` and exclude `mine.wp`. Hand-listing risks drift. Source of truth for the base agent set is FR#1's 8 names.

## Verify
- [ ] FR#1: `BUNDLES` has one `always_installed` base bundle containing all `skills/*` dirs except `mine.wp`, the 8 FR#1 agents, and packages `spec-helper` + `merge-settings`; `do_install` symlinks them with no prompt.
- [ ] FR#2: `run_wizard` issues a single `_ask_checkbox` over the five optional bundles; no skills/agents/hooks/packages-category prompts remain.
- [ ] FR#3: the five optional bundles (`frontend`, `cli`, `memory`, `engineering`, `extra-agents`) are defined with the exact skills/agents/packages from FR#3.
- [ ] FR#4: deselecting an optional bundle removes its skill+agent symlinks and uninstalls its packages (test asserts both).
- [ ] FR#6: a bundle newly added to `BUNDLES` is detected by smart-diff and prompted for, with existing selections preserved.
- [ ] FR#7: non-interactive mode applies saved v2 config; with no config it installs all bundles.
- [ ] FR#8: `--dry-run` lists each optional bundle with install/remove/skip status and makes no filesystem changes.
- [ ] FR#9: after a base-only install, every `mine.*` skill except `mine.wp` is symlinked; `mine.wp` is not.
- [ ] FR#10: `capabilities-core.md` is not listed in any bundle and installs via the always-installed `rules/` symlinks.
- [ ] AC#1: fresh machine, no config → base symlinks + single optional-bundle prompt → selected bundle symlinks.
- [ ] AC#3: `--reconfigure` shows all five optional bundles with current state pre-checked.
- [ ] AC#4: deselecting Memory removes cm-* skill symlinks, cm-* agent symlinks, and uninstalls claude-memory.
- [ ] AC#5: `--dry-run` output lists bundles with install/remove/skip status.
- [ ] AC#10: installer run after a new bundle is added prompts for the new bundle only, preserving existing selections.
- [ ] AC#11: non-interactive with a v2 config applies saved selections without prompting; with no config installs all bundles.
- [ ] AC#12: every `mine.*` skill except `mine.wp` present after base-only install; `mine.wp` not symlinked.
- [ ] AC#13: `capabilities-core.md` present in `rules/common/` regardless of bundle selections.
