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

**Any blocking findings** (no proceed option offered while any remain — regardless of `minor_blocks`). Use `<blocking_question>` if the caller supplied one; otherwise the default string shown here:

```
AskUserQuestion:
  question: "<blocking_question, default: Fine-toothed comb found blocking issues: <summary>. These must be resolved before proceeding.>"
  header: "<header>"
  multiSelect: false
  options:
    - label: "Fix and re-review"
      description: "Address the findings, then re-run the comb"
    - label: "Stop"
      description: "Halt and address issues manually"
```

## On the user's choice

- **Fix and re-review** — apply `<re_review_instructions>`, then re-run the comb from the top (re-dispatch the agent). Loop until the comb returns no blocking findings.
- **`<proceed_label>`** — accept the minor findings and continue to the next step.
- **Stop** — halt; the user addresses issues manually. Leave any checkpoint in place.
