# Research Brief: Why Compressed Routing Tables Cause Skill Under-Triggering

**Date**: 2026-03-16
**Status**: Ready for Decision
**Proposal**: Diagnose why the compressed routing table format in `capabilities.md` causes Claude Code to perform tasks inline instead of invoking skills via the Skill tool
**Initiated by**: 9/10 confusion-pair eval tests failing after commit dfa2623 compressed routing tables from markdown tables to pipe-delimited format

## Context

### What prompted this

After compressing `capabilities.md` (23,256 -> 6,042 chars, -74%) and `agents.md` (11,483 -> 2,786 chars, -76%), Claude Code reads the routing tables but performs tasks directly instead of dispatching to skills. Negative tests (10/10) pass fine — Claude does not over-trigger. The problem is exclusively under-triggering: Claude understands the intent but does not call the Skill tool.

### Current state

The routing table in `rules/common/capabilities.md` uses a pipe-delimited comment format:

```
# trigger phrases | target
brainstorm options, generate ideas, explore ideas | /mine.brainstorm
design this change, write a design doc | /mine.design
```

The old format was a markdown table:

```markdown
| User says something like... | Use this |
|-----------------------------|----------|
| "brainstorm options", "generate ideas" | `/mine.brainstorm` |
| "design this change", "write a design doc" | `/mine.design` |
```

### Key constraints

- The routing table must remain always-loaded (cannot move to an on-demand skill — chicken-and-egg problem)
- The 36% context reduction is valuable and should be preserved where possible
- The eval tests use `anthropic:claude-agent-sdk` provider with `working_dir: .` and `permission_mode: default`

## Root Cause Analysis

### The routing table is not what triggers skill invocation

This is the core finding. The routing table in `capabilities.md` is a **rules file** — it loads into the system prompt as context. But skill invocation is governed by a completely separate mechanism:

1. **The Skill tool has its own `<available_skills>` section** embedded in the tool description, built from skill frontmatter (`name` and `description` fields). This is what Claude sees when deciding whether to use a skill.

2. **The Skill tool description says**: "When users ask you to perform tasks, check if any of the available skills below can help complete the task more effectively." This is the actual trigger — Claude matches user intent against skill descriptions in the tool, not against the routing table.

3. **The Skill tool description also says** invoking a matching skill is a **"BLOCKING REQUIREMENT"** before generating other responses.

4. **The system prompt for skill invocation says**: `/<skill-name>` is shorthand for invoking skills. "IMPORTANT: Only use ${SKILL_TOOL_NAME} for skills listed in its user-invocable skills section - do not guess."

So the routing table in `capabilities.md` is supplementary guidance — a hint to Claude about which skill maps to which intent. But Claude's primary decision mechanism is the `<available_skills>` list in the Skill tool description, which is built from skill frontmatter.

### Why the old format worked better

The old markdown table format had several properties that strengthened the routing signal:

1. **Quoted trigger phrases**: `"brainstorm options"`, `"generate ideas"` — the quotes made these feel like exact-match specifications, not commentary
2. **Backtick-formatted targets**: `` `/mine.brainstorm` `` — code formatting signaled "this is a tool invocation, not prose"
3. **Table structure**: Markdown tables are a well-established pattern that LLMs recognize as structured data with clear column semantics
4. **Column headers**: "User says something like..." / "Use this" — imperative framing that explicitly mapped intent to action

### Why the new format works worse

The compressed format has several properties that weaken the routing signal:

1. **Comment-style header** (`# trigger phrases | target`) — the `#` prefix makes this look like a code comment, which LLMs often treat as advisory/ignorable metadata
2. **No quoting of trigger phrases** — `brainstorm options, generate ideas` reads as natural language description, not as match patterns
3. **No code formatting of targets** — `/mine.brainstorm` without backticks loses the "this is a tool call" signal
4. **Ambiguous format** — pipe-delimited plain text is less structured than a markdown table. The format looks like a comment block, which Claude may interpret as documentation rather than an actionable instruction set
5. **Lost imperative framing** — the column headers "User says something like..." (input) / "Use this" (action) were replaced with passive labels "trigger phrases" / "target"

### The compound effect

The routing table was already a secondary signal (the primary one being the Skill tool's `<available_skills>` section). When the secondary signal was strong (quoted phrases, code-formatted targets, imperative headers), it reinforced the primary signal enough to tip Claude toward skill invocation. When it was weakened (comments, plain text, passive framing), it no longer added enough reinforcement, and Claude defaulted to answering directly — which is the path of least resistance.

### Evidence from eval baselines

The WP01 baseline recorded that routing was "mediocre even with verbose tables" — some skill routing tests already failed with the old format. This confirms the routing table is supplementary, not primary. The old format was just barely reinforcing the `<available_skills>` signal enough to work; the new format drops below that threshold.

### External validation

Scott Spence's research on Claude Code skill activation reliability found that:
- Simple instruction-based hooks achieve only **20% success** at triggering skill invocation
- A "forced eval" pattern (requiring Claude to explicitly evaluate each skill YES/NO before proceeding) achieves **84% success**
- The key insight: "Passive suggestions like 'If the prompt matches skill keywords, use Skill()' become background noise"

This directly explains what is happening: the compressed routing table reads as a passive suggestion rather than an active instruction.

## What Would Need to Change

| Area | Files affected | Effort | Risk |
|------|---------------|--------|------|
| Routing table format | 1 file (`capabilities.md`) | Low | Low — format change only |
| Skill descriptions | 30+ SKILL.md files | Medium | Medium — descriptions drive primary routing |
| Eval infrastructure | 16 YAML files | Low | Low — already exists |

## Options Evaluated

### Option A: Restore imperative framing in compressed format

**How it works**: Keep the pipe-delimited format (preserving the context savings) but restore the properties that made the old format work:

1. Add imperative instruction text before the table:
   ```markdown
   ## Intent Routing

   **BLOCKING REQUIREMENT**: When a user request matches a trigger phrase below,
   you MUST invoke the corresponding skill via the Skill tool before responding.
   Do NOT perform the task directly — dispatch to the skill.

   | trigger phrases | action |
   |----------------|--------|
   | "brainstorm options", "generate ideas", "explore ideas" | Invoke `/mine.brainstorm` |
   | "design this change", "write a design doc" | Invoke `/mine.design` |
   ```

2. Use a markdown table (minimal overhead) instead of comment-style format
3. Quote trigger phrases to signal pattern-matching
4. Use "Invoke `/mine.X`" rather than just `/mine.X` to make the action explicit
5. Add "BLOCKING REQUIREMENT" language mirroring the Skill tool's own description

**Pros**:
- Directly addresses the root cause (weak framing)
- Maintains most of the context reduction (the CLI tool docs were 18K of the 23K — those stay moved to skills)
- Uses language that mirrors the Skill tool's own "BLOCKING REQUIREMENT" directive, creating reinforcement
- Markdown tables are still compact — maybe 30% larger than comment format but 60% smaller than the old verbose format

**Cons**:
- Adds ~1-2K chars back to capabilities.md (still a large net reduction from the original 23K)
- Still relies on the routing table as a secondary signal

**Effort estimate**: Small — format change to one file

**Dependencies**: None

### Option B: Improve skill descriptions (fix the primary signal)

**How it works**: The `<available_skills>` section in the Skill tool is built from each skill's `description` frontmatter. If those descriptions better match natural user language, Claude will route to skills without needing the routing table at all.

For example, `mine.brainstorm`'s current description is:
> "Open-ended idea generation using four parallel thinkers."

A better description for routing would be:
> "Open-ended idea generation. Use when the user wants to brainstorm options, generate ideas, explore approaches, or asks 'what are our options?'"

This puts the trigger phrases into the primary signal rather than relying on a secondary routing table.

**Pros**:
- Fixes the root cause at the source — the Skill tool's own description is what Claude primarily uses
- Does not depend on the routing table format at all
- Each skill's description is already loaded into context via `<available_skills>`
- The `<available_skills>` section triggers the "BLOCKING REQUIREMENT" behavior

**Cons**:
- Requires updating 30+ skill files
- Description length is constrained by the `SLASH_COMMAND_TOOL_CHAR_BUDGET` (2% of context window, fallback 16K chars) — if descriptions get too verbose, skills may be excluded
- More diffuse change — harder to validate holistically

**Effort estimate**: Medium — one-line change per skill, but 30+ files, and each description needs to be crafted carefully to include trigger phrases without bloating the budget

**Dependencies**: None

### Option C: Both A and B (belt and suspenders)

**How it works**: Restore imperative framing in the routing table (Option A) AND improve skill descriptions (Option B). The routing table becomes a reinforcement layer for the primary `<available_skills>` signal.

**Pros**:
- Maximum routing reliability — two independent signals pointing to the same action
- If one mechanism changes (e.g., Claude Code updates the Skill tool prompt), the other still works
- The routing table serves as documentation for humans too

**Cons**:
- More work upfront
- Risk of the two sources drifting out of sync over time

**Effort estimate**: Medium — combines both changes

**Dependencies**: None

### Option D: Do nothing — accept that routing tables are supplementary

**How it works**: Accept that the routing table was never the primary routing mechanism. Focus eval tests on whether Claude uses the Skill tool at all (based on `<available_skills>`), not on whether the routing table drives decisions. Remove or relax the confusion-pair tests.

**Pros**:
- Preserves the full context savings
- Honestly reflects how Claude Code's Skill tool actually works
- The negative tests (no over-triggering) already pass

**Cons**:
- Does not fix the under-triggering problem — Claude will still do tasks inline
- The whole point of the routing table is to improve routing; accepting failure defeats its purpose

**Effort estimate**: Small — adjust eval expectations

**Dependencies**: None

## Concerns

### Technical risks

- **Skill description budget**: The `SLASH_COMMAND_TOOL_CHAR_BUDGET` caps at 2% of context window (fallback 16K). With 30+ skills, each description averages ~500 chars max. Adding trigger phrases to descriptions may push some skills over budget, causing them to be excluded from `<available_skills>` entirely. This would make routing worse, not better.
- **Eval fidelity**: The promptfoo `claude-agent-sdk` provider runs with `permission_mode: default`, which may block Skill tool calls requiring approval. The eval assertion checks both `toolCalls` and response text, but blocked calls may still look like failures.

### Complexity risks

- Maintaining trigger phrases in two places (routing table + skill descriptions) creates sync burden
- The "BLOCKING REQUIREMENT" language in the Skill tool description may not be reinforced by a rules file — the tool description is authoritative; rules files are contextual

### Maintenance risks

- Any new skill needs its description written to include trigger phrases (Option B)
- The routing table needs to stay in sync with skill descriptions (Option A+B)

## Open Questions

- [ ] What is the current `SLASH_COMMAND_TOOL_CHAR_BUDGET` effective limit for this project? Run `/context` in Claude Code to check for skill budget warnings.
- [ ] Are the eval test failures actually caused by `permission_mode: default` blocking the Skill tool, rather than Claude not attempting to invoke it? The assertion checks response text as a fallback, but it is worth running a test manually to inspect Claude's reasoning.
- [ ] How much of the description field does Claude actually use from `<available_skills>`? Is it the full text, or just the first sentence? This affects how much trigger-phrase content is useful in Option B.

## Recommendation

**Start with Option A (restore imperative framing in compressed format), then iterate toward Option B as a follow-up.**

Rationale:
1. Option A is a single-file change that directly addresses the formatting regression. It can be validated immediately with the existing eval suite.
2. The context cost is minimal — adding ~1-2K chars back still preserves a 70%+ reduction from the original 23K.
3. Option B (improving skill descriptions) is the structurally correct long-term fix, but it is a larger change that should be done incrementally — start with the 5-10 most commonly triggered skills and measure the effect.
4. The "BLOCKING REQUIREMENT" language from the Skill tool description should be echoed in the routing table preamble. This creates a consistent signal that Claude recognizes as authoritative.

Do NOT pursue Option D. The routing table serves a real purpose — it bridges the gap between natural user language and skill names. The old format demonstrably worked better; the goal is to find a compact format that preserves that effectiveness.

### Suggested next steps

1. **Reformat `capabilities.md`** — switch from comment-style to slim markdown table with imperative preamble, quoted trigger phrases, and explicit "Invoke" action language
2. **Run the confusion-pair eval suite** to validate improvement: `ANTHROPIC_API_KEY="$(printenv MY_ANTHROPIC_API_KEY)" node_modules/.bin/promptfoo eval -c evals/compliance/routing/intent-to-skill-confusion.yaml`
3. **Audit the top 10 most-used skill descriptions** for trigger-phrase coverage — ensure descriptions in SKILL.md frontmatter include the natural language phrases users actually say
4. **Check skill budget** — run `/context` to see if any skills are being excluded due to the character budget

## Sources

- [Claude Code Skills Documentation](https://code.claude.com/docs/en/skills) — official docs on skill discovery, invocation, and the `<available_skills>` mechanism
- [Claude Code System Prompts (Piebald-AI)](https://github.com/Piebald-AI/claude-code-system-prompts) — extracted system prompt showing "BLOCKING REQUIREMENT" in Skill tool description
- [Skill Tool Description](https://github.com/Piebald-AI/claude-code-system-prompts/blob/main/system-prompts/tool-description-skill.md) — the exact Skill tool prompt Claude sees
- [Skill Invocation System Prompt](https://github.com/Piebald-AI/claude-code-system-prompts/blob/main/system-prompts/system-prompt-tool-usage-skill-invocation.md) — slash command handling instructions
- [How to Make Claude Code Skills Activate Reliably — Scott Spence](https://scottspence.com/posts/how-to-make-claude-code-skills-activate-reliably) — empirical testing showing 20% vs 84% activation rates
- [Inside Claude Code Skills — Mikhail Shilkov](https://mikhail.io/2025/10/claude-code-skills/) — internal architecture of skill discovery and the meta-tool pattern
- [Claude Agent Skills: A First Principles Deep Dive — Lee Hanchung](https://leehanchung.github.io/blogs/2025/10/26/claude-skills-deep-dive/) — explains "no algorithmic skill selection" and pure LM inference routing
