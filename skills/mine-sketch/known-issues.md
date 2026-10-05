# Known Issues

Use this when a sketch build confirms a real issue and intentionally leaves it unfixed. The record outlives the session, so whoever picks the work up later knows what was left and why.

## The File

Record known issues next to the ledger:

```text
<feature_dir>/known-issues.md
```

Create it on first use with this header:

```md
# Known Issues

Real issues found while building this feature and intentionally left unfixed.
```

## What Qualifies

Record an issue only when all of these are true:

- It is real: you checked it against the code (see `receiving-code-review.md`).
- It should not be fixed in this build.
- The reason it isn't fixed is context someone will need later.
- There is a plausible follow-up action or decision.

The usual reasons:

- `faithful-port`: the change ports existing behavior, and fixing it would make the port diverge from the source.
- `out-of-scope`: fixing it would go beyond the ratified decisions.
- `behavior-change`: fixing it could change externally visible behavior.
- `needs-decision`: fixing it needs product, architecture, or business context.
- `blocked`: fixing it depends on an external dependency, upstream change, or migration.

Don't record findings rejected as invalid, findings fixed in the build, generic improvements with no concrete follow-up, or infrastructure flakes with no consequence for the product or the code.

## Severity Gate

Some issues can't be deferred silently. The gate applies only to findings the user hasn't seen, such as a pre-commit reviewer finding you're deferring on your own. A finding the user already chose to skip in the challenge walkthrough was their call, so it needs no second question. Before deferring an unseen finding, check whether any of these hold:

- User-visible breakage with no explanation surfaced to the user. The app looks hung, broken, or non-functional, with no visible error or status saying why. An internal log the user never sees doesn't count.
- Silent data loss or corruption.
- A security or auth exposure.
- The core workflow is blocked entirely for all users, not an edge case or a degraded-but-usable path.

If one does, stop and ask. This is a major gate (see `interaction.md`): run `context-pct` and prepend the result. Recommend from the finding: "Fix now" when the fix is contained and verifiable, "Stop here" when it needs a design decision or reaches across many files, "Ship anyway" only when the risk is real but outside this change's scope.

```
AskUserQuestion:
  question: "[Context: N%] This finding is too severe to defer silently: <one-line description>. <which condition it trips>. What next?"
  header: "Severe issue"
  multiSelect: false
  options:
    - label: "Fix now"
      description: "Fix just this issue before continuing the build"
    - label: "Stop here"
      description: "Pause the build; I'll handle this myself"
    - label: "Ship anyway"
      description: "I understand the risk — record it as a known issue and continue"
```

On "Fix now", fix it through the normal pre-commit reviewers and record nothing. On "Stop here", leave the ledger at `**Status:** ratified` and stop. On "Ship anyway", record the entry and say in `Why deferred:` that the user accepted the risk after seeing the Severity Gate trip.

## Entry Format

Append entries with the next free ID (`KI-001`, `KI-002`, ...):

```md
## KI-001: <short title>

Status: open
Recorded: <YYYY-MM-DD> (<branch>)
Source: <pre-commit-review | ship-challenge | other>
Reason not fixed now: <faithful-port | out-of-scope | behavior-change | needs-decision | blocked>
Affected files:
- <path>

Issue:
<what is wrong>

Why deferred:
<why fixing it now would be incorrect, risky, or out of scope>

Recommended follow-up:
<what should happen later>

Acceptance criteria:
- <how to know the follow-up resolved it>
```

A new entry's `Status:` is `open`. The pre-ship walkthrough covers every open entry and changes it to `resolved — fixed before ship` or `filed (<issue-key>)`, or leaves it `open`. `Recorded:` tells the user which build an entry came from; it doesn't filter the walk.
