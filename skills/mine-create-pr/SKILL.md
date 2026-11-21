---
name: mine-create-pr
description: "Use when the user says: \"create PR\" or \"open pull request\". Reviews branch changes and creates a PR on GitHub or Azure DevOps."
user-invocable: true
---

# Create PR

Open a PR for the current branch on GitHub or Azure DevOps. Opening it triggers reviewers and CI on the branch as it stands, so everything that belongs in the PR (review-question fixes, the changelog entry) has to be committed and pushed first. It is outward-facing and a duplicate is noise.

Run this yourself in this conversation, using what you already know about the branch. If a step fails, stop and report which and why; don't carry on to PR creation.

A user or repo rule that changes the flow wins over this skill. If one says the repo takes direct pushes instead of PRs, or otherwise says a PR isn't wanted here, say so and ask before opening one anyway.

## Before opening

First, run `git-platform` (`github` → `gh`, `ado` → `ado-api pr`; on `unknown`, read stderr: if it says the directory is wrong, rerun from the repo root or with `-C <repo>`; if the remote isn't recognized, stop). Then check no PR already exists for the branch: `gh pr list --head <branch>` on GitHub, or `ado-api pr show --json` with no id on Azure DevOps, which looks up the active PR for the current branch (`ado-api pr list` has no branch filter and caps at 50, so it can miss it). A PR is returned as JSON; when none exists it exits 1 with `No active PR found for branch ...` on stderr, which is the clear-to-open outcome, while any other error means the check didn't happen. If a PR exists, report its URL and stop, before anything below pushes to it. Also confirm the branch has no unpushed commits of the user's own (`git status -sb`, or `git log @{u}..`); if it does, stop and say so now, because the review-question steps below push and would publish them. Commits made below are yours to push.

Run the pre-flight scripts, but treat their output as leads, not verdicts. Decide whether each finding matters for this branch; say in one line when you set one aside, and only stop or ask when a real decision is left.

- **`check-review-questions`** (no arguments) flags on file overlap alone. Read each flagged `REVIEW.md` against the branch diff and decide whether the change made a question wrong or opened a concern none covers. Update the questions the change made wrong, commit (`docs: update REVIEW.md review questions`), push, and name what you changed. Ask only when the right edit is a real call, such as a question that no longer applies and deleting it would drop a concern the module still has (offer the outcomes that fit: remove, rewrite, or what you found).
- **`check-review-coverage`** (no arguments) lists branch-touched source directories with no `REVIEW.md`. A missing file isn't a reason to add one. Judge which directories hold cross-cutting concerns review questions are for (`${CLAUDE_CONFIG_DIR:-~/.claude}/references/common/review-questions.md`). If any do, ask whether to add them, naming the directories and the concern each would cover, and offering outcomes: add now, defer (ask again later), or suppress for good.
  - **Add:** follow `review-questions.md` for the authoring rules and the cross-module pointer placement (the pointer goes in this directory's own `REVIEW.md`, naming each dependency). Commit (`docs: add REVIEW.md review questions`) and push.
  - **Defer:** per directory, write `{"status": "deferred", "tier": <new_tier>, "prompt_after": "<YYYY-MM-DD>"}` to `${CLAUDE_CONFIG_DIR:-$HOME/.claude}/projects/<hashed-key>/review-coverage.json`. The key is `printf '%s' "$state_key" | sha256sum | cut -c1-16`, where `state_key` is `${main_repo_root}/${dir}` and `main_repo_root` comes from `git rev-parse --git-common-dir` → `dirname` → `cd` + `pwd -P`. Read the current tier from that file (default 0), set `prompt_after` (zero-padded `YYYY-MM-DD`, compared as a string) to today + `[3,7,14,30][tier]` days, then bump the tier by 1 (cap 3).
  - **Suppress:** write `{"status": "suppressed"}` to the same path.

Then gather what you need: current branch, `git-default-branch`, the remote URL, `git-branch-log`, and `git-branch-diff-stat`.

## Draft PR Body

Follow `git-workflow.md` (PR Description Content): the body answers what changed and why, as the shipped state, in terms a reviewer who never saw this session can use. You hold the whole session, including abandoned approaches, so draft from the full branch diff and commit log (all commits, not just the latest), reading modified files where the diff isn't enough.

**Title:** under 70 characters. If the repo uses conventional-commit prefixes on PR titles, the title must start with one (`feat`, `fix`, `refactor`, `docs`, `test`, `chore`, `perf`, `ci`): squash-merge repos use the title as the changelog entry, and a missing prefix breaks generation or silently drops it. Do recent merged PRs mostly use them (`gh pr list --state merged --limit 8 --json title` / `ado-api pr list --status completed --top 8`)? If the sample is thin or mixed, `release-please-config.json`, commitlint config, or commit-convention rules in the repo's `.claude/` confirm it. With no signal, use a plain title.

**Body:** group by topic under `###` headers, most impactful first, with bullets that state what changed and why, including the tradeoff of the approach taken. Collect small standalone changes under `### Notable Changes` (top, if worth seeing first) and `### Housekeeping` (bottom). If the PR changes `./design/` documents, reference them (`design/specs/NNN-slug/design.md`) instead of restating their reasoning.

**Closing issues** (GitHub only; skip for Azure DevOps): find the issues this PR resolves and end the body with `Closes #N` per issue, each on its own line. Sources include the conversation (an issue the user named as the work), a number in the branch name (`123-fix-null`, `issue-123`, `issue/123`, `fix/123-description`; confirm it is an open issue this work resolves, since `upgrade-node-20` isn't), closing keywords in commit messages (`Fixes #123`, `Closes #123`, `Resolves #123`; not `refs #123`), and every key on the `**Issues:**` line of a sketch ledger the branch builds. Judge whether the branch is really that ledger's work: a ledger touched only in passing, such as an Addendum on an already-built one, doesn't close its issues.

## Changelog

Changelog entries are written at PR time, from the full branch diff. Find the changelog that covers the code this branch changed (one per package if the diff spans several; `git ls-files '*CHANGELOG.md'` lists candidates). A changelog for an unrelated package doesn't count. None covers it, or the repo says it has no changelog: skip.

Judge the full branch diff (`git diff origin/<base>...HEAD`), not individual commits. User-facing features, fixes, behavior changes, integrations, and breaking changes get an entry; test fixes, lint cleanup, internal refactors, and comment/typo changes don't. If the branch already carries changelog entries, keep them. Match the file's structure (`## [Unreleased]` or date sections, creating today's if needed), one terse user-facing bullet per logical change. The PR doesn't exist yet, so entries carry no PR number. Stage only the changelog path (the tree may hold unrelated edits), commit as `docs: update changelog`, and push.

## Create

Make a directory with `mktemp -d <scratchpad>/mine-create-pr-XXXXXX` and write the body to `<dir>/body.md`.

- **GitHub:** `gh pr create --title "..." --body-file <dir>/body.md`
- **Azure DevOps:** `ado-api pr create --title "..." --description-file <dir>/body.md --source-branch <branch> --target-branch <default-branch>` (never put the body in a shell argument; backticks in it would execute). It prints the new PR's id but no URL, so build the URL from the id and the remote (`git remote get-url origin`): `https://dev.azure.com/{org}/{project}/_git/{repo}/pullrequest/{id}`.

Finish by giving the PR URL on its own line, preceded by any notes (e.g. no changelog found). If something failed, say which step and why instead of a URL.
