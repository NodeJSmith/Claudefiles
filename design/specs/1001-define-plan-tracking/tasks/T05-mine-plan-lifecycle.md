---
task_id: "T05"
title: "Add cfl lifecycle tracking to mine-plan"
status: "done"
depends_on: ["T03"]
implements: ["FR#12"]
---

## Summary
Update the mine-plan skill file to emit cfl calls at each lifecycle point. At startup, detect whether a run exists (from mine-define) and either advance it to `plan` phase or create a new one. Then emit events, dispatches, and gates at each phase boundary through the plan workflow.

## Target Files
- modify: `skills/mine-plan/SKILL.md`
- read: `design/specs/1001-define-plan-tracking/design.md`

## Prompt
### Before Phase 1 — run state detection

Add a new section before Phase 1 ("Read the Design Doc"), after the branch staleness pre-flight:

```markdown
### Initialize plan tracking

Determine the run state for this spec:

```bash
cfl run status
```

Branch on the result:

- `"exists": true` and `"phase": "define"` — advance to plan phase:
```bash
cfl run advance-phase plan
cfl event plan.started
```

- `"exists": true` and `"phase": "plan"` — already in plan phase. Resume. Emit `cfl event plan.started` only if this is a fresh entry (not a revision loop re-entry).

- `"exists": true` and `"phase": "orchestrate"` — the run has already advanced past plan. This shouldn't happen in normal flow. Emit a warning and proceed without phase tracking.

- `"exists": false` — no active run. Try resuming a stopped run:
```bash
cfl run resume
```

If resume succeeds, the run is active again with its original phase. If the phase is `define`, advance to `plan`. If already `plan`, proceed.

If resume errors with `no_stopped_run`, create a new run:
```bash
cfl run start --phase plan --base-commit $(git rev-parse --short HEAD)
cfl event plan.started
```
```

### Phase 3 event — after task files written

After Phase 3 ("Write Task Files") completes (both context.md and all T*.md files are written), add:

```markdown
```bash
cfl event plan.tasks-written --data '{"task_count": <N>}'
```

Where N is the number of task files generated.
```

### Phase 3.5 dispatch and gate — validation

In Phase 3.5 ("Validation Gate"), wrap the validator subagent dispatch with cfl tracking. Before dispatching:

```markdown
```bash
cfl dispatch plan-validator --agent-type general-purpose --model sonnet
```
```

After the validator completes:

```markdown
```bash
cfl dispatch end <dispatch_id>
cfl gate plan-validation --verdict <PASS|FAIL>
```
```

### Phase 4 gate — spec validate

After `cfl spec validate` runs (lines 335-336 of the current SKILL.md), record the gate:

```markdown
```bash
cfl gate plan-spec-validate --verdict <v>
```

Verdict mapping: clean output → PASS, warnings → WARN, errors → FAIL.
```

### Phase 5 dispatch and gate — review

In Phase 5 ("Review"), wrap the reviewer subagent dispatch with cfl tracking. Before dispatching:

```markdown
```bash
cfl dispatch plan-reviewer --agent-type general-purpose --model sonnet
```
```

After the reviewer completes:

```markdown
```bash
cfl dispatch end <dispatch_id>
cfl gate plan-review --verdict <v>
```

Verdict mapping: reviewer PASS → PASS, reviewer FAIL → FAIL, reviewer ABANDON → FAIL (ABANDON is not a valid cfl gate verdict; map it to FAIL since it blocks the plan).
```

### Phase 5.5 comb dispatch and gate

In Phase 5.5 ("Fine-Toothed Comb Review"), wrap the comb agent dispatch with cfl tracking. Before dispatching:

```markdown
```bash
cfl dispatch plan-comb --agent-type fine-toothed-comb --model sonnet
```
```

After the comb completes:

```markdown
```bash
cfl dispatch end <dispatch_id>
cfl gate plan-comb --verdict <v>
```

Verdict mapping: no findings → PASS, minor findings accepted → WARN, blocking findings → FAIL.
```

### Phase 6 gate — approval

After the user makes their approval choice in Phase 6 ("Gate"), record the gate:

```markdown
```bash
cfl gate plan-approval --verdict <v>
cfl event plan.approved
```

Verdict mapping:
- "Approve as-is" / "Approve with suggestions" → PASS
- "Revise the plan" → WARN (loop continues; re-emit on each revision cycle)
- "Abandon" → FAIL
```

Only emit `cfl event plan.approved` when the verdict is PASS.

## Focus
- The run state detection at startup mirrors mine-define's three-branch pattern but adds the phase check — a run from mine-define will be in `define` phase and needs to advance.
- `cfl run advance-phase plan` will emit a `phase.advanced` event automatically (handled by the cfl function). The `plan.started` event is separate — it signals that the plan skill has begun its work, not just that the phase transitioned.
- The `cfl spec validate` call (Phase 4) already exists in mine-plan. The new `cfl gate plan-spec-validate` call is added after it — it records the validate result as a gate, complementing the schema validation the command performs.
- Dispatch tracking uses the pattern: capture `dispatch_id` from `cfl dispatch` output, then pass it to `cfl dispatch end <dispatch_id>`. The dispatch_id is an integer.
- On "Revise the plan" (Phase 6), the flow loops back to Phase 2. The `plan-approval` gate with WARN verdict captures each revision attempt. On the eventual approval, a PASS verdict is recorded.

## Verify
- [ ] FR#12: mine-plan SKILL.md contains cfl calls at: run state detection + plan.started event (before Phase 1), tasks-written event (Phase 3), plan-validator dispatch/gate (Phase 3.5), plan-spec-validate gate (Phase 4), plan-reviewer dispatch/gate (Phase 5), plan-comb dispatch/gate (Phase 5.5), plan-approval gate + plan.approved event (Phase 6)
