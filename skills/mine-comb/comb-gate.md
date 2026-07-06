# Comb Gate

The shared gate applied after a `fine-toothed-comb` agent returns. Callers (`mine-comb`, `mine-define`, `mine-plan`, `mine-orchestrate`) read this file and instantiate the parameters below. One source of truth for the gate's central invariant:

> **A comb that surfaces issues is never cleared by acknowledgement — only by a fresh run that comes back clean (or with minor findings the user accepts).**

Acknowledging a finding and moving on is not allowed. The only ways past a blocking finding are: fix it and re-comb, or stop.

## Parameters the caller supplies

- **`<header>`** — the `AskUserQuestion` header chip, e.g. `Design comb`, `Plan comb`, `Impl comb`. Keep it ≤12 chars — the chip truncates past that.
- **`minor_blocks`** — `true` if minor findings should ask the user (cheap-to-fix artifacts: designs, plans); `false` if minor findings are noted and the caller proceeds without asking (a finished implementation shouldn't block shipping on polish).
- **`<proceed_label>` / `<proceed_description>`** — the "accept the minor findings and continue" option, named for the caller's next step (e.g. `Proceed to sign-off`, `Proceed to the gate`). **Required only when `minor_blocks` is `true`** — when `minor_blocks` is `false` the minor-findings prompt never fires, so omit it.
- **`<re_review_instructions>`** — what "Fix and re-review" does in this context: which files may be edited, any scope restriction, and (for implementation combs) the subagent dispatch to apply the fix. The re-comb always re-runs the comb from the top.
- **`<blocking_question>`** *(optional)* — overrides the blocking-findings question text when the caller needs context-specific wording (e.g. "before shipping"). Defaults to the standard string below. The options and the no-acknowledgement rule are never overridable.

## Iteration tracking

Track how many times the comb has run in this phase (starting at 1). Each "Fix and re-review" increments the counter. This is internal state — callers do not supply it.

## The gate

Read the agent's `## Summary` line for the blocking/minor counts.

**No findings** (`no findings`): proceed to the next step silently.

**Only minor findings:**
- If `minor_blocks` is `false`: note the minor findings for the downstream summary and proceed. No prompt.
- If `minor_blocks` is `true`:

```
AskUserQuestion:
  question: "Fine-toothed comb found only minor issues: <summary>. How to proceed?"
  header: "<header>"
  multiSelect: false
  options:
    - label: "Fix and re-review"
      description: "Address the findings, then re-run the comb"
    - label: "<proceed_label>"
      description: "<proceed_description>"
    - label: "Stop"
      description: "Halt and address issues manually"
```

**Any blocking findings** (no proceed option offered while any remain — regardless of `minor_blocks`). Use the caller's `<blocking_question>` if one was supplied; otherwise use the default `question` shown here verbatim:

```
AskUserQuestion:
  question: "Fine-toothed comb found blocking issues: <summary>. These must be resolved before proceeding."
  header: "<header>"
  multiSelect: false
  options:
    - label: "Fix and re-review"
      description: "Address the findings, then re-run the comb"
    - label: "Stop"
      description: "Halt and address issues manually"
```

**Diminishing returns (3rd+ run):** After 2 fix-and-re-comb cycles, significant issues should be resolved. If the comb still reports blocking findings on run 3 or later, add a third option to the blocking-findings prompt — `label: "Accept and proceed"`, `description: "Two fix cycles have passed — remaining findings are likely diminishing returns"` — and change the question text to note the run count (e.g. "run 3", "run 4"). This gives the user an exit from a loop that is no longer earning its keep, without silently lowering the bar.

## On the user's choice

- **Fix and re-review** — apply `<re_review_instructions>`, then re-run the comb from the top (re-dispatch the agent). Loop until the comb returns no blocking findings.

  **Design decisions:** Before applying each fix, classify it — is this a clear correction (inconsistency, typo, gap with an obvious fill) or does it require a design decision (multiple valid approaches, a trade-off between competing concerns, or the finding questions a deliberate choice)? Clear corrections: apply directly. Design decisions: surface to the user via `AskUserQuestion` before applying — present the finding, the options you see, and your recommendation. Do not make design decisions autonomously. The comb surfaces gaps; the user decides how to fill them.
- **`<proceed_label>`** — accept the minor findings and continue to the next step.
- **Stop** — halt; the user addresses issues manually. Leave any checkpoint in place.
