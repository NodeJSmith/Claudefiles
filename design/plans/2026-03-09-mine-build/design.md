# Design: mine.build — Single Entry Point Skill

**Date:** 2026-03-09
**Status:** implemented

## Problem

The caliper workflow has six skills that must be invoked in sequence (design → draft-plan → plan-review → orchestrate → implementation-review → ship), and sophia CR tracking is an optional layer on top. There's no single entry point — the user must know which skill to start, pass arguments between steps, and remember which step comes next. This creates friction for common use cases and makes the workflow harder to discover.

The simple case (1-3 file change, clear approach) is over-engineered by the full caliper chain, but the user has to decide that themselves before picking a skill.

## Non-goals

- Does not replace or modify any existing skill (mine.design, mine.draft-plan, mine.orchestrate, mine.ship, mine.sophia, mine.implementation-review). This skill only orchestrates them.
- Does not add new workflow steps beyond what those skills already define.
- Does not implement code itself for the complex paths — it delegates to the appropriate skills.
- Does not auto-detect complexity without asking the user to confirm the routing choice.

## Proposed approach

A new `skills/mine.build/SKILL.md` with three phases:

**Phase 1 — Understand the request.** Accept `$ARGUMENTS` as the change description or ask if empty. Briefly paraphrase what was heard to confirm scope.

**Phase 2 — Check sophia + route.** Run two parallel checks: `command -v sophia` and `Glob: SOPHIA.yaml`. Then present three routing options via AskUserQuestion, with a brief complexity signal to guide the choice:

- **Simple** — implement inline → code-reviewer subagent → mine.ship
- **Complex** — chain mine.design → mine.draft-plan → mine.plan-review → mine.orchestrate → mine.implementation-review → mine.ship
- **Complex + Sophia** — same as Complex with sophia CR setup woven in at the right points

The Sophia option is always shown, but if sophia is not installed or SOPHIA.yaml is missing, its description notes "setup required."

**Phase 3 — Execute the chosen path.**

*Path A (Simple):* Explore with Glob/Grep/Read, implement the change, launch the code-reviewer subagent, present findings, gate on ship/fix/stop.

*Path B (Complex):* Chain the skills in sequence. Each skill handles its own sign-off gate. mine.build bridges the handoffs: when mine.design approves → run mine.draft-plan; when that finishes → mine.plan-review; on APPROVE → mine.orchestrate; mine.orchestrate's post-execution handoff offers mine.implementation-review; after that approves → gate on mine.ship.

*Path C (Complex + Sophia):* Run Path B, but: (1) resolve sophia readiness first (install if missing, init SOPHIA.yaml if missing via mine.sophia, or switch to Path B if user declines), (2) after plan is approved create a sophia CR and optionally set its contract via mine.sophia, (3) mine.orchestrate already detects the active CR and offers per-task updates, (4) after implementation review APPROVE offer sophia cr merge before mine.ship.

## Alternatives considered

**Auto-classify complexity without asking.** Rejected — the signals for "simple vs complex" are often ambiguous (a 2-file change might have significant design uncertainty). Presenting a routing choice with a brief complexity assessment is better than a wrong auto-classification.

**Duplicate skill logic inline.** Rejected — duplicating mine.design, mine.draft-plan, etc. inside mine.build would create a maintenance burden. The skill chains by instructing Claude to follow each referenced skill's phases in sequence.

**Single new mega-skill replacing the chain.** Rejected — the individual skills have standalone value and are invoked directly in many workflows. mine.build wraps them, not replaces them.

## Open questions

None.

## Impact

- New file: `skills/mine.build/SKILL.md`
- Run `./install.sh` after adding to create the symlink
- Update `README.md`: skill count + new row in skills table
- Update `rules/common/capabilities.md`: add mine.build to the intent routing table and the Workflow skills section description
