# Encode Lessons in Structure

Every error, human correction, and unexpected outcome is a learning signal. Capture it, route it, and close the loop.

Most lessons need a short instruction at most. A mechanism (lint rule, metadata flag, runtime check) enforces a rule without anyone having to remember it, but it also runs on every future change and has to be maintained. Use one when a lesson keeps recurring despite the instruction.

## When to Encode

A one-off correction gets a short note or instruction. Build a mechanism only when both hold:

1. The mistake recurred after an instruction against it already existed.
2. The mechanism costs less to keep than the mistake costs when it happens.

If both hold, encode it and delete the instruction. If not, keep the instruction short and add an example of the failure mode.

### Pick the Lightest Mechanism That Works

When a lesson does earn a mechanism, pick the lightest one that would have caught the recurrence:

1. **Metadata flag** — marks the constraint in data
2. **Lint rule / pre-commit hook** — catches it before commit
3. **Runtime check** — fails immediately when violated

## Feedback Loop

- **Capture every correction.** When the human intervenes or tests fail, decide if it is a one-off or a pattern.
- **Route to the right layer.** One-off: note it. Recurring fix: skill, lint rule, or hook. Systemic issue: principle or rule file.
- **Close the loop.** Do not just record. Apply now or create a concrete todo.

## Anti-Patterns

- Acknowledging without recording ("I'll keep that in mind" does not persist)
- Recording without routing (a lesson that has earned a mechanism under the test above, but only ever gets written down as a note)
- Fixing without generalizing (fixing one instance while leaving the recurring pattern intact)
