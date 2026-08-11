# Known Issues

Durable issues discovered during orchestration that were intentionally not fixed in this run.

## KI-001: `collision_keys` silently dropped when lint fails between the two sync-state writes

Status: open
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
