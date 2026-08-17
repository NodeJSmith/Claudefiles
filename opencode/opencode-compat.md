---
tool: opencode
---

# OpenCode Compatibility

This configuration was developed for Claude Code and adapted for OpenCode. Most rules, skills, and agents work as-is. Where a specific instruction references a Claude Code feature that doesn't exist in OpenCode, use the OpenCode equivalent:

- "AskUserQuestion tool" → use OpenCode's interactive prompting
- "Agent tool with subagent_type" → use OpenCode's agent dispatch
- "Skill tool" → use OpenCode's native skill tool; slash-command bridges exist only for selected skills
- "Read/Write/Edit/Grep/Glob tools" → use OpenCode's file tools
- "TaskCreate/TaskUpdate" → use OpenCode's task tracking if available
- "PreToolUse/PostToolUse hooks" → OpenCode plugins (tool.execute.before)
- "settings.json" → opencode.json
- MCP tool names: Claude names MCP tools `mcp__<server>__<tool>` (double underscore); OpenCode builds tool names as `sanitize(client) + "_" + sanitize(name)` (single underscore), so the same tool is named `<server>_<tool>` under OpenCode. For example, `mcp__context7__query-docs` becomes `context7_query-docs`. Apply this transformation whenever a rule or skill names a Claude-style `mcp__` tool.

When an instruction is clearly inapplicable (e.g., references a hook that doesn't exist), skip it silently rather than erroring.
