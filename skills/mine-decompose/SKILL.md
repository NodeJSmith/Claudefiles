---
name: mine-decompose
description: "Use when the user says: 'decompose this', 'find decomposition opportunities', 'what should I split', 'break this apart', 'this file is too big', 'split opportunities', 'extract candidates', 'find god classes'. Analyzes code for decomposition opportunities — prioritized by Git behavioral signals and structural metrics, with concrete split suggestions."
user-invocable: true
---

# Decompose

Find the files, classes, and functions worth splitting, and propose concrete splits. A big file isn't a finding: a cohesive, stable, well-tested one should stay as it is. The cases that pay off are code that changes often and mixes unrelated responsibilities, so Git behavior (what changes together, what changes often) outranks static metrics. Done is a ranked set of splits, each saying what moves where and why those pieces belong together, or an honest "this is already well decomposed."

## Arguments

$ARGUMENTS: optional target scope.
- Empty: the whole codebase
- A directory or file: `/mine-decompose src/services/`
- A concern: `/mine-decompose "god classes"` or `"coupling hotspots"`. Treat it as `<concern_filter>`, which narrows what the subagents look for; for a path, the filter is empty.

If the scope holds more than about 200 source files, ask the user to narrow it before analyzing. Skip vendored, generated, and build directories.

## How to analyze

Subagents read code with Read, Grep, Glob and use `git log`/`shortlog`/`diff-tree`/`show`, `wc -l`, `find`/`grep`, text-processing pipes, and the project's linters. They don't write or run analysis scripts (no AST parsers or custom complexity calculators); the reading is the analysis.

Create a working directory with `mktemp -d <scratchpad>/mine-decompose-XXXXXX`, then dispatch two `light-worker` subagents in parallel using the prompt templates in `REFERENCE.md`, substituting `<tmpdir>`, `<scope>`, and `<concern_filter>`:

- **Git behavioral analysis** writes `<tmpdir>/git-analysis.md`: churn hotspots, change coupling, developer dispersion, and functions that never co-change with the rest of their file.
- **Structural and cohesion analysis** writes `<tmpdir>/structural-analysis.md`: size, coupling, disconnected responsibility clusters, mixed abstraction levels, and the coupling effect of a split.

Both files start with the per-file summary tables given in the templates; join them on file path, noting the gap when a file appears in only one.

**Squash-merge trap.** If recent history is mostly single-commit squash merges, functions bundled in one PR look coupled when they aren't, so change-coupling data is diluted. Say so in the report and lean on structural signals for ranking.

## Judging

A file, class, or function qualifies when splitting it would make the code easier to change, and you can name the evidence. Examples: disconnected responsibility clusters, high churn with low cohesion, non-co-changing functions forced into one file, or fan-in high enough to suggest too many responsibilities, or a function too long, deep, or wide to follow. Behavioral evidence ranks higher than structural: HIGH when behavioral signals are present, MEDIUM for structural signals with little churn, LOW for a single marginal signal.

Drop a suggestion when the split would make things worse:
- **Coupling increase.** If the structural analysis marks `coupling-delta` positive, the new modules must always change together, which is worse than the status quo.
- **Over-decomposition.** Modules under ~50 lines that are really private functions, all imported by the same callers, add indirection without reducing coordination cost.

For each HIGH and MEDIUM opportunity, make the proposal concrete (see the report format in `REFERENCE.md`): specific functions and classes and the new module names, why they group together, how cohesion and coupling change and which callers are affected, a well-decomposed peer in the codebase if one exists, and a dependency-aware order for the splits.

## Presenting

Write `<tmpdir>/decomposition-report.md` in the format from `REFERENCE.md`. Present the top findings inline, HIGH first, each with the signal that flagged it and the proposed split in brief, ending with `Full report at <tmpdir>/decomposition-report.md`.

If nothing survived the checks above, say the code is already well decomposed and stop. Otherwise ask what to do next, building the options from the findings (naming the top opportunity and the count). The outcomes are: build the top opportunity (recommend when it is HIGH and self-contained), file one issue per HIGH/MEDIUM opportunity in the project's tracker (recommend when they are many, MEDIUM, or need several PRs), save the report by copying it to `design/audits/YYYY-MM-DD-decomposition/decomposition.md`, or done. Diagnosis only until the user picks a build.

## Not this skill

Broad codebase health is `/mine-audit`. Micro-extractions (a clear, cohesive 30-line function stays as-is) and runtime performance are out of scope; complexity here is structural.
