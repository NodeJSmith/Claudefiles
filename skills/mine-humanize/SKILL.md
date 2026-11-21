---
name: mine-humanize
description: "Use when the user says: \"humanize this\", \"unslop this\", \"de-slop this\", \"fix AI writing\", \"remove AI tells\", \"clean up AI prose\". Edits prose to remove AI writing patterns and add human voice. Analyzes, then fixes. Prose complement to mine-clean-code."
user-invocable: true
---

# Humanize

Edit existing prose (PR descriptions, commit messages, docs, research briefs, skill and rule files) so it stops reading as AI-generated. The tells are structural (negative parallelisms, tricolon lists, resolution closers) and lexical (delve, tapestry, crucial). Readers spot them and discount the text even when the content is right. For code quality use `/mine-clean-code`.

Done means the tells are gone, the meaning and every factual claim are unchanged, and the result doesn't read as sanded flat.

The pattern reference is `${CLAUDE_CONFIG_DIR:-~/.claude}/references/common/writing-quality.md`. Read it in full before analyzing.

## Arguments

$ARGUMENTS — a file, a directory (its `.md`, `.txt`, `.rst` files, skipping `node_modules` and `.git`; ask to narrow if there are more than 10), or empty. If empty, use staged prose files (`git diff --cached --name-only`); if none, ask what to humanize, accepting a path or pasted text. Pasted text goes to a temp file under `mktemp -d <scratchpad>/mine-humanize-XXXXXX` and is treated as general prose.

## How to approach it

**Match the register to the text.** Infer the type from path and content and say what you're treating it as: research briefs are analytical and may use first person; commit messages are terse and imperative; PR descriptions are narrative but tight and outcome-focused; instruction files (`skills/`, `rules/`, `agents/`) are direct and imperative with no hedging; docs and READMEs are clear and concrete; other prose is balanced with varied rhythm.

**Leave non-prose alone.** Code blocks, inline code, URLs, frontmatter, tables, HTML, file paths, and command examples are accuracy-critical or structurally fixed. Edit only the prose between them.

**Analyze, then fix.** Scan against the reference and number the findings across files so the user can refer to them: pattern, `file:line`, quoted text, suggested fix, grouped by file. End with the count by type. With zero findings, say so and stop.

**The invocation is the request to fix**, so choose the mode and go, naming it and why in one line:
- Surgical edits for a few scattered vocabulary or style issues. Subtract first, with minimal targeted changes that keep meaning and register. Then re-read the file from disk, which forces a real second reading, to catch cascading tells and sterile patches and, where the register allows, restore rhythm, specificity, and voice.
- Full rewrite when structural issues pervade most paragraphs. Rewrite from scratch in the target register, preserving all technical content, protected regions, and claims; show a before/after for each file and apply it only after the user accepts it, with options to adjust or reject.
- Cherry-pick only when the user named which findings to apply or skip: apply exactly those, report applied and skipped, and don't ask again.

**Protect against loss.** A tracked file with no uncommitted changes can be restored from git. For an untracked or uncommitted-changes target, back it up to a `mktemp -d <scratchpad>/mine-humanize-XXXXXX` directory before editing and say where.

When finished, summarize the files and changes made.

## Out of scope

Code quality (`/mine-clean-code`), preventing the patterns at writing time (`writing-quality.md` is loaded on demand for that), and scoring against AI detectors. This edits for quality, not to fool classifiers.
