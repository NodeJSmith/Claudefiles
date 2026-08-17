---
task_id: "T05"
title: "Strip the dispatch translation layer from bin/opencode-sync"
status: "done"
depends_on: ["T04"]
implements: ["FR#14", "FR#15", "FR#16", "FR#17", "FR#18", "FR#21", "FR#22", "FR#25", "AC#8", "AC#9", "AC#10", "AC#16", "AC#17", "AC#21", "AC#26"]
---

## Summary

With every dispatch correct at the source, the translation layer has nothing left to translate. Delete worker generation, opus-variant generation, dispatch rewriting, config-level agent pinning, and the five dispatch-translation regexes. Reimplement `--check-source` and `--lint-only` rather than narrowing them — their current methods are "rewrite, then check nothing residual survived," which stops meaning anything without a rewriter. Add an orphan check so the next deletion wave cannot leave a stranded helper behind. Two things that look deletable and are not: `check_variant_names()` is narrowed (it guards the #514 failure mode), and `_walk_synced_md_files()` survives because a surviving caller still uses it.

## Target Files

- modify: `bin/opencode-sync` — the deletions and rewrites in the design's Replacement Targets table
- modify: `tests/test_opencode_sync.py` — substantial deletions; the twelve `test_check_variant_names_*` tests are adapted, not deleted
- modify: `prek.toml` — wire the orphan check; the existing `lint-opencode-sync` hook at `:114-121` keeps its entry
- modify: every file carrying a `<!-- opencode-sync: ok -->` suppression — enumerate with `grep -rn 'opencode-sync: ok' skills skills-cli skills-impeccable commands agents`
- read: `design/specs/1008-opencode-named-roles/design.md` — **Architecture → What leaves `bin/opencode-sync`** is the authoritative deletion analysis
- read: `bin/opencode-variant-audit` — the runtime observation tool that does *not* substitute for the commit-time variant guard

## Prompt

Read `design/specs/1008-opencode-named-roles/design.md`, sections **Architecture → What leaves `bin/opencode-sync`** (read this in full before deleting anything — it names three helpers that look dead and are not), **Replacement Targets**, and FR#14–18, FR#21, FR#22, FR#25.

**1. Remove outright.**

- `generate_worker_agents()` (`:796-838`) and `generate_specialist_opus_variants()` (`:841-967`) — the agents they synthesize are real files now (FR#14, FR#15).
- `rewrite_all_dispatches()` (`:1522-1536`), `_rewrite_dispatch_file()`, `_rewrite_line()`, `_apply_edits()` (`:1316`), `_removal_span_for_model()` (`:1323`), `rewrite_dispatches_prose()` (`:1406`), `rewrite_dispatches_cli()` (`:1457`), and `resolve()` (`:1259-1303`) (FR#16).
- The five dispatch-translation regex constants: `SUBAGENT_TYPE_RE`, `BARE_BUILTIN_RE`, `MODEL_RE`, `STANDALONE_MODEL_RE`, `CLI_DISPATCH_RE`.
- `SPECIALIST_AGENTS` (`:168`), `WORKER_AGENT_TEMPLATE` (`:175`), `BUILTIN_CASE_MAP` (`:1153`) — comments included. Two of them carry comments containing the literal `general-purpose` (`:158`, `:1151`), and AC#8's grep does not reach zero until those go.
- `LINT_SUPPRESS_RE` (`:1256`) and every `<!-- opencode-sync: ok -->` call site.
- `build_agent_config()` (`:1042-1077`) and `_config_json_pins()` (`:1686-1722`) (FR#17).

**2. Rewrite, do not remove.**

- **`check_variant_names()` (`:1725-1772`) is narrowed.** Its docstring names three subjects and only one dies. Drop the `_config_json_pins()` cross-check and the model-pin arm of `_agent_variant_errors()` (`:1775-1832`) that depends on it. Keep the `TIER_MAP` and frontmatter arms, keep `OPENCODE_VARIANTS` (no other consumer), and keep `run_lint()`'s call at `:1848`.
- **`check_source_dispatch_patterns()` (`:2024-2091`) is reimplemented (FR#21).** It currently stages a scratch tree, calls `rewrite_all_dispatches(scratch, dry_run=False)` and `process_agent_frontmatter(scratch, ...)`, then `run_lint(scratch)`. With no rewriter, that whole method is gone. It becomes a direct assertion over source: every dispatched agent name has a file in `agents/`, and no raw model clause remains (FR#18). No scratch tree, no rewrite pass, no reuse of the deleted regexes. Note the `OPENCODE_EXCLUDED_RULES` staleness check at `:2086` lives *inside* this function, so it rides along with the rewrite rather than surviving independently.
- **`_lint_content()` (`:1562-1650`) loses its dispatch-residue checks (FR#22).** It deliberately reuses the five deleted regexes so "the lint's notion of 'a residual dispatch' can't drift from what the rewriter actually rewrites" — that reasoning dies with its subject. Keep the rules-glob check and the `isolation: "worktree"` / `run_in_background` warnings (`:1643-1650`).
- **`TIER_MAP`** survives in reduced form — `OPENCODE_VARIANTS` and the model identifiers are still needed — but its `worker` / `worker_description` / `builtins` fields become dead.

**3. Add the orphan check (FR#25).**

A check that fails when `bin/opencode-sync` contains a module-level definition whose name appears only once in the file (i.e. on its own definition line). Enumerating deletions by hand has repeatedly missed one; this replaces a longer list with a mechanism. Wire it as a prek hook following the shape at `prek.toml:114-121`. It must report zero against the pre-change file, and must report a stranded private helper if a function is removed but its helper is not.

**4. Adapt the tests.**

Delete tests whose subject is a Replacement Target: worker generation, opus-variant generation, dispatch rewriting, `resolve()` routing, regex matching, config-level agent pinning. `rewrite_dispatches_prose` has direct unit tests at `tests/test_opencode_sync.py:1184,1194,1200` that go with it. The twelve `test_check_variant_names_*` tests are **adapted** — only the cases asserting on `config.json` pins lose their subject. Losing the frontmatter-variant cases would drop coverage of the #514 failure mode.

Add coverage for the reimplemented `--check-source` (fails on a dispatch naming a nonexistent agent, passes on a valid name) and the orphan check.

## Focus

**The deletion list's non-obvious dependencies run in the opposite direction from the orphan check.** FR#25's check catches a *deleted* symbol's helper going unreferenced. It does not catch the reverse — a **surviving** function still calling something the deletion wave removed. `run_lint()` has that shape twice. Re-read every surviving caller's body against the post-deletion symbol set; do not rely on the orphan check to find this class.

**Three helpers look like rewriter internals and must survive:**
- `_walk_synced_md_files()` (`:1497-1519`) — reads as a rewriter helper because `rewrite_all_dispatches` calls it at `:1532`, but `_lint_targets()` calls it too (`:1552`), and `_lint_targets` survives to feed the reduced `_lint_content`. Its own docstring says so at `:1505`.
- `_split_eol` (`:1306`) — still used by `process_agent_frontmatter` at `:605`/`:612`.
- `_split_frontmatter` (`:534`) — still used by `process_agent_frontmatter` and `generate_skill_commands` at `:982`.

**`FRONTMATTER_MODEL_RE` (`:1239`) must stay.** It looks like a sixth dispatch regex and is not — it is load-bearing for `process_agent_frontmatter()` (used at `:605`, `:628`), which survives and remaps a synced agent's Claude tier name to an OpenCode model ID. Removing it raises `NameError`. The other surviving `re.compile()` constants are also unrelated to dispatch: `OPKG_SUCCESS_PATTERN`, `OPENCODE_COMMAND_RE`, `ISOLATION_WORKTREE_RE`, `RUN_IN_BACKGROUND_RE`.

**Do not delete `check_variant_names()`, however obvious it looks.** It guards against an agent silently losing its variant — the same failure the `effort` → `variant` fix closed, which is bug #514. The design's own Architecture argument cites #514 as the evidence that OpenCode discards unknown config keys silently. Deleting the guard against the exact failure mode the design argues from would be a regression, and `bin/opencode-variant-audit` is a runtime observation tool, not a commit-time gate. AC#26 checks specifically that this guard still fires.

**AC#8 is an exhaustive symbol list** and includes both a must-be-absent set and a must-still-be-present set. Run it as written rather than eyeballing the diff.

**Behavioral invariant:** `--check`, `--dry-run`, `--check-source`, and `--lint-only` all continue to exist as CLI entry points and exit 0 on a clean tree. Their implementations change substantially and what they report is deliberately reduced — the invariant is about the interface, not the checks behind it.

**Observability gap, already accepted:** no integration layer exists for observing OpenCode startup with Claude fallback disabled, so FR#17's removal of config-level agent pinning is verified by source reading plus post-merge observation, not by an automated test. Do not invent a test that claims to cover it.

## Verify

- [ ] FR#14: `bin/opencode-sync` contains no `generate_worker_agents` definition or call.
- [ ] FR#15: `bin/opencode-sync` contains no `generate_specialist_opus_variants` definition or call.
- [ ] FR#16: `bin/opencode-sync` contains no dispatch-rewriting function and none of the five dispatch-translation regex constants.
- [ ] FR#17: `bin/opencode-sync --dry-run` emits a `config.json` with no `agent` key, and `build_agent_config` / `_config_json_pins` are absent.
- [ ] FR#18: `bin/opencode-sync --check-source` exits non-zero when a dispatch names an agent with no file in `agents/`.
- [ ] FR#21: `check_source_dispatch_patterns` stages no scratch tree, calls no rewriter, and reuses none of the deleted regexes.
- [ ] FR#22: `bin/opencode-sync --lint-only` reports no dispatch-pattern or `config.json` agent-pin checks and exits 0 on a clean tree.
- [ ] FR#25: The orphan check reports zero module-level definitions in `bin/opencode-sync` whose name appears only once in the file.
- [ ] AC#8: `grep -c 'general-purpose' bin/opencode-sync` returns 0 including comments; every symbol AC#8 marks for removal is absent; and `FRONTMATTER_MODEL_RE`, `process_agent_frontmatter`, `_walk_synced_md_files`, `_lint_targets`, `check_variant_names`, `_agent_variant_errors`, and `OPENCODE_VARIANTS` are all still present, with `check_variant_names` still called at `run_lint()`.
- [ ] AC#9: `bin/opencode-sync --dry-run` emits a `config.json` containing no `agent` key.
- [ ] AC#10: Adding a dispatch naming a nonexistent agent to a scratch skill file makes `bin/opencode-sync --check-source` exit non-zero.
- [ ] AC#16: `grep -n 'rewrite_all_dispatches\|SUBAGENT_TYPE_RE\|MODEL_RE' bin/opencode-sync` returns no matches inside `check_source_dispatch_patterns` or `run_lint`.
- [x] AC#17: `bin/opencode-sync --lint-only` exits 0 against the current install and its output references no dispatch-pattern or `config.json` agent-pin checks. **CONTESTED — accepted 2026-08-17.** This machine's live `~/.config/opencode` install carries stale `worker-*.md` files from a pre-migration sync, previously rescued by the now-deleted `config.json` agent-pin cross-check (FR#17). That machine state predates this task and is outside code scope; against a clean synthetic tree the check exits 0, and the design's Test Strategy names this exact gap as accepted (source reading + post-merge observation, not an automated test). Resolved by a real sync run later, not by this task.
- [ ] AC#21: The orphan check reports zero module-level `def`s and `CONSTANT =` bindings whose name appears only once; run against the pre-change file it reports zero; run after removing a function but not its private helper it reports that helper.
- [ ] AC#26: Writing an unresolvable `variant:` into a synced agent file, or removing its `variant:` line entirely, still makes `bin/opencode-sync --lint-only` exit non-zero naming that agent.
