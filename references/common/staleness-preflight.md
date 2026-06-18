# Branch Staleness Pre-flight

Catches the "I forgot to pull latest before starting" mistake before work commits to a stale base. Callers invoke this in one of two **modes** and supply a **stakes** sentence describing why staleness bites at their stage.

- **`gate` mode** (plan, orchestrate) — staleness is expensive to unwind later, so when behind, offer to fix it before proceeding.
- **`soft` mode** (define) — the artifact is forgiving prose; surface staleness but don't force a stop.

If a caller passes any mode other than `gate` or `soft`, treat it as `gate` (the more conservative) and note the unknown mode.

## Check

```bash
git-branch-behind --json
```

Read `behind`, `fetch_ok`, and `current` from the JSON.

**First, handle detached HEAD** (this governs all outcomes): if `current` is empty, a rebase isn't meaningful — surface "detached HEAD — staleness not actionable here", then:

- `gate` mode **and** `behind` > 0 → present a 2-option Proceed / Abort question (no Rebase) and act on it.
- otherwise (`behind` is 0 or null, or `soft` mode) → surface the message and proceed; do not stop.

Otherwise branch on `behind` — **check these in order**, because an earlier case must not mask a later one:

- **`behind` is `null`** — could not compare (no `origin/<default>` ref at all: fresh clone, or never fetched). This is a *maximally stale* state, not a clean one — never read it as up to date. Surface "couldn't verify staleness — no `origin/<default>` ref" and proceed.
- **`behind` is `0` and `fetch_ok` is `true`** — up to date. Proceed silently.
- **`behind` is `0` and `fetch_ok` is `false`** — up to date *against the last-known ref*, but the fetch didn't refresh it. Emit one line — "up to date against last-known state; couldn't refresh origin" — and proceed. Do not claim a clean verified state.
- **`behind` > 0** — the branch is missing commits from the default branch. Surface it (below). If `fetch_ok` is `false` here, the count is real but computed against a ref that wasn't refreshed this run — the stale-ref guard in the Rebase section handles that honesty before any rebase.

**Never block on a network failure** — a failed fetch degrades to a caveat, never a hard stop.

## When behind

Substitute the actual `base_ref` and `behind` values from the JSON into the question before calling `AskUserQuestion` — do not present the literal `<base_ref>`/`<behind>` placeholders.

Option set by mode:

- **`gate`** — 3 options: Rebase / Proceed anyway / Abort.
- **`soft`** — 2 options: Rebase / Proceed anyway. No Abort.

```
AskUserQuestion:
  question: "This branch is behind <base_ref> by <behind> commit(s). <stakes>"
  header: "Stale base"
  multiSelect: false
  options:
    - label: "Rebase onto <base_ref>"
      description: "I'll rebase this branch onto the latest default branch first"
    - label: "Proceed anyway"
      description: "Run against the current (stale) base — I understand the risk"
    - label: "Abort"                 # gate mode only — omit in soft mode
      description: "Stop so I can sync manually"
```

`<stakes>` is the caller-supplied sentence (e.g. "Task files generated now will reference paths from stale code.").

## Acting on the choice

**Rebase** — three guards, in order:

1. **Dirty-tree check.** Run `git status --porcelain`. If it prints anything, the working tree has uncommitted changes — these skills run in worktrees where that's common. Do **not** rebase a dirty tree (git will refuse, or silently autostash and risk conflict markers in unsaved work). Instead, list the changed files and tell the user "Commit or stash these first, then choose Rebase." Re-present the original question's options minus Rebase (Proceed / Abort in gate mode, Proceed in soft mode) and act on that choice.
2. **Stale-ref honesty.** If `fetch_ok` is `false`, the rebase target wasn't refreshed this run — rebasing onto it may not reach the true latest. Confirm before running it: present a 2-option question — "Rebase onto last-fetched `<base_ref>` anyway" / "Don't rebase — proceed against the current base". Only continue to step 3 if they pick "rebase anyway"; otherwise proceed against the current base.
3. **Rebase + verified recovery.** On a clean tree, run `git rebase <base_ref>`. On success, proceed. If it exits non-zero, first determine whether a rebase is actually in progress — a rebase can also fail to *start* (bad ref, pre-rebase hook), which leaves the tree unchanged. Check with `git rebase --show-current-patch`: exit 0 means a rebase IS in progress, non-zero means none is (this inverts the usual shell convention, and it's worktree-safe unlike checking a `.git/` path). Then:
   - **Not in progress** (failed to start): report the original error verbatim; the tree is unchanged — do not claim a mid-rebase state or run `--abort`.
   - **In progress** (conflicts): run `git rebase --abort`, then check its exit code. Abort succeeded → "Rebase hit conflicts and was aborted — resolve manually, then re-run." Abort failed (non-zero) → "Rebase abort FAILED — the worktree is mid-rebase. Do NOT re-run; run `git status` / `git rebase --abort` manually first." Stop.
   Never attempt to auto-resolve conflicts.

**Proceed anyway** — continue against the current base.

**Abort** (gate mode only) — stop here.
