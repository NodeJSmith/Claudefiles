---
task_id: "T05"
title: "Update Claudefiles skills and docs for the changed ado-api command surface"
status: "done"
depends_on: ["T01"]
implements: ["FR#7"]
---

## Target Files

- modify: `skills/mine-address-pr-issues/SKILL.md`
- modify: `rules/common/capabilities-core.md`
- modify: `REFERENCE.md`

## Prompt

The `ado-api` port removed and renamed commands. Three files in this repo still describe the old
surface. Fix them.

Read `tasks/context.md` and `design.md` in this spec directory first. Verify each claim below against
the actual CLI (`ado-api <group> --help`) rather than trusting this prompt — the port is done by the
time this task runs, so the real help output is available and authoritative.

### `skills/mine-address-pr-issues/SKILL.md`

Line 147 (as of writing) reads:

```
**ADO:** `ado-api logs errors <build-id>` — fetches and filters failure logs. Run `ado-api logs --help` for full usage.
```

`logs errors` no longer exists. `logs list`, `logs get`, and `logs search` are gone too — all four
collapsed into a single `logs read <build-id>` with orthogonal selector flags (`--step` / `--failed` /
`--log-id`) and content flags (`--issues` / `--tail` / `--head` / `--grep` / `--context`).

The replacement for this use — "show me why the build failed" — is
`ado-api logs read <build-id> --failed --issues`. Confirm the flag names against `ado-api logs read --help`
before writing them.

Also check line 323's summary list of ADO commands and anything else in the file that names an
`ado-api` subcommand; update whatever no longer matches. Do not rewrite prose that is still correct.

### `rules/common/capabilities-core.md`

The ADO rows are in the "CLI Tools" table (around lines 96-101). The existing rows for `ado-api builds`,
`ado-api logs`, `ado-api pr`, `ado-api pr threads`, `ado-api builds approve`, and `ado-api work-item`
all still point at commands that exist — leave their tool column alone.

Add trigger rows for the commands the port introduced, matching the file's existing style (natural
phrasings a user would actually type, in the "User says something like..." column):

- `builds retry-stage` — re-running a stage on a completed build
- `builds missed-prod` — finding releases that reached stage but not prod
- `builds steps` — per-run timeline/step records for a build
- `pipeline create` / `pipeline build-validate`

Two constraints on the phrasings: they must not collide with the existing `ado-api builds` row's
triggers ("cancel builds", "list ADO builds"), and `missed-prod` / `retry-stage` are specific enough
that generic phrasings would misroute. Read the surrounding table before writing to match its voice.

### `REFERENCE.md`

Line 308 (as of writing) describes the package as:

```
| `ado-api` | Azure DevOps CLI — builds, logs, PR management, work items, approvals |
```

Extend it to cover pipelines and stage retries. Keep it to one line in the existing table format.

Check line 304's prose about `ado-api` not being wired into a bundle — that is still accurate and
should not change.

### Do not touch

`install.py` and `tests/test_install.py` were both checked and need no change: the first-install tip
at `install.py:1690` already says "pull requests, builds, pipelines, and work items", and
`test_install.py` uses `"ado-api"` only as a package-name fixture. Leave both alone.

Do not add an entry to the root `CHANGELOG.md` — that happens at PR creation.

## Verify

- [ ] FR#7 / AC#8: `grep -rn "logs errors\|logs get\|logs search\|logs list" skills/ rules/ REFERENCE.md` returns nothing.
- [ ] FR#7: every `ado-api` subcommand named in `skills/mine-address-pr-issues/SKILL.md`, `rules/common/capabilities-core.md`, and `REFERENCE.md` exists in the installed CLI. Confirm by running each named command's `--help`.
- [ ] `rules/common/capabilities-core.md` has trigger rows for `retry-stage`, `missed-prod`, `builds steps`, and `pipeline`.
- [ ] `REFERENCE.md`'s `ado-api` row mentions pipelines.
- [ ] `git diff --stat install.py tests/test_install.py CHANGELOG.md` is empty.
