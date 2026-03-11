---
name: mine.build
description: Smart build entry point — routes a change request to simple direct implementation or the full caliper v2 workflow based on complexity.
user-invokable: true
---

# Build

One command to go from idea to shipped code. Routes your request to the right workflow: implement directly for small changes, or engage the full pipeline (specify → design → draft-plan → plan-review → orchestrate → implementation-review → ship) for complex ones.

## Arguments

$ARGUMENTS — a description of the change to build. If empty, ask.

---

## Phase 1: Understand the Request

If $ARGUMENTS is non-empty, use it as the change description. If empty, ask the user directly:

> What would you like to build or change?

Wait for their reply and treat it as the change description.

Paraphrase the request back in one or two sentences to confirm understanding before proceeding.

---

## Phase 2: Route

### Detect prior analysis

Before routing, check whether the conversation already contains findings from an analysis skill or command (`/mine.challenge`, `/mine.audit`, `/mine.brainstorm`, `/mine.research`, `/mine.5whys`). Signals:

- Structured findings with severity labels (CRITICAL / HIGH / MEDIUM)
- A phased implementation plan produced by a planner agent
- Backlog items already saved to `.claude/backlog.md` or filed as issues
- Temp file reports from critic/thinker subagents

If prior analysis exists, the specify and research steps are already done — the findings are the spec, and the critique/audit is the research. Offer the **accelerated** path alongside the others.

### Complexity signal

- **Simple** — touches 1–3 files, clear approach, no design uncertainty, no cross-system impact
- **Complex** — touches multiple modules, has design uncertainty, crosses system boundaries, or has unclear implementation approach

### Present routing options

If **no prior analysis** detected:

```
AskUserQuestion:
  question: "How should we approach this? (Complexity signal: <Simple|Complex>)"
  header: "Workflow"
  multiSelect: false
  options:
    - label: "Simple — implement directly"
      description: "Explore, implement, code-review, then offer to ship"
    - label: "Complex — full caliper workflow"
      description: "specify → design → draft-plan → plan-review → orchestrate → implementation-review"
```

If **prior analysis detected** (findings, plan, or critique already in context):

```
AskUserQuestion:
  question: "Prior analysis detected — findings and/or a plan already exist. How should we proceed? (Complexity signal: <Simple|Complex>)"
  header: "Workflow"
  multiSelect: false
  options:
    - label: "Simple — implement directly"
      description: "Explore, implement, code-review, then offer to ship"
    - label: "Accelerated — skip specify, lightweight design phase"
      description: "Formalize findings into design.md (skip research — already done) → draft-plan → plan-review → orchestrate"
    - label: "Full caliper workflow"
      description: "specify → design → draft-plan → plan-review → orchestrate — start from scratch"
```

---

## Phase 3: Execute

### Path A — Simple: Implement Directly

Explore the codebase relevant to the request:

```
Glob: <relevant patterns based on the request>
Grep: <relevant symbols or keywords>
Read: <key files identified by Glob/Grep>
```

Implement the change. Follow the coding style and patterns in `rules/common/coding-style.md`.

Launch a `code-reviewer` subagent to review the implementation.

Present the code-reviewer's findings to the user (CRITICAL, HIGH, MEDIUM findings highlighted).

Then gate:

```
AskUserQuestion:
  question: "Implementation complete. What next?"
  header: "Ship or fix?"
  multiSelect: false
  options:
    - label: "Ship via /mine.ship"
      description: "Commit, push, and open a PR"
    - label: "Fix issues and re-review"
      description: "Address the reviewer's findings, then re-run the code-reviewer"
    - label: "Stop here"
      description: "Leave the changes uncommitted for now"
```

If "Fix issues and re-review": address CRITICAL and HIGH issues, then re-launch the code-reviewer subagent and present findings again. Offer the same gate.

If "Ship via /mine.ship": invoke `/mine.ship`.

---

### Path B — Complex: Full Caliper Workflow

Tell the user:

> Starting the full caliper workflow — each step has its own sign-off gate.

Then chain the following skills in sequence. Do not duplicate their logic — follow each skill's own phases as documented:

1. **Follow `/mine.specify` phases** for this request. Pass the change description as the argument. Wait for the user to approve the spec before proceeding. If the user saves and stops, stop here.

2. **Follow `/mine.design` phases** using the feature directory produced by mine.specify. Wait for the user to approve the design doc before proceeding. If the user abandons, stop.

3. **Follow `/mine.draft-plan` phases** using the feature directory from step 2. Wait for the WPs to be generated. If the user abandons, stop.

4. **Follow `/mine.plan-review` phases** for the design doc.
   - If APPROVE: continue to step 5.
   - If REQUEST_REVISIONS: return to step 3 (`/mine.draft-plan`) with the reviewer's notes. Repeat until APPROVE or ABANDON.
   - If ABANDON: stop.

5. **Follow `/mine.orchestrate` phases** using the feature directory. mine.orchestrate handles per-WP execution, deviation classification, lane updates, and its own post-execution handoff.

6. mine.orchestrate's Phase 3 post-execution handoff offers `/mine.implementation-review` inline. Follow that flow. If the user declines, offer the ship gate directly with a note that implementation-review was skipped.

7. After implementation review completes:
   - If **APPROVE**: proceed to the ship gate below.
   - If **REQUEST_FIXES**: surface the blocking issues. Tell the user to address them and re-run `/mine.orchestrate`, then `/mine.implementation-review`. Stop here.
   - If **ABANDON**: confirm abandonment and stop.

   Ship gate (on APPROVE):

```
AskUserQuestion:
  question: "Implementation reviewed and approved. Ship it?"
  header: "Ship?"
  multiSelect: false
  options:
    - label: "Yes — ship via /mine.ship"
      description: "Commit, push, and open a PR"
    - label: "No — I'll ship manually"
      description: "Stop here; changes are committed but not pushed"
```

If "Yes": invoke `/mine.ship`.

---

### Path C — Accelerated: Post-Analysis Caliper

Use this path when prior analysis (challenge, audit, brainstorm, research, 5whys) has already produced findings and/or a plan. The analysis serves as the spec and research — no need to redo that work.

Tell the user:

> Starting accelerated caliper workflow — skipping specify (findings are the spec) and using a lightweight design phase (skipping research — the critique already mapped the codebase).

Then chain the following steps:

1. **Lightweight `/mine.design`** — Follow mine.design's phases with these modifications:
   - **Phase 1 (Understand the Ask)**: Use the analysis findings as the problem statement. Skip scoping questions — the findings already define what's wrong, why it matters, and what the better approach is.
   - **Phase 2 (Investigate)**: **Skip entirely.** The analysis skill already explored the codebase. Do not dispatch mine.research as a subagent. Use the analysis findings as the research input for the design doc — no additional investigation needed.
   - **Phase 3 (Planning Interrogation)**: Run normally — ask proportional architecture questions to fill gaps the analysis didn't cover. Focus on approach alignment and interface contracts.
   - **Phase 4 (Write Design Doc)**: Run normally — write design.md using the analysis findings as the research brief. Populate the Problem section from the findings, Architecture from the recommended approaches, and Alternatives from any TENSION findings where critics disagreed.
   - **Phase 5 (Sign-Off Gate)**: Run normally — gate on user approval.

2. **Follow `/mine.draft-plan` phases** using the feature directory from step 1.

3. **Follow `/mine.plan-review` phases** for the design doc.
   - If APPROVE: continue to step 4.
   - If REQUEST_REVISIONS: return to step 2 with the reviewer's notes. Repeat until APPROVE or ABANDON.
   - If ABANDON: stop.

4. **Follow `/mine.orchestrate` phases** using the feature directory.

5. mine.orchestrate's Phase 3 post-execution handoff offers `/mine.implementation-review` inline. Follow that flow. If the user declines, offer the ship gate directly.

6. After implementation review completes:
   - If **APPROVE**: proceed to the ship gate below.
   - If **REQUEST_FIXES**: surface the blocking issues. Tell the user to address them and re-run `/mine.orchestrate`, then `/mine.implementation-review`. Stop here.
   - If **ABANDON**: confirm abandonment and stop.

   Ship gate (on APPROVE):

```
AskUserQuestion:
  question: "Implementation reviewed and approved. Ship it?"
  header: "Ship?"
  multiSelect: false
  options:
    - label: "Yes — ship via /mine.ship"
      description: "Commit, push, and open a PR"
    - label: "No — I'll ship manually"
      description: "Stop here; changes are committed but not pushed"
```

If "Yes": invoke `/mine.ship`.
