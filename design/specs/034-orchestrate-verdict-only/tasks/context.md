# Context: mine-orchestrate — retain only verdicts on the happy path

## Problem & Motivation

`mine-orchestrate` runs as one long-lived **Opus** conversation (~154 turns/run). Every file the orchestrator `Read`s persists in its context and is re-billed as `cache_read` on every subsequent turn. The 033 cost analysis found the orchestrator loop is the #1 cost bucket (~60% of spend, 98% `cache_read`) because, per task, it reads ~6 full review report files into its own context (Step 8 reads all reviews; Step 12 reads code+integration reviews and fixes inline; Step 13 re-reads all five). A report read on task 1 is re-cached every turn through task N. This is also the main driver of ~500k-token sessions. On the happy path the orchestrator only needs the verdict and whether findings exist — full detail matters only when acting on findings (FAIL/retry, already lean). The fix: keep only verdict lines in the orchestrator's context; read detail only in ephemeral subagent contexts.

## Visual Artifacts

None.

## Key Decisions

1. **Canonical verdict line, one source of truth.** Every reviewer ends its report with a line the orchestrator greps instead of reading the body. Code & integration: `**Verdict:** <VERDICT> (findings: N)`; spec & visual: `**Verdict:** <VERDICT>` (no count). The `**Verdict:**` prefix is reserved for this one line. Format defined once in `verdict-line-format.md`; a permanent conformance check enforces it (SYNC markers are honor-system). This also fixes a latent bug: integration-reviewer's current `**VERDICT: ...**` matches neither alternative of the existing Step 13 grep.
2. **`(findings: N)` is single, new-findings-only, code/integration only.** No blocking/advisory split (it drove no decision). Pre-existing findings are excluded (reviewers already exclude them from the verdict). N answers one question: does the fixer need to run? Spec/visual carry no count — they route by verdict word.
3. **Concise-return via sentinel + file path.** In orchestrate mode the reviewer's *return message* is only its canonical verdict line (so the auto-injected message doesn't bloat context); the full report always goes to the file. Activated only when the dispatch contains the literal token `CONCISE-RETURN-MODE` **and** supplies an output file path. Default (and any path-less caller like `/mine-review`) = full report. Correctness never depends on compliance — the file is authoritative.
4. **Dispatched fixer + terminal ledger replaces inline Step 12 fixing.** When code/integration report findings, a Sonnet fixer subagent reads the reviews in its own context, applies fixes, and writes a ledger classifying every finding the current review reports as `fixed | deferred(reason) | unresolved`. The orchestrator alternates fixer pass → independent re-review, ending on a fixer pass, then gates on the terminal ledger's `unresolved` rows. Detection stays with the independent reviewers; defer-vs-unresolved classification stays in one fixer context that read the latest review (mirroring today's orchestrator-as-fixer); the orchestrator never matches findings across agents and never reads a body.
5. **Lean orchestrator consumption.** Step 8 extracts verdict lines (no body read); Step 9 tees raw test/lint output to logs (summary only in context); Step 12 points to `findings-fix-loop.md`; Step 13 uses a presence test + the extracted verdicts; Step 14 assembles from verdict lines + ledger. On a spec WARN, the orchestrator reads `spec-review.md` to classify (off happy path, infrequent).
6. **Measured win.** After the change, re-run `orchestrate-cost` against the 033 baseline to confirm the orchestrator `cache_read` band drops; a compliance probe measures concise-return adherence.

## Constraints & Anti-Patterns

- **Gate decisions stay computable on the Opus orchestrator.** The fixer applies fixes and classifies; the orchestrator computes PASS/WARN/FAIL from verdict lines + the ledger. Do not move gate computation to a subagent.
- **Detection stays independent; classification stays single-context.** Never reconstruct deferred-vs-unresolved in the orchestrator from counts or cross-agent finding IDs — that approach was explicitly rejected (no reviewer emits stable IDs; the orchestrator can't read bodies). The terminal fixer classifies the latest review in its own context.
- **Concise-return must never leak to full-report callers.** `code-reviewer`/`integration-reviewer` are shared with `/mine-ship`, `/mine-commit-push`, `/mine-review`, `/mine-build`, `/mine-address-pr-issues`, and Phase-3. The default is unconditionally the full report; concise-return requires the exact sentinel **and** a file path. `/mine-review` passes no path → must get the full report.
- **Do not change reviewer model declarations.** `code-reviewer` and `integration-reviewer` are pinned Sonnet pre-commit safety gates (`lint-agent-models` enforces this). Touch the output contract, not the model.
- **The fixer gets a purpose-built prompt — not `retry-prompt.md` wholesale.** `retry-prompt.md` is framed for re-implementing a failing task and carries a `SYNC` header with `references/common/receiving-code-review.md`. Reuse only the verify-before-fix + YAGNI posture by reference; do not import the executor framing or drift the SYNC'd file.
- **Preserve every `trail-log` call.** The trail audit checks the per-task event sequence; a dropped call surfaces as a spurious audit finding.
- **Non-goals:** Phase-3 post-execution pipeline is out of scope (it runs once at end-of-run; reads persist for far fewer turns). Orchestrator→Sonnet is parked. Proactive mid-run resume (#411) is a separate issue. Do not change what reviewers check or their severity criteria.

## Design Doc References

- `## Architecture` — the three moving parts (canonical line + SoT, lean consumption, dispatched fixer + terminal ledger) with per-file edits.
- `## Functional Requirements` (FR#1–10) and `## Acceptance Criteria` (AC#1–7) — the contract each task implements/verifies.
- `## Edge Cases` — reviewer crash, wrong count, fixer regression, deferred-reappears, concise non-compliance, multiple verdict lines, pre-existing exclusion, resume, the latent integration grep bug.
- `## Key Constraints` — sentinel+path gating, single source of truth + permanent check, model pins, detection/classification split, trail-log preservation, fixer prompt.
- `## Replacement Targets` — what is removed/migrated (inline Step 12, Step 8 "Read all output files", Step 13 Reads, integration `**VERDICT:**` line, visual verdict lines, the `**Overall verdict:**` grep alternative).
- `## Impact → Changed Files` and `### Behavioral Invariants` — file inventory and behaviors that must not change.

## Convention Examples

### Pattern: a "read and follow" supporting-file pointer (how Step 12 should look)

**Source:** `skills/mine-orchestrate/SKILL.md:422-424` (Step 10)

```markdown
### Step 10: WARN fix loop (if spec reviewer returned WARN)

Read `${CLAUDE_HOME:-~/.claude}/skills/mine-orchestrate/warn-fix-loop.md` and follow it.
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

### Pattern: passing file paths to a subagent, not contents (the lean idiom)

**Source:** `skills/mine-orchestrate/retry-prompt.md:71-75`

```markdown
## Reviewer Files

The orchestrator provides paths to reviewer output files. **Read each file in full before touching any code.** Do not rely on summaries.
```

### Pattern: caller-aware reviewer behavior (model for the concise-return branch)

**Source:** `agents/code-reviewer.md:23-25`

```markdown
## Invocation patterns
- **Orchestrate pipeline** (`mine-orchestrate`): passes explicit file list in prompt — use that list, skip self-discovery
- **Ship / commit-push / build / manual**: no file list provided — use the self-discovery cascade below
```

### Pattern: a pre-commit check wired like the existing model-lint (model for the conformance check)

**Source:** `.pre-commit-config.yaml:29-34`

```yaml
      - id: lint-agent-models
        name: Agent registry sync (models + install.py)
        entry: bin/lint-agent-models
        language: system
        pass_filenames: false
        always_run: true
```
