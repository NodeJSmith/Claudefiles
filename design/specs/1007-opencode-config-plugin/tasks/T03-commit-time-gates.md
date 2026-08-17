---
task_id: "T03"
title: "Move the surviving checks into --check-source"
status: "planned"
depends_on: ["T01"]
implements: ["FR#8", "FR#23", "AC#5"]
---

## Summary

Relocate the two checks worth keeping out of the installed-file lint and into `--check-source`, and repoint the exclusion and instruction-coverage checks at the shared data file. This runs **before** the removal wave (T04) deliberately: the platform-semantics warnings currently live inside `_lint_content()`, which T04 deletes, so the logic has to move while its source still exists — migrate callers, then delete.

The commit-time exclusion gate is not built from scratch. `check_source_dispatch_patterns()` already runs `apply_rule_exclusions()` and `check_instruction_globs()` against a scratch copy of the repo's `rules/` (`bin/opencode-sync:1348-1365`). The work is repointing them at `opencode/config-data.json` and making the exclusion check non-mutating, since there is no longer a staged tree to delete files from.

## Target Files

- modify: `bin/opencode-sync` (`apply_rule_exclusions:314`, `check_instruction_globs:1044`, `check_source_dispatch_patterns:1252`, `_lint_content:1012`, constants `OPENCODE_EXCLUDED_RULES:90`, `INSTRUCTION_DIRS:101`, `INSTRUCTION_ROOT:106`, regexes `ISOLATION_WORKTREE_RE:916`, `RUN_IN_BACKGROUND_RE:917`)
- modify: `tests/test_opencode_sync.py`
- read: `opencode/config-data.json`
- read: `design/specs/1007-opencode-config-plugin/design.md` (Architecture → "What `bin/opencode-sync` becomes"; Replacement Targets)

## Prompt

**1. Load the shared data.** Add a loader that reads `opencode/config-data.json` relative to the script's own repo root (`_script_repo_root()` at `:281` already resolves this and is what `check_source()` uses). Replace the module constants `OPENCODE_EXCLUDED_RULES` (`:90-94`) and `INSTRUCTION_DIRS` (`:101`) with values read from that file. Delete both constants — a hand-copy on the Python side is exactly what FR#27 forbids.

Note the instruction-directory list gains a second entry here: the shared file names `rules/common` **and** `rules/personal`, where `INSTRUCTION_DIRS` named only `rules/common`.

**2. Make `apply_rule_exclusions()` non-mutating.** Today it deletes matched files from the tree it is handed and returns the entries that matched nothing (`:314-328`). With no staged tree there is nothing to delete. Rewrite it to take a rules root and return only the unmatched entries — and rename it to say what it now does (`unmatched_rule_exclusions()` or similar), since "apply" no longer describes it.

That change makes the scratch-copy dance in `check_source_dispatch_patterns()` unnecessary. The `shutil.copytree` at `:1350-1355` exists solely because the old function deleted real files; a read-only check can run against `claudefiles / "rules"` directly. Remove the `TemporaryDirectory` block and call both checks against the live source tree. Keep the surrounding comment's point — that `rules/` needs checking even though it is not dispatch-scanned — but update its explanation, which currently describes the copy as the thing being worked around.

**3. Retarget `check_instruction_globs()`.** It currently asks "is every synced rules directory under the *config dir* covered by an `instructions` glob" (`:1044-1074`). It now asks "is every subdirectory under this repo's own `rules/` named in the shared instruction-directory list". Same question, different tree, and the answer no longer concerns globs at all — the plugin emits explicit paths. Rewrite the docstring and the error message accordingly: the remedy is "add it to the instruction-directory list in `opencode/config-data.json`", not "add it to `INSTRUCTION_DIRS` in `bin/opencode-sync`". Rename it if `_globs` no longer fits.

`INSTRUCTION_ROOT` (`:106`) may or may not survive this rewrite. If the retargeted function derives the root from its argument instead, delete the constant — `--check-orphans` will fail the commit otherwise.

**4. Move the platform-semantics warnings.** `_lint_content()` (`:1012`) currently emits warnings for `isolation: "worktree"` and `run_in_background` (regexes at `:916-917`) against installed files. Move that scanning into `check_source_dispatch_patterns()`, over the same three directories it already walks — `skills/`, `commands/`, `agents/` (the tuple at `:1301`). These stay **warnings**, not errors: they flag Claude-only dispatch semantics OpenCode cannot honor, which is a known permanent gap, not a commit-blocking fault.

Note that `check_source_dispatch_patterns()`'s docstring currently promises "Warnings always come back empty" (`:1275-1277`). That stops being true here — update it. `report_lint()` (`:1191`) already handles a non-empty warnings list, so no caller changes.

Do **not** widen the scan to `skills-cli/` or `skills-impeccable/`. Every current occurrence lives under `skills/` (`mine-visual-qa/SKILL.md`, `mine-challenge/SKILL.md`, `mine-issues-triage/SKILL.md`, `mine-orchestrate/post-execution-pipeline.md`), so no scope change is needed — and widening this function's scan would also widen its unrelated dispatch-name enforcement, which is a separate shipped contract.

**5. Tests.** In `tests/test_opencode_sync.py`, adapt rather than delete:
- `test_apply_rule_exclusions_reports_stale_entry` (`:407`) — same assertion, non-mutating signature, and add a positive assertion that the matched file is **still present** afterward.
- `test_check_source_gate_flags_stale_exclusion` (`:421`) — this is AC#5's test. Keep it.
- `test_check_source_gate_sees_uncovered_rules_directory` (`:435`), `test_check_instruction_globs_*` (`:291`, `:312`, `:323`) — retarget to the repo-source tree.
- `test_check_source_gate_judges_the_tree_that_ships` (`:462`) — its premise was the scratch copy mirroring staging exclusions. Re-derive or remove it once there is no staged tree.
- `test_stage_config_drops_only_excluded_rules` (`:342`), `test_opencode_marked_rule_is_never_excluded` (`:372`), `test_real_repo_stages_every_rule_but_the_excluded` (`:388`) — these assert on `stage_config()`, which T04 deletes. Leave them alone in this task; T04 owns their removal.

Add a test that the exclusion list loaded from `opencode/config-data.json` has exactly one entry and that a rule named `common/performance.md` or `common/tmux.md` is **not** filtered out — the shrink from three entries to one is the behavior change users will feel, and nothing else asserts it.

## Focus

**This task must leave `bin/opencode-sync` runnable.** It runs before the removal wave, so `stage_config()`, `run_opkg()`, `process_agent_frontmatter()` and the rest are all still present and still call into the code you are changing. Check callers before renaming: `apply_rule_exclusions()` is called from both `stage_config()` (`:331`) and `check_source_dispatch_patterns()` (`:1358`). `stage_config()`'s call *relies on the deletion side effect* — it is how excluded rules stay out of the staged tree. When you make the function non-mutating, `stage_config()` must do its own unlinking inline, or it silently starts staging `sudo.md`. That code is deleted in T04, so a short inline loop with a comment pointing at T04 is the right amount of effort; do not build anything durable there.

**`prek run --all-files` must pass at the end of this task**, since both `--check-source` and `--check-orphans` are blocking pre-commit hooks and you are editing the code they run. Run it before declaring done.

**`--check-orphans` is unreliable as a completeness proof.** `find_orphaned_definitions()` counts raw substring occurrences across the whole file including comments and docstrings (`:1400-1407`, a deliberate false-positive-avoidance lean). A constant you deleted whose name still appears in a docstring will not be flagged. `rg` for the name as well.

**Accepted limitation, documented — do not try to fix it here.** The retargeted coverage check reads this repo's `rules/`, which contains only `common/` (34 files). `rules/personal/` exists solely in `~/.claude` as five Dotfiles symlinks, so the check cannot see a rules subdirectory Dotfiles adds. This was raised during planning and accepted: pointing the commit-time gate at a live install would break `check_source()`'s reproducible-on-a-fresh-checkout contract (`:1370-1385`). The design doc records it under Dependencies and Assumptions. Your job is to make the check work correctly over the tree it can see, not to widen its reach.

Gap-check item this task addresses: gap 6 (above) and gap 7 — the instruction-directory list moving into the shared data file rather than being hand-copied on the Python side.

## Verify

- [ ] FR#8: renaming `rules/common/sudo.md` in a scratch copy of the repo and running `--check-source` against it exits non-zero with a message naming the unmatched exclusion entry; restoring the name makes it exit 0.
- [ ] FR#23: `rg -n 'ISOLATION_WORKTREE_RE|RUN_IN_BACKGROUND_RE' bin/opencode-sync` shows both regexes referenced from `check_source_dispatch_patterns()` and no longer from `_lint_content()`; running `--check-source` against the repo emits warnings for the four known occurrences under `skills/` and still exits 0.
- [ ] AC#5: covered by a test in `tests/test_opencode_sync.py` that renames the excluded rule in a `tmp_path` repo copy and asserts a non-zero exit naming the entry — `mise run test:root` passes.
