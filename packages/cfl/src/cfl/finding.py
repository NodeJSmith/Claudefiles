"""Challenge/review finding tracking for cfl.

Records design-level and code-level findings raised by challenge (and, in
future, other producers — see `source`) across mine-define, mine-sketch, and
mine-orchestrate runs. Models on `question.py`: findings are leaf telemetry,
so `record_finding` emits no implicit event the way `record_gate` does.

`severity` is open vocabulary — it is a producer's own taxonomy (challenge's
CRITICAL/HIGH/MEDIUM/TENSION today; a future producer may use a different
scale), so unknown values warn but still write, with no DDL `CHECK`.
`visibility`, `disposition`, and `design_level` are cfl's own vocabulary —
closed, DDL-`CHECK`ed, and rejected outright on an unknown value.
`source`, `finding_type`, and `classification` are unconstrained free text
with no frozenset at all — single-producer columns where validation ceremony
is premature.
"""

import json
import sqlite3

import cfl.output as output_module
from cfl.session import read_context_pct

KNOWN_SEVERITIES: frozenset[str] = frozenset({"CRITICAL", "HIGH", "MEDIUM", "TENSION"})

VALID_VISIBILITIES: frozenset[str] = frozenset(
    {"presented", "overflow", "likely-invalid"}
)

VALID_DISPOSITIONS: frozenset[str] = frozenset(
    {"pending", "applied", "skipped", "filed"}
)

VALID_DESIGN_LEVELS: frozenset[str] = frozenset({"Yes", "No"})

REQUIRED_BATCH_FIELDS: tuple[str, ...] = (
    "finding_num",
    "title",
    "severity",
    "visibility",
)


def validate_finding_fields(
    severity: str | None,
    visibility: str | None,
    disposition: str | None,
    design_level: str | None,
) -> None:
    """Validate one finding's severity/visibility/disposition/design_level.

    Shared by record_finding and record_finding_batch so the four tiers of
    validation are defined once. Warns for unknown severity but still
    returns. Exits 2 for invalid visibility, disposition, or design_level.
    """
    if severity not in KNOWN_SEVERITIES:
        output_module.emit_warning(
            f"Unknown severity '{severity}'. Known: {sorted(KNOWN_SEVERITIES)}",
            code="unknown_severity",
        )

    if visibility not in VALID_VISIBILITIES:
        output_module.emit_error(
            f"Unknown visibility '{visibility}'."
            f" Use: {', '.join(sorted(VALID_VISIBILITIES))}.",
            code="invalid_visibility",
            exit_code=2,
        )

    if disposition is not None and disposition not in VALID_DISPOSITIONS:
        output_module.emit_error(
            f"Unknown disposition '{disposition}'."
            f" Use: {', '.join(sorted(VALID_DISPOSITIONS))}.",
            code="invalid_disposition",
            exit_code=2,
        )

    if design_level is not None and design_level not in VALID_DESIGN_LEVELS:
        output_module.emit_error(
            f"Unknown design_level '{design_level}'."
            f" Use: {', '.join(sorted(VALID_DESIGN_LEVELS))}.",
            code="invalid_design_level",
            exit_code=2,
        )


def record_finding(
    conn: sqlite3.Connection,
    run_id: int | None,
    gate_id: int | None,
    source: str,
    finding_num: int,
    *,
    title: str,
    severity: str,
    visibility: str,
    target: str | None = None,
    finding_type: str | None = None,
    design_level: str | None = None,
    raised_by: str | None = None,
    classification: str | None = None,
    disposition: str | None = None,
    why_it_matters: str | None = None,
) -> None:
    """Record a single finding.

    Warns for unknown severity but still writes.
    Exits 2 for invalid visibility, invalid disposition, or invalid design_level.
    """
    validate_finding_fields(severity, visibility, disposition, design_level)

    context_pct = read_context_pct()

    cursor = conn.execute(
        """INSERT INTO findings
             (run_id, gate_id, source, finding_num, title, target, severity,
              finding_type, design_level, raised_by, classification, visibility,
              disposition, why_it_matters, context_pct, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))""",
        (
            run_id,
            gate_id,
            source,
            finding_num,
            title,
            target,
            severity,
            finding_type,
            design_level,
            raised_by,
            classification,
            visibility,
            disposition,
            why_it_matters,
            context_pct,
        ),
    )
    finding_id = cursor.lastrowid

    output_module.emit(
        {
            "finding_id": finding_id,
            "run_id": run_id,
            "gate_id": gate_id,
            "source": source,
            "finding_num": finding_num,
        }
    )


def record_finding_batch(
    conn: sqlite3.Connection,
    gate_id: int | None,
    findings_file: str,
    *,
    source: str,
    run_id: int | None = None,
) -> int:
    """Write every finding in a JSON file for one gate in a single transaction.

    findings_file is a path to a JSON array of finding objects, each carrying
    the same keys as record_finding's parameters (minus conn, run_id, gate_id,
    and source, which are supplied here). Applies the same validation tiers as
    record_finding: unknown severity warns but still writes; an invalid
    visibility, disposition, or design_level anywhere in the array is
    validated before any row is written, so a violation rejects the whole
    batch (exit 2) with no partial writes. Returns the number of rows written.

    Exits 2 with invalid_findings_file if findings_file is missing, is not
    valid JSON, or does not parse to a JSON array.
    """
    try:
        with open(findings_file) as f:
            findings = json.load(f)
    except (OSError, json.JSONDecodeError) as e:
        output_module.emit_error(
            f"Could not read findings file '{findings_file}': {e}",
            code="invalid_findings_file",
            exit_code=2,
        )

    if not isinstance(findings, list):
        output_module.emit_error(
            f"Findings file '{findings_file}' must contain a JSON array.",
            code="invalid_findings_file",
            exit_code=2,
        )

    for finding in findings:
        if not isinstance(finding, dict):
            output_module.emit_error(
                f"Each finding must be a JSON object, got {type(finding).__name__}",
                code="invalid_findings_file",
                exit_code=2,
            )

        missing = [
            field for field in REQUIRED_BATCH_FIELDS if finding.get(field) is None
        ]
        if missing:
            output_module.emit_error(
                f"Finding is missing required field(s): {', '.join(missing)}",
                code="invalid_findings_file",
                exit_code=2,
            )

        validate_finding_fields(
            finding.get("severity"),
            finding.get("visibility"),
            finding.get("disposition"),
            finding.get("design_level"),
        )

    context_pct = read_context_pct()

    conn.execute("BEGIN IMMEDIATE")
    try:
        for finding in findings:
            conn.execute(
                """INSERT INTO findings
                     (run_id, gate_id, source, finding_num, title, target, severity,
                      finding_type, design_level, raised_by, classification, visibility,
                      disposition, why_it_matters, context_pct, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))""",
                (
                    run_id,
                    gate_id,
                    source,
                    finding.get("finding_num"),
                    finding.get("title"),
                    finding.get("target"),
                    finding.get("severity"),
                    finding.get("finding_type"),
                    finding.get("design_level"),
                    finding.get("raised_by"),
                    finding.get("classification"),
                    finding.get("visibility"),
                    finding.get("disposition"),
                    finding.get("why_it_matters"),
                    context_pct,
                ),
            )
        conn.execute("COMMIT")
    except Exception:
        conn.execute("ROLLBACK")
        raise

    output_module.emit(
        {"batch_size": len(findings), "gate_id": gate_id, "source": source}
    )
    return len(findings)


def list_findings(
    conn: sqlite3.Connection,
    *,
    source: str | None = None,
    severity: str | None = None,
    gate_id: int | None = None,
    run_id: int | None = None,
    limit: int = 50,
) -> None:
    """Query findings with optional filters.

    Warns for unknown severity but still queries.
    Exits 2 for a negative limit.
    """
    if severity is not None and severity not in KNOWN_SEVERITIES:
        output_module.emit_warning(
            f"Unknown severity '{severity}'. Known: {sorted(KNOWN_SEVERITIES)}",
            code="unknown_severity",
        )

    if limit < 0:
        output_module.emit_error(
            f"Invalid limit '{limit}'. Must be non-negative.",
            code="invalid_limit",
            exit_code=2,
        )

    conditions: list[str] = []
    params: list[str | int] = []

    if source is not None:
        conditions.append("source = ?")
        params.append(source)
    if severity is not None:
        conditions.append("severity = ?")
        params.append(severity)
    if gate_id is not None:
        conditions.append("gate_id = ?")
        params.append(gate_id)
    if run_id is not None:
        conditions.append("run_id = ?")
        params.append(run_id)

    where = f" WHERE {' AND '.join(conditions)}" if conditions else ""
    params.append(limit)

    rows = conn.execute(
        "SELECT id, run_id, gate_id, source, finding_num, title, target, severity,"
        " finding_type, design_level, raised_by, classification, visibility,"
        " disposition, why_it_matters, context_pct, resolved_at, created_at"
        f" FROM findings{where} ORDER BY id DESC LIMIT ?",
        params,
    ).fetchall()

    findings = []
    for r in rows:
        finding = dict(r)
        if finding.get("created_at"):
            finding["created_at"] = output_module.to_iso(finding["created_at"])
        if finding.get("resolved_at"):
            finding["resolved_at"] = output_module.to_iso(finding["resolved_at"])
        findings.append(finding)

    output_module.emit({"count": len(findings), "findings": findings})


def resolve_finding(
    conn: sqlite3.Connection,
    gate_id: int,
    finding_num: int,
    disposition: str,
) -> int:
    """Update a presented finding's disposition and stamp resolved_at.

    Exits 2 for invalid disposition.
    The `visibility = 'presented'` guard means an overflow or likely-invalid
    finding is never resolved this way. Returns the updated row count (0 or
    1) so the caller can detect a finding_num with no matching presented row.
    """
    if disposition not in VALID_DISPOSITIONS:
        output_module.emit_error(
            f"Unknown disposition '{disposition}'."
            f" Use: {', '.join(sorted(VALID_DISPOSITIONS))}.",
            code="invalid_disposition",
            exit_code=2,
        )

    cursor = conn.execute(
        """UPDATE findings SET disposition = ?, resolved_at = datetime('now')
           WHERE gate_id = ? AND finding_num = ? AND visibility = 'presented'""",
        (disposition, gate_id, finding_num),
    )
    updated = cursor.rowcount

    output_module.emit(
        {
            "updated": updated,
            "gate_id": gate_id,
            "finding_num": finding_num,
            "disposition": disposition,
        }
    )
    return updated
