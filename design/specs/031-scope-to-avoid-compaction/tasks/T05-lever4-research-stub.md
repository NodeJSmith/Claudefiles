---
task_id: "T05"
title: "Write Lever 4 baseline-trim research stub"
status: "planned"
depends_on: []
implements: ["FR#10", "AC#9"]
---

## Summary
Lever 4 is research-only this round — no skill edits. This task creates a tracked research stub that
records the scope of the ~44k subagent baseline-trim investigation so it isn't lost, including the
deferred `/mine.prior-art` run that must incorporate the Claude Code digest repos. It does NOT
perform the research or edit any skill — it captures the work item with enough detail to pick up
later.

## Prompt
Create a new research stub at `design/research/2026-06-16-subagent-baseline-trim/research.md` (create
the directory). The stub should record, drawing from the design's `## Architecture` (Lever 4) and
`## Dependencies and Assumptions`:

1. **The problem**: every subagent inherits a ~44k fixed baseline (system prompt + tool schemas +
   inherited rules/CLAUDE.md) of its ~167k compaction ceiling — the dominant, job-independent tax.
2. **Prior art already in this repo**: `design/research/2026-03-16-hot-cold-architecture/` and
   `design/research/2026-06-08-conditional-rule-loading/`; partial fix shipped in PR #366
   (−46% always-loaded rule lines).
3. **Known blockers** (verify whether still true when the research runs): `paths:` frontmatter for
   conditional rule loading (issues #16299/#16853) and PreToolUse `additionalContext` injection
   silently dropping (issues #19432/#55889).
4. **Three research sub-questions**, marked as not-yet-done:
   - Run `/mine.prior-art` — **must incorporate the repos from the Claude Code digest** (Jessica's
     explicit requirement; the digest source/location is to be supplied at run time — flag it as a
     prerequisite).
   - Have the blocking platform bugs moved since June 2026?
   - Measure the *actual* baseline composition empirically from subagent JSONLs (split system-prompt
     vs tool schemas vs rules vs scaffolding), and evaluate scaffolding-trim (passing `tdd.md`/other
     scaffolding by path instead of inlining) as the one lever actionable today (~3–4k recovery).

Mark the stub's status clearly as "scoped, not started." Do not edit any skill file. Do not run the
prior-art investigation.

## Focus
- This is a documentation deliverable, not an investigation — keep it to the scope record. The actual
  research is a separate future session.
- The Claude Code digest pointer is deliberately unresolved (deferred per the plan's open-question
  gate); call it out explicitly as a prerequisite so the future run knows to ask for it.
- Place it under `design/research/` (the repo's existing research location, per the prior-art docs
  referenced above), dated `2026-06-16`.

## Verify
- [ ] FR#10: A research stub exists at `design/research/2026-06-16-subagent-baseline-trim/research.md`
      recording the ~44k baseline scope and a no-edit research task; no skill file was modified.
- [ ] AC#9: The stub names the ~44k baseline, both prior research docs, the blocking platform issues
      (#16299/#16853, #19432/#55889), the three sub-questions, and a `/mine.prior-art` run that must
      incorporate the Claude Code digest repos.
