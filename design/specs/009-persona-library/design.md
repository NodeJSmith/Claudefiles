# Design: Extractable Persona Library for Subagent-Launching Skills

**Date:** 2026-03-29
**Status:** archived
**Research:** design/research/2026-03-29-persona-library/research.md
**Experiment data:** design/research/2026-03-29-persona-library/experiment-results.md

## Problem

mine.challenge hardcodes three generic critic personas (Senior Engineer, Systems Architect, Adversarial Reviewer) that run on every target regardless of domain. Experimental validation (2026-03-29) proved that domain-specialist critics surface real findings the generics miss:

- **Contract & Caller Critic** found 5 unique findings on a SKILL.md target (undocumented contract fields, caller coupling, hybrid caller categories)
- **Data Integrity Critic** found 3 unique bugs in Python async code (non-atomic deletes, partial batch writes, no job persistence)
- **Operational Resilience Critic** found 3 unique production risks (missing timeouts, thundering herd, no observability)

However, generics also catch structural/design issues (code duplication, coupling, API contracts) that all specialists missed. The answer is augmentation — always run generics, add specialists — not replacement.

## Non-Goals

- **No brainstorm/visual-qa extraction** — their "personas" are complete prompt templates with `[INSERT X]` placeholders, not focus lenses. Different pattern needed; separate PR.
- **No dynamic/LLM-based selection** — research shows automatic persona selection is unreliable across all tested approaches (PRISM paper, RoBERTa classifiers, LLM routing). Use deterministic target-type presets. The `--focus` flag uses deterministic slug matching, not semantic interpretation.
- **No speculative specialist personas** — only the 4 experimentally validated specialists ship in this PR.
- **No mine.audit integration** — future PR. If mine.audit needs the same personas, they can be extracted to a shared directory at that point (mechanical refactor).

## Architecture

### Persona file format

Each persona is a focus-lens file: YAML frontmatter + markdown body. The body contains the persona's identity, characteristic question, and focus bullets. No prompt templates, no `[INSERT X]` placeholders, no output format instructions. Skills construct their own prompts around the focus lens.

```markdown
---
name: Skeptical Senior Engineer
type: generic
---

**Persona**: Has seen this pattern fail in production. Not theorizing — remembering.

**Characteristic question**: *"What happens when this assumption is wrong?"*

**Focus**:
- Runtime risks and edge cases that aren't handled
- Assumptions that will eventually be wrong
- ...
```

Frontmatter fields:
- `name` (string, required): Display name
- `type` (enum, required): `generic` or `specialist`

No `domains` field — the SKILL.md mapping table is the single source of truth for which specialists serve which target types. Persona files are pure focus-lens content; they don't know which skills use them or when.

### Directory structure

Persona files live inside the skill directory, following the established companion-file pattern (orchestrate, plan-review, implementation-review):

```
skills/mine.challenge/
  SKILL.md
  personas/
    generic/
      senior-engineer.md
      systems-architect.md
      adversarial-reviewer.md
    specialist/
      contract-caller.md
      data-integrity.md
      operational-resilience.md
      workflow-ux.md
```

This follows the proven pattern: `skills/mine.orchestrate/` already has 5 companion `.md` files. No install.sh changes needed — the `skills/mine.challenge/` directory is already symlinked, so all files within it are accessible at `~/.claude/skills/mine.challenge/personas/`.

**Future extraction**: If mine.audit or another skill needs the same personas, extract `personas/` to a shared top-level directory at that point. This is a mechanical refactor — move files, update Read paths. YAGNI until a second consumer exists.

### Selection mechanism: target-type presets

mine.challenge already classifies targets into types (`code`, `spec`, `design-doc`, `brief`, `skill-file`, `research`, `other`). The new mapping table extends this classification to specialist selection:

| Target type | Specialist personas |
|-------------|-------------------|
| `code` | Data Integrity + Operational Resilience |
| `skill-file` | Contract & Caller + Workflow & UX |
| `design-doc` | Contract & Caller + Operational Resilience |
| `spec` | Workflow & UX |
| `brief` | Workflow & UX |
| `research` | _(none — generics only)_ |
| `other` | _(none — generics only)_ |

This is a static table in the SKILL.md. No glob, no tag matching, no LLM selection.

### Escape hatches

1. **`--focus` override**: If the user passes `--focus="data-integrity"` on a `spec` target (which normally wouldn't get the Data Integrity specialist), the skill matches the focus string against specialist filenames (deterministic slug match, not LLM judgment). Capped at 2 specialists total (5 total critics is the practical limit for synthesis quality — beyond that, findings overlap increases and synthesis becomes unreliable). If the cap is already full from preset defaults, the focus specialist replaces the second default.
2. **`--no-specialists` flag**: Explicitly skip specialist selection and run generics-only.
3. **Generics always run**: A bad specialist pick adds noise but doesn't lose coverage.

No interactive confirmation step. The preset table is deterministic — specialists are selected automatically based on target-type. Users who want generics-only pass `--no-specialists`.

### mine.challenge changes

**Phase 2 rewrite** — the core change:

1. Read 3 generic persona files from `~/.claude/skills/mine.challenge/personas/generic/` (Read)
2. Look up target-type in the mapping table → 0-2 specialist personas
3. If `--focus` was provided, match against specialist filenames (deterministic slug match). If a match is found and not already in the preset, add it (cap at 2; if full, replace the second default).
4. If `--no-specialists` was passed, skip steps 2-3.
5. Read selected specialist persona files from `~/.claude/skills/mine.challenge/personas/specialist/`
6. After reading persona files, verify each has `name` and `type` in frontmatter. Exclude malformed files with a warning.
7. Launch all critics in parallel (3-5 Agent calls in a single message)
8. Each critic receives: target files, target-type classification, focus lens from persona file, the shared rules (evidence, direct naming, proposed fix, tagging, design question, pushback, read beyond)
9. Generic critics write to `<tmpdir>/senior.md`, `<tmpdir>/architect.md`, `<tmpdir>/adversarial.md`
10. Specialist critics write to `<tmpdir>/<slug>.md` (e.g., `<tmpdir>/data-integrity.md`, `<tmpdir>/contract-caller.md`)
11. Remove inline persona definitions (current lines 213-252) — replaced by file reads

**Phase 3 synthesis update**:
- Read expected critic report files by name: `senior.md`, `architect.md`, `adversarial.md`, plus specialist slugs (e.g., `data-integrity.md`, `contract-caller.md`). Do NOT glob `*.md` — the tmpdir also contains `findings.md`. If an expected file is missing, note the missing critic in synthesis output.
- Confidence notation changes from `N/3` to `N/<total>` (see Output contract update below)
- `raised-by` tag includes specialist critic names when they contributed

**Phase 4 presentation update**:
- List all critic report file paths dynamically instead of hardcoded three

**Output contract update**:
- Remove `confidence` from the contract tag name list — it is presentation-only and no caller parses it. This frees the format to evolve (from `N/3` to `N/<total>`) without requiring caller updates.
- Document that specialist critic names may appear in `raised-by`
- Add `--no-specialists` to the recognized flags list
- No changes to severity, type, design-level, resolution, or findings file structure

### Prompt construction pattern

Each skill constructs its own prompt around the persona's focus lens. The persona file provides WHO the critic is and WHAT they focus on. The SKILL.md provides HOW to structure output, WHAT rules to follow, and WHAT target to review.

```
[Skill-specific preamble: target files, target-type, rules 1-7]

[Persona focus lens from file: identity, characteristic question, focus bullets]

[Skill-specific output instructions: write to tmpdir, finding format]
```

This separation is what enables future cross-skill reuse — if extracted to a shared directory, the same Data Integrity focus lens could work in mine.challenge (adversarial critique with findings taxonomy) and mine.audit (health scan with different output format).

## Alternatives Considered

### Shared top-level `personas/` directory

Put persona files in a new `personas/` directory at repo root, symlinked by install.sh.

**Deferred (not rejected)**: The only current consumer is mine.challenge. mine.audit compatibility is unvalidated (audit uses Explore subagents, not persona-based critics). Building shared infrastructure for a single consumer is premature. If a second consumer materializes, extracting from skill-local to shared is a mechanical refactor.

### Replace generics with specialists (pure selection model)

Pick 3 from a pool of 15 personas based on the target. No always-run generics.

**Rejected because**: The experiment proved generics catch structural/design issues that ALL specialists missed. The Systems Architect found code duplication, SQL coupling, and isinstance chains that no specialist surfaced. Replacement loses coverage; augmentation preserves it.

### LLM-based persona selection

Ask the model to pick the best specialists from the pool based on target content.

**Rejected because**: Research (PRISM paper, March 2026) shows automatic persona selection is unreliable — even trained RoBERTa classifiers performed no better than random. Target-type presets are deterministic, debuggable, and sufficient for the current pool size.

### Defer until concrete failure evidence

Wait until someone runs mine.challenge and demonstrably misses a domain-specific issue.

**Rejected because**: We already ran the experiment. The Data Integrity Critic found real bugs (non-atomic multi-table deletes, partial batch writes) that three generic critics missed across three independent runs. The evidence exists.

## Test Strategy

N/A — no test infrastructure in this repo. Manual verification:

- Run `/mine.challenge` against a Python file → verify Data Integrity + Ops Resilience specialists launch alongside generics
- Run `/mine.challenge` against a SKILL.md → verify Contract & Caller + Workflow & UX specialists launch
- Run `/mine.challenge --focus="data-integrity" some-spec.md` → verify Data Integrity specialist added despite `spec` target-type
- Run `/mine.challenge --no-specialists some-file.py` → verify only 3 generics launch
- Verify synthesis handles variable critic count (N/5 confidence notation)
- Verify a malformed persona file (missing `name:`) produces a warning and is excluded

## Open Questions

_(None — all questions resolved during research, experimentation, and challenge phases)_

## Impact

### Files modified
- `skills/mine.challenge/SKILL.md` — Phase 2 rewrite (specialist selection + persona file reads), Phase 3/4 updates for variable critic count, output contract update (remove `confidence` from contract tags, add `--no-specialists` flag)
- `CLAUDE.md` — mention persona companion files in "How the Pieces Connect"
- `README.md` — update mine.challenge description to mention specialist personas

### Files created
- `skills/mine.challenge/personas/generic/senior-engineer.md`
- `skills/mine.challenge/personas/generic/systems-architect.md`
- `skills/mine.challenge/personas/generic/adversarial-reviewer.md`
- `skills/mine.challenge/personas/specialist/contract-caller.md`
- `skills/mine.challenge/personas/specialist/data-integrity.md`
- `skills/mine.challenge/personas/specialist/operational-resilience.md`
- `skills/mine.challenge/personas/specialist/workflow-ux.md`

### Blast radius
- mine.challenge behavior changes (additional critics, automatic specialist selection by target-type)
- Confidence format evolves from `N/3` to `N/<total>` (removed from contract tag list — presentation-only)
- No install.sh changes (skill-local companion files)
- No changes to mine.brainstorm, mine.visual-qa, or mine.audit (out of scope)
