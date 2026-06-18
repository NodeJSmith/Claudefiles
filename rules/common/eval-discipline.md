---
tool: claude, codex, antigravity
---

# Eval Discipline

**Scope:** Applies when explicitly running an evaluation of agent behavior (e.g., A/B comparisons of prompts, skills, or structural changes via `/mine-mutation-test` or manual eval sessions). Not a general coding rule.

When testing how a skill, prompt, or structural change affects agent behavior, the failure mode is the observer effect. An agent that knows it is being evaluated behaves differently from one doing organic work. Candidates must run blind.

## Non-Negotiables for Blinding

- No `eval`, `test`, `judge`, `experiment`, `rubric`, `score`, `compare`, `benchmark`, `candidate`, or `arena` in any directory, file, or prompt the candidate sees.
- The candidate prompt looks like an organic user request. State the goal, not the meta. "Build me a small todo CLI" not "show me how you follow the principles chain."
- No chain-eliciting cues. Do not ask the candidate to list which skills, principles, or files it applied. That inflates citation behavior. Grade chain-following from code shape, not self-report.
- Sanitize directory and slug names. Use project-shaped names a user might pick, not labels like `candidate-1` or `agent-a`.
- Do not tell the candidate other candidates exist.
- The judge can know it is judging but sees outputs by sanitized label only, never by model name.

## Comparing Two Variants

One judge scores both sets in a single pass on one scale, blind to which set each output came from. Two separate judge runs with different prompts do not compare; the calibration drifts and you will read the drift as a result.

## Verification

Read each candidate's actual behavior (which files it opened, what code it wrote) rather than trusting its self-report. Citing a principle is not the same as reading its source, and reading it is not the same as applying it. Grade from artifacts, not claims.
