---
name: mine-review
description: "Use when the user says: \"review my changes\", \"run the reviewers\", \"code and integration review\", \"readability review\", \"maintainability review\", \"sniff test this\", \"WTF check\", \"code smells\", \"is this code any good\", \"fresh eyes on this branch\", \"review this directory\", \"check this module\", \"review this skill\", \"review these instructions\". Dispatches parallel reviewers — code, integration, and a readability pass for code; consistency, instruction quality, and writing quality for instruction files; both sets for a mixed change — and consolidates findings into one prioritized report."
user-invocable: true
---

# Technical Review

Get an independent read on the user's changes (or a directory) before they ship, from reviewers working in parallel, and hand back one prioritized report the user can act on. Code gets correctness, integration fit, and readability reviewers; instruction files (`.md`) get consistency, instruction-quality, and writing-quality reviewers. Every file in scope reaches the reviewers for its kind, so a change that touches both gets both sets.

Done looks like: each real problem appears once with the specific edit that would fix it, ordered by how much it matters, with weak findings separated out so the user isn't asked to act on them.

## Arguments

$ARGUMENTS — optional scope. Empty for the full branch diff, or a directory/file list. Path mode applies when the files exist but have no branch changes.

## Scope

Read and follow `${CLAUDE_CONFIG_DIR:-~/.claude}/skills/mine-review/scope-detection.md`. It resolves `$ARGUMENTS` to diff mode or path mode.

## Dispatch

The reviewers each carry their own checklist and output format, so give them the scope and nothing else: no hypotheses about what is wrong, which would anchor them.

Split the files in scope by kind. Instruction files are what an agent loads as instructions: skills, agent prompts, rules, commands, `CLAUDE.md`, and their reference files. Other prose (README, CHANGELOG, design docs) goes with the code when there is code, and counts as instruction files when the change is prose only. Only code means **code mode**, only instruction files means **instruction mode**, and both means **mixed mode**, which runs both reviewer sets, each scoped to its own files. Code reviewers given a skill alongside a script would judge the skill as code, and instruction-quality review of it would never happen.

In diff mode, write each set's diff to a file first so its reviewers all read the same one: `mktemp -d <scratchpad>/mine-review-XXXXXX` for `<tmpdir>`, `git rev-parse HEAD` for `<sha>`, then the diff command with its pathspec replaced by that set's files (`git diff <base>...HEAD -- <that set's files> > <tmpdir>/<code|instruction>.patch`; appending a second `--` would OR the pathspecs and undo the split).

Scope line:
- **Diff mode**: `Diff at <tmpdir>/<its patch> (HEAD: <sha>). Read changed files for surrounding context. Before relying on the diff, verify HEAD matches <sha>.`
- **Path mode**: `Review these existing files (not a diff): <file list>`
- **Diff mode, instruction reviewers**: also append `Read every changed file in full, not just diff hunks.`

Dispatch every agent for the mode in one message (six in mixed mode):

- Code files: `code-reviewer`, `integration-reviewer`, `wtf-reviewer`, each with `Review changes. <scope line>`
- Instruction files: `fine-toothed-comb` with `Review these instruction files for consistency, accuracy, and completeness. <scope line>. Read sibling files for cross-reference context.`; `instruction-quality-reviewer` and `writing-quality-reviewer` with `Review these instruction files. <scope line>`

## Consolidate and present

Merge duplicate findings into one entry that notes the cross-signal (`flagged by code-review + readability pass`). The instruction reviewers report blocking/minor; rank blocking as High and minor as Low alongside the code reviewers' severities. Judge validity with `${CLAUDE_CONFIG_DIR:-~/.claude}/skills/mine-challenge/findings-protocol.md`: findings are valid by default, and calling one likely invalid needs a concrete evidence trail.

Organize the report by severity, not by reviewer, under `## [Technical|Instruction|Technical + Instruction] Review: [branch name or target path]`. Open with the scope (files and line counts), each reviewer's verdict or finding counts, and the likely-invalid count. Label sources `Code`, `Integration`, `Readability` for the code reviewers and `Consistency`, `Instruction`, `Writing` for the instruction reviewers. Every finding carries the proposed fix, the specific edit, because the user decides from seeing both the problem and the edit. Likely-invalid findings go in their own section with Claimed / Actually / Why-invalid.

## Next steps

If nothing is worth fixing (everything passed, what's left is likely-invalid, or only medium and low findings remain and aren't worth the churn), say so and stop; there is nothing to ask.

Otherwise ask what to do with the findings. This is a major gate (see `interaction.md`): run `context-pct` and prepend `[Context: N%]`. Build the options from the severity mix and what you found, put finding counts in the descriptions, and recommend the one that fits. The usual outcomes are fix everything, fix only critical/high, or note and move on; drop any the findings make meaningless (no critical/high means no "critical/high only"; if medium and low aren't worth the churn, recommend critical/high only over fix-all).

When fixing, edit directly, highest severity first, then re-read what you changed and say: "Fixes complete — run `/mine-commit-push` or proceed to commit when ready."

## What This Skill Does NOT Do

- **Deep codebase audit** — use `/mine-audit`
- **Exhaustive style sweep** — use `/mine-clean-code`
- **Fix without asking** — it diagnoses, then asks what to fix
