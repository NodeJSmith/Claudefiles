# Changelog

All notable changes to this Claudefiles repository are documented here.

## 2026-03-19

### Fixed
- `AskUserQuestion` blocks in skills rendered as plain markdown bullets instead of interactive selectors — added CRITICAL rule to `interaction.md` enforcing tool calls with exact labels (#106)

### Added
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
