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
2. **COMMIT SCOPE CHECK:** Review the diff for unrelated changes that belong in separate commits (e.g., a feature + an unrelated bug fix, or a config change mixed with new functionality). If the changes clearly span distinct concerns, **ask the user** whether to split them into separate commits before proceeding. If the changes are all part of one logical unit of work, continue.
3. **CHANGELOG CHECK (mandatory — never skip this step):** Locate the nearest `CHANGELOG.md` using this algorithm: walk upward from the current working directory one level at a time toward the repo root, checking each directory for `CHANGELOG.md` — the first one found is the nearest, use it. If no `CHANGELOG.md` is found by walking up, run `git ls-files '*CHANGELOG.md'` to find any changelogs elsewhere in the repo and pick the one with the shortest relative path from CWD. If none exist anywhere, skip this step. Use the Read tool on the specific path identified — do NOT treat a failed read of `./CHANGELOG.md` as proof that no changelog exists. Once read, decide whether the changes deserve a changelog entry:
   - **Update silently** for: new features, user-facing bug fixes, behavior changes, new integrations, breaking changes.
   - **Skip silently** for: fixing tests, lint/format cleanup, internal refactoring with no behavior change, code comments/docstrings, typo fixes in code.
   - **Ask the user** if you're unsure — e.g., a mix of internal and user-facing changes, or changes that could be described either way.
   - If updating, **match the existing changelog structure**: read the file to determine whether it uses `## [Unreleased]` sections or date-based sections (`## YYYY-MM-DD`). Add entries under the appropriate heading — either the existing `[Unreleased]` section or today's date section (creating it if needed). Keep them **high-level and terse** — one bullet per change, two at most. These are **user-facing** entries; describe what changed for the user, not implementation details.
   - If you need to ask, do so **before** proceeding to step 4.
4. **CODE REVIEW (skip for documentation-only changes):** Run the code-reviewer loop, then `integration-reviewer` + `wtf-reviewer` in parallel on the final diff — protocol and exit conditions as specified in `rules/common/git-workflow.md` (Mandatory Code Review Before Commit). If the same CRITICAL or HIGH findings recur and cannot be auto-fixed, defer to the user — do not proceed to commit.
5. **LOCAL VERIFICATION (skip for documentation-only changes):** Run tests + linter per `rules/common/commit-conventions.md` (Local Verification Before Commit — discovery order and 3-attempt retry limit), plus one gate that file doesn't cover:
   - **TEST PRESENCE CHECK (skip if no test command was found — the repo has no test infrastructure. Also skip for changes exempt per the Test Co-location rule in `references/common/testing.md`):**
     Review the branch diff (`git diff --name-only` against the default branch). If the diff contains new or changed source files but zero changes in test files (no files matching common test patterns like `test_*`, `*_test.*`, `*_spec.*`, `__tests__/`), mention this to the user and ask whether to proceed or stop to write tests. Advisory, not a hard block — the user decides.
6. **TASK FILE ARCHIVAL (auto — before staging):** Follow `rules/common/git-workflow.md` (Task File Cleanup). If `spec-helper archive --all` exits non-zero, stop and report the error to the user — do not proceed to commit. Include the resulting deletions and design.md changes in the commit.
7. Stage all relevant files (including CHANGELOG.md if updated, and any archival deletions from step 6).
8. For multi-line commit messages, run `get-skill-tmpdir mine-commit` to create a temp directory, then write the message to `<dir>/message.md` and run `git commit -F <dir>/message.md` — cleaner than embedding a heredoc on the command line. For simple one-line messages, `git commit -m "..."` is fine.
9. Push the branch to origin (use `-u` flag only if you just created a new branch).
10. You MUST do steps 7–9 (stage, commit, push) in a single message. Include the Write call for the commit message file (if needed) in that same message. Do not use any other tools or do anything else besides these tool calls.
