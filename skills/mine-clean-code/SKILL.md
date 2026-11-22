---
name: mine-clean-code
description: "Use when the user says: \"clean code check\", \"style review\", \"LLM smell check\", \"code hygiene\", \"nitpick this\", \"style check\", \"find style sins\", \"nitpicker review\", \"anal retentive review\", \"exhaustive style review\", \"no-filter style report\". Dispatches three parallel stylistic checkers — llm-checker (training-bias patterns), lazy-checker (deferred debt), and nitpicker (style hygiene) — and consolidates findings into a report organized by checker with a Summary section."
user-invocable: true
---

# Clean Code Review

Surface the stylistic debt a correctness review won't: LLM training-bias patterns, deferred-debt shortcuts, and style hygiene, each from its own checker. Not a correctness review; use `/mine-review` for that.

Done looks like: one report organized by checker, each finding with its proposed fix, tagged by whether this diff caused it, and the user's chosen outcome carried out (fixes applied, the out-of-scope remainder filed as a single follow-up issue, or noted and left).

## Context

- Issue tracker: !`printenv ISSUE_TRACKER`

## Arguments

$ARGUMENTS — optional scope. Empty for the full branch diff, or a directory/file list. Path mode applies when the files exist but have no branch changes.

## Scope

Read and follow `${CLAUDE_CONFIG_DIR:-~/.claude}/skills/mine-review/scope-detection.md`. Keep code files only; drop `.md` and other prose. If no code files remain, say "No code files in scope — use `/mine-review` for instruction files." and stop.

## Dispatch

Dispatch all three checkers in one message. Each carries its own checklist and output format, so give it the scope line only:

- `subagent_type: "llm-checker"` — `Review for LLM training-bias patterns. <scope line>`
- `subagent_type: "lazy-checker"` — `Review for deferred-debt patterns. <scope line>`
- `subagent_type: "nitpicker"` — `Review for style and hygiene issues. <scope line>`

Scope line: in diff mode `Run: <diff command>. Read each changed file in full.`; in path mode `Review these existing files (not a diff): <file list>`.

Above ~30 files, split the files into balanced batches of ~30 and dispatch all three checkers on every batch (3×K dispatches). Each file lands in exactly one batch but must get all three lenses, so batch the files, never the checkers. Batched diff-mode scope line: `Files in this batch: <file list>. Read each file in full.` Merge each checker's findings across batches before consolidating.

## Consolidate and present

When two checkers flag the same file:line, keep both in their own sections and note the cross-signal; they are different quality dimensions.

**Likely-invalid.** Judge with `${CLAUDE_CONFIG_DIR:-~/.claude}/skills/mine-challenge/findings-protocol.md`: valid by default, and calling one likely invalid needs a concrete evidence trail. Likely-invalid findings go only in their own section (Claimed / Actually / Why-invalid) and drop out of every count below.

**In scope or out (diff mode only).** The checkers read whole files, so findings can land on code this diff never touched, and the user needs to know which problems are theirs to fix now. Tag each finding `(in scope)` when its line falls in a hunk the diff changed, or when the finding's own text attributes it to a change made elsewhere in this diff (a helper newly dead because the diff removed its last caller); otherwise `(out of scope)`. Take that causal link from what the finding itself says, not from your own inference, so tags stay checkable. Get changed ranges from the `+c,d` side of `@@` headers in `<base diff command> -U0 -- <file>`, where `<base diff command>` is `git diff <base>...HEAD` or `git diff HEAD` without any path suffix: git honors only the first `--` as the pathspec separator, so an existing `-- <paths>` suffix would turn this one into a second, non-matching pathspec and silently give 3-line-context hunks. Path mode has no PR to be in or out of, so skip tagging and treat everything as in scope.

Report under `## Clean Code Review: [branch name or target path]`: the scope (files and line counts), a table with one row per checker (`LLM Patterns` CLEAN / SMELLS (N), `Lazy/Debt` CLEAN / DEBT (N), `Nitpick` CLEAN / FINDINGS (N)) and a total, the likely-invalid count, and in diff mode `N in scope · M out of scope`. Then one section per checker, each finding with its scope tag and the specific proposed edit, because the user decides from seeing the problem and the fix.

## Next steps

If nothing is left but likely-invalid findings (or every checker is CLEAN), say so and stop.

Otherwise ask what to do. Put finding counts in the descriptions and recommend from the findings (fix-all when mostly mechanical, one checker when it produced most of them, note-and-move-on when only trivial nitpicks remain). Offer the outcomes that apply:

- **Fix all**: apply every proposed fix, in scope and (in diff mode) out of scope, taking llm-checker, then lazy-checker, then nitpicker, and re-read what changed.
- **Fix one checker's findings**: only when more than one checker has findings. Fix all of that checker's findings, in scope and out; with more than 8, show 4 at a time so the user can steer, then offer another checker.
- **Note and move on**: no fixes, nothing filed. Keep this exact label; `mine-ship` selects it.

When out-of-scope findings exist in diff mode, state the split first (`<Total> clean code findings. <N> are in scope of this PR. <M> are out of scope`) and add a **Fix in scope, file the rest** option, which applies the in-scope fixes and then files the out-of-scope findings per the next section. Offer it only if a usable tracker exists: check you have tools for the tracker `$ISSUE_TRACKER` names (unset or empty means GitHub `gh`); don't guess. With no usable tracker, say the out-of-scope findings won't be auto-filed and offer **Fix in scope, note the rest** instead, which leaves them in the report.

Edit directly; ask only about judgment calls. After fixes: "Fixes complete — run `/mine-review` before committing."

## Filing out-of-scope findings

File one issue for all of them, never one per finding, titled `Clean code follow-ups: <branch name>`. Group the body by checker, each finding as `- **file:line** — <description> → <proposed fix>`. Write the body to `<tmpdir>/issue-body.md` (`mktemp -d <scratchpad>/mine-clean-code-XXXXXX`) and pass it by the tracker's `--body-file`/`--description-file` flag or stdin, never as a shell argument (see `git-workflow.md`, Issue Creation Conventions, for labels and milestone). Report the issue URL.

## What This Skill Does NOT Do

- **Correctness or security review** — use `/mine-review`
- **Deep codebase audit** — use `/mine-audit`
- **Fix without asking** — it diagnoses, then asks what to fix
