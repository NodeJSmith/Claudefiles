---
task_id: "T06"
title: "Update mine-orchestrate for phase-aware run detection"
status: "planned"
depends_on: ["T03"]
implements: ["AC#5"]
---

## Summary
Update mine-orchestrate's Phase 0 initialization and resume protocol to handle runs that already exist from the define/plan phases. When a run exists in define or plan phase, orchestrate must advance it to orchestrate phase (loading tasks) rather than creating a new run. The resume protocol must detect define/plan-phase runs and route them correctly instead of presenting the existing "Resume from task X" prompt.

## Target Files
- modify: `skills/mine-orchestrate/SKILL.md`
- modify: `skills/mine-orchestrate/resume-protocol.md`
- read: `design/specs/1001-define-plan-tracking/design.md`

## Prompt
### resume-protocol.md: Phase-aware branching

The current resume-protocol.md (51 lines) checks `cfl run status` and branches on `"exists": true/false`. Add a phase check between the existence check and the existing resume/restart logic.

After the `cfl run status` call (line 8) and the `"exists": false` branch (line 11), add a new branch before the existing `"exists": true` handling (line 13):

```markdown
### Phase check

If `"exists": true`, read the `"phase"` field from the output.

**If phase is `"define"` or `"plan"`** (zero tasks loaded):

Do not present the "Resume from task X" / "Restart fresh" options — there are no tasks to resume from.

```
AskUserQuestion:
  question: "An active run exists in <phase> phase (from mine-<phase>). Advance to orchestrate to begin task execution?"
  header: "Phase advance"
  multiSelect: false
  options:
    - label: "Advance to orchestrate"
      description: "Load task files and begin execution"
    - label: "Stop the run"
      description: "Stop this run; the spec remains in <phase> phase"
```

- **"Advance to orchestrate"**: Set an internal flag `advance_from_prior_phase = true`. Do NOT call `cfl run advance-phase` here — tmpdir, visual_mode, and dev_server_url are not yet resolved. Fall through to the remainder of Phase 0's setup steps (feature directory discovery, design doc read, task file read, dev server check, vision capability check).

- **"Stop the run"**: Call `cfl run stop --reason "user chose stop from orchestrate"` and exit.

**If phase is `"orchestrate"`** — proceed with the existing resume logic (lines 13-50 of the current file) unchanged.
```

### SKILL.md: Phase 0 run initialization

In Phase 0 ("Initialize orchestration run via cfl", around line 128), the existing instruction is:

```bash
cfl run start --base-commit <sha> --tmpdir <tmpdir> [--visual-mode ...] [--dev-server-url ...]
```

Replace this section with branching logic:

```markdown
### Initialize orchestration run via cfl

**If `advance_from_prior_phase` is set** (from resume-protocol's phase check):

```bash
cfl run advance-phase orchestrate --base-commit <sha> --tmpdir <tmpdir> [--visual-mode <mode>] [--dev-server-url <url>]
```

This advances the existing run to orchestrate phase, loads task files into the DB, refreshes `base_commit` to the current HEAD (so define/plan commits don't appear in the post-execution diff), and sets `tmpdir`/`visual_mode`/`dev_server_url`. The output matches `cfl run start` — it includes `run_id`, `tasks`, `task_count`.

**If no run exists** (fresh start, no prior define/plan):

```bash
cfl run start --base-commit <sha> --tmpdir <tmpdir> [--visual-mode <mode>] [--dev-server-url <url>]
```

This is the existing behavior — creates a new run, discovers tasks, inserts task rows.

**If a run exists in orchestrate phase** (handled by resume-protocol):

The run is already active with tasks loaded. `cfl run resume` was called by resume-protocol. Proceed directly to Phase 2 — do not call `cfl run start` or `cfl run advance-phase`.
```

Both `cfl run start` and `cfl run advance-phase orchestrate` produce the same output shape. The rest of Phase 0 and all of Phase 2 proceed identically regardless of which path was taken.

## Focus
- The `advance_from_prior_phase` flag is a conceptual instruction for the executing agent — it's not a literal variable. The agent reads the resume-protocol, makes the decision, then acts on it when it reaches the run initialization step in SKILL.md.
- The key constraint is that `cfl run advance-phase orchestrate` must be called AFTER tmpdir creation, dev server detection, and vision capability checks — these happen between the resume-protocol check (top of Phase 0) and the run initialization (line ~128 of SKILL.md).
- `cfl run advance-phase orchestrate` refreshes `base_commit` by default (auto-resolves HEAD if `--base-commit` is not passed). mine-orchestrate always passes `--base-commit` explicitly (captured at line 121-122 of SKILL.md).
- The `post-execution-pipeline.md` (which calls `cfl run status`) is unaffected — the new `phase` field is additive and the pipeline doesn't depend on it.

## Verify
- [ ] AC#5: After a full mine-define→mine-plan→mine-orchestrate flow, `cfl event list` shows events from all three phases in chronological order under the same run_id — the orchestrate phase uses the same run_id created by mine-define, advanced through plan by mine-plan
