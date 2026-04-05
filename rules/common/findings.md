# Findings

When analysis skills produce findings, follow this convention for presenting and resolving them. This applies to skills that identify fixable issues — audit, challenge (standalone), visual-qa, tool-gaps, and similar. It does not apply to ideation skills like brainstorm, which manage their own output.

## Principle: All Findings Must Be Resolved

Every finding must be resolved — meaning fixed, filed as an issue, or explicitly deferred by the user. Do not guide the user toward shipping code with known unresolved findings. "File as issue" is not skipping — it's proper tracking for work that can't happen now. Explicit user deferral ("Skip") is valid — the principle prevents silent abandonment, not informed decisions.

## Presenting Findings

Every finding must include a **concrete recommendation** — not just what's wrong, but what to do about it. A finding without a recommendation is incomplete.

For findings with multiple valid approaches, present options:
- **Option A** is always the recommended approach, labeled with `(Recommended)`
- Additional options follow
- "File as issue" is always available as an option; recommend it when the fix is out of scope for this session

## Proceed Gate

After presenting all findings, ask once:

```
AskUserQuestion:
  question: "Proceed to fix all findings?"
  header: "Findings"
  multiSelect: false
  options:
    - label: "Yes"
      description: "Auto-apply unambiguous fixes; ask per-finding for judgment calls"
    - label: "No"
      description: "Stop here — I'll direct next steps"
```

Do not begin fixing anything before this prompt. Do not ask "which findings" — the default is all of them.

## Resolving Findings

After the user confirms:

### 1. Collect all user-directed answers first

Before making any code changes, ask **all** user-directed questions upfront. Present each judgment call, collect the user's choice, then move to the next question. Do not interleave questions with code changes — the user may be in a different context (tab, window) and questions that sit unanswered between changes are disruptive.

### 2. Execute all fixes

Once all answers are collected:

- **Auto-apply unambiguous fixes** — findings where there's one clear, localized fix. When classification is ambiguous, default to user-directed. Auto-apply only when the fix is purely additive, scoped to a single location, and introduces no behavior change.
- **Apply user-directed fixes** using the answers collected in step 1.
- **File issues** for findings where "file as issue" was selected, using `gh-issue create`.

## Skill-Specific Overrides

Some skills have post-finding interactions beyond fix/file (e.g., visual-qa offers "re-run with different viewport" and "read agent report"). These skills may present their own post-finding gate in place of — not in addition to — the Proceed Gate. The skill's gate should still include fix and file-as-issue paths.
