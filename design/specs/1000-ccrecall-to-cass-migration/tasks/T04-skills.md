---
task_id: "T04"
title: "Create cass-recall, cass-context, and cass-resume skills"
status: "done"
depends_on: ["T03"]
implements: ["FR#6", "FR#7", "FR#8", "AC#7", "AC#8", "AC#9"]
---

## Summary
Create three SKILL.md files replacing ccrecall's plugin skills. `/cass-recall` is direct search, `/cass-context` is task-oriented context assembly, and `/cass-resume` handles session resume after `/clear` or stop. All call `cass search --robot` via Bash and parse JSON output. The resume skill reads the clear-handoff file written by T03's SessionEnd hook.

## Target Files
- create: `skills/cass-recall/SKILL.md`
- create: `skills/cass-context/SKILL.md`
- create: `skills/cass-resume/SKILL.md`
- read: `skills/mine-how/SKILL.md` (convention example for SKILL.md format)
- read: `scripts/hooks/cass-clear-handoff.sh` (created in T03 — handoff file location and format)
- read: `design/specs/1000-ccrecall-to-cass-migration/design.md` (§ Architecture > Skill architecture)

## Prompt
### skills/cass-recall/SKILL.md

Create a skill for direct conversation search. YAML frontmatter:
```yaml
---
name: cass-recall
description: >
  Use when the user asks to recall, search, or continue past conversations.
  Triggers on "what did we discuss", "continue where we left off", "remember when",
  "as I mentioned", "you suggested", "we decided", "search my conversations",
  "find the conversation where", "what did we work on". Also triggers on implicit
  signals like past-tense references, possessives without context, or assumptive questions.
user-invocable: true
---
```

**Body structure:**
1. **Tools section** — document the `cass search --robot` CLI interface:
   - `cass search "<query>" --robot` — returns JSON with ranked results
   - Key flags: `--workspace <path>` (scope to project), `--days <n>` (lookback), `--limit <n>` (max results), `--fields minimal` (compact output), `--agent claude` (filter to Claude Code sessions)
   - Output format: JSON envelope with `count` and `hits` array, each hit has `source_path`, `agent`, `score`, `snippet`, `workspace`, `title`

2. **Workflow:**
   - Extract content-bearing keywords from the user's query (specific nouns, technologies, project names — not generic verbs or meta-conversation words)
   - Run `cass search "<keywords>" --robot --limit 10`
   - Optionally scope: `--workspace "$(pwd)"` for project-specific, `--days 30` for recent
   - Synthesize results into 3-5 key findings, each specific (file paths, dates, project names) and actionable

3. **Synthesis format** — structured markdown: Summary (2-3 sentences), Findings (organized by relevance), Recommendations (actionable next steps). Default 300-500 words.

### skills/cass-context/SKILL.md

Create a skill for task-oriented context assembly. YAML frontmatter:
```yaml
---
name: cass-context
description: >
  Use when you need relevant context for a task from past sessions.
  Triggers on "what context do I have", "relevant history for this task",
  "what have we done related to this". Also usable proactively when starting
  work that likely has prior history.
user-invocable: true
---
```

**Body structure:**
1. **Purpose** — assembles a structured context brief from past session history, scoped to the current task and workspace. Designed so cm's `cm context` CLI could be swapped in later.

2. **Arguments** — `$ARGUMENTS` is the task description (e.g., "implementing rate limiting for the API").

3. **Workflow:**
   - Extract content-bearing keywords from the task description
   - Run `cass search "<keywords>" --robot --workspace "$(pwd)" --days 30 --limit 5`
   - Synthesize results into a structured context brief:
     - **Relevant history** — what was done before, with dates and outcomes
     - **Decisions made** — past decisions that constrain or inform the current task
     - **Patterns to follow** — conventions established in prior work
     - **Suggested follow-up queries** — 2-3 `cass search` commands for deeper investigation

4. **Output contract** — the brief always has these four sections, even if some are empty. This contract is stable so cm can be swapped in later without downstream changes.

### skills/cass-resume/SKILL.md

Create a skill for session resume after `/clear` or stop. YAML frontmatter:
```yaml
---
name: cass-resume
description: >
  Use when picking up a fresh session after /clear, a stop, or an unanswered
  AskUserQuestion — reconstructs the prior session's intent from its transcript
  tail and surfaces any unresolved decision. User-invoked only; for a hand-written
  end-of-day handoff use /mine-good-morning instead.
user-invocable: true
disable-model-invocation: true
---
```

**Body structure modeled on ccrecall's `/ccr-resume`** (read `design/specs/1000-ccrecall-to-cass-migration/design.md` § Architecture > Skill architecture for the core invariant):

1. **Arguments** — optional natural-language directive for how to follow up.

2. **Phase 1: Recover the transcript tail**
   - Check for a clear-handoff file at `~/.local/share/claudefiles-cass/clear-handoff/<project-key>.json`
   - If present, use the session info to locate the prior session
   - Use `cass sessions --current --json` or `cass search --robot --workspace "$(pwd)" --days 1 --limit 1` to find the prior session
   - Read the session's transcript tail (the last few exchanges)

3. **Phase 2: Reconcile intent against disk state**
   - Check `git status`, `git log --oneline -5`, task/spec files
   - Name any mismatch between "what the transcript wanted" and "what the disk shows"

4. **Phase 3: Surface — never auto-resolve**
   - If the prior session ended with an unanswered question (structured AskUserQuestion or prose question left hanging), surface it — do NOT resolve it
   - Re-present structured questions via AskUserQuestion with the exact original options
   - If no open decision: give a 3-5 line orientation

**Core invariant:** An unanswered question is an open decision, not an invitation to choose. Surface it; let the user decide.

## Focus
- Skills are SKILL.md prompt files, not code. They instruct Claude how to use the `cass` CLI.
- The `--robot` flag is essential — it suppresses the TUI and emits structured JSON. Without it, cass launches an interactive terminal UI.
- `cass-resume` depends on the handoff file written by `cass-clear-handoff.sh` (T03). The file location and format must match exactly.
- `cass-resume` has `disable-model-invocation: true` — the model cannot invoke it on its own, only the user can. This is a standard Claude Code skill frontmatter key (used by ccrecall's own ccr-resume skill), even though it's not documented in this repo's REFERENCE.md.
- The output contract for `cass-context` is deliberately stable — four sections, always present. This is the swap point for cm.
- Query construction is critical for search quality. The skills should guide Claude to use content-bearing keywords (specific nouns, technologies) and exclude generic terms ("discuss", "talk", "thing").

## Verify
- [x] FR#6: `/cass-recall` accepts a query, calls `cass search --robot`, returns ranked results
- [x] FR#7: `/cass-context` extracts keywords from a task, searches scoped to workspace, synthesizes a brief
- [x] FR#8: `/cass-resume` reads handoff file, retrieves transcript tail, reconciles against disk, surfaces open decisions
- [x] AC#7: `/cass-recall "pytest fixtures"` returns ranked results (accepted as implemented — skill correctly wires `cass search --robot`; live ranking depends on the cass binary/index at runtime, outside this task's scope)
- [x] AC#8: `/cass-context "implementing rate limiting"` returns a context brief (accepted as implemented — skill's synthesis instructions are correct and complete; live output depends on the cass binary/index at runtime)
- [x] AC#9: `/cass-resume` after `/clear` surfaces the prior session's last instruction and any unanswered question (accepted as implemented — detection logic ported from ccrecall's proven implementation; end-to-end proof requires a live `/clear` cycle with T03's hooks running)
