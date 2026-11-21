---
name: mine-commit-push
description: "Use when the user says: \"commit and push\". Commits and pushes changes to the current branch."
user-invocable: true
---

## Context

- Current git status: !`git status`
- Current git diff (staged and unstaged changes): !`git diff HEAD`
- Current branch: !`git branch --show-current`

## Goal

Land the current changes as clean commits on the remote, after the review and verification that make a push safe to trust. Standalone, and also the first stage of `mine-ship`.

Commit and push are outward-facing and hard to take back, so the gates below run before them, not after.

## Where commits go

By default, never commit to the default branch (`git-default-branch`): create a branch first, and set the upstream if the branch has none. Any rule in the user's or repo's instructions that changes where commits land or how they're published (for example a repo that takes direct pushes to the default branch) wins over this default. Follow it without asking.

## Before committing

- **Scope.** Changes that span distinct concerns (a feature plus an unrelated fix, config mixed with new behavior) become one commit per concern, and you say so. Review and verification run once on the whole change, before the first commit. Ask only when concerns interleave within the same hunks, or when an unrelated change plausibly belongs on another branch or PR.
- **Review.** Run the code review in `rules/common/git-workflow.md` (Code Review Before Commit), including its skip criteria and loop. If the same CRITICAL or HIGH findings keep recurring and can't be auto-fixed, stop and defer to the user instead of committing.
- **Verification.** Skip for prose-only docs; instruction files (skills, rules, agent prompts) still get the repo's lint. Otherwise run tests and linter per `rules/common/commit-conventions.md` (Local Verification Before Commit), and fix failures first.
- **Test presence.** Skip when the repo has no test infrastructure or the change is exempt under the Test Co-location rule in `references/common/testing.md`. If the diff against the default branch has new or changed source but no test changes, write the missing tests yourself, in the repo's conventions, and commit them with the change. A test that exists only to satisfy this check (asserts nothing, mirrors the implementation) is the trap: a test earns its place if it would fail with the change reverted. If no meaningful test is feasible, say "no tests added: <reason>" in one line.

## Committing and pushing

Stage the relevant files, commit only what passed the gates, and push only after the commit succeeded: chain them (`git add ... && git commit ... && git push`) so a rejected commit never pushes the old HEAD and gets reported as shipped. When splitting, chain each commit in turn. If a hook rejects or reformats, fix it, re-stage, and retry; if the push is rejected, handle it per the user's rules, and don't report success until the push lands. For a multi-line message, make a directory with `mktemp -d <scratchpad>/mine-commit-XXXXXX`, write `<dir>/message.md`, and use `git commit -F <dir>/message.md`; a one-line message can use `-m`.
