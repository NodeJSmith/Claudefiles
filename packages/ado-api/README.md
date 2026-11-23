# ado-api

Azure DevOps CLI: builds, logs, PRs, work items, and pipelines.

The code is vendored from Rhyme's analytics monorepo. Don't edit `src/` or `tests/` here:
`revendor.py` regenerates both. [UPSTREAM.md](UPSTREAM.md) covers how to revendor and
lists every change Claudefiles makes to the upstream code.

## Install

```bash
uv tool install -e packages/ado-api
```

## Auth and Configuration

The PAT is resolved in order, first hit wins:

1. `SYSTEM_ACCESSTOKEN`, set automatically inside Azure Pipelines CI.
2. `ADO_PAT`, an explicit override for local use.
3. `~/.azure/azuredevops/personalAccessTokens`, the `az` CLI's cache written by `az login` or
   `az devops login`.

Organization and project come from `az devops configure --list`. `ado-api setup` checks `az`, the
`azure-devops` extension, the defaults, and the login, installs what it can, and prints the
`az devops configure --defaults ...` command when the defaults are missing.

PATs only carry the scopes they were created with. `pipeline create` lists agent queues (Agent
Pools (Read)) and the `builds approve` list reads approver groups (Identity (Read)). Without the
scope, both fall back to an `az login` token and say so on stderr.

## Repo and Project

`--repo` and `--project` work before or after the subcommand. The project is, in order: `--project`;
the project the `--repo` repository lives in; the cwd checkout's `origin`; the az default. So a
command run inside any checkout reaches that repo's project without flags, and `--repo NAME` works
from anywhere. Commands that change something print `Project: <org>/<project> (from <source>)` on
stderr.

## Commands

| Group | Commands |
|---|---|
| `builds` | `list`, `steps`, `wait`, `watch`, `cancel`, `cancel-by-tag`, `cancel-superseded`, `approve`, `retry-stage`, `missed-prod`, `stage-check` |
| `logs` | `read` |
| `pr` | `list`, `show`, `create`, `update`, `threads`, `thread-add`, `reply`, `resolve`, `resolve-pattern`, `work-item-list`, `work-item-add`, `work-item-remove`, `work-item-create` |
| `work-item` | `create` |
| `pipeline` | `create`, `build-validate` |
| `setup` | |

`ado-api <group> <command> --help` is the reference for flags. Some things worth knowing up front:

- **`logs read`** needs a selector (`--step`, `--failed`, `--log-id`). With no content flag it
  prints the whole log; `--failed` alone prints the last 200 lines of each failing step.
  `--issues`, `--tail`/`--head` and `--grep` narrow it.
- **`builds wait`** follows whole builds to completion and names the failing steps, so there's
  no need for a sleep loop. `builds watch` follows one stage.
- **Text flags** (`--description`, `--body`) each have a `--description-file`/`--body-file`
  counterpart that reads a file, or stdin with `-`. Use it for multi-line markdown, which a shell
  argument would mangle.
- **Rhyme-specific commands.** The release commands (`approve`, `retry-stage`, `missed-prod`,
  `cancel-superseded`) rely on Rhyme's build tags, the `approve` list reads Rhyme's prod gate, and
  `stage-check` reads Databricks. Elsewhere they find nothing or fail. See
  [UPSTREAM.md](UPSTREAM.md#rhyme-specific-behavior-kept-as-is).

## Conventions

Every command follows these, and `src/ado_api/REVIEW.md` checks changes against them:

- **stdout is the result:** a table, `--json`, or one line per item. Progress, warnings, hints,
  "nothing found" and prompts go to stderr. An error that stops the command starts with `Error:`;
  a failed batch item reads `Failed <thing> <id>: <error>` and the rest of the batch still runs.
- **Tables** align in a terminal and are tab-separated when piped. Times are local, with the zone;
  `--json` keeps UTC. Scripts should use `--json`, not column positions.
- **`--json`** works on every command except `setup`. Keys are camelCase.
- **Commands that change several things** show the plan, prompt, and take `--yes`/`-y` and
  `--dry-run`. Declining exits 1 and changes nothing.
- **Exit codes:** 0 success; 1 usage error, or the answer is no (declined prompt, refused
  approval, failed build, timeout); 2 config; 3 auth; 4 internal error; 5 an ADO call failed,
  including one item of a batch; 130 Ctrl-C.

## Common Workflows

```bash
# Why did the build fail?
ado-api builds list --pr <pr-id> --status completed
ado-api logs read <build-id> --failed --issues

# Wait for a PR's build instead of polling
ado-api builds wait <build-id>

# Post a multi-line PR comment
ado-api pr thread-add <pr-id> --body-file comment.md
```

## Shell Completion

```bash
ado-api --install-completion          # auto-detects your shell
ado-api --generate-completion --shell zsh > /path/to/_ado-api
```

For zsh the script goes to `~/.zsh/completions/_ado-api`, which must be on `$fpath` before
`compinit` runs. The command prints the lines to add if they're missing.
