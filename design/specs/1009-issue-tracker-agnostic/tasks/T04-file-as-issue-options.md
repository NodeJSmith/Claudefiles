---
task_id: "T04"
title: "generalize 'file as issue' options across six skills"
status: "done"
depends_on: []
implements: ["FR#2", "AC#4"]
---

## Target Files

- modify: `skills/mine-challenge/findings-protocol.md` — lines 188, 193, 209
- modify: `skills/mine-orchestrate/post-execution-pipeline.md` — lines 404-405, 416
- modify: `skills/mine-brainstorm/SKILL.md` — line 247
- modify: `skills/mine-decompose/SKILL.md` — lines 130, 137
- modify: `skills/mine-audit/SKILL.md` — lines 152, 168
- modify: `skills/mine-tool-gaps/SKILL.md` — lines 227, 252

## Prompt

Six skills have "file as issue" functionality with GitHub-specific labels and commands. Make each platform-neutral.

### Pattern to apply everywhere

**AskUserQuestion option labels:**
- "Create a GitHub issue" → "Create an issue"
- "File as GitHub issue" → "File as issue"
- "Create GitHub issues" → "Create issues"

**Option descriptions:**
- "Create a GitHub issue for this finding" → "Create an issue for this finding"
- "Create a tracked issue via gh-issue and mark this entry filed" → "Create a tracked issue and mark this entry filed"
- "Create GitHub issues for the decomposition opportunities" → "Create issues for the decomposition opportunities"

**Resolution instructions:**
- "create issue via `gh-issue create`" → "create an issue in the project's issue tracker"
- "run `gh-issue create`" → "create an issue"
- "create one issue per idea using `gh-issue create`" → "create one issue per idea in the project's issue tracker"
- "Draft and file immediately using `gh-issue create`" → "Draft and file the issue immediately"

### Specific files

**findings-protocol.md:** Three locations — two AskUserQuestion blocks (user-directed and TENSION findings) have a "File as issue" option, and one resolution instruction references `gh-issue create`. Update all three.

**post-execution-pipeline.md:** The option label "File as GitHub issue" and its description reference `gh-issue`. The resolution at line 416 says "run `gh-issue create` (see `...git-workflow.md` — Issue Creation Conventions)". Change to "create an issue (see `...git-workflow.md` — Issue Creation Conventions)". The reference to the conventions section stays — it's still the right guidance, just no longer GitHub-specific after T03.

**brainstorm/SKILL.md:** Line 247 says "create one issue per idea using `gh-issue create`."

**decompose/SKILL.md:** Option label at line 130 says "Create GitHub issues for the decomposition opportunities". Resolution at line 137 says "create one issue per HIGH/MEDIUM opportunity via `gh-issue create`."

**audit/SKILL.md:** Option B label at line 152 says "track in GitHub for future work". Resolution at line 168 says "create a GitHub issue via `gh-issue create`."

**tool-gaps/SKILL.md:** Line 227 says "Draft and file immediately using `gh-issue create`." Line 252 has the `gh-issue create` command in a code block.

For tool-gaps, the code block at line 252 should be removed or replaced with intent language — don't show a specific CLI command, just say "create the issue with the drafted title and body."

## Verify

- [ ] FR#2: `grep -rn 'gh-issue\|GitHub issue' skills/mine-challenge/findings-protocol.md skills/mine-orchestrate/post-execution-pipeline.md skills/mine-brainstorm/SKILL.md skills/mine-decompose/SKILL.md skills/mine-audit/SKILL.md skills/mine-tool-gaps/SKILL.md` returns no matches
- [ ] AC#4: Each file uses intent language ("create an issue") instead of tool-specific commands
