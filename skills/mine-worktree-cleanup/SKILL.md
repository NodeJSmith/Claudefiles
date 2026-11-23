---
name: mine-worktree-cleanup
description: "Use when the user says: 'clean up worktrees', 'we have a ton of old worktrees', 'prune stale worktrees', 'which worktrees can I delete', 'clean up old branches', 'delete stale local branches'. Works out which of a repo's git worktrees and leftover local branches are finished, describes anything that exists only in one of them, and removes the ones the user approves."
user-invocable: true
---

# mine-worktree-cleanup

Worktrees pile up, one per task, review, or subagent, and so do local branches nothing has checked out, often left behind when a worktree is removed without its branch. The goal is to get the repo down to the worktrees and branches that still hold something, without deleting anything the user would want back.

A worktree or branch is finished when its work exists somewhere that stays: its PR merged (or was closed on purpose) with nothing committed after it, and it has no uncommitted, untracked, or gitignored files that matter. Anything short of that gets looked at before it goes. When content exists only in one worktree, the user decides from what it is, not from its file names.

## Arguments

$ARGUMENTS — optional repo path (default: the current repo).

## Done looks like

- Every worktree the user approved is gone, with its local branch, and `git worktree list` confirms it.
- Every leftover local branch the user approved is gone, and `git branch` confirms it.
- Every worktree and leftover branch left has a reason the user has seen.
- Nothing that existed only in one worktree or branch, whether files or commits, was removed unless the user saw what it was and said to remove it.

## Gathering the facts

`git-worktree-audit -C <repo>` lists each worktree's PR and its state and author, whether the tip is still the PR's last commit, its commits ahead of the default branch, its uncommitted, untracked and gitignored files (skipping rebuildable caches), whether its remote branch exists, how long since it was last used, and whether a process is running inside it right now. Add `--json` for the file lists and the PR author. Its `branches` section (a second table in text mode) gives the same PR, tip and ahead facts for local branches no worktree has checked out. It reports facts and makes no verdicts. Most worktrees and branches settle on these facts alone: a merged PR at its tip with a clean tree is done, a branch with nothing ahead of the default branch is done, and an open PR stays.

For the rest, read the untracked and ignored files and say what they are, for example "July outage queries against hardcoded sandbox tables." Check whether commits after the PR, or a branch with no PR, made it to the default branch some other way. Squash merges hide this from ancestry and commit subjects, so look for the change itself in the default branch's code; a subagent's branch usually landed through its parent branch's PR. Check whether two worktrees hold the same notes, and if so which one is the superset. A worktree used in the last few days may be a parked session even with no process inside it, and one outside the repo may belong to a tool that expects it to be there.

## Contract

- Show the findings with `SendUserMessage` before asking anything: what's finished, what you looked into and found, and what's staying and why. Then ask with `AskUserQuestion`.
- Remove only what the user approved, with `git-worktree-audit -C <repo> remove --delete-branch <path>...`. It removes nested worktrees before their parents and refuses a parent whose nested worktree wasn't also selected. Without `--force`, git refuses any tree that still has uncommitted or untracked files, but it deletes gitignored files without asking, so those need the user's eyes first like anything else that exists only there. Add `--force` only for trees whose remaining content the user has seen and agreed to lose, including copies that exist elsewhere and noise like a regenerated cache. `--delete-branch` force-deletes the branch, so commits that aren't in a merged or closed PR and never reached the default branch need the user to have seen them too. Removing large trees takes a while, so run it in the background.
- Delete approved leftover branches with `git -C <repo> branch -D <name>...`.
- Deleting remote branches changes shared state, so it needs its own yes. Name whose branch each one is, because review worktrees often track a colleague's branch.
