---
name: mine-decompose
description: "Use when the user says: 'decompose this', 'find decomposition opportunities', 'what should I split', 'break this apart', 'this file is too big', 'split opportunities', 'extract candidates', 'find god classes'. Analyzes code for decomposition opportunities — prioritized by Git behavioral signals and structural metrics, with concrete split suggestions."
user-invocable: true
---

# Decompose

Analyzes a codebase (or portion of it) for decomposition opportunities — files that should be split, god classes that need extraction, functions doing too much. Prioritizes by ROI using Git behavioral signals (what changes often) combined with structural metrics (what's complex), then proposes concrete splits with before/after sketches.

## Arguments

$ARGUMENTS — optional target scope. Can be:
- Empty: analyze the entire codebase (default)
- A directory: `/mine-decompose src/services/`
- A file: `/mine-decompose src/services/payment.py`
- A concern: `/mine-decompose "god classes"` or `/mine-decompose "coupling hotspots"`

## How to Analyze Code

**Read the code and reason about it directly.** Subagents use Read, Grep, Glob to examine files. Do NOT write or execute analysis scripts — no AST parsers, no custom complexity calculators.

Allowed commands during analysis:
- `git log` / `git shortlog` / `git diff-tree` / `git show` — churn, change coupling, developer dispersion, per-commit diffs
- `wc -l` — file and function size counts
- `find` / `grep` — file discovery, import/fan-in analysis
- `sort`, `uniq`, `head`, `xargs` — text processing for git output pipelines
- Project linters if available

## Phase 1: Scope

1. If $ARGUMENTS specifies a file or directory, verify it exists. If it's a concern keyword (e.g., "god classes", "coupling hotspots"), set `<concern_filter>` to that keyword — this narrows what subagents look for in Phase 2. If it's a path, set `<concern_filter>` to empty.
2. **Count files first** — run `find <scope> -type f \( -name '*.py' -o -name '*.ts' -o -name '*.js' -o -name '*.go' -o -name '*.rs' -o -name '*.java' \) | wc -l` (adapt extensions to project language). If >200: **stop here**, ask the user to narrow scope, and restart Phase 1 with the new scope.
3. Map the file tree (depth 2-3), identify source files, skip vendored/generated/build directories.

## Phase 2: Analysis

Run `get-skill-tmpdir mine-decompose` to create a temp directory.

**Squash-merge caveat**: If `git log --oneline | head -50` shows mostly single-commit merges (squash-merge workflow), note this in the report. Change coupling data is diluted — functions bundled in the same PR appear coupled even when they aren't. The behavioral signals are still directionally useful if PRs are reasonably focused, but lean harder on structural signals for ranking when the history is squash-heavy.

Launch **two subagents in parallel** (both `subagent_type: general-purpose`, `model: haiku`). See REFERENCE.md for full prompt templates — substitute the actual `<tmpdir>` path, `<scope>`, and `<concern_filter>` into each template before dispatching.

Each subagent writes structured output to the tmpdir — the orchestrator reads both files in Phase 3 and joins on file path.

### Subagent A: Git Behavioral Analysis

Writes to `<tmpdir>/git-analysis.md`. Examines Git history for decomposition signals:
- **Churn hotspots**: files ranked by commit frequency in the last 6 months
- **Change coupling**: for each hotspot, which other files/functions change in the same commits
- **Developer dispersion**: how many authors touch each hotspot
- **Temporal independence**: functions within a file that never co-change (safe extraction candidates)

Output must start with a per-file summary table: `| file | commits_6mo | co_changing_files | authors | notes |`

### Subagent B: Structural & Cohesion Analysis

Writes to `<tmpdir>/structural-analysis.md`. Reads the code to assess structural signals:
- **Size**: files >400 lines, functions >50 lines, nesting >4 levels
- **Coupling**: fan-in/fan-out per file (import analysis), circular dependencies
- **Cohesion**: disconnected responsibility clusters within files/classes (groups of methods sharing no data)
- **Mixed abstractions**: high-level orchestration mixed with low-level details
- **Responsibility mapping**: for each large file/class, which methods cluster by shared data/purpose

Output must start with a per-file summary table: `| file | lines | functions | clusters | fan_in | fan_out | notes |`

## Phase 3: Synthesize & Suggest

Read `<tmpdir>/git-analysis.md` and `<tmpdir>/structural-analysis.md`. Join on file path — for each file, merge behavioral signals (churn, coupling, dispersion) with structural signals (size, clusters, fan-in/fan-out). Files appearing in only one report get partial data; note the gap.

### Prioritization

Two-stage ranking: **qualify** (does this file clear any decomposition bar?), then **rank** (given qualifying signals, what priority?). Behavioral signals dominate structural when they conflict.

**Qualification** — a file is a decomposition candidate if ANY of these hold:
- Multiple disconnected responsibility clusters (structural signal)
- High churn with low cohesion (behavioral + structural)
- Change coupling violations — non-co-changing functions forced into same file (behavioral)
- High fan-in (>10 importers) suggesting too many responsibilities (structural)

Do NOT qualify files that are cohesive, well-tested, and stable — size alone is not a decomposition signal.

**Ranking** — given qualified candidates, assign priority:

| Priority | Determining signal |
|----------|--------------------|
| HIGH | Behavioral signal present (high churn, change coupling violations, high developer dispersion) |
| MEDIUM | Structural signals only (multiple clusters, high fan-in, large size) with low or no churn |
| LOW | Single marginal signal (e.g., size threshold crossed but cohesive) |

### Suggestion Generation

For each HIGH and MEDIUM opportunity, propose a concrete split. See REFERENCE.md for the full output format. Each suggestion includes:

1. **What moves where** — specific functions/classes, proposed new module names
2. **Why these group together** — change coupling, shared data access, or domain concept
3. **Cohesion improvement** — how the split reduces disconnected responsibility clusters
4. **Coupling impact** — new cross-module dependencies? Existing callers affected?
5. **Good example** — if the codebase has a well-decomposed module with a similar pattern, reference it
6. **Suggested order** — dependency-aware sequence for implementing the splits

### Anti-Pattern Guard

Before finalizing any suggestion, check for two failure modes:

1. **Coupling increase** — check Subagent B's `coupling-delta` field. If `positive`, drop the suggestion — splitting creates modules that must always change together, which is worse than the status quo.
2. **Over-decomposition** — if a proposed split would produce modules under ~50 lines that are really just private functions, drop the suggestion. Extracting tiny modules that all get imported by the same callers adds indirection without reducing coordination cost.

## Phase 4: Present

### Step 1: Write the report

Write `<tmpdir>/decomposition-report.md` (same tmpdir from Phase 2). See REFERENCE.md for the full format template.

### Step 2: Narrative summary

Present the top findings inline — lead with HIGH priority, include the key signal that flagged each, and show the proposed split in brief. End with: `Full report at <tmpdir>/decomposition-report.md`

### Step 3: Offer next steps

```
AskUserQuestion:
  question: "What would you like to do with these findings?"
  header: "Next steps"
  multiSelect: false
  options:
    - label: "Build top opportunity"
      description: "Implement the highest-priority decomposition via /mine-build"
    - label: "File as issues"
      description: "Create GitHub issues for the decomposition opportunities"
    - label: "Save report"
      description: "Save to design/audits/ for future reference"
    - label: "Done"
      description: "Acknowledged — no action this session"
```

If the user chooses "Build top opportunity", invoke `/mine-build` with a description of the decomposition. If "File as issues", create one issue per HIGH/MEDIUM opportunity via `gh-issue create`. If "Save report", copy to `design/audits/YYYY-MM-DD-decomposition/decomposition.md`.

## What This Skill Does NOT Do

- **Implement splits** — diagnosis only. Fixes flow through `/mine-build`
- **Replace `/mine-audit`** — audit covers broad codebase health. This focuses specifically on decomposition
- **Suggest micro-extractions** — a clear, cohesive 30-line function stays as-is even if 3 lines could be extracted
- **Profile runtime performance** — complexity here is structural, not runtime

## Principles

1. **Show, don't tell** — concrete "move X to Y" suggestions, not "consider improving cohesion"
2. **Behavioral signals first** — Git history reveals what actually changes together; static metrics are secondary
