---
task_id: "T02"
title: "consolidate capabilities-core.md routing table and tool notes"
status: "done"
depends_on: ["T01"]
implements: ["FR#6", "AC#3"]
---

## Target Files

- modify: `rules/common/capabilities-core.md`

## Prompt

Restructure the CLI Tools section of `rules/common/capabilities-core.md`.

**Current state:** Lines 76-79 route generic issue/PR trigger phrases ("view issue", "create issue", "list PR threads") to GitHub-specific tools (`gh-issue`, `gh-pr-threads`, etc.). Lines 96-105 have separate ADO-specific rows that are only reachable via ADO-prefixed phrases ("cancel ADO builds", "create ADO PR"). This means a user saying "create issue" always routes to GitHub.

**Target state:** Merge the issue and PR rows into unified entries. The trigger phrases should be platform-neutral. Don't prescribe which tool to run — Claude will use `gh-issue`, `ado-api work-item`, or whatever is appropriate based on the project's platform.

Specifically:
1. The rows for "view issue", "create issue", "list issues" (currently → `gh-issue`) and "create ADO work item" (currently → `ado-api work-item`) should become one row with platform-neutral phrases. Don't name a specific tool — just describe the intent.
2. The rows for "list PR threads" / "reply to PR comment" / "resolve PR thread" (currently → `gh-pr-*`) and "list ADO PR threads" / "reply to ADO PR comment" (currently → `ado-api pr threads`) should merge similarly.
3. ADO-specific CI/CD rows STAY as-is — `ado-api builds`, `ado-api logs`, `ado-api builds approve`, `ado-api builds retry-stage`, `ado-api builds missed-prod`, `ado-api builds steps`, `ado-api pipeline`. These have no GitHub CLI equivalent. Keep the `git-platform` row too.
4. The "GitHub tool notes" section (lines 107-113) documents tool-specific behavior (bot-token auth, thread workflow, gh-pr-threads JSON shape). This is useful documentation for when Claude IS using those tools. Keep it but rename the header to make clear it's tool-specific reference, not a workflow instruction. The content stays unchanged.

The result: generic intent phrases route to the right tool automatically; ADO-only CI/CD operations keep their explicit rows; tool-specific reference docs stay as reference.

## Verify

- [ ] FR#6: No duplicate trigger phrases appear across GitHub-specific and ADO-specific rows
- [ ] AC#3: The routing table rows (the `| User says... | Run |` tables) contain no `gh-issue`, `gh-pr-threads`, `gh-pr-reply`, or `gh-pr-resolve-thread` tool names. These names may still appear in the tool-reference documentation section below the tables.
