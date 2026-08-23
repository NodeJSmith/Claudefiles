# Changelog

## 2026-08-23

- `pipeline build-validate`'s `--branch` no longer defaults to `master` outright; it now resolves the
  repository's actual default branch via `_get_default_branch()` when omitted, matching `pipeline
  create`'s existing auto-detection. Repos that default to `develop`, `main`, or anything else now get
  a correctly targeted build validation policy instead of one silently pointed at `master`. (#534)

## 2026-08-19

- **Breaking:** Port `ado-api` from the analytics monorepo into Claudefiles as a standalone package,
  replacing the two-year-old v0.1.0 pydantic-settings fork wholesale. The CLI framework migrates from
  pydantic-settings to cyclopts (`cli.py`, `cli_context.py`, and `cli_models/` are deleted outright and
  replaced by `cli/__init__.py` and `cli/context.py`), bringing five commands the fork lacked
  (`builds missed-prod`, `builds retry-stage`, `builds steps`, `pipeline create`,
  `pipeline build-validate`), retries via `tenacity`, and the parse-bug fix already covered below.
- **Breaking:** Drop the `rhyme-constants` dependency. The four build-tag helpers it provided
  (`pr_tag_variants`, `DEPLOYMENT_TAG_PREFIXES`, `TAG_PR_RE`, `TAG_PROD_RE`, `TAG_STAGE_RE`, plus the
  rest of the same module) are now vendored as `src/ado_api/tags.py`. These encode one organization's
  build-tag conventions (`pr=`/`PR-`, `stage=`, `prod=`); `builds missed-prod`, `builds retry-stage`,
  and `builds approve`'s PR-tag lookup depend on them and will find nothing at an org that tags builds
  differently — this is expected, not a bug.
- `ado-api setup`'s configuration hint no longer names a specific organization or project — it prints
  a generic `az devops configure --defaults organization=https://dev.azure.com/YOUR-ORG
  project='Your Project'` placeholder instead.
- Drop the `<3.13` Python cap; the `>=3.12` floor is unchanged.
- Re-apply the two Claudefiles-only features that don't exist upstream: `--description-file` on
  `pr create`, `pr update`, `pr work-item-create`, and `work-item create`, and `--body-file` on
  `pr thread-add` and `pr reply` — both accept `-` to read from stdin. Grafted onto the new cyclopts
  CLI layer without touching the underlying `commands/*.py` business logic.
- Add `--branch` to `builds approve`, scoping the pending-approval listing the same way every sibling
  branch-filtering command already does. Omitting it leaves behavior unchanged; it has no effect once
  approving specific IDs.

## 2026-08-10

- **Breaking:** Migrate the CLI framework from pydantic-settings to cyclopts — `cli.py`, `cli_context.py`, and the entire `cli_models/` directory are deleted outright and replaced by `cli/__init__.py` (a cyclopts `App` with a meta-app launcher carrying global `--json`/`--project` flags) and `cli/context.py` (an `AdoCliContext` dataclass replacing the `ContextVar`-based `--project` threading)
- **Breaking:** Reshape the `logs` command group around the ADO resources it actually queries — `logs list` (a misnomer; it lists per-run timeline/step records, not logs) becomes `builds steps <build-id>`; `logs get`/`logs errors`/`logs search` are removed and merged into a single `logs read <build-id>` with orthogonal selector (`--step`/`--failed`/`--log-id`) and content (`--issues`/`--tail`|`--head`/`--grep`/`--context`) flags. Fixes a live parse bug in `logs errors --with-log [N]` (an argparse monkeypatch that silently misparsed when the flag preceded its positional build ID) by deleting the optional-value-flag mechanism entirely — no flag in the new surface uses that shape
- **Breaking:** Seven flags renamed from underscore-case to kebab-case: `--yml_file_name`→`--yml-file-name`, `--queue_id`→`--queue-id`, `--match_kind`→`--match-kind`, `--identifier_kind`→`--identifier-kind`, `--is_enabled`→`--is-enabled`, `--is_blocking`→`--is-blocking`, `--path_filter`→`--path-filter`
- **Breaking:** `builds approve` drops the `-p` short flag — PR-ID mode is now the unconditional default when `-b`/`--build` is absent, so `builds approve 49846` replaces `builds approve -p 49846`. Typing the removed `-p` now produces a standard unknown-option error instead of a silent no-op
- **Breaking:** `ado-api` with no subcommand now prints help and exits 0 (previously exited 1 via a string-matching hack on `SettingsError`)
- **Breaking:** `--json` passed to `setup`, `pipeline create`, or `pipeline build-validate` is now silently accepted and ignored, where it previously rejected with a parse error — these commands have no JSON output path either way, but a scripted caller relying on the old parse error to detect misuse will no longer get one
- A real ADO REST API failure (`AdoApiError` — 404, permission denial, rate limit) propagating uncaught to the CLI now gets its own exit code (5) with a clean `Error: <message>` line, instead of falling into the generic catch-all's "This may be a bug" message
- `builds retry-stage`'s "exactly one of `--build`/`--tag`/`--pr`" rule is now enforced by a cyclopts group validator during argument parsing (exit code 1, before any API call), rather than a function-body check reachable only at execution time
- Free-text parameters that can plausibly begin with a hyphen (`pr reply`'s body, `pr thread-add --body`, `pr create --description`, `logs read --grep`, `work-item --fields`) now correctly accept literal values that look like flags, matching pre-migration behavior

## Unreleased

- Add `builds retry-stage` to re-run a stage (default `prod`) on completed builds, selected by `--pr`, `--tag`, or `--build`. Recovers releases whose prod approval timed out — the stage completes as `skipped` while the build still reports `succeeded`, so the miss is otherwise silent. Supports `--exclude` for superseded pipelines, `--dry-run`, and `--watch` (polls each requeued build's stage until it reaches a terminal state or timeout)
- Fix `builds approve` hiding requeued releases — it filtered builds to `inProgress`, but a build whose stage was re-run reverts to `notStarted` while the new attempt waits on the gate
- Fix `builds approve -p pr-123` (lowercase hyphenated) silently matching nothing — PR-tag normalization is now case-insensitive, via a shared `pr_tag_variants` helper that replaces the duplicated prefix-stripping logic
- Refactor the column-aligned table printer into `formatting.aligned_table`, replacing three near-identical implementations in `missed-prod`, `approve`, and `retry-stage`
- Refactor the org+project REST URL prefix into an `AdoConfig.base_url` property, replacing 17 hand-built copies across 8 command modules
- Refactor the variadic-argument cap into a shared `variadic_limit_validator`, replacing three separately-declared `_MAX_VARIADIC_ITEMS` constants whose error wording had already drifted apart

## 0.1.0

- Fix `pipeline create` producing definitions with no agent pool — every build failed instantly with "No pool was specified". The queue and triggers are now set at creation time, with the queue auto-detected from the project's hosted pools (preferring non-legacy) and overridable via `--queue_id`. Queue lookup needs the Agent Pools (Read) PAT scope; PATs without it fall back to an `az login` AAD token
- Fix `pipeline build-validate --path_filter` accepting only one glob — repeat the flag to scope validation to multiple paths
- Fix `pr work-item-create/add/remove` — linking always failed due to wrong REST endpoint
- Migrate CLI from argparse to pydantic-settings (typed models, no behavior change)
- Migrate 6 remaining `az` CLI subprocess commands to direct REST API calls
- Add `builds approve` for listing and approving pending release approvals
- Add `--project` flag for cross-project targeting
- Add PR title descriptions to `builds missed-prod` output
- Add friendly error messages with setup hints for auth/config failures
- Add `builds missed-prod` to find releases deployed to stage but not prod
- Add `pr work-item-list/add/remove/create` for PR work item linking
- Add `work-item create` for standalone work item creation
- Add `pr` subcommands for PR and thread management (list, show, create, update, threads, reply, resolve, resolve-pattern)
- Add `--json` flag per-subcommand (flags now work after the subcommand)
- Initial release — Azure DevOps build and log inspection CLI (ported from personal Dotfiles)
