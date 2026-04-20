---
name: mine.audit
description: "Use when the user says: \"audit the codebase\", \"find tech debt\", or \"health check\". Systematic codebase health audit — surfaces aging code, brittle designs, missing tests, and accumulated debt, ranked by impact."
user-invocable: true
---

# Codebase Audit

Systematic assessment of a codebase's health. Finds the problems worth fixing — not everything that's imperfect, but the things that are actively hurting: code that's aged poorly, designs that have become brittle, abstractions that leak, areas with no test safety net.

## Arguments

$ARGUMENTS — optional scope narrowing. Can be:
- Empty: audit the entire codebase (default)
- A directory: `/mine.audit src/services/`
- A concern: `/mine.audit "test coverage"` or `/mine.audit "error handling"`
- A question: `/mine.audit "what's the riskiest part of this codebase?"`

## How to Analyze Code

**Read the code and reason about it directly.** Subagents should use Read, Grep, and Glob to examine files. Do NOT write or execute Python/shell scripts to perform analysis — no AST parsers, no custom complexity calculators, no throwaway scripts to count imports or measure coupling. You can read code and identify these patterns yourself.

The only commands to execute during analysis are:
- `git log` / `git diff` / `git shortlog` — for churn, age, and history data
- `pytest --cov` or equivalent — for actual test coverage numbers
- Project linters (`ruff`, `eslint`) — for existing lint output
- `wc -l` or similar — for quick file size counts when scanning many files
- `agnix .` — if auditing a Claudefiles-style repo (agents/, skills/, commands/)

Everything else — identifying smells, mapping dependencies, assessing coupling, spotting duplication — comes from reading the files.

## Phase 1: Directory Discovery

Identify the top-level modules and determine review units.

1. Map the directory tree (depth 2-3) using Glob
2. Identify top-level modules (e.g., `src/api/`, `src/services/`, `src/models/`)
3. Group small related directories into single review units if needed
4. Skip vendored, generated, and build output directories

## Phase 1.5: Per-Directory Reconnaissance

Launch parallel `Explore` subagents — one per review unit identified in Phase 1. Each subagent assesses ALL concerns for its directory:

- **Structure & Size** — largest files, largest functions, disproportionate growth
- **Churn & Age** — hot spots, cold spots, churn + complexity
- **Dependencies** — imports in/out, fan-in, fan-out, circular refs
- **Tests** — coverage, stale tests, untested high-churn code
- **Quality signals** — nesting, params, duplication, broad catches, hardcoded values

Each subagent returns a structured summary for its directory. This is faster and produces better results than concern-based slicing because each subagent sees the full context of its directory.

## Phase 1.6: Cross-Scope Synthesis

Launch a single `Explore` subagent that reads ALL per-directory findings plus the full file manifest. This subagent looks for problems that only emerge at the boundary between directories:

- Cross-directory DRY violations (same logic duplicated in multiple modules)
- Naming drift (same concept called different things in different directories)
- Circular dependencies between top-level modules
- Inconsistent patterns (error handling, logging, config access)
- God modules that everything imports from

## Phase 2: Synthesize Findings

Don't just dump raw data. Synthesize the per-directory and cross-scope results into a prioritized assessment.

### Prioritization criteria

Rank findings by **impact** — how much this problem is likely to cause bugs, slow down development, or resist change:

| Signal | Why it matters |
|--------|---------------|
| High churn + high complexity | Changed often but hard to change safely — the most dangerous combination |
| High fan-in + no tests | Many things depend on it but there's no safety net |
| Large + old + still active | Written long ago, never cleaned up, still critical path |
| Inconsistent patterns | Developers can't build intuition — each area works differently |
| Missing error handling on boundaries | Silent failures, data corruption, hard-to-debug production issues |
| Tight coupling clusters | Can't change A without breaking B, C, and D |

### What to ignore

- Style nits that a formatter can fix (leave that to ruff/eslint)
- One-off small functions that are slightly long
- Code that works fine and isn't changing (don't manufacture problems)
- TODO comments less than a month old (they're probably in progress)

### Severity mapping

- **CRITICAL** — high churn + low coverage on the critical path, or circular dependencies blocking all development
- **HIGH** — significant structural problems, test gaps on high-value code, active architectural debt
- **MEDIUM** — accumulating risk that isn't urgent but will compound
- **TENSION** — worth noting; low urgency

## Phase 3: Present the Report

### Step 1: Narrative summary

Before entering the findings flow, present the findings as a narrative organized by severity so the user can orient:

```
## Codebase Audit: [project name]

### Critical (high impact, fix soon)
1. **src/services/payment.py** (520 lines, 47 changes in 3 months, 12% test coverage)
   The most frequently changed file in the codebase has almost no test coverage. It handles payment processing and has 3 broad `except Exception` blocks that silently swallow errors.

2. **Circular dependency: models ↔ services ↔ utils**
   These three directories have 14 circular import paths. Adding anything to models/ requires understanding how services/ and utils/ will react. This is the main reason features take longer than expected.

### Concerning (accumulating risk)
3. **src/api/routes.py** (680 lines, mixes routing + business logic + validation)
   God file that 23 other modules import from. Every API change requires modifying this single file. Should be split by domain.

4. **No tests for src/integrations/** (4 files, 1,200 lines)
   External API integrations with zero test coverage. These modules do have error handling but it's untested — if an API changes behavior, you'll find out in production.

### Worth noting (low urgency)
5. **Inconsistent error handling** — src/api/ uses custom exceptions, src/services/ returns error tuples, src/utils/ raises ValueError for everything
6. **8 TODO/FIXME comments older than 6 months** — may be stale or forgotten
```

### Step 2: Write findings file

Run `get-skill-tmpdir mine-audit` and write `<tmpdir>/findings.md` using the findings file format:

```markdown
# Audit Findings
**Target:** [project name or scope]
**Date:** [today's date]
**Format-version:** 2

## Finding 1: [concise title]
**Severity:** CRITICAL | **Type:** Test Gap | **Raised by:** Audit Analysis (1/1)
**Resolution:** User-directed

**Problem:** [specific description with evidence — file names, line counts, churn data]

**Why it matters:** [concrete consequence — what breaks, what slows down]

**Recommendation:** Option A

**Options:**
- **A** *(recommended)*: Build the fix via `/mine.build`
- **B**: File as issue — track in GitHub for future work
- **C**: Skip — noted, no action this session

**Why A:** [one-sentence rationale specific to this finding]
```

Use finding types from this vocabulary: `Test Gap` | `Structural` | `Coupling` | `Tech Debt` | `Pattern Drift`

The `(1/1)` in `Raised by` is the single-source convention for non-critic-panel callers — audit has one analyst, not a critic panel.

### Step 3: Follow findings protocol

Follow `${CLAUDE_HOME:-~/.claude}/skills/mine.challenge/findings-protocol.md` for the Consent Gate, manifest editor, and execution.

Audit findings use the User-directed model with explicit option letters (A/B/C). During manifest execution, option verbs execute as follows:
- **`A`** (or `fix`) — invoke `/mine.build` with the finding's description as the argument. For structural/architectural problems, `/mine.build` will assess complexity and route to direct implementation or the full caliper workflow.
- **`B`** — create a GitHub issue via `gh-issue create` for this finding
- **`C`** (or `skip`) — noted in session summary, no action

Since the resolution model is User-directed with option letters, "File as issue" and "Skip" are explicit options in the findings template — the findings protocol does not append them again during `ask` execution (the `ask` verb is not used for these findings).

**Multiple findings selected for build**: if several findings are being addressed via `/mine.build`, suggest an order of attack — highest impact first, dependency-aware (e.g., fix the circular dependency before refactoring the modules caught in the cycle).

## Phase 4: Save Report (optional)

After findings are resolved, offer to save the audit to the repo. Audits are backward-looking snapshots that feed into future design docs and refactors.

Recommended convention — date-stamped directory under `design/audits/`:

```
design/audits/
└── YYYY-MM-DD-topic-name/
    ├── audit.md              Narrative summary + findings list
    └── ...
```

Create `design/audits/` if it doesn't exist. If the project already saves audits elsewhere, follow the existing convention.

## What This Skill Does NOT Do

- **Fix anything** — this is diagnosis, not treatment. Fixes flow through `/mine.build`
- **Rewrite scores or letter grades** — subjective ratings create false precision. Instead: specific problems ranked by impact
- **Profile performance** — runtime performance requires execution and profiling tools, not static analysis

## Principles

1. **Problems, not nitpicks** — surface things that actually hurt. A 60-line function that's clear and well-tested is not a finding.
2. **Evidence over opinion** — every finding should cite specific files, line counts, churn data, or dependency chains. No vague "this could be better."
3. **Rank by impact** — the user's time is limited. Put the thing that will cause the next production incident at the top.
4. **Respect working code** — code that works, has tests, and isn't changing doesn't need attention just because it's old or imperfect.
5. **Actionable handoff** — every finding should connect to a concrete next step, even if the user decides not to take it right now.
