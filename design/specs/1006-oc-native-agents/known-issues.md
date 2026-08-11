# Known Issues

Durable issues discovered during orchestration that were intentionally not fixed in this run.

## KI-001: `collision_keys` silently dropped when lint fails between the two sync-state writes

Status: filed (#499)
Run: 70
Source: T04
Reason not fixed now: needs-decision
Observed in: T04 (bin/opencode-sync), iteration-3 code review and integration review
Affected files:
- bin/opencode-sync

Issue:
`main()` writes `sync_state` to disk twice per run (bin/opencode-sync:1341-1390): once right after `generate_config()` succeeds (to persist `config_hash` immediately, independent of lint outcome), and once at the end after `run_lint()` passes (to persist `sync_sha`/`sync_script_hash`). `check_collisions()` sits between the two writes and mutates `sync_state["collision_keys"]` in place (bin/opencode-sync:1213). If `run_lint()` fails, `main()` returns early at line 1379 and the second write never runs, so the freshly computed `collision_keys` from `check_collisions()` is never persisted — it's silently dropped. The next invocation's nagging-suppression comparison (`collisions != previous`, bin/opencode-sync:1202) then compares against a `collision_keys` value that is one run older than it should be, for exactly one sync cycle. Depending on the transition this either re-fires a warning for an already-resolved collision or suppresses a warning for a newly-introduced one. No data loss to the actual synced config, no crash, no security issue — self-heals the moment a run reaches a successful lint pass. Both the code reviewer (LOW) and the integration reviewer (MEDIUM, `[COUPLED]`) independently flagged this as the same underlying defect.

Why deferred:
This is the classify-only terminal pass for T04 (fixer-pass budget exhausted, iteration 3). The fix is a small design choice between two valid options rather than an obvious correction, so it shouldn't be rushed into a pass with no further review budget:
(a) move `check_collisions()` before the first write, so both `config_hash` and `collision_keys` land in the same write — simpler, since nothing in `check_collisions()` depends on `generate_config()` having already run.
(b) re-persist `collision_keys` specifically before the early return on lint failure — keeps `check_collisions()` running after `generate_config()`, as originally sequenced.
Neither option is fixable safely without a deliberate choice and a follow-up review pass.

Recommended follow-up:
Pick option (a) or (b) above and implement it as a follow-up change to `bin/opencode-sync`, then re-run `code-reviewer`/`integration-reviewer` on the diff to confirm the coupling is closed.

Acceptance criteria:
- `collision_keys` is persisted to `.claudefiles-sync-state.json` even when a sync run ends via the lint-failure early return.
- A lint-fail-then-fix-then-rerun cycle does not re-fire an already-resolved collision warning, and does not suppress a newly-introduced one.

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
