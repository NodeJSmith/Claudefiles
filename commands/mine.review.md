---
description: Run code-reviewer and integration-reviewer in parallel on the current branch diff.
---

# Review Command

Run both reviewers in parallel on the current branch's changes. Use this for ad-hoc review before committing, or any time you want a quality check on your work.

## Determine the diff

Get the base branch:

```bash
git-branch-base
```

If that fails (e.g., on `main` with no upstream diff), fall back to `HEAD` (review only staged/unstaged changes).

## Launch reviewers

Launch both agents **in parallel** using a single message with two Agent tool calls:

### Code Reviewer

```
Agent(subagent_type: "code-reviewer"):
  prompt: |
    Review all changes on this branch compared to the base branch.

    Run: git diff <base>...HEAD

    This repo may or may not have tests/linters — check before running them.
    Focus on correctness, types, security, performance, and style.
```

### Integration Reviewer

```
Agent(subagent_type: "integration-reviewer"):
  prompt: |
    Review all changes on this branch for integration issues.

    Run: git diff <base>...HEAD

    Check for duplication, convention drift, misplacement, orphaned code,
    and design violations.
```

## Present results

After both agents complete, present a unified summary:

1. **Code review verdict** — APPROVE / WARN / BLOCK + finding count by severity
2. **Integration review verdict** — PASS / WARN / BLOCK + dimensions checked
3. **Action items** — list any CRITICAL/HIGH findings that need fixing

If both approve with no CRITICAL/HIGH issues, say so concisely.
