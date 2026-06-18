---
tool: claude, codex, antigravity
---

# Performance Discipline

<!-- SYNC: rules/common/invariants.md — update the corresponding invariant entry when changing this rule. -->

When investigating a measured slowness, the evidence is the trace. Hypotheses without profiling data are guesses. See also `debugging-discipline.md` for the same evidence-first approach applied to bug fixing.

## Baseline First

Capture a baseline trace or measurement before changing anything. Without a baseline, you cannot prove the fix improved anything. The baseline is the artifact you compare against, not a feeling that "it was slow before."

## Ground Hypotheses in Traces

Do not guess at the bottleneck. Profile, read the trace, and let the data point to the hot path. Common tools: browser DevTools Performance tab, `perf`, `py-spy`, `flamegraph`, framework-specific profilers.

Form hypotheses from what the trace shows, not from what you expect to be slow. Intuition about performance is frequently wrong.

## Fix From the Trace

Address the specific bottleneck the trace identified. Do not scatter optimizations across the codebase hoping one helps. Each change should target a measured hot path.

## Compare Artifacts

After fixing, capture a new trace or measurement and compare it against the baseline. The improvement must be visible in the data. "It feels faster" is not verification.

If the fix did not move the metric, revert it. A performance change that cannot be measured is not a performance improvement.
