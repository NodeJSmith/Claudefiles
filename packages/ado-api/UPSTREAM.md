# Upstream and Claudefiles Changes

`ado-api` is developed in Rhyme's analytics monorepo (`packages/ado-api`, private Azure
DevOps repo) and vendored here so it works without Rhyme's other packages. This file is
the porting guide: what Claudefiles changes, and how to pull a newer upstream.

The next line is rewritten by `revendor.py` on every run; leave its `**Upstream base:**`
prefix intact.

**Upstream base:** `25d82eb6b` (2026-11-23, Merged PR 51530: fix(ado-api): did_not_run retries, Bearer az tokens, no POST retries; local-time tables)

## The rule

`src/` and `tests/` are generated. Don't edit them here: `revendor.py` replaces both
directories on every run. It refuses while they have uncommitted changes (unless
`--force`), but a committed local edit is still overwritten. A fix that isn't
Rhyme-specific goes into analytics first and arrives with the next revendor. A change
only Claudefiles needs becomes a substitution in `revendor.py` and an entry under
[Substitutions](#substitutions), with the same name.

## Revendoring

Fetch in the analytics clone (`git -C ~/source/rhyme/analytics fetch origin master`),
then from the Claudefiles root:

```bash
packages/ado-api/revendor.py ~/source/rhyme/analytics      # or --ref <commit>
```

If a substitution no longer matches, the script stops before touching `src/` or
`tests/`: upstream moved the code it patches. Fix the substitution and its entry below,
then rerun.

After a run, in this order:

1. **Dependencies.** If the script printed a dependency difference, update
   `pyproject.toml`'s runtime dependencies to match.
2. **Lock and test.** `cd packages/ado-api && uv lock && mise run test:ado-api`.
3. **Command surface.** `git diff -- packages/ado-api/tests/golden/` shows every help-text
   change. Update `README.md` for new, removed, or renamed commands, and check the skills
   that call `ado-api` (`grep -rn 'ado-api' skills rules`) against renamed flags, JSON
   fields, and quoted error text.
4. **Conventions.** Compare the README's Conventions section with the "Conventions every
   command follows" list in analytics' `.claude/reference/cli-tools/ado-api.md`, and copy
   over what changed.
5. **New Rhyme specifics.** Grep `src/` for new imports from other analytics packages. The
   script already fails on `rhyme_constants`; any other monorepo import needs a
   substitution.
6. **Changelog.** Add a `CHANGELOG.md` entry naming the new base and what changed for
   users.

## Substitutions

Each heading is the `name` of one or more substitutions in `revendor.py`.

### Vendored build-tag helpers

Upstream imports its build-tag regexes and `pr_tag_variants` from `rhyme-constants`, a
monorepo path dependency. The script copies `rhyme_constants/ado_tags.py` to
`src/ado_api/tags.py` with a docstring saying the formats are Rhyme's, and its test to
`tests/test_tags.py`. The substitutions rewrite every `rhyme_constants.ado_tags`
reference to `ado_api.tags`, and the two docstrings that name analytics'
`tag_pipeline_run.py` to say "a Rhyme pipeline run".

### Generic setup hint

Upstream prints Rhyme's org URL and project in `setup`'s `az devops configure` hint, from
`rhyme_constants.ado`. The substitutions drop that import and print `ORG`/`PROJECT`
placeholders.

### Review questions point at the README

Upstream's `src/ado_api/REVIEW.md` points to the conventions section of
`.claude/reference/cli-tools/ado-api.md`, which lives only in analytics. Here it points
to the README's Conventions section, kept in sync by checklist step 4.

### Pending upstream: mock the default branch in one test

`test_missed_prod_defaults` in `tests/test_entrypoint_pin.py` leaves
`get_default_branch` unmocked, so it passes only in a repo whose default branch is
`master`, and fails here (`main`). The substitution patches it to `master` around the
call. Once analytics fixes the test, this substitution stops matching: delete it and
this entry.

## Files Claudefiles owns

The script copies only `src/` and `tests/`. Everything else in the package is maintained
here:

- `pyproject.toml`: no `rhyme-constants`, no author email, no `<3.13` Python cap, the
  setuptools `src` layout, a `dev` dependency group for `mise run test:ado-api`, and its
  own ruff root with upstream's 120-column line length. The line length keeps ruff
  format from rewrapping vendored code, so a diff against upstream shows only real
  changes.
- `uv.lock`, regenerated here.
- `README.md`, `CHANGELOG.md`, `revendor.py`, and this file.

Upstream's `azure-pipelines.yml` and `requirements.txt` are its CI and aren't vendored.

## Rhyme-specific behavior kept as-is

These are vendored unchanged, on purpose. Removing them would mean editing upstream code
on every revendor, and they're only used at Rhyme:

- **Build tags.** `builds approve` (by PR ID), `missed-prod`, `retry-stage --pr/--tag` and
  `cancel-superseded` find builds through Rhyme's `pr=`, `stage=` and `prod=` tags. At an
  org that tags builds differently they find nothing.
- **Prod gate** (`commands/gate.py`). The `builds approve` list reads each build's gate
  assuming Rhyme's prod checkpoint: two Approval checks and a two-person Azure Function
  check. At another org the approval counts can be wrong, and an unreadable gate exits 5.
- **`builds stage-check`** reads Databricks job runs through the `databricks` CLI's `dev`
  profile. Without that CLI it fails with "databricks CLI not found".
- **Test fixtures** use Rhyme's org, project, and repo names as sample data.
