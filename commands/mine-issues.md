---
description: Deep-dive issues by key, inferring one from the branch name if none are given.
---

# Issues Command

Deep-dive specific issues by key. If no keys are given, infer one from the current branch name, or ask. Works with whatever issue tracker Claude has tools for, signaled by the `$ISSUE_TRACKER` env var.

## Arguments

$ARGUMENTS — zero or more issue keys, in whatever format the configured tracker uses (e.g. `123 456` for a numeric tracker, `PROJ-123 PROJ-456` for a project-prefixed tracker). If none provided, infer a key from the branch name, or ask.

## Phase 1: Tool Detection

Read `$ISSUE_TRACKER`.

- If **unset or empty**: tell the user `$ISSUE_TRACKER is not configured. Set it in your context var file.` and **stop**.
- If set to any value: proceed — use whatever tool matches that tracker.

## Phase 2: Route

- **Arguments provided**: Continue to Phase 3 (Deep Dive).
- **No arguments provided**: Try to infer an issue key from the current branch name before asking.
  1. Run `git branch --show-current`.
  2. Judge whether the branch name unambiguously names an issue, in whatever key format the configured tracker uses. For a numeric tracker like GitHub, recognize the same patterns as `skills/mine-create-pr/worker.md`'s closing-keyword detection: a leading number (`123-fix-thing`), `issue-N`/`issue/N`, or `fix/N-description`, `feat/N-description`, `chore/N-description`, etc. For a project-prefixed tracker like Jira, a leading project-prefixed key (`PROJ-123-fix-thing` → `PROJ-123`). Don't infer from a number that's more plausibly a date, version, or something unrelated (e.g. `2026-08-cleanup`).
  3. **If a key is inferred**: say so (e.g. "Inferred issue #123 from the branch name — deep diving.") and use it as the sole argument, continuing to Phase 3. If the Phase 3 subagent returns `LOOKUP_FAILED` (issue doesn't exist), fall back to step 4 instead of surfacing a raw tool error.
  4. **If no key is inferred, or the inferred key's lookup failed**: ask the user which issue to deep-dive: "No issue key in the branch name — which issue should I look at?" If they give a key, use it as the sole argument and continue to Phase 3.

## Phase 3: Deep Dive (Subagent)

For **each** issue key in the arguments, launch a **Task subagent** (`subagent_type: light-worker`) with this prompt:

> Fetch the full issue for key <KEY> from the project's issue tracker (`$ISSUE_TRACKER`) — title, body, comments, labels/tags, assignees, and milestone/sprint if applicable.
>
> If the lookup fails or reports the issue does not exist, return exactly `LOOKUP_FAILED` and nothing else.
>
> Then scan the codebase for files and areas mentioned in or related to the issue (grep for keywords, check referenced file paths, look at relevant modules).
>
> Return this structured summary and nothing else:
>
> ```
> ## Issue <KEY> — Title
> - **Description**: [condensed from body, 2-3 sentences max]
> - **Key comments**: [relevant discussion points, or "None" if no useful comments]
> - **Affected areas**: [files/modules identified from codebase scan]
> - **Estimated scope**: [small/medium/large with brief reasoning]
> - **Suggested approach**: [1-2 sentences]
> ```

Launch subagents **in parallel** when multiple keys are provided. Display all structured summaries.

## Phase 4: Next Step (Main Context)

Hand the deep-dive context off to the implementation pipeline. Use `AskUserQuestion`:

- **Build it** — Hand the issue to `/mine-build`, which routes by complexity (direct implementation for small changes, the full `define → plan → orchestrate` pipeline for large ones)
- **Research first** — Run `/mine-research` to investigate feasibility before committing to an approach
- **Skip** — Done for now, I'll come back to this later

Use the issue's **Estimated scope** from Phase 3 to recommend: small/medium → "Build it"; large or uncertain approach → mention "Research first" is worth considering. Phrase the recommendation, but let the user choose.

**If the user picks "Build it":**
1. **Branch naming reminder**: Check `git branch --show-current`. If the current branch name does not contain the issue number, remind the user:
   > "When you create your working branch, include the issue number so the PR links back automatically — e.g., `git checkout -b 123-short-description` or `claude --worktree 123-short-description`."
2. Invoke `/mine-build`, passing the issue's structured summary (title, description, estimated scope, affected areas, suggested approach) as the change description.

**If the user picks "Research first":** invoke `/mine-research`, passing the issue context as the proposal to investigate.

**If the user picks "Skip":** stop.
