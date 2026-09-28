---
name: mine-address-pr-issues
description: "Use when the user says: \"address PR comments\", \"fix review feedback\", \"fix failing CI\", or \"resolve merge conflicts\". Triages and resolves PR blockers on GitHub or Azure DevOps."
user-invocable: true
opencode-command: true
---

# Address PR Issues

Triage and resolve everything blocking a PR from merging: unresolved review comments, merge conflicts, and failing CI checks. Works on both GitHub and Azure DevOps — detects the platform automatically.

## Usage

```
/mine-address-pr-issues [PR#]
```

If no PR number is given, auto-detect from the current branch.

## Phase 1: Fetch & Detect

### Platform detection

```bash
git-platform
```

Output is `github`, `ado`, or `unknown`. If `unknown`, tell the user the platform could not be detected from the git remote and stop.

### PR metadata

**GitHub:**

```bash
gh pr view {PR} --json number,title,url,author,baseRefName,headRefName,mergeable,mergeStateStatus,statusCheckRollup,isDraft,reviewDecision
```

The PR author is `author.login`.

If `mergeable` is `UNKNOWN`, retry up to 3 times with backoff (3s, 6s, 12s) — GitHub computes mergeability asynchronously. If still `UNKNOWN` after retries, warn the user and continue.

**ADO:**

```bash
ado-api pr show {PR} --json
```

Returns `pullRequestId`, `title`, `status`, `author` (the PR author's `uniqueName`), `sourceRefName`, `targetRefName`, `repository.webUrl`. URL: `repository.webUrl + "/pullrequest/" + pullRequestId`. Note: `mergeStatus` is optional and only present after a merge attempt.

### Review threads & non-thread comments (separate from metadata)

`gh pr view --json` does not return review threads (inline comments from reviewers or Copilot), so PR metadata alone can't tell you whether review comments exist. Run the fetching command below, saving its output for the Phase 2 ledger in a temp directory:

```bash
get-skill-tmpdir mine-address-pr
```

Use the printed path as `<tmpdir>` for the rest of the run.

**GitHub:**

```bash
gh-pr-threads {PR} --json --all > <tmpdir>/feedback.json
```

Returns a JSON object with three surfaces — **all three need triage** — plus `.excluded`:

- `.threads` — inline review threads (resolvable). Each has `id` (`PRRT_…`), `isResolved`, `isOutdated`, `path`, `line`, `startLine`, `diffSide`, and `comments` (with `databaseId`, `body`, `author.login`, `author.__typename`).
- `.reviewComments` — every non-empty review body. Some carry findings that are **not** inline threads: CodeRabbit posts substantial findings here ("Outside diff range comments", "Duplicate comments", "Nitpick comments") when it can't anchor to the diff. **Not resolvable** — no `PRRT_` id; reply with a normal PR comment. Each has `author`, `state`, `url`, `body`.
- `.issueComments` — PR conversation comments (human comments, bot replies, and CodeRabbit's walkthrough, whose pre-merge checks can report failures). **Not resolvable.** Each has `author`, `databaseId`, `url`, `body`.

`.excluded` lists the known-noise messages the tool left out (Codecov reports, Codex status tables, review triggers), each with its reason. Resolved threads are kept on purpose: they are the earlier review rounds the Phase 2 ledger compares new findings against.

**ADO:**

```bash
ado-api pr threads {PR} --json --all > <tmpdir>/feedback.json
```

Returns a list of threads, each with `id`, `status` (`active` or `pending` is open), and `comments` (`id`, `author`, `content`, `publishedDate`). ADO carries general conversation in the same list, so it has no separate `.reviewComments`/`.issueComments` split, and no `isOutdated` concept.

### CI status

**GitHub:** From `statusCheckRollup` in metadata. Filter for `conclusion` in `FAILURE`, `TIMED_OUT`, `ACTION_REQUIRED`.

**ADO:**

```bash
az repos pr policy list --id {PR_ID} -o json
```

Filter for `status` in `rejected`, `broken`.

### Pre-flight warnings

Check and display as informational warnings (NOT blockers):
- **isDraft** (GitHub) — "This is a draft PR. Changes can be made but it won't be mergeable until marked Ready for Review."
- **reviewDecision == CHANGES_REQUESTED** (GitHub) — "Reviewer requested changes. Even after fixing all comments, they'll need to re-approve."

## Phase 2: Triage & Plan

Triage covers three groups: **review comments**, **merge conflicts**, **CI failures**.

### Review comments: build the ledger

Review comments are triaged into a **ledger**: one row per piece of feedback, resolved history included, each with the same fields (mechanism, root cause, proposed fix, what the fix adds, disposition). Laying every finding side by side is what reveals a **convergence**: distinct findings, often across review rounds, that keep landing on the same mechanism. That pattern means the mechanism may be wrong rather than under-patched, and no single finding shows it.

If the feedback holds no threads, review bodies, or conversation comments, skip the ledger and the convergence gate; the plan then covers only merge conflicts and CI.

First write the skeleton: one row per input item, with every field that can be read off the feedback (ids, sources, authors, author kinds, rounds, thread status) already filled in, so the subagent spends its judgment only where judgment is needed:

```bash
pr-ledger-check init <tmpdir>/feedback.json <tmpdir>/ledger.json --pr-author <PR author from Phase 1>
```

Then dispatch the rest of the ledger to a **`deep-worker` subagent**. It runs at the deep tier whatever model the main session uses, because the triage and convergence judgment is the part of this skill that most needs it:

> Build the review-feedback ledger for PR #{N} ({platform}). Read `${CLAUDE_CONFIG_DIR:-~/.claude}/skills/mine-address-pr-issues/ledger-procedure.md` and follow it exactly.
>
> - Review feedback: `<tmpdir>/feedback.json`
> - The repository is the current working directory, at the PR's head. Read code as needed; do not modify files or run git commands that change state.
> - Skeleton ledger to fill in place: `<tmpdir>/ledger.json`

Then verify it mechanically:

```bash
pr-ledger-check check <tmpdir>/feedback.json <tmpdir>/ledger.json
```

Exit 0 means every input item has a row, the derived fields still match the feedback, and every rule in the ledger procedure holds. On exit 1, dispatch `deep-worker` again with the check's output and the instruction to fix `<tmpdir>/ledger.json` per the same procedure until `pr-ledger-check` passes. After two failed fix rounds, show the remaining problems to the user and stop: an incomplete ledger means some feedback would go unaddressed without anyone knowing.

Read the ledger with `Read`; it is the source for everything below.

### Convergence gate

If the ledger has any `convergences`, stop here, **before** planning or fixing anything else, merge conflicts and CI failures included. A structural problem can make other fixes moot or conflict with them, and a redesign can change what the conflicting or failing code even is, so it is discussed first.

For each convergence, print: its `mechanism`; its members, one line each with the finding, round, and `outcome` or open status; its `summary`; and its `open_questions` as a list. The open questions are for the user's re-evaluation; do not answer them or propose a redesign here.

```
AskUserQuestion:
  question: "Review feedback on PR #{N} keeps converging on {mechanism(s)}. Findings like these often mean the mechanism should be re-evaluated rather than patched again. How do you want to proceed?"
  header: "Converging"
  multiSelect: false
  options:
    - label: "Stop and discuss (Recommended)"
      description: "Make no fixes or replies; talk through whether the mechanism should change first"
    - label: "Patch individually"
      description: "Continue to the plan and address the converging findings one by one, like any other finding"
```

If "Stop and discuss": end the skill here with no code changes, commits, or thread replies. The ledger at `<tmpdir>/ledger.json` is the reference for that discussion; a later run of this skill builds a fresh one. If "Patch individually": continue, and note in the Phase 4 summary that the convergence was patched individually by choice.

### Merge conflicts

**GitHub:** `mergeable == "CONFLICTING"` or `mergeStateStatus == "DIRTY"`
**ADO:** `mergeStatus == "conflicts"` (if present)

### CI failures

Fetch failure logs and categorize: test failures, lint/type errors, build errors, other.

**GitHub:** `gh run view <run-id> --log-failed`
**ADO:** `ado-api logs read <build-id> --failed --issues` — reads the failed step's log and filters to error/warning lines. Run `ado-api logs read --help` for full usage.

### Present the plan

Build the plan from the ledger:

```bash
pr-ledger-check plan <tmpdir>/feedback.json <tmpdir>/ledger.json > <tmpdir>/plan.json
```

It walks every **open** row once; resolved rows are history and appear nowhere. `entries` has one entry per open row that carries a concern, with `also_answers` listing the open duplicates answered along with it. `responses` is every reply and PR comment Phase 3 will post. `unanswered` lists the open rows that get no response, each with the reason. Every open row lands in exactly one entry and in exactly one response or `unanswered`, so the plan and the replies can't drift apart. Read `plan.json` with `Read`, and look up each row's other fields in the ledger by id.

Start with one count line from `counts`, whose parts add up to `open_rows`: "Ledger: N open items — A actionable, B already addressed, C not acting on, D duplicates answered with them."

Print the plan as a numbered list **before** the AskUserQuestion. Each `actionable` entry is one item, grouped under its `mechanism` (entries sharing a mechanism are fixed together as one logical group in Phase 3). Each item must include:

1. **The reviewer's concern** — the row's `finding`
2. **Proposed fix** — the row's `proposed_fix`
3. **Investigation depth** — the row's `depth`
4. **Response** — from the row's response in `responses`: reply and resolve (`reply` and `resolve` true), reply only (a human reviewer's thread), resolve only (`reply` false: an earlier run replied but the resolve didn't go through), or a PR comment (`channel` `pr-comment`)
5. **Also answers** — the entry's `also_answers`

Mark rows with a non-null `decision` as **`[DECISION NEEDED]`**, and state its `why`, `options`, and `recommendation`.

Also include:
- Pre-flight warnings from Phase 1
- `already-addressed` entries, with the evidence from `disposition_reason` and their `also_answers`, listed separately so the user can verify.
- `not-actionable` entries under "Not acting on", each with its `disposition_reason` and `also_answers`, so a dismissal is visible rather than silent.
- `unanswered` rows under "No reply", each with its reason.

```
AskUserQuestion:
  question: "Here's my plan for PR #{N}. Items marked [DECISION NEEDED] have options listed — choosing 'Looks good' accepts my recommendation for those. Review and tell me if anything should change."
  header: "PR Plan"
  multiSelect: false
  options:
    - label: "Looks good — address all"
      description: "Proceed with the full plan, using the proposed recommendations for [DECISION NEEDED] items"
    - label: "Adjust items"
      description: "I'll tell you what to change, skip, or decide differently"
    - label: "Cancel"
      description: "Exit without making changes"
```

If "Adjust items": ask which numbered items to skip or change. For items the user wants changed, ask what they want instead and update the plan entry before proceeding.

### Merge conflict strategy

If conflicts exist, ask the user:

```
AskUserQuestion:
  question: "Merge conflicts detected. How should I resolve them?"
  header: "Conflicts"
  options:
    - label: "Merge (Recommended)"
      description: "git merge origin/<base> — creates a merge commit, preserves history"
    - label: "Rebase"
      description: "git rebase origin/<base> — rewrites history, requires force-push"
```

## Phase 3: Execute

### Fix each logical group (serial)

For each group from the plan, launch a **`standard-worker` subagent** with:
- The review comment(s) to address (bodies, file paths, line numbers, and the ledger row's `root_cause`)
- The approved proposed fix from the plan (what the user agreed to)
- For `[DECISION NEEDED]` items: the resolved decision
- The investigation depth (`light`, `medium`, or `deep`): the deepest `depth` among the group's rows, so no row in the group is under-investigated
- Output path: `<tmpdir>/group-N/result.md`

**Subagent prompt template:**

> You are addressing PR review feedback. Your output goes to `{output_path}`.
>
> **Comments to address:**
> {comment_details}
>
> **Approved fix:**
> {proposed_fix_from_plan}
>
> **Investigation depth: {depth}**
>
> If `light`: Read the target file. Apply the fix. Run the project's test suite. If tests fail: fix or escalate. Max 3 retries.
>
> If `medium`: Read the target file fully. Grep for call sites of the function/class being modified. Read at least one call site to understand usage. Apply the fix. Run the project's test suite (follow the test execution discovery order from `references/common/testing.md`). If tests fail: fix the code. Max 3 retries, then escalate to user.
>
> If `deep`: Read the target file fully. Grep for call sites — read ALL callers. Read related test files. Read adjacent modules in the same package/directory. Apply the fix. Run the project's test suite. If tests fail: fix or escalate. Max 3 retries.
>
> **CRITICAL**: Never explain away a test failure or CI error. If tests fail after your fix, the fix is wrong — revise it. Do not suggest the test is outdated, flaky, or testing the wrong thing. Do not suggest skipping or marking the test as expected failure. Fix the code until tests pass, or escalate to the user after 3 attempts.
>
> Write a one-line summary as the first line of your output file, then details below.

Read only the **first line** of each result file for the summary — do not read full subagent output into main context.

### Code review loop

After all subagents complete:

1. Run **code-reviewer** agent on modified files
2. For each CRITICAL or HIGH finding: auto-fix when unambiguous, defer to user when judgment is needed
3. If any auto-fixes applied, re-run **code-reviewer** (max 3 iterations)
4. Stop when no CRITICAL/HIGH issues remain or 3 iterations reached
5. Run **integration-reviewer** once on the final diff

Do NOT commit until both reviewers pass. If CRITICAL/HIGH findings remain after 3 iterations, present them to the user before proceeding.

### Commit and push

Commit **per logical group** with descriptive messages:
```
fix(auth): use logging instead of print per review
fix(config): add LOGIN_REDIRECT_URL to test settings
```

Push once after all commits.

### Responses

After push is confirmed, act on every item in `plan.json`'s `responses`, in order. Each item says what is still needed: post a message when `reply` is true (one message per item, one line per entry in its `lines`), and resolve the thread when `resolve` is true. The two are separate because they are separate calls: an item with `reply` false and `resolve` true is a thread an earlier run replied to but did not manage to resolve, so resolve it without posting again. Drop lines for rows the user skipped in the plan, and post nothing for an item whose lines are all dropped; resolve it only if `reply` is false, since that resolve finishes a reply an earlier run already posted. Otherwise act exactly on what the list says: it already covers every open row, and already leaves out anything an earlier run finished.

Each line's `answer` sets its wording. `with` names the row that carries the concern for a duplicate; link that row's thread or item.
- `fixed`: "Fixed — [what changed]." With `with`: "Fixed together with [link] — [what changed]."
- `already-addressed`: "Already addressed — [the evidence in the carrying row's `disposition_reason`]." If the code at that location no longer exists: "The code at this location was refactored and this concern no longer applies."
- `not-acting`: "Not planning to change this — [the carrying row's `disposition_reason`]."

A `pr-comment` item answers a review body or conversation comment, which has no thread to reply in: link the item named in `about`, and start each line with the finding it answers (the row's `finding`) so it reads on its own. End every message with the item's `marker`: it is how a re-run knows this feedback was answered, and how it tells this skill's own comments apart from new feedback.

| `channel` | GitHub | ADO |
|---|---|---|
| `thread`, `reply` true | `gh-pr-reply {PR} {comment_id} "{body}"`, adding `--resolve {thread_id}` when `resolve` is true | `ado-api pr reply {PR} {thread_id} "{body}"`, then `ado-api pr resolve {PR} {thread_id}` when `resolve` is true |
| `thread`, `reply` false | `gh-pr-resolve-thread {thread_id}` | `ado-api pr resolve {PR} {thread_id}` |
| `pr-comment` | Write the body to `<tmpdir>/response-N.md`, then `gh pr comment {PR} --body-file <tmpdir>/response-N.md` | Not produced: ADO carries all conversation in threads |

`resolve` is true for an open thread raised by a bot or by the PR author. A human reviewer's thread gets the reply only, so the reviewer can verify the change and resolve it.

**Rate limiting:** 1-second delay between mutative API calls.

## Phase 4: Summary

Present a structured summary:

```
## Summary

### Review Comments
- Resolved (bot or self threads): N threads [replied & resolved, or resolved only where an earlier run had already replied]
- Replied (human threads): M threads [reply posted, awaiting reviewer]
- PR comments: P [answering review bodies, conversation comments, and their embedded findings]
- Already addressed: K items [answered with the evidence]
- Not acting on: J items [answered with the reason from the ledger]
- No reply: U items [each with its reason from `unanswered`]
- Convergences: none, or each mechanism and whether it was patched individually by choice

### Merge Conflicts
- Resolved: N files — [merge/rebase] origin/<base> into <head>

### CI Failures
- Fixed: N checks — [brief description of each fix]
- Still pending: CI will re-run on push

### Commits
- [list each commit with its message]

### Needs Manual Review
- [any items that could not be resolved automatically]
```

## Helper Scripts

**IMPORTANT**: Use these helper scripts instead of inline commands. They handle authentication, pagination, and output formatting.

- **GitHub**: `gh-pr-threads`, `gh-pr-reply` (with `--resolve`), `git-platform` — run `--help` on each for usage
- **ADO**: `ado-api pr` (show/list/create/update/threads/reply/resolve/resolve-pattern), `ado-api logs read` (CI failure logs), `ado-api work-item` — run `ado-api --help` for usage
- **Platform**: `git-platform` — prints `github`, `ado`, or `unknown`
- **Ledger**: `pr-ledger-check init <feedback.json> <ledger.json> --pr-author <login>` writes the Phase 2 skeleton ledger; `pr-ledger-check check <feedback.json> <ledger.json>` verifies the filled-in ledger against the feedback and the ledger procedure's rules; `pr-ledger-check plan <feedback.json> <ledger.json>` lists the plan entries and every Phase 3 response

### Error handling

- Auth failures: suggest `gh auth login` (GitHub) or `az login` (ADO)
- Rate limiting: inform user and suggest waiting
- No PR found: ask user for a PR number
- GitHub GraphQL permissions: suggest `gh auth refresh -s repo`
