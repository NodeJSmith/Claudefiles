---
proposal: "Mine patterns from obra/superpowers for improving code-reviewer and integration-reviewer agents"
date: 2026-04-10
status: Draft
flexibility: Exploring
motivation: "Find prior-art patterns, prompt structures, and review techniques from a well-regarded public Claude Code skill bundle that could improve the existing code-reviewer and integration-reviewer agents"
constraints: "Findings must be applicable to Claude Code subagent definitions (YAML frontmatter + system prompt). Agents must remain compatible with the existing mine.orchestrate, mine.ship, and mine.review invocation pipelines."
non-goals: "Not a full rewrite of either agent. Not adopting obra/superpowers as a dependency. Not changing the Python/static-analysis checks themselves."
depth: normal
---

# Research Brief: Code Review Patterns from obra/superpowers

**Initiated by**: User asked for a thorough look at `obra/superpowers` with the specific goal of finding patterns, prompt engineering, checklist structures, and agent architectures that could inform improvements to the existing `agents/code-reviewer.md` and `agents/integration-reviewer.md`.

## Context

### What prompted this
The repo's two pre-commit review agents (`code-reviewer`, `integration-reviewer`) are the main quality gate before any commit. They work, but the user wants to know whether a prominent public skill bundle — `obra/superpowers` by Jesse Vincent — has prompt patterns, workflow structures, or review techniques worth absorbing.

### What obra/superpowers is
A published Claude Code plugin / skills framework positioned as "an agentic skills framework and software development methodology that works." It ships via the official Claude plugin marketplace (`/plugin install superpowers@claude-plugins-official`) and also via the `obra/superpowers-marketplace` registry. It runs on Claude Code, Cursor, Codex, OpenCode, Copilot CLI, and Gemini CLI.

The overall thesis: **process over guessing**. Instead of jumping to code, the agent is pushed through brainstorming -> design -> plan -> subagent-driven implementation -> layered review -> finish-branch. Review is not a one-shot late-stage activity; it's a checkpoint after every task.

Top-level skills (14 total):
- `brainstorming`
- `dispatching-parallel-agents`
- `executing-plans`
- `finishing-a-development-branch`
- **`receiving-code-review`**
- **`requesting-code-review`**
- `subagent-driven-development`
- `systematic-debugging`
- `test-driven-development`
- `using-git-worktrees`
- `using-superpowers`
- **`verification-before-completion`**
- `writing-plans`
- `writing-skills`

Only one agent file: `agents/code-reviewer.md`. The review-heavy work is split across the three skills highlighted above plus the two-stage review embedded in `subagent-driven-development`.

### Current state of the target agents
- `agents/code-reviewer.md` (model: sonnet, ~620 lines): a large content-dense checklist agent covering Python security, error handling, type hints, Pythonic code, concurrency, performance, best practices, markdown/skill-file conventions, diagnostic commands, framework-specific checks, and approval criteria. Uses severity bands (CRITICAL / HIGH / MEDIUM / LOW). Has explicit invocation-pattern branching (orchestrate vs manual) and a git-discovery cascade.
- `agents/integration-reviewer.md` (model: sonnet, ~255 lines): a dimension-based checker (Duplication, Misplacement, Interface inconsistency, Design violation, Naming drift, Orphaned code, Coupling). Explicitly bounds exploration ("5 sibling reads + 8 grep searches"). Defines a "What This Agent Does NOT Do" section to prevent scope creep. Outputs a summary table with verdict.

Both agents are strong on *content* (what to look for) and *discovery* (how to find the diff). The gaps exposed by the comparison below are mostly about *workflow*, *trust*, *verification*, and *reviewer-reviewee interaction*, not the checklists themselves.

### Key constraints
- Must remain single-invocation subagents callable by `mine.orchestrate`, `mine.ship`, and `mine.review`
- Cannot depend on obra/superpowers being installed
- Must keep existing Python-specific checks intact — they encode repo conventions the user curated
- The orchestrate pipeline passes explicit file lists; the self-discovery cascade must remain for other invocations

## Feasibility Analysis

### What would need to change

| Area | Files affected | Effort | Risk |
|------|---------------|--------|------|
| Add explicit anti-trust framing ("do not trust the implementer's report") | `agents/code-reviewer.md` (already has a minimal version; could strengthen) | Small | Low |
| Add verdict vocabulary / status discipline | `agents/code-reviewer.md` | Small | Low |
| Add self-review loop guidance for re-review after fixes | Both agents + callers (`mine.orchestrate`, `mine.review`) | Medium | Medium — changes orchestration contract |
| Split code-reviewer into two roles: spec-compliance vs code-quality | `agents/code-reviewer.md` -> new agent + rework | Large | High — breaks existing single-agent model |
| Add reviewer-reviewee interaction protocol (how the implementer responds) | New: `rules/common/receiving-code-review.md` or similar | Small | Low |
| Introduce a "verification-before-completion" rule | New rule file or section in `git-workflow.md` | Small | Low |
| Template-based invocation (placeholders for BASE_SHA / HEAD_SHA / description) | `agents/code-reviewer.md` + callers | Medium | Medium — every caller must fill placeholders |

### What already supports this
- Both agents already have strong severity banding — adopting superpowers' Critical/Important/Minor vocabulary is a near-zero-cost rename if desired
- `integration-reviewer` already has a "What This Agent Does NOT Do" section — superpowers uses the same device in multiple skills, validating the pattern
- The codebase already uses per-skill temp directories (`get-skill-tmpdir`), which maps cleanly onto superpowers' "Task tool fills a prompt template" pattern
- `mine.orchestrate` already runs executor + reviewer subagents — the conceptual architecture is the same as superpowers' subagent-driven-development

### What works against this
- The target `code-reviewer.md` is a **content-heavy single agent** (~620 lines). Superpowers' model is **process-heavy small prompts**. Adopting the superpowers structure wholesale would mean splitting the file and moving much of the checklist content into a separate Python-conventions document — a big structural change
- The user curated per-language anti-pattern examples (SQL injection, mutable defaults, shadowing built-ins, etc.) that superpowers' agent doesn't have. These can't be dropped
- Superpowers review uses a template at `requesting-code-review/code-reviewer.md` that callers fill in. The target repo's agents self-discover everything. Moving to templates means every caller (`mine.orchestrate`, `mine.ship`, `mine.review`, manual invocations) has to learn the new contract

## Options Evaluated

### Option A: Targeted absorption of four specific patterns (Recommended)

Pull four concrete, self-contained techniques from superpowers into the existing agents without changing their overall shape. Each is independently landable.

**Pattern 1 — Explicit anti-trust framing (from `spec-reviewer-prompt.md`).** Superpowers' spec reviewer starts with:

> "The implementer finished suspiciously quickly. Their report may be incomplete, inaccurate, or optimistic. You MUST verify everything independently.
> **DO NOT:** Take their word for what they implemented / Trust their claims about completeness / Accept their interpretation of requirements
> **DO:** Read the actual code they wrote / Compare actual implementation to requirements line by line / Check for missing pieces they claimed to implement / Look for extra features they didn't mention"

The target `code-reviewer.md` has a short "Spec Verification (HIGH)" section that says something similar but lacks the adversarial tone and the DO/DO NOT structure. The superpowers version is both shorter and more enforceable because it frames the mental stance, not just the checks. Worth copying verbatim (with attribution).

**Pattern 2 — Verdict vocabulary and "assessment" block (from `code-reviewer.md` template).** Superpowers requires the reviewer to end with:

```
### Assessment
**Ready to merge?** [Yes/No/With fixes]
**Reasoning:** [Technical assessment in 1-2 sentences]
```

Target `code-reviewer.md` has "Approval Criteria" but no required verdict output format. `integration-reviewer` already has `APPROVE / WARN / BLOCK` — worth standardizing both agents on the same verdict vocabulary. Adopt `APPROVE / APPROVE_WITH_FIXES / BLOCK` as a unified scheme.

**Pattern 3 — Category discipline ("DO: categorize by actual severity; DON'T: mark nitpicks as Critical").** Superpowers' template has a "Critical Rules" list:

> **DO:** Categorize by actual severity (not everything is Critical) / Be specific (file:line, not vague) / Explain WHY issues matter / Acknowledge strengths / Give clear verdict
> **DON'T:** Say "looks good" without checking / Mark nitpicks as Critical / Give feedback on code you didn't review / Be vague / Avoid giving a clear verdict

Target `code-reviewer.md`'s "Critical Rules" section is close but doesn't explicitly warn against severity inflation. This is a ~5-line addition that directly addresses a common failure mode of LLM reviewers (marking everything as HIGH to look thorough).

**Pattern 4 — Acknowledge strengths explicitly.** Both superpowers templates require a `### Strengths` section before issues. The target agents don't. Omitting this is an intentional terseness choice, but the presence of strengths has a real downstream effect: it signals to the implementer that the review is calibrated, which reduces the "argue with the reviewer" problem that `receiving-code-review` tries to solve. Low-cost to add; high-value for tone.

**Pros (specific to this codebase):**
- No breaking changes to invocation contract — `mine.orchestrate` and `mine.ship` don't need to change
- Each pattern is independently valuable and independently reversible
- Preserves the Python-specific checklist content that makes the target agents uniquely useful
- Patterns 1 and 3 directly address known LLM review failure modes (optimistic reports, severity inflation)

**Cons (specific to this codebase):**
- Does not capture superpowers' biggest structural insight: two-stage review (spec compliance, *then* code quality)
- Leaves `code-reviewer.md` as a 600+ line single file — the length itself may be a maintainability cost

**Effort estimate**: Small — each pattern is 5-20 lines of addition to existing files, no structural changes, no caller changes.

**Dependencies**: None.

### Option B: Adopt the two-stage review model

Split review into two subagents with strict ordering, mirroring superpowers' spec-reviewer -> code-quality-reviewer pipeline.

- `spec-reviewer`: Verifies the diff matches the stated requirements (what a WP or issue said to do). Primary question: "Did they build the right thing?" Outputs: missing requirements, extra/unrequested features, misinterpretations.
- `code-quality-reviewer`: Verifies the diff is well-built. Primary question: "Is it built well?" Outputs: the existing Python/security/correctness checks.
- **Ordering is strict**: code-quality review cannot run until spec review is green. Superpowers enforces this explicitly ("Never: Start code quality review before spec compliance is green").

**How it works**: `mine.orchestrate`'s Phase 3 (implementation review) becomes a two-call sequence. The existing `code-reviewer` agent keeps the correctness/security checks and loses the "Spec Verification" section. A new `spec-reviewer` agent owns WP/spec compliance. Both callers (`mine.orchestrate`, `mine.ship`, `mine.review`) need to run the spec check first, then the quality check.

**Pros:**
- Matches the two failure modes that *actually* ship bad code: built-the-wrong-thing and built-the-right-thing-badly. These are genuinely orthogonal
- Reduces cognitive load on each reviewer — each one has a single lens
- Maps cleanly onto the caliper workflow where WPs define "what" and code conventions define "how"
- Would catch "implementer added a flag nobody asked for" scenarios that `code-reviewer.md` is not designed to catch

**Cons:**
- Doubles the number of reviewer calls in the pipeline (cost and latency — though superpowers argues catching issues early pays for it)
- `mine.ship` and `mine.review` callers need to learn the new contract
- Risk of duplication between spec-reviewer and integration-reviewer — both are "fit" checks. Need a clean boundary
- `code-reviewer` has to give up its "Spec Verification" section, which duplicates effort today

**Effort estimate**: Large — new agent file, rework of `code-reviewer.md`, updates to `mine.orchestrate`, `mine.ship`, `mine.review` and associated rules (`rules/common/git-workflow.md`).

**Dependencies**: None technical, but requires user buy-in for a workflow contract change.

### Option C: Add a `receiving-code-review` rule (do less)

The single highest-leverage, smallest-surface-area change from superpowers is **not** about the reviewers — it's about how the implementer responds. Superpowers' `receiving-code-review/SKILL.md` is a 180-line rule that forbids performative agreement ("You're absolutely right!"), forbids blind implementation, requires verification against the codebase before acting on feedback, and describes when to push back.

The target repo has no equivalent. Its closest document is `rules/common/git-workflow.md`, which describes the code-review loop (3 iterations max) but says nothing about the posture the agent should take when receiving feedback. This is where Claude often burns cycles — accepting a wrong suggestion, "fixing" it, and breaking something else.

**How it works**: Add a new rule file `rules/common/receiving-code-review.md` (or a section in `git-workflow.md`) that encodes:
- The response pattern: READ -> UNDERSTAND -> VERIFY -> EVALUATE -> RESPOND -> IMPLEMENT
- Forbidden responses ("You're absolutely right", "Great point", "Let me implement that now")
- Source-specific handling (trusted human feedback vs external reviewer)
- YAGNI check for "professional features" — grep for usage before adding suggested abstractions
- Implementation order for multi-item feedback (clarify unclear items first, then blocking -> simple -> complex)
- Guidance on when to push back with technical reasoning

**Pros:**
- Addresses a real failure mode: Claude implementing incorrect review suggestions because it treats review as social pressure
- Zero-cost to the reviewer agents themselves
- One file, auto-loaded via `rules/common/`, applies to every invocation where feedback is received
- Complements the user's existing rule against sycophancy
- Directly lifts battle-tested language from superpowers

**Cons:**
- Doesn't improve the reviewers themselves — leaves Option A and B on the table
- Another rule file to maintain in the always-loaded set

**Effort estimate**: Small — single file, ~100 lines, copy-and-adapt from superpowers.

**Dependencies**: None.

## Concerns

### Technical risks
- **Adopting Option B without a clean boundary between `spec-reviewer` and `integration-reviewer` risks duplicate findings.** Both check "fit" in different senses. A clear decision: `spec-reviewer` checks against the WP/spec document; `integration-reviewer` checks against the rest of the codebase. Keep them orthogonal or merge them
- **Superpowers' review templates use `general-purpose` subagents with a filled-in prompt**, while this repo uses named agents with stable prompts + caller file lists. The two models don't mix cleanly — if you copy the template pattern, you get caller complexity; if you keep named agents, you can't fully adopt the template model. Option A avoids this tension by cherry-picking content, not structure
- **The anti-trust framing (Pattern 1) only works if reviewers actually re-read the code.** Both target agents already read changed files, but the superpowers version pushes further — it also implies grepping for "did the implementer actually wire this up" rather than just reading the diff. That's stronger and would require explicit instruction to run verification searches

### Complexity risks
- **Option B splits review cleanly but doubles the agent count.** The target repo already has 18 agents — adding a 19th with overlapping responsibilities could confuse the routing table in `rules/common/agents.md`
- **Option A's four patterns are independent but, if all landed, they interact with each other.** Each adds ~10-20 lines to `code-reviewer.md`. Cumulative ~60-line growth on an already-long file is meaningful. Consider landing them in order of highest-impact (Pattern 1, Pattern 3, Pattern 4, Pattern 2)

### Maintenance risks
- **Any verdict vocabulary change is a contract break for downstream parsing.** `mine.orchestrate` currently reads reviewer output to decide whether to loop. If it parses "APPROVE / WARN / BLOCK" from `integration-reviewer` today, changing `code-reviewer` to emit "APPROVE_WITH_FIXES" means updating the orchestrator's parser. Verify before changing
- **A new `receiving-code-review` rule becomes a permanent context cost** — it loads on every session. Keep it under 150 lines; the superpowers version is 180 and is close to the upper bound of what belongs in an always-loaded rule

## Open Questions

- [ ] Does `mine.orchestrate` parse reviewer output programmatically, or just feed it back into a judge-style agent? (Affects whether verdict vocabulary changes are free or expensive.)
- [ ] Is the user willing to split `code-reviewer.md` into spec vs quality, or is the current single-agent model a hard constraint? (Determines whether Option B is viable.)
- [ ] Should a new `receiving-code-review` rule apply globally (auto-loaded from `rules/common/`) or only in the code-review loop in `mine.orchestrate` and `mine.ship`? Global gives broader coverage; scoped keeps context smaller.
- [ ] Does the user want to adopt superpowers' "Strengths" requirement? It's low-cost but does add output volume — a preference call, not a correctness call.
- [ ] Is there appetite for adding a `verification-before-completion` rule separate from the reviewer agents? Superpowers treats this as a cross-cutting discipline, not a review-only concern.

## Recommendation

**Land Option A (four targeted patterns) plus Option C (receiving-code-review rule).** Together, these deliver the biggest wins from superpowers' review methodology without breaking any caller contracts or forcing a structural rework. They are additive, reversible, and address specific known failure modes in LLM-driven code review.

**Defer Option B (two-stage review).** The structural insight is real, but the integration cost is high and there's meaningful overlap with `integration-reviewer`. Revisit if `mine.orchestrate` reviewer quality becomes a bottleneck.

### Suggested next steps

1. **Pattern 1 first** — add the adversarial "do not trust the implementer's report" framing to `code-reviewer.md`'s Spec Verification section. It is the single highest-leverage addition and copies almost verbatim from superpowers' `spec-reviewer-prompt.md`.
2. **Create `rules/common/receiving-code-review.md`** — lift and adapt the response pattern, forbidden-responses list, and YAGNI check. Keep it under 120 lines.
3. **Add Pattern 3 (severity-inflation warning) and Pattern 4 (strengths section)** to `code-reviewer.md`. Small additions, immediate value.
4. **Defer Pattern 2 (verdict vocabulary unification)** until a check of `mine.orchestrate`'s reviewer-output parser confirms the change is safe.
5. **Before any of the above**, audit the existing `rules/common/git-workflow.md` "Code Review Loop" section for conflicts with a new `receiving-code-review.md` rule — they should be complementary, not overlapping.

## Sources

- [obra/superpowers — GitHub](https://github.com/obra/superpowers)
- [obra/superpowers — README.md](https://github.com/obra/superpowers/blob/main/README.md)
- [obra/superpowers — agents/code-reviewer.md](https://github.com/obra/superpowers/blob/main/agents/code-reviewer.md)
- [obra/superpowers — skills/requesting-code-review/SKILL.md](https://github.com/obra/superpowers/blob/main/skills/requesting-code-review/SKILL.md)
- [obra/superpowers — skills/requesting-code-review/code-reviewer.md (template)](https://github.com/obra/superpowers/blob/main/skills/requesting-code-review/code-reviewer.md)
- [obra/superpowers — skills/receiving-code-review/SKILL.md](https://github.com/obra/superpowers/blob/main/skills/receiving-code-review/SKILL.md)
- [obra/superpowers — skills/subagent-driven-development/SKILL.md](https://github.com/obra/superpowers/blob/main/skills/subagent-driven-development/SKILL.md)
- [obra/superpowers — skills/subagent-driven-development/spec-reviewer-prompt.md](https://github.com/obra/superpowers/blob/main/skills/subagent-driven-development/spec-reviewer-prompt.md)
- [obra/superpowers — skills/subagent-driven-development/code-quality-reviewer-prompt.md](https://github.com/obra/superpowers/blob/main/skills/subagent-driven-development/code-quality-reviewer-prompt.md)
- [obra/superpowers — skills/subagent-driven-development/implementer-prompt.md](https://github.com/obra/superpowers/blob/main/skills/subagent-driven-development/implementer-prompt.md)
- [obra/superpowers — skills/verification-before-completion/SKILL.md](https://github.com/obra/superpowers/blob/main/skills/verification-before-completion/SKILL.md)
- [Superpowers: How I'm using coding agents in October 2025 — blog.fsck.com](https://blog.fsck.com/2025/10/09/superpowers/)
