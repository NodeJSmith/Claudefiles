---
name: mine.changelog-review
description: "Use when the user says: 'clean up the changelog', 'review the release PR', 'changelog review', 'prep the release'. Reviews and rewrites the release-please changelog PR with user-facing descriptions."
user-invocable: true
---

Review the open release-please PR's changelog, rewrite auto-generated entries into user-facing descriptions, and push the result. Works with any repo using release-please with conventional commits.

## Context

- release-please config: !`cat release-please-config.json 2>/dev/null || echo "not found"`
- Changelog quality rule: !`cat .claude/rules/changelog-quality.md 2>/dev/null || echo "no rule file"`

## Phase 1: Find the release PR

1. Run `gh pr list --search "chore(main): release" --state open --json number,title,headRefName --limit 5` to find the release-please PR.
2. If no PR found, tell the user there's no open release-please PR and stop.
3. If multiple, ask which one.
4. Fetch and checkout the release-please branch: `git fetch origin <headRefName> && git checkout <headRefName>`.

## Phase 2: Analyze the changelog

1. Read `CHANGELOG.md` and identify the **new release section** (the topmost `## [x.y.z]` heading that doesn't exist on the default branch yet).
2. Find the previous release tag from the compare link in the heading.
3. List commits between the two releases: `git log --oneline <prev-tag>..<new-release-base>`.
4. For each commit that produced a changelog entry, fetch the PR body: `gh pr view <pr-number> --json title,body`. Use the PR number from the `(#NNN)` reference in the commit subject.
5. Classify each entry:
   - **User-facing**: features, bug fixes, breaking changes visible to app authors
   - **Internal**: CI, test infra, prior art research, refactoring with no behavior change, docs that are developer-internal (not user docs)
6. For breaking changes (`feat!:`, `fix!:`), extract the migration details from the PR body.

## Phase 3: Rewrite

Rewrite the new release section following these rules:

- **Remove internal entries** — CI, test infrastructure, prior art research, internal refactoring. If the `docs:` entry describes user-facing documentation changes (tutorials, API reference), keep it; otherwise remove.
- **Expand vague entries** — replace commit-subject echoes with descriptions from the PR body that explain what changed for users.
- **Group by feature area** — if 5+ entries remain, organize into topic sections (e.g., "### Scheduler", "### Bus", "### Web UI", "### Bug Fixes") instead of flat "### Features" / "### Bug Fixes" lists.
- **Rewrite breaking changes** — each breaking change must explain: (1) what changed, (2) what user code is affected, (3) what to do about it. Use the PR body's breaking change details.
- **Format** — use `- ` bullet points with bold lead-in for breaking changes (e.g., `- **Field type narrowing (StrEnum)** — description (#NNN)`). Include issue numbers as `(#NNN)`, no commit SHAs.
- **Preserve the heading format** — keep `## [x.y.z](compare-link) (date)` exactly as release-please generated it.

## Phase 4: Also check recent past releases

Scan the 2–3 release sections below the new one. If any still have the raw release-please format (flat `### Features` / `### Bug Fixes` with commit-SHA links), flag them:

```
AskUserQuestion:
  question: "I also found unreviewed changelog entries in older releases (v0.X.Y, v0.X.Z). Should I clean those up too?"
  header: "Older entries"
  multiSelect: false
  options:
    - label: "Yes, clean them all"
      description: "Rewrite older releases to match the same quality standard"
    - label: "No, just the new release"
      description: "Only edit the current release section"
```

If the user says yes, apply the same rewrite rules to those sections.

## Phase 5: Review and push

1. Show the user a summary of changes: entries removed, entries rewritten, breaking changes added/improved.
2. Present the rewritten section(s) for approval.

```
AskUserQuestion:
  question: "The changelog has been rewritten. Ready to push to the release-please branch?"
  header: "Push"
  multiSelect: false
  options:
    - label: "Push it"
      description: "Commit and push the edited CHANGELOG.md to the release-please branch"
    - label: "Let me review first"
      description: "Show the full diff before pushing"
```

3. If approved, commit with message `docs: rewrite changelog with user-facing descriptions` and push to the release-please branch.
4. If the user wants to review, show the diff and wait for approval.
