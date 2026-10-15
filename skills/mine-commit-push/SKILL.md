---
name: mine-commit-push
description: "Use when the user says: \"commit and push\". Commits and pushes changes to the current branch."
user-invocable: true
---

## Context

- Current git status: !`git status`
- Current git diff (staged and unstaged changes): !`git diff HEAD`
- Current branch: !`git branch --show-current`

## About this skill

Handles the "commit & push with quality gates" phase — standalone, and as Phase 1 of `mine-ship` (which adds PR creation).

## Your task

Based on the above changes:

1. If on the default branch (run `git-default-branch` to check), create a new branch first.
2. **COMMIT SCOPE CHECK:** Review the diff for unrelated changes that belong in separate commits (e.g., a feature + an unrelated bug fix, or a config change mixed with new functionality). If the changes clearly span distinct concerns, split them into one commit per concern and say so. Review and verification (steps 3-4) run once on the whole change, before the first commit. Ask the user only when the concerns interleave within the same hunks, or when the unrelated change plausibly belongs on a different branch or PR. If the changes are all part of one logical unit of work, continue.
3. **CODE REVIEW (skip when a reviewer couldn't catch anything the tests and type checker wouldn't; criteria in Code Review Before Commit in `rules/common/git-workflow.md`):** Run the code-reviewer loop, then `integration-reviewer` + `wtf-reviewer` in parallel on the final diff — protocol and exit conditions as specified in `rules/common/git-workflow.md` (Code Review Before Commit). If the same CRITICAL or HIGH findings recur and cannot be auto-fixed, defer to the user — do not proceed to commit.
4. **LOCAL VERIFICATION (skip for documentation-only changes):** Run tests + linter per `rules/common/commit-conventions.md` (Local Verification Before Commit — discovery order and 3-attempt retry limit), plus one gate that file doesn't cover:
   - **TEST PRESENCE CHECK (skip if no test command was found — the repo has no test infrastructure. Also skip for changes exempt per the Test Co-location rule in `references/common/testing.md`):**
     Review the branch diff (`git diff --name-only` against the default branch). If the diff contains new or changed source files but zero changes in test files (no files matching common test patterns like `test_*`, `*_test.*`, `*_spec.*`, `__tests__/`), write the missing tests yourself, following the repo's test conventions, and include them in the commit. The trap is a test that exists to satisfy this check: one that asserts nothing, or mirrors the implementation. A test earns its place if it would fail with the change reverted. If no meaningful test is feasible, proceed and say so in one line: "no tests added: <reason>".
5. Stage all relevant files.
6. For multi-line commit messages, run `get-skill-tmpdir mine-commit` to create a temp directory, then write the message to `<dir>/message.md` and run `git commit -F <dir>/message.md` — cleaner than embedding a heredoc on the command line. For simple one-line messages, `git commit -m "..."` is fine.
7. Push the branch to origin (use `-u` flag only if you just created a new branch).
8. You MUST do steps 5–7 (stage, commit, push) in a single message; when splitting into several commits, stage and commit each in turn in that same message. Include the Write call for the commit message file (if needed) in that same message. Do not use any other tools or do anything else besides these tool calls.
