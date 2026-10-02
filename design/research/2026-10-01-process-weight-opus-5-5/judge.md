# Judge report: #1798, arm A vs arm B

A = `.claude/worktrees/1798-decision-ledger`, B = `.claude/worktrees/1798-decision-ledger-opus`. Line numbers refer to each arm's HEAD.

**Bottom line:** merge **B**, by a clear margin. The production code in the two arms behaves almost the same. Both implement the ledger correctly. B wins on tests (RED/GREEN commits, more spec rows pinned, real `partial_cleanup` path) and on docs (the #13 code example, `fire_event` coverage, the `original_data` docstring). B has one defect that must be fixed before merge: its caplog tests depend on test order, and I reproduced the failure.

## What I ran

- New and changed unit test files in each arm, with `-n 0`: A 49 passed, B 31 passed.
- Sync-facade generator with `--check` (`codegen/src/hassette_codegen/sync_facade/ --target all --check`): exit 0 in both arms. `sync.py` matches the generator output in both.
- Both arms' testing snippets ran as pytest (pass). The snippets, plus B's managing-helpers snippet, also pass `pyright --project docs` (0 errors).
- Order probe: `pytest -n 0 -p no:randomly tests/unit/test_logging_capture_handler.py tests/unit/core/test_websocket_outcome_unknown.py` in B gives **4 failed**. Details in §3.

## 1. Spec conformance

| Item | A | B |
|---|---|---|
| 1 Default stays True; writes opt out | Met | Met |
| 2 No `call_service` path re-sends; no new kwarg | Met | Met |
| 3 Marker parent with no body, two concrete subclasses, no `TimeoutError` | Met | Met |
| 4 Names | Met | Met |
| 5 Raised on every timeout, including a retried read's last attempt | Met | Met |
| 6 Redacted message, `original_data` holds the payload, `ResponseLostError` has `close_code` and no payload | Met | Met |
| 7 Predicate unchanged | Met | Met |
| 8 Disconnect while waiting becomes `ResponseLostError`, never retried | Met | Met |
| 9 REST out of scope, follow-up issue filed | Partial: no follow-up issue found (`gh issue list` shows none) | Partial: same |
| 10 Keep `retry_on_timeout` on `ws_send_and_wait` | Met | Met |
| 11 `fix:`, non-breaking | Met (single `fix:` commit) | Met. Its `fix:` commit is `04bcedcd`, but there is also a `feat:` commit (`9548357b`). That only matters if the PR is rebase-merged instead of squashed. |
| 12a WARNING at the single exit point | Met (`websocket_service.py:749-753`) | Met (`websocket_service.py:748-756`) |
| 12b Late-reply record: 100-entry `OrderedDict` cap, oldest evicted first, cleared in both cleanups, INFO/WARNING with type and id | Met (`:751-762, :775-776, :795-820`) | Met (`:752-756, :768-773, :791-809`) |
| 13 Recovery guidance | **Partial.** `managing-helpers.md:73-82` gives the `helpers.list` check as prose only; the spec asks for code. `methods.md:550-557` (the Low-level warning) has nothing about `fire_event`/`call_service` being unable to confirm their effect. A's only check-state advice is in the `call_service` warning at `:230-236`, which never mentions `fire_event`. | Met (snippet `managing-helpers/outcome_unknown.py`; `methods.md:565-573`) |
| 14 Harness example via `--8<--` snippet | Met | Met |
| A1 `fire_event` sends once | Met | Met |
| A2 Helper CRUD sends once, `list` retries; `_ws_helper_call` mechanism | Met | Met |
| A3 `subscribe_events` untouched | Met | Met |
| A4 `_ws_helper_call` passes `OutcomeUnknownError` through; tests for helper timeout and disconnect | Met (tested at `_ws_helper_call` level only) | Met (tested at `_ws_helper_call` level and through `helpers.create`/`delete`) |
| A5 Exceptions live in `exceptions.py`; `original_data` is the outgoing payload, stated in **both** docstrings | **Partial.** The `FailedMessageError` docstring is unchanged (`exceptions.py:161-185`); only the `ResponseTimeoutError` docstring says it. | Met (`exceptions.py:181-183`) |
| A6 `wait_for_ack` keeps its name and default; docstring updated | Met | Met |
| A7 No signature changes; `sync.py` regenerated | Met (generator `--check` exit 0) | Met (generator `--check` exit 0) |
| A8 Retry count and backoff unchanged | Met | Met |
| A9 RED then GREEN; WS-level tests; Api-level tests include the reads | **Violated / Partial.** One squashed commit `d9548c14`, so there is no RED evidence. Reads `get_states`/`get_config`/`get_services`/`get_panels` are never asserted; only helper `list` is. | Met. `a6ee9e2e` is the "(red)" commit. Reads are parametrized in `tests/unit/test_api_ws_retry_policy.py:28-38`. |
| A10 Docstrings (`wait_for_ack`; `_ws_helper_call` note) | Met, with a nit: `api.py:261-264` says to also catch `RetryableConnectionClosedError` "for a disconnect that occurs outside it". After this change, no plain `RetryableConnectionClosedError` leaves `ws_send_and_wait` (pre-send failures raise plain `ConnectionClosedError`, `websocket_service.py:814-815`). That contradicts "single catch". | Met |
| A11 Docs: `methods.md`, Low-level warning, `managing-helpers` warning, `troubleshooting`; "don't blindly re-send, check state" | **Partial.** The Low-level warning (`methods.md:550-557`) never says don't blindly re-send or check state. | Met (`methods.md:553-561`, `managing-helpers.md:86-89`) |
| A12 No frontend change | Met | Met |
| A13 Branch, no PR | Met | Met (the worktree branch name differs; that comes from the harness) |

## 2. Unledgered decisions

Both arms independently picked the same mechanism for A2: a keyword-only `retry_on_timeout: bool = True` on `_ws_helper_call`. Good call: minimal, and `list` keeps the default.

**A (5 consequential):**
1. `_ws_helper_call` kwarg, as above. Good.
2. Late-reply lookup also runs when a future exists but is already done (`if not fut or fut.done()`, `websocket_service.py:775-776`). Neutral; this is unreachable in practice because `send_and_await_response` pops the future in `finally` (`:590-591`).
3. The late-failure WARNING includes HA's error `message` text (`:814-820`). Leaning bad: HA/voluptuous validation messages can echo input values, which cuts against the #6 redaction posture.
4. The `ResponseLostError` message embeds `close_code` (`:742-744`). Neutral to good.
5. The `send_and_wait` Raises section drops `FailedMessageError` entirely (`:708-713`). An HA rejection still raises it. Bad: the API docstring is now inaccurate.

**B (6 consequential):**
1. `_ws_helper_call` kwarg, as above. Good.
2. A late reply is only settled when no future is registered; a done future returns silently (`:768-773`). Neutral to good, and clearer.
3. The late-failure WARNING logs HA's `code`, not its message (`:803-809`). Good: no value-echo risk.
4. The exception messages themselves say "the command may or may not have applied" (`:735-746`). Good: logs are self-explanatory.
5. The `ResponseLostError` message omits `close_code`; the attribute still carries it. Neutral.
6. The Api-level `ws_send_and_wait` docstring now names `ResponseTimeoutError` (`api.py:343-346`, regenerated into `sync.py`), and `send_and_wait` keeps `FailedMessageError` under Raises. Good.

B's docs also claim HA creates a `_2`-suffixed duplicate on a re-sent create (`managing-helpers.md:88`). That matches HA's collection `IDManager` and is useful.

## 3. Correctness bugs and risks

- **B, MEDIUM-HIGH (tests): order-dependent caplog tests, confirmed.** `tests/unit/core/test_websocket_outcome_unknown.py:91, :149, :168, :183` read records through `caplog`. `tests/unit/conftest.py:259-261` (the `logging_pipeline` fixture) sets `logging.getLogger("hassette").propagate = False` and never restores it. Run after `test_logging_capture_handler.py` in the same process, 4 tests fail (`assert [] == [30]`). `:209` (`test_unrecorded_late_reply_is_silent`) then passes vacuously. Under `-n 4 --dist loadscope` this depends on which worker each module lands on, so it is a latent CI flake.
  - `tests/unit/web/conftest.py:8-21` already holds the known workaround (an autouse fixture that sets `propagate = True`). `tests/unit/core/test_ws_connection_state.py:139` documents that core tests mock the logger instead.
  - Fix: add that autouse fixture for this module, or switch to the mocked-logger convention.
- **A, LOW:** the late-failure WARNING carries HA's error message text (§2 A3). This is a payload-echo risk in logs, not in exceptions.
- **A, LOW:** two inaccurate docstrings: `send_and_wait` Raises omits `FailedMessageError` (`:708-713`), and the `_ws_helper_call` note (`api.py:261-264`) is misleading.
- **B, LOW:** `call_service` Raises lists only `ResponseTimeoutError` (`api.py:600-603`), not `ResponseLostError`.
- **Checked in both, no issue found:**
  - Late-reply detection: the future is popped in `finally` before the outer `except` registers the id, and there is no `await` between them, so no race.
  - Cap and eviction: `popitem(last=False)` after insert.
  - Clearing: both `cleanup()` and `partial_cleanup()` clear the record next to `_response_futures.clear()`.
  - Payload leakage: the exception messages carry type, id and cause only. `before_sleep_log` now logs redacted messages too.
  - `original_data=dict(data)`: the full outgoing payload including `id`.
  - Exception MRO: the marker has no `__init__`, so construction resolves to `FailedMessageError` / `RetryableConnectionClosedError` respectively.
  - Pre-send `ConnectionClosedError` is not converted. Correct, because nothing was sent.
  - Retry predicate: unchanged, matches `ResponseTimeoutError`, does not match `ResponseLostError`.
  - `sync.py`: matches the generator in both arms.
- **Shared, pre-existing, informational:** a retried read that times out on every attempt also gets tenacity's per-retry WARNING (`before_sleep_log`), so there is more than one WARNING per event. A's test comment at `test_websocket_service_coverage.py:186-190` implies only one fires. That is true only of `logger.warning` calls on the mock, not of the records actually emitted.

## 4. Test quality

**A: weaker pins.**
- Logging is tested by replacing `websocket_service.logger` with `Mock()` and asserting a substring of the *format string* (`"Outcome unknown"`, `"Late response"`, `"did not apply"`). Nothing checks that the type and id appear, which #12b requires. These are mock-called assertions, but they are robust to ordering.
- Regressions A would not catch:
  - `cleanup()` not clearing the record (only `partial_cleanup` is tested, `:257`).
  - Retried reads being recorded.
  - Unrecorded late replies logging.
  - Reads gaining `retry_on_timeout=False`. Helper `list` is the exception; it is pinned.
- The redaction check is weak: it only asserts `"counter" not in msg`.
- The cap test uses the real constant (101 sends at a 0s timeout). It is deterministic, but it checks only that the oldest id is gone, not the order.
- The disconnect test fakes the future's exception rather than driving `partial_cleanup`.

**B: stronger pins.**
- The redaction test uses a secret value (`hunter2`) and asserts `original_data` equals the full payload.
- Log records are checked for level, type and id.
- Tests cover: a retried read is not recorded, an unrecorded late reply is silent, `cleanup()` and `partial_cleanup()` both clear, the cap evicts in exact order (constant patched to 2), and a real `partial_cleanup` fails a pending send as `ResponseLostError`.
- The reads are parametrized, and helper CRUD is tested through `HelperClient`.
- The caplog design is the right observation for a spec that asks for log levels, but it is order-fragile (§3).
- B's tests patch the cap constant, so a change to 100 would go unnoticed. A doesn't assert the value 100 either.

## 5. Docs

- **A:**
  - Inaccurate claim at `harness.md:293-295`: "only `call_service`'s waiting paths ... can raise `ResponseTimeoutError`". `fire_event`, helper CRUD, `ws_send_and_wait`, and a retried read's final attempt all raise it too.
  - Missing items: #13's code example, the check-the-side-effect guidance next to the Low-level warning, and `fire_event` coverage in `methods.md`.
  - No invented API. The snippet runs and type-checks.
- **B:**
  - Everything checked was accurate. It covers every spec'd doc item, adds a `fire_event` paragraph (`methods.md:427-430`), and keeps the note that existing `FailedMessageError`/`RetryableConnectionClosedError` handlers still work.
  - No invented API: `api_recorder.assert_called("fire_event", event_type=...)` exists, and the snippet passes.

## 6. Verdict

**Merge B** after fixing its caplog propagation flake. That fix is a one-fixture change. B leads by a clear margin: the production code is close to equivalent, but B meets every ledger and Assumed item, while A misses several.

The three differences that matter most for the decision:

1. **Spec-verifying tests.** B has RED/GREEN commits and pins the #12b behaviors: type and id in the logs, `cleanup()` clearing, retried reads not recorded, silence for unrecorded replies, eviction order. It also pins the reads' retry default and the real `partial_cleanup` path. A pins mostly format strings on a mocked logger, has no RED commit, and leaves the reads untested.
2. **Docs completeness and accuracy.** A misses #13's code example and the Low-level check-state guidance, never updates the `FailedMessageError` `original_data` docstring, and makes a false claim in `harness.md`. B covers all of these accurately.
3. **B's one real defect.** Its caplog tests fail when run after a module that leaves the `hassette` logger non-propagating. A's mocked-logger tests don't have this problem, and it must be fixed before merging B. On the code side, A's late-failure log includes HA's message text where B logs only the code, a small edge in B's favor.
