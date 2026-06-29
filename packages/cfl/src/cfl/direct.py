"""Direct-access tier for cfl — set_field() bypasses the state machine.

Implements `cfl set <entity> <id> <field>=<value> ...`.

This is the escape hatch for crash recovery, correcting state that guarded
commands can't reach, and debugging. Both tiers log everything — the `set.applied`
event captures before/after state for the audit trail.
"""

import json
import sqlite3

import cfl.output as output_module

# ---------------------------------------------------------------------------
# Entity → table mapping
# ---------------------------------------------------------------------------

VALID_ENTITIES: frozenset[str] = frozenset({"task", "run", "spec", "session"})

_ENTITY_TABLE: dict[str, str] = {
    "task": "tasks",
    "run": "runs",
    "spec": "specs",
    "session": "sessions",
}

# Primary key column name per entity.
_ENTITY_PK: dict[str, str] = {
    "task": "task_id",  # For tasks, ID is the task_id string within the active run.
    "run": "id",
    "spec": "id",
    "session": "id",
}

# Column names that exist in each table. Used to validate field names before
# issuing any UPDATE. Must match the schema in db.py exactly.
_ENTITY_COLUMNS: dict[str, frozenset[str]] = {
    "task": frozenset(
        {
            "status",
            "verdict",
            "verdict_detail",
            "commit_sha",
            "started_at",
            "ended_at",
            "title",
        }
    ),
    "run": frozenset(
        {
            "status",
            "base_commit",
            "visual_mode",
            "dev_server_url",
            "tmpdir",
            "started_at",
            "ended_at",
        }
    ),
    "spec": frozenset(
        {
            "status",
            "slug",
            "repo_url",
            "repo_path",
            "active_run_id",
            "created_at",
        }
    ),
    "session": frozenset(
        {
            "model",
            "context_pct_start",
            "context_pct_end",
            "started_at",
            "ended_at",
        }
    ),
}


def set_field(
    conn: sqlite3.Connection,
    entity: str,
    entity_id: str,
    fields: dict[str, str | None],
    *,
    active_run_id: int | None = None,
) -> None:
    """Apply arbitrary field updates to a row, bypassing state machine guards.

    Parameters
    ----------
    conn:
        Open DB connection.
    entity:
        One of: task, run, spec, session.
    entity_id:
        Row identifier. For task: task_id string (e.g. 'T03') — requires an
        active_run_id to scope the lookup. For run/spec/session: numeric ID as
        a string.
    fields:
        Mapping of column name → value. Use None to write SQL NULL.
    active_run_id:
        Required when entity='task' to scope the lookup by run.
    """
    if entity not in VALID_ENTITIES:
        output_module.emit_error(
            f"Unknown entity: {entity!r}. Valid entities: {sorted(VALID_ENTITIES)}",
            code="unknown_entity",
            exit_code=2,
        )

    if not fields:
        output_module.emit_error(
            "No fields specified. Provide at least one field=value pair.",
            code="usage_error",
            exit_code=2,
        )

    # Validate field names against known columns — exit 2 on unknown.
    valid_cols = _ENTITY_COLUMNS[entity]
    unknown = sorted(set(fields) - valid_cols)
    if unknown:
        output_module.emit_error(
            f"Unknown field(s) for entity '{entity}': {unknown}. "
            f"Valid fields: {sorted(valid_cols)}",
            code="unknown_field",
            exit_code=2,
        )

    table = _ENTITY_TABLE[entity]

    # Locate the row and read current values.
    row = _find_row(conn, entity, entity_id, table, active_run_id)
    if row is None:
        output_module.emit_error(
            f"No {entity} with id {entity_id!r} found.",
            code="not_found",
        )

    # Capture previous values for the audit event.
    previous = {col: row[col] for col in fields}

    # Apply updates — no state machine validation.
    set_clauses = ", ".join(f"{col}=?" for col in fields)
    values = list(fields.values())

    if entity == "task":
        # Tasks are scoped by run_id + task_id.
        where_clause = "run_id=? AND task_id=?"
        where_values = [active_run_id, entity_id]
    else:
        pk_col = _ENTITY_PK[entity]
        numeric_id = _parse_numeric_id(entity_id, entity)
        where_clause = f"{pk_col}=?"
        where_values = [numeric_id]

    conn.execute("BEGIN IMMEDIATE")
    try:
        conn.execute(
            f"UPDATE {table} SET {set_clauses} WHERE {where_clause}",
            [*values, *where_values],
        )

        # Log set.applied event with before/after state.
        event_data = json.dumps(
            {
                "entity": entity,
                "id": entity_id,
                "fields": {k: v for k, v in fields.items()},
                "previous": previous,
            }
        )
        cursor = conn.execute(
            """INSERT INTO events (run_id, event, data, created_at)
               VALUES (?, 'set.applied', ?, datetime('now'))""",
            (active_run_id, event_data),
        )
        event_id = cursor.lastrowid
        conn.execute("COMMIT")
    except Exception:
        conn.execute("ROLLBACK")
        raise

    output_module.emit(
        {
            "entity": entity,
            "id": entity_id,
            "updated": {k: v for k, v in fields.items()},
            "previous": previous,
            "event_id": event_id,
        }
    )


# ---------------------------------------------------------------------------
# Argument parsing helpers
# ---------------------------------------------------------------------------


def parse_field_args(raw_pairs: list[str]) -> dict[str, str | None]:
    """Parse 'field=value' positional args into a dict.

    'key=null' → None (SQL NULL).
    Values are kept as strings; type coercion happens at the DB layer.

    Raises SystemExit(2) on malformed input.
    """
    result: dict[str, str | None] = {}
    for pair in raw_pairs:
        if "=" not in pair:
            output_module.emit_error(
                f"Invalid field spec {pair!r}. Expected field=value or field=null.",
                code="usage_error",
                exit_code=2,
            )
        key, _, value = pair.partition("=")
        if not key:
            output_module.emit_error(
                f"Empty field name in {pair!r}.",
                code="usage_error",
                exit_code=2,
            )
        result[key] = None if value.lower() == "null" else value
    return result


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _find_row(
    conn: sqlite3.Connection,
    entity: str,
    entity_id: str,
    table: str,
    active_run_id: int | None,
) -> sqlite3.Row | None:
    """Fetch the target row for a set_field call."""
    if entity == "task":
        if active_run_id is None:
            output_module.emit_error(
                "cfl set task requires an active run. "
                "No active run found for the current spec.",
                code="no_active_run",
                hint="Start a run with `cfl run start`, or use --spec NNN.",
            )
        return conn.execute(
            "SELECT * FROM tasks WHERE run_id=? AND task_id=?",
            (active_run_id, entity_id),
        ).fetchone()

    numeric_id = _parse_numeric_id(entity_id, entity)
    pk_col = _ENTITY_PK[entity]
    return conn.execute(
        f"SELECT * FROM {table} WHERE {pk_col}=?",
        (numeric_id,),
    ).fetchone()


def _parse_numeric_id(entity_id: str, entity: str) -> int:
    """Parse entity_id as an integer. Exits with code 2 on failure."""
    try:
        return int(entity_id)
    except ValueError:
        output_module.emit_error(
            f"Entity id for '{entity}' must be a numeric integer, got: {entity_id!r}",
            code="usage_error",
            exit_code=2,
        )
        raise AssertionError("unreachable: emit_error always exits")
