# Design: Port the analytics ado-api (cyclopts) into Claudefiles

**Date:** 2026-08-19
**Status:** archived
**Mode:** sketch

## Problem

`Claudefiles/packages/ado-api` is a v0.1.0 pydantic-settings fork that has fallen ~2 years behind
its sibling at `analytics/packages/ado-api` (v0.2.0, cyclopts). The Claudefiles copy is missing five
commands, retries, and the cyclopts framework that `rules/personal/python-packaging.md` mandates for
new CLIs. It also still carries a parse bug the migration fixed: `logs errors --with-log [N]` used an
argparse monkeypatch for optional-value flags that silently misparsed when the flag preceded its
positional build ID. The cyclopts surface has no flag of that shape, so the mechanism is deleted
rather than repaired — it rides along with the wholesale copy and needs no separate task.

Jessica now works at two ADO shops (Rhyme and Orion), so the personal copy — not the work-monorepo
copy — needs to be the good one.

## Goals

- Claudefiles' `ado-api` is functionally equal to the analytics copy, minus its Rhyme-repo coupling.
- The two Claudefiles-only features (`--body-file` / `--description-file`, with `-` for stdin) survive the port.
- The package installs and runs standalone at both jobs with no `rhyme-constants` and no per-job config code.
- Claudefiles docs and skills stop referring to commands the port removes.

## Non-Goals

- **No anti-drift mechanism.** This is a deliberate fork that will diverge from analytics again. No
  sync script, no shared upstream, no drift check.
- **No changes to `rhyme-claude-code/packages/ado-api`.** Jessica is handling that copy separately.
- **No changes to `analytics/packages/ado-api`.** Read-only source.
- **No config plumbing for build-tag conventions.** The vendored tag constants are module defaults.
- **No branch-role configuration.** Deferred to a follow-up done on the Orion machine — see
  "Deferred: multi-org branch roles" below.

## Functional Requirements

- **FR#1** The `ado-api` package in Claudefiles exposes the analytics command surface: `builds list/cancel/cancel-by-tag/steps/approve/missed-prod/retry-stage`, `logs read`, `pipeline create/build-validate`, `pr` (13 subcommands), `work-item create`, `setup`.
- **FR#2** The package imports nothing from `rhyme_constants`; the build-tag helpers it needs live in a vendored module inside `ado_api`.
- **FR#3** `ado-api setup`'s configuration hint names no specific organization or project.
- **FR#4** `pr create`, `pr update`, `pr thread-add`, `pr reply`, `pr work-item-create`, and `work-item create` each accept a file-backed alternative to their inline text argument (`--description-file` / `--body-file`), where `-` reads stdin.
- **FR#5** Supplying both the inline text and its `--*-file` counterpart is a usage error; supplying neither, where the value is required, is also a usage error.
- **FR#6** The package builds and installs via `uv tool install -e packages/ado-api` on Python 3.12 and later.
- **FR#7** Claudefiles skills and reference docs describe only commands that exist after the port.
- **FR#8** `builds approve` accepts an explicit `--branch` that scopes the pending-approval listing, matching the override every sibling branch-filtering command already offers. With the flag omitted, behavior is unchanged.

## Acceptance Criteria

- **AC#1** `grep -rn "rhyme_constants" packages/ado-api/src packages/ado-api/tests` returns nothing. (FR#2)
- **AC#2** `uv run --project packages/ado-api pytest` passes with zero failures, with `rhyme-constants` not installed in the environment. (FR#1, FR#2)
- **AC#3** `ado-api --help` lists `builds`, `logs`, `pipeline`, `pr`, `work-item`, `setup`; `ado-api builds --help` lists `retry-stage`, `missed-prod`, and `steps`; `ado-api logs --help` lists `read` and does not list `errors`, `get`, `search`, or `list`. (FR#1)
- **AC#4** `ado-api setup` output contains neither `priorauthnow` nor `Analytics Platform`. (FR#3)
- **AC#5** For each of the six commands in FR#4, `--help` shows the file flag, and a test proves the file's contents reach the underlying `cmd_*` function; one test per flag family proves `-` reads stdin. (FR#4)
- **AC#6** A test per command proves that passing both inline and file forms exits non-zero with an error naming both flags, and that omitting both where required exits non-zero. (FR#5)
- **AC#7** `uv tool install -e packages/ado-api` completes without error and the installed `ado-api --help` runs; the test suite passes under Python 3.12 and under 3.14. (FR#6)
- **AC#8** `grep -rn "logs errors\|logs get\|logs search\|logs list" skills/ rules/ REFERENCE.md` returns nothing. (FR#7)
- **AC#9** `ado-api builds approve --help` shows `--branch`; a test proves the value reaches the approvals request URL as `branchName=refs/heads/<value>`, and a second test proves the URL is unchanged when the flag is omitted. (FR#8)
- **AC#10** `grep -rn '"master"' packages/ado-api/src` returns the same three sites after FR#8's change as before it — the new flag adds an override without altering any default. (FR#8)

## Approach

### Wholesale replacement, not a merge

The cyclopts migration deleted `cli.py`, `cli_context.py`, and the entire `cli_models/` directory and
replaced them with `cli/` — every command module changed alongside. Cherry-picking would produce a
fourth divergent variant. So: copy the analytics `src/` and `tests/` trees over the Claudefiles ones
wholesale, then apply the de-Rhyming and the file-flag graft on top of the result.

`src/ado_api/git.py` is already byte-identical across both copies, so it is the one file the copy
does not disturb.

### Vendoring the Rhyme coupling

`rhyme-constants` has four `import` sites and no test imports it — but **five** textual occurrences.
The fifth is a docstring cross-reference at `commands/approve.py:145`
(`` :func:`rhyme_constants.ado_tags.pr_tag_variants` ``) that no import-level fix would touch, and
AC#1's grep is a plain text search that will catch it. It gets repointed at `ado_api.tags` alongside
the imports.

| File | Imports | Disposition |
|---|---|---|
| `commands/setup.py` | `ADO_ORG_URL`, `ADO_PROJECT` | Do **not** vendor. One print statement (line 90) becomes a generic placeholder: `az devops configure --defaults organization=https://dev.azure.com/YOUR-ORG project='Your Project'`. |
| `commands/approve.py` | `pr_tag_variants` | Vendor |
| `commands/retry_stage.py` | `pr_tag_variants` | Vendor |
| `commands/missed_prod.py` | `DEPLOYMENT_TAG_PREFIXES`, `TAG_PR_RE`, `TAG_PROD_RE`, `TAG_STAGE_RE` | Vendor |

The vendored surface becomes `src/ado_api/tags.py`, copied from
`analytics/packages/rhyme-constants/src/rhyme_constants/ado_tags.py` (~96 lines). Copy the whole
module, not just the four consumed names — `format_pr_tag`, `format_commit_tag`, `parse_tags_to_dict`,
`TAG_COMMIT_RE`, and `TIMESTAMP_RE` are the rest of one coherent tag-format contract, and splitting it
would leave a module that is hard to reason about. Its docstring must be rewritten: the analytics
version names producers and consumers (`tag_pipeline_run.py`, `workflow_creator.py`, `dbx-pipeline-health`)
that do not exist here. Replace it with a statement that these are Rhyme's build-tag conventions,
that `builds missed-prod` / `retry-stage` / `approve`-by-PR-tag depend on them, and that those three
commands are inert at an org whose pipelines tag differently.

Port `analytics/packages/rhyme-constants/tests/test_ado_tags.py` (151 lines) as `tests/test_tags.py`.

### Grafting the file flags onto cyclopts

`cli/commands/*.py` is a thin parse-and-dispatch layer over `commands/*.py`, so the graft is confined
to the CLI layer and does not touch business logic.

`resolve_file_text()` moves from the deleted `cli_context.py` into the new `cli/context.py`, unchanged —
its signature already covers every case needed (`required`, `inline_name` for positional arguments).
Its tests move from `tests/test_cli_context.py` into the analytics `tests/test_context.py`.

Each of the six sites gains a keyword parameter and one resolve call:

| Command function | Current text param | Added flag |
|---|---|---|
| `cli_pr_create` | `description` (keyword) | `--description-file` |
| `cli_pr_update` | `description` (keyword) | `--description-file` |
| `cli_pr_work_item_create` | `description` (keyword) | `--description-file` |
| `cli_work_item_create` | `description` (keyword) | `--description-file` |
| `cli_pr_thread_add` | `body` (required keyword) | `--body-file` |
| `cli_pr_reply` | `body` (**required positional**) | `--body-file` |

The last two need care. `cli_pr_thread_add`'s `body` and `cli_pr_reply`'s positional `body` are
currently required; adding a file alternative means each must become optional at the parser level,
with `resolve_file_text(..., required=True)` enforcing "exactly one" afterward. For `cli_pr_reply`
this means an optional positional following two required positionals (`pr_id`, `thread_id`) — pass
`inline_name="<body>"` so the error text reads `<body> and --body-file` rather than inventing a
`--body` flag that does not exist. The four `description` sites are optional already, so they take
`required=False` (the default) and no parser change.

Keep the existing `Parameter(allow_leading_hyphen=True)` on the inline params — dropping it would
regress the analytics fix that lets a body start with `-`.

### One test carries a hidden dependency on the ambient git repo

`tests/test_entrypoint_pin.py::TestBuildsMissedProdDispatch::test_missed_prod_defaults` asserts the
request URL contains `branchName=refs/heads/master`. It patches `call_ado_api`, `get_pat`, and
`get_ado_config` — but **not** `_get_default_branch`, which shells out to the `git-default-branch`
script against whatever repo the tests are running in.

That works in analytics, whose default branch is `master`. Claudefiles' is `main`, so this test fails
after the port. Measured, not predicted: a rehearsal of the port in a scratchpad copy under both 3.12
and 3.14 passes 504/504 with an analytics-shaped remote and fails exactly this one test once the
remote is Claudefiles' own.

Fix by patching `_get_default_branch` in the test so the assertion is deterministic. Do not "fix" it
by asserting against the dynamically resolved branch — that makes the assertion tautological and
tests nothing. The behavior under test is "missed-prod defaults to the repo's default branch," which
a mock expresses directly.

This also removes a latent network dependency: `git-default-branch` can consult the remote, so the
unmocked test's result varies with connectivity.

### The rest of the suite needs a parseable `origin`

Roughly 20 tests call `_get_repo_or_exit()` and fail if the working directory has no `origin` remote.
Claudefiles has one, and `get_repo_name()` resolves its GitHub SSH URL to `Claudefiles` via the
non-ADO fallback branch, so the suite is fine here. Worth knowing so a run from a detached scratch
directory is not misread as a port regression.

### Python version range

`requires-python` becomes `">=3.12"` — the floor is unchanged from analytics, only the `<3.13` cap
is dropped.

The cap is a work-monorepo pin with no meaning here. It was tested rather than assumed: a scratchpad
rehearsal of the fully ported package (tags vendored, `rhyme-constants` removed) installs and runs
**504/504 tests green under both 3.12 and 3.14**, with wheels available for all three runtime deps.
Keeping the cap would refuse a working interpreter for no reason.

The floor deliberately stays at 3.12. An earlier draft of this design lowered it to 3.11, which would
have required rewriting the PEP 695 generic at `cli/limits.py:13`
(`def variadic_limit_validator[T](...)`, the only 3.12+ construct in the tree). That rewrite buys
nothing: `install.py` installs this package with `uv tool install -e`, and uv downloads a managed
interpreter when the local one does not satisfy `requires-python`, so the floor never gates
installability on any machine. Leave `limits.py` as-is.

### pyproject

Start from the analytics file. Remove `[tool.uv.sources]` and the `rhyme-constants` dependency;
remaining runtime deps are `cyclopts>=4.16`, `pydantic>=2.0,<3`, `tenacity>=9.0,<10`. Drop
`pydantic-settings` and `yarl` (the Claudefiles copy's deps — neither is used post-port). Keep the
setuptools backend.

The two dependency groups **cannot be folded verbatim** — their `pytest` pins do not intersect. The
target has `pytest>=8.0`, the source has `pytest>=7.4.2,<8`; combining both entries yields an
unsatisfiable spec. Keep `pytest>=8.0` and drop the `<8` cap, which is the same category of stale
work-monorepo pin as `requires-python`'s `<3.13`. Verified rather than assumed: the rehearsal
resolves `>=8.0` to pytest 9.1.1 and runs 503 passed / 1 failed, where the single failure is the
known `test_missed_prod_defaults` ambient-branch issue that T01 Step 5 fixes — not a pytest
incompatibility. The `pytest-mock` pins are identical in both (`>=3.12.0,<4`) and merge cleanly.

`readme = "README.md"` is a real trap: analytics declares it but has no such file, so the key comes
across as a **build failure** the moment `uv tool install -e` runs. Writing the README (see below) is
therefore load-bearing, not optional polish.

### README

`RhymeAnalyticsDocumentation/References/CLI-Tools/ado-api.md` (90 lines) is a useful structural seed
but is **stale** — it documents `builds approve -p`, which the cyclopts migration removed. Use it for
section layout only and write the content from the actual `--help` output of the ported CLI.

### Downstream Claudefiles updates

Only three files outside the package need edits. I checked `install.py` and `tests/test_install.py`:
the tip text at `install.py:1690` already says "pull requests, builds, pipelines, and work items", and
`test_install.py` uses `"ado-api"` only as a package-name fixture. Neither changes.

- `skills/mine-address-pr-issues/SKILL.md:147` — `ado-api logs errors <build-id>` no longer exists →
  `ado-api logs read <build-id> --failed --issues`.
- `rules/common/capabilities-core.md` — the existing `ado-api builds` / `logs` / `pr` / `work-item`
  rows survive; add trigger rows for `retry-stage`, `missed-prod`, `pipeline`, and `builds steps`.
- `REFERENCE.md:308` — the one-line package description gains pipelines and retries.
- `CHANGELOG.md` (repo root) — an entry for the port. Per `git-workflow.md` this lands at PR
  creation, not during feature work, so it is out of scope for the tasks here.

Verified as still valid, needing no edit: `pr show --json` and `pr threads {PR} --json --all`. The
cyclopts meta app accepts `--json` both before and after the subcommand (`tests/test_cli_init.py:86`
and `:100` cover both positions), and `--all` survives as `Parameter(name="--all")`.

## Dependencies and Assumptions

- **Orion cannot be verified from here.** This session runs on Rhyme. Everything in the Smoke Test
  below is a Rhyme observation. The Orion claim rests on the fact that org/project come from
  `az devops configure --list` and the PAT from `SYSTEM_ACCESSTOKEN` → `ADO_PAT` →
  `~/.azure/azuredevops/personalAccessTokens` — no compiled-in identity anywhere. Re-run the smoke
  test on Orion before trusting it there; this is an accepted verification gap, not a covered case.
- **Branch defaults are Rhyme-shaped throughout** — every one of them resolves to `master` at Rhyme,
  which is correct there and wrong at Orion. Deferred, not fixed; see the next section.
- **`missed-prod`, `retry-stage`, and `approve`-by-PR-tag are Rhyme-shaped and will be inert at Orion**
  unless Orion's pipelines happen to use `pr=`/`stage=`/`prod=` build tags. Accepted deliberately —
  making the conventions configurable is deferred until Orion is known to need it.
- The analytics test suite is assumed to pass at its source before the copy. Confirm this first; a
  pre-existing failure carried across the copy would otherwise read as a port regression.

## Deferred: multi-org branch roles

Out of scope here, to be designed and built **on the Orion machine** where the relevant repos can be
inspected directly. This section exists so that session starts from findings rather than rediscovering
them. Nothing below is implemented by T01-T05; the code ports verbatim.

### The requirement

Rhyme has one branch role: feature → `master` → prod. Orion has two: `develop` is what feature
branches cut from and merge back to, `main` is what goes to prod. So the tool needs an *integration*
branch and a *production* branch, which happen to be the same value at Rhyme.

### Why this must be observed at Orion, not designed from here

`git-default-branch` and the ADO web UI **disagree** on Orion's `Prefect-2`: git resolves `develop`
(via `origin/HEAD`), while the ADO UI marks `main` as the default branch. And it varies by repo. So
there is no single authoritative source to derive from, which is why explicit flags plus explicit
configuration are needed rather than smarter detection. Confirming the actual per-repo spread is the
first task of that session.

### The five defaulting sites

| Site | Command | Role it wants |
|---|---|---|
| `commands/builds.py:200` | `builds cancel-by-tag` | integration |
| `cli/commands/pipeline.py:41` | `pipeline create` fallback | integration |
| `cli/commands/pipeline.py:57` | `pipeline build-validate` | integration |
| `commands/approve.py:36` | `builds approve` | production |
| `commands/missed_prod.py:180` | `builds missed-prod` | production |

Three hardcode the literal `"master"` (`cli/commands/pipeline.py:41`, `:57`, and
`commands/builds.py:35` as `_get_default_branch`'s fallback). The role assignments above are this
session's reading of intent, not verified against Orion's actual pipelines — treat them as a starting
hypothesis.

### The missing flag is already handled

`builds approve` was the one branch-filtering command with no `--branch` override. That gap is **not**
deferred — it is FR#8, built in T03, because it is a missing affordance at any org rather than an
Orion-specific one, and the config work below is easier to reason about once every command has an
explicit override. T03 adds the override without touching any default, so it does not prejudge
anything in this section.

### Configuration shape already chosen

A config file at `~/.config/ado-api/config.toml`, keyed by org with per-repo overrides (the per-repo
layer is required, since the branch model varies by repo at Orion):

```toml
[branches]              # fallback when nothing more specific matches
integration = "main"
production  = "main"

[org."priorauthnow"]    # Rhyme — both roles collapse to one branch
integration = "master"
production  = "master"

[org."<orion-org>"]
integration = "develop"
production  = "main"

[repo."<orion-org>/Prefect-2"]
integration = "develop"
production  = "main"
```

Suggested resolution order per role: explicit `--branch` flag → `[repo."<org>/<repo>"]` →
`[org."<org>"]` → `[branches]` → for the integration role only, `git-default-branch` → error.
Production falls back to the resolved integration branch, which makes Rhyme work with an empty config
file. Nothing should ever fall back to a hardcoded `"master"`, and an unresolvable branch should be a
clear error rather than a guess — the current failure mode is silently querying a branch that does
not exist and reporting no results.

## Smoke Test

Post-install, on Rhyme, against real ADO:

1. `ado-api setup` — every check reports `[ok]`, and the output names no specific org or project.
2. `ado-api builds list --top 5` — five real builds in an aligned table.
3. `ado-api logs read <build-id> --failed --issues` on a known-failed build — prints that build's
   failure lines. This is the command the `mine-address-pr-issues` edit points at, so it is the one
   that proves the doc change is correct rather than merely consistent.
4. `printf 'line one\nline two\n' | ado-api pr thread-add <pr-id> --body-file -` on a scratch PR —
   the thread appears in ADO with both lines intact. This is the whole point of the flag: multi-line
   markdown that would be mangled as a shell argument.
5. `ado-api pr threads <pr-id> --json --all | jq '.[0].id'` — confirms the JSON path the skills use.

Success: all five produce their expected output, and no invocation prints a traceback or the
"This may be a bug" catch-all.

## Changed Files

**Package — `packages/ado-api/`**

- delete: `src/ado_api/cli.py` — pydantic-settings root model, replaced by `cli/`
- delete: `src/ado_api/cli_context.py` — ContextVar project threading; `resolve_file_text` is salvaged first
- delete: `src/ado_api/cli_models/` (6 files) — pydantic-settings command models
- create: `src/ado_api/cli/__init__.py` — cyclopts `App`, meta launcher, completion commands
- create: `src/ado_api/cli/context.py` — `AdoCliContext` + `make_ado_context` + salvaged `resolve_file_text`
- create: `src/ado_api/cli/limits.py` — variadic cap, copied unchanged
- create: `src/ado_api/cli/commands/{__init__,builds,logs,pipeline,pr,work_item}.py` — parse-and-dispatch layer; `pr` and `work_item` also carry the file-flag graft
- create: `src/ado_api/tags.py` — vendored from `rhyme_constants.ado_tags`, docstring rewritten
- create: `src/ado_api/commands/{missed_prod,pipeline,retry_stage}.py` — new command implementations
- modify: `src/ado_api/commands/{approve,builds,logs,pr,setup,work_item}.py` — analytics versions; `setup.py` additionally loses its hardcoded org/project hint, and `approve.py` later threads an optional branch through `_builds_url` / `_get_in_progress_builds` / `cmd_builds_approve_list` (FR#8)
- modify: `src/ado_api/cli/commands/builds.py` — `cli_builds_approve` gains the `--branch` parameter (FR#8)
- modify: `src/ado_api/az_client.py` — adds `AdoConfig.base_url` and tenacity retries; drops `yarl`. `AdoApiError` already exists in both trees — what is new is the CLI giving it its own exit code, which lives in `cli/__init__.py`
- modify: `src/ado_api/formatting.py` — adds `aligned_table` and `osc8`
- unchanged: `src/ado_api/git.py` — already byte-identical
- delete: `tests/test_cli_models.py` — tests pydantic models that no longer exist
- delete: `tests/test_cli_context.py` — split into `tests/test_context.py` and the file-flag tests
- create: `tests/{test_context,test_cli_init,test_entrypoint_pin,test_limits,test_missed_prod,test_parse_args,test_pipeline,test_retry_stage}.py` — from analytics
- create: `tests/test_tags.py` — from `rhyme-constants/tests/test_ado_tags.py`
- create: `tests/test_file_args.py` — file/stdin flag coverage on the cyclopts surface
- create: `tests/golden/help_pipeline.txt` — help fixture for the new command group
- modify: `tests/golden/{help_root,help_builds,help_logs,help_pr,help_work_item}.txt` — argparse-shaped help output replaced by cyclopts-shaped
- unchanged: `tests/golden/{approve_partial_failure_baseline,resolve_partial_failure_baseline}.txt` — already identical across both trees
- modify: `tests/{test_approve,test_az_client,test_builds,test_cli,test_formatting,test_integration,test_logs,test_pr,test_setup,test_work_item}.py` — analytics versions
- create: `README.md` — required by `readme =` in pyproject; seeded from the (stale) analytics doc, written from real `--help`
- create: `CHANGELOG.md` — analytics changelog, with a port entry
- modify: `pyproject.toml` — cyclopts + tenacity deps, no `rhyme-constants`, no `[tool.uv.sources]`, `requires-python = ">=3.12"`

**Repo**

- modify: `skills/mine-address-pr-issues/SKILL.md` — `logs errors` → `logs read --failed --issues`
- modify: `rules/common/capabilities-core.md` — trigger rows for the new commands
- modify: `REFERENCE.md` — package description line
