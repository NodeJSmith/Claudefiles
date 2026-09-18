"""Gate evaluation recording for cfl.

Implements record_gate() — inserts into gates table and emits the implicit
task.gated or review.gated event in a single atomic transaction.
"""

import json
import sqlite3

import cfl.output as output_module
from cfl.session import read_context_pct
from cfl.vocabulary import COMMON_VERDICTS

KNOWN_GATE_TYPES: frozenset[str] = frozenset(
    {
        "spec-review",
        "code-review",
        "integration-review",
        "test-gate",
        "lint-gate",
        "visual-review",
        "verdict-assembly",
        "impl-review",
        "cross-file-review",
        "clean-code",
        "final-review",
        "shipping-gate",
        "define-blindspot",
        "define-comb",
        "define-signoff",
        "plan-validation",
        "plan-review",
        "plan-comb",
        "plan-approval",
        "sketch-comb",
        "define-challenge",
        "sketch-challenge",
        "ship-challenge",
        "known-issues-walkthrough",
    }
)

# Maps Phase 3 gate types to pipeline step names (identity mapping — step
# names ARE the gate type names). Insertion order matches the pipeline step
# sequence and is load-bearing: resume uses it to determine "the step after
# pipeline_step."
GATE_TYPE_TO_STEP: dict[str, str] = {
    "impl-review": "impl-review",
    "cross-file-review": "cross-file-review",
    "ship-challenge": "ship-challenge",
    "clean-code": "clean-code",
    "final-review": "final-review",
    "known-issues-walkthrough": "known-issues-walkthrough",
    "shipping-gate": "shipping-gate",
}

# Shared base from vocabulary.py; extend here when gate verdicts diverge from task verdicts.
VALID_GATE_VERDICTS: frozenset[str] = COMMON_VERDICTS

# Verdicts that count as "the step is done" for pipeline_step advancement.
ADVANCING_VERDICTS: frozenset[str] = frozenset({"PASS", "WARN"})


def record_gate(
    conn: sqlite3.Connection,
    run_id: int,
    gate_type: str,
    *,
    task_id: str | None = None,
    verdict: str,
    iteration: int | None = None,
    detail: str | None = None,
    data: str | None = None,
    reviewed_head: str | None = None,
) -> None:
    """Record a gate evaluation result.

    Atomically INSERTs into gates and emits task.gated (when task_id is set)
    or review.gated (when task_id is None) into events. For Phase 3 run-level
    gates (task_id is None and gate_type is in GATE_TYPE_TO_STEP), also
    advances runs.pipeline_step (on PASS/WARN) and runs.reviewed_head (when
    reviewed_head is provided) in the same transaction.

    Warns to stderr for unknown gate_type but still writes.
    Exits 2 for invalid verdict.
    data must be a valid JSON string when provided.
    """
    if gate_type not in KNOWN_GATE_TYPES:
        output_module.emit_warning(
            f"Unknown gate_type '{gate_type}'. Known types: {sorted(KNOWN_GATE_TYPES)}",
            code="unknown_gate_type",
        )

    if verdict not in VALID_GATE_VERDICTS:
        output_module.emit_error(
            f"Unknown verdict '{verdict}'. Use: {', '.join(sorted(VALID_GATE_VERDICTS))}.",
            code="invalid_verdict",
            exit_code=2,
        )

    if data is not None:
        try:
            json.loads(data)
        except json.JSONDecodeError as exc:
            output_module.emit_error(
                f"--data is not valid JSON: {exc}",
                code="invalid_json",
                exit_code=2,
            )

    context_pct = read_context_pct()

    conn.execute("BEGIN IMMEDIATE")
    try:
        if iteration is None:
            iter_row = conn.execute(
                """SELECT COALESCE(MAX(iteration), 0) + 1 AS next_iter
                   FROM gates WHERE run_id=? AND task_id IS ? AND gate_type=?""",
                (run_id, task_id, gate_type),
            ).fetchone()
            iteration = iter_row["next_iter"]

        cursor = conn.execute(
            """INSERT INTO gates
               (run_id, task_id, gate_type, iteration, verdict, detail, data, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, datetime('now'))""",
            (run_id, task_id, gate_type, iteration, verdict, detail, data),
        )
        gate_id = cursor.lastrowid

        event_name = "task.gated" if task_id is not None else "review.gated"
        event_data = json.dumps({"gate_type": gate_type, "verdict": verdict})
        conn.execute(
            """INSERT INTO events (run_id, task_id, event, data, context_pct, created_at)
               VALUES (?, ?, ?, ?, ?, datetime('now'))""",
            (run_id, task_id, event_name, event_data, context_pct),
        )

        _advance_pipeline_position(
            conn,
            run_id,
            gate_type,
            task_id=task_id,
            verdict=verdict,
            reviewed_head=reviewed_head,
        )

        conn.execute("COMMIT")
    except Exception:
        conn.execute("ROLLBACK")
        raise

    output_module.emit(
        {
            "gate_id": gate_id,
            "run_id": run_id,
            "task_id": task_id,
            "gate_type": gate_type,
            "verdict": verdict,
            "iteration": iteration,
        }
    )


def _advance_pipeline_position(
    conn: sqlite3.Connection,
    run_id: int,
    gate_type: str,
    *,
    task_id: str | None,
    verdict: str,
    reviewed_head: str | None,
) -> None:
    """Update runs.pipeline_step and runs.reviewed_head for a Phase 3 run-level gate.

    Must be called inside record_gate()'s open transaction — issues UPDATEs
    only, no BEGIN/COMMIT of its own. No-op when gate_type isn't in
    GATE_TYPE_TO_STEP or task_id is set (task-scoped gates never touch
    run-level position).
    """
    step = GATE_TYPE_TO_STEP.get(gate_type)
    is_phase3_run_level = step is not None and task_id is None
    if not is_phase3_run_level:
        return

    if verdict in ADVANCING_VERDICTS:
        step_order = list(GATE_TYPE_TO_STEP.values())
        current_step = conn.execute(
            "SELECT pipeline_step FROM runs WHERE id = ?", (run_id,)
        ).fetchone()["pipeline_step"]
        # A pipeline_step written out-of-band (e.g. via `cfl set run`) to a
        # value outside GATE_TYPE_TO_STEP's vocabulary is treated as unset
        # here: recovery is "accept this gate's step and move on" rather than
        # refusing to advance past an unrecognized value forever.
        is_forward = (
            current_step is None
            or current_step not in step_order
            or step_order.index(step) >= step_order.index(current_step)
        )
        if is_forward:
            conn.execute(
                "UPDATE runs SET pipeline_step = ? WHERE id = ?",
                (step, run_id),
            )
        else:
            output_module.emit_warning(
                f"Gate '{gate_type}' would move pipeline_step backward "
                f"(from '{current_step}' to '{step}'); not advancing. "
                "Use `cfl set run` to force a backward move if intentional.",
                code="pipeline_step_backward_move",
            )

    # Unlike pipeline_step above, this has no verdict check — SKIPPED (and
    # FAIL) still update reviewed_head. Intentional: reviewed_head tracks
    # "code as of this HEAD was seen by this step," not "this step passed."
    if reviewed_head is not None:
        conn.execute(
            "UPDATE runs SET reviewed_head = ? WHERE id = ?",
            (reviewed_head, run_id),
        )


def resolve_run_id_for_gate(conn: sqlite3.Connection, gate_id: int) -> int:
    """Look up the run_id a gate belongs to.

    gates.run_id is NOT NULL, so this is authoritative for gate-backed
    findings — unlike the ambiguous repo-wide active-run lookup, which
    returns None whenever more than one spec run is active for the repo.
    Exits 2 if gate_id does not exist.
    """
    row = conn.execute("SELECT run_id FROM gates WHERE id = ?", (gate_id,)).fetchone()
    if row is None:
        output_module.emit_error(
            f"Gate {gate_id} not found.",
            code="gate_not_found",
            exit_code=2,
        )
    return row["run_id"]
