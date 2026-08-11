# Known Issues

Durable issues discovered during orchestration that were intentionally not fixed in this run.

## KI-001: Duplicate Phase 3 blocking-review mechanics

Status: resolved — shared blocking-review lifecycle introduced
Run: 66
Source: clean-code
Reason not fixed now: needs-decision
Observed in: Phase 3 clean-code review
Affected files:
- skills/mine-orchestrate/post-execution-pipeline.md

Issue:
The implementation-review and cross-file-review fix paths repeat dispatch, test, review, and retry mechanics.

Why deferred:
Extracting a parameterized instruction loop would change the architecture of the orchestration prose and requires a deliberate decision about which gate-specific instructions remain at each call site.

Recommended follow-up:
Decide whether to introduce a shared blocking-review protocol, then verify that its gate-specific prompts and retry behavior remain explicit.

Acceptance criteria:
- The two paths share one canonical retry algorithm without losing gate-specific inputs or user choices.

## KI-002: Narrow prose-fragment contract test

Status: resolved — fixed during known issues walkthrough
Run: 66
Source: clean-code
Reason not fixed now: needs-decision
Observed in: Phase 3 clean-code review
Affected files:
- tests/test_mine_orchestrate_protocol_contracts.py

Issue:
The contract test checks a small table of exact prose snippets rather than a broader set of stable protocol anchors.

Why deferred:
Replacing the current assertions with headings, command/schema anchors, or broader coverage changes the contract-test strategy and needs a decision about which documentation surface is authoritative.

Recommended follow-up:
Define the stable contract anchors for each canonical protocol, then expand the table-driven checks deliberately.

Acceptance criteria:
- Contract tests protect headings, commands, schemas, option labels, and artifact paths without coupling ordinary explanatory wording to test edits.
