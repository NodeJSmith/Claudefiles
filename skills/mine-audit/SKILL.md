---
name: mine-audit
description: "Use when the user says: \"audit the codebase\", \"find tech debt\", or \"health check\". Systematic codebase health audit — surfaces aging code, brittle designs, missing tests, and accumulated debt, ranked by impact."
user-invocable: true
---

# Codebase Audit

Find the problems in a codebase that are actively hurting: code that has aged poorly, designs that have become brittle, abstractions that leak, areas with no test safety net. Not everything imperfect, only what is likely to cause bugs, slow development, or resist change, ranked so the next production incident is at the top. Done is a findings file the user has walked through, with each finding fixed, filed, or knowingly skipped, and a saved report.

## Arguments

$ARGUMENTS: optional scope narrowing.
- Empty: the whole codebase
- A directory: `/mine-audit src/services/`
- A concern: `/mine-audit "test coverage"` or `"error handling"`
- A question: `/mine-audit "what's the riskiest part of this codebase?"`

## How to analyze

Read the code and reason about it directly with Read, Grep, and Glob. Don't write or run analysis scripts (no AST parsers, complexity calculators, or throwaway import counters); identifying smells, mapping dependencies, and judging coupling and duplication come from reading. The commands worth running are `git log`/`diff`/`shortlog` for churn, age, and history, `pytest --cov` or the equivalent for real coverage numbers, the project's linters for existing output, `wc -l` for sizes, and `lint-agent-files .` in a Claudefiles-style repo.

Map the directory tree (skipping vendored, generated, and build output), group it into review units (top-level modules, with small related directories combined), and dispatch one `standard-worker` per unit in parallel. Slicing by directory rather than by concern lets each subagent see the full context of its area. Each assesses structure and size, churn and age, dependencies (fan-in, fan-out, cycles), tests (coverage, staleness, untested high-churn code), and quality signals, and returns a structured summary.

Then dispatch one `standard-worker` over all the per-directory summaries plus the full file manifest, to find what only shows at the boundaries: duplicated logic across modules, the same concept under different names, circular dependencies between top-level modules, inconsistent patterns (error handling, logging, config access), and god modules everything imports from.

## Judging what matters

Synthesize; don't dump raw data. Rank by impact. The most dangerous findings typically are code that changes often and is hard to change safely (high churn plus high complexity), things many others depend on with no tests, large old code still on the critical path, inconsistent patterns that stop developers building intuition, missing error handling at boundaries, and tight coupling clusters.

Leave out what a formatter fixes, slightly long one-off functions, code that works and isn't changing, and young TODOs. Manufacturing problems for working code wastes the user's time.

Severity: **CRITICAL** is high churn with low coverage on the critical path, or cycles blocking all development; **HIGH** is significant structural problems, test gaps on high-value code, or active architectural debt; **MEDIUM** is accumulating risk that isn't urgent; **TENSION** is worth noting, low urgency.

Apply the Validity Assessment protocol from `${CLAUDE_CONFIG_DIR:-~/.claude}/skills/mine-challenge/findings-protocol.md`: findings are valid by default, and calling one likely invalid needs a concrete evidence trail (the claim versus what the code actually does). Verify by reading the source, not just the summaries. Likely-invalid findings stay out of the narrative and go in the file's `## Likely Invalid` section per the protocol, with the count in both the file header and the narrative.

## Presenting

First send the findings with `SendUserMessage` as a narrative by severity (critical, concerning, worth noting) so the user can orient. Every finding cites evidence: file names, line counts, churn data, dependency chains. Include the `**Likely-invalid:** N` count.

Then run `mktemp -d <scratchpad>/mine-audit-XXXXXX` and write `<tmpdir>/audit-results.md` in the findings format below, following `findings-protocol.md` for field definitions. Finding types: `Test Gap` | `Structural` | `Coupling` | `Tech Debt` | `Pattern Drift`. `Raised-by` is `Audit Analysis (1/1)`, the single-source convention for non-critic-panel callers.

```markdown
# Audit Findings
**Target:** [project name or scope]
**Date:** [today's date]
**Format-version:** 4
**Likely-invalid:** <count>

## Finding 1: [concise title]
**Severity:** CRITICAL | **Type:** Test Gap | **Raised-by:** Audit Analysis (1/1)
**Classification:** User-directed
**visibility:** presented
**disposition:** pending

**Problem:** [specific description with evidence]

**Why-it-matters:** [concrete consequence: what breaks, what slows down]

**Recommendation:** Option A

**Options:**
- **A** *(recommended)*: Fix it now
- **B**: File as issue: track for future work
- **C**: Skip: noted, no action this session

**Why A:** [one-sentence rationale specific to this finding]

## Likely Invalid

<!-- See findings-protocol.md's ### LI-N format. Omit this section entirely when Likely-invalid is 0. -->
```

Walk the user through them. Audit findings are User-directed with option letters: **A** (or `fix`) implements the fix now, **B** files an issue in the project's tracker, **C** (or `skip`) is noted in the session summary only. Present CRITICAL and HIGH findings one at a time via AskUserQuestion. MEDIUM and lower go in a single numbered list sent with `SendUserMessage`, then one question asking which to file (taking the numbers as free text; unselected ones are noted in the summary only), since they are rarely worth a stop each and a multiSelect holds at most four. When several findings are going to be fixed, suggest an order of attack: highest impact first and dependency-aware (break the cycle before refactoring the modules caught in it).

## Saving the report

After the walkthrough, save the audit and tell the user the path. Audits are backward-looking snapshots that feed future design docs and refactors. Default to `design/audits/YYYY-MM-DD-topic-name/audit.md` (narrative summary plus findings list), creating `design/audits/` if needed; if the project already saves audits elsewhere, follow that.

## Not this skill

Fixing happens after the walkthrough, not during diagnosis. No letter grades or scores (they're false precision; specific problems ranked by impact instead). Runtime performance needs profiling, not static analysis.
