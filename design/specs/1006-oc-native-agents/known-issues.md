# Known Issues

Durable issues discovered during orchestration that were intentionally not fixed in this run.

## KI-001: `collision_keys` silently dropped when lint fails between the two sync-state writes

Status: obsoleted by removal (#499 closed)

The `collision_keys` nagging-suppression mechanism this issue describes (persisting the collision set across syncs so an unresolved collision doesn't re-warn every run) was removed entirely during a later `/mine-challenge` pass — `check_collisions()` now warns on every sync while a collision exists, with no persisted state (see design.md FR#13's revision note). There is no longer a `collision_keys` field in the sync state, no two-write gap to drop it in, and no nagging-suppression comparison for stale state to desync. The bug this issue reported cannot recur because the code path it described no longer exists.

## KI-002: `main()` mixes seven orchestration concerns in one 109-line function

Status: filed (#500)
Run: 70
Source: clean-code
Reason not fixed now: needs-decision
Observed in: clean-code review of bin/opencode-sync (commit c397dcf)
Affected files:
- bin/opencode-sync

Issue:
`main()` (bin/opencode-sync:1295-1403) inlines argument dispatch, worktree safety checks, tempdir staging, opkg orchestration, dispatch rewriting, config generation, sync-state persistence, and lint reporting in one function body — well over the file's own 50-line function guideline. The nitpicker checker flagged this as the single largest structural offender in the file and, independently, the lazy-checker's file-size finding (KI-003) traces to the same root cause.

Why deferred:
`main()`'s current ordering encodes several load-bearing, non-obvious sequencing decisions with inline comments explaining why (e.g. `sync_state["config_hash"]` must be persisted immediately after `generate_config()` regardless of lint outcome, not bundled with the later `sync_sha`/`sync_script_hash` write; the lint runs against just-installed output and gates the final state write). Extracting a `run_sync(args)` orchestrator with named sub-steps is the right shape, but doing it safely requires deliberately preserving every one of these ordering invariants — a mechanical extraction risks silently reordering a write and reintroducing exactly the kind of bug KI-001 already found once. This is architectural-judgment work, not an unambiguous style fix, and this review's fixer pass has no further review budget to validate a refactor of this sensitivity.

Recommended follow-up:
Extract `run_sync(args) -> int` (or similarly named) from `main()`'s body, preserving the exact write ordering documented in the current inline comments. Re-run `code-reviewer`/`integration-reviewer` on the diff, and re-verify the full Test Strategy checklist in design.md (dry-run output, `--check`, `--lint-only`, SQLite child-session query) since a reordering bug here would be silent (no test framework exists for this script per the design doc's accepted gap).

Acceptance criteria:
- `main()` is under ~50 lines and delegates to named helper(s) for staging/opkg, rewrite/remap, config generation, and lint reporting.
- All existing ordering invariants (config_hash persisted before lint gate; sync_sha/sync_script_hash persisted only after a clean lint) hold, verified by the design doc's Test Strategy checklist.

## KI-003: `bin/opencode-sync` (1397 lines) exceeds the 800-line file-size guideline via incremental task accretion

Status: filed (#501)
Run: 70
Source: clean-code
Reason not fixed now: needs-decision
Observed in: clean-code review of bin/opencode-sync (commit c397dcf)
Affected files:
- bin/opencode-sync

Issue:
The lazy-checker flagged that the file has grown to 1397 lines — well past the repo's 800-line hard cap — by literally bolting one task's worth of functionality onto the last (per the module's own docstring: "T01 laid the skeleton; T02 added ...; T03 added ...; T04 added ..."). Staging/opkg orchestration, worker-agent generation, dispatch rewriting (5 regexes + two rewrite passes), compatibility linting, JSONC collision detection, and sync-state management are five fairly separable concerns now living in one file with no split.

Why deferred:
Splitting into multiple modules (e.g. `staging.py`/`dispatch_rewrite.py`/`lint.py`/`state.py`) is in direct tension with the design's Implementation Preferences and the script's own packaging convention: `bin/opencode-sync` is a self-contained `uv run --script` file (shebang `#!/usr/bin/env -S uv run --script` with inline PEP 723 dependency metadata), and the design doc's Replacement Targets section explicitly scopes this as "`bin/opencode-sync` (bash) → `bin/opencode-sync` (Python) — full rewrite, same filename," not a package. Whether to break that single-file convention to enable a multi-module split is a packaging/architecture decision outside this review's scope, not a mechanical cleanup.

Recommended follow-up:
As a follow-up design decision, evaluate whether `bin/opencode-sync` should become a thin entry point importing from a `packages/opencode-sync/` (or similar) package, or whether the single-file convention should be kept and KI-002's `run_sync()` extraction is sufficient. If a split is chosen, verify the `uv run --script` invocation and opkg distribution pipeline still work unchanged (`opencode-sync --dry-run`, `--check`, `--lint-only`).

Acceptance criteria:
- Either the file is intentionally kept single-file (decision recorded, no action needed), or `bin/opencode-sync` is reduced to an entry point under ~200 lines with logic split into a package, and all existing CLI invocations behave identically.
