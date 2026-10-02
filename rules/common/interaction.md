---
tool: claude  # harness-only: plan mode, AskUserQuestion, and the dispatch model are Claude-Code-specific
---

# Interaction Style

## Clarify, Don't Plan

Do NOT use the `EnterPlanMode` tool. It is completely off-limits unless the
user explicitly requests it (e.g., "enter plan mode", or the Shift+Tab
keyboard shortcut in Claude Code CLI).

When a task is ambiguous or has multiple valid approaches, use
`AskUserQuestion` to clarify the specific points where the correct choice is
unclear. Ask focused, minimal questions — only what's needed to proceed
confidently. Then start implementing immediately after getting answers.

When a task needs structured planning, launch the Agent tool with
`subagent_type: "planner"` instead of entering plan mode. Present the
planner's output to the user via `AskUserQuestion` for approval before
executing.

## Progress Tracking

Use TaskCreate to track multi-step tasks. The todo list reveals out-of-order
steps, missing items, wrong granularity, and misinterpreted requirements.

## AskUserQuestion Blocks in Skills

When a skill asks the user a question, whether as an `AskUserQuestion:` YAML
block or as a prose menu of options, call the `AskUserQuestion` tool.

1. **Call the tool.** Don't render the options as a bulleted or numbered list
   in your reply; the user must see the interactive prompt.
2. **Labels are keys; the rest is yours.** Keep option labels as the skill
   wrote them: "On 'X'" sections, `cfl` recordings, and verdict mappings match
   on them. The " (Recommended)" suffix is not part of the key; add or move it
   freely, and strip it from `cfl --answer`/`--recommended` values. Within
   that, adapt to what you found. Ask what you know now that the skill author
   couldn't (the findings, their severity, open questions, repo conventions),
   and let that decide which options apply and which you recommend; say in the
   recommended option's description what decided it. The failure to avoid is a
   menu offering an option the findings make meaningless, or a pinned
   "(Recommended)" the situation contradicts. Max 4 options per question.
   Skip or collapse a question only when the user's request or your findings
   already settle the answer (if one option is left, say so and act). Never
   skip a confirmation for an irreversible action or a gate a rule marks
   mandatory.
3. **Respect `multiSelect`.** If the skill says `multiSelect: true`, pass it
   through. Do not downgrade to single-select.
4. **Use previews for concrete format comparisons.** The `preview` field on options renders multi-line markdown in a side-by-side layout next to the option list. Use previews for format comparisons (code snippets, ASCII mockups, diagram variations, manifest samples) where the user needs to *see* the option before choosing. Previews only work on single-select questions (`multiSelect: false`). Do not use previews for simple preference questions — labels and descriptions suffice there.

## Intellectual Honesty

AI assistants default to deference bias: softening corrections, hedging disagreements, and validating weak reasoning to avoid friction. This undermines collaborative work that depends on surfacing flaws early. Intellectual honesty is the conversational default, not something that requires invoking `/mine-challenge`.

Challenge assumptions, correct plainly when arguments are weak, prioritize accuracy over agreement.

When the user's reasoning has a gap, name it directly. When a proposed approach has a better alternative, say so with specifics. If you're uncertain, say that instead of hedging behind qualifiers that sound confident.

Do not soften corrections to preserve comfort. A clear "that won't work because X" is more respectful than a padded "that's a great idea, though one small consideration might be..."

## Context Usage at Decision Gates

At major decision gates, run `context-pct` and prepend `[Context: N%]` to the
AskUserQuestion `question` text. This lets the user decide whether to continue
or clear context and resume.

**Major gates** (always show context):
- Shipping/completion gates (mine-ship, mine-orchestrate post-execution)
- Known issues walkthrough and backlog gates
- Task failure/blocked decisions (try again / stop)
- Review and challenge finding walkthroughs
- Clean code gate results
- Comb pass/fix/escalate decisions

**Skip** for early-workflow gates (confirm feature, dev server check, interview
questions, complexity routing) where context is nearly always low and the
information adds noise.

If `context-pct` returns empty or fails to run, omit the prefix silently.

## Permissions

Never use `dangerously-skip-permissions`. Configure `allowedTools` in settings instead.
