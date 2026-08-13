---
tool: claude  # harness-only: the code-reviewer/wtf-reviewer agent gate, cfl, and mine-* skills are Claude-Code-specific
---

# Git Workflow

Claude-Code-specific git workflow. Tool-agnostic git and commit hygiene lives in `commit-conventions.md`.

## Pre-commit Hook Validation

Before your first commit in a repo during a session, check for a hook config. Repos may use either runner — check `prek.toml` first, since `pre-commit` cannot read prek's native TOML format:

1. **Detect config and runner** — `Read(<repo-root>/prek.toml)`. If present, runner is `prek` — stop here. Otherwise `Read(<repo-root>/.pre-commit-config.yaml)` (also check `.yml`); if present, runner is `pre-commit`, unless the top of the file is a comment stating it's managed by prek instead (prek can also read this YAML format; a repo that hasn't migrated to prek's native TOML yet may still run prek against it — rare, but the comment is an explicit, unambiguous signal when it occurs). If neither file exists, skip.
2. **Check if the runner is installed** — `prek --version` or `pre-commit --version` as appropriate. If missing, prompt user to install (`mise use prek` covers prek).
3. **Determine hook types** — scan config for `default_install_hook_types:`, `stages:`, `default_stages:` (YAML), or `stages = [...]` per-hook (prek's TOML).
4. **Check if hooks are installed** — first check `git config --get core.hooksPath`; if unset, use `git rev-parse --git-common-dir` + `/hooks`. Test for each hook type file.
5. **Install missing hooks** — `prek install -t <type>` or `pre-commit install -t <type>` for each missing type.

**Worktree note:** When `core.hooksPath` is not set, all worktrees share `.git/hooks/` via `git-common-dir`.

## Mandatory Code Review Before Commit

**ALWAYS run `code-reviewer`, `integration-reviewer`, and `wtf-reviewer` before committing code changes.** All three run in parallel on the final diff.

Exceptions: documentation-only changes (READMEs, changelogs, comments) or explicit user skip. Skill files, rules, agent prompts, and CLAUDE.md are **not** documentation-only — they are instructions that affect agent behavior and must be reviewed. `/mine-review` routes these to instruction-mode reviewers automatically.

### Code Reviewer Loop

Loop until no CRITICAL/HIGH issues remain:
1. Auto-fix unambiguous issues; defer to user for judgment calls
2. Re-run `code-reviewer`
3. Stop when no CRITICAL/HIGH remain

Then run `integration-reviewer` and `wtf-reviewer` in parallel on the final diff.

## Code Review vs Challenge

Code review and challenge are **orthogonal quality gates** with different scopes. One does not substitute for the other.

- **Code review** catches: correctness, style, obvious bugs, regressions
- **WTF review** catches: readability traps, confusing naming, code that works but will puzzle the next reader
- **Challenge** catches: design coherence, fragility, anti-patterns, cross-cutting concerns, missing edge cases

A green code review does not mean challenge is unnecessary. A green test suite is necessary but not sufficient — tests verify expected behavior, not unexpected behavior.

## Issue Creation Conventions

When creating issues with `gh-issue create`, match the conventions already in use in the repo:

1. **Run `gh-issue overview`** — shows milestones, labels, and usage patterns in one command. Run once per session or when switching repos; no need to re-run for each issue in a batch.
2. **Assign a milestone** if >50% of recent issues have milestones — pick the milestone that fits the work's scope or timeline. Use `--milestone "name"` on create.
3. **Apply labels** if >50% of recent issues have labels — use existing labels consistent with the repo's patterns. Don't invent new labels without asking.

When in doubt about which milestone or labels to use, ask the user.

## Task File Cleanup

Before committing changes (whether via `/mine-ship`, `/mine-commit-push`, `/mine-create-pr`, or a manual commit), check for task files via `find design/specs -path '*/tasks/T*.md' -print -quit 2>/dev/null`.

**No output → nothing to do.** If the `find` prints nothing (no task files exist, or `design/specs/` doesn't exist), skip this section entirely and continue with the commit.

**Output → archive before committing.** If task files exist, run `cfl archive --dry-run`. If the output has `"status": "would_archive"`, run `cfl archive` to remove `tasks/` directories and set `**Status:** archived` in the preserved `design.md` — then include those deletions in the commit. Do not ask — just archive and commit the cleanup alongside the other changes.

Task files must never reach a PR. Git history preserves the full content.

## Worktree Baseline Testing

When you need to run tests against the default branch (e.g., to confirm a failure is new), do not stash and switch branches. If the main repo is already on the default branch, run the tests there directly using its path. The main repo is the worktree's parent — find it via `git -C <worktree> worktree list`.

## Changelog Timing

Do not add changelog entries during feature work or at commit time. Changelog entries belong at PR creation, when the full branch diff is known and the entry can describe the shipped change coherently. `mine-create-pr` handles this automatically.

Adding entries mid-feature produces noisy, granular, often-wrong entries that accumulate across multiple commits and don't reflect what actually shipped.

## Commit Attribution

Attribution disabled globally via `$CLAUDE_CONFIG_DIR/settings.json`.
