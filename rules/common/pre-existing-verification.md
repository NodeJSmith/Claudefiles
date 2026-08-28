---
tool: claude, antigravity
---

# "Pre-existing" Means Verified Against the Default Branch, Nothing Else

"Pre-existing," "baseline," "already broken," and "predates this change" get used as if they all point at the same reference: the repo's default branch (`main`, `master`, or whatever it's actually called — resolve it, never assume the name). They don't. Each of these is also routinely used to mean something narrower — the state before your own uncommitted edit, an orchestration run's captured starting point, an earlier commit on the same branch — and none of those prove the thing is actually on the default branch. Asserting the narrow claim while implying the broad one lets a regression you (or an earlier task in the same session) introduced get waved off as unrelated debt.

## The Failure Mode

A debugging session hit a test failure, `git stash push`'d its own uncommitted fix to get a clean before/after, reran the tests, and declared: "Confirmed — pre-existing on baseline too." That "baseline" was the stash — the state before that one edit, several commits into the same feature branch. The session used the same word again later to mean "at commit X, end of an earlier task" — still not the default branch. The bug was eventually traced to the session's *own* earlier commit from a few tool calls before. It only surfaced because the user asked directly, "was this on main or introduced in this branch?" — forcing an actual check that reversed the conclusion. The same pattern repeated later in the *same* session on a different failure set. Getting caught once didn't stop it from recurring — which is why this needs a check, not a reminder to be more careful.

## The Rule

When "pre-existing," "baseline," "already broken," or "doesn't need fixing here" is being used to claim a failure or issue predates the current change — in a report, a commit message, or a reply to the user — verify it against the actual default branch first, not against whatever reference point is closest at hand (a stash, an orchestration run's `base_commit`, an earlier commit on this same branch, "the file before I touched it"). This does not cover routine uses of "baseline" as a captured measurement snapshot unrelated to blame — an orchestration test/lint baseline, a screenshot baseline, a performance trace captured before an operation. Those aren't claims about the default branch and don't need this check.

**Never mutate the current working tree or index to run this check.** No `git stash`, `git reset`, `git checkout <default-branch>`, or switching the worktree's branch — ever, for this purpose alone. This has cost real work before: a stash or reset done to "just peek at main" can lose uncommitted changes if something goes wrong on the way back. Every command below is read-only and never touches the working tree or index.

**If you're in a worktree** (the common case — see `worktrees.md`), prefer reading straight from the main repo clone instead of anything in the current worktree:

```bash
git -C <worktree> worktree list          # first entry is the main clone's path
```

If that main clone is checked out to the default branch **and has a clean working tree** (check first — a dirty working tree means `Read`/`Grep` would show uncommitted edits, not the default-branch commit), `Read`/`Grep` the file there directly, or run:

```bash
git -C <main_repo_path> status --porcelain=v1 --untracked-files=all   # must be empty
git -C <main_repo_path> show HEAD:<path-relative-to-repo-root>
```

**Otherwise** — no separate main clone, it's not on the default branch, or its working tree is dirty — use read-only plumbing against the resolved default-branch ref, from the current worktree, without switching anything. Use `git-default-branch`, not `git-branch-base`: `git-branch-base` resolves the *closest* branch (fewest commits ahead of HEAD) for diff-scoping purposes — on a stacked branch that's a parent feature branch, not main, which silently defeats this exact check.

```bash
git-default-branch                                                              # resolves the actual default branch name ("main", "master", whatever it is)
git fetch origin "$(git-default-branch)" 2>/dev/null || true                   # refresh the remote-tracking ref before relying on it — read-only, doesn't touch the working tree. A failure here (offline, no origin) is not fatal: the diff/show fallbacks below still work against the last-known local ref
git diff "origin/$(git-default-branch)" -- <path> 2>/dev/null || \
  git diff "$(git-default-branch)" -- <path>                                    # empty output = genuinely unchanged since the default branch, IF <path> is tracked (see caveat below)
git show "origin/$(git-default-branch)":<path> 2>/dev/null || \
  git show "$(git-default-branch)":<path>                                       # read the file as it exists on the default branch
```

If `<path>` is untracked (`git status --porcelain -- <path>` shows `??`), the `git diff` check above cannot tell you anything — `git diff` is silent for untracked paths regardless of whether they've "changed," so there is nothing on the default branch to compare against by definition. Treat it as unverified/new rather than "unchanged."

If you have not run one of these, you do not get to say "pre-existing." Say what you actually verified instead — "not touched by my uncommitted edit," "unchanged since the start of this run," "present at an earlier commit on this branch" — each is a real, narrower claim, and none of them means the default branch.

## When This Applies

Any time a claim about "not my problem" or "not new" would change what gets fixed and what gets left alone: debugging a test failure, reviewing a diff, closing out an investigation, writing a "Pre-existing Issues" section in a review report, deciding whether a regression blocks a task in `mine-orchestrate`. Mid-session recurrence is expected — re-run the check every time the claim is about to be made, not just the first time.

## Orchestration-Specific Note

`mine-orchestrate`'s `base_commit` is captured at the start of the current run (HEAD before any task executes), specifically so the run's own diff stays clean of unrelated prior commits — see `skills/mine-orchestrate/SKILL.md`. It is a real and useful reference point for *regression-within-this-run* detection (test/lint gates), but it is not the default branch, and a branch can already be many commits past the default branch when a run starts (a resumed run, a branch with prior manual work). A finding that is "pre-existing relative to `base_commit`" has not been checked against the default branch — say so, or run the check above before reporting it to the user as settled debt.
