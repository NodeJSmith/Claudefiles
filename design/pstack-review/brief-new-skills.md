# Brief: New Skills to Steal from cursor/plugins:pstack

Source: Claude Code Digest May 27 + Jun 1, 2026  
Branch: pstack-review  
Status: Ready for pickup

---

## Overview

Six fully novel skills from pstack, none with meaningful local equivalents. Ranked by impact.

---

## 1. `show-me-your-work` — Autonomous Run Audit Trail

**What it does:** Maintains an append-only TSV decision trail (timestamp, phase, decision, why, evidence, result) for long-running or unattended agent work. Includes a hardened `log.sh` helper that strips formula-injection characters. Has a cross-model review step that spawns a different model family to audit the trail for weak evidence and skipped verification before handing back.

**Why we need it:** When `mine.orchestrate` runs unattended over multiple tasks, there's no structured record of what it did or why. You end up reading diffs and trying to reconstruct reasoning. This skill would give you a reviewable log that renders as a GitHub table, making post-run audits concrete rather than reconstructed.

**Priority:** High — this directly plugs the autonomous-run discipline gap. The `autonomous-run-discipline.md` rule tells the agent to "keep a decision trail" but provides no mechanism to actually do it.

**Implementation sketch:**
- New skill at `skills/mine.show-my-work/SKILL.md`
- TSV written to `get-skill-tmpdir show-my-work` per run, optionally committed
- `log.sh` wrapper strips `;`, `=`, `+`, `@` from first char to block formula injection
- Cross-model audit: after main work, spawn a Haiku reviewer on the trail file, flag entries with "should work" / "probably" / no evidence field
- Wire into `mine.orchestrate` Phase 3 as an optional step

**Source:** `cursor/plugins:pstack` (PRs #78, #89)

---

## 2. `arena` — Multi-Model Parallel Implementation + Synthesis

**What it does:** Fans out N parallel attempts at the same artifact across diverse models (different model families, not just parallel Sonnet runs). Reads every candidate end-to-end using a concrete rubric derived from the task. Picks the strongest as the base, then grafts the best ideas from the losers into the winner. Each candidate writes to its own worktree.

**Why we need it:** `mine.brainstorm` generates ranked ideas for human selection. `arena` produces N concrete implementations and synthesizes the best parts of all of them. For one-way-door decisions — a skill file design, a complex API shape, a hook architecture — this is meaningfully better than a single attempt plus review. The cross-judge phase gives you an objective comparison before you commit.

**Priority:** High — the worktree isolation machinery is already here. This is mostly a skill file + orchestration pattern.

**Implementation sketch:**
- New skill at `skills/mine.arena/SKILL.md`
- Phase 1: derive concrete rubric from the task (3–5 measurable criteria)
- Phase 2: fan out 3–4 parallel executor agents, each in its own worktree (per `agents.md` isolation rules)
- Phase 3: synthesize — spawn an Opus judge that reads every candidate against the rubric, picks the winner, identifies the best move from each loser
- Phase 4: graft — apply the best-of-losers moves into the winner worktree
- Works on: skill files, agent definitions, rule files, API designs, complex functions
- Trigger: "run arena on this", "parallel implementations", "best of N"

---

## 3. `interrogate-cross-model` — Model-Diversity Review

**What it does:** Spawns four reviewers on four different model families with identical prompts and a concrete rubric. A lead-judgment step then categorizes all findings into act-on / consider / noted / dismissed — actively dismissing findings that miss context with explicit reasoning, not just consolidating everything.

**Why we need it:** The local `mine.review` uses three domain-specialized reviewers (correctness, integration, readability) on a single model. Cross-model agreement is a fundamentally different signal — findings that three different model families all flag independently are near-certain real issues. The active dismissal step also addresses a real pain point: consolidated review lists include a lot of noise that requires manual filtering.

**Priority:** Medium-high — this is an upgrade to `mine.review` rather than a net-new workflow. Could be a flag (`mine.review --cross-model`) or a separate skill.

**Implementation sketch:**
- New skill at `skills/mine.interrogate/SKILL.md` or flag on `mine.review`
- Rubric: 4–5 criteria derived from the diff context (security, correctness, perf, readability, test coverage)
- Reviewers: Opus, Sonnet 3.7, Haiku 3.5, Sonnet 3.5 — same prompt, different families
- Lead judgment (Opus): categorize each unique finding across reviewers, actively dismiss findings that conflict with project context, output structured table
- Useful for: pre-merge review of large PRs, skill files before shipping, security-sensitive changes
- Trigger: "cross-model review", "interrogate this", "high-confidence review"

---

## 4. `how` — Interactive Subsystem Explanation

**What it does:** Explains subsystem architecture and runtime flow at senior-engineer onboarding depth. Complexity-adaptive: spawns 2–4 parallel explorer agents for multi-file subsystems then synthesizes with Opus; uses a single direct-explain agent for simple questions. Optional critique mode spawns independent reviewers after the explanation to check it for gaps.

**Why we need it:** The `architect` agent generates architectural documentation (diagrams, overviews). That's not the same as answering "walk me through how `mine.orchestrate` phases work when a task fails." The how skill is for building mental models interactively, not producing artifacts.

**Priority:** Medium — low implementation cost, high daily usefulness.

**Implementation sketch:**
- New skill at `skills/mine.how/SKILL.md`
- Complexity gate: if question involves >3 files or a non-trivial runtime flow → spawn 2–4 parallel Haiku explorers, synthesize with Sonnet
- Simple questions: single Sonnet direct-explain
- Output: narrative walkthrough — no diagrams, no headers-heavy docs, just explanation
- Optional: `--critique` flag spawns an independent Haiku reviewer on the explanation to flag gaps or inaccuracies
- Trigger: "how does X work", "walk me through", "explain this subsystem"

---

## 5. `why` — Decision Rationale Investigation

**What it does:** Investigates why code is shaped the way it is by querying seven evidence categories in parallel: source control history, issue trackers, design docs, team chat, observability, error tracking, analytics. Treats null results as first-class evidence. Operates under strict "evidence before narrative" epistemics — explicitly refuses to speculate when evidence is absent.

**Why we need it:** `mine.research` investigates feasibility of proposed changes. It does not reconstruct historical rationale for existing decisions. "Why is this code shaped this way?" is a different question that's critical for safe refactoring — if you don't know why a weird constraint exists, removing it can break things that aren't obvious from the diff.

**Priority:** Medium — useful for legacy code archaeology and refactor safety.

**Implementation sketch:**
- New skill at `skills/mine.why/SKILL.md`
- Seven parallel evidence agents (Haiku): git log + blame, issue tracker search, design docs glob, CLAUDE.md + rules, comments in code, test assertions (often encode constraints), PR descriptions
- Synthesis (Sonnet): confidence-calibrated narrative — HIGH (multiple sources agree), MEDIUM (one source), LOW (inference), UNKNOWN (no evidence, explicitly stated)
- Output: "Here's what the evidence says and how confident we are" — not "here's the probable explanation"
- Trigger: "why is this code like this", "decision rationale", "why does this exist", "why was this built this way"

---

## 6. `figure-it-out` — Meta-Playbook for Ambiguous Tasks

**What it does:** For large or cross-cutting tasks that don't fit a narrower playbook. Requires framing a falsifiable definition-of-done and quantified scope before committing to a long run. Designs a phased workflow with explicit rigor calibration (how thorough does each phase need to be?). Runs a hypothesis loop: state claim → make smallest change → measure on real artifact → keep or revert. Logs all decisions via show-me-your-work.

**Why we need it:** Local setup has `mine.define` (requirements), `mine.orchestrate` (execution), `mine.debug` (bug investigation). Nothing for "here is a large ambiguous task — design the right approach first." Figure-it-out fills that gap, particularly for large Python migrations or multi-phase shell automation where the correct workflow isn't yet known.

**Priority:** Medium — complements rather than replaces existing skills. Most valuable when the task scope itself is unclear before starting.

**Implementation sketch:**
- New skill at `skills/mine.figure-it-out/SKILL.md`
- Phase 0: Framing — write a falsifiable predicate (tests green on these cases, file sizes below these thresholds, etc.) and quantify scope (N files, M callers, K edge cases)
- Phase 1: Workflow design — propose phases, assign rigor level (exhaustive / spot-check / trust-types), identify blockers and parallels
- Phase 2: Hypothesis loop — per iteration: state the hypothesis, make the smallest change, measure on real artifact, keep or revert, log
- Phase 3: Handoff to `mine.orchestrate` if the workflow is now concrete enough
- Trigger: "figure this out", "I don't know how to approach this", "large ambiguous task"
