# Design: Caliper v2 Workflow Improvements

**Date:** 2026-03-16
**Status:** implemented

## Problem

The caliper v2 workflow has four friction points that reduce quality, waste cycles, or break flow:

1. **No per-WP code review.** `mine.orchestrate` runs executor → spec reviewer → quality reviewer per WP, but never runs the standard `code-reviewer` or `integration-reviewer` agents. Issues accumulate across WPs and are only caught at ship time — when they're harder to fix.

2. **Slash command printing.** Skills like `mine.design`, `mine.draft-plan`, `mine.plan-review`, and `mine.implementation-review` tell the user "Run `/mine.X <path>`" instead of invoking the next step directly. The human has to copy-paste commands, breaking flow.

3. **No local test/lint gate.** The workflow is push-first: code review happens before commit, but tests and linters never run locally. CI failures lead to reactive fix-and-push cycles with noisy commit histories.

4. **Slow to search the web.** When stuck on unfamiliar APIs or recurring errors, Claude retries the same approaches instead of searching for the answer.

## Non-Goals

- Changing the executor, spec reviewer, or overall orchestrate flow beyond swapping quality reviewer for standard agents
- Adding new skills or commands (a new rule file in `rules/common/` is fine — it's auto-loaded, not a skill or command)
- Changing how `mine.build` chains skills (it already auto-continues; the issue is the individual skills' handoff text)
- Modifying CI pipeline configuration or adding CI-specific tooling

## Architecture

### Change 1: Replace quality reviewer with standard code-reviewer + integration-reviewer

**In `skills/mine.orchestrate/SKILL.md`:**

- Remove Step 6 (quality reviewer subagent) entirely
- Add Step 6: **Code reviewer loop** — launch `code-reviewer` subagent on files changed by the executor. Loop until no CRITICAL/HIGH issues remain. Auto-fix unambiguous issues between iterations.
- Add Step 7: **Integration reviewer** — launch `integration-reviewer` subagent once on the same changed files.
- Renumber old Step 7 (present results and gate) → Step 8, old Step 8 (update WP lane) → Step 9
- Update Step 8's verdict table to include code-reviewer and integration-reviewer results alongside spec reviewer
- Keep Step 4 (spec reviewer) unchanged — it checks WP-specific completion criteria that the standard agents don't cover

**Gate behavior update:** If code-reviewer finds CRITICAL/HIGH issues that can't be auto-fixed, the WP verdict becomes FAIL regardless of spec reviewer result.

**Temp file cleanup:** Remove the quality reviewer temp file reference from Step 2. Add code-reviewer and integration-reviewer output paths instead.

### Change 2: Replace slash command printing with prompted invocation

**Pattern:** Replace every "Tell the user: Run `/mine.X`" with an AskUserQuestion gate that, on approval, invokes the skill directly. Add an autonomous mode escape hatch.

**Autonomous mode detection:** At the top of each affected skill, check if the current execution context is being driven by `mine.build` (Path B or C), which already auto-continues between steps. If so, skip the gate and invoke the next skill immediately. Otherwise, present the AskUserQuestion.

Implementation: Add this instruction at the top of the handoff sections:

> If this skill was invoked inline by `mine.build` (the user chose "Full caliper workflow" or "Accelerated"), skip the gate below and invoke the next skill directly — `mine.build` handles the flow. Otherwise, present the gate.

**Specific changes:**

1. **`mine.design` Phase 5 "Approve":**
   - Remove: `Tell the user: > Design approved. Run /mine.draft-plan <feature_dir> to generate work packages.`
   - Add: AskUserQuestion "Design approved. Proceed to generate work packages?" → on Yes, invoke `/mine.draft-plan <feature_dir>` directly

2. **`mine.draft-plan` Phase 5 "Yes":**
   - Remove: `tell the user to run /mine.plan-review <feature_dir>/design.md`
   - Add: Invoke `/mine.plan-review <feature_dir>` directly (the option label already says "show me the command" — change to "Yes — run plan review")

3. **`mine.plan-review` Phase 4 "Approve as-is" and "Approve with suggestions":**
   - Remove: `Tell the user: > Design approved. Run /mine.orchestrate <feature_dir> to begin implementation.`
   - Add: AskUserQuestion "Plan approved. Begin implementation?" → on Yes, invoke `/mine.orchestrate <feature_dir>` directly

4. **`mine.plan-review` Phase 4 "Revise the plan":**
   - Remove: `Tell the user: > Run /mine.draft-plan <feature_dir> and paste the following reviewer notes`
   - Add: Invoke `/mine.draft-plan <feature_dir>` directly, passing the reviewer notes as context

5. **`mine.implementation-review` Phase 4 "Request fixes":**
   - Remove: `Tell the user: > Address these issues and re-run /mine.orchestrate... then /mine.implementation-review`
   - Add: AskUserQuestion "Blocking issues found. Fix and re-run execution?" → on Yes, invoke `/mine.orchestrate <feature_dir>` directly (with a note that implementation-review should follow)

### Change 3: Local test/lint verification before commit

**Two layers: a rule + concrete skill steps.**

**New section in `rules/common/git-workflow.md` — "Local Verification Before Commit":**

Add a rule after the "Mandatory Code Review Before Commit" section:

> After code review passes and before staging files, run the project's test suite and linter locally. Follow the test execution discovery order from `rules/common/testing.md` to determine the correct commands. Fix any failures before proceeding to commit. Do not push code that fails local tests or linting.
>
> **When to skip:** Documentation-only changes (pure markdown, no code). Changes where the project has no test suite or linter configured (note this in the commit message).
>
> **Retry limit:** If local tests fail 3 times after fixes, stop and present the failures to the user rather than continuing to iterate.

**New step in `skills/mine.ship/SKILL.md` and `skills/mine.commit-push/SKILL.md`:**

Add a step between the code-review loop (step 4) / integration review (step 5) and staging (step 6):

> **LOCAL VERIFICATION (skip for documentation-only changes):**
> 1. Determine the project's test command using the test execution discovery order from `rules/common/testing.md`
> 2. Run the test suite locally. If tests fail, fix the issues and re-run (max 3 iterations)
> 3. Run the project's linter if configured (e.g., `ruff check` for Python). Fix any issues.
> 4. Only proceed to staging once both pass.

### Change 4: Web search when stuck

**New file: `rules/common/web-search.md`**

Add a rule that triggers web search proactively:

> **Search before retrying.** When the same error occurs 2+ times, or when working with an unfamiliar API or library, search the web (WebSearch) or fetch documentation (Context7's `resolve-library-id` + `query-docs`) before attempting another fix. Prefer searching over guessing.
>
> **Signals to search:**
> - Same error message appears after 2 fix attempts
> - Working with an API/library you haven't used in this session
> - Error message contains a version number or deprecation notice
> - Stack trace points to third-party library internals
>
> **Search strategy:**
> 1. For library-specific questions: use Context7 first (resolve library ID, then query docs)
> 2. For error messages: WebSearch with the exact error message + library name
> 3. For API usage: Context7 for official docs, WebSearch for community solutions
>
> **Do not** search for things you can determine from the codebase (function signatures, local config, existing patterns).

## Alternatives Considered

### Keep quality reviewer alongside standard agents (Change 1)
Running all three (quality reviewer + code-reviewer + integration-reviewer) per WP would be more thorough but adds ~2 minutes per WP. The quality reviewer's checks overlap significantly with code-reviewer (style, complexity, naming). Rejected in favor of replacing to avoid redundancy.

### Auto-continue without gating (Change 2)
Could have removed all gates and made every transition automatic. Rejected because the user wants control — gates ensure the human can review and course-correct between phases. The autonomous mode flag preserves the option for mine.build's chained execution.

### Rule only for local testing (Change 3)
Could rely on the rule in git-workflow.md without adding explicit steps to ship/commit-push. Rejected because rules are advisory — explicit steps in the skill files make the behavior mandatory and visible.

## Open Questions

None — all decisions resolved during architecture discussion.

## Impact

**Files modified:**
- `skills/mine.orchestrate/SKILL.md` — remove quality reviewer, add code-reviewer + integration-reviewer steps, renumber
- `skills/mine.design/SKILL.md` — Phase 5 handoff change
- `skills/mine.draft-plan/SKILL.md` — Phase 5 handoff change
- `skills/mine.plan-review/SKILL.md` — Phase 4 handoff changes (3 options)
- `skills/mine.implementation-review/SKILL.md` — Phase 4 handoff change
- `skills/mine.ship/SKILL.md` — add local verification step
- `skills/mine.commit-push/SKILL.md` — add local verification step
- `rules/common/git-workflow.md` — add local verification rule section

**Files created:**
- `rules/common/web-search.md` — new rule file

**Blast radius:** Low — all changes are to prompt/config files, not application code. Each change is independent and can be verified by reading the modified file.

**Dependencies:** The orchestrate change (1) references the `code-reviewer` and `integration-reviewer` agent definitions in `agents/`. These already exist and don't need modification.
