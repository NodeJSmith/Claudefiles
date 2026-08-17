---
task_id: "T01"
title: "Create the worker and spec-reviewer agents, widen the fleet"
status: "planned"
depends_on: []
implements: ["FR#3", "FR#5", "FR#6", "FR#7", "FR#12", "FR#26", "FR#27", "AC#3", "AC#4", "AC#5", "AC#19", "AC#23", "AC#25"]
---

## Summary

Build the agent fleet that every later task depends on. Three agents are created: `light-worker` (haiku) and `standard-worker` (sonnet), which absorb every dispatch that names no specialist, and `spec-reviewer` (sonnet), a real specialist whose 126-line methodology moves out of `skills/mine-orchestrate/spec-reviewer-prompt.md` and into the agent body. All 23 existing agent files gain a `bundle:` frontmatter field and a widened `tools:` list. Nothing dispatches these agents yet — that is T04. This task only has to leave the tree green.

## Target Files

- create: `agents/light-worker.md`
- create: `agents/standard-worker.md`
- create: `agents/spec-reviewer.md`
- delete: `skills/mine-orchestrate/spec-reviewer-prompt.md`
- modify: `agents/architect.md`, `agents/code-judo-reviewer.md`, `agents/code-reviewer.md`, `agents/engineering-backend-developer.md`, `agents/engineering-data-engineer.md`, `agents/engineering-frontend-developer.md`, `agents/engineering-sre.md`, `agents/engineering-technical-writer.md`, `agents/fine-toothed-comb.md`, `agents/instruction-quality-reviewer.md`, `agents/integration-reviewer.md`, `agents/issue-refiner.md`, `agents/lazy-checker.md`, `agents/llm-checker.md`, `agents/nitpicker.md`, `agents/planner.md`, `agents/qa-specialist.md`, `agents/researcher.md`, `agents/secrets-auditor.md`, `agents/testing-reality-checker.md`, `agents/visual-diff.md`, `agents/writing-quality-reviewer.md`, `agents/wtf-reviewer.md` — add `bundle:`, widen `tools:`
- modify: `agents/secrets-auditor.md` — additionally, delete both read-only claims (frontmatter description `:5`, body `:9`)
- modify: `skills/mine-orchestrate/SKILL.md` — the two `spec-reviewer-prompt.md` references at `:378` and `:421`
- modify: `skills/mine-orchestrate/verdict-line-format.md` — the table row at `:28` and the hosts-list entry at `:80`
- modify: `bin/lint-verdict-line` — three hardcoded paths at `:29`, `:42-46`, `:62`
- modify: `rules/common/performance.md` — hand-add the three new agents to the declaration list
- modify: `install.py` — hand-add the three new agents to the `base` bundle tuple at `:112-126`
- read: `tests/test_lint_verdict_line.py` — runs `bin/lint-verdict-line` against the live repo; it fails transitively until the retarget above lands, and passes again afterward with no edit of its own
- read: `design/specs/1008-opencode-named-roles/design.md`
- read: `agents/engineering-sre.md` — source of the verbatim Executor note
- read: `bin/lint-agent-models` — the checks this task must keep green

## Prompt

Read `design/specs/1008-opencode-named-roles/design.md`, sections **Functional Requirements** (FR#3, FR#5, FR#6, FR#7, FR#12, FR#26, FR#27), **Key Constraints**, **Architecture → The new agents**, **Architecture → The declaration site**, and **Dependencies and Assumptions**.

**1. Create the two worker agents.**

`agents/light-worker.md` declares `model: haiku`; `agents/standard-worker.md` declares `model: sonnet`. Both declare `effort: high`, a `description:`, a widened `tools:` list, and `bundle: base`.

Each body states only the dispatch discipline every caller relies on: write output to the path the caller names, cite evidence for findings, stay inside the assigned scope. No task-specific process content, and no mention of any specific skill — AC#4 asserts `grep -c 'mine-' <file>` returns 0 for each. These bodies are deliberately short; the design's Dependencies and Assumptions notes they will not resemble the 38-line floor the rest of the fleet sets, because a worker's methodology arrives with the prompt.

`agents/standard-worker.md` additionally carries the Executor note block verbatim as it appears at `agents/engineering-sre.md:16`, because `skills/mine-orchestrate/agent-routing.md`'s fallback row migrates to it (FR#27). Copy that line exactly; do not paraphrase.

**2. Move the spec reviewer.**

Create `agents/spec-reviewer.md` with frontmatter (`model: sonnet`, `effort: high`, `description:`, widened `tools:`, `bundle: base`) and the full contents of `skills/mine-orchestrate/spec-reviewer-prompt.md` as its body. This is a move, not a copy — delete the prompt file. Then retarget every reference to the deleted path:

- `skills/mine-orchestrate/SKILL.md:378` (a `Read` instruction) and `:421` (a `<full spec-reviewer-prompt.md content>` placeholder). The dispatch itself becomes `subagent_type: spec-reviewer` supplying only per-run context; the skill no longer inlines the methodology.
- `skills/mine-orchestrate/verdict-line-format.md:28` (verdict-vocabulary table row) and `:80` (the legitimate-hosts list).
- `bin/lint-verdict-line` at `:29` (`REVIEWERS_WITHOUT_COUNT`), `:42-46` (the `REVIEWER_ALLOWED_VERDICTS` key), and `:62` (`ACTIVE_CONTRACT_FILES`).

**3. Widen `tools:` across the fleet and add `bundle:`.**

Every file in `agents/` gets a `tools:` list containing at minimum `Read`, `Write`, `Edit`, `Bash`, `Grep`, `Glob` (AC#19), and a `bundle:` line naming the bundle it already belongs to in `install.py` (`base`, `frontend`, `cli`, `engineering`, or `extra-agents` — read `install.py`'s `get_bundles()` to get each agent's current membership; do not guess).

Preserve everything else in each frontmatter exactly: the trailing rationale comments on `model:` lines (thirteen files carry one; three are safety-gate warnings), and the `color:`/`emoji:`/`vibe:` keys six files carry.

`agents/secrets-auditor.md` needs one extra edit: delete **both** read-only claims, the frontmatter description's opening "Read-only credential scanner" (`:5`) and the body's "You are read-only — flag findings, never modify files" (`:9`). Both become false under FR#12. While editing the fleet, check every other agent's **body** as well as its description for the same pattern and delete any you find.

**4. Keep the tree green.**

`bin/lint-agent-models` requires every `agents/*.md` to appear in `rules/common/performance.md`'s list and in exactly one `install.py` bundle tuple. Hand-add the three new agents to both. In `performance.md` the list-entry format is `` - `agents/<name>.md` — <model>, <effort> `` (see `AGENT_BULLET` at `bin/lint-agent-models:26-28`). In `install.py`, add all three to the `base` tuple at `:112-126`. T02 converts both sites to generated output; this hand-edit is the bridge.

## Focus

**The `lint-verdict-line` retarget is blocking, not cosmetic.** `bin/lint-verdict-line` is a live pre-commit hook (`prek.toml:97-99`). Both `check_reviewer()` (`:86-93`) and `check_forbidden_vocab()` (`:147-154`) return `"<path>: file not found"` and exit non-zero on a missing file. Delete `spec-reviewer-prompt.md` without updating those three constants and this task's own commit fails. Neither the design's original Impact section nor any dispatch grep surfaces `bin/lint-verdict-line` — it was found by tracing the deleted path.

**Do not strip `model:` from agent frontmatter.** That line is the declaration site FR#7 requires. Removing dispatch-site model clauses is T04's job and applies to skills and commands, not to `agents/*.md`. Twenty-two of the twenty-three agent files contain no dispatch at all — they match a naive `model:` grep purely on their own frontmatter. `agents/researcher.md` is the only agent file with dispatches in its body, and those are T04's.

**`bundle:` values must be read, not inferred from the name.** `testing-reality-checker` sits in the `engineering` bundle, not `base`, despite not being an `engineering-*` file (`install.py:169-180`). `architect`, `planner`, `qa-specialist`, and `visual-diff` are in `extra-agents` (`:181-185`). The `base` tuple is at `:112-126`.

**Body content bar.** The design's Key Constraints set the bar for what a worker body may contain: dispatch discipline only. Resist writing a methodology — the whole argument for two workers rather than nine intent agents is that no invariant methodology exists at these sites.

**Verify locally with the real hooks**, not by inspection: `bin/lint-agent-models`, `bin/lint-verdict-line`, and `bin/lint-agent-files` all run on commit.

## Verify

- [ ] FR#3: `agents/light-worker.md` and `agents/standard-worker.md` exist, declaring `model: haiku` and `model: sonnet` respectively.
- [ ] FR#5: Both worker bodies state each of the three dispatch-discipline points (write output to the caller's named path, cite evidence for findings, stay inside the assigned scope), and neither names a specific skill or workflow step — `grep -c 'mine-' agents/light-worker.md agents/standard-worker.md` returns 0 for each.
- [ ] FR#6: `light-worker`, `standard-worker`, and `spec-reviewer` all declare `bundle: base`.
- [ ] FR#7: Every file in `agents/` declares all five of `model`, `effort`, `tools`, `description`, and `bundle` in its frontmatter.
- [ ] FR#12: Every agent's `tools:` list contains at minimum `Read`, `Write`, `Edit`, `Bash`, `Grep`, `Glob`, and `grep -rin 'read-only' agents/` returns no match claiming an agent cannot write.
- [ ] FR#26: `agents/spec-reviewer.md` carries the former prompt file's methodology; `skills/mine-orchestrate/spec-reviewer-prompt.md` is deleted; `bin/lint-verdict-line` exits 0.
- [ ] FR#27: `agents/standard-worker.md` contains the Executor note block byte-identical to `agents/engineering-sre.md:16`.
- [ ] AC#3: `agents/light-worker.md` and `agents/standard-worker.md` exist declaring `haiku` and `sonnet`, and no file exists in `agents/` named `triager`, `analyzer`, `critic`, `synthesizer`, `ideator`, `judge`, `reviewer`, `writer`, or `implementer`.
- [ ] AC#4: Both worker files have non-empty body content below their frontmatter, and `grep -c 'mine-' agents/light-worker.md agents/standard-worker.md` returns 0 for each.
- [ ] AC#5: `light-worker`, `standard-worker`, and `spec-reviewer` all appear in `install.py`'s `base` bundle tuple.
- [ ] AC#19: Every agent file's `tools:` list contains at minimum `Read`, `Write`, `Edit`, `Bash`, `Grep`, `Glob`.
- [ ] AC#23: `grep -rn 'spec-reviewer-prompt' skills/ bin/` returns no matches, and `bin/lint-verdict-line` exits 0.
- [ ] AC#25: `agents/standard-worker.md` contains the Executor note block verbatim as it appears in `agents/engineering-sre.md:16`.
