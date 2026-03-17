# Interaction Style

## Clarify, Don't Plan

Do NOT use the `EnterPlanMode` tool. It is completely off-limits unless the
user explicitly requests it (e.g., "enter plan mode", Shift+Tab toggle).

When a task is ambiguous or has multiple valid approaches, use
`AskUserQuestion` to clarify the specific points where the correct choice is
unclear. Ask focused, minimal questions — only what's needed to proceed
confidently. Then start implementing immediately after getting answers.

When a task needs structured planning, launch the `planner` subagent instead
of entering plan mode. Present the planner's output to the user via
`AskUserQuestion` for approval before executing.
