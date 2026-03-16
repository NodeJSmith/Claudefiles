---
name: mine.challenge
description: "Use when the user says: \"challenge this design\", \"poke holes in this\", or \"what's wrong with this approach\". Adversarial design critique using three parallel critics. Assumes the design is wrong, finds out why, and argues for a better approach."
user-invokable: true
---

# Challenge

Adversarial design critique. This skill assumes the code under review is poorly designed and sets out to prove it. Three independent critics analyze from different angles, findings are cross-referenced for confidence, and every claim must cite evidence.

## How This Differs From Other Skills

| Skill | Question it answers |
|-------|-------------------|
| `mine.audit` | "What health problems does this codebase have?" |
| **`mine.challenge`** | **"Is this design actually correct?"** |
| `mine.refactor` | "How do I improve the structure of this code?" |
| `code-reviewer` | "Is this diff correct and safe to merge?" |

## Arguments

$ARGUMENTS — optional scope:
- File/path: `/mine.challenge src/services/user_service.py`
- Module/concept: `/mine.challenge "the auth module"`
- Empty: brief recon to find the most suspect design areas, then confirm scope before critiquing

## How to Analyze Code

Do NOT run tests, execute builds, install packages, run linters, or write throwaway analysis scripts.

DO read code directly (Read, Grep, Glob, `git log` / `git diff`). Use WebSearch to look up canonical descriptions of design patterns you recommend, or to cite documented failure modes — a "better approach" backed by a reference is stronger than one asserted without it.

## Phase 1: Gather Context

### If $ARGUMENTS given

1. Read the targeted file(s) fully
2. Grep for call sites and dependencies — understand what uses this code and what it uses
3. Note what problem this code ostensibly solves

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
- The code under review (file paths + key excerpts)
- Their persona and focus lens (described below)
- The path to write their report to
- These four rules:
  1. **Cite evidence for every claim** — no vague assertions:
     - For claims about this codebase, cite `file:line` for each point.
     - For external best practices, patterns, or failure modes, cite a canonical URL (via WebSearch).
  2. **Name the problem directly** — no hedging, no "this could potentially be improved"
  3. **Name a better approach** — either a design pattern, a concrete structural alternative, or "this belongs in X instead of Y"
  4. **Add one design question** — a question that forces the author to justify or reconsider the design

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

**Characteristic question**: *"What problem is this actually solving, and is this the right solution?"*

**Focus**:
- Wrong abstraction level — solving the wrong problem, or solving the right problem at the wrong place
- Wrong pattern entirely — there's a well-known design that fits this use case and this isn't it
- The design fighting against the user instead of with them (friction, workarounds, awkward call sites)
- Cases where the whole thing should be scrapped and replaced with something fundamentally different

## Phase 3: Synthesize

Read all three temp report files and merge findings.

**Confidence scoring based on agreement:**

| Agreement | Severity | Meaning |
|-----------|----------|---------|
| All 3 flagged it | CRITICAL | High-confidence fundamental flaw |
| 2 flagged it | HIGH | Serious concern, well-evidenced |
| 1 flagged it | MEDIUM | Valid concern, one perspective |
| Critics disagree on direction | TENSION | Surface both views — worth discussing |

Deduplicate findings that are the same problem framed differently. Preserve the sharpest phrasing.

**What to exclude**: Style, naming, formatting nits. Not design critiques — skip them.

## Phase 4: Present Findings

### Per-finding format

```
### [Issue name] — CRITICAL / HIGH / MEDIUM / TENSION

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
**The disagreement**: [Critic A argues X because Y. Critic B argues Z because W. Worth deciding which matters more here.]
```

### Save the backlog first

If there are 3 or more actionable findings, invoke the backlog save flow from `rules/common/backlog.md` before presenting the action options. Confirm what was saved, then proceed. If fewer than 3 findings, skip this step.

**Note:** If you created GitHub issues via the backlog save flow, skip the "Create issues for tracked concerns" option below — those findings are already tracked.

### After presenting findings

```
AskUserQuestion:
  question: "These are the design concerns I found. What would you like to do?"
  multiSelect: true
  options:
    - label: "Discuss a specific finding"
      description: "Go deeper on one concern — understand the tradeoffs"
    - label: "Hand off to /mine.refactor"
      description: "Structural fixes — rearrange the code within the current design"
    - label: "Build the fix (/mine.build)"
      description: "Direct implementation or full caliper workflow, depending on complexity"
    - label: "Record an architectural decision (/mine.adrs)"
      description: "Capture a significant design direction change"
    - label: "Create issues for tracked concerns"
      description: "File findings as issues to address later"
    - label: "Save the critique report"
      description: "Write the findings to design/critiques/"
    - label: "Read a specific critic's full report"
      description: "See the unfiltered reasoning from one critic (temp files listed below)"
```

When offering "Read a specific critic's full report", list the three temp file paths so the user knows where to look.

## Phase 5: Handoffs

**Structural fixes** → `/mine.refactor`

**Build the fix** → `/mine.build` — routes to direct implementation or the full caliper workflow based on complexity. Use when the finding needs new code, not just rearrangement.

**Architectural decisions** → `/mine.adrs`

**Track without acting** → create an issue in the project's issue tracker. Write the finding as the issue body:

```markdown
## Design Concern

<Direct statement of the problem>

## Evidence

- <file:line — specific citations>

## Consequence

<What happens if this is left as-is>

## Suggested approach

<Design pattern, structural alternative, or "move X to Y">

## Source

Identified during design critique on <date>.
Raised by: <which critics>
```

Use `gh-issue create` for GitHub projects.

**Save report** → `design/critiques/YYYY-MM-DD-<topic>/critique.md`

Include an appendix in the saved report with the three temp file paths for reference:

```markdown
## Appendix: Individual Critic Reports

These files contain each critic's unfiltered findings and are available for the duration of this session:

- Senior Engineer: <dir>/senior.md
- Systems Architect: <dir>/architect.md
- Adversarial Reviewer: <dir>/adversarial.md
```

## Principles

1. **Evidence or silence** — every claim must cite a specific file and line. No "this module is unclear" without pointing at exactly what's unclear and why.
2. **Direct** — name the problem, explain the consequence, move on. No hedging.
3. **The better way** — a critique without a direction isn't actionable. Every finding must name a pattern, approach, or structural alternative.
4. **Questions challenge, not embarrass** — the design question is there to surface assumptions, not score points.
5. **Ensemble = confidence** — findings backed by multiple critics carry more weight. Make that visible.
6. **Not a style guide** — naming, formatting, and style nits are not design critiques. Skip them.
