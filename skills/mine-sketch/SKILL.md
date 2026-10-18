---
name: mine-sketch
description: "Use when the user says: \"sketch this out\", \"sketch this feature\", \"lightweight plan\", \"structured but lightweight\", or wants the decisions behind a change settled before building it (\"spec this out\", \"design this change\"). Produces a decision ledger (design.md) the user ratifies one decision at a time; `/mine-sketch <dir>` on a ratified ledger builds it in one session."
user-invocable: true
---

# Sketch

Structured design before code. Sketch mode first settles the change's posture and checks where its new pieces fit. It then surfaces every decision the change needs into a **decision ledger** (`design.md`), has the user ratify each one, and challenges and combs the ledger. Build mode, run in a fresh session, implements the whole change from the ratified ledger and checks the result with a ship-time challenge. A ledger sketched at milestone altitude is a plan for several issues instead: it ends in an issue breakdown, and each issue is built on its own later.

The value is in the decisions. A judgment call made silently is the failure this skill exists to prevent, so every choice that would change the code gets surfaced, reasoned, and ratified before any code is written. One session builds the whole change, gated by the normal pre-commit reviewers.

## Arguments

$ARGUMENTS — a description of what to build, or a feature directory path. Can be:
- A feature idea: `/mine-sketch "add webhook support to notifications"` (sketch mode)
- A feature directory: `/mine-sketch design/specs/005-webhooks/` (resumes or builds, by the ledger's status)
- Empty: ask "What would you like to build or change?" and continue in sketch mode

## Routing

If $ARGUMENTS points to a directory containing `design.md`, that directory is `<feature_dir>`; read the ledger's header and route by the first row that matches. A directory with only a `brief.md` takes the last row.

| Ledger | Do |
|---|---|
| `**Mode:** sketch`, `**Status:** draft` | Resume sketch mode. If `## Posture` is missing or still holds template placeholders, run Phase 1's Posture step first and write it into the ledger. Otherwise skip Phase 1 and continue at the first `**Ratified:** pending` decision (Phase 3). If none are pending, continue at Phase 4, unless `## Decisions` has no `### D<n>` blocks at all: then drafting was interrupted, so finish Phase 2 first. |
| `**Mode:** sketch`, `**Status:** ratified`, `## Posture` Altitude `milestone` | Report that the ledger is a milestone plan, not a build spec, and list its Breakdown with any filed issue keys. Each issue is built on its own: `/mine-sketch` on the issue, naming this ledger so it's read as prior work, or without a sketch when the issue leaves no open decisions. If the Breakdown isn't filed yet, offer to file it as in [On "Ratify"](#on-ratify). If every issue is closed and the Done-when holds, offer to set `**Status:** archived`. Stop. |
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

If the request names a brief or research file (from `/mine-research`, `/mine-grill`, or similar), read it first and treat it as prior work: its findings ground the scan and the decision tables, and its open questions become decisions. A milestone ledger is prior work too, including one an issue's body points to, but its ratified decisions are settled: carry the ones this change relies on into Assumed, citing the ledger and its `D<n>`, rather than redrafting them. Its references are concepts rather than files, so the scan finds where each one lives now.

### Fit check

For each new piece of state or behavior the change adds, name where it lives. Then ask whether that's where it would go if the requirement had existed on day one (`redesign-from-first-principles.md`). When the honest answer is "on X, but X isn't really about this", that's a **structural gap**: a field stuffed onto an unrelated model, or a responsibility handed to whichever class was nearby. Without this check the draft quietly bolts the change on, and the gap surfaces at the challenge, or never.

Each gap becomes a decision in Phase 2, whatever the posture says. Its options are usually: bolt it on and propose a tracker issue for the debt, model it properly in this change, or land a prerequisite refactor first. To weight the table, ask what happens when the host changes for reasons unrelated to this feature. Does the new piece get dragged along or break? The host's importer count is good evidence. A bolt-on onto something many modules depend on spreads, and one in a leaf module stays contained.

Stay within the places this change has to put something. Structural problems elsewhere in the area are an audit's job, not this sketch's.

### Posture

Ledgers bloat with decisions the user considers unwarranted: one per failure edge case, one per compatibility path, one per "should it also handle X". Most come from a few areas. Settle the change's stance on each one up front, so the draft doesn't turn every case they cover into a decision:

| Axis | The stance to settle |
|---|---|
| Failure handling | Happy path with loud failure, or graceful degradation and retries |
| Compatibility | Callers, config, and stored data can break freely, or there are consumers to protect |
| Scope | The minimal version that works, or the complete feature |
| Rollout | Ship it outright, or flag, stage, or migrate |
| Hardening | Observability, performance, and security at the project's defaults, or raised for this change |
| Altitude | `build`: one session builds it, and the ledger cites files. `milestone`: the ledger names concepts, modules, and classes, never file:line or code steps, and ends in an issue breakdown built later |

Add an axis when the change turns on one the table lacks, such as concurrency or a data migration.

Altitude decides what the ledger is for, not how cautious the change is, so infer it from the request rather than the minimal default below. The question is whether whoever builds this will read the ledger after the code it would cite has moved or been split. If so, it's `milestone`, and the request usually says as much by asking for a plan, a milestone, or issues. Otherwise it's `build`. The two halves of `milestone` go together: a ledger that has to survive refactors can't also be a file-level spec for one build session. A ledger with no Altitude line is `build`.

Infer a stance for each axis from the request, the scan, the CLAUDE.md frontmatter (`audience`, `developers`, `data-sensitivity`; see `project-context.md`), and the repo itself. A public repo with releases or a changelog has consumers, and a private one with no installs usually doesn't. Your defaults skew toward more failure handling, more compatibility, and more scope than a project warrants, and a cautious posture invites a rubber stamp. So infer the minimal stance on each axis unless something you found argues for more, and name that evidence.

Write the proposed posture as message text, one line per axis with what drove it, then ask:

```
AskUserQuestion:
  question: "Does this posture fit the change?"
  header: "Posture"
  multiSelect: false
  options:
    - label: "Use this posture"
      description: "Draft the ledger within these stances"
    - label: "Adjust the posture"
      description: "Say which stances to change"
    # Include only when the frontmatter declares `peers` and the change adds a new mechanism, not a routine edit:
    - label: "Check peers first"
      description: "Run /mine-prior-art on how <peers> handle this, then revisit the posture"
```

On "Adjust the posture", ask which stances to change. On "Check peers first", invoke `/mine-prior-art` with the mechanism as the topic, and revise the stances its findings bear on. Peers routinely accept limitations a fresh design would engineer around. Either way, show the revised posture and ask again, without the peers option once it has run. Proceed on "Use this posture".

### Create the feature directory

For a new request, derive a `<slug>` (kebab-case, max 40 chars) and create the directory:

```bash
new-spec-dir <slug>
```

It prints the new directory's path; record it as `<feature_dir>`. When the request is a feature directory with a brief, that directory is `<feature_dir>`.

---

## Phase 2: Draft the Ledger

Read `${CLAUDE_CONFIG_DIR:-~/.claude}/skills/mine-sketch/design-template.md` and `${CLAUDE_CONFIG_DIR:-~/.claude}/references/common/presenting-decisions.md`. Write `<feature_dir>/design.md` from the template, following both.

- **Write the posture first.** Record the confirmed posture in `## Posture`. A case a stance settles follows that stance and is not a decision, even one you would otherwise have asked about. A retry policy under "loud failure" is one example, and a deprecation path under "break freely" is another. The ledger's value is the decisions the user wants a say in, not an exhaustive enumeration.
- **Find every decision the posture leaves open.** Walk the change from entry point to tests and list each place where more than one reasonable answer exists and the answer changes the code: behavior at edge cases, error and retry handling, what gets exposed or logged, compatibility, naming that callers will see. None is resolved silently. When unsure whether a case is covered, ask whether the user would be surprised to see it settled by the posture. If yes, it's a decision. Every structural gap from the fit check is a decision.
- **Name each home.** The Summary names where each new piece of state or behavior lives, so the comb and the build can check it.
- **Resumable work state.** When the change owns work state across invocations (a background worker, batch job, queue consumer, scheduler, or persistent retry state), its lifecycle is a set of decisions: completion, retry eligibility and bounds, recovery from states that need user action, repeated-run convergence, and visible progress and failure accounting.
- **Fill each table before recommending.** Ground the criteria in what the scan found, cited at the posture's altitude.
- **Assumed** gets the facts the build relies on, each with evidence.
- **Self-sufficient.** The build runs in a fresh session with only this file and the repo. Name what the change touches; don't refer to "as discussed".
- **Write at the posture's altitude.** At `build`, cite files. At `milestone`, use names that survive a file being moved or split (concepts, packages, classes, public functions), and leave out paths, line numbers, and code-step lists. The scan's evidence comes back file-shaped and precise citations feel rigorous, so the pull is to paste them in; translate each finding to the concept it shows. Then write `## Breakdown`: the proposed issues, each independently landable and naming the decisions it implements, plus a Done-when for the milestone as a whole. Leave out `## Build`.

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

When no decision is pending, on the first pass only, copy `design.md` to `<tmpdir>/ratified-ledger.md`, where `<tmpdir>` comes from `get-skill-tmpdir mine-sketch`. Keep that path for the rest of the session, since each call prints a new directory. Later passes leave the copy alone. The ledger is usually uncommitted at this point and the challenge and comb edit it in place, so this copy is the only record of what the user ratified; Phase 6 diffs against it.

---

## Phase 4: Challenge

Run the mandatory sketch-time challenge. Read `${CLAUDE_CONFIG_DIR:-~/.claude}/skills/mine-challenge/challenge-gate.md` and follow it with:

- **`<header>`**: `Challenge`
- **`<gate_type>`**: `sketch-challenge`
- **`<target>`**: `<feature_dir>/design.md`
- **`<critic_flag>`**: `--critics=2`
- **`<focus_flag>`**: (empty; `/mine-challenge` reads the ledger's `## Posture` itself)
- **`<re_challenge_flag>`**: `--re-challenge` when Phase 6's Revise sent you here, otherwise empty
- **`<post_resolution>`**: A finding the user answered has already ratified the decision it added or changed; the user's choice is the ratification (the findings protocol's rule for sketch ledgers). The ratifying edit also adds or updates that option's column in the decision's criteria table, so Phase 5's comb finds the table consistent. Only a decision an Auto-apply finding added or changed is back at `**Ratified:** pending`. Run Phase 3 for those, if any, then continue to Phase 5. A finding the user accepted that changes a posture stance has already edited `## Posture`, but not the decisions that relied on the old stance. Note the stance and carry it to Phase 6.
- **`<review_log>`**: `<feature_dir>/review-log.jsonl`
- **`<ledger>`**: `<feature_dir>/design.md`

**Resume check.** When entering this phase on resume, skip it only if the challenge already covers the current ledger: `<feature_dir>/review-log.jsonl` has a `sketch-challenge` record, and its newest `sketch-challenge` or `sketch-comb` record has a `ledger_hash` equal to `git hash-object <feature_dir>/design.md` now. The comb record counts because the comb runs after the challenge, so its fixes don't invalidate the challenge. Otherwise the ledger changed since then (or the challenge never finished), so run it.

---

## Phase 5: Comb

Comb the ledger once, after the challenge, so the comb also catches inconsistencies the challenge's edits introduced.

```
Agent:
  subagent_type: fine-toothed-comb
  prompt: |
    Read this decision ledger: <feature_dir>/design.md
    Its format and content rules: ${CLAUDE_CONFIG_DIR:-~/.claude}/skills/mine-sketch/design-template.md

    Go over it with a fine-toothed comb. Check:
    - Decisions, assumptions, and the summary are consistent: no contradictions, no decision restated elsewhere
    - Each ratified sentence matches an option in its table, and the table scores every option on every criterion
    - Every judgment call the change needs is a decision, unless its case follows a stance in Posture; nothing else with more than one reasonable answer hides in Assumed or the summary
    - The Summary names a home for every new piece of state or behavior, and a home that doesn't fit is a decision, not a silent bolt-on
    - Each assumption has evidence
    - Decisions state behavior a test must pin, not test technique
    - References match the Posture's Altitude: at `milestone`, no paths, line numbers, or code-step lists. A stray one is minor unless a decision depends on it
    - At `build` altitude, a fresh session with only this file and the repo could build the change. At `milestone`, every decision lands in some Breakdown issue, each issue could be picked up on its own, and the Done-when is observable

    Define blocking as: a direct inconsistency, a missing decision, or an error that would mislead the build. A section that could be more detailed is minor, not blocking.
```

After the comb completes, and before fixing anything, append a record of its counts to the review log, one per pass, so the log shows how many passes the comb took to converge. Substitute the blocking and minor counts as numbers:

```bash
jq -cn --arg date "$(date +%F)" --arg hash "$(git hash-object <feature_dir>/design.md)" \
  --argjson blocking <N> --argjson minor <M> \
  '{gate: "sketch-comb", date: $date, ledger_hash: $hash, blocking: $blocking, minor: $minor}' >> <feature_dir>/review-log.jsonl
```

Read `${CLAUDE_CONFIG_DIR:-~/.claude}/skills/mine-comb/comb-gate.md` and apply it with:
- **`<header>`**: `Sketch comb`
- **`minor_blocks`**: `false`
- **`<re_review_instructions>`**: fix the findings in `design.md`, then re-run this phase. A fix you made on your own that adds or changes a decision sets it back to `**Ratified:** pending` and runs it through Phase 3 first. A design-decision option the user picked at the gate is already their ratification: write the `**Ratified:**` sentence in the same edit.

---

## Phase 6: Ledger Gate

Every decision was ratified one at a time, by the user's own answer. This applies on the first pass only. A pass that returns here from "Revise a decision" always shows the gate.

Check what the challenge and comb changed by diffing `design.md` against `<tmpdir>/ratified-ledger.md`, the copy saved when Phase 3 first finished. If there is no copy (a session that resumed straight into Phase 4), there is nothing to prove the edits were all the user's, so show the gate. A stance change that hasn't been through Revise yet skips the gate's question: one carried from Phase 4, or a `## Posture` stance that differs from the copy and that Revise hasn't handled this session. Go straight to [On "Revise a decision"](#on-revise-a-decision) for that stance, so nothing can ratify the new stance before its dependent decisions are handled. Revise returns here afterward, and a stance it handled doesn't route back again. Otherwise, if every change is an edit the user chose between (no Auto-apply edits, no comb fixes you made on your own, no decision back at `pending`), there is nothing new to approve. Go straight to "On Ratify" below, print the ledger path along with any minor comb findings noted for the summary, and, at `build` altitude, say they can reopen a decision at the start of the build session.

Otherwise show the gate, because ratification was per-decision and this read is the only place a cross-decision inconsistency an automatic edit introduced would show up.

Present the full ledger as text, with its path, and show what changed since the last ratified decision. At `milestone` altitude, the question ends "Ratify it as the milestone plan?" and Ratify's description is "Lock the ledger; offer to file its issues". This is a completion gate (see `interaction.md`): run `context-pct` and prepend the result.

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

Set `**Status:** ratified` in `design.md`.

At `build` altitude, tell the user: "Ledger ratified at `<feature_dir>/design.md`. Start a fresh session and run `/mine-sketch <feature_dir>` to build it." Stop. The build always runs in a fresh session, so this session never continues into build mode.

At `milestone` altitude there is no build and no new session. Filing the Breakdown is the rest of this one. Resolve the tracker the way `skills/mine-create-issue/worker.md` Step 3 does: `$ISSUE_TRACKER` unset or empty means GitHub, and a tracker you have no tools for means leaving the Breakdown unfiled, saying why, and stopping without the question below rather than guessing at a tool. Filing is outward-facing, so ask before doing it:

```
AskUserQuestion:
  question: "File the <N> Breakdown issues on <tracker>?"
  header: "File"
  multiSelect: false
  options:
    - label: "File them (Recommended)"
      description: "<N> issues, grouped under <the tracker's milestone, epic, or parent item>"
    - label: "Not yet"
      description: "Leave the Breakdown unfiled; re-run /mine-sketch on the ledger to file later"
```

File per the repo's issue conventions (`git-workflow.md`), grouping the issues under whatever the tracker uses for a milestone (a GitHub milestone, a Jira epic, a parent work item), in dependency order so each issue can link the ones in its `After:`. Each issue body gives its scope at the ledger's altitude, the decisions it implements, and the ledger's repo path; the ledger has to reach the default branch before the issues are picked up, so say that if it's still on a branch. Write each issue key into its Breakdown entry, commit the ledger on the current branch (off the default branch, if the repo requires PRs), and stop.

### On "Revise a decision"

Ask which decision to reopen, or what new decision to add, and what should change. To change a posture stance, update `## Posture` (a stance carried from Phase 4 is already updated), then list the decisions whose answers relied on the old stance and the cases the new stance no longer settles. The user picks which decisions to reopen, and each unsettled case becomes a new decision. Set that decision's `**Ratified:**` back to `pending` (a new decision starts as `pending`), then run Phase 3, Phase 4 with `--re-challenge`, and Phase 5, and return to this gate.

An Altitude change reopens no decisions. Rewrite the ledger at the new altitude instead (re-cite its references, and swap `## Breakdown` and `## Build`), then run Phase 5 and return to this gate.

### On "Save and stop"

Leave `**Status:** draft`. Confirm: "Ledger saved at `<feature_dir>`. Resume with `/mine-sketch <feature_dir>`."

---

## Build Mode

Runs when `/mine-sketch <dir>` finds `**Status:** ratified`.

### Step 1: Orient

Read the whole ledger and the files it names. Check git state (branch, uncommitted changes, recent commits, and `git-branch-behind` for how far the branch trails the default branch) and raise anything surprising, such as being on the default branch, unrelated uncommitted work, or a stale base the ledger's file references may no longer match, before writing code.

Read the `## Build` checklist. If no step is ticked, this is a fresh build. If some are, resume after the last ticked step, using the branch's commits to see where the work stands.

The user ran `/mine-sketch <dir>` on a ratified ledger, so the request to build is already explicit. If Orient raised something surprising, resolve that with the user first. Otherwise name the ledger being built (`<feature_dir>/design.md`, `<M>` ratified decisions), note they can say so to reopen a decision before you start, and begin.

If they ask to reopen a decision: ask which one and what should change. Set `**Status:** draft` and that decision's `**Ratified:**` back to `pending`, then resume sketch mode at Phase 3. A posture stance reopens the same way, handled as in [On "Revise a decision"](#on-revise-a-decision).

### Step 2: Implement

Implement the change with its tests and docs. The ledger is the spec:

- Every ratified decision and every assumption holds in the code.
- Tests pin the behavior each decision specifies. The ledger says what to pin; choosing how is yours.
- When the ledger doesn't settle something, make the call and record it under `**Calls made during the build:**` as `- <the call>: <one line of why>`. The ship-time challenge checks each one against the code. A call that contradicts a ratified decision isn't a build-time call: stop and ask the user whether to reopen the decision.

When you decide not to fix a real finding (from the pre-commit reviewers here, or the ship-time challenge in Step 3), follow `${CLAUDE_CONFIG_DIR:-~/.claude}/skills/mine-sketch/known-issues.md`:

- If you are deferring it on your own (the user never saw it, as with a pre-commit reviewer finding), check its Severity Gate first.
- Then record the finding if it qualifies.

Commit as you judge best. Every repo squash-merges, so there's no required commit sequence. Run the pre-commit reviewers in `git-workflow.md` on each commit that meets its criteria. Tick each `## Build` step, and add each build-time call, in the same commit as the work it describes. When the change needs no doc updates, tick Docs and note "none needed".

### Step 3: Ship-time Challenge

Write the branch's changed files to a list: the union of `git-branch-diff-files`, `git diff --name-only HEAD`, and `git ls-files --others --exclude-standard`, deduplicated. Make sure `<feature_dir>/design.md` is in it. Write the list to `<tmpdir>/challenge-changed-files.txt`, where `<tmpdir>` comes from `get-skill-tmpdir mine-sketch` (or the one this session already has).

Read `${CLAUDE_CONFIG_DIR:-~/.claude}/skills/mine-challenge/challenge-gate.md` and follow it with:

- **`<header>`**: `Challenge`
- **`<gate_type>`**: `ship-challenge`
- **`<target>`**: `<tmpdir>/challenge-changed-files.txt`
- **`<critic_flag>`**: (empty — use triage default 1–3)
- **`<focus_flag>`**: `--focus="The ledger at <feature_dir>/design.md is the reference. (A) Does what landed match its ratified decisions and assumptions, with tests pinning the behavior each one specifies? (B) Where the code diverges, does the ledger's Build section give a sound reason? Check each stated reason against the code. (C) What unintended consequences are there beyond what the ledger covered? Its Posture section is accepted scope: a gap it deliberately leaves is not a finding unless the posture itself is wrong for this change."`
- **`<re_challenge_flag>`**: (empty)
- **`<post_resolution>`**: Fixes go through the normal pre-commit reviewers. A real finding the user left with `disposition: skipped` or `accepted` is recorded as in Step 2; the Severity Gate doesn't apply, since the user already saw it.
- **`<review_log>`**: `<feature_dir>/review-log.jsonl`
- **`<ledger>`**: `<feature_dir>/design.md`

Findings resolve inline, as in any challenge. The `## Build` record is the build's stated reasoning, not evidence: the challenge checks it against the code rather than taking it on its word.

### Step 4: Finish

Settle `<feature_dir>/known-issues.md`'s `Status: open` entries without a per-entry walkthrough:

- An entry from a finding the user already saw and chose to skip in the ship-time challenge stays `open`. It was their call.
- A contained fix that the pre-commit reviewers can verify: fix it now, and set Status to `resolved — fixed before ship`.
- An entry tied to this feature's follow-up work stays `open`.
- An entry that needs its own change should become a tracker issue. Filing is outward-facing, so offer it as an option in the Ship? question below; Status becomes `filed (<issue-key>)` only if the user takes it, and stays `open` otherwise.

When an entry's `Recorded:` line names a different branch from this one, it came from an earlier build; say so in the report.

Then tick `Ship-time challenge`, set `**Status:** built`, and commit the ledger, the review log, and any known-issues updates. Report what was built, any build-time calls, the known issues fixed, and the known issues left open (marking any that need their own tracker issue). This is a completion gate: run `context-pct` and prepend the result.

```
AskUserQuestion:
  question: "[Context: N%] Build complete and challenged. Ship it?"
  header: "Ship?"
  multiSelect: false
  options:
    - label: "Ship via /mine-ship"
      description: "Push and open a PR"
    # Include only when some known issues need their own tracker issue:
    - label: "File the <N> issues, then ship"
      description: "Open a tracker issue per entry (KI-<NNN>, ...), then push and open a PR"
    - label: "Stop here"
      description: "Leave the branch as is"
```

On "Ship via /mine-ship": invoke `/mine-ship`. On "File the <N> issues, then ship": create the issues, update each entry's Status, commit the ledger, then invoke `/mine-ship`.
