---
description: Run code-reviewer and integration-reviewer in parallel on the current branch diff.
---

# Review Command

Run both reviewers in parallel on the current branch's changes. Use this for ad-hoc quality checks at any point during development.

## Determine the diff

Get the base branch:

```bash
git-branch-base
```

Choose the diff command based on the result:

- **Base found** → `git diff <base>...HEAD` (all committed changes on this branch)
- **Base not found** (e.g., on `main` with no upstream diff) → `git diff HEAD` (staged and unstaged changes against the last commit)

If there are no changes in either case, inform the user and stop.

## Launch reviewers

Launch both agents **in parallel** using a single message with two Agent tool calls:

### Code Reviewer

```
Agent(subagent_type: "code-reviewer"):
  prompt: |
    Review all changes on this branch.

    Run: <diff command from above>

    This repo may or may not have tests/linters — check before running them.
    Focus on correctness, types, security, performance, and style.
```

### Integration Reviewer

```
Agent(subagent_type: "integration-reviewer"):
  prompt: |
    Review all changes on this branch for integration issues.

    Run: <diff command from above>

    Check for duplication, convention drift, misplacement, orphaned code,
    and design violations.
```

## Present results

After both agents complete, present a unified summary:

1. **Code review verdict** — APPROVE / WARN / BLOCK + finding count by severity
2. **Integration review verdict** — PASS / WARN / BLOCK + dimensions checked
3. **Action items** — list any CRITICAL/HIGH findings that need fixing

If both approve with no CRITICAL/HIGH issues, say so concisely.
