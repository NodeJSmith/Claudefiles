# Changelog

All notable changes to this Claudefiles repository are documented here.

## 2026-04-25

### Added
- Pre-flight analysis phase for `/mine.challenge` — catches surface issues and validates architecture before launching critics; re-challenge detection reduces to 2 critics (#253)

### Changed
- `pytest-loop-detector.sh` — add total failure counter (threshold 8) that catches edit-run-fail flailing loops; denied runs no longer inflate counters (#264)

### Removed
- `commands/cm-manage-memory.md` — dead command; functionality superseded by automatic session sync hook (#255)

## 2026-04-24

### Added
- `--body-file` flag on `gh-pr-reply`, `ado-api pr reply`, and `ado-api pr thread-add`; `--description-file` flag on `ado-api pr create`, `pr update`, `work-item create`, and `pr work-item-create` — pass large text via file instead of inline argument; all support `-` for stdin (#251)
- `deny_all` option in `pytest-guard.sh` per-repo config — block all pytest invocations in repos that use nox or other test runners (#252)

## 2026-04-22

### Added
- `/mine.debug` skill — 4-phase systematic debugging methodology (root cause investigation, pattern analysis, hypothesis testing, implementation) with escalation protocol and session-scoped error file; owns the error-tracking contract previously in `error-tracking.md` (#244)
- `pytest-loop-detector.sh` / `pytest-loop-reset.sh` hooks — deny pytest after 3 consecutive post-failure runs without code changes; counter resets on any Edit/Write/MultiEdit/NotebookEdit; override via `CLAUDE_PYTEST_LOOP_BYPASS=1` or `bin/pytest-loop-reset` (#244)
- `pytest-guard.sh` PreToolUse hook — denies bare pytest without `timeout` wrapper to prevent orphaned processes; supports per-repo `.claude/pytest-guard.json` for deny_flags and custom timeouts (#242)

### Removed
- `rules/common/error-tracking.md` — contract moved into `/mine.debug` skill (#244)
- `rules/common/research-escalation.md` — escalation protocol absorbed into `/mine.debug`'s Phase 4 escalation rules (#244)

## 2026-04-21

### Fixed
- `mine.orchestrate` executor, spec reviewer, and Phase 3 fix executor subagents now declare `model: sonnet` — previously inherited the parent conversation's model (Opus), wasting tokens on implementation work (#241)

### Added
- `ado-api` Python package — Azure DevOps CLI for builds, logs, PR management, work items, and approvals; replaces bash `ado-*` scripts with typed Pydantic-settings CLI (#240)

### Removed
- `bin/ado-builds`, `bin/ado-logs`, `bin/ado-pr`, `bin/ado-pr-threads`, `bin/ado-common.sh` — replaced by `packages/ado-api` (#240)

### Changed
- `ado-pr-threads create` subcommand — create new comment threads on ADO pull requests with inline body or `--file` for longer comments (#238)

## 2026-04-20

### Added
- `mine.audit` skill restored — systematic codebase health audit with parallel directory recon, cross-scope synthesis, and findings-protocol.md resolution flow; routing fixed from `/mine.challenge` to `/mine.audit` (#234)

## 2026-04-19

### Fixed
- `mine.challenge` synthesis subagent silently dropping findings file under heavy context — front-loaded file-write instruction + orchestrator fallback write with header injection (#232)

### Added
- `mine.plan` Phase 2 reverse-dependency gap check — extracts identifiers from the Architecture section, greps the full codebase for unlisted dependencies, includes them as WP subtasks with gap-to-WP attribution in design.md (#230)
- Reviewer checklist item 10 (gap coverage verification) (#230)
- `gh-issue overview` subcommand — shows repo milestones, labels (with descriptions), and usage patterns; new "Issue Creation Conventions" rule in `git-workflow.md` with >50% threshold for auto-applying milestones/labels (#229)

### Removed
- `claude-log` CLI tool — retired in favor of `cm-search-conversations` (#230)
## 2026-04-18

### Changed
- `mine.define` now produces a single `design.md` instead of separate `spec.md` + `design.md` — spec content (Goals, User Scenarios, Functional Requirements, Edge Cases, Acceptance Criteria) merged into design.md (#223)
- `spec-helper archive` no longer deletes `spec.md` (only `tasks/` + status update) (#223)
- All caliper skills updated to reference `design.md` only: `mine.plan`, `mine.challenge`, `mine.build`, `mine.mockup`, `mine.commit-push`, `mine.create-pr`, `i-teach-impeccable` (#223)
- `caller-protocol.md` routing simplified — single-document targeting replaces spec-vs-design heuristic (#223)

## 2026-04-17

### Changed
- Sync `i-*` Impeccable skills with upstream v2.1.1: add `i-shape`, `i-overdrive`, `i-layout`; merge deprecated `i-arrange`/`i-extract`/`i-normalize`/`i-onboard` into surviving skills; enrich `i-frontend-design` with inline principles and bans (#220)
- All `.claude/` write targets (audits, screenshots, mockups) moved to `/tmp/` via `get-skill-tmpdir` — eliminates forced permission prompts on Claude Code 2.1.77+ (#218)
- Caliper pipeline simplified: `mine.specify` + `mine.design` → `mine.define`; `mine.draft-plan` + `mine.plan-review` → `mine.plan` (6 skills → 4, fewer user checkpoints) (#219)
- `mine.orchestrate` per-WP reviewers run in parallel; auto-challenge removed from Phase 3 (now opt-in) (#219)
- `caller-protocol.md` — shared manifest flow for challenge callers (#217); code-fix caller removed (#219)
- `spec-helper archive` removes `tasks/` and stamps design.md status
- Per-finding resolution manifest for challenge findings (#217); `**Doc target:**` field added (#217)

### Removed
- 4 unused agents: `dep-auditor`, `ui-auditor`, `db-auditor`, `browser-qa-agent` (#218)

## 2026-04-16

### Changed
- `mine.orchestrate` "Address fixes" (impl-review loop) and "Address findings" (challenge loop) no longer hard-stop after 2 iterations. Starting at the 3rd round, a soft warning is prepended to the gate prompt: "Multiple rounds have not resolved …". The user retains control over when to stop. Other gate logic is preserved — "Accept and ship" remains suppressed while CRITICAL/HIGH findings exist or impl-review returns REQUEST_FIXES
- `mine.design` and `mine.specify` `## Non-Goals` section is now opt-in: present only when the user explicitly named exclusions, omitted entirely when they stated none. Claude is prohibited from inferring non-goals from the research brief or its own judgment. Prevents invented exclusions from creating false scope-violation findings in downstream critics. `mine.draft-plan` and `mine.specify` revision routing updated to tolerate an absent Non-Goals section

## 2026-04-12

### Added
- `cm-*` memory skills from Claudest: `cm-recall-conversations`, `cm-extract-learnings`, `cm-get-token-insights`, `cm-memory-auditor`, `cm-signal-discoverer`, `cm-manage-memory` (#212)
- Memory session hooks wired into `settings.json`: `memory-setup`, `onboarding`, `memory-context`, `consolidation-check`, `clear-handoff`, `memory-sync` (#212)

## 2026-04-11

### Removed
- Pyright prerequisite check from `install.sh` — LSP plugin is disabled and the warning caused confusion (#211)

## 2026-04-10

### Changed
- `code-reviewer` agent rewritten: slimmed from 619 → 133 lines, now language-neutral; Claudefiles-specific skill/markdown checks moved to `CLAUDE.md` where they auto-load only in this repo (#207)
- `spec-reviewer-prompt` strengthened with adversarial DO/DON'T framing — explicit "do not trust the executor's self-report" stance (#207)
- Phase 3 fix executors (impl-review and challenge loops) now use `retry-prompt.md` instead of `implementer-prompt.md` (#207)
- README section counts removed — one less thing to keep in sync (#207)
- `mine.challenge` resolve flow replaced with a per-finding Resolution Manifest — findings become an editable `resolutions.md` file opened in `$EDITOR` via new `bin/edit-manifest` helper, replacing the "Accept all?" bundled prompt that routinely collapsed 7-11 findings into a single binary choice (#206)

### Added
- `retry-prompt.md`: new executor prompt for retry/fix passes — verify-before-implement, YAGNI check, push-back protocol; replaces mechanical "read and fix" with an evaluative stance (#207)
- `rules/common/receiving-code-review.md`: new always-loaded rule encoding the same posture for the main agent in conversational/manual review contexts (#207)
## 2026-04-07

### Changed
- Challenge findings.md enriched with four presentation fields (`why-it-matters`, `evidence`, `references`, `design-challenge`) — critics produce structured sections, synthesis copies them, Phase 4 renders mechanically from file instead of generating (#195)
- Phase 4 template restructured as mutually exclusive blocks (Auto-apply / User-directed / TENSION) with explicit suppress rules for backward compatibility (#195)
- Synthesis now validates severity values against the contract taxonomy — non-contract values (e.g., `LOW`) are reclassified as `MEDIUM` with a validation warning (#195)
- Added `Format-version: 2` header to findings files for format detection (#195)
- Session manifest replaces context-dependent mode detection — `mode`, `findings-out`, `focus`, and `target` persisted as compaction-safe artifacts (#195)
- Added `--mode=passthrough` flag — passthrough detection is now deterministic, not inferred from LLM context; mine.brainstorm and mine.research updated (#195)
- Structured callers (mine.design, mine.specify) now assert `Format-version: 2` and validate contract tags before consuming findings (#195)
- WP format noise reduction — remove `Activity Log` (never read by any consumer) and `plan_section` (decorative) from WP schema; replace full `design.md` injection with targeted section extracts via new `spec-helper design-extract` subcommand (~19% executor prompt token reduction) (#191)

## 2026-04-06

### Added
- Anti-rationalization tables in mine.build, mine.challenge, mine.research, and research-escalation.md — derived from session archaeology of 73 transcripts; 19 rationalizations covering workflow phase skipping, research escalation failure, gate conflation, and scope drift (#187)
- Canonical "Code Review vs Challenge" section in git-workflow.md — extracted from per-skill duplications (#187)

### Changed
- Add explicit model declarations to all 18 agents — 16 sonnet, 1 opus (researcher), 1 haiku (ui-auditor); previously all inherited Opus (#186)
- Expand `performance.md` with Haiku disqualifiers, agent model cross-reference, and inline skill model tracking (#186)
- `spec-helper` — replace `visual_skip` boolean with `visual_mode` tri-state string (`enabled`/`skipped_no_server`/`skipped_no_vision`), add `executing`/`warn_retry` to checkpoint status values, bump `CHECKPOINT_VERSION` to 2, add write-time validation and checkpoint hardening (immutable fields, symmetric pairing guards, malformed verdict detection, fsync) (#181)

## 2026-04-05

### Changed
- Impeccable i-* bundle remediation — 4 rounds of `/mine.challenge` adversarial review, 30 files changed (#175)
- All modification skills (16) now propose changes and confirm before implementing — no skill writes code without user approval (#175)
- `i-teach-impeccable` absorbs `mine.look-and-feel` — single writer for design context at `design/context.md` (#175)
- Context Gathering Protocol rewritten — `design/context.md` is canonical, with migration fallbacks for `.impeccable.md` and `design/direction.md` (#175)
- All MANDATORY PREPARATION blocks now use explicit `Read` instruction instead of prose "use the skill" (#175)
- Anti-pattern DON'T list extracted to single-source reference file; inline duplications replaced with pointers (#175)
- Per-finding skill routing in i-audit/i-critique — category-to-skill mapping instead of generic suggestion (#175)
- Default scoping rule added to i-frontend-design — all skills ask for scope when ambiguous (#175)
- Per-skill completion contracts — diagnostics write report files, modification skills summarize in conversation (#175)
- Richer aesthetic capture in i-teach-impeccable — visual movements, concrete constraints, take/leave analysis (#175)
- Diagnostic skills (i-audit, i-critique) no longer block on missing design context — warn and proceed (#175)
- Replace backlog convention with findings convention — default is now fix-all with auto-apply for unambiguous fixes, user-directed answers collected before code changes, and per-finding "file as issue" option; remove `mine.audit` (use `/mine.challenge` instead) (#176)
- `mine.orchestrate` — replace `visual_skip` boolean with `visual_mode` enum (`enabled`/`skipped_no_server`/`skipped_no_vision`); move vision check to Phase 0; replace 24h staleness heuristic with git-state check; extract agent routing table to `agent-routing.md` (#174)
- `mine.orchestrate` — add explicit verdict assembly step (Step 8.7), independent test gate (Step 5.3) with regression detection, and ABANDON handling for impl-review (#174)

### Removed
- `i-overdrive` — WebGL/WASM/scroll-driven animations skill not in use (#175)
- `mine.look-and-feel` — absorbed into `i-teach-impeccable` (#175)
- `IMPECCABLE_VERSION.md` — git history preserves same info (#175)
- `skills/mine.orchestrate/phase-executor-prompt.md` — content absorbed into `implementer-prompt.md` (#174)

### Fixed
- i-extract, i-harden, i-optimize missing MANDATORY PREPARATION blocks (#175)
- i-clarify vs i-delight error copy contradiction (humor now scoped to non-blocking errors on playful brands) (#175)
- i-animate vs i-delight spring physics contradiction (spring without overshoot is permitted) (#175)
- i-harden out-of-scope server-side validation and test-writing sections removed (#175)
- Hardcoded 19-skill suggestion lists in i-audit/i-critique replaced with dynamic instruction (#175)
- Reference file paths switched from broken relative to absolute `~/.claude/skills/` paths (#175)
- `mine.orchestrate` — align all prompt files with caliper v2 WP schema; merge `phase-executor-prompt.md` into `implementer-prompt.md`; fix 72 findings across 3 challenge rounds covering ghost schema fields, verdict assembly, test gate regression detection, checkpoint resilience, Phase 3 fix context, and visual verification contracts (#174)

## 2026-04-04

### Fixed
- `mine.address-pr-issues` — add mandatory markers for review thread fetching so Claude doesn't skip `gh-pr-threads` and falsely report "no review comments" (#172)
- `install.sh` — add `-n` flag to `ln -sf` calls so re-runs replace symlinks-to-directories instead of creating self-referencing links inside them (#173)

### Changed
- `mine.plan-review`, `mine.implementation-review` — switch review subagents from Opus to Sonnet; structured checklist evaluation doesn't need Opus-tier reasoning (#173)

## 2026-04-03

### Added
- `engineering-data-engineer` agent — PySpark/Delta Lake/Databricks specialist with lakehouse conventions, dedup patterns, and gold-layer-as-dbt-schemas architecture (#164)
- `engineering-backend-developer` agent — FastAPI specialist with async patterns, DI examples, SQLAlchemy session management, and test patterns (#164)
- `mine.challenge` — Agent Definition specialist persona for reviewing agent files: identity bloat, missing conventions, executor compatibility, scope overlap (#165)
- `mine.challenge` — `agent-file` target type with heuristic detection and gold-standard comparison context gathering (#165)
- `mine.challenge` — Web Platform specialist persona for reviewing frontend code: client-side performance, component performance patterns, data fetching, source-detectable accessibility, client-side security, CSS architecture (#167)
- `mine.challenge` — `frontend-code` target type with heuristic detection (`.tsx`, `.jsx`, `.vue`, `.svelte`, `.astro`, component directories) and specialist mapping (Web Platform + Operational Resilience) (#167)
- `mine.challenge` — two new documentation specialist personas: End-User Reader (page-level prerequisite audit) and Documentation Architect (set-level structure and Diataxis mode review) (#162)
- `mine.challenge` — new `docs` target type with path-based heuristic detection (`README.md`, `docs/` directory) and specialist mapping (#162)
- `scripts/hooks/sudo-poll.sh` — PreToolUse hook that enables sudo in Claude Code sessions via deny-then-poll with credential cache (requires `Defaults timestamp_type=global` in sudoers) (#163)
- `rules/common/sudo.md` — rule for sudo operations: hook-first workflow with script-generation fallback for complex cases (#163)

### Fixed
- Codebase health fixes from `/mine.challenge` adversarial review: atomic writes, rule/enforcement consistency, dead schema removal, platform-aware issue creation, and safety improvements across 31 files (#170)

### Changed
- `mine.challenge` — orphan detection warns when specialist persona files exist but aren't in the mapping table; runs unconditionally for all target types (#168)
- `mine.challenge` — specialist selection hardened: manifest-derived Phase 4 announcements, persistent validation warnings, identity-based manifest parsing, `Warnings:` field in findings header (#168)
- `rules/common/command-output.md` — reinforces capturing long-running command output to tmp files instead of re-running with larger tail arguments (#168)
- `rules/common/git-workflow.md` — WP archival check now applies to all push flows, not just `/mine.ship` (#168)
- `engineering-technical-writer` agent — complete rewrite to gold standard: executor note, codebase conventions, MkDocs patterns, anti-patterns, test execution discovery, enforced tooling (#165)
- `engineering-frontend-developer` agent — complete rewrite: added `tools` frontmatter, executor note, codebase conventions, anti-patterns with SYNC markers, test execution discovery, enforced tooling; removed competing deliverable template, editor extension contamination, false memory claims, and inaccessible code example (#164)
- `rules/common/python.md` — explicitly bans `Optional[X]` (was only implicitly discouraged via `X | Y` preference) (#164)
- `rules/common/coding-style.md` — adds PySpark DataFrame reassignment carve-out to the immutability rule (#164)
- `mine.orchestrate` — routing table now dispatches PySpark/dbt and FastAPI WPs to specialized agents (#164)
- Eval assertions updated to use full `engineering-*` agent names instead of partial substrings (#164)
- `mine.challenge` — `--focus` prefix matching now requires 6-character minimum to prevent short-prefix misfires (#162)
- `mine.challenge` — `--focus` specialist replacement is announced post-run instead of blocking with an interactive gate (unblocks subagent callers) (#162)
- `mine.challenge` — specialist selection announced before findings in Phase 4, not after (#162)
- Anti-patterns sections added to 7 agents: db-auditor, dep-auditor, ui-auditor, browser-qa-agent, visual-diff, testing-reality-checker, engineering-sre (#165)

### Removed
- 19 agents removed (37 → 18): agents-orchestrator, design-ui-designer, design-ux-architect, design-ux-researcher, design-visual-storyteller, engineering-ai-engineer, engineering-devops-automator, engineering-incident-response-commander, engineering-rapid-prototyper, engineering-security-engineer, product-feedback-synthesizer, product-sprint-prioritizer, specialized-developer-advocate, specialized-mcp-builder, specialized-model-qa, testing-api-tester, testing-performance-benchmarker, testing-tool-evaluator, testing-workflow-optimizer (#165)
- `evals/` directory — promptfoo compliance tests removed entirely (#165)

## 2026-04-01

### Added
- `mine.ship` now reminds about WP archival after PR creation — runs `spec-helper archive --dry-run --json` and surfaces specs ready to archive (#155)

### Changed
- `mine.challenge` Phase 3 synthesis now requires reading every critic report in full — prevents partial reads that silently drop findings (#157)
- `mine.orchestrate` Phase 3 subagents must now run in foreground — several steps spawn parallel child subagents internally which requires foreground execution (#156)
- `bin/claude-log` — redesigned from JSON-only output with 9 commands to text-first output with 4 commands (list, search, show, stats); orientation mode for show, `--grep` for within-session search, conversation-turn context in search results, `--json` flag for structured output (#153)
- `skills/mine.tool-gaps/SKILL.md` — updated `claude-log extract --bash` references to `claude-log show --tools --grep` (#153)
- `mine.draft-plan` no longer caps Work Packages at 8 — design complexity determines the count (#152)
- Removed `rules/common/lsp.md` and LSP references — pyright-lsp plugin being disabled due to stale diagnostic noise; linter/type checker discovery added to `git-workflow.md` (#152)

### Removed
- `bin/claude-log` — removed `extract`, `grep`, `skills`, `agents`, `permissions` subcommands (functionality absorbed into remaining 4 commands) (#153)

### Fixed
- `spec-helper init` now respects monorepo structure — creates features in the nearest `design/specs/` relative to cwd, not at the git root (#152)
## 2026-03-30

### Added
- `mine.prior-art` skill — web-first survey of best practices, reference implementations, and established patterns for mid-design architectural questions (#151)
- `spec-helper archive` subcommand — archives completed specs by removing `tasks/` and setting `**Status:** archived` in design.md; supports `--all`, `--dry-run`, `--json` (#143)
- Artifact lifecycle convention in CLAUDE.md — documents which design artifacts are permanent vs development-only (#143)
- `bin/lint-cli-conventions` — pre-commit hook that verifies `--help` presence in bin/ scripts and capabilities.md CLI table sync with bin/ contents; prevents drift recurrence (#144)
- `rules/common/lsp.md` — LSP tool guidance for Python symbol navigation (definitions, references, call hierarchy) via pyright (#144)
- `--help` with usage examples on all 21 executable scripts in `bin/` — agents can now discover tool capabilities at runtime (#144)
- `rules/common/research-escalation.md` — escalation ladder for when Claude is stuck: search first (Context7/WebSearch), then dispatch a research subagent, then present to user; replaces `web-search.md` with broader coverage including subagent dispatch, error file integration, and exit protocol (#145)

### Changed
- Archived 10 completed spec task directories (54 WP files removed), renamed `009-test-coverage-enforcement` to `012-*` to fix duplicate numbering (#143)
- `rules/common/capabilities.md` — removed `gh-bot`, `gh-app-token`, `git-rebase-onto` (external tools); added `agnix-check`, `git-platform`; inlined GitHub tool notes (auth, workflow, gotchas) from deleted `mine.gh-tools` skill (#144)

### Removed
- `design/specs/003-selective-context/` — abandoned spec, never implemented (#143)
- `design/specs/004-visual-verification-frontend-wps/` — implemented elsewhere, design doc stale (#143)
- `rules/common/web-search.md` — content absorbed into `research-escalation.md`; the standalone rule wasn't triggering proactive search behavior (#145)
- `skills/mine.gh-tools/` — non-user-invocable skill files aren't reliably loaded by Claude; tool details now live in `capabilities.md` (auto-loaded) + `--help` (runtime discovery) (#144)
- `evals/compliance/tools/skill-cross-reference.yaml` — tested the "See skill:" cross-reference pattern which is no longer used (#144)
- `bin/claude-log` — removed `from __future__ import annotations`, moved lazy imports to top-level, added argparse epilog examples (#144)
- `bin/claude-merge-settings` — moved lazy `import argparse` to top-level, added epilog examples (#144)

### Fixed
- `rules/common/backlog.md` — removed explicit `gh-app-token` tool name reference (auto-loaded rule shouldn't name tools outside this repo's contract) (#144)

## 2026-03-29

### Added
- `mine.challenge` specialist personas — domain-specific critics (Contract & Caller, Data Integrity, Operational Resilience, Workflow & UX) selected by target type to augment the 3 generic critics; `--no-specialists` flag to opt out; `--focus` prefix matching to override defaults (#142)

### Changed
- `mine.challenge` critic subagents now use Sonnet model (experiment showed comparable finding quality at lower cost) (#142)
- `mine.challenge` confidence moved from standalone findings field to severity parenthetical; removed from output contract tags (presentation-only) (#142)
- `mine.orchestrate` git state management — added Step 4.5 (capture changed files after executor), pass explicit file lists to reviewers, re-capture after auto-fix loops, use `--pathspec-from-file` instead of `git add -A` for targeted staging (#140)
- `mine.draft-plan` TDD ordering — subtasks are now behavioral units ordered by dependency; Test Strategy is a coverage inventory; executor determines test-first sequencing at runtime (aligns with Kent Beck's canonical TDD) (#140)
- `code-reviewer` and `integration-reviewer` file discovery — accept explicit file lists from orchestrate, fall back to `git diff --name-only HEAD` for uncommitted changes, documented dual invocation patterns (#140)
- `spec-reviewer-prompt` — Test Strategy treated as coverage inventory; test function names are advisory, not strict contracts (#140)

## 2026-03-27

### Added
- Redesigned `mine.address-pr-issues` — inverted opt-out flow, investigate-before-fix subagents with depth tiers, test-before-push mandate, bot-vs-human thread resolution policy, idempotent reply markers, per-group commits, cite-or-escalate outdated thread triage (#137)
- `bin/git-platform` — detect git hosting platform (`github`/`ado`/`unknown`) from remote URL; replaces duplicated detection logic in 3 skills (#137)
- `gh-pr-threads --json` and `--all` flags — structured JSON output with pagination and `__typename` for bot detection (#137)
- Test Co-location principle in `rules/common/testing.md` — canonical rule that unit tests ship with code, with predicate for repos with test infrastructure and unified exemption list (#136)
- `## Test Strategy` section in `mine.design` design doc template — forces test thinking at architecture time, consumed by `mine.draft-plan` Phase 1 (#136)
- Test-presence check in `mine.ship` LOCAL VERIFICATION — advisory "zero test files in diff" heuristic for ad-hoc work (#136)
- Python rules file (`rules/common/python.md`) — bans `from __future__ import annotations` (#136)
- Parallel reviewer/critic launch pattern in `rules/common/agents.md` — parallel foreground execution for independent agents (#136)

### Changed
- `mine.draft-plan` WP ordering rules — unit tests must live in same WP as code; integration tests may follow in subsequent WP (#136)
- `mine.draft-plan` Test Strategy field rule — strengthened from advisory to structural with numbered sub-list (#136)
- `mine.implementation-review` item 7 upgraded to CRITICAL severity with explicit FAIL/WARN categories and verdict rule (#136)
- `mine.orchestrate` `tdd.md` — added Test Co-location section so executor subagents see the principle directly (#136)
- `mine.challenge` critic launch now specifies parallel foreground execution (#136)
- Log capture tests discouraged in `rules/common/testing.md` — test behavior, not log output (#136)
## 2026-03-26

### Fixed
- `mine.challenge` standalone wrap-up — now provides summary and next-step prompt after presenting findings instead of silently stopping; passthrough callers (`mine.grill`, `mine.brainstorm`, `mine.research`) get summary only to avoid double-prompting with their own gates (#132)

### Changed
- `mine.orchestrate` resilience overhaul — checkpoint file for resume across sessions, WIP commits per WP, WARN fix loop (1 auto-retry before escalation), streamlined Phase 3 with auto implementation-review + auto challenge + ship gate (#131)
- `mine.implementation-review` made non-user-invocable — now internal to orchestrate Phase 3 pipeline; `--inline` flag and Phase 4 gate removed (#131)
- `mine.build` post-orchestration steps simplified — orchestrate owns the full pipeline including review, challenge, and shipping (#131)

### Added
- `spec-helper checkpoint-{init,read,update,verdict,delete}` — deterministic checkpoint I/O with schema validation, version field, frozen dataclasses, and atomic writes; replaces LLM text parsing of orchestration state (#131)
- `mine.orchestrate` auto-challenge gate — dispatches `/mine.challenge` as Opus subagent after all WPs complete, scoped to `base_commit..HEAD` diff (#131)
- `mine.implementation-review` item #6 (integration gaps) expanded with verification method, 9 integration patterns, and 3-tier classification (true gap / test-only / wired) (#131)

## 2026-03-25

### Changed
- `mine.research` overhauled — multi-domain Phase 1 examples (breaks persistence anchoring bias), depth parameter (quick/normal/deep) inferred from Phase 1 flexibility and scope, failure handling after researcher dispatch, `/mine.design` added to next-step gate, challenge passthrough always uses tmpdir path with `--target-type=research` (#127)
- `researcher` agent formalized — caller prompt checklist, YAML frontmatter in brief output, flexibility-based Options scaling (Decided=single deep-dive, Exploring=full multi-option), depth-based subagent count (#127)
- `mine.design` auto-detects existing research briefs before dispatching researcher agent (prevents duplicate investigation), `**Research:**` field added to design doc template (#127)
- `mine.build` prior-analysis detection now recognizes research briefs (YAML frontmatter and header-based) (#127)
- `mine.challenge` overhauled — rebranded to "adversarial review" (any artifact, not just designs), impact-based severity with confidence annotations, target-type classification (7 types + `--target-type` override), simplified 3-step synthesis, sharpened personas (security, ops, user-need), new `--focus` argument, TENSION clarified, positional-first argument parsing (#126)
- `mine.challenge` no longer prompts after presenting findings — auto-completes and lists file paths; callers handle persistence (#125)
- `spec-helper` rewritten as an installable Python package (`packages/spec-helper/`) — replaces fragile hand-rolled YAML parser with `python-frontmatter`, adds `wp-validate` and `wp-list` commands, fixes silent `cwd` fallback, atomic writes, section-aware activity log insertion (#124)
- Install via `uv tool install -e packages/spec-helper` instead of bin/ symlink (#124)

### Added
- `spec-helper wp-validate [feature] [--fix]` — validates WP frontmatter schema, checks `depends_on` references, detects old-schema drift; `--fix` normalizes files in place (#124)
- `spec-helper wp-list <feature>` — JSON output of WP metadata for programmatic consumers (#124)
- `--auto` flag on all feature-accepting commands — resolves most recently modified feature directory (#124)

### Fixed
- Stale "user selects Done" references in `mine.design`, `mine.specify`, `mine.grill`, `mine.research`, `mine.brainstorm` (#125)

### Removed
- `bin/spec-helper` single-file script — replaced by the `packages/spec-helper/` package (#124)

## 2026-03-24

### Changed
- `mine.challenge` rewritten as pure adversarial critique — produces findings only, no longer generates revision plans or manages caliper workflow (#123)
- Finding taxonomy: four types (Structural / Approach / Fragility / Gap), `design-level` tag, `Auto-apply` vs `User-directed` resolution, structured `findings.md` handoff (#123)
- Revision plan logic moved to `mine.design` and `mine.specify` — each generates plans from challenge's `findings.md` after challenge completes (#123)
- `mine.specify` routes `design-level: Yes` findings to spec or design phase with concrete heuristic; deferred findings persisted to `design.md` Open Questions (#123)

### Added
- `--findings-out` argument for `mine.challenge` — callers pass a known output path for deterministic handoff (#123)
- Output contract section in `mine.challenge` documenting breaking-change tag names, values, and known callers (#123)

## 2026-03-21

### Added
- `claude-log` subagent tool extraction — all commands now surface tool calls from subagent progress messages by default (#111)
- `claude-log search` and `grep` now support `--fixed`/`-F` for literal matching; both are regex by default (#118)
- `claude-log show` and `extract` gain `--limit` flag to cap output entries (#122)
- JSONL corruption warnings — stderr warning when >1 corrupt line is skipped per file (#122)
- `extract_cwd` reads real working directory from JSONL entries, fixing lossy path decoding for hyphenated project names (#114)

### Changed
- `claude-log` output is now JSON-only — ANSI color system, table formatter, and human-readable output paths removed (#116)
- `find_sessions` optimized to read first ~20 lines per file instead of every line (#115)
- Skill detection deduplicated per-turn with early colon normalization; JSON output includes `via` field (#120)
- `cmd_show` unified into single-pass JSON builder, removing `_filter_entries_for_show` duplication (#119)
- `cmd_agents` now detects both `Agent` and `Task` tool names for backward compatibility (#122)

### Removed
- `claude-log permissions` subcommand and all supporting code (~160 lines) — replaced by `mine.permissions-audit` which reads debug logs directly (#117)
- ANSI color constants, `format_table()`, `truncate()`, `USE_COLOR` global, `--json`/`--no-color`/`--no-subagents` flags (#116)

## 2026-03-19

### Added
- [Impeccable](https://impeccable.style/) frontend design skill bundle — 21 `i-*` skills for typography, color, layout, animation, accessibility, and UI quality (#109)
- Intent routing for all 20 user-invocable `i-*` skills in `capabilities.md` (#109)
- Design context bridging — `mine.look-and-feel` now writes `.impeccable.md`, and `i-frontend-design` reads `design/direction.md` as fallback (#109)
- `IMPECCABLE_VERSION.md` for upstream version tracking and upgrade policy (#109)

### Fixed
- `AskUserQuestion` blocks in skills rendered as plain markdown bullets instead of interactive selectors — added CRITICAL rule to `interaction.md` enforcing tool calls with exact labels (#106)

### Added
- `mine.look-and-feel` skill — plan UI design direction (tokens, palette, typography, spacing) and persist to `design/direction.md`; replaces `mine.interface-design` (#104)
- `mine.mockup` skill — generate self-contained HTML mockup files, reads `design/direction.md` for consistent styling; replaces `vx.visual-explainer` (#104)
- `mine.look-and-feel` and `mine.mockup` commands (#104)
- Boundary eval tests for mine.design vs mine.look-and-feel disambiguation and negative tests for dropped diagram routing (#104)
- `mine.build` direction.md detection — reads `design/direction*.md` before UI work and applies closed token layer (#104)

### Changed
- `mine.orchestrate` now enforces code reviewer and integration reviewer as mandatory steps — MANDATORY headers, file-existence gate (Step 8.5), and FAIL override prevent review skipping (#110)
- `mine.specify` now produces structured User Scenarios with per-actor task flows (Sees/Decides/Then steps) — downstream UI skills (`mine.look-and-feel`, `mine.mockup`, `mine.design`) consume spec.md directly instead of re-asking actor/goal questions (#108)
- Routing table: `mine.interface-design` → `mine.look-and-feel`, `vx.visual-explainer` → `mine.mockup`; diagram routing intentionally dropped (#104)
- All skills now use `mine.*` prefix — removed `vx.*` multi-prefix convention (#104)
- Eval file `intent-to-skill-design-ux.yaml` rewritten: 3 look-and-feel + 3 mockup + 6 boundary + 2 negative tests (#104)

### Removed
- `mine.interface-design` skill and command — replaced by `mine.look-and-feel` (#104)
- `vx.visual-explainer` skill — replaced by `mine.mockup`; dead subcommands (diff-review, fact-check, slides, share, project-recap) not migrated (#104)

---

### Added (PR #105, #103)
- `claude-log skills --audit` flag — cross-references session usage against skills/commands on disk, showing active, never-used, and ghost entries (#105)
- Visual verification for frontend work packages — `mine.draft-plan` generates scenario tables (Page/Setup/Verify), executor captures before/after screenshots, dedicated visual reviewer judges against criteria; per-WP temp subdirectories preserve evidence across orchestration runs (#103)
- `mine.worktree-rebase` accepts explicit branch name and natural-language skip (`just rebase`, `force`) (#105)

### Removed
- 3 unused docs-only skills: `mine.ado-tools`, `mine.git-tools`, `mine.session-tools` — routing table in `capabilities.md` already covers these; scripts have `--help` (#105)
- 8 unused `vx.*` command shortcuts — identical copies of templates already inside `vx.visual-explainer/commands/` (#105)
- 4 unused commands: `mine.5whys`, `mine.agnix`, `mine.capture_lesson`, `mine.session_reflect` (#105)
- `mine.skill-eval` skill + `skill-eval-run`/`skill-eval-aggregate` bin scripts — redundant with promptfoo evals (#105)
- `mine.human-centered-design` (1,128 lines, 1 use), `mine.security-review` (891 lines, 0 uses), `mine.refactor` (320 lines, 1 use) (#105)
- `mine.interviewer` (alias for specify), `mine.ux-antipatterns` (overlaps with reviewers + challenge) (#105)
- `mine.adrs` — research → design → WP pipeline already captures decisions in context (#105)

### Fixed
- `rules/common/interaction.md` referenced nonexistent `TodoWrite` tool (now `TaskCreate`) (#105)
- `bin/ado-common.sh` lacked `set -euo pipefail` — shared library now defensive (#105)
- `mine.specify` scope question ("What is explicitly out of scope?") reworded to avoid ambiguous double-negative options (#105)
- Removed "Docs" column from CLI tools routing table — scripts have `--help` (#105)

## 2026-03-18

### Removed
- `rules/python/` — all 5 Python-specific rules files; Claude already knows Python conventions (#102)
- `rules/common/patterns.md`, `rules/common/security.md`, `rules/common/hooks.md` — restated Claude's default behavior (#102)
- `mine.agent-patterns`, `mine.python-patterns`, `mine.python-testing`, `mine.backend-patterns` — non-invocable reference skills (2,052 lines of tutorials Claude doesn't need); agent patterns inlined into `agents.md` (#102)

### Changed
- Compressed all remaining rules files from 1,010 to 561 lines (44% reduction) — removed textbook definitions, "Why This Matters" sections, CLI flag documentation, and redundant examples (#102)
- Inlined agent patterns (parallel execution, subagent types, context passing) into `rules/common/agents.md` (#102)
- Moved TodoWrite and permissions content from deleted `hooks.md` into `interaction.md` (#102)

### Added
- `mine.visual-qa` skill — Playwright screenshotter captures pages + interactive element states, then three agents analyze under separated viewing conditions (first impressions, consistency audit, unstructured design narrative); supports `--mobile` and `--dark` flags for focused per-viewport runs (#99, #101)
- `mine.grill` — pre-pipeline multi-angle interrogation (product, design, engineering, scope, adversarial lenses); produces `brief.md` that `/mine.specify` can ingest (#100)
- `mine.write-skill` — guided skill creation with quality checklist and auto-wiring of routing in `capabilities.md` + README (#100)
- TDD vertical-slice methodology and mocking rules to `rules/common/testing.md` (#100)
- Codebase reconnaissance (Phase 1.5) and adaptive follow-up branches in `mine.specify` (#100)
- 9-point plan review checklist (spec coverage, design coverage, scope containment) in `mine.plan-review` (#100)
- `/mine.challenge` gate option in `mine.specify`, `mine.grill`, `mine.brainstorm`, and `mine.research` sign-off gates (#100)

### Changed
- `mine.build`, `mine.design`, `mine.specify`, `mine.grill` — scoping summaries now start with "**Understood pain point:**" to reinforce pain-point-first thinking (#100)
- `rules/common/interaction.md` — one-line nudge to suggest `/mine.challenge` before committing to non-trivial designs or workflow changes (#100)
- `rules/common/worktrees.md` — removed proactive worktree prompt; worktree decisions are user-driven (#100)

## 2026-03-17

### Changed
- `mine.address-pr-issues` helper scripts section replaced with "See skill:" cross-references to `mine.gh-tools` and `mine.ado-tools` (#98)

### Added
- `rules/common/interaction.md` — ban `EnterPlanMode` unless explicitly requested; use `planner` subagent + `AskUserQuestion` instead (#95)
- `/mine.review` command — run code-reviewer and integration-reviewer in parallel on the current branch diff (#96)
- `scripts/hooks/tmux-remind.sh` — `SessionStart` hook that reminds Claude to rename the tmux session (only fires when `$TMUX` is set) (#97)

### Changed
- `mine.design` Phase 5 sign-off gate now offers "Challenge this design" option — runs `/mine.challenge` on the design doc before approving (#97)

### Removed
- `mine.constitution` skill and all references — redundant with global rules; per-project overrides belong in CLAUDE.md (#96)

### Changed
- `mine.orchestrate` executor subagent now selects a specialized agent type based on WP content instead of always using general-purpose (#96)

### Fixed
- Agent frontmatter `name` fields now match filenames (kebab-case) so `subagent_type` references resolve correctly — previously Title Case names like `Code Reviewer` didn't match kebab-case references like `code-reviewer` (#96)
- `mine.design` and `mine.specify` interview questions now use one `AskUserQuestion` per question instead of batching multiple questions into a single call with mismatched options (#96)

### Changed
- `mine.refactor`, `mine.address-pr-issues`, `mine.5whys`, `mine.issues` — replaced `EnterPlanMode`/`ExitPlanMode` with `planner` subagent + `AskUserQuestion` approval flow (#95)
- `rules/common/web-search.md` — search-before-retry rule: triggers on recurring errors (2+), unfamiliar APIs, version/deprecation messages; routes to Context7 or WebSearch by situation (#94)
- Local test/lint verification step in `mine.ship` and `mine.commit-push` — runs test suite and linter before committing, with 3-retry limit (#94)

### Changed
- `mine.orchestrate` per-WP loop now runs `code-reviewer` (loop) and `integration-reviewer` (once) instead of the custom quality reviewer — catches issues per WP rather than at ship time (#94)
- Caliper skill handoffs (`mine.design`, `mine.draft-plan`, `mine.plan-review`, `mine.implementation-review`) replaced "Run `/mine.X`" text with AskUserQuestion gates that invoke the next skill directly on approval (#94)

## 2026-03-16

### Changed
- `mine.plan-review` Phase 4 gate expanded from 3 to 4 options — adds "Approve with suggestions" for applying non-blocking reviewer suggestions without a full revision cycle; "Request revisions" renamed to "Revise the plan", "Approve — begin execution" renamed to "Approve as-is" (#93)
- `mine.build` plan-review gate references updated to match the new option labels (#93)

### Added
- `bin/git-branch-base` — extracts shared base-detection logic used by `git-branch-log`, `git-branch-diff-stat`, and the new `git-branch-diff-files` (#91)
- `bin/git-branch-diff-files` — print changed file names for the current branch vs its base; replaces hand-rolled fallback chains in skills (#91)
- 266 routing eval tests across 14 files — skills, agents, CLI tools, confusion pairs, and negative tests with 3 prompt variations each (direct/natural/indirect) (#89)
- `evals/fixtures/python-api/` — minimal FastAPI fixture repo for realistic eval contexts (#89)
- `evals/compliance/rules/test-discovery.yaml` — eval for test execution discovery rule (#89)

### Changed
- All `gh issue` commands in skills, commands, and agents replaced with `gh-issue` wrapper (bot token support) — `mine.5whys`, `mine.issues`, `mine.issues-scan`, `mine.refactor`, `issue-refiner` (#91)
- `mine.gh-tools` skill docs now cover `gh-issue` and `gh-pr-create` in addition to PR tools (#91)
- `mine.git-tools` skill docs now cover `git-branch-base`, `git-branch-log`, `git-branch-diff-stat`, and `git-branch-diff-files` (#91)
- `mine.implementation-review` and `mine.mutation-test` simplified — replaced multi-step git diff fallback chains with `git-branch-diff-files` (#91)
- `git-branch-log` and `git-branch-diff-stat` refactored to use `git-branch-base` instead of inline base-detection logic (#91)
- `capabilities.md` CLI Tools table now includes `gh-issue`, `gh-pr-create`, `git-branch-log`, `git-branch-diff-stat`, `git-branch-diff-files`, `git-branch-base` (#91)
- `settings.json` allowlist updated with `gh-issue`, `gh-pr-create`, and all git-branch-* scripts (#91)

### Fixed
- `user-invokable` typo corrected to `user-invocable` across all 35 SKILL.md files, `agents/code-reviewer.md`, and `.agnix.toml` — the CLI silently ignored the misspelled field, so `user-invocable: false` skills were never actually hidden (#92)
- `issue-refiner` agent replaced deprecated `$CLAUDE_SESSION_ID` temp file paths with `get-skill-tmpdir` pattern (#91)
- `mine.challenge` and `vx.visual-explainer` skill descriptions updated with "Use when the user says:" trigger phrases; `mine.challenge` added to routing table (#90)
- Routing table (`capabilities.md`) restored to imperative markdown table format with "BLOCKING REQUIREMENT" preamble and quoted trigger phrases — fixes under-triggering from compressed comment format (#89)
- Agent routing table (`agents.md`) similarly restored with imperative framing (#89)
- 21 skill descriptions updated with trigger phrases ("Use when the user says: ...") to improve `<available_skills>` routing signal (#89)
- All eval provider configs now include `setting_sources: ['user']` and `append_allowed_tools: ['Skill']` — previously skills were invisible to eval sessions (#89)

## 2026-03-15

### Added
- `mine.gh-tools` skill — on-demand GitHub PR helper docs (gh-pr-threads, gh-pr-reply, gh-pr-resolve-thread, gh-bot, gh-app-token) (#88)
- `mine.ado-tools` skill — on-demand Azure DevOps CLI docs (ado-builds, ado-logs, ado-pr, ado-pr-threads) (#88)
- `mine.session-tools` skill — on-demand session management docs (claude-tmux, claude-log, claude-merge-settings) (#88)
- `mine.git-tools` skill — on-demand git helper docs (git-default-branch, git-rebase-onto) (#88)
- `mine.agent-patterns` skill — on-demand agent orchestration patterns (parallel execution, model selection, context passing) (#88)
- `evals/compliance/routing/` — 23 promptfoo routing eval tests (12 skill, 6 agent, 5 CLI tool) (#88)
- `researcher` agent — autonomous codebase research and feasibility analysis; launched by `mine.research` and `mine.design` instead of inline investigation phases (#85)

### Changed
- `capabilities.md` compressed from 23,256 to 6,042 chars (-74%) — pipe-delimited routing format, CLI docs moved to on-demand skills (#88)
- `agents.md` compressed from 11,483 to 2,786 chars (-76%) — pipe-delimited routing, agent patterns moved to on-demand skill (#88)
- `mine.research` refactored to thin interactive wrapper — gathers user intent (Phase 1), dispatches `researcher` agent (Phase 2), presents brief and asks next steps (Phase 3) (#85)
- `mine.design` Phase 2 now dispatches `researcher` agent instead of an inline general-purpose subagent prompt (#85)

## 2026-03-14

### Added
- `vx.visual-explainer` skill — generates self-contained HTML pages for diagrams, diff reviews, plan audits, data tables, and slide decks instead of ASCII art; commands: `/vx.generate-web-diagram`, `/vx.diff-review`, `/vx.plan-review`, `/vx.project-recap`, `/vx.generate-slides`, `/vx.generate-visual-plan`, `/vx.fact-check`, `/vx.share` (#86)
- `evals/` — promptfoo-based instruction compliance test suite; verifies Claude follows configured rules and tool preferences (gh helper scripts, dedicated file tools) (#82)

### Changed
- `code-reviewer` now runs in a loop before committing — auto-fixes unambiguous issues (bugs, type errors, style) and defers complex decisions to the user; `integration-reviewer` runs once after the loop on the final diff (previously both ran in parallel) (#83)

## 2026-03-13

### Added
- `integration-reviewer` agent — checks how new code fits the codebase: duplication, misplacement, convention drift, orphaned code, and design doc violations (caliper-aware) (#80)
- `code-reviewer` and `integration-reviewer` are now mandated to run in parallel before every commit (#80)

### Fixed
- `git-branch-log` and `git-branch-diff-stat` now compute the base branch by finding the closest remote branch (fewest commits ahead) instead of `@{upstream}` — fixes diffs in worktrees and fresh clones where no tracking branch is set (#78)

### Added
- Improved 7 existing agents with critical rules, severity calibration, success gates, and scope boundaries: `code-reviewer`, `ui-auditor`, `db-auditor`, `browser-qa-agent`, `visual-diff`, `planner`, `qa-specialist` (#76)
- 22 new agents imported from msitarzewski/agency-agents (MIT): engineering specialists (security, SRE, DevOps, AI, frontend, prototyper, technical writer, incident response), testing (API tester, performance benchmarker, reality checker, tool evaluator, workflow optimizer), specialized (MCP builder, agents orchestrator, model QA, developer advocate), design (UI designer, UX architect, UX researcher), and product (sprint prioritizer, feedback synthesizer) (#76)
- `design-visual-storyteller` agent — visual narratives, multimedia content, brand storytelling, and data visualization (from msitarzewski/agency-agents) (#79)
- `testing-reality-checker` adapted to use Playwright MCP instead of the upstream `qa-playwright-capture.sh` script (#76)

### Changed
- `gh-pr-reply` now accepts `--resolve <PRRT_...>` to reply and resolve a thread in one call (#81)
- `mine.draft-plan` now walks through each open question in the design doc interactively — presents options with a recommendation for each one, rather than a single "proceed or stop" prompt (#75)


## 2026-03-12

### Added
- `mine.worktree-rebase` skill — detects when a worktree's parent repo is currently on a feature branch and rebases onto it after confirmation (#74)

### Changed
- `mine.create-pr` now detects the related issue from the branch name and commit messages and appends `Closes #N` to the PR body automatically (GitHub only) (#73)
- `mine.issues` now reminds the user to include the issue number in their branch name when starting implementation, so `mine.create-pr` can link the issue automatically (#73)

### Fixed
- Pre-commit hook check now respects `core.hooksPath` (checked first) before falling back to `git-common-dir`; path used directly instead of via `xargs` to avoid space-breakage (#72)

### Added
- Pre-commit hook validation rule — before the first commit in a repo, Claude now checks for `.pre-commit-config.yaml`, verifies `pre-commit` is installed, and installs any missing hook types (handles multi-type configs correctly) (#72)

## 2026-03-11

### Changed
- Replaced `$CLAUDE_SESSION_ID` temp file paths with `get-skill-tmpdir` helper across all 13 skills — fixes collisions in concurrent sessions (#70)
- Code-reviewer agent is now mandatory before all commits, not just feature workflows (#70)
- Expanded `rules/common/agents.md` parallel execution guidance — subagent type selection, inline vs temp file output, foreground vs background, context passing, and standard phrasing for skills (#71)
- Added worktree safety rules to `rules/common/worktrees.md` — edit only worktree files, never run install.sh, use `git -C` (#71)
- Updated analysis skill handoffs to offer `/mine.build` caliper workflow: `mine.challenge`, `mine.audit`, `mine.brainstorm`, `mine.research`, `mine.tool-gaps` (#71)
- Added Path C (accelerated post-analysis caliper) to `mine.build` — detects prior analysis findings and offers shortened pipeline: skip specify, lightweight design (no research), then draft-plan → plan-review → orchestrate (#71)
- Removed `model: sonnet` pin from all 10 agent definitions — subagents now inherit the parent session's model instead of always running Sonnet (#71)
- Reduced interactive gates in caliper workflow: `mine.build` auto-continues between skill phases, `mine.orchestrate` auto-starts from first planned WP and auto-continues on PASS/WARN verdicts — only interrupts on failures or genuine ambiguity (#71)
- Added WARN accumulation checkpoint to `mine.orchestrate` — pauses after 3+ consecutive WARN verdicts to surface potential systemic issues (#71)

### Added
- `bin/get-skill-tmpdir` — create unique `claude-`-prefixed temp directories for skill runs via `mktemp -d` (#70)
- `claude-log grep <pattern>` — search bash commands across all sessions by regex with session/timestamp context; eliminates for-loops over `claude-log extract` (#69)
- `claude-log extract --bash --grep <pattern>` — filter extracted bash commands by regex within a single session (#69)
- `claude-merge-settings --inspect` — read-only summary of `permissions.allow`, `permissions.deny`, `allowedTools`, and `hooks` from the merged settings; no merge performed (#69)
- `mine.tool-gaps` Phase 2.5 — permission friction signal that classifies for-loop artifacts and multi-call batching as batch mode gaps rather than allow-list gaps (#69)
## 2026-03-10

### Added
- `mine.specify` skill — proportional discovery interview (1–2 questions for trivial features, 5+ for complex) + 12-item spec quality validation → `design/specs/NNN-slug/spec.md`
- `mine.wp` skill — WP lane management: `move`, `status`, `list` via `spec-helper`
- `mine.constitution` skill — guided interview that produces `.claude/constitution.md` for project-level constraint validation in `mine.design`
- `bin/spec-helper` — Python stdlib CLI for feature directory and WP management: `init`, `wp-move`, `status`, `next-number`

### Changed
- Replaced `get-tmp-filename` two-call pattern with session-ID-scoped fixed paths in `mine.commit-push`, `mine.ship`, `mine.create-pr`, `mine.design`, `mine.plan-review`, `mine.implementation-review`, `mine.orchestrate`, `mine.audit`, `mine.tool-gaps`, `mine.eval-repo`, `issue-refiner`, and `code-reviewer` — removes unnecessary Bash calls for use cases that only need a writable path (Write tool usage, not piped capture) (#68)
- Stripped `${CLAUDE_CODE_TMPDIR:-/tmp}` guard from all skill/agent/rule text; replaced with plain `/tmp` (guard is only preserved in `command-output.md` which explains `get-tmp-filename` behavior) (#68)
- `mine.build` — removed sophia Path C; simplified to Simple / Complex two-option routing; Complex path now starts with `mine.specify`
- `mine.design` — added constitution check, proportional planning interrogation (1–5+ architecture questions), and updated output path to `design/specs/NNN-slug/design.md`
- `mine.draft-plan` — generates `WP*.md` files (with frontmatter lane state + structured sections) instead of caliper `plan.md`; commits WPs after generation
- `mine.orchestrate` — removed sophia CR integration; reads `WP*.md` files; calls `spec-helper wp-move` on lane transitions; sub-prompts rewritten for WP section structure
- `mine.implementation-review` — rewritten for v2: accepts feature directory, reads `design.md` + WPs, updates `design.md` status on approve
- `mine.plan-review` — reviews `design.md` + WPs instead of `plan.md`; APPROVE gate directs to `mine.orchestrate` instead of sophia
- `mine.interviewer` — now an alias for `mine.specify`
- `mine.status` — adds terminal kanban section via `spec-helper status`

### Removed
- `mine.sophia` skill (sophia CR tracking removed from the pipeline entirely)
- `SOPHIA.yaml` from repo root

## 2026-03-09

### Fixed
- `settings.json` — `/tmp/*` permissions restored alongside `/tmp/**`; the previous upgrade accidentally dropped flat-file auto-approval (e.g. commit message and PR body temp files), causing two spurious permission prompts per ship (#64)

### Added
- `mine.build` skill — single entry point that routes a change request to simple direct implementation (explore → implement → code-review → ship) or the full caliper workflow (design → plan → review → orchestrate → implementation-review → ship), with optional sophia CR tracking (#66)
- `mine.orchestrate` skill — executes a caliper plan task-by-task with a three-subagent loop (executor, spec reviewer, quality reviewer); classifies deviations automatically and integrates with sophia CR tracking (#65)
- `mine.implementation-review` skill — post-execution quality gate using an Opus subagent across 7 categories (cross-task boundaries, duplication, dead code, docs, error handling, integration gaps, test coverage) (#65)
- `mine.interviewer` skill — structured interview skill that extracts full intent from a vague idea and produces a `spec.md` for the design pipeline; supports optional HTML wireframe generation for user-facing products (#63)
- `shellcheck` + `shfmt` pre-commit hooks and CI job (`shell-check`) to catch shell bugs and style drift automatically (#62)
- `.shellcheckrc` — targets bash, follows `source` calls (#62)
- `ruff` lint + format-check added to pre-commit hooks (complements existing CI coverage) (#62)

### Changed
- All bash scripts in `bin/` and `install.sh` reformatted to consistent 2-space indent style via `shfmt` (#62)

## 2026-03-08

### Fixed
- `mine.create-pr` no longer fails with a permission prompt on load — `||` fallback chains in `!` template expansions replaced by `git-branch-log` and `git-branch-diff-stat` helper scripts that handle remote/local fallback internally (#60)
- `settings.json` — `/tmp/*` permission globs upgraded to `/tmp/**` so files in subdirectories (e.g. eval-repo clones, sandbox tmp dirs) are auto-approved without prompts
- `bin/get-tmp-filename` — now uses `$CLAUDE_CODE_TMPDIR` when set (sandbox mode), falling back to `/tmp`; updated header comment to show correct two-call pattern instead of prohibited `$()`
- All `/tmp/` hardcodes in skills, agents, commands, and rules updated to `${CLAUDE_CODE_TMPDIR:-/tmp}` — covers `mine.brainstorm`, `mine.challenge`, `mine.audit`, `mine.eval-repo`, `mine.tool-gaps`, `mine.status`, `issue-refiner`, `code-reviewer`, `error-tracking`, `command-output`
- `install.sh` — parallel shadowed-file arrays replaced with an associative array (eliminates accidental cross-pairing; **requires Bash 4+**), `rm -rf` used for all shadowed targets (prevents crash under `set -e`), directory entries annotated before the `[y/N]` prompt, stale-link non-interactive block gains a header, prompts redirected to `/dev/tty` (#51)
- `install.sh` — `shadowed_containers` array separates true container dirs (`rules/<lang>`, `learned`) from ordinary dir symlinks (skills, agents, etc.); `shadowed` entries now always re-link inline with `ln -s` without a `[ -d ]` branch (#51)

### Added
- `bin/git-branch-log` — prints `git log --oneline` for current branch vs default, with remote/local fallback (#60)
- `bin/git-branch-diff-stat` — prints `git diff --stat` for current branch vs default, with remote/local fallback (#60)
- `install.sh` — post-install check warns if `pyright` is not found, with install instructions (`npm install -g pyright`) (#59)
- `mine.design` skill — scope a change, dispatch mine.research, write a design doc, gate on sign-off before planning (#61)
- `mine.draft-plan` skill — turn an approved design doc into a strict 5-field caliper implementation plan (#61)
- `mine.plan-review` skill — review a caliper plan with a subagent against a 6-point checklist, gate on approve/revise/abandon (#61)
- `mine.sophia` skill — sophia intent-tracking CLI integration for CR lifecycle, contracts, checkpoints, and validation (#57)
- `mine.skill-eval` skill — evaluate and compare skill variants with structured grading, blind A/B comparison, and statistical analysis (#57)
- `bin/sophia-install` — download and install the sophia binary with platform detection (#57)
- `bin/skill-eval-run`, `bin/skill-eval-aggregate` — run skill evaluation iterations and aggregate graded results (#57)
- `templates/SOPHIA.yaml.template` — reference template for sophia project configuration (#57)
- `rules/common/worktrees.md` — before any large multi-file task, detects if already in a worktree and pauses to offer `claude --worktree <branch>` vs. continue-in-place (#50)
- `rules/common/backlog.md` — new convention: analysis skills (audit, challenge, brainstorm) must save findings to a durable backlog before asking which to tackle; user chooses between `.claude/backlog.md`, GitHub issues, or a split; prevents findings from being lost to context compaction (#48)
- `rules/common/bash-tools.md` — new rule reinforcing when to use dedicated tools (Read/Write/Edit/Grep/Glob) vs Bash; covers permission cost, permission allow-list mismatches for quoted arguments (permission prompt / not auto-approved), and `sed -i` risk (#49)

### Changed
- `install.sh` — TTY-aware interactive cleanup: when run from a terminal, shadowed files and stale symlinks now prompt `[y/N]` instead of printing `rm` commands; non-interactive (piped/CI) behavior is unchanged (#51)
- `mine.audit` Phase 1 replaced flat 5-subagent approach with two-pass architecture: per-directory reconnaissance + cross-scope synthesis (#57)
- `agents/code-reviewer.md` — added Spec Verification section for verifying implementations against specifications (#57)
- `agents/planner.md` — added note about `/mine.draft-plan` for full caliper workflow (#57)

### Removed
- `mine.worktree`, `mine.start`, `mine.bare-repo` skills — superseded by `claude --worktree <branch>` + `--resume`; no plan file handoff needed (#50)
- `mine.tackle` command — its value was the worktree+handoff flow; without that it duplicates `/mine.issues` + plan mode (#50)
- `bin/setup-worktree`, `bin/git-convert-to-bare`, `bin/git-convert-to-bare-external` — no longer needed (#50)
## 2026-03-06

### Added
- `rules/common/frontend-workflow.md` — two new rules: scope expansion before UI changes (screenshot + sibling check + full plan before any implementation), and mandatory screenshots before any design review (UX audit, HCD, anti-pattern scan); single source of truth so individual skills don't repeat it
- `mine.ux-review` — scan target extended to include `.html`, `.jinja`, `.erb` templates in addition to tsx/jsx/vue/svelte
- `claude-log list --cwd <substring>` — filter sessions by working directory path; JSON output schema documented in `--help` (#46)
- `settings.json` — new portable allow entries (`ls`, `uv`, `claude-tmux`, `which`, `mine.commit-push`); `Bash(uv run python:*)` moved to `ask` list (#46)
- `mine.brainstorm` skill — open-ended idea generation with four parallel thinkers (Pragmatist, User Advocate, Moonshot Thinker, Wildly Imaginative); ideas deduplicated with convergence as signal; ranked by user-chosen criteria (feasibility, impact, originality, codebase fit, speed); handoffs to `/mine.research`, `/mine.adrs`, plan mode, or issue tracker (#45)
- `mine.challenge` skill — adversarial design critique with three parallel critics (Skeptical Senior Engineer, Systems Architect, Adversarial Reviewer); findings cross-referenced for confidence scoring (CRITICAL/HIGH/MEDIUM/TENSION); every claim requires file:line evidence; handoffs to `/mine.refactor`, `/mine.adrs`, or issue tracker (#44)

## 2026-03-05

### Removed
- `block-git-c.js` PreToolUse hook removed — `cd && git` compound commands now require a separate permission prompt, making `git -C <path>` the safer choice; `rules/common/git-workflow.md` updated accordingly (#43)

### Changed
- `settings.json` — `includeGitInstructions: false` removes Claude Code's built-in commit/PR workflow instructions; custom `rules/common/git-workflow.md` is now the sole source of truth (#42)

## 2026-03-02

### Changed
- `mine.create-pr` PR body format revised — changes grouped under `### H3` headers ordered most-to-least impactful; bullets explain *why* not just *what*; small standalone items collected under `### Notable Changes` (top) or `### Housekeeping` (bottom); design docs in `./design/` are referenced rather than re-summarized in the PR body (#41)

## 2026-03-01

### Fixed
- `mine.bare-repo` Convert-External is now a first-class detect-mode option — auto-routes on "external"/load-bearing mentions instead of requiring a nested prompt (#39)
- `git-convert-to-bare-external` now creates `<bare-path>/.bare/` as the git database with a `.git` pointer alongside (rather than making `<bare-path>/` itself the database root); recovery instructions updated with `core.bare false` step (#39)

### Added
- `claude-merge-settings` now detects runtime additions Claude Code wrote to `settings.json` during a session (new permissions, plugins, etc.) and offers to promote them to `settings.machine.json` so they survive future merges; `model` key is excluded (use `ANTHROPIC_MODEL` env var instead) (#40)
- `gh-pr-create`, `gh-issue`, `setup-worktree` scripts added to `bin/` — GitHub write operations now use bot token when available with personal token fallback; `mine.ship`, `mine.create-pr`, and `mine.tool-gaps` updated to use the wrappers; `setup-worktree` moved from Dotfiles into Claudefiles (#37)
- `git-convert-to-bare` and `git-convert-to-bare-external` scripts — convert existing repos to bare+worktree structure; external variant keeps the original path unchanged for load-bearing repos (symlinks, installed tools); `mine.bare-repo` skill updated with convert-external mode and nested-vs-external prompt (#37)
- `mine.tool-gaps` skill — surface missing CLI functionality and unscripted recurring patterns by mining session history for workarounds (#34)
- `agents/code-reviewer.md` extended to review Claude Code skill files — checks bash `$()` safety, frontmatter completeness, skill scope, and supporting file sync (#34)
- 8 new agents: `qa-specialist`, `architect`, `issue-refiner`, `db-auditor`, `dep-auditor`, `ui-auditor`, `browser-qa-agent`, `visual-diff` — sourced from awesome-copilot and undeadlist/claude-code-agents, adapted for Claude Code tool conventions (#35)
- `/mine.agnix` command and CI workflow (`agnix.yml`) that enforces agnix v0.14.0 validation on agent, skill, command, and CLAUDE.md files; `.agnix.toml` suppresses false-positive rules for this repo's naming conventions; `code-reviewer` and `mine.audit` now reference agnix organically (#35)
## 2026-02-28

### Changed
- Auto-allow `git` commands in permissions — eliminates frequent "manual approval required" prompts for basic git operations (#33)

### Fixed
- `block-git-c.js` hook no longer false-positives on "git -C" appearing inside commit messages, PR bodies, or quoted strings — now strips heredocs and string literals before matching (#33)
- Commit and PR skills use `git commit -F` and `--body-file` instead of `$(cat <<'EOF'...)` command substitution, which triggered extra permission prompts (#33)

## 2026-02-27

### Changed
- `install.sh` rules installation switched from whole-directory symlinks to file-level symlinks — allows Claudefiles and Dotfiles to contribute files into the same `~/.claude/rules/<lang>/` directory without conflict; added equivalent handling for `learned/` (#32)

## 2026-02-26

### Added
- Test execution discovery guidance in `common/testing.md` and `python/testing.md` — Claude now checks CI config, task runners, and project docs before running tests, reducing false positives from environment mismatches (#31)

## 2026-02-25

### Added
- `CLAUDE.md` Bash Tool Restrictions section documenting `$()`, backtick, and bare-pipe limitations with workarounds (#24)

### Changed
- `gh-pr-reply` and `gh-pr-resolve-thread` auto-use bot token when `gh-app-token` is installed and `GITHUB_APP_ID` is set; falls back to personal token otherwise (#27)
- `install.sh` warnings now print copy-pastable `rm` commands for each shadowed file and stale symlink
- `claude-tmux capture` accepts optional line count — `claude-tmux capture session 200` for deeper history (default remains 20) (#23)
- Added cross-pane monitoring docs to tmux rules — discover running processes with `panes`, grab their output with `capture` (#23)
- PR creation now uses draft→ready flow — changelog PR numbers are added before reviewers see the PR, eliminating the confusing second commit (#25)
- Switched `code-reviewer` and `planner` agents from Opus to Sonnet to reduce token usage (#29)

### Fixed
- Changelog check in `/mine.ship` and `/mine.commit-push` now requires an explicit file read instead of guessing, preventing false "no changelog" skips
- Eliminated `$()` command substitution from affected template expansions and Bash tool instructions to avoid eval wrapper bugs (#24)
- ADO helper scripts — fixed broken PR URLs, wrong auth format, hardcoded `master` default, missing API error handling; consolidated shared code into `ado-common.sh` (#26)
- `ado-common.sh` config parser truncated multi-word project names (e.g., "Analytics Platform" → "Analytics") — replaced `cut` with `sed` to capture the full value (#28)
- `ado-pr-threads resolve` now accepts `--pr PR_ID` flag and uses case-insensitive pattern matching (#26)
## 2026-02-24

### Changed
- Renamed `mine.address-pr-comments` → `mine.address-pr-issues` — now handles review comments, merge conflicts, and failing CI on both GitHub and Azure DevOps (#22)

### Added
- `tests/test_claude_log.py` — 86 unit tests for claude-log pure functions and helpers
- `.github/workflows/test.yml` — CI pipeline runs tests, lint, and format checks on PRs and pushes
- `bin/ado-builds` — Azure DevOps build management CLI for listing, canceling, and bulk-canceling pipeline builds (#18)
- `bin/ado-pr` — Azure DevOps PR helper with smart defaults for list, show, create, and update operations (#21)
- `bin/ado-pr-threads` — Azure DevOps PR thread operations for listing, replying, and resolving review threads (#21)

### Changed
- `agents/code-reviewer.md` — instruct code-reviewer to batch ad-hoc shell checks into a single temp script to reduce permission prompts (#19)
- `bin/claude-log` — deduplicated iteration pattern across 4 commands into shared `iter_session_files` generator; added input validation for `--since` and `--limit` flags

## 2026-02-23

### Added
- `mine.permissions-audit` command — analyze frequent permission prompts across sessions and recommend allow-list entries to reduce friction (#15)
- `install.sh` post-install diagnostics — warns about non-symlink files shadowing repo entries (e.g., a stale binary at `~/.local/bin/claude-log` preventing the symlink) and stale symlinks whose targets no longer exist (#15)
- `/mine.mutation-test` skill — Claude-driven mutation testing that intentionally breaks code to verify tests catch real bugs (#14)
- `command-output.md` rule — two-step pattern for preserving verbose command output in `/tmp` files to avoid re-running truncated commands (#9)
- `bin/get-tmp-filename` helper script — creates temp files for output capture, pre-allowed via `Bash(get-tmp-filename)` (#9)
- `bin/claude-merge-settings` — three-layer settings merge tool, configurable via `$CLAUDE_DOTFILES_SETTINGS` (#10)
- `bin/claude-log` — query Claude Code JSONL session logs with search, stats, skill/agent usage, and permission auditing (#13)

### Changed
- Replaced project-specific example name ("hassette") with generic "myapp" across docs and skills (#12)
- Clarified that the Dotfiles merge layer in `claude-merge-settings` is optional and silently skipped when missing (#12)

### Fixed
- `claude-tmux` no longer silently succeeds outside tmux — now reports "Not in tmux" so Claude stops attempting tmux operations (#11)

## 2026-02-22

### Changed
- `/mine.refactor` skill — replaced line-count metrics and numeric thresholds with holistic code reading throughout all phases (#7)

### Added
- `capabilities.md` rule — intent routing table and usage reference for all skills, commands, and CLI tools (#5)
- Automatic tmux session naming — Claude renames the tmux session at conversation start based on project and branch/task context (#4)
- `bin/claude-tmux` helper script — consolidates tmux operations (rename, current, new) behind a single pre-allowed tool (#4)
- `claude-tmux` list, panes, capture, and kill subcommands — eliminates raw tmux calls for session management (#6)

### Fixed
- Skill template parser error when `!` appeared in backticks (affected `/mine.ship` and `/mine.create-pr` ADO changelog instructions) (#4)

## 2026-02-21

### Added
- `/mine.eval-repo` skill — evaluate third-party GitHub repos before adopting them; assesses test coverage, code quality, maintenance health, bus factor, and project maturity with parallel subagents (#1)
- `CLAUDE.md` project instructions for repo contributors (#2)
- `bin/` directory with `gh-pr-threads`, `gh-pr-reply`, `gh-pr-resolve-thread` helper scripts (symlinked to `~/.local/bin` by installer) (#2)
- `settings.json` with hook wiring and default permissions for Claudefiles-owned tools (#2)

### Changed
- `/mine.create-pr` and `/mine.ship` now use `!` prefix for Azure DevOps PR references in changelogs (instead of `#`, which links to work items) and suggest adding a `CHANGELOG.md` if one doesn't exist (#3)
- `/mine.pre-compact` command now outputs a ready-to-paste `/compact` prompt instead of offering to run it (#2)

### Initial release
- Extracted shareable Claude Code configuration from personal dotfiles
- 18 skills: address-pr-issues, adrs, audit, backend-patterns, bare-repo, commit-push, create-pr, human-centered-design, interface-design, python-patterns, python-testing, refactor, research, security-review, ship, start, ux-antipatterns, worktree
- 10 commands: 5whys, capture_lesson, interface-design, issues-scan, issues, pre-compact, session_reflect, status, tackle, ux-review
- 2 agents: code-reviewer, planner
- 14 rules across common and Python domains (coding-style, testing, security, git-workflow, performance, error-tracking, hooks, patterns, agents)
- `install.sh` script for symlinking into `~/.claude/`
- `block-git-c.js` hook script
