# ado-api

Azure DevOps CLI — builds, logs, pipelines, pull requests, and work items.

## Install

```bash
uv tool install -e packages/ado-api
```

## Auth and Configuration

The PAT is resolved in order, first hit wins:

1. `SYSTEM_ACCESSTOKEN` — set automatically inside Azure Pipelines CI.
2. `ADO_PAT` — explicit override for local / manual use.
3. `~/.azure/azuredevops/personalAccessTokens` — the `az` CLI's own cache, written when you run
   `az login` or `az devops login`.

Organization and project come from `az devops configure --list`. If neither is set, `ado-api setup`
tells you what to run:

```bash
az devops configure --defaults organization=https://dev.azure.com/YOUR-ORG project='Your Project'
```

Run `ado-api setup` any time to check that `az`, the `azure-devops` extension, defaults, and login
are all in place — it installs what's missing and prints `[ok]`/`[missing]` per prerequisite.

## Global Options

Every command accepts these, before or after the subcommand:

```bash
ado-api --json <command>        # JSON output instead of a formatted table (most commands)
ado-api --project <name> <command>  # target a project other than the configured default
```

`--json` has no effect on `setup`, `pipeline create`, or `pipeline build-validate` — none of the
three have a JSON output path.

## Commands

### Builds

```bash
ado-api builds list [--tags TAG] [--branch BRANCH] [--status STATUS] [--top N]
ado-api builds cancel BUILD-IDS...
ado-api builds cancel-by-tag TAG [--branch BRANCH]
ado-api builds steps BUILD-ID [--failed] [--type TYPE]
ado-api builds approve [IDS...] [-b/--build] [--branch BRANCH] [-y/--yes]
ado-api builds missed-prod [--days N] [--top N] [--pipeline TEXT] [--branch BRANCH]
ado-api builds retry-stage (--build IDS | --tag TAG | --pr PR) [--stage STAGE]
    [--exclude IDS] [--branch BRANCH] [-y/--yes] [--dry-run] [-w/--watch]
    [--watch-interval SECONDS] [--watch-timeout MINUTES]
```

`builds approve` with no IDs lists pending approvals. With IDs and no `-b`/`--build`, the IDs are
treated as PR IDs and expanded to the build(s) waiting on approval for that PR; pass `-b` to treat
them as raw build IDs instead. `--branch` scopes the *listing* only — it filters which pending
approvals are shown, and is ignored once you're approving specific IDs.

`builds retry-stage` requires exactly one of `--build`, `--tag`, or `--pr` (enforced during argument
parsing, before any API call). It re-runs a stage — `prod` by default — on builds whose stage
completed as `skipped` because an approval gate timed out. `--watch` polls each requeued build until
its stage reaches a terminal state or `--watch-timeout` minutes elapse.

**`missed-prod`, `retry-stage`, and `approve`'s PR-ID lookup depend on one organization's build-tag
conventions** (`pr=`/`PR-`, `stage=`, `prod=` — see `src/ado_api/tags.py`). They find matching builds
by parsing these tags off completed runs. At an organization whose pipelines tag builds differently,
these three commands will find nothing to act on — they aren't broken, there's just nothing to match.
Making the tag format configurable is deferred until a non-Rhyme org is known to need it.

### Logs

```bash
ado-api logs read BUILD-ID (--step ID | --failed | --log-id ID)
    [--issues] [--tail N | --head N] [--grep PATTERN] [--context N]
```

At least one selector (`--step`, `--failed`, `--log-id`) is required; the content flags (`--issues`,
`--tail`/`--head`, `--grep`) are independent of the selector and combine freely with each other and
with `--json`. `--failed` is the fastest path to understanding a build failure:

```bash
ado-api logs read <build-id> --failed --issues
```

### Pipelines

```bash
ado-api pipeline create NAME [--branch BRANCH] [--yml-file-name FILE]
    [--folder FOLDER] [--queue-id ID]
ado-api pipeline build-validate BUILDS... [--branch BRANCH]
    [--match-kind exact|prefix] [--identifier-kind id|name]
    [--is-enabled/--no-is-enabled] [--is-blocking/--no-is-blocking]
    [--path-filter GLOB]
```

`pipeline create`'s branch auto-detects from git when omitted, falling back to `master` if detection
fails. `pipeline build-validate`'s branch defaults to `master` outright. Queue lookup for `create`
needs the Agent Pools (Read) PAT scope; without it, the command falls back to an `az login` AAD
token.

### Pull Requests

`PR-ID` is optional on most subcommands — when omitted, it's auto-detected from the current branch.

```bash
ado-api pr list [--status STATUS] [--author AUTHOR] [--top N]
ado-api pr show [PR-ID]
ado-api pr create TITLE [--description TEXT | --description-file FILE]
    [--source BRANCH] [--target BRANCH] [--draft]
ado-api pr update PR-ID [--title TEXT] [--description TEXT | --description-file FILE]
    [--status STATUS] [--draft/--no-draft]
ado-api pr threads [PR-ID] [--all]
ado-api pr thread-add [PR-ID] (--body TEXT | --body-file FILE)
ado-api pr reply PR-ID THREAD-ID (BODY | --body-file FILE) [--parent COMMENT-ID]
ado-api pr resolve PR-ID THREAD-IDS... [--status STATUS]
ado-api pr resolve-pattern PR-ID PATTERN [--execute] [--first-comment] [--status STATUS]
```

`pr threads` shows active threads only by default; pass `--all` to include resolved ones.
`pr resolve-pattern` is dry-run by default — pass `--execute` to actually resolve the matches it
finds.

Every `--description`/`--body` argument above has a `--description-file`/`--body-file` counterpart
that reads the text from a file instead of the shell argument — pass `-` to read from stdin. Supply
exactly one of the pair; giving both, or (where the text is required) neither, is a usage error naming
both flags. This exists for multi-line markdown that a shell argument would mangle:

```bash
printf 'line one\nline two\n' | ado-api pr thread-add <pr-id> --body-file -
```

### Work Items

```bash
ado-api pr work-item-list [PR-ID]
ado-api pr work-item-add [PR-ID] --work-items ID...
ado-api pr work-item-remove [PR-ID] --work-items ID...
ado-api pr work-item-create [PR-ID] --title TEXT --type TYPE
    [--assigned-to EMAIL] [--area PATH] [--iteration PATH]
    [--description TEXT | --description-file FILE]
ado-api work-item create --title TEXT --type TYPE
    [--assigned-to EMAIL] [--area PATH] [--iteration PATH]
    [--description TEXT | --description-file FILE] [--fields KEY=VALUE...]
```

`pr work-item-create` and `work-item create` both accept `--description-file` (with `-` for stdin),
same rule as the PR text flags above.

### Setup

```bash
ado-api setup
```

Checks `az` CLI installation, the `azure-devops` extension, `az devops configure` defaults, and an
active `az login` session — installing what's missing where it can.

## Shell Completion

```bash
ado-api --install-completion          # auto-detects your shell
ado-api --install-completion --shell zsh
ado-api --generate-completion --shell zsh > /path/to/_ado-api  # print instead of install
```

For zsh, the installed script goes to `~/.zsh/completions/_ado-api`. That directory needs to be on
your `$fpath` before `compinit` runs, or the completion won't load — the command prints the exact
lines to add if they're missing:

```bash
fpath=(~/.zsh/completions $fpath)
autoload -Uz compinit && compinit
```

Restart your shell (or `exec zsh`) after installing.

## Common Workflows

**Why did the build fail?**

```bash
ado-api builds list --branch feature/jsmith/my-branch --status failed
ado-api logs read <build-id> --failed --issues
ado-api logs read <build-id> --failed --grep "Exception"
```

**Approve a pending release:**

```bash
ado-api builds approve              # see what's pending
ado-api builds approve <id> -b -y   # approve by build ID, skip confirmation
```

**Recover a release whose prod approval timed out:**

```bash
ado-api builds retry-stage --pr <pr-id> --dry-run   # see what would be requeued
ado-api builds retry-stage --pr <pr-id> --watch      # requeue and wait for completion
```

## Exit Codes

A real Azure DevOps API failure (404, permission denial, rate limit) that reaches the CLI uncaught
gets exit code 5 and a `Error: <message>` line, rather than the generic "This may be a bug"
catch-all.

See `ado-api --help` and each subcommand's `--help` for the full, current parameter list — this
document is a guide, not a substitute for it.
