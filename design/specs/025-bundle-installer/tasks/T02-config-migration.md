---
task_id: "T02"
title: "Add v1 to v2 config migration"
status: "done"
depends_on: ["T01"]
implements: ["FR#5", "AC#2"]
---

## Summary

Add a pure `migrate_v1_to_v2(v1_config) -> dict` function that maps the old type-based config (skills/agents/hooks/packages selections) onto v2 bundle selections, plus the `packages` section slot in the v2 format. Wire it into the main flow: detect `version == 1`, migrate, back up the v1 file, save the v2 result, and show a migration summary that names any items being force-installed (the base is non-negotiable in v2). `load_config` stays read-only.

## Prompt

Work in `install.py` and `tests/test_install.py`. Implement the design's `## Architecture` → "Config migration (v1 → v2)" and the relevant `## Edge Cases`.

**1. Migration function.** Add `migrate_v1_to_v2(v1_config: dict) -> dict` — a pure function (no I/O) that returns a v2-format dict `{"version": 2, "bundles": {...}, "packages": {...}}`. Map per the design's migration table:
- `skills.impeccable` → `bundles.frontend`
- `skills.cli` → `bundles.cli`
- `skills.memory` → `bundles.memory`
- `agents.engineering` → `bundles.engineering`
- `agents.core` → `bundles.extra-agents` (true iff `agents.core` was true; the 8 base agents install unconditionally regardless)
- `skills.core`, `packages.spec-helper`, `packages.merge-settings`, `hooks.*` → no bundle mapping (folded into the always-installed base)
- `packages.ado-api` → `packages.ado-api` (preserve the boolean if present; default false)
- `packages.claude-memory`, `agents.memory` → covered by `bundles.memory` (no separate mapping)

Missing v1 fields default to false for optional bundles. The mapping is lossless for the all-selected case and best-effort for partial selections (Key Constraint).

**2. Establish the `packages` config section.** v2 config is `{"version": 2, "bundles": {...}, "packages": {"ado-api": false}}`. `migrate_v1_to_v2` populates `packages.ado-api` from v1. `_all_selected_config` (rewritten in T01) should also include a `packages` key (ado-api default false — fresh all-install does not force ado-api; it is detection-driven, see T03). The behavioral wiring of ado-api install/uninstall is T03; this task only establishes the data slot and migration mapping.

**3. Main-flow wiring.** In `main` (install.py ~952), after `load_config`, detect a v1 config (`saved.get("version") == 1`, or absence of `version`/`bundles` indicating pre-v2). When detected: call `migrate_v1_to_v2`, write a backup of the raw v1 config to `.claudefiles-install-config.v1.json.bak` (alongside the config file), use the migrated dict as `saved`, and print a migration summary. The summary must (a) show the v1→v2 bundle mapping, (b) name which items are force-installed because the base is now mandatory (former core skills/agents, research and issues skills, spec-helper/merge-settings), and (c) state the backup path. No confirmation prompt — the base bundle is non-negotiable (design Edge Cases).

`load_config` (install.py:179) stays pure/read-only — do not migrate inside it. Note that `load_config` currently rejects configs whose version != `CONFIG_VERSION` (install.py:185), returning None; adjust so a v1 config is returned (or otherwise surfaced) to the main flow for migration rather than silently discarded.

Add co-located tests: v1 configs with various selection combinations (all-selected, none-selected, partial, core-deselected, `skills.core=false`) → asserted v2 bundle mappings; backup file written; migration summary content.

## Focus

- The current `load_config` (install.py:179-190) returns `None` when `data.get("version") != CONFIG_VERSION`. With `CONFIG_VERSION` now 2 (set in T01), a v1 config (version 1) would be silently dropped — the migration path must intercept the v1 config before that rejection. Decide the cleanest seam: either `load_config` returns the raw dict and the version check moves to `main`, or add a dedicated read for the migration case. Keep `load_config` free of write side effects either way.
- `save_config` (install.py:192) force-stamps `version = CONFIG_VERSION` (2) on write — so saving the migrated dict tags it v2 automatically. The backup must be written from the *raw* v1 bytes/dict before `save_config` runs.
- Edge cases to honor (design `## Edge Cases`): v1 with core agents deselected still installs the 8 base agents (force-install, named in summary); v1 with `skills.core=false` still installs base. No confirmation prompt in either case.
- Only Jessica has a v1 config (design Blast Radius) — migration runs once, for one user. Keep it simple; do not over-engineer for configs that never existed.
- Test command: `timeout 300 uv run --with pytest --with python-frontmatter --with rich --with questionary --find-links packages/spec-helper pytest tests/ -v`.

## Verify
- [ ] FR#5: `migrate_v1_to_v2` maps every v1 field per the design's migration table; `main` detects a v1 config, migrates it, backs it up to `.claudefiles-install-config.v1.json.bak`, and saves v2.
- [ ] AC#2: running with a v1 config produces the correct bundle selections inferred from the old groups (test asserts the mapping for representative v1 configs, including partial selections and core-deselected).
