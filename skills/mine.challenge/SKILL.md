---
name: mine.challenge
description: "Use when the user says: \"challenge this design\", \"poke holes in this\", or \"what's wrong with this approach\". Adversarial design critique using three parallel critics. Assumes the design is wrong, finds out why, and argues for a better approach."
user-invocable: true
---

# Challenge

Adversarial design critique. This skill assumes the target under review is poorly designed and sets out to prove it. Three independent critics analyze from different angles, findings are cross-referenced for confidence, and every claim must cite evidence.

This skill produces **findings only**. It does not revise documents or apply fixes — that's the caller's job. When invoked from caliper workflow skills (mine.specify, mine.design), those skills handle revision planning after challenge completes.

## How This Differs From Other Skills

| Skill | Question it answers |
|-------|-------------------|
| `mine.audit` | "What health problems does this codebase have?" |
| **`mine.challenge`** | **"Is this design actually correct?"** |
| `code-reviewer` | "Is this diff correct and safe to merge?" |

## Arguments

$ARGUMENTS — optional scope:
- File/path: `/mine.challenge src/services/user_service.py`
- Module/concept: `/mine.challenge "the auth module"`
- Empty: brief recon to find the most suspect design areas, then confirm scope before critiquing

**Caller-provided argument**: `--findings-out=<path>` — when a calling skill (mine.design, mine.specify) invokes challenge, it passes a known output path for the findings file. Challenge writes `findings.md` to this path instead of to its own tmpdir. This lets the caller control the location without parsing output. When not provided, challenge creates its own tmpdir as usual.

## How to Analyze Code

Do NOT run tests, execute builds, install packages, run linters, or write throwaway analysis scripts.

DO read code directly (Read, Grep, Glob, `git log` / `git diff`). Use WebSearch to look up canonical descriptions of design patterns you recommend, or to cite documented failure modes — a "better approach" backed by a reference is stronger than one asserted without it.

## Finding Taxonomy

Every finding gets four tags: **severity**, **type**, **design-level**, and **resolution**.

### Severity (confidence-based)

| Agreement | Severity | Meaning |
|-----------|----------|---------|
| All 3 flagged it | CRITICAL | High-confidence fundamental flaw |
| 2 flagged it | HIGH | Serious concern, well-evidenced |
| 1 flagged it | MEDIUM | Valid concern, one perspective |
| Critics disagree on direction | TENSION | Surface both views — worth discussing |

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

- **Tag names**: `severity`, `design-level`, `resolution`
- **Severity values**: `CRITICAL`, `HIGH`, `MEDIUM`, `TENSION`
- **design-level values**: `Yes`, `No`
- **Resolution values**: `Auto-apply`, `User-directed`
- **Findings file**: `<tmpdir>/findings.md` or caller-specified path via `--findings-out` (structured summary, always written)

**Known callers** (update all when contract changes):

Structured callers (consume `--findings-out` and generate revision plans):
- `skills/mine.design/SKILL.md` — "On 'Challenge this design'" section
- `skills/mine.specify/SKILL.md` — "On 'Challenge this spec first'" section

Passthrough callers (invoke challenge standalone, don't consume findings file programmatically):
- `skills/mine.grill/SKILL.md`
- `skills/mine.research/SKILL.md`
- `skills/mine.brainstorm/SKILL.md`

## Phase 1: Gather Context

### Parse arguments

If `$ARGUMENTS` contains `--findings-out=<path>`, extract and store that path separately. The remainder of `$ARGUMENTS` is the target scope. If `--findings-out` is not present, challenge creates its own tmpdir for the findings file.

### If $ARGUMENTS given (after extracting --findings-out)

1. Read the targeted file(s) fully
2. If the target is a code file: grep for call sites and dependencies — understand what uses this code and what it uses
3. If the target is a document (spec.md, design.md, or other markdown): read related codebase files the document references, and any adjacent design artifacts in the same feature directory
4. Note what problem this code/design ostensibly solves

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

## Phase 2: Launch Three Parallel Critics

Before launching, create a unique temp directory for this run:

1. Run: `get-skill-tmpdir mine-challenge`
2. Note the directory path printed (e.g., `/tmp/claude-mine-challenge-a8Kx3Q`)

Subagents write their reports inside this directory:
- `<dir>/senior.md`
- `<dir>/architect.md`
- `<dir>/adversarial.md`

Launch all three as parallel Task calls with `subagent_type: general-purpose`. Each critic receives:
- The code under review (file paths to read — pass full file paths, not excerpts)
- Their persona and focus lens (described below)
- The path to write their report to
- These six rules:
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
  4. **Tag each finding** with type (Structural / Approach-now / Approach-later / Fragility / Gap) and design-level (Yes / No)
  5. **Add one design question** — a question that forces the author to justify or reconsider the design
  6. **Read beyond the provided files** — you have Read, Grep, and Glob access. Before writing your report, grep for call sites of the primary module/function under review and read at least two of them. Include a **Files examined** section at the top of your report listing every file you read. Don't limit your critique to what was handed to you.

Each critic writes their full, unfiltered findings to their temp file. These files persist for the session so the user can read any individual critic's reasoning after the skill completes.

### Critic 1: Skeptical Senior Engineer

**Persona**: Has seen this pattern fail in production. Not theorizing — remembering.

**Characteristic question**: *"What happens when this assumption is wrong?"*

**Focus**:
- Runtime risks and edge cases that aren't handled
- Assumptions baked into the design that will eventually be wrong
- "This worked until it didn't" failure modes
- Hidden state, shared mutable data, things that break under load or concurrency
- Coupling the original author didn't notice because it hasn't bitten them yet

### Critic 2: Systems Architect

**Persona**: Thinks in systems. Cares about coupling, change surfaces, and what breaks when requirements shift.

**Characteristic question**: *"When requirements change — and they will — what has to change with them?"*

**Focus**:
- Design boundaries where responsibilities have leaked across them
- Abstraction violations — things that know too much about their collaborators
- Hidden coupling (things that look independent but share a fate)
- Wrong layer — logic that lives at the wrong level of the system
- What breaks when a likely future requirement arrives

### Critic 3: Adversarial Reviewer

**Persona**: Hired to find the fatal flaw. Assumes the design is wrong until proven otherwise.

**Characteristic question**: *"Should this design exist at all — and if so, is this the right solution?"*

**Focus**:
- Wrong solution entirely — the problem statement is wrong, or the solution doesn't solve the actual user need
- Wrong pattern entirely — there's a well-known design that fits this use case and this isn't it
- The design fighting against the user instead of with them (friction, workarounds, awkward call sites)
- Cases where the whole thing should be scrapped and replaced with something fundamentally different

### Note on document targets

When the target is a spec.md or design.md rather than source code, critics analyze internal consistency, completeness, and design soundness rather than production failure modes. The "I've seen this fail" grounding comes from experience with designs that led to production problems, not from the code itself.

## Phase 3: Synthesize

Read all three temp report files and merge findings.

### Synthesis procedure

Follow this order strictly:

1. **Group by problem area** — cluster findings that address the same part of the system or the same concern
2. **Deduplicate within groups** — merge findings where the core issue is the same problem framed differently. Two findings are "the same problem" when they identify the same root cause in the same location, even if they emphasize different consequences. Preserve the sharpest phrasing. For document targets, "same location" means the same section AND the same design concern — two findings in the "Architecture" section that address different subsystems are not the same problem even if they share a section header.
3. **Assign severity** by post-merge contributor count (how many critics flagged the merged finding)
4. **Assign type** — compare across critics. When critics tagged differently, use the type that best describes the merged finding's root cause. For Approach timing conflicts (one critic says `now`, another says `later`), surface both: tag as `Approach-now/later` and add a **Timing disagreement** note in the finding body.
5. **Assign design-level** — when critics disagree, Yes wins (architectural concerns should surface, not be silently shelved)
6. **Assign resolution** — compare the structured `**Proposed fix**` sections across critics:
   - If fixes match (same action, same target, anchored to the same problem name): **Auto-apply** if the change is localized and additive; **User-directed** if it's large or structural
   - If fixes differ: **User-directed** — present the distinct options
   - If a critic's Proposed fix block is absent or malformed: treat as no fix proposal → **User-directed**
   - If ambiguous: **User-directed**
7. **Write a recommendation** for each User-directed finding — which option you'd pick and a one-sentence reason. **Exception**: for TENSION findings, replace the recommendation with a **Deciding factor** — one question or data point that would resolve the disagreement. Don't pretend to have a preference when the critics genuinely disagree on direction.

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
- **Severity**: CRITICAL / HIGH / MEDIUM / TENSION
- **Type**: Structural / Approach-now / Approach-later / Approach-now/later / Fragility / Gap
- **Design-level**: Yes / No
- **Resolution**: Auto-apply / User-directed
- **Raised by**: Senior + Architect / etc.
- **Summary**: <one-sentence description>
- **Better approach** (Auto-apply only): <the fix>
- **Options** (User-directed only, mutually exclusive with Better approach): <Option A: [approach] / Option B: [approach]>
- **Recommendation** (User-directed only): <which option and why. For TENSION: deciding factor>

## Finding 2: <name>
...
```

This file is written before Phase 4 presentation.

## Phase 4: Present Findings

### Per-finding format

```
### [Issue name] — SEVERITY
**Type**: [Structural / Approach-now / Approach-later / Fragility / Gap] | **Design-level**: [Yes / No] | **Resolution**: [Auto-apply / User-directed]

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

Always show all options. The action prompt is the same every time — no conditional hiding.

```
AskUserQuestion:
  question: "How would you like to proceed?"
  multiSelect: true
  options:
    - label: "Discuss a specific finding"
      description: "Go deeper on one concern — understand the tradeoffs"
    - label: "Save findings"
      description: "Save to .claude/backlog.md, create issues in your tracker, or write to design/critiques/"
    - label: "Read a specific critic's full report"
      description: "See the unfiltered reasoning from one critic"
    - label: "Done"
      description: "Challenge complete. findings.md is written. Continue your design/spec workflow, or handle findings directly."
```

When the user selects **"Save findings"**:

```
AskUserQuestion:
  question: "Where should findings be saved?"
  header: "Save to"
  multiSelect: false
  options:
    - label: "Backlog file"
      description: "Append to .claude/backlog.md"
    - label: "Issue tracker"
      description: "Create one issue per finding in the project's tracker"
    - label: "Critique report"
      description: "Write to design/critiques/YYYY-MM-DD-<topic>/"
```

Route accordingly: backlog file → invoke `rules/common/backlog.md` flow. Issue tracker → use the project's issue tracker (`gh-issue create` for GitHub, or whatever the project uses). Critique report → write to `design/critiques/`.

When the user selects **"Done"**, end the challenge skill. If a calling skill (mine.design, mine.specify) invoked challenge, it will resume and generate a revision plan from the findings file.

List the three temp file paths and the findings.md path so the user knows where reports are.

## Phase 5: Handoffs

**Save findings** — route based on user's choice:

**Backlog file** → invoke the backlog save flow from `rules/common/backlog.md`. Use the findings from the findings file as the source.

**Issue tracker** → create one issue per finding. Use the project's issue tracker (`gh-issue create` for GitHub, or whatever the project uses). Issue body format:

```markdown
## Design Concern
**Type**: [type] | **Design-level**: [Yes/No] | **Resolution**: [Auto-apply/User-directed]

<Summary from findings file>

## Evidence

<Evidence citations from the finding>

## Suggested approach

<For Auto-apply: the fix. For User-directed: options with tradeoffs and recommendation.>

## Source

Identified during design critique on <date>.
Raised by: <which critics>
```

**Critique report** → `design/critiques/YYYY-MM-DD-<topic>/critique.md`

Include an appendix in the saved report with the temp file paths for reference:

```markdown
## Appendix: Individual Critic Reports

These files contain each critic's unfiltered findings and are available for the duration of this session:

- Senior Engineer: <dir>/senior.md
- Systems Architect: <dir>/architect.md
- Adversarial Reviewer: <dir>/adversarial.md
- Structured findings: <dir>/findings.md
```

## Principles

1. **Evidence or silence** — every claim must cite a specific file and line. No "this module is unclear" without pointing at exactly what's unclear and why.
2. **Direct** — name the problem, explain the consequence, move on. No hedging.
3. **The better way** — a critique without a direction isn't actionable. Every finding must name a pattern, approach, or structural alternative.
4. **Questions challenge, not embarrass** — the design question is there to surface assumptions, not score points.
5. **Ensemble = confidence** — findings backed by multiple critics carry more weight. Make that visible.
6. **Not a style guide** — naming, formatting, and style nits are not design critiques. Skip them.
7. **Recommend, don't just present** — for User-directed findings, state which option you'd pick and why. The user overrides if they disagree. Exception: TENSION findings get a deciding factor instead, because honest uncertainty is more useful than a fabricated preference.
8. **Err toward user input** — when resolution classification is ambiguous, default to User-directed. The cost of asking is low; the cost of a wrong auto-apply is high.
9. **Findings only** — this skill produces findings. It does not revise documents, apply fixes, or manage workflow. The caller decides what to do with the output.
