---
task_id: "T02"
title: "Dispatched fixer loop with terminal ledger"
status: "planned"
depends_on: ["T01"]
implements: ["FR#10", "AC#6"]
---

## Summary

Create the supporting file that defines the dispatched fixer loop replacing today's inline Step-12 fixing. A Sonnet fixer subagent reads the code/integration review files in its own ephemeral context, applies unambiguous fixes, defers judgment calls, and writes a terminal ledger classifying every finding the current review reports. The orchestrator alternates fixer pass → independent re-review, ending on a fixer pass, then gates on the ledger's `unresolved` rows. This restores the deferred-vs-unresolved distinction across the orchestrator/fixer split without any cross-agent finding-ID matching. This task creates the loop definition only; T03 wires Step 12 to it.

## Target Files

- create: `skills/mine-orchestrate/findings-fix-loop.md`
- read: `design/specs/034-orchestrate-verdict-only/design.md` (Architecture §4, FR#10, AC#3, AC#6)
- read: `skills/mine-orchestrate/warn-fix-loop.md` (structural model for a self-contained loop file)
- read: `skills/mine-orchestrate/retry-prompt.md` (source of the verify-before-fix + YAGNI posture to reference, NOT to reuse wholesale)
- read: `skills/mine-orchestrate/SKILL.md` (current Step 12, lines ~436-460, for the fix/defer policy wording to preserve)
- read: `references/common/receiving-code-review.md` (the shared posture the fixer cites by reference)

## Prompt

Create `skills/mine-orchestrate/findings-fix-loop.md` implementing the dispatched fixer + terminal-ledger model from the design doc's `## Architecture` §4 and `## Functional Requirements` FR#10. Model the file's shape on `warn-fix-loop.md` (a self-contained, numbered, "read and follow" supporting file). It must specify:

1. **When it runs:** invoked from Step 12 when the code-review or integration-review canonical line shows `findings > 0` or a WARN/BLOCK verdict (the trigger condition lives in SKILL Step 12, added by T03; state the precondition here).

2. **The fixer dispatch:** a `general-purpose` subagent with `model: sonnet`. Inputs passed to it: the code-review and integration-review file **paths** (not contents), the changed-files list, and the design doc path. Constraints stated in its prompt: fix findings only; do **not** re-run the task or re-capture screenshots; verify each finding against the actual code before acting (verify-before-fix + YAGNI — cite `references/common/receiving-code-review.md` by reference, do not paste the executor re-implementation framing from `retry-prompt.md`).

3. **The fix/defer policy:** identical wording to today's Step 12 — auto-fix when the correct solution is unambiguous; defer when the fix requires architectural judgment or business context.

4. **The ledger:** the fixer writes `<task_id>/fix-ledger.md`, **overwritten each pass**, with one row per finding the current review reports, classified `fixed` | `deferred(reason)` | `unresolved`. Rows are descriptive (e.g. `[MEDIUM] foo.py:42 — deferred: architectural judgment`) — they are NOT keyed by a cross-agent finding-ID and are never matched across agents. The fixer also returns a one-line summary (`fixed: N, deferred: M, unresolved: K`).

5. **The loop (orchestrator-driven), ending on a fixer pass:**
   - Iteration 1 is the Step 8 review.
   - Then alternate: fixer pass → re-capture changed files → re-dispatch code + integration reviewers (concise) → re-extract verdict lines.
   - Budget: at most **2 fixer passes** (3 iterations total, matching today's "max 3 iterations including the initial run").
   - If the fresh re-review reports `findings: 0` → done.
   - If the budget is exhausted while the latest review still reports findings → run one final fixer pass in **classify mode** over that latest review, so the terminal ledger reflects it.

6. **The gate:** the orchestrator reads only the terminal ledger (compact). Any `unresolved` row → the task verdict is FAIL (routes to Step 16). Deferred-only or empty → PASS (with a `(N auto-fixed)` note for Step 14/15). The orchestrator reads no report body and matches no findings across agents.

7. **Trail logging:** preserve the existing Step-12 trail-log fix-summary call (`trail-log "<trail_path>" p2 <task_id> fix "..."`) — adapt its detail to report the ledger summary (fixed/deferred/unresolved counts and iteration count).

Keep the file consistent in tone and structure with `warn-fix-loop.md`.

## Focus

- **The terminal-fixer model is the crux fix** from the design's challenge rounds. The reconciliation of deferred-vs-unresolved MUST happen inside a fixer context that has read the latest review — never reconstructed by the orchestrator from counts or IDs. Make this explicit so an implementer doesn't reintroduce orchestrator-side matching.
- **Detection stays independent:** findings come from the independent code/integration reviewers' files; the fixer classifies those findings (defer/unresolved) — exactly what today's orchestrator-as-fixer does. The fixer does not invent findings.
- **Iteration accounting is load-bearing and was a prior bug source.** State it unambiguously: initial review + ≤2 fixer passes; each dispatch is a single pass; the fixer does not loop internally.
- Do NOT reuse `retry-prompt.md` whole — it opens "You are re-implementing a task" and carries a `SYNC` header to `receiving-code-review.md`; reuse only the verify-before-fix posture by reference. Editing `retry-prompt.md` would drift the SYNC'd file.
- `get-skill-tmpdir` / per-task subdir: the ledger lives in the run tmpdir's per-task subdirectory `<dir>/<task_id>/fix-ledger.md` (same place as `code-review.md` etc., per SKILL Step 3).

## Verify

- [ ] FR#10: `findings-fix-loop.md` defines the fixer dispatch (paths not contents; sonnet; findings-only constraints), the overwrite-each-pass ledger classifying current-review findings as fixed/deferred/unresolved, the loop ending on a fixer pass with the initial-review + ≤2-passes budget and a classify-mode terminal pass, and the gate reading only the terminal ledger's `unresolved` rows.
- [ ] AC#6: The loop guarantees every code/integration finding on a passing task is either fixed or recorded as `deferred(reason)` in the ledger — never silently skipped — and the file states this explicitly.
