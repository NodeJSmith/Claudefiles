---
name: mine-define
description: "Use when the user says: \"spec this out\", \"help me define what I want to build\", \"interview me about this idea\", \"design this change\", \"write a design doc\", or needs to define WHAT and HOW to build something. Proportional discovery interview + codebase investigation → design.md."
user-invocable: true
---

# Define

Structured discovery and design skill. Turns a vague idea into a signed-off design.md through proportional questioning, codebase investigation, and architecture interrogation. Callable standalone or from `mine-build`.

## Arguments

$ARGUMENTS — optional initial description or path. Can be:
- A feature directory path: `/mine-define design/specs/001-user-auth/` (resumes from existing spec/design)
- A research brief path: `/mine-define design/research/2026-03-25-persistent-state/research.md`
- A feature idea: `/mine-define "add rate limiting to the API"`
- Empty: ask the user what they want to build

---

## Phase 1: Scope and Classify

### Branch staleness pre-flight

Before investigating the codebase, confirm the branch contains the latest default branch — designing against stale code produces a design with stale references that compound downstream (plan inherits them, then orchestrate). Read `${CLAUDE_CONFIG_DIR:-~/.claude}/references/common/staleness-preflight.md` and follow it in **soft** mode, with this stakes sentence: "Designing against stale code can carry into the plan and the run."

### Understand the initial request

If $ARGUMENTS points to a `design/specs/NNN-*/` directory, check for existing `design.md` and read it if present (the header fields — `**Status:**`, `**Scope-mode:**` — are needed for resume detection in later phases). If a `brief.md` from a prior `/mine-grill` session exists, read it and use its Key Decisions, Scope Boundaries, and Open Questions as starting context — skip any discovery questions the brief already answers.

If $ARGUMENTS is provided (text or path), paraphrase it back in one sentence to confirm understanding. If empty, ask:

```
AskUserQuestion:
  question: "What would you like to build or change?"
  header: "Define"
  multiSelect: false
  options: []
```

### Assess complexity

Classify the request as one of:
- **Trivial** — single-purpose utility, isolated change, no external dependencies, obvious scope. Requires 1–2 clarifying questions.
- **Moderate** — multi-component feature, some design decisions, limited integrations. Requires 3–4 clarifying questions.
- **Complex** — cross-system, platform-level, significant UX or data design, external integrations, security-sensitive, or high blast radius. Requires 5+ questions.

Do NOT share the classification with the user — use it only to calibrate how many questions to ask.

Derive a preliminary `<slug>`: a kebab-case identifier from the request (e.g. `user-auth`, `payment-flow`, `csv-export`). Maximum 40 characters.

### Initialize tracking

After deriving the slug:

1. If `$ARGUMENTS` pointed to an existing `design/specs/NNN-*/` directory, extract `NNN` and check whether cfl already has a row for it:

```bash
cfl spec status --spec <NNN>
```

- If this succeeds (spec data is returned), a spec already exists in cfl for this directory. Skip `cfl spec init`. Set the feature directory directly to the existing `design/specs/NNN-slug/` path — do not rely on `spec init` output, since it will not run. Set `<spec_number>` to `NNN`.
- If this errors with `spec_not_found`, the directory predates cfl tracking and cfl cannot currently adopt it: `cfl spec init` always assigns the next available number and creates a brand-new directory (`mkdir(exist_ok=False)`), so it cannot register this pre-existing `NNN` or reuse its directory. **Do not fall through to `cfl spec init <slug>`** — doing so would silently create an unrelated, wrongly-numbered duplicate directory. Instead, tell the user: "This directory predates cfl lifecycle tracking and can't be adopted automatically — proceeding without cfl tracking for this session." Continue the rest of Phase 1 using the existing directory as the feature directory. **No `<spec_number>` is set in this branch** — skip every `cfl` call for the remainder of this run (Phase 1's run-state step below, and all later dispatch/event/gate calls in Phases 2-6). Each of those sections below notes this same condition — re-check it before running any `cfl` command, since a resumed session may re-enter at any phase.

If `$ARGUMENTS` did not point to an existing spec directory, run:

```bash
cfl spec init <slug>
```

Record the `dir` field from the output as the feature directory and the `number` field as `<spec_number>`.

**Why `<spec_number>` must be threaded through:** `cfl` commands resolve the current spec from the working directory by default — they glob `design/specs/*/tasks/T*.md` first, falling back to bare `design/specs/*/` only when no repo-wide task files exist at all. A freshly created spec has no `tasks/` directory yet (that's created later by `mine-plan`), so it's invisible to that glob. If any *other* spec directory in the repo still has task files — a common state, not an edge case — CWD-based resolution silently attaches to that unrelated spec instead, misattributing this run's entire lifecycle history. Passing `--spec <spec_number>` on every subsequent `cfl` call removes the ambiguity. From here on, every `cfl run`, `cfl gate`, `cfl dispatch`, and `cfl event` call in this skill appends `--spec <spec_number>` (the one exception is `cfl dispatch end <id>`, which resolves entirely from the dispatch id and takes no `--spec`) — unless cfl tracking was disabled per the "predates cfl tracking" branch above, in which case all such calls are skipped instead.

2. Determine run state:

```bash
cfl run status --spec <spec_number>
```

- If the output has `"exists": true` — an active run exists. Resume it (no new run needed). Record the `run_id` for subsequent cfl calls.
- If the output has `"exists": false` — try resuming a stopped run:

```bash
cfl run resume --spec <spec_number>
```

If this succeeds, the stopped run is now active again with its original run_id and phase preserved. If it errors with `no_stopped_run`, create a new run:

```bash
cfl run start --phase define --base-commit $(git rev-parse --short HEAD) --spec <spec_number>
cfl event define.started --spec <spec_number>
```

---

## Phase 1.5: Codebase Reconnaissance (moderate+ only)

Read `${CLAUDE_CONFIG_DIR:-~/.claude}/skills/mine-define/recon-protocol.md` and follow it.

---

## Phase 2: Proportional Discovery

Read `${CLAUDE_CONFIG_DIR:-~/.claude}/skills/mine-define/interview-protocol.md` and follow it. The protocol covers structured questions, scope mode selection, adaptive follow-ups, completeness self-check, code leverage mapping, and convention examples checkpoint.

### Record discovery completion

Skip if cfl tracking was disabled in Phase 1 (no `<spec_number>` set).

```bash
cfl event define.discovery-complete --spec <spec_number>
```

---

## Phase 3: Investigate

### Check for an existing research brief

Before dispatching the researcher agent, check whether a research brief already exists for this topic:

1. If the user passed a research brief path (e.g., from `/mine-research` handoff), read it directly.
2. If a `design/specs/NNN-*/` directory exists for this feature, check for `research.md` inside it.
3. Glob `design/research/*/research.md` and scan for potential matches.

If a potential match is found, **always confirm with the user before reusing**:

> Found an existing research brief at `<path>`:
> - **Brief's proposal**: "<proposal text from the brief>"
> - **Current topic**: "<what the user is building>"
>
> Use this as prior work and skip investigation?

### Dispatch researcher (if no existing brief)

**Skip for trivial features** — codebase reconnaissance from Phase 1.5 is sufficient.

Run `get-skill-tmpdir mine-define-research` and use `<dir>/brief.md` as the research brief destination.

Before dispatching, record the dispatch. Skip this call (and the dispatch-end call below) if cfl tracking was disabled in Phase 1 (no `<spec_number>` set):

```bash
cfl dispatch researcher --agent-type researcher --model opus --spec <spec_number>
```

Record the `dispatch_id` from the output.

Launch `Agent(subagent_type: "researcher")` with this prompt:

```
Investigate a proposed change for a design document.

## Research Context
Proposal: <what was scoped>
Motivation: <why this change is being considered>
Flexibility: Decided
Constraints: <known constraints>
Desired outcome: <success criteria from Phase 2>
Non-goals: <explicit exclusions — omit if unknown>
Depth: <quick for Trivial changes, normal for Moderate/Complex>

Write your research brief to: <temp file path>
```

After the agent completes, **verify the output**: read the temp file and check that it exists and contains the `# Research Brief:` header. If missing or malformed, inform the user and offer to retry or proceed with manual investigation.

### Record researcher dispatch end

After the researcher subagent completes:

```bash
cfl dispatch end <dispatch_id>
```

Skip this section (and the dispatch record above) if the researcher was not dispatched (trivial features, or existing research brief reused) or if cfl tracking was disabled in Phase 1.

---

## Phase 3.5: Blind Spot Self-Assessment (moderate+ only)

Read `${CLAUDE_CONFIG_DIR:-~/.claude}/skills/mine-define/blind-spot-protocol.md` and follow it.

---

## Phase 4: Write design.md

### Write to the feature directory

The feature directory was created in Phase 1's "Initialize tracking" step. Write design.md to `<feature_dir>/design.md`.

### Design context check

If the work touches frontend (CSS, components, layouts, styles), check for design context:

- **`design/context.md` found:** Read it. If it has a Design Tokens section, apply the closed token layer — every CSS value must reference a token from the context file (no raw hex, no magic spacing numbers). State which tokens and decisions apply to this change.
- **`.impeccable.md` found** (migration fallback): Read it — use its brand personality and aesthetic direction for general decisions, but note there are no concrete design tokens. For non-trivial UI work, suggest running `/i-teach-impeccable` first to generate a full token set.
- **None found** and the work involves non-trivial UI: suggest "No design context found. Consider running `/i-teach-impeccable` first for consistent results."

### Write design.md

Read `${CLAUDE_CONFIG_DIR:-~/.claude}/skills/mine-define/design-template.md` and use it as the template. Populate each section from the research brief, discovery answers, and codebase reconnaissance. Be specific — reference actual file paths, class names, and patterns found during investigation.

### Record design doc written

After the design doc is written to disk. Skip if cfl tracking was disabled in Phase 1 (no `<spec_number>` set):

```bash
cfl event define.design-written --spec <spec_number>
```

---

## Phase 5: Quality Validation

Read `${CLAUDE_CONFIG_DIR:-~/.claude}/skills/mine-define/quality-checklist.md` and validate the design doc against it.

### Record quality gate

Skip if cfl tracking was disabled in Phase 1 (no `<spec_number>` set):

```bash
cfl gate define-quality --verdict <PASS|FAIL> --spec <spec_number>
```

Where verdict is PASS if all 20 checks passed, FAIL if any blocked.

---

## Phase 5.5: Fine-Toothed Comb Review

After the structured checklist passes and before sign-off, comb the design doc one more time. This is an open-ended pass — no checklist, no rubric — and it catches what a checklist can't: the doc reading as inconsistent, inaccurate, or thin once you take it in as a whole. It complements Phase 5, it does not replace it.

Before dispatching, record the dispatch. Skip this call (and the dispatch-end/gate calls below) if cfl tracking was disabled in Phase 1 (no `<spec_number>` set):

```bash
cfl dispatch define-comb --agent-type fine-toothed-comb --model sonnet --spec <spec_number>
```

Record the `dispatch_id` from the output.

Dispatch the `fine-toothed-comb` agent (see `${CLAUDE_CONFIG_DIR:-~/.claude}/agents/fine-toothed-comb.md`):

```
Agent:
  subagent_type: fine-toothed-comb
  model: sonnet
  prompt: |
    Read this design file: <design_doc_path>

    Go over it with a fine-toothed comb and make sure it's accurate, consistent, and thorough. Report anything you find.

    Define blocking as: a direct inconsistency or inaccuracy that would mislead planning or implementation. A section that could be more detailed is minor, not blocking — only flag a gap as blocking when the missing information has no reasonable default and would force the implementer to guess.
```

After the comb completes, record the dispatch end and the gate:

```bash
cfl dispatch end <dispatch_id>
cfl gate define-comb --verdict <v> --spec <spec_number> --data '{"blocking": <N>, "minor": <M>}'
```

Verdict mapping: no findings → PASS, minor findings accepted → WARN, blocking findings → FAIL.

### Comb gate

Read `${CLAUDE_CONFIG_DIR:-~/.claude}/skills/mine-comb/comb-gate.md` and apply it with:

- **`<header>`**: `Design comb`
- **`minor_blocks`**: `false` — minor findings are noted for sign-off but do not block
- **`<re_review_instructions>`**: apply the fixes to the design doc, then re-run this phase from the top

Phase 6 does not begin until the comb gate resolves. The "No findings" path proceeds to Phase 6 silently.

---

## Phase 6: Sign-Off Gate

Present the design doc path followed by the quality checklist results, then:

```
AskUserQuestion:
  question: "Design doc complete. What next?"
  header: "Sign-off"
  multiSelect: false
  options:
    - label: "Gap-close first"
      description: "Run /mine-gap-close on the design doc to fill completeness gaps"
    - label: "Approve — proceed to planning"
      description: "Hand off to /mine-plan to generate task files"
    - label: "Revise — I have changes"
      description: "Tell me what to change and I'll update"
    - label: "Save and stop"
      description: "Design doc saved as draft; pick it up later"
```

### Record sign-off gate

Skip both calls below if cfl tracking was disabled in Phase 1 (no `<spec_number>` set). Always record the gate:

```bash
cfl gate define-signoff --verdict <v> --spec <spec_number>
```

Verdict mapping:
- "Approve — proceed to planning" → PASS
- "Revise — I have changes" → WARN (loop continues; re-emit on each revision cycle)
- "Save and stop" → SKIPPED
- "Gap-close first" → no gate emitted (gap-close runs, then re-enters sign-off)

Only when the verdict is PASS (approved), also emit the sign-off event:

```bash
cfl event define.signed-off --spec <spec_number>
```

On Revise, Save-and-stop, or Gap-close, do **not** run the `cfl event` command above — no decision was finalized.

### On "Gap-close first"

Invoke: `/mine-gap-close <design-doc-path>`

After gap-close completes, loop back to the sign-off gate above.

### On "Approve"

Record the sign-off gate with verdict `PASS` and emit `cfl event define.signed-off` (see "Record sign-off gate" above).

Update design.md `**Status:**` from `draft` to `approved`.

**If invoked inline by `mine-build`** (the user chose "Full caliper workflow" or "Accelerated"), skip the gate below and invoke `/mine-plan <feature_dir>` directly — `mine-build` handles the flow.

**Otherwise**, ask:

```
AskUserQuestion:
  question: "Design doc approved. Proceed to generate task files?"
  header: "Next step"
  multiSelect: false
  options:
    - label: "Yes — generate task files"
      description: "Invoke /mine-plan for this feature"
    - label: "No — I'll do it later"
      description: "Stop here; design doc is saved"
```

If "Yes": invoke `/mine-plan <feature_dir>` directly.

### On "Revise"

Record the sign-off gate with verdict `WARN` (see "Record sign-off gate" above — no event emitted).

Ask what to change. Apply the edits to the design doc. Re-run the quality validation. Present for sign-off again.

### On "Save and stop"

Record the sign-off gate with verdict `SKIPPED` (see "Record sign-off gate" above — no event emitted).

Confirm: "Design doc saved as draft at `<feature_dir>`. Resume with `/mine-define` later."
