---
name: mine.ux-review
description: Scan frontend code for UX anti-patterns — layout shifts, missing feedback, broken forms, race conditions, accessibility gaps.
---

## Required Reading

Before scanning, read completely:

1. Read the skill: `~/.claude/skills/mine.ux-antipatterns/SKILL.md`
2. Read the reference: `~/.claude/skills/mine.ux-antipatterns/references/antipatterns.md`

## Screenshots (Live App)

Before scanning code, check whether Playwright MCP is available and a dev server is running:

1. Check for an existing `screenshots/current/` directory — if present and recent, read those screenshots first
2. If Playwright MCP tools are available, try navigating to the running app (common ports: 3000, 5173, 8000, 8080) and screenshot all main pages — save to `screenshots/current/` in the project root
3. Read each screenshot alongside the code — visual review surfaces presentation issues invisible in code alone
4. Correlate code findings with what's visible: "this code produces that visual"

If Playwright MCP is not available and no screenshots exist, proceed with code-only review and note the limitation.

## Scan Target

If the user specified files or paths, scan those. Otherwise, search for UI files in the project (tsx, jsx, vue, svelte, html, jinja, erb) and scan all of them.

## Review Process

1. Check each file against the 13 anti-pattern categories
2. Only flag patterns that cause measurable user harm — not style preferences
3. Check for nearby explanatory elements before reporting (e.g., a disabled button may be explained by wizard context)
4. Read the implementation before flagging — if the code already handles the edge case, don't report it

## Report Format

Group findings by anti-pattern category. For each finding:

```
**[Category]: [Anti-pattern name]**
File: path/to/file.tsx:line
Harm: [what the user experiences]
Fix: [concrete fix]
```

If no anti-patterns are found, say the code is clean. Don't manufacture findings.
