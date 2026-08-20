---
task_id: "T04"
title: "Integrate mandatory challenge into define, sketch, and orchestrate"
status: "done"
depends_on: ["T03"]
implements: ["FR#1", "FR#2", "FR#3", "FR#4", "FR#5", "FR#6", "FR#7", "FR#8", "FR#9", "FR#10", "AC#1", "AC#2", "AC#3", "AC#4", "AC#15"]
---

## Summary
Wire the mandatory challenge into all three skill files: add a new challenge phase to `mine-define` (between comb and sign-off) and `mine-sketch` (between comb and handoff), add Step 3.5 to `mine-orchestrate`'s post-execution pipeline, remove the "Challenge first" options from both sign-off and shipping gates, update the shipping gate summary line, and add the sketch upgrade-to-caliper prompt. Also update `mine-build` with the rationalization row and routing descriptions, and update `rules/common/git-workflow.md` and `rules/common/invariants.md`.

## Target Files

- modify: `skills/mine-define/SKILL.md`
- modify: `skills/mine-sketch/SKILL.md`
- modify: `skills/mine-orchestrate/post-execution-pipeline.md`
- modify: `skills/mine-build/SKILL.md`
- modify: `rules/common/git-workflow.md`
- modify: `rules/common/invariants.md`
- modify: `REFERENCE.md`
- read: `skills/mine-challenge/challenge-gate.md`
- read: `skills/mine-comb/comb-gate.md`

## Prompt

### 1. mine-define — mandatory challenge phase (SKILL.md)

**Add Phase 5.5: Challenge** between Phase 5 (Fine-Toothed Comb Review, ending at the "Phase 6 does not begin until the comb gate resolves" line around line 259) and Phase 6 (Sign-Off Gate, heading at line 263).

Insert a new section:

```markdown
---

## Phase 5.5: Challenge

Run the mandatory design-time challenge. Read `${CLAUDE_CONFIG_DIR:-~/.claude}/skills/mine-challenge/challenge-gate.md` and follow it with:

- **`<header>`**: `Challenge`
- **`<gate_type>`**: `define-challenge`
- **`<target>`**: `<design_doc_path>`
- **`<critic_flag>`**: (empty — use triage default 1–3)
- **`<re_challenge_flag>`**: (empty — first challenge in this run)
- **`<post_resolution>`**: none — proceed to Phase 6

Skip the cfl dispatch/gate/finding calls if cfl tracking was disabled in Phase 1 (no `<spec_number>` set). The challenge itself still runs regardless.

If this is a resume and the challenge already ran in a prior session, skip this phase. Check via: `cfl event list --event review.gated --run <run_id>` — if any row's data contains `"gate_type": "define-challenge"`, the challenge already ran for this run. (`record_gate` emits a `review.gated` event for every run-level gate, with the gate type in its JSON data — `packages/cfl/src/cfl/gate.py:106-108`.)

Phase 6 does not begin until the challenge completes.
```

**Remove "Challenge first" from Phase 6 sign-off gate:**

1. Delete the `"Challenge first"` option from the AskUserQuestion block (the option at line 273-274).
2. Delete the verdict-mapping line for "Challenge first" at line 303.
3. Update line 311 ("On Revise, Save-and-stop, or Challenge, do **not** run the `cfl event` command above") to remove the "or Challenge" reference — that option no longer exists.
4. Delete the "On 'Challenge first'" handler section (lines 313-317) entirely.

**Update the Revise handler** (around line 344): The existing text says "Re-run the Fine-Toothed Comb Review." Keep this — do NOT add challenge to the revise loop. FR#3 requires that Revise re-runs the comb without re-running challenge.

### 2. mine-sketch — mandatory challenge phase (SKILL.md)

**Add Phase 4.5: Challenge** between Phase 4 (Comb, ending at the "---" before Phase 5 around line 243) and Phase 5 (Handoff, heading at line 245).

Insert a new section:

```markdown
---

## Phase 4.5: Challenge

Run the mandatory sketch-time challenge. Read `${CLAUDE_CONFIG_DIR:-~/.claude}/skills/mine-challenge/challenge-gate.md` and follow it with:

- **`<header>`**: `Challenge`
- **`<gate_type>`**: `sketch-challenge`
- **`<target>`**: `<design_doc_path>`
- **`<critic_flag>`**: `--critics=2`
- **`<re_challenge_flag>`**: (empty — first challenge in this run)
- **`<post_resolution>`**: If any CRITICAL finding was produced (check the findings file), offer the upgrade-to-caliper choice before proceeding to Phase 5. See below.

Skip the cfl dispatch/gate/finding calls if cfl tracking was disabled in Phase 1 (no `<spec_number>` set). The challenge itself still runs regardless.

### CRITICAL escalation

If any CRITICAL finding was produced by the challenge (regardless of its disposition — even if applied), present:

```
AskUserQuestion:
  question: "The challenge found a CRITICAL structural issue. A sketch may not be the right vehicle for this change. Upgrade to the full caliper workflow?"
  header: "Escalate?"
  multiSelect: false
  options:
    - label: "Upgrade to full caliper"
      description: "Stop here — invoke /mine-define for a full investigation and design"
    - label: "Continue with sketch"
      description: "Proceed with the sketch despite the CRITICAL finding"
```

On "Upgrade to full caliper": tell the user to invoke `/mine-define` and stop. The resolved findings have already improved `design.md`, which `/mine-define` picks up.

On "Continue with sketch": proceed to Phase 5 (Handoff) as normal.

Phase 5 does not begin until the challenge (and any escalation prompt) completes.
```

### 3. mine-orchestrate — Step 3.5 (post-execution-pipeline.md)

**Add Step 3.5: Challenge** between the cross-file review section (Step 3, which ends with the shared blocking-review fixer protocol around line 275) and Step 4 (Clean code check, heading around line 276).

Insert a new section:

```markdown
## Step 3.5: Challenge

Run the mandatory ship-time challenge against the branch's changed files.

Compute the changed-files list using the same three-command union as Step 2 (`git diff --name-only <base_commit> HEAD`, `git diff --name-only HEAD`, `git ls-files --others --exclude-standard`). Write the deduplicated list to `<dir>/challenge-changed-files.txt`.

Read `${CLAUDE_CONFIG_DIR:-~/.claude}/skills/mine-challenge/challenge-gate.md` and follow it with:

- **`<header>`**: `Challenge`
- **`<gate_type>`**: `ship-challenge`
- **`<target>`**: `<dir>/challenge-changed-files.txt`
- **`<critic_flag>`**: (empty — use triage default 1–3)
- **`<re_challenge_flag>`**: (empty — first challenge in this run)
- **`<post_resolution>`**: After step 6 of the recipe, read the findings file and note any CRITICAL or HIGH finding left with `disposition: skipped`. These will be named in the Step 6 shipping gate summary.

Step 4 does not begin until the challenge completes.
```

**Remove "Challenge first" from Step 6 shipping gate:**

1. Delete the `"Challenge first"` option from the AskUserQuestion block (line 453-454).
2. Remove `challenge` from the `--data '{"choice": ...}'` enum literal in the gate recording line (line 462).
3. Delete the "On 'Challenge first'" handler (line 493) entirely.
4. Update the verdict-mapping parenthetical (line 465) to remove the "Challenge first" reference. Also update the sentence on the same line that reads "the terminal choice (ship/challenge/stop) re-records the gate" — remove "challenge" from that list since the option no longer exists.

**Update the shipping gate question text** (line 445): Add a challenge result field to the summary line. Place it in step-chronological order — after "Cross-file review: ..." and before "Clean code check: ...", matching the pipeline execution sequence (Step 3 cross-file → Step 3.5 challenge → Step 4 clean-code). Add: `Challenge: <PASS — no findings | WARN — N findings, all resolved | note naming any CRITICAL/HIGH with disposition: skipped>.`

### 4. mine-build — rationalization and routing descriptions (SKILL.md)

In `skills/mine-build/SKILL.md`:

**Execution Rationalizations table** (around line 215): Add a new row:
```
| "We can skip the challenge on this one" | Challenge is mandatory in Structured and Complex paths. It cannot be skipped. If the change is small enough to skip challenge, use the Simple path — which has no challenge because Path A doesn't route through orchestration. |
```

**Routing option descriptions**: In the two AskUserQuestion blocks (lines 68-82 and 84-100), add a note to the Structured and Complex options that challenge is included. For example:
- Structured: `"Lightweight design.md + task files → orchestrate with full execution gates (includes mandatory challenge)"`
- Complex / Full caliper workflow (both blocks — the no-prior-analysis "Complex" option and the prior-analysis-detected "Full caliper workflow" option describe the same underlying path): `"define → plan → orchestrate → ship (includes mandatory challenge at design and ship time)"`
- Accelerated (in the prior-analysis-detected block): `"Formalize findings into design.md (skip research — already done) → plan → orchestrate → ship (includes mandatory challenge)"`
- Simple stays unchanged (no challenge).

### 5. git-workflow.md — mandate statement

In `rules/common/git-workflow.md`, in the "Code Review vs Challenge" section, add:

> Challenge is mandatory in orchestration workflows (`mine-define`, `mine-sketch`, `mine-orchestrate`). It runs automatically at defined points and cannot be declined.

### 6. invariants.md — Should-tier entry

In `rules/common/invariants.md`, under the "### Should" section, add:

```markdown
#### Mandatory Challenge in Orchestration
Challenge runs at both design-time and ship-time in orchestration workflows. It is not offered as an option and cannot be skipped.
**Defined in:** `rules/common/git-workflow.md`
```

### 7. REFERENCE.md — cfl subcommand row

In `REFERENCE.md`, find the `cfl` row (around line 240). Update the subcommand list to include `finding record/record-batch/list/resolve` and restore the omitted `question`. The updated subcommand list should read: `spec init/adopt/validate/status/set-status/next-number`, `run start/status/complete/stop/resume/advance-phase`, `task start/update/verdict/block`, `gate`, `dispatch`/`dispatch end`, `event`, `session end/compacted`, `question`, `finding record/record-batch/list/resolve`, `archive`, `set`, `stop-orphans`.

## Focus

- The Phase 5.5 / Phase 4.5 / Step 3.5 numbering follows the existing "half-step" convention used by the comb gate in mine-plan.
- The mine-define Revise handler is load-bearing: FR#3 explicitly requires that Revise re-runs the comb but NOT challenge. Do not add a challenge re-run to the Revise path.
- The sketch escalation prompt reuses the same shape as Phase 1's escalation check (lines 96-107 of mine-sketch/SKILL.md) — same two options, same "tell the user to invoke `/mine-define` and stop" behavior on upgrade.
- The shipping gate summary must name unresolved CRITICAL/HIGH findings by title so the user cannot miss them. This is the enforcement point for the edge case where a finding was skipped at resolution time.
- The "Challenge first" option in both gates must be fully removed — not just hidden. This means deleting the option, its verdict mapping, and its handler section.

## Verify
- [ ] FR#1: `skills/mine-define/SKILL.md` contains a Phase 5.5 Challenge heading between the Phase 5 comb and Phase 6 sign-off, with no option to decline
- [ ] FR#2: `grep -c 'Challenge first' skills/mine-define/SKILL.md` returns 0
- [ ] FR#3: The mine-define Revise handler re-runs the comb but does not invoke challenge
- [ ] FR#4: `skills/mine-sketch/SKILL.md` contains a Phase 4.5 Challenge heading between Phase 4 comb and Phase 5 handoff
- [ ] FR#5: The sketch challenge invocation includes `--critics=2`
- [ ] FR#6: The sketch Phase 4.5 contains the upgrade-to-caliper prompt after resolution, triggered on any CRITICAL finding
- [ ] FR#7: `skills/mine-orchestrate/post-execution-pipeline.md` contains a Step 3.5 heading between Step 3 and Step 4
- [ ] FR#8: Step 3.5 invokes `/mine-challenge` rather than instructing the user to run it
- [ ] FR#9: `grep -c 'Challenge first' skills/mine-orchestrate/post-execution-pipeline.md` returns 0
- [ ] FR#10: The shipping gate question text includes a challenge result field that names any CRITICAL/HIGH finding with `disposition: skipped`
- [ ] AC#1: `grep -c 'Challenge first' skills/mine-define/SKILL.md skills/mine-orchestrate/post-execution-pipeline.md` returns 0 for both files
- [ ] AC#2: The Phase 5.5 heading sits between Phase 5 and Phase 6 in mine-define
- [ ] AC#3: The Phase 4.5 heading sits between Phase 4 and Phase 5 in mine-sketch, and the invocation carries `--critics=2`
- [ ] AC#4: Step 3.5 sits between Step 3 and Step 4 in post-execution-pipeline.md, and invokes `/mine-challenge`
- [ ] AC#15: The shipping gate summary names any CRITICAL/HIGH finding with `disposition: skipped`
