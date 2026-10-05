---
name: mine-sketch
description: "Use when the user says: \"sketch this out\", \"sketch this feature\", \"lightweight plan\", \"structured but lightweight\", or wants the decisions behind a change settled before building it (\"spec this out\", \"design this change\"). Produces a decision ledger (design.md) the user ratifies one decision at a time; `/mine-sketch <dir>` on a ratified ledger builds it in one session."
user-invocable: true
opencode-command: true
---

# Sketch

Structured design before code. Sketch mode surfaces every decision a change needs into a **decision ledger** (`design.md`) and has the user ratify each one, then challenges and combs the ledger. Build mode, run in a fresh session, implements the whole change from the ratified ledger and checks the result with a ship-time challenge.

The value is in the decisions. A judgment call made silently is the failure this skill exists to prevent, so every choice that would change the code gets surfaced, reasoned, and ratified before any code is written. One session builds the whole change, gated by the normal pre-commit reviewers.

## Arguments

$ARGUMENTS — a description of what to build, or a feature directory path. Can be:
- A feature idea: `/mine-sketch "add webhook support to notifications"` (sketch mode)
- A feature directory: `/mine-sketch design/specs/005-webhooks/` (resumes or builds, by the ledger's status)
- Empty: ask "What would you like to build or change?" and continue in sketch mode

## Routing

If $ARGUMENTS points to a directory containing `design.md`, read its header and route by the first row that matches. A directory with only a `brief.md` takes the last row.

| Ledger | Do |
|---|---|
| `**Mode:** sketch`, `**Status:** draft` | Resume sketch mode. Run Phase 1's cfl setup but not its scan, then continue at the first `**Ratified:** pending` decision (Phase 3). If none are pending, continue at Phase 4, unless `## Decisions` has no `### D<n>` blocks at all: then drafting was interrupted, so finish Phase 2 first. |
| `**Mode:** sketch`, `**Status:** ratified` | [Build mode](#build-mode). |
| `**Mode:** sketch`, `**Status:** built` | Report that the build is done and point to `/mine-ship`. Stop. |
| `**Status:** archived` or `abandoned` | Report the status and stop. |
| No `design.md`, but a `brief.md` (from `/mine-grill`) | A new sketch: read the brief as prior work and put the ledger in this directory. Start at Phase 1. |

Otherwise, treat $ARGUMENTS as a new request and start at Phase 1.

---

## Phase 1: Scope

For a new request, paraphrase it in one sentence to confirm understanding.

### Quick codebase scan

Read 3-8 files relevant to the change:
- Files that will be modified (current structure)
- Adjacent files that establish conventions
- Test files that cover the area

Keep it fast. You're looking for conventions, constraints, and the decisions the change will force, not doing a deep investigation.

If the request names a brief or research file (from `/mine-research`, `/mine-grill`, or similar), read it first and treat it as prior work: its findings ground the scan and the decision tables, and its open questions become decisions.

### Initialize CFL tracking

For a new request, derive a `<slug>` (kebab-case, max 40 chars) and create the spec:

```bash
cfl spec init <slug>
```

Record `dir` as `<feature_dir>` and `number` as `<spec_number>`. When the request is a feature directory with a brief, skip `cfl spec init`: that directory is `<feature_dir>`. Take `<spec_number>` from the directory name and check it with `cfl spec status` exactly as on resume below, including the `spec_not_found` fallback.

On resume, extract the number from the directory name and run `cfl spec status --spec <NNN>`. If it errors with `spec_not_found`, the directory predates cfl tracking: tell the user, and skip every `cfl` call for the rest of this run.

### Start run

Skip if cfl tracking is disabled.

```bash
cfl run status --spec <spec_number>
```

- `"exists": true`: an active run exists. Record its `run_id` and continue.
- `"exists": false`: try `cfl run resume --spec <spec_number>`. If that errors with `no_stopped_run`, or with `run_completed` (the ledger was ratified, then reopened), start a new run:

```bash
cfl run start --phase sketch --base-commit $(git rev-parse --short HEAD) --spec <spec_number>
cfl event sketch.started --spec <spec_number>
```

Record the `run_id`.

---

## Phase 2: Draft the Ledger

Read `${CLAUDE_CONFIG_DIR:-~/.claude}/skills/mine-sketch/design-template.md` and `${CLAUDE_CONFIG_DIR:-~/.claude}/references/common/presenting-decisions.md`. Write `<feature_dir>/design.md` from the template, following both.

- **Find every decision.** Walk the change from entry point to tests and list each place where more than one reasonable answer exists and the answer changes the code: behavior at edge cases, error and retry handling, what gets exposed or logged, compatibility, naming that callers will see. None is resolved silently. When unsure whether something is a decision, make it one; collapsing a small decision costs less than missing one.
- **Resumable work state.** When the change owns work state across invocations (a background worker, batch job, queue consumer, scheduler, or persistent retry state), its lifecycle is a set of decisions: completion, retry eligibility and bounds, recovery from states that need user action, repeated-run convergence, and visible progress and failure accounting.
- **Fill each table before recommending.** Ground the criteria in what the scan found, and cite files.
- **Assumed** gets the facts the build relies on, each with evidence.
- **Self-sufficient.** The build runs in a fresh session with only this file and the repo. Name the files and modules; don't refer to "as discussed".

Every decision starts as `**Ratified:** pending`.

---

## Phase 3: Ratify

Take each `**Ratified:** pending` decision in order, one at a time. Never batch.

1. Write the decision's rubric as message text before the `AskUserQuestion` call: the deciding factor, the criteria × options table, the recommendation, and each "Pick X instead if", formatted per `presenting-decisions.md`. This is the user's chance to push back on the reasoning, so write it in full, not summarized.
2. Ask:

   ```
   AskUserQuestion:
     question: "Decision <N> of <M>: <the decision's question>"
     header: "D<n>"
     multiSelect: false
     options:
       - label: "<recommended option> (Recommended)"
         description: "<one line: what it means for the change>"
       - label: "<other option>"
         description: "<one line>"
   ```

   One option per column of the decision's table, recommended first, at most 4. When `<M>` has grown since the interview started, say so in the question ("Decision 5 of 7, 2 new").
3. Replace `pending` with one sentence: "Chose X over Y, to achieve Q, accepting D." If the user answered with something not in the table, add it as a column, score it, and ratify that.
4. When an answer surfaces a new decision, add a `### D<n>` block with `**Ratified:** pending` and ratify it in turn.

When no decision is pending, record that the ledger changed (skip if cfl tracking is disabled):

```bash
cfl event sketch.design-written --spec <spec_number>
```

Phase 4's resume check compares against this event, so emit it on every pass through this phase, including re-ratification after the challenge and after Revise.

---

## Phase 4: Challenge

Run the mandatory sketch-time challenge. Read `${CLAUDE_CONFIG_DIR:-~/.claude}/skills/mine-challenge/challenge-gate.md` and follow it with:

- **`<header>`**: `Challenge`
- **`<gate_type>`**: `sketch-challenge`
- **`<target>`**: `<feature_dir>/design.md`
- **`<critic_flag>`**: `--critics=2`
- **`<focus_flag>`**: (empty)
- **`<re_challenge_flag>`**: `--re-challenge` when Phase 6's Revise sent you here, otherwise empty
- **`<post_resolution>`**: A resolved finding that added or changed a decision has set it back to `**Ratified:** pending` (the findings protocol's rule for sketch ledgers). Run Phase 3 for those decisions, then continue to Phase 5.

Skip the cfl calls inside the gate if cfl tracking is disabled. The challenge itself always runs.

**Resume check.** When entering this phase on resume, skip it only if the challenge already covers the current ledger: run `cfl event list --event challenge.findings-persisted --run <run_id>` and `cfl event list --event sketch.design-written --run <run_id>`. Skip when the newest `challenge.findings-persisted` row whose data has `"gate_type": "sketch-challenge"` has a higher `id` than the newest `sketch.design-written` row. Otherwise the ledger changed since the last challenge, so run it. With cfl tracking disabled, always run it.

---

## Phase 5: Comb

Comb the ledger once, after the challenge, so the comb also catches inconsistencies the challenge's edits introduced.

Skip the cfl calls if cfl tracking is disabled. The comb itself always runs.

```bash
cfl dispatch sketch-comb --agent-type fine-toothed-comb --spec <spec_number>
```

Record the `dispatch_id`.

```
Agent:
  subagent_type: fine-toothed-comb
  prompt: |
    Read this decision ledger: <feature_dir>/design.md
    Its format and content rules: ${CLAUDE_CONFIG_DIR:-~/.claude}/skills/mine-sketch/design-template.md

    Go over it with a fine-toothed comb. Check:
    - Decisions, assumptions, and the summary are consistent: no contradictions, no decision restated elsewhere
    - Each ratified sentence matches an option in its table, and the table scores every option on every criterion
    - Every judgment call the change needs is a decision; nothing with more than one reasonable answer hides in Assumed or the summary
    - Each assumption has evidence
    - Decisions state behavior a test must pin, not test technique
    - A fresh session with only this file and the repo could build the change

    Define blocking as: a direct inconsistency, a missing decision, or an error that would mislead the build. A section that could be more detailed is minor, not blocking.
```

After the comb completes:

```bash
cfl dispatch end <dispatch_id>
cfl gate sketch-comb --verdict <v> --spec <spec_number> --data '{"blocking": <N>, "minor": <M>}'
```

Verdict: `blocking` = 0 → PASS, `blocking` > 0 → FAIL.

Read `${CLAUDE_CONFIG_DIR:-~/.claude}/skills/mine-comb/comb-gate.md` and apply it with:
- **`<header>`**: `Sketch comb`
- **`minor_blocks`**: `false`
- **`<re_review_instructions>`**: fix the findings in `design.md`, then re-run this phase. A fix that adds or changes a decision sets it back to `**Ratified:** pending` and runs it through Phase 3 first.

---

## Phase 6: Ledger Gate

Present the full ledger as text, with its path. This is a completion gate (see `interaction.md`): run `context-pct` and prepend the result.

```
AskUserQuestion:
  question: "[Context: N%] The ledger is ready. Ratify it for the build?"
  header: "Ledger"
  multiSelect: false
  options:
    - label: "Ratify"
      description: "Lock the ledger; build it in a fresh session"
    - label: "Revise a decision"
      description: "Reopen a decision, or add one"
    - label: "Save and stop"
      description: "Keep the draft on disk; pick it up later"
```

### On "Ratify"

Set `**Status:** ratified` in `design.md`. Then, unless cfl tracking is disabled:

```bash
cfl event sketch.approved --spec <spec_number>
cfl run complete --spec <spec_number>
```

Tell the user: "Ledger ratified at `<feature_dir>/design.md`. Start a fresh session and run `/mine-sketch <feature_dir>` to build it."

Stop. The build always runs in a fresh session, so this session never continues into build mode.

### On "Revise a decision"

Ask which decision to reopen, or what new decision to add, and what should change. Set that decision's `**Ratified:**` back to `pending` (a new decision starts as `pending`), then run Phase 3, Phase 4 with `--re-challenge`, and Phase 5, and return to this gate.

### On "Save and stop"

Leave `**Status:** draft` and the cfl run open. Don't call `cfl run stop`, which would mark the spec approved. Confirm: "Ledger saved at `<feature_dir>`. Resume with `/mine-sketch <feature_dir>`."

---

## Build Mode

Runs when `/mine-sketch <dir>` finds `**Status:** ratified`. Building doesn't touch cfl: the sketch's run closed at Ratify, so skip every cfl call in Steps 2-4, including those inside `challenge-gate.md`. Only reopening a decision (Step 1) returns to sketch mode, where cfl applies again.

### Step 1: Orient

Read the whole ledger and the files it names. Check git state (branch, uncommitted changes, recent commits, and `git-branch-behind` for how far the branch trails the default branch) and raise anything surprising, such as being on the default branch, unrelated uncommitted work, or a stale base the ledger's file references may no longer match, before writing code.

Read the `## Build` checklist. If no step is ticked, this is a fresh build. If some are, resume after the last ticked step, using the branch's commits to see where the work stands.

The user ran `/mine-sketch <dir>` on a ratified ledger, so the request to build is already explicit. If Orient raised something surprising, resolve that with the user first. Otherwise name the ledger being built (`<feature_dir>/design.md`, `<M>` ratified decisions), note they can say so to reopen a decision before you start, and begin.

If they ask to reopen a decision: ask which one and what should change. Set `**Status:** draft` and that decision's `**Ratified:**` back to `pending`, then follow the sketch-mode flow from Phase 1's cfl setup, as a draft resume.

### Step 2: Implement

Implement the change with its tests and docs. The ledger is the spec:

- Every ratified decision and every assumption holds in the code.
- Tests pin the behavior each decision specifies. The ledger says what to pin; choosing how is yours.
- When the ledger doesn't settle something, make the call and record it under `**Calls made during the build:**` as `- <the call>: <one line of why>`. The ship-time challenge checks each one against the code. A call that contradicts a ratified decision isn't a build-time call: stop and ask the user whether to reopen the decision.

When you decide not to fix a real finding (from the pre-commit reviewers here, or the ship-time challenge in Step 3), follow `${CLAUDE_CONFIG_DIR:-~/.claude}/skills/mine-sketch/known-issues.md`:

- If you are deferring it on your own (the user never saw it, as with a pre-commit reviewer finding), check its Severity Gate first.
- Then record the finding if it qualifies.

Commit as you judge best. Every repo squash-merges, so there's no required commit sequence. The pre-commit reviewers in `git-workflow.md` gate each commit. Tick each `## Build` step, and add each build-time call, in the same commit as the work it describes. When the change needs no doc updates, tick Docs and note "none needed".

### Step 3: Ship-time Challenge

Write the branch's changed files to a list: the union of `git-branch-diff-files`, `git diff --name-only HEAD`, and `git ls-files --others --exclude-standard`, deduplicated. Make sure `<feature_dir>/design.md` is in it. Write the list to `<tmpdir>/challenge-changed-files.txt`, where `<tmpdir>` comes from `get-skill-tmpdir mine-sketch`.

Read `${CLAUDE_CONFIG_DIR:-~/.claude}/skills/mine-challenge/challenge-gate.md` and follow it with:

- **`<header>`**: `Challenge`
- **`<gate_type>`**: `ship-challenge`
- **`<target>`**: `<tmpdir>/challenge-changed-files.txt`
- **`<critic_flag>`**: (empty — use triage default 1–3)
- **`<focus_flag>`**: `--focus="The ledger at <feature_dir>/design.md is the reference. (A) Does what landed match its ratified decisions and assumptions, with tests pinning the behavior each one specifies? (B) Where the code diverges, does the ledger's Build section give a sound reason? Check each stated reason against the code. (C) What unintended consequences are there beyond what the ledger covered?"`
- **`<re_challenge_flag>`**: (empty)
- **`<post_resolution>`**: Fixes go through the normal pre-commit reviewers. A real finding the user left with `disposition: skipped` is recorded as in Step 2; the Severity Gate doesn't apply, since the user already saw it.

Findings resolve inline, as in any challenge. The `## Build` record is the build's stated reasoning, not evidence: the challenge checks it against the code rather than taking it on its word.

### Step 4: Finish

If `<feature_dir>/known-issues.md` has `Status: open` entries, walk all of them before the Ship? gate, one question per entry, batched up to 4 questions per `AskUserQuestion` call (major gate: run `context-pct` and prepend it to the first). In each question, say when the entry's `Recorded:` line names a different branch from this one, since that entry came from an earlier build. Recommend fixing when it's contained, filing when it needs its own change, keeping it open when it's tied to this feature's follow-up work:

```
AskUserQuestion:
  question: "[Context: N%] KI-<NNN>: <title>. <one-line issue>. What now?"
  header: "KI-<NNN>"
  multiSelect: false
  options:
    - label: "Fix now"
      description: "Fix it through the pre-commit reviewers (no re-challenge); Status becomes `resolved — fixed before ship`"
    - label: "File as issue"
      description: "Create a tracker issue; Status becomes `filed (<issue-key>)`"
    - label: "Keep open"
      description: "Status stays `open` for later"
```

Then tick `Ship-time challenge`, set `**Status:** built`, and commit the ledger with any known-issues updates. Report what was built, any build-time calls, and the known issues left open. This is a completion gate: run `context-pct` and prepend the result.

```
AskUserQuestion:
  question: "[Context: N%] Build complete and challenged. Ship it?"
  header: "Ship?"
  multiSelect: false
  options:
    - label: "Ship via /mine-ship"
      description: "Push and open a PR"
    - label: "Stop here"
      description: "Leave the branch as is"
```

On "Ship via /mine-ship": invoke `/mine-ship`.
