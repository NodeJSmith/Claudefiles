# Design: Mandatory Challenge in Orchestration Workflows

**Date:** 2026-08-20
**Status:** archived
**Scope-mode:** expand
**Research:** `/tmp/claude-mine-define-research-AmZxKr/brief.md` (ephemeral — key findings inlined below)

## Problem

Challenge is optional at every point it appears in an orchestration workflow, so it gets skipped. Because it gets skipped, the problems it would have caught are never surfaced — and code quality degrades without a visible cause. The gate that exists to catch design-level problems is the one gate that never runs.

Concretely, challenge appears in exactly two places today and is declinable in both:

- `skills/mine-define/SKILL.md:273` — "Challenge first" is one of four sign-off options. Choosing it invokes challenge properly; not choosing it is the default path.
- `skills/mine-orchestrate/post-execution-pipeline.md:453` — "Challenge first" is one of four shipping-gate options, and choosing it does not even run challenge. Line 493 reads: *"Tell the user to run `/mine-challenge` on the changed files."* The pipeline abandons the user at the point they asked for help.

Everywhere else there is nothing. `mine-sketch` — the Structured path, reached from `mine-build`'s routing gate and the most-used structured entry point — has a fine-toothed comb but no challenge at any point. `mine-plan` has none.

A second, compounding problem: when challenge does run, its findings are written to a `mktemp -d` directory (`bin/get-skill-tmpdir`) and are gone as soon as that directory is cleaned. There is no record of what challenge found, so there is no way to answer whether the gate earns its cost, what it catches that other gates miss, or whether a given class of finding could have been prevented upstream.

## Goals

- Challenge runs automatically at two points in every orchestrated path — once against the design artifact, once against the implemented branch — with no option to decline it.
- The orchestrate shipping path dispatches challenge itself rather than instructing the user to go run it.
- Every challenge finding produced inside an orchestration run is recorded durably and queryably, with enough detail to later ask: what was caught, at which gate, by which critic, against which artifact, and was it acted on.
- The mandate is enforced structurally, not only by prose, so it cannot be quietly edited out.

## Non-Goals

- **Path A (Simple) in `mine-build` is exempt.** It keeps its `code-reviewer`-only flow. Small direct changes do not route through this pipeline.
- **Retrofitting other finding producers.** `clean-code`, the comb, and the code/integration reviewers keep writing findings the way they do today. The `findings` schema reserves a `source` column for them; wiring them up is a later change.
- **Changing how challenge synthesizes findings.** Phase 1–3 of `mine-challenge` (triage, critique, synthesis) are untouched except for the two new flags and the removal of dead detection code.
- **Looping challenge.** Challenge is single-pass by construction and stays that way. A revised design re-runs the comb, never the challenge.
- **A reporting tool or dashboard.** `cfl finding list` ships for reachability; anything richer is a later change informed by the data.

## User Scenarios

### Jessica: Solo developer running a feature through the pipeline

- **Goal:** ship a feature without having silently skipped the review that catches design-level problems
- **Context:** running `/mine-build`, `/mine-sketch`, or `/mine-define` on a change large enough to warrant structure

#### Structured path — sketch through orchestrate

1. **Approves the sketch's design and task files**
   - Sees: design.md and task file paths, comb results
   - Decides: nothing — the challenge is not offered as a choice
   - Then: two critics run against the design doc automatically; findings are resolved inline

2. **Resolves a design-level finding**
   - Sees: one finding at a time, with severity, the critic who raised it, and options
   - Decides: which option to apply, or defer, or file as an issue
   - Then: the choice is applied to design.md and recorded to cfl

3. **Finishes resolving a CRITICAL structural finding on a lightweight sketch**
   - Sees: what fixing it actually took, plus the observation that a sketch may be the wrong vehicle for it
   - Decides: upgrade to full caliper, or continue with the sketch
   - Then: on upgrade, sketch stops and tells them to invoke `/mine-define`, which picks up the same improved `design.md`; otherwise the handoff gate follows

4. **Reaches the shipping gate after execution**
   - Sees: impl-review, cross-file, challenge, clean-code, final review, and known-issues results in one summary
   - Decides: ship, smoke test, or stop — challenge is not among the options because it already ran
   - Then: `/mine-ship` or a pause

#### Weeks later — asking whether the gate earns its keep

1. **Queries the findings table**
   - Sees: every challenge finding across runs, with gate, severity, type, critic, target, and disposition
   - Decides: whether either challenge point is catching enough to justify its cost
   - Then: trims, moves, or retunes a gate on evidence rather than instinct

## Functional Requirements

- **FR#1** `mine-define` runs a challenge phase between the fine-toothed comb (Phase 5) and the sign-off gate (Phase 6), with no option to decline it.
- **FR#2** The `mine-define` sign-off gate no longer offers "Challenge first" as an option.
- **FR#3** Choosing "Revise" at the `mine-define` sign-off gate re-runs the comb and returns to sign-off without re-running the challenge.
- **FR#4** `mine-sketch` runs a challenge phase between its comb (Phase 4) and its handoff gate (Phase 5), with no option to decline it.
- **FR#5** The `mine-sketch` challenge runs with exactly two critics.
- **FR#6** When the `mine-sketch` challenge produced any CRITICAL finding, the user is offered the choice to upgrade to full caliper after resolution completes and before the handoff gate.
- **FR#7** `mine-orchestrate`'s post-execution pipeline runs a challenge step between the cross-file consistency review (Step 3) and the clean code check (Step 4).
- **FR#8** The orchestrate challenge step dispatches challenge against the branch's changed files; it does not instruct the user to run it.
- **FR#9** The orchestrate shipping gate no longer offers "Challenge first" as an option.
- **FR#10** The orchestrate shipping gate's summary line reports the challenge result alongside the other gate results, naming any CRITICAL or HIGH finding left unresolved.
- **FR#11** Each of the three challenge call sites records a cfl gate whose `--data` carries `blocking` and `minor` counts plus a per-severity breakdown.
- **FR#12** Each of the three challenge call sites records one `findings` row per finding produced, including findings flagged likely-invalid.
- **FR#13** `mine-challenge` accepts a `--critics=N` flag that pins the critic count to exactly N.
- **FR#14** `--critics=N` takes precedence over both triage's default 1–3 range and the re-challenge cap of 2.
- **FR#15** `mine-challenge` accepts a `--re-challenge` flag that marks a run as a re-challenge.
- **FR#16** `mine-challenge` no longer attempts to detect a prior run by looking for a findings file in the target's directory.
- **FR#17** cfl stores review findings in a `findings` table created by schema migration 8.
- **FR#18** `cfl finding record` writes one finding row.
- **FR#18a** `cfl finding record-batch` writes all findings for a gate in a single transaction.
- **FR#19** `cfl finding list` queries recorded findings with filters for source, severity, and gate.
- **FR#20** `findings.severity` accepts unrecognized values with a warning and still writes the row. `source`, `finding_type`, and `classification` are unvalidated free-text columns.
- **FR#21** `findings.visibility`, `disposition`, and `design_level` reject unrecognized values with exit code 2.
- **FR#22** `findings.run_id` accepts NULL so a finding can be recorded outside an active run.
- **FR#23** `findings-protocol.md` defines `filed` as a disposition distinct from `skipped`.
- **FR#25** `cfl finding resolve` updates a finding's `disposition` and stamps `resolved_at`.
- **FR#24** A contract test fails when any of the three mandatory challenge invocations is absent from its skill file.

## Edge Cases

- **Challenge finds nothing.** Gate records PASS with zero counts, no findings rows are written, no prompts fire. The phase is silent.
- **A ship-time CRITICAL or HIGH is left unresolved.** Challenge's inline flow offers Apply / Skip / File-as-issue. With FR#23 landed these end at three distinct dispositions: `applied`, `skipped`, and `filed`. A `filed` finding has a tracked issue as its durable record and needs nothing further. A `skipped` one is recorded in the `findings` table by FR#12 — so it does not vanish — but nothing would put it back in front of the user before shipping. FR#10 closes that: the shipping gate names any CRITICAL or HIGH finding left with `disposition: skipped` in the question text the user must read to answer the gate.

  This deliberately does **not** write a `known-issues.md` entry. That artifact exists for reviewer-deferred issues and its Entry Format requires `Source:` (a closed enum with no challenge value), `Reason not fixed now:` (a closed enum), `Why deferred:`, `Recommended follow-up:`, and `Acceptance criteria:` (`known-issues-protocol.md:92-118`). A Skip supplies none of them — the user was asked directly and declined, so there is no deferral rationale to record, and synthesizing one would be inventing content. The known-issues walkthrough would also re-ask about a decision made minutes earlier. The shipping gate is the better surface: it is the actual decision point, and it costs no extra prompt.
- **A ship-time CRITICAL is really a design error.** Challenge's inline flow has no "go back to design" option and none is added. The finding is applied, filed as a tracked issue, or named at the shipping gate per the case above — where "Stop here" is already an option.
- **A sketch challenge surfaces a CRITICAL.** Sketch's existing Phase 1 escalation prompt shape is reused to offer an upgrade to full caliper (FR#6), rather than patching a structural finding into a design doc that was never meant to carry it.
- **The user stops mid-resolution at ship time.** `resume-protocol.md` has no step-level resume inside Phase 3, so a resumed run re-enters the post-execution pipeline at Step 1 and the challenge runs again. Accepted; not fixed here. The re-run produces a second gate row at `iteration` 2, which keeps its findings distinguishable from the first round's.
- **A design is substantially revised after its challenge ran.** FR#3 re-combs but does not re-challenge, so the revised text ships without the critics having seen it. This is a deliberate, named gap: re-challenging on every revision would make cost scale with how many times the wording gets tweaked, and most revisions are exactly that. The comb still runs on the revised doc and catches inconsistency introduced by the edit. If a revision is large enough to want fresh critics, the user can invoke `/mine-challenge --re-challenge <design-doc>` directly — which is part of why `--re-challenge` exists as a caller-facing flag rather than internal state.
- **`mine-define` is resumed after its challenge already ran.** Findings live in tmp and cannot be consulted. The marker is a `challenge.findings-persisted` event with `gate_type: define-challenge` for the current run: present means findings were fully persisted and resolved, so skip it. The gate row alone (`review.gated`) is not sufficient — it's written before findings are persisted (`challenge-gate.md` steps 4 vs. 5–6), so a run interrupted between those steps needs the resume check to re-enter the phase rather than skip it. The marker also waits on `<post_resolution>` (the caller's comb re-run) — it fires after that work completes, not before, so a run interrupted mid-`<post_resolution>` likewise re-enters the whole phase rather than skipping it.
- **A challenge edit breaks the test suite.** Step 4's clean-code wrapper runs the project test suite after its own fixes, so a break introduced at Step 3.5 surfaces there.
- **Two challenge rounds inside one run.** `finding_num` restarts at 1 per challenge invocation, so numbers collide within a run. `gate_id` is the discriminator: each round records its own gate row, and `gates` already carries `iteration` with `UNIQUE(run_id, task_id, gate_type, iteration)`.
- **A finding and a likely-invalid entry share a number.** `Finding 3` and `LI-3` both record `finding_num` 3 under the same `gate_id`, distinguished only by `visibility` (`presented` vs `likely-invalid`). Accepted — queries filter on visibility.
- **cfl tracking is disabled for the spec.** `mine-define` and `mine-sketch` both have a branch for specs predating cfl. In that branch the challenge still runs; only the `cfl` gate and finding calls are skipped.
- **Challenge is invoked ad hoc, outside any run.** No gate exists, so no findings are recorded. `run_id` nullability means this can change later without a migration.

## Acceptance Criteria

- **AC#1** `grep -c 'Challenge first' skills/mine-define/SKILL.md skills/mine-orchestrate/post-execution-pipeline.md` returns 0 for both files. (FR#2, FR#9)
- **AC#2** `skills/mine-define/SKILL.md` contains a challenge phase heading positioned between the Phase 5 comb heading and the Phase 6 sign-off heading. (FR#1)
- **AC#3** `skills/mine-sketch/SKILL.md` contains a challenge phase heading between its Phase 4 comb and Phase 5 handoff headings, and the invocation carries `--critics=2`. (FR#4, FR#5)
- **AC#4** `skills/mine-orchestrate/post-execution-pipeline.md` contains a Step 3.5 heading between the Step 3 and Step 4 headings, and its body invokes `/mine-challenge` rather than instructing the user to. (FR#7, FR#8)
- **AC#5** `mise run test:root` passes, including the new `tests/test_challenge_mandate_contracts.py`, which fails when any of the three invocations is removed. (FR#24)
- **AC#6** `mise run test:cfl` passes, including a new `packages/cfl/tests/test_finding.py`. (FR#17, FR#18, FR#19)
- **AC#7** `cfl finding record challenge 1 --title X --severity HIGH --type Gap --classification User-directed --visibility presented --disposition pending` writes a row and emits JSON containing `finding_id`. (FR#18)
- **AC#8** `cfl finding record` with `--severity UNKNOWN` emits a warning naming the known severities and still writes the row; with `--visibility bogus` it exits 2 and writes nothing. (FR#20, FR#21)
- **AC#9** `cfl finding list --source challenge` returns recorded rows; `--severity` and `--gate-id` filter them. (FR#19)
- **AC#10** A v7 database upgraded in place gains the `findings` table with all pre-existing rows intact, verified by a migration test in `packages/cfl/tests/test_db.py`. (FR#17)
- **AC#11** A freshly created database and a migrated database produce identical `findings` schemas, verified by a convergence test. (FR#17)
- **AC#12** `skills/mine-challenge/SKILL.md` documents `--critics=N` and `--re-challenge` in its Arguments section, and its triage rules state that `--critics=N` overrides the re-challenge cap. (FR#13, FR#14, FR#15)
- **AC#13** `grep -n 'challenge-results\*' skills/mine-challenge/SKILL.md` returns nothing. (FR#16)
- **AC#14** `skills/mine-challenge/findings-protocol.md` lists `filed` in its disposition table with distinct semantics from `skipped`. (FR#23)
- **AC#15** After a Step 3.5 run in which a CRITICAL finding was skipped, the shipping gate's question text names that finding, and `cfl finding list --source challenge` shows it with `disposition: skipped`. (FR#10, FR#12)
- **AC#20** `cfl finding resolve --gate-id X --finding-num 1 --disposition applied` updates the row's `disposition` and stamps `resolved_at`, and the JSON output includes both fields. (FR#25)
- **AC#16** `skills/mine-challenge/challenge-gate.md` names `blocking` and `minor` as required `--data` keys, and a contract test fails if either name is absent. (FR#11)
- **AC#17** `skills/mine-define/SKILL.md`'s Revise handler re-runs the comb and does not invoke challenge, verified by a contract anchor. (FR#3)
- **AC#18** `skills/mine-sketch/SKILL.md` contains the upgrade-to-caliper prompt positioned after its challenge phase and before its handoff gate, verified by a contract anchor. (FR#6)
- **AC#19** `prek run --all-files --stage pre-commit` passes. (all)

## Key Constraints

- **No compatibility shims for the replaced branches.** The two "Challenge first" options and the file-based re-challenge detection are deleted in the same change that adds their replacements, per `rules/common/coding-style.md` (Migrate Callers Then Delete Legacy APIs). Do not leave them alongside the new paths.
- **Do not add `challenge` to `KNOWN_GATE_TYPES`.** The gate types are `define-challenge`, `sketch-challenge`, and `ship-challenge`. A generic `challenge` gate would lose the one distinction the telemetry exists to make.
- **Do not put a `CHECK` constraint on `findings.source`.** The forward-compatibility promise — that another producer can adopt the table without a migration — is only true if `source` is unconstrained in SQL. This is the `gate_type` precedent (`packages/cfl/src/cfl/gate.py:14`) and it is the whole reason the column exists.
- **Do not make `mine-challenge` call `cfl`.** Challenge has no cfl calls today and nineteen callers listed in its own Known Callers section, all but one of which have no active run. The recording lives in the callers.
- **Do not add an `iteration` column to `findings`.** `gate_id` already discriminates rounds; a second mechanism would need to be kept in sync with the first.
- **`design_level` is `TEXT`, not `INTEGER`.** cfl has no boolean column anywhere in its schema; every enumerated value is `TEXT` with a `CHECK`.

## Dependencies and Assumptions

- **Accepted: the per-run challenge cost roughly doubles.** Two mandatory challenges per orchestrated feature, each a Haiku triage plus one to three Sonnet critics plus a Sonnet synthesis. Accepted explicitly by the user: *"it needs to be mandatory at both ends. we'll let the data show where it can be trimmed once we have a few weeks of data in the database."* The `findings` table and the three distinct gate types exist to make that trimming decision evidential. Mitigation is the decision itself — revisit with `bin/agent-stats` and `bin/orchestrate-cost` once several weeks of runs have accumulated.
- **Accepted: skill-file mandates are enforced structurally only at the text level.** This repo can assert that a skill file *contains* an instruction; it cannot execute the file and assert the instruction *ran*. Accepted by the user during test-requirements discovery. Mitigation: `tests/test_challenge_mandate_contracts.py` makes silent deletion fail CI, which is the strongest available rung.
- **Accepted: ship-time challenge does not review the final diff.** Steps 4 and 5 edit code after Step 3.5. Mitigation: those steps are stylistic fixes and regression review respectively, neither of which a design-level critic would rule on differently; Step 5 exists precisely to catch regressions from automated edits.
- **Accepted: the `source` column's forward-compatibility is untested.** No second producer exercises it. `code-reviewer` and `integration-reviewer` use `LOW` and have no `TENSION`, which is why `severity` carries no `CHECK`. Mitigation: the open-vocabulary treatment on all four producer-specific columns means a mismatch warns rather than fails.
- **Fixed: retry-duplication risk on `cfl finding record-batch`.** A retried batch call would otherwise write a second complete set of rows for the same `gate_id`. `UNIQUE(gate_id, finding_num, visibility)` closes this — a byte-identical retry of `(gate_id, finding_num, visibility)` is rejected, while the Finding-N/LI-N coexistence case (same `finding_num`, different `visibility`) is unaffected, since the constraint distinguishes on all three columns.
- **Depends on:** `bin/get-skill-tmpdir` continuing to print a path challenge reports back, since the callers read the findings file from it.
- **Known drift, fixed opportunistically:** `REFERENCE.md:240` enumerates cfl's subcommands and omits `question`. The row is being edited to add `finding`; restoring `question` at the same time costs one word.

## Architecture

### Where challenge runs

Three call sites, each mandatory, each recording its own gate type:

| Call site | Position | Target | Critics | Gate type |
|---|---|---|---|---|
| `mine-define` | new phase between Phase 5 (comb) and Phase 6 (sign-off) | `<feature_dir>/design.md` | triage default (1–3) | `define-challenge` |
| `mine-sketch` | new phase between Phase 4 (comb) and Phase 5 (handoff) | `<feature_dir>/design.md` | pinned to 2 | `sketch-challenge` |
| `mine-orchestrate` | new Step 3.5 in `post-execution-pipeline.md` | changed-files list | triage default (1–3) | `ship-challenge` |

Sketch's critic count is pinned to 2 rather than left to triage's adaptive 1–3 range. One critic is not enough for a design-level review — a single perspective produces findings with no cross-examination. Three is excessive for a sketch, which is a lightweight vehicle by construction. Two matches the existing re-challenge cap (`skills/mine-challenge/SKILL.md:110`), a cost heuristic that has worked in practice.

The ship-time position is load-bearing. Placing challenge after cross-file review means impl-review and integration have already fixed correctness and fit issues, so critics do not spend findings on them. Placing it before clean-code means the style pass polishes post-challenge code rather than code about to be restructured. And it means challenge's own edits are re-reviewed by Step 4 and Step 5 with no new machinery — Step 5 already exists to catch "auto-fix regressions" from Step 4 (`post-execution-pipeline.md:334`), and challenge's edits ride the same path.

### The shared recipe

All three sites follow one procedure, extracted to `skills/mine-challenge/challenge-gate.md` on the model of `skills/mine-comb/comb-gate.md`. Caller-supplied parameters: gate type, target expression, critic-count flag (if pinned), and any site-specific post-resolution handling. The file owns the invariant that the other three would otherwise each restate — that this challenge is not declinable — plus the mechanical sequence:

1. `cfl dispatch <gate-type> --agent-type standard-worker` — record, capture `dispatch_id`
2. Invoke `/mine-challenge [--critics=N] [--re-challenge] <target>` and let it resolve findings inline (flags before target — SKILL.md parses flags from the beginning of $ARGUMENTS only, stopping at the first non-flag token)
3. `cfl dispatch end <dispatch_id>`
4. `cfl gate <gate-type> --verdict <v> --data '{...}'` — capture `gate_id` from the JSON
5. Read the findings file challenge reported, and emit one `cfl finding record-batch --gate-id <gate_id> --file <findings.json>` call that writes all findings in a single transaction, including likely-invalid entries
6. For each finding resolved during step 2 (disposition is `applied`, `skipped`, or `filed`), emit `cfl finding resolve --gate-id <gate_id> --finding-num <N> --disposition <d>` to stamp `resolved_at`

The recipe is identical at all three sites — no caller-specific branches, and step 2 stays a single atomic invocation. What differs is the parameters in the table above, plus two obligations that live in the callers rather than the recipe. Both run **after** step 6, and both read the findings file it already parsed:

- **Ship-time:** Step 6's shipping-gate summary names any CRITICAL or HIGH finding left with `disposition: skipped` (FR#10).
- **Sketch:** if any CRITICAL finding was produced, offer the upgrade-to-caliper choice before the handoff gate (FR#6), reusing both the prompt shape and the on-upgrade behavior sketch already has in its Phase 1 — which stops and tells the user to invoke `/mine-define` rather than auto-invoking it.

Placing the sketch prompt after resolution rather than mid-flight is deliberate. Interrupting between synthesis and resolution would mean splitting the atomic `/mine-challenge` call — either a caller-aware branch inside challenge's Phase 4, or a passthrough invocation followed by the caller reimplementing the inline resolution flow. Both couple challenge to one caller for no gain. Resolution is also not wasted work when the user upgrades: the resolved findings improve the same `design.md` that `/mine-define` then picks up. And a CRITICAL structural finding is usually best judged *after* working through what fixing it would take, which is exactly when the user learns whether a sketch was the right vehicle.

Steps 5 and 6 are why the callers record rather than challenge itself: challenge reports its findings-file path on completion, and the caller — which has an active run by construction — reads it. Challenge stays free of cfl, which keeps it working unchanged for `mine-grill`, `mine-research`, `mine-brainstorm`, the fourteen `i-*` skills, and `mine-build`, none of which have a run. Step 5's batch write ensures the gate row and its findings rows are consistent — a single transactional call replaces the original per-finding loop, eliminating the partial-write window that an interruption between step 4 and a multi-call step 5 would have left.

Gate verdict maps mechanically from the counts, the same way `define-comb` already does: no findings → PASS; findings but none CRITICAL or HIGH → WARN; any CRITICAL or HIGH → FAIL. FAIL here means "found serious findings," not "blocked" — the findings are resolved inline before the phase completes.

The `--data` payload must carry `blocking` (CRITICAL + HIGH) and `minor` (MEDIUM + TENSION) under exactly those key names. `bin/agent-stats:170` reads `gate_data.get("minor") or gate_data.get("findings") or 1`, so a payload carrying only severity names would silently report `minor=1` from the fallback on every challenge gate. The per-severity breakdown and the applied/skipped/filed counts ride alongside as extra keys, which agent-stats ignores.

### The findings table

Migration 8. The DDL is added to **both** `_SCHEMA_STATEMENTS` and `MIGRATIONS[8]` in `packages/cfl/src/cfl/db.py` — the two paths never touch each other (`_create_schema` runs the first for a new database, `_apply_migrations` runs the second for an existing one), and they are hand-synced. `_FK_UNSAFE_MIGRATIONS` stays `{6}`; this is a plain `CREATE TABLE`, not a rebuild.

```sql
CREATE TABLE IF NOT EXISTS findings (
    id             INTEGER PRIMARY KEY,
    run_id         INTEGER REFERENCES runs(id),
    gate_id        INTEGER REFERENCES gates(id),
    source         TEXT NOT NULL,
    finding_num    INTEGER NOT NULL,
    title          TEXT NOT NULL,
    target         TEXT,
    severity       TEXT NOT NULL,
    finding_type   TEXT,
    design_level   TEXT
        CHECK(design_level IS NULL OR design_level IN ('Yes', 'No')),
    raised_by      TEXT,
    classification TEXT,
    visibility     TEXT NOT NULL
        CHECK(visibility IN ('presented', 'overflow', 'likely-invalid')),
    disposition    TEXT
        CHECK(disposition IS NULL OR disposition IN ('pending', 'applied', 'skipped', 'filed')),
    why_it_matters TEXT,
    context_pct    INTEGER,
    resolved_at    TEXT,
    created_at     TEXT NOT NULL
)
```

Plus `idx_findings_run ON findings(run_id)`, matching the run-scoped index shape `questions` uses. No index on `source` — with a single producer (`challenge`) the index is pure overhead; add it when a second producer materializes. No index on `gate_id` — `dispatches.gate_id` is unindexed despite `bin/agent-stats:135` joining on it, and at roughly seven rows per challenge run SQLite will not care.

Column rationale where it is not obvious:

- **`run_id` nullable.** SQLite cannot drop `NOT NULL` via `ALTER`, so relaxing it later would mean a full table rebuild like migration 6. `events.run_id` is already nullable and `try_resolve_active_run_id()` (`packages/cfl/src/cfl/resolve.py:29`) exists for exactly this shape. Free now, expensive later.
- **`gate_id` nullable.** Same rationale as `run_id`: all three call sites in this design always have a gate, but a future finding recorded outside a gate-producing workflow (e.g., an ad-hoc `/mine-challenge` invocation that opts into recording) would need NULL. SQLite cannot drop `NOT NULL` via `ALTER`, so the nullable default avoids a future table rebuild.
- **`classification`.** Synthesis-time approach: `Auto-apply` or `User-directed`. Named `classification` rather than `resolution` because this column records how the finding was *classified* for handling, not what happened to it. The actual outcome lives in `disposition`. Open vocabulary — a future producer may use different classification values.
- **`visibility` and `disposition` — the three-column split.** The old `status` column carried two independent axes: synthesis-time filtering (`overflow`, `likely-invalid`) and resolution-time outcome (`pending`, `applied`, `skipped`, `filed`). These are now separate columns. `visibility` is set once at synthesis and never changes: `presented` (in scope for resolution), `overflow` (exceeded cap), or `likely-invalid` (flagged by synthesis). `disposition` tracks the resolution outcome: `pending` → `applied` | `skipped` | `filed`. `disposition` is `NULL` for overflow and likely-invalid findings that never enter the resolution flow.
- **`resolved_at`.** Stamps the moment a finding's `disposition` transitions from `pending`. Without it, the telemetry cannot distinguish "challenge found nothing" from "the user rubber-stamped through everything" — both look identical in the severity/count data. Note this is a batch-clustered timestamp, not per-finding deliberation latency: `challenge-gate.md` step 6 resolves every finding in a gate in one tight caller-side loop after `/mine-challenge` has already returned, so all findings in a gate get a `resolved_at` within the same few seconds regardless of how long the actual `AskUserQuestion` exchanges took. It still distinguishes "found nothing" from "found and resolved," just not at per-finding granularity.
- **`target`.** What artifact the challenge examined — a design doc path, or the changed-files list. Without it, a query cannot tell whether two findings from different gates were even looking at the same thing, which is most of "could another gate have caught it."
- **`context_pct`.** Mirrors `questions.context_pct`, populated by `read_context_pct()` (`packages/cfl/src/cfl/session.py:34`), which reads the *calling process's* own session sidecar. Because challenge's triage/critics/synthesis all run as separate subagent contexts (per the "Do not make `mine-challenge` call `cfl`" constraint below), this column is a caller-side, pipeline-position proxy — it reflects how deep the orchestrator/mine-define/mine-sketch session is when it calls `record_finding_batch`, not the critics' own context pressure. `ship-challenge` rows (recorded deep into orchestrate) will read high and `define-challenge`/`sketch-challenge` rows (short sessions) will read low regardless of what the critics actually experienced. Treat it as "which pipeline position produced this finding," not "how much context pressure was the critic under."
- **No `evidence` column.** The protocol's evidence field is a list of `file:line` citations — the bulkiest field and the least aggregatable. `title` plus `why_it_matters` plus `target` carries the reasoning load.

### Validation tiers

cfl uses three distinct treatments and picking the wrong one is the likeliest convention violation. The rule for this table: **columns carrying a producer's own vocabulary are open; columns carrying cfl's vocabulary are closed.**

| Column | Tier | Mechanism |
|---|---|---|
| `severity`, `source`, `classification` | Open | Module-level `KNOWN_SEVERITIES`/`KNOWN_SOURCES`/`KNOWN_CLASSIFICATIONS` frozensets, `emit_warning`, row still written. No DDL `CHECK`. |
| `visibility`, `disposition`, `design_level` | Closed | DDL `CHECK` plus module `VALID_*` frozensets, `emit_error(..., exit_code=2)`. |
| `finding_type`, `raised_by`, `target`, `title`, `why_it_matters` | Free | No validation. `finding_type` has no stable cross-producer taxonomy yet. The others are free-text fields that change independently of cfl. |

`severity` being open is the consequential one: `CRITICAL|HIGH|MEDIUM|TENSION` is challenge's taxonomy verbatim, while `code-reviewer` emits `LOW` and has no `TENSION`. A `CHECK` there would make the `source` column's forward-compatibility promise false.

### The module and command

`packages/cfl/src/cfl/finding.py` models on `question.py`, not `gate.py` — findings are leaf telemetry, so `record_finding` emits **no** implicit event. `record_gate` and `record_dispatch` emit lifecycle events because they mark run milestones; `record_question` does not, and up to seven findings per challenge would add noise to the shared audit trail for no lifecycle signal.

Body order follows `question.py:71-132` exactly: docstring stating the warn-versus-exit contract, then warn-tier checks, then error-tier checks, then a single `conn.execute` INSERT, then `cursor.lastrowid`, then `output_module.emit`. A single-row write needs no explicit transaction, matching `record_question`.

`resolve_finding` is a second function in the same module. It takes `gate_id`, `finding_num`, and `disposition`, validates `disposition` against `VALID_DISPOSITIONS`, and runs a single `UPDATE findings SET disposition = ?, resolved_at = datetime('now') WHERE gate_id = ? AND finding_num = ? AND visibility = 'presented'`. The `visibility = 'presented'` guard prevents accidentally resolving an overflow or likely-invalid row. Returns the updated row count (0 or 1) so the caller can detect a missing finding.

CLI wiring is four edits to `packages/cfl/src/cfl/cli.py`: add `"finding"` to `_GROUPED_COMMANDS` (line 68), register `finding_app` after `question_app`, add the import block, and add the command functions. `record`, `list`, and `resolve` are **named** subcommands rather than `@finding_app.default`. This diverges from `question` and `dispatch` deliberately: using `.default` is what forced the documented special case in `_parse_argv_for_telemetry` (`cli.py:1004-1012`), and a named subcommand avoids reopening that scar.

`--spec` is not declared by the command — it is threaded through the module-level `_spec_override` global that `app.meta.default` sets. Most commands read it via `resolve_context(conn, spec_override=_spec_override)`. The finding commands are the exception: they use `try_resolve_active_run_id(conn)` instead, because `run_id` is nullable and `resolve_context` would error when no active run exists.

### Challenge's two flags

`--critics=N` pins the count. Precedence: an explicit count from a caller overrides both triage's default 1–3 range and the re-challenge cap of 2, because the cap is a cost heuristic and the flag is intent. When `--focus` forces a specialist, that specialist occupies one of the N slots rather than adding to them — N is a hard count.

`--re-challenge` replaces the detection branch being deleted. The existing check looks for `challenge-results*.md` in the target's directory, but challenge writes to a fresh `mktemp -d` every invocation, so the file is never where the check looks. It has never fired. The conversation-context fallback stays as-is for manual invocations.

## Implementation Preferences

- **cyclopts** for the CLI, following the existing sub-app registration pattern. Not argparse, not Typer.
- **`Annotated[T, Parameter(...)]`** for every command parameter, with `Parameter(name=["--gate-id"])` where the flag name must differ from the Python identifier.
- **Help strings interpolate the module's frozensets** rather than repeating literal value lists, matching `cli.py:502` and `cli.py:785`.
- **No `from __future__ import annotations`**, no `Optional[X]` (use `X | None`), no lazy imports — per `rules/common/python.md`.
- **Required positionals stay flag-addressable.** `source` and `finding_num` are declared positionally, matching `record_question`'s `skill`/`topic`; cyclopts also accepts them as `--source`/`--finding-num`, and both forms are intended.
- **`cli.py` contains no SQL.** Every command body is `with db_connection() as conn:` → `resolve_context(...)` → delegate to the module function.

## Replacement Targets

- **`skills/mine-orchestrate/post-execution-pipeline.md:453` and `:493`** — the shipping gate's "Challenge first" option and its "tell the user to run it" handler. Replaced by the automatic Step 3.5. Remove outright.
- **`skills/mine-define/SKILL.md:273-274`, `:303`, `:313-317`** — the sign-off gate's "Challenge first" option, its verdict-mapping line, and its handler section. Replaced by the mandatory phase. Remove outright.
- **`skills/mine-challenge/SKILL.md`, Re-challenge detection step 1** — the `challenge-results*.md` directory lookup. Replaced by `--re-challenge`. Remove outright; it is dead code that cannot fire.
- **`packages/cfl/tests/test_db.py:91`** — `assert SCHEMA_VERSION == 7`. Updated to 8, not removed.
- **`packages/cfl/tests/test_cli.py:39`** — the `registered - expected_commands` upper-bound check. Extended to include the new commands.

## Migration

Schema migration 7 → 8 creates the `findings` table and its index. Purely additive: no existing table is altered, no data is transformed, and no existing row is touched. A v7 database upgrades in place on the next `cfl` invocation via `_apply_migrations`.

Reversibility: dropping the table restores v7 behavior exactly, since nothing else reads it. There is no downgrade path in cfl and none is added — consistent with how migrations 2 through 7 were handled.

Data written by the old code: none exists. This is a net-new table with no predecessor; challenge findings have never been persisted.

## Convention Examples

### Record function structure — warn tier, error tier, insert, emit

**Source:** `packages/cfl/src/cfl/question.py:61-132` (abridged — the real function also warns on unknown `topic` and validates `disposition`)

```python
def record_question(
    conn: sqlite3.Connection,
    run_id: int,
    skill: str,
    topic: str,
    *,
    status: str,
    answer: str | None = None,
    disposition: str | None = None,
) -> None:
    """Record a discovery question as asked or skipped.

    Warns for unknown skill or topic but still writes.
    Exits 2 for invalid status, invalid disposition, or a disposition on a
    skipped question.
    """
    if skill not in KNOWN_SKILLS:
        output_module.emit_warning(
            f"Unknown skill '{skill}'. Known: {sorted(KNOWN_SKILLS)}",
            code="unknown_skill",
        )

    if status not in VALID_STATUSES:
        output_module.emit_error(
            f"Unknown status '{status}'. Use: {', '.join(sorted(VALID_STATUSES))}.",
            code="invalid_status",
            exit_code=2,
        )

    context_pct = read_context_pct()

    cursor = conn.execute(
        """INSERT INTO questions
             (run_id, skill, topic, status, disposition, answer, context_pct, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, datetime('now'))""",
        (run_id, skill, topic, status, disposition, answer, context_pct),
    )
    question_id = cursor.lastrowid

    output_module.emit({"question_id": question_id, "run_id": run_id, ...})
```

DO put the docstring's warn-versus-exit contract first — it is the file's own statement of which tier each column belongs to. DON'T wrap a single-row insert in an explicit transaction; `record_gate` and `record_dispatch` do that only because they write two or more rows atomically.

### Open-vocabulary validation — warn but still write

**Source:** `packages/cfl/src/cfl/gate.py:14-37, 63-67` (abridged — the frozenset holds twenty gate types)

```python
KNOWN_GATE_TYPES: frozenset[str] = frozenset(
    {
        "spec-review",
        "code-review",
        # ...
    }
)

    if gate_type not in KNOWN_GATE_TYPES:
        output_module.emit_warning(
            f"Unknown gate_type '{gate_type}'. Known types: {sorted(KNOWN_GATE_TYPES)}",
            code="unknown_gate_type",
        )
```

Note there is no `CHECK` on `gates.gate_type` in the DDL — that absence is deliberate and is what lets the vocabulary grow without a migration. The same absence is required on `findings.source`, `severity`, `finding_type`, and `classification`.

### Vocabulary membership assertions

**Source:** `packages/cfl/tests/test_gate.py:284-290` (abridged — seven assertions in the real block)

```python
    """KNOWN_GATE_TYPES is a frozenset with the expected canonical types."""
    assert "code-review" in KNOWN_GATE_TYPES
    assert "impl-review" in KNOWN_GATE_TYPES
    assert "shipping-gate" in KNOWN_GATE_TYPES
```

### Skill-file contract guards

**Source:** `tests/test_mine_orchestrate_protocol_contracts.py:12-38` (abridged — the real entry carries eight anchors, and the range covers a second parametrize entry)

```python
@pytest.mark.parametrize(
    ("relative_path", "required_anchors"),
    [
        (
            "skills/mine-orchestrate/known-issues-protocol.md",
            [
                ("protocol heading", r"^# Known Issues Protocol$"),
                ("canonical artifact path", r"<feature_dir>/known-issues\.md"),
                ("severity gate", r"^## Severity Gate$"),
            ],
        ),
    ],
)
```

### Shared gate file — declaring caller-supplied parameters

**Source:** `skills/mine-comb/comb-gate.md:9-17` (abridged — five parameters are documented there)

```markdown
## Parameters the caller supplies

- **`<header>`** — the `AskUserQuestion` header chip, e.g. `Design comb`. Keep it ≤12 chars.
- **`minor_blocks`** — `true` if minor findings should ask the user; `false` if noted and skipped.
- **`<re_review_instructions>`** — what "Fix and re-review" does in this context.
```

## Alternatives Considered

**Challenge records its own findings to cfl.** Rejected. Challenge has no cfl calls today and nineteen callers listed in its own Known Callers section, all but one of which have no active run — `mine-grill`, `mine-research`, `mine-brainstorm`, fourteen `i-*` skills, and `mine-build`. Making it cfl-aware would mean a run-presence guard on every recording call and would couple a general-purpose review skill to the orchestration store. Having callers record instead confines the coupling to the three sites that already have runs.

**Ship-time challenge at Step 6, immediately before the shipping gate.** Rejected in favour of Step 3.5. Placing it last means its edits invalidate every gate result upstream, requiring either a full five-gate replay or an explicit staleness exception. At 3.5 the existing pipeline absorbs the re-review — Step 5 already exists to catch regressions from Step 4's automated edits. The cost is that challenge no longer reviews the literally-final diff, which is accepted above.

**Aggregate severity counts in `gates.data` instead of a findings table.** Rejected. It requires no schema change and `agent-stats` already reads it, but it answers only "how many and how severe." The stated goal is to reason about whether a finding could have been caught elsewhere, which is a question about the finding's content.

**Retrofit all finding producers to the new table in this change.** Rejected as scope. It is the only way to answer "could another gate have caught it" from data rather than by hand, but it touches roughly six more dispatch sites across `post-execution-pipeline.md` and `mine-clean-code`. The `source` column keeps the door open.

**A `challenge-gate.md` that is only prose, with each site inlining the mechanics.** Rejected once the findings-recording step landed. With just a dispatch and a gate call the recipe was thin enough to inline three times; with findings-file parsing and per-finding recording it is a real procedure, and three copies would drift.

**Do nothing — rely on remembering to run challenge.** This is the status quo, and the problem statement is the evidence against it.

## Test Strategy

### Required Test Types

- **Unit (`mise run test:cfl`)** — the `findings` table, `record_finding`'s validation tiers, and both CLI commands. Single-package change with clear input/output contracts.
- **Migration (`mise run test:cfl`)** — the v7 → v8 upgrade path against a populated database, plus a fresh-versus-migrated schema convergence check.
- **Contract (`mise run test:root`)** — regex anchors proving all three mandatory invocations exist in their skill files.

**Gap:** this repo can assert that a skill file contains an instruction but cannot execute the file and assert the instruction ran. The mandate is guarded structurally at the text level only. Accepted; recorded in Dependencies and Assumptions.

### Existing Tests to Adapt

- `packages/cfl/tests/test_db.py:91` — `assert SCHEMA_VERSION == 7` becomes 8. All other version assertions in that file are relative and need no change.
- `packages/cfl/tests/test_cli.py:39` — the `registered - expected_commands` upper-bound check needs the new commands added to `expected_commands`.
- `packages/cfl/tests/test_db.py:11-21` — `EXPECTED_TABLES` gains `findings`. Note this constant has already drifted (it omits `plan_snapshots` and `task_snapshots`); adding `findings` correctly does not require fixing that drift, but it is a one-line adjacent fix.

### New Test Coverage

- **`packages/cfl/tests/test_finding.py`** (new) — `record_finding` writes a row with all columns populated (FR#17, FR#18); unknown `severity` warns to stderr and still writes (FR#20); invalid `visibility`, `disposition`, and `design_level` exit 2 and write nothing (FR#21); `run_id=None` writes successfully (FR#22); `gate_id` links to a gate row; JSON output shape includes `finding_id` first. `cfl finding list` filters by source, severity, and gate (FR#19). `resolve_finding` updates `disposition` and stamps `resolved_at` (FR#25).
- **`packages/cfl/tests/test_db.py`** — a v8 migration test on a populated v7 database, modelled on `test_migration_v7_adds_disposition_to_populated_questions` (FR#17, AC#10); a fresh-versus-migrated convergence test comparing `PRAGMA table_info(findings)` across both paths (AC#11). The convergence test is new coverage for an existing risk: the `_SCHEMA_STATEMENTS`/`MIGRATIONS` duplication is currently enforced only by a comment.
- **`packages/cfl/tests/test_gate.py`** — membership assertions for `define-challenge`, `sketch-challenge`, and `ship-challenge` in `KNOWN_GATE_TYPES` (FR#11).
- **`tests/test_challenge_mandate_contracts.py`** (new) — anchors for the define phase between comb and sign-off (FR#1), the sketch phase with `--critics=2` (FR#4, FR#5), the orchestrate Step 3.5 dispatching rather than delegating (FR#7, FR#8), absence of "Challenge first" in both files (FR#2, FR#9), the existence of `challenge-gate.md` with its parameter block (FR#24), the `blocking`/`minor` key names in that file (FR#11, AC#16), define's Revise handler re-combing without re-challenging (FR#3, AC#17), and sketch's upgrade prompt sitting between its challenge phase and handoff gate (FR#6, AC#18).

### Tests to Remove

No tests to remove. Nothing currently covers the branches being deleted — which is part of why they went unnoticed.

## Smoke Test

**Verification surface:** terminal output from a real orchestration run, plus rows in `~/.local/share/claudefiles/cfl.db`.

**Scenario:** run `/mine-sketch` on a deliberately small change in a scratch repo. Observe that after the comb reports, two critics run against `design.md` without any prompt asking whether to challenge, and that findings are presented one at a time for resolution. Continue through to `/mine-orchestrate` and observe that Step 3.5 dispatches challenge against the changed files between the cross-file review and the clean code check, and that the shipping gate's summary line reports a challenge result and offers no "Challenge first" option.

**Success:** `cfl finding list --source challenge` returns rows from both the sketch-time and ship-time challenges; `sqlite3` confirms both sets share one `run_id` and carry different `gate_id` values resolving to `sketch-challenge` and `ship-challenge`; and `bin/agent-stats` reports non-fallback blocking/minor counts for both gate types.

## Documentation Updates

- **`REFERENCE.md:240`** — the `cfl` row's subcommand list gains `finding record/list/resolve`, and the omitted `question` is restored.
- **`skills/mine-challenge/SKILL.md`** — Arguments section documents `--critics=N` and `--re-challenge`; the Known Callers section replaces the existing mine-define entry — which names the "Challenge first" option this change deletes — with the three orchestration call sites as standalone callers.
- **`skills/mine-challenge/findings-protocol.md`** — the `status` field splits into `visibility` (synthesis-time: `presented`/`overflow`/`likely-invalid`) and `disposition` (resolution-time: `pending`/`applied`/`skipped`/`filed`); `Resolution` field renamed to `Classification`; `filed` added as a disposition distinct from `skipped`; `findings-format-version` bumps 3 → 4.
- **`skills/mine-challenge/SKILL.md:200` and `skills/mine-audit/SKILL.md:137`** — the two places that hardcode the literal `Format-version: 3`, updated to match the bump. Nothing validates version agreement at runtime, but leaving them stale would be a lie in the docs.
- **`rules/common/git-workflow.md`** — the "Code Review vs Challenge" section states the orthogonality but requires nothing; it gains the statement that challenge is mandatory in orchestration workflows.
- **`rules/common/invariants.md`** — a Should-tier entry pointing at the rule above.
- **`skills/mine-build/SKILL.md`** — the Execution Rationalizations table gains a row for "we can skip the challenge on this one"; the routing option descriptions note that challenge is included in the Structured and Complex paths and absent from Simple.
- **`CHANGELOG.md`** — at PR creation, not during feature work, per `rules/common/git-workflow.md`.

## Impact

### Changed Files

Shared and cross-cutting first.

- modify: `packages/cfl/src/cfl/db.py` — `SCHEMA_VERSION` to 8; `findings` DDL and index added to both `_SCHEMA_STATEMENTS` and `MIGRATIONS[8]`
- create: `packages/cfl/src/cfl/finding.py` — `record_finding`, `list_findings`, and the `KNOWN_*`/`VALID_*` frozensets
- modify: `packages/cfl/src/cfl/cli.py` — `_GROUPED_COMMANDS`, `finding_app` registration, imports, and the `record`/`list`/`resolve` command functions
- modify: `packages/cfl/src/cfl/gate.py` — three new entries in `KNOWN_GATE_TYPES`
- modify: `packages/cfl/src/cfl/epilogues.py` — `FINDING_RECORD`, `FINDING_RECORD_BATCH`, `FINDING_LIST`, and `FINDING_RESOLVE` help epilogues (no bare group-level constant — that pattern exists only for `.default` sub-apps like `dispatch` and `question`)
- create: `skills/mine-challenge/challenge-gate.md` — the shared recipe
- modify: `skills/mine-challenge/SKILL.md` — two new flags, deleted detection branch, Known Callers replacement, `Format-version: 3` literal at line 200
- modify: `skills/mine-challenge/findings-protocol.md` — `filed` status, format-version bump
- modify: `skills/mine-define/SKILL.md` — new challenge phase; three deletions at the sign-off gate
- modify: `skills/mine-sketch/SKILL.md` — new challenge phase with `--critics=2` and the CRITICAL escalation
- modify: `skills/mine-orchestrate/post-execution-pipeline.md` — new Step 3.5; two deletions at the shipping gate, including `challenge` in the `--data '{"choice": ...}'` enum literal; shipping-gate summary line
- modify: `skills/mine-build/SKILL.md` — rationalization row and routing descriptions
- modify: `skills/mine-audit/SKILL.md` — format-version literal
- modify: `rules/common/git-workflow.md` — mandate statement
- modify: `rules/common/invariants.md` — Should-tier entry
- create: `packages/cfl/tests/test_finding.py`
- create: `tests/test_challenge_mandate_contracts.py`
- modify: `packages/cfl/tests/test_db.py` — version assertion, `EXPECTED_TABLES`, migration and convergence tests
- modify: `packages/cfl/tests/test_cli.py` — `expected_commands`
- modify: `packages/cfl/tests/test_gate.py` — membership assertions
- modify: `REFERENCE.md` — cfl subcommand row

### Behavioral Invariants

- **`mine-challenge` keeps working unchanged for every non-orchestration caller.** `mine-grill`, `mine-research`, `mine-brainstorm`, the fourteen `i-*` skills, and direct `/mine-challenge <path>` invocation must behave exactly as they do today, including `--mode=passthrough`.
- **Existing cfl gate types, event names, and CLI commands are unchanged.** This change is additive to all three vocabularies.
- **A v7 database keeps all its rows.** Migration 8 adds a table and touches nothing else.
- **The comb gates are untouched.** `define-comb`, `sketch-comb`, and `plan-comb` keep their current position, parameters, and behavior.
- **`bin/agent-stats` and `bin/orchestrate-cost` continue to work without modification.** The new gate types flow through their generic gate handling, which is why the `--data` key names are constrained.

### Blast Radius

Every future orchestrated feature in every repo, since these skills are installed globally via `install.py` — this is the intended effect, not a side effect. The cfl database is shared across all projects, so the `findings` table accumulates rows from every repo the user orchestrates in; `source` and `run_id` scope any query.

Anything reading `~/.local/share/claudefiles/cfl.db` directly sees a new table. Nothing in the repo enumerates tables at runtime except `EXPECTED_TABLES` in the test suite.

## Open Questions

None. Every item from the blind-spot pass was probed, decided, extended into a section above, or accepted into Dependencies and Assumptions.
