# Context: Port the analytics ado-api (cyclopts) into Claudefiles

## Problem & Motivation

`Claudefiles/packages/ado-api` is a v0.1.0 pydantic-settings fork that has fallen ~2 years behind its
sibling at `~/source/rhyme/analytics/packages/ado-api` (v0.2.0, cyclopts). The Claudefiles
copy lacks five commands, a parse-bug fix, retries, and the cyclopts framework the user's own
`python-packaging.md` rule mandates. The user now works at two Azure DevOps shops, so the personal
copy needs to become the good one.

## Key Decisions

1. **Wholesale replacement, not a merge.** The cyclopts migration deleted `cli.py`, `cli_context.py`,
   and all of `cli_models/`, and touched every command module. Copy the analytics `src/` and `tests/`
   trees over the Claudefiles ones, then apply changes on top of that result. Do not cherry-pick.
2. **Vendor, don't depend.** `rhyme-constants` has 4 import sites plus a 5th textual reference in a
   docstring (`commands/approve.py:145`). The tag helpers become `src/ado_api/tags.py` inside this
   package. The org/project constants are *not* vendored — the one place they are used (a `setup.py`
   print hint) becomes a generic placeholder.
3. **No config plumbing for tag conventions.** The vendored constants are module defaults. Commands
   that depend on Rhyme's build-tag format (`missed-prod`, `retry-stage`, `approve`-by-PR-tag) are
   simply inert at an org that tags differently. This is deliberate.
4. **The two Claudefiles-only features must survive.** `--body-file` / `--description-file` (with `-`
   for stdin) exist nowhere in the analytics copy and must be re-applied on the cyclopts surface.
5. **Drop the `<3.13` Python cap; keep the `>=3.12` floor.** The cap is a work-monorepo pin. The
   floor stays because `uv tool install` fetches a managed interpreter when the local one is too
   old, so lowering it would buy nothing — and it would force a pointless rewrite of the PEP 695
   generic in `cli/limits.py`.
6. **`readme = "README.md"` in the analytics pyproject points at a file that does not exist.** Writing
   the README is load-bearing — without it `uv tool install -e` fails.

## Constraints

- **Do not modify** `~/source/rhyme/analytics/**` — read-only source.
- **Do not modify** `~/source/rhyme/rhyme-claude-code/**` — the user is handling that
  copy separately.
- **Do not touch branch defaulting.** The ported code hardcodes `"master"` in three places
  (`cli/commands/pipeline.py:41`, `:57`, `commands/builds.py:35`) and `builds approve` has no
  `--branch` flag. These are known and deliberately deferred to a follow-up built on the Orion
  machine — see "Deferred: multi-org branch roles" in `design.md`. Port them verbatim. Two
  deliberate exceptions, neither of which changes a default: the *test-level* fix in T01 Step 5,
  which mocks `_get_default_branch`; and T03, which adds a `--branch` override to `builds approve`
  where none exists.
- **Do not build any anti-drift mechanism** (sync script, shared upstream, drift check). The fork is
  accepted and expected to diverge again.
- **Do not add config files, env vars, or profile mechanisms** for org/project/tags. Auth and
  org/project resolution are already portable and must not be reworked.
- **Do not touch `install.py` or `tests/test_install.py`.** Both were checked and need no change.
- **Do not add a root `CHANGELOG.md` entry.** Per `rules/common/git-workflow.md`, changelog entries
  land at PR creation, not during feature work. (The package's own `packages/ado-api/CHANGELOG.md` is
  a different file and *is* in scope.)
- Follow `rules/common/python.md`: no `from __future__ import annotations`, no `Optional[X]`, no lazy
  imports.
- Preserve `Parameter(allow_leading_hyphen=True)` wherever analytics has it — it is a deliberate fix
  letting free-text values begin with `-`.
