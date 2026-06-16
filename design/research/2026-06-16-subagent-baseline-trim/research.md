# Research: Subagent Baseline-Trim (Lever 4)

**Date:** 2026-06-16
**Status:** scoped, not started
**Spec:** 031-scope-to-avoid-compaction (design.md → Architecture → Lever 4)
**Implementer note:** This stub records the scope of the investigation so it isn't lost between
sessions. Do NOT run the investigation here — it is deferred work. No skill files were modified.

---

## The Problem

Every subagent launched by `mine.orchestrate`, `mine.review`, and `mine.clean-code` starts life
already carrying a ~44k fixed baseline:

- Subagent system prompt
- Tool schemas
- Inherited rules / CLAUDE.md

This baseline is **job-independent** — it is paid by every subagent regardless of what it actually
does. Against the ~167k auto-compaction ceiling (~83% of the ~200k window), that leaves only
**~115k tokens of real working budget** before the harness compacts the subagent and drops file
references, prior decisions, and test output.

The ~44k baseline is the **dominant tax** in the compaction arithmetic. Levers 1–3 of spec 031
cut avoidable *usage* of the working budget (re-deriving diffs, inlining full test output,
full-suite re-runs mid-task). Lever 4 investigates whether the baseline itself can be shrunk.

Note: the ~200k/~167k window parameters are empirically confirmed from 15 `compact_boundary`
events (all firing in a 167k–176k band across four `hassette` worktrees) but are **platform
parameters, not contracts** — they can move. The research must not hardcode them into anything
user-facing.

---

## Prior Art Already in This Repo

Two earlier research docs and one shipped partial fix provide the starting point:

- `design/research/2026-03-16-hot-cold-architecture/research.md` — hot/cold architecture
  investigation (earlier attempt at selective rule loading)
- `design/research/2026-06-08-conditional-rule-loading/research.md` — conditional rule loading
  investigation; the partial fix from this work shipped in PR #366, cutting always-loaded rule
  lines by −46% (2,441 → 1,313 lines; see `CHANGELOG.md`)

Both directories confirmed to exist at the time this stub was written.

---

## Known Blockers (verify status when research runs)

Two platform features would enable deeper per-subagent scoping but were broken at the time of the
June 2026 investigation. **Verify whether these are still blocked before designing any solution:**

| Feature | Issues | Symptom |
|---|---|---|
| `paths:` frontmatter for conditional rule loading | #16299, #16853 | Rule files cannot be scoped to specific path patterns; frontmatter silently ignored |
| PreToolUse `additionalContext` injection | #19432, #55889 | Injection silently drops — context never reaches the subagent |

If either has been fixed since June 2026, that changes the solution space significantly.

---

## Research Sub-Questions (none started)

### Q1 — Prior art: how have others reduced per-subagent baseline context?

**Status:** not started

Run `/mine.prior-art` to survey external approaches to reducing per-subagent baseline context
(system prompt trimming, tool-schema pruning, rule hot-swapping, lazy loading patterns, etc.).

**PREREQUISITE — obtain before running:** The `/mine.prior-art` run **must incorporate the repos
surfaced in the Claude Code digest**. The pointer to that digest (its location and format) has not
been resolved — it is an open question deferred from spec 031. Before running Q1, ask Jessica for
the Claude Code digest repo list / location. Do not invent or guess a path.

Scope the prior-art question to: techniques for reducing the fixed baseline paid by subagents in
Claude Code–style harnesses, including work published or shared since June 2026.

### Q2 — Have the blocking platform bugs moved?

**Status:** not started

Check the current status of:
- #16299 and #16853 (`paths:` frontmatter for conditional rule loading)
- #19432 and #55889 (PreToolUse `additionalContext` injection)

For each: is it fixed, in progress, or still open? If fixed, what version or release shipped the
fix? Does the fix match what was originally needed, or is the behavior subtly different?

### Q3 — What is the actual baseline composition, and is scaffolding-trim actionable today?

**Status:** not started

Measure the ~44k baseline empirically rather than estimating. Source: subagent JSONLs (the same
`compact_boundary` JSONL data that confirmed the 15 compaction events). Split the baseline into:

- System prompt (harness-injected, per-subagent)
- Tool schemas (MCP + built-in tools)
- Inherited rules (always-loaded rule files, post-PR-#366)
- Scaffolding (e.g., `tdd.md`, `implementer-prompt.md`, other inline-included content)

Then evaluate **scaffolding-trim** as the one lever potentially actionable today without platform
fixes: passing `tdd.md` and similar scaffolding files by path reference instead of inlining them
would avoid repeating their content in every subagent's baseline. Estimated recovery: ~3–4k tokens.

Assess: is that recovery worth the complexity? Does it require any platform features that are
currently broken, or is it achievable with current capabilities?

---

## Out of Scope for This Research

- Editing any skill file, rule file, or agent file — Lever 4 is research-only this round.
- Introducing a new hook or runtime enforcement mechanism.
- Resolving the Claude Code digest source pointer — that is the open question that gates Q1.

---

## Deliverable

A follow-up research doc (or an update to this file) recording:

1. Q1 findings from `/mine.prior-art` with digest repos included.
2. Q2 bug-status verdicts for all four issue numbers, with version info if fixed.
3. Q3 empirical baseline breakdown (token counts by component) and a scaffolding-trim
   recommendation (adopt / defer / skip, with rationale).
4. A proposed next step: if blockers are cleared and prior art points to a viable approach,
   draft a follow-on design stub. If blockers remain and scaffolding-trim is the only lever,
   assess whether it warrants its own small implementation task.
