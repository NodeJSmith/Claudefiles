# Design Critique: mine.visual-qa

**Date**: 2026-03-17
**Target**: `skills/mine.visual-qa/SKILL.md`
**Status**: Findings saved, decision pending

## Summary

Three independent critics reviewed the mine.visual-qa skill design. Core tension: the skill formalizes a three-agent parallel architecture based on UX evaluation research, but the original success came from two agents with simple prompts. The formalization may not produce better results.

## Findings

### 1. Use `general-purpose`, not named agent types — CRITICAL

**What's wrong**: The skill routes through `design-visual-storyteller`, `design-ux-researcher`, `design-ui-designer` — agent types whose definitions are about brand storytelling, A/B testing, and design tokens. The prompts completely override these definitions (the research brief itself says so at line 205), so they add 100+ lines of irrelevant system prompt noise. Worse, named agent types may not have access to Playwright MCP tools — `mine.challenge` uses `general-purpose` for exactly this reason.
**Raised by**: All three critics
**Better approach**: `subagent_type: general-purpose` for all agents, same as `mine.challenge`.
**Design challenge**: Have you actually tested that a `design-visual-storyteller` agent can call Playwright MCP tools?

### 2. Three parallel agents fighting over one Playwright browser — CRITICAL

**What's wrong**: Playwright MCP manages a single browser instance. Three agents concurrently calling `browser_navigate` will fight over the same tab. Meanwhile, Agent 2 (Flow Walker) is instructed to create, edit, and delete items, mutating the state the other two agents are reading.
**Raised by**: Senior + Architect
**Better approach**: Screenshot-first architecture — a single orchestrator navigates all pages serially, captures all screenshots, saves to temp dir. Then agents analyze saved screenshots in parallel without Playwright access.
**Design challenge**: Have you tested two background agents calling `browser_navigate` simultaneously?

### 3. Over-engineering what worked — research recommendations skipped — HIGH

**What's wrong**: The research recommended: (1) sharpen the 2-agent split, (2) test for <30% overlap, (3) only then add a third if gaps remain. Steps 2-4 were skipped. The skill ships maximum complexity without validating it produces better results than the simple version.
**Raised by**: Adversarial (CRITICAL) + Senior
**Better approach**: Ship a simpler version first. Validate three agents find meaningfully different things.
**Design challenge**: Can you point to a concrete example where the three-agent version found something the original two-agent approach would have missed?

### 4. IGNORE instructions are a leaky abstraction — HIGH

**What's wrong**: Each agent is told what NOT to critique. LLMs don't reliably obey negative instructions. When a label confusion IS the flow problem, the IGNORE creates a gap. `mine.challenge` never needs IGNORE instructions because its critics' focus areas are naturally disjoint — the need for IGNORE signals the pattern doesn't fit.
**Raised by**: Adversarial + Architect
**Better approach**: Give agents a sharply scoped task that naturally excludes other concerns.
**Design challenge**: What happens when you remove the IGNORE instructions entirely?

### 5. The mine.challenge template may not transfer to visual review — HIGH

**What's wrong**: Code has genuinely disjoint concern layers (runtime, coupling, abstraction). Screenshots don't — an LLM sees the entire visual surface at once. The ~33% overlap figure is from human evaluators; AI agents have less natural variation.
**Raised by**: Adversarial + Senior
**Better approach**: Consider a sequential pipeline — one agent reacts, a second probes gaps.
**Design challenge**: Can you show non-overlapping findings from Agent 1 and Agent 3 on the same screenshot?

### 6. Synthesis confidence scoring adds no value — MEDIUM

**What's wrong**: "2-3 agents agree = HIGH CONFIDENCE" doesn't mean meaningful triangulation for visual review. Missing TENSION tier for contradictions.
**Raised by**: Adversarial + Architect
**Better approach**: Drop confidence scoring. Prioritize by user impact. Add TENSION tier.

### 7. No pre-flight checks, no auth handling, no failure recovery — MEDIUM

**What's wrong**: No Playwright verification, `ss` fails on macOS, no auth concept, no timeout handling for background agents.
**Raised by**: Senior
**Better approach**: Pre-flight phase that confirms Playwright, checks auth, handles macOS.

## Architectural Recommendation

The senior engineer's **screenshot-first architecture** resolves findings 1, 2, and state mutation simultaneously:
1. Single orchestrator navigates all pages, takes all screenshots (desktop + mobile + dark mode), saves to temp dir
2. N `general-purpose` agents analyze saved screenshots in parallel without Playwright access
3. No browser contention, no state mutation, agent type doesn't matter

The adversarial reviewer's deeper question remains open: is the three-parallel-agent pattern the right approach at all for visual review, or should this be fundamentally simpler?

## Appendix: Individual Critic Reports

These files contain each critic's unfiltered findings:

- Senior Engineer: `/tmp/claude-mine-challenge-17sPch/senior.md`
- Systems Architect: `/tmp/claude-mine-challenge-17sPch/architect.md`
- Adversarial Reviewer: `/tmp/claude-mine-challenge-17sPch/adversarial.md`
