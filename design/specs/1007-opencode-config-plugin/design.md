# Design: OpenCode Config Plugin — Runtime Generation from the Live Install

**Date:** 2026-08-17
**Status:** approved
**Scope-mode:** hold
**Research:** `design/research/2026-08-16-opencode-plugin-viability/research.md` (Track 2; its Track 1 half stays out of scope)

## Problem

`bin/opencode-sync` delivers Claudefiles to OpenCode by copying files to disk: it stages a clean tree, invokes OpenPackage, rewrites agent frontmatter in place, generates skill-command wrappers, writes `config.json`, and then maintains a sync-state file so it can tell whether any of that went stale. Most of the script exists to make those disk writes safe rather than to decide anything.

Three concrete problems, all observed on the live install rather than inferred:

**The synced skills are worse than not syncing at all.** OpenCode natively scans `~/.claude/skills/**/SKILL.md` (`skill/index.ts:187-193`). Claudefiles symlinks its skills there, so OpenCode already sees them live. The sync then installs a *second* copy under `~/.config/opencode/skills/`, and `skill/index.ts:125-134` logs a duplicate-name warning and **overwrites** — last write wins, so the copy shadows the live symlink. A live run resolves 79 skills — 78 from disk plus OpenCode's built-in `customize-opencode` — with **41 duplicate-name warnings**, and for all 41 the winner is the potentially-stale copy. Meanwhile the 37 skills the sync does not deliver reach OpenCode *only* through that native scan: every `cli-*`, every `i-*`, the eleven Dotfiles-sourced skills (`mine-gog`, `mine-kimai`, `mine-ha-api`, `mine-paperless-api`, `mine-banfield-api`, `mine-otf-api`, `mine-listonic-api`, `mine-karakeep-api`, `mine-monarch-api`, `mine-dotcheck`, `mine-gmail-filter`), and `codebase-memory`, which is a real directory rather than a symlink — installed by the third-party codebase-memory-mcp tool, owned by neither repo.

**Generated artifacts outlive their source.** `~/.config/opencode/agents/` currently holds 33 agents against 26 real ones. The extra seven — `worker-lightweight`, `worker-standard`, `worker-opus`, and four `engineering-*-opus` — are generation output from before spec 1008 deleted the machinery that produced them. They are still discoverable and still dispatchable, pinned to a tier vocabulary that no longer has a source.

**Personal rules never arrive.** `~/.claude/rules/personal/` (five files symlinked from Dotfiles) is not staged and not covered by `instructions`. `design/opencode-integration-roadmap.md:194` deferred the decision on how to wire it, framing the choice as "`opencode-sync` grows a cross-repo staging source, or `instructions` points directly at the Claude install's copy."

Spec 1008 already removed the largest reason the copy-to-disk design existed: with every dispatch naming a real agent file, there is no dispatch syntax left to translate, so nothing has to be rewritten on the way across. What remains is transport.

## Goals

- Editing any skill, agent, or rule takes effect in the next OpenCode **process** with no sync command. Probe-verified granularity: `config()` runs once per process, so a new session attached to an already-running `opencode serve` does *not* pick up edits — see Dependencies and Assumptions. For the TUI daily driver each invocation is a new process, so this is the ordinary case; for `serve`/`attach` workflows it means restarting the server, not just opening a session.
- Every agent resolves with the correct model and reasoning variant, observable in `opencode.db` via `bin/opencode-variant-audit` reporting `fell_back: 0`.
- Personal rules from Dotfiles reach OpenCode, closing roadmap `:194`. (Dotfiles-sourced *skills* already arrive today via the native scan — this change stops the sync from shadowing them, but it is not what `:194` deferred.)
- Startup produces no duplicate-skill warnings, and no agent exists in OpenCode without a source file.
- `bin/opencode-sync` sheds every function whose only purpose is making a disk write safe.

## Non-Goals

- Track 1 runtime hook parity (`additionalContext`-style injection, porting `scripts/hooks/*.sh` to plugins). Deferred; it is what would make `sudo.md` correct for OpenCode.
- `chat.params` for reasoning effort. Its signature (`packages/plugin/src/index.ts:247-256`) exposes only `temperature`, `topP`, `topK`, `maxOutputTokens`, `options` — it cannot reach `variant`, which resolves from agent config in `session/prompt.ts:654`. The research brief's claim that it is "a strictly more robust fix for the effort/variant bug class" does not hold.
- Any `experimental.*` hook.
- Adopting `oh-my-opencode-slim`, and its `customAppendPrompt` pattern.
- Executing KI-002 (#500), KI-003 (#501), or #517. This change removes much of their subject matter; see Dependencies and Assumptions.
- `tool.execute.after` skill-content rewriting. The research brief scoped this as Track 2's path into roadmap Workstream 3; spec 1008 removed the need entirely, and skills are confirmed to reach OpenCode unrewritten today and work.

## User Scenarios

### Jessica: Sole developer and operator of this configuration

- **Goal:** Change a skill, agent, or rule once and have both harnesses pick it up.
- **Context:** Editing in `~/Claudefiles` or `~/Dotfiles`, running both Claude Code and OpenCode on `jessica-desktop`.

#### Editing shared content

1. **Edit a skill, agent, or rule**
   - Sees: the file in its repo, as today
   - Decides: nothing new
   - Then: no sync step exists to forget

2. **Start OpenCode**
   - Sees: the edited content in effect
   - Decides: nothing
   - Then: the plugin reads the live install during process startup. For the TUI each invocation is its own process, so this is just "open OpenCode"; against a long-lived `opencode serve`, a new session is not enough and the server must be restarted

#### Verifying the wiring after a change to the plugin itself

1. **Run the verification command**
   - Sees: pass/fail naming the agent it probed
   - Decides: whether to investigate
   - Then: a silently-unloaded plugin fails loudly instead of yielding an agent-less session

## Functional Requirements

- **FR#1** A plugin registered in OpenCode's global config populates `cfg.agent` at session start from the agent files installed under `~/.claude/agents/`.
- **FR#2** Each generated agent entry carries a provider-qualified model ID and a reasoning `variant`, resolved from the agent's Claude tier name through `TIER_MAP`.
- **FR#3** An agent's prompt is that agent file's body, and its description is that agent file's `description` frontmatter field.
- **FR#4** The plugin populates `cfg.command` with one entry per skill whose frontmatter declares `opencode-command: true`, discovered from the skills installed under `~/.claude/skills/`.
- **FR#5** The plugin populates `cfg.instructions` with the rule files installed under `~/.claude/rules/common/` and `~/.claude/rules/personal/`, as explicit file paths.
- **FR#6** Rules named in the exclusion list are absent from `cfg.instructions`.
- **FR#7** The exclusion list contains exactly one entry, `common/sudo.md`.
- **FR#8** An exclusion entry that matches no file fails `--check-source` at commit time rather than silently widening what reaches OpenCode. The check runs against the repository's own `rules/` tree, not inside the plugin — exceptions raised in a plugin's `config()` hook are caught and discarded by OpenCode (`plugin/index.ts:243-251`, `Effect.ignore`), so a plugin-side throw cannot surface a failure to anyone.
- **FR#9** The OpenCode compatibility rule reaches `cfg.instructions` alongside the shared rules.
- **FR#10** The compatibility rule states the mapping from Claude MCP tool names (`mcp__<server>__<tool>`) to OpenCode's (`<server>_<tool>`).
- **FR#11** `bin/opencode-sync` no longer stages a copy of the repository.
- **FR#12** `bin/opencode-sync` no longer invokes OpenPackage.
- **FR#13** `bin/opencode-sync` no longer installs skills, agents, or rules to disk.
- **FR#14** `bin/opencode-sync` no longer rewrites agent frontmatter.
- **FR#15** `bin/opencode-sync` no longer writes skill-command wrapper files.
- **FR#16** `bin/opencode-sync` no longer maintains sync-state, staleness detection, or foreign-config detection.
- **FR#17** The generated `config.json` declares `$schema`, the plugin, and `subagent_depth`, and nothing else.
- **FR#18** A machine-local `opencode.jsonc` is never read, written, or moved by this change.
- **FR#19** `bin/opencode-sync --prune` removes the previously-installed skill, agent, command, and rule trees from the OpenCode config directory.
- **FR#20** `bin/opencode-sync --verify` exits non-zero when any agent file under `~/.claude/agents/` fails to resolve in OpenCode, naming every one that failed. An optional agent name narrows it to a single check.
- **FR#21** `bin/opencode-sync --check-source` and `--check-orphans` continue to exist and to gate commits. `--check` is removed along with the staleness it reported — with live reads there is no stale state for it to detect, and `--verify` answers the question that replaces it.
- **FR#22** The plugin source is version-controlled in this repository and reaches the OpenCode config directory by symlink, so editing it needs no reinstall.
- **FR#23** The compatibility lint over installed files, and its `--lint-only` entry point, are removed; the platform-semantics warnings it carried (`isolation: "worktree"`, `run_in_background`) are scanned against repository source by `--check-source` instead.
- **FR#24** No module-level definition in `bin/opencode-sync` is left without a caller after the removals land.
- **FR#25** `bin/opencode-sync --bootstrap` writes `config.json` and symlinks the plugin and the compatibility rule into the OpenCode config directory, and is idempotent across repeated runs.
- **FR#26** `--bootstrap` runs the full verification sweep (FR#20) as its final step, so the one moment the plugin is guaranteed to have just changed ends in a pass/fail the developer sees.
- **FR#27** The values both sides need — the tier→model/variant map, the allowed variant names, the rule-exclusion list, the skill-command template, and the instruction-directory list — live in one version-controlled data file that the Python script and the TypeScript plugin each read directly. Neither hand-copies the other's values. The instruction-directory list is shared for the same reason as the rest: the plugin emits `cfg.instructions` from it and `--check-source`'s coverage check validates against it, so a hand-copy on either side would let the two disagree silently.
- **FR#28** A pre-commit hook runs `--verify` when `opencode/claudefiles.ts` or the shared data file changes, so a plugin regression fails the same gate the Python side already has. It is scoped to those files rather than `always_run`, because it starts an OpenCode process and is too slow for every commit.

## Edge Cases

- **The plugin fails to load, or throws inside `config()`.** OpenCode swallows both. A load failure is logged and discarded (`plugin/index.ts:222-238` — `Effect.catch(() => Effect.void)`, with the session-event publish commented out under `// TODO: make proper events for this`); a `config()` hook failure is logged and discarded too (`:243-251`, `Effect.ignore`). The session then starts normally with no Claudefiles agents at all — worse than today, where stale files still resolve, and **silent by default**. Nothing the plugin does can change this: it cannot raise a failure anyone will see. Detection is therefore external and explicit — FR#20's `--verify`, run automatically at the end of every `--bootstrap` (FR#26) and manually after an `opencode upgrade`. This is a real weakening versus static files, accepted because the failure is loud the moment `--verify` runs and bootstrap is when breakage is most likely introduced.
- **Seven orphaned agents are installed right now.** `worker-lightweight`, `worker-standard`, `worker-opus`, and four `engineering-*-opus` are present in `~/.config/opencode/agents/` with no source. FR#19 removes them; without it they survive as dispatchable ghosts and can shadow plugin-injected names of the same spelling.
- **A bundle is not installed.** `~/.claude/` contains only the bundles `install.py` selected, so an unselected bundle yields no skills or agents to OpenCode. This is a semantic change from staging the whole repo, and it is the intended behavior: the two harnesses should agree on which bundles are active.
- **`--prune` deletes hand-authored OpenCode-native content.** It removes those four directories wholesale, unlike `generate_skill_commands()` (`bin/opencode-sync:764-767`), which only deleted marker-tagged files and explicitly preserved source commands. That is safe **on the assumption that `~/.config/opencode/{agents,skills,commands,rules}` is 100% generated output today** — confirmed by the agent accounting in Problem (33 installed against 26 real). Recorded because nothing enforces it: OpenCode natively scans those same directories for user-authored content, so a hand-dropped native agent added *after* this ships would be indistinguishable from generated output and silently deleted by a later `--prune`. If that ever becomes a real workflow, `--prune` needs marker-based selectivity or a dry-run default.
- **A symlink dangles.** If `~/Claudefiles` or `~/Dotfiles` moves, entries under `~/.claude/` break. Skills degrade quietly (OpenCode's glob skips them); agents would produce an entry with an empty prompt, so the plugin skips any agent file it cannot read rather than emitting a malformed entry.
- **The exclusion entry is renamed.** `sudo.md` moving or being renamed silently re-admits it. FR#8 keeps the existing matched-nothing check.
- **A rule is added to a new subdirectory under `~/.claude/rules/`.** FR#5 names two directories explicitly; a third would be missed. The existing `check_instruction_globs()` coverage check is retargeted rather than deleted.
- **`git pull` lands mid-session-start.** A file can be read while being rewritten. The window is narrow, the failure is one malformed read, and the recovery is a restart. Accepted without mitigation.
- **`~/.config/opencode/AGENTS.md` suppresses `~/.claude/CLAUDE.md`.** Confirmed harmless here: `CLAUDE.md` is ten lines containing only the CodeGraph block, and `AGENTS.md` already contains that block verbatim — it is a superset. Both are third-party installer output (codebase-memory-mcp, codegraph); neither is Claudefiles-managed, and this design does not touch either.
- **A skill and an agent share a name.** Not possible to collide in config: they populate different keys (`cfg.command` vs `cfg.agent`).

## Acceptance Criteria

- **AC#1** With the plugin active, `opencode debug agent <name>` resolves for every file in `~/.claude/agents/`, and its output shows a `providerID`/`modelID` pair and a `variant` rather than a bare Claude tier name. (FR#1, FR#2, FR#3)
- **AC#2** `opencode debug agent <name> --pure` fails for the same agent, proving the entry came from the plugin and not from a file on disk. (FR#1, FR#13)
- **AC#3** `GET /command` on a running `opencode serve` returns one entry per skill declaring `opencode-command: true`. (FR#4)
- **AC#4** `opencode debug config` lists every non-excluded file under `~/.claude/rules/common/` and `~/.claude/rules/personal/` in `instructions`, and does not list `sudo.md`. (FR#5, FR#6, FR#7)
- **AC#5** Renaming `rules/common/sudo.md` in a scratch copy of the repo makes `--check-source` exit non-zero naming the unmatched exclusion entry. (FR#8)
- **AC#6** The compatibility rule's path appears in `instructions`, and the file contains the `mcp__<server>__<tool>` → `<server>_<tool>` mapping. (FR#9, FR#10)
- **AC#7** `grep -c 'opkg\|OPKG' bin/opencode-sync` returns 0, and every function named "remove outright" in Replacement Targets is absent from the file: `stage_config`, `run_opkg`, `_run_opkg_best_effort`, `opkg_list_includes_claudefiles`, `uninstall_previous`, `process_agent_frontmatter`, `generate_skill_commands`, `build_instructions`, `check_sync_status`, `load_sync_state`, `write_sync_state`, `_empty_sync_state`, `_sha256_file`, `handle_foreign_config`, `_atomic_write_json`, `check_variant_names`, `_agent_variant_errors`, `run_lint`, `report_lint`, `lint_only`, `_lint_targets`, `_lint_content`, and `_walk_synced_md_files`. (FR#11–FR#16, FR#23)

  This list names *direct* removals only. It is deliberately not the completeness check — enumerating transitive fallout by hand is what produced the `_atomic_write_json` mismatch this design already had to fix once. AC#18 owns completeness.
- **AC#8** The generated `config.json` parses as JSON whose top-level keys are exactly `$schema`, `plugin`, and `subagent_depth`. (FR#17)
- **AC#9** A pre-existing `opencode.jsonc` is byte-identical before and after running the sync command. (FR#18)
- **AC#10** After `--prune` runs against a scratch OpenCode config dir seeded with the current install, no `agents/`, `skills/`, `commands/`, or `rules/` directory remains under it. (FR#19)
- **AC#11** `--verify` with no argument checks every file in `~/.claude/agents/` and exits zero; with one agent file made unreadable it exits non-zero naming that agent. With an explicit name it checks only that one. (FR#20)
- **AC#12** `bin/opencode-sync --check-source` and `--check-orphans` both exit 0 against the migrated tree, both remain wired in `prek.toml`, and `--check` is no longer an accepted flag. (FR#21)
- **AC#13** The plugin source file in the repo and `~/.config/opencode/claudefiles.ts` resolve to the same inode. (FR#22)
- **AC#14** Starting an OpenCode session emits no `duplicate skill name` warnings.
- **AC#15** `bin/opencode-variant-audit --json` reports `fell_back: 0` across a dogfooded session's dispatches.
- **AC#16** `timeout 300 pytest tests/` passes with zero failures.
- **AC#17** `prek run --all-files` passes.
- **AC#18** `bin/opencode-sync --check-orphans` exits 0 against the migrated file, catching any helper left callerless by the removals — including the transitive cases AC#7 does not enumerate, such as `_split_eol` and `_atomic_write_text`, whose only callers today sit inside removed functions. `_atomic_write` itself must still be present — it acquires the config writer as a direct caller. (FR#24)
- **AC#19** `bin/opencode-sync --lint-only` no longer exists as a flag, and `--check-source` reports on `isolation: "worktree"` and `run_in_background` occurrences across the same three directories it already scans — `skills/`, `commands/`, `agents/` (`check_source_dispatch_patterns()`, `bin/opencode-sync:1252`; its directory tuple is at `:1301`). Every current occurrence lives in `skills/` (`mine-visual-qa/SKILL.md`, `mine-challenge/SKILL.md`, `mine-issues-triage/SKILL.md`, `mine-orchestrate/post-execution-pipeline.md`), so the relocated check needs no scan-scope change; deliberately **not** extended to `skills-cli/` or `skills-impeccable/`, since widening an already-shipped check's scope would also widen its unrelated dispatch-name enforcement. (FR#23)
- **AC#20** Running `--bootstrap` twice against a scratch OpenCode config dir leaves `config.json`, the plugin symlink, and the compatibility-rule symlink identical after the second run as after the first. (FR#25)
- **AC#21** `--bootstrap` against a config dir whose plugin symlink points at a deliberately broken file exits non-zero, and its output names the agent that failed to resolve. (FR#26)
- **AC#22** Neither `bin/opencode-sync` nor `opencode/claudefiles.ts` contains a literal copy of any value the shared data file owns: `grep -c 'gpt-5\.6\|sudo\.md' ` returns 0 for both, and neither file defines a tier map, variant-name set, exclusion list, command template, or instruction-directory list as a literal — each loads them from `opencode/config-data.json`. The grep covers the two greppable values; the other three are checked by reading the files. (FR#27)
- **AC#23** All three tiers resolve to distinct, specific triples matching the shared data file: `opus` → `openai/gpt-5.6-sol`, `sonnet` → `openai/gpt-5.6-terra`, `haiku` → `openai/gpt-5.6-luna`, each at `variant: high`. Asserted per-tier, not just as "some `providerID`/`modelID` pair resolved". (FR#2, FR#27)
- **AC#24** `prek.toml` contains a hook whose `entry` invokes `--verify` and whose `files` pattern matches `opencode/claudefiles.ts` and the shared data file, and it does not set `always_run = true`. (FR#28)

## Key Constraints

- **Do not read `~/Claudefiles` or `~/Dotfiles` directly.** The plugin reads `~/.claude/`, which is the union of both repos as installed. Reading either repo directly loses the other's contribution — Dotfiles owns eleven of the skills OpenCode currently gets and all five personal rules.
- **Do not reintroduce a copy of shared content under `~/.config/opencode/`.** A second copy of a skill or agent is what produces the duplicate-name shadowing this change removes.
- **Do not set `cfg.skills.paths` from the plugin.** Probe-verified as racy (see Dependencies and Assumptions). Skills need no config at all — OpenCode's native scan already delivers them.
- **Do not manage `opencode.jsonc`.** It is the machine-local overlay for `permission` and `mcp`, owned by the user, and `loadGlobal()` already merges it last so it wins over generated content (`config/config.ts:258-260`).
- **Do not rewrite skill or rule content.** Translation is the compatibility rule's job, performed by the model at read time. Spec 1008 established this and it is confirmed working.

## Dependencies and Assumptions

- **`config()` mutation reaches `cfg.agent` and `cfg.command`, and does not reach `cfg.skills.paths`.** Probe-verified on OpenCode 1.18.18 against an isolated config dir (`XDG_CONFIG_HOME`), each observation taken from the consuming *service* rather than the config object, with a `--pure` control run:

  | Surface | Observation surface | With plugin | `--pure` |
  |---|---|---|---|
  | `cfg.agent` | `opencode debug agent` | resolves, 8/8 runs, with `providerID: openai`, `modelID: gpt-5.6-luna`, `variant: high` — the probe agent was declared with that model directly, so this shows an injected provider-qualified model and variant being honored, not a tier lookup | 0/8 |
  | `cfg.command` | `GET /command` (backed by `Command.Service`) | present, 4/4 runs | 0/4 |
  | `cfg.skills.paths` | `opencode debug skill` | absent in all but one of ~16 runs, with the hook confirmed firing on every run | absent |

  The `skills.paths` failure is **racy, not deterministic** — one run in roughly sixteen did pick it up, and skill counts varied run to run. A surface that works occasionally is more dangerous than one that never works, which is why FR-level design routes around it entirely rather than retrying.

- **The declared-dependency theory does not predict which surfaces work.** `Agent.node` lists `Plugin.node` in its deps (`agent/agent.ts:450`) and works; `Command.node` does not (`command/index.ts:175`) and works anyway; `Skill.node` does not (`skill/index.ts:351`) and does not work. The probe is the authority here, not the layer graph. Any future surface must be probed the same way before being relied on.

- **Propagation granularity is the process, not the session — probe-verified.** With a plugin edit made while `opencode serve` was running, a new request to the same server did not see the change (`probe-cmd-LATE` absent); killing the process and starting a fresh one with the identical plugin did (`probe-cmd-LATE` present). `config()` runs once during plugin-layer init and its result is cached per instance (`effect/instance-state.ts:26-40`, `ScopedCache` with `capacity: POSITIVE_INFINITY`). Because the plugin reads `~/.claude` *inside* `config()`, this applies equally to agent and rule edits, not just plugin edits. Consequence for the daily driver: TUI invocations are separate processes and behave as Goal #1 describes; a long-lived `opencode serve` needs a restart. Documented in ONBOARDING/REFERENCE rather than mitigated — no cache-invalidation hook is in scope.

- **`cfg.instructions` is assumed safe on weaker evidence than the other two.** `Instruction.systemPaths()` calls `cfg.get()` inside an `Effect.fn` invoked per message (`session/instruction.ts:110-113`), long after plugin init completes, so it is a call-time read rather than a layer-ordering question. This was **not** probed at the service level — it is carried by the Smoke Test instead.

- **A raw Claude tier name in an agent's `model:` field does not fail loudly.** `ConfigAgentV1.Info` types `model` as `Schema.optional(Schema.String)` with no format validation, and `Provider.parseModel()` splits on `/` (`provider/provider.ts:1997-2003`), so `"sonnet"` yields `providerID: "sonnet"`, `modelID: ""`. The tier remap is therefore load-bearing in any architecture — it is not legacy plumbing that live paths make unnecessary.

- **OpenCode depends on `install.py` having run.** This makes `design/opencode-integration-roadmap.md:53` ("must not rely on OpenCode silently falling back to files under `~/.claude`") and `:236` ("OpenCode artifacts must work with Claude fallback disabled") false as written. **Accepted deliberately**, on three grounds: the fallback is already how 37 skills reach OpenCode today; the invariant's stated purpose is preventing a *copy* from concealing broken generation, and there is no copy left to conceal anything; and reading `~/.claude` is the only way to get Dotfiles' contribution. The roadmap is amended rather than silently violated — see Documentation Updates.

- **`OPENCODE_DISABLE_CLAUDE_CODE_SKILLS` is deliberately not used.** It is an env var (`effect/runtime-flags.ts:27-30`), settable only from the shell profile — not from `config.json` and not from a plugin. Since this design stops producing a second copy, there is nothing to disambiguate and no reason to suppress the native scan.

- **`sudo.md` stays excluded, unlike the other two former entries.** `performance.md` and `tmux.md` are dropped from the list: `performance.md`'s stated rationale ("names the Claude model IDs this sync deliberately remaps") is stale after 1008 deleted its inline-model list and made its agent list generated, and the file explicitly discusses OpenCode's own `variant` mechanism; `tmux.md`'s `claude-tmux` is an ordinary shell script that works under either harness, and only its drift-check hook is Claude-only. `sudo.md` is different in kind: its instruction is "write `sudo` directly, the hook manages authentication," and with no hook firing the command hits a passwordless prompt with no TTY and **hangs**. That is an active failure, not an inapplicable paragraph. Revisit when Track 1 lands.

- **`mcp-tools.md` reaches OpenCode naming tools that do not exist there.** It documents `mcp__context7__*`; OpenCode builds `sanitize(client) + "_" + sanitize(name)` (`mcp/catalog.ts:119`), so the same tool is `context7_query-docs`. Context7 is also absent from the current `opencode.jsonc`. Handled by FR#10's compatibility-rule mapping rather than exclusion, because the mapping fixes every rule and skill naming a Claude MCP tool rather than this one file.

- **`capabilities.md` routes to `/ccr-recall`, which does not exist under OpenCode.** It is a Claude Code plugin skill, not a Claudefiles skill, so no bridge is generated for it. Known gap, accepted; the compatibility rule's "skip clearly inapplicable instructions" clause covers it.

- **The instruction-directory coverage check is repo-scoped, and `rules/personal` is therefore unverified.** `check_instruction_globs()` retargets to this repo's own `rules/` tree, which contains only `common/` — `rules/personal/` exists solely in `~/.claude` as five symlinks into Dotfiles. So the check proves a *Claudefiles*-side rules directory is covered by the shared instruction-directory list, and cannot see a directory Dotfiles adds. If Dotfiles grows `rules/<something-new>/`, its rules land on disk and never reach `cfg.instructions`, silently, until someone notices a rule isn't being followed. **Accepted rather than mitigated**, on the grounds that pointing the commit-time gate at a live install would break `check_source()`'s reproducible-on-a-fresh-checkout contract (`:1370-1385`), and that the alternative — extending `--verify` to sweep `~/.claude/rules/` — widens FR#20 beyond agents for a directory that has changed once in the project's history. Revisit if Dotfiles' rules tree starts moving.

- **OpenCode has no `@filepath` reference expansion.** `experimentalReferences` is declared in `effect/runtime-flags.ts` and referenced nowhere else; `session/instruction.ts` has no `@`-expansion logic. Recorded because it is a natural thing to reach for when composing instruction files, and it is not available.

- **KI-002 (#500), KI-003 (#501), and #517 should be updated, not executed.** All three concern `bin/opencode-sync`'s size and `main()`'s concerns. This change deletes most of their subject matter. Their filed resolutions should be paused pending the result.

- **`opencode upgrade` invalidates every probe result in this document.** The architecture rests on undocumented internal behavior of one build — including a `cfg.skills.paths` result that is *racy* rather than cleanly broken, and a hook-ordering outcome the declared-dependency graph does not predict. A patch release could flip any of it with no change on either side. Until the roadmap's deferred drift checks exist (`design/opencode-integration-roadmap.md:206`, Spec 5), the mitigation is procedural: run `--verify` after any OpenCode version bump. Named here so the next person upgrading knows this design has a stake in it.

- **The reference clone matches the installed binary.** `~/source/opencode` is at commit `3fd77ae`, `packages/opencode/package.json` reports `1.18.18`, and the installed binary reports `1.18.18`. One flag divergence was observed and worked around during probing: `OPENCODE_CONFIG_DIR` did not redirect `debug paths` output, so `XDG_CONFIG_HOME` was used for isolation instead.

## Architecture

### One plugin, three keys, one source of truth on disk

OpenCode already has a live, complete, correctly-merged copy of everything it needs: `~/.claude/`, produced by `install.py` from Claudefiles and by Dotfiles' own installer. Skills are already discovered from it natively. What is missing is that agents there carry Claude tier names OpenCode cannot parse, rules there are not wired into `instructions`, and skill-command bridges do not exist.

A plugin at `~/.config/opencode/claudefiles.ts` — a symlink to `opencode/claudefiles.ts` in this repo — supplies exactly those three things in memory at session start:

| Key | Built from | Transform |
|---|---|---|
| `cfg.agent` | `~/.claude/agents/*.md` | frontmatter `model:` tier → `TIER_MAP` model + variant; body → `prompt`; `description` passthrough |
| `cfg.command` | `~/.claude/skills/*/SKILL.md` with `opencode-command: true` | wrapper template naming the skill |
| `cfg.instructions` | `~/.claude/rules/{common,personal}/*.md` | drop exclusions; emit explicit paths; append the compatibility rule |

Skills need no entry at all. `skill/index.ts:187-193` already scans `~/.claude/skills`, and once the second copy stops being installed, that scan is the only source and the duplicate warnings disappear.

`config.json` shrinks to a plugin declaration and `subagent_depth`. `opencode.jsonc` is untouched and still wins on merge (`config/config.ts:258-260`), which is what preserves machine-local `permission` and `mcp` settings through regeneration — the "explicit, testable, documented" overlay mechanism roadmap `:88` asks for, now with nothing generated that could collide with it.

### Why the transform must survive even though the transport does not

It is tempting to conclude that pointing OpenCode at live files removes the need for `process_agent_frontmatter()` along with everything else. It does not. `ConfigAgentV1.Info` (`packages/core/src/v1/config/agent.ts:14`) types `model` as an unvalidated optional string, and `Provider.parseModel()` (`provider/provider.ts:1997-2003`) splits it on `/` and takes the first segment as a provider ID. An agent file reaching OpenCode with `model: sonnet` therefore resolves to `providerID: "sonnet"`, `modelID: ""` — no error, no fallback, just a nonexistent model. The tier remap is the one piece of real translation this integration has always needed, and moving it from a disk rewrite into `config()` is what lets the disk rewrite go.

### What `bin/opencode-sync` becomes

The script keeps its role as the control plane (roadmap `:25`) and loses everything that existed to make disk writes safe:

- **Bootstrap** (`--bootstrap`) — symlink the plugin and the compatibility rule into the config dir; write `config.json`. Idempotent, so re-running after a plugin edit is a no-op rather than a duplicate.
- **Prune** (`--prune`) — remove the previously-installed `agents/`, `skills/`, `commands/`, `rules/` trees, including the seven orphans.
- **Verify** (`--verify`) — shell out to `opencode debug agent <name>` and fail if it does not resolve.
- **Lint** — `--check-source` and `--check-orphans`, both still wired into `prek.toml` (hook blocks at `:114-121` and `:123-130`). `--check-orphans` is unchanged. `--check-source` absorbs the one check worth keeping from the retired installed-file lint (below).

The compatibility lint over *installed* files retires with the installs. `run_lint()` (`:1173`), `report_lint()` (`:1191`), `lint_only()` (`:1246`), `_lint_targets()` (`:991`), `_lint_content()` (`:1012`), and `_walk_synced_md_files()` (`:967`) all operate on `config_dir/{skills,commands,agents}` — precisely the trees FR#13 stops populating and FR#19 deletes — so they lose their subject for the same reason `check_variant_names()` does. `--lint-only` goes with them (FR#23); it is a documented CLI flag, so its removal is a deliberate contract change, not an oversight.

One check inside `_lint_content()` is worth keeping and does not depend on installed files: the `isolation: "worktree"` and `run_in_background` warnings flag Claude-only dispatch semantics OpenCode cannot honor. That is a property of the *source*, so it moves into `--check-source`, which already scans the repo's own directories. `check_instruction_globs()` (`:1044`) moves there too, retargeted from "is every synced rules directory covered by a glob" to "is every subdirectory under `rules/` named in the plugin's instruction-directory list" — same question, asked at commit time about source rather than at sync time about output.

Gone: staging (`stage_config:331`), OpenPackage (`run_opkg:429`, `_run_opkg_best_effort:356`, `opkg_list_includes_claudefiles:384`, `uninstall_previous:399`), frontmatter rewriting (`process_agent_frontmatter:519`), wrapper generation (`generate_skill_commands:761`), sync state (`check_sync_status:725`, `load_sync_state:627`, `write_sync_state:713`, `_empty_sync_state:619`, `_sha256_file:615`), foreign-config detection (`handle_foreign_config:1209`), and the config-hash/collision machinery around them.

`OPENCODE_COMPAT_RULE` stops being a Python string constant and becomes a real markdown file in the repo, which is both reviewable and reachable by the same symlink mechanism as the plugin.

`check_variant_names()` (`:1077`) and `_agent_variant_errors()` (`:1126`) lose their subject — they validate `variant:` lines written into synced agent files, and no agent files are written. The failure mode they guard (an agent silently losing its variant, bug #514) is now covered at runtime by AC#1's assertion that `debug agent` shows a real variant, and by `bin/opencode-variant-audit`. `check_instruction_globs()` (`:1044`) is retargeted rather than deleted: it still answers "is a rules directory missing from the instruction list," which FR#5's two named directories still need.

### Existing code leverage

| Sub-problem | Existing code | Coverage |
|---|---|---|
| Map Claude tier → OpenCode model + variant | `TIER_MAP` (`bin/opencode-sync:123`) | Replace — the data moves to `opencode/config-data.json`; both sides read it, neither hand-copies it |
| Validate variant names | `OPENCODE_VARIANTS` (`:146`) | Replace — moves to the same shared data file |
| Exclude rules from OpenCode | `OPENCODE_EXCLUDED_RULES` (`:90`), `apply_rule_exclusions` (`:314`) | Partial — list shrinks to one entry and moves to the shared data file; the plugin filters at runtime, Python reads the same list for FR#8's `--check-source` gate |
| Instruction directory coverage check | `check_instruction_globs` (`:1044`) | Partial — retargeted from synced dirs to the repo's own `rules/` tree, under `--check-source`. Deliberately **not** pointed at `~/.claude`: `check_source()`'s docstring (`:1370-1385`) establishes that commit-time checks read repo source rather than a live install, so they stay reproducible on a fresh checkout |
| Skill-command wrapper body | `SKILL_COMMAND_TEMPLATE` (`:159`) | Replace — moved to the shared data file and emitted as `cfg.command[].template`, **minus the `{marker}` placeholder**: it existed to stamp generated `.md` wrapper files for later pruning, and no wrapper files are written anymore |
| Compatibility translation table | `OPENCODE_COMPAT_RULE` (`:178`) | Partial — moves to a repo file, gains the MCP naming line |
| Deliver skills to OpenCode | OpenCode's native `~/.claude` scan | Replace — the staged copy is superseded |
| Deliver agents/rules to OpenCode | staging + opkg | Replace — superseded by `config()` |
| Detect a broken install | `check_sync_status` (`:725`), reached via `--check` | Replace — staleness is meaningless with live reads; `--verify` answers a different and better question, and `--check` retires with its subject |

## Implementation Preferences

- **The plugin is TypeScript at `opencode/claudefiles.ts` in this repo**, symlinked into the config dir. Path-like plugin specs resolve relative to the declaring config file (`config/config.ts:101-108`), and `@opencode-ai/plugin` is already installed at `~/.config/opencode/node_modules` (OpenCode auto-installs it, `config/config.ts:438-446`). No build step, no publish, no new package manager.
- **Shared values live in `opencode/config-data.json`, read by both sides** (FR#27). `TIER_MAP`, `OPENCODE_VARIANTS`, `OPENCODE_EXCLUDED_RULES`, and `SKILL_COMMAND_TEMPLATE` move there out of `bin/opencode-sync`; the Python script reads it with stdlib `json`, the plugin with `JSON.parse`. **JSON specifically, not TOML** — `tomllib` is Python-stdlib only from 3.11 (this script's floor is 3.10) and, more decisively, TypeScript has no built-in TOML parser, so TOML would force a plugin dependency the design otherwise avoids. JSON is the one format both read with zero dependencies.

  JSON has no comment syntax, and `TIER_MAP`'s existing comment is load-bearing — it records why the key is `variant` and not `effort`, the #514 lesson. Carry it as a `$comment` string key, which both parsers ignore without special handling. Losing that rationale to a format choice would be a bad trade.
- **Python side follows repo rules**: no `from __future__ import annotations`, `X | None` over `Optional[X]`, no lazy imports, `whenever` if any date handling arises.
- **`GENERATED_FILE_MARKER` goes away with its only consumer.** It is an HTML comment (`bin/opencode-sync:154`) used solely in the skill-command wrapper `.md` files that FR#15 removes. It cannot mark `config.json` — JSON has no comment syntax, and adding it as a key would violate AC#8's exactly-three-keys assertion.
- **Frontmatter parsing in TypeScript** should not pull a YAML dependency for the three fields it needs (`model`, `description`, `opencode-command`). A line-scan over the frontmatter block matches what `_split_frontmatter` (`:499`) already does on the Python side and keeps the plugin dependency-free.

## Replacement Targets

| Target | Replaced by | Disposition |
|---|---|---|
| `bin/opencode-sync:331` `stage_config()` | live reads from `~/.claude` | remove outright |
| `bin/opencode-sync:429,356,384,399` `run_opkg()`, `_run_opkg_best_effort()`, `opkg_list_includes_claudefiles()`, `uninstall_previous()` | nothing — no install step | remove outright |
| `bin/opencode-sync:519` `process_agent_frontmatter()` | plugin `config()` tier remap | remove outright |
| `bin/opencode-sync:761` `generate_skill_commands()` | plugin `cfg.command` | remove outright |
| `bin/opencode-sync:833` `build_instructions()` | plugin `cfg.instructions` | remove outright |
| `bin/opencode-sync:615,619,627,713,725` sync-state and staleness | `--verify` | remove outright |
| `bin/opencode-sync:1209` `handle_foreign_config()` | nothing to protect — `opencode.jsonc` is never written | remove outright |
| `bin/opencode-sync:690` `_atomic_write_json()` | a direct `_atomic_write(target, json.dumps(...).encode())` call | remove outright — the **validate-then-backup** ceremony it wraps guarded hand-authored complexity a three-key generated file no longer has. **`_atomic_write()` (`:645`) survives** and gains the config-writer as its direct caller: torn-write risk is orthogonal to key count, and `loadGlobal()` collapses to an empty config on any parse failure across all three global files (`config/config.ts:282-286`), taking `opencode.jsonc`'s machine-local settings down with it for that process |
| `bin/opencode-sync:1077,1126` `check_variant_names()`, `_agent_variant_errors()` | AC#1 plus `bin/opencode-variant-audit` | remove outright |
| `bin/opencode-sync:1044` `check_instruction_globs()` | itself, retargeted to source `rules/*` under `--check-source` | rewrite |
| `bin/opencode-sync:1173,1191,1246,991,1012,967` `run_lint()`, `report_lint()`, `lint_only()`, `_lint_targets()`, `_lint_content()`, `_walk_synced_md_files()` | `--check-source`, which absorbs the platform-semantics warnings | remove outright — they scan installed trees that no longer exist; `--lint-only` retires with them (FR#23) |
| `bin/opencode-sync:956,681` `_split_eol()`, `_atomic_write_text()` | nothing — every caller sits inside a function removed above (`_split_eol` only in `process_agent_frontmatter`; `_atomic_write_text` only in `process_agent_frontmatter` and `generate_skill_commands`) | remove as fallout; AC#18's orphan check is what proves none was missed. **Not** `_atomic_write()`, which survives per the row above |
| `bin/opencode-sync:314` `apply_rule_exclusions()` | the plugin's runtime filter, plus a `--check-source` gate reading the same shared list | rewrite — the staged-tree delete goes; the matched-nothing check survives in Python as FR#8's commit-time gate |
| `bin/opencode-sync:90,123,146,159` `OPENCODE_EXCLUDED_RULES`, `TIER_MAP`, `OPENCODE_VARIANTS`, `SKILL_COMMAND_TEMPLATE` | `opencode/config-data.json`, read by both sides | migrate — data moves out of the script; the `variant`-not-`effort` rationale rides along as a `$comment` key (FR#27) |
| `bin/opencode-sync:178` `OPENCODE_COMPAT_RULE` string constant | `opencode/opencode-compat.md` in the repo | migrate — plus the MCP naming line |
| `bin/opencode-sync:90` `OPENCODE_EXCLUDED_RULES` 3 entries | 1 entry (`common/sudo.md`) | reduce |
| Installed `~/.config/opencode/{agents,skills,commands,rules}` trees | live `~/.claude` | delete via FR#19 — includes the 7 orphaned agents |
| `tests/test_opencode_sync.py` cases covering the removed functions | — | remove with their subjects |

## Convention Examples

### `bin/` scripts are `uv run --script` with inline PEP 723 metadata

**Source:** `bin/opencode-sync:1-5`

```python
#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
```

### Docstrings cite upstream source and defend the non-obvious choice

**Source:** `bin/opencode-sync:833-855`

```python
def build_instructions(config_dir: Path) -> list[str]:
    """Build the `instructions` list of config.json: the synced shared rules.

    [...]

    One glob per directory, never `**`: for an absolute path OpenCode globs
    only `basename(pattern)` within `dirname(pattern)`, so a recursive
    pattern silently matches nothing. Add a line here when a rules
    subdirectory is added, and see check_instruction_globs() -- which fails
    the sync if a synced rules directory has no glob covering it -- rather
    than relying on remembering to.
    """
```

(Excerpted — the full docstring also explains why the rules would be inert without this list, and why paths derive from `config_dir` rather than the module constant.)

Non-obvious behavior gets its upstream mechanism named and the wrong-looking-but-correct choice defended, so it survives future cleanup.

### Frontmatter is split by line scan, not a YAML parser

**Source:** `bin/opencode-sync:499-516`

```python
def _split_frontmatter(content: str) -> tuple[str, str]:
    lines = content.splitlines(keepends=True)
    if not lines or lines[0].strip() != "---":
        return "", content

    end_idx = None
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            end_idx = i
            break
    if end_idx is None:
        return "", content

    return "".join(lines[: end_idx + 1]), "".join(lines[end_idx + 1 :])
```

### Testing a `bin/` script

**Source:** `tests/test_opencode_variant_audit.py`

```python
import runpy
import pytest

def _load_script() -> dict:
    ...

@pytest.mark.parametrize("variant,expected_resolved", [...])
def test_classify_verdicts(variant: str | None, expected_resolved: bool) -> None:
    ...
```

`bin/` scripts have no importable module, so tests load them via `runpy`, with `parametrize` for cases and `tmp_path` for filesystem fixtures.

### Wiring a check as a pre-commit hook

**Source:** `prek.toml:114-121`

```toml
[[repos.hooks]]
id = "lint-opencode-sync"
name = "OpenCode dispatch pattern coverage"
entry = "bin/opencode-sync --check-source"
language = "system"
pass_filenames = false
always_run = true
stages = ["pre-commit"]
```

## Alternatives Considered

**Keep the static generation and just fix it.** Extend `opencode-sync` to also stage `skills-cli/`, `skills-impeccable/`, and Dotfiles' skills, and set `OPENCODE_DISABLE_CLAUDE_CODE_SKILLS` so there is exactly one source. Rejected: it keeps every function this change deletes, requires a cross-repo staging source for Dotfiles that roadmap `:194` flagged as its own decision, needs an env var in the shell profile to work at all, and still leaves content stale between syncs. It preserves the fallback invariant, which is the one thing it has going for it.

**Point `skills.paths` and `instructions` at `~/Claudefiles` directly.** Rejected on a fact rather than a preference: Dotfiles contributes eleven skills and all five personal rules, none of which exist in the Claudefiles repo. Reading the repo is strictly less complete than reading the install.

**Let the plugin own `cfg.skills.paths` too, for symmetry.** Rejected on probe evidence — it is racy (one success in ~16 runs) and OpenCode's native scan already covers it. Symmetry would buy a config key that sometimes silently loses every skill.

**A curated symlink farm for per-skill exclusion.** Generate a directory of symlinks to allowed skills and point `skills.paths` there, preserving live content plus file-granular filtering for roadmap `:106`. Rejected as premature: no skill is excluded today, no classification exists yet (Workstream 3 owns it), and the mechanism can be added later without disturbing anything here. Recorded because going to a native scan does foreclose staging-time filtering, and this is the way back if it is ever needed.

**Do nothing.** Rejected. It leaves 41 duplicate warnings per startup with stale copies winning, seven ghost agents dispatchable, Dotfiles skills and personal rules unreachable, and roughly twenty functions maintained for a transport mechanism nothing needs.

## Test Strategy

### Required Test Types

**Unit (pytest, `runpy`)** — for the reduced `bin/opencode-sync`: the exclusion filter's matched-nothing behavior (FR#8), the retargeted instruction-directory coverage check, `config.json` shape (AC#8), and the prune command against a scratch config dir (AC#10).

**Observation, not unit tests, for the plugin.** There is no TypeScript test infrastructure in this repo — `package.json` is promptfoo-only and `bun` is not on `PATH` — and adding one for a single dependency-free file is not proportionate. Plugin correctness is verified against OpenCode's own introspection surfaces (`opencode debug agent|skill|config`, `GET /command`), which is what AC#1–AC#4 assert and what this design's probe already exercised successfully. This is a deliberate substitution of observation for unit coverage, not an untested component: the observations are stronger evidence than a unit test of a config-shaping function would be, because they prove the consuming service actually resolved the value.

**Gap:** no automated integration harness exists to run OpenCode with Claude fallback disabled (roadmap Spec 1 asked for one and it was never built). With this design that harness would also be testing something the design deliberately depends on, so its absence is less consequential than it was — but it means AC#14 and AC#15 are run by hand rather than in CI.

### Existing Tests to Adapt

- `tests/test_opencode_sync.py` — substantial deletions. Every test whose subject is a Replacement Target loses its subject: staging, opkg orchestration, frontmatter remapping, skill-command generation, sync-state hashing, foreign-config detection, and `check_variant_names`. Tests for `_split_frontmatter` survive if that helper survives; tests for `check_instruction_globs` are adapted to its new target rather than deleted.

### New Test Coverage

- Exclusion list filters `sudo.md` out of the instruction list, and a renamed entry exits non-zero (FR#6, FR#7, FR#8).
- Instruction list contains every non-excluded file in both rule directories (FR#5).
- `config.json` has exactly three top-level keys (FR#17).
- The prune command empties a seeded scratch config dir of all four trees (FR#19).
- The verify command's exit code for a resolvable vs unresolvable agent name (FR#20).
- A pre-existing `opencode.jsonc` in a scratch config dir is unchanged after a sync run (FR#18).
- `--bootstrap` is idempotent: a second run against an already-bootstrapped scratch config dir changes nothing (FR#25).
- `--bootstrap` propagates a verification failure as its own non-zero exit (FR#26).
- Both sides load the shared data file rather than literals, and the tier map resolves per-tier to the expected model/variant (FR#27).
- The `--verify` hook's `files` pattern matches the plugin and shared data file and not other paths (FR#28).

### Tests to Remove

All tests in `tests/test_opencode_sync.py` whose subject appears in Replacement Targets.

## Smoke Test

**Surface:** OpenCode's own introspection commands, plus a real session.

**Scenario:** Run the bootstrap, then:

1. `opencode debug agent code-reviewer` — expect a `providerID`/`modelID` pair and a `variant`, not `sonnet`.
2. The same command with `--pure` — expect failure, proving the entry came from the plugin.
3. Start a session and confirm no `duplicate skill name` warnings appear in the log.
4. Edit a rule under `~/Claudefiles/rules/common/`, start a **new `opencode` process**, and confirm the change is in effect with no sync command run in between. (Probe-verified that a new session against an already-running `opencode serve` will *not* show it — see Dependencies and Assumptions.)
5. Confirm a personal rule (`~/.claude/rules/personal/machines.md`) appears in `opencode debug config`'s `instructions` — this is the roadmap `:194` closure and the one instruction-layer behavior the probe did not verify at service level.
6. Run a dispatch-bearing workflow and check `bin/opencode-variant-audit --json` reports `fell_back: 0`.

**Success:** agents resolve with real models and variants that came from the plugin; skills load once each; a rule edit propagates with only a restart; personal rules are present; no dispatch falls back.

## Documentation Updates

- `design/opencode-integration-roadmap.md` — the substantive one. Amend `:53` and `:236` (the Claude-fallback invariants) to record that OpenCode now intentionally reads the shared install at `~/.claude`, with the rationale from Dependencies and Assumptions; mark Workstream 4's deferred personal-rules decision (`:194`) resolved; note that the Minimum Supported Workflows per-skill exclusion requirement (`:106`) now has no mechanism — and that Workstream 3's skill-classification bullet (`:165`) is what would produce the list it needs — naming the symlink-farm option from Alternatives as the way back; update the Current State bullets that describe staging and remapping.
- `design/opencode-integration-roadmap.md:146` — its Workstream 2 correction says model and variant enforcement "live entirely in each agent's own **synced** frontmatter." After this ships nothing is synced; frontmatter is read live and transformed in memory. Reword rather than leave a stale authoritative record.
- `install.py` — a comment where it writes `~/.claude/{agents,skills,rules}` noting that `opencode/claudefiles.ts` now reads that output directly, so its directory and frontmatter shape is a two-consumer contract rather than a Claude-Code-only detail. This design changes no code in `install.py`, but it does change what breaking it costs.
- `REFERENCE.md` — the OpenCode Sync section: new commands, removed behavior (`--check`, `--lint-only`), the plugin file, and the process-not-session restart granularity.
- `ONBOARDING.md` — that OpenCode support is a plugin reading the Claude install, and that `install.py` is now a prerequisite for OpenCode rather than only for Claude Code.
- `opencode/opencode-compat.md` — the compatibility rule's new home as a repo file (moved out of the `OPENCODE_COMPAT_RULE` Python constant, and no longer written into a staged `rules/common/` tree), gaining the MCP tool-name mapping line (FR#10).
- `bin/opencode-sync` module docstring — its described workflow is entirely superseded.
- `CHANGELOG.md` — at PR creation, per repo convention.
- Issues #500, #501, #517 — comment that their subject matter is largely removed and their filed resolutions should be re-scoped rather than executed.

## Impact

### Changed Files

<!-- Gap check 2026-08-17: 7 unlisted dependencies found, all included — rules/common/performance.md:17,19 (claims process_agent_frontmatter rewrites effort→variant at sync time and that TIER_MAP lives in bin/opencode-sync; file is now un-excluded so OpenCode reads it) → T06; bin/opencode-variant-audit:8,103,108,176 (--lint-only, OPENCODE_VARIANTS ownership, "re-run opencode-sync" remediation string) → T06; design/opencode-integration-roadmap.md:90-92 (third Claude-fallback invariant, alongside the :53 and :236 the design already names) → T06; skills/mine-write-skill/REFERENCE.md:40 ("generates a thin bridge" — now in-memory config) → T06; bin/opencode-sync:191 inside OPENCODE_COMPAT_RULE ("${CLAUDE_CONFIG_DIR:-~/.claude}" paths → ~/.config/opencode, now wrong since the plugin reads ~/.claude deliberately) → T01; check_instruction_globs cannot see rules/personal from repo source → accepted, recorded in Dependencies and Assumptions, T03 Focus; instruction-directory list absent from FR#27's shared values while the retargeted check must validate against it → FR#27 and AC#22 amended, T01 + T03. -->

**Cross-cutting first:**

- modify: `bin/opencode-sync` — large deletions per Replacement Targets; new bootstrap/prune/verify commands
- create: `opencode/claudefiles.ts` — the plugin
- create: `opencode/config-data.json` — shared tier map, variant names, exclusion list, command template (FR#27)
- create: `opencode/opencode-compat.md` — the compatibility rule, moved out of the Python constant
- modify: `prek.toml` — existing two hooks keep their entries; add the file-scoped `--verify` hook (FR#28)
- modify: `install.py` — comment only, recording the new cross-tool contract on `~/.claude`'s shape
- modify: `tests/test_opencode_sync.py` — deletions plus new cases

**Documentation:**

- modify: `design/opencode-integration-roadmap.md`, `REFERENCE.md`, `ONBOARDING.md`

**Not changed, deliberately:**

- `~/.config/opencode/opencode.jsonc` — machine-local, never touched (FR#18)
- `install.py`'s behavior — it already produces everything the plugin reads, and no logic changes. The only edit is the comment above, recording that its output now has a second consumer
- `agents/*.md`, `skills/**`, `rules/**` — no source content changes

### Behavioral Invariants

- Every agent dispatchable in OpenCode before this change remains dispatchable, under the same name, at the same tier — except the seven orphans, whose removal is the point.
- Claude Code behavior does not change at all. No file Claude Code reads is modified.
- `bin/opencode-sync --check-source` and `--check-orphans` keep their exit-code contracts and stay wired into pre-commit. `--check` and `--lint-only` are removed; that is a deliberate CLI contract change, recorded in Documentation Updates.
- Machine-local `permission` and `mcp` settings in `opencode.jsonc` survive, as they do today.
- The 37 skills currently reaching OpenCode only via the native scan keep working; the other 41 switch from a stale copy to the live symlink.

### Blast Radius

Every OpenCode session on `jessica-desktop`. No Claude Code surface. `bin/opencode-sync`'s CLI contract changes for anyone with muscle memory for it — the sync-and-install flow becomes bootstrap-once plus verify. Spec 1008's `bin/opencode-variant-audit` becomes the primary runtime check rather than a supplementary one.

## Open Questions

None outstanding.

Three questions raised during discovery are closed and recorded here so they are not reopened:

- *Whether the plugin should own `cfg.skills.paths`.* Closed by probe: racy, and unnecessary given the native scan.
- *Whether to keep excluding `performance.md` and `tmux.md`.* Closed: both rationales are stale post-1008; only `sudo.md`'s survives, on the grounds that it hangs rather than merely misinforms.
- *Whether `~/.claude/CLAUDE.md`'s suppression by `AGENTS.md` loses anything.* Closed by inspection: `CLAUDE.md` is ten lines whose entire content already appears in `AGENTS.md`.
