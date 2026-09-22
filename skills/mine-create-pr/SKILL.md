---
name: mine-create-pr
description: "Use when the user says: \"create PR\" or \"open pull request\". Reviews branch changes and creates a PR on GitHub or Azure DevOps."
user-invocable: true
---

# Create PR

## Step 1: Review-Question Staleness Check

Before creating the PR, run `check-review-questions` (no arguments). If it produces output, present it to the user and ask:

```
AskUserQuestion:
  question: "This branch changes code referenced by REVIEW.md review questions (shown above). Want to update them before creating the PR?"
  header: "Review Q's"
  multiSelect: false
  options:
    - label: "Update now"
      description: "Open the flagged REVIEW.md files and update the review questions"
    - label: "Skip"
      description: "Create the PR without updating — questions may be stale"
```

- **"Update now"**: For each flagged `REVIEW.md` file, read it, read the changed code it references, and update the review questions to reflect the current code. Commit (`docs: update REVIEW.md review questions`) and push.
- **"Skip"**: Continue.

If `check-review-questions` produces no output, skip silently.

## Step 1b: Review-Question Coverage Check

Run `check-review-coverage` (no arguments). If it produces output, the branch touches source directories that have no `REVIEW.md` file. Present the list and ask:

```
AskUserQuestion:
  question: "These source directories were touched but have no REVIEW.md review questions. Want to add them?"
  header: "Review Q's"
  multiSelect: false
  options:
    - label: "Add now"
      description: "Generate REVIEW.md files for the listed directories"
    - label: "Not now"
      description: "Skip for now — ask again in a few days"
    - label: "Never for these"
      description: "Permanently suppress this prompt for these directories"
```

- **"Add now"**: Read `${CLAUDE_CONFIG_DIR:-~/.claude}/references/common/review-questions.md` for the authoring rules (questions vs. assertions, cross-module pointer placement, size limit, worked example) — do not freehand a `REVIEW.md` from this bullet alone. For each listed directory, read the source files in it, identify the cross-cutting review concerns (data completeness, guard coverage, contract consistency, field propagation — the kinds of questions that catch bugs reviewers miss), and write a `REVIEW.md` following that guidance. For each module this directory depends on, add a cross-module pointer to *this* directory's own `REVIEW.md` naming that dependency — see `review-questions.md`'s placement rule for why the pointer goes here and not in the dependency's file. The reverse case (another module depends on this directory) is out of scope here: that module's own `REVIEW.md`, if it has one, is where its pointer back to this directory belongs — don't add it to this directory's `REVIEW.md`, and only touch that other file if it's also in the listed set. Commit (`docs: add REVIEW.md review questions`) and push.
- **"Not now"**: For each listed directory, write/update its state file with escalating deferral. Compute the state key: resolve the stable repo root via `git rev-parse --git-common-dir` → `dirname` → `cd` + `pwd -P`, then join it with the directory (`${main_repo_root}/${dir}`), and encode as `printf '%s' "$state_key" | sha256sum | cut -c1-16` (hashed, not character-substituted — this key appends a directory suffix to the repo root, unlike the `tr '/.' '--'` scheme used elsewhere for a repo-root-only key, so a distinct encoding avoids the collision a substitution scheme would risk here). Read the current tier from `${CLAUDE_CONFIG_DIR:-$HOME/.claude}/projects/<hashed-key>/review-coverage.json` (default tier 0), compute `prompt_after` as `today + [3,7,14,30][tier] days`, then bump tier by 1 (cap at 3) and write: `{"status": "deferred", "tier": <new_tier>, "prompt_after": "<computed date>"}`.
- **"Never for these"**: For each listed directory, write `{"status": "suppressed"}` to the same state file path.

If `check-review-coverage` produces no output, skip silently.

## Step 2: Create PR

Launch one subagent (`subagent_type: standard-worker`):

> Create a PR for the current branch.
>
> Read `${CLAUDE_CONFIG_DIR:-~/.claude}/skills/mine-create-pr/worker.md` for the complete workflow. Follow every step in order. Do NOT use the Skill tool — the instructions are in worker.md, not a skill.

The subagent returns the PR URL, or an error message if something blocked it (unsupported platform, branch not pushed, PR already exists with its URL).

## Step 3: Present Result

Present the PR URL to the user.
