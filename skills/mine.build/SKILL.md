---
name: mine.build
description: "Use when the user says: \"build this\", \"implement this\", \"make this change\", or \"start a feature\". Smart entry point that routes to direct implementation or the full caliper v2 workflow based on complexity."
user-invocable: true
---

# Build

One command to go from idea to shipped code. Routes your request to the right workflow: implement directly for small changes, or engage the full pipeline (specify → design → draft-plan → plan-review → orchestrate → ship) for complex ones.

## Arguments

$ARGUMENTS — a description of the change to build. If empty, ask.

---

## Phase 1: Understand the Request

If $ARGUMENTS is non-empty, use it as the change description. If empty, ask the user directly:

> What would you like to build or change?

Wait for their reply and treat it as the change description.

Paraphrase the request back, starting with a structured pain point line:

> **Understood pain point:** <the underlying problem or frustration driving this request>
>
> <1-2 sentence paraphrase of the proposed change>

If the user's request is solution-shaped ("add X", "change Y to Z") but the underlying problem isn't stated, infer it from context or ask: "What's not working well?" before paraphrasing. If the user already described the problem, extract it directly.

### Design context check

If the work touches frontend (CSS, components, layouts, styles), check for design context:

- **`design/context.md` found:** Read it. If it has a Design Tokens section, apply the closed token layer — every CSS value must reference a token from the context file (no raw hex, no magic spacing numbers). State which tokens and decisions apply to this change.
- **`.impeccable.md` found** (migration fallback): Read it — use its brand personality and aesthetic direction for general decisions, but note there are no concrete design tokens. For non-trivial UI work, suggest running `/i-teach-impeccable` to generate a full token set.
- **`design/direction.md` found** (migration fallback): Read it and apply its tokens as above.
- **None found** and the work involves non-trivial UI (new pages, new components, visual redesign): suggest "No design context found. Consider running `/i-teach-impeccable` first for consistent results."

**Token compliance (code-reviewer guidance):** When design/context.md has a Design Tokens section and the diff touches CSS/styles, the code-reviewer should flag raw hex values (`#[0-9a-f]{3,8}`), raw px values not matching the spacing scale, and font names not listed in design/context.md. Surface violations as HIGH findings referencing the specific token that should be used.

---

## Phase 2: Route

### Detect prior analysis

Before routing, check whether the conversation already contains findings from an analysis skill or command (`/mine.challenge`, `/mine.brainstorm`, `/mine.research`). Signals:

- Structured findings with severity labels (CRITICAL / HIGH / MEDIUM)
- A research brief (contains "Research Brief:", "Options Evaluated", "Feasibility Analysis" headers, or YAML frontmatter with `proposal:` and `flexibility:` fields)
- A phased implementation plan produced by a planner agent
- Backlog items or issues that explicitly reference findings from one of these skills (not just a title — the body must cite specific analysis results)
- Temp file reports from critic/thinker subagents

If prior analysis exists, the specify and research steps are likely already covered — the findings serve as the spec, and the critique/audit serves as the research. Offer the **accelerated** path alongside the others.

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
      description: "specify → design → draft-plan → plan-review → orchestrate → ship"
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
      description: "Formalize findings into design.md (skip research — already done) → draft-plan → plan-review → orchestrate → ship"
    - label: "Full caliper workflow"
      description: "specify → design → draft-plan → plan-review → orchestrate → ship — start from scratch"
```

### Routing Rationalizations

| Rationalization | Reality |
|---|---|
| "The findings are the spec — skip specify" | Findings identify problems; specs define success criteria, scope boundaries, and non-goals. Don't silently skip specify — use the routing gate to offer the accelerated path. If the user selects the accelerated path, that's the legitimate workflow. |
| "This is small enough to skip the caliper workflow" | The routing gate exists for this judgment. If you chose "Complex" or the user chose caliper, every phase runs. Don't downgrade mid-flight because individual WPs look simple. |
| "Prior analysis already covers research" | Prior analysis covers the *problem space*. Design-phase research covers the *solution space* — interfaces, constraints, existing patterns. Skip only when the accelerated path was explicitly selected and the analysis genuinely mapped the codebase. |
| "Just do the simple version — user said so" | Agreeing to narrow scope without reading the affected backend code is how architectural blockers surface during challenge instead of during planning. Before confirming a narrowed scope, verify the simple version is feasible in the implementation layer. If it isn't, return to the routing gate and present the complexity finding to the user before proceeding. |

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

> Starting the full caliper workflow.

**Auto-continue between steps.** Execute each skill's phases inline — do not stop and tell the user to run the next command. The user should only be interrupted for decisions that genuinely require their input (spec approval, design sign-off, plan-review verdict). Between those gates, continue automatically.

Chain the following skills in sequence. Do not duplicate their logic — follow each skill's own phases as documented:

1. **Follow `/mine.specify` phases** for this request. Pass the change description as the argument. Wait for the user to approve the spec, then continue.

2. **Follow `/mine.design` phases** using the feature directory produced by mine.specify. Wait for the user to approve the design doc, then continue.

3. **Follow `/mine.draft-plan` phases** using the feature directory from step 2.

4. **Follow `/mine.plan-review` phases** for the design doc.
   - If "Approve as-is" or "Approve with suggestions": continue to step 5.
   - If "Revise the plan": return to step 3 (`/mine.draft-plan`) with the reviewer's notes. Repeat until approved or abandoned.
   - If "Abandon": stop.

5. **Follow `/mine.orchestrate` phases** using the feature directory. The orchestrator handles per-WP execution, implementation review, challenge, and shipping as part of its Phase 3 pipeline. No further steps needed from mine.build after this point.

---

### Path C — Accelerated: Post-Analysis Caliper

Use this path when prior analysis (challenge, audit, brainstorm, research, 5whys) has already produced findings and/or a plan. The analysis serves as the spec and research — no need to redo that work.

Tell the user:

> Starting accelerated caliper workflow — skipping specify (findings are the spec) and using a lightweight design phase (skipping research — the critique already mapped the codebase).

**Auto-continue between steps** — same principle as Path B. Execute inline, only interrupt for decisions that genuinely need user input.

Then chain the following steps:

1. **Lightweight `/mine.design`** — Follow mine.design's phases with these modifications:
   - **Phase 1 (Understand the Ask)**: Use the analysis findings as the problem statement. Skip scoping questions — the findings already define what's wrong, why it matters, and what the better approach is.
   - **Phase 2 (Investigate)**: **Skip unless the analysis findings don't cover the interfaces or constraints needed for the design doc** — in that case, run targeted investigation only for the gaps (e.g., a single focused mine.research query, not the full multi-agent sweep). Use the analysis findings as the primary research input.
   - **Phase 3 (Planning Interrogation)**: Run normally — ask proportional architecture questions to fill gaps the analysis didn't cover. Focus on approach alignment and interface contracts.
   - **Phase 4 (Write Design Doc)**: Run normally — write design.md using the analysis findings as the research brief. Populate the Problem section from the findings, Architecture from the recommended approaches, and Alternatives from any TENSION findings where critics disagreed.
   - **Phase 5 (Sign-Off Gate)**: Run normally — gate on user approval.

2. **Follow `/mine.draft-plan` phases** using the feature directory from step 1.

3. **Follow `/mine.plan-review` phases** for the design doc.
   - If "Approve as-is" or "Approve with suggestions": continue to step 4.
   - If "Revise the plan": return to step 2 with the reviewer's notes. Repeat until approved or abandoned.
   - If "Abandon": stop.

4. **Follow `/mine.orchestrate` phases** using the feature directory. The orchestrator handles per-WP execution, implementation review, challenge, and shipping as part of its Phase 3 pipeline. No further steps needed from mine.build after this point.

---

## Execution Rationalizations

| Rationalization | Reality |
|---|---|
| "I'll batch these issues and start the smallest first" | Multi-issue work still flows through design → plan → review → execute. Starting with "the easy one" bypasses the plan that sequences all of them. |
| "We already did code review, we can ship" | Code review and challenge are orthogonal gates — see `rules/common/git-workflow.md`. One does not substitute for the other. |
| "The user said 'start the workflow' — I'll run it all continuously" | Each caliper phase has its own decision gate. "Start the workflow" means begin Phase 1, not execute all phases as one atomic operation. Pause for user confirmation between design sign-off, plan review, and orchestration. |
