---
task_id: "T03"
title: "Add an explicit --branch flag to builds approve"
status: "planned"
depends_on: ["T01"]
implements: ["FR#8"]
---

## Target Files

- modify: `packages/ado-api/src/ado_api/commands/approve.py`
- modify: `packages/ado-api/src/ado_api/cli/commands/builds.py`
- modify: `packages/ado-api/tests/test_approve.py`

## Prompt

`ado-api builds approve`, with no IDs, lists pending release approvals. To do that it fetches
candidate builds filtered to a single branch — and that branch is resolved internally with no way for
the caller to override it. Every sibling command (`builds list`, `cancel-by-tag`, `missed-prod`,
`retry-stage`, `pipeline create`, `pipeline build-validate`) already exposes `--branch`. This one is
the odd gap. Close it.

Read `tasks/context.md` and `design.md` in this spec directory first.

### Why this is in scope when branch *defaulting* is not

`context.md` forbids touching branch defaulting — the hardcoded `"master"` literals and the
integration-vs-production branch model are deferred to a follow-up built on a different machine
(design.md, "Deferred: multi-org branch roles"). This task does not violate that. It adds an
*override path* where none exists and changes no default: with `--branch` omitted, behavior is
byte-identical to the port. Do not "improve" the fallback while you are in the file.

### The call chain

```
cli_builds_approve            cli/commands/builds.py   — needs the new parameter
  -> cmd_builds_approve_list  commands/approve.py:153
    -> _get_in_progress_builds  commands/approve.py:71
      -> _builds_url            commands/approve.py:35  — where _get_default_branch() is called
```

Thread an optional branch through those four functions. `commands/approve.py:36` currently reads
`branch = _get_default_branch()`; it becomes the caller's value when given, and that same call when
not.

Note there are **two** different `_builds_url` functions in this package —
`commands/approve.py:35` (approvals-specific: adds `statusFilter` and `branchName`) and
`commands/builds.py:38` (a plain base URL). This task touches only the first. Do not change the
second or any of its callers.

### Scope of the flag: the listing path only

`builds approve` has two modes. With no IDs it lists pending approvals — branch-filtered, and the
mode this flag affects. With IDs it resolves them to builds and approves them; that path runs through
`resolve_pr_ids_to_builds`, which queries `_list_builds(ctx, tags=...)` with **no** branch filter on
purpose, because a PR's builds are identified uniquely by tag regardless of which branch they ran on.

Do not add branch filtering to the ID path. Narrowing a tag lookup by branch would silently drop
legitimate builds, which is a behavior change and a regression.

Because the flag is inert in ID mode, say so in its `help=` text rather than leaving a user to
discover it. Something to the effect of: applies when listing pending approvals; ignored when
approving specific IDs.

### Tests

Extend `tests/test_approve.py`, following the conventions already in that file. Cover:
- `--branch` reaches the request URL as `branchName=refs/heads/<value>`
- omitting `--branch` produces the same URL the pre-change code produced (a regression guard on the
  "changes no default" claim above)
- the ID path is unaffected by `--branch` — the tag query it issues carries no `branchName`

For the second case, mock `_get_default_branch` rather than depending on the ambient repo's default
branch, for the same reason T01 Step 5 does.

## Verify

- [ ] FR#8: `ado-api builds approve --help` shows `--branch`, and its help text states the flag applies to listing rather than to approving specific IDs.
- [ ] FR#8: a test proves `--branch release/x` reaches the approvals request URL as `branchName=refs/heads/release/x`.
- [ ] FR#8: a test proves that with `--branch` omitted, the URL is unchanged from the ported behavior.
- [ ] FR#8: a test proves the PR-ID path issues a tag query with no `branchName` filter, with or without `--branch`.
- [ ] `uv run --project packages/ado-api pytest` passes with zero failures.
- [ ] No branch *default* changed: `grep -rn '"master"' packages/ado-api/src` still returns the same three sites it did after T01 (`cli/commands/pipeline.py` twice, `commands/builds.py` once).
- [ ] `commands/builds.py`'s own `_builds_url` and its callers are untouched **by this task**. Since T01 already rewrote that file, compare against the state at this task's start rather than against `HEAD`: record the file's hash before you begin and confirm it is unchanged at the end.
