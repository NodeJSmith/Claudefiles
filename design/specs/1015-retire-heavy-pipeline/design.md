# Design: Retire the define → plan → orchestrate pipeline

**Date:** 2026-10-05
**Status:** built
**Mode:** sketch

## Summary

Issue #616. The heavy pipeline (`mine-define` → `mine-plan` → `mine-orchestrate`) has been replaced in practice by `mine-sketch`: a ratified decision ledger, a mandatory challenge, and a one-session build, with oversized work splitting into separate ledgers. Issue #605 measured orchestrate at 3–5x the cost of a single session. Recent hassette work produced four ledgers and two re-splits and created no task files. The pipeline's skills, routing, rules and docs are still installed, though, and they load instructions for a workflow nobody uses.

This change deletes the pipeline and whatever exists only to serve it, rewires every surviving caller, and removes the references. The decisions below each name their own sites. This summary only gives the overall shape.

**Deleted:**
- the skills `mine-plan`, `mine-orchestrate` and `mine-implementation-review`, along with `tests/test_mine_orchestrate_protocol_contracts.py`, which tests them. Retiring these is the premise of #616, not a decision here.
- the skills `mine-define` (D1) and `mine-build` (D4)
- the verdict-line machinery (D5)
- `agents/spec-reviewer.md` (D6)
- `bin/orchestrate-cost` (D7)

**Added:** `skills/mine-sketch/known-issues.md` (D10).

**Rewired:** callers and references in this repo, per D2, D3, D4, D7, D8, D9 and D10.

**Also rewired, in `~/Dotfiles` (explicitly requested):** `scripts/hooks/reset-nudge.sh:139` names `/mine-orchestrate <feature_dir>` as one of "exactly two valid" resume commands. It becomes `/mine-sketch <feature_dir>` for ledger work. The receiver docs that repeat it change to match: `config/claude/receiver/CLAUDE.md:207`, `docs/subsystems/reset-receiver.md`, and the `services/user/units/claude-receiver.service` description. Follow Dotfiles' own branch and PR rules, per `repos.md`.

**Out of scope:** the `packages/cfl/` package. Its orchestrate-era commands (`archive`, task and question tracking) are audited in #615, and this change only edits cfl where a direct reference would break. One such site is known: `packages/cfl/tests/test_snapshot.py` reads `skills/mine-define/design-doc-format.md`. Delete `test_design_doc_format_examples_match_cfl_parser`, `_extract_example_block` and the `DESIGN_DOC_FORMAT` constant, and drop the pointer comment at `packages/cfl/src/cfl/snapshot.py:19`. The parser itself stays for #615. So do `run.py`'s resume hints, which still name the retired skills. Stop any open define/plan/orchestrate runs with `cfl run stop` rather than editing them here. `CHANGELOG.md` history is left as it is. Archived `design/specs/*` docs are frozen and stay untouched.

## Decisions

### D1: What happens to `mine-define`?

**Deciding factor:** one design path (sketch).

| | A: Delete it with plan/orchestrate | B: Keep it as a standalone design-doc writer |
|---|---|---|
| Paths to a design | one (sketch) | two, with overlapping triggers ("spec this out" vs "sketch this") |
| Files kept | 0 | `skills/mine-define/` (6 files) plus its contract tests |
| What its output feeds | n/a | nothing, since plan/orchestrate consume `design.md` FR/AC and are gone |
| Covers "deep investigation" work | no dedicated path. It comes up in conversation or through `/mine-research` (see D2) | yes, through its own researcher dispatch |

**Recommendation:** A. Without `mine-plan`, a define-format `design.md` has no consumer, and its FR/AC structure exists to feed task-file traceability.
**Pick B instead if** you still want a design doc for its own sake (handing a spec to another person or team) that isn't a ratified ledger.
**Reversibility:** easy (git history keeps the skill)
**Ratified:** Chose deleting mine-define over keeping it standalone, to leave sketch as the single design path, accepting that formal FR/AC spec docs are no longer produced.

### D2: What happens to `mine-sketch`'s escalation prompts once `mine-define` is gone?

`skills/mine-sketch/SKILL.md` has escalation prompts in two places:

- Phase 1's `### Escalation check`. It holds "needs investigation, not a sketch" (→ `/mine-define`) and "the build won't fit one session" (stop or continue).
- Phase 4's CRITICAL-finding escalation (→ `/mine-define`).

**Deciding factor:** each escalation lands on a step that answers what the escalation found.

| | A: Phase 1 investigation → `/mine-research`, then re-sketch with the brief. Phase 4 → "stop and rescope or split" | B: Remove the two `/mine-define` escalations | C: Both `/mine-define` escalations → "stop and rescope" | D: Remove every escalation prompt, including the one-session check |
|---|---|---|---|---|
| Phase 1 "architectural question with no obvious answer" | answered by a research brief, which sketch then takes as input | raised in conversation | the user does it by hand | raised in conversation |
| Phase 1 "won't fit one session" | prompt kept | prompt kept | prompt kept | raised in conversation |
| Phase 4 CRITICAL structural finding | the user splits or rescopes | no checkpoint beyond the challenge's own per-finding walkthrough | same as A | same as B |
| Wording to write | two prompts reworded | two prompts deleted, contract-test anchors dropped | two prompts reworded | whole `### Escalation check` section and Phase 4 block deleted, contract-test anchors dropped |

**Recommendation (at drafting):** A. Research is the existing tool for "we don't know enough", and splitting is the observed answer to "the shape is wrong".
**Pick B instead if** you've never actually hit either escalation and want less ceremony. **Pick C instead if** you'd rather pick the follow-up yourself each time. **Pick D instead if** scope and splitting should always be conversational calls, never prompts.
**Reversibility:** easy
**Ratified:** Chose removing every escalation prompt (D: first ratified as B, then extended to D during the challenge, Finding 10) over routing them to research or a rescope prompt, to let "this needs investigation", "this structure is wrong" and "this is too big for one session" come up as ordinary conversational calls, accepting that nothing forces the stop. Delete Phase 1's whole `### Escalation check` section, Phase 4's CRITICAL escalation block and the `<post_resolution>` pointer to it ("continue to the CRITICAL escalation below"), Phase 2's "Accepted risk" bullet, and the Routing table's "escalation check" mention in the `**Status:** draft` resume row. Remove the contract test's upgrade-prompt anchors.

### D3: What do `mine-grill` and `mine-research` hand off to instead of `/mine-define`?

Both have a "Specify / Design it (`/mine-define`)" next-step option, and `mine-grill`'s "Done for now" message tells the user to resume with `/mine-define`.

**Deciding factor:** the brief reaches the ledger as input, with no extra hop.

| | A: Replace with "Sketch it (`/mine-sketch`)", passing the brief path | B: Drop the option and leave "Build it (`/mine-build`)" (scored before D4, which makes it moot) |
|---|---|---|
| Brief reaches the design | directly, once `mine-sketch` Phase 1 is taught to read it (last row). Today `SKILL.md` has no brief handling | through `mine-build`'s prior-analysis detection, then the routing gate |
| Gate size | unchanged | one option fewer |
| Change to `mine-sketch` | Phase 1 reads any brief or research path named in the request | none |

**Recommendation:** A. The brief exists to feed a design step, and sketch is now that step.
**Pick B instead if** you'd rather keep every "go build" path behind `mine-build`'s single routing gate.
**Reversibility:** easy
**Ratified:** Chose a "Sketch it (`/mine-sketch`)" handoff carrying the brief path over dropping the option, so the brief feeds the ledger directly, accepting a small Phase 1 addition to `mine-sketch` that reads a named brief or research path as prior work.

### D4: What happens to `mine-build`?

`skills/mine-build/SKILL.md` is a routing gate with Path A (Simple), Path D (Structured: sketch), Path B (Complex: full caliper), and Path C (Accelerated: post-analysis caliper). With B and C gone and D2's escalations moved into conversation, only the question "trivial, so just do it, or real decisions, so sketch" is left.

These callers hand off to it:

- `skills/mine-audit/SKILL.md`, `skills/mine-decompose/SKILL.md`, `skills/mine-tool-gaps/SKILL.md`, `skills/mine-research/SKILL.md`, `skills/mine-grill/SKILL.md`, `skills/mine-brainstorm/SKILL.md`, `skills/mine-eval-repo/SKILL.md`, and `commands/mine-issues.md`
- the "build this / implement this" trigger row in `rules/common/capabilities-core.md`

(`skills/mine-challenge/SKILL.md`'s call-site list also names it. That edit is handled under D7.)

**Deciding factor:** no skill whose only job is a question the main session already answers in conversation.

| | A: Delete `mine-build` | B: Keep a two-route gate (Simple / Sketch) |
|---|---|---|
| Hops from a handoff to the work | 0 for small work. 1 (sketch) for decision-heavy work | 1 extra routing prompt every time |
| Simple-path review | `git-workflow.md`'s mandatory pre-commit reviewers, which already apply | duplicated in Path A |
| Frontend design-token check | moved to `references/common/frontend.md`, which weakens it: it runs only when that reference is loaded for frontend work, and only where a `design/context.md` already exists, since no surviving workflow creates one. `mine-build` is the only surviving reader of that file once D1 deletes `mine-define`, which carries the same check | stays in `mine-build`, unconditional |
| Caller edits | 8 handoffs reworded and 1 trigger row deleted | descriptions reworded |

**Recommendation:** A. Every caller's "Build it" option becomes "implement it now". The session implements small, clear changes directly and suggests `/mine-sketch` in conversation when the work has real decisions. `test_install.py` and `test_skill_census.py`, which use `mine-build` only as a sample skill name, switch to a surviving base skill.
**Pick B instead if** you want a fixed checkpoint before any implementation starts from a handoff.
**Reversibility:** easy
**Ratified:** Chose deleting `mine-build` over keeping a two-route gate, to remove a routing hop the main session can decide in conversation, accepting that small-versus-sketch is now an unprompted judgment call. Its design-token check moves to `references/common/frontend.md`, accepting that it runs only when that reference is loaded and only where a `design/context.md` exists, which in practice is rare since nothing creates one.

### D5: What happens to the reviewer verdict-line contract and concise-return mode?

`skills/mine-orchestrate/verdict-line-format.md` defines the canonical `**Verdict:**` line. `agents/code-reviewer.md` and `agents/integration-reviewer.md` carry `<!-- SYNC -->` comments to that file and a "Concise-Return Mode" section.

Three things enforce or measure the contract:

- `bin/lint-verdict-line` and `tests/test_lint_verdict_line.py` check it over the reviewer files.
- The `lint-verdict-line` hook block in `prek.toml` (lines 99–106, `always_run`) runs that lint on every commit.
- `bin/orchestrate-concise-probe` measures concise-return compliance.

Only orchestrate parses the line or sends `CONCISE-RETURN-MODE`. Nothing else greps for it: no consumer turns up in `skills/mine-review`, `mine-sketch`, `mine-challenge`, or `mine-ship`.

**Deciding factor:** no contract machinery without a consumer.

| | A: Delete the format doc, lint, lint test, prek hook, concise probe, SYNC comments and concise-return sections. Keep each agent's Assessment block as plain report output | B: Move `verdict-line-format.md` to `references/common/` and keep the lint and hook |
|---|---|---|
| Machine consumer | none. People and the main session read the Assessment | none, so the lint enforces a format nobody parses |
| Files kept | 0 | format doc, lint, test, hook |
| Readers' view of the reviewer report | unchanged (same Assessment block) | unchanged |

**Recommendation:** A. The lint guards a parser that no longer exists. `spec-reviewer.md` and `visual-reviewer-prompt.md`, two of the four files the lint covers, are deleted anyway. The prek hook block is removed in the same commit as the script. Otherwise every commit fails.
**Pick B instead if** you plan to parse reviewer verdicts mechanically again soon, for example in agent-stats.
**Reversibility:** easy
**Ratified:** Chose deleting the verdict-line format doc, `bin/lint-verdict-line`, its test, its `prek.toml` hook block (in the same commit), `bin/orchestrate-concise-probe`, the SYNC comments and the concise-return sections over relocating them, to drop a contract with no consumer, accepting that the reviewers' Assessment format is no longer lint-enforced.

### D6: What happens to the orphan agents?

`spec-reviewer` verifies an orchestrate task against its Verify section, which only exists in task files. `planner` is unrelated to the pipeline's task files: `rules/common/interaction.md` dispatches it for "structured planning". Only its `/mine-plan` note and the description clause "those go to mine-build and the caliper workflow" point at the pipeline.

**Deciding factor:** keep an agent only if something still dispatches it.

**Recommendation:** delete `agents/spec-reviewer.md`. Remove it from `install.py`'s bundle tuple and `rules/common/performance.md`'s list by running `bin/lint-agent-models --write`, and drop the `references/common/agents.md` example that names it. Keep `agents/planner.md`, minus its `/mine-plan` note and its `mine-build`/caliper description clause.
**Pick B (delete `planner` too) instead if** you want it gone as well. Then `interaction.md`'s "launch planner" instruction needs a replacement, which belongs in a separate change.
**Reversibility:** easy
**Ratified:** Chose deleting `spec-reviewer` and keeping `planner` over deleting both, to remove only the agent with no dispatcher, accepting `planner`'s continued, separate existence.

### D7: How are pipeline references in surviving rules, references, agents and docs handled?

The sites are:

- `rules/common/`:
  - `git-workflow.md`: the mandatory-challenge sentence. Task File Cleanup is D8.
  - `invariants.md`: "Mandatory Challenge in Orchestration"
  - `capabilities-core.md`: the define/plan/orchestrate trigger rows and the `orchestrate-cost` row
  - `sequence-verifiable-units.md`: "Applies to mine-orchestrate and mine-ship"
  - `pre-existing-verification.md`: "Orchestration-Specific Note"
  - `interaction.md`: the gate list
  - `pause-safely.md`: the example
  - `redesign-from-first-principles.md`: its Addendum pointer, re-pointed at `skills/mine-sketch/design-template.md`
- `references/common/`: `agents.md` (the PARALLEL comment and the sequential-executor example), `testing.md` ("WP in the caliper workflow" and the SYNC to the implementation-review prompt), `receiving-code-review.md` (the SYNC to `retry-prompt.md`), and `staleness-preflight.md` (the `mine-define` example).
- `agents/`:
  - `code-reviewer.md` and `integration-reviewer.md`: the "Orchestrate pipeline" invocation-mode lines
  - `integration-reviewer.md`: the task-file reading in its design-doc check
  - `researcher.md`: the define-specific rows
  - `fine-toothed-comb.md`: the task-file example
- `agents/standard-worker.md` and the five `agents/engineering-*.md`: the "Executor note" pointing at `implementer-prompt.md`, `standard-worker`'s "orchestrate-executor fallback" description clause, and the "WP" wording in `engineering-frontend-developer.md`. The specialists still have a dispatcher (`references/common/agents.md:21-25`), so only the wording goes.
- Contracts whose consumer survives are re-owned by `mine-sketch`, not deleted: the caller lists in `skills/mine-comb/SKILL.md:12` and `comb-gate.md:3,12`, the `--spec` caller note in `challenge-gate.md:3,25`, the field-ownership rows in `researcher.md:32-34`, and the `<feature_dir>` allowances in `staleness-preflight.md:63`.
- Other skills and commands that name the pipeline:
  - `mine-challenge` (`SKILL.md` target-type table and call-site list, `personas/specialist/agent-definition.md`)
  - `mine-ship`: its Phase 1.5 prior-clean-code-run detection only matches orchestrate's tmpdir
  - `mine-clean-code`: its "when invoked from mine-orchestrate" summary
  - `mine-how` and `mine-prior-art`: examples and rows
  - `commands/mine-end-of-day.md`: the task-files mention
- `REFERENCE.md` and `ONBOARDING.md`: remove the deleted components and the define → plan → orchestrate walkthrough and cfl section (`ONBOARDING.md` lines 88–111 and 175–181), and add the D10 protocol.
- Deleted outright: `bin/orchestrate-cost`, which only measures orchestrate runs.
- Stragglers: `.gitignore:17` (`.orchestrate-state.md`), plus the comments in `bin/find-review-md:22`, `bin/git-branch-behind:6`, `scripts/hooks/context-tier.sh:19`, `scripts/hooks/dispatch-stats.sh:10` and `scripts/hooks/subagent-compaction-check.sh`.

**Deciding factor:** each surviving principle stays true without the pipeline, and no rule names a skill that no longer exists.

| | A: Delete orchestrate-only sections. Generalize sentences whose principle still holds. Re-point the mandatory-challenge rule at `mine-sketch` (sketch time and build time) | B: Rewrite every orchestrate-specific section as a `mine-sketch` build-mode equivalent |
|---|---|---|
| Rule length | shorter | about the same |
| Risk of inventing new sketch requirements | none | high. For example, `pre-existing-verification`'s `base_commit` note has no sketch analogue |
| Mandatory-challenge invariant | kept, with sketch as its only call site | kept |
| Parallel Executor Isolation invariant | kept, since it applies to any parallel writers | kept |

**Recommendation:** A. Afterward, regenerate `performance.md` and `install.py` with `bin/lint-agent-models --write`.
**Pick B instead if** you see a specific orchestrate rule whose behavior you want carried into sketch build mode. Name it, and it becomes its own decision.
**Reversibility:** easy
**Ratified:** Chose delete-and-generalize over porting each orchestrate section to sketch, to keep only principles that stand without the pipeline. This accepts that orchestrate-specific guidance (`base_commit`, sequential executors) disappears rather than gaining a sketch analogue. It also accepts, as confirmed during the challenge, that orchestrate's visual-reviewer gate and `tdd.md` discipline are dropped on purpose. Known-issues tracking is kept by D10.

### D8: What happens to the task-file cleanup machinery?

Three places assume task files can exist:

- the "Task File Cleanup" section in `rules/common/git-workflow.md`, which runs `cfl archive` before every commit
- step 34 of `skills/mine-create-pr/worker.md`
- the "Spec Run Status" section in `commands/mine-status.md`, gated on `T*.md`

With `mine-plan` gone, nothing creates task files. One stray `design/specs/024-svelte-voice-guide/tasks/.gitignore` exists and holds no `T*.md`.

**Deciding factor:** don't run a check on every commit for files nothing can produce.

| | A: Remove all three, including the section's closing "archiving freezes design.md" paragraph. `redesign-from-first-principles.md`'s terminal-status exception (D7) already carries that idea | B: Keep them as harmless no-ops until #615 decides `cfl archive`'s fate |
|---|---|---|
| Per-commit cost | none | one `find` per commit, which is cheap but noise in the rule text |
| Coupling to #615 | `cfl archive` stays in cfl, unreferenced by rules. #615 decides whether to delete it | rules keep calling it |
| `mine-status` | drops the task section | keeps a section that never fires |

**Recommendation:** A. A sketch ledger has its own terminal status (`built`), so it doesn't need `cfl archive` to stamp it.
**Pick B instead if** #615 might keep task files alive for some other producer.
**Reversibility:** easy
**Ratified:** Chose removing Task File Cleanup, the create-pr archive step, and mine-status's task section over keeping them until #615, to stop running checks for files nothing produces, accepting that `cfl archive` becomes unreferenced by rules pending #615.

### D9: How do `mine-sketch` and `mine-challenge` treat legacy define-format `design.md` files?

About 40 docs under `design/specs/` lack `**Mode:** sketch`. `mine-sketch`'s routing row sends them to `/mine-plan`. `findings-protocol.md` falls back to `skills/mine-define/design-template.md`'s Content Rules for any non-sketch design doc.

**Deciding factor:** no instruction points at a deleted file.

| | A: Sketch reports "pre-sketch design doc. Start a new sketch with it as input" and stops. The findings protocol applies the sketch template's rules to sketch ledgers and generic one-fact-one-home to other design docs | B: Sketch converts a legacy doc into a ledger on the spot | C: Write no legacy handling at all |
|---|---|---|---|
| Work to build | a routing row and a findings-protocol sentence | a conversion procedure that has never been designed | delete the routing row and the fallback clause |
| Legacy docs actually resumed | rare. Most are `archived` | same | same, with no special routing |

**Recommendation (at drafting):** A.
**Pick B instead if** you have un-archived define designs you actually want to build. **Pick C instead if** the case won't recur and isn't worth any prose.
**Reversibility:** easy
**Ratified:** Chose C (write no legacy handling at all) over A and B, to avoid prose for an edge case that won't recur, accepting that a legacy doc passed to sketch gets no special routing. Delete `mine-sketch`'s "No `**Mode:** sketch`" routing row. `findings-protocol.md` cites only the sketch template's Content Rules, with no fallback. Drop the `mine-define/design-template.md` assertion from `test_challenge_inline_resolution_references_design_template_content_rules`.

### D10: Where does known-issues tracking live once `mine-orchestrate` is gone?

`skills/mine-orchestrate/known-issues-protocol.md` defines the durable `<feature_dir>/known-issues.md`. It holds `KI-NNN` entries with Status, Reason not fixed (`faithful-port | out-of-scope | behavior-change | needs-decision | blocked`), Affected files, Issue, Why deferred, Recommended follow-up, and Acceptance criteria. It also defines what qualifies, a Severity Gate (user-visible breakage with no explanation, silent data loss, a security or auth exposure, or a blocked core workflow can't be silently deferred), and a pre-ship walkthrough (fix now, file, or keep open). Today `mine-sketch` build mode only mentions skipped CRITICAL or HIGH challenge findings in chat (`skills/mine-sketch/SKILL.md` Step 3 `<post_resolution>`, Step 4).

**Deciding factor:** a real issue left unfixed during a build always leaves a durable record, and you see it before shipping.

| | A: Move the protocol into `mine-sketch` build mode | B: Move it to `references/common/known-issues.md` for any session that defers a real finding | C: Record only challenge findings set to `skipped` |
|---|---|---|---|
| Covers sketch builds | yes: pre-commit reviewer findings and ship-time challenge findings | yes | only challenge findings |
| Covers non-sketch work (direct fixes, PR feedback) | no | yes, but there's no `<feature_dir>` to hold the file | only when a challenge ran |
| Where the file lives | `<feature_dir>/known-issues.md`, next to the ledger | the feature dir if there is one, otherwise undefined | the feature dir |
| Pre-ship walkthrough | Step 4, before the Ship? gate | the caller decides | Step 4 |
| Size | protocol trimmed to sketch's call sites | protocol plus a "where's the file" rule | smallest |

**Recommendation:** A. Sketch is now the only workflow with a feature directory, and the protocol's value comes from being tied to one build's deferrals and walked before that build ships. Its concrete shape:

- Trim the protocol to `skills/mine-sketch/known-issues.md`, keeping the qualifying rules, the Severity Gate, and the entry schema.
- Replace the cfl `Run: <run_id>` field with `Recorded: YYYY-MM-DD (<branch>)`, since build mode doesn't touch cfl. The Step 4 walkthrough tells this build's entries from the backlog by branch.
- During Steps 2 and 3, a real finding the build decides not to fix (from the pre-commit reviewers or the ship-time challenge, including a `skipped` disposition) gets recorded when it qualifies.
- A finding that trips the Severity Gate is put to you with options to fix it now, stop, or ship anyway, and is never silently deferred.
- Step 4 walks each of this build's open entries before the Ship? gate (fix now, file as issue, keep open) and states the count of open backlog entries.
- `mine-ship`'s `known-issues.md` mention (line 37) stays valid.

**Pick B instead if** you also want deferrals tracked during non-sketch work and are willing to settle where the file lives without a feature dir. **Pick C instead if** you only care about deferred challenge findings.
**Reversibility:** easy
**Ratified:** Chose moving a trimmed known-issues protocol into `mine-sketch` build mode over a general reference or challenge-skips-only, to keep a durable record of every qualifying build-time deferral walked before ship, accepting that non-sketch work gets no known-issues tracking.

## Assumed

- The installer discovers skills by directory and removes owned dangling symlinks: automatically on non-interactive runs, and after a "Remove stale symlinks?" confirmation on interactive runs. Deleted skills disappear from `$CLAUDE_CONFIG_DIR` only on machines where `uv run install.py` has run since. Evidence: `install.py` lists no skill names (only agent tuples, line 125). Stale-symlink sweep is `resolve_stale_symlinks` at `install.py:1130-1175`.
- `install.py`'s agent tuples and `rules/common/performance.md`'s agent list are generated from agent frontmatter. Evidence: `bin/lint-agent-models` docstring, lines 11–12.
- `bin/agent-stats` reads cfl gate verdicts and agents' `## Summary` lines, not the orchestrate verdict line, so D5 doesn't break it. Evidence: `bin/agent-stats:11,129-167`.
- The contract tests that pin sketch, challenge and comb behavior stay valid. The exceptions are the anchors D2 and D9 remove, and tests whose subject file is deleted. Evidence: test names in `tests/test_design_doc_contracts.py` (`test_sketch_*`, `test_challenge_*`, `test_comb_gate_*`) and `tests/test_challenge_mandate_contracts.py`.
- `mine-sketch` itself calls `cfl spec`, `cfl run`, `cfl event`, `cfl dispatch` and `cfl gate`, and those stay as they are (#615). Evidence: `skills/mine-sketch/SKILL.md` Phases 1, 3, 5, 6.
- Under D9, a non-archived `design.md` without `**Mode:** sketch` matches no routing row, so sketch treats it as a new request and `cfl spec init` creates a second spec directory beside it. Accepted as rare: 39 of the 40 non-sketch design docs in this repo are `archived`. Evidence: `skills/mine-sketch/SKILL.md` Routing ("Otherwise, treat $ARGUMENTS as a new request").

## Build

- [x] Implementation and tests committed
- [x] Docs (the `uv run install.py` note is deferred to the PR description and CHANGELOG)
- [x] Ship-time challenge

**Calls made during the build:**
- `references/common/staleness-preflight.md` is deleted rather than re-owned by sketch (amends D7, confirmed with the user during the build): its only callers were define, plan and orchestrate, and sketch never called it.
- `researcher.md`'s optional-field rows stay, with "Used by" set to "any caller": nothing dispatches the researcher with those fields today, but they're usable by anyone, and D7 said keep them.
- `mine-ship` Phase 1.5 drops prior-run detection entirely and always runs `/mine-clean-code` on code diffs: the only producer of `clean-code-summary.md` was orchestrate. Its `known-issues.md` exemption went with it, since that exemption only applied to prior-run detection.
- Grill hands sketch its `<feature_dir>`, and sketch adopts a directory holding `brief.md` but no `design.md` as the new ledger's home, skipping `cfl spec init`: grill already ran `cfl spec init`, and a second spec directory would split the brief from its ledger.
- `capabilities-core.md` moves "spec this out" and "design this change" onto the `/mine-sketch` row rather than dropping them, since sketch now owns that intent. The `cfl archive` trigger row is deleted (D8).
- `redesign-from-first-principles.md`'s terminal-status exception adds `built`, matching the sketch template's own Addendum rule.
- `findings-protocol.md` and its test drop the `**Mode:** sketch` condition along with the define fallback (D9): with no fallback, there's nothing to branch on.
- A new `tests/test_retired_pipeline.py` fails if any installed skill, command, agent, rule or reference names a retired component, and pins D3's brief reading, D9's missing legacy row and D10's known-issues wiring.
- The install note goes in the PR description and CHANGELOG entry rather than ONBOARDING, since it's a one-time post-merge step.
- D10's "`mine-ship`'s `known-issues.md` mention stays valid" no longer holds: the mention went with prior-run detection (see the `mine-ship` call above).
- Known-issues mechanics, settled with the user after the ship-time challenge: every qualifying deferral is recorded, but the Severity Gate question fires only for deferrals the user hasn't seen (a skip in the challenge walkthrough already was the user's call). Step 4 walks every open entry, batched up to 4 per question, with no branch filter; `Recorded:` only labels which build an entry came from. `mine-ship`'s clean-code skips stay out of `known-issues.md`: they're stylistic, and `mine-ship` stays generic.
- `bin/agent-stats` is deleted, at the user's direction during the ship-time challenge: with orchestrate gone nothing writes the reviewer gate rows it reported on, and it was no longer used. The Assumed bullet about it held at ratification and is now moot.
- The "Build it" handoffs in `mine-audit`, `mine-brainstorm`, `mine-decompose`, `mine-eval-repo`, `mine-tool-gaps` and `/mine-issues` say only "implement it", with no implement-vs-sketch threshold (settled with the user during the ship-time challenge): the always-loaded `/mine-sketch` trigger row is enough for the agent to offer sketch on its own, and differently worded copies of the threshold would drift.
- Build Step 1 Orient also checks how far the branch trails the default branch (ship-time challenge): the build runs in a fresh session, possibly days after ratification, against `file:line` evidence a stale base can invalidate.
