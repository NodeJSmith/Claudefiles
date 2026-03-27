# Design: Redesign mine.address-pr-issues

**Date:** 2026-03-27
**Status:** approved
**Research:** /tmp/claude-mine-challenge-sy7NbQ/ (findings.md, research.md, platform-research.md)

## Problem

The `mine.address-pr-issues` skill promises "make this PR mergeable" but fails at it in practice. Four user-reported pain points, confirmed by adversarial challenge (3 critics, 11 findings) and industry research (20+ sources):

1. **Uninformed gate** — Phase 3 asks "what do you want to do?" before the user has seen details. The user always picks "address all." The decision point adds friction without value.
2. **No research before fixing** — jumps straight to editing code without reading context, call sites, or understanding why the code is the way it is. Produces shallow fixes that miss root causes.
3. **Commits before testing** — pushes "fixes" without running tests locally. Half the time discovers the fix was wrong, creating a fix-commit-push-broken loop.
4. **Explains away failures** — rationalizes test/CI failures instead of fixing them. Common LLM behavior that needs explicit guardrails.

Additionally, the challenge found structural issues: inline GraphQL duplication (3/3 critic consensus), auto-resolving human reviewer threads against industry norms, no idempotency for re-runs, and hardcoded platform-specific commands throughout.

## Non-Goals

- **Not adding GitLab/Bitbucket support** — platform-agnostic architecture enables it later, but this redesign targets GitHub + ADO only.
- **Not building a platform plugin system** — thin dispatch via helpers, not an abstraction layer.
- **Not splitting into sub-skills** — the all-in-one triage is a differentiator (research confirmed no other tool covers review comments + CI + conflicts together).
- **Not changing helper script interfaces for existing callers** — all helper changes are additive (`--json` flags, new scripts).

## Architecture

### Phase restructuring

The current 6-phase flow has structural problems: triage is separated from planning, planning requires uninformed user consent, execution lacks verification, and thread resolution happens before code is pushed. The redesigned flow:

```
Phase 1: Fetch & Detect
  → git-platform detects GitHub/ADO
  → Fetch PR metadata (including isDraft, reviewDecision)
  → Fetch review threads (via helpers with --json)
  → Fetch CI status
  → Fetch general PR comments

Phase 2: Triage & Plan (merged — no uninformed gate)
  → Categorize all issues
  → For each issue, investigate context and propose a specific fix
  → Present the full plan with proposed actions
  → User opts OUT of specific items (inverted default)

Phase 3: Execute (serial subagents, test-before-push)
  → For each logical group of fixes:
    → Launch general-purpose subagent (writes results to temp file)
    → Subagent investigates (depth: light/medium/deep per Phase 2)
    → Subagent applies fix
    → Subagent runs tests locally
    → If tests fail: fix or escalate (never explain away)
  → After all subagents complete:
    → Run code-reviewer + integration-reviewer
    → Commit per logical group (descriptive messages, enables bisect/revert)
    → Push once
  → After push confirmed:
    → Reply to threads (with idempotency check)
    → Resolve bot threads only (default) or all threads (if user opted in)

Phase 4: Summary
  → Report what was done, what was skipped, what needs manual review
```

### Key design decisions

#### D1: Inverted opt-out flow (addresses pain point #1)

Current: Show summary → ask "what to do?" → show details → execute.
New: Show full plan with proposed fixes → ask "skip any?" → execute.

The `AskUserQuestion` in Phase 2 becomes:

```yaml
AskUserQuestion:
  question: "Here's my plan for PR #N. Review and skip any items you don't want me to address."
  header: "PR Plan"
  multiSelect: true
  options:
    - label: "Looks good — address all"
      description: "Proceed with the full plan as shown"
    - label: "Skip specific items"
      description: "I'll tell you which items to skip"
    - label: "Cancel"
      description: "Exit without making changes"
```

If "Skip specific items": follow-up asking which numbered items to skip.

#### D2: Investigate-then-fix subagents (addresses pain points #2 and #3)

Each subagent receives:
- The review comment(s) to address
- The file path(s) and line numbers
- Explicit instructions to investigate before fixing

Subagent investigation mandate (depth-dependent — Phase 2 triage assigns depth per issue):

**Light** (rename, docstring, formatting — skip call-site investigation):
1. Read the target file
2. Apply the fix
3. Run the project's test suite
4. If tests fail: fix or escalate. Max 3 retries.

**Medium** (logic change — default depth):
1. Read the target file fully
2. Grep for call sites of the function/class being modified
3. Read at least one call site to understand usage
4. Apply the fix
5. Run the project's test suite (using the test execution discovery order from `rules/common/testing.md`)
6. If tests fail: fix the code, don't rationalize. Max 3 retries, then escalate to user.

**Deep** (architectural concern — read call sites, tests, related modules):
1. Read the target file fully
2. Grep for call sites — read ALL callers (not just one)
3. Read related test files to understand expected behavior
4. Read adjacent modules in the same package/directory
5. Apply the fix
6. Run the project's test suite
7. If tests fail: fix or escalate. Max 3 retries.

Phase 2 assigns depth based on the review comment's nature: trivial changes get `light`, standard logic changes get `medium`, comments that question design patterns, error handling strategies, or architectural choices get `deep`.

Subagents are launched **serially** (not parallel), grouped logically — e.g., all comments about error handling together, all comments about a single feature together. The main agent determines grouping during Phase 2.

**Subagent output management**: Each subagent writes its results to a temp file at `<tmpdir>/group-N/result.md` (using `get-skill-tmpdir mine-address-pr`). The main agent reads only a one-line summary from each result file, not the full output. This prevents context exhaustion on PRs with many comment groups (follows the mine.orchestrate pattern).

After all subagents finish, the main agent:
1. Runs `code-reviewer` agent on all modified files
2. Runs `integration-reviewer` agent on the full diff
3. Commits **per logical group** with descriptive messages (e.g., `fix(auth): use logging instead of print per review`, `fix(config): add LOGIN_REDIRECT_URL to test settings`). This enables `git bisect` and selective `git revert` if one fix turns out to be wrong. The test-before-push mandate prevents the broken-commit loop — per-group commits add granularity without risk.
4. Pushes once (single push after all commits)

#### D3: Thread resolution policy (addresses challenge finding #3)

Research confirmed: no major tool resolves human reviewer threads automatically. Default behavior:

| Thread author | Action |
|---|---|
| Bot (Copilot, dependabot, CodeRabbit, etc.) | Reply + resolve |
| Human reviewer | Reply only — reviewer resolves after verifying |
| PR author (self-review) | Reply + resolve |

Bot detection (platform-specific):
- **GitHub**: Use the `__typename` field from the GraphQL `author` fragment. If `__typename == "Bot"`, treat as bot. Fall back to `[bot]` suffix check for edge cases where `__typename` is unavailable. No hardcoded name list.
- **ADO**: The thread comment `author` object does not include bot-detection fields (`isContainer`/`isAadIdentity` are on the Identity API, not the PR thread API). Fall back to `[bot]` suffix check on `author.uniqueName`. For ADO-specific service accounts, the LLM should check if `author.uniqueName` matches known service patterns (e.g., no `@` domain, or matches the project's build service identity). This is less reliable than GitHub's `__typename` but is the best available signal without additional API calls.

The Phase 2 plan presentation shows the resolution policy for each thread so the user knows what will happen. If the user wants to override (auto-resolve all), they can say so.

Thread resolution happens **after push**, not before. This ensures the reviewer can see the fix in the PR diff when they read the reply.

#### D4: Anti-rationalization guardrail (addresses pain point #4)

Explicit instruction in subagent prompts:

> **CRITICAL**: Never explain away a test failure or CI error. If tests fail after your fix, the fix is wrong — revise it. Do not suggest the test is outdated, flaky, or testing the wrong thing. Do not suggest skipping or marking the test as expected failure. Fix the code until tests pass, or escalate to the user after 3 attempts.

This won't eliminate the behavior entirely but makes it a clear rule violation rather than a judgment call.

#### D5: Platform-agnostic via thin dispatch (addresses challenge findings #1, #7, #8)

Three helper changes:

**New: `bin/git-platform`** (~15 lines)
- Reads `git remote get-url origin`
- Prints `github`, `ado`, or `unknown` to stdout — always exits 0 (non-zero exit codes confuse LLM error handling)
- Consuming skills check for `unknown` and stop with a user-facing message
- Used by `address-pr-issues`, `create-pr`, `ship`

**Extended: `bin/gh-pr-threads --json`** (~20 lines added)
- New `--json` flag emits raw GraphQL response as JSON
- Includes `isResolved`, `isOutdated`, `path`, `line`, `startLine`, `diffSide`, `comments` with `databaseId`, `body`, `author.login`
- Handles pagination internally (cursor-based) — returns ALL threads in a single JSON array, even for PRs with >100 threads. The SKILL.md makes one call, gets all data. No pagination logic in the skill.
- Existing human-readable output unchanged (no `--json` = current behavior)

**Extended: `bin/gh-pr-threads --all`** (small addition)
- Currently filters to unresolved only. Add `--all` flag to include resolved threads (needed for idempotency — checking if a thread was already replied to)

The SKILL.md uses thin dispatch blocks:

```
platform = git-platform
if github:
  threads = gh-pr-threads {PR} --json
  metadata = gh pr view --json ...
elif ado:
  threads = ado-pr-threads list --json
  metadata = ado-pr show --json
```

CI log fetching stays platform-specific (4-6 lines per platform) — the GitHub/ADO CI models are too different to normalize without a leaky abstraction.

**ADO-specific notes for the SKILL.md:**
- `ado-pr show --json` returns `status` (not `mergeStatus`). `mergeStatus` is optional and only present after a merge attempt. URL must be constructed: `repository.webUrl + "/pullrequest/" + pullRequestId`.
- `ado-pr-threads list --json` already has `--json` and `--all` flags and returns all threads in a single call (no pagination needed).
- ADO threads have no `isOutdated` concept — the outdated thread triage logic (D8) applies only to GitHub. For ADO, all active threads are treated as current.
- ADO thread `author` has `displayName`, `uniqueName`, and `id` — no `__typename` equivalent (see D3 bot detection notes).

#### D6: Idempotency for re-runs (addresses research finding)

Before posting a reply:
1. Include a hidden HTML marker in every reply: `<!-- addressed-pr-issues -->` (invisible in rendered markdown)
2. Check the thread's comment history (already fetched in Phase 1) for ANY comment by the current user/bot that contains this marker — not just the last comment (intervening replies from other users would defeat a last-comment-only check)
3. If marker found: skip the reply and log "Already replied to thread at {path}:{line} — skipping"
4. If marker not found but thread is resolved and has our reply (partial-failure recovery from D10): retry the resolve only

For thread resolution: `resolveReviewThread` is already idempotent (calling it on a resolved thread is a no-op).

Rate limiting: add 1-second delay between mutative API calls (reply + resolve). For typical PRs (<20 threads), this adds <20s total.

#### D7: Pre-flight status enrichment (addresses challenge finding #10)

Phase 1 fetches additional metadata:
- `isDraft` — warn "This is a draft PR. Changes can be made but it won't be mergeable until marked Ready for Review."
- `reviewDecision` — warn if `CHANGES_REQUESTED`: "Reviewer @X requested changes. Even after fixing all comments, they'll need to re-approve."
- Required approvals count vs current approvals

These are informational warnings in the Phase 2 plan, not blockers.

#### D8: Outdated thread triage with cite-or-escalate (addresses challenge finding #11)

For threads where `isOutdated: true`:
1. Read the comment body to understand the concern
2. Read the current code at that location
3. If the code at the location was **entirely deleted**: auto-categorize as "location removed — likely addressed by refactoring"
4. If the concern is addressed: categorize as "already addressed" **only if you can cite the specific line that addresses it**
5. Otherwise: categorize as "needs manual review"

The cite-or-escalate rule prevents the LLM from confidently dismissing valid concerns.

#### D9: Merge conflict strategy (addresses challenge finding #5)

Instead of hardcoding `git merge`, ask:

```yaml
AskUserQuestion:
  question: "Merge conflicts detected. How should I resolve them?"
  header: "Conflicts"
  options:
    - label: "Merge (Recommended)"
      description: "git merge origin/<base> — creates a merge commit, preserves history"
    - label: "Rebase"
      description: "git rebase origin/<base> — rewrites history, requires force-push"
```

Default recommendation is merge (safer, doesn't rewrite history). Only ask this if conflicts actually exist.

#### D10: Reply+resolve colocation (addresses challenge finding #4)

For GitHub: use `gh-pr-reply {PR} {comment-id} "body" --resolve {thread-id}` (single combined call) instead of separate reply + resolve calls. Note: this is colocation, not true atomicity — `gh-pr-reply` makes two sequential API calls (REST reply + GraphQL resolve). If the resolve fails after the reply posts, the thread will have our reply but remain unresolved. The idempotency check in D6 should detect this state (thread has our reply marker but is still unresolved) and retry the resolve on re-run.

For ADO: keep two calls (`ado-pr-threads reply` + `ado-pr-threads resolve`) since the ADO helper doesn't support combined operations.

### SKILL.md structure (post-redesign)

The redesigned SKILL.md will be structured as:

```
Frontmatter (name, description, user-invocable)
When to Activate (trigger phrases)
Usage (arguments)

Phase 1: Fetch & Detect
  - Platform detection via git-platform
  - PR metadata fetch (thin dispatch)
  - Thread fetch via helpers (--json)
  - CI status fetch (thin dispatch)
  - Pre-flight warnings (draft, CHANGES_REQUESTED)

Phase 2: Triage & Plan
  - Categorize issues (review comments, CI, conflicts)
  - Outdated thread assessment (cite-or-escalate)
  - General comment assessment
  - Already-addressed detection
  - Present full plan with proposed actions
  - Opt-out AskUserQuestion (inverted from current opt-in)
  - If conflicts: ask merge strategy

Phase 3: Execute
  - For each logical group:
    - Launch serial general-purpose subagent (writes to temp file)
    - Subagent: investigate (light/medium/deep) → fix → test → verify
    - Anti-rationalization guardrail in subagent prompt
  - After all subagents:
    - Code-reviewer + integration-reviewer
    - Commit per logical group + single push
  - After push confirmed:
    - Reply to threads (idempotency check)
    - Resolve per policy (bots: resolve, humans: reply-only)
    - 1s delay between API calls

Phase 4: Summary
  - Threads resolved/replied
  - Code changes committed
  - CI status (pending re-run)
  - Items skipped or needing manual review

Helper Scripts reference
  - GitHub: gh-pr-threads, gh-pr-reply (--resolve), git-platform
  - ADO: ado-pr, ado-pr-threads, git-platform
  - Docs: mine.gh-tools skill
```

Estimated length: ~250-300 lines (down from 377), with platform-specific content moved to helpers.

## Alternatives Considered

### Split into separate skills (review, CI, conflicts)

Rejected. The all-in-one triage is a differentiator — research confirmed no other tool covers all three together. The `AskUserQuestion` opt-out flow handles scope selection without requiring separate skill invocations.

### Thick platform abstraction (unified `pr-*` commands)

Rejected. Would require new `pr-threads`, `pr-reply`, `pr-resolve`, `pr-view`, `pr-checks` scripts that internally dispatch to `gh` or `az`. This is a plugin system by another name — adds maintenance burden without proportional benefit. The thin dispatch approach (small if/else blocks in the SKILL.md) is pragmatic and keeps helpers independently useful.

### Parallel subagents for fixes

Rejected per user preference. Serial execution avoids file conflicts and keeps the flow predictable. The time cost is acceptable — most PRs have <10 review comments, and each subagent runs in seconds.

### Keep Explore subagents for analysis, main agent for edits

Rejected. The current Phase 4 (Explore) → Phase 5 (main agent applies) flow wastes context by re-reading everything the subagent already read. General-purpose subagents that investigate AND fix eliminate this duplication.

## Test Strategy

N/A — no test infrastructure in this repo. The skill is a prompt file (`SKILL.md`) and helper scripts (`bin/`). Validation is via:
- Manual testing on a real PR with unresolved threads, CI failures, and merge conflicts
- Routing eval coverage in `evals/compliance/routing/intent-to-skill.yaml` (already exists)
- Code review of helper script changes (`git-platform`, `gh-pr-threads --json`)

## Open Questions

- Should `git-platform` also emit the detected PR number (both platforms can auto-detect it), or keep that in per-platform helpers?
- Is there appetite for a `pr-checks` helper to normalize CI status, or is 4-6 lines of platform-specific code acceptable?
- **TENSION (challenge finding #10):** Is the opt-out AskUserQuestion gate in D1 worth the interaction cost? Adversarial critic argues it's ceremony — users pick "Looks good" 90%+ of the time. Architect argues it's fundamentally different from the current uninformed gate because the user sees a concrete plan. Deciding factor: what percentage of real invocations result in skipping items?

## Impact

**Files modified:**
- `skills/mine.address-pr-issues/SKILL.md` — full rewrite (~250-300 lines, down from 377)
- `bin/gh-pr-threads` — add `--json` and `--all` flags, add pagination
- `skills/mine.create-pr/SKILL.md` — replace detection block with `git-platform` (3-line edit)
- `skills/mine.ship/SKILL.md` — replace detection block with `git-platform` (3-line edit)
- `skills/mine.gh-tools/SKILL.md` — document new `--json`/`--all` flags on `gh-pr-threads`
- `README.md` — update bin/ inventory (new script)
- `CHANGELOG.md` — entry for the address-pr-issues redesign

**Files created:**
- `bin/git-platform` — new helper (~15 lines)

**Not modified or removed:**
- `bin/gh-pr-resolve-thread` — the redesigned skill uses `gh-pr-reply --resolve` instead, but `gh-pr-resolve-thread` remains available as a standalone tool for resolve-without-reply scenarios (e.g., bulk-resolving bot threads)

**Blast radius:** Low. Helper changes are additive (new flags). The SKILL.md rewrite is self-contained. The `git-platform` usage in `create-pr` and `ship` is a trivial substitution. No existing callers break.
