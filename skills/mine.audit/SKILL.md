---
name: mine.audit
description: Systematic codebase health audit. Surfaces the biggest problems — aging code, brittle designs, over-exposed internals, missing tests, and accumulated debt — ranked by impact. Feeds into /mine.refactor and /mine.adrs.
user-invokable: true
---

# Codebase Audit

Systematic assessment of a codebase's health. Finds the problems worth fixing — not everything that's imperfect, but the things that are actively hurting: code that's aged poorly, designs that have become brittle, abstractions that leak, areas with no test safety net.

## Arguments

$ARGUMENTS — optional scope narrowing. Can be:
- Empty: audit the entire codebase (default)
- A directory: `/audit src/services/`
- A concern: `/audit "test coverage"` or `/audit "error handling"`
- A question: `/audit "what's the riskiest part of this codebase?"`

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

## Phase 3: Present the Report

Use AskUserQuestion to present findings and determine next steps.

### Format the report as context, then ask

Present the findings organized by severity, then ask what to focus on:

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

### Save the backlog first

If there are 3 or more actionable findings, invoke the backlog save flow from `rules/common/backlog.md` before asking what to focus on. Confirm what was saved, then proceed. If fewer than 3 findings, skip this step.

### Ask what to focus on

```
AskUserQuestion:
  question: "These are the biggest issues I found. What would you like to focus on?"
  header: "Focus area"
  multiSelect: true
  options:
    - label: "Payment module (Recommended)"
      description: "High churn, low coverage, silent error swallowing — highest risk item"
    - label: "Circular dependencies"
      description: "Structural issue slowing down all development"
    - label: "Split routes.py"
      description: "God file affecting every API change"
    - label: "Integration tests"
      description: "External API calls with zero test safety net"
```

### Per-finding action

For each selected finding, ask what to do with it. Not everything needs to be fixed right now — sometimes the right move is to record the problem and move on.

```
AskUserQuestion:
  question: "For the payment module: this is both a structural problem (too large, mixed concerns) and a safety problem (low test coverage). What's the priority?"
  header: "Approach"
  multiSelect: false
  options:
    - label: "Tests first (Recommended)"
      description: "Add test coverage before refactoring — build the safety net, then restructure"
    - label: "Refactor first"
      description: "Clean up the structure now, write tests against the new shape"
    - label: "Create an issue"
      description: "File a GitHub issue capturing this finding — deal with it later"
    - label: "Skip"
      description: "Noted, but no action needed right now"
```

### Hand off to the right tool

Based on the user's choice per finding:

- **Structural problems** (long files, god classes, tangled modules) → run `/mine.refactor`
- **Architectural problems** (wrong abstractions, missing layers, circular dependencies) → create an ADR with `/mine.adrs`, then plan the rearchitecture
- **Test coverage gaps** → write tests using the mine.python-testing skill
- **Security concerns** → hand off to the mine.security-review skill
- **Create an issue** → file a GitHub issue (see below)
- **Multiple findings selected** → ask per finding, then suggest an order of attack for the ones being addressed now (highest impact first, dependency-aware — e.g., fix the circular deps before trying to refactor the modules caught in the cycle)

### Filing issues

When the user chooses "Create an issue" for a finding, create it immediately:

1. Use the Write tool to write the issue body to a temp file (e.g., `${CLAUDE_CODE_TMPDIR:-/tmp}/issue-body.md`):
   ```markdown
   ## Problem

   <2-3 sentence description of the finding from the audit>

   ## Evidence

   - <specific files, line counts, churn data, coverage numbers>
   - <dependency information if relevant>

   ## Suggested approach

   <brief recommendation — e.g., "Add test coverage first, then refactor" or "Needs architectural decision — consider an ADR">

   ## Source

   Identified during codebase audit on <date>.
   ```
2. Create the issue:
   ```bash
   gh-issue create --title "<concise problem statement>" --body-file "${CLAUDE_CODE_TMPDIR:-/tmp}/issue-body.md"
   ```

After creating the issue, confirm the URL and move on to the next finding. The user can batch multiple findings as issues — ask once per finding, don't force them to address everything in this session.

If the user picks "Skip" for all findings, that's fine — the conversation itself has value. Offer to save the report (Phase 4).

## Phase 4: Save Report (optional)

If the user wants to keep the audit results:

Audits are backward-looking — they assess the current state of the codebase and produce prioritized work items. They feed into multiple future efforts (refactors, test coverage, ADRs) rather than a single decision.

The recommended convention is a date-stamped topic directory under `design/audits/`:

```
design/audits/
└── YYYY-MM-DD-topic-name/
    ├── audit.md              Main audit brief
    └── ...                   Additional artifacts (data, follow-up analysis)
```

```
AskUserQuestion:
  question: "Want me to save this audit report?"
  header: "Save"
  multiSelect: false
  options:
    - label: "Save to design/audits/ (Recommended)"
      description: "Save as design/audits/YYYY-MM-DD-<topic>/audit.md"
    - label: "Save to docs/"
      description: "Save as docs/audit-YYYY-MM-DD.md"
    - label: "No, just the conversation"
      description: "I have what I need from the discussion"
```

Create the `design/audits/` directory if it doesn't exist. If the project already has audits elsewhere, follow the existing convention.

## What This Skill Does NOT Do

- **Fix anything** — this is diagnosis, not treatment. It feeds into `/mine.refactor` and `/mine.adrs`
- **Rewrite scores or letter grades** — subjective ratings create false precision. Instead: specific problems ranked by impact
- **Audit security** — use the mine.security-review skill for that. This skill may flag obvious security smells (broad catches, no input validation) but won't do a thorough security review
- **Profile performance** — runtime performance requires execution and profiling tools, not static analysis

## Principles

1. **Problems, not nitpicks** — surface things that actually hurt. A 60-line function that's clear and well-tested is not a finding.
2. **Evidence over opinion** — every finding should cite specific files, line counts, churn data, or dependency chains. No vague "this could be better."
3. **Rank by impact** — the user's time is limited. Put the thing that will cause the next production incident at the top.
4. **Respect working code** — code that works, has tests, and isn't changing doesn't need attention just because it's old or imperfect.
5. **Actionable handoff** — every finding should connect to a concrete next step, even if the user decides not to take it right now.
