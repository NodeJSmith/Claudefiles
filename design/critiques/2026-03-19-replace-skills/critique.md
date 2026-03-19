# Design Critique: Replace interface-design + visual-explainer with mine.mockup

**Date**: 2026-03-19
**Target**: `design/research/2026-03-19-replace-skills/research.md`
**Critics**: Senior Engineer, Systems Architect, Adversarial Reviewer

## Findings

### 1. Mandatory design-direction gate on non-UI content — CRITICAL

**What's wrong**: The proposal mandates design-direction questions ("Who is this human?", domain exploration, signature element) before *any* HTML generation. This is essential for UI mockups but adversarial for architecture diagrams, data tables, and technical visualizations — which are the majority of current vx use cases.
**Why it matters**: vx's "Think (5 seconds, not 5 minutes)" phase was intentionally lightweight. Replacing it with interface-design's heavy Intent First + Domain Exploration for every request means diagram users either rush through irrelevant questions or abandon the skill.
**Evidence (code)**:
- `research.md:148` — "mandatory gate... you cannot skip"
- `skills/vx.visual-explainer/SKILL.md:35` — "Think (5 seconds, not 5 minutes)"
- `skills/mine.interface-design/SKILL.md:26-36` — intent questions are UI-specific
**Raised by**: Senior + Architect + Adversarial
**Better approach**: Make Phase 1 conditional. UI mockup requests get the full design-direction phase. Diagram/table/visualization requests get a lightweight Think phase (audience, content type, aesthetic).
**Design challenge**: How long does the design-direction phase take for "generate a Mermaid diagram of our database schema"? Is that time well spent?

---

### 2. 8 subcommands deleted without triage — CRITICAL

**What's wrong**: All 8 vx subcommands are marked "user wants these tossed" without distinguishing bloat from valuable capabilities. `diff-review`, `fact-check`, `plan-review`, and `project-recap` are distinct analytical workflows with their own data-gathering logic — not "thin wrappers."
**Why it matters**: After deletion, "fact check this doc" and "visual diff review" have no handler. The research conflates "user is frustrated with the implementation" with "these capabilities have no value."
**Evidence (code)**:
- `research.md:131` — all 8 listed as "NOT worth keeping"
- `rules/common/capabilities.md:28` — routes "diff review", "fact check a doc" as distinct intents
- `skills/vx.visual-explainer/commands/diff-review.md`, `plan-review.md`, `project-recap.md` — each has unique data-gathering workflows
**Raised by**: Senior + Architect + Adversarial
**Better approach**: Categorize into three buckets: (1) dead (slides, share), (2) subsumed by mockup (generate-web-diagram), (3) distinct workflows needing a new home or explicit deletion decision (diff-review, fact-check, plan-review, project-recap).
**Design challenge**: After this merge, what handles "fact check this document against the actual code"?

---

### 3. Eval suite not in cleanup manifest — HIGH

**What's wrong**: `evals/compliance/routing/intent-to-skill-design-ux.yaml` has 6 test cases asserting routing to the deleted skills. The cleanup manifest doesn't mention this file.
**Why it matters**: 6 eval failures after migration. If evals run in CI, this blocks merges. If they don't, stale evals mislead future maintainers.
**Evidence (code)**:
- `evals/compliance/routing/intent-to-skill-design-ux.yaml:24-58` — 3 interface-design cases
- `evals/compliance/routing/intent-to-skill-design-ux.yaml:138-158` — 3 visual-explainer cases
- `research.md:319-325` — cleanup manifest omits eval files
**Raised by**: Senior + Architect + Adversarial
**Better approach**: Add eval file to "Files to MODIFY." Update all 6 cases to expect `mine.mockup`.

---

### 4. Session persistence silently dropped — HIGH

**What's wrong**: `.interface-design/system.md` is the mechanism that prevents "every session starts from scratch." The research dismisses it as not needed for mockups, but without persistence, the same design-direction questions get asked every session for the same project.
**Why it matters**: Reintroduces the exact problem interface-design was built to solve (`SKILL.md:20`).
**Evidence (code)**:
- `skills/mine.interface-design/SKILL.md:20-22` — frames persistence as the core problem
- `skills/mine.interface-design/SKILL.md:256-258` — reads system.md on every invocation
- `research.md:111` — dismisses persistence
**Raised by**: Senior
**Better approach**: Save the design brief (intent, palette, typography, signature) to a project-local file after Phase 1. Check for it on subsequent invocations.
**Design challenge**: If you create 3 mockups for the same project over 3 sessions, do you want to answer the design-direction questions each time?

---

### 5. Design-direction principles have no extraction point — HIGH

**What's wrong**: The research acknowledges design-direction principles are useful for `mine.build` and real app code, but defers extraction as a "future optimization." This guarantees duplication the moment someone needs design direction outside mockup context.
**Why it matters**: After interface-design is deleted, "help me design this settings page" for a real Svelte app has nowhere to go except `/mine.mockup` — which generates standalone HTML, not project code.
**Evidence (code)**:
- `research.md:264` — "future optimization, not a blocker"
- `skills/mine.interface-design/SKILL.md:145-212` — principles are framework-agnostic
**Raised by**: Architect
**Better approach**: Extract design-direction framework into `skills/mine.mockup/references/design-direction.md`. mine.mockup reads it in Phase 1; other skills can reference it too.

---

### 6. HCD pipeline semantics break — MEDIUM

**What's wrong**: Replacing interface-design (a decision layer) with mockup (an artifact layer) changes the pipeline from "progressive refinement of design decisions" to "empathy -> HTML file."
**Why it matters**: HCD outputs (accessibility requirements, persona analysis) should feed into whatever you're building, not just standalone HTML mockups.
**Evidence (code)**:
- `skills/mine.human-centered-design/SKILL.md:274` — "Craft the visual system with intent"
- `research.md:260` — claims the change is "actually better"
**Raised by**: Architect + Adversarial
**Note**: User confirmed HCD is going away in a separate PR. This finding is moot for this change but worth noting if HCD survives.

---

### 7. Prefix convention loses its only example — MEDIUM

**What's wrong**: Removing vx leaves the multi-prefix naming system with no concrete example in CLAUDE.md/README.md.
**Raised by**: Senior
**Better approach**: Replace with a hypothetical example.

---

## Appendix: Individual Critic Reports

These files contain each critic's unfiltered findings and are available for the duration of this session:

- Senior Engineer: `/tmp/claude-mine-challenge-SS71bB/senior.md`
- Systems Architect: `/tmp/claude-mine-challenge-SS71bB/architect.md`
- Adversarial Reviewer: `/tmp/claude-mine-challenge-SS71bB/adversarial.md`
