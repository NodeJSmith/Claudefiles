---
name: mine-review-pr
description: "Use when the user says: \"review this PR\", \"review PR <number>\", \"review someone else's PR\", \"review the PR for <branch>\", \"review their branch\". Reviews another developer's open PR read-only. Gathers the PR's context, dispatches the standard reviewer trio, proves or drops each finding with executed checks (tests, queries, consumers, CI, the target branch), shows full drafts, and optionally posts them as PR comment threads. Never edits code."
user-invocable: true
---

# Review External PR

Reviews someone else's open PR: gathers its context, runs the reviewer trio against the diff, then proves or drops every finding that matters by running the check that settles it. Re-reading the code is not proof. Nothing reaches the PR author that this skill could have checked itself and didn't. Posting requires explicit approval, and this skill never edits code. See `REFERENCE.md` for the comment template and footer.

The investigation in Phase 4 is open-ended digging, so this skill works best on Opus.

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

## Running commands

These hold for every phase:

- **One command per Bash call.** No for-loops, `cd &&` chains, or several substitutions in one call; worktree sessions refuse them. Put a loop in a script file under the tmpdir and run that.
- **A failed command is "no answer".** An error, a non-zero exit, or empty output from a command that errored is never evidence that something is absent or that a check passed. Fix an obvious command mistake once; otherwise report "no answer" for what it was checking. The exception is a search: `grep` or `git grep` exiting 1 with no output means "no match", which is a real answer. Exit 2 or an error message is a failure. A command the permission system denies is reported as "blocked by permissions", not as an error.
- **Don't poll.** Reviewer subagents notify on completion. No `sleep`, no `ScheduleWakeup`.

## Phase 0: Resolve the PR and gather its context

1. Run `git-platform` to determine `github` or `ado`. All PR commands below adapt to the platform:

   | Operation | GitHub | ADO |
   |-----------|--------|-----|
   | Show PR | `gh pr view <id> --json number,title,author,body,headRefName,baseRefName,state,headRefOid,isCrossRepository` | `ado-api pr show <id> --json` |
   | Head SHA (Phase 7) | `gh pr view <id> --json headRefOid` | `git ls-remote origin 'refs/heads/<source-branch>'` (empty output means the branch is gone: "no answer") |
   | Linked work items | `gh pr view <id> --json closingIssuesReferences` | `ado-api pr work-item-list <id> --json` |
   | List threads | `gh-pr-threads <id> --json --all` | `ado-api pr threads <id> --json --all` |
   | Post thread | `gh pr comment <id> --body-file <file>` | `ado-api pr thread-add <id> --body-file <file>` |

   `ado-api pr threads --json` prints a `PR #<id> — N thread(s)` line before the JSON array; skip that first line before parsing. `ado-api pr show --json` carries no head or merge commit, which is why the ADO head SHA comes from `git ls-remote`.

2. If given a URL, extract the PR number from it. GitHub URLs follow `github.com/<owner>/<repo>/pull/<number>`. ADO URLs follow `dev.azure.com/<org>/<project>/_git/<repo>/pullrequest/<number>`. If given a branch name, look up the PR for that branch (`gh pr list --head <branch> --json number` or `ado-api pr list --json` and match on source).

   **URL repo mismatch check.** A URL also names a repository. Extract it (`<owner>/<repo>` for GitHub, `<org>/<project>/<repo>` for ADO). Run `git remote get-url origin` and normalize both sides to a bare `owner/repo` (or `org/project/repo`) tuple before comparing — strip the protocol/host and any trailing `.git`, so both `git@github.com:owner/repo.git` (SSH) and `https://github.com/owner/repo.git` (HTTPS) reduce to `owner/repo`; compare case-insensitively. If `origin` doesn't exist or the command errors, treat that as unknown rather than a mismatch and ask the user to confirm the target repo before proceeding. If the normalized values don't match, stop and tell the user — this worktree isn't checked out against that repo, and reusing its PR number against the wrong remote would review or comment on the wrong PR. Don't guess; a fresh worktree against the right remote is the fix.
3. Fetch PR metadata. Extract: `source` branch, `target` branch, `title`, `author`, `description`, and `state`.
4. **Check PR state.** If the PR is merged or closed/abandoned, say so in one line and proceed; review is read-only and posting is gated separately in Phase 7. If a merged PR's source branch can no longer be fetched in Phase 1, say so and stop.
5. **Check PR author.** On GitHub, compare the PR's `author.login` against `gh api user --jq .login`. On ADO, compare against the `git config user.email` value (ADO PR metadata includes the author's email). If it is the user's own PR, say so and suggest `/mine-review` instead.
6. **Gather context in one batch.** Run the linked-work-items and list-threads commands from the table in parallel, one command per call, without asking about each one. Get the PR's CI or validation-build status too (`gh pr checks <id>` on GitHub; on ADO, `az` with the devops extension works), and note any run or build links the author left in the description or threads. A command that errors is recorded as "no answer" for that item, not skipped silently. This context is what the reviewers and the investigation work from: what the PR says it does, what it's meant to fix, whether CI passed, and what has already been raised.

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

3. Capture the diff and pin the commits. Each line is its own Bash call:
   ```bash
   mktemp -d <scratchpad>/mine-review-pr-XXXXXX
   ```
   ```bash
   git diff 'origin/<target>...HEAD' > <tmpdir>/diff.patch
   git diff 'origin/<target>...HEAD' --stat
   git rev-parse HEAD
   git merge-base 'origin/<target>' HEAD
   ```

   The `rev-parse` output is the pinned `<sha>`. The `merge-base` output is `<base>`, the commit the PR branched from. The three-dot diff is taken from `<base>`, so it is right for open and squash-merged PRs alike.

4. Write the Phase 0 context to `<tmpdir>/context.md`: the PR description, linked work items, CI status, run links, and a one-line summary of each existing thread.

5. If the diff exceeds ~500 files, ask the user to confirm before proceeding.

## Phase 2: Dispatch reviewers and write the overview

### Detect review mode

Determine the file extensions in the diff via `git diff 'origin/<target>...HEAD' --name-only`. A file is an **instruction file** if it has a `.md` extension. If ALL changed files are instruction files, use **instruction mode**. Otherwise use **code mode**.

### Dispatch

Single message, three parallel `Agent` calls. Each given:

```
Review changes. Diff at <tmpdir>/diff.patch (HEAD: <sha>). PR context (description,
linked work items, CI status, existing threads) at <tmpdir>/context.md. Read changed
files for surrounding context. Before relying on the diff, verify HEAD matches <sha>.
This is PR review of someone else's branch. You are reviewing, not fixing.
For each finding, name the command that would confirm or refute it (a test to run,
a query, a grep for consumers, a log to read, a file to check on the target branch).
```

Pass the reviewers the gathered context only, never your own hypotheses about the PR: a hypothesis in the prompt anchors them, and they come back confirming it instead of reading the code fresh.

**Code mode:** `code-reviewer`, `integration-reviewer`, `wtf-reviewer`

**Instruction mode:** `fine-toothed-comb`, `instruction-quality-reviewer`, `writing-quality-reviewer`. These report blocking/minor; treat blocking as High and minor as Low.

### Write the PR overview while reviewers run

While the reviewers run, write a short overview of what the PR contains, for the user only. It is never posted, because the author already knows what their PR does. Read `<tmpdir>/diff.patch` (and changed files where the hunks need context), then compare it with the PR description, the linked work items, and the commit list (`git log --oneline '<base>..HEAD'`). Describe what the diff does, not what the description or commit subjects say it does:

- **Purpose** — one or two sentences on what the PR is for.
- **Changes** — grouped by area or intent ("adds four claims task classes", "changes the shared `PreProcTask.launch()`"), not a per-file list; the diff stat already covers files.
- **Description vs. diff** — anything the diff changes that the description doesn't mention, or anything the description claims that the diff doesn't contain. Omit this line when they agree.
- **Claims** — what the PR says it fixes, preserves, or proves: a root cause, "logic unchanged", "fixes the duplicate rows", "no consumer impact". List each checkable claim. Each is an entry for Phase 4 to prove or disprove, not a finding, so the PR's own story is tested, not only its lines.

The user needs to know what the PR does to judge the findings, and on a clean PR the overview is the main output.

Then wait for all three completion notifications. Do not fabricate or predict results before they land.

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

A finding that spans two buckets goes to whichever bucket the repo's rules enforce more strictly (a mandatory-tests rule beats a docs nicety). Check project rules before defaulting.

Only Medium-and-above code issues get their own thread. Fold Low and nit code findings into an adjacent thread or drop them. A minor point posted as its own thread on someone else's PR reads as nagging.

## Phase 4: Prove or drop (do not skip)

Phase 3's "valid by default" governs triage, so reviewers' findings aren't discarded on a hunch. This phase sets the higher bar for what gets presented.

1. **Existing threads, description, current code.** Read each finding's file at HEAD, not the patch: line numbers drift, and a duplicated block may already be fixed. Drop a finding or disproved claim that duplicates an existing thread: same file:line (or the same code construct, if line numbers drifted) and the same underlying concern, not merely the same topic. Match threads from any author. A finding that duplicates a *resolved* thread is kept if the issue is still present at HEAD (the prior fix didn't fully land), otherwise dropped. The Claude attribution footer identifies this skill's own prior comments for tracking re-review passes, not for gating dedup. Then drop or reframe any finding that calls something "undisclosed" or "unexplained" when the PR description already says it. That is the most common false positive, and posting it tells the author their description wasn't read.
2. **Introduced or already there.** For each Medium-and-above finding, ask whether the issue would exist if the PR never merged. Check it at `<base>` with `git show '<base>:<path>'` or `git grep '<pattern>' '<base>'`. These are read-only; never check out `<base>`. Route by what the PR did:
   - **The PR introduced it, or copied, extended, or worsened an existing instance:** a finding like any other.
   - **It's at `<base>` and the PR touches that code:** a finding, labelled with the "while you're in here" variant from `REFERENCE.md`.
   - **It's at `<base>` and the PR neither touches nor worsens it:** a tracker candidate for the user, not drafted.
3. **Investigate.** For every remaining Medium-and-above finding and every PR claim, run the check that proves or disproves it, starting from the command the reviewer named: run the tests, query the built output, look up the real consumers, read the CI logs, check the history. Follow up on whatever comes back unknown until you can state the impact and one concrete fix, until it's clear no executable check applies (step 4's `judgment:` route), or until step 4's open-question criteria apply.
   - Read the repo's `CLAUDE.md` and rules for how to query its systems: built output, consumers, schedules, CI.
   - Check a claim about consumers, schedules, or test coverage against the live system, never against a repo doc. Docs go stale.
   - Re-reading the PR's own code is not a check for a Medium-and-above finding or a claim. A grep for the other copy, a consumer lookup, or a test run is.
   - Low findings and nits get the step 1 re-read only.

   **What you may run:** read-only commands, scratch files in the tmpdir, and the PR's tests when they write nothing outside the review worktree and the tmpdir (unit tests; not `dbt run`/`build`, and not integration tests that hit real services). PR tests run PR-authored code with your credentials, so run them only on teammates' PRs, never on a fork (`isCrossRepository` on GitHub). A reviewer-named command is a suggestion; run it only if it fits this scope. Never run DML or any other database or external-service write. A check that needs one becomes an open question, with the command written out for the user to run.

4. **Record the outcome.** Each surviving finding carries an `Evidence:` line quoting the command run and the part of its output that settles the finding. Say "verified", "confirmed", or "proven" only when that line names something run. A finding about naming, design shape, or prose may have no executable check: its Evidence line reads `judgment: <the reasoning>`, and it is never called verified. A finding about runtime behavior, consumers, or coverage is never judgment-only: run its check, or make it an open question.

   - Set each surviving finding's severity from the impact the investigation proved, not the reviewer's estimate.
   - A confirmed PR claim is noted in the overview. A disproved claim becomes a High Code-issue finding, unless an existing thread already raises it (step 1).
   - A finding the evidence refutes is dropped.
   - A Low folded into a host thread that was dropped or rerouted folds into another surviving thread, or is dropped.
   - A finding becomes an **open question** only when its settling check can't be run here (it needs the author's intent, or access this session lacks), was blocked by permissions, or errored. A runnable check you skipped is unfinished work, so go run it. Each open question states what was tried, why it didn't settle, and the one check that would.

## Phase 5: Report and shape the set

The report, in this order:

1. **Overview** from Phase 2, with confirmed claims noted, plus a **riskiest merge decision** line written from what Phase 4 proved: the one thing most likely to hurt if this merges as is, and what you recommend. Omit that line when there is none.
2. **Findings**, a short entry each, grouped by severity: severity, bucket, label (`Blocking` / `Non-blocking`, defaults in `REFERENCE.md`), the gist, the evidence cut to the command and a one-clause result (the full output belongs in the draft), any folded Lows, and for a finding that predates the PR, its routing and the one-line reason.
3. **Open questions for you** — each with what was tried, why it didn't settle, and the check that would settle it.
4. **Tracker candidates** — issues already on the target branch that the PR doesn't touch, each with where it lives.

If no findings, open questions, or tracker candidates survived, show the overview, say nothing survived, and stop. No prompt. If only open questions or tracker candidates survived, show the report and stop; the user replies in free text if they want anything done.

Otherwise ask:

```
AskUserQuestion:
  question: "Draft comment threads for these {N} finding(s)?"
  header: "Draft"
  multiSelect: false
  options:
    - label: "Draft these"
      description: "Write a full draft for each finding as listed"
    - label: "Change the set first"
      description: "Tell me what to drop, add, relabel, dig into, or post as a question"
    - label: "Stop"
      description: "Just wanted the review; draft nothing"
```

On "Change the set first", take the changes as free text: drop or add findings, flip a label, dig further into a finding or open question, or post an open question as a question to the author (the question form in `REFERENCE.md`). Apply them (digging means back through Phase 4 step 3 for that item), show the changed entries, and ask again.

## Phase 6: Draft comment threads

One draft per thread in the shaped set: each Medium-and-above code issue, the tests bucket, and the docs bucket, with folded findings inside their host thread. Use the template, labels, and footer in `REFERENCE.md`. Write each draft body to a temp file under the tmpdir (one file per thread).

Show every draft's full body inline as message text, in one message, before the post gate. Never show only titles or paths, and don't rely on a `Read` of the files, which the terminal collapses: the user approves what they have read.

## Phase 7: Confirm, then post

```
AskUserQuestion:
  question: "Ready to post these {N} thread(s) to PR #{id}?"
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

Never post without this confirmation: a posted thread can't be unsent and lands under the user's name. On "Edit some first", show each changed body in full again before asking again.

On approval, first get the PR's current head SHA with the Phase 0 table command and compare it to the pinned `<sha>`. Never compare against a local ref (`origin/<branch>`, `git rev-parse`): that compares the Phase 1 fetch to itself. If the head moved, the author pushed during the review: tell the user what changed and let them decide whether to post, re-review, or stop. If the command fails, say "head check: no answer" and ask the same way.

Then post each draft using the platform command from the Phase 0 table (use `--body-file` to avoid shell quoting issues). Report back the thread IDs. If a post fails, report which one and don't retry blind: a post that errored after landing would double-post.

## What This Skill Does NOT Do

- **Edit the PR author's code.** Read-only, always.
- **Write to databases or external services.** Checks that need a write are handed to the user.
- **Review your own PR.** Use `/mine-review` for that.
- **Deep codebase audit.** Use `/mine-audit`.
- **Exhaustive style sweep.** Use `/mine-clean-code`.
