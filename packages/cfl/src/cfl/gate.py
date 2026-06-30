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
        "trail-audit",
        "impl-comb",
        "shipping-gate",
    }
)

# Shared base from vocabulary.py; extend here when gate verdicts diverge from task verdicts.
VALID_GATE_VERDICTS: frozenset[str] = COMMON_VERDICTS


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
) -> None:
    """Record a gate evaluation result.

    Atomically INSERTs into gates and emits task.gated (when task_id is set)
    or review.gated (when task_id is None) into events.

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
