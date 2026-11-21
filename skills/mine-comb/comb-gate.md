# Comb Gate

The shared gate applied after a `fine-toothed-comb` agent returns. Callers (`mine-comb`, `mine-sketch`) read this file and instantiate the parameters below.

> **A comb that surfaces issues is never cleared by acknowledgement — only by a fresh run that comes back clean, or by fixing the findings and finishing (bounded, see Iteration tracking).**

The point is that an artifact someone acts on next must not carry known problems forward on a nod. Findings with a single fix are fixed and re-combed automatically, up to a cap. The user is asked only when a finding is a real design decision, or when the loop hasn't converged by the cap.

## Parameters the caller supplies

- **`<header>`**: the `AskUserQuestion` header chip, e.g. `Sketch comb`, `Comb`. At most 12 characters; the chip truncates past that.
- **`minor_blocks`**: whether a run with only minor findings still gets fixed. `true` fixes them (`mine-comb`, where the user invoked the comb to get what it finds); `false` notes them for the downstream summary and proceeds (`mine-sketch`, which has its own later sign-off and shouldn't stall re-combing over polish).
- **`<re_review_instructions>`**: what applying a fix means here: which files may be edited, any scope restriction, and for implementation combs the subagent dispatch that applies it. The re-comb re-runs the comb from the top unless the caller's instructions narrow it.
- **`<blocking_question>`** (optional): replacement question text for the non-convergence prompt when the caller needs context-specific wording. The options and the no-acknowledgement rule are never overridable.

## Iteration tracking

Count comb runs in this phase, starting at 1. Every re-run increments it, whether it came from the automatic fix or from a design-decision option the user picked (which always triggers a re-comb). This is internal state.

Automatic fixing stops after run 3: two fix-and-re-comb cycles resolve the significant issues, and a loop still failing then isn't converging by itself. From then on every run that still blocks asks the user.

## The gate

Read the agent's `## Summary` line for blocking and minor counts, then scan `### Blocking` and `### Minor` for findings tagged `**[Design decision]**` (see `${CLAUDE_CONFIG_DIR:-~/.claude}/agents/fine-toothed-comb.md`). With `no findings`, proceed silently.

### Design-decision findings

A design-decision finding has no single fix, so the agent can't apply one, and a generic question would make the user re-explain what they need. The finding's own `Options` are the fix; picking one resolves it. Resolve these before the ordinary flow, but only those that would otherwise be acted on: every one in `### Blocking`, and ones in `### Minor` only when `minor_blocks` is `true` (otherwise note them for the summary and don't prompt). The tag changes the shape of a question that would be asked anyway; it never makes a minor finding actionable under `minor_blocks: false`.

Ask one `AskUserQuestion` per finding, in order, never batched. It is a major gate (see `interaction.md`): run `context-pct` and prepend `[Context: N%]`. The question is `<header> found a design decision: <finding text, minus the tag>`; the options are the finding's Options A and B (labels as written, trade-offs as descriptions, `(Recommended)` appended when the finding names a lean), plus `Skip — decide later` ("Leave this open; it isn't blocking") for a Minor-list finding only, plus `Stop` ("Halt and address issues manually") always. The agent caps Options at two, so this fits the 4-option limit.

Apply the chosen option to the artifact immediately per `<re_review_instructions>`. `Stop` halts the whole gate. `Skip` leaves the artifact untouched and carries the finding into the downstream summary; like a resolved finding it is done with this gate and is not re-prompted this run (the next comb run will find it again, since the decision is deferred, not forgotten).

If nothing chose Stop and any design-decision finding was resolved by applying an option, fix the run's ordinary findings in the same pass and re-run the comb from the top: an applied option is a substantive edit that needs a fresh run whatever else is left, and that run also verifies the ordinary fixes. At run 3 or later, fix only the minor ones and leave ordinary blocking findings for the cap prompt.

Only when no design-decision finding was resolved this pass (all Skipped, or none tagged) does the ordinary flow below apply, to whatever is left: untagged findings, plus minor design-decision findings left untouched under `minor_blocks: false`. Resolved and Skipped findings drop out of the counts. If nothing is left, report the outcome; nothing was applied, so there is nothing to re-comb.

### Ordinary findings

Build `<summary>` from what is actually left.

**Only minor findings and `minor_blocks: false`**: note them for the downstream summary and proceed. No fix, no prompt.

**Anything else** (a blocking finding, or minor findings with `minor_blocks: true`): if this is run 3 or later and a blocking finding remains, go to "When the cap is reached". Otherwise fix. Say so in one line (`Comb run N: <summary> — fixing`), apply `<re_review_instructions>` to the run's blocking and minor findings, excluding minor design-decision findings already noted, only the listed findings and no wider scope. Then:

- **Re-comb from the top** when a blocking finding was fixed, or when the minor fixes are substantive enough to introduce new problems. From run 3 on there is no further automatic re-comb: finish and report.
- **Proceed without re-combing** when only polish was fixed (wording, formatting, a stale reference). The test: could the fix change the meaning or structure of something the comb already judged? If not, it's polish. Report what was fixed.

Never hold minor findings back for a later round. A held finding is still in the artifact, so every later run reports it again, and fixing the pile after the last run leaves those edits with no comb to check them. The re-comb already coming verifies them at no extra cost. `minor_blocks: false` only skips fixing a run whose findings are all minor.

Untagged findings should be clear corrections. If one turns out to have no single fix (the agent under-tagged it), ask via `AskUserQuestion` with the options and your recommendation before applying anything, the same as a tagged one; don't make the call autonomously because it slipped through.

### When the cap is reached

If run 3 or any later run still reports blocking findings, stop fixing automatically and ask. It is a major gate: prepend `[Context: N%]`. Use `<blocking_question>` if supplied, otherwise `Fine-toothed comb still reports blocking issues on run <N>: <summary>. Fix-and-re-comb cycles haven't cleared them.` Header `<header>`, options:

- `Fix and re-review`: "One more fix-and-re-comb cycle". Apply `<re_review_instructions>` to the same findings an ordinary fix pass covers, then re-run the comb from the top. If the next run still blocks, it asks again.
- `Fix and finish`: "Fix these findings but skip the next comb". Same fixes, then proceed without re-running.
- `Stop`: "Halt and address issues manually". Leave any checkpoint in place.

Minor-only findings never trigger this prompt: at the cap they are fixed (when `minor_blocks` is `true`) and the gate finishes without another run.
