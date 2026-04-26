---
name: mine.challenge
description: "Use when the user says: \"challenge this\", \"poke holes in this\", or \"what's wrong with this approach\". Adversarial review with triage-driven critic selection, parallel critics (1–3 on first run; max 2 on re-challenges). Assumes the target is wrong, finds out why, and argues for a better approach."
user-invocable: true
---

# Challenge

Adversarial review of any artifact — code, specs, designs, briefs, skill files. Assumes the target is wrong and sets out to prove it. A Haiku triage pass selects 1–3 critics best suited to the target; critics run in parallel and findings are synthesized, classified, and executed inline.

## Arguments

$ARGUMENTS — optional scope:
- File/path: `/mine.challenge src/services/user_service.py`
- Module/concept: `/mine.challenge "the auth module"`
- Empty: brief recon to find the most suspect design areas, then confirm scope

**Optional arguments** (extracted from the beginning of $ARGUMENTS only — stop at first non-flag token):
- `--focus="<area>"` — steer critics; also forces any specialist whose filename slug prefix-matches (≥6 chars, case-insensitive, single word only)
- `--target-type=<type>` — override heuristic classification. Values: `code`, `frontend-code`, `spec`, `design-doc`, `brief`, `skill-file`, `agent-file`, `rule`, `docs`, `research`, `other`
- `--findings-out=<path>` — deterministic output path (structured callers only, e.g., mine.define). Overwrites without warning.
- `--mode=passthrough` — present summary only; skip inline resolution (mine.brainstorm, mine.research)
- `--no-specialists` — triage selects from generic personas only
- `--cap=N` — finding cap (default 7). CRITICAL and HIGH are never capped.
- `--verbose` — show all findings including overflow

## How to Analyze

Do NOT run tests, execute builds, or write throwaway scripts.

DO use Read, Grep, Glob, `git log`/`git diff`. Use WebSearch to cite canonical patterns or failure modes.

## Finding Taxonomy

Every finding gets: **severity** (CRITICAL / HIGH / MEDIUM / TENSION), **type** (Structural / Approach-now / Approach-later / Fragility / Gap), **design-level** (Yes / No), **resolution** (Auto-apply / User-directed).

See `${CLAUDE_HOME:-~/.claude}/skills/mine.challenge/findings-protocol.md` for classification criteria, status/overflow fields, and the inline resolution flow.

## Phase 1: Triage

### Parse arguments and create tmpdir

Extract flags from $ARGUMENTS. Run `get-skill-tmpdir mine-challenge` — note the directory (e.g., `/tmp/claude-mine-challenge-a8Kx3Q`). All intermediate files live here.

### Read target and classify type

Determine the input shape and read the target:
- **File path**: read the file(s) fully
- **List file** (`.txt`/`.list`): read as newline-separated paths; skip blank/comment lines; record missing files to `<tmpdir>/validation-warnings.md`
- **Inline content** (multi-sentence markdown): treat as target text directly

Classify target type — use `--target-type` if provided, otherwise:

| Target type | Detected by |
|-------------|-------------|
| `code` | `.py`, `.go`, `.rs`, `.java`, `.ts`, `.js` (backend); mixed/repo-wide scope |
| `frontend-code` | `.tsx`, `.jsx`, `.vue`, `.svelte`, `.astro`; UI framework imports; dirs named `components/`, `pages/`, `hooks/` |
| `spec` | Standalone requirement docs outside caliper workflow |
| `design-doc` | `design.md`; architecture/API contract content |
| `brief` | `brief.md`; grill/brainstorm output |
| `skill-file` | `SKILL.md`; phases/persona definitions |
| `agent-file` | Files in `agents/`; `.md` with agent frontmatter |
| `docs` | `README.md`; `.md` in `docs/` directories |
| `research` | `research.md`; investigation output |
| `rule` | Files in `rules/`; convention/guideline definitions |
| `other` | Nothing matches |

### Re-challenge detection

Check for a prior challenge run before dispatching triage:
1. If `--findings-out` provided: check whether that file exists and starts with `# Challenge Findings` + `**Format-version:**`. If yes → re-challenge.
2. Otherwise: look for `challenge-results*.md` or `challenge-findings*.md` in the target's directory with the same validation check.
3. Fallback: if conversation context shows a prior challenge against this target → re-challenge.

Note re-challenge status in context for Phase 2 critic selection.

### Dispatch Haiku triage subagent

**Dispatch a single triage subagent** (`model: haiku`, `subagent_type: general-purpose`). Pass:
- Full target content (or file paths to read)
- Target type classification
- Re-challenge flag (`yes` / `no`)
- `--focus` value if provided
- `--no-specialists` flag if provided
- The persona catalog (name + one-line description from each frontmatter):

**Generics:**
- `senior-engineer.md` — Skeptical Senior Engineer: runtime risks, edge cases, security, operational blindness
- `systems-architect.md` — Systems Architect: abstraction violations, change amplification, data model problems
- `adversarial-reviewer.md` — Adversarial Reviewer: wrong solution entirely, UX failures, "should this exist?"

**Specialists:**
- `agent-definition.md` — Agent Definition Critic: agent file quality, executor compatibility, scope leakage
- `contract-caller.md` — Contract & Caller Critic: output schema fragility, breaking change surface, implicit contracts
- `data-integrity.md` — Data Integrity Critic: transaction safety, partial writes, cache/source-of-truth divergence
- `documentation-architect.md` — Documentation Architect Critic: doc set structure, mode confusion, findability gaps
- `end-user-reader.md` — End-User Reader Critic: assumed prerequisites, missing steps, error path silence
- `operational-resilience.md` — Operational Resilience Critic: resource exhaustion, upstream failures, recovery behavior
- `web-platform.md` — Web Platform Critic: re-renders, data fetching patterns, accessibility, CSS architecture
- `workflow-ux.md` — Workflow & UX Critic: phase transitions, unhelpful defaults, unnecessary friction

**Triage subagent instructions:** Return a JSON block with:
- `critics`: array of 1–3 persona filenames (e.g., `["senior-engineer.md", "contract-caller.md"]`)
- `rationale`: object mapping each filename to a one-sentence reason for selection
- `target_summary`: one sentence describing what the target does

**Triage rules:**
- If `--no-specialists`: select only from generics
- If `--focus` is a single word ≥6 chars that prefix-matches a specialist slug: always include that specialist
- If re-challenge (`yes`): select max 2 critics total
- Otherwise: select 1–3 critics; include at least one generic unless the target is highly specialized

Write triage JSON to `<tmpdir>/triage.md`. Parse the result in the orchestrator context.

### If empty $ARGUMENTS

Quick recon: directory structure, recently modified files (`git log -n 10 --diff-filter=M --name-only --format=`), largest files. Then:

```
AskUserQuestion:
  question: "I've scanned the codebase. These areas look most suspect. Which should I critique?"
  header: "Focus area"
  multiSelect: false
  options:
    - label: "<area 1>"
      description: "<why it looks suspect>"
    - label: "<area 2>"
      description: "<why it looks suspect>"
    - label: "Let me specify"
      description: "I'll tell you exactly what to look at"
```

## Phase 2: Critique

### Read selected persona files

For each persona filename from triage, resolve to the full path by searching `${CLAUDE_HOME:-~/.claude}/skills/mine.challenge/personas/generic/` then `personas/specialist/`. Verify each file has `name` and `type` in frontmatter and a non-empty body. Record validation issues to `<tmpdir>/validation-warnings.md` and exclude invalid files.

If the generic persona directory is missing or empty, stop with: "Cannot launch critics — persona files not found at `${CLAUDE_HOME:-~/.claude}/skills/mine.challenge/personas/generic/`. Run `uv run install.py`."

### Dispatch critics in parallel

**Issue ALL critic Agent tool calls in a single response message.** Each uses `model: sonnet`, `subagent_type: general-purpose`, NOT `run_in_background`. Each critic receives:
- Target content (file paths to read, or inline text)
- Target type and `target_summary` from triage
- Full persona content (Persona, Characteristic question, Focus bullets)
- Triage rationale for why this critic was selected
- Focus instruction if `--focus` was provided: "The user is specifically concerned about: <focus>. Weight your analysis toward this concern."
- If re-challenge: "This is a re-challenge after fixes were applied. Focus on: (1) whether the fixes were thorough, (2) whether fixes introduced new problems, (3) issues missed in the first round."
- Output path: `<tmpdir>/<persona-slug>-report.md`
- Critic rules:
  1. **Cite evidence for every claim** — `file:line` for codebase claims; canonical URL for external patterns
  2. **Name the problem directly** — no hedging
  3. **Propose a fix**: `Resolution: Auto-apply | User-directed` + one-sentence fix or options
  4. **Tag each finding**: severity (CRITICAL/HIGH/MEDIUM/TENSION), type, design-level
  5. **Structure each finding**: `**Why it matters**`, `**Evidence**`, `**References**` (if any), `**Design challenge**`
  6. **Include a Pushback section**: findings you anticipate other critics raising that you'd disagree with
  7. **Read beyond provided files**: use Read, Grep, Glob; include **Files examined** at top of report

After all critics complete, verify each output file exists and has ≥500 bytes. Record undersized/missing files to `<tmpdir>/validation-warnings.md`.

## Phase 3: Synthesize + Classify

**Dispatch synthesis as a separate subagent** (`model: sonnet`, `subagent_type: general-purpose`) for fresh context.

The synthesis subagent receives:
- All critic report paths (`<tmpdir>/<slug>-report.md` for each critic)
- Triage rationale and `target_summary`
- Target type
- Cap value (from `--cap`, default 7)
- Output path: `--findings-out` path if provided, otherwise `<tmpdir>/challenge-results.md`
- Contents of `<tmpdir>/validation-warnings.md` if it exists
- The full synthesis procedure below

**PRIMARY OBJECTIVE** (include as opening paragraph): You MUST write a findings file to `<output path>` using the Write tool before you finish. If you do nothing else, write that file.

**Synthesis procedure:**

1. **Read all critic reports in full** — do not glob; read each named file explicitly
2. **Group by problem area** — cluster findings addressing the same concern. Keep similar-but-distinct issues separate.
3. **Assign tags per finding:**
   - `severity`: highest severity any critic assigned (must be CRITICAL / HIGH / MEDIUM / TENSION — reclassify non-contract values as MEDIUM)
   - `type`: type best describing the root cause
   - `design-level`: Yes wins when critics disagree
   - `resolution`: Auto-apply only when ALL critics agree on the same fix AND it's localized and additive AND severity is not CRITICAL. Otherwise User-directed. When ambiguous, default User-directed.
   - `status`: `pending` for all in-cap findings; `overflow` for findings beyond the cap
   - `overflow`: `false` for in-cap findings; `true` for findings beyond the cap
4. **CRITICAL guard**: CRITICAL findings MUST always be classified as `resolution: User-directed` regardless of the resolution field from any critic or agreement level. This is a non-negotiable override — do not classify any CRITICAL finding as Auto-apply under any circumstances.
5. **Cap enforcement:**
   - CRITICAL and HIGH: always included, never overflow
   - TENSION: overflow if any CRITICAL or HIGH findings exist
   - MEDIUM: include up to `max(3, cap - CRITICAL_count - HIGH_count)` MEDIUMs; remaining are overflow
6. **Copy presentation fields** from critic reports: `why-it-matters` (most concrete consequence statement), `evidence` (all file:line citations, deduped), `references` (all URLs), `design-challenge` (strongest question). Write `not cited` for evidence when none; omit other fields when absent.
7. **Write recommendation** for each User-directed finding (which option and why). For TENSION: write deciding-factor instead.

**Write findings file** to the output path using `Format-version: 3` header. Format per `${CLAUDE_HOME:-~/.claude}/skills/mine.challenge/findings-protocol.md`.

**After synthesis subagent completes:** Verify the findings file exists at the output path. If missing (subagent returned text instead of writing), extract findings from the returned text: if it starts with `# Challenge Findings` and contains `**Format-version:**` write as-is; if it contains `## Finding` headings inject the header block then write; otherwise stop with "Error: synthesis subagent did not produce findings in a writable format — re-run `/mine.challenge`."

## Phase 4: Execute

Read the findings file. Announce: "Specialists selected: [names from triage]" and note re-challenge if applicable. For each critic excluded by validation, announce the exclusion before findings.

**If `--mode=passthrough`**: present a one-paragraph summary (count by severity, top takeaway). Return. Do not execute anything.

**If `--findings-out` provided (structured mode)**: auto-apply all `resolution: Auto-apply, status: pending` findings directly via Edit tool. Update `status: applied` in findings file for each. Skip interactive prompts. Write "Challenge complete — findings written to `<path>`. Returning to caller." Return.

**If standalone mode** (direct user invocation, mine.grill caller):

Read and follow the Inline Resolution Flow in `${CLAUDE_HOME:-~/.claude}/skills/mine.challenge/findings-protocol.md` exactly. After all findings are processed, report: "Applied N findings. M skipped. K overflow (use `--verbose` to see all)." List critic report paths and findings file path.

If `--verbose`: also present overflow findings (status: overflow) after the main flow, labeled as "Additional findings (beyond cap)".

## Principles

1. **Evidence or silence** — every claim must cite a specific file and line
2. **Direct** — name the problem, explain the consequence, move on
3. **The better way** — every finding must name a pattern, approach, or structural alternative
4. **Impact over consensus** — severity reflects consequence, not vote count
5. **Err toward user input** — ambiguous resolution → User-directed
6. **CRITICAL → always user-directed** — no exceptions

## Known Callers

Structured callers (pass `--findings-out`, read findings file per `${CLAUDE_HOME:-~/.claude}/skills/mine.challenge/caller-protocol.md`):
- `skills/mine.define/SKILL.md`

Passthrough callers (pass `--mode=passthrough`):
- `skills/mine.research/SKILL.md`
- `skills/mine.brainstorm/SKILL.md`

Standalone callers (full inline resolution flow):
- `skills/mine.grill/SKILL.md`
- `skills/mine.gap-close/SKILL.md`

Inline-revision callers (invoke challenge, read findings in-context, revise own proposal):
- `skills-impeccable/i-adapt/SKILL.md`, `skills-impeccable/i-animate/SKILL.md`, `skills-impeccable/i-bolder/SKILL.md`
- `skills-impeccable/i-clarify/SKILL.md`, `skills-impeccable/i-colorize/SKILL.md`, `skills-impeccable/i-delight/SKILL.md`
- `skills-impeccable/i-distill/SKILL.md`, `skills-impeccable/i-harden/SKILL.md`, `skills-impeccable/i-layout/SKILL.md`
- `skills-impeccable/i-overdrive/SKILL.md`, `skills-impeccable/i-optimize/SKILL.md`, `skills-impeccable/i-polish/SKILL.md`
- `skills-impeccable/i-quieter/SKILL.md`, `skills-impeccable/i-typeset/SKILL.md`

Detection callers (scan for severity labels, don't read findings file):
- `skills/mine.build/SKILL.md`

To find all callers: `grep -r 'CHALLENGE-CALLER' ${CLAUDE_HOME:-~/.claude}/skills/ ${CLAUDE_HOME:-~/.claude}/skills-impeccable/ --include='*.md' -l`
