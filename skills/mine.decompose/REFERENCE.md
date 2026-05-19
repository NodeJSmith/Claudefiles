# Decompose — Reference

Extended guidance for the decomposition analysis skill. Referenced by SKILL.md.

---

## Subagent Prompt Templates

### Subagent A: Git Behavioral Analysis

Replace `<scope>` with the target from Phase 1 before dispatching. If `<concern_filter>` is set, append the concern focus line below.

```
Analyze the Git history of the following target for decomposition-relevant signals.

Target: <scope>
Concern filter: <concern_filter or "none — analyze all decomposition signals">

Run these commands and analyze the results:

1. **Churn hotspots** — files ranked by commit frequency:
   git log --since="6 months ago" --format='' --name-only -- <scope> | sort | uniq -c | sort -rn | head -30

2. **Change coupling** — for each of the top 10 hotspot files, which OTHER files change in the same commits:
   git log --since="6 months ago" --format='%H' -- <file> | xargs -I {} git diff-tree --no-commit-id --name-only -r {} | sort | uniq -c | sort -rn | head -10

3. **Function-level churn** (for top 5 hotspot files) — which functions change most often:
   git log --since="6 months ago" --format="%H" -- <file> | head -20
   For each commit, read the diff (`git show <hash> -- <file>`) and identify which function bodies changed by scanning `@@` hunk headers for the nearest enclosing function name. Build a per-function commit-set: `{func_name: [commit1, commit2, ...]}`. Functions sharing many commits are change-coupled; functions with no shared commits are temporally independent (safe extraction candidates).

4. **Developer dispersion** — how many authors touch each hotspot:
   git shortlog HEAD --since="6 months ago" -s -- <file>

For each hotspot file, report:
- Change frequency (commits in last 6 months)
- Top co-changing files with approximate coupling percentage
- Function-level hotspots within the file
- Number of distinct authors

Then identify:
- **Co-change clusters**: groups of functions that always change together (should stay in same unit)
- **Independent functions**: functions that never co-change with the rest of their file (extraction candidates)
- **Cross-file coupling**: files that change together so often they might belong in the same module

**Output format**: Write to `<tmpdir>/git-analysis.md`. Start with a per-file summary table:

| file | commits_6mo | co_changing_files | authors | notes |
|------|-------------|-------------------|---------|-------|

Follow with detailed per-file analysis sections.
```

### Subagent B: Structural & Cohesion Analysis

Replace `<scope>` and `<file list>` with targets from Phase 1 before dispatching. If `<concern_filter>` is set, append the concern focus line below.

```
Analyze the following files for structural decomposition signals. Read the code directly — do not write analysis scripts.

Target: <scope>
Files: <file list or "discover from target">
Concern filter: <concern_filter or "none — analyze all decomposition signals">

For each source file in scope, assess:

1. **Size** — use `wc -l` for file sizes. Read files >200 lines carefully. For large files, inventory all functions/methods with approximate line counts. Flag:
   - Functions >50 lines
   - Nesting >4 levels
   - Parameter count >5

2. **Coupling** — examine imports in both directions:
   - Fan-out: what does this file import?
   - Fan-in: what imports this file? (grep for import statements referencing this module)
   - Circular dependencies (A imports B imports A)

3. **Cohesion** — for files >200 lines or classes with >6 methods:
   - Group functions/methods by shared data access (instance variables, parameters, return types)
   - Identify mixed abstraction levels (orchestration logic mixed with implementation details)
   - Count disconnected responsibility clusters — groups of functions with no shared data
   - A file with N disconnected clusters has LCOM ~N and should likely become N modules

4. **Responsibility mapping** — for each decomposition candidate, produce a cluster map:
   File: <path> (<lines> lines)
   Cluster A (<domain concept>): func1(), func2(), func3() — share <data>, <purpose>
   Cluster B (<domain concept>): func4(), func5() — share <data>, no overlap with A
   Cluster C (<role>): func6() — orchestrates A and B

5. **Coupling-delta pre-check** — for each candidate with multiple clusters, estimate whether splitting along cluster boundaries would increase or decrease cross-module imports. Count: how many imports would the new modules need from each other vs how many external modules currently import specific functions from the original? Include a `coupling-delta` field per candidate: `positive` (split increases coupling — flag as risky), `neutral`, or `negative` (split reduces coupling — good).

6. **Positive exemplar search** — for each decomposition candidate, look for a peer module in the same codebase that has a similar responsibility scope but is already well-decomposed (smaller, cleaner import graph, focused responsibility). Grep for modules in sibling directories or related packages. Record the exemplar path and a one-line note on what makes it a good model. Explicitly record "none found" when no peer exists — do not fabricate examples.

**Output format**: Write to `<tmpdir>/structural-analysis.md`. Start with a per-file summary table:

| file | lines | functions | clusters | fan_in | fan_out | coupling_delta | exemplar | notes |
|------|-------|-----------|----------|--------|---------|----------------|----------|-------|

Follow with detailed per-file analysis sections including cluster maps. Skip files that are large but cohesive (all functions serve one clear purpose).
```

---

## Report Format

The decomposition report (`decomposition-report.md`) uses this structure:

```markdown
# Decomposition Report

**Target:** [scope]
**Date:** [today's date]
**Files analyzed:** N
**Opportunities found:** N (H high, M medium, L low)

---

## Opportunity 1: Split `<file>` (<lines> lines -> ~N modules)

**Priority:** HIGH
**Signals:** [e.g., "47 commits/3mo, 3 disconnected responsibility clusters, 520 lines"]
**Change coupling:** [what changes together vs independently]

**Current structure:**
- Cluster A (<name>): `func1()`, `func2()`, `func3()` — [shared data/purpose]
- Cluster B (<name>): `func4()`, `func5()` — [shared data/purpose]
- Cluster C (<name>): `func6()` — [independent / orchestrator]

**Suggested split:**
- `<new_module_a>.py` — Cluster A ([rationale])
- `<new_module_b>.py` — Cluster B ([rationale])
- `<original>.py` — Cluster C, remains as facade/entry point

**Cohesion improvement:** 3 disconnected clusters -> 1 focused cluster per module
**Coupling impact:** [new dependencies? caller changes needed?]
**Similar example:** [well-decomposed module in same codebase, or "none found"]
**Suggested sequence:** [which piece to extract first and why]

---

## Opportunity 2: Extract methods from `<file>:<function>` (<lines> lines)

**Priority:** MEDIUM
**Signals:** [e.g., "82 lines, nesting depth 6, 8 parameters, cognitive complexity high"]

**Current structure:**
[Brief description of what the function does and where the natural seams are]

**Suggested extractions:**
1. Lines ~N-M -> `<new_function_name>()` — [what it does]
2. Lines ~N-M -> `<new_function_name>()` — [what it does]

**Remaining function:** ~N lines, focused on [core responsibility]

---

## Low Priority (noted, not detailed)

| File | Size | Signal | Note |
|------|------|--------|------|
| `path/to/file.py` | 380 lines | Size only | Cohesive and stable — not urgent |
| `path/to/other.py` | 420 lines | Mild coupling | 2 clusters but rarely changes |
```

---

## Decomposition Signals Reference

### Behavioral Signals (from Git)

| Signal | What it reveals | Decomposition implication |
|--------|----------------|--------------------------|
| Change frequency | How often a file is modified | High churn = high ROI for decomposition |
| Change coupling | Functions/files that change in same commits | Co-changing functions belong together; non-co-changing functions are extraction candidates |
| Developer dispersion | How many authors touch a file | Many authors + complexity = coordination bottleneck |
| Temporal independence | Functions that never co-change | Safe extraction candidates — no hidden coupling |

### Structural Signals (from code)

| Signal | Threshold | Implication |
|--------|-----------|-------------|
| File size | >400 lines | Investigate (not sufficient alone) |
| Function length | >50 lines | Extract method candidate |
| Nesting depth | >4 levels | Mixed abstraction levels |
| Parameter count | >5 params | Combined responsibilities |
| Fan-in | >10 importers | God module — too many responsibilities |
| Fan-out | >10 imports | Too many dependencies |
| Circular deps | Any | Must break the cycle |

### Cohesion Signals (from reading code)

| Signal | What to look for | Implication |
|--------|-----------------|-------------|
| Disconnected clusters | Groups of methods sharing no data | Each cluster -> separate module |
| Mixed abstractions | Orchestration + implementation in same file | Extract the detail level |
| Domain mixing | Unrelated domain concepts in same class | Extract by domain concept |
| Utility accumulation | Generic helpers growing alongside domain logic | Extract to shared module |
