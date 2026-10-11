---
topic: "How much of the define → plan → orchestrate pipeline still pays off with Opus 5.5"
date: 2026-10-01
status: Draft
---

# Process weight with Opus 5.5: hassette #1798

## Bottom line

Once the design decisions were ratified, the implementation pipeline barely mattered. Three runs built
the same aligned spec. Their core code came out nearly identical: same classes, same conversion point,
same call sites, even the same line numbers. A one-prompt Opus 5.5 run
with a decision ledger finished in 31 minutes for about $37. The full `mine-orchestrate` run had not
finished after 1h48m and $63, and was abandoned. The heavy run's real advantage was test quality. A
single test-focused review pass would likely buy that much more cheaply.

What earned its keep was the work *before* implementation: getting every decision in front of the
user and challenging it. The ledger and challenge rounds caught real design gaps in both arms; task
files, per-task executors and per-task review did not change the code.

## Setup

- **Issue:** hassette #1798, stop re-sending non-idempotent WebSocket commands on response timeout. It's
  medium-sized: a new exception family, conversion in `send_and_wait`, a late-reply record, six call
  sites, and docs on four pages.
- **Design phase:** two arms worked the same issue.
  - Heavy arm: `mine-sketch` produced `design.md` and task files.
  - Light arm: a decision ledger, with a "Needs your call" table, a Ratified table, and Assumed
    bullets.
  - Both arms ran `mine-challenge`.
  - The user answered both arms' questions. The two arms were then aligned to one spec, the light
    ledger's, which was judged smaller and better.
  - The heavy `design.md` and task files were rewritten to match it, and both were combed clean.
- **Implementation phase:** three runs started within the same minute from that spec.

| Arm | Driver | Models |
|---|---|---|
| Heavy | `/mine-orchestrate` with 4 task files | Sonnet 5 orchestrator and executors; spec, code and integration reviewers per task |
| Light / Opus | one prompt: implement from the ledger, RED/GREEN, CLAUDE.md gates, commit, append "Made during implementation" | Opus 5.5 main, with Sonnet reviewers via global rules |
| Light / Sonnet | the same prompt | Sonnet 5 main and reviewers |

**Grading:**
- **Blind judge:** one Opus `deep-worker` saw both light diffs as A/B in a single pass, scoring them
  against the ledger row by row (`judge.md`; A = Sonnet, B = Opus).
- **Spot checks:** I re-ran the judge's key claims myself, plus the full `nox -s dev` suite in each
  worktree.
- **Cost:** summed from transcript `usage` fields, deduplicated by message id, including subagent
  transcripts (`session_cost.py`). These are list prices, with Opus 5.5 assumed at $5/$25 per MTok.
  `orchestrate-cost` was not used: it doesn't work.

## Results

| | Heavy (stopped) | Light / Opus | Light / Sonnet |
|---|---|---|---|
| Wall time | 1h48m, T04 in review, 7 pipeline steps left | **31 min** | 58 min |
| Cost | $63 so far: main $15, 24 subagents $48 | **~$37**: main $13, subagents $24 | ~$41: main $26, subagents $15 |
| Mid-build questions to the user | 0 | 0 | 0 |
| Code vs ledger | meets it | meets all 14 rows | code meets it; docs only partly meet row 13 |
| Consequential unledgered decisions (judge's count, from code) | not judged | 6: 5 good, 1 neutral | 5: 1 good, 2 neutral, 2 bad |
| Tests | strongest: every spec'd behavior pinned; mocked logger | strong, but 4 log tests depend on test order (`caplog`) | weak: mostly format-string matching on a mocked logger |
| Docs | not graded | accurate | one false claim in `harness.md` |
| Commits | one WIP commit per task | RED, then GREEN, then docs | one squashed commit, so no RED evidence |
| Full suite (`nox -s dev`) | not run | 8088 passed | 8072 passed |

## Findings

1. **Implementation converged once decisions were fixed.** The three diffs differ in wording, helper
   extraction, and test layout. They do not differ in architecture. The heavy pipeline's structure
   (task decomposition, executor isolation, per-task spec review) bought no design benefit on a spec
   this complete.

2. **Opus 5.5 with a ledger is the best value.**
   - It took half the wall time of Sonnet-light and was the cheapest of the three.
   - It had the best docs, and it made the safest judgment call no one asked for: it logs HA's error
     *code* on a late failure, not the message text, which can echo payload values.
   - It was cheaper than Sonnet even at Opus prices. Sonnet took more turns, read 72M cached tokens to
     Opus's 20M, and wrote twice the output.
   - Opus pushed review work into Sonnet subagents, so the main session's context percentage
     understates its cost.

3. **The heavy pipeline's one real win was tests.** Its tests pinned everything the spec asked for. It
   also avoided a trap that Opus-light walked into: the shared `logging_pipeline` fixture sets
   `propagate = False` on the `hassette` logger and never resets it, which breaks `caplog` in later
   tests in the same process. Opus-light's own code, integration and wtf reviewers didn't catch it, and
   neither did the full suite (`--dist loadscope` happened to hide it). Sonnet-light hit the flake,
   worked out the cause, and switched to a mocked logger. The heavy run's executor did the same up
   front and documented why. A test-focused reviewer on the light path would likely close this gap
   for a fraction of the cost.

4. **The spec caused that defect.** The ledger said to assert log levels, and that pushed both
   implementers toward `caplog`, against the house no-log-capture rule. Ledgers and specs should state
   what behavior a test must pin, not how to test it.

5. **"Made during implementation" self-reports aren't reliable.**
   - Opus listed 25 items, mostly naming and wording, with the 3–4 real calls buried among them.
   - Sonnet listed 15 and was more candid about scope cuts (testing only 1 of the 8 helper domains),
     but omitted both of its bad calls: misleading `Raises` docstrings, and HA error text in the late
     log.
   - The judge's independent count matched neither list. Grade from the diff.

6. **The design phase is where the value is.**
   - From the design-phase half of this experiment:
     - The ledger surfaced decisions that `mine-sketch` made silently: REST retries, a payload leak in
       error messages, and the disconnect case.
     - Sketch silently picked a `ValueError` validation and a `fix!` marker.
     - Challenge, especially its convergence check, found real gaps in *both* arms.
   - Two weaknesses showed up:
     - The user picked the recommended option every time, even where the two arms recommended
       opposite things, so how the recommendation is framed drives the outcome.
     - Ratifying a decision sometimes shielded it from the critics (Claudefiles #604). A later re-run
       did challenge a ratified row, so that evidence is mixed.

## Caveats

- One issue, one run per arm. It's a medium-sized change with a precise spec. A large or foggy
  change might reward task decomposition more.
- The aligned spec was the light ledger, polished by two combs. Its completeness is a big part of
  why implementation converged.
- The heavy arm was stopped before its ship-time challenge, clean-code and final-review steps. Those
  might have found something, but they would not have changed the cost picture.
- The light arms got a review loop for free, through the global `git-workflow.md` rule that requires
  code, integration and wtf review before commit. "Light" is not "no review".
- The Opus price is an assumption, so dollar figures are approximate. The ratios hold.

## Files

- `judge.md`: the blind judge's report on the two light arms (A = Sonnet-light, B = Opus-light).
- `session_cost.py`: a per-session cost calculator over transcripts, including subagents. Usage:
  `python3 session_cost.py <session>.jsonl ...`
