---
name: mine-review-pr
description: "Use when the user says: \"review this PR\", \"review PR <number>\", \"review someone else's PR\", \"review the PR for <branch>\", \"review their branch\". Reviews another developer's open PR read-only. Gathers the PR's context, dispatches the standard reviewer trio, proves or drops each finding with executed checks (tests, queries, consumers, CI, the target branch), shows full drafts, and optionally posts them as PR comment threads. Never edits code."
user-invocable: true
---

# Review External PR

Review someone else's open PR so the user can judge it and, if they choose, send the author comments worth acting on. Run the reviewer trio on the diff, then prove or drop every finding that matters by running the check that settles it. Re-reading the code is not proof. Nothing should reach the author that this skill could have checked itself and didn't, because a wrong or unchecked comment on a teammate's PR costs the user's credibility. Posting needs explicit approval (a posted thread can't be unsent and lands under the user's name), and this skill never edits code. `REFERENCE.md` has the comment template, labels, and footer.

The investigation is open-ended digging, so this skill works best on Opus.

Done looks like: the user has an overview of what the PR does, a short list of findings each backed by a command that was run (or marked as judgment), open questions stating what couldn't be settled, and, only if they approved, the posted threads.

## Arguments

$ARGUMENTS is a PR number, branch name, or PR URL (`https://github.com/org/repo/pull/123`, `https://dev.azure.com/.../pullrequest/50058`).

If empty, try to infer a number before asking; a review worktree is usually launched named for its PR (`claude --worktree review-pr-50058`). Get the branch (`git branch --show-current`) and the worktree directory's last path component (`git rev-parse --show-toplevel`), each in its own Bash call; the directory name still holds the number when HEAD is detached. Infer only from a number paired with an explicit PR marker (`review-pr-50058`, `pr-50058`, `pr/50058`, optionally with Claude Code's `worktree-` prefix). A bare or leading number (`2026-08-cleanup`, `123-fix-thing`) doesn't count, and two names giving different numbers means not inferred. When you infer one, say where it came from along with the PR title once fetched, so a wrong guess is easy to spot. If you can't infer one, or no PR has that number (say so), ask: `Which PR should I review? (number, branch name, or URL)`.

## Running commands

- **One command per Bash call.** No loops, `cd &&` chains, or several substitutions in one call; worktree sessions refuse them. Put a loop in a script under the tmpdir.
- **A failed command is "no answer".** An error, non-zero exit, or empty output from a command that errored is never evidence that something is absent or a check passed. Fix an obvious command mistake once, otherwise report "no answer". The exception is a search: `grep`/`git grep` exiting 1 with no output is a real "no match"; exit 2 or an error message is a failure. A command denied by permissions is "blocked by permissions", not an error.
- **Don't poll.** Reviewer subagents notify on completion; no `sleep`, no `ScheduleWakeup`.

## Resolve the PR and gather context

Run `git-platform` for `github` or `ado`. If it prints `unknown`, its stderr says why; rerun from the repo root (or `-C <repo>`), and stop only when the remote itself isn't recognized.

| Operation | GitHub | ADO |
|-----------|--------|-----|
| Show PR | `gh pr view <id> --json number,title,author,body,headRefName,baseRefName,state,headRefOid,isCrossRepository` | `ado-api pr show <id> --json` |
| Linked work items | `gh pr view <id> --json closingIssuesReferences` | `ado-api pr work-item-list <id> --json` |
| List threads | `gh-pr-threads <id> --json --all` | `ado-api pr threads <id> --json --all` |
| Post thread | `gh pr comment <id> --body-file <file>` | `ado-api pr thread-add <id> --body-file <file>` |

A branch name resolves through `gh pr list --head <branch> --json number` or `ado-api pr list --json` (match on source).

A URL also names a repository, and commenting on the wrong remote's PR #N is the failure to prevent. Normalize it and `git remote get-url origin` to bare `owner/repo` (or `org/project/repo`), stripping protocol, host, and `.git`, and compare case-insensitively. A mismatch means stop and tell the user (a fresh worktree against the right remote is the fix). If `origin` is missing or errors, treat it as unknown and ask the user to confirm the repo.

From the metadata take source and target branches, title, author, description, and state. If an inferred number matches no PR, go back to asking. A merged or closed PR proceeds (review is read-only; posting is gated separately); if a merged PR's head can't be fetched, say so and stop. If the PR is the user's own (GitHub: `author.login` against `gh api user --jq .login`; ADO: author email against `git config user.email`), say so and suggest `/mine-review`.

Gather context in parallel, one command per call, without asking about each: linked work items, existing threads, and CI or validation-build status (`gh pr checks <id>`; on ADO `az` with the devops extension), plus any run or build links in the description or threads. An erroring command is recorded as "no answer". This is what the reviewers and the investigation work from: what the PR says it does and fixes, whether CI passed, what has already been raised.

## Fetch and capture the diff

Run from a review worktree. Confirm `git status --porcelain` is clean, fetch the target, and check out the PR head detached so no local branch is touched (on GitHub `gh pr checkout <id> --detach` also handles forks). Then, each in its own Bash call: `mktemp -d <scratchpad>/mine-review-pr-XXXXXX` for `<tmpdir>`; `git diff 'origin/<target>...HEAD' > <tmpdir>/diff.patch`; the same with `--stat`; `git rev-parse HEAD` (the pinned `<sha>`); `git merge-base 'origin/<target>' HEAD` (`<base>`, where the PR branched; the three-dot diff is right for open and squash-merged PRs alike). Write the gathered context to `<tmpdir>/context.md`: description, work items, CI status, run links, and a one-line summary of each thread. Over ~500 files, confirm with the user first.

## Dispatch reviewers and write the overview

Split the changed files by kind: `.md` files are instruction files, everything else is code. Each kind goes to its own reviewers, so a PR with both runs both sets, each with its own diff (`git diff 'origin/<target>...HEAD' -- <that set's files> > <tmpdir>/<code|instruction>.patch`); code reviewers would otherwise judge a skill as code and its instruction quality would go unreviewed. In one message dispatch all the reviewers that apply (three or six parallel `Agent` calls), each given:

```
Review changes. Diff at <tmpdir>/<its patch> (HEAD: <sha>). PR context (description,
linked work items, CI status, existing threads) at <tmpdir>/context.md. Read changed
files for surrounding context. Before relying on the diff, verify HEAD matches <sha>.
This is PR review of someone else's branch. You are reviewing, not fixing.
For each finding, name the command that would confirm or refute it (a test to run,
a query, a grep for consumers, a log to read, a file to check on the target branch).
```

- Code files: `code-reviewer`, `integration-reviewer`, `wtf-reviewer`
- Instruction files: `fine-toothed-comb`, `instruction-quality-reviewer`, `writing-quality-reviewer` (they report blocking/minor; treat blocking as High and minor as Low)

Pass only the gathered context, never your own hypotheses about the PR: a hypothesis anchors reviewers into confirming it instead of reading the code fresh.

While they run, write an overview for the user only, never posted, since the author knows what their PR does. The user needs it to judge the findings, and on a clean PR it is the main output. Read the diff (and files where hunks need context) and compare it with the description, work items, and `git log --oneline '<base>..HEAD'`. Describe what the diff does, not what the description or commit subjects claim: its purpose, its changes grouped by intent rather than file, any mismatch between description and diff (omit if they agree), and the **claims** the PR makes (a root cause, "logic unchanged", "fixes the duplicate rows", "no consumer impact"). Each checkable claim is an item to prove or disprove below, so the PR's own story is tested, not only its lines.

Then wait for all three completion notifications; don't fabricate or predict results.

## Consolidate

Merge duplicates, noting the cross-signal. Judge validity with `${CLAUDE_CONFIG_DIR:-~/.claude}/skills/mine-challenge/findings-protocol.md` (valid by default; likely-invalid needs an evidence trail). That default only keeps reviewers' findings from being discarded on a hunch; the next section sets the bar for what gets presented.

Sort each finding into one thread bucket, because it decides how the author experiences it: a **tests** bucket (one thread for all missing or inadequate coverage, since that's usually one wholesale ask), a **docs** bucket (one thread, same reason), and **code issue** (everything else, one thread per distinct issue, since each is independently resolvable and the author may push back on some). A finding spanning two buckets goes to whichever the repo's rules enforce more strictly. Only Medium-and-above code issues get their own thread; fold Low findings and nits into an adjacent thread or drop them, since a minor point as its own thread on someone else's PR reads as nagging.

## Prove or drop (do not skip)

For each surviving finding and PR claim:

1. **Check what's already known.** Read the file at HEAD, not the patch (line numbers drift and a duplicated block may be fixed). Drop a finding that duplicates an existing thread from any author: same file:line, or same construct if lines drifted, and the same underlying concern, not merely the same topic. A duplicate of a *resolved* thread stays if the issue is still present at HEAD. The attribution footer identifies this skill's own prior comments but doesn't gate dedup. Drop or reframe anything calling something "undisclosed" or "unexplained" that the description already says; that is the commonest false positive, and posting it tells the author their description wasn't read.
2. **Introduced or already there.** For each Medium-and-above finding, ask whether the issue would exist if the PR never merged, checking at `<base>` with read-only `git show` or `git grep` (never check out `<base>`). If the PR introduced it, or copied, extended, or worsened an instance, it's a finding. If it's at `<base>` and the PR touches that code, it's a finding with the "while you're in here" label from `REFERENCE.md`. If it's at `<base>` and the PR neither touches nor worsens it, it's a tracker candidate for the user, not drafted.
3. **Investigate.** Run the check that proves or disproves each remaining Medium-and-above finding and claim, starting from the command the reviewer named: run the tests, query built output, look up real consumers, read CI logs, check history. Follow up on whatever comes back unknown until you can state the impact and one concrete fix, or it's clear no executable check applies. The repo's `CLAUDE.md` and rules say how to query its systems. Check claims about consumers, schedules, or coverage against the live system, never a repo doc, which goes stale. Re-reading the PR's own code is not a check at this severity; a grep for the other copy, a consumer lookup, or a test run is. Low findings and nits get only the step 1 re-read.

   You may run read-only commands, scratch files in the tmpdir, and the PR's tests when they write nothing outside the worktree and tmpdir (unit tests; not `dbt run`/`build`, not integration tests hitting real services). PR tests run PR-authored code with your credentials, so run them only on teammates' PRs, never forks (`isCrossRepository`). A reviewer-named command is a suggestion; run it only if it fits this scope. Never run DML or any database or external-service write: a check needing one becomes an open question with the command written out for the user.
4. **Record the outcome.** Each surviving finding carries an `Evidence:` line quoting the command run and the part of its output that settles it. Say "verified", "confirmed", or "proven" only when that line names something run. A finding about naming, design shape, or prose may have none: its line reads `judgment: <the reasoning>` and is never called verified. A finding about runtime behavior, consumers, or coverage is never judgment-only: run its check or make it an open question. Set severity from the impact the investigation proved, not the reviewer's estimate. A confirmed claim is noted in the overview; a disproved claim becomes a High code-issue finding unless a thread already raises it. Evidence that refutes a finding drops it. A Low folded into a host thread that was dropped folds into another surviving thread or is dropped.

A finding becomes an **open question** only when its settling check can't be run here (it needs the author's intent or access this session lacks), was blocked by permissions, or errored. A runnable check you skipped is unfinished work. Each open question states what was tried, why it didn't settle, and the one check that would.

## Report and shape the set

Show: the **overview** with confirmed claims noted, plus a **riskiest merge decision** line (the one thing most likely to hurt if this merges as is, and your recommendation; omit if none); **findings** grouped by severity, each short, with severity, bucket, label (`Blocking` / `Non-blocking`, defaults in `REFERENCE.md`), the gist, evidence cut to the command and a one-clause result (full output belongs in the draft), any folded Lows, and for a pre-existing issue its routing and one-line reason; **open questions for you**; and **tracker candidates** with where each lives.

If nothing survived, show the overview, say so, and stop. If only open questions or tracker candidates survived, show the report and stop; the user replies in free text if they want anything done. Otherwise ask:

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

"Change the set first" takes free text: drop or add findings, flip a label, dig further (back through investigation for that item), or post an open question to the author (question form in `REFERENCE.md`). Apply it, show the changed entries, and ask again.

## Draft comment threads

One draft per thread in the shaped set (each Medium-and-above code issue, the tests bucket, the docs bucket, folded findings inside their host), using the template, labels, and footer in `REFERENCE.md`. Write each body to its own temp file under the tmpdir. Show every draft's full body with `SendUserMessage`, in one message, before the post gate; never titles or paths alone, and not via a `Read`, which the terminal collapses. The user approves what they have read.

## Confirm, then post

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

Never post without this confirmation. On "Edit some first", show each changed body in full again before asking again.

On approval, first confirm the PR's head on the platform is still `<sha>` (a local ref only compares the earlier fetch to itself). If it moved, the author pushed mid-review: tell the user what changed and let them choose to post, re-review, or stop. If you can't confirm the head, say so and ask the same way.

Then post each draft with the platform command from the table (`--body-file`, to avoid shell quoting problems) and report the thread IDs. If a post fails, report which one and don't retry blind: a post that errored after landing would double-post.

## What This Skill Does NOT Do

- **Edit the PR author's code.** Read-only, always.
- **Write to databases or external services.** Checks that need a write are handed to the user.
- **Review your own PR.** Use `/mine-review`.
- **Deep codebase audit.** Use `/mine-audit`.
- **Exhaustive style sweep.** Use `/mine-clean-code`.
