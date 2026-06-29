# Design: mine-orchestrate — retain only verdicts on the happy path

**Date:** 2026-06-27
**Status:** archived
**Scope-mode:** hold
**Issue:** #410 (part of the 033 cost analysis)

## Problem

`mine-orchestrate` runs as a single long-lived **Opus** conversation — ~154 turns for a typical run. Every file the orchestrator `Read`s stays in its context permanently and is re-billed as `cache_read` on *every subsequent turn*. The 033 cost analysis measured the consequence: the orchestrator loop is the single largest cost bucket (~$1,240 of ~$2,068 across 30 runs, ~60%), and its absorbed band is **98% `cache_read`** (1.55B tokens). The cache is healthy (only 1.6% creation) — the problem is **volume**, not churn.

The driver is verdict consumption. Per task, the orchestrator reads ~6 full report files into its own context:

- `spec-review.md`, `code-review.md`, `integration-review.md` — read in full at **Step 8** ("Read all output files").
- `code-review.md` + `integration-review.md` — read *again* at **Step 12**, where the orchestrator applies findings fixes **inline in its own context**.
- all five review/gate files — read *again* at **Step 13** for the gate.

A report read on task 1 is re-cached on every turn through task N. On the happy path the orchestrator only needs the **verdict** (PASS/WARN/FAIL) and whether findings exist to gate; the full detail only matters when *acting on findings*. The FAIL/retry path is already lean — `retry-prompt.md` passes file *paths* and the executor reads them in its own (ephemeral) context. The happy path is the leak.

A second, smaller leak: the reviewer subagents' **return messages** are auto-injected into the orchestrator's context when each Agent call completes. If a reviewer's final message is its full report, the orchestrator absorbs the full report *even before it Reads the file* — so grepping the file instead of reading it only half-fixes the leak unless the reviewer's return message is also made concise.

## Goals

- On the happy path, each task contributes **~verdict lines** to the orchestrator's context, not full reports.
- Gate decisions remain **faithful** to today: given the same reviewer findings, the assembled task verdict and the auto-continue-vs-user-gate outcome are identical. The deferred-vs-unresolved distinction the FAIL rule depends on is preserved by reconciling it **inside a single fixer context** (as today's orchestrator-as-fixer does) — not by matching counts or IDs across agents.
- Gate **decisions stay computable on the Opus orchestrator** (the 033 analysis explicitly parked "orchestrator→Sonnet" to keep Opus reliability for gating). The orchestrator derives PASS/WARN/FAIL from compact signals (verdict words + a fixer-produced ledger), not from full report bodies.
- The FAIL/retry path continues to read full detail on demand (already true; must not regress).
- MEDIUM/LOW findings still get fixed — now by a dispatched fixer rather than inline orchestrator work — with no silent reduction in cleanup.
- The cost win is **measured**, not assumed: the realized `cache_read` reduction is confirmed against the 033 baseline after the change.

## Non-Goals

- **Phase 3 (post-execution pipeline) is out of scope.** It runs once at end-of-run, so its reads persist for far fewer turns than the per-task loop, and its fix steps genuinely need full detail. Its reviewers will still emit the new canonical verdict line (same shared agents), but Phase 3's read/fix flow is unchanged. Applying verdict-only to Phase 3 is the deferred "Expand" option.
- **Orchestrator → Sonnet** — parked in 033; not revisited here.
- **Proactive checkpoint+resume mid-run** (#411) — complementary lever, separate issue.
- No change to *what* the reviewers check or their severity criteria — only their machine-readable verdict line and (in orchestrate mode) their return-message verbosity.

## User Scenarios

### Actor: the orchestrator (Opus main loop)
- **Goal:** drive each task through review → gate → commit while keeping its own context lean.
- **Context:** a long autonomous run (often overnight), many tasks, no human in the loop except at gates.

#### Happy-path task (PASS, no findings)

1. **Dispatch the three reviewers (Step 8)** in concise-return mode.
   - Sees: each reviewer's concise return message — its single canonical verdict line.
   - Then: extracts each verdict from the report *files* (authoritative) — `spec=PASS code=APPROVE (findings: 0) integration=APPROVE (findings: 0)`. Reads no report bodies.
2. **Assemble the verdict (Step 14)** from the verdict lines → PASS. Commit + checkpoint, next task. No full report was absorbed.

#### Happy-path task with findings (PASS after auto-fix)

1. **Extract verdict lines (Step 8).** Sees `code=APPROVE (findings: 3)` → findings exist.
2. **Run the fixer loop (Step 12).** The orchestrator dispatches a fixer subagent with the code/integration report *paths*. The fixer reads them in its own context, applies unambiguous fixes, and writes a **ledger** classifying every finding it saw as `fixed | deferred(reason) | unresolved`. The orchestrator re-captures changed files and re-dispatches code+integration reviewers (concise) → fresh verdict lines. If findings remain, another fixer pass reads the *fresh* review and re-classifies — within budget (initial review + ≤2 fixer passes).
3. **Gate (Step 14)** on the terminal fixer's ledger: `unresolved` rows → FAIL; deferred-only or clean → PASS (`PASS (3 auto-fixed)`). The orchestrator read zero report bodies and one compact ledger; the defer-vs-unresolved judgment was made in the fixer's context, which had the latest review in front of it.

#### FAIL / retry task (unchanged)

1. **Extract verdict lines.** Sees `spec=FAIL`.
2. **Gate to the user (Step 16); on "Fix and retry"** → dispatch the executor with reviewer file **paths** (existing `retry-prompt.md` flow). The executor reads detail in its own context. Orchestrator stays lean.

## Functional Requirements

- **FR#1** Every reviewer (spec, code, integration, visual) writes one canonical verdict line. For **code and integration** reviewers it is `**Verdict:** <VERDICT> (findings: <N>)`; for **spec and visual** reviewers it is `**Verdict:** <VERDICT>` (no count — see FR#2). `<VERDICT>` uses that reviewer's native vocabulary (spec: PASS/WARN/FAIL; code & integration: APPROVE/WARN/BLOCK; visual: VERIFIED/WARN/FAIL). The `**Verdict:**` prefix is reserved exclusively for this line — no other line in any reviewer's report may begin with it (visual's per-scenario lines are renamed `**Scenario verdict:**`; spec's existing opening `**Verdict:**` line *is* the canonical line; visual's `**Overall verdict:**` is replaced by the canonical line). The orchestrator extracts it as the last line matching the canonical pattern (reviewers may emit reasoning/pre-existing sections afterward — it is not necessarily the file's final line).
- **FR#2** `<N>` (code & integration only) is the count of findings **introduced by this change** — pre-existing findings, which both shared reviewers already exclude from their verdict, are excluded from the count. There is a single count; no blocking/advisory split. `N` exists for exactly one decision: *does the code/integration fixer need to run?* Spec and visual carry no count because their findings never trigger the fixer (spec routes by verdict word to the WARN loop or the FAIL gate; visual feeds Step 14 by verdict word).
- **FR#3** Concise-return mode is activated only when **both** conditions hold: the dispatch prompt contains a single **literal sentinel token** (verbatim), **and** the dispatch provides an output file path. In concise-return the reviewer's final message is only its canonical verdict line; the full report still goes to the file. Absent the sentinel **or** absent a file path (e.g. `/mine-review`, which passes no path and consumes the return message), the reviewer returns its full report as today. The unconditional default is the full report.
- **FR#4** In Step 8 the orchestrator extracts each task's reviewer verdicts from the canonical lines without reading the full report bodies into its own context on the happy path.
- **FR#5** When the **code-review or integration-review** canonical line shows `findings > 0`, or its verdict is WARN/BLOCK, the orchestrator runs the fixer loop (FR#10). Spec and visual findings do **not** trigger the fixer — a spec WARN routes to the Step 10 WARN loop, a spec FAIL to the Step 16 gate, and visual findings feed Step 14 directly, all as today.
- **FR#6** In Step 13 the orchestrator verifies review-file presence without reading bodies and sources verdicts from the canonical lines; a missing or unparseable canonical line for a required reviewer causes that reviewer to be re-run (existing behavior, now the primary path).
- **FR#7** The Step 14 verdict assembly produces the same canonical task verdict it does today, derived from the verdict lines and the terminal fixer ledger (FR#10) rather than from full report contents.
- **FR#8** On a spec **WARN**, the orchestrator reads the spec-review file to classify the WARN structural-vs-fixable (as today). This is acceptable: WARN is off the happy path and infrequent, so reading there does not grow the dominant per-task context. The happy path (spec PASS) reads nothing. The structural/fixable taxonomy stays in `warn-fix-loop.md` — the spec reviewer is not asked to self-classify. (Concise-return still writes the full spec report to the file, so this read works.)
- **FR#9** The test and lint gates (Step 9) pipe raw command output to the per-task log files and keep only a short summary in the orchestrator's context (no full command output absorbed).
- **FR#10** The fixer loop, defined in a new `findings-fix-loop.md`, works as follows. The orchestrator alternates **fixer pass → independent re-review**, ending on a fixer pass:
  1. **Fixer pass:** a `general-purpose`/`model: sonnet` subagent receives the current code-review + integration-review file *paths*, the changed-files list, and the design doc path. It reads the reviews in its own context, applies unambiguous fixes (same fix/defer policy as today's Step 12), and **writes a ledger** (`<task_id>/fix-ledger.md`) classifying *every finding the current review reports* as `fixed` | `deferred(reason)` | `unresolved`. The ledger is overwritten each pass — it always reflects the latest review's findings, classified in one context (so no cross-agent ID matching is needed; ledger rows are descriptive, not keyed).
  2. **Re-review:** the orchestrator re-captures changed files and re-dispatches the code + integration reviewers (concise), getting fresh verdict lines. This independently detects whether fixes worked and surfaces any fixer-introduced regressions.
  3. **Loop control:** if the fresh review reports `findings: 0` → done (PASS). Otherwise loop again, **budget = initial Step 8 review + at most 2 fixer passes** (3 iterations total, matching today). If the budget is exhausted while the latest review still reports findings, run one final fixer pass in *classify mode* over that latest review so the ledger reflects it.
  4. **Gate:** the orchestrator reads only the terminal ledger (compact). Any `unresolved` row → the task verdict is FAIL (routes to Step 16). Deferred-only or empty → PASS (with a `(N auto-fixed)` note). The orchestrator never reads a report body and never matches findings across agents; detection stays with the independent reviewers, and defer-vs-unresolved classification stays in a single fixer context that read the latest review — mirroring today's orchestrator-as-fixer.

## Edge Cases

- **Reviewer crashes / emits no canonical verdict line** — extraction finds nothing for that file; the orchestrator treats it as a failed review and re-runs that reviewer (FR#6). A task summary missing a required review is overridden to FAIL with "review step skipped" (existing rule preserved).
- **Reviewer reports a clean verdict but a stale/wrong count** — the fixer trigger is `findings > 0` **OR** verdict ∈ {WARN, BLOCK}, so any non-clean verdict still triggers the fixer even if the count is wrong. The only un-caught case is APPROVE **with** `findings: 0` while the body actually lists a new finding — i.e., the reviewer both gave a clean verdict *and* miscounted. That is a reviewer-fidelity bug of the same class as today's "reviewer fails to list a finding," outside this design's scope; it is not introduced by this change.
- **Fixer introduces a regression** — caught by the next independent re-review (FR#10 step 2), which reports it; the next fixer pass reads and classifies it. Because the loop ends on a fixer pass that reads the latest review, regressions present at termination land in the ledger as `unresolved` (or `fixed`), never silently dropped.
- **A fixer-deferred finding reappears in the re-review** — expected and handled: the terminal fixer re-reads the latest review and re-classifies that finding as `deferred` (the defer criteria are stable, so the judgment is consistent). The orchestrator counts only `unresolved` rows, so a legitimately re-deferred finding does not FAIL the task. No cross-pass identity matching is required.
- **Concise-return non-compliance** — a reviewer ignores the sentinel and returns its full report. Correctness is unaffected (the file is authoritative); only the return-message cost win is lost for that one dispatch. The compliance probe (Test Strategy) measures how often this happens.
- **Fixer modifies files beyond the changed-files list** — the post-fix changed-files re-capture (existing Step 12 behavior) catches them.
- **Multiple `**Verdict:**` lines** — prevented by FR#1 reserving the prefix; defensively, the orchestrator takes the last matching line.
- **Pre-existing findings** — excluded from `<N>` (FR#2), so the fixer is not dispatched against debt the reviewers deliberately carved out of the verdict.
- **Resume after compaction** — verdict lines and the ledger are re-read from the persisted files in the run tmpdir. If the tmpdir was cleared, the existing graceful-skip for already-completed tasks applies; in-progress tasks re-run the missing reviewer.
- **Integration-reviewer's current `**VERDICT: ... **` line** matches neither alternative of the existing Step 13 grep (`**Verdict:**` / `**Overall verdict:**`) — a latent gate bug today, masked only because an Opus orchestrator reads the body and recognizes the verdict semantically. Standardizing to FR#1 fixes it; the `**Overall verdict:**` alternative (currently matching only the visual reviewer) becomes redundant and is removed.

## Acceptance Criteria

- **AC#1** A happy-path task (PASS, with or without auto-fixed findings) adds only verdict lines, a compact fixer ledger, and short summaries to the orchestrator's context — no full report body is `Read` by the orchestrator. (maps FR#3, FR#4, FR#5, FR#10)
- **AC#2** The FAIL/retry path still surfaces full reviewer detail on demand by passing file paths to a subagent, never by the orchestrator reading bodies into its own context. (maps FR#5 retry path, existing retry-prompt flow)
- **AC#3** Given identical reviewer findings, the assembled task verdict and the gate decision (auto-continue vs user gate) are identical to the pre-change behavior — including the deferred-vs-unresolved distinction, which is reconciled in a single fixer context. (maps FR#7, FR#10)
- **AC#4** A single pattern (`**Verdict:**`) *matches* the canonical line in all four reviewers' reports, replacing the current two-alternative grep (`**Verdict:**` / `**Overall verdict:**`); it matches integration-reviewer output, which the current grep does not. Parsing is per-file: code/integration carry a `(findings: N)` suffix, spec/visual do not. (maps FR#1, FR#2, FR#6)
- **AC#5** Reviewers invoked outside orchestrate (ship, commit-push, review, build, **address-pr-issues**, Phase-3) still return their full report. Verifiable by confirming the sentinel token appears only in orchestrate per-task dispatch prompts — `grep -rl <sentinel>` over the skill/command callers returns only the orchestrate per-task dispatch (the reviewer agent files themselves legitimately contain the token to *define* activation and are excluded from this check). (maps FR#3)
- **AC#6** MEDIUM/LOW findings on a passing task are still fixed (by the fixer) or explicitly deferred in the ledger — never silently skipped. (maps FR#5, FR#10)
- **AC#7** After the change, `orchestrate-cost` re-run on a sample run shows the orchestrator band's `cache_read` dropping materially versus the 033 baseline, and a compliance probe (grep a sample run's JSONL for multi-line reviewer return messages) reports the concise-return compliance rate. (maps Goals — measured cost win)

## Key Constraints

- **Concise-return must be gated on a literal sentinel + a file path** — never open-ended prose, and never when no file path is supplied. The default for the shared agents is unconditionally the full report. `code-reviewer` and `integration-reviewer` serve `/mine-ship`, `/mine-commit-push`, `/mine-review`, `/mine-build`, `/mine-address-pr-issues`, and Phase-3; `/mine-review` in particular passes no file path and reads the return message, so a path-less dispatch must always get the full report.
- **The canonical verdict-line format has one source of truth.** It is emitted by four files and parsed by the orchestrator; define it once (a shared format note the reviewers reference, with `<!-- SYNC -->` markers) and back it with a permanent self-check that reads the four reviewer files and verifies each specifies a conformant line — SYNC markers alone are honor-system (no tooling enforces them in this repo), so the self-check is the actual enforcement.
- **Do not change reviewer model declarations.** `code-reviewer` and `integration-reviewer` are pinned Sonnet pre-commit safety gates (`lint-agent-models` enforces this). This change touches their output contract, not their model.
- **Detection stays independent; classification stays single-context.** Findings are detected by the independent code/integration reviewers (unchanged). The defer-vs-unresolved classification that feeds the gate is made by a fixer pass that has read the latest review — never reconstructed by the orchestrator from counts or cross-agent IDs.
- **Preserve every `trail-log` call.** The trail audit checks the per-task event sequence; dropping a log call surfaces as a spurious audit finding.
- **The fixer gets a purpose-built prompt, not `retry-prompt.md` wholesale.** `retry-prompt.md` is framed for re-implementing a failing task (subtask sequencing, screenshot re-capture) and carries a `SYNC` header with `references/common/receiving-code-review.md`. The fixer does findings-only fixing — reuse only the verify-before-fix + YAGNI posture by reference, not the executor framing.

## Dependencies and Assumptions

- Assumes the run tmpdir persists across the per-task loop (already required for evidence/resume); the fixer ledger lives there.
- Assumes Sonnet reviewers reliably emit the single canonical line when instructed (a simple, deterministic instruction; extraction-from-file is the authoritative fallback if not).
- Depends on no external systems. Pure prompt/instruction redesign in skill + agent markdown, plus a new ledger artifact and a self-check.
- `agnix-check` and `lint-agent-models` (pre-commit) must continue to pass for the edited `agents/*.md` files.
- `orchestrate-cost` (repo tool) is available to measure AC#7.

## Architecture

Three moving parts: a **canonical verdict line** (single source of truth), a **lean consumption pattern** in the orchestrator, and a **dispatched fixer with a terminal ledger** replacing inline fixing.

### 1. Canonical verdict line + single source of truth (FR#1, FR#2)

Code & integration reviewers end their report with `**Verdict:** <VERDICT> (findings: <N>)`; spec & visual with `**Verdict:** <VERDICT>`. `<N>` is a single new-findings-only count, used solely to trigger the code/integration fixer. The `**Verdict:**` prefix is reserved for this line (visual's per-scenario lines → `**Scenario verdict:**`; spec's existing opening `**Verdict:**` *is* the canonical line; visual's `**Overall verdict:**` is replaced). The orchestrator extracts the **last line matching** `^\*\*Verdict:\*\*`.

The format is defined once in a shared note — `skills/mine-orchestrate/verdict-line-format.md` — referenced by the two orchestrate-local prompts and embedded in the two `agents/` files with a `<!-- SYNC: verdict-line-format.md -->` marker. A committed self-check (Test Strategy) reads the four reviewer files and fails if any specifies a non-conformant line. This fixes the latent bug where integration-reviewer's `**VERDICT: ...**` matches no grep alternative.

Edits:
- `agents/code-reviewer.md` — `### Assessment` `**Verdict:**` line gains `(findings: N)`; `Reasoning` may follow (extraction uses last-matching-line).
- `agents/integration-reviewer.md` — replace `**VERDICT: APPROVE / WARN / BLOCK**` with the canonical `**Verdict:** <VERDICT> (findings: N)` line; `## Pre-existing Issues` may follow.
- `skills/mine-orchestrate/spec-reviewer-prompt.md` — the opening `**Verdict:**` line stays (no count added).
- `skills/mine-orchestrate/visual-reviewer-prompt.md` — per-scenario `**Verdict:**` → `**Scenario verdict:**`; `**Overall verdict:**` → canonical `**Verdict:** <VERDICT>`.

### 2. Concise-return via sentinel + file path (FR#3)

A single literal token (e.g. `CONCISE-RETURN-MODE`) plus a supplied file path activates concise-return. The two shared agent files state: *default = full report; enter concise-return (final message = only the canonical verdict line) only when the dispatch contains the exact token `CONCISE-RETURN-MODE` AND provides an output file path; the full report is always written to the file in that case.* The two orchestrate-local prompt files state the same. The orchestrate Step 8/12 dispatch prompts include the token verbatim (and always provide a path). `/mine-review` and other path-less callers never get concise behavior.

### 3. Lean orchestrator consumption (FR#4, FR#6–FR#9)

- **Step 8** — replace "Read all output files" with extraction of the canonical lines from the three review files.
- **Step 9** — `tee` raw test/lint output to per-task logs; keep only a summary in context.
- **Step 12** — replace the inline read-and-fix loop with the dispatched fixer loop (§4).
- **Step 13** — replace the five `Read:` calls with a non-empty-file presence test plus reuse of the extracted verdict lines; a missing/unparseable line re-runs that reviewer.
- **Step 14** — assemble from the verdict lines + the terminal ledger (vocab mapping unchanged).
- **Step 10** (`warn-fix-loop.md`) — on a spec WARN, the orchestrator reads `spec-review.md` to classify (off happy path).

### 4. Dispatched fixer + terminal ledger (FR#5, FR#10) — replaces inline Step 12

Extracted to `skills/mine-orchestrate/findings-fix-loop.md` (mirroring `warn-fix-loop.md`); Step 12 becomes a short "read and follow" pointer. The file specifies, directly (not by reusing `retry-prompt.md`):

- **Dispatch:** `general-purpose`, `model: sonnet`. Inputs: code-review + integration-review file paths, changed-files list, design doc path. Constraints: fix findings only; do not re-run the task or re-capture screenshots.
- **Posture:** verify-before-fix + YAGNI (the shared stance from `receiving-code-review.md`, cited by reference — not the executor re-implementation framing).
- **Fix/defer policy:** identical wording to today's Step 12.
- **Ledger:** `<task_id>/fix-ledger.md`, overwritten each pass, classifying every finding the *current* review reports as `fixed | deferred(reason) | unresolved`. Rows are descriptive, not keyed — no cross-agent IDs.
- **Loop (orchestrator-driven), ending on a fixer pass:** initial Step 8 review = iteration 1; then alternate fixer pass → independent re-review, budget ≤2 fixer passes; if the budget ends on a re-review that still reports findings, run one final classify-mode fixer pass over that review.
- **Gate (orchestrator, Opus):** read the terminal ledger; any `unresolved` row → FAIL; deferred-only/empty → PASS.

This is the one **behavior change**: per-task findings fixing moves from the Opus orchestrator (inline) to a Sonnet subagent. Gate *computation* stays on Opus; detection stays with the independent reviewers; the defer/fix *judgment quality* moves to Sonnet (named below). User-approved during define.

## Replacement Targets

- **Step 12 inline read-and-fix loop** (`SKILL.md:436–460`) — replaced by the dispatched fixer + terminal ledger in `findings-fix-loop.md`.
- **Step 8 "Read all output files"** (`SKILL.md:385`) — replaced by extraction of canonical verdict lines.
- **Step 13 five `Read:` calls** (`SKILL.md:466–472`) — replaced by presence test + verdict-line reuse.
- **integration-reviewer `**VERDICT: ...**` summary line** — replaced by the canonical `**Verdict:**` line.
- **visual-reviewer per-scenario `**Verdict:**` and `**Overall verdict:**`** — renamed/replaced so `**Verdict:**` is reserved for the canonical line.
- **`**Overall verdict:**` alternative in the Step 13 grep** — removed once all four reviewers emit `**Verdict:**`.

These are removed/migrated, not left alongside the new flow.

## Convention Examples

### Pattern: a "read and follow" supporting-file pointer (how Step 12 should look after extraction)

**Source:** `skills/mine-orchestrate/SKILL.md:422-424` (Step 10)

```markdown
### Step 10: WARN fix loop (if spec reviewer returned WARN)

Read `${CLAUDE_CONFIG_DIR:-~/.claude}/skills/mine-orchestrate/warn-fix-loop.md` and follow it.
```

### Pattern: a self-contained loop supporting file (model for findings-fix-loop.md)

**Source:** `skills/mine-orchestrate/warn-fix-loop.md:1-17`

```markdown
# WARN Fix Loop (Step 10)
...
3. **Re-run the executor (Step 5)** ...
4. **Re-capture changed files (Step 6)** ...
6. **Re-run the parallel review pass (Step 8)** ...
```

### Pattern: passing file paths to a subagent (not contents) — the existing lean idiom

**Source:** `skills/mine-orchestrate/retry-prompt.md:71-75`

```markdown
## Reviewer Files

The orchestrator provides paths to reviewer output files. **Read each file in full before touching any code.** Do not rely on summaries.
```

### Pattern: caller-aware reviewer behavior (model for the concise-return sentinel branch)

**Source:** `agents/code-reviewer.md:23-25`

```markdown
## Invocation patterns
- **Orchestrate pipeline** (`mine-orchestrate`): passes explicit file list in prompt — use that list, skip self-discovery
- **Ship / commit-push / build / manual**: no file list provided — use the self-discovery cascade below
```

### Pattern: a greppable finding marker (code-reviewer)

**Source:** `agents/code-reviewer.md:163-166`

```text
[CRITICAL] SQL Injection vulnerability
File: app/routes/user.py:42
```

## Alternatives Considered

- **Keep fixing on the orchestrator, optimize only the truly-clean path** (the "Reduce" scope). Rejected by the user during define: a PASS-with-auto-fixes task still pulls full reports inline — only a partial win, failing AC#1 for findings-bearing happy-path tasks.
- **Convey post-fix state via two counts (reviewer re-count + fixer "M deferred")** — first draft. Rejected (round-1 challenge): counts carry cardinality, not identity, so a fixer-deferred finding the re-review re-reports cannot be distinguished from an unresolved one.
- **A ledger keyed by `finding-id` that the orchestrator matches against re-review counts** — second draft. Rejected (re-challenge): no reviewer emits stable IDs (`path:line` shifts after edits, `[SEVERITY] title` is rephrased across runs), the fixer and re-reviewer are different agent instances with no shared ID space, and under AC#1 the orchestrator can't read the re-review body to match anyway — so reconciliation collapsed back to count-subtraction. Replaced by the terminal-fixer model: the fixer reads the latest review and classifies in one context; the orchestrator counts only `unresolved` rows.
- **A blocking/advisory count split on the verdict line** — first draft. Rejected: nothing branches on the split; collapsed to a single new-findings count, code/integration only.
- **Make reviewers globally return only a verdict line, or gate concise-return on fuzzy prose.** Rejected — breaks/leaks into the full-report callers. Concise-return is gated on a literal sentinel + a file path, default full.
- **Keep the spec-WARN structural/fixable tag on the reviewer's verdict line.** Rejected: the spec reviewer doesn't classify today, porting the taxonomy duplicates it across two files, and WARN is off the happy path — so the orchestrator reads spec-review on WARN (FR#8).
- **Do nothing.** Rejected — the orchestrator loop is the #1 cost and the main 500k-token pressure; this is the highest-leverage 033 lever.

## Test Strategy

This repo has no unit-test harness for skill/agent **prose behavior**. Verification is structural, observational, and — for the cost claim — measured.

### Existing Tests to Adapt
No automated tests cover orchestrate behavior. `agnix-check` (schema/frontmatter) and `lint-agent-models` (model-declaration) pre-commit hooks cover the edited `agents/*.md` files and must continue to pass.

### New Test Coverage
- **Permanent verdict-line conformance check** (committed, per build-the-lever — not a throwaway): a check that reads the four reviewer files (`code-reviewer.md`, `integration-reviewer.md`, `spec-reviewer-prompt.md`, `visual-reviewer-prompt.md`) and verifies each specifies a canonical line conformant to `verdict-line-format.md` (correct prefix; count present for code/integration, absent for spec/visual). Fails pre-commit when any reviewer's line drifts. This — not the honor-system SYNC markers — is the real enforcement. Addresses AC#4 and the change-amplification risk.
- **Concise-return leak check**: `grep -rl CONCISE-RETURN-MODE` over the skill/command callers (excluding the reviewer agent files that define the token) confirms it appears only in orchestrate per-task dispatch (AC#5).
- **Cost measurement (AC#7)**: re-run `orchestrate-cost` on a sample run after the change; confirm the orchestrator band `cache_read` drops materially vs the 033 baseline. Plus a compliance probe: grep a sample run's JSONL for multi-line reviewer return messages to report the concise-return compliance rate.
- **Fidelity walk-through**: trace Step 14 verdict assembly and the FR#10 terminal-ledger gate for the PASS-with-deferred-finding and the fixer-introduced-regression cases, confirming the gate outcome matches today (AC#3, AC#6).

### Tests to Remove
None.

## Documentation Updates

- **`REFERENCE.md`** — `findings-fix-loop.md` and `verdict-line-format.md` need no entry (supporting files inside an existing skill directory). The two new `bin/` scripts *do* get rows in the Helper Scripts table per the CLAUDE.md mandate: **`bin/orchestrate-concise-probe`** (T04) and **`bin/lint-verdict-line`** (T01, a pre-commit lint hook listed alongside its siblings `lint-agent-models` and `lint-cli-conventions`, which are already in the table).
- **No capabilities-file change** — no new trigger phrases.
- **No `ONBOARDING.md` change** — internal cost optimization.

## Impact

### Changed Files
- `skills/mine-orchestrate/SKILL.md` — modify (Steps 8, 9, 12, 13, 14; Step 10 ref): extract verdicts; sentinel dispatch; presence-test gate; fixer-loop pointer; ledger-based assembly.
- `agents/code-reviewer.md` — modify: canonical verdict line with count; concise-return sentinel+path branch; SYNC marker. (shared agent — higher risk)
- `agents/integration-reviewer.md` — modify: canonical verdict line replacing `**VERDICT: ...**`; concise-return sentinel+path branch; SYNC marker. (shared agent — higher risk; fixes latent grep bug)
- `skills/mine-orchestrate/spec-reviewer-prompt.md` — modify: reserve `**Verdict:**` for the canonical line (no count); concise-return sentinel+path.
- `skills/mine-orchestrate/visual-reviewer-prompt.md` — modify: rename per-scenario lines; canonical line replaces `**Overall verdict:**`; concise-return sentinel+path.
- `skills/mine-orchestrate/warn-fix-loop.md` — modify: on spec WARN the orchestrator reads spec-review to classify (no reviewer self-tag).
- `skills/mine-orchestrate/findings-fix-loop.md` — create: the dispatched fixer + terminal-ledger loop (purpose-built prompt; iteration accounting; classify-mode terminal pass).
- `skills/mine-orchestrate/verdict-line-format.md` — create: single source of truth for the canonical line, referenced by all four reviewers.
- Permanent verdict-line conformance check — create (location per repo convention for checks, e.g. `bin/` + pre-commit hook).
- `bin/orchestrate-concise-probe` — create: read-only probe reporting the concise-return compliance rate from a run's JSONL (AC#7).
- `design/specs/034-orchestrate-verdict-only/measurement.md` — create: the cost-measurement runbook (AC#7).

### Behavioral Invariants
- Task verdict and gate decision identical for identical findings, including deferred-vs-unresolved (AC#3, via the terminal-fixer ledger).
- FAIL/retry path unchanged (paths to executor; executor reads).
- Shared reviewers' behavior for non-orchestrate callers unchanged (AC#5); path-less callers always get the full report.
- MEDIUM/LOW findings still fixed or explicitly deferred (AC#6).
- All `trail-log` call sites preserved.
- Reviewer model pins unchanged.
- **Named trade:** the fix/defer *judgment quality* moves from the Opus orchestrator (full run context) to a Sonnet fixer (review paths + changed files + design doc). Finding *detection* stays with the independent reviewers and gate *computation* stays on Opus (via the ledger), but *which* MEDIUM/LOW items get fixed-vs-deferred is now Sonnet's call. Accepted as the consequence of delegating fixing (chosen during define); surfaced in the ledger and the Step 15 summary so the distribution stays visible.

### Blast Radius
- **`code-reviewer` and `integration-reviewer` are shared** across `/mine-ship`, `/mine-commit-push`, `/mine-review`, `/mine-build`, `/mine-address-pr-issues`, and Phase-3. The verdict-line format change is additive; the concise-return change is sentinel+path-gated. Both must be verified not to alter what those callers see (AC#5). Per the round-1 contract investigation, every one of those callers consumes the reviewer's full report via an LLM (none deterministically parses the verdict string), so the additive reformat does not break them — but the verification set must include all six.
- Phase-3 consumes the same reviewers — it sees the new canonical line but is otherwise unchanged.

## Open Questions

None.
