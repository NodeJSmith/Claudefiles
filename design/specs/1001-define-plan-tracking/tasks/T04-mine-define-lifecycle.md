---
task_id: "T04"
title: "Add cfl lifecycle tracking to mine-define"
status: "done"
depends_on: ["T03"]
implements: ["FR#11"]
---

## Summary
Update the mine-define skill file to emit cfl calls at each lifecycle point. The key structural change is resequencing `cfl spec init` + `cfl run start --phase define` from Phase 4 to Phase 1 (after the slug is derived), so a run_id exists before Phase 2/3 emit dispatches and events. All other phases gain cfl event, gate, and dispatch calls at their natural completion points.

## Target Files
- modify: `skills/mine-define/SKILL.md`
- read: `design/specs/1001-define-plan-tracking/design.md`

## Prompt
### Phase 1 resequencing

In Phase 1 ("Scope and Classify"), after the "Assess complexity" section (around line 50 where the slug is derived), add a new subsection:

```markdown
### Initialize tracking

After deriving the slug:

1. If `$ARGUMENTS` pointed to an existing `design/specs/NNN-*/` directory and a spec already exists in cfl, skip `cfl spec init`. Otherwise run:

```bash
cfl spec init <slug>
```

Record the `dir` field from the output as the feature directory.

2. Determine run state:

```bash
cfl run status
```

- If the output has `"exists": true` — an active run exists. Resume it (no new run needed). Record the `run_id` for subsequent cfl calls.
- If the output has `"exists": false` — try resuming a stopped run:

```bash
cfl run resume
```

If this succeeds, the stopped run is now active again with its original run_id and phase preserved. If it errors with `no_stopped_run`, create a new run:

```bash
cfl run start --phase define --base-commit $(git rev-parse --short HEAD)
cfl event define.started
```
```

### Remove Phase 4 spec init

In Phase 4 ("Write design.md"), the existing "Initialize the feature directory" subsection (around lines 386-396) runs `cfl spec init`. Remove this subsection — it has moved to Phase 1. Replace it with a note:

```markdown
### Write to the feature directory

The feature directory was created in Phase 1's "Initialize tracking" step. Write design.md to `<feature_dir>/design.md`.
```

Keep the "Design context check" subsection and "Write design.md" subsection unchanged.

### Phase 2 event

After the "Proportional Discovery" phase completes (end of Phase 2, after the "Confirm intent summary" or "Convention examples checkpoint" step), add:

```markdown
### Record discovery completion

```bash
cfl event define.discovery-complete
```
```

### Phase 3 dispatch

In Phase 3 ("Investigate"), after the researcher subagent completes and its output is verified, add:

```markdown
### Record researcher dispatch

After the researcher subagent completes, record the dispatch:

```bash
cfl dispatch researcher --agent-type researcher --model opus
```

Record the `dispatch_id` from the output. Then:

```bash
cfl dispatch end <dispatch_id>
```
```

Skip this if the researcher was not dispatched (trivial features, or existing research brief reused).

### Phase 4 event

After the design doc is written to disk, add:

```markdown
```bash
cfl event define.design-written
```
```

### Phase 5 gate

After the quality validation checklist passes (or fails and is fixed), add:

```markdown
```bash
cfl gate define-quality --verdict <PASS|FAIL>
```
```

Where verdict is PASS if all 19 checks passed, FAIL if any blocked.

### Phase 5.5 comb gate

After the fine-toothed comb agent completes, add dispatch tracking around it. Before dispatching:

```markdown
```bash
cfl dispatch define-comb --agent-type fine-toothed-comb --model sonnet
```
```

After the comb completes:

```markdown
```bash
cfl dispatch end <dispatch_id>
cfl gate define-comb --verdict <v>
```

Verdict mapping: no findings → PASS, minor findings accepted → WARN, blocking findings → FAIL.
```

### Phase 6 sign-off gate

After the user makes their sign-off choice, record the gate:

```markdown
```bash
cfl gate define-signoff --verdict <v>
cfl event define.signed-off
```

Verdict mapping:
- "Approve — proceed to planning" → PASS
- "Revise — I have changes" → WARN (loop continues; re-emit on each revision cycle)
- "Save and stop" → SKIPPED
- "Gap-close first" → no gate emitted (gap-close runs, then re-enters sign-off)

Only emit `cfl event define.signed-off` when the verdict is PASS (approved). On Revise, Save-and-stop, or Gap-close, the event is not emitted — no decision was finalized.
```

## Focus
- The phase resequencing moves `cfl spec init` from Phase 4 to Phase 1. This means the feature directory exists earlier, which is fine — Phase 4's design doc write just uses the directory that Phase 1 already created.
- The three-branch run detection (active/stopped/new) is important for the resume edge case. `cfl run resume` auto-picks the most recent stopped run for the spec when no `--run-id` is given.
- Dispatch tracking uses role names as the first positional arg to `cfl dispatch`. The `--agent-type` and `--model` flags are optional metadata. The `dispatch_id` from the output must be captured for the `cfl dispatch end` call.
- Phase 5's quality validation is a checklist run by the planner itself (not a subagent), so it gets a gate but no dispatch.
- The `cfl event` calls are fire-and-forget — they never error, even if the run_id is invalid.

## Verify
- [ ] FR#11: mine-define SKILL.md contains cfl calls at: run start + define.started event (Phase 1), discovery-complete event (Phase 2), researcher dispatch/end (Phase 3), design-written event (Phase 4), define-quality gate (Phase 5), define-comb dispatch/gate (Phase 5.5), define-signoff gate + signed-off event (Phase 6)
