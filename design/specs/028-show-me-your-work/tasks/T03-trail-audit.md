---
task_id: "T03"
title: "Add trail audit step and shipping gate update"
status: "planned"
depends_on: ["T01", "T02"]
implements: ["FR#7", "FR#8", "AC#5"]
---

## Summary
Add the trail audit step (Step 5.5) to the post-execution pipeline and update the shipping gate question to include audit findings. The audit is a single Sonnet subagent that reads the full trail and checks for structural anomalies using an explicit expected-sequence grammar. Findings are informational — they do not block shipping.

## Prompt
Read `design/specs/028-show-me-your-work/design.md` section `## Architecture > Post-run audit (Phase 3, Step 5.5)` for the full audit subagent prompt specification, and `## Architecture > Shipping gate update` for the gate text change.

Modify `skills/mine.orchestrate/post-execution-pipeline.md`:

### Add Step 5.5 (between Step 5 and Step 6, after line ~182)

Insert a new section: `## Step 5.5: Trail audit (automatic)`

The step launches a single `general-purpose` subagent with `model: sonnet`. The subagent prompt is specified in the design doc and includes:
- The trail file path derived from `feature_dir`
- An explicit expected-sequence grammar: `start → [dispatch] → [contested*] → [gate] → [retry*] → [review] → [fix*] → verdict`
- Five structural checks: missing entries, sequence anomalies, retry patterns, timing outliers, empty detail fields
- An explicit instruction NOT to verify content veracity
- A structured output requirement: `## Summary` line with finding count
- Output path: `<feature_dir>/trail-audit.md`

After the subagent completes, read `<feature_dir>/trail-audit.md` and extract the finding count from the `## Summary` line. If the report is missing or the subagent failed, use "failed to complete" as the status.

Also log a trail entry for the audit itself: `log.sh <trail_path> p3 - review "trail audit: N findings"` (or "trail audit: failed to complete").

### Update Step 6 shipping gate question (around line ~188-189)

Add a new field to the existing shipping gate question string. The current question is:

```
"All tasks complete. Implementation review: <...>. Cross-file review: <...>. Clean code check: <...>. Structural simplification: <...>. Final review: <...>. What next?"
```

Insert after the Final review field:

```
Trail audit: <N findings — or 'no findings' — or 'failed to complete'>.
```

If the log failure counter from T02 is > 0, also include: `Trail logging: N write failures.`

The shipping gate options remain unchanged — the audit is informational.

### Edge case handling
- If the trail file does not exist (trail logging was unavailable per T02's Phase 0 probe), skip Step 5.5 entirely and show "Trail audit: skipped (trail unavailable)" at the shipping gate
- If the audit subagent fails or produces no output, show "Trail audit: failed to complete" at the shipping gate — do not block

## Focus
- The post-execution pipeline requires all Phase 3 subagents to run in foreground (`post-execution-pipeline.md:5`) — do not set `run_in_background: true`
- The audit report goes to `<feature_dir>/trail-audit.md` (alongside `trail.tsv`), NOT to the ephemeral tmpdir. This is intentional — it persists across session boundaries
- The expected-sequence grammar in the audit prompt must match the call-site table from T02. If T02 changes the call sites, the grammar here must be updated to match
- The shipping gate question string is at `post-execution-pipeline.md` lines ~188-189. It is a single AskUserQuestion with a long question field — append the new fields to the existing string
- Follow the Step 4/4.5 pattern for formatting the new step: heading level, description, subagent launch, result handling

## Verify
- [ ] FR#7: After Phase 3 completes, `trail-audit.md` exists in the feature directory and contains a `## Summary` line with a finding count
- [ ] FR#8: The shipping gate question includes "Trail audit: N findings" (or variant) alongside existing review results, and the audit does not block shipping (same gate options as before)
- [ ] AC#5: The Phase 3 shipping gate includes audit findings (or "no findings") alongside the existing impl-review and clean-code results
