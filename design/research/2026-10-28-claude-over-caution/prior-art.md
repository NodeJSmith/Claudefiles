---
topic: "Excessive caution and defensive over-engineering in recent Claude models"
date: 2026-10-28
status: Draft
---

# Prior Art: Excessive Caution in Recent Claude Models

## The Problem

Recent Claude models treat every possible gap or risk as something to fix, and the fix is usually new machinery: a guard, a fallback, a validation layer, a rule, a hook, a check. Each addition looks reasonable on its own. Together they add diff noise, more rules to maintain, and more review findings, and the user ends up arguing against them most days. The goal is a middle ground: real risks still get handled, imagined ones don't grow infrastructure.

This is a measured, widely reported trait of the Claude 5 generation, not a quirk of one setup. ParanoiaEval (arXiv 2610.08662) found that Opus 5 under Claude Code did unnecessary defensive work in **58.7%** of runs where the repo or the prompt had already said it wasn't needed. That was the highest rate of the 8 configurations tested, even though Opus 5 also had a top task-success rate (95.8%). Sonnet 4.6 came in at 11.2%. Tests caught none of it, because functional correctness hid 92.7% of the violations. On Hacker News, an Opus 5.5 user put it as "no sense of 'good enough'... resolve edge-cases on edge-cases", and another as "they always want to fix it by adding more things".

## How We Do It Today

Some instructions push against over-building:

- `rules/common/laziness-protocol.md` (prefer deletion, smallest diff)
- `rules/common/debugging-discipline.md` ("belt-and-suspenders is a hypothesis, not a fix")
- `rules/common/project-context.md` (calibrate advice to the audience)
- the `llm-checker` "Defensive Everything" pattern
- the memories `feedback_trust_over_gates` and `feedback_less_prescriptive_instructions`

Other instructions push toward more caution, and several of them describe the exact symptom:

- `rules/common/verification.md` "Name Observability Gaps" tells the agent to raise every gap as a finding.
- `rules/common/logging.md` "Mandatory coverage" / "No Dark Operations" asks "how will I know if this fails?" for every operation.
- `rules/common/encode-lessons-in-structure.md` "Pick the Strongest Rung" sends every recurring lesson toward a runtime check, lint, or hook.
- `rules/common/invariants.md` holds about 30 Must/Should items and grows by one entry per recurring review catch.
- `rules/common/git-workflow.md` loops reviewers until no CRITICAL/HIGH remain, and its challenge step can't be declined. `agents/nitpicker.md` says "do not decide something is not worth mentioning". `agents/testing-reality-checker.md` defaults to NEEDS WORK.
- The memory `feedback_quality_gate_sensitivity` ("prefer over-sensitive defaults") contradicts `feedback_trust_over_gates`.

Nothing applies a cost test to the agent's own proposal to add a guard.

## Patterns Found

### Pattern 1: Write down the bounds and the risks you've accepted

**Used by**: ParanoiaEval (measured), Andreas Rau's write-up of it, and an HN commenter ("an underspecified interface... the agent has to assume it should guarantee thread safety in all contexts").
**How it works**: ParanoiaEval runs each task twice: once with a single fact saying the extra work isn't needed, and once without it. How much the agent backs off depends a lot on the kind of fact:

| Kind of fact | Example | Excess work without → with the fact | How well it worked |
|---|---|---|---|
| **Acceptance** | "we accept this risk" | 54.0% → 19.3% | best (up to 93.9% in the best configuration) |
| **Mitigation** | a stated verification bound, e.g. "run only the affected package's tests" | 78.5% → 26.4% | strong. Removing the bound raised excess work in all 8 configurations, by up to 68.7 points. |
| **Avoidance** | the repo state already removes the risk | — | weak (21%). The agent keeps treating the risk anyway. |
| **Transfer** | "CI / a reviewer owns this check" | — | ~8%, not significant. The agent runs its own pass regardless. |

The researchers' explanation: mitigation has no natural stopping point unless someone writes one down. Excess work cost reviewers: satisfaction dropped from 3.85/5 to 2.58/5, and runs were accepted as-is 38% of the time instead of 78%.
**Strengths**: The only controlled measurement found. It says which kind of instruction actually reduces excess work: specific accepted-risk statements and explicit stopping bounds. Adjectives and appeals to trust do much less.
**Weaknesses**: Measured on Opus 5, not 5.5, with only 8 configurations. "CI owns this" barely helps, so telling the agent who owns a check isn't enough.
**Example**: https://arxiv.org/abs/2610.08662 · https://andreasrau.tech/writing/agentic-coding-paper-2026-10-07/

### Pattern 2: Remove verification and thoroughness instructions; prune rules

**Used by**: Anthropic (the Opus 5 prompting guide, the July 2026 "new rules of context engineering" post, and the Claude Code best-practices doc), HumanLayer, the MakeUseOf author, and fcakyon ("additions require deletions").
**How it works**: The Opus 5 guide says it plainly: "Claude Opus 5 verifies its own work without being told to. If your prompt contains explicit verification instructions... remove them: instructions like these cause over-verification... removing them reduces wasted tokens with no loss in quality. The same applies to legacy harness scaffolding that adds separate verification steps." It also says not to "use subagents to verify or double-check your own work".

Anthropic's July post goes further: they "removed over 80% of Claude Code's system prompt for models like Claude Opus 5... with no measurable loss". It retires "give Claude rules" in favor of "let Claude use judgment". It also says conflicting messages across layers (system prompt, skills, user request) make the model "think more carefully about these overlapping and conflicting messages", which costs something even when it gets the answer right. The example rewrite turns 39 words of prohibition into 15 words of direction ("Write code that reads like the surrounding code"). That line is already in this session's system prompt.

The older best-practices doc adds that CRITICAL/MUST wording "mostly makes Claude over-apply the rule", that "be thorough / don't be lazy" lines cause over-work, and that hooks which only encode preferences should be deleted.
**Strengths**: The vendor's current guidance for this exact model generation, with an 80%-cut data point behind it. It treats the cause, not the symptom.
**Weaknesses**: "No measurable loss on coding evals" isn't the same test the guardrails were written for. A regression from pruning may show up later.
**Example**: https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/prompting-claude-opus-5 · https://claude.com/blog/the-new-rules-of-context-engineering-for-claude-5-generation-models

### Pattern 3: A scope statement and a decision ladder

**Used by**: Anthropic (the Opus 5 scope block), SuperClaude (`RULES.md` "YAGNI Enforcement"), Samuel Lawrentz (measured), fcakyon ("Delete > Replace > Add"), and Michel Faure.
**How it works**: Anthropic's suggested block for Opus 5 scope creep: "Deliver what was asked, at the scope intended. Make routine judgment calls yourself... If the request seems mistaken or a better approach exists, say so in a sentence and continue with the task as asked rather than quietly narrowing, widening, or transforming it." Lawrentz measured a single "Do not overengineer." line roughly halving diffs on 2 of 3 tasks, and a step-by-step ladder doing better (needed at all? → already exists? → stdlib? → one line? → minimal code). The positive framing ("abstract on the second occurrence") avoids priming the unwanted behavior.
**Strengths**: Cheap, and the ladder has some measured effect. "Say so in a sentence and continue" is a direct model for flagging a risk without building something for it.
**Weaknesses**: Lawrentz tested only 3 tasks. Applied where robustness really matters, a ladder can lead to under-building.
**Example**: https://samuellawrentz.com/blog/do-not-overengineer/

### Pattern 4: Report everything, filter in a separate pass

**Used by**: Anthropic (the Opus 5 guide and the code-review plugin), obra/superpowers, and a note.com author's "OVER" axis.
**How it works**: Anthropic warns that telling an Opus 5 reviewer to "only report high-severity issues" or "be conservative" makes it "follow that instruction literally and report less". Their advice is to have the reviewer report everything and filter in a separate pass. Their code-review plugin does exactly that: a separate agent scores each finding from 0 to 100 against an explicit false-positive list (pre-existing issues, "pedantic nitpicks a senior engineer wouldn't call out", anything a linter would catch). superpowers anchors review to the brief, treats "Extra: over-engineering" as a finding category, and says "Not everything is Critical".
**Strengths**: It moves the calibration out of the reviewer, where it suppresses real findings, and into the filter, where it belongs.
**Weaknesses**: An extra agent pass costs tokens.
**Example**: https://github.com/anthropics/claude-plugins-official/blob/main/plugins/code-review/commands/code-review.md

### Pattern 5: Fail loudly instead of defending

**Used by**: the defuse gist and fcakyon ("guard nothing, relocate the trigger"). The Claude Code base prompt includes a mild version ("only validate at system boundaries").
**How it works**: Assertions and strict validation at the boundary replace fallbacks and try/except, and unreachable branches raise an error. The fix goes into the code path that owns the behavior, not into a guard in front of it.
**Strengths**: Keeps correctness without adding machinery.
**Weaknesses**: Absolute wording gets ignored (anthropics/claude-code#21027), and it's the wrong default for unattended services.
**Example**: https://gist.github.com/defuse/da01a26ffd94018043799bcd9400ecc1

### Pattern 6: Accept it, or switch models

**Used by**: HN commenters. Several said they prune by hand ("it's possible, sort of, to drive it to fix by removing things instead but it's a battle"), and some moved small personal work to other models (DeepSeek, GLM) that "do what I ask for".
**How it works**: Tolerate the extra work, or route work around it.
**Strengths**: No instructions to maintain.
**Weaknesses**: Costs review attention every day, which is the friction you want to reduce.

## Anti-Patterns

- **Explicit verification steps and "verify with a subagent"**: on Opus 5 these cause over-verification (Anthropic).
- **"Be conservative" / "only high severity" in reviewer prompts**: the model follows it literally and reports less, so filter separately instead (Anthropic).
- **Shouting** (CRITICAL/ALWAYS/MANDATORY): over-applied, and still ignored in some cases (#21027).
- **Rules that contradict each other across layers**: they cost reasoning even when Claude resolves them (Anthropic's July post).
- **One rule per incident with nothing removed**: fcakyon's fix is "to add a rule, remove or merge one".
- **Contaminated baselines**: global hooks and rules leak into A/B runs, so use `--setting-sources project` or an equivalent clean config.

## Relevance to Us

**1. Several of our rules match what Anthropic says to remove for this model generation.** The always-loaded set includes:
- explicit verification rules: `verification.md`, "Evidence Before Claims", and the review trio before every logic commit;
- separate verification stages: mandatory challenge, a reviewer loop until no HIGH findings remain, and testing-reality-checker defaulting to NEEDS WORK;
- risk-seeking "be thorough" lines: "Name Observability Gaps", logging's "how will I know if this fails?", and nitpicker's "do not decide something is not worth mentioning".

The Opus 5 guide says a model that already verifies on its own over-verifies when given these. "Pick the Strongest Rung" turns every lesson into machinery by default, which is the symptom written down as policy. `invariants.md` adds one rule per catch and never removes any.

**2. The anti-caution side gives the agent adjectives where it needs specific facts.** The laziness protocol and `project-context.md` describe a stance ("personal tool, skip enterprise patterns"). ParanoiaEval suggests that specific accepted-risk statements and stated stopping bounds work much better, for example "we accept that X can race; don't guard it" or "verification for a skill edit = lint-agent-files + one read-through, nothing more". The `project-context.md` frontmatter is the right place for that shape, but it only holds three coarse labels right now.

**3. Some of our tension is the "conflicting layers" cost Anthropic describes.** Two memories contradict each other (over-sensitive gates vs. trust over gates), and laziness and encode-lessons pull in opposite directions. Anthropic says the model has to think through those conflicts on every request.

**4. On reviewers, Anthropic's advice cuts the other way from simply softening them.** Telling reviewers to be conservative makes them miss real bugs. The better shape is to let them report everything and add a filtering step that knows about scope and project context. In our loop, unfiltered reviewer output decides whether the loop continues, so findings that are only true in theory keep it running.

None of the listed peers has anything aimed specifically at this. SuperClaude's `RULES.md` has a "YAGNI Enforcement" scope rule, superpowers' reviewer has an "Extra" category, and mattpocock/skills, ouroboros and citypaul had nothing relevant.

## Recommendation

Subtract first, then add specific facts rather than more stance. In order:

1. **Remove or narrow the instructions that call for verification and thoroughness.** Anthropic's Opus 5 guidance says to do this outright.
   - Narrow "Name Observability Gaps" and logging's mandatory coverage to unattended processes and external I/O.
   - Reverse "Pick the Strongest Rung" so a written instruction is the default and machinery has to justify itself.
   - Make the review trio and challenge proportional rather than mandatory, or check whether the existing skip criteria already do this in practice.
   - Delete the over-sensitive-gates memory.
2. **Write down bounds and accepted risks (ParanoiaEval's strongest lever).**
   - Add a short "accepted risks" list and "verification bounds" to `project-context.md` or the project CLAUDE.md, for example: "single user; races between concurrent sessions are accepted"; "a skill edit is verified by lint plus a read-through".
   - Pair it with one sentence in `laziness-protocol.md`: before adding a guard, fallback, check or rule, name the concrete failure it prevents. If no such failure can be named, or the risk is listed as accepted, mention it in one sentence and move on.
3. **Restructure the reviewer gate as report, then filter.** Leave the reviewers unconstrained, and put a filtering step before the loop's stopping condition that drops findings outside the requested scope, hypothetical risks with no named trigger, and risks on the accepted list. Add "Extra / over-built" as a finding category so over-caution itself gets flagged.
4. **Make invariant growth one-in, one-out.**

Before calling it fixed, run `/doctor prompt-audit` against the installed rules. If you want to measure it, rerun a few real tasks before and after on a clean config (`--setting-sources project`).

**Coverage:** strong where it matters most. There is a controlled benchmark that names Opus 5, Anthropic's guidance for this model generation, and a recent HN thread about Opus 5.5. Reddit came up empty: the keyword search returned only unrelated posts, and Exa searches restricted to reddit.com returned nothing. ParanoiaEval measured Opus 5, not 5.5, and Anthropic's Opus 5.5 guide says Opus 5 patterns "remain a reasonable starting point".

## Sources

URLs were not live-verified.

### Research
- https://arxiv.org/abs/2610.08662 — ParanoiaEval: Benchmarking Unnecessary Defensive Work in Agentic Coding
- https://andreasrau.tech/writing/agentic-coding-paper-2026-10-07/ — a practitioner's summary of ParanoiaEval with setup changes

### Documentation & standards
- https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/prompting-claude-opus-5 — "Task scope and over-verification", the reviewer conservatism warning, subagent verification
- https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/prompting-claude-opus-5-5 — Opus 5 patterns still apply
- https://claude.com/blog/the-new-rules-of-context-engineering-for-claude-5-generation-models — the 80% system-prompt cut, rules → judgment, the cost of conflicting layers
- https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/claude-prompting-best-practices — the "Overeagerness" block, softening aggressive language
- https://code.claude.com/docs/en/best-practices — emphasis causes over-application, delete preference hooks, `/doctor prompt-audit`

### Reference implementations
- https://github.com/anthropics/claude-plugins-official/blob/main/plugins/code-review/commands/code-review.md — reviewers scored by a separate agent, with a false-positive list
- https://github.com/obra/superpowers/blob/main/skills/subagent-driven-development/task-reviewer-prompt.md — scope-anchored reviewer with an "Extra" category
- https://github.com/SuperClaude-Org/SuperClaude_Framework/blob/master/src/superclaude/core/RULES.md — "YAGNI Enforcement" scope rule
- https://github.com/fcakyon/claude-codex-settings/blob/main/.claude/CLAUDE.md — "guard nothing", "additions require deletions"
- https://gist.github.com/defuse/da01a26ffd94018043799bcd9400ecc1 — fail-loud CLAUDE.md
- https://github.com/Piebald-AI/claude-code-system-prompts/blob/HEAD/system-prompts/system-prompt-doing-tasks-no-unnecessary-error-handling.md — base-prompt boundary-validation fragment
- https://github.com/anthropics/claude-code/issues/21027 — emphatic anti-fallback rules ignored

### Community & writeups
- https://news.ycombinator.com/item?id=50119223 — Opus 5.5 "no sense of good enough" thread
- https://news.ycombinator.com/item?id=45975298 — Sonnet 4.5 still adds null checks after being told not to
- https://medium.com/ai-all-in/everyone-benchmarked-opus-5-nobody-read-the-deletion-list-that-shipped-with-it-daa43800d4eb — Opus 5 migration as a list of things to delete
- https://samuellawrentz.com/blog/do-not-overengineer/ — measured one line vs. a ladder
- https://dev.to/michelfaure/one-line-in-claudemd-that-breaks-claudes-over-engineering-reflex-3fnk — positive-default phrasing
- https://www.humanlayer.dev/blog/writing-a-good-claude-md — instruction budget
- https://www.makeuseof.com/i-cut-my-claudemd-in-half-and-claude-code-stopped-fighting-itself/ — pruning CLAUDE.md
