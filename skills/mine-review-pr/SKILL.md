---
name: mine-review-pr
description: "Use when the user says: \"review this PR\", \"review PR <number>\", \"review someone else's PR\", \"review the PR for <branch>\", \"review their branch\". Reviews another developer's open PR read-only — dispatches the standard reviewer trio, verifies findings against the real code and PR description, and optionally posts them as PR comment threads. Never edits code."
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
3. Fetch PR metadata. Extract: `source` branch, `target` branch, `title`, `author`, `description`, and `state`.
4. **Check PR state.** If the PR is merged or closed/abandoned, warn the user and confirm before proceeding. A merged PR's source branch may already be deleted upstream.
5. **Check PR author.** On GitHub, compare the PR's `author.login` against `gh api user --jq .login`. On ADO, compare against the `git config user.email` value (ADO PR metadata includes the author's email). If it is the user's own PR, say so and suggest `/mine-review` instead.

## Phase 1: Fetch branches and capture the diff

This skill expects to run from a review worktree (e.g. `review-pr-50058`). It fetches and checks out branches as needed. If the worktree is already on the source branch, no checkout is required.

1. Fetch both the source and target branches:
   ```bash
   git fetch origin <source-branch> <target-branch>
   ```

2. If HEAD does not match `origin/<source-branch>`, check `git status --porcelain` is clean, then switch:
   ```bash
   git checkout -B <source-branch> origin/<source-branch>
   ```

3. Capture the diff:
   ```bash
   get-skill-tmpdir mine-review-pr
   ```
   ```bash
   git diff origin/<target>...HEAD > <tmpdir>/diff.patch
   git diff origin/<target>...HEAD --stat
   git rev-parse HEAD
   ```

4. If the diff exceeds ~500 files, ask the user to confirm before proceeding.

## Phase 2: Dispatch reviewers

### Detect review mode

Determine the file extensions in the diff via `git diff origin/<target>...HEAD --name-only`. A file is an **instruction file** if it has a `.md` extension. If ALL changed files are instruction files, use **instruction mode**. Otherwise use **code mode**.

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

## Phase 3: Consolidate, categorize, and present

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

### Present the report

Use `mine-review`'s severity-grouped format, organized by severity, not by reviewer. Include the proposed bucket assignment for each finding so the user can see what would be posted.

## Phase 4: Verify every claim before drafting (do not skip)

Reviewers read a diff, not the PR's own account of itself. Before drafting comments, re-check each surviving finding three ways:

1. **Against the code.** Read the actual current file, grep for the specific claim. Line numbers drift, duplicated blocks get fixed between diff and HEAD.
2. **Against the PR description.** Re-read the description from Phase 0. A finding that frames something as "undisclosed" or "unexplained" is wrong if the PR description already says it. This is the most common false positive. Posting it tells the author their PR description wasn't read, which undermines every other finding.
3. **Against existing threads.** Fetch existing PR threads (see Phase 0 table). Check for threads with the Claude attribution footer. Drop any finding that duplicates an already-posted thread. Only draft what is new or materially changed since the last review pass.

Drop or reframe any claim that does not survive this check.

## Phase 5: Draft comment threads

One draft per bucket/issue from Phase 3. Use the template and footer in `REFERENCE.md`. Write each draft body to a temp file under the skill tmpdir (one file per thread).

Present every draft in one message before posting anything.

## Phase 6: Confirm, then post

If no findings survived Phase 4 (nothing new since a prior pass, or the PR is genuinely clean), say so and stop. No empty confirmation prompt.

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
