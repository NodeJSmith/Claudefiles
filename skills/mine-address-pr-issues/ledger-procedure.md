# Ledger Procedure

The ledger subagent reads this file and follows it exactly. The dispatching prompt supplies the platform, the path to the saved review feedback JSON, and the path to the skeleton ledger. Everything about *how* to build the ledger lives here, so it reaches the subagent verbatim instead of through the orchestrator's summary of it.

You are triaging every piece of review feedback on a pull request. Your output is a **ledger**: one row per input item, nothing skipped, nothing merged away. A finding you dismiss still gets a row that says why. Then, from the rows, you identify **convergences**: distinct findings that keep landing on the same mechanism.

## Why the ledger exists

Review rounds often treat each finding as an isolated local patch. When findings across rounds keep landing on one mechanism, that pattern is itself the most important finding: the mechanism may be wrong, not under-patched, and each local fix may be hardening a design that should be reconsidered. No single finding shows this. Only the full set, laid side by side with the same fields, does.

## Input

- **GitHub** (`gh-pr-threads --json --all`): `.threads` (inline review threads, resolved and open), `.reviewComments` (review bodies), and `.issueComments` (PR conversation comments). Resolved threads are earlier review rounds: what was raised, and from the replies, what was done about it. `.excluded` lists known-noise messages the tool already left out; they need no rows.
- **ADO** (`ado-api pr threads --json --all`): a list of threads, each with `id`, `status` (`active` or `pending` is open), and `comments`. ADO carries general conversation in the same list.

The repository is the current working directory, checked out at the PR's head. Read the code a finding refers to whenever you need it to fill a field accurately.

## Step 1: one row per input item

The ledger file already exists. `pr-ledger-check init` wrote one row for every thread, review body, and conversation comment, keyed by its `id` (threads, including every ADO thread) or `url` (GitHub review bodies and conversation comments), with every field that can be read straight off the feedback already filled in: `id`, `source`, `author`, `author_kind`, `round`, and on threads `status`. Do not change those fields, remove rows, or run `init` again: `pr-ledger-check check` re-derives them from the feedback and reports any difference. Your job is the fields that need judgment.

If a review body or conversation comment contains findings that appear nowhere else (for example CodeRabbit "Outside diff range" or "Duplicate comments" sections, or failed pre-merge checks in a walkthrough), add a row for each such embedded finding with id `<url>#<n>` (on ADO, where general conversation is a thread, `<thread id>#<n>`), `source` `embedded`, and the parent's `author`, `author_kind`, and `round` copied over. The parent keeps its own row too, and records how many embedded rows you gave it in `embedded_count` — you already read the full text to find them, so this is a declaration, not a re-count. GitHub inline threads never get embedded rows: a thread is one finding, and `embedded_count` is `null` there.

### Fields

Fields marked *init* are already filled in on every input row; copy them from the parent onto embedded rows as described above.

| Field | What to write |
|---|---|
| `id` | *init.* Thread `id`, or the item's `url` (`<url>#<n>` for embedded findings) |
| `source` | *init.* `thread`, `reviewBody`, `issueComment`, or `embedded` |
| `embedded_count` | Only on a review body, conversation comment, or ADO thread (`null` on a GitHub inline thread; `init` leaves it `null` everywhere, so you must declare it): how many embedded findings you gave their own row under this item. `0` if none. `pr-ledger-check` verifies this against the `<id>#<n>` rows that actually exist, so an embedded finding you noticed but forgot to give a row fails the check regardless of which reviewer tool's markup it came from. |
| `round` | *init.* Timestamp of the item's first comment |
| `status` | *init* on threads (an unresolved GitHub thread or an `active`/`pending` ADO thread is `open`, anything else `resolved`). On a review body, conversation comment, or embedded row, you decide: `open` if nobody has answered it, `resolved` if it was already dealt with before this run (history, not something this run does). |
| `author` | *init.* Login of whoever raised it |
| `author_kind` | *init.* `bot`, `human`, or `self` (the PR author) |
| `location` | Path plus the function, symbol, or doc section it concerns, with the line when known. `null` for items with no code location. |
| `finding` | Required for every row. One sentence: what the reviewer says is wrong. For an item that is not a finding (a review trigger, an acknowledgement, a summary), say what it is. The plan and every reply quote this field. |
| `mechanism` | See below. The most important field. |
| `root_cause` | Why the code is wrong: the assumption or design choice that fails. Not a restatement of the symptom. |
| `proposed_fix` | The concrete change. For resolved rows, what the replies say was done. For open rows, what you would do, specific enough to act on: name the function, the file, and what changes. "Fix error handling" is not a fix; "wrap `fetch_user()` in try/except for `ConnectionError` in `auth.py:42`" is. |
| `fix_adds` | One of `correction`, `guard`, `state`, `mirrored-field`, `special-case`, `reset`, `timeout-or-retry`, `docs-only`, `none`, then a short phrase naming what it adds. See below. |
| `outcome` | Resolved rows only: `fixed`, `declined`, `deferred` (with the issue number), or `withdrawn` (the reviewer retracted it). `null` for open rows. |
| `disposition` | `actionable`, `already-addressed`, `not-actionable`, or `duplicate`. `duplicate` means another row raises the same concern (see `related`); `not-actionable` means no row will act on it (declined, withdrawn, disagreed, or not a finding). |
| `disposition_reason` | Required for every row. For `already-addressed`, cite the specific file and line that addresses it; without that citation the row is `actionable`. For `duplicate`, name the row that carries the concern. For `not-actionable`, the specific reason. |
| `related` | Ids of other rows raising the **same concern** (the same problem restated, possibly by another reviewer or after an earlier dismissal). `[]` if none. Among open rows that list each other here, exactly one keeps a substantive disposition (`actionable`, `already-addressed`, or `not-actionable`); the rest are `duplicate`, so the concern is planned and fixed once. An open `duplicate` must name that open substantive row directly: the plan lists a duplicate only under the row it names. If the concern's only other row is resolved history, the open row is substantive itself. |
| `depth` | Open `actionable` rows only: `light` (rename, docstring, formatting, typo), `medium` (logic change, bug fix, error handling), or `deep` (architectural concern, design pattern, API contract). `null` otherwise. |
| `decision` | Open `actionable` rows only, when the fix needs the user's call; otherwise `null`. Needed when the reviewer offers two or more valid approaches, the concern is a design question with no single obvious answer, you disagree with the reviewer (say why), or the requested change conflicts with another row. Write `{"why": "...", "options": ["...", "..."], "recommendation": "..."}` with at least two options; a single option is not a decision. |

**Outdated threads (GitHub `isOutdated: true`)** are still triaged, never skipped. Read the current code at that location. If the location was deleted, the row is `already-addressed` with reason "location removed — likely addressed by refactoring". If the concern is addressed, the row is `already-addressed` only with a cited line. Otherwise treat it as any open row.

**Non-thread items**: a review body or conversation comment that is discussion, approval, acknowledgement, or a summary of inline threads is `not-actionable` with the reason; its embedded findings get their own rows. Mark one `duplicate` only when it raises a specific concern as a finding in its own right that another row also raises: a duplicate gets a reply ("fixed together with …"), a `not-actionable` review body or conversation comment does not.

### `mechanism`

Name the component, piece of state, protocol, or loop that the finding is really about: one level above the symptom. A useful test: **two findings share a mechanism if a single redesign of that thing could plausibly make both of them moot.**

- Too literal: a line, a variable, or one function name (`retryCount on line 88`). Two findings about the same design then look unrelated.
- Too vague: a subsystem or area (`webhooks`, `auth code`, `error handling`). Unrelated findings then look connected.
- About right: `the outbound-webhook retry loop's backoff and give-up accounting`, `the session cache's invalidate-on-logout protocol across tabs`.

**Name the design, not the function.** A label describes what the mechanism does or what state it keeps, in design terms. A function or variable name may appear only in parentheses after that description, never as the head of the label. `refreshToken's expiry check` names where the code lives; `client-side token refresh that predicts server-side expiry (refreshToken)` names the design. Findings in different functions that serve one design share one label.

Label in three passes:

1. **Draft** a mechanism for each row.
2. **Normalize**: rows about the same mechanism must use the identical `mechanism` string, and rows about different mechanisms must not.
3. **Go one level up**: for every pair of distinct labels that share a component, a piece of state, an owner, or a lifecycle (for example, two stages of the same object's lifecycle, or two helpers of the same protocol), ask whether one redesign could plausibly make the findings under both labels moot. If yes, merge them into one label that names the shared design. If no, keep them apart. Stop at the level where the answer changes; merging further produces the too-vague failure.

Findings about docs, tests, or style get the mechanism they describe or test when their problem comes from that mechanism's behavior, and otherwise a plain label for what they are about (`API reference page tone`).

### `fix_adds`

The adding kinds matter: several of them landing on one mechanism means it is being hardened patch by patch. Classify what the fix adds to the code, not how big it is.

- `correction` fixes a wrong value, condition, or call without adding anything new.
- `guard`, `state`, `special-case`, `reset`, and `timeout-or-retry` add a check, a flag, counter, or cache, a branch for one scenario, a reset path, or a timeout or retry.
- `mirrored-field` adds a field to a hand-maintained copy of something defined elsewhere.

<!-- SYNC: skills/mine-challenge/synthesis-procedure.md step 8 defines the same convergence idea for challenge findings (same mechanism test, same "re-evaluate before patching" framing, open questions left unanswered). Change them together. -->
## Step 2: convergences

A **convergence** is a set of distinct findings that land on the same mechanism, where the pattern suggests the mechanism itself should be re-evaluated rather than patched again. Members may all be resolved: a mechanism that earlier rounds already patched several times is exactly the pattern to surface before it is patched again. Use judgment; there is no minimum count. Signals, strongest first:

- Findings on one mechanism across **multiple review rounds**, especially where a later finding is caused by, or cites "fresh evidence beyond", the fix for an earlier one. A mechanism hit again in the round right after it was patched is enough to ask.
- Several fixes that **add** state, guards, special cases, or mirrored fields to the same mechanism.
- Distinct findings from **different reviewers** on one mechanism.

Findings that only touch the same file are not a convergence. Several unrelated small findings are not a convergence either. One concern restated by several reviewers (rows that list each other in `related`) counts as a single finding: a convergence needs at least two findings that are distinct after collapsing restatements.

For each convergence, record:
- `mechanism`: the shared mechanism string.
- `members`: the row ids.
- `rounds`: how many distinct review rounds the members span.
- `summary`: what the members have in common.
- `open_questions`: the questions a re-evaluation would need to answer, including whether the mechanism is needed at all. Do **not** answer them: no proposed design, fix, or scope.

## Output

Fill in the skeleton ledger in place, keeping its `pr` and `pr_author` keys:

```json
{
  "pr": "<title>",
  "pr_author": "<login>",
  "rows": [ { "id": "...", "source": "...", ... } ],
  "convergences": [ { "mechanism": "...", "members": ["..."], "rounds": 3, "summary": "...", "open_questions": ["..."] } ]
}
```

Then run `pr-ledger-check check <input-json> <ledger-json>` and fix everything it reports, until it exits 0. Each problem it lists breaks one of the rules in this file: a missing or unknown row, an *init* field that no longer matches the feedback, a field its row's status and disposition require that is missing or invalid (including a `fix_adds` that doesn't start with one of its kinds, or a `decision` with fewer than two options), an `embedded_count` that disagrees with the embedded rows, a `related` id that names no row, an open duplicate that names no open substantive row, a restated concern with more or fewer than one substantive row, or a convergence that is incomplete, has a `rounds` that isn't a positive integer, has fewer than two distinct findings, or whose members don't match the rows carrying its `mechanism`. A membership mismatch means a label is wrong; fix the label, not just the list.

Reply with one line: the ledger path, the row count, and the number of convergences.
