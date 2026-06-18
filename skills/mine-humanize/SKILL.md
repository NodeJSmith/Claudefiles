---
name: mine-humanize
description: "Use when the user says: \"humanize this\", \"unslop this\", \"de-slop this\", \"fix AI writing\", \"remove AI tells\", \"clean up AI prose\". Edits prose to remove AI writing patterns and add human voice. Analyzes first, then asks how to fix. Prose complement to mine-clean-code."
user-invocable: true
---

# Humanize

Fix prose that reads as AI-generated. This skill edits text that already exists -- PR descriptions, commit messages, docs, research briefs, skill files, rule files. For code quality, use `/mine-clean-code`.

Agents default to generating text that reads as generated. The tells are structural (negative parallelisms, tricolon lists, resolution closers) and lexical (delve, tapestry, crucial). Readers develop an instinct for it and discount the text even when the content is correct.

The pattern reference is `${CLAUDE_HOME:-~/.claude}/references/common/writing-quality.md`. Read it in full before starting any analysis.

## Arguments

$ARGUMENTS -- the target. Can be:
- A file path: `/mine-humanize design/research/brief.md`
- A directory: `/mine-humanize design/` (processes all `.md` files)
- Empty: check for staged prose files first (`git diff --cached --name-only | grep -E '\.(md|txt|rst)$'`), then ask

If $ARGUMENTS is empty and nothing is staged:

```yaml
AskUserQuestion:
  question: "What should I humanize?"
  header: "Target"
  multiSelect: false
  options:
    - label: "Pick a file"
      description: "I'll give you a file or directory path"
    - label: "Paste text"
      description: "I'll paste text in the next message for you to edit"
```

If the user picks "Paste text", wait for their next message, then treat the pasted content as the target. Write it to a temp file (via `get-skill-tmpdir mine-humanize`), classify as "General prose", and proceed to Phase 2.

## Phase 1: Scope and Classify

### Resolve target files

If the target is a directory, find prose files:

```bash
find <path> -type f \( -name '*.md' -o -name '*.txt' -o -name '*.rst' \) -not -path '*node_modules*' -not -path '*/.git/*'
```

If more than 10 files, ask to narrow scope.

### Detect text type

For each file, infer the register from its path and content:

| Signal | Text type | Register |
|--------|-----------|----------|
| Path contains `design/` or file named `*brief*`, `*research*` | Research brief | Analytical, evidence-grounded, can use first person |
| Commit message (piped or `.gitmessage`) | Commit message | Terse, imperative, no filler |
| PR description or `PULL_REQUEST_TEMPLATE` | PR description | Narrative but tight, outcome-focused |
| Path under `skills/` or `rules/` or `agents/` | Instruction file | Direct, imperative, no hedging |
| Path under `docs/` or named `README*`, `CONTRIBUTING*` | Documentation | Clear, scannable, concrete examples |
| Other `.md` files | General prose | Balanced, specific, varied rhythm |

Surface the inferred type: "Treating `design/brief.md` as a research brief. Editing for analytical register."

## Phase 2: Analyze

### Content protection

Protect regions where accuracy is mandatory or the content is structurally fixed, not prose. Edits to these regions would corrupt meaning. Common cases:
- Fenced code blocks (``` or ~~~)
- Inline code (backticks)
- URLs and link references
- YAML frontmatter (between `---` markers at file start)
- Tables (lines starting with `|`)
- HTML tags and blocks
- File paths and command examples

Analyze only the prose between protected regions.

### Scan for patterns

Read each file and identify AI writing patterns from writing-quality.md. Number each finding sequentially across all files. For each:

```text
- **Finding N** — [Pattern name] (file:line): "quoted text" → suggested fix
```

Group by file, then by category (AI Vocabulary, Structural, Style, Communication). For multi-file targets, emit progress: `Scanning [N/total]: <filename>`.

End with a summary: `Found N issues across M files (X vocabulary, Y structural, Z style)`.

### Ask how to proceed

```yaml
AskUserQuestion:
  question: "Found {N} issues. How should I fix them?"
  header: "Fix mode"
  multiSelect: false
  options:
    - label: "Surgical edits"
      description: "Minimal targeted fixes — swap words, restructure sentences, cut filler"
    - label: "Full rewrite"
      description: "Reconstruct from scratch preserving meaning and technical content"
    - label: "Cherry-pick"
      description: "I'll tell you which finding numbers to apply (e.g. 1,3,5)"
    - label: "Done"
      description: "Report noted, no changes needed"
```

If zero findings: "No AI writing patterns found." Stop.

## Phase 3: Fix

### Surgical edits

Two-pass editing, one file at a time. For multi-file targets, emit progress: `Editing [N/total]: <filename>`.

**Pass 1 -- Subtract.** Fix the identified findings with minimal, targeted changes:
- Replace AI vocabulary with plain words
- Restructure negative parallelisms ("it's not X -- it's Y" → state Y directly)
- Break tricolon lists to their natural count (2 or 4 items)
- Cut resolution closers that restate what was just said
- Remove filler phrases, excessive hedging, chatbot phrases
- Fix em-dash and colon overuse (periods or commas)
- Cut significance inflation and abstract metaphor nouns
- Convert inline-header lists to prose where the bold label restates the line

Apply pass 1 edits via the Edit tool. Preserve the author's meaning and the text type's register.

**Pass 2 -- Re-read and add voice.** Read the file back from disk (this forces genuine re-reading of edited content, not continuation from the same context). This pass catches:
- Cascading tells: vocabulary fixes that exposed structural patterns, or structural fixes that created new vocabulary tells
- Sterile patches: sections where pass 1 removed everything interesting and left flat, lifeless prose
- Voice injection (for text types that warrant it): vary rhythm, add specificity, let opinions through where the register allows

Apply pass 2 edits. After all files are edited, show a summary:

```text
Edited N files, M changes total.
- file1.md: X changes (vocabulary: A, structural: B, style: C)
- file2.md: Y changes (...)
```

### Full rewrite

One file at a time. For each file:

1. Read the file and understand its meaning, intent, and factual claims
2. Generate the rewrite in memory (do not call Edit yet)
3. Present a before/after diff
4. Ask:

```yaml
AskUserQuestion:
  question: "Accept this rewrite of {filename}?"
  header: "Accept"
  multiSelect: false
  options:
    - label: "Accept"
      description: "Apply the rewrite"
    - label: "Adjust"
      description: "I'll tell you what to change"
    - label: "Reject"
      description: "Keep the original, skip this file"
```

Only call Edit on Accept. Rewrite from scratch in the target register -- preserve all technical content, protected regions, and factual claims but restructure freely.

### Cherry-pick

Show the finding numbers from Phase 2. Ask: "Which finding numbers should I apply? (e.g. 1,3,5)". Apply only the specified findings, report which were applied and which were skipped.

## What This Skill Does NOT Do

- **Code quality** -- use `/mine-clean-code` for LLM-bias patterns, deferred debt, and style hygiene in code
- **Prevention** -- `writing-quality.md` is a reference file loaded on demand via the Domain References meta-rule. This skill fixes text after the fact.
- **AI detection scoring** -- edits for quality, not to fool classifiers
