# Comb Gate

The shared gate applied after a `fine-toothed-comb` agent returns. Callers (`mine-comb`, `mine-sketch`) read this file and instantiate the parameters below. One source of truth for the gate's central invariant:

> **A comb that surfaces issues is never cleared by acknowledgement — only by a fresh run that comes back clean, or by fixing the findings and finishing (bounded, see Iteration tracking).**

Acknowledging a finding and moving on is not allowed. Findings that have a single fix are fixed by the agent and re-combed automatically, up to a cap. The user is asked only when a finding is a real design decision, or when the loop hasn't converged by the cap.

## Parameters the caller supplies

- **`<header>`** — the `AskUserQuestion` header chip, e.g. `Sketch comb`, `Comb`. Keep it ≤12 chars — the chip truncates past that.
- **`minor_blocks`** — whether a run with only minor findings still gets fixed. `true` fixes them (the standalone `mine-comb` skill, where the user invoked the comb specifically to get what it finds); `false` notes them for the downstream summary and proceeds (`mine-sketch` — a ledger shouldn't get stuck re-combing over polish when it has its own later sign-off). See "Ordinary findings" for runs with more than minor findings.
- **`<re_review_instructions>`** — what applying a fix means in this context: which files may be edited, any scope restriction, and (for implementation combs) the subagent dispatch to apply the fix. The re-comb always re-runs the comb from the top.
- **`<blocking_question>`** *(optional)* — overrides the question text of the non-convergence prompt when the caller needs context-specific wording (e.g. "before shipping"). Defaults to the standard string below. The options and the no-acknowledgement rule are never overridable.

## Iteration tracking

Track how many times the comb has run in this phase (starting at 1). Increment the counter each time the comb re-runs — whether that re-run came from the automatic fix or from resolving a design-decision finding via an applied A/B option (which always triggers a re-comb, regardless of what else was left over): run 2 exists either way. This is internal state — callers do not supply it.

Automatic fixing stops after run 3: two fix-and-re-comb cycles is enough for the significant issues to be resolved, and a loop still failing after that is not converging on its own. From then on, every run that still blocks asks the user.

## The gate

Read the agent's `## Summary` line for the blocking/minor counts, then scan the `### Blocking` and `### Minor` lists for any finding tagged `**[Design decision]**` (see `${CLAUDE_CONFIG_DIR:-~/.claude}/agents/fine-toothed-comb.md`).

**No findings** (`no findings`): proceed to the next step silently.

### Design-decision findings

Resolve these before the ordinary flow below — but only the ones that would otherwise be acted on. A `[Design decision]` finding from the `### Blocking` list is always resolved this way. A `[Design decision]` finding from the `### Minor` list is resolved this way only when `minor_blocks` is `true`; when `minor_blocks` is `false`, note it for the downstream summary and don't prompt. Tagging a finding `[Design decision]` changes the *shape* of the question asked when one would be asked anyway; it never makes a minor finding actionable under `minor_blocks: false`, even in a run that fixes blocking findings.

For each design-decision finding in scope: it has no single fix, so the agent can't apply one on its own, and a generic question would just force the user to reject the tool call and re-explain what they actually needed. The finding's own `Options` are the fix; picking one resolves it on the spot.

Present each one individually — one `AskUserQuestion` per finding, in the order it appears, never batched. This is a major gate (comb pass/fix/escalate decision, see `interaction.md`) — run `context-pct` and prepend the result:

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

Apply the chosen option to the artifact immediately, per `<re_review_instructions>` — don't defer it into the ordinary flow's fix pass. "Stop" halts the whole gate right there. "Skip" leaves the artifact untouched and carries the finding into the downstream summary as a noted item — and, same as a resolved (A/B) finding, it is done with this gate: it does not get folded into the "Ordinary findings" flow below or re-prompted this run. (The artifact still has an unresolved design decision in it, which the *next* comb run will find again and ask about fresh — "Skip" defers the decision, not the gate's memory of it.)

If nothing chose Stop: **if any design-decision finding was resolved (an A/B option applied to the artifact), fix the run's ordinary findings in the same pass, then re-run the comb from the top.** At run 3 or later, fix only the minor ones and leave ordinary blocking findings for the next run's cap prompt. An applied option is a substantive edit, so it needs a fresh run regardless of what else happens to be left over, and that run verifies the ordinary fixes too. Don't skip the re-run because only minor findings are left: the ordinary flow's silent "note and proceed" is for runs where nothing was edited.

Only when **no** design-decision finding was resolved this pass (every one still in scope was Skipped, or none were tagged) does the ordinary flow below apply, unmodified, to whatever's left. "Whatever's left" means ordinary (untagged) findings, plus any minor design-decision findings that were left untouched because `minor_blocks` was `false` — those stay noted for the summary and are never fixed. It does **not** include Skipped findings: those are already handled per the paragraph above (noted for the summary, never re-prompted this run) and drop out of the counts entirely, the same as a resolved one. If nothing's left after that exclusion, report the outcome directly — nothing was applied, so there's nothing new to re-comb.

### Ordinary findings

Build `<summary>` below from what's actually left — exclude every design-decision finding that was resolved or Skipped above; only ordinary findings and untouched minor design-decision findings (`minor_blocks: false`) count.

**Only minor findings, `minor_blocks: false`:** note them for the downstream summary and proceed. No fix, no prompt.

**Anything else — any blocking finding, or minor findings with `minor_blocks: true`:** if this is run 3 or later and a blocking finding remains, go to "When the cap is reached" below instead of fixing. Otherwise fix them. Say what is happening in one line (`Comb run N: <summary> — fixing`), apply `<re_review_instructions>` to the run's blocking and minor findings, except minor design-decision findings already noted (only the listed findings, don't expand scope), then:

- **Re-comb from the top** (re-dispatch the agent) when any blocking finding was fixed, or when the minor fixes are substantive enough that they could introduce new problems. From run 3 on there is no further automatic re-comb: finish and report.
- **Proceed without re-combing** when only polish-level minor findings were fixed (wording, formatting, a stale reference). The test: could this fix change the meaning or structure of something the comb already judged? If not, it is polish. Report what was fixed.

**Never hold minor findings back for a later round or the end of the loop.** A held finding is still in the artifact, so every later run reports it again, and fixing the pile after the last run leaves those edits with no comb to check them. The re-comb that's already coming verifies them at no extra cost. `minor_blocks: false` only skips fixing a run whose findings are all minor.

Untagged findings should be clear corrections; anything needing a decision was handled in the section above. If one still turns out to have no single fix (the agent under-tagged it), stop and ask via `AskUserQuestion` with the options and your recommendation before applying anything, exactly as above — don't make the call autonomously just because it slipped through untagged.

### When the cap is reached

If run 3 or any later run still reports blocking findings, stop fixing automatically and ask. This is a major gate — prepend the `context-pct` result. Use the caller's `<blocking_question>` if one was supplied; otherwise use the default `question` shown here, filling in the run count:

```
AskUserQuestion:
  question: "[Context: N%] Fine-toothed comb still reports blocking issues on run <N>: <summary>. Fix-and-re-comb cycles haven't cleared them."
  header: "<header>"
  multiSelect: false
  options:
    - label: "Fix and re-review"
      description: "One more fix-and-re-comb cycle"
    - label: "Fix and finish"
      description: "Fix these findings but skip the next comb"
    - label: "Stop"
      description: "Halt and address issues manually"
```

- **Fix and re-review** — apply `<re_review_instructions>` to the same findings an ordinary fix pass covers, then re-run the comb from the top. The next run, if it still blocks, asks again.
- **Fix and finish** — apply `<re_review_instructions>` to the same findings an ordinary fix pass covers, then proceed without re-running the comb.
- **Stop** — halt; the user addresses issues manually. Leave any checkpoint in place.

Minor-only findings never trigger this prompt: at the cap they are fixed (when `minor_blocks` is `true`) and the gate finishes without another run.
