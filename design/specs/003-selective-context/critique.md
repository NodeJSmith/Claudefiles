# Design Critique: Selective Context Loading via SessionStart Hook

**Date**: 2026-03-18
**Target**: `design/specs/003-selective-context/design.md`
**Critics**: Skeptical Senior Engineer, Systems Architect, Adversarial Reviewer

---

## Findings

### 1. Compressed hints are a lossy cache with no sync mechanism — CRITICAL

**What's wrong**: Two representations of every rule — shell script hints + context files — with no mechanism to keep them in sync. When someone edits `context/git.md`, nothing forces an update to the corresponding hint in `session-context.sh`. The design identifies "silent behavioral drift" as Risk #1, then proposes the mechanism most likely to cause it.
**Why it matters**: Claude acts on hint text directly most of the time. If hints drift from source files, Claude follows stale rules on the happy path and correct rules only when it happens to Read the full file.
**Evidence**: `design.md:89-93` (hints are inline shell literals), `design.md:209` (Risk #1 is silent drift)
**Raised by**: Senior + Architect + Adversarial
**Better approach**: Generate hints from context files rather than hand-authoring. Options: (a) YAML `hints:` frontmatter in each `context/*.md` read by the hook at runtime; (b) `*.hint` sidecar files; (c) extract `# HINT:` marked lines from source. Single source of truth.
**Design challenge**: When someone edits `context/git.md` six months from now, what mechanism ensures the hint in `session-context.sh` updates?

---

### 2. Git hint drops mandatory test-before-commit requirement — CRITICAL

**What's wrong**: `git-workflow.md:88-94` requires running tests + linter before committing. The compressed git hint (`design.md:113-117`) omits this requirement entirely. The pre-commit workflow is: code review loop -> integration review -> run tests -> commit. The hint drops step 3.
**Why it matters**: This is the design's own Risk #1 baked into the design itself.
**Evidence**: `rules/common/git-workflow.md:88-94`, `design.md:113-117`
**Raised by**: Senior + Architect
**Better approach**: Every hint block must be diffed against its source to verify no MUST/ALWAYS/NEVER requirements were dropped.
**Design challenge**: Did you diff each compressed hint against its source file to verify no hard requirements were dropped?

---

### 3. Self-invocation problem isn't solved, just renamed — HIGH

**What's wrong**: The design claims "Files Claude must self-invoke: 0" but every hint ends with "Full rules: ~/Claudefiles/context/X.md" — requiring Claude to decide to Read. Same judgment call as self-invoking a skill, different tool. No evidence Read is more reliable than skill invocation.
**Why it matters**: If Option A failed because Claude doesn't reliably self-invoke, the "full details" path has the same failure mode.
**Evidence**: `design.md:5-6` (Option A failure), `design.md:130-148` (Read pointers)
**Raised by**: Adversarial + Senior
**Better approach**: Hints must be *sufficient* for the happy path — all MUST/ALWAYS/NEVER rules inline. The Read pointer is a fallback for rare edge cases, not the primary mechanism.
**Design challenge**: What evidence exists that Claude will Read a context file more reliably than it invokes a `user-invocable: false` skill?

---

### 4. Context-level demotion: hook output vs. system-level rules — HIGH

**What's wrong**: Rules in `rules/` are system-level context. Hook output is conversation context — lower precedence. The design doesn't acknowledge this semantic demotion or measure its impact.
**Why it matters**: Mandatory behaviors may be followed less reliably as conversation context vs. system context.
**Evidence**: Claude Code docs (hook stdout is conversation context), `design.md:209` (attributes drift to compression, not demotion)
**Raised by**: Senior
**Better approach**: Keep the most critical file (`git-workflow.md`) in rules/. Measure adherence before/after.
**Design challenge**: Have you tested whether Claude follows "MUST run code-reviewer before committing" with the same reliability from hook output vs. rules/?

---

### 5. No rollback or measurement plan — HIGH

**What's wrong**: For a change whose #1 risk is "silent behavioral drift," there's no metric, timeline, phased rollout, or rollback procedure.
**Why it matters**: Silent failures go unnoticed until something breaks badly enough to be obvious.
**Evidence**: `design.md:207-217` (5 risks, no mitigation timelines)
**Raised by**: Senior + Adversarial
**Better approach**: Phase rollout (Python first -> measure -> git -> measure). Define success: "Claude still uses ruff/pyright; still discovers test commands from CI; still runs code-reviewer before commit." Tag pre-migration commit for easy revert.
**Design challenge**: What does "success" look like quantitatively?

---

### 6. ROI is 6% for the primary use case — HIGH

**What's wrong**: Git+Python+tmux+worktree sessions (most common) save only 87 lines (6%). The 54% headline only applies to non-development sessions. 1M context windows make 13K tokens (1.35%) a rounding error.
**Why it matters**: Significant complexity for minimal savings where it matters most.
**Evidence**: `research-rules-classification.md:174` ("Git + Python + tmux + worktree: ~87 lines, 6%")
**Raised by**: Adversarial
**Better approach**: Address conversation history and tool output (which dwarf rules tokens), or wait for `paths:` frontmatter fix.
**Design challenge**: For sessions that hit context limits, what's the measurable benefit of ~900 tokens when a single `pytest -v` is 5,000+ tokens?

---

### 7. Broken cross-references after migration — MEDIUM

**What's wrong**: `git-workflow.md:90` references `rules/common/testing.md`. After migration, both files move but internal cross-references aren't updated. No implementation step covers this.
**Raised by**: Architect + Senior
**Better approach**: Build complete cross-reference map before migration. Update every internal reference as an explicit step.

---

### 8. File merging destroys git blame — MEDIUM

**What's wrong**: Merging 5 Python files into one `context/python.md` kills per-file history and makes partial rollback impossible.
**Raised by**: Senior + Architect + Adversarial
**Better approach**: Keep 1:1 file mapping. File count in `context/` doesn't affect performance.

---

### 9. Hook conflates detection and content — MEDIUM

**What's wrong**: One shell script handles both environment detection and hint formatting. Every rules change requires editing shell code.
**Raised by**: Architect
**Better approach**: Each `context/*.md` declares its detection signal in frontmatter. Hook iterates files, runs detection, emits hints. New files added without touching hook script.

---

### 10. `testing.md` demotion ignores coupling analysis — TENSION

**The disagreement**: Architect argues testing.md should be split (TDD core stays hot, discovery moves to context) because it's coupled to the commit workflow. Adversarial argues the whole optimization is marginal. Senior notes the git hint already drops the test requirement, making coupling moot if the hint is fixed.
**Raised by**: Architect + Senior (different angles)

---

## Appendix: Individual Critic Reports

These files contain each critic's unfiltered findings and are available for the duration of this session:

- Senior Engineer: `/tmp/claude-mine-challenge-bXD8xR/senior.md`
- Systems Architect: `/tmp/claude-mine-challenge-bXD8xR/architect.md`
- Adversarial Reviewer: `/tmp/claude-mine-challenge-bXD8xR/adversarial.md`
