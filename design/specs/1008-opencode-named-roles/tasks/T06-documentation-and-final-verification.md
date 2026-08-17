---
task_id: "T06"
title: "Update the documentation set and verify the end state"
status: "done"
depends_on: ["T02", "T05"]
implements: ["AC#13", "AC#14"]
---

## Summary

Bring the documentation set in line with what shipped, and run the repo-wide gates that no earlier task can satisfy alone. The doc work is not cosmetic: `references/common/agents.md` is a domain reference loaded whenever an agent does subagent-orchestration work, and it currently instructs the reader to use exactly the dispatch shape this spec removes. Leaving it would teach the old shape back into the codebase. This task owns the two end-state assertions — the full test suite and the full hook chain — because they are the only criteria that depend on every prior task having landed.

## Target Files

- modify: `references/common/agents.md` — the "Subagent Types" table at `:44-50` and the "Default to `Explore`" line at `:52`
- modify: `REFERENCE.md` — add `light-worker`, `standard-worker`, `spec-reviewer` to the agent table; add the generator to the bin table; remove `spec-reviewer-prompt.md` if listed among `mine-orchestrate`'s files
- modify: `ONBOARDING.md` — that dispatches name agents, and that an agent's model, effort, tools, and bundle are declared in its own frontmatter
- modify: `design/opencode-integration-roadmap.md` — Workstream 3's dispatch-conversion scope, Workstream 2's `-opus` machinery, plus two corrections found during investigation
- modify: `bin/opencode-sync` — the module docstring, whose task-accretion history no longer matches the file
- read: `design/specs/1008-opencode-named-roles/design.md` — the **Documentation Updates** section is this task's checklist
- read: `CLAUDE.md` — the repo's own rules on which docs must be updated when components change

## Prompt

Read `design/specs/1008-opencode-named-roles/design.md`, section **Documentation Updates**, which enumerates this task's scope. Work through it, plus the items below.

**1. `references/common/agents.md` (`:44-52`) — the highest-stakes doc change.**

Its "Subagent Types" table currently reads:

| Need | `subagent_type` |
|------|----------------|
| Read code, search, analyze | `Explore` (fast, Haiku, read-only) |
| Full autonomy (write, run, search) | `general-purpose` |
| Domain-specific review | Named agent (e.g., `code-reviewer`) |

followed by "Default to `Explore` unless the subagent needs to write files, run commands, or search the web."

Both `Explore` and `general-purpose` stop being valid dispatch targets. Rewrite the table and the default-guidance line so they describe the post-migration model: a dispatch names an agent; pick the specialist whose role matches, and otherwise pick the worker matching the tier the work needs. Note that the read-only/write-capable distinction the table encodes is also gone — FR#12 widened `tools:` fleet-wide — so guidance keyed on "needs to write files" no longer selects anything.

**2. `REFERENCE.md` and `ONBOARDING.md`.**

Per `CLAUDE.md`, `REFERENCE.md` holds the full component tables and must be updated when agents or bin scripts are added, removed, or renamed; `ONBOARDING.md` must be updated when a new adopter needs to know about a capability. Both apply here.

**3. `design/opencode-integration-roadmap.md`.**

Workstream 3's dispatch-conversion scope is satisfied differently than written, and Workstream 2's `-opus` variant machinery is removed. Also record two corrections found during this spec's investigation:

- OpenCode ships a worktree workspace adapter (`packages/opencode/src/control-plane/adapters/worktree.ts`) and exposes `experimental_workspace.register()`, so Workstream 6's premise that worktree isolation does not exist is stale.
- Background subagents are supported behind `OPENCODE_EXPERIMENTAL_BACKGROUND_SUBAGENTS=true` (`packages/opencode/src/tool/task.ts:98-100`), so the `run_in_background` warning has a fix available rather than being permanent.

**4. `bin/opencode-sync`'s module docstring.**

It describes a task-accretion history that no longer matches the file after T05's deletions.

**5. Run the end-state gates.**

`mise run test:root` (which runs `pytest tests/`) and `prek run --all-files`. These are AC#13 and AC#14. Fix anything they surface; if a failure belongs to an earlier task's scope, fix it here rather than leaving the suite red — this is the last task.

**Not in scope:** `CHANGELOG.md`. Per repo convention and `rules/common/git-workflow.md`, changelog entries are written at PR creation, not during feature work.

## Focus

**`references/common/agents.md` is loaded as a domain reference, not read as prose.** `rules/common/invariants.md`'s Domain References table routes any work on "subagent orchestration, parallel executors" to it as a blocking read. An agent doing that work after this migration would be told to dispatch `Explore` and `general-purpose` — names that no longer resolve. This is the one doc in the set whose staleness actively causes regressions rather than just misleading a reader.

**Do not invent counts.** Per the repo's own conventions, `REFERENCE.md` and `performance.md` must not carry numeric counts of agents, skills, or files. Add the rows; do not add or update a total.

**`performance.md` is not in this task's scope** even though it is a doc. T02 made its agent list generated and deleted its skill-declarations list, including the surrounding prose. Editing it here risks conflicting with the generated region.

**The two verification criteria are genuinely global.** No earlier task can assert AC#13 or AC#14 honestly, because each lands only part of the change and the hook chain runs against the whole tree. Expect the first full `prek run --all-files` to surface something — the orphan check (T05), the staleness check (T02), and `lint-agent-models` all run together here for the first time against a fully migrated tree.

**Smoke test.** The design's **Smoke Test** section defines two scenarios worth running by hand once the gates are green: (1) change one agent's `model:` in its own file, run the generator, confirm `performance.md` and `install.py` both reflect it while that agent file stays byte-identical apart from the edit — use an `engineering-*` agent, which carries all three of `color:`, `emoji:`, and `vibe:` — then revert and confirm `git diff --exit-code` is clean; (2) add a dispatch naming a nonexistent agent to a scratch skill file, attempt a commit, expect the hook to fail naming the missing agent, then delete the scratch file.

## Verify

- [ ] AC#13: `timeout 300 mise run test:root` passes with zero failures.
- [ ] AC#14: `prek run --all-files` passes.
