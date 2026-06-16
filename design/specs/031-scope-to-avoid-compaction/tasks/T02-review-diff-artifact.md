---
task_id: "T02"
title: "Pass mine.review critics a pre-computed diff artifact"
status: "done"
depends_on: []
implements: ["FR#5", "AC#5", "AC#8"]
---

## Summary
Lever 2a. `mine.review` currently tells each of its three critics `Run: <diff command>`, so every
critic re-derives the changeset itself (the measured failure mode: one critic ran 80 Bash calls
doing git archaeology). Change it so the orchestrator computes the diff once, writes it to a temp
artifact stamped with the HEAD SHA, and points each critic at the artifact path with an instruction
not to re-derive the changeset. This is diff-mode only; path mode is unchanged.

## Prompt
Edit `skills/mine.review/SKILL.md` (diff mode only — the section that resolves scope via
`scope-detection.md` and the three critic prompts that currently say `Run: <diff command>`, around
lines 28–70):

1. After `scope-detection.md` resolves the diff command in diff mode, have the orchestrator run it
   once and write the output to a temp file via `get-skill-tmpdir mine-review` (e.g.
   `<dir>/diff.patch`), and record the HEAD SHA it was computed against (e.g. `git rev-parse HEAD`).
2. In each of the three critic prompts (code-reviewer, integration-reviewer, wtf-reviewer), replace
   the `Run: <diff command>` line with: a reference to the pre-computed artifact path (stamped with
   `<SHA>`), an instruction to **read the artifact rather than re-run the diff command to
   reconstruct the changeset**, permission to read changed files in full only for surrounding
   context, and a fallback: "if HEAD has moved past `<SHA>`, fall back to the live diff command."
3. Specify the artifact lifecycle in the skill prose: created by the orchestrator before dispatch,
   lives in the run's `get-skill-tmpdir` directory, cleaned up with it.

Do NOT add diff-artifact logic to `scope-detection.md` — it is shared with `mine.clean-code`
(`mine.clean-code/SKILL.md:28`), which must not inherit this. Keep the artifact computation in
`mine.review/SKILL.md`. Do NOT touch `mine.challenge` (it has no diff mode). Reference the design's
`## Architecture` (Lever 2) and `## Edge Cases`.

## Focus
- `scope-detection.md` physically lives at `skills/mine.review/scope-detection.md` and is read by
  both review and clean-code. The diff-artifact change must stay in `mine.review/SKILL.md` so it
  doesn't leak into clean-code's resolution.
- The three critic prompts are fenced blocks; edit inside the fences. The current instruction
  literally is `Run: <diff command>` at the lines surfaced by grep (`mine.review/SKILL.md:41,52,66`).
- The wording must be firm enough to actually stop the git archaeology: critics are otherwise told
  they may use `git log`/`git diff` (the skill allows git tooling generally), so the instruction
  must explicitly say "do not re-run the diff to reconstruct the changeset — read the artifact."
- Staleness is the real failure mode for a cached diff: the HEAD-SHA stamp + fallback is what makes
  it safe against a working tree that moved between artifact creation and a critic reading it.
- AC#8: this edits critic-facing instructions but must not change *what* the critics review
  (correctness/integration/readability dimensions, severity) — only where the diff comes from.

## Verify
- [ ] FR#5: In diff mode, `mine.review` computes the diff once, writes a HEAD-SHA-stamped artifact,
      and each critic prompt references the artifact path instead of `Run: <diff command>`.
- [ ] AC#5: Critic prompts instruct not re-deriving the changeset; the artifact's create/cleanup
      lifecycle and the HEAD-moved fallback are specified; `mine.challenge` is not modified;
      `scope-detection.md` is unchanged.
- [ ] AC#8: The review dimensions (correctness/integration/readability) and severity behavior of the
      three critics are unchanged — only the changeset source differs.
