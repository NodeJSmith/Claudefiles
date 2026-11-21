---
name: mine-create-issue
description: "Use when the user says: 'create an issue', 'file an issue', 'open an issue', 'write an issue', 'new issue for this'. Codebase-aware issue creation — investigates the code to produce well-structured issues with acceptance criteria, affected areas, and enough detail for automated triage."
user-invocable: true
---

# Create Issue

File an issue that someone (or an automated triager) can pick up without asking questions: the codebase is investigated first, so the issue names the real files, patterns, and constraints. A subagent does the investigation, drafting, and filing. To enrich an existing issue, use the `issue-refiner` agent instead.

## Arguments

$ARGUMENTS — a description of the issue to file (a feature, a bug report, a task). If empty, ask what the user wants to file.

## Before dispatching

Work out whether this is a bug, feature, task, or chore, since that decides which labels apply and what detail the issue needs. When it's ambiguous, default to task.

Ask the user only for what the description lacks and the codebase can't supply, at most two questions. For a bug, that is usually what happens versus what should happen, and how to reproduce it. For a feature, the problem it solves and any constraints or non-goals. Don't ask for file paths or function names; the investigation finds those.

## Dispatch

Launch one subagent (`subagent_type: standard-worker`):

> Create an issue for this codebase.
>
> **Type:** <classified type>
> **Description:** <user's description + any follow-up answers>
>
> Read `${CLAUDE_CONFIG_DIR:-~/.claude}/skills/mine-create-issue/worker.md` for the complete workflow. Do NOT use the Skill tool — the instructions are in worker.md, not a skill.

The subagent's final message ends with the issue URL on its own line (notes may precede it), or is an `ERROR:` line if something blocked it. Report the result to the user. If the error says no tools are available for the configured tracker, ask the user how to proceed rather than retrying or choosing another tracker yourself; the tooling for that tracker may live in another repo on this machine.
