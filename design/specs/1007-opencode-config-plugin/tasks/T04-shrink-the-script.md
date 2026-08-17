---
task_id: "T04"
title: "Delete the disk-write machinery from bin/opencode-sync"
status: "planned"
depends_on: ["T02", "T03"]
implements: ["FR#11", "FR#12", "FR#13", "FR#14", "FR#15", "FR#16", "FR#17", "FR#18", "FR#21", "FR#23", "FR#24", "AC#7", "AC#8", "AC#9", "AC#12", "AC#18", "AC#19", "AC#22"]
---

## Summary

The subtraction wave. Remove staging, OpenPackage invocation, frontmatter rewriting, skill-command wrapper generation, sync-state and staleness detection, foreign-config detection, and the compatibility lint over installed files — along with `main()`'s entire install pipeline and the `--check` and `--lint-only` flags. Shrink `config.json` to exactly three keys. Delete the tests whose subjects go with them.

This is the largest diff in the spec and it is almost entirely deletion. What remains after this task is a script with four flags (`--check-source`, `--check-orphans`, and the new commands T05 adds) and a three-key config writer.

## Target Files

- modify: `bin/opencode-sync`
- modify: `tests/test_opencode_sync.py`
- read: `opencode/config-data.json`
- read: `design/specs/1007-opencode-config-plugin/design.md` (Replacement Targets — the per-function disposition table)

## Prompt

**Remove outright**, per the design's Replacement Targets table (line numbers are pre-edit; re-locate by name):

`stage_config` (`:331`), `run_opkg` (`:429`), `_run_opkg_best_effort` (`:356`), `opkg_list_includes_claudefiles` (`:384`), `uninstall_previous` (`:399`), `process_agent_frontmatter` (`:519`), `generate_skill_commands` (`:761`), `build_instructions` (`:833`), `check_sync_status` (`:725`), `load_sync_state` (`:627`), `write_sync_state` (`:713`), `_empty_sync_state` (`:619`), `_sha256_file` (`:615`), `handle_foreign_config` (`:1209`), `_atomic_write_json` (`:690`), `check_variant_names` (`:1077`), `_agent_variant_errors` (`:1126`), `run_lint` (`:1173`), `report_lint` (`:1191`), `lint_only` (`:1246`), `_lint_targets` (`:991`), `_lint_content` (`:1012`), `_walk_synced_md_files` (`:967`).

**`_atomic_write()` (`:645`) survives.** It gains the config writer as its direct caller. Torn-write risk is orthogonal to key count — `loadGlobal()` collapses to an empty config on a parse failure across all three global files (`config/config.ts:282-286`), taking `opencode.jsonc`'s machine-local `permission` and `mcp` settings down with it for that process. What goes is `_atomic_write_json`'s validate-then-backup ceremony, which guarded hand-authored complexity a three-key generated file does not have.

**Remove as fallout** — every caller sits inside a function removed above: `_split_eol` (`:956`, called only from `process_agent_frontmatter`) and `_atomic_write_text` (`:681`, called only from `process_agent_frontmatter` and `generate_skill_commands`).

**Also remove** the constants and helpers stranded by the above: `OPKG_VERSION`/`OPKG_PACKAGE_NAME`/`OPKG_TIMEOUT_SECONDS` (`:39-41`), `SYNC_STATE_FILE` (`:48`), `SHA_DISPLAY_LEN` (`:49`), `CONFIG_BACKUP_SUFFIX`/`FOREIGN_BACKUP_SUFFIX` (`:55-56`), `EXCLUDE_DIRS` (`:62`), `OPKG_SUCCESS_PATTERN` (`:109`), `TIER_MAP` (`:123`), `OPENCODE_VARIANTS` (`:146`), `GENERATED_FILE_MARKER` (`:154`), `LEGACY_SKILL_COMMAND_MARKER` (`:155`), `SKILL_COMMAND_TEMPLATE` (`:159`), `OPENCODE_COMMAND_RE` (`:170`), `OPENCODE_COMPAT_RULE` (`:178`), `FRONTMATTER_MODEL_RE` (`:911`). Let `--check-orphans` guide you, but do not trust it alone — see Focus.

`TIER_MAP`, `OPENCODE_VARIANTS`, and `SKILL_COMMAND_TEMPLATE` are deleted rather than repointed at `opencode/config-data.json`: the Python side has no remaining consumer for any of them. Only the plugin does. `OPENCODE_COMPAT_RULE` is deleted because T01 promoted it to `opencode/opencode-compat.md`.

Check whether `_split_frontmatter` (`:499`) still has a caller after the removals. `check_source_dispatch_patterns()` uses it (`:1316`), so it should survive — confirm rather than assume.

**Rewrite `parse_args()` and `main()`.** Drop `--dry-run`, `--verbose`, `--allow-worktree`, `--check`, and `--lint-only`. Keep `--check-source` and `--check-orphans`. `main()` collapses to flag dispatch — the entire staging/install/rewrite pipeline at `:1523-1617` and beyond goes. T05 adds `--bootstrap`, `--prune`, and `--verify`; leave room for them but do not implement them here.

Removing `--dry-run` also removes the dry-run preview machinery's reason to exist, and with it the need for `--allow-worktree` and `in_worktree()`/`_warn_on_worktree_mismatch()`/`_git_rev_parse()`/`_GIT_ENV_OVERRIDE_VARS` — those guarded against a worktree checkout overwriting the live config, and nothing in the new command set writes shared content. Check each for surviving callers before deleting; `_script_repo_root()` (`:281`) is used by `check_source()` and must stay. `check_deps()` (`:208`) checked for `npx`; with opkg gone it has no subject.

**Shrink `config.json` (FR#17, FR#18).** `generate_config()` (`:858`) keeps its name and its `config_dir`-derived paths, and emits exactly three top-level keys: `$schema`, `plugin`, and `subagent_depth`. The `instructions` key goes — the plugin owns it now. `plugin` declares the symlinked `claudefiles.ts`; path-like plugin specs resolve relative to the declaring config file (`config/config.ts:101-108`), so a bare filename is what you want. Write it through the surviving `_atomic_write()`. Update the docstring: its current text explains at length why there is no `agent` key and how the returned content gets hashed into sync state — the first half is still true and worth keeping, the second half's subject no longer exists.

**Never read, write, or move `opencode.jsonc`** (FR#18). With `handle_foreign_config()` gone this should follow automatically; assert it with a test.

**Tests.** Delete every test in `tests/test_opencode_sync.py` whose subject is on the removal list: `test_stage_config_creates_missing_rules_common_dir` (`:37`), `test_run_opkg_*` (`:64`, `:104`), `test_uninstall_previous_home_override_targets_scratch_home` (`:143`), `test_generate_skill_commands_*` (`:167`, `:192`, `:213`, `:237`), `test_build_instructions_never_uses_recursive_glob` (`:279`), `test_stage_config_drops_only_excluded_rules` (`:342`), `test_opencode_marked_rule_is_never_excluded` (`:372`), `test_real_repo_stages_every_rule_but_the_excluded` (`:388`), `test_check_variant_names_*` (`:605`–`:734`, seven tests), `test_run_lint_surfaces_variant_errors` (`:734`), `test_tier_map_variants_are_names_opencode_resolves` (`:749`), `test_process_agent_frontmatter_*` (`:766`, `:792`, `:812`), and `test_generate_config_points_instructions_at_synced_rules` (`:252`).

Keep and adapt `test_generate_config_emits_no_agent_key` (`:266`) — retarget it to assert the exact three-key set. Keep the `find_orphaned_definitions` / `check_orphans` tests (`:836`–`:930`) untouched; they are the completeness mechanism.

Add: a test asserting `generate_config()`'s output has exactly `{$schema, plugin, subagent_depth}` (AC#8); a test asserting a pre-existing `opencode.jsonc` in a scratch config dir is byte-identical before and after (AC#9); a test asserting `parse_args` rejects `--check` and `--lint-only` (AC#12).

## Focus

**Sequence the deletion so the file stays parseable.** `main()` references most of what you are deleting. Rewrite `main()` and `parse_args()` first, then delete the now-unreferenced functions bottom-up, running `--check-orphans` as you go.

**`--check-orphans` is the completeness mechanism (AC#18) but it under-reports.** `find_orphaned_definitions()` counts raw substring occurrences of a name across the whole file, comments and docstrings included (`:1400-1407`) — a deliberate lean toward fewer false positives. So a deleted helper whose name survives in a docstring explaining why it was removed will not be flagged. After the removals, `rg -c '<name>' bin/opencode-sync` each removed name and confirm any surviving hits are intentional prose. AC#7's explicit list is *not* the completeness check — the design says so directly, and enumerating transitive fallout by hand is what produced the `_atomic_write_json` mismatch the design already had to fix once.

**The module docstring (`:6-23`) describes a workflow that no longer exists** — it names opkg, staging, `process_agent_frontmatter`, skill-command bridges, and `--lint-only`. Rewrite it in this task rather than deferring to T06: leaving it stale would also feed `--check-orphans` false negatives, since removed function names would still appear in the file.

**Do not touch `check_source_dispatch_patterns()`'s dispatch-name or model-clause enforcement.** T03 added the platform-semantics warnings to it; both are shipped contracts and out of scope here. Your only interaction with it is confirming `_split_frontmatter()` still has a caller.

**AC#22's grep is `grep -c 'gpt-5\.6\|sudo\.md'` returning 0 for both `bin/opencode-sync` and `opencode/claudefiles.ts`.** Watch for these strings surviving in comments or docstrings — a comment saying "the tier map used to live here and mapped sonnet to gpt-5.6-terra" fails the check. Reference the shared file by name instead.

**`prek run --all-files` and `mise run test:root` must both pass before this task is done.** `--check-source` and `--check-orphans` are blocking pre-commit hooks running against the file you are gutting.

## Verify

- [ ] FR#11: `rg -c 'stage_config' bin/opencode-sync` returns 0.
- [ ] FR#12: `rg -c -i 'opkg' bin/opencode-sync` returns 0.
- [ ] FR#13: no function in `bin/opencode-sync` writes into `<config_dir>/{skills,agents,commands,rules}` — confirmed by reading every remaining write site; the only file written is `config.json`.
- [ ] FR#14: `rg -c 'process_agent_frontmatter|FRONTMATTER_MODEL_RE' bin/opencode-sync` returns 0.
- [ ] FR#15: `rg -c 'generate_skill_commands|SKILL_COMMAND_TEMPLATE|GENERATED_FILE_MARKER' bin/opencode-sync` returns 0.
- [ ] FR#16: `rg -c 'sync_state|SYNC_STATE_FILE|handle_foreign_config|check_sync_status' bin/opencode-sync` returns 0.
- [ ] FR#17: `generate_config()`'s output parses as JSON whose top-level keys are exactly `$schema`, `plugin`, `subagent_depth` — asserted by a test in `tests/test_opencode_sync.py`.
- [ ] FR#18: a test seeds a scratch config dir with an `opencode.jsonc`, runs the config writer, and asserts the file's bytes are unchanged.
- [ ] FR#21: `bin/opencode-sync --check-source` and `--check-orphans` both exit 0; `--check` and `--lint-only` both exit non-zero as unrecognized arguments.
- [ ] FR#23: `rg -c 'run_lint|report_lint|lint_only|_lint_targets|_lint_content|_walk_synced_md_files' bin/opencode-sync` returns 0.
- [ ] FR#24: `bin/opencode-sync --check-orphans` exits 0.
- [ ] AC#7: `grep -c 'opkg\|OPKG' bin/opencode-sync` returns 0, and each of the 23 function names listed in AC#7 is absent as a definition — confirmed by `rg -n '^def <name>' ` for each.
- [ ] AC#8: covered by the FR#17 test above; `mise run test:root` passes.
- [ ] AC#9: covered by the FR#18 test above.
- [ ] AC#12: `--check-source` and `--check-orphans` exit 0 against the migrated tree, both hook blocks remain in `prek.toml` unchanged, and `--check` is rejected.
- [ ] AC#18: `--check-orphans` exits 0, and `rg -c '_split_eol|_atomic_write_text' bin/opencode-sync` returns 0 while `rg -c '_atomic_write\b' bin/opencode-sync` returns non-zero.
- [ ] AC#19: `bin/opencode-sync --lint-only` exits non-zero as an unrecognized argument, and `--check-source` still reports the `isolation: "worktree"` / `run_in_background` occurrences across `skills/`, `commands/`, `agents/` that T03 relocated into it.
- [ ] AC#22: `grep -c 'gpt-5\.6\|sudo\.md' bin/opencode-sync` returns 0, `grep -c 'gpt-5\.6\|sudo\.md' opencode/claudefiles.ts` returns 0, and reading both files confirms neither defines a tier map, variant-name set, exclusion list, command template, or instruction-directory list as a literal.
