# Design: Review Skill Consolidation

**Date:** 2026-05-25
**Status:** archived
**Scope-mode:** hold
**Research:** /tmp/claude-mine-prior-art-DUYybd/brief.md

## Problem

The existing review tools don't catch LLM-specific code smells — training-bias patterns that are syntactically correct, pass standard linters, and survive code review precisely because they look like good engineering (well-commented, defensively coded, properly abstracted). Academic research quantifies this: LLM-generated code has 42–85% more code smells than human-written code, with the gap widening on complex tasks.

The review skill landscape also has overlapping coverage. Three separate skills (`mine.review`, `mine.wtf`, `mine.nitpick`) run partially redundant reviewer sets with unclear boundaries. The automated pipeline runs two of these as separate sequential steps, adding cost and latency without clear separation of concerns.

## Goals

- Detect LLM training-bias patterns (obvious comments, defensive everything, unnecessary abstractions, dead helpers, over-engineered error hierarchies, context blindness) in branch diffs and file sets
- Detect deferred-debt and shortcut patterns (verbosity inflation, naming inconsistency, copy-paste, TODO rot) that accumulate when code is written hastily
- Consolidate review skills into two with clear ownership: technical correctness vs. stylistic quality
- Integrate stylistic review as a required gate in the orchestration pipeline and shipping flow

## User Scenarios

### Jessica: Developer

- **Goal:** ensure code quality before shipping
- **Context:** during development, at end of orchestration, before creating PRs

#### Manual review during development

1. **Invokes `/mine.review`**
   - Sees: consolidated findings from code-reviewer, integration-reviewer, and wtf-reviewer organized by severity
   - Decides: which findings to fix (all, critical/high only, or note and move on)
   - Then: fixes are applied; pre-commit gates run on the fixed code

2. **Invokes `/mine.clean-code`**
   - Sees: consolidated findings from llm-checker, lazy-checker, and nitpicker organized by category
   - Decides: which findings to fix (all, by category, or note and move on)
   - Then: fixes are applied; mine.review runs before committing

#### Automated review in orchestration

1. **Orchestration Phase 3 runs mine.clean-code automatically**
   - Sees: (Opus subagent handles this) findings from all three stylistic checkers
   - Then: subagent auto-fixes unambiguous issues, defers architectural judgment calls

#### Pre-ship gate

1. **Invokes `/mine.ship`**
   - Sees: mine.commit-push runs technical gates (code-reviewer + integration-reviewer), then mine.clean-code runs stylistic gate before PR creation
   - Decides: whether to proceed to PR after reviewing any unfixed findings
   - Then: PR is created

## Functional Requirements

- **FR#1** The system detects obvious-comment patterns where comments restate what the code does without adding information
- **FR#2** The system detects defensive coding at wrong trust boundaries — try/catch, null checks, and input validation on values already validated upstream or guaranteed by the type system
- **FR#3** The system detects unnecessary abstraction stacks — abstract base classes with one implementation, factories with one product, strategy patterns with one strategy
- **FR#4** The system detects dead helper methods and unused infrastructure — functions, utility classes, and config structures that are generated but never called
- **FR#5** The system detects over-engineered error hierarchies — custom exception trees where callers only catch the base class, paired with excessive entry/exit logging
- **FR#6** The system detects context blindness — design patterns applied where their preconditions don't hold (Singleton with no state, Builder for a simple config dict, Strategy with one concrete strategy)
- **FR#7** The system detects verbosity inflation — wrapper functions for trivial operations, redundant intermediate variables, repeated validation logic
- **FR#8** The system detects naming inconsistency within a file — mixed conventions, inconsistent abbreviations, generic names that communicate nothing
- **FR#9** The system detects deferred-debt patterns — TODO/FIXME rot without ticket references, copy-paste duplication instead of extraction, hardcoded values that should be configurable
- **FR#10** The technical review skill dispatches code-reviewer, integration-reviewer, and wtf-reviewer in parallel
- **FR#11** The technical review skill consolidates findings from all three reviewers by severity with deduplication
- **FR#12** The stylistic review skill dispatches llm-checker, lazy-checker, and nitpicker in parallel
- **FR#13** The stylistic review skill consolidates findings from all three checkers by category with cross-checker deduplication
- **FR#14** The technical review skill supports both diff mode (branch changes) and path mode (review files as-is)
- **FR#15** The stylistic review skill supports both diff mode and path mode
- **FR#16** The stylistic review skill runs as a single step in orchestration Phase 3, replacing the current separate wtf and nitpick steps
- **FR#17** The stylistic review skill runs as a quality gate before PR creation in the shipping flow
- **FR#18** Trigger phrases for the retired skills route to their replacement skills

## Edge Cases

- **Cross-checker duplicate findings**: The llm-checker flags "defensive code at wrong boundary" and the nitpicker flags the same code as "scattered constants in the try/catch block." The consolidation step must deduplicate by file:line, keeping the most specific finding and noting the cross-signal.
- **Overlap between code-reviewer's LLM section and llm-checker**: The code-reviewer has its own "LLM-Specific Smells" dimension (MEDIUM severity). When mine.review and mine.clean-code both run in the same pipeline (orchestration), some findings may appear in both passes. This is acceptable — each pass runs independently and the orchestration pipeline presents results sequentially.
- **Empty diff in path mode**: Files exist but have no changes on the branch. Both skills should review the files as-is without requiring a diff.
- **Large scope**: The existing mine.wtf caps at ~500 files (diff) / 200 files (path). Both new skills should inherit these limits.
- **Nitpicker agent conversion**: The nitpicker is converted from a REFERENCE.md template to a named agent file. The 10-category checklist and output format transfer verbatim; only the frontmatter wrapper is new.

## Acceptance Criteria

- **AC#1** Running `/mine.clean-code` on a branch with obvious LLM-generated code produces findings in at least 3 of the 6 LLM-checker categories (FR#1–FR#6)
- **AC#2** Running `/mine.clean-code` on a branch with hasty code produces findings from the lazy-checker (FR#7–FR#9)
- **AC#3** Running `/mine.review` dispatches all three technical reviewers in parallel and produces a consolidated report with deduplication (FR#10, FR#11)
- **AC#4** Running `/mine.wtf` invokes mine.review (FR#18)
- **AC#5** Running `/mine.nitpick` invokes mine.clean-code (FR#18)
- **AC#6** Orchestration Phase 3 runs mine.clean-code as a single step instead of separate wtf + nitpick steps (FR#16)
- **AC#7** `/mine.ship` runs mine.clean-code between commit-push and PR creation (FR#17)
- **AC#8** Running `/mine.review src/` on files with no branch changes reviews files as-is in path mode (FR#14)
- **AC#9** Running `/mine.clean-code src/` on files with no branch changes reviews files as-is in path mode (FR#15)

## Key Constraints

- The llm-checker must ask "does this code behave like it was written for a library/tutorial context?" rather than scanning for specific syntax patterns — the root cause is training-data bias, not syntactic mistakes
- The lazy-checker must be distinct from the nitpicker: lazy catches *patterns of shortcuts and deferred debt*; nitpick catches *individual instances of style violations*
- FR#2 (defensive coding) must reference `rules/common/reliability.md`'s "defensive at boundaries only" framing — findings should cite the trust boundary distinction
- FR#3 and FR#6 (abstractions, context blindness) require the reviewer to grep for callers/implementations — a structural check, not just visual pattern matching

## Dependencies and Assumptions

- The `code-reviewer`, `integration-reviewer`, and `wtf-reviewer` agents continue to exist as independent agent files
- The nitpicker's 10-category checklist and output format transfer cleanly into a named agent file
- `spec-helper`, `git-branch-base`, and `git-default-branch` CLI tools remain available
- The orchestration checkpoint system is unchanged

## Architecture

### New files

**`skills/mine.review/SKILL.md`** — Full skill replacing `commands/mine.review.md`. Adopts `skills/mine.wtf/SKILL.md`'s three-phase architecture (scope detection → parallel dispatch → consolidation) with the same three agents: `code-reviewer`, `integration-reviewer`, `wtf-reviewer`. The scope detection (diff vs. path mode), consolidation logic (deduplication, validity assessment, severity-organized output), and next-steps flow transfer from mine.wtf. The post-fix instruction in the next-steps flow must NOT be "run mine.review" (self-referential). Replace with: "Fixes complete — run `/mine.commit-push` or proceed to commit when ready." For mine.clean-code, the post-fix instruction remains "run `/mine.review` before committing." Trigger phrases absorb both mine.review and mine.wtf triggers.

**`skills/mine.clean-code/SKILL.md`** — New skill following the same three-phase architecture as mine.review. Dispatches three named agents in parallel: `llm-checker`, `lazy-checker`, and `nitpicker`. All three use the same dispatch pattern (`subagent_type: "<name>"`), eliminating the heterogeneous dispatch that would result from mixing named agents with REFERENCE.md templates. Output format: a Summary section at the top with aggregate counts (total findings, by-checker breakdown), followed by by-checker detail sections. Each checker's findings stay grouped since they represent different quality dimensions. Cross-checker duplicates are noted but not merged. When invoked from orchestration, the Opus subagent writes the Summary section to `clean-code-summary.md` for the shipping gate to consume. Next-steps flow offers "Fix all", "Fix one checker's findings", or "Note and move on".

**`agents/llm-checker.md`** — Named agent file following `agents/code-reviewer.md` conventions (frontmatter with name/group/model/description/tools, invocation patterns, review dimensions, output format, verdict criteria). Model: sonnet. Covers 6 training-bias patterns:

1. **Obvious-Comment Plague** — comments restating what the code does (`# Open connection` above `db.connect()`)
2. **Defensive Everything** — try/catch, null checks, validation at wrong trust boundaries; must distinguish from legitimate boundary validation per `rules/common/reliability.md`
3. **Unnecessary Abstraction Stack** — ABCs with one implementation, factories with one product. **Mandatory discovery step:** before flagging, the agent must grep for subclass implementations and callers across the repo and cite the grep result in the finding (mirror `integration-reviewer.md:103–116`). A finding without a grep citation for this pattern is classified UNCERTAIN, not SMELLS.
4. **Dead Helper Methods** — functions/classes generated but never called. **Mandatory discovery step:** before flagging, the agent must grep for callers across the repo and cite the grep result. A finding without a grep citation is classified UNCERTAIN, not SMELLS.
5. **Over-Engineered Error Hierarchies** — custom exception trees where callers only catch the base; paired with log-at-every-step
6. **Context Blindness** — GoF patterns where preconditions don't hold (Singleton with no state, Strategy with one concrete strategy)

Output format: findings table with LLM-smell category, description, and file:line. Verdict: CLEAN / SMELLS (count) — no BLOCK/APPROVE since these are quality signals, not correctness gates.

**`agents/nitpicker.md`** — Named agent file wrapping the existing nitpicker prompt template from `skills/mine.nitpick/REFERENCE.md`. Adds frontmatter (name, group, model: sonnet, description, tools: ["Read", "Grep", "Glob", "Bash"]) and preserves the 10-category checklist and output format. Converts the REFERENCE.md template into a proper agent with tool constraints matching llm-checker and lazy-checker.

**`agents/lazy-checker.md`** — Named agent file, same conventions. Model: sonnet. Covers deferred-debt patterns:

1. **Verbosity Inflation** — wrapper functions for trivial operations, redundant intermediate variables, repeated validation
2. **Naming Chaos** — mixed conventions within a file (camelCase + snake_case), inconsistent abbreviations, generic names (`data`, `result`, `temp`)
3. **Copy-Paste Duplication** — near-identical blocks differing only in field names or literals; should be a loop or shared helper
4. **TODO Rot** — TODO/FIXME/HACK/XXX comments without ticket references; feature flags that are always-on/off
5. **Hardcoded Shortcuts** — values that should be configurable (URLs, limits, paths) buried in business logic

Output format: same as llm-checker. Verdict: CLEAN / DEBT (count). For Copy-Paste Duplication and Hardcoded Shortcuts, scope the check to the reviewed files and their immediate import siblings (files they directly import). Do not attempt full-codebase scans — full-codebase duplication detection is integration-reviewer territory (Dimension 1: Duplication).

### Modified files

**`agents/wtf-reviewer.md`** — Remove the `### LLM-Specific Patterns` section entirely (all 4 bullet points: prompt-biased code, non-prompted consideration, defensive code for impossible cases, dead code from removed features). Move "Non-prompted consideration" (things the LLM should have thought about but didn't) into the `### Readability Debt` section with a clarifying note: "This is a completeness-of-thinking check — it applies equally to human-written code, not an LLM-specific smell." Add to the `## What NOT to Flag` section: "LLM-specific smell patterns — those belong to the `llm-checker` agent." The wtf-reviewer retains Readability Debt (now with the completeness check), Bespoke Complexity, and Structural Smells sections. Update the opening description to reflect the narrower scope. Update Invocation patterns: replace `**WTF skill** (\`mine.wtf\`)` with `**Technical review skill** (\`mine.review\`)`: passes diff command or file list in prompt — use what's provided.

**`skills/mine.orchestrate/post-execution-pipeline.md`** — Collapse Steps 4 (WTF check) and 5 (Nitpick check) into a single Step 4 (Clean code check). The new step launches one Opus subagent that runs `/mine.clean-code` on the full branch diff and auto-fixes unambiguous findings. The Step 4 subagent prompt is a full rewrite — the current prompts embed literal `/mine.wtf` and `/mine.nitpick` invocations plus skill-specific summary filenames that will not survive deletion. The new prompt must invoke `/mine.clean-code` and write its summary to `clean-code-summary.md` (replacing both `wtf-summary.md` and `nitpick-summary.md`). Renumber subsequent steps (old Step 6 → new Step 5, old Step 7 → new Step 6, old Step 8 → new Step 7). The shipping gate question replaces the two-line WTF/Nitpick summary with a single line: `Clean code check: <N fixed, M unfixed — or 'all clean'>`.

**`skills/mine.ship/SKILL.md`** — Add a Phase 1.5 between commit-push (Phase 1) and PR creation (Phase 2). Phase 1.5 checks for a `clean-code-summary.md` file in the skill tmpdir — if it exists and was written at the current git HEAD, skip Phase 1.5 silently with a note ("stylistic review already completed"). Otherwise, run `/mine.clean-code` on the branch diff. If findings exist, present them with an "Address findings" / "Ship anyway" / "Stop here" gate. "Address findings" applies fixes top-to-bottom (orchestrator edits directly, no subagent), then proceeds to Phase 2 without re-running mine.clean-code — single-pass, consistent with nitpick/wtf fix flows. "Ship anyway" proceeds to PR creation. This gate is advisory, not blocking — the user can choose to ship with style findings. If any checker subagent fails to complete, skip that checker's findings and note "unavailable" in the gate question — do not block PR creation for checker failures.

**`rules/common/capabilities-core.md`** — Update trigger phrases:
- mine.review absorbs mine.wtf triggers: "sniff test this", "WTF check", "code smells", "is this code any good", "fresh eyes on this branch", "review this directory", "check this module"
- mine.clean-code gets new triggers: "clean code check", "style review", "LLM smell check", "code hygiene" (absorbed from mine.nitpick)
- mine.nitpick triggers ("nitpick this", "style check", etc.) redirect to mine.clean-code
- mine.wtf row removed

**`rules/common/agents.md`** — Add routing entries for `llm-checker` and `lazy-checker` in the Agent Routing table. Remove `wtf-reviewer` as a standalone routing entry (it's only dispatched by mine.review, not directly by users).

**`rules/common/performance.md`** — Add model declarations for `agents/llm-checker.md` (sonnet), `agents/lazy-checker.md` (sonnet), and `agents/nitpicker.md` (sonnet) in the Agent Model Declarations list.

**`skills/mine.orchestrate/SKILL.md`** — Update any Phase 3 references that mention mine.wtf or mine.nitpick to reference mine.clean-code.

**`README.md`** — Add mine.clean-code and mine.review (skill) entries. Remove mine.wtf and mine.nitpick entries. Add llm-checker and lazy-checker agent entries.

### Deleted files

**`commands/mine.review.md`** — Replaced by `skills/mine.review/SKILL.md`.

**`skills/mine.wtf/SKILL.md`** — Replaced by `skills/mine.review/SKILL.md`. The entire `skills/mine.wtf/` directory is removed.

**`skills/mine.nitpick/SKILL.md`** — Standalone skill retired. The `skills/mine.nitpick/` directory is removed; `REFERENCE.md` content becomes `agents/nitpicker.md` (named agent).

## Replacement Targets

| Target | Replaced by | Action |
|---|---|---|
| `commands/mine.review.md` | `skills/mine.review/SKILL.md` | Delete command; full skill replaces it |
| `skills/mine.wtf/SKILL.md` | `skills/mine.review/SKILL.md` | Delete directory; mine.review adopts the 3-agent architecture |
| `skills/mine.nitpick/SKILL.md` + `REFERENCE.md` | `skills/mine.clean-code/SKILL.md` + `agents/nitpicker.md` | Delete directory; prompt template becomes a named agent file |
| `post-execution-pipeline.md` Steps 4+5 | Single Step 4 (mine.clean-code) | In-place edit; collapse two steps into one |
| wtf-reviewer LLM-Specific Patterns section | `agents/llm-checker.md` | In-place edit; remove section from wtf-reviewer |

## Convention Examples

### Agent file structure

**Source:** `agents/code-reviewer.md`

```markdown
---
name: code-reviewer
group: core
model: sonnet  # claude-sonnet-4-6 as of 2026-04-06
description: Expert code reviewer for correctness, security...
tools: ["Read", "Grep", "Glob", "Bash"]
---

You are a senior code reviewer. Your job is to find real problems...

## Invocation patterns
- **Orchestrate pipeline**: passes explicit file list — use it
- **Manual**: no file list — use self-discovery cascade

## Security (CRITICAL)
...

## Review Output Format
[CRITICAL] Finding title
File: path:line
Issue: [what's wrong]
Fix: [corrected code]

### Assessment
**Verdict:** APPROVE | WARN | BLOCK
```

### Parallel agent dispatch

**Source:** `skills/mine.wtf/SKILL.md:86-170`

```markdown
## Phase 2: Dispatch Three Parallel Reviewers

Launch all three agents **in a single message** so they run in parallel.

#### Reviewer 1: Code Review (`subagent_type: "code-reviewer"`)
[prompt with diff command]

#### Reviewer 2: Integration Review (`subagent_type: "integration-reviewer"`)
[prompt with diff command]

#### Reviewer 3: WTF Readability Pass (`subagent_type: "wtf-reviewer"`)
[prompt with diff command]
```

DO: dispatch all agents in one message for parallel execution.
DON'T: launch agents sequentially or set `run_in_background: true` (agents may need permissions).

### Findings consolidation

**Source:** `skills/mine.wtf/SKILL.md:174-230`

```markdown
## Phase 3: Consolidate Findings

### Step 1: Deduplicate
If two reviewers flagged the same issue, keep one entry and note
the cross-signal: `(flagged by code-review + WTF pass)`.

### Step 1.5: Validity assessment
Assess whether each finding holds up against the actual code.
Move likely-invalid findings to a separate section with evidence.

### Step 2: Present the consolidated report
Organize by severity, not by reviewer.
```

### Checklist-style reviewer prompt

**Source:** `skills/mine.nitpick/REFERENCE.md`

```markdown
You are The Nitpicker — a code quality obsessive...

## Your Checklist

### 1. Magic Numbers and Strings
- Literal numbers with no named constant
- Exception: 0 and 1 in arithmetic...

### 2. Scattered Constants
- Constants defined inline at the call site...

## Output Format
Group findings by category. Within each category:
  **`file.ext:line`** — [precise description]
If a category has zero findings: **(category name): clean**
```

### Scope detection (diff vs. path mode)

**Source:** `skills/mine.wtf/SKILL.md:26-78`

```markdown
## Phase 1: Determine Scope

### Step 1: Detect mode
If $ARGUMENTS is non-empty, check whether arguments resolve to paths:
- All paths exist → check for branch changes → diff or path mode
- No paths exist → diff mode on full branch

### Step 2a: Diff mode
git-branch-base → choose diff command → capture stats

### Step 2b: Path mode
find <paths> -type f → count → cap at 200 files
```

## Alternatives Considered

### Keep mine.wtf and add LLM/lazy as additional standalone skills

Would avoid the consolidation effort but perpetuates the unclear boundaries between mine.review, mine.wtf, and mine.nitpick. Users would have five review skills to choose from instead of two. Rejected because the consolidation is the mechanism for achieving clean ownership boundaries.

### Build all three checkers as REFERENCE.md templates instead of agent files

Would co-locate all checker logic in the mine.clean-code skill directory (like nitpick's original pattern). Rejected because dedicated agent files are independently reusable, discoverable via the agents table, follow the established pattern for reviewers in this codebase, and eliminate dispatch heterogeneity in the parallel launch. All three checkers — including the nitpicker — are named agent files.

### Wire mine.clean-code into mine.commit-push instead of mine.ship

Would make stylistic review mandatory on every commit, not just when shipping. Rejected because stylistic review is expensive (3 parallel agents) and most commits during active development don't need it — the orchestration and ship gates are sufficient enforcement points.

## Test Strategy

N/A — no test infrastructure in this repo.

## Documentation Updates

- **`README.md`**: Add `mine.clean-code` skill entry, update `mine.review` description (command → skill absorbing mine.wtf), remove `mine.wtf` and `mine.nitpick` entries, add `llm-checker` and `lazy-checker` agent entries
- **`rules/common/capabilities-core.md`**: Update trigger phrase routing — mine.review absorbs mine.wtf triggers, mine.clean-code absorbs mine.nitpick triggers and gets new triggers, remove mine.wtf and mine.nitpick rows
- **`rules/common/agents.md`**: Add routing entries for llm-checker and lazy-checker
- **`rules/common/performance.md`**: Add model declarations for llm-checker (sonnet) and lazy-checker (sonnet) in Agent Model Declarations list
- **`skills/mine.orchestrate/SKILL.md`**: Update Phase 3 references from mine.wtf/mine.nitpick to mine.clean-code

## Impact

### Changed Files

- `skills/mine.orchestrate/post-execution-pipeline.md` — Steps 4+5 collapse into single step (shared, high-risk — orchestration pipeline)
- `skills/mine.orchestrate/SKILL.md` — Phase 3 references updated (shared)
- `skills/mine.ship/SKILL.md` — New Phase 1.5 added (shared)
- `rules/common/capabilities-core.md` — Trigger phrase routing updated (shared)
- `rules/common/agents.md` — New agent routing entries (shared)
- `rules/common/performance.md` — New model declarations (shared)
- `agents/wtf-reviewer.md` — LLM section removed (agent file)
- `README.md` — Skill/agent entries updated (docs)
- `skills/mine.review/SKILL.md` — Created (new skill)
- `skills/mine.clean-code/SKILL.md` — Created (new skill)
- `agents/nitpicker.md` — Created (converted from mine.nitpick REFERENCE.md)
- `agents/llm-checker.md` — Created (new agent)
- `agents/lazy-checker.md` — Created (new agent)
- `commands/mine.review.md` — Deleted
- `skills/mine.wtf/SKILL.md` — Deleted (directory removed)
- `skills/mine.nitpick/SKILL.md` — Deleted (directory removed)
- `skills/mine.nitpick/REFERENCE.md` — Deleted (content moved to `agents/nitpicker.md`)

### Behavioral Invariants

- `code-reviewer` agent behavior is unchanged — same invocation patterns, same output format, same verdict criteria
- `integration-reviewer` agent behavior is unchanged
- `wtf-reviewer` agent continues to work for readability/maintainability review; narrower scope (no LLM section) but same output format
- mine.commit-push's code review loop (Steps 4-5) is unchanged — technical review gates are not affected
- Orchestration Phase 2 per-task review (code-reviewer + integration-reviewer + spec-reviewer) is unchanged
- Orchestration Phase 3 Steps 1-3 (summary, impl-review, cross-file consistency) are unchanged

### Blast Radius

- Any running orchestration pipeline will see different Phase 3 steps (Steps 4-5 become single Step 4)
- Users who invoke `/mine.wtf` or `/mine.nitpick` by muscle memory will get redirected — the functionality still exists but under different names
- The shipping flow gains an additional gate (mine.clean-code) that didn't exist before — slightly longer ship time

## Open Questions

None — all design decisions resolved during discovery.
