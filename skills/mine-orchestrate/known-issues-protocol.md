# Known Issues Protocol

Use this protocol when orchestration discovers a real issue that should not be fixed during the current run. The goal is to preserve intentional deferrals as durable feature context, not to create a dumping ground for every reviewer note.

## Durable Artifact

Record known issues in the feature directory:

```text
<feature_dir>/known-issues.md
```

This protocol is the canonical source for the artifact name, entry ID format, status field, source labels, and qualifying reasons. Other orchestration files should reference this protocol instead of redefining the schema.

Create the file on first use. Use this header:

```md
# Known Issues

Durable issues discovered during orchestration that were intentionally not fixed in this run.
```

## What Qualifies

Record an issue only when all are true:

- The issue is real after verify-before-fix review.
- The issue should not be fixed during this orchestration run.
- The reason for not fixing it is durable context someone will need later.
- There is a plausible follow-up action or decision.

Common qualifying reasons:

- `faithful-port`: fixing it would make the port diverge from the source behavior.
- `out-of-scope`: fixing it would expand beyond the approved task/design scope.
- `behavior-change`: fixing it could change externally visible behavior.
- `needs-decision`: fixing it requires product, architecture, or business context.
- `blocked`: fixing it depends on an external dependency, upstream change, or migration.

Do **not** record:

- Findings rejected as invalid after checking the code.
- Findings that were fixed in the run.
- Temporary later-task handoffs already covered by an unexecuted task.
- Generic improvements with no concrete follow-up.
- Infrastructure flakes with no product or implementation consequence.

## Entry Format

Append entries in this format. Use the next numeric ID already present in the file (`KI-001`, `KI-002`, ...). If no entries exist, start at `KI-001`.

```md
## KI-001: <short title>

Status: open
Source: <task_id | impl-review | cross-file-review | clean-code | final-review | other>
Reason not fixed now: <faithful-port | out-of-scope | behavior-change | needs-decision | blocked>
Observed in: <task_id and/or commit sha if available>
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

Keep entries concise. They should be detailed enough for a later agent to act without reconstructing the orchestration context.

## Gate Rule

Before a task or final review treats a real unfixed issue as acceptable, it must be in one of these states:

- Fixed in code.
- Rejected as invalid with rationale in the relevant review/fix summary.
- Deferred only to a later task that still owns the relevant files.
- Recorded in `<feature_dir>/known-issues.md`.

An intentional deferral recorded in `known-issues.md` does not by itself downgrade a task from PASS to WARN. WARN remains reserved for unresolved execution conditions such as visual uncertainty, regressions, or lint/test issues that still need attention in this run.

## Shipping Summary

Before the shipping gate, read `<feature_dir>/known-issues.md` if it exists and count entries with `Status: open`. Surface the count and titles in the shipping prompt so the user can choose whether to ship with known follow-ups.
