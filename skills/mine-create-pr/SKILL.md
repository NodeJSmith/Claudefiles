---
name: mine-create-pr
description: "Use when the user says: \"create PR\" or \"open pull request\". Reviews branch changes and creates a PR on GitHub or Azure DevOps."
user-invocable: true
---

# Create PR

Run these steps yourself, in order, in this conversation, using what you already know about the branch to skip re-deriving context.

If any step fails, stop and report which step failed and why. Do not carry on: Step 7 needs the PR number from Step 6, and Step 8 runs only when Step 6 succeeded and the Step 7 push landed (or Step 7 was legitimately skipped), because marking ready triggers reviewers and CI on the PR as it stands.

## Step 1: Review-Question Staleness Check

Before creating the PR, run `check-review-questions` (no arguments). It flags on file overlap alone, so its output tells you where to look, not that anything is stale. Read each flagged `REVIEW.md` against the branch diff and decide whether the change made a question wrong or opened a concern no question covers. If nothing did, say so in one line and continue. Otherwise update the questions the change made wrong so they match the current code, commit (`docs: update REVIEW.md review questions`), push, and name what you changed in one line. Knowingly opening a PR with stale review questions helps no one, so there is no skip option.

Ask only when the right edit is a real call, such as a question that no longer applies at all and deleting it would drop a concern the module still has:

```
AskUserQuestion:
  question: "<which REVIEW.md question and why the right edit is unclear>. What should happen to it?"
  header: "Review Q's"
  multiSelect: false
  options:
    - label: "Remove it"
      description: "The concern no longer applies"
    - label: "Rewrite it"
      description: "Keep the concern, reworded for the current code"
```

If `check-review-questions` produces no output, skip silently.

## Step 1b: Review-Question Coverage Check

Run `check-review-coverage` (no arguments). If it produces output, the branch touches source directories that have no `REVIEW.md` file. A missing file isn't a reason to add one. Judge which listed directories hold the cross-cutting concerns review questions are for (see `${CLAUDE_CONFIG_DIR:-~/.claude}/references/common/review-questions.md`). If none do, say so in one line and continue. Otherwise ask, listing only the directories that warrant questions and the concern each would cover:

```
AskUserQuestion:
  question: "<directories that warrant review questions, with the concern for each>. Add REVIEW.md files for them?"
  header: "Review Q's"
  multiSelect: false
  options:
    - label: "Add now (Recommended)"
      description: "Generate REVIEW.md files for the listed directories"
    - label: "Not now"
      description: "Skip for now — ask again in a few days"
    - label: "Never for these"
      description: "Permanently suppress this prompt for these directories"
```

- **"Add now"**: Read `${CLAUDE_CONFIG_DIR:-~/.claude}/references/common/review-questions.md` for the authoring rules (questions vs. assertions, cross-module pointer placement, size limit, worked example) — do not freehand a `REVIEW.md` from this bullet alone. For each directory named in the question, read the source files in it, identify the cross-cutting review concerns (data completeness, guard coverage, contract consistency, field propagation — the kinds of questions that catch bugs reviewers miss), and write a `REVIEW.md` following that guidance. For each module this directory depends on, add a cross-module pointer to *this* directory's own `REVIEW.md` naming that dependency — see `review-questions.md`'s placement rule for why the pointer goes here and not in the dependency's file. The reverse case (another module depends on this directory) is out of scope here: that module's own `REVIEW.md`, if it has one, is where its pointer back to this directory belongs — don't add it to this directory's `REVIEW.md`, and only touch that other file if it's also in the listed set. Commit (`docs: add REVIEW.md review questions`) and push.
- **"Not now"**: For each directory named in the question, write/update its state file with escalating deferral. Compute the state key: resolve the stable repo root via `git rev-parse --git-common-dir` → `dirname` → `cd` + `pwd -P`, then join it with the directory (`${main_repo_root}/${dir}`), and encode as `printf '%s' "$state_key" | sha256sum | cut -c1-16` (hashed, not character-substituted — this key appends a directory suffix to the repo root, unlike the `tr '/.' '--'` scheme used elsewhere for a repo-root-only key, so a distinct encoding avoids the collision a substitution scheme would risk here). Read the current tier from `${CLAUDE_CONFIG_DIR:-$HOME/.claude}/projects/<hashed-key>/review-coverage.json` (default tier 0), compute `prompt_after` as `today + [3,7,14,30][tier] days`, then bump tier by 1 (cap at 3) and write: `{"status": "deferred", "tier": <new_tier>, "prompt_after": "<computed date>"}`.
- **"Never for these"**: For each directory named in the question, write `{"status": "suppressed"}` to the same state file path.

If `check-review-coverage` produces no output, skip silently.

## Step 2: Gather Context

Run these commands and note the results:

```bash
git branch --show-current          # → current branch
git-default-branch                 # → default branch
git remote get-url origin 2>/dev/null  # → remote URL
git-branch-log                     # → commits on this branch
git-branch-diff-stat               # → diff summary
```

## Step 3: Platform and Preconditions

1. **Detect platform** by running `git-platform`. If output is `unknown`, stop and tell the user the platform is unsupported. If `github`, use `gh` CLI. If `ado`, use `az` CLI.
2. Verify the branch is pushed to remote (check `git status` for "Your branch is ahead" or "not yet pushed" messages). If not pushed, stop and tell the user the branch isn't pushed to the remote.
3. Check if a PR already exists for this branch:
   - **GitHub**: `gh pr list --head <branch-name>`
   - **Azure DevOps**: `az repos pr list --source-branch <branch-name> --status active`
   - If a PR exists, report its URL and stop (do not create a duplicate).

## Step 4: Analyze Changes

1. Analyze ALL commits in the branch (not just the latest) using `git log`
2. Use `git diff [base-branch]...HEAD` to see all code changes
3. Read key modified files if needed for additional context

## Step 5: Draft PR Body

Follow `git-workflow.md` (PR Description Content). The body records the shipped state and its durable rationale, not the process that produced it. You hold the whole session, including abandoned approaches, so draft from the branch diff and commit log as a reviewer will see them, and ask of each bullet: would this still be true to someone who never saw this session? Terse, not exhaustive, but terse is not the same as vague.

**Title:** < 70 characters, summarize the change.

**Conventional commit prefix** — check whether the target repo expects a type prefix on PR titles.
1. **Primary signal:** Check recent merged PRs (`gh pr list --state merged --limit 8 --json title` / `az repos pr list --status completed --top 8`). If ≥75% of returned PRs use a type prefix (minimum sample of 3), the convention is in use. If fewer than 3 merged PRs exist, skip to signal 2.
2. **Corroborating signals** (use when fewer than 3 merged PRs exist, or when 40–74% use prefixes): `release-please-config.json`, `.commitlintrc*`, `commitlint.config.*`, or commit-convention rules in the repo's `.claude/` directory. Any match confirms the convention is in use.
3. If the convention is in use, the title MUST start with a type prefix — one of: `feat`, `fix`, `refactor`, `docs`, `test`, `chore`, `perf`, `ci` (see `commit-conventions.md`). Squash-merge repos use the PR title as the changelog entry — a missing prefix breaks generation or silently omits it.
4. If no signal confirms the convention, use a plain descriptive title without a prefix.

**Body format:** Group changes by topic. For each logical area with multiple related changes, use an `### H3` header followed by bullet points. Order sections from most to least impactful.

Each bullet answers *what* changed and *why*: the problem it solves, the tradeoff of the approach taken. Never the sequence of attempts that led there. Do not write "tried X, ended up doing Y because Z" or otherwise narrate the development session, even when it's the most memorable part of the work. If an earlier approach's rejection is durably useful to record (it would stop a future reader from re-trying it), state the tradeoff as a fact about the shipped design instead of an account of having tried it: "X isn't done here because it breaks Y."

Skip mechanical or self-explanatory changes (renames, formatting, obvious refactors) that are incidental to a larger change, unless they need explaining. That skip doesn't apply when one of those same changes — or a dependency bump or typo fix — is the whole PR rather than a side effect of something bigger; applied literally there, it would leave the body empty. A standalone change like that still gets a terse one-line mention under Housekeeping below, not full narration. Not every file touched needs a bullet — a reviewer needs the load-bearing decisions, not an inventory of the diff.

Exception: if the PR includes changes to `./design/` (ADRs, design docs, decision records), don't re-explain that reasoning in the PR body — reference the document (e.g., "see `design/adr-012-auth-approach.md`").

Collect small, standalone changes into one or two ungrouped sections:
- **`### Notable Changes`** (top) — small but important changes worth seeing first
- **`### Housekeeping`** (bottom) — minor cleanup, dependency bumps, typo fixes, etc.
- Use both if needed, one if all small changes fall into the same category, or neither if everything fits under a topic header.

Example shape:

```markdown
### Notable Changes
- Important small change and why it matters

### Feature name or area
- What changed and why this approach was chosen over alternatives
- Any tradeoff future readers need to know, stated as a fact about the design — not as a retelling of how it was found

### Another significant area
- Change detail with its rationale

### Housekeeping
- Bump dependency X to v2
- Fix typo in README
```

**Closing issues** (GitHub only): Detect any issue this PR resolves and append a closing keyword on its own line at the end of the body. Check these sources in order:
1. **Branch name** — look for a leading or embedded issue number. Common patterns (extract `N`):
   - `N-description` (e.g., `123-fix-null`)
   - `issue-N` or `issue/N`
   - `fix/N-description`, `feat/N-description`, `chore/N-description`, etc.
2. **Commit messages** — scan `git log` output for GitHub closing keywords followed by an issue number (e.g., `Fixes #123`, `Closes #123`, `Resolves #123`). Do NOT match generic references like `refs #123`.
3. **Sketch ledger** — if the branch builds a sketch ledger, take every key on its `**Issues:**` line. Use judgment about whether the branch is actually that ledger's work: a ledger touched only in passing, such as an Addendum appended to an already-built one, doesn't close its issues.
- If found, append `Closes #N` per issue.
- Skip for Azure DevOps.

## Step 6: Create PR (Draft)

1. Run `mktemp -d <scratchpad>/mine-create-pr-XXXXXX` to create a temp directory
2. Write the PR body to `<dir>/body.md`
3. Create the PR:
   - **GitHub**:
     ```bash
     gh pr create --draft --title "..." --body-file <dir>/body.md
     ```
   - **Azure DevOps**: Read the body file content, then pass it as a literal string:
     ```bash
     az repos pr create --draft true --title "..." --description "<body content>" --source-branch <branch> --target-branch <default-branch>
     ```

## Step 7: Write CHANGELOG Entry

Locate the nearest `CHANGELOG.md` using the ancestor-walk algorithm: walk upward from the current working directory one level at a time toward the repo root, checking each directory for `CHANGELOG.md`. The first one found is the nearest. If none found by walking up, run `git ls-files '*CHANGELOG.md'` and pick the result with the shortest relative path from CWD. If no `CHANGELOG.md` exists anywhere, skip this step.

Once located:

### 7a: Determine if the branch deserves a changelog entry

Analyze the full branch diff (`git diff origin/<base>...HEAD`) — not individual commits:
- **Add an entry** for: new features, user-facing bug fixes, behavior changes, new integrations, breaking changes.
- **Skip silently** for: fixing tests, lint/format cleanup, internal refactoring with no behavior change, code comments/docstrings, typo fixes in code.
- If the branch already has changelog entries (check `git diff origin/<base>...HEAD -- <changelog-path>`), keep them as-is and skip to step 7b.

If adding an entry, **match the existing changelog structure**: read the file to determine whether it uses `## [Unreleased]` sections or date-based sections (`## YYYY-MM-DD`). Add entries under the appropriate heading — either the existing `[Unreleased]` section or today's date section (creating it if needed). Keep them **high-level and terse** — one bullet per logical change, describing what changed for the user, not implementation details.

### 7b: Annotate entries with PR number

1. Extract the PR number from the PR URL
2. Use the platform-appropriate prefix:
   - **GitHub**: `#` (e.g., `(#123)`)
   - **Azure DevOps**: `!` (e.g., `(!123)`)
3. Use `git diff origin/<base>...HEAD -- <changelog-path>` to identify lines added in this branch (including any just written in 7a)
4. For each newly added changelog entry line (lines starting with `- `) that does not already contain a PR reference (`(#...)` or `(!...)`), append ` (#<PR_NUMBER>)` for GitHub or ` (!<PR_NUMBER>)` for Azure DevOps
5. If there is anything to commit, stage only `<changelog-path>` (the working tree may hold unrelated edits) and commit: `docs: update changelog for PR #<NUMBER>` (or `!<NUMBER>` for ADO)
6. Push

## Step 8: Mark PR Ready

- **GitHub**: `gh pr ready`
- **Azure DevOps**: `az repos pr update --id <PR_ID> --draft false`

## Step 9: Present Result

Present the PR URL on its own line, preceded by any notes (e.g., no CHANGELOG found). If a step failed, say which step and why instead of a URL.

## Azure DevOps Notes

- Infer org, project, and repo from the remote URL where possible (e.g., `https://dev.azure.com/{org}/{project}/_git/{repo}`)
- Do not use `--auto-complete` or `--delete-source-branch` flags
- The `az repos pr create` command returns JSON; extract the PR URL from the response
