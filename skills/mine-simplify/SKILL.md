---
name: mine-simplify
description: "Use when the user says: \"simplify this codebase\", \"find simplification opportunities\", \"where can I simplify\", \"code judo this\", \"judo this module\", \"find structural simplifications\", \"what can I collapse\", \"reduce complexity in this code\". Runs the code-judo posture against existing code (a file, directory, or whole repo) — not a diff — fanning out parallel structural-simplification reviewers and consolidating their moves into one impact-ranked report."
user-invocable: true
---

# Simplify (Codebase Judo)

Hunts for dramatic structural simplifications across a body of **existing** code — moves that delete whole layers, collapse abstractions, or replace orchestration with a data transformation while preserving behavior. This is the on-demand, codebase-scoped form of the `code-judo-reviewer` posture: same structural simplification lens, pointed at existing code rather than a branch diff.

Use this to judo a module you suspect is over-built, audit a subsystem for collapse opportunities, or sweep a small repo for structural debt. This is **not** a correctness review (use `/mine-review`), a style sweep (use `/mine-clean-code`), a broad health audit (use `/mine-audit`), or a split-the-big-file analysis (use `/mine-decompose` — that splits; this collapses).

## Arguments

$ARGUMENTS — the scope to simplify. Can be:
- A directory: `/mine-simplify src/services/`
- A file list: `/mine-simplify src/api/routes.py src/api/handlers.py`
- Empty: the skill asks what to target (it does not silently sweep the whole repo)

`mine-simplify` always operates in **codebase mode** — it reads the target files in full and treats pre-existing complexity as in scope. It never diffs against a branch; for simplifying just your branch changes, dispatch `code-judo-reviewer` directly on the diff.

## How to Analyze Code

Subagents read code and reason about it directly using Read, Grep, Glob, and `git`/repo-helper CLIs. Do NOT write or execute analysis scripts — no AST parsers, no custom complexity calculators.

## Phase 1: Determine Scope

Resolve $ARGUMENTS to a file list using **only the path-mode logic** from `${CLAUDE_HOME:-~/.claude}/skills/mine-review/scope-detection.md` (Step 2b: the `find` expansion with its exclusions, language adaptation, and the 200-file count guard). Skip Step 1's diff detection and Step 2a entirely — this skill is always path/codebase mode.

- **$ARGUMENTS resolves to existing paths** → expand per Step 2b and proceed.
- **Some paths missing** → warn about the missing ones, proceed with the rest.
- **$ARGUMENTS empty or all paths missing** → do not default to the whole repo. Ask:

```
AskUserQuestion:
  question: "What code should I look to simplify?"
  header: "Target"
  multiSelect: false
  options:
    - label: "A specific directory"
      description: "I'll name a module or directory to judo"
    - label: "Specific files"
      description: "I'll list the files"
    - label: "The whole repo"
      description: "Sweep everything — slower, and cross-module moves may span batches"
```

Resolve the user's answer (typed via Other) back through Step 2b.

## Phase 2: Determine Batching

Count the resolved files.

- **~8 or fewer files:** a single batch — dispatch one `code-judo-reviewer` over the whole list. A single batch is best: the agent sees every file at once, so cross-file structural moves (collapse two modules, route callers past a layer) are visible.
- **More than ~8 files:** partition into batches. Batching rules:
  - Target ~8 files per batch. Judo agents read every file in full plus sibling/caller context, so keep batches smaller than `mine-clean-code`'s ~10.
  - **Group by directory/module first**, then count-balance within that. Unlike style checks, structural simplification is mostly cross-file *within a module* — keeping a module's files in one batch preserves those moves. Only split a single directory across batches when it alone exceeds ~12 files.
  - Each file appears in exactly one batch; one `code-judo-reviewer` runs per batch. Total dispatch count = number of batches.

**Cross-batch limitation (state it to the user when batching):** a simplification that spans two batches (e.g., a layer in module A made redundant by module B) can be missed. For a thorough pass on a bounded target, prefer a scope small enough to fit one batch.

## Phase 3: Dispatch Parallel Judo Reviewers

Launch one `code-judo-reviewer` agent per batch. For a single batch, one dispatch. For multiple batches reading disjoint directories, **launch all batch agents in a single message** so they run in parallel.

Each agent uses `subagent_type: "code-judo-reviewer"`. Prompt per batch:

```
Run a codebase-mode structural simplification review.

[CODEBASE MODE] Files: <file list for this batch>

These are existing files, NOT a diff. Read every listed file IN FULL. Pre-existing
complexity is in scope — it is exactly what you are hunting. Also read surrounding
context: callers of the functions in these files, sibling modules, and the package
each file lives in, so you can spot moves that delete a layer or collapse two
abstractions across files.

Apply your full posture: assume a dramatically simpler structure exists and find
it. Be ambitious — hunt for moves that delete whole files or layers, not just local
cleanup. Use your standard output format (Strengths, impact table with the mandatory
`→` move format, Assessment). If the code is already lean, say so plainly.
```

After all agents complete, verify each returned a report with an impact table or a clean-exit assessment.

## Phase 4: Consolidate and Present

Merge the per-batch reports into one report.

### Step 1: Merge and dedup

Concatenate every agent's findings, preserving `file:line` references. When two agents flag the same structural move (possible when a module's callers landed in a different batch), merge into one entry and note both locations. Keep distinct moves separate even when they touch the same file.

### Step 2: Validity assessment

Apply the Validity Assessment protocol from `${CLAUDE_HOME:-~/.claude}/skills/mine-challenge/findings-protocol.md`: findings are valid by default; flagging one as likely invalid requires a concrete evidence trail (what the finding claims vs. what the code actually does, with `file:line`). Move likely-invalid findings into a separate `### Likely Invalid` section at the bottom.

### Step 3: Present the consolidated report

Order by impact (HIGH → MEDIUM → LOW), not by batch:

```markdown
## Simplification Review: [target path]

**Scope:** N files across M batches, X total lines

### Summary

| Impact | Count |
|--------|-------|
| HIGH   | N |
| MEDIUM | N |
| LOW    | N |
| **Total** | **N** |

**Likely-invalid:** N

### Strengths

[structural choices already clean — pulled from the agents' Strengths sections, deduped]

### Findings

| # | Impact | Finding | File |
|---|--------|---------|------|
| 1 | HIGH | [what's complex] → [the structural move] | `file:line` |

### Likely Invalid (if any)
```

Every finding keeps the mandatory `→` format — the specific structural move, not just the problem. For likely-invalid findings use the named-field format (`Claimed` / `Actually` / `Why-invalid`).

If every agent returned a clean-exit assessment (no HIGH/MEDIUM), report that the code is already structurally lean and stop — do not offer fixes.

### Step 4: Offer next steps

Otherwise:

```
AskUserQuestion:
  question: "What would you like to do with these simplifications?"
  header: "Next steps"
  multiSelect: false
  options:
    - label: "Apply HIGH moves"
      description: "Implement the HIGH-impact structural moves now; verify against tests after"
    - label: "Pick which to apply"
      description: "I'll choose specific findings to implement"
    - label: "Note and move on"
      description: "Acknowledged — no changes this session"
```

**Applying any move is a refactor.** Before implementing, pin behavior per `refactoring-discipline.md` — confirm the target has test coverage (or write a characterization test first), apply the move, then run the test suite to prove behavior is unchanged. Structural moves that delete layers are high-blast-radius; verify on the real artifact, not "it compiles." After fixes, say: "Simplifications applied — run `/mine-review` before committing."

## What This Skill Does NOT Do

- **Simplify a diff** — dispatch `code-judo-reviewer` directly on the branch diff
- **Correctness or security review** — use `/mine-review`
- **Style/hygiene sweep** — use `/mine-clean-code`
- **Broad health audit (churn, coverage, aging)** — use `/mine-audit`
- **Find files to split** — use `/mine-decompose` (it splits; this collapses)
- **Apply moves without asking** — it proposes, then asks what to implement
