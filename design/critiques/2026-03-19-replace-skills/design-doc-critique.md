# Design Critique: design/specs/005-replace-skills/design.md

**Date**: 2026-03-19
**Target**: `design/specs/005-replace-skills/design.md`
**Critics**: Senior Engineer, Systems Architect, Adversarial Reviewer

## Findings

### 1. mine.mockup's inline direction fallback undermines persistence — CRITICAL

**What's wrong**: When no direction.md exists, mine.mockup offers a "quick inline direction" path that produces session-local, non-persisted decisions. This is exactly the dysfunction the redesign exists to fix. It's the path of least resistance and will be chosen by default.
**Why it matters**: direction.md rarely materializes. The three-skill architecture collapses back to the one-skill reality with ephemeral aesthetic decisions.
**Evidence (code)**:
- `design.md:159-162` — inline path produces "session-local direction, not a persisted file"
- `design.md:9-11` — "each session starts from scratch" identified as the core problem
- `vx.visual-explainer/SKILL.md:35` — "Think (5 seconds, not 5 minutes)" was the existing lightweight path users are trained on
**Raised by**: Senior + Architect + Adversarial
**Better approach**: Make the inline fallback write a lightweight direction.md after the mockup is generated — offer to save. This converts the fast path into a persistence opportunity without blocking flow.
**Design challenge**: What percentage of mockup invocations will have a pre-existing direction.md?

---

### 2. mine.design vs mine.design-direction routing collision — CRITICAL

**What's wrong**: "design this UI" — the exact current trigger for interface-design — is not in either proposed routing table. Users saying "design the dashboard" could hit mine.design (architecture doc) or nothing. Only 2 boundary test cases proposed.
**Why it matters**: The most natural phrase a user would say is orphaned. Persistent misrouting between visual planning and architecture docs.
**Evidence (code)**:
- `capabilities.md:23` — currently routes "design this UI" to mine.interface-design
- `design.md:240-242` — proposed routing does not include "design this UI" in any skill
- `design.md:253-255` — only 2 boundary test cases for a collision-prone boundary
**Raised by**: Senior + Architect + Adversarial
**Better approach**: Add "design this UI", "design this dashboard" to mine.design-direction triggers. Add 5+ boundary test cases. Consider renaming to mine.visual-direction or mine.style-direction.
**Design challenge**: Walk through the routing table for "design this dashboard" post-change.

---

### 3. Closed token layer has no enforcement — HIGH

**What's wrong**: "Every CSS value must reference a token" is a prose instruction with no validation step. No linter, hook, or post-build audit.
**Why it matters**: LLMs will ignore it when context is full. The "primary anti-drift mechanism" is aspirational.
**Evidence (code)**:
- `design.md:147` — closed token layer stated as hard rule
- `design.md:220-225` — mine.build enforcement is a suggestion, not validation
- `design-direction-research.md:281` — research recommends "audit scripts for token compliance"
**Raised by**: Senior + Architect + Adversarial
**Better approach**: Add post-build compliance check: grep for raw hex/px values not matching direction.md tokens. Could live in mine.build's UI path or in code-reviewer agent.
**Design challenge**: If an LLM session ignores the closed-token-layer instruction, how does the user discover the drift?

---

### 4. direction.md location wrong for consumer projects — HIGH

**What's wrong**: `design/` is a Claudefiles convention. Consumer projects won't have this directory. May collide with existing design/ directories.
**Evidence (code)**:
- `CLAUDE.md:33-43` — design/ contains Claudefiles-specific artifacts
- `design-direction-research.md:149,257` — research originally suggested .interface-design/direction.md
**Raised by**: Senior
**Better approach**: Use a dotfile (.design/direction.md), or accept that design/ is a reasonable convention to import into consumer projects.

---

### 5. direction.md singleton — wrong cardinality — HIGH

**What's wrong**: One file per project. Projects with multiple visual contexts (admin, marketing, docs) need scoped directions.
**Raised by**: Senior + Architect + Adversarial
**Better approach**: Support direction-{scope}.md with direction.md as default. When multiple exist, mine.build asks which applies.
**Design challenge**: If the user runs design-direction for admin panel, then marketing site, what happens to the first direction?

---

### 6. Diagram generation drops from routing — MEDIUM

**What's wrong**: Templates survive in mine.mockup but "generate a diagram" routing is removed. Capability exists but unreachable.
**Raised by**: Senior + Architect + Adversarial
**Note**: User explicitly confirmed this is intentional. Should be documented more prominently in Non-Goals.

---

### 7. Empty spec — no acceptance criteria — MEDIUM

**What's wrong**: No testable success criteria exist.
**Raised by**: Adversarial

---

## Appendix: Individual Critic Reports

- Senior Engineer: `/tmp/claude-mine-challenge-xTPpBU/senior.md`
- Systems Architect: `/tmp/claude-mine-challenge-xTPpBU/architect.md`
- Adversarial Reviewer: `/tmp/claude-mine-challenge-xTPpBU/adversarial.md`
