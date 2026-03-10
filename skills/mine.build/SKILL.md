---
name: mine.build
description: Smart build entry point — routes a change request to simple direct implementation or the full caliper workflow (with optional sophia CR tracking) based on complexity.
user-invokable: true
---

# Build

One command to go from idea to shipped code. Routes your request to the right workflow: implement directly for small changes, or engage the full caliper pipeline (design → draft-plan → plan-review → orchestrate → implementation-review → ship) for complex ones. Optionally integrates sophia CR tracking.

## Arguments

$ARGUMENTS — a description of the change to build. If empty, ask.

## Phase 1: Understand the Request

If $ARGUMENTS is non-empty, use it as the change description. If empty, ask the user directly:

> What would you like to build or change?

Wait for their reply and treat it as the change description.

Paraphrase the request back in one or two sentences to confirm understanding before proceeding.

## Phase 2: Check Sophia + Route

Make two separate tool calls to check sophia readiness:

```bash
command -v sophia > /dev/null 2>&1 && echo "installed" || echo "missing"
```

```
Glob: SOPHIA.yaml
```

Record:
- `sophia_installed` — true if the first call printed "installed"
- `sophia_yaml_exists` — true if the Glob returned a result

Provide a brief complexity signal based on the request:
- **Simple** — touches 1–3 files, clear approach, no design uncertainty, no cross-system impact
- **Complex** — touches multiple modules, has design uncertainty, crosses system boundaries, or has unclear implementation approach

Then present routing options:

```
AskUserQuestion:
  question: "How should we approach this? (Complexity signal: <Simple|Complex>)"
  header: "Workflow"
  multiSelect: false
  options:
    - label: "Simple — implement directly"
      description: "Explore, implement, code-review, then offer to ship"
    - label: "Complex — full caliper workflow"
      description: "design → draft-plan → plan-review → orchestrate → implementation-review"
    - label: "Complex + Sophia — full workflow with CR tracking"
      description: "Full caliper workflow plus sophia change request lifecycle<sophia_note>"
```

Replace `<sophia_note>` with:
- `""` — if both sophia_installed and sophia_yaml_exists are true
- `" (sophia setup required)"` — if either check was negative

Always show all three options regardless of sophia readiness. The Sophia option description communicates setup status; the user decides whether to proceed.

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

1. **Follow `/mine.design` phases** for this request. Pass the change description as the argument. Wait for the user to approve the design doc before proceeding. If the user abandons, stop.

2. **Follow `/mine.draft-plan` phases** using the design doc path produced in step 1. Wait for the plan to be drafted. If the user abandons, stop.

3. **Follow `/mine.plan-review` phases** for the drafted plan.
   - If APPROVE: continue to step 4.
   - If REQUEST_REVISIONS: return to step 2 (`/mine.draft-plan`) with the reviewer's notes. Repeat until APPROVE or ABANDON.
   - If ABANDON: stop.

4. **Follow `/mine.orchestrate` phases** using the approved plan path. mine.orchestrate handles per-task execution, deviation classification, and its own post-execution handoff.

5. mine.orchestrate's Phase 4 post-execution handoff offers `/mine.implementation-review` inline. Follow that flow. If the user declines the implementation-review handoff, offer the ship gate directly with a note that implementation-review was skipped.

6. After implementation review completes:
   - If **APPROVE**: proceed to the ship gate below.
   - If **REQUEST_FIXES**: surface the blocking issues. Tell the user to address them and re-run `/mine.orchestrate`, then `/mine.implementation-review`. Stop here — resume with `/mine.build` or manually after fixes are applied.
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

### Path C — Complex + Sophia: Full Workflow with CR Tracking

**Step 1: Resolve sophia readiness.**

If sophia is not installed:

```
AskUserQuestion:
  question: "sophia is not installed. Install it now to enable CR tracking?"
  header: "Sophia setup"
  multiSelect: false
  options:
    - label: "Yes — install sophia"
      description: "Run sophia-install, then continue with the full workflow"
    - label: "Switch to Complex (no sophia)"
      description: "Proceed with Path B instead"
    - label: "Stop"
      description: "Cancel"
```

If "Yes — install sophia":

```bash
sophia-install
```

On success, continue. On failure, offer:

```
AskUserQuestion:
  question: "sophia-install failed. How would you like to proceed?"
  header: "Setup failed"
  multiSelect: false
  options:
    - label: "Switch to Complex (no sophia)"
      description: "Proceed with Path B instead"
    - label: "Stop"
      description: "Cancel"
```

If sophia is installed but SOPHIA.yaml is missing:

```
AskUserQuestion:
  question: "sophia is installed but SOPHIA.yaml is missing — the CR system needs to be initialized for this repo. Initialize it now?"
  header: "Sophia init"
  multiSelect: false
  options:
    - label: "Yes — run /mine.sophia to init"
      description: "Follow the sophia initialization flow, then continue"
    - label: "Switch to Complex (no sophia)"
      description: "Proceed with Path B instead"
    - label: "Stop"
      description: "Cancel"
```

If "Yes — run /mine.sophia to init": follow `/mine.sophia` initialization phases. If the init flow completes successfully, continue. If it fails or the user abandons during init, offer:

```
AskUserQuestion:
  question: "Sophia initialization did not complete. How would you like to proceed?"
  header: "Init failed"
  multiSelect: false
  options:
    - label: "Switch to Complex (no sophia)"
      description: "Proceed with Path B instead"
    - label: "Stop"
      description: "Cancel"
```

**Step 2: Run Path B with sophia additions.**

Follow all steps of Path B (design → draft-plan → plan-review → orchestrate → implementation-review → ship gate), with these additions at the marked points:

**After plan-review APPROVE (before orchestrate):**

Create a sophia CR for this change:

```bash
sophia cr add --description "<change description>"
```

Then offer:

```
AskUserQuestion:
  question: "Sophia CR created. Set the contract now?"
  header: "Contract"
  multiSelect: false
  options:
    - label: "Yes — set the contract via /mine.sophia contract"
      description: "Define success criteria and constraints for this CR"
    - label: "Skip — add the contract later"
      description: "Proceed to orchestrate; contract can be added before merge"
```

If "Yes": follow `/mine.sophia` contract phases for this CR, then continue to orchestrate.

**During orchestrate:** mine.orchestrate detects the active CR automatically and handles per-task sophia updates. No additional sophia steps needed here.

**After implementation review APPROVE:**

Run:

```bash
sophia cr status --json
```

Surface the CR state to the user (phase, tasks completed, any outstanding items).

Then offer:

> Note: If `merge.mode: pr_gate` is set in SOPHIA.yaml, the CR will be closed automatically when the PR is merged — this step is optional in that case.

```
AskUserQuestion:
  question: "CR tracking is up to date. Merge the CR?"
  header: "CR merge"
  multiSelect: false
  options:
    - label: "Yes — sophia cr merge"
      description: "Mark the CR as merged in sophia"
    - label: "No — I'll handle it manually"
      description: "Leave the CR in its current state"
```

If "Yes":

```bash
sophia cr merge
```

If `sophia cr merge` fails, surface the error output and offer:

```
AskUserQuestion:
  question: "sophia cr merge failed. How would you like to proceed?"
  header: "Merge failed"
  multiSelect: false
  options:
    - label: "Skip CR merge and ship anyway"
      description: "Proceed to the ship gate; the CR stays open"
    - label: "Stop here"
      description: "Resolve the sophia issue manually before shipping"
```

Then proceed to the ship gate (same as Path B step 6).
