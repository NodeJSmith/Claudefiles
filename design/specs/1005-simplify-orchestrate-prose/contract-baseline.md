# Contract Baseline

Baseline captured before T01 instruction edits.

## Baseline line count

- Command used for this baseline: `wc -l skills/mine-orchestrate/*.md`
- Total `skills/mine-orchestrate/*.md` lines before edits: `2449`

| File | Lines |
|---|---:|
| `skills/mine-orchestrate/SKILL.md` | 674 |
| `skills/mine-orchestrate/agent-routing.md` | 21 |
| `skills/mine-orchestrate/contested-criteria.md` | 31 |
| `skills/mine-orchestrate/findings-fix-loop.md` | 227 |
| `skills/mine-orchestrate/implementer-prompt.md` | 208 |
| `skills/mine-orchestrate/known-issues-protocol.md` | 137 |
| `skills/mine-orchestrate/post-execution-pipeline.md` | 450 |
| `skills/mine-orchestrate/resume-protocol.md` | 113 |
| `skills/mine-orchestrate/retry-prompt.md` | 53 |
| `skills/mine-orchestrate/spec-fix-loop.md` | 39 |
| `skills/mine-orchestrate/spec-reviewer-prompt.md` | 126 |
| `skills/mine-orchestrate/tdd.md` | 68 |
| `skills/mine-orchestrate/verdict-line-format.md` | 95 |
| `skills/mine-orchestrate/visual-reviewer-launch.md` | 109 |
| `skills/mine-orchestrate/visual-reviewer-prompt.md` | 104 |
| `skills/mine-orchestrate/wip-commit-protocol.md` | 86 |

## Workflow phases and numbered steps

- Phase 0: Locate the tasks
- Phase 1: Parse tasks and select start point
- Phase 2: Per-task execution loop
- Phase 3: Post-execution review pipeline

Phase 2 numbered steps:

1. Announce task and `cfl task start`
2. Discover, confirm, and baseline test/lint commands on the first task only
3. Create per-task temp subdirectory and artifact paths
4. Select executor agent type from `agent-routing.md`
5. Launch executor with canonical prompt payload
6. Capture changed files
6b. Transition task to `reviewing`
7. Resolve `CONTESTED` criteria and emit `task.contested` events
8. Run spec/code/integration review pass in parallel
9. Re-run test and lint gates
10. Run `spec-fix-loop.md` on spec FAIL
11. Run visual reviewer when applicable
12. Run `findings-fix-loop.md` at WP scope on code/integration WARN or FAIL
13. Verify review artifacts and verdict lines exist
14. Assemble task verdict
15. Present task result summary
16. Apply task gate prompt / retry / block / stop behavior
17a. Update task status and create WIP commit
17b. Record task verdict via `cfl`

Phase 3 numbered steps:

1. Summary from `cfl run status`
2. Implementation review gate
3. Cross-file consistency review gate
4. Clean code check
5. Final code/integration review plus final-scope findings fix loop and retest
5.5. Known issues summary
5.6. Known issues walkthrough
6. Shipping gate
7. `cfl run complete`

## cfl commands and dispatch telemetry

Run lifecycle commands:

- `cfl run status`
- `cfl run stop --reason ...`
- `cfl run stop --at-task <task_id> --reason ...`
- `cfl run resume`
- `cfl run start --base-commit <sha> --tmpdir <tmpdir> [--visual-mode ...] [--dev-server-url <url>]`
- `cfl run advance-phase orchestrate --base-commit <sha> --tmpdir <tmpdir> [--visual-mode ...] [--dev-server-url <url>]`
- `cfl run snapshot --spec <spec_number>`
- `cfl run complete`

Task lifecycle commands:

- `cfl task start <task_id>`
- `cfl task update <task_id> --status reviewing`
- `cfl task update <task_id> --status fixing`
- `cfl task verdict <task_id> <PASS|WARN> --commit <sha|no-changes> [--detail ...] --data '{"spec": ..., "code": ..., "integration": ..., "test": ..., "lint": ..., "visual": ...}'`
- `cfl task block <task_id> --reason ...`

Dispatch commands:

- `cfl dispatch executor <task_id> --agent-type <selected_agent_type> --model <model>`
- `cfl dispatch spec-reviewer <task_id> --agent-type general-purpose --model sonnet`
- `cfl dispatch code-reviewer <task_id> --agent-type code-reviewer --model sonnet`
- `cfl dispatch integration-reviewer <task_id> --agent-type integration-reviewer --model sonnet`
- `cfl dispatch visual-reviewer <task_id> --agent-type general-purpose --model sonnet`
- `cfl dispatch end <visual_reviewer_dispatch_id>`
- `cfl dispatch impl-fixer --agent-type general-purpose --model sonnet`
- `cfl dispatch cross-file-reviewer --agent-type integration-reviewer --model sonnet`
- `cfl dispatch cross-file-fixer --agent-type general-purpose --model sonnet`
- `cfl dispatch clean-code-executor --agent-type general-purpose --model sonnet`
- `cfl dispatch final-code-reviewer --agent-type code-reviewer --model sonnet`
- `cfl dispatch final-integration-reviewer --agent-type integration-reviewer --model sonnet`
- `cfl dispatch severity-fixer --agent-type general-purpose --model sonnet`
- `cfl dispatch severity-review --agent-type code-reviewer --model sonnet`
- `cfl dispatch known-issue-fixer --agent-type general-purpose --model sonnet`
- `cfl dispatch known-issue-review --agent-type code-reviewer --model sonnet`
- Every dispatch must be paired with `cfl dispatch end <dispatch_id>`

Event and gate commands:

- `cfl event task.contested <task_id> --data '{"criterion": ..., "decision": "accept"|"reject", "rationale": ...}'`
- `cfl event task.retried <task_id> --data '{"reason": ..., "iteration": <N>}'`
- `cfl gate spec-review ...`
- `cfl gate code-review ... --data '{"findings": <N>, "critical": <C>, "high": <H>, "medium": <M>, "low": <L>}'`
- `cfl gate integration-review ... --data '{"findings": <N>, "critical": <C>, "high": <H>, "medium": <M>, "low": <L>}'`
- `cfl gate test-gate ... --data '{"total": <N>, "passed": <N>, "failed": <N>, "regressions": <N>}'`
- `cfl gate lint-gate ... --data '{"commands": [<per-command results>]}'`
- `cfl gate visual-review ... --data '{"scenarios": <N>, "passed": <N>, "warned": <N>, "skipped": <N>}'`
- `cfl gate impl-review --verdict <PASS|FAIL> --detail ...`
- `cfl gate cross-file-review --verdict <PASS|WARN|FAIL> --data '{"findings": <N>, "critical": <C>, "high": <H>, "medium": <M>, "low": <L>}'`
- `cfl gate clean-code --verdict <PASS|WARN> --data '{"fixed": <N>, "unfixed": <M>}'`
- `cfl gate final-review --verdict <PASS|FAIL> --data '{"fixed": <N>, "deferred": <M>, "rejected": <R>, "unresolved": <K>}'`
- `cfl gate shipping-gate --verdict <PASS|WARN|FAIL> --data '{"choice": "ship"|"challenge"|"stop"}'`

Dispatch telemetry contracts:

- Every subagent prompt in Phase 2 and Phase 3 includes `cfl_dispatch_id: <dispatch_id>` from the immediately preceding `cfl dispatch` call.
- Phase 3 subagents must run in foreground.
- `run_id` is passed into clean-code and findings/known-issue flows when they may write `known-issues.md`.
- `dispatch_id` values are parsed from `cfl dispatch` JSON output and later consumed by `cfl dispatch end`.

## Gates, verdicts, and reviewer types

Reviewer types:

- Executor: selected specialist or `general-purpose`
- Spec reviewer: `general-purpose`
- Code reviewer: `code-reviewer`
- Integration reviewer: `integration-reviewer`
- Visual reviewer: orchestrate-local prompt/launch flow
- Phase 3 impl fixer, cross-file fixer, clean-code executor, severity fixer, known-issue fixer: `general-purpose`

Per-reviewer verdict vocabulary:

- Spec reviewer: `PASS | FAIL`
- Code reviewer: `PASS | WARN | FAIL` with findings counts
- Integration reviewer: `PASS | WARN | FAIL` with findings counts
- Visual reviewer: `PASS | WARN | FAIL`
- Task verdict: `PASS | WARN | FAIL | BLOCKED` as workflow outcomes, with `cfl task verdict` only recording `PASS|WARN`
- Gate verdicts use normalized `PASS | WARN | FAIL | SKIPPED` where applicable

Task verdict assembly rules preserved in baseline:

- FAIL on visual FAIL, fixer-gate FAIL, or test-gate FAIL
- WARN on unresolved visual issues, expected-but-skipped visual review, downstream-only test regressions, pre-existing test failures, or unresolved lint regressions
- PASS when reviewers are clean and unresolved issues are absent, including PASS with detail notes for auto-fixed findings or recorded known issues

## Prompt payload requirements

Executor first-pass payload requires:

- Full `T*.md` task content
- Absolute design doc path, read directly
- Optional absolute `tasks/context.md` path
- Full `implementer-prompt.md`
- Full `tdd.md`
- Canonical test command from `<dir>/test-command.txt`
- Canonical lint command from `<dir>/lint-command.txt`
- Output capture instructions and absolute output paths
- Visual verification status block
- `cfl_dispatch_id`

Executor retry payload adds:

- Full `retry-prompt.md`
- Populated `## Previous review feedback`
- Retry-specific instruction to fix only identified gaps/findings

Spec reviewer payload requires:

- Full task content
- Design doc path
- Changed files list
- Executor output path
- Task scope boundary listing later tasks' write targets
- Full `spec-reviewer-prompt.md`
- `CONCISE-RETURN-MODE`
- `cfl_dispatch_id`
- Output path

Code and integration reviewer payload requires:

- Changed files list
- Task scope boundary for later-task ownership
- `CONCISE-RETURN-MODE`
- `cfl_dispatch_id`
- Output path

Phase 3 payload requirements preserved:

- Impl-fixer gets impl-review findings, relevant file paths, design doc path, all task files, accumulated spec reviews, `implementer-prompt.md`, `retry-prompt.md`, `tdd.md`, populated previous-feedback section, and strict scope instructions.
- Cross-file reviewer gets full branch diff files, design doc path, and explicit cross-file focus areas.
- Cross-file fixer gets findings, changed files, design doc path, task files, and fix-only scope.
- Clean-code executor gets branch diff, base commit, design doc path, canonical test/lint commands, `run_id`, output path, and the `<!-- HEAD: <sha> -->` summary-file contract.
- Final reviewers get full branch diff, `CONCISE-RETURN-MODE`, `cfl_dispatch_id`, and output file paths.

## Artifacts and schemas

Run-level artifacts:

- `<dir>/test-command.txt`
- `<dir>/lint-command.txt`
- `<dir>/test-baseline.md`
- `<dir>/lint-baseline.md`
- `<dir>/clean-code-summary.md`
- `<dir>/final/code-review.md`
- `<dir>/final/integration-review.md`

Per-task artifacts under `<dir>/<task_id>/`:

- `executor.md`
- `spec-review.md`
- `visual-review.md`
- `code-review.md`
- `integration-review.md`
- `test-gate.md`
- `lint-gate.md`
- `fix-ledger.md`
- `test-output.log`
- `lint-output.log`
- `changed-files.txt`
- `committed-files.txt`
- `before-*.png` / `after-*.png`

Durable feature artifact:

- `<feature_dir>/known-issues.md`

Known-issues schema contracts:

- File header is fixed
- Entry IDs are `KI-001`, `KI-002`, ...
- Fields include `Status`, `Run`, `Source`, `Reason not fixed now`, `Observed in`, `Affected files`, `Issue`, `Why deferred`, `Recommended follow-up`, `Acceptance criteria`
- Allowed reason labels: `faithful-port`, `out-of-scope`, `behavior-change`, `needs-decision`, `blocked`
- `Run: <run_id>` is mandatory for every entry writer
- Status starts `open` and may change to `resolved — fixed during known issues walkthrough` or `filed (#<issue-number>)`

Verdict-line contracts:

- Code/integration canonical line: `**Verdict:** PASS | WARN | FAIL (findings: N, critical: C, high: H, medium: M, low: L)`
- Spec canonical line: `**Verdict:** PASS | FAIL`
- Visual canonical line: `**Verdict:** PASS | WARN | FAIL`
- Only one line may begin with `**Verdict:**` in each reviewer file
- Consumers extract the last matching verdict line
- `CONCISE-RETURN-MODE` activates only when the exact token and an output path are both present

## User choices and retry limits

User choice prompts present in the baseline:

- Resume protocol: `Stop the run`, `I already have task files`, `Advance to orchestrate`, `Resume from <task>`, `Restart fresh`
- Feature confirmation: `Yes — execute it`, `No — let me specify the path`
- Dev server: `I'll start the server now`, `Skip visual verification for this run`
- Command confirmation: `Correct`, `Needs correction`
- Spec FAIL persistence gate: `Fix review findings`, `Mark as blocked and skip`, `Stop here`
- Task FAIL gate: `Fix review findings`, `Mark as blocked and skip`, `Stop here`
- Architectural block gate: `Stop and revise the design`, `Stop here for now`
- Impl-review FAIL gate: `Address fixes`, `Stop here`
- Impl-review ABANDON gate: `Stop and revise the design`, `Stop here for now`
- Severity escalation gate: `Fix now`, `Stop here`, `Ship anyway`
- Known issue walkthrough: `Fix now`, `File as GitHub issue`, `Leave deferred`
- Known issues backlog: `Not now`, `Review them`
- Shipping gate: `Ship via /mine-ship`, `Challenge first`, `Stop here`

Retry / repetition limits:

- Dev-server reprobe: up to 3 attempts with 5-second pause
- Spec auto-fix loop: 1 automatic retry, then user gate; if user chooses another fix cycle and it FAILs again, only `Mark as blocked and skip` or `Stop here` remain
- Impl-review and cross-file-review fix loops: no hard numeric cap; warning starts on the 3rd round, user may continue or stop
- Severity escalation and known-issue walkthrough fix-now paths re-prompt on failure rather than auto-loop
- Findings-fix-loop budgets, classify behavior, and no-op fingerprint route are preserved in `findings-fix-loop.md` and referenced as unchanged baseline contracts

## State transitions and sync contracts

State transitions:

- Run phases: `define` -> `plan`/`sketch` -> `orchestrate` -> completed
- Resume protocol may stop a run, advance from prior phase, or resume existing orchestrate state
- Task statuses include at least `executing`, `reviewing`, `fixing`, `done`, and blocked states recorded by `cfl task block`
- `current_task` and `last_completed` are DB-derived and drive resume/start-point selection
- Retries cycle `fixing -> reviewing`; final verdict recording happens only after Step 17b, after Step 17a has created the WIP commit or recorded `no-changes`
- WIP commit step runs only for PASS or WARN task outcomes

Sync contracts explicitly present before edits:

- `agent-routing.md` has a `SYNC CHECKLIST` comment tying the routing table to `references/common/agents.md`, `agents/<name>.md`, and `SKILL.md` Step 3 routing references
- `verdict-line-format.md` is the canonical verdict-line source for all four reviewers and references reviewer-file `SYNC` markers plus `bin/lint-verdict-line`

## Comparison target for later tasks

T04 should compare the completed workflow against this baseline for:

- Phase and step preservation
- Unchanged `cfl` command families and telemetry fields
- Unchanged gate shapes, verdict vocabularies, and reviewer types
- Unchanged prompt payload requirements for isolated subagents
- Unchanged artifact names, schemas, user-choice prompts, retry ceilings/policies, and state transitions
- No removed real sync contract without a clear canonical owner

## T02 comparison

Compared `SKILL.md`, `post-execution-pipeline.md`, and `findings-fix-loop.md` against the inventory
above after T02 edits.

| Inventory area | Comparison result |
|---|---|
| Phases and numbered steps | Retained: Phase 0, Phase 1, all Phase 2 steps including 6b, and Phase 3 delegation. |
| Commands, dispatches, gates, and telemetry | Retained: command syntax, reviewer/fixer agent types, foreground execution, dispatch IDs, `run_id`, gate payloads, and dispatch-end pairing. |
| Artifacts and prompt payloads | Retained: task/review/gate artifacts, command files, logs, screenshots, known-issues paths, isolated prompt inputs, concrete code/integration reviewer scope boundaries, and output paths. |
| Verdicts and state transitions | Retained: reviewer vocabulary, task assembly, retry/block/stop choices, fixer terminal states, ledger rules, and run completion behavior. |
| Findings fixer loop | Retained: WP/final scope matrix, exact fingerprint command, before/after comparison, both no-op exits, two normal passes with pass-dependent latest review inputs, classify-only terminal dispatch, reviewer parallelism, ledger validation, and iteration counts 1/2/3. |
| User choices and post-execution paths | Retained: implementation/cross-file/known-issue/shipping prompts, automatic reviews, retesting, shipping choices, and completion conditions. |

### Retained redundancy rationale

- Isolated subagent payloads still name their required paths, sentinels, dispatch IDs, and output
  files because dispatched agents do not inherit orchestrator context.
- Exact shell commands remain beside the fingerprint and gate decisions because a plausible
  execution error there would change no-op detection or terminal routing.
- Terminal ledger invariants, known-issue validation, and user-choice blocks remain explicit at
  their gates because references alone could make a skipped action look valid during execution.

## T04 final audit

Command used for the final measurement: `wc -l skills/mine-orchestrate/*.md`

| Measure | Before T01 | After T04 | Result |
|---|---:|---:|---|
| Total orchestration Markdown lines | 2449 | 2554 | 105 lines added (4.29%); current-branch measurement includes review-driven edits |
| Long-line reflow used as the reduction | no | no | reduction is from deleted/replaced duplicated prose |
| AC#5 target (`>=15%`) | 2449 | 2554 | **EXCEPTION APPROVED: inherited target is not met; the final measurement is 4.29% above baseline because necessary workflow safeguards, explicit handoff contracts, and isolated subagent context were retained rather than removing roughly 300 additional lines to satisfy the metric** |

The final audit found and fixed the original four contract issues plus the approved follow-up
corrections: optional task sections are now treated as
optional (`Summary`/`Focus`), the post-execution fixer prompt no longer references the absent
`Review Guidance` section, visual scenario output includes `WARN [INFRA]`, and visual no-screenshot
fallback precedence is deterministic. Retry feedback also names the `Visual reviewer` host. The
configured visual review model remains `sonnet`, so no model change was required.

### Before/after contract inventory

| Contract category | Before | After | Evidence / explanation |
|---|---|---|---|
| Phases and numbered steps | Phase 0, 1, 2, 3; task steps 1-17; Phase 3 1-7 | Retained | No phase or step removal; optional-section wording only changed. |
| Commands and command families | All `cfl run`, `cfl task`, `cfl dispatch`, `cfl event`, and `cfl gate` families | Retained | Search and manual comparison found no command-family removal. |
| Dispatch telemetry | `cfl_dispatch_id`, foreground Phase 3, `run_id`, dispatch-end pairing | Retained | Every reviewer dispatch, including visual review, carries an ID and has a paired end call. |
| Prompt payloads | Executor, retry, spec, code/integration, visual, and Phase 3 payload fields | Retained | Isolated prompts retain required paths, IDs, commands, and output files; visual review now carries its dispatch ID; retry adds Visual reviewer label. |
| Gates and artifacts | Test/lint/visual/reviewer/fixer/shipping gates and all listed paths | Retained | No gate or artifact name was removed. |
| Reviewers and verdicts | Executor, spec, code, integration, visual; PASS/WARN/FAIL/SKIPPED rules | Retained | Canonical verdict owner and lint pass; visual `WARN [INFRA]` is now explicit per existing behavior. |
| Known-issue fields and fingerprint paths | Full schema, `Run`, severity gate, and `fingerprint-pre-passN.txt` | Retained | No field, path, or terminal ledger rule changed. |
| User choices | Resume, command, visual, retry, known-issue, and shipping choices | Retained | No option label or branch was removed. |
| Retry limits and transitions | Visual probe, spec retry, fixer budget, review rounds, task/run states | Retained | No ceiling, transition, or terminal outcome changed. |
| `SYNC` contracts | Reviewer verdict owner, isolated retry guidance, routing checklist | Retained | No new marker; existing markers still identify canonical owners. |
| `CONCISE-RETURN-MODE` hosts | Six legitimate `skills/mine-orchestrate` hosts | Retained | `grep -rl` returns exactly the six documented paths. |

### Verification results

| Check | Result |
|---|---|
| `bin/lint-verdict-line` | PASS |
| `grep -rl CONCISE-RETURN-MODE skills commands` | PASS; exactly six documented hosts |
| `uv run prek run --all-files` | PASS |
| `mise run 'test:*'` | PASS; authoritative full-suite command |
