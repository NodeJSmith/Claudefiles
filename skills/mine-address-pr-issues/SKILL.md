---
name: mine-address-pr-issues
description: "Use when the user says: \"address PR comments\", \"fix review feedback\", \"fix failing CI\", or \"resolve merge conflicts\". Triages and resolves PR blockers on GitHub or Azure DevOps."
user-invocable: true
---

# Address PR Issues

Get a PR unblocked: every unresolved review comment answered or fixed, merge conflicts resolved, CI failures fixed. Works on GitHub and Azure DevOps.

```
/mine-address-pr-issues [PR#]
```

With no PR number, detect it from the current branch.

Replies, resolved threads, and pushes are visible to reviewers and hard to take back, so nothing is posted or pushed until the user has approved the plan and the fixes have passed local tests and review. Three failures are worth guarding against:

- **Explaining away a failure.** A failing test or CI check means the code is wrong. Never call it flaky, outdated, or expected; fix the code, or escalate after three honest attempts.
- **Fixing before understanding.** Read the file and the reviewer's intent before editing, and the callers as far as the fix's depth calls for. A fix that changes line Y without knowing why Y exists breaks Z.
- **Pushing before testing.** Run the project's tests locally after each fix and before any push; a push-and-see loop wastes CI cycles and clutters history.

## Fetch and detect

`git-platform` prints `github`, `ado`, or `unknown`. On `unknown`, read its stderr: if it points at the wrong directory, rerun from the repo root (or `-C <repo>`); stop and tell the user only when the remote itself isn't recognized.

Create a run directory with `mktemp -d <scratchpad>/mine-address-pr-XXXXXX` (`<tmpdir>` below) and save the feedback there; the ledger and plan files live beside it.

**GitHub**

- Metadata: `gh pr view {PR} --json number,title,url,author,baseRefName,headRefName,mergeable,mergeStateStatus,statusCheckRollup,isDraft,reviewDecision`. The PR author is `author.login`. `mergeable` is computed asynchronously, so if it's `UNKNOWN`, retry up to 3 times (3s, 6s, 12s) and then warn and continue.
- Feedback: `gh-pr-threads {PR} --json --all > <tmpdir>/feedback.json`. `gh pr view` doesn't return review threads, so this is the only way to know whether review comments exist. All three surfaces need triage:
  - `.threads`: inline review threads, resolvable (`PRRT_…` id, `isResolved`, `isOutdated`, `path`, `line`, `comments` with `databaseId`, `body`, `author`).
  - `.reviewComments`: review bodies. Some carry findings that aren't inline threads (CodeRabbit's "Outside diff range", "Duplicate comments", "Nitpick comments"). Not resolvable; answer with a PR comment.
  - `.issueComments`: conversation comments, including CodeRabbit's walkthrough, whose pre-merge checks can report failures. Not resolvable.
  - `.excluded` lists known noise the tool dropped. Resolved threads are kept on purpose: they're the earlier rounds the ledger compares against.
- CI: failing entries in `statusCheckRollup` (`conclusion` of `FAILURE`, `TIMED_OUT`, `ACTION_REQUIRED`); logs via `gh run view <run-id> --log-failed`.

**ADO**

- Metadata: `ado-api pr show {PR} --json` (`id`, `title`, `status`, `author` (the PR author's `uniqueName`), `source` and `target` (branch names), `url`, `sourceCommit`). `mergeStatus` is null until ADO has attempted the merge.
- Feedback: `ado-api pr threads {PR} --json --all > <tmpdir>/feedback.json`. One list of threads (`status` `active` or `pending` is open) that includes general conversation; there is no `isOutdated`.
- CI: `az repos pr policy list --id {PR_ID} -o json`, filtered to `rejected` or `broken`; logs via `ado-api logs read <build-id> --failed --issues`.

Mention, as warnings and not blockers, a draft PR (not mergeable until ready for review) and `reviewDecision == CHANGES_REQUESTED` (the reviewer still has to re-approve).

## Triage and plan

Three groups: review comments, merge conflicts, CI failures. Categorize CI failures from their logs (tests, lint/types, build, other).

### Review comments: the ledger

The point of the ledger is to see all feedback side by side, resolved history included, because findings that keep landing on one mechanism show up only that way. Rounds of local patches can be hardening a design that should be reconsidered, and no single finding reveals it. `ledger-procedure.md` defines the format and `bin/pr-ledger-check` verifies it.

History matters as much as threads: if the PR builds a sketch ledger, that feature directory's `review-log.jsonl` and `known-issues.md` (found through the PR's changed files, e.g. `design/specs/<n>-<name>/`) are earlier rounds, and a mechanism a challenge already patched twice is the clearest convergence there is. Collect the ones that exist and pass their paths to the subagent below.

A convergence doesn't need multiple rounds: one round whose findings share a mechanism counts. Build the ledger unless convergence is plainly impossible (a couple of unrelated findings, or a round of only typo and docs fixes); with history files present, a thin PR doesn't rule it out.

Skip the ledger when convergence is plainly impossible or there is no feedback at all, open or resolved (then the plan covers only conflicts and CI). Resolved-only feedback still gets the ledger: an all-resolved convergence is the pattern it exists to catch. Either way the plan is still shown and approved; only how it is built changes. Say why in one line, triage by hand, and build the plan and response list by hand in the same shape: every open item gets an entry and a response, and a thread an earlier run already replied to only needs resolving. Hand-built replies carry the same markers (see Responses). Leave out every `ledger.json`/`plan.json` step below.

Steps, in this order:

1. `pr-ledger-check init <tmpdir>/feedback.json <tmpdir>/ledger.json --pr-author <PR author>` writes the skeleton, with everything derivable from the feedback filled in.
2. Dispatch a **`deep-worker`** subagent (the triage and convergence judgment is what most needs the deep tier) with this prompt:

   > Build the review-feedback ledger for PR #{N} ({platform}). Read `${CLAUDE_CONFIG_DIR:-~/.claude}/skills/mine-address-pr-issues/ledger-procedure.md` and follow it exactly.
   >
   > - Review feedback: `<tmpdir>/feedback.json`
   > - The repository is the current working directory, at the PR's head. Read code as needed; do not modify files or run git commands that change state.
   > - History files (earlier ship-time challenge findings and known issues; add history rows per the procedure): `<paths, or "none found">`
   > - Skeleton ledger to fill in place: `<tmpdir>/ledger.json`

3. `pr-ledger-check check <tmpdir>/feedback.json <tmpdir>/ledger.json`. Exit 1: re-dispatch `deep-worker` with the output to fix the ledger until it passes. After two failed rounds, show the user the remaining problems and stop, since an incomplete ledger means feedback goes unaddressed unnoticed.
4. `Read` the ledger; everything below draws on it.

### Convergence gate

If the ledger has `convergences`, stop here, before planning or fixing anything, conflicts and CI included: a structural problem can make other fixes moot, and a redesign changes what the conflicting or failing code even is.

Show each convergence (its `mechanism`; members one per line with finding, round, and outcome or open status; `summary`; `open_questions`). The open questions are for the user to weigh; don't answer them or propose a redesign. Then ask how to proceed. The outcomes on offer: check prior art then discuss, stop and discuss, or patch the findings individually. Recommend prior art when the mechanism is one comparable projects face, per `${CLAUDE_CONFIG_DIR:-~/.claude}/skills/mine-prior-art/SKILL.md` (Invoking From a Convergence Gate); if the mechanism is internal, drop that option and recommend discussing.

- **Prior art:** invoke `/mine-prior-art` on the topic that section describes, then continue as for discussing, opening with the brief's recommendation.
- **Discuss:** make no code changes, commits, or replies until every convergence is decided. The discussion can take many turns and pull in `/mine-prior-art` or `/mine-challenge`; settling one can show it was never a real convergence.
- **Patch individually:** continue, and note in the summary that it was by choice.

Once the user has decided, even with a bare "go ahead", don't implement straight from the discussion: the plan has to come from the updated ledger, or the fixes skip the plan review, the ledger check, and CI triage. This run posts the replies, so don't tell the user to re-run. Re-read the ledger, update it to match each decision, run `pr-ledger-check check` until it passes, then continue to conflict and CI triage and the plan. The gate doesn't repeat for these convergences.

- Leave `mechanism` and `convergences` alone (`check` matches members by label).
- Rewrite `root_cause`, `proposed_fix`, `fix_adds`, `depth`, and `decision` on every open row whose fix changed. Set `decision` to `null` once settled, or the plan asks again. A row that becomes `not-actionable` needs `depth` and `decision` `null`.
- *Redesign:* members whose local fix the redesign replaces stay `actionable` with the redesign as the fix, so their threads get a reply when it lands. If every member is already resolved, there's no thread to answer: add the redesign to the plan by hand as one extra item and name it in the summary.
- *Accept the limitation:* members become `not-actionable`, with `disposition_reason` citing where the limitation is documented; if it isn't, keep one member `actionable` with documenting it as the fix.
- *Not a real convergence:* leave the rows as they were.

Two outcomes end the run with no replies: the user abandons or replaces the PR, or the redesign is big enough to settle in `/mine-sketch` first. Say which threads stay open and why.

### Merge conflicts

GitHub: `mergeable == "CONFLICTING"` or `mergeStateStatus == "DIRTY"`. ADO: `mergeStatus == "conflicts"`.

Pick merge or rebase from the repo's own convention (merge commits from base on the branch, linear history on base, whether linear history is required) and say in one line which signal decided it. What needs care is the force-push a rebase implies: a branch under review is shared by default, since reviewers or CI may have fetched it. Treat it as private only when every commit is the user's and no review round has fetched it, and always push with `--force-with-lease`. Ask only when the signals conflict, or when the repo wants linear history but the branch is shared.

### The plan

Build it mechanically: `pr-ledger-check plan <tmpdir>/feedback.json <tmpdir>/ledger.json > <tmpdir>/plan.json`. It walks every open row once: `entries` (one per open row carrying a concern, with `also_answers` for the duplicates answered along with it), `responses` (every reply and PR comment the Responses step will post), and `unanswered` (open rows getting no response, with reasons). Resolved rows are history and appear nowhere. Look up each row's other fields in the ledger by id.

Show the full plan before asking anything, because the user can't judge a plan they haven't seen. Open with one count line (`counts`, or your own tally without a ledger): "Ledger: N open items — A actionable, B already addressed, C not acting on, D duplicates answered with them." Number the items and group actionable entries under their `mechanism` (a group is fixed together). Each item gives the reviewer's concern (`finding`), the proposed fix, its depth, the response (reply and resolve, reply only for a human reviewer's thread, resolve only when an earlier run replied but the resolve failed, or a PR comment), and `also_answers`. Mark rows with a non-null `decision` as `[DECISION NEEDED]` with its `why`, `options`, and `recommendation`. List separately, so dismissals are visible, the already-addressed entries with their evidence, "Not acting on" with reasons, and "No reply" rows with reasons. Include what else goes out on the same approval: CI fixes, and the merge or rebase chosen above, including the `--force-with-lease` push a rebase implies. Include the draft and changes-requested warnings.

Then ask, and wait for the answer before changing anything: no merge, rebase, or fix runs first. Options: approve (recommended; accepts the recommendations on `[DECISION NEEDED]` items), adjust items, or cancel. For an adjusted item, ask what they want instead and update the plan entry. Cancelling ends the run with no changes.

## Execute

Fixes and their tests have to run on the code that will be pushed, so the order is: merge or rebase, CI fixes, group fixes, review over all of it, commits, one push.

### Merge or rebase, then CI fixes

Conclude the approved merge or rebase first, on a clean tree, committing it as git does (a rebase makes its commits as it runs; an unfinished merge would swallow every later fix into its commit). Then apply the CI fixes, running tests after each; those fixes stay uncommitted until review.

### Fix each group, serially

Per group, launch a **`standard-worker`** subagent giving it the comments (bodies, paths, lines), the root cause (the row's `root_cause`, or your triage), the approved fix, any resolved decision, the deepest `depth` among the group's rows so none is under-investigated, and an output path `<tmpdir>/group-N/result.md`. Tell it:

- Investigate until you know what this change could break, to the depth given: `light` (the target file is enough), `medium` (callers matter), `deep` (the contract itself is in question).
- Apply the fix, then run the project's test suite (discovery order in `references/common/testing.md`). On failure, revise the fix; three attempts, then escalate.
- Give it the failure modes listed in the opening section, plus never skipping a test or marking it as an expected failure.
- Put a one-line summary first in the output file, details below.

Read only the first line of each result file, which keeps worker output out of your context; read the rest when the summary reports an escalation or failure.

### Review, then commit and push

Run **code-reviewer** on everything this run will push: the committed conflict resolution (for a merge, `git show --remerge-diff`) plus the uncommitted fixes. Auto-fix unambiguous CRITICAL/HIGH findings, deferring judgment calls to the user. Re-run it after fixes (at most 3 rounds, unless the fixes all fall under the skip criteria in `git-workflow.md`, Code Review Before Commit), then run **integration-reviewer** once on the final diff. Make no further commits until both pass; if CRITICAL/HIGH findings remain after 3 rounds, present them to the user first.

Then commit per logical group with descriptive conventional messages, and push once after all commits so the single push carries all of it.

### Responses

Only after the push is confirmed (or you know there was nothing to push), act on every item in `plan.json`'s `responses` (or the hand-built list), in order. The plan already covers every open row and leaves out what earlier runs finished, so act exactly on it. Each item says what's needed: post one message when `reply` is true (one line per entry in `lines`), and resolve the thread when `resolve` is true. They are separate calls: `reply` false with `resolve` true is a thread an earlier run replied to but didn't resolve, so resolve without posting again. Drop lines for rows the user skipped; if all of an item's lines are dropped, post nothing and resolve only when `reply` is false.

Wording follows each line's `answer`; `with` names the row carrying the concern, so link it.
- `fixed`: "Fixed — [what changed]." With `with`: "Fixed together with [link] — [what changed]."
- `already-addressed`: "Already addressed — [evidence from the carrying row's `disposition_reason`]." If the code is gone: "The code at this location was refactored and this concern no longer applies."
- `not-acting`: "Not planning to change this — [the carrying row's `disposition_reason`]."

A `pr-comment` item answers a body or conversation comment, which has no thread: link the item in `about` and start each line with the finding it answers so it reads alone. End every message with the item's `marker` (on the hand-built path: `<!-- addressed-pr-issues -->` for a thread reply, `<!-- addressed-pr-issues:X -->` for a PR comment, where `X` is the URL of the comment answered). A re-run uses markers, counted only at the very end of a message, to know feedback was answered and to tell this skill's comments from new feedback: a thread is answered only if a marker reply exists and nobody but the PR author commented after it; a PR comment is answered when a marker names its URL.

| `channel` | GitHub | ADO |
|---|---|---|
| `thread`, `reply` true | `gh-pr-reply {PR} {comment_id} --body-file <tmpdir>/response-N.md`, plus `--resolve {thread_id}` when `resolve` is true | `ado-api pr reply {PR} {thread_id} --body-file <tmpdir>/response-N.md`, then `ado-api pr resolve {PR} {thread_id}` when `resolve` is true |
| `thread`, `reply` false | `gh-pr-resolve-thread {thread_id}` | `ado-api pr resolve {PR} {thread_id}` |
| `pr-comment` | `gh pr comment {PR} --body-file <tmpdir>/response-N.md` | not produced (ADO carries all conversation in threads) |

Write every body to its `<tmpdir>/response-N.md` first, so backticks in a reply never reach the shell.

`resolve` is true for open threads raised by a bot or the PR author. A human reviewer's thread gets the reply only, so they can verify the change and resolve it themselves. Wait 1 second between mutating API calls.

## Summary

Report what happened so the user can verify it: review comments (threads resolved, human threads replied to and awaiting the reviewer, PR comments, already-addressed, not-acting with ledger reasons, no-reply with reasons, and each convergence with what was decided), merge conflicts (files, merge or rebase), CI fixes (and that CI re-runs on push), the commits, and anything needing manual review.

## Tools and errors

Use the helper scripts, not inline API calls; they handle auth, pagination, and output. `gh-pr-threads`, `gh-pr-reply`, `gh-pr-resolve-thread`, `git-platform`, `ado-api pr` (show/list/create/update/threads/reply/resolve/resolve-pattern), `ado-api logs read`, `ado-api work-item`, and `pr-ledger-check` (`init`, `check`, `plan`) all take `--help`.

Auth failure: suggest `gh auth login` or `az login`. Rate limiting: tell the user and suggest waiting. No PR found: ask for a number. GitHub GraphQL permission errors: suggest `gh auth refresh -s repo`.
