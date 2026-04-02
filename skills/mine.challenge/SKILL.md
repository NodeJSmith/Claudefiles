---
name: mine.challenge
description: "Use when the user says: \"challenge this\", \"poke holes in this\", or \"what's wrong with this approach\". Adversarial review using parallel critics (3 generics + 0-2 domain specialists). Assumes the target is wrong, finds out why, and argues for a better approach."
user-invocable: true
---

# Challenge

Adversarial review of any artifact — code, specs, designs, briefs, skill files. Assumes the target is wrong and sets out to prove it. Three generic critics always run; up to two domain-specialist critics are added based on target type. Findings are cross-referenced for confidence, and every claim must cite evidence.

This skill produces **findings only**. It does not revise documents or apply fixes — that's the caller's job. When invoked from caliper workflow skills (mine.specify, mine.design), those skills handle revision planning after challenge completes.

## How This Differs From Other Skills

| Skill | Stage | Question it answers |
|-------|-------|-------------------|
| `mine.grill` | Idea | "Have I thought this through?" |
| **`mine.challenge`** | **Artifact** | **"Is this approach actually right?"** |
| `code-reviewer` | Diff | "Is this diff safe to merge?" |
| `mine.audit` | Codebase | "What health problems does this codebase have?" |

## Arguments

$ARGUMENTS — optional scope:
- File/path: `/mine.challenge src/services/user_service.py`
- Module/concept: `/mine.challenge "the auth module"`
- Empty: brief recon to find the most suspect design areas, then confirm scope before critiquing

**Optional arguments**:
- `--focus="<area>"` — steer critics toward specific concerns (e.g., `--focus="security, error handling"`). Passed to all critics as a priority signal: "Pay special attention to X." Critics still review broadly but weight output toward the user's concern. **Note:** specialist override only applies when `--focus` is a single slug/prefix that matches a specialist name (e.g., `--focus="data-integrity"`), not when multiple comma-separated areas are provided.
- `--target-type=<type>` — override heuristic target-type classification. Callers that know their artifact type should pass this. Values: `code`, `spec`, `design-doc`, `brief`, `skill-file`, `research`, `other`.
- `--findings-out=<path>` — (structured callers only) deterministic output path for the findings file. Used by mine.design and mine.specify for reliable handoff. Not needed for standalone or passthrough invocations.
- `--no-specialists` — skip specialist selection, run only the three generic critics.

## How to Analyze

Do NOT run tests, execute builds, install packages, run linters, or write throwaway analysis scripts.

DO read directly (Read, Grep, Glob, `git log` / `git diff`). Use WebSearch to look up canonical descriptions of design patterns you recommend, or to cite documented failure modes — a "better approach" backed by a reference is stronger than one asserted without it.

## Finding Taxonomy

Every finding gets four contract tags: **severity**, **type**, **design-level**, and **resolution**, plus a **confidence** annotation (presentation-only). TENSION findings add three more: **side-a**, **side-b**, **deciding-factor**.

### Severity (impact-based)

Each critic assigns severity based on consequence — how bad is this if left unfixed?

| Severity | Meaning |
|----------|---------|
| **CRITICAL** | Fundamental flaw — the target cannot succeed as designed |
| **HIGH** | Serious problem — will cause real damage but the target isn't doomed |
| **MEDIUM** | Valid concern — worth fixing but won't cause failure |
| **TENSION** | Critics disagree on whether this is even a problem — surface both views for the user to decide |

**TENSION vs. fix disagreement**: TENSION means critics disagree on whether something is a problem at all (one says "this is broken," another says "this is fine"). If critics agree it's a problem but propose different fixes, that's NOT TENSION — use the highest severity and present the differing fixes as options in a User-directed finding.

During synthesis, the **highest severity any critic assigned** is used. Agreement count is recorded on a separate **confidence** line (e.g., `3/5 (Senior + Architect + Data Integrity)` or `1/4 (Senior only)`). This prevents novel findings from being deprioritized just because only one specialist spotted them. The `severity` field must be exactly one of `CRITICAL`, `HIGH`, `MEDIUM`, or `TENSION` — a single token with no parenthetical. Confidence is a separate, non-contract field.

### Type (what kind of problem)

Describes the nature of the finding — what's wrong, not where to fix it.

| Type | Meaning |
|------|---------|
| **Structural** | Boundary, coupling, or layering problem — system shape is wrong |
| **Approach** | The pattern or method is flawed — wrong abstraction, fighting the framework. Sub-tag with timing: `now` (wrong regardless of conditions) or `later` (will become wrong as requirements evolve or scale increases) |
| **Fragility** | Correct under happy-path conditions, will fail under specific operational stress — concurrency bugs, hidden state, race conditions, resource exhaustion, partial failures. Signals "fix before ship," not "revisit later" |
| **Gap** | Missing details, unhandled cases, spec holes, undefined behavior |

### Design-level (architectural scope)

Whether this finding is architectural/structural in nature — meaning it would require revisiting how the system was designed, not just how it was implemented. This is about the nature of the finding, not about whether a specific document exists.

| Value | Meaning |
|-------|---------|
| **Yes** | Architectural or structural — would require revisiting design decisions |
| **No** | Implementation-level — addressable during coding without design changes |

### Resolution (does the user need to decide?)

| Resolution | Meaning | How it appears |
|------------|---------|----------------|
| **Auto-apply** | One clear fix, localized and additive — safe to apply directly | "Here's the change" — approve or skip |
| **User-directed** | Multiple valid approaches, OR the fix is large/structural | "Here are the options, here's my recommendation" — you pick |

**Classification rules:**
- **Auto-apply** requires: (1) critics agree on both problem and fix, AND (2) the fix is localized — edits to a specific section, additive content, or wording changes. Not deletions, restructurings, or section rewrites.
- **User-directed** when: critics disagree on the fix, OR the fix involves deletion, restructuring, or rewriting a significant section — regardless of critic agreement.
- **When ambiguous, default to User-directed.** Err toward user input, not silent application.

## Output Contract

The following tag names and values are consumed by calling skills (mine.design, mine.specify) to generate revision plans. Changing these is a **breaking change** — update all callers.

- **Contract tag names**: `severity`, `type`, `design-level`, `resolution`, `raised-by`
- **Contract tag names (TENSION only)**: `side-a`, `side-b`, `deciding-factor`
- **Severity values**: `CRITICAL`, `HIGH`, `MEDIUM`, `TENSION`
- **Confidence format** (presentation-only, not a contract field): `N/<total> (<critic names>)` — e.g., `3/5 (Senior + Architect + Data Integrity)`. Total is the number of critics that successfully produced reports. If a critic fails to report, note the missing critic and reduce the denominator.
- **design-level values**: `Yes`, `No`
- **Resolution values**: `Auto-apply`, `User-directed`
- **Findings file**: `<tmpdir>/findings.md`, or `--findings-out` path when provided by structured callers (always written)

**Note**: Specialist critic names (e.g., Data Integrity, Contract & Caller) may appear in `raised-by` when specialists contributed to a finding.

**Known callers** (update all when contract changes):

Structured callers (read findings file and generate revision plans):
- `skills/mine.design/SKILL.md` — "On 'Challenge this design'" section
- `skills/mine.specify/SKILL.md` — "On 'Challenge this spec first'" section
- `skills/mine.orchestrate/SKILL.md` — Phase 3 Step 3 auto-challenge (dispatched as subagent with `--findings-out`)

Detection callers (scan for severity labels to detect prior analysis, don't read findings file):
- `skills/mine.build/SKILL.md` — accelerated path detection

Passthrough callers (invoke challenge standalone, don't consume findings file):
- `skills/mine.grill/SKILL.md`
- `skills/mine.research/SKILL.md`
- `skills/mine.brainstorm/SKILL.md`

**Caller guidance for TENSION findings**: Structured callers should route TENSION findings to the document's "Open Questions" section rather than generating revisions — TENSION means the critics genuinely disagree, so the user needs to decide.

## Phase 1: Gather Context

### Parse arguments

Extract optional flags from the **beginning** of `$ARGUMENTS` only. Once a non-flag token is encountered (no `--` prefix), treat all remaining text as the target scope — do not extract flags from within target content. This prevents passthrough callers' inline content from being misinterpreted as flags.

Recognized flags:
- `--findings-out=<path>` — deterministic output path (structured callers only)
- `--focus="<area>"` — critic focus steering
- `--target-type=<type>` — override heuristic classification
- `--no-specialists` — skip specialist selection, run generics only

The remainder of `$ARGUMENTS` is the target scope. If `--findings-out` is not present, challenge creates its own tmpdir for the findings file.

### If $ARGUMENTS given (after extracting flags)

1. Determine the **input shape**:
   - **File path or module name**: read the targeted file(s) fully
   - **Inline content** (multiple sentences or structured markdown): treat the argument text as the target to analyze directly — do not attempt to read it as a file. This happens when passthrough callers (mine.research, mine.brainstorm) pass content instead of a path.

2. **Classify the target type** — if `--target-type` was provided, use it directly. Otherwise, use heuristics. This classification is passed to critics in Phase 2:

   | Target type | Detected by | What critics focus on |
   |-------------|-------------|----------------------|
   | `code` | `.py`, `.ts`, `.js`, `.go`, etc. | Runtime failures, coupling, security, error handling |
   | `spec` | `spec.md` or content with requirements/acceptance criteria | Completeness, testability, internal consistency, scope gaps |
   | `design-doc` | `design.md` or content with architecture/API contracts | Feasibility, missing alternatives, boundary correctness |
   | `brief` | `brief.md` or content from grill/brainstorm | Framing validity, assumption quality, scope coherence |
   | `skill-file` | `SKILL.md` or content with phases/persona definitions | LLM behavior assumptions, prompt ambiguity, contract fragility, caller compatibility |
   | `research` | `research.md` or research artifacts/investigation output | Conclusion validity, exploration completeness, confirmation bias |
   | `other` | No type matches above | Correctness, assumption validity, internal consistency — critics use their general focus without type-specific narrowing |

3. **Gather context** based on target type:
   - **Code**: grep for call sites and dependencies — understand what uses this code and what it uses
   - **Document** (spec, design-doc, brief, research): read related codebase files the document references, and any adjacent artifacts in the same feature directory
   - **Skill file**: read all callers listed in the file, grep for additional references across the codebase
4. Note what problem the target ostensibly solves

### If empty

1. Quick recon: directory structure, recently changed files (`git log -n 10 --diff-filter=M --name-only --format= | sort -u`), largest files
2. Use `AskUserQuestion` to confirm the focus area before proceeding:

```
AskUserQuestion:
  question: "I've scanned the codebase. These areas look most suspect. Which should I critique?"
  header: "Focus area"
  multiSelect: false
  options:
    - label: "<area 1>"
      description: "<brief observation about why it looks suspect>"
    - label: "<area 2>"
      description: "<brief observation>"
    - label: "Let me specify"
      description: "I'll tell you exactly what to look at"
```

### Specialist Selection

After classifying the target type, select specialist personas to augment the three generic critics. Specialists provide domain-specific focus that generics are blind to.

**If `--no-specialists` was passed**, skip this section entirely — only generics run.

**Target-type → specialist mapping**:

| Target type | Specialist personas |
|-------------|-------------------|
| `code` | Data Integrity + Operational Resilience |
| `skill-file` | Contract & Caller + Workflow & UX |
| `design-doc` | Contract & Caller + Operational Resilience |
| `spec` | Workflow & UX |
| `brief` | Workflow & UX |
| `research` | _(none — generics only)_ |
| `other` | _(none — generics only)_ |

**`--focus` override**: If `--focus` was provided, match its value against specialist filenames in `~/.claude/skills/mine.challenge/personas/specialist/` using case-insensitive prefix matching on the filename slug (e.g., `--focus="data-integrity"` or `--focus="data"` matches `data-integrity.md`, but `--focus="integrity"` does not). If a match is found and not already in the preset selection, add it. Capped at 2 specialists total (5 total critics is the practical limit for synthesis quality). If the cap is already full from the preset, the focus specialist replaces the second preset default.

## Phase 2: Launch Critics

Before launching, create a unique temp directory for this run:

1. Run: `get-skill-tmpdir mine-challenge`
2. Note the directory path printed (e.g., `/tmp/claude-mine-challenge-a8Kx3Q`)

### Read persona files

Read all 3 generic persona files from `~/.claude/skills/mine.challenge/personas/generic/`:
- `senior-engineer.md`
- `systems-architect.md`
- `adversarial-reviewer.md`

If specialists were selected, read the corresponding files from `~/.claude/skills/mine.challenge/personas/specialist/` (e.g., `data-integrity.md`, `contract-caller.md`).

**Validate**: After reading each persona file, verify it has `name` and `type` in its YAML frontmatter, and the body contains at least one of "Persona", "Characteristic question", or "Focus". If a file is missing, has malformed frontmatter, or has an empty body, warn the user and exclude it from the run.

### Launch all critics in parallel

Subagents write their reports inside this directory:
- Generic critics: `<tmpdir>/senior.md`, `<tmpdir>/architect.md`, `<tmpdir>/adversarial.md`
- Specialist critics: `<tmpdir>/<slug>.md` matching the persona filename (e.g., `<tmpdir>/data-integrity.md`, `<tmpdir>/contract-caller.md`)

**CRITICAL: Issue ALL Agent tool calls (3-5 critics) in a single response message. Each call must use `subagent_type: general-purpose`, `model: sonnet`, and must NOT set `run_in_background`.** Foreground agents in the same message run concurrently. Background agents cannot request permissions and cannot spawn their own subagents — both are required here. Each critic receives:
- The target under review (file paths to read — pass full file paths, not excerpts; or inline content if the target was passed as text)
- The **target type** from Phase 1 classification (e.g., "This is a `spec` target — focus on requirement completeness, testability, and internal consistency")
- Their persona and focus lens (from the persona file read above — include the full body text: Persona, Characteristic question, and Focus bullets)
- If `--focus` was provided: "The user is specifically concerned about: <focus area>. Weight your analysis toward this concern."
- The path to write their report to
- These rules:
  1. **Cite evidence for every claim** — no vague assertions:
     - For claims about this codebase, cite `file:line` for each point.
     - For external best practices, patterns, or failure modes, cite a canonical URL (via WebSearch).
  2. **Name the problem directly** — no hedging, no "this could potentially be improved"
  3. **Propose a fix** using this structure (required for every finding). Anchor option descriptions to the finding's problem name for reliable cross-critic matching:
     ```
     **Proposed fix**:
     - Resolution: Auto-apply | User-directed
     - If Auto-apply: [one-sentence description of the specific change]
     - If User-directed: [Option A — Option B — key tradeoff between them]
     ```
  4. **Tag each finding** with severity (CRITICAL / HIGH / MEDIUM), type (Structural / Approach-now / Approach-later / Fragility / Gap), and design-level (Yes / No). Assign severity based on impact — how bad is this if left unfixed?
  5. **Add one design question** — a question that forces the author to justify or reconsider
  6. **Include a "Pushback" section** at the end of your report. For each finding raised by other critics (you won't see their reports, but anticipate likely concerns from the other critics), note any you would disagree with and why. If you think something another critic is likely to flag is actually fine, say so explicitly — e.g., "The coupling here is intentional because X." This gives synthesis the raw material to produce TENSION findings.
  7. **Read beyond the provided files** — you have Read, Grep, and Glob access. Before writing your report, grep for call sites of the primary module/function under review and read at least two of them. Include a **Files examined** section at the top of your report listing every file you read. Don't limit your critique to what was handed to you.

Each critic writes their full, unfiltered findings to their temp file. These files persist for the session so the user can read any individual critic's reasoning after the skill completes.

### Persona assignment

Each critic's identity and focus lens comes from the persona file read above. Pass the full body text (Persona, Characteristic question, Focus bullets) as part of the subagent prompt. The generic critics are:

- **senior-engineer.md** → writes to `<tmpdir>/senior.md`
- **systems-architect.md** → writes to `<tmpdir>/architect.md`
- **adversarial-reviewer.md** → writes to `<tmpdir>/adversarial.md`

Specialist critics (when selected) use their filename slug as the output name:

- **contract-caller.md** → writes to `<tmpdir>/contract-caller.md`
- **data-integrity.md** → writes to `<tmpdir>/data-integrity.md`
- **operational-resilience.md** → writes to `<tmpdir>/operational-resilience.md`
- **workflow-ux.md** → writes to `<tmpdir>/workflow-ux.md`

## Phase 3: Synthesize

Read all critic report files by expected name: `senior.md`, `architect.md`, `adversarial.md`, plus any specialist critics that were successfully launched in Phase 2 after validation (e.g., `data-integrity.md`, `contract-caller.md`). Do NOT glob `*.md` — the tmpdir also contains `findings.md`. If an expected file from this launched-critic set is missing, note the missing critic in synthesis output and adjust the confidence denominator.

### Synthesis procedure

Three steps. Prioritize trustworthy output over compact output — showing an extra finding is far cheaper than a bad merge or wrong tag.

1. **Group by problem area** — cluster findings that address the same part of the system or the same concern. List all critic perspectives for each group. Do NOT merge or deduplicate — if two critics flagged similar-but-distinct issues, keep both as separate findings. The user can mentally merge; they can't un-apply a wrong auto-apply.

2. **Assign tags per finding**:
   - **Severity**: take the highest severity any contributing critic assigned. Record agreement count on the separate confidence line (e.g., `3/5 (Senior + Architect + Data Integrity)` or `1/4 (Senior only)`).
   - **Type**: use the type that best describes the root cause. For Approach timing conflicts (`now` vs `later`), tag as `Approach-now/later`.
   - **Design-level**: when critics disagree, Yes wins (architectural concerns should surface).
   - **Resolution**: default to **User-directed** unless ALL critics proposed the same fix AND it's localized and additive — only then use **Auto-apply**. When in doubt, User-directed.

3. **Write a recommendation** for each User-directed finding — which option you'd pick and a one-sentence reason. **Exception**: for TENSION findings, replace the recommendation with a **Deciding factor** — one question or data point that would resolve the disagreement.

**What to exclude**: Style, naming, formatting nits. Not design critiques — skip them.

### Write findings file

After synthesis, **always** write the findings file. If `--findings-out=<path>` was provided, write to that path. Otherwise, write to `<tmpdir>/findings.md`. This file is the handoff contract for calling skills that generate revision plans.

Format:

```markdown
# Challenge Findings — <target>
Date: YYYY-MM-DD
Target: <file or scope>
Temp dir: <tmpdir>

## Finding 1: <name>
- severity: CRITICAL / HIGH / MEDIUM / TENSION
- confidence (non-contract): N/<total> (<which critics>) — e.g., "3/5 (Senior + Architect + Data Integrity)" or "1/4 (Adversarial only)"
- type: Structural / Approach-now / Approach-later / Approach-now/later / Fragility / Gap
- design-level: Yes / No
- resolution: Auto-apply / User-directed
- raised-by: Senior + Architect / etc.
- summary: <one-sentence description>
- better-approach (Auto-apply only): <the fix>
- options (User-directed only, mutually exclusive with better-approach): <Option A: [approach] / Option B: [approach]>
- recommendation (User-directed only): <which option and why. For TENSION: deciding factor>
- side-a (TENSION only): <Critic A argues X because Y>
- side-b (TENSION only): <Critic B argues Z because W>
- deciding-factor (TENSION only): <question or data point that would resolve the disagreement>

## Finding 2: <name>
...
```

This file is written before Phase 4 presentation.

## Phase 4: Present Findings

### Per-finding format

Findings MUST be numbered sequentially (`### 1.`, `### 2.`, etc.) for easy reference in conversation.

```
### N. [Issue name] — SEVERITY (confidence)
**Type**: [Structural / Approach-now / Approach-later / Approach-now/later / Fragility / Gap] | **Design-level**: [Yes / No] | **Resolution**: [Auto-apply / User-directed]

**What's wrong**: [Direct statement — no softening]
**Why it matters**: [Consequence if left as-is]
**Evidence (code)**:
- [file:line — one bullet per distinct assertion in What's wrong / Why it matters]
**References (external)** (optional):
- [Spec / RFC / canonical doc URL that supports this critique]
**Raised by**: [which critics — e.g. "Senior + Architect"]
**Better approach**: [Design pattern by name, concrete structural alternative, or "move X to Y"]
**Design challenge**: [One question that forces the author to justify or rethink this]
```

For TENSION findings, add:
```
**The disagreement**: [Critic A argues X because Y. Critic B argues Z because W.]
**Deciding factor**: [One question or data point that would resolve the disagreement]
```

For **User-directed** findings (non-TENSION), replace "Better approach" with:
```
**Options**:
- **Option A**: [approach] — *tradeoff: [what you gain / what you lose]*
- **Option B**: [approach] — *tradeoff: [what you gain / what you lose]*
**Recommendation**: [Option X] — [one-sentence reason]
```

### After presenting findings

If specialists ran, announce the selection before listing reports: "Specialists selected: [names] (target-type: [type])". If `--focus` caused a replacement, note it: "Note: [focus specialist] replaced [dropped preset] due to 2-specialist cap."

List all critic report file paths so the user knows where reports are. Always list the three generics, then any specialists that ran:

- Senior Engineer: `<tmpdir>/senior.md`
- Systems Architect: `<tmpdir>/architect.md`
- Adversarial Reviewer: `<tmpdir>/adversarial.md`
- _(if specialists ran)_ `<tmpdir>/<slug>.md` for each specialist (e.g., `data-integrity.md`, `contract-caller.md`)
- Structured findings: `<tmpdir>/findings.md` (or the path provided via `--findings-out`, if specified)

### Wrap-up: structured callers vs standalone

**If `--findings-out` was passed** (structured caller mode — used by mine.design, mine.specify, mine.orchestrate, or any caller requesting deterministic output): challenge is done. The caller resumes and generates a revision plan from the findings file.

**If challenge was invoked standalone** (user ran `/mine.challenge` directly): provide a wrap-up before stopping.

1. **Summary** — one paragraph: total finding count, breakdown by severity, the single most important takeaway across all findings.

2. **Next step** — ask which finding to address in this session (or whether the user wants to stop here).

**If a passthrough caller dispatched challenge** (mine.grill, mine.brainstorm, mine.research — no `--findings-out`): provide the summary (step 1) but skip the next-step prompt — the calling skill handles its own routing after challenge completes.

## Principles

1. **Evidence or silence** — every claim must cite a specific file and line. No "this module is unclear" without pointing at exactly what's unclear and why.
2. **Direct** — name the problem, explain the consequence, move on. No hedging.
3. **The better way** — a critique without a direction isn't actionable. Every finding must name a pattern, approach, or structural alternative.
4. **Questions challenge, not embarrass** — the design question is there to surface assumptions, not score points.
5. **Impact over consensus** — severity reflects consequence, not vote count. Agreement is reported as confidence, not importance. A CRITICAL finding from one specialist outranks a MEDIUM finding all three noticed.
6. **Not a style guide** — naming, formatting, and style nits are not design critiques. Skip them.
7. **Recommend, don't just present** — for User-directed findings, state which option you'd pick and why. The user overrides if they disagree. Exception: TENSION findings get a deciding factor instead, because honest uncertainty is more useful than a fabricated preference.
8. **Err toward user input** — when resolution classification is ambiguous, default to User-directed. The cost of asking is low; the cost of a wrong auto-apply is high.
9. **Findings only** — this skill produces findings. It does not revise documents or apply fixes. When invoked standalone, challenge provides a summary and asks which finding to address, but does not apply changes itself.
