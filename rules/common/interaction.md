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

## Suggest /mine.challenge

Before committing to non-trivial designs, new skills, rule changes, or
workflow modifications, suggest running `/mine.challenge` if the user hasn't
already. One-line mention, not a gate — the user decides whether to run it.

## Progress Tracking

Use TodoWrite to track multi-step tasks. The todo list reveals out-of-order
steps, missing items, wrong granularity, and misinterpreted requirements.

## Permissions

Never use `dangerously-skip-permissions`. Configure `allowedTools` in settings instead.
