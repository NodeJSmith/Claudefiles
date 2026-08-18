---
task_id: "T06"
title: "Update documentation and amend the roadmap"
status: "done"
depends_on: ["T05"]
implements: ["AC#17"]
---

## Summary

Bring every document describing the old sync into line with what now exists, and record the roadmap invariants this design deliberately breaks rather than leaving them silently violated. Five of these files were found by the planning gap check and are not in the design doc's Documentation Updates list; they are called out individually below because each contains a specific claim that becomes false.

Nothing in this task changes behavior. Its gate is `prek run --all-files`.

## Target Files

- modify: `design/opencode-integration-roadmap.md`
- modify: `REFERENCE.md`
- modify: `ONBOARDING.md`
- modify: `install.py` (comment only)
- modify: `rules/common/performance.md`
- modify: `bin/opencode-variant-audit`
- modify: `skills/mine-write-skill/REFERENCE.md`
- read: `skills/mine-write-skill/SKILL.md` (line 51 — check whether its wording needs the same fix; it likely does not)
- read: `design/specs/1007-opencode-config-plugin/design.md` (Documentation Updates; Dependencies and Assumptions)
- read: `bin/opencode-sync`
- read: `opencode/claudefiles.ts`

## Prompt

**`design/opencode-integration-roadmap.md` — the substantive one.**

Three invariants are now deliberately false, and the design's position is that they get amended rather than quietly violated:
- `:53` — "The OpenCode output must be valid on its own. It must not rely on OpenCode silently falling back to files under `~/.claude`."
- `:236` — "OpenCode artifacts must work with Claude fallback disabled."
- `:90-92` (**gap-check find, not in the design's Documentation Updates**) — "Tests must isolate OpenCode from Claude fallback… Otherwise, a test may pass because OpenCode loaded the original Claude artifact rather than the generated OpenCode artifact." This is the same invariant expressed as a testing requirement, and amending only the first two would leave the roadmap self-contradictory.

Amend all three to record that OpenCode now intentionally reads the shared install at `~/.claude`, carrying the design's three grounds: the fallback is already how 37 skills reach OpenCode today; the invariant's stated purpose was preventing a *copy* from concealing broken generation, and there is no copy left to conceal anything; and reading `~/.claude` is the only way to get Dotfiles' contribution (eleven skills, all five personal rules). For `:90-92` specifically, note that the isolation requirement inverts — a test that disabled Claude fallback would now be testing something the design depends on, so the meaningful check is `--verify`, not fallback-disabled isolation.

Also:
- Mark Workstream 4's deferred personal-rules decision (`:194`) **resolved**: `cfg.instructions` points at the Claude install's copy, which is the second of the two options that entry framed.
- Note that the Minimum Supported Workflows per-skill exclusion requirement (`:106`) now has **no mechanism** — going to a native scan forecloses staging-time filtering. Name Workstream 3's skill-classification bullet (`:165`) as what would produce the list it needs, and the curated-symlink-farm option from the design's Alternatives Considered as the way back.
- `:146` — its Workstream 2 correction says model and variant enforcement "live entirely in each agent's own **synced** frontmatter." Nothing is synced after this; frontmatter is read live and transformed in memory. Reword rather than leave a stale authoritative record.
- Update the Current State bullets (`:9-22`) that describe staging and remapping.
- `:25` establishes `bin/opencode-sync` as the supported control plane for "generating, installing, upgrading, and pruning." It keeps that role but the verbs change — bootstrap, prune, verify. Worth a light touch so the sentence still describes the command.

Leave `:74-78` ("Unsupported guarantees must fail visibly") alone. The design's accepted silent-plugin-failure edge case sits in tension with it, but the tension is real and named, and `--verify` plus the bootstrap tail is the answer to it. Do not soften the principle to fit.

**`REFERENCE.md`** — the `opencode-sync` table row (`:242`) and the whole `### OpenCode Sync` section (`:251-288`). Nearly all of it describes machinery that no longer exists: staging, opkg, `process_agent_frontmatter()`, wrapper generation, `--check`, `--lint-only`, `check_variant_names()`, `INSTRUCTION_DIRS`, the three-entry `OPENCODE_EXCLUDED_RULES`. Rewrite for the new shape: the plugin file, the shared data file, the compatibility rule as a repo file, the new commands, and the **process-not-session** restart granularity. Keep the `opencode-variant-audit` row (`:243`) and the `opencode.db` query section (`:265-288`), correcting their references to `--lint-only`.

**`ONBOARDING.md`** (`:207-221`) — that OpenCode support is now a plugin reading the Claude install, and that `install.py` is a **prerequisite** for OpenCode rather than only for Claude Code. The `--lint-only` example at `:216` and the claim at `:219` that "OpenCode can also discover the original Claude artifacts, so apparent success does not yet prove the generated OpenCode copy is self-sufficient" both need rewriting — the second is now backwards, since discovering the Claude artifacts is the mechanism, not a confound.

**`install.py`** — a comment where it writes `~/.claude/{agents,skills,rules}` noting that `opencode/claudefiles.ts` reads that output directly, so the directory layout and frontmatter shape are a two-consumer contract rather than a Claude-Code-only detail. **Comment only — no behavior change.** `install.py` already produces everything the plugin reads; what changes is what breaking it costs.

**Gap-check finds — each contains a specific claim that becomes false:**

- `rules/common/performance.md:17,19` — says `opencode-sync`'s `process_agent_frontmatter()` rewrites `effort:` → `variant:` during sync, and that "raising a tier's reasoning level for OpenCode means editing `TIER_MAP`, not the agent files." Both false: the function is deleted and `TIER_MAP` now lives in `opencode/config-data.json`, applied by the plugin at process start. This one matters more than ordinary doc drift — FR#7 drops this file from the exclusion list, so OpenCode now *reads* it and would be acting on stale instructions about its own configuration.
- `bin/opencode-variant-audit` — `:8` and `:108` reference `opencode-sync --lint-only` (removed); `:103` and `:108` reference "opencode-sync's `OPENCODE_VARIANTS`" (moved to the shared data file); `:176` prints remediation text "Re-run opencode-sync, then start a NEW OpenCode session", which no longer describes anything — there is no re-sync, and the correct remedy is restarting the OpenCode **process**. Update the docstrings and that user-facing string. The tool's actual logic is unaffected.
- `skills/mine-write-skill/REFERENCE.md:40` — "`opencode-command: true` generates a thin OpenCode slash-command bridge." The bridge is now an in-memory `cfg.command` entry, not a generated file. One-line wording fix. `skills/mine-write-skill/SKILL.md:51` describes the same thing accurately enough ("a dedicated OpenCode `/mine-<name>` bridge") and needs no change — check it rather than assuming.

**Do not add a `CHANGELOG.md` entry.** Repo convention puts changelog entries at PR creation, where the full branch diff is known; `mine-create-pr` handles it.

**Do not comment on issues #500, #501, or #517.** The design lists that under Documentation Updates, but it is an outward-facing action on a third-party tracker and belongs with the PR, not with a task file's execution.

## Focus

Read the current text of every file before rewriting it. Several of these sections are long, carefully argued, and contain reasoning that survives the change even where the mechanism does not — `REFERENCE.md:258`'s explanation of why `tool:` frontmatter is the wrong filter for OpenCode exclusion is still exactly right, as is `:257`'s account of why there is no `agent` key. Preserve the arguments; replace the mechanisms.

The house convention for `docs`-type changes: rules, SKILL.md, and agent prompt changes are `docs`, not `feat`/`refactor`. That matters for the eventual commit message, and it also means `rules/common/performance.md` and `skills/mine-write-skill/REFERENCE.md` are instruction files — they get instruction-mode review, not a pass because "it's only docs."

Watch for AI-prose tells in the roadmap amendments specifically, since they are the longest new prose in this spec: em dashes standing in for real connectives, hedging, and significance inflation. The roadmap's existing voice is declarative and unhedged; match it.

Do not update `REFERENCE.md`'s component tables for anything other than `opencode-sync` and `opencode-variant-audit`. No agents, skills, or bin scripts are added or removed by this spec — `opencode/claudefiles.ts` is a plugin, not a `bin/` script, and belongs in the OpenCode Sync section rather than the CLI tools table.

Gap-check items this task addresses: gaps 1, 2, 3, and 4.

## Verify

- [ ] AC#17: `prek run --all-files` exits 0 with every documentation file staged.
