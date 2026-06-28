# Cost Measurement Runbook — 034 orchestrate verdict-only

**AC#7 measurement procedure.** Run this after a real orchestrate run on the post-change
codebase. The cost comparison cannot be produced at build time — this runbook makes it
a one-command follow-up rather than guesswork.

---

## Baseline (033 findings)

From `design/specs/033-orchestration-cost-analysis/findings.md`, dataset of 30 runs
(2026-06-11 … 2026-06-26):

| Metric | 033 baseline |
|---|---|
| Runs measured | 30 |
| Total spend | ~$2,068 |
| Mean per run | ~$69 |
| Orchestrator loop total | ~$1,240 (~60% of spend) |
| Orchestrator own-gen | ~$129 |
| Orchestrator absorbed | ~$1,111 |
| Absorbed breakdown | **98% `cache_read`** (1.55B tokens across 30 runs) |
| Mean absorbed per run | ~$37 |

The absorbed band is dominated by `cache_read` because the orchestrator re-reads
accumulated full review reports on every turn. The 034 change targets this directly —
on the happy path the orchestrator absorbs only verdict lines, not full report bodies.

---

## After-measurement procedure

### 1. Confirm at least one complete post-change run is available

The `orchestrate-cost` tool delimits runs from durable trail markers in parent-session
JSONLs. Verify a run landed by checking that `orchestrate-cost` reports at least one run
whose start marker falls on or after the merge date.

### 2. Run orchestrate-cost against the post-change sample

```bash
# Replace YYYY-MM-DD with the date this feature was merged to main.
orchestrate-cost --since YYYY-MM-DD
```

For machine-readable output (useful for scripting or diffing):

```bash
orchestrate-cost --since YYYY-MM-DD --json
```

### 3. Read the orchestrator band from the output

In the table output, find the two orchestrator rows:

```
role                   model        calls       total   mean/call    %
----------------------------------------------------------------------
orchestrator (own-gen)   —            N          $X.XX      $X.XX    N%
orchestrator (absorbed)  —            N          $X.XX      $X.XX    N%
```

**The key metric is `orchestrator (absorbed)` — specifically its per-run mean.**

In JSON output, the field is:

```
.orchestrator_band.absorbed   # total absorbed across all selected runs
.per_run.n                    # divide to get mean per run
```

Per-run mean absorbed = `.orchestrator_band.absorbed` / `.per_run.n`

### 4. Success criterion

**The orchestrator band's `absorbed` cost per run drops materially versus the 033
baseline of ~$37/run mean.**

"Materially" means a reduction visible beyond measurement noise — a 20%+ drop is
a strong signal; a 5% or smaller change is within noise given the attribution
heuristics in `orchestrate-cost` (prompt-signature drift, session-window inflation).
No specific threshold is hard-coded here because the realized saving depends on task
count and how many tasks hit the fixer path.

If the number is roughly unchanged, the most likely explanation is that concise-return
is not being honored (check the compliance probe below) or that the change is not
yet active on the measured runs.

---

## Compliance probe

The compliance probe checks whether reviewer subagents dispatched in orchestrate
mode are actually returning a single `**Verdict:**` line rather than a full report.
A non-compliant reviewer still writes its full report to the output file (correctness
is unaffected), but the return-message leak into the orchestrator's context is not
eliminated — the cost win is lost for that dispatch.

### Run the probe

Against a specific post-change orchestrate parent-session JSONL:

```bash
# Find the JSONL path for a recent orchestrate run:
ls -lt "${CLAUDE_HOME:-~/.claude}"/projects/*/  | grep '\.jsonl' | head -20

# Then probe it:
orchestrate-concise-probe "${CLAUDE_HOME:-~/.claude}"/projects/<project-dir>/<session-uuid>.jsonl
```

Or scan all runs since the merge date:

```bash
orchestrate-concise-probe --since YYYY-MM-DD
```

For machine-readable output:

```bash
orchestrate-concise-probe --since YYYY-MM-DD --json
```

### Interpret the output

The probe reports a compliance rate per reviewer role (code-reviewer,
integration-reviewer, spec-reviewer, visual-reviewer) and a global rate:

```
concise-return compliance: 34/34 (100%)

  role                     dispatches compliant   rate
  -------------------------------------------------------
  code-reviewer                    17        17   100%
  integration-reviewer             17        17   100%
```

- **100%** — all reviewer return messages are single verdict lines; the context-leak
  is closed and the cost reduction should be visible in orchestrate-cost output.
- **0% (or near 0%)** — reviewers are returning their full reports. The
  `CONCISE-RETURN-MODE` sentinel instruction is present in the dispatch prompt but the
  reviewer is not complying. Check that the sentinel is literally included in the
  orchestrate Step 8/12 dispatch prompt and that the reviewer agent file's
  concise-return branch is correctly conditioned.
- **Mixed** — partial compliance. Check non-compliant dispatches listed in the output
  (each shows the role, feature, return-line count, and subagent JSONL path).

Non-compliant dispatches do not affect task correctness — the reviewer output file
is always the authoritative source. A low compliance rate signals the
concise-return instruction needs strengthening in the agent or dispatch prompt.

---

## Notes

- **A real orchestrate run is required.** The probe and `orchestrate-cost` both read
  actual JSONL transcripts. Neither can produce a measurement at build time against
  synthetic data.
- **Attribution is heuristic.** `orchestrate-cost` uses prompt-signature matching and
  timestamp windowing (documented in its source). Run count is a lower bound.
  Single-run measurements have higher noise than the 033 30-run dataset; collect
  several runs before drawing firm conclusions.
- **The compliance probe is a permanent lever.** It can be re-run against any past or
  future orchestrate session JSONL to monitor concise-return adherence over time.
  See `bin/orchestrate-concise-probe --help` for the full interface.
