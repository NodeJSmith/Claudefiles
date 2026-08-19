---
task_id: "T01"
title: "Replace the ado-api package tree with the analytics cyclopts version, vendored and de-Rhymed"
status: "done"
depends_on: []
implements: ["FR#1", "FR#2", "FR#3"]
---

## Target Files

- delete: `packages/ado-api/src/ado_api/cli.py`
- delete: `packages/ado-api/src/ado_api/cli_context.py`
- delete: `packages/ado-api/src/ado_api/cli_models/__init__.py`
- delete: `packages/ado-api/src/ado_api/cli_models/builds.py`
- delete: `packages/ado-api/src/ado_api/cli_models/logs.py`
- delete: `packages/ado-api/src/ado_api/cli_models/pr.py`
- delete: `packages/ado-api/src/ado_api/cli_models/setup.py`
- delete: `packages/ado-api/src/ado_api/cli_models/work_item.py`
- delete: `packages/ado-api/tests/test_cli_models.py`
- delete: `packages/ado-api/tests/test_cli_context.py`
- create: `packages/ado-api/src/ado_api/cli/__init__.py`
- create: `packages/ado-api/src/ado_api/cli/context.py`
- create: `packages/ado-api/src/ado_api/cli/limits.py`
- create: `packages/ado-api/src/ado_api/cli/commands/__init__.py`
- create: `packages/ado-api/src/ado_api/cli/commands/builds.py`
- create: `packages/ado-api/src/ado_api/cli/commands/logs.py`
- create: `packages/ado-api/src/ado_api/cli/commands/pipeline.py`
- create: `packages/ado-api/src/ado_api/cli/commands/pr.py`
- create: `packages/ado-api/src/ado_api/cli/commands/work_item.py`
- create: `packages/ado-api/src/ado_api/tags.py`
- create: `packages/ado-api/src/ado_api/commands/missed_prod.py`
- create: `packages/ado-api/src/ado_api/commands/pipeline.py`
- create: `packages/ado-api/src/ado_api/commands/retry_stage.py`
- create: `packages/ado-api/README.md`
- create: `packages/ado-api/tests/test_tags.py`
- create: `packages/ado-api/tests/test_context.py`
- create: `packages/ado-api/tests/test_cli_init.py`
- create: `packages/ado-api/tests/test_entrypoint_pin.py`
- create: `packages/ado-api/tests/test_limits.py`
- create: `packages/ado-api/tests/test_missed_prod.py`
- create: `packages/ado-api/tests/test_parse_args.py`
- create: `packages/ado-api/tests/test_pipeline.py`
- create: `packages/ado-api/tests/test_retry_stage.py`
- create: `packages/ado-api/tests/golden/help_pipeline.txt`
- modify: `packages/ado-api/tests/golden/help_root.txt`
- modify: `packages/ado-api/tests/golden/help_builds.txt`
- modify: `packages/ado-api/tests/golden/help_logs.txt`
- modify: `packages/ado-api/tests/golden/help_pr.txt`
- modify: `packages/ado-api/tests/golden/help_work_item.txt`
- modify: `packages/ado-api/tests/golden/approve_partial_failure_baseline.txt`
- modify: `packages/ado-api/tests/golden/resolve_partial_failure_baseline.txt`
- modify: `packages/ado-api/src/ado_api/az_client.py`
- modify: `packages/ado-api/src/ado_api/formatting.py`
- modify: `packages/ado-api/src/ado_api/commands/approve.py`
- modify: `packages/ado-api/src/ado_api/commands/builds.py`
- modify: `packages/ado-api/src/ado_api/commands/logs.py`
- modify: `packages/ado-api/src/ado_api/commands/pr.py`
- modify: `packages/ado-api/src/ado_api/commands/setup.py`
- modify: `packages/ado-api/src/ado_api/commands/work_item.py`
- modify: `packages/ado-api/pyproject.toml`
- modify: `packages/ado-api/tests/test_approve.py`
- modify: `packages/ado-api/tests/test_az_client.py`
- modify: `packages/ado-api/tests/test_builds.py`
- modify: `packages/ado-api/tests/test_cli.py`
- modify: `packages/ado-api/tests/test_formatting.py`
- modify: `packages/ado-api/tests/test_integration.py`
- modify: `packages/ado-api/tests/test_logs.py`
- modify: `packages/ado-api/tests/test_pr.py`
- modify: `packages/ado-api/tests/test_setup.py`
- modify: `packages/ado-api/tests/test_work_item.py`

## Prompt

Replace the `ado-api` package in this repo with the newer version living in another repo on this
machine, removing that version's dependency on a private work package as you go.

**Source (read-only, never modify):** `~/source/rhyme/analytics/packages/ado-api`
**Target:** `packages/ado-api` in this repo.

Read `tasks/context.md` and `design.md` in this spec directory first. The design's "Approach"
section is authoritative for every decision below.

### Step 0 — establish the baseline

Before copying anything, run the source package's test suite at its own location and record the
result. A failure that already exists upstream must not be misread later as a port regression. If
the source suite is not green, stop and report rather than proceeding.

### Step 1 — salvage, then copy

`packages/ado-api/src/ado_api/cli_context.py` (target, about to be deleted) contains a function
`resolve_file_text()` plus its `_get_repo_or_exit` / `_get_repo_or_none` helpers. Save
`resolve_file_text()` somewhere you can retrieve it in Step 3 — it does not exist in the source
package and a later task depends on it. Its tests are in `packages/ado-api/tests/test_cli_context.py`
(the class covering `resolve_file_text`); save those too.

Then replace the target's `src/` and `tests/` trees with the source's, excluding `.venv/`,
`__pycache__/`, `.pytest_cache/`, and `*.egg-info/`. The result must contain no leftovers of the old
layout: no `cli.py`, no `cli_context.py`, no `cli_models/` directory, no `test_cli_models.py`, no
`test_cli_context.py`.

This includes `tests/golden/` — those are `.txt` help-output fixtures, not Python, so a copy filtered
to `*.py` would silently leave stale argparse-shaped expectations behind and fail the suite. Five
existing fixtures differ between the trees (the `help_*.txt` set), the two
`*_partial_failure_baseline.txt` files are already identical, and the source adds
`help_pipeline.txt`.

`src/ado_api/git.py` is byte-identical between the two packages; confirm that after the copy rather
than assuming it.

### Step 2 — vendor the tag constants

The copied tree imports `rhyme_constants`, which does not exist here. There are exactly four import
sites; the design's Approach section tables them.

Copy `~/source/rhyme/analytics/packages/rhyme-constants/src/rhyme_constants/ado_tags.py`
to `packages/ado-api/src/ado_api/tags.py`. Copy the **whole module**, not just the names currently
imported — it is one coherent tag-format contract and splitting it leaves something hard to reason
about.

Rewrite its module docstring. The original names producers and consumers that do not exist in this
repo (`tag_pipeline_run.py`, `workflow_creator.py`, `add_pr_comment.py`, `dbx-pipeline-health`).
Replace it with a docstring that says: these are one specific organization's build-tag conventions;
`builds missed-prod`, `builds retry-stage`, and `builds approve`'s PR-tag lookup depend on them; at
an organization whose pipelines tag builds differently, those three commands will find nothing. Say
that plainly — a future reader hitting empty output at a different job needs this to be the first
thing they find.

Repoint the three consuming modules (`commands/approve.py`, `commands/retry_stage.py`,
`commands/missed_prod.py`) at `ado_api.tags`.

**There are four imports but five textual occurrences.** `commands/approve.py:145` carries a
docstring cross-reference — `` :func:`rhyme_constants.ado_tags.pr_tag_variants` `` — that no
import-level fix touches. Repoint it too. The Verify grep below is a plain text search and will fail
if you fix only the imports.

`commands/setup.py` is different: it imports `ADO_ORG_URL` and `ADO_PROJECT` only to interpolate them
into a single hint string (around line 90 of the source). Do **not** vendor those constants. Drop the
import and make the hint generic, e.g.:

```
Run: az devops configure --defaults organization=https://dev.azure.com/YOUR-ORG project='Your Project'
```

Port `~/source/rhyme/analytics/packages/rhyme-constants/tests/test_ado_tags.py` to
`packages/ado-api/tests/test_tags.py`, repointing its imports.

### Step 3 — restore the salvaged helper

Put the salvaged `resolve_file_text()` into the new `src/ado_api/cli/context.py`, unchanged. The
source's `cli/context.py` already has `_get_repo_or_exit` and `_get_repo_or_none`, so only
`resolve_file_text` needs restoring — do not duplicate the repo helpers.

Merge the salvaged `resolve_file_text` tests into `packages/ado-api/tests/test_context.py` (which
arrived from the source), adjusting imports to the new module path.

**Do not** wire `resolve_file_text` into any command in this task. Task T02 owns that.

### Step 4 — pyproject

Start from the source's `pyproject.toml` and change:

- Remove the `[tool.uv.sources]` table and the `rhyme-constants` dependency. Runtime deps become
  `cyclopts>=4.16`, `pydantic>=2.0,<3`, `tenacity>=9.0,<10`. `pydantic-settings` and `yarl` (deps of
  the version being replaced) are no longer used — confirm by grep before removing, then remove.
- `requires-python = ">=3.12"` — drop the `<3.13` upper cap, keep the floor. The cap is a
  work-monorepo pin; the tree compiles clean under 3.13 and its runtime deps all support it, so the
  cap would refuse a valid interpreter for no reason. Do **not** lower the floor to 3.11 and do
  **not** rewrite the PEP 695 generic in `cli/limits.py` — `uv tool install` downloads a managed
  interpreter when the local one is too old, so a lower floor buys nothing.
- Merge the dependency groups so a plain `uv run pytest` works in this repo — but **not verbatim**.
  The target pins `pytest>=8.0` and the source pins `pytest>=7.4.2,<8`; those ranges do not
  intersect, so copying both entries in produces an unsatisfiable spec. Keep `pytest>=8.0` and drop
  the `<8` cap — it is a stale work-monorepo pin, and the suite has been confirmed green on pytest 9
  (503 passed, the one failure being the Step 5 issue below). `pytest-mock` is `>=3.12.0,<4` in both
  and merges cleanly.
- Keep the `setuptools.build_meta` backend.

The source declares `readme = "README.md"` but ships no such file, so that key is a latent build
failure. Create a short `packages/ado-api/README.md` — title, one-line description, and the
`uv tool install -e` line are enough here. Task T04 expands it into the full command reference.

### Step 5 — fix the one test that depends on the ambient git repo

`tests/test_entrypoint_pin.py::TestBuildsMissedProdDispatch::test_missed_prod_defaults` asserts the
request URL contains `branchName=refs/heads/master`. It patches `call_ado_api`, `get_pat`, and
`get_ado_config` — but not `_get_default_branch`, which shells out to the `git-default-branch` script
against whatever repo the suite runs in.

That resolves to `master` in the source repo and `main` in this one, so the test fails here as
copied. This has been confirmed by running it, not inferred — do not skip the fix on the assumption
it might pass.

Patch `_get_default_branch` in the test so the assertion is deterministic. Do **not** change the
assertion to compare against the dynamically resolved branch: that would make it tautological and
test nothing. The behavior under test is "missed-prod defaults to the repo's default branch," which
a mock states directly. Mocking also removes a latent network dependency, since `git-default-branch`
may consult the remote.

Check whether any sibling test in `TestBuildsMissedProdDispatch` or `tests/test_missed_prod.py` has
the same unmocked dependency, and give it the same treatment.

### Step 6 — verify

Run the target package's test suite in an environment where `rhyme-constants` is **not** installed.
That absence is the point of the exercise: a suite that passes only because a stale `rhyme-constants`
is still importable proves nothing. Then exercise the CLI's help surface directly.

## Verify

- [ ] FR#2 / AC#1: `grep -rn "rhyme_constants\|rhyme-constants" packages/ado-api/src packages/ado-api/tests packages/ado-api/pyproject.toml` returns nothing.
- [ ] FR#1 / AC#2: `uv run --project packages/ado-api pytest` passes with zero failures, in an environment without `rhyme-constants` installed. Paste the summary line. Run it from inside this repo — about 20 tests call `_get_repo_or_exit()` and fail in any directory with no `origin` remote, which is an environment artifact and not a port regression.
- [ ] FR#1 / AC#3: `ado-api --help` lists `builds`, `logs`, `pipeline`, `pr`, `work-item`, `setup`.
- [ ] FR#1 / AC#3: `ado-api builds --help` lists `retry-stage`, `missed-prod`, and `steps`.
- [ ] FR#1 / AC#3: `ado-api logs --help` lists `read` and lists none of `errors`, `get`, `search`, `list`.
- [ ] FR#3 / AC#4: `ado-api setup` output contains neither `priorauthnow` nor `Analytics Platform`.
- [ ] The old layout is gone: `cli.py`, `cli_context.py`, `cli_models/`, `test_cli_models.py`, and `test_cli_context.py` no longer exist under `packages/ado-api/`.
- [ ] `packages/ado-api/pyproject.toml` has `requires-python = ">=3.12"` with no upper cap, and `src/ado_api/cli/limits.py` is byte-identical to the source copy.
- [ ] `tests/golden/` contains `help_pipeline.txt`, and no golden fixture still shows argparse-style help output. Confirm with `diff -r` against the source's `tests/golden/`.
- [ ] `test_missed_prod_defaults` passes, and patches `_get_default_branch` rather than depending on the ambient repo. Prove the mock is real: the test still passes when run from a directory whose git default branch is not `master`.
- [x] `git -C ~/source/rhyme/analytics status --porcelain packages/` is empty — the source repo was not modified. (CONTESTED, accepted: two pre-existing untracked files in the unrelated `quicksight-assets` package predate this session; nothing under `ado-api/`/`rhyme-constants/` in the source repo changed.)
