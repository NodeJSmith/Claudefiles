---
topic: "Replace mine-sketch's design.md + task files with a decision ledger and a one-session build"
date: 2026-10-02
status: Draft
issue: "#605"
---

# Brief: mine-sketch becomes a decision ledger plus a one-session build

## Bottom line

`mine-sketch` stops producing FR/AC lists and task files for `mine-orchestrate`. It produces a
**decision ledger**: every decision the change needs, each ratified one at a time with a grounded
recommendation, then challenged and combed. A **fresh session** builds the whole change from that
ledger, with the existing pre-commit reviewers. A **ship-time challenge**
then checks the diff against the ledger before shipping. `mine-define`,
`mine-plan` and `mine-orchestrate` are untouched and remain the heavy path.

## Why

A controlled comparison (hassette #1798, `design/research/2026-10-01-process-weight-opus-5-5/` on branch
`research-process-weight-1798`) had three runs implement the same aligned spec:

| | Heavy (`mine-orchestrate`, Sonnet) | Light / Opus 5.5 (one prompt from the ledger) | Light / Sonnet |
|---|---|---|---|
| Outcome | abandoned at 1h48m, $63, 7 steps left | 31 min, ~$37, all 14 ledger rows met | 58 min, ~$41, weaker tests, one false doc claim |

- **The code converged.** All three diffs had the same architecture. Task decomposition, per-task
  executors and per-task review didn't change the code.
- **Heavy's one win was test quality.** It caught a `caplog`/`propagate` test-order trap that the
  Opus-light reviewers missed. That trap came from the ledger itself, which told the implementer
  how to test ("assert log level") instead of what the test must pin.
- **The design phase carried the value.** The ledger surfaced decisions that `mine-sketch` had made
  silently, such as REST retries, a payload leak, and the disconnect case. Challenge's convergence
  check found real gaps in both arms.
- **Recommendations drive the outcome.** The user mostly accepted the recommended option, and in
  the design phase the two arms recommended opposite things on the same question. The user wants
  to keep recommendations, because the agent usually knows the codebase better, but grounded
  enough to push back on.

A prior-art survey (`/tmp/claude-mine-prior-art-LDAgF2/brief.md`, unsaved) found:

- Decision records sized by reversibility (MADR plus Y-statements).
- Documented anchoring when a recommendation is shown before the options.
- EARS and Given/When/Then as the standard way to state behavior without technique.
- LLM conformance judges misjudge often, and more elaborate prompts make that worse.
- No established format separates "assumed" from "decided".

**Caveat:** this is n=1, on a medium change with an unusually complete spec. Large or foggy work
is untested on the light path.

## Success measure

Judged by the hassette PRs built this way:

- **Better:** the same or fewer Codex/CodeRabbit findings, and fewer review rounds, than PRs from
  the current pipeline.
- **Acceptable:** steady.
- **Investigate:** the counts go up. cfl's challenge and comb records are then the first place to
  look.

There is no automated metric. The user judges this by eye across PRs.

## Decisions already made

These are ratified. Critics may still challenge them.

1. **Scope.** Only `mine-sketch` is redesigned. Shared files change only where they reference
   sketch, with one exception: the rubric's second consumer, challenge's `findings-protocol.md`,
   which changes every user-directed and TENSION question repo-wide (decision 7). `mine-define`,
   `mine-plan`, `mine-orchestrate` and cfl's orchestration machinery otherwise stay as-is for now. Deleting them is a later decision that depends on
   how this trial goes, including on one big item.
2. **The build always runs in a fresh session**, for context reasons alone. The ledger must
   therefore be self-sufficient.
3. **The skill keeps its name**, `mine-sketch`. Routing, trigger phrases and habits are unchanged.
4. **The file is still `design.md` with `**Mode:** sketch`.** The challenge findings protocol, the
   archive `**Status:**` regex, sketch's resume detection, and the Addendum convention all key on
   it.
5. **Build mode is `/mine-sketch <dir>`.** Pointing sketch at a ratified ledger starts the build,
   so there's no pasted prompt.
6. **cfl tracking stays where it already works.** Sketch keeps `cfl spec init` for numbering and
   a run for the comb and challenge gates and findings. "Save and stop" leaves the run open
   rather than calling `cfl run stop`, because stopping marks the spec `approved` too early.
   `cfl run complete` at Ratify closes it. Build mode doesn't touch cfl.
7. **The recommendation rubric is a shared reference**:
   `references/common/presenting-decisions.md`. It has two consumers in this change: sketch's
   ratify loop, and challenge's user-directed finding walkthrough in `findings-protocol.md`, where
   a recommendation has been taken as-is most often. The ledger template cites the reference
   rather than restating its rules. `mine-define` can adopt it later.
8. **Big work: an escalation question only.** When the scan shows the change won't fit one
   session, sketch says so and asks "Stop here" or "Continue anyway — I understand the risk". It
   doesn't suggest `mine-wayfinder`. The first big item is handled by
   ear, and the slicing recipe gets encoded after that.
9. **The build's self-report is a record, not evidence.** Build mode lists the calls it made in
   the ledger's `## Build` section, which keeps rationale the diff can't show. The ship-time
   challenge reads it as the build's stated reasons and checks each one against the code.
   Nothing is taken on the record's word.
10. **Some breakage while this lands is acceptable.**

## Lifecycle

The ledger's state lives in the ledger itself, as explicit markers rather than inferred from its
prose.

| `**Status:**` | Meaning | `/mine-sketch <dir>` does |
|---|---|---|
| `draft` | being written or ratified | resumes at the first `**Ratified:** pending` decision, or at the whole-ledger gate if none are pending |
| `ratified` | the user approved the whole ledger | build mode. An empty `## Build` checklist starts fresh, and a partly checked one resumes after the last checked step |
| `built` | the build and its ship-time challenge are finished | reports that the build is done and points to `/mine-ship` |

- **Pending decisions.** Every decision is created with `**Ratified:** pending`, and resume
  matches that string literally.
- **Build progress.** The `## Build` checklist records it. There's no `building` status, because
  the checklist already says whether a build has started.
- **Orchestrate.** Its sketch-phase resume branch checks for `tasks/T*.md`. If there are none, it
  says the directory is a ledger and points to `/mine-sketch <dir>`.

## New flow

### Sketch mode (`/mine-sketch "<request>"`)

1. **Scope.** Paraphrase the request. Run `cfl spec init` and start the run. Scan 3-8 relevant files.
2. **Escalation check.** If the change needs `mine-define`-level investigation, offer to upgrade, as
   today. If it won't fit one build session, say so and ask "Stop here" or "Continue
   anyway" (decision 8).
3. **Draft the ledger** in `design.md`: summary, decisions, and assumptions. Every judgment call
   that would change the code is a decision. None is resolved silently.
4. **Ratify.** For each decision, one at a time:
   - Show the rubric summary as text, before the question.
   - Ask the question, prefixed "Decision N of M". M can grow, and the prefix notes when new
     decisions have surfaced.
   - Write the answer into the decision's block as one `**Ratified:**` sentence.
   - New decisions can surface mid-interview. They go through the same loop.
5. **Challenge**, mandatory with 2 critics, through `challenge-gate.md` as today. A finding that adds
   or changes a decision goes through the rubric and ratification loop again.
6. **Comb** the ledger once, after challenge, so it also catches inconsistency challenge's edits
   introduced. This replaces today's comb → challenge → re-comb loop.
7. **Whole-ledger gate.** Show the full ledger, then ask Ratify, Revise a decision, or Save and
   stop.
   - **Ratify** sets `**Status:** ratified`, runs `cfl run complete`, and tells the user: "Start a
     fresh session and run `/mine-sketch <dir>`."
   - **Revise** reopens the named decision, so its `**Ratified:**` line goes back to `pending`.
     Then it runs that decision through steps 4–6 and returns to this gate.
   - **Save and stop** leaves the status at `draft` and the cfl run open.

A CRITICAL challenge finding still offers the upgrade to `mine-define`, as today.

### Build mode (`/mine-sketch <dir>`, where `<dir>/design.md` has status `ratified`)

1. Read the ledger and the files it names, and check git state (branch, uncommitted changes,
   recent commits) before starting or resuming. Open by naming the ledger being built, so the
   user can ask to reopen a decision instead. Reopening sets `**Status:**` back to `draft` and that
   decision's `**Ratified:**` back to `pending`, then returns to the sketch-mode flow for it.
2. Implement the change with tests and docs, committing as the agent judges best. The pre-commit
   reviewers from `git-workflow.md` gate each commit. There's no required commit sequence, since
   every repo squash-merges. Tick each `## Build` checklist step and add build-time calls as they
   happen, in the same commit as the work.
3. **Ship-time challenge** through `challenge-gate.md`, the same way `mine-orchestrate` Step 3.5
   runs it:
   - **Gate type:** `ship-challenge`.
   - **Target:** the branch's changed-files list, which includes `design.md`.
   - **Focus:** the ledger is the reference. It asks three questions:
     - (A) Does what landed match the ratified decisions and assumptions, with tests pinning the
       behavior each one specifies?
     - (B) Where it diverges, does the `## Build` record give a sound reason, checked against the
       code?
     - (C) Are there unintended consequences beyond what the ledger covered?
   - Findings resolve inline as in any challenge, and fixes go through the normal pre-commit
     reviewers.
4. Set `**Status:** built`, tick the last checklist step, and offer `/mine-ship`.

## Ledger format (`skills/mine-sketch/design-template.md`)

```markdown
# Design: <topic>

**Date:** YYYY-MM-DD
**Status:** draft | ratified | built
**Mode:** sketch

## Summary
<Problem, the change, in scope, out of scope. Short.>

## Decisions

### D1: <question>
**Deciding factor:** <what the recommendation optimizes, e.g. "no breaking change">

| | A: <option> | B: <option> | C: <option> |
|---|---|---|---|
| <criterion 1> | | | |
| <criterion 2> | | | |

**Recommendation:** A, because <reason tied to the deciding factor>.
**Pick B instead if** <condition>. **Pick C instead if** <condition>.
**Reversibility:** easy | hard (<why>)
**Ratified:** pending  ← replaced with one sentence: chose X over Y, to achieve Q, accepting D

## Assumed
- <fact or inherited constraint>. Evidence: <file:line, issue, or doc>.

## Build
<Written by build mode only.>
- [ ] Implementation and tests committed
- [ ] Docs
- [ ] Ship-time challenge

**Calls made during the build:** <judgment calls the ledger didn't settle, each with one line of
why. The ship-time challenge checks each against the code.>

## Addendum
<Only after a terminal status.>
```

**Content rules:**

- **One home per decision.** Its options, reasoning and ratified answer all live in its block, with
  no second "Ratified" table.
- **Behavior, not technique.** Decisions and assumptions state what behavior a test must pin,
  never how to test it: no fixtures, no capture mechanisms, no test-file layout.
- **"Assumed" holds facts and inherited constraints**, each with evidence. It is not an
  implementation plan. Anything with more than one reasonable answer is a decision.
- **Each decision block follows the rubric** in `references/common/presenting-decisions.md`. The
  template cites it and doesn't restate its rules.
- **A small decision may collapse.** One with a single obvious answer and easy reversibility can
  skip the table and keep the deciding factor, the recommendation, and "pick X if".

## Recommendation rubric (`references/common/presenting-decisions.md`)

Before any question that asks the user to pick among options with a recommendation:

1. **Deciding factor first.** Name what the recommendation optimizes, in one line.
2. **Same criteria for every option.** Use a criteria × options table, so a weak recommendation
   shows as a bad trade rather than a shorter list.
3. **"Pick X instead if"** for every non-recommended option.
4. **Fill in the table before choosing**, so the pros and cons aren't written to justify a pick.
5. **Persist the reasoning.** The rubric goes in the artifact (the ledger), not only in chat, so
   critics can attack the reasoning and not only the outcome.

## Files

- **Rewrite:**
  - `skills/mine-sketch/SKILL.md`
  - `skills/mine-sketch/design-template.md`
- **Create:**
  - `references/common/presenting-decisions.md`
- **Modify:**
  - `rules/common/invariants.md`: Domain References row for the rubric.
  - `skills/mine-build/SKILL.md`: Path D label, description and text.
  - `REFERENCE.md`, `ONBOARDING.md`.
  - `rules/common/capabilities-core.md`: sketch trigger phrases ("quick design and tasks").
  - `skills/mine-challenge/findings-protocol.md`: the sketch-template note assumes FR/AC. Also,
    before each user-directed and TENSION question, show the rubric summary (deciding factor,
    criteria × options, "pick X instead if").
  - `skills/mine-define/design-doc-format.md`: its intro says sketch shares the FR/AC format.
  - `skills/mine-comb/SKILL.md`: names sketch's comb phase number.
  - `tests/test_design_doc_contracts.py`: the sketch half asserts FR/AC structure. Rewrite it for
    the ledger template.
  - `tests/test_challenge_mandate_contracts.py`: confirm it still holds, since sketch keeps a
    challenge phase with `--critics=2` and the CRITICAL escalation.
  - `skills/mine-orchestrate/resume-protocol.md`: the sketch-phase branch redirects to
    `/mine-sketch <dir>` when no `tasks/T*.md` exist. It still advances old sketch runs that do
    have task files.
- **Untouched:**
  - The cfl gate types `sketch-comb` and `sketch-challenge`.

## Known gaps

- **Large or foggy work is untested.** It is handled by ear the first time (decision 8).
- **Nothing tests agent behavior on the new flow.** Contract tests check the skill text only.
  The first real hassette runs are the test.
- **A parked draft's cfl run never closes.** "Save and stop" leaves the run open, and nothing
  closes it if the draft is abandoned. `cfl stop-orphans` reaps it only if the worktree is
  deleted, and then marks the spec `approved`. That's acceptable for a personal tool. Session
  transcripts (ccrecall) answer "what happened" when the records are unclear.
- **Ship-time challenge findings aren't recorded in cfl.** Build mode has no cfl run, so
  `challenge-gate.md` skips its cfl calls. The findings live only in the challenge's findings file.
- **There is no automated success metric.** It is judged by eye on hassette PRs.
- **Ratified decisions may be shielded from critics.** Ratifying before challenge can suppress
  critique of settled rows (Claudefiles #604). A later re-run did challenge one, so the evidence
  is mixed.
- **Build mode has no `cfl run status` visibility.** Decision 6 keeps cfl out of the build, so
  progress is visible only from the `## Build` checklist and the branch's commits.

## Implementation notes

Decided during implementation and review, after the brief was challenged:

- **`challenge-gate.md` gains an optional `<focus_flag>`**, so build mode can pass its (A)/(B)/(C)
  focus. Every other caller passes it empty.
- **Challenge's synthesis writes the rubric.** `synthesis-procedure.md` step 6 fills in the deciding
  factor, criteria table, and "pick X instead if" before choosing a recommendation, and
  `findings-protocol.md` shows those stored fields. A table built at question time would argue for a
  pick already made. The findings format stays at version 4: the fields are presentation-only.
- **cfl setup moves after the escalation check**, so "Stop here" and "Upgrade" leave no orphan spec.
- **The challenge's resume check compares event ids.** Every ratify pass emits
  `sketch.design-written`. The challenge is skipped on resume only if a `sketch-challenge`
  persisted after the last one, so a revised ledger is always re-challenged.
- **Built ledgers are not archived.** `built` is the ledger's terminal status. `cfl archive` would
  only relabel it, since a ledger has no `tasks/` to remove.
- **Also modified:** `rules/common/git-workflow.md`, `skills/mine-challenge/SKILL.md`,
  `skills/mine-define/SKILL.md` and `skills/mine-orchestrate/post-execution-pipeline.md` (the
  `<focus_flag>` parameter and the build-mode challenge).
