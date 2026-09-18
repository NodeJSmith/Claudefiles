"""Tests for cfl.gate — gate evaluation recording."""

import json

import pytest
from cfl.gate import (
    GATE_TYPE_TO_STEP,
    KNOWN_GATE_TYPES,
    VALID_GATE_VERDICTS,
    record_gate,
    resolve_run_id_for_gate,
)

from tests.helpers import REMOTE_URL, insert_spec_with_run, insert_task

# ---------------------------------------------------------------------------
# Gate creation — basic happy path (FR#18, AC#18)
# ---------------------------------------------------------------------------


def test_record_gate_creates_gate_row_with_correct_fields(db_conn, capsys):
    """record_gate inserts a gates row with gate_type, verdict, and data (FR#18, AC#18)."""
    _, run_id = insert_spec_with_run(db_conn, 1, "my-feature", REMOTE_URL)
    insert_task(db_conn, run_id, "T01")

    record_gate(
        db_conn,
        run_id,
        "code-review",
        task_id="T01",
        verdict="PASS",
        data='{"findings": 0}',
    )

    gate = db_conn.execute(
        "SELECT * FROM gates WHERE run_id=? AND task_id='T01' AND gate_type='code-review'",
        (run_id,),
    ).fetchone()
    assert gate is not None
    assert gate["gate_type"] == "code-review"
    assert gate["verdict"] == "PASS"
    assert gate["iteration"] == 1
    stored = json.loads(gate["data"])
    assert stored["findings"] == 0


def test_record_gate_outputs_json_with_required_fields(db_conn, capsys):
    """record_gate emits JSON with gate_id, run_id, task_id, gate_type, verdict, iteration."""
    _, run_id = insert_spec_with_run(db_conn, 1, "my-feature", REMOTE_URL)
    insert_task(db_conn, run_id, "T01")

    record_gate(db_conn, run_id, "code-review", task_id="T01", verdict="PASS")

    out = json.loads(capsys.readouterr().out)
    assert "gate_id" in out
    assert isinstance(out["gate_id"], int)
    assert out["run_id"] == run_id
    assert out["task_id"] == "T01"
    assert out["gate_type"] == "code-review"
    assert out["verdict"] == "PASS"
    assert out["iteration"] == 1


def test_record_gate_stores_detail(db_conn, capsys):
    """record_gate stores the --detail field in the gate row."""
    _, run_id = insert_spec_with_run(db_conn, 1, "my-feature", REMOTE_URL)
    insert_task(db_conn, run_id, "T01")

    record_gate(
        db_conn,
        run_id,
        "code-review",
        task_id="T01",
        verdict="WARN",
        detail="minor nit",
    )

    gate = db_conn.execute(
        "SELECT detail FROM gates WHERE run_id=? AND gate_type='code-review'",
        (run_id,),
    ).fetchone()
    assert gate["detail"] == "minor nit"


def test_record_gate_run_level_no_task_id(db_conn, capsys):
    """record_gate works with task_id=None for run-level gates (Phase 3)."""
    _, run_id = insert_spec_with_run(db_conn, 1, "my-feature", REMOTE_URL)

    record_gate(db_conn, run_id, "impl-review", verdict="PASS")

    gate = db_conn.execute(
        "SELECT task_id, gate_type FROM gates WHERE run_id=? AND gate_type='impl-review'",
        (run_id,),
    ).fetchone()
    assert gate is not None
    assert gate["task_id"] is None

    out = json.loads(capsys.readouterr().out)
    assert out["task_id"] is None


# ---------------------------------------------------------------------------
# Iteration auto-increment (FR#18)
# ---------------------------------------------------------------------------


def test_record_gate_auto_increments_iteration_to_1_on_first_call(db_conn, capsys):
    """First gate for a (run, task, gate_type) starts at iteration=1."""
    _, run_id = insert_spec_with_run(db_conn, 1, "my-feature", REMOTE_URL)
    insert_task(db_conn, run_id, "T01")

    record_gate(db_conn, run_id, "code-review", task_id="T01", verdict="PASS")

    gate = db_conn.execute(
        "SELECT iteration FROM gates WHERE run_id=? AND task_id='T01' AND gate_type='code-review'",
        (run_id,),
    ).fetchone()
    assert gate["iteration"] == 1


def test_record_gate_auto_increments_iteration_on_retry(db_conn, capsys):
    """record_gate auto-increments iteration for same (run, task, gate_type) on retry."""
    _, run_id = insert_spec_with_run(db_conn, 1, "my-feature", REMOTE_URL)
    insert_task(db_conn, run_id, "T01")

    record_gate(db_conn, run_id, "code-review", task_id="T01", verdict="FAIL")
    _ = capsys.readouterr()
    record_gate(db_conn, run_id, "code-review", task_id="T01", verdict="PASS")

    gates = db_conn.execute(
        """SELECT iteration FROM gates
           WHERE run_id=? AND task_id='T01' AND gate_type='code-review'
           ORDER BY iteration""",
        (run_id,),
    ).fetchall()
    assert len(gates) == 2
    assert gates[0]["iteration"] == 1
    assert gates[1]["iteration"] == 2


def test_record_gate_explicit_iteration_overrides_auto(db_conn, capsys):
    """Providing iteration= uses that value instead of auto-incrementing."""
    _, run_id = insert_spec_with_run(db_conn, 1, "my-feature", REMOTE_URL)
    insert_task(db_conn, run_id, "T01")

    record_gate(
        db_conn, run_id, "code-review", task_id="T01", verdict="PASS", iteration=7
    )

    gate = db_conn.execute(
        "SELECT iteration FROM gates WHERE run_id=? AND gate_type='code-review'",
        (run_id,),
    ).fetchone()
    assert gate["iteration"] == 7


def test_record_gate_run_level_auto_increments_separately_from_task_level(
    db_conn, capsys
):
    """Run-level gate iteration is counted separately from task-level iterations."""
    _, run_id = insert_spec_with_run(db_conn, 1, "my-feature", REMOTE_URL)
    insert_task(db_conn, run_id, "T01")

    # task-level gate: iteration 1
    record_gate(db_conn, run_id, "code-review", task_id="T01", verdict="PASS")
    _ = capsys.readouterr()
    # run-level gate of same type: also iteration 1 (independent counter)
    record_gate(db_conn, run_id, "code-review", verdict="PASS")

    run_gate = db_conn.execute(
        "SELECT iteration FROM gates WHERE run_id=? AND task_id IS NULL AND gate_type='code-review'",
        (run_id,),
    ).fetchone()
    assert run_gate["iteration"] == 1


# ---------------------------------------------------------------------------
# Implicit event emission (FR#21, AC#18)
# ---------------------------------------------------------------------------


def test_record_gate_emits_task_gated_for_task_level(db_conn, capsys):
    """record_gate emits task.gated event when task_id is provided (FR#21)."""
    _, run_id = insert_spec_with_run(db_conn, 1, "my-feature", REMOTE_URL)
    insert_task(db_conn, run_id, "T01")

    record_gate(db_conn, run_id, "code-review", task_id="T01", verdict="PASS")

    event = db_conn.execute(
        "SELECT event, task_id, data FROM events WHERE run_id=? AND event='task.gated'",
        (run_id,),
    ).fetchone()
    assert event is not None
    assert event["task_id"] == "T01"
    event_data = json.loads(event["data"])
    assert event_data["gate_type"] == "code-review"
    assert event_data["verdict"] == "PASS"


def test_record_gate_emits_review_gated_for_run_level(db_conn, capsys):
    """record_gate emits review.gated event when task_id is None (run-level gate)."""
    _, run_id = insert_spec_with_run(db_conn, 1, "my-feature", REMOTE_URL)

    record_gate(db_conn, run_id, "impl-review", verdict="PASS")

    event = db_conn.execute(
        "SELECT event, task_id FROM events WHERE run_id=? AND event='review.gated'",
        (run_id,),
    ).fetchone()
    assert event is not None
    assert event["task_id"] is None


def test_record_gate_does_not_emit_task_gated_for_run_level(db_conn, capsys):
    """record_gate does NOT emit task.gated for run-level gates."""
    _, run_id = insert_spec_with_run(db_conn, 1, "my-feature", REMOTE_URL)

    record_gate(db_conn, run_id, "impl-review", verdict="PASS")

    count = db_conn.execute(
        "SELECT COUNT(*) AS cnt FROM events WHERE run_id=? AND event='task.gated'",
        (run_id,),
    ).fetchone()["cnt"]
    assert count == 0


# ---------------------------------------------------------------------------
# Unknown gate_type — warn but still write (vocabulary validation)
# ---------------------------------------------------------------------------


def test_record_gate_unknown_gate_type_warns_stderr(db_conn, capsys):
    """record_gate emits a warning to stderr for unknown gate_type."""
    _, run_id = insert_spec_with_run(db_conn, 1, "my-feature", REMOTE_URL)

    record_gate(db_conn, run_id, "my-custom-gate", verdict="PASS")

    captured = capsys.readouterr()
    assert captured.err  # something went to stderr


def test_record_gate_unknown_gate_type_still_writes_row(db_conn, capsys):
    """record_gate writes the gate row even when gate_type is unknown."""
    _, run_id = insert_spec_with_run(db_conn, 1, "my-feature", REMOTE_URL)

    record_gate(db_conn, run_id, "my-custom-gate", verdict="PASS")

    gate = db_conn.execute(
        "SELECT gate_type FROM gates WHERE run_id=? AND gate_type='my-custom-gate'",
        (run_id,),
    ).fetchone()
    assert gate is not None


# ---------------------------------------------------------------------------
# Invalid verdict — exit 2 (design invariant)
# ---------------------------------------------------------------------------


def test_record_gate_invalid_verdict_exits_2(db_conn, capsys):
    """record_gate exits 2 with invalid_verdict for unknown verdict strings."""
    _, run_id = insert_spec_with_run(db_conn, 1, "my-feature", REMOTE_URL)

    with pytest.raises(SystemExit) as exc_info:
        record_gate(db_conn, run_id, "code-review", task_id="T01", verdict="APPROVE")
    assert exc_info.value.code == 2

    err = json.loads(capsys.readouterr().err)
    assert err["code"] == "invalid_verdict"


def test_record_gate_all_valid_verdicts_accepted(db_conn, capsys):
    """Each of PASS, WARN, FAIL, SKIPPED is accepted by record_gate."""
    _, run_id = insert_spec_with_run(db_conn, 1, "my-feature", REMOTE_URL)

    for index, verdict in enumerate(sorted(VALID_GATE_VERDICTS), start=1):
        task_id = f"T{index:02d}"
        insert_task(db_conn, run_id, task_id)
        record_gate(db_conn, run_id, "code-review", task_id=task_id, verdict=verdict)
        _ = capsys.readouterr()


# ---------------------------------------------------------------------------
# Vocabulary constants are exported
# ---------------------------------------------------------------------------


def test_known_gate_types_exported():
    """KNOWN_GATE_TYPES is a frozenset with the expected canonical types."""
    assert "code-review" in KNOWN_GATE_TYPES
    assert "impl-review" in KNOWN_GATE_TYPES
    assert "shipping-gate" in KNOWN_GATE_TYPES
    assert "verdict-assembly" in KNOWN_GATE_TYPES
    assert "plan-validation" in KNOWN_GATE_TYPES
    assert "define-signoff" in KNOWN_GATE_TYPES
    assert "define-blindspot" in KNOWN_GATE_TYPES
    assert "define-challenge" in KNOWN_GATE_TYPES
    assert "sketch-challenge" in KNOWN_GATE_TYPES
    assert "ship-challenge" in KNOWN_GATE_TYPES


def test_valid_gate_verdicts_exported():
    """VALID_GATE_VERDICTS contains PASS, WARN, FAIL, SKIPPED."""
    assert VALID_GATE_VERDICTS == frozenset({"PASS", "WARN", "FAIL", "SKIPPED"})


# ---------------------------------------------------------------------------
# resolve_run_id_for_gate
# ---------------------------------------------------------------------------


def test_resolve_run_id_for_gate_returns_owning_run_id(db_conn, capsys):
    """Looks up run_id from the gate row, authoritative regardless of how
    many runs are active elsewhere in the repo."""
    _, run_id = insert_spec_with_run(db_conn, 1, "my-feature", REMOTE_URL)
    record_gate(db_conn, run_id, "ship-challenge", verdict="PASS")
    gate_id = json.loads(capsys.readouterr().out)["gate_id"]

    assert resolve_run_id_for_gate(db_conn, gate_id) == run_id


def test_resolve_run_id_for_gate_missing_gate_exits_2(db_conn):
    with pytest.raises(SystemExit) as exc_info:
        resolve_run_id_for_gate(db_conn, 999999)
    assert exc_info.value.code == 2


# ---------------------------------------------------------------------------
# Position advancement (FR#1, FR#2, FR#3, FR#4, FR#8, AC#1, AC#2, AC#3, AC#4,
# AC#8, AC#9, AC#10)
# ---------------------------------------------------------------------------


def test_record_gate_phase3_pass_advances_pipeline_step(db_conn, capsys):
    """Phase 3 run-level gate + PASS advances pipeline_step to the gate type name (AC#1)."""
    _, run_id = insert_spec_with_run(db_conn, 1, "my-feature", REMOTE_URL)

    record_gate(db_conn, run_id, "impl-review", verdict="PASS")

    row = db_conn.execute(
        "SELECT pipeline_step FROM runs WHERE id=?", (run_id,)
    ).fetchone()
    assert row["pipeline_step"] == "impl-review"


def test_record_gate_phase3_fail_does_not_advance_pipeline_step(db_conn, capsys):
    """Phase 3 run-level gate + FAIL leaves pipeline_step unchanged (AC#2)."""
    _, run_id = insert_spec_with_run(db_conn, 1, "my-feature", REMOTE_URL)

    record_gate(db_conn, run_id, "impl-review", verdict="FAIL")

    row = db_conn.execute(
        "SELECT pipeline_step FROM runs WHERE id=?", (run_id,)
    ).fetchone()
    assert row["pipeline_step"] is None


def test_record_gate_backward_move_does_not_regress_pipeline_step(db_conn, capsys):
    """A gate call earlier in GATE_TYPE_TO_STEP order than the current step warns and does not regress pipeline_step."""
    _, run_id = insert_spec_with_run(db_conn, 1, "my-feature", REMOTE_URL)

    record_gate(db_conn, run_id, "cross-file-review", verdict="PASS")
    record_gate(db_conn, run_id, "impl-review", verdict="PASS")

    row = db_conn.execute(
        "SELECT pipeline_step FROM runs WHERE id=?", (run_id,)
    ).fetchone()
    assert row["pipeline_step"] == "cross-file-review"
    err = json.loads(capsys.readouterr().err)
    assert err["code"] == "pipeline_step_backward_move"


def test_record_gate_backward_move_does_not_regress_reviewed_head(db_conn, capsys):
    """A backward-move gate call must leave reviewed_head unchanged too, not just pipeline_step.

    Otherwise the staleness check (reviewed_head vs current git HEAD) can report "not stale"
    for a later step that never actually re-ran against that HEAD.
    """
    _, run_id = insert_spec_with_run(db_conn, 1, "my-feature", REMOTE_URL)

    record_gate(
        db_conn, run_id, "cross-file-review", verdict="PASS", reviewed_head="H1"
    )
    capsys.readouterr()
    record_gate(db_conn, run_id, "impl-review", verdict="PASS", reviewed_head="H2")

    row = db_conn.execute(
        "SELECT pipeline_step, reviewed_head FROM runs WHERE id=?", (run_id,)
    ).fetchone()
    assert row["pipeline_step"] == "cross-file-review"
    assert row["reviewed_head"] == "H1"
    err = json.loads(capsys.readouterr().err)
    assert err["code"] == "pipeline_step_backward_move"


def test_record_gate_same_step_reissued_does_not_warn(db_conn, capsys):
    """Re-issuing the same gate type is a no-op advance (equal index), not a backward move."""
    _, run_id = insert_spec_with_run(db_conn, 1, "my-feature", REMOTE_URL)

    record_gate(db_conn, run_id, "final-review", verdict="PASS")
    capsys.readouterr()
    record_gate(db_conn, run_id, "final-review", verdict="PASS")

    row = db_conn.execute(
        "SELECT pipeline_step FROM runs WHERE id=?", (run_id,)
    ).fetchone()
    assert row["pipeline_step"] == "final-review"
    captured = capsys.readouterr()
    assert captured.err == "" or "pipeline_step_backward_move" not in captured.err


def test_record_gate_non_phase3_gate_does_not_advance_pipeline_step(db_conn, capsys):
    """A non-Phase-3 gate type leaves pipeline_step unchanged (AC#3)."""
    _, run_id = insert_spec_with_run(db_conn, 1, "my-feature", REMOTE_URL)

    record_gate(db_conn, run_id, "define-comb", verdict="PASS")

    row = db_conn.execute(
        "SELECT pipeline_step FROM runs WHERE id=?", (run_id,)
    ).fetchone()
    assert row["pipeline_step"] is None


def test_record_gate_phase3_run_level_updates_reviewed_head(db_conn, capsys):
    """Phase 3 run-level gate with reviewed_head passed updates runs.reviewed_head (AC#4)."""
    _, run_id = insert_spec_with_run(db_conn, 1, "my-feature", REMOTE_URL)

    record_gate(db_conn, run_id, "impl-review", verdict="PASS", reviewed_head="deadbee")

    row = db_conn.execute(
        "SELECT reviewed_head FROM runs WHERE id=?", (run_id,)
    ).fetchone()
    assert row["reviewed_head"] == "deadbee"


def test_record_gate_fail_at_current_step_does_not_update_reviewed_head(
    db_conn, capsys
):
    """A FAIL at the run's already-advanced current step must not update reviewed_head.

    Otherwise resume sees reviewed_head matching the current git HEAD and concludes
    the failed step isn't stale, skipping it instead of re-running it.
    """
    _, run_id = insert_spec_with_run(db_conn, 1, "my-feature", REMOTE_URL)

    record_gate(db_conn, run_id, "impl-review", verdict="PASS", reviewed_head="H1")
    record_gate(db_conn, run_id, "impl-review", verdict="FAIL", reviewed_head="H2")

    row = db_conn.execute(
        "SELECT pipeline_step, reviewed_head FROM runs WHERE id=?", (run_id,)
    ).fetchone()
    assert row["pipeline_step"] == "impl-review"
    assert row["reviewed_head"] == "H1"


def test_record_gate_skipped_at_current_step_updates_reviewed_head(db_conn, capsys):
    """SKIPPED means the step was evaluated and doesn't need to run — reviewed_head updates."""
    _, run_id = insert_spec_with_run(db_conn, 1, "my-feature", REMOTE_URL)

    record_gate(db_conn, run_id, "impl-review", verdict="PASS", reviewed_head="H1")
    record_gate(db_conn, run_id, "impl-review", verdict="SKIPPED", reviewed_head="H2")

    row = db_conn.execute(
        "SELECT pipeline_step, reviewed_head FROM runs WHERE id=?", (run_id,)
    ).fetchone()
    assert row["pipeline_step"] == "impl-review"
    assert row["reviewed_head"] == "H2"


def test_record_gate_non_phase3_gate_does_not_update_reviewed_head(db_conn, capsys):
    """A non-Phase-3 gate type leaves reviewed_head unchanged, even if passed (AC#10)."""
    _, run_id = insert_spec_with_run(db_conn, 1, "my-feature", REMOTE_URL)

    record_gate(db_conn, run_id, "define-comb", verdict="PASS", reviewed_head="deadbee")

    row = db_conn.execute(
        "SELECT reviewed_head FROM runs WHERE id=?", (run_id,)
    ).fetchone()
    assert row["reviewed_head"] is None


def test_record_gate_task_scoped_phase3_gate_does_not_advance_position(db_conn, capsys):
    """A task-scoped gate reusing a Phase-3 gate type name must not advance
    pipeline_step or reviewed_head (AC#9, AC#10)."""
    _, run_id = insert_spec_with_run(db_conn, 1, "my-feature", REMOTE_URL)
    insert_task(db_conn, run_id, "T01")

    record_gate(
        db_conn,
        run_id,
        "impl-review",
        task_id="T01",
        verdict="PASS",
        reviewed_head="abc1234",
    )

    row = db_conn.execute(
        "SELECT pipeline_step, reviewed_head FROM runs WHERE id=?", (run_id,)
    ).fetchone()
    assert row["pipeline_step"] is None
    assert row["reviewed_head"] is None


def test_known_issues_walkthrough_in_known_gate_types():
    """known-issues-walkthrough is a recognized gate type (FR#8, AC#8)."""
    assert "known-issues-walkthrough" in KNOWN_GATE_TYPES


def test_known_issues_walkthrough_in_gate_type_to_step():
    """known-issues-walkthrough maps to a pipeline step (FR#8, AC#8)."""
    assert "known-issues-walkthrough" in GATE_TYPE_TO_STEP
    assert GATE_TYPE_TO_STEP["known-issues-walkthrough"] == "known-issues-walkthrough"
