# Design: usability-check — experience evaluation for CLI and UI deliverables

**Date:** 2026-07-14
**Status:** draft
**Scope-mode:** hold
**Research:** ~/Dotfiles/design/research/2026-07-13-llm-ux-evaluation/research.md

## Problem

CLI tools and UI features pass all code review gates (code-reviewer, integration-reviewer, wtf-reviewer) but ship with poor user experience. The pipeline evaluates code correctness, not output quality. The motivating example: `dfl` — a CLI tool that passed every review but produced structlog key=value noise on every command, logged 58 "unchanged" lines when all links were up to date, gave no progress feedback during slow checks, and printed "dfl ready" instead of help on bare invocation. Four post-ship fix commits were needed to make the output usable.

The root cause: nobody runs the tool and evaluates what it actually prints. Code review reads source code, not terminal output. The gap exists at two pipeline stages — design docs don't include output mockups (so the executor has no experience reference), and post-execution review doesn't evaluate the running tool.

## Goals

- CLI tools built through the pipeline produce output that a human finds natural to read on first use — quiet on success, informative on action, progressive on slow operations
- UI features built through the pipeline match the visual intent from design mockups
- Usability problems are caught before PR creation — either at design time (experience artifacts) or post-execution (usability evaluation)
- The dfl failure class (spec-correct, experience-bad) is structurally prevented, not just documented as a risk

## User Scenarios

### Jessica: Dotfiles maintainer using the caliper pipeline

- **Goal:** build CLI tools and UI features that are pleasant to use
- **Context:** after mine-orchestrate finishes executing all tasks, before shipping

#### Post-execution usability evaluation (CLI)

1. **mine-orchestrate completes all tasks**
   - Sees: verdict table from impl-review, cross-file review, clean-code check
   - Then: pipeline detects the deliverable has CLI commands (from the design doc)

2. **Usability check runs automatically**
   - Sees: "Running usability check — evaluating CLI output for dfl link, dfl check, dfl install-services..."
   - Then: skill runs each command in representative scenarios, captures output

3. **Review findings (if any)**
   - Sees: findings like "dfl link: 58 lines of output when no changes needed — quiet success violated" or "dfl check --slow: no progress indication during 12-second execution"
   - Decides: address findings via fixer dispatch or defer
   - Then: if address, orchestrate dispatches a fixer subagent; if defer, note and continue

4. **Review output artifact**
   - Sees: markdown file showing each command's actual terminal output for representative scenarios (success, nothing-to-do, error, slow operation)
   - Decides: whether the output feels right as a human reader
   - Then: approve or request changes

#### Standalone usability evaluation

1. **Run `/mine-usability-check dfl`**
   - Sees: skill detects CLI entry points, runs commands, evaluates output
   - Then: findings presented with the output artifact

#### Design-time experience artifacts

1. **Run `/mine-define` for a CLI tool**
   - Sees: during the design interview, after architecture decisions, mine-define says "Before I finalize the design, let me draft what each command will actually print"
   - Then: terminal output mockups are included in the design doc's Experience Artifacts section

2. **Executor builds against the mockups**
   - Sees: the design doc shows exactly what `dfl link` should print when all links are up to date (nothing), when links are created (a summary line), etc.
   - Then: builds the output to match, not to satisfy a vague "structlog console renderer" spec

## Functional Requirements

- **FR#1** The standalone skill accepts a CLI command name, executable path, or URL as input. For CLIs, it discovers available subcommands (via `--help` parsing or design doc). For UI, it takes a URL or detects a running dev server.
- **FR#2** For CLI targets, the skill runs each discovered command in representative scenarios — success, nothing-to-do, error/invalid input, slow operation (if applicable), bare invocation (no args), and `--help` — capturing stdout, stderr, exit code, and wall-clock duration for each.
- **FR#3** For UI targets, the skill delegates to mine-visual-qa's Playwright screenshot infrastructure to capture the rendered interface.
- **FR#4** The skill evaluates captured CLI output against a rubric with these dimensions: quiet success (no noise when nothing changed), progress visibility (feedback during slow operations), bare invocation behavior (no args → help/usage), help quality (clear, complete `--help` output), error message actionability, output scannability (human-readable, not structured-log noise), and output consistency across subcommands.
- **FR#5** Evaluation uses subtraction-based personas — the evaluator is instructed as "a user encountering this tool's output for the first time, with no knowledge of the codebase, the design doc, or why the tool works the way it does." The persona lacks context, not capability.
- **FR#6** When a design doc with experience artifacts exists, the skill compares actual output against the mockups and flags divergence.
- **FR#7** The skill produces a findings report (blocking/note severity) and a separate output review file showing each command's actual terminal output under each scenario, formatted for human scanning.
- **FR#8** The skill reports findings only — it does not auto-fix. Fixing is handled by the caller (mine-orchestrate's fixer dispatch or the user).
- **FR#9** mine-orchestrate's post-execution pipeline includes a new step that detects whether the deliverable has a user-facing surface (from the design doc's user scenarios, functional requirements, and architecture — no formal classifier, just Claude reading the doc) and invokes `/mine-usability-check` if so.
- **FR#10** mine-define's design doc template evolves the "Visual Artifacts" section into "Experience Artifacts" — conditionally required when the deliverable has a user-facing surface. For CLIs: terminal output mockups showing what each command prints in representative scenarios. For UI: HTML mockups (via `/mine-mockup` or manual creation) or wireframe descriptions.
- **FR#11** If the CLI crashes or fails to run during evaluation, that is itself a finding (not a skill error) — reported as a blocking usability issue.

## Edge Cases

- **CLI not installed or not on PATH**: The skill checks whether the command is available before running. If not, it reports a blocking finding ("command not found") rather than erroring. For orchestrated builds, the tool should have been installed as part of the task execution.
- **CLI requires environment variables or secrets**: The skill runs in the same shell environment as the executor. If a command fails due to missing env vars, it's reported as a finding with the error output.
- **No experience artifacts in the design doc**: The skill runs the rubric evaluation without the comparison step. Findings are based on the rubric alone — no "diverges from mockup" findings.
- **Deliverable has no user-facing surface**: mine-orchestrate's detection reads the design doc and skips the usability step entirely. No overhead beyond reading the doc.
- **UI with no running dev server**: For UI targets, the skill checks for a running dev server (same port-scanning approach as mine-visual-qa). If none found, it reports that the UI evaluation was skipped with instructions to start the server and re-run.
- **Intentional structured output (--json mode)**: The rubric evaluates the default (human) output mode. If a command supports `--json`, the skill does not evaluate JSON output against human-readability criteria — `--json` is for machines.
- **Commands that modify state**: The skill runs commands normally by default — most CLI commands are safe to run (e.g., `dfl link` is idempotent). For state-modifying commands, the skill prefers `--dry-run` when available. Only truly destructive commands (data deletion, irreversible operations) are skipped with a note; the skill uses judgment based on what the command does, not a blanket rule.

## Acceptance Criteria

- **AC#1** Running `/mine-usability-check dfl` on the pre-fix dfl codebase (commit `a854211`) produces findings for at least: structlog key=value output noise, no quiet success on `dfl link`, no progress on `dfl check --slow`, and wrong bare-invocation behavior (FR#2, FR#4, FR#5)
- **AC#2** The output review file shows actual terminal output for each command in each scenario, formatted readably — verified by human inspection (FR#7)
- **AC#3** When a design doc with experience artifacts exists, divergence between actual output and mockups is flagged — verified by creating a mockup that doesn't match and running the skill (FR#6)
- **AC#4** mine-orchestrate's post-execution pipeline runs the usability check after the clean-code check (Step 4) for deliverables with user-facing surfaces, and skips it for library/internal-only deliverables — verified by running orchestrate on both types (FR#9)
- **AC#5** mine-define produces experience artifacts for CLI features — verified by running `/mine-define` on a CLI feature and checking the design doc contains terminal output mockups (FR#10)
- **AC#6** A CLI that crashes during evaluation produces a blocking finding, not a skill error (FR#11)
- **AC#7** All subcommands invoked with `--help` and bare (no args) as part of the scenario set (FR#2)
- **AC#8** The evaluation persona is subtraction-based — the evaluator prompt contains no reference to the design doc's rationale, implementation choices, or codebase context (FR#5)

## Experience Artifacts

### CLI output mockup example (what mine-define would generate for dfl)

```
$ dfl link
link complete: 58 unchanged

$ dfl link  (when changes exist)
  created: ~/.config/starship.toml
  replaced: ~/.gitconfig (backed up)
link complete: 1 created, 1 replaced, 56 unchanged

$ dfl check --slow
  checking mise versions...
  checking upstream repos...
  checking uv tool health...
  checking completions...
⚠ mise: mass 0.6.1 → 0.7.0 available
⚠ upstream: Dotfiles is 3 commits behind origin/main

$ dfl  (bare invocation)
Usage: dfl [OPTIONS] COMMAND

Unified Dotfiles management CLI.

Commands:
  link                Create and validate symlinks
  check               Run health checks
  install-services    Install systemd user services
  ...
```

This is the artifact mine-define would include in the design doc. The executor builds output to match this, and the usability check compares actual output against it.

## Key Constraints

- The standalone skill reports findings only — no auto-fix. The orchestrate pipeline's existing fixer dispatch pattern handles remediation.
- The evaluation persona must be subtraction-based (lacks context about the tool's internals), not adversarial (told to find flaws). Per the prior art research, adversarial framing produces performative bluntness without changing the underlying judgment.
- Do not use numeric scoring (0-5 per dimension). The research shows severity scoring is unreliable (near-zero inter-rater agreement). Use presence/absence detection: the issue exists or it doesn't.
- Do not evaluate `--json` output against human-readability criteria.

## Dependencies and Assumptions

- mine-visual-qa's Playwright infrastructure is available for UI evaluation (FR#3)
- CLIs to evaluate are installed and on PATH in the execution environment
- The skill runs in the same shell environment as the executor (access to the same env vars, PATH, working directory)
- mine-orchestrate's post-execution pipeline (post-execution-pipeline.md) is the integration point — the new step follows the existing gate pattern

## Architecture

### Standalone skill: `/mine-usability-check`

A new skill at `skills/mine-usability-check/SKILL.md` with a `REFERENCE.md` containing the CLI usability rubric.

**Phase 1: Detect surface and discover scenarios**

The skill determines the target type from its input:
- CLI command name or path → CLI evaluation
- URL → UI evaluation (delegates to mine-visual-qa flow)
- Design doc path → reads the doc to determine surface type and extract experience artifacts

For CLI targets, discover subcommands via `--help` parsing. For each subcommand, plan the scenario matrix:

| Scenario | What to run | Why |
|---|---|---|
| Bare invocation | `<cmd>` with no args | Should show help or usage, not crash or log noise |
| Help | `<cmd> --help` | Should produce clear, complete help text |
| Success | `<cmd> <valid-args>` | Normal operation — output should be clean and informative |
| Nothing-to-do | `<cmd>` when already done | Quiet success — minimal or no output |
| Error | `<cmd> <invalid-args>` | Error message should be actionable and go to stderr |
| Slow operation | `<cmd>` on something slow | Progress indication should be visible |

Not all scenarios apply to every command — the skill uses judgment based on what the command does.

**Phase 2: Execute and capture**

For each scenario in the matrix, run the command and capture stdout, stderr, exit code, and wall-clock duration. If a command supports `--dry-run`, prefer that for destructive operations. If a command crashes (non-zero exit on a success scenario), that's a finding, not a skill error.

Capture output to `<tmpdir>/captures/<cmd>-<scenario>.txt`.

**Phase 3: Evaluate**

Dispatch a single evaluation subagent (`model: sonnet`) with:
- The captured outputs from Phase 2
- The CLI usability rubric from REFERENCE.md
- The subtraction-based persona instruction
- Experience artifacts from the design doc (if available) for comparison

The evaluator reads each capture through the persona lens and scores each rubric dimension as PASS or ISSUE. For each ISSUE, it provides: the dimension violated, the specific output that triggered it, and a concrete description of what's wrong.

If experience artifacts exist, the evaluator also compares actual output to the mockups and flags material divergence (not cosmetic differences like exact whitespace, but structural differences like extra fields, missing summary lines, or different information hierarchy).

**Phase 4: Report**

Present findings as a prioritized list (blocking first, notes second). Generate an output review file at `<tmpdir>/output-review.md` showing each command's actual terminal output under each scenario, formatted with fenced code blocks and scenario labels.

For the user: present the findings inline, then note the output review file path for human inspection.

### CLI usability rubric (REFERENCE.md)

Dimensions derived from cli-output's anti-patterns list and the prior art research:

| Dimension | What it checks | dfl example |
|---|---|---|
| Quiet success | When nothing changed, output is minimal or silent | 58 "unchanged" lines logged |
| Progress visibility | Slow operations (>2s) show what's happening | `dfl check --slow` hung for 12s with no output |
| Bare invocation | No args → help/usage, not an error or noise | `dfl` logged "dfl ready" |
| Error actionability | Error messages say what went wrong and what to do | (not a dfl issue, but a rubric dimension) |
| Output scannability | Output is human-readable text, not structured-log key=value pairs | structlog `status=exists dry_run=False count=58 targets=[...]` |
| Consistency | All subcommands follow the same output conventions | (checked across the full command set) |
| Help quality | `--help` produces clear, complete, well-organized help text | (standard dimension) |

Each dimension in REFERENCE.md includes: the rule, why it matters, a PASS example, and an ISSUE example.

### mine-orchestrate integration

A new step in `post-execution-pipeline.md`, placed after the clean-code check (Step 4) and before the final review pass. The step:

1. Reads the design doc to determine if the deliverable has a user-facing surface (CLI commands, UI components, interactive features). This is judgment-based, not a classifier — Claude reads the design doc's User Scenarios, Functional Requirements, and Architecture.
2. If no user-facing surface: skip with a note ("no user-facing surface detected — usability check skipped").
3. If CLI: extract command names from the design doc, invoke `/mine-usability-check` with the command name.
4. If UI: invoke `/mine-usability-check` with the dev server URL (if available) or skip with a note.
5. Record the gate result via `cfl gate usability-check --verdict <PASS|WARN|FAIL>`. Verdict mapping: no findings → PASS, notes only (no blocking) → WARN, any blocking findings → FAIL.
6. If FAIL (blocking findings): present findings to the user with the standard "Address fixes" / "Stop here" gate. On "Address fixes", dispatch a fixer subagent with the findings (same pattern as impl-review and clean-code fixer dispatches).
7. If PASS or WARN: note any non-blocking findings and continue to the final review pass. The usability-check verdict is included in the Step 6 shipping gate summary alongside impl-review, cross-file, and clean-code results.

### mine-define experience artifacts

Evolve the "Visual Artifacts" section to "Experience Artifacts" with this behavior:

- After Phase 4 writes the design doc, mine-define checks whether the deliverable has a user-facing surface (from the User Scenarios and Architecture sections it just wrote). This is not a classifier — Claude already knows because it just wrote the doc.
- If CLI: generate terminal output mockups for each subcommand in representative scenarios (success, nothing-to-do, error, bare invocation). Include them in the Experience Artifacts section as fenced code blocks with `$ command` prompts.
- If UI: note that HTML mockups should be created (suggest `/mine-mockup`) or include wireframe descriptions. Link to any existing design context (`design/context.md`).
- If neither: omit the section (same as current behavior for Visual Artifacts when no visual references exist).

The section template becomes:

```markdown
## Experience Artifacts

[Required for deliverables with user-facing surfaces. For CLIs: terminal output mockups showing what each command prints in representative scenarios (success, nothing-to-do, error, bare invocation). For UI: HTML mockups or wireframe descriptions. Omit this section for libraries, internal modules, or refactors with no user-facing output change.]
```

## Implementation Preferences

- **Skill structure**: Follow mine-clean-code's pattern — SKILL.md with phases, REFERENCE.md for the rubric
- **Evaluation model**: Sonnet for the evaluation subagent (same as other review agents)
- **Persona approach**: Subtraction-based only. No adversarial framing ("find flaws"), no elaborate backstories. The persona instruction is: "You are encountering this tool's output for the first time. You have no knowledge of the codebase, the design document, or why the tool works the way it does. You do not know what structured logging is. Evaluate what you see."
- **Finding severity**: Two tiers only — blocking (must fix before ship) and note (worth considering). No numeric scores.
- **Output capture**: Temp files via `get-skill-tmpdir mine-usability-check`
- **No Artifact tool for CLI output review**. The output review file is a markdown file presented via SendUserFile or shown inline.

## Replacement Targets

No existing code is being replaced. This is purely additive — a new skill, a new pipeline step, and a template evolution.

## Convention Examples

### Skill frontmatter pattern

**Source:** `skills/mine-clean-code/SKILL.md`

```yaml
---
name: mine-clean-code
description: '"clean code check", "style review", "LLM smell check" — dispatches three parallel stylistic checkers and consolidates findings'
user-invocable: true
---
```

### Post-execution pipeline step pattern

**Source:** `skills/mine-orchestrate/post-execution-pipeline.md` (Step 4)

```markdown
## Step 4: Clean code check (automatic)

Record the dispatch and capture its ID:

\```bash
cfl dispatch clean-code-executor --agent-type general-purpose --model sonnet
\```

Launch a single `general-purpose` subagent with `model: sonnet`...

After the subagent completes:

\```bash
cfl dispatch end <dispatch_id>
\```

Record the gate result:

\```bash
cfl gate clean-code --verdict <PASS|WARN> --data '{"fixed": N, "unfixed": M}'
\```
```

### Rubric dimension pattern

**Source:** `skills-cli/cli-output/REFERENCE.md`

```markdown
## Progress Indication

**Rule:** Commands running >2s must show activity. Spinners, progress bars, or periodic status lines.

**Why:** A silent terminal during a 15-second operation feels broken. Users ctrl-C processes they think are hung.

**PASS:**
\```
$ dfl check --slow
  checking mise versions...
  checking upstream repos...
⚠ mise: mass 0.6.1 → 0.7.0 available
\```

**ISSUE:**
\```
$ dfl check --slow
[12 seconds of silence]
⚠ mise: mass 0.6.1 → 0.7.0 available
\```
```

### Subtraction-based persona pattern

**Source:** Prior art research — Automattic's "Roast Me"

The effective approach removes capabilities/context rather than adding backstory:

```
DO:  "You have no knowledge of the codebase or why this tool works the way it does."
DO:  "You do not know what structured logging is."
DO:  "You are seeing this output for the first time."

DON'T: "You are Sarah, a junior developer who just joined the team..."
DON'T: "Take an adversarial stance and find all the flaws."
DON'T: "Be brutally honest and don't hold back."
```

## Alternatives Considered

**Add a checklist item to mine-gap-close instead of evolving mine-define.** Gap-close would validate that experience artifacts exist after the design doc is written. Rejected: the user rarely runs gap-close these days — the comb pass covers more ground. The intervention needs to be where the work already happens (mine-define), not in an optional validation step.

**Auto-fix inside the standalone skill.** The skill would both detect and fix usability issues. Rejected: fixing is the orchestrate pipeline's job. The standalone skill reports; the pipeline dispatches a fixer. This matches the existing pattern (mine-clean-code reports, orchestrate Step 4 fixes) and keeps the skill simple.

**Adversarial prompt framing ("find every flaw").** The research shows adversarial framing produces performative bluntness without changing the underlying judgment — the model says "I'll be direct" but the review stays soft. Subtraction-based personas are more effective because they change what the model attends to, not just its tone.

**Numeric scoring (0-5 per rubric dimension).** The research shows severity scoring has near-zero inter-rater agreement. Presence/absence detection (issue exists or doesn't) is more reliable. Two-tier severity (blocking/note) is the right granularity — finer distinctions aren't trustworthy.

**Use the Artifact tool for CLI output review.** Rejected for CLI output — a markdown file or inline presentation is sufficient and simpler. The Artifact tool may be appropriate for UI evaluation results (rendered HTML side-by-side comparison) but is not required for this initial scope.

## Test Strategy

### Existing Tests to Adapt

No existing tests affected — this is purely additive.

### New Test Coverage

- The skill is a SKILL.md file (instructions), not code — there is no pytest suite to write. Verification is behavioral: run the skill against a known-bad CLI output and confirm it produces the expected findings (AC#1).
- The mine-define template change is validated by running `/mine-define` on a CLI feature and inspecting the output (AC#5).
- The mine-orchestrate integration is validated by running an orchestrated build with a user-facing deliverable and confirming the usability step fires (AC#4).

### Tests to Remove

No tests to remove.

## Documentation Updates

- **REFERENCE.md** — add mine-usability-check to the skills table under the appropriate category
- **rules/common/capabilities-core.md** — add trigger phrases for `/mine-usability-check`
- **ONBOARDING.md** — mention the new usability evaluation capability
- **rules/common/invariants.md** — add "Experience Artifacts for User-Facing Surfaces" to the Consider tier

## Impact

### Changed Files

- create `skills/mine-usability-check/SKILL.md` — the standalone skill
- create `skills/mine-usability-check/REFERENCE.md` — the CLI usability rubric
- modify `skills/mine-orchestrate/post-execution-pipeline.md` — add usability check step after Step 4
- modify `skills/mine-define/SKILL.md` — evolve Visual Artifacts to Experience Artifacts, add generation step after Phase 4 doc writing
- modify `REFERENCE.md` — add skill to the skills table
- modify `rules/common/capabilities-core.md` — add trigger phrases
- modify `rules/common/invariants.md` — add Consider-tier invariant

### Behavioral Invariants

- mine-define must continue to produce valid design docs for non-CLI, non-UI features — the Experience Artifacts section is omitted when no user-facing surface exists
- mine-orchestrate's post-execution pipeline must continue to work for deliverables with no user-facing surface — the usability step skips cleanly
- The standalone skill must not modify any files — it is read-only (captures to tmpdir, reports findings)

### Blast Radius

- All future orchestrated builds with user-facing deliverables will include a usability evaluation step
- All future mine-define runs for CLI/UI features will include experience artifact generation
- No existing skills or workflows are broken — this is purely additive
