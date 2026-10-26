# Design: mine-review-pr proves its findings before presenting them

**Date:** 2026-10-26
**Status:** ratified
**Mode:** sketch

## Summary

An audit of all 18 `/mine-review-pr` runs (2026-08-25 to 2026-10-26, Rhyme `analytics` repo, ADO) found the skill reviews quickly but shallowly:

- Phase 4 re-checks that a finding is *in the code* (head SHA, file, description, threads). It never checks that the finding is *true in effect*. Almost no run executed a test, query, consumer lookup, CI-log read or history check before the report.
- Wrong HIGH/CRITICAL findings reached the user or the PR: 50558, 50303, 50534, 50163, 50685.
- Unverified findings were posted as questions to the author ("could you confirm", "was this intentional?") in 50795, 50886, 50955, 50189, 50253 and 50629, or were silently dropped (50795).
- What the PR itself claims to fix was never tested. 50839's description misdiagnosed the incident; 50629 and 50795 got no equivalence check.
- The user approved drafts they never saw. Titles or paths were shown instead of bodies in nearly every run.
- Comments put the evidence before the ask.
- Nothing checked whether an issue was introduced by the PR or already on the target branch.
- The ADO head-SHA check reads a field `ado-api` doesn't return.

Per-run evidence: the audit files under the session scratchpad (`review-pr-audit-AtTOAs/{A,B,C,D}/pr-*.md`). They are not needed to build; the decisions below carry what matters.

The change rewrites `skills/mine-review-pr/SKILL.md` and `skills/mine-review-pr/REFERENCE.md`. Where each new piece lives:

- **Context gathering** (PR description, linked work items, CI/build status, author run links, existing threads): a new step in SKILL.md Phase 0, gathered in one batch with no per-item prompts. Its output goes to every reviewer as context, never the session's own hypotheses.
- **Claims pass** (what the PR says it fixes or preserves, and the riskiest merge decision): owner per D2. The riskiest-merge-decision line is omitted when there is none.
- **Prove-or-drop investigation** (replaces today's Phase 4 "verify"): the main session, inline (D1), as a rewritten SKILL.md Phase 4 whose shape is D8. Reviewers name a check per finding in the dispatch prompt (SKILL.md Phase 2).
- **Investigation scope (D4), introduced-vs-target routing (D6), the open-questions entry rule (D3) and the live-system rule (D7):** the rewritten Phase 4 text.
- **Low/nit folding (D4):** SKILL.md Phase 3 categorization.
- **Open questions (D3) and tracker candidates (D6) as report sections:** Phase 5, per D9.
- **Comment template:** REFERENCE.md, per D5. REFERENCE.md's worked example, "Why Phase 4 is mandatory" and "Re-reviewing After New Commits" (which cites "Phase 4 step 4") are rewritten to match.
- **Report → draft → post flow:** SKILL.md Phases 5–7, shaped per D9. Full draft bodies are shown inline once before the post gate; this is a hard rule, from the audit's "approved unseen" pattern.
- **Mechanical fixes** (SKILL.md):
  - ADO head SHA from a fresh `git ls-remote origin '<source>'`, compared with the HEAD pinned in Phase 1. GitHub keeps `gh pr view --json headRefOid`, which works (including fork PRs, where `ls-remote origin` can't see the branch). Never compare against a local ref (`origin/<branch>`, `git rev-parse`), which compares the Phase 1 fetch to itself. The check stays at the start of Phase 4. If it fails, report "head check: no answer" and continue against the pinned HEAD.
  - Strip the `ado-api pr threads` header line before parsing.
  - Delete today's merge-commit handling in Phase 0 step 4 (the `mergeCommit`/`lastMergeCommit` first-parent base). The user's repos all squash-merge, and the three-dot diff from Phase 1 is correct for squash-merged PRs. A merged PR whose source branch can't be fetched is reported and the skill stops.
  - One command per Bash call.
  - No sleep/ScheduleWakeup polling for reviewers.
  - A failed or errored command is "no answer", never evidence of absence or a passed check.
- **Docs:** update the skill's row in repo-root `REFERENCE.md`. The `capabilities-core.md` trigger phrases are unchanged.

Out of scope:
- New features beyond the audit (e.g. carrying the user's past review direction across PRs).
- The trigger phrases.
- Edits to other repos' rules (D7).
- Fixing `ado-api` itself. The skill works around its gaps (no source or merge commit in `pr show --json`, a header line before `pr threads --json`), and ClickUp Sand task 86bcrn71j tracks adding them to the tool so the workarounds can be removed later.

## Posture

- **Failure handling:** loud. A check that errors or can't run is reported as "no answer" for that finding, never as a pass or as "nothing found". No retries beyond fixing an obvious command mistake.
- **Compatibility:** break freely. Personal skill (`audience: personal`); phases may be renamed, merged, or removed with no shims.
- **Scope:** the audit's patterns only: proof before presenting, claims check, unresolved-finding handling, draft display, comment template, introduced-vs-target, mechanical fixes.
- **Rollout:** ships outright; the next `/mine-review-pr` run uses it.
- **Hardening:** project defaults.
- **Cost:** no extra agents beyond today's reviewer trio (D1).
- **Altitude:** `build`; one session edits the two skill files.

## Decisions

### D1: Who runs the prove-or-drop investigation?

**Deciding factor:** findings get executed evidence regardless of which model the session runs on.

| | A: Main session, inline | B: One `deep-worker` (Opus) per finding group, in parallel | C: One `deep-worker` for all findings |
|---|---|---|---|
| Depth on a Sonnet session | Audit: 17 of 18 runs were Sonnet and only re-read files. 9175bc8b shows Sonnet *can* run tests when prompted, so stronger instructions help, but nothing guarantees it | Opus regardless of session model; fresh context per finding | Opus, but one context serially working 3–8 findings; later ones get less attention |
| Wall time | Serial; each finding's queries add up | Parallel; bounded by the slowest finding | Serial inside one agent |
| Cost | No extra agents | ~3–8 Opus agents per review (bounded by D4's threshold) | 1 Opus agent |
| Main-session context | Fills with query output | Stays lean; reads one result file per worker | Stays lean |
| Cross-finding links (two findings with one root cause) | Natural | Main session groups related findings into one worker before dispatch | Natural |
| Tool access (Bash, repo CLIs like `dbx-api`) | Yes | Yes (`agents/deep-worker.md` grants Bash) | Yes |

**Recommendation:** B. It's the only option where depth doesn't depend on the session model. Today's Phase 4 never asks for execution, so the audit shows the skill didn't ask, not that sessions ignore the request. Grouping related findings keeps cost to a handful of agents.
**Pick A instead if** you'd rather pay nothing extra and will run the skill on Opus anyway. **Pick C instead if** cost matters more than wall time and per-finding attention.
**Reversibility:** easy (one phase's dispatch shape)
**Ratified:** Chose A (main session, inline) over per-group deep-workers, to avoid extra agent cost and keep evidence in the session that presents it, accepting that depth relies on the skill's instructions and on running the skill on Opus.

### D2: Who owns the claims pass?

**Deciding factor:** someone tests the PR's own story (root cause, "logic preserved", "fixes X"), not only the diff's lines.

| | A: Main session, extending the overview it already writes while reviewers run | B: Fourth dispatched agent (deep-worker) | C: Replace `wtf-reviewer` with a claims agent |
|---|---|---|---|
| Has the inputs | Already reads the full diff, description and commits for the overview (SKILL.md Phase 2) | Needs them passed in | Needs them passed in |
| Proves the claims | Identifies them; each checkable claim becomes a finding that goes through D1's investigation | Identifies and checks them in one agent | Same as B |
| Extra cost | None | One more Opus agent | None net |
| Loses anything | Nothing | Nothing | The readability pass. In the audit its output was mostly nits the skill folds or drops (50237 #7/#8, 50509, 50534), but it also caught 50163's naming drift |
| Takes a position on the riskiest merge decision | Yes; it's in the overview, which the user reads first | Buried in an agent's report | Same as B |

**Recommendation:** A. The overview already has every input. Routing checkable claims into D1 reuses the proof machinery instead of building a second one. The "riskiest merge decision and what I recommend" line belongs where the user reads first.

Under A, checkable claims join the findings list at Phase 3 consolidation, so a head-moved re-run of Phases 2–3 regenerates them. A claim the investigation disproves becomes a Code-issue finding, drafted like any other (subject to D9's shaping gate). A claim it confirms is only noted in the overview.
**Pick B instead if** you want at least one Opus pass guaranteed now that D1 runs inline. **Pick C instead if** you've found the readability pass adds nothing on others' PRs.
**Reversibility:** easy
**Ratified:** Chose A (main session extends the overview) over a fourth agent or replacing wtf-reviewer, to test the PR's own claims (a disproved claim becomes a drafted Code-issue finding) and state the riskiest merge decision where the user reads first, accepting that claim-checking depth rides on the same inline investigation as D1.

### D3: What happens to a finding the investigation can't settle?

**Deciding factor:** nothing reaches the PR author that the reviewer could have checked itself, and nothing real disappears silently.

| | A: "Open questions for you" section; drafted only if the user asks at D9's shaping gate | B: Drop it | C: Post as a question to the author (today's de facto behavior) |
|---|---|---|---|
| Author sees unverified claims | No | No | Yes; the audit's main complaint (50795 HIGH posted with "please confirm") |
| Real issues lost | No; the user sees it and can ask, dig, or post | Yes (50795's dropped Month/Week regression) | No |
| User load | One short section, each item with what was tried and what would settle it | None | None, until the author replies |
| Fits "you post what you'd stand behind" | Yes | Yes | No |

**Recommendation:** A. Each open question states what was tried, why it didn't settle (including "the command errored"), and the one check that would. The user can then post it, dig, or drop it. An item enters this section only if its settling check can't be run by the session (needs author intent, or access the session lacks) or the check errored. A runnable check that wasn't run is unfinished work, not an open question.
**Pick B instead if** you'd rather never see unconfirmed items. **Pick C instead if** the author is the only one who can answer (rare: intent questions). A question that only the author can answer still goes through you first under A.
**Reversibility:** easy
**Ratified:** Chose A (open questions for the user, entered only when the check can't be run or errored, drafted only on request at D9's shaping gate) over dropping or asking the author, to keep unverified claims off the PR by default without losing real issues, accepting one extra report section for the user to triage.

### D4: Which findings get the full investigation?

**Deciding factor:** spend proof effort where a wrong finding hurts.

**Recommendation:** every finding at Medium or above and every checkable PR claim from D2. Low findings and nits get only today's code re-read, and they fold into an adjacent thread or are dropped. Only Medium+ findings and the tests/docs bucket threads get their own thread. This extends today's fold-or-drop rule (SKILL.md Phase 3, nits only) to Low. Instruction-mode reviewers that report blocking/minor map blocking to High and minor to Low.
**Pick "everything" instead if** you want even folded Lows proven (adds inline run time). **Pick "High+ only" instead if** cost bites; but non-High findings were wrong too (50534 #6).
**Reversibility:** easy
**Ratified:** Chose Medium+ plus checkable claims over everything or High+ only, with Low findings and nits folded or dropped rather than given their own thread, to spend proof effort where a wrong post hurts, accepting that folded Lows ship on a code re-read alone.

### D5: Comment template shape

**Deciding factor:** the author can act on the comment from its first two lines.

| | A: Blocking label + ask first, then why/evidence | B: Ask first, then why/evidence, no label | C: Today's (finding + evidence, fix last) |
|---|---|---|---|
| Matches stated preference | Yes. "What should change first, then why", shorter, one ask (50163). "Needs to be addressed before approval" vs nice-to-have framing, and severity on threads (48733, 48914) | Partly; no blocking signal | No; the user rewrote every draft in 50163 |
| Author knows what blocks approval | Yes | Must infer | Must infer |
| Length | ≤ ~6 lines plus footer; bullets only for 3+ sub-points | Same | 1–4 + 1–2 sentences, often longer in practice |

Template A: `**[Blocking|Non-blocking] <title>**`, then 1–2 sentences on exactly what to change (one ask, no "or alternatively" options), then 1–3 sentences of why with file:line and the evidence actually run, then the existing footer. Pre-existing issues the PR touches use "Non-blocking — worth fixing while you're in here" (the 50303 wording).

Label default: Critical/High findings and any disproved PR claim (D2) are Blocking. Medium and below, and the tests/docs bucket threads, are Non-blocking. The user can flip any label at D9's shaping gate.

**Recommendation:** A.
**Pick B instead if** severity labels feel heavy-handed on teammates' PRs. **Pick C instead if** never.
**Reversibility:** easy
**Ratified:** Chose A (blocking label defaulting from severity, ask first, then why/evidence) over no label or today's order, so the author can act from the first two lines and knows what blocks approval, accepting a label that may read as firm on teammates' PRs.

### D6: How are issues that predate the PR handled?

**Deciding factor:** the PR author is asked only about what their PR changed or made worse.

| | A: Check the target branch; touched → non-blocking thread, untouched or repo-wide → tracker candidate for you | B: Drop pre-existing | C: Post everything |
|---|---|---|---|
| How it's determined | `git show <base>:<path>` / grep at `<base>`, where `<base>` is `git merge-base origin/<target> HEAD`, the commit the PR branched from. This is right for open and squash-merged PRs alike; the tip of `origin/<target>` already holds a squash-merged PR's changes (read-only, per `pre-existing-verification.md`) | Same check | No check |
| Matches audit | Yes. 50163 "was this actually changed in this PR?"; 50955 "mentioned on my PRs too → ClickUp"; 50795, where a dropped "pre-existing" finding was one the PR made worse | Loses 50795-type findings | Reproduces 50163 |
| Outward-facing actions | Filing stays the user's call (offered, not done) | None | None |

Rule under A:
- Present on the target branch, and the PR neither touches nor worsens it: listed to the user as a tracker candidate, not drafted.
- The PR touches it: may be drafted as Non-blocking "while you're in here".
- The PR copies or extends it: treated as introduced.

**Recommendation:** A.
**Pick B instead if** you never want pre-existing items surfaced. **Pick C instead if** never.
**Reversibility:** easy
**Ratified:** Chose A (check at the merge-base and route by what the PR did) over dropping or posting all pre-existing items, so authors are asked only about what their PR changed or worsened, accepting one read-only merge-base check per Medium+ finding.

### D7: Where do repo-specific evidence sources live?

**Deciding factor:** the generic skill knows *what kind* of evidence to get; the repo says *how*.

The skill tells the session to read the repo's `CLAUDE.md` and rules for how to query built output, look up consumers and read CI. It also states the generic rule: a claim about consumers, schedules or test coverage is checked against the live system, never a repo doc. That rule is what 50558, 50534 and 50303 broke.

Checked against `analytics/.claude/rules/`, the only fact missing is where a PR build's output lands (`sandbox.vsts__reporting.pr<id>_pullrequest__<model>`). The other candidates are already covered or weren't real gaps:
- `lineage-api` correctly omits soft-deleted nodes.
- The stale "data_tests don't run" text is gone.
- Run links are in `databricks-deployment.md`.

| | A: Generic pointer; PR-table line as a follow-up | B: Generic pointer; make the line now | C: Generic pointer; skip the line |
|---|---|---|---|
| Skill stays generic | Yes | Yes | Yes |
| Scope | This repo; one follow-up edit elsewhere | Adds a PR in the analytics repo | This repo only |
| PR output discoverable | After the follow-up | Immediately | Via `information_schema`, as 51063 found it |

**Recommendation:** A.
**Pick B instead if** you want the first review after this ships to find PR tables without searching. **Pick C instead if** searching `information_schema` is cheap enough.
**Reversibility:** easy
**Ratified:** Chose C (generic pointer, no analytics edit) over a follow-up or same-change edit, to keep the change to this repo with no follow-up, accepting that sessions locate PR build tables by searching `information_schema`.

### D8: What does the Phase 4 investigation consist of?

**Deciding factor:** findings get real checks, with as little skill text as possible. A short prompt that asks the model to dig in and follow up on unknowns works well on Opus; more machinery doesn't add depth.

| | A: Minimal — reviewers name a check; short dig-in instruction; Evidence line; D3's entry rule | B: Full mechanism — A plus a per-finding check cap, a queue/progress message, and verdict files persisted to the tmpdir |
|---|---|---|
| Gets executed evidence | Yes, by asking for it directly (today's Phase 4 never does) | Yes |
| Overclaims visible | Yes: "verified/confirmed/proven" only when the Evidence line names something run | Yes |
| Skill text added | A paragraph plus one dispatch sentence | Several rules plus a message format and file layout |
| Long runs | User can interrupt | Bounded and visible |
| Survives a crash mid-phase | No | Yes |

Under A:
- The reviewer dispatch asks each reviewer to name, per finding, the command that would confirm or refute it.
- Phase 4 tells the session, for every finding in D4's scope, to run the check that proves or disproves it (tests, queries, consumers, CI logs, history, the target branch per D6), to follow up on unknowns until it can state the impact and one concrete fix, and to read the repo's CLAUDE.md and rules for how to query its systems (D7).
- Each reported finding carries an `Evidence:` line naming what was run.
- Execution scope: read-only commands, scratch files on disk, and PR tests that write nothing outside the review worktree and the skill's tmpdir (unit tests; not `dbt run`/`build` or integration tests that hit real services). The test for each check is "does this write to anything outside the worktree and the tmpdir?" PR test code runs with the session's credentials; for teammates' PRs that is accepted. The session never runs DML or any other database or external-service write; a check that needs one becomes an open question (D3) with the command written out for the user to run. A denied command is reported as "blocked by permissions", distinct from "errored".
- SKILL.md notes the skill works best on Opus.

**Recommendation:** A.
**Pick B instead if** runs on large PRs turn out to drag or die mid-phase often enough to need bounds and persistence.
**Reversibility:** easy
**Ratified:** Chose A (minimal: reviewers name a check, a short dig-in instruction, an Evidence line, D3's entry rule, an execution scope of read-only commands plus local tests, with no database or external writes) over caps, progress messages and persisted verdicts, to keep the skill small while getting executed evidence, accepting unbounded run time on large PRs and no recovery from a mid-phase crash.

### D9: What does the user see between the investigation and posting?

**Deciding factor:** the user reads each thing once and has one place to shape the set; any added prompt replaces the "draft them?" question sessions already improvise.

| | A: Compact report → one shaping gate → full drafts once → post gate | B: Today's flow (full report → automatic drafts → post gate) plus full bodies |
|---|---|---|
| Full text read once | Yes | No; findings are shown in the report and again as drafts |
| Shaping before drafts exist | Yes, at the shaping gate | No; changes cost a redraft |
| Prompts on the approve path | 2 (draft, post). The first replaces the "draft them?" question sessions already improvise | 1 |
| Open questions and tracker candidates get a disposition | Yes, as free text at the shaping gate ("dig into #2", "post #3 as a question") | Undefined |
| Wrong label or routing caught | Yes; both are on each finding's line | Only if the user reads drafts closely |

Under A:
- **Report:** the overview, then one line per finding with severity, bucket, label (D5), gist, the Evidence line (D8) and the routing outcome with its one-line reason (D6). Then open questions (D3) and tracker candidates (D6).
- **Shaping gate:** "Draft these" / "Change the set first" / "Stop". Changes, digs and question posts are given as free text.
- **Drafts:** every full body inline once, then today's post gate.
- **Clean path unchanged:** when no findings, open questions or tracker candidates survive, show the overview and stop with no prompt (today's SKILL.md Phase 5 behavior). When only open questions or tracker candidates exist, show the report and stop; the user replies in free text if they want anything done.

**Recommendation:** A.
**Pick B instead if** you rarely change the set before seeing drafts.
**Reversibility:** easy
**Ratified:** Chose A (compact report, one shaping gate, full drafts once) over today's flow with full bodies added, so each thing is read once and shaping happens before drafting, accepting a second prompt on the approve path in place of the improvised one.

## Assumed

- `ado-api pr show <id> --json` has no `lastMergeSourceCommit`; every ADO run fell back to `git ls-remote` or failed. Evidence: 51047 (SA3B empty grep), 51063 (AkJQ rc=1), audit C and D notes for 50629–50955.
- `ado-api pr threads <id> --json` prints a `PR #<id> — N thread(s)` line before the JSON array. Evidence: 51063 tool result vpsZ.
- Reviewer subagents run in parallel and notify on completion; the session must not poll. Evidence: SKILL.md Phase 2 "Do not poll"; audit B 50509/50534 ScheduleWakeup misfire.
- In Rhyme worktree sessions the Grep tool is unavailable and the worktree guard refuses compound Bash commands (for-loops, `cd &&`, multiple substitutions). Evidence: 51047/51063 Grep errors; audit A–D guard refusals; `rules/common/worktrees.md` item 4.
- The PR-description check, existing-thread dedup (including resolved threads, which also backs REFERENCE.md "Re-reviewing After New Commits"), the never-post-without-confirmation gate, and the stop-early path when nothing survives (overview, "no findings survived", no prompt) worked in every run and must survive the rewrite. Evidence: audit A–D "What worked".
- The skill's repo-root `REFERENCE.md` row describes the phases; trigger phrases live in `rules/common/capabilities-core.md:40`. Evidence: those lines.

## Build

- [x] Implementation and tests committed (instruction-only change; no test suite covers this skill. `lint-agent-files` and the skill census tests pass)
- [x] Docs (repo-root `REFERENCE.md` row updated; trigger phrases unchanged)
- [ ] Ship-time challenge

**Calls made during the build:**
- ADO CI status comes from `ado-api builds list --branch 'refs/pull/<id>/merge'`: ADO PR validation builds run on that ref, and `ado-api` has no per-PR build command.
- The PR claims enter Phase 3 as entries to investigate rather than findings, so a confirmed claim never gets a severity or thread; only a disproved one becomes a Code-issue finding (D2).
- Phase 4 runs the cheap filters (thread dedup, description check, then the D6 target-branch check) before the investigation, so no effort is spent proving a finding that would be dropped as a duplicate or routed to tracker candidates. A tracker candidate's proof is showing it exists at `<base>`.
- A finding with no executable check (naming, design, instruction prose) carries `Evidence: judgment: <reasoning>` and is never called verified. D8 assumed every finding has a runnable check; without this route a session would invent a token check or push judgment calls into open questions, which D3's entry rule forbids. Its label still follows D5's severity default.
- A disproved PR claim enters as High, matching D5's Blocking default for it.
- The report adds a "Dropped" list (gist + refuting command), so a wrong drop can be caught. This serves D3's "nothing real disappears silently".
- The Phase 2 riskiest-merge-decision line is re-derived in Phase 5 from what Phase 4 proved, since it is written before any check runs.
- REFERENCE.md gains a `[Question]` form for an open question the user chooses to post (D3/D9 allow it; the D5 template had no question shape).
- Thread dedup and the description check apply to every finding, Low included; only the executed investigation is limited to Medium+ and claims (D4).
- The rule set that holds across phases (one command per call, failed command is "no answer", denied is "blocked by permissions", no polling) is a short "Running commands" section before Phase 0 instead of being repeated per phase.
- `git grep` at `<base>` is the named search for D6, since the Grep tool is unavailable in Rhyme worktree sessions.
