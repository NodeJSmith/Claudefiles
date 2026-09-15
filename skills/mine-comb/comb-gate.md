# Comb Gate

The shared gate applied after a `fine-toothed-comb` agent returns. Callers (`mine-comb`, `mine-define`, `mine-sketch`, `mine-plan`, `mine-orchestrate`) read this file and instantiate the parameters below. One source of truth for the gate's central invariant:

> **A comb that surfaces issues is never cleared by acknowledgement — only by a fresh run that comes back clean (or by fixing the findings and proceeding without re-combing).**

Acknowledging a finding and moving on is not allowed. The only ways past a blocking finding are: fix it and re-comb, stop, or — once diminishing returns kick in on the 3rd+ run (see below) — fix it and proceed without another comb.

## Parameters the caller supplies

- **`<header>`** — the `AskUserQuestion` header chip, e.g. `Design comb`, `Plan comb`, `Comb`. Keep it ≤12 chars — the chip truncates past that.
- **`minor_blocks`** — `true` if minor findings should ask the user (the standalone `mine-comb` skill, where the user invoked the comb specifically to get a call on what it finds); `false` if minor findings are noted and the caller proceeds without asking (`mine-define`, `mine-plan`, `mine-sketch` — a design or plan doc shouldn't get stuck re-combing over polish when the phase has its own later sign-off).
- **`<proceed_label>` / `<proceed_description>`** — the "fix and move on" option, named for the caller's next step (e.g. `Proceed to sign-off`, `Proceed to the gate`). Fixes the current findings but skips the re-comb. **Required only when `minor_blocks` is `true`** — when `minor_blocks` is `false` the minor-findings prompt never fires, so omit it.
- **`<re_review_instructions>`** — what "Fix and re-review" does in this context: which files may be edited, any scope restriction, and (for implementation combs) the subagent dispatch to apply the fix. The re-comb always re-runs the comb from the top.
- **`<blocking_question>`** *(optional)* — overrides the blocking-findings question text when the caller needs context-specific wording (e.g. "before shipping"). Defaults to the standard string below. The options and the no-acknowledgement rule are never overridable.

## Iteration tracking

Track how many times the comb has run in this phase (starting at 1). Increment the counter each time the comb re-runs — whether that re-run came from "Fix and re-review" or from resolving a design-decision finding via an applied A/B option (which always triggers a re-comb, regardless of what else was left over): run 2 exists either way. This is internal state — callers do not supply it.

## The gate

Read the agent's `## Summary` line for the blocking/minor counts, then scan the `### Blocking` and `### Minor` lists for any finding tagged `**[Design decision]**` (see `${CLAUDE_CONFIG_DIR:-~/.claude}/agents/fine-toothed-comb.md`).

**No findings** (`no findings`): proceed to the next step silently.

### Design-decision findings

Resolve these before the ordinary flow below — but only the ones that would otherwise block or prompt. A `[Design decision]` finding from the `### Blocking` list is always resolved this way (blocking findings already prompt unconditionally, regardless of `minor_blocks`). A `[Design decision]` finding from the `### Minor` list is resolved this way only when `minor_blocks` is `true`; when `minor_blocks` is `false`, treat it exactly like any other minor finding — note it for the downstream summary and don't prompt. Tagging a finding `[Design decision]` changes the *shape* of the question asked when one would be asked anyway; it never overrides `minor_blocks`'s decision about whether to ask at all.

For each design-decision finding in scope: a generic "fix and re-review" question is the wrong shape for it — it has no single fix, and asking the generic version anyway just forces the user to reject the tool call and re-explain what they actually needed, which is the failure this section exists to prevent. The finding's own `Options` are the fix; picking one resolves it on the spot.

Present each one individually — one `AskUserQuestion` per finding, in the order it appears, never batched. Same major-gate rule as below — run `context-pct` and prepend the result:

```
AskUserQuestion:
  question: "[Context: N%] <header> found a design decision: <finding text, minus the tag>"
  header: "<header>"
  multiSelect: false
  options:
    - label: "<Option A>"  # append " (Recommended)" if the finding names a lean
      description: "<A's trade-off, from the finding>"
    - label: "<Option B>"
      description: "<B's trade-off, from the finding>"
    <!-- Minor-list findings only (implies minor_blocks is true here) — insert exactly this one option: -->
    - label: "Skip — decide later"
      description: "Leave this open; it isn't blocking"
    <!-- Always present, for every design-decision finding, blocking or minor: -->
    - label: "Stop"
      description: "Halt and address issues manually"
```

The agent caps `Options` at two (see `${CLAUDE_CONFIG_DIR:-~/.claude}/agents/fine-toothed-comb.md`), so this stays within `AskUserQuestion`'s 4-option limit even with Skip and Stop both present.

Apply the chosen option to the artifact immediately, per `<re_review_instructions>` — don't defer it into the ordinary flow's fix-and-re-review pass. "Stop" halts the whole gate right there, same as Stop below. "Skip" leaves the artifact untouched and carries the finding into the downstream summary as a noted item — and, same as a resolved (A/B) finding, it is done with this gate: it does not get folded into the "Ordinary findings" flow below or re-prompted this run. (The artifact still has an unresolved design decision in it, which the *next* comb run will find again and ask about fresh — "Skip" defers the decision, not the gate's memory of it.)

If nothing chose Stop: **if any design-decision finding was resolved (an A/B option applied to the artifact), re-run the comb from the top now, before doing anything else in this gate.** An applied option is a substantive edit — the same kind of change "Fix and re-review" exists to re-verify — so it needs a fresh run regardless of what else happens to be left over. Don't let an unrelated leftover minor finding (with `minor_blocks: false`) route past this into the ordinary flow's silent "note and proceed"; that path is for findings nothing has touched, not for skipping verification of an edit you just made.

Only when **no** design-decision finding was resolved this pass (every one still in scope was Skipped, or none were tagged) does the ordinary flow below apply, unmodified, to whatever's left. "Whatever's left" means ordinary (untagged) findings, plus any minor design-decision findings that were left untouched because `minor_blocks` was `false` — those flow into the ordinary minor-findings handling like any other minor finding. It does **not** include Skipped findings: those are already handled per the paragraph above (noted for the summary, never re-prompted this run) and drop out of the counts entirely, the same as a resolved one. If nothing's left after that exclusion, report the outcome directly — nothing was applied, so there's nothing new to re-comb.

### Ordinary findings

Build `<summary>` below from what's actually left — exclude every design-decision finding that was resolved or Skipped above; only ordinary findings and untouched minor design-decision findings (`minor_blocks: false`) count.

**Only minor findings:**
- If `minor_blocks` is `false`: note the minor findings for the downstream summary and proceed. No prompt.
- If `minor_blocks` is `true` (a major gate — comb pass/fix/escalate decision, see
  `interaction.md` — so run `context-pct` and prepend the result to the question):

```
AskUserQuestion:
  question: "[Context: N%] Fine-toothed comb found only minor issues: <summary>. How to proceed?"
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

**Any blocking findings** (no proceed option offered while any remain — regardless of `minor_blocks`). Use the caller's `<blocking_question>` if one was supplied; otherwise use the default `question` shown here verbatim. Same major-gate rule applies — prepend the `context-pct` result:

```
AskUserQuestion:
  question: "[Context: N%] Fine-toothed comb found blocking issues: <summary>. These must be resolved before proceeding."
  header: "<header>"
  multiSelect: false
  options:
    - label: "Fix and re-review"
      description: "Address the findings, then re-run the comb"
    - label: "Stop"
      description: "Halt and address issues manually"
```

**Diminishing returns (3rd+ run):** After 2 fix-and-re-comb cycles, significant issues should be resolved. If the comb still reports blocking findings on run 3 or later, add a third option to the blocking-findings prompt — `label: "Fix and finish"`, `description: "Fix these findings but skip the next comb — two cycles is enough"` — and change the question text to note the run count (e.g. "run 3", "run 4"). This gives the user an exit from a loop that is no longer earning its keep, without silently lowering the bar.

## On the user's choice

- **Fix and re-review** — apply `<re_review_instructions>`, then re-run the comb from the top (re-dispatch the agent). Loop until the comb returns no blocking findings.

  **Untagged design decisions:** The findings resolved here should already be clear corrections — anything needing a decision was handled in the Design-decision findings step above. If one still turns out to have no single fix (the agent under-tagged it), stop and ask via `AskUserQuestion` with the options and your recommendation before applying anything, exactly as above — don't make the call autonomously just because it slipped through untagged.
- **Fix and finish** *(3rd+ run only)* — apply `<re_review_instructions>` for the current findings, then proceed without re-running the comb.
- **`<proceed_label>`** — fix the current findings, then continue to the next step without re-running the comb.
- **Stop** — halt; the user addresses issues manually. Leave any checkpoint in place.
