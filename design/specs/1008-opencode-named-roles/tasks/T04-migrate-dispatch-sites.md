---
task_id: "T04"
title: "Migrate every dispatch site to name a real agent"
status: "done"
depends_on: ["T01", "T03"]
implements: ["FR#1", "FR#2", "FR#4", "FR#20", "FR#24", "AC#1", "AC#2", "AC#15", "AC#20", "AC#24"]
---

## Summary

The central migration. Every subagent dispatch across `skills/`, `skills-cli/`, `skills-impeccable/`, `commands/`, and `agents/` stops naming a harness built-in with a sibling model clause and starts naming a real agent file. A site's worker is chosen by the tier it dispatches at today, so migration preserves every site's tier exactly. Where an existing specialist already covers a site's intent, the site dispatches that specialist instead — even when the specialist's pinned model differs from the site's current tier, in which case the change is recorded rather than avoided. The `cfl dispatch` telemetry form is migrated alongside, since it names the same agent and tier.

## Target Files

Do not work from a fixed list — enumerate at implementation time with the greps below, since four separate forms are in play and no single grep sees them all. The verified surface as of planning is 31 files:

- modify: `skills/mine-address-pr-issues/SKILL.md`, `skills/mine-brainstorm/SKILL.md`, `skills/mine-challenge/SKILL.md`, `skills/mine-comb/SKILL.md`, `skills/mine-create-issue/SKILL.md`, `skills/mine-create-pr/SKILL.md`, `skills/mine-decompose/SKILL.md`, `skills/mine-define/SKILL.md`, `skills/mine-define/blind-spot-protocol.md`, `skills/mine-document/SKILL.md`, `skills/mine-elevate/SKILL.md`, `skills/mine-eval-repo/SKILL.md`, `skills/mine-how/SKILL.md`, `skills/mine-implementation-review/SKILL.md`, `skills/mine-issues-triage/SKILL.md`, `skills/mine-mockup/SKILL.md`, `skills/mine-plan/SKILL.md`, `skills/mine-prior-art/SKILL.md`, `skills/mine-sketch/SKILL.md`, `skills/mine-visual-qa/SKILL.md`, `skills/mine-why/SKILL.md`
- modify: `skills/mine-orchestrate/SKILL.md`, `skills/mine-orchestrate/agent-routing.md`, `skills/mine-orchestrate/findings-fix-loop.md`, `skills/mine-orchestrate/known-issues-protocol.md`, `skills/mine-orchestrate/post-execution-pipeline.md`, `skills/mine-orchestrate/spec-fix-loop.md`, `skills/mine-orchestrate/visual-reviewer-launch.md`
- modify: `commands/mine-issues.md`, `commands/mine-permissions-audit.md`
- modify: `agents/researcher.md` — the only file in `agents/` containing dispatches (four `subagent_type: Explore` sites at `:82`, `:93`, `:101`, `:111`)
- modify: `tests/test_mine_orchestrate_protocol_contracts.py` — two anchors assert on the literal pre-migration shape (`:28`, `:364`)
- modify: `bin/orchestrate-cost` — `GP_SIGNATURES` (`:89`), `ORCHESTRATE_TYPES` (`:114`), and the resolution branch at `:310-315`
- modify: `bin/orchestrate-concise-probe` — `spec-reviewer` signature matching at `:51-52` and `:161-165`
- modify: `design/specs/1008-opencode-named-roles/design.md` — record any newly discovered tier change in Dependencies and Assumptions (FR#24)
- read: `agents/` — the roster of real agent names available as dispatch targets
- read: `rules/common/performance.md` — the `subagent-model-default` hook's injection behavior, which determines the effective tier of a site carrying no explicit model clause

## Prompt

Read `design/specs/1008-opencode-named-roles/design.md`, sections **Problem** (the four dispatch-bearing forms), **Architecture → The new agents**, **Key Constraints**, **Impact → Changed Files → Dispatch sites**, and FR#1, FR#2, FR#4, FR#20, FR#24.

**1. Enumerate the surface. Do not work from memory or from the design's illustrative table.**

Four greps, because no single one sees every form:

```
grep -rl 'general-purpose' skills skills-cli skills-impeccable commands agents
grep -rE 'model:\s*(sonnet|haiku|opus)' skills skills-cli skills-impeccable commands
grep -rln 'cfl dispatch .*--model' skills skills-cli skills-impeccable commands
grep -rn 'subagent_type[:=][^\n]*Explore' skills skills-cli skills-impeccable commands agents
```

The second is authoritative for scoping (AC#2) and has no false negatives against the corpus. The first two characterize shapes but each misses live sites: `skills/mine-comb/SKILL.md:30-31` dispatches the already-named specialist `fine-toothed-comb` with a bare `model: sonnet` clause, so neither the `general-purpose` grep nor the `cfl dispatch` grep sees it. The third set is **not** a subset of the first: `skills/mine-sketch/SKILL.md:206` and `skills/mine-define/SKILL.md:145,224` record `--agent-type <named-specialist> --model <tier>` and contain no `general-purpose` anywhere.

For the Explore form use the pattern given above, not a bare `grep -rl Explore` (15 files, most matching the ordinary verb in headings like "Explore the Codebase") and not a two-stage `subagent_type` filter piped through `grep -l Explore` (8 files — it matches any file having some dispatch plus the word "Explore" anywhere).

**2. Migrate each site by tier, auditing for a specialist first.**

For each site: determine the tier it dispatches at today, then pick its target.

- If an existing specialist in `agents/` already covers the site's intent, name that specialist. The worker is the fallback, not the default — audit each site individually.
- Otherwise name `light-worker` if the site runs at haiku, `standard-worker` if it runs at sonnet.

A site carrying no explicit model clause is not tier-less: the `subagent-model-default` hook injects `sonnet` for built-in types. Confirm each such site's injected tier rather than assuming — this applies to the eight Explore sites that carry no model clause (`commands/mine-issues.md:31` is the one that declares `model: haiku` explicitly and becomes `light-worker`).

Then delete the model clause. Preserve the prose shape — the six structural shapes (YAML block, function-call, inline prose, list item, heading, table cell) stay as shapes; only their content changes.

**3. Migrate the `cfl dispatch` telemetry form (FR#20).**

Each `cfl dispatch <role> --agent-type <X> --model <tier>` must name the same agent its sibling dispatch now names, with the `--model` argument removed entirely. Nine files, 32 occurrences.

**4. Record tier changes (FR#24).**

Promotion to a specialist can change a site's tier, and that is accepted — but every instance must be written into the design's **Dependencies and Assumptions** before this task is done. One is already recorded: `skills/mine-prior-art/SKILL.md:61` moves from `model: sonnet` to `agents/researcher.md`'s pinned `model: opus`. Compare each promoted site's current tier against the target specialist's pinned model and add an entry for every difference you find. Do not retune the specialist to avoid a difference — that would change behavior for its other callers.

**5. Fix the dependents that parse the old shape.**

- `tests/test_mine_orchestrate_protocol_contracts.py:28` requires the literal `cfl dispatch severity-fixer --agent-type general-purpose --model sonnet` in `known-issues-protocol.md`. Update the anchor to the migrated string.
- Same file, `:364` requires the literal `general-purpose` in `agent-routing.md`'s fallback route. Update it to match the migrated fallback (`standard-worker`).
- `bin/orchestrate-cost` exists to disambiguate the shared `general-purpose` agentType into real roles by prompt signature. Add the new agent names to `ORCHESTRATE_TYPES` (`:114`) so migrated runs stay in the cost taxonomy, and prune the `GP_SIGNATURES` entries (`:89`) whose subject no longer dispatches as `general-purpose`.
- `bin/orchestrate-concise-probe` resolves `spec-reviewer` only via a general-purpose signature match (`:51-52`, `:161-165`). Add `spec-reviewer` as a direct agentType.

## Focus

**The single largest trap: do not strip `model:` from agent frontmatter.** A naive union grep across the four patterns returns 53 files, but 22 of them are `agents/*.md` matching solely on their own frontmatter `model:` line — the declaration site FR#7 requires and T01 just established. `agents/researcher.md` is the only file in `agents/` with dispatches in its body. AC#2's grep deliberately scopes to `skills skills-cli skills-impeccable commands` for exactly this reason; AC#1's grep includes `agents/` but checks dispatch *names*, not model clauses.

**`bin/orchestrate-cost` and `bin/orchestrate-concise-probe` fail silently.** Neither is a commit-time gate. If they are not updated, orchestrate runs simply drop out of cost attribution and concise-mode probing with no error anywhere — the failure surfaces weeks later as missing data. This is why they are in scope despite nothing breaking loudly.

**Verified counts to check your enumeration against** (as of planning): 25 files contain `general-purpose`; 24 files carry 34 `model: <tier>` clause occurrences; 9 files carry 32 `cfl dispatch --model` occurrences; 9 `Explore` dispatch sites across 4 files (`agents/researcher.md` ×4, `skills/mine-eval-repo/SKILL.md` ×3, `skills/mine-prior-art/SKILL.md` ×1, `commands/mine-issues.md` ×1). A materially different count means your grep differs from the ones above — reconcile before editing.

**Two prose mentions need a content change, not just a marker removal.** Both name `general-purpose` as a bare word with no `subagent_type`, no `model:` clause, and no `agent-type` argument — so none of this task's four greps, and none of its Verify criteria, will catch either one. Find them by hand:

- `commands/mine-permissions-audit.md:74` reads "Task tools — `Task(Explore)`, `Task(general-purpose)`, etc." Both named targets stop existing, so the line's meaning is what is stale.
- `skills/mine-orchestrate/SKILL.md:271` reads "determine if a specialized agent is a better fit than `general-purpose`". Reword to name the fallback worker (`standard-worker`) instead. T05 removes this line's `<!-- opencode-sync: ok -->` marker; the sentence itself is yours.

`grep -rn 'general-purpose' skills skills-cli skills-impeccable commands agents` returning zero at the end of this task is the check that catches both.

**T03 already deleted the escalation text**, which removed two `general-purpose` occurrences (`SKILL.md:651`, `spec-fix-loop.md:31`). Your enumeration will therefore return fewer sites than the design's Problem section states. That is expected, not a discrepancy.

**`<!-- opencode-sync: ok -->` suppressions** are removed by T05 along with the lint that reads them. Leave any you encounter in place; deleting them here creates a conflict with that task.

**This task's Verify criteria are repo-wide greps**, so no partial migration passes. Run them before declaring done.

## Verify

- [ ] FR#1: `grep -rE 'subagent_type' skills skills-cli skills-impeccable commands agents` returns only dispatches naming agents that have files in `agents/`.
- [ ] FR#2: No dispatch site in `skills/`, `skills-cli/`, `skills-impeccable/`, or `commands/` carries a `model:` tier clause.
- [ ] FR#4: Every migrated site names the worker matching the tier it dispatched at before migration.
- [ ] FR#20: No `cfl dispatch` invocation in shared content passes `--model`, and each names the same agent its sibling dispatch names.
- [ ] FR#24: Every site whose tier changed as a result of specialist promotion has an entry in the design's Dependencies and Assumptions.
- [ ] AC#1: `grep -rE 'subagent_type' skills skills-cli skills-impeccable commands agents` returns only dispatches naming agents that have files in `agents/`.
- [ ] AC#2: `grep -rE 'model:\s*(sonnet|haiku|opus)' skills skills-cli skills-impeccable commands` returns no dispatch-site matches.
- [ ] AC#15: `grep -rn 'agent-type general-purpose' skills skills-cli skills-impeccable commands` returns no matches, and no `cfl dispatch` invocation in shared content passes `--model`.
- [ ] AC#20: For every site migrated to a named specialist, `git diff <base>..HEAD` on that file shows either the same model tier as before, or the file is named in the design's Dependencies and Assumptions as an accepted tier change.
- [ ] AC#24: Every migrated dispatch site's worker matches its prior tier — a site that carried `model: haiku` names `light-worker`, one that carried `model: sonnet` (explicitly or by hook injection) names `standard-worker`.
