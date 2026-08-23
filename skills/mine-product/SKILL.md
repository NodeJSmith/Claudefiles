---
name: mine-product
description: "Use when the user says: \"create product context\", \"generate product.md\", \"set up product context\", \"document this product\", or \"update product context\". Generates or refreshes a product.md for the current repo via inference + interview."
user-invocable: true
opencode-command: true
---

# Product Context

Generates or refreshes a `product.md` for the current repo — a standing artifact that tells Claude what kind of thing this is, who uses it, and what reviewers must never get wrong. The file gets `@`-loaded in `CLAUDE.md` so this context is always in scope.

Adapted from the [product.md open standard](https://product.md).

---

## Phase 1: Detect Mode

Check whether `product.md` already exists at the repo root:

```bash
test -f product.md && echo "exists" || echo "new"
```

- **exists** → this is a **refresh** run. Read the existing file. Proceed to Phase 2 with that content as the starting baseline.
- **new** → this is a **create** run. Proceed to Phase 2 with a blank slate.

---

## Phase 2: Inference

Gather information from every available source before asking the user anything. The goal is to arrive at the interview with a draft answer for most questions, so the interview confirms or corrects rather than interrogates from scratch.

### 2a. Repo structure

Read these if they exist:
- `README.md` — purpose, audience, usage examples
- `CLAUDE.md` — any existing product or audience context
- `pyproject.toml` / `package.json` / `Cargo.toml` — package description, entry points

```bash
# Identify the repo name
basename $(git rev-parse --show-toplevel)
```

### 2b. Design files

Use the Glob tool to find design docs:

```
Glob: design/**/*.md
```

Read any design docs found — they often contain the clearest statement of what the product is and why.

### 2c. GitHub issues and PRs

Pull recent signal — what are users actually struggling with, asking for, and confused by? This is more reliable than documentation for understanding real usage.

```bash
# Recent issues — titles and labels are enough
gh issue list --limit 40 --json number,title,labels,state 2>/dev/null

# Recent PRs — titles and first 200 chars of body reveal what's being built and why
gh pr list --limit 20 --state all --json number,title,body 2>/dev/null | \
  jq '.[] | {number, title, body: (.body // "" | .[0:200])}' 2>/dev/null
```

Scan for patterns: recurring complaint types, common use cases mentioned, environments or configurations that come up repeatedly, things users expected to work that didn't.

### 2d. Memory recall

Search past conversations for product-relevant context — decisions made, problems surfaced, things the user has explained about this codebase:

Invoke `/ccr-recall` with a query targeting this repo's product context. Use the repo name and terms like "users", "framework", "API", "usage", "audience", "what it's for".

---

## Phase 3: Draft and Interview

### Build the draft

From everything gathered in Phase 2, draft answers for each product.md section. Classify each answer's confidence:

- **inferred** — source material provides a *specific, actionable* answer. The bar is high: "a tool for developers" does not yield an inferred Users answer; "Python developers building Home Assistant integrations" does. If the source material only mentions the topic without specificity, classify as **unknown**, not inferred.
- **uncertain** — partial signal that points in a direction but needs confirmation
- **unknown** — no signal found, or signal too generic to be actionable

### Interview

Present the draft to the user, section by section, for anything **uncertain** or **unknown**. For **inferred** answers, present them and ask for confirmation or correction — don't ask open-ended questions when you already have a specific answer.

**One AskUserQuestion per ambiguity**, except for Reviewer Invariants — see that section below.

Key things that must be nailed down before writing:

1. **Type** — what kind of thing is this?
   - Framework or library (code other developers import and build on)
   - CLI tool (command developers or end users run directly)
   - Service or API (something other systems call)
   - App (something end users interact with directly)

2. **Users** — who actually uses this, and what are they trying to accomplish? Be specific: "Python developers building Home Assistant integrations" not "developers".

3. **Usage patterns** — how is it used day-to-day? Invocation style, integration patterns, typical workflow.

4. **Boundaries** — what is this explicitly NOT? What adjacent things belong elsewhere?

5. **Reviewer invariants** — what must reviewers, critics, and auditors never get wrong about this codebase? Reviewers cause the most damage here: a wrong invariant silently permits bad advice in every future session.

   **Named failure mode:** users rarely volunteer invisible constraints — things so obvious to them they never think to mention. After the initial answer, always push with: *"Has a reviewer or critic ever suggested something that was clearly wrong for this codebase?"* That answer is usually the real invariant. This section permits multiple follow-up turns — the one-per-ambiguity rule does not apply here. Probe until you have specifics about what correct reviewers know that incorrect ones miss.

   Things to probe for:
   - Things that look wrong but aren't (e.g., "methods that appear unused are public API")
   - Environments or configurations the code must handle that aren't obvious (monorepos, unusual setups, specific config patterns)
   - Stability or compatibility requirements
   - Anything that's caused a reviewer to give wrong advice in the past

---

## Phase 4: Write product.md

Write to `<repo-root>/product.md`:

```markdown
# Product: <repo-name>

<!-- Generated by /mine-product on YYYY-MM-DD. Re-run to update. -->

## Type

<framework | library | cli-tool | service | app | other>

## Register

<!-- brand: the interface/API surface IS the product — every design decision is a product decision -->
<!-- product: the product serves a deeper purpose — design is a means to an end -->
<brand | product>

## Users

<who uses this, in language they'd use to describe themselves and their goals>

## Problem

<what breaks, gets painful, or stays unsolved without this>

## Purpose

<what it does; what "working well" looks like from the user's perspective>

## Usage Patterns

<how users interact day-to-day — invocation, integration, typical workflows>

## Boundaries

<what this is explicitly NOT; what's out of scope; what adjacent things belong elsewhere>

## Reviewer Invariants

<!-- These apply in every code review, audit, and challenge in this repo. -->
<!-- If a reviewer or critic contradicts these, they are wrong. -->

<bullet list of non-negotiables — things critics must never suggest, things that look wrong but aren't, constraints every review must respect>
```

Populate every section from the interview and inference results. The target reader is Claude running a code review or challenge six months from now with no other context — be specific enough that the artifact is useful to a reader who has never spoken to the user.

For **Reviewer Invariants**, write them as direct, unambiguous statements. Examples of good invariants:
- "This is a public API framework. Methods that appear unused in this repo are used by downstream consumers. Never suggest removing them."
- "Users run this inside monorepos with unusual directory structures. Configuration assumptions must be validated, never hardcoded."
- "This CLI is run daily by real users. Every UX change must consider the muscle memory and scripting patterns of existing users."

**Quality check before saving:** if the invariants you've written would apply equally to any similar repo — any Python library, any CLI tool, any service — they are not specific enough. Start the Reviewer Invariants section over.

---

## Phase 5: CLAUDE.md Integration

Check whether `CLAUDE.md` exists and whether it already loads `product.md`:

```bash
# Check if CLAUDE.md exists
test -f CLAUDE.md && echo "exists" || echo "missing"

# If it exists, check for the @product.md loading line (not just a mention in a comment)
grep -qE '^\s*@product\.md' CLAUDE.md 2>/dev/null && echo "loaded" || echo "not-loaded"
```

- **CLAUDE.md missing + not-loaded** → ask:

```
AskUserQuestion:
  question: "CLAUDE.md doesn't exist yet. Create it with @product.md, or skip integration for now?"
  header: "Integration"
  multiSelect: false
  options:
    - label: "Create CLAUDE.md with @product.md"
      description: "I'll create a minimal CLAUDE.md that loads product.md"
    - label: "Skip — I'll handle it"
      description: "Leave CLAUDE.md alone; you add the reference manually"
```

  If "Create": write a minimal `CLAUDE.md` containing only `@product.md`.

- **CLAUDE.md exists, not-loaded** → ask:

```
AskUserQuestion:
  question: "Add @product.md to CLAUDE.md so it loads automatically in every session?"
  header: "Integration"
  multiSelect: false
  options:
    - label: "Yes — add it automatically"
      description: "I'll add an @product.md reference to your CLAUDE.md"
    - label: "I'll add it manually"
      description: "You handle the placement"
```

  If "Yes": read CLAUDE.md, find a sensible insertion point near the top (after any frontmatter, before the main content), and add `@product.md`.

- **loaded** → nothing to do. Confirm: "product.md is already loaded in CLAUDE.md."

---

## Phase 6: Confirm

Report what was written and where. For refresh runs, briefly note what changed from the prior version.

If this is a **create** run, suggest the next step:
> "product.md is live. Consider running `/mine-grill` or `/mine-define` on your next feature — both will now have product context in scope."
