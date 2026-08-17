# Known Issues

Durable issues discovered during orchestration that were intentionally not fixed in this run.

## KI-001: standard-worker's WebSearch/WebFetch grant undocumented in Dependencies and Assumptions

Status: resolved — fixed during known issues walkthrough
Run: 93
Source: T04
Reason not fixed now: out-of-scope
Observed in: T04 (pass-2 re-review)
Affected files:
- design/specs/1008-opencode-named-roles/design.md
- agents/standard-worker.md

Issue:
`agents/standard-worker.md:6` was widened during T04's fixer passes to add `WebSearch`
and `WebFetch` to its `tools:` allowlist, because three migrated sites now dispatch it
expecting those tools (`skills/mine-prior-art/SKILL.md:70` — the file's PRIMARY phase,
`skills/mine-brainstorm/SKILL.md:70`, `skills/mine-challenge/SKILL.md:31`). This capability
grant is confirmed correct and working (code-review.md pass 2 verifies the frontmatter and
the empirical justification), but it is not recorded anywhere in `design.md`'s Dependencies
and Assumptions section — unlike every other per-agent tool deviation the doc tracks (the
"Fleet-wide tool widening" bullet covering `planner`/`secrets-auditor`, and the
`mine-prior-art:61` tier-collision bullet for FR#24). A reader relying on Dependencies and
Assumptions as the durable record of accepted deviations would not learn this one happened.

Why deferred:
This is a documentation-completeness gap, not a functional defect — the underlying code
change is correct, tested, and already verified by the pass-2 code review. FR#24 and this
task's own Target Files note for `design.md` scope its "record in Dependencies and
Assumptions" duty specifically to *model-tier* changes from specialist promotion; this is a
*tool* addition to a worker whose tier never changed, so it falls outside FR#24's literal
requirement even though the same "don't discover it after the fact" reasoning applies. This
terminal pass is classify-only (no code changes permitted), so a one-line design.md addition
cannot be made here regardless of how small it is.

Recommended follow-up:
Add a bullet to `design.md`'s Dependencies and Assumptions section, alongside the existing
"Fleet-wide tool widening" bullet, recording that `agents/standard-worker.md` gained
`WebSearch`/`WebFetch` during migration because `mine-prior-art:70`, `mine-brainstorm:70`,
and `mine-challenge:31` require them, following the same format used for the
`secrets-auditor`/`planner` entries.

Acceptance criteria:
- `design.md`'s Dependencies and Assumptions section names `agents/standard-worker.md`'s
  `WebSearch`/`WebFetch` grant and the three consuming sites.

## KI-002: main() and check_source_dispatch_patterns()/check_source() remain long after this migration's rewrite

Status: filed (#517)
Run: 93
Source: clean-code
Reason not fixed now: out-of-scope
Observed in: clean-code review of run 93 (nitpicker checker)
Affected files:
- bin/opencode-sync

Issue:
`main()` (`bin/opencode-sync:1506-1661`, ~156 lines) interleaves CLI-flag branching,
dry-run staging with a disposable scratch home, real-install staging, frontmatter
processing, config generation, lint gating, and sync-state persistence in one function
body, with no docstring to offset the line count (unlike most other functions in this
file). `check_source_dispatch_patterns()` (`bin/opencode-sync:1252-1369`, ~117 lines,
well-commented) does three distinct things: directory-presence validation, per-file
dispatch/model-clause scanning, and a separate scratch-copy rules-coverage check tacked
on at the end. Both functions were substantially rewritten by this migration itself
(FR#21/FR#22, `check_source()` at :1370 replaced the scratch-tree rewrite-then-lint
approach with a direct source assertion) but the rewrite did not also split them into
smaller units.

Why deferred:
Both functions have real side effects (disposable scratch homes, config generation,
lint gating that pre-commit hooks depend on) and multi-branch control flow. Splitting
them into extracted helpers without changing behavior is a genuine refactor, not a
mechanical style fix — it needs a characterization test pinning current behavior first
(per this repo's refactoring-discipline rule) and is a bigger unit of work than a
clean-code pass should absorb inside an already-large migration. The design doc's
Replacement Targets mandated *what* gets deleted and *that* these two functions get
reimplemented, not a further internal decomposition of the result, so extracting
helpers now would expand past the design's approved scope.

Recommended follow-up:
Pin current behavior (`--check-source`/`--dry-run`/`--check` CLI contracts already
covered by `tests/test_opencode_sync.py`), then extract `main()`'s dry-run and
real-sync branches into two named helpers (e.g. `_do_dry_run_preview()` /
`_do_real_sync()`), and split `check_source_dispatch_patterns()`'s rules-coverage tail
into its own helper. Re-run the full opencode-sync test suite after each extraction.

Acceptance criteria:
- `main()` in `bin/opencode-sync` is under ~80 lines with its dry-run and real-sync
  paths extracted to named helpers.
- `check_source_dispatch_patterns()` no longer performs rules-coverage checking inline.
- `tests/test_opencode_sync.py` passes unchanged (behavior-preserving refactor).
