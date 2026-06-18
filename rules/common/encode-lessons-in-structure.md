---
tool: claude, codex, antigravity
---

# Encode Lessons in Structure

<!-- SYNC: rules/common/invariants.md — update the corresponding invariant entry when changing this rule. -->

Encode recurring fixes in mechanisms (tools, code, metadata, automation) instead of textual instructions. Every error, human correction, and unexpected outcome is a learning signal. Capture it, route it, and close the loop.

Textual instructions are easy to miss. They require the reader to notice, remember, and comply. Structural mechanisms (lint rules, metadata flags, runtime checks, automation scripts) enforce the rule without cooperation.

## When to Encode

When you catch yourself writing the same instruction a second time:

1. Ask: can this be a lint rule, a metadata flag, a runtime check, or a script?
2. If yes, encode it. Delete the instruction.
3. If no (genuinely requires judgment), make the instruction more prominent and add an example of the failure mode.

Do not paper over symptoms. If the fix is structural, only use the structural fix. The instruction is the symptom.

## Feedback Loop

- **Capture every correction.** When the human intervenes or tests fail, decide if it is a one-off or a pattern.
- **Route to the right layer.** One-off: note it. Recurring fix: skill, lint rule, or hook. Systemic issue: principle or rule file.
- **Close the loop.** Do not just record. Apply now or create a concrete todo.

## Anti-Patterns

- Acknowledging without recording ("I'll keep that in mind" does not persist)
- Recording without routing (a note about a lint rule that should exist is wasted unless the lint rule gets implemented)
- Fixing without generalizing (fixing one instance while leaving the recurring pattern intact)
