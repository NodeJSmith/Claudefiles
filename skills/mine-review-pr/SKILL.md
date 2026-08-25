---
name: mine-review-pr
description: "Use when the user says: \"review this PR\", \"review PR <number>\", \"review someone else's PR\", \"review the PR for <branch>\", \"review their branch\". Reviews another developer's open PR read-only — dispatches the standard reviewer trio, verifies findings against the current PR head, the real code, the PR description, and existing threads before presenting them, and optionally posts them as PR comment threads. Never edits code."
user-invocable: true
---

# Review External PR

Reviews someone else's open PR: fetches the branch, runs the appropriate reviewer trio against the diff, verifies every finding before trusting it. Posting findings as PR comment threads requires explicit approval. This skill never edits code. See `REFERENCE.md` for the comment-draft template and footer.

## Arguments

$ARGUMENTS can be a PR number, branch name, or PR URL. Examples:
- `/mine-review-pr 50058`
- `/mine-review-pr feature/patrick/claims`
- `/mine-review-pr https://dev.azure.com/.../pullrequest/50058`
- `/mine-review-pr https://github.com/org/repo/pull/123`

If empty, ask for one:

```
AskUserQuestion:
  question: "Which PR should I review? (number, branch name, or URL)"
  header: "PR target"
```

## Phase 0: Detect platform and resolve the PR

1. Run `git-platform` to determine `github` or `ado`. All PR commands below adapt to the platform:

   | Operation | GitHub | ADO |
   |-----------|--------|-----|
   | Show PR | `gh pr view <id> --json number,title,author,body,headRefName,baseRefName,state` | `ado-api pr show <id> --json` |
   | List threads | `gh-pr-threads <id> --json --all` | `ado-api pr threads <id> --json --all` |
   | Post thread | `gh pr comment <id> --body-file <file>` | `ado-api pr thread-add <id> --body-file <file>` |

2. If given a URL, extract the PR number from it. GitHub URLs follow `github.com/<owner>/<repo>/pull/<number>`. ADO URLs follow `dev.azure.com/<org>/<project>/_git/<repo>/pullrequest/<number>`. If given a branch name, look up the PR for that branch (`gh pr list --head <branch> --json number` or `ado-api pr list --json` and match on source).

   **URL repo mismatch check.** A URL also names a repository. Extract it (`<owner>/<repo>` for GitHub, `<org>/<project>/<repo>` for ADO). Run `git remote get-url origin` and normalize both sides to a bare `owner/repo` (or `org/project/repo`) tuple before comparing — strip the protocol/host and any trailing `.git`, so both `git@github.com:owner/repo.git` (SSH) and `https://github.com/owner/repo.git` (HTTPS) reduce to `owner/repo`; compare case-insensitively. If `origin` doesn't exist or the command errors, treat that as unknown rather than a mismatch and ask the user to confirm the target repo before proceeding. If the normalized values don't match, stop and tell the user — this worktree isn't checked out against that repo, and reusing its PR number against the wrong remote would review or comment on the wrong PR. Don't guess; a fresh worktree against the right remote is the fix.
3. Fetch PR metadata. Extract: `source` branch, `target` branch, `title`, `author`, `description`, and `state`.
4. **Check PR state.** If the PR is merged or closed/abandoned, warn the user and confirm before proceeding. A merged PR's source branch may already be deleted upstream.
5. **Check PR author.** On GitHub, compare the PR's `author.login` against `gh api user --jq .login`. On ADO, compare against the `git config user.email` value (ADO PR metadata includes the author's email). If it is the user's own PR, say so and suggest `/mine-review` instead.

## Phase 1: Fetch branches and capture the diff

This skill expects to run from a review worktree (e.g. `review-pr-50058`). It fetches and checks out branches as needed. If the worktree is already on the source branch, no checkout is required.

1. Fetch both the source and target branches. Single-quote the branch names — they come from someone else's PR and could contain shell metacharacters. Double quotes are not enough here: they still allow `$(...)`/backtick command substitution, which git's ref-name rules do not forbid:
   ```bash
   git fetch origin '<source-branch>' '<target-branch>'
   ```

2. If HEAD does not match `origin/<source-branch>`, check `git status --porcelain` is clean, then switch to a detached checkout — this reviews the commit without touching any local branch, so a local branch that happens to share the source branch's name is never reset:
   ```bash
   git checkout --detach 'origin/<source-branch>'
   ```

3. Capture the diff:
   ```bash
   get-skill-tmpdir mine-review-pr
   ```
   ```bash
   git diff 'origin/<target>...HEAD' > <tmpdir>/diff.patch
   git diff 'origin/<target>...HEAD' --stat
   git rev-parse HEAD
   ```

4. If the diff exceeds ~500 files, ask the user to confirm before proceeding.

## Phase 2: Dispatch reviewers

### Detect review mode

Determine the file extensions in the diff via `git diff 'origin/<target>...HEAD' --name-only`. A file is an **instruction file** if it has a `.md` extension. If ALL changed files are instruction files, use **instruction mode**. Otherwise use **code mode**.

### Dispatch

Single message, three parallel `Agent` calls. Each given:

```
Review changes. Diff at <tmpdir>/diff.patch (HEAD: <sha>). Read changed files
for surrounding context. Before relying on the diff, verify HEAD matches <sha>.
This is PR review of someone else's branch. You are reviewing, not fixing.
```

**Code mode:** `code-reviewer`, `integration-reviewer`, `wtf-reviewer`

**Instruction mode:** `fine-toothed-comb`, `instruction-quality-reviewer`, `writing-quality-reviewer`

Wait for all three completion notifications. Do not poll, and do not fabricate or predict results before they land.

## Phase 3: Consolidate and categorize

### Deduplicate

If two reviewers flagged the same issue, keep one entry and note the cross-signal (`flagged by code-review + readability pass`).

### Validity assessment

Apply the protocol from `${CLAUDE_CONFIG_DIR:-~/.claude}/skills/mine-challenge/findings-protocol.md`: findings are valid by default; flagging one as likely invalid requires a concrete evidence trail.

### Categorize for threading

Sort every finding into exactly one bucket:
- **Tests bucket** — missing or inadequate test coverage. One thread for all of these, because test gaps are usually a single wholesale ask ("please add tests for X, Y, Z") rather than independently actionable items.
- **Docs bucket** — stale or missing documentation. One thread for the same reason.
- **Code issue** — everything else (correctness, duplication, design, performance). **One thread per distinct issue**, because each is independently resolvable and the PR author may agree with some and push back on others.

A finding that spans two buckets goes to whichever the repo's own conventions treat as the harder requirement. Check project rules before defaulting.

Fold nitpick-severity findings into an adjacent code-issue bucket or drop them. A readability nit posted as its own thread on someone else's PR reads as nagging.

## Phase 4: Verify every claim before presenting (do not skip)

Reviewers read a diff, not the PR's own account of itself, and the PR may have moved since Phase 1. Before showing the user anything, re-check each surviving finding four ways:

1. **Against the current PR head.** Re-fetch the PR's head SHA — `gh pr view <id> --json headRefOid` (GitHub) or `ado-api pr show <id> --json`, reading `lastMergeSourceCommit.commitId` (ADO) — and compare to the HEAD pinned in Phase 1. If it changed, the author pushed while reviewers were running: tell the user, redo Phase 1 steps 1–3 (re-fetch, re-checkout the new head, and re-capture the diff), and re-run both Phase 2 (dispatch) and Phase 3 (consolidate and categorize) on the fresh output before resuming this phase. Don't verify or present findings against a stale diff, and don't resume verification on output that hasn't been deduplicated and bucketed yet.
2. **Against the code.** Read the actual current file, grep for the specific claim. Line numbers drift, duplicated blocks get fixed between diff and HEAD.
3. **Against the PR description.** Re-read the description from Phase 0. A finding that frames something as "undisclosed" or "unexplained" is wrong if the PR description already says it. This is the most common false positive. Posting it tells the author their PR description wasn't read, which undermines every other finding.
4. **Against existing threads.** Fetch existing PR threads (see Phase 0 table), including resolved ones. A finding is a duplicate if it names the same file:line (or the same code construct, if line numbers drifted) and the same underlying concern as an existing thread — not merely the same general topic; two findings about different aspects of the same function are not duplicates. Drop findings that duplicate an unresolved thread. For a finding that duplicates a *resolved* thread, check it against step 2: if the underlying issue is still present in the code, treat it as unresolved despite the thread's status and keep it (the prior fix didn't fully land); otherwise drop it. Match against threads from any author — a concern already raised by a human reviewer or another bot is still a duplicate. The Claude attribution footer identifies this skill's own prior comments, for tracking re-review passes, not for gating which threads count toward dedup.

Drop or reframe any claim that does not survive this check.

## Phase 5: Present the report

Use `mine-review`'s severity-grouped format, organized by severity, not by reviewer. Include the proposed bucket assignment for each finding so the user can see what would be posted. Only findings that survived Phase 4 appear here.

If nothing survived Phase 4 (nothing new since a prior pass, or the PR is genuinely clean), say so and stop here. No empty confirmation prompt.

## Phase 6: Draft comment threads

One draft per bucket/issue among the findings presented in Phase 5 (bucketed per Phase 3). Use the template and footer in `REFERENCE.md`. Write each draft body to a temp file under the skill tmpdir (one file per thread).

Present every draft in one message before posting anything.

## Phase 7: Confirm, then post

```
AskUserQuestion:
  question: "Ready to post these {N} comment(s) to PR #{id}?"
  header: "Post comments"
  multiSelect: false
  options:
    - label: "Post all now"
      description: "Post each draft as a comment thread"
    - label: "Edit some first"
      description: "Tell me which thread(s) to change or drop before posting"
    - label: "Don't post"
      description: "Hold everything, just wanted the review"
```

Never post without this confirmation. This skill comments on someone else's work.

On approval, post each draft using the platform command from the Phase 0 table (use `--body-file` to avoid shell quoting issues). Report back the thread IDs.

## What This Skill Does NOT Do

- **Edit the PR author's code.** Read-only, always.
- **Review your own PR.** Use `/mine-review` for that.
- **Deep codebase audit.** Use `/mine-audit`.
- **Exhaustive style sweep.** Use `/mine-clean-code`.
