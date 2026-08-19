---
task_id: "T04"
title: "Write the package README and CHANGELOG, and prove the package installs standalone"
status: "planned"
depends_on: ["T02", "T03"]
implements: ["FR#6"]
---

## Target Files

- modify: `packages/ado-api/README.md`
- create: `packages/ado-api/CHANGELOG.md`

## Prompt

The `ado-api` package now has its final command surface. Document it and prove it installs as a
standalone tool.

Read `tasks/context.md` and `design.md` in this spec directory first.

### README

Task T01 left a stub `packages/ado-api/README.md` (enough to satisfy `readme =` in `pyproject.toml`).
Expand it into a real command reference.

There is a useful structural seed at
`~/source/rhyme/RhymeAnalyticsDocumentation/References/CLI-Tools/ado-api.md` (90 lines,
read-only — do not modify it). **It is stale**: it documents `builds approve -p`, a flag the cyclopts
migration removed, and it predates several commands. Use it for section layout and tone only.

Write the actual content from the CLI's real behavior — run `ado-api --help` and each
`ado-api <group> --help`, and document what they print. Do not transcribe the seed doc's command
lines.

Cover: auth and org/project resolution (PAT from `SYSTEM_ACCESSTOKEN` → `ADO_PAT` →
`~/.azure/azuredevops/personalAccessTokens`; org/project from `az devops configure --list`), the
global `--json` and `--project` flags, each command group, and installation via `uv tool install -e`.

Two things a reader needs that `--help` will not tell them:

1. **`builds missed-prod`, `builds retry-stage`, and `builds approve`'s PR-tag lookup depend on one
   organization's build-tag conventions** (`pr=`/`PR-`, `stage=`, `prod=` — see `src/ado_api/tags.py`).
   At an organization tagging builds differently they will return nothing. Say so where a reader hits
   it, not in a footnote.
2. **Shell completion**: `ado-api --install-completion` exists; note the zsh `$fpath` requirement the
   command itself prints.

### CHANGELOG

Create `packages/ado-api/CHANGELOG.md`. Seed it from
`~/source/rhyme/analytics/packages/ado-api/CHANGELOG.md` (read-only), which is the honest
history of the code now in this repo. Two adjustments:

- Its entries carry work-tracker references (`(!49947)`, `(!48512)`, …) that resolve to nothing here.
  Strip them.
- Add a new top entry, dated today, for this port: the framework migration, the vendored tag
  constants, the dropped `<3.13` Python cap, and the re-applied `--body-file`/`--description-file`
  flags.

This is the package's own changelog, not the repo root's. Do **not** add an entry to the root
`CHANGELOG.md` — per `rules/common/git-workflow.md` that happens at PR creation.

### Prove it installs

`uv tool install -e packages/ado-api`, then run the installed binary from outside the package
directory. This is the check that would have caught the missing-README build failure, so run it as a
real install, not `uv run`.

## Verify

- [ ] FR#6 / AC#7: `uv tool install -e packages/ado-api` completes with exit code 0. Paste the output.
- [ ] FR#6 / AC#7: `cd /tmp && ado-api --help` runs successfully against the installed binary.
- [ ] FR#6 / AC#7: the test suite passes under Python 3.12 and under Python 3.14 (`uv venv --python 3.14` in a scratch directory, install the package, run pytest from inside this repo). A scratchpad rehearsal already showed 504/504 on both, so a failure here means the port diverged from that rehearsal.
- [ ] `README.md` documents every command group that `ado-api --help` lists, with no command that `--help` does not list.
- [ ] `README.md` states that `missed-prod`, `retry-stage`, and PR-tag `approve` depend on org-specific build-tag conventions.
- [ ] `packages/ado-api/CHANGELOG.md` exists, contains no `(!NNNNN)` references, and its top entry describes this port.
- [ ] The repo-root `CHANGELOG.md` is unmodified: `git diff --stat CHANGELOG.md` is empty.
