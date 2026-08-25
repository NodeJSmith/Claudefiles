---
name: mine-clean-code
description: "Use when the user says: \"clean code check\", \"style review\", \"LLM smell check\", \"code hygiene\", \"nitpick this\", \"style check\", \"find style sins\", \"nitpicker review\", \"anal retentive review\", \"exhaustive style review\", \"no-filter style report\". Dispatches three parallel stylistic checkers — llm-checker (training-bias patterns), lazy-checker (deferred debt), and nitpicker (style hygiene) — and consolidates findings into a report organized by checker with a Summary section for orchestration consumption."
user-invocable: true
opencode-command: true
---

# Clean Code Review

Three-dimensional stylistic review: LLM training-bias patterns, deferred-debt patterns, and style hygiene. Not a correctness review — use `/mine-review` for that.

## Context

- Issue tracker: !`printenv ISSUE_TRACKER`

## Arguments

$ARGUMENTS — optional scope. Empty for full branch diff, or a directory/file list. Path mode when files exist with no branch changes.

## Phase 1: Determine Scope

Read and execute `${CLAUDE_CONFIG_DIR:-~/.claude}/skills/mine-review/scope-detection.md`.

**Code files only.** Filter out `.md` and other prose files. If no code files remain: "No code files in scope — use `/mine-review` for instruction files." Stop.

## Phase 1.5: Batching

If >30 changed files, partition into balanced batches of ~30. **Critical invariant:** chunk WITHIN each checker — each batch goes to all three checkers (3×K total dispatches). Each file appears in exactly one batch but receives all three lenses.

## Phase 2: Dispatch Three Parallel Checkers

Build a scope line:
- **Diff mode**: `Run: <diff command>. Read each changed file in full.`
- **Diff mode (batched)**: `Files in this batch: <file list>. Read each file in full.`
- **Path mode**: `Review these existing files (not a diff): <file list>`

Each agent has its own checklist and output format. Dispatch all three in one message (per batch if batched):

- `subagent_type: "llm-checker"` — `Review for LLM training-bias patterns. <scope line>`
- `subagent_type: "lazy-checker"` — `Review for deferred-debt patterns. <scope line>`
- `subagent_type: "nitpicker"` — `Review for style and hygiene issues. <scope line>`

If batched: merge each checker's findings across its batches before consolidation.

## Phase 3: Consolidate and Present

### Cross-checker duplicates

Because the checkers represent different quality dimensions, when two checkers flag the same file:line, keep both in their respective sections but note the cross-signal.

### Scope classification (diff mode only)

Checkers read each changed file in full, so findings can land on lines the diff never touched. Classify every finding:

- **In scope** — the finding's line falls inside a hunk this diff actually changed.
- **Out of scope** — the file is part of the diff, but the finding predates this PR.

Compute changed line ranges once per file with `<base diff command> -U0 -- <file>`, where `<base diff command>` is Phase 1's `git diff <base>...HEAD` or `git diff HEAD` — **not** the path-suffixed `<diff command>` a directory/file scope produces. Git only honors the first `--` as the pathspec separator, so appending `-U0 -- <file>` after an existing `-- <paths>` suffix would be parsed as a second, non-matching pathspec instead of scoping the diff, silently producing standard 3-line-context hunks instead of the exact 0-context ones this step needs.

Read the `@@ -a,b +c,d @@` hunk headers — a finding is in scope when its line falls within one of the `+c,d` ranges (count defaults to 1 when omitted), **or** when the finding's own description attributes it to a change made elsewhere in this diff (e.g., a helper newly dead because this diff deleted its last caller elsewhere in the file — the dead-code finding lands on the helper's unchanged definition, but the diff caused it). Judge the second case from what the finding's own text says caused it, not from line ranges and not from your own inference — this can't be checked mechanically, and only counts when the finding itself draws the causal link. Tag each finding inline by appending `(in scope)` or `(out of scope)` after its `file.ext:line` locator.

Path mode has no PR to be in or out of — skip this classification and treat every finding as in scope.

### Validity assessment

Apply the protocol from `${CLAUDE_CONFIG_DIR:-~/.claude}/skills/mine-challenge/findings-protocol.md`: findings are valid by default; flagging one as likely invalid requires a concrete evidence trail.

Likely-invalid findings move entirely into the report's Likely-invalid section (see below) and drop out of every other count — the per-checker Findings/Total numbers, and the in-scope/out-of-scope counts and checker sections — a finding that's both out-of-scope and likely-invalid is reported once, as likely-invalid. "Out of scope" (M, everywhere below) always means out-of-scope **and** not likely-invalid.

### Report

Organize by checker, not severity. Summary table:

```markdown
## Clean Code Review: [branch name or target path]

**Scope:** N files changed, +X/-Y lines (diff) | N files, X total lines (path)

| Checker | Findings | Verdict |
|---------|----------|---------|
| LLM Patterns | N | CLEAN / SMELLS (N) |
| Lazy/Debt | N | CLEAN / DEBT (N) |
| Nitpick | N | CLEAN / FINDINGS (N) |
| **Total** | **N** | |

**Likely-invalid:** N
**In scope / out of scope:** N in scope · M out of scope (diff mode only — omit this line in path mode)
```

Then checker sections with grouped findings, each tagged `(in scope)` / `(out of scope)` per the classification above (diff mode only — path-mode findings carry no scope tag, since Scope classification skips them entirely). Each finding includes the proposed fix — the specific edit that would be applied. The user decides what to fix based on seeing both the problem and the proposed edit. Likely-invalid findings in a separate section with Claimed/Actually/Why-invalid fields.

When invoked from `mine-orchestrate`, write `clean-code-summary.md` with `<!-- HEAD: <short-sha> -->` header followed by a narrative of what was fixed and what was left.

### Next steps

If all CLEAN, congratulate and stop. Otherwise, determine which condition applies before
building anything:

- **No out-of-scope findings, or path mode** — use the first gate below.
- **Out-of-scope findings exist (diff mode)** — resolve `$ISSUE_TRACKER` (captured in Context
  above) to a tool: `gh` → "GitHub", `jira` → "Jira", `clickup` → "ClickUp", `ado` → "Azure
  DevOps", anything else → the raw value title-cased. Don't guess at a tool — same check every
  other `$ISSUE_TRACKER` consumer in this repo makes (e.g. `skills/mine-create-issue/worker.md`
  Step 3). If you have tools for the resolved tracker, use the second gate. If the tracker is
  unset/empty, or you have no tools for it, use the third gate.

This is a major gate (clean code gate result, see `interaction.md`) — run `context-pct` and
prepend the result to the question in whichever gate you use.

**No out-of-scope findings, or path mode:**

```
AskUserQuestion:
  question: "[Context: N%] What would you like to do with these findings?"
  header: "Next steps"
  multiSelect: false
  options:
    - label: "Fix all"
      description: "Apply the proposed fixes listed above across all checkers, then re-read the modified content"
    - label: "Fix one checker's findings"
      description: "Pick a single checker to clean up now"
    - label: "Note and move on"
      description: "Acknowledged — no fixes this session"
```

**Fix all:** Work through llm-checker → lazy-checker → nitpicker findings top-to-bottom.

**Out-of-scope findings, tracker available:** Open with: `<Total> clean code findings.
<In-scope N> are in scope of this PR. <Out-of-scope M> are out of scope and will be filed as a
follow-up issue in <Tracker>.`

```
AskUserQuestion:
  question: "[Context: N%] <the line above> What would you like to do?"
  header: "Next steps"
  multiSelect: false
  options:
    - label: "Fix in scope, file the rest"
      description: "Apply fixes for in-scope findings, then file out-of-scope findings as one follow-up issue in <Tracker>"
    - label: "Fix everything now"
      description: "Apply the proposed fixes for all findings, in scope and out, then re-read the modified content"
    - label: "Fix one checker's findings"
      description: "Pick a single checker to clean up now"
    - label: "Note and move on"
      description: "Acknowledged — no fixes, no issue filed this session"
```

**Fix in scope, file the rest:** Work through in-scope findings only, top-to-bottom by
checker. Then file the out-of-scope findings — see "Filing out-of-scope findings" below.

**Out-of-scope findings, no usable tracker:** Open with: `<Total> clean code findings.
<In-scope N> are in scope of this PR. <Out-of-scope M> are out of scope, but no usable issue
tracker is available, so they won't be auto-filed.`

```
AskUserQuestion:
  question: "[Context: N%] <the line above> What would you like to do?"
  header: "Next steps"
  multiSelect: false
  options:
    - label: "Fix in scope, note the rest"
      description: "Apply fixes for in-scope findings; leave out-of-scope findings in the report, unfiled"
    - label: "Fix everything now"
      description: "Apply the proposed fixes for all findings, in scope and out, then re-read the modified content"
    - label: "Fix one checker's findings"
      description: "Pick a single checker to clean up now"
    - label: "Note and move on"
      description: "Acknowledged — no fixes, no issue filed this session"
```

**Fix in scope, note the rest:** Work through in-scope findings only. Leave out-of-scope
findings as-is in the report; nothing is filed.

**Fix everything now** (offered whenever out-of-scope findings exist): Work through
llm-checker → lazy-checker → nitpicker findings top-to-bottom, in scope and out.

**Fix one checker** (any gate): Present non-zero checkers as options. Work through the chosen
checker's findings (in scope and out — checker choice doesn't filter by scope). If >8 findings,
show 4 at a time. After completing a checker, offer to continue to another.

**Note and move on** (any gate): No fixes, nothing filed.

Make edits directly — only ask for confirmation on judgment calls. After fixes: "Fixes complete — run `/mine-review` before committing."

### Filing out-of-scope findings

Bundle every out-of-scope finding into a single issue — never file one per finding. Title:
`Clean code follow-ups: <branch name>`. Body: group by checker, each finding as `- **file:line**
— <description> → <proposed fix>`. Run `get-skill-tmpdir mine-clean-code` and write the body to
`<tmpdir>/issue-body.md` — pass it via the tracker's `--body-file`/`--description-file` flag or
its stdin equivalent, never as a raw shell argument (see `git-workflow.md` — Issue Creation
Conventions, which also covers labels and milestone). Report the issue URL in your final
message.

## What This Skill Does NOT Do

- **Correctness or security review** — use `/mine-review`
- **Deep codebase audit** — use `/mine-audit`
- **Automatic fixing without asking** — it diagnoses, then asks what to fix
