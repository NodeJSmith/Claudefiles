# Design: Named Agents as the Single Dispatch Concept

**Date:** 2026-08-16
**Status:** draft
**Scope-mode:** hold
**Research:** `design/research/2026-08-16-opencode-plugin-viability/research.md` (background context — this spec emerged from that investigation but addresses a prerequisite, not the plugin itself)

## Problem

Shared skills, agents, and commands hardcode Claude Code's subagent dispatch ABI. A dispatch is written as a `subagent_type` naming a generic agent plus a separate `model:` tier clause — `subagent_type: general-purpose, model: sonnet` — in six different prose shapes.

There are two distinct dispatch-bearing forms, and both need migrating:

- **The dispatch itself** — `subagent_type: general-purpose` with a sibling `model:` clause, in prose, YAML blocks, function-call syntax, list items, headings, and table cells.
- **The telemetry record** — `cfl dispatch <role> --agent-type general-purpose --model sonnet`, which records what is about to be dispatched. It names the same agent type and tier and drifts from reality if only the first form is migrated.

The authoritative scoping check is AC#2's grep — `grep -rE 'model:\s*(sonnet|haiku|opus)' skills skills-cli skills-impeccable commands` — which has no false negatives against the corpus. The two searches below characterize the *shapes* within that set; they do not derive it, and at least one live site escapes both. `skills/mine-comb/SKILL.md:30-31` dispatches the already-named specialist `fine-toothed-comb` with a bare `model: sonnet` clause: the type is not `general-purpose` and there is no `cfl dispatch` wrapper, so neither grep sees it. Triage from AC#2's pattern, not from these two:

```
grep -rl 'general-purpose' skills skills-cli skills-impeccable commands agents   # 25 files
grep -rln 'cfl dispatch .*--model' skills skills-cli skills-impeccable commands  # adds mine-sketch, mine-define
```

The second search matters because `cfl dispatch --model` also appears alongside *named specialist* agents — `skills/mine-define/SKILL.md:145` records `--agent-type researcher --model opus`, and `:224` and `skills/mine-sketch/SKILL.md:206` record `--agent-type fine-toothed-comb --model sonnet`. Those agent names are already correct; it is the `--model` argument that must go, since model tier moves into the agent's own declaration.

This causes three concrete problems:

**It couples shared content to one harness's tool signature.** If Claude Code's Agent tool changes shape, every dispatch site is wrong. There is no single place to fix it.

**It forces a translation layer for OpenCode.** OpenCode has no `general-purpose` agent and no per-call model parameter, so `bin/opencode-sync` carries a dispatch rewriter — six named regex constants (`SUBAGENT_TYPE_RE`, `BARE_BUILTIN_RE`, `MODEL_RE`, `STANDALONE_MODEL_RE`, `CLI_DISPATCH_RE`) plus inline patterns in `_removal_span_for_model`, `resolve()`, `rewrite_all_dispatches()`, and a compatibility lint — purely to translate this syntax at sync time. Three of those regexes (`SUBAGENT_TYPE_RE`, `MODEL_RE`, `STANDALONE_MODEL_RE`) use Python-only conditional groups (`(?(id)yes)`), which is a hard portability barrier for any future runtime implementation.

**It contradicts the project's own target architecture.** `design/opencode-integration-roadmap.md:33-41` specifies shared content feeding a Claude adapter and an OpenCode adapter. Today Claude Code is not an adapter — it is the native format, and OpenCode is a patch layered on top.

Separately and compounding it, agent metadata is declared in three places at once: each agent's own frontmatter, `rules/common/performance.md`'s 23-entry list, and `install.py`'s per-bundle tuples. `bin/lint-agent-models` exists solely to keep those in sync — a drift check standing in for a single source of truth. Note which of the three is already authoritative in practice: `bin/lint-agent-models` parses frontmatter and compares the other two against it (`:41-44`, `:69-91`). The redundancy is real, but the source is not in question.

## Goals

- Every subagent dispatch names an agent that exists as a file and resolves identically on both harnesses, with no per-harness mapping.
- Model tier is declared once per agent, in one place, and changing it touches no dispatch site.
- Agent metadata has exactly one declaration site — each agent's own frontmatter — and the other two become generated artifacts.
- `bin/opencode-sync` sheds every function that exists only to translate or synthesize dispatch targets.

## Non-Goals

- The OpenCode `config()` plugin. Parked as spec `1007-opencode-config-plugin`; this spec is its prerequisite and shrinks it substantially.
- Track 1 hook injection, `oh-my-opencode-slim` adoption, and the `experimental.*` hook surface.
- Executing KI-002 (#500) or KI-003 (#501). This work removes much of their subject matter; their disposition is recorded in Dependencies and Assumptions rather than actioned.
- The `customAppendPrompt` pattern from slim — independent, low-risk, its own follow-up.

## User Scenarios

### Jessica: Sole developer and operator of this configuration

- **Goal:** Write a skill that dispatches subagents, without encoding harness-specific dispatch syntax.
- **Context:** Authoring or editing a skill in `skills/`, on either harness.

#### Authoring a dispatch

1. **Decide what kind of work the subagent does**
   - Sees: the agent roster in `agents/`, each with a name describing its role
   - Decides: which agent's role matches the work
   - Then: writes the dispatch naming that agent, with no model clause

2. **Commit**
   - Sees: pre-commit lint output
   - Decides: nothing if clean; on failure, whether the named agent should exist
   - Then: lint fails if the dispatch names an agent with no file, or if a raw `model:` tier clause was written

#### Retuning a role's model

1. **Change the model for a class of work**
   - Sees: that agent's own file in `agents/`, where model sits next to the role's prompt
   - Decides: which tier the role should run at
   - Then: edits one frontmatter field, runs the generator; no skill file changes

## Functional Requirements

- **FR#1** Every subagent dispatch in `skills/`, `skills-cli/`, `skills-impeccable/`, `commands/`, and `agents/` names an agent that has a corresponding file in `agents/`.
- **FR#2** No dispatch site in shared content carries a `model:` tier clause.
- **FR#3** Two worker agents exist, one per model tier in current use: `light-worker` (haiku) and `standard-worker` (sonnet). Every dispatch that does not name a specialist names one of these.
- **FR#4** A site's worker is chosen by that site's current model tier, so migration preserves every site's tier exactly.
- **FR#26** `skills/mine-orchestrate/spec-reviewer-prompt.md`'s contents move into `agents/spec-reviewer.md` and the prompt file is deleted; `mine-orchestrate`'s spec-review dispatch names that agent and supplies only per-run context. Every reference to the deleted path is retargeted in the same change: `bin/lint-verdict-line`'s three hardcoded constants (`REVIEWERS_WITHOUT_COUNT` `:29`, the `REVIEWER_ALLOWED_VERDICTS` key `:42-46`, and `ACTIVE_CONTRACT_FILES` `:62`), and `skills/mine-orchestrate/verdict-line-format.md`'s verdict-vocabulary table row (`:28`) and legitimate-hosts list (`:80`).
- **FR#5** Each worker agent carries body content stating the dispatch discipline every caller relies on — write output to the path the caller names, cite evidence for findings, stay inside the assigned scope — and no task-specific process content.
- **FR#27** `agents/standard-worker.md` carries the Executor note block that every orchestrate-executor-capable agent carries, because `skills/mine-orchestrate/agent-routing.md`'s fallback row (`:26`) migrates to it.
- **FR#6** Both worker agents and `spec-reviewer` are members of the `base` bundle.
- **FR#7** Each agent's own frontmatter declares its model, effort, tools, description, and bundle membership. `bundle` is new; the other four already exist on every agent file today.
- **FR#8** Agent files remain entirely hand-written — neither frontmatter nor body is generated. Frontmatter is the single declaration site, not a generation target.
- **FR#9** `rules/common/performance.md`'s agent declaration list is generated from agent frontmatter.
- **FR#10** `install.py`'s per-bundle `agents=(...)` tuples are generated from agent frontmatter.
- **FR#11** A check fails when any generated artifact diverges from agent frontmatter.
- **FR#12** Agent `tools:` lists grant broad tool access across the fleet.
- **FR#13** `mine-orchestrate`'s "Try again with stronger model" escalation is removed everywhere it appears: the option and its handler in `SKILL.md` (`:640-641`, `:651`) and `spec-fix-loop.md` (`:25-26`, `:31`), the whole of `agent-routing.md`'s SYNC CHECKLIST item 5 (`:10-14`, which exists only to register an agent so its opus variant is generated), `known-issues-protocol.md:59`'s listing of the option among the Step 14/16 choices, and `spec-fix-loop.md:29`'s parenthetical, whose stated reason for re-presenting the gate options is the escalation choice itself.
- **FR#28** Both task-gate prompts left single-optioned by FR#13 — `spec-fix-loop.md:22-27` and `SKILL.md:637-642` — list `Try again`, `Mark as blocked and skip`, and `Stop here` as real options. The latter two are currently reachable only by typing into the picker's Other field, and both files already document their handlers (`spec-fix-loop.md:33,35`; `SKILL.md:652-659`), so the handlers move rather than being written.
- **FR#14** `bin/opencode-sync` no longer generates worker agents.
- **FR#15** `bin/opencode-sync` no longer generates specialist opus variants.
- **FR#16** `bin/opencode-sync` no longer rewrites dispatch syntax in synced files.
- **FR#17** `bin/opencode-sync` no longer emits agent entries into `config.json`.
- **FR#18** `opencode-sync --check-source` fails when a dispatch names an agent with no file in `agents/`.
- **FR#20** `cfl dispatch ... --agent-type` invocations in shared content name the same agent the dispatch itself names, with no `--model` tier argument.
- **FR#21** `opencode-sync --check-source` is reimplemented rather than narrowed: it no longer stages a scratch tree, applies the rewriter, or reuses the rewriter's regexes.
- **FR#22** `opencode-sync --lint-only` reports on content that still exists after this change — it no longer checks residual dispatch patterns or `config.json` agent pins.
- **FR#23** An agent file is rejected when any of model, effort, tools, description, or bundle is absent from its frontmatter.
- **FR#24** Every migrated site that changes model tier as a result of specialist promotion is recorded in the design's Dependencies and Assumptions before the migration lands.
- **FR#25** A check fails when `bin/opencode-sync` contains a module-level definition that is never referenced outside its own definition line.
- **FR#29** `rules/common/performance.md`'s "Skill files with inline model declarations" list (`:69-83`) and the `bin/lint-agent-models` check that validates it (`SKILL_BULLET` at `:29`, its parse at `:66-67`, its assertion loop at `:119-132`) are both deleted. The list names fourteen skill files and asserts each literally contains a `model: <tier>` clause — exactly what FR#2 removes — so the check fails on all fourteen the moment the migration lands. Deleting rather than retargeting it to agent names: FR#18 already verifies every dispatched name resolves to a file, which is the only claim a retargeted list could still make.

## Edge Cases

- **A dispatch names an agent that was deleted.** FR#18 catches it at commit. Without this, the failure surfaces at runtime as OpenCode's `Unknown agent type` error or Claude Code's equivalent.
- **An agent is added to `agents/` but the generated artifacts aren't regenerated.** The staleness check (FR#11) fails, because regenerating from the new frontmatter set would produce a different `performance.md` list and `install.py` tuple than what is on disk. This failure mode is impossible in the other direction — an agent cannot exist without a declaration, because its file *is* the declaration.
- **An agent file is missing a required frontmatter field.** FR#23 rejects it, naming the file and the missing field. `bundle` is the field most likely to be forgotten, since the other four are already habitual.
- **A skill dispatches an agent from an optional bundle the user did not install.** Not caught, and deliberately so — see Alternatives Considered. This is already live and intentional: `mine-orchestrate` is a `base` skill whose routing table names four `engineering-*` agents from the optional `engineering` bundle (`skills/mine-orchestrate/agent-routing.md:19-23`). It degrades gracefully today — an unmatched row falls through to the table's own `general-purpose` default (`:24`, `:26`). Every agent this spec creates lands in `base` (FR#6), so the migration adds no new instance.
- **Someone edits an agent's frontmatter by hand.** That is the supported workflow — frontmatter is hand-written (FR#8). The staleness check (FR#11) then fails until the generator is re-run to propagate the change into `performance.md` and `install.py`. Only those two artifacts carry a generated-region marker, following the existing `GENERATED_FILE_MARKER` convention (`bin/opencode-sync:189`); agent files carry none.
- **A specialist needs to run at a stronger model for one dispatch.** Not expressible, by design — escalation is removed (FR#13). OpenCode has no per-call model parameter, so this was never expressible there without generated `-opus` variants.
- **Prose that mentions an agent name without dispatching it** (table cells, headings, documentation about dispatching). FR#18's check must distinguish a dispatch from a mention, or accept mentions that name real agents. Existing `LINT_SUPPRESS_RE` (`<!-- opencode-sync: ok -->`) provides an escape hatch precedent.

## Acceptance Criteria

- **AC#1** `grep -rE 'subagent_type' skills skills-cli skills-impeccable commands agents` returns only dispatches naming agents that have files in `agents/`. (FR#1)
- **AC#2** `grep -rE 'model:\s*(sonnet|haiku|opus)' skills skills-cli skills-impeccable commands` returns no dispatch-site matches. (FR#2)
- **AC#3** `agents/light-worker.md` and `agents/standard-worker.md` exist, declaring `haiku` and `sonnet` respectively, and no agent file exists under any of the nine rejected intent names — `triager`, `analyzer`, `critic`, `synthesizer`, `ideator`, `judge`, `reviewer`, `writer`, `implementer`. (FR#3)
- **AC#23** `agents/spec-reviewer.md` exists and contains the methodology previously in `skills/mine-orchestrate/spec-reviewer-prompt.md`; that prompt file no longer exists; `grep -rn 'spec-reviewer-prompt' skills/ bin/` returns no matches; and `bin/lint-verdict-line` exits 0. (FR#26)
- **AC#4** Both worker agent files have non-empty body content below their frontmatter, and `grep -c 'mine-' agents/light-worker.md agents/standard-worker.md` returns 0 for each — a worker body that names a specific skill has task-specific content in it. (FR#5)
- **AC#5** `light-worker`, `standard-worker`, and `spec-reviewer` all appear in `install.py`'s `base` bundle tuple. (FR#6)
- **AC#25** `agents/standard-worker.md` contains the Executor note block verbatim as it appears in `agents/engineering-sre.md:16` and the other four `engineering-*` agents. (FR#27)
- **AC#24** Every migrated dispatch site's worker matches the tier it dispatched at before: a site that carried `model: haiku` names `light-worker`, one that carried `model: sonnet` (explicitly, or by the `subagent-model-default` hook's injection for built-in types) names `standard-worker`. (FR#4)
- **AC#6** Running the generator with no changes to any agent file leaves the working tree clean (`git diff --exit-code`). (FR#9, FR#10, FR#11)
- **AC#7** Mutating one frontmatter field in one agent file and running the staleness check without regenerating exits non-zero. (FR#11)
- **AC#8** `grep -c 'general-purpose' bin/opencode-sync` returns 0 — including comments — and every symbol Replacement Targets marks for removal is absent from the file: `generate_worker_agents`, `generate_specialist_opus_variants`, `rewrite_all_dispatches`, `_rewrite_dispatch_file`, `_rewrite_line`, `_apply_edits`, `_removal_span_for_model`, `rewrite_dispatches_prose`, `rewrite_dispatches_cli`, `resolve`, `build_agent_config`, `_config_json_pins`, `SPECIALIST_AGENTS`, `WORKER_AGENT_TEMPLATE`, `BUILTIN_CASE_MAP`, and `LINT_SUPPRESS_RE`. `FRONTMATTER_MODEL_RE`, `process_agent_frontmatter`, `_walk_synced_md_files`, `_lint_targets`, `check_variant_names`, `_agent_variant_errors`, and `OPENCODE_VARIANTS` must still be present — `check_variant_names` is narrowed, not removed (see Architecture), and keeps its call at `:1848` inside `run_lint()`. (FR#14, FR#15, FR#16, FR#17)
- **AC#9** `bin/opencode-sync --dry-run` emits a `config.json` containing no `agent` key. (FR#17)
- **AC#10** Adding a dispatch naming a nonexistent agent to a scratch skill file makes `bin/opencode-sync --check-source` exit non-zero. (FR#18)
- **AC#11** `grep -rn 'stronger model' skills/` returns no matches, and `skills/mine-orchestrate/agent-routing.md` retains no SYNC CHECKLIST item referencing `SPECIALIST_AGENTS` or opus variants. (FR#13)
- **AC#27** The `AskUserQuestion` blocks at `skills/mine-orchestrate/spec-fix-loop.md` and `skills/mine-orchestrate/SKILL.md`'s task gate each list exactly three options — `Try again`, `Mark as blocked and skip`, `Stop here` — and neither file describes the latter two as reached "via Other". (FR#28)
- **AC#13** `timeout 300 pytest tests/` passes with zero failures.
- **AC#14** `prek run --all-files` passes.
- **AC#15** `grep -rn 'agent-type general-purpose' skills skills-cli skills-impeccable commands` returns no matches, and no `cfl dispatch` invocation in shared content passes `--model`. (FR#20)
- **AC#16** `grep -n 'rewrite_all_dispatches\|SUBAGENT_TYPE_RE\|MODEL_RE' bin/opencode-sync` returns no matches inside `check_source_dispatch_patterns` or `run_lint`. (FR#21, FR#22)
- **AC#26** Writing an unresolvable `variant:` into a synced agent file, or removing its `variant:` line entirely, still makes `bin/opencode-sync --lint-only` exit non-zero naming that agent — the #514 failure mode stays caught after `check_variant_names()` is narrowed. (FR#22)
- **AC#17** `bin/opencode-sync --lint-only` exits 0 against the current install and its output references no dispatch-pattern or `config.json` agent-pin checks. (FR#22)
- **AC#18** Removing any of the five required fields from an agent file's frontmatter makes the generator exit non-zero with a message naming the file and the missing field. (FR#7, FR#23)
- **AC#19** Every agent file's `tools:` list contains at minimum `Read`, `Write`, `Edit`, `Bash`, `Grep`, `Glob`. (FR#12)
- **AC#22** No file in `agents/` contains a generated-region marker; `git diff` after running the generator shows changes only under `rules/common/performance.md` and `install.py`. (FR#8)
- **AC#20** For every site the migration changes to dispatch a named specialist, `git diff <base>..HEAD` on that file shows either the same model tier as before, or the file is named in the design's Dependencies and Assumptions as an accepted tier change. (FR#24)
- **AC#21** An orphan check over `bin/opencode-sync` reports zero module-level `def`s and `CONSTANT =` bindings whose name appears only once in the file. Running it against the pre-change file reports zero; running it after removing a function but not its private helper reports that helper. (FR#25)
- **AC#28** `grep -n 'Skill files with inline model declarations' rules/common/performance.md` and `grep -n 'SKILL_BULLET' bin/lint-agent-models` both return no matches, and `bin/lint-agent-models` exits 0 against the migrated tree. (FR#29)

## Key Constraints

- **Do not introduce a per-harness mapping table.** Probe evidence (below) establishes that both harnesses resolve agent names from files identically. A mapping table would reintroduce the two-source drift problem this spec exists to remove.
- **Do not migrate prose shapes for their own sake.** The six structural dispatch shapes (YAML block, function-call, inline prose, list item, heading, table cell) may remain as shapes. What changes is their *content*: an agent name and no model clause. Restructuring prose beyond that risks Claude Code regressions for no gain, against roadmap invariant `:229`.
- **Do not generate any part of an agent file.** Both frontmatter and body are hand-written. Generating prompts would make the fleet's actual behavior a build artifact; generating frontmatter would put a build step between the author and the field they are editing, and would erase the rationale comments that currently sit on the `model:` line.
- **Do not preserve `-opus` variants in any form.** They exist only to work around OpenCode's lack of a per-call model parameter, and escalation is being removed.
- **Do not create an agent for a dispatch intent.** A new agent is justified by a role with a body a caller can rely on without re-deriving it — not by a verb describing what a dispatch does. **The bar is the body, and only the body: does an invariant methodology exist that every caller of this name would rely on and none would contradict?** If yes, it is an agent. If no, it names a worker and keeps its prompt at the call site.

  Caller count is evidence, not a gate, and it points both ways — which is why it is not the test. `analyzer` had four callers and still failed, because their methodologies contradicted each other. `spec-reviewer` has one caller and passes, because its 126 lines are self-contained and the caller re-derives none of them. `critic` and `judge` each have one caller and fail, because their prompts are assembled per dispatch and there is nothing invariant to write down. The nine-agent intent roster this design started with failed the body test across the board, and failing it quietly is how the fleet regrows.

## Dependencies and Assumptions

- **OpenCode resolves agents from markdown frontmatter alone.** Confirmed by source read: `packages/opencode/src/config/agent.ts:11-32` globs `{agent,agents}/**/*.md`; `config.ts:460-461` merges the result into `cfg.agent` — the same field `opencode.json` populates; `agent/agent.ts:267-294` treats both origins identically. Clone at `~/source/opencode`, commit `3fd77ae`, OpenCode v1.18.18.
- **`build_agent_config()`'s justification for config-level pinning is misattributed.** Its docstring cites issues #17870/#35126 as a "frontmatter-ignored failure mode." Those issues describe subagents inheriting the *parent's* active model, not frontmatter being ignored; #35126 was closed with the maintainer confirming frontmatter is honored through the task tool. **Accepted risk:** FR#17 removes config-level pinning based on current-source reading rather than observation of this install. Mitigation: the dogfood step observes `opencode.db` after merge; `bin/opencode-variant-audit --json` reports `fell_back` directly.
- **Near-empty agent bodies are valid but not conventional.** Claude Code requires only `name` and `description` (official docs); `bin/lint-agent-files:123-141` (`check_agent()`) checks nothing about body content. FR#5 still requires real bodies for the two workers, but they are short by design and will not resemble the 38-line floor the existing fleet sets — a worker's body is dispatch discipline, not methodology, because the methodology arrives with the prompt.
- **Escalation removal leaves no recovery path for a task failing review repeatedly.** Accepted explicitly by the user: *"i think we can drop the escalation altogether — it is very new and i'm hoping that we don't end up needing it, if we get opencode to be as capable as claude code."*
- **Fleet-wide tool widening overrides roadmap invariants `:70`** ("read-only exploration roles separated from write-capable execution roles") **and `:233`** ("read-only and write-capable agents must have permissions matching their responsibility"). Accepted explicitly by the user, who reports never having seen a benefit from restriction. Two mitigating facts, both verified: (1) the read-only separation is already illusory — `agents/code-reviewer.md` declares `tools: ["Read", "Grep", "Glob", "Bash"]` with no `Write`, yet `skills/mine-orchestrate/post-execution-pipeline.md:346` instructs it to "write to `<dir>/final/code-review.md`", which it can only do through `Bash`. Granting `Bash` already grants writing. (2) Parallel-dispatch safety comes from distinct output paths per subagent, not from tool restriction — `post-execution-pipeline.md:344-348` launches reviewers in parallel with each writing to its own file.

  Mitigating fact (1) does not cover every agent: `agents/planner.md` declares `tools: ["Read", "Grep", "Glob"]` with no `Bash`, so its restriction is genuinely enforced today, and it is actively dispatched (`rules/common/interaction.md` routes structured planning to it). Widening it is a real capability change, not the removal of a fiction. It is accepted on the blanket decision rather than on fact (1)'s reasoning, and unlike `secrets-auditor` it carries no false read-only claim in its own text, so nothing there needs correcting.

  **The one agent where this costs something specific is `secrets-auditor`**, whose whole design center is refusing write access while scanning attacker-influenceable content — diffs and commit messages from a branch it did not author. The acceptance above was reasoned from `code-reviewer`'s case, which is a weaker one; `secrets-auditor` has a genuinely different threat model. Widening it anyway is the accepted decision, on the same grounds as everywhere else: it already holds `Bash`, so the restriction was never enforced, only asserted. The reduced defense-in-depth is real but nominal, and both of its read-only claims are deleted rather than left contradicting the frontmatter (see Documentation Updates).
- **Specialist promotion changes model tier at some sites.** Known instance: `skills/mine-prior-art/SKILL.md:61` moves from `model: sonnet` to `agents/researcher.md`'s pinned `model: opus` — a cost and capability increase for prior-art web research. Accepted by the user as the general rule for tier collisions, in preference to skipping the promotion or retuning the shared specialist. Mitigation: migration compares each promoted site's current tier against the target specialist's pin and records every difference here, so no tier change is discovered after the fact.
- **Context cost.** Three additional agents (`light-worker`, `standard-worker`, `spec-reviewer`) add roughly 240 tokens to every session's baseline, and `spec-reviewer` is close to cost-neutral since its 126 lines move out of a skill file. An earlier draft's nine intent agents plus a fallback would have cost ~800.
- **Generation adds a step to the most common fleet edit.** Changing a model means editing that agent's frontmatter and regenerating so `performance.md` and `install.py` follow. Accepted — and cheaper than the alternative, since the edit happens in the file the author already has open rather than in a separate registry.
- **KI-002 (#500) and KI-003 (#501) should be updated, not executed.** Both concern `bin/opencode-sync`'s structure — `main()`'s seven concerns and the file's size. This spec deletes a large fraction of their subject matter. Their filed resolutions should be paused pending the result rather than performed.

## Architecture

### One concept: the agent

A dispatch names an agent. An agent is a file in `agents/` with frontmatter (name, description, model, effort, tools) and a hand-written body. Both harnesses resolve that name to that file. There is nothing else — no roles, no mapping tables, no tier vocabulary at call sites, no per-call model parameter.

This works because of an asymmetry confirmed during investigation: OpenCode **silently discards** unknown *config keys* (the `effort`-vs-`variant` bug that shipped undetected in #514), but **loudly rejects** unknown *agent names*. `packages/opencode/src/tool/task.ts:131-133`:

```ts
const next = yield* agent.get(params.subagent_type)
if (!next) {
  return yield* Effect.fail(new Error(`Unknown agent type: ${params.subagent_type} is not a valid agent type`))
}
```

A dispatch naming a missing agent therefore fails visibly rather than degrading silently, satisfying the roadmap's cross-spec invariant *"Unsupported platform behavior must be reported by validation, not skipped silently"* (`design/opencode-integration-roadmap.md:235`) using OpenCode's own guard rather than machinery this repo maintains. FR#18 moves that detection earlier still, to commit time.

### The new agents

Every dispatch names either an existing specialist or one of two workers, chosen by the tier that dispatch already runs at. The table below is illustrative, not the complete list — the migration's authoritative scope is AC#2's grep, plus every file returned by `grep -rl 'general-purpose' skills skills-cli skills-impeccable commands agents`, which includes the `cfl dispatch --agent-type` telemetry form (FR#20) and prose forms that name no `subagent_type` at all (`mine-address-pr-issues/SKILL.md:211`, `mine-implementation-review/SKILL.md:84`, `mine-visual-qa/SKILL.md:67,159`).

| Agent | Sites it replaces |
|---|---|
| `light-worker` (haiku) | `mine-challenge:78`, `mine-issues-triage:64`, `mine-why:54`, `mine-document:154`, `mine-how:104`, `mine-decompose:42`, `commands/mine-issues:31` |
| `standard-worker` (sonnet) | `mine-challenge:144/166`, `mine-why:186`, `mine-brainstorm:66`, `mine-elevate:57/67`, `mine-create-issue:45`, `mine-create-pr:13`, `mine-mockup:26`, `mine-document:107/182/228`, `mine-how:69/131/164`, and the remaining `Explore` sites |
| `spec-reviewer` (sonnet) | `mine-orchestrate:393` — a real specialist, not a worker (see below) |

**An earlier draft of this design proposed nine intent-named agents** (`triager`, `analyzer`, `critic`, `synthesizer`, `ideator`, `judge`, `reviewer`, `writer`, `implementer`) derived by classifying the generic dispatch sites by verb. That roster turned out to be a model-tier partition wearing role names. Reading every site's actual model clause:

- The haiku sites are exactly `triager` ∪ `analyzer`.
- The sonnet sites are exactly everything else.

There were no exceptions in either direction. Worse, the verbs did not survive contact with the sites they named: three of `analyzer`'s four callers describe themselves differently in their own prose — `mine-why:54` dispatches "6 parallel **evidence-gathering** agents," while `mine-document:154` and `mine-how:104` both dispatch "2-4 parallel **explorer** agents." One name covered three unrelated methodologies (git-churn analysis, evidence gathering, and angle-based exploration) because what those sites actually share is a tier and a shape, not a role.

So the roster is two workers, named for what they are. This is the option Alternatives Considered originally rejected, on the grounds that tier-shaped names "weld role to model." That objection only bites when there is a role to retune, and at these sites there is not: every one of them assembles its full prompt at dispatch time, so "what tier should this run at" is genuinely a property of the call, and the call site is the only thing that knows the prompt. Where a real role does exist it keeps its own agent, and retuning it still touches no call site — which is where that benefit was ever real.

The Goal survives literally: `light-worker`'s model is declared once, in `agents/light-worker.md`, and changing it touches no dispatch site. What is removed is the claim that six verbs were roles when they were two tiers.

Three consequences worth naming:

- **`mine-orchestrate:393` becomes a named specialist, `spec-reviewer`** (FR#26) — the one generic site with a real role behind it. Its methodology is already a self-contained 126-line file, `skills/mine-orchestrate/spec-reviewer-prompt.md`, with no per-run interpolation, so it *moves* into the agent body and the prompt file is deleted. Nothing is duplicated. The name is domain-qualified to match the fleet's existing `code-reviewer` / `integration-reviewer` / `wtf-reviewer` / `code-judo-reviewer` convention; a bare `reviewer` beside those would say nothing about which kind of review it performs.
- **`standard-worker` inherits the orchestrate-executor role.** `skills/mine-orchestrate/agent-routing.md:26` says "If the WP does not clearly match a row, use `general-purpose`, `model: sonnet`" — so after migration a work package that matches no specialist row lands on `standard-worker`, launched as an executor exactly like the five `engineering-*` agents. Those all carry an identical Executor note ("your output format is governed by the injected `implementer-prompt.md`. Do not override the output structure.", `agents/engineering-sre.md:16`), and `agent-routing.md`'s own SYNC CHECKLIST (`:5-14`) requires it when adding an executor-capable agent. `standard-worker` needs it too (FR#27); without it, a fallback WP produces whatever shape the worker body implies rather than what Step 8's review pass expects.
- **The nine `Explore` sites route by tier like everything else**, which resolves them without a separate decision. `commands/mine-issues.md:31` declares `model: haiku` and becomes `light-worker`; the rest (`mine-prior-art:50`, `mine-eval-repo:41/50/67`, `agents/researcher.md:82/93/101/111`) carry no model clause, so the `subagent-model-default` hook injects `sonnet` for them today (`rules/common/performance.md`) and they become `standard-worker`. Confirm each site's injected tier during migration rather than assuming.

Where an existing specialist already covers a site's intent, the site dispatches that specialist rather than a worker. Each site is audited individually during migration — the worker is the fallback, not the default.

**Promotion may change a site's model tier, and that is accepted.** A specialist's model is pinned in its own file, which will not always match what the promoted site dispatches at today. `mine-prior-art:61` is the known instance: it dispatches at `model: sonnet`, while `agents/researcher.md` is pinned `model: opus`, so promoting it raises that site's tier. The rule is to promote anyway and record each tier change individually in Dependencies and Assumptions — not to skip the promotion, and not to retune the specialist (which would change behavior for that specialist's *other* callers, e.g. `mine-define:145`'s opus researcher dispatch).

Migration must therefore compare each promoted site's current tier against the target specialist's pinned model, and surface any difference rather than letting it ride silently.

### The declaration site

An agent's own frontmatter is the single declaration site. Nothing generates it; it is hand-written alongside the body it governs. Generation runs one way, outward:

| Target | Generated portion | Source |
|---|---|---|
| `agents/<name>.md` | **nothing** — frontmatter and body both hand-written | — |
| `rules/common/performance.md` | the agent declaration list | `agents/*.md` frontmatter |
| `install.py` | per-bundle `agents=(...)` tuples | `agents/*.md` frontmatter (`bundle:` field) |

The direction matters. Four of the five fields FR#7 requires — model, effort, tools, description — already live in every agent's frontmatter today (`agents/code-reviewer.md:2-6`), and `bin/lint-agent-models` already treats frontmatter as ground truth, parsing it and comparing the other two sites against it (`:41-44`, `:69-91`). Only `bundle` is genuinely new, and it is one line per file. Generating *into* frontmatter from a separate registry would invert a relationship the repo already has right, and would be lossy in two concrete ways:

- **Rationale comments.** Thirteen of the twenty-three agent files carry a trailing comment on the `model:` line; three are explicit safety-gate warnings — `agents/code-reviewer.md:3`, `agents/integration-reviewer.md:3`, and `agents/testing-reality-checker.md:3` all read `do not downgrade; pre-commit safety gate` or equivalent. A whole-block frontmatter generator erases them, and a five-field schema has nowhere to put them back. Leaving frontmatter hand-written keeps the warning adjacent to the field it guards.
- **Display metadata.** Six agent files carry frontmatter keys outside the five-field set: the five `agents/engineering-*.md` files carry `color:`, `emoji:`, and `vibe:`; `agents/testing-reality-checker.md` carries `color:` and `emoji:` but no `vibe:`. Nothing regenerates them, so nothing can drop them.

Generation is safe for `install.py`: its tuples are pure declarative data with no order or index dependence (`install.py:1028-1043`, `:1129-1130`; the only other use is a cosmetic join at `:1479`). Persisted config stores bundle *keys and booleans* only (`:378-453`), never agent names, so bundle contents can change without touching existing installs, and the v1→v2 migration never reads them.

`bin/lint-agent-models` already regex-parses those tuples for set-membership validation (`:36-40`, `:104-121`), so extending it into a generator codifies a pattern the repo already relies on rather than introducing a new one — matching this spec's own Implementation Preference to extend that script. It gains a staleness check: regenerate, diff, fail on divergence.

### What leaves `bin/opencode-sync`

`generate_worker_agents()` (`:796-838`) and `generate_specialist_opus_variants()` (`:841-967`) synthesize agents that will now be real files. `rewrite_all_dispatches()` (`:1522-1536`), `_rewrite_dispatch_file()`, `resolve()` (`:1259-1303`), `_rewrite_line()`, and the five dispatch-translation regex constants (`SUBAGENT_TYPE_RE`, `BARE_BUILTIN_RE`, `MODEL_RE`, `STANDALONE_MODEL_RE`, `CLI_DISPATCH_RE`) translate a syntax that will no longer exist. The file's other `re.compile()` constants are unrelated and **must stay**: `OPKG_SUCCESS_PATTERN` and `OPENCODE_COMMAND_RE` serve opkg detection and command matching; `ISOLATION_WORKTREE_RE` and `RUN_IN_BACKGROUND_RE` back lint warnings; and `FRONTMATTER_MODEL_RE` (`:1239`) is load-bearing for `process_agent_frontmatter()` (used at `:605` and `:628`), which survives this change — it remaps a synced agent's Claude tier name to an OpenCode model ID and is unrelated to dispatch translation. Removing it would raise `NameError`.

Three module-level constants become dead once their only consumers go: `SPECIALIST_AGENTS` (`:168`), `WORKER_AGENT_TEMPLATE` (`:175`), and `BUILTIN_CASE_MAP` (`:1153`). Two of them — `SPECIALIST_AGENTS` and `BUILTIN_CASE_MAP` — carry comments containing the literal string `general-purpose` (`:158`, `:1151`), so AC#8's grep does not reach zero until they go; `WORKER_AGENT_TEMPLATE` has no such comment and is listed purely as dead code. `LINT_SUPPRESS_RE` (`:1256`) also loses its subject once the literal-`general-purpose` lint is gone.

The rewriter's internal helpers go with it and are individually named in AC#8, because none contains the string `general-purpose` and so none is caught by that grep: `_apply_edits` (`:1316`), `_removal_span_for_model` (`:1323`), `rewrite_dispatches_prose` (`:1406`), and `rewrite_dispatches_cli` (`:1457`). `rewrite_dispatches_prose` has direct unit tests (`tests/test_opencode_sync.py:1184,1194,1200`) that go with it. `_agent_variant_errors()` (`:1775-1832`) is private to `check_variant_names()` and survives with it, minus the model-pin arm that depends on `_config_json_pins()`.

Enumerating these by hand has repeatedly missed one, so FR#25/AC#21 add an orphan check instead of a longer list: after the deletions, no module-level definition in `bin/opencode-sync` may have its name appear only once in the file. Three helpers that look like candidates but **survive**: `_split_eol` (`:1306`, still used by `process_agent_frontmatter` at `:605`/`:612`), `_split_frontmatter` (`:534`, still used by `process_agent_frontmatter` and `generate_skill_commands` at `:982`), and `_walk_synced_md_files` (`:1497-1519`) — it reads as a rewriter helper because `rewrite_all_dispatches` calls it at `:1532`, but `_lint_targets()` calls it too (`:1552`), and `_lint_targets` survives to feed the reduced `_lint_content`. Its own docstring says so (`:1505`). It is a file-walk utility, not dispatch translation. `build_agent_config()` (`:1042-1077`) and `SPECIALIST_AGENTS` pin agents at config level for a reason that turns out to be misattributed.

**`--check-source` and `--lint-only` are reimplemented, not narrowed** (FR#21, FR#22). These are the places where the deletion list has non-obvious dependencies, and they must not be discovered mid-implementation. Note the direction of the risk: FR#25's orphan check catches a *deleted* symbol's helper going unreferenced, but not the reverse — a **surviving** function that still calls something the deletion wave removed. `run_lint()` has that shape twice, so each surviving caller's body must be re-read against the post-deletion symbol set:

- `check_source_dispatch_patterns()` (`:2024-2091`) currently stages a scratch tree, calls `rewrite_all_dispatches(scratch, dry_run=False)` and `process_agent_frontmatter(scratch, ...)`, then `run_lint(scratch)`. Its whole method is "rewrite, then check nothing residual survived." With no rewriter, that method is gone — the check becomes a direct assertion over source: every dispatched agent name has a file, no raw model clause remains.
- `run_lint()` → `_lint_content()` (`:1562-1650`) deliberately reuses `SUBAGENT_TYPE_RE`, `BARE_BUILTIN_RE`, `MODEL_RE`, `STANDALONE_MODEL_RE`, and `CLI_DISPATCH_RE` so that "the lint's notion of 'a residual dispatch' can't drift from what the rewriter actually rewrites" (its own docstring). Those checks lose their subject entirely.
- `_config_json_pins()` (`:1686-1722`) reads `config.json`'s `agent` key, which FR#17 removes. It is deleted.
- **`check_variant_names()` (`:1725-1772`) is narrowed, not deleted.** Its docstring names three subjects, and only one of them dies: `TIER_MAP`'s variants (TIER_MAP survives, see below), the `variant:` lines `process_agent_frontmatter()` writes into synced agent files (that function survives and is load-bearing), and `config.json`'s pins (gone with FR#17). Drop the `_config_json_pins()` cross-check and the model-pin arm of `_agent_variant_errors()` that depends on it; keep the TIER_MAP and frontmatter arms, and keep `OPENCODE_VARIANTS`, which has no other consumer. `run_lint()` keeps calling it at `:1848`.

  This one is worth stating plainly because the deletion looked obvious and is not. The check exists to stop an agent silently losing its variant — *"the same failure the `effort` -> `variant` fix closed,"* per its own docstring. That is bug #514, which this design cites at Architecture (`:172`) as the evidence that OpenCode discards unknown *config keys* silently. Deleting the guard against the exact failure mode the design argues from would be a regression, and `bin/opencode-variant-audit` is a runtime observation tool, not a commit-time gate.
- `_lint_targets()` (`:1539-1559`) survives and keeps calling `_walk_synced_md_files()` at `:1552`, which is why that helper is not on the removal list (see above).
- What survives in `run_lint()`: `_lint_targets()` feeding a reduced `_lint_content()`, `check_instruction_globs()` (`:1653-1683`) — the rules-glob check, untouched by this change — and the narrowed `check_variant_names()`. The `OPENCODE_EXCLUDED_RULES` staleness check is **not** in `run_lint()`; it lives at `:2086` inside `check_source_dispatch_patterns()`, so it rides along with that function's rewrite rather than surviving independently.

The `isolation: "worktree"` and `run_in_background` warnings (`:1643-1650`) also survive, but both are stale — see Documentation Updates.

`TIER_MAP` survives in reduced form — `OPENCODE_VARIANTS` and the model identifiers are still needed — but its `worker`/`worker_description`/`builtins` fields become dead with worker generation gone.

## Implementation Preferences

- **No new file format.** Frontmatter is already YAML and already parsed by `bin/lint-agent-models`; the generator reads what is there rather than introducing a registry file to keep in sync with it.
- **The generator is a `bin/` script** following the repo's `uv run --script` convention with inline PEP 723 metadata, matching `bin/opencode-sync` and `bin/opencode-variant-audit`.
- **Wire checks as `prek` hooks** in `prek.toml`, following the shape at `:114-121` (`entry`, `language = "system"`, `pass_filenames = false`, `always_run = true`, `stages = ["pre-commit"]`).
- **Mark generated regions** in `rules/common/performance.md` and `install.py` following the existing `GENERATED_FILE_MARKER` convention (`bin/opencode-sync:189`). Agent files get no marker — nothing in them is generated.
- **Prefer extending `bin/lint-agent-models`** over a new script — it already parses all three declaration sites, in the same direction this design generates.
- Per repo rules: no `from __future__ import annotations`, `X | None` over `Optional[X]`, no lazy imports, `whenever` over stdlib `datetime` if any date handling arises.

## Replacement Targets

| Target | Replaced by | Disposition |
|---|---|---|
| `bin/opencode-sync:796-838` `generate_worker_agents()` | real agent files | remove outright |
| `bin/opencode-sync:841-967` `generate_specialist_opus_variants()` | escalation removal | remove outright |
| `bin/opencode-sync:1522-1536` `rewrite_all_dispatches()` and its rewrite helpers | correct-at-source dispatches | remove outright — but **not** `_walk_synced_md_files()` (`:1497-1519`), which `_lint_targets()` still calls at `:1552` |
| `bin/opencode-sync:1259-1303` `resolve()` and the five dispatch-translation regex constants | no translation needed | remove outright |
| `bin/opencode-sync:168,175,1153` `SPECIALIST_AGENTS`, `WORKER_AGENT_TEMPLATE`, `BUILTIN_CASE_MAP` | nothing — sole consumers are removed above | remove outright, comments included |
| `bin/opencode-sync:1256` `LINT_SUPPRESS_RE` and its `<!-- opencode-sync: ok -->` call sites | no lint to suppress | remove outright |
| `bin/opencode-sync:1042-1077` `build_agent_config()` | frontmatter resolution | remove outright |
| `bin/opencode-sync:1686-1722` `_config_json_pins()` | no `config.json` agent key to check | remove outright |
| `bin/opencode-sync:1725-1772` `check_variant_names()` and `:1775-1832` `_agent_variant_errors()` | narrowed to their two surviving subjects | **rewrite, do not remove** — drop the `_config_json_pins()` cross-check and the model-pin arm; keep TIER_MAP and frontmatter validation, `OPENCODE_VARIANTS`, and `run_lint()`'s call at `:1848` |
| `bin/opencode-sync:1562-1650` `_lint_content()`'s dispatch-residue checks | direct source assertion | rewrite — keep the rules-glob and exclusion checks |
| `bin/opencode-sync:2024-2091` `check_source_dispatch_patterns()` | direct source assertion (no scratch tree, no rewrite pass) | rewrite |
| `rules/common/performance.md` hand-maintained agent list | generated from agent frontmatter | migrate |
| `rules/common/performance.md:69-83` "Skill files with inline model declarations" list | nothing — FR#18 covers the only claim it could still make | remove outright (FR#29) |
| `bin/lint-agent-models` `SKILL_BULLET` (`:29`), its parse (`:66-67`), and its assertion loop (`:119-132`) | nothing — subject removed by FR#2 | remove outright (FR#29) |
| `install.py` hand-maintained `agents=(...)` tuples | generated from agent frontmatter (`bundle:` field) | migrate |
| `mine-orchestrate` escalation paths (`SKILL.md:640,651`, `spec-fix-loop.md:25,31`, `agent-routing.md:10-14`, `known-issues-protocol.md:59`) | nothing | remove outright |
| `spec-fix-loop.md:29`'s parenthetical rationale ("the user may want to retry with a stronger model") | the re-present instruction stays; its reason is reworded | rewrite |
| Other-typed gate choices in `spec-fix-loop.md:33,35` and `SKILL.md:652-659` | real `AskUserQuestion` options (FR#28) | migrate — handlers move, no new logic |
| `skills/mine-orchestrate/spec-reviewer-prompt.md` (126 lines) | `agents/spec-reviewer.md` | move — contents relocate into the agent body verbatim; the file is deleted, not copied (FR#26) |
| `bin/lint-verdict-line:29,42-46,62` — three hardcoded paths to `spec-reviewer-prompt.md` | `agents/spec-reviewer.md` | retarget — **blocking**: both `check_reviewer()` (`:86-93`) and `check_forbidden_vocab()` (`:147-154`) return `"file not found"` and exit non-zero if the path is deleted without this, and `lint-verdict-line` is a live pre-commit hook (`prek.toml:97-99`) |
| `skills/mine-orchestrate/verdict-line-format.md:28,80` — verdict-vocabulary table row and legitimate-hosts list | `agents/spec-reviewer.md` | retarget — AC#23's grep fails otherwise |
| `<!-- opencode-sync: ok -->` suppressions — five live occurrences: `findings-fix-loop.md:175`, `SKILL.md:651`, `SKILL.md:271`, `spec-fix-loop.md:31`, `commands/mine-permissions-audit.md:74`. Enumerate with `grep -rn 'opencode-sync: ok' skills skills-cli skills-impeccable commands agents` rather than working from this list | no lint to suppress | remove outright |

## Convention Examples

### Testing a `bin/` script

**Source:** `tests/test_opencode_variant_audit.py`

```python
import runpy
import pytest

def _load_script() -> dict:
    ...

@pytest.mark.parametrize(
    "variant,expected_resolved",
    [...],
)
def test_classify_verdicts(variant: str | None, expected_resolved: bool) -> None:
    ...

def test_fetch_honors_cutoff(tmp_path: Path) -> None:
    ...
```

`bin/` scripts are `uv run --script` files with no importable module, so tests load them via `runpy`. Parametrized cases plus `tmp_path` for filesystem fixtures.

### Docstrings explain why, cite sources, and warn against reverting

**Source:** `bin/opencode-sync:1080-1102`

```python
def build_instructions(config_dir: Path) -> list[str]:
    """Build the `instructions` list of config.json: the synced shared rules.

    Without this, the rules opkg installs under `<config>/rules/` are inert.
    OpenCode discovers global instructions from exactly two places
    (session/instruction.ts): its `instructions` config array, and the first
    existing entry of `[<config>/AGENTS.md, ~/.claude/CLAUDE.md]` -- note the
    `break`, so a present AGENTS.md means the Claude file is never read
    either. Nothing globs `<config>/rules/`.

    One glob per directory, never `**`: for an absolute path OpenCode globs
    only `basename(pattern)` within `dirname(pattern)`, so a recursive
    pattern silently matches nothing. [...]
    """
```

(Excerpted — the full docstring also cross-references `check_instruction_globs()` and explains why paths derive from `config_dir` rather than the module constant.)

Non-obvious behavior gets its upstream source cited by file and symbol, the failure mode named, and the wrong-looking-but-correct choice defended so it survives future cleanup.

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

### Marking generated content

**Source:** `bin/opencode-sync:189`

```python
GENERATED_FILE_MARKER = "<!-- GENERATED BY opencode-sync -- DO NOT EDIT MANUALLY. -->"
```

## Alternatives Considered

**Keep the dispatch rewriter, port its regexes to TypeScript.** Rejected. Three of the five dispatch-translation constants use Python-only conditional groups with no JavaScript equivalent, so this is a rewrite of hard-won patterns rather than a translation — each carries a comment documenting a specific bug it was hardened against. It also preserves the coupling this spec exists to remove.

**Keep the rewriter in Python; have callers shell out to it.** Rejected. Zero regex-port risk, but it keeps every translation function alive, adds subprocess latency per skill read, and still leaves shared content encoding one harness's ABI.

**Enforce a single canonical dispatch syntax and use one simple pattern.** Rejected as originally scoped. The variation is structural (six shapes including headings and table cells), not just delimiters, so normalizing it means rewriting prose across live Claude Code skills for an OpenCode-side simplification — against roadmap invariant `:229`. Its enforcement half survives: FR#18's check gates new dispatch sites.

**Intent-neutral role names resolving through per-harness mapping tables.** Rejected once probes confirmed both harnesses resolve agent names from files identically. A mapping table would have needed generation, a drift lint, and two-table consistency — all of which disappear when the dispatch target is simply an agent.

**A separate `agents.toml` registry generating agent frontmatter.** Rejected. This was the design's original shape, and it inverts a relationship the repo already has right: four of the five fields already live in frontmatter, and `bin/lint-agent-models` already treats frontmatter as ground truth (`:41-44`, `:69-91`). Only `bundle` was genuinely new — one line per file, against a whole new file format, a round-trip, and a generated-region marker inside every agent file. It is also lossy: a whole-block frontmatter generator erases the trailing `model:` comments that thirteen of twenty-three agent files carry (three of them explicit "do not downgrade — safety gate" warnings, `agents/code-reviewer.md:3`, `agents/integration-reviewer.md:3`, `agents/testing-reality-checker.md:3`), and drops the `color:`/`emoji:`/`vibe:` keys six agent files carry outside the five-field schema (all three keys on the five `engineering-*` agents; `color:` and `emoji:` only on `testing-reality-checker`). Generating outward from frontmatter instead needs no new format and cannot lose fields it does not know about.

**Intent-named generic agents (`triager`, `analyzer`, `critic`, `synthesizer`, `ideator`, `judge`, `reviewer`, `writer`, `implementer`).** Rejected after reading every site's model clause: the roster was a model-tier partition with verbs attached, exactly matching haiku on one side and sonnet on the other with no exceptions. Its bodies had nothing role-level to say, because the roles were not real — `analyzer` alone spanned git-churn analysis, evidence gathering, and angle-based exploration, and three of its four callers name themselves differently in their own prose. Naming what is actually there costs seven fewer agent files, ~560 fewer tokens of session baseline, and no invented methodology. See Architecture for the full argument. Real specialists — including the promoted `spec-reviewer` — keep their own agents, which is where independent retuning was ever worth anything.

**A bundle-coverage check failing when a skill dispatches an agent outside its own bundle plus `base`.** Rejected — it would fail on correct code the day it shipped. `mine-orchestrate` lives in `base` (every directory under `skills/` does, via `install.py`'s `base_skills()`), and its executor routing table names four agents from the optional `engineering` bundle (`skills/mine-orchestrate/agent-routing.md:19-23`; bundle membership at `install.py:169-180`). Those five rows are deliberate, they are dispatches by this design's own definition — the table-cell shape is one of the six catalogued above — and they already degrade gracefully, since an unmatched row falls through to the table's `general-purpose` default (`:24`, `:26`). The rule as worded flags all five. The same pattern appears in the sibling-skill pointer tables at `mine-how:17`, `mine-document:17`, and `mine-visual-qa:15`, which name `architect` and `visual-diff` from `extra-agents`.

Correctly scoping the check therefore means first deciding what a graceful cross-bundle dispatch *is* — currently an unwritten convention — and then spec'ing `commands/` as a third dispatch-bearing surface, since it has no bundle membership anywhere in `install.py` (the `Bundle` dataclass carries `skills`, `agents`, `packages`, and `capabilities_files`, with no `commands` field, `:73-80`; commands are always-installed independent of bundle selection, `:1438`) while two live dispatch sites already sit there (`commands/mine-issues.md`, `commands/mine-permissions-audit.md`). That is its own design question, and nothing in this migration forces it: every agent created here lands in `base` (FR#6), so the migration adds no new cross-bundle instance. Revisit as a standalone change, whose first job is the fallback convention, not the lint.

**Do nothing.** Rejected. The coupling is already costing a translation layer, and the plugin work parked as spec 1007 is substantially larger without this.

## Test Strategy

### Required Test Types

**Unit (pytest)** — for the generator and the new checks, following the existing `runpy` + `parametrize` + `tmp_path` pattern. This is where logic lands.

**Lint (prek hooks)** — the primary verification surface. The artifact is largely prose and generated files, so the invariants between them are what can be mechanically checked: dispatch/agent-file correspondence (FR#18) and generated-artifact staleness (FR#11).

**Gap:** no integration layer exists for observing OpenCode startup with Claude fallback disabled — roadmap Spec 1 called for an isolated fixture home and it was never built. This means FR#17's removal of config-level agent pinning is verified by source reading plus post-merge observation, not by an automated test. Named as an observability gap rather than covered.

### Existing Tests to Adapt

- `tests/test_opencode_sync.py` — substantial deletions. Tests covering `generate_worker_agents`, `generate_specialist_opus_variants`, `rewrite_all_dispatches`, `resolve()`, the dispatch regexes, and `build_agent_config` all lose their subject. The twelve `test_check_variant_names_*` tests are the exception: that function is narrowed rather than removed, so those tests are **adapted**, not deleted — only the cases asserting on `config.json` pins lose their subject. Losing the frontmatter-variant cases would drop coverage of the #514 failure mode.
- `tests/test_lint_agent_files.py` — extend if frontmatter gains a generated-region marker.
- `tests/test_install.py` — bundle contents become generated; tests already compare `bundle.agents` as sets (`:491-492`, `:637`), so order-independence holds.

### New Test Coverage

- Generator produces byte-identical output on repeated runs from unchanged input (FR#9, FR#10).
- Generator preserves fields it does not know about: an agent file carrying unknown frontmatter keys and a trailing comment on `model:` is unchanged on disk after a generator run (FR#8, AC#22). Use an `engineering-*` agent as the fixture — those carry all three of `color:`, `emoji:`, and `vibe:`; `testing-reality-checker` has no `vibe:` line to assert on.
- Staleness check exits non-zero when a generated artifact diverges (FR#11).
- Dispatch check fails on a name with no agent file, passes on a valid name (FR#18).
- Dispatch check distinguishes a dispatch from a prose mention (Edge Cases).
- Frontmatter completeness: every agent file declares all five required fields, and a file missing `bundle` is rejected by name (FR#23).

### Tests to Remove

All tests in `tests/test_opencode_sync.py` whose subject is a Replacement Target — worker generation, opus-variant generation, dispatch rewriting, `resolve()` routing, regex matching, and config-level agent pinning.

## Smoke Test

**Surface:** terminal output from the generator and the pre-commit hooks.

**Scenario:** change one agent's `model:` in its own file in `agents/`, run the generator, and confirm `performance.md`'s list entry and `install.py`'s tuples both reflect it — with no skill file modified, and that agent file otherwise byte-identical (its trailing `model:` comment and any display keys intact — pick an `engineering-*` agent, which carries all three of `color:`, `emoji:`, and `vibe:`). Then revert the change, re-run, and confirm `git diff --exit-code` is clean.

**Success:** one field edited in one file propagates to two generated artifacts; the edited file itself is not rewritten beyond that edit; no dispatch site anywhere required editing; a second run with unchanged input is a no-op.

**Second scenario:** add a dispatch naming a nonexistent agent to a scratch skill file and attempt a commit. Expect the hook to fail and name the missing agent. Delete the scratch file.

## Documentation Updates

- `REFERENCE.md` — `light-worker`, `standard-worker`, and `spec-reviewer` in the agent table; the generator script in the bin table; removal of `spec-reviewer-prompt.md` if it is listed among `mine-orchestrate`'s files.
- `ONBOARDING.md` — that dispatches name agents, and that an agent's model, effort, tools, and bundle are declared in its own frontmatter.
- `rules/common/performance.md` — its agent list becomes generated from agent frontmatter; the surrounding prose needs to say so, and the "Agent Model Declarations" section's manual-maintenance instructions are superseded. Its *other* list — "Skill files with inline model declarations" (`:69-83`) — is deleted outright rather than generated, per FR#29. The three safety-gate warnings currently carried in that prose (`:46-51`) now live authoritatively as comments on the corresponding `model:` lines; decide whether the generated list reproduces them or the prose points at the files.
- `design/opencode-integration-roadmap.md` — Workstream 3's dispatch-conversion scope is satisfied differently than written; Workstream 2's `-opus` variant machinery is removed. Also record two corrections found during investigation: OpenCode ships a worktree workspace adapter (`packages/opencode/src/control-plane/adapters/worktree.ts`) and exposes `experimental_workspace.register()`, so Workstream 6's premise that worktree isolation does not exist is stale; and background subagents are supported behind `OPENCODE_EXPERIMENTAL_BACKGROUND_SUBAGENTS=true` (`packages/opencode/src/tool/task.ts:98-100`), so the `run_in_background` warning has a fix available rather than being permanent.
- `CHANGELOG.md` — at PR creation, per repo convention.
- `bin/opencode-sync` module docstring — its task-accretion history no longer matches the file.
- `agents/secrets-auditor.md` — **two** read-only claims become literally false under FR#12's tool widening, not one. Its frontmatter description opens "Read-only credential scanner" (`:5`), and its body states "You are read-only — flag findings, never modify files" (`:9`). Delete both claims during migration rather than only the description. Check every other agent's body, not just its description, for the same pattern.
- `commands/mine-permissions-audit.md:74` — the line reads "Task tools — `Task(Explore)`, `Task(general-purpose)`, etc." Both named dispatch targets stop existing, so the line's *content* needs updating, not just the `<!-- opencode-sync: ok -->` marker it carries.

## Impact

### Changed Files

**Cross-cutting first:**

- create: `bin/<generator>` — generation + staleness check (or, per Implementation Preferences, an extension of `bin/lint-agent-models` rather than a new file)
- modify: `bin/opencode-sync` — large deletions per Replacement Targets
- modify: `bin/lint-agent-models` — becomes generation- and staleness-oriented
- modify: `install.py` — bundle tuples become generated
- modify: `rules/common/performance.md` — list becomes generated
- modify: `prek.toml` — hook wiring for new checks

**New agents:**

- create: `agents/light-worker.md`, `agents/standard-worker.md`
- create: `agents/spec-reviewer.md` — content moved from `skills/mine-orchestrate/spec-reviewer-prompt.md` (FR#26)
- delete: `skills/mine-orchestrate/spec-reviewer-prompt.md`
- modify: `bin/lint-verdict-line` — three hardcoded paths to the deleted prompt file retargeted to `agents/spec-reviewer.md`. Must land in the same commit as the deletion; the hook fails otherwise
- modify: `skills/mine-orchestrate/verdict-line-format.md` — same retarget, at `:28` and `:80`. Not in any dispatch grep, so it is invisible to the enumeration commands above

**Dispatch sites** — do not work from a fixed list here; enumerate at implementation time, since three separate forms are in play (`subagent_type:`, `cfl dispatch --agent-type`, and bare prose):

- modify: every file returned by `grep -rl 'general-purpose' skills skills-cli skills-impeccable commands agents` — currently 25 files, including `mine-plan`, `mine-address-pr-issues`, `mine-implementation-review`, `mine-visual-qa`, `mine-define/blind-spot-protocol.md`, `commands/mine-permissions-audit.md`, and six files under `mine-orchestrate/` beyond `SKILL.md`
- modify: `skills/mine-comb/SKILL.md` — a third shape: a named specialist (`fine-toothed-comb`) carrying a bare `model: sonnet` clause at `:30-31`, matched by neither grep above. Enumerate this class with AC#2's pattern
- modify: every file returned by `grep -rln 'cfl dispatch .*--model' skills skills-cli skills-impeccable commands` — strips `--model` from telemetry records. This set is **not** a subset of the one above: `skills/mine-sketch/SKILL.md:206` and `skills/mine-define/SKILL.md:145,224` dispatch *named specialists* with a `--model` argument and contain no `general-purpose` anywhere (FR#20, AC#15)
- modify: the `Explore` dispatch sites — `skills/mine-prior-art/SKILL.md`, `skills/mine-eval-repo/SKILL.md`, `commands/mine-issues.md`, `agents/researcher.md`. Enumerate by matching the dispatch form directly, scoped to the same directories as every other grep here — `grep -rl 'subagent_type[:=][^\n]*Explore' skills skills-cli skills-impeccable commands agents` — **not** a bare `grep -rl Explore` (15 files, most matching the ordinary verb in headings like "Explore the Codebase") and not a two-stage `subagent_type` filter piped through `grep -l Explore` (8 files — it matches any file having *some* dispatch plus the word "Explore" anywhere)
- modify: `agents/*.md` — `tools:` widening across the fleet, plus a `bundle:` line added to each file's frontmatter (FR#7). Frontmatter stays hand-written; these are ordinary edits, not generated output

**Escalation removal:**

- modify: `skills/mine-orchestrate/{SKILL.md,spec-fix-loop.md,agent-routing.md,known-issues-protocol.md,findings-fix-loop.md}` — the first four for escalation removal, `findings-fix-loop.md` only for its `<!-- opencode-sync: ok -->` suppression comment

**Tests:**

- modify: `tests/test_opencode_sync.py`, `tests/test_install.py`, `tests/test_lint_agent_files.py`
- modify: `tests/test_mine_orchestrate_protocol_contracts.py` — two anchors assert on the literal old dispatch shape: `:28` requires `cfl dispatch severity-fixer --agent-type general-purpose --model sonnet` verbatim in `known-issues-protocol.md`, and `:364` requires the literal string `general-purpose` in `agent-routing.md`'s fallback row. Both break on migration
- modify: `tests/test_lint_verdict_line.py` — runs `bin/lint-verdict-line` against the live repo, so it fails transitively until that script's three hardcoded paths are retargeted
- create: tests for the generator and new checks

**Tooling that parses the old dispatch shape** (analysis tools, not commit-time gates — these degrade silently rather than failing, which is why they are easy to miss):

- modify: `bin/orchestrate-cost` — exists to disambiguate the shared `general-purpose` agentType into real roles by prompt signature (`GP_SIGNATURES` `:89`, consumed at `:310-315`). Its `ORCHESTRATE_TYPES` allowlist (`:114`) does not contain the new agent names, so post-migration runs drop out of cost attribution with no error
- modify: `bin/orchestrate-concise-probe` — same pattern; resolves `spec-reviewer` only via a general-purpose signature match (`:51-52`, `:161-165`) and needs it as a direct agentType
- modify: `references/common/agents.md:44-50` — its "Subagent Types" table instructs `Explore` for reads and `general-purpose` for "full autonomy", and tells the reader to default to `Explore`. This is a domain reference loaded for subagent-orchestration work, so leaving it would keep teaching the shape this spec removes

<!-- Gap check 2026-08-16: 8 gaps found, all included. bin/lint-verdict-line (3 hardcoded paths) → T01; verdict-line-format.md:28,80 → T01; tests/test_lint_verdict_line.py → T01 (transitive); tests/test_mine_orchestrate_protocol_contracts.py:28 → T04; same file :364 → T04; bin/orchestrate-cost → T04; bin/orchestrate-concise-probe → T04; references/common/agents.md:44-50 → T06. All eight are indirect dependents (tests, tooling, docs that quote or parse the old shape); the gap check found zero missed direct dispatch sites. -->


### Behavioral Invariants

- Every skill's *behavior* is unchanged **except where a site is promoted to a named specialist whose pinned model differs from that site's current tier**. Migrating a site to a worker must always preserve its tier exactly — that is what choosing the worker *by* tier (FR#4, AC#24) guarantees. Promotions may change it, and every such change is named and accepted in Dependencies and Assumptions — none rides along silently.
- `bin/opencode-sync --check`, `--dry-run`, `--check-source`, and `--lint-only` continue to exist as CLI entry points and exit 0 on a clean tree. Their *implementations* change substantially (FR#21, FR#22) and what they report is deliberately reduced — this invariant is about the interface, not the checks behind it.
- `install.py` remains re-runnable and idempotent, and existing saved configs continue to load.
- Rules loading via `config.json`'s `instructions` array is untouched.
- Claude Code behavior must not regress (roadmap `:229`). Two deliberate exceptions, both accepted in Dependencies and Assumptions: escalation removal (FR#13), and fleet-wide `tools:` widening (FR#12), which overrides a different roadmap invariant (`:70`) and costs `secrets-auditor` its read-only guarantee specifically.

### Blast Radius

Every skill that dispatches a subagent, which is most of the `mine-*` fleet. Both harnesses. The pre-commit hook chain. `install.py`'s bundle definitions, and therefore any future re-install. Spec `1007-opencode-config-plugin` depends on this landing first and shrinks substantially when it does.

## Open Questions

None outstanding.

Three questions carried by earlier drafts are closed, and are recorded here so they are not reopened:

- *Whether removing the escalation option leaves orphaned logic in `spec-fix-loop.md` beyond the `AskUserQuestion` option itself.* Closed by tracing every consumer of the option label. There is no branch handling keyed on the choice, but there is orphaned prose — enumerated in FR#13, which now names each site rather than the four files. The trace also found that deleting the option leaves both gate prompts single-optioned; FR#28 and AC#27 cover reshaping them.
- *Whether `mine-document:228`/`mine-how:164` are `reviewer` and `mine-document:182`/`mine-how:131` are `synthesizer`.* Moot — all four dispatch at `sonnet` and become `standard-worker`. The classification only mattered while intent names existed.
- *Whether the nine `Explore` sites become an `explorer` agent or fold into `analyzer`.* Closed — they route by tier like every other site (Architecture, "The new agents"). One is `haiku`, the rest `sonnet`.
