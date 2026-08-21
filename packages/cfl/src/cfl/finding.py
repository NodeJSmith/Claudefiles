"""Challenge/review finding tracking for cfl.

Records design-level and code-level findings raised by challenge (and, in
future, other producers — see `source`) across mine-define, mine-sketch, and
mine-orchestrate runs. Models on `question.py`: findings are leaf telemetry,
so `record_finding` emits no implicit event the way `record_gate` does.

`severity`, `source`, and `classification` are open vocabulary — each is a
producer's own taxonomy (challenge's CRITICAL/HIGH/MEDIUM/TENSION severities,
`"challenge"` as the sole source today, Auto-apply/User-directed
classifications), so unknown values warn but still write, with no DDL
`CHECK` — matching the same warn-but-write pattern `gate.py`'s
`KNOWN_GATE_TYPES` and `question.py`'s `KNOWN_SKILLS`/`KNOWN_TOPICS` use.
`visibility`, `disposition`, and `design_level` are cfl's own vocabulary —
closed, DDL-`CHECK`ed, and rejected outright on an unknown value.
`finding_type` remains unconstrained free text with no frozenset — it has no
stable taxonomy yet across producers.
"""

import json
import sqlite3

import cfl.output as output_module
from cfl.session import read_context_pct

KNOWN_SEVERITIES: frozenset[str] = frozenset({"CRITICAL", "HIGH", "MEDIUM", "TENSION"})

KNOWN_SOURCES: frozenset[str] = frozenset({"challenge"})

KNOWN_CLASSIFICATIONS: frozenset[str] = frozenset({"Auto-apply", "User-directed"})

VALID_VISIBILITIES: frozenset[str] = frozenset(
    {"presented", "overflow", "likely-invalid"}
)

VALID_FINDING_DISPOSITIONS: frozenset[str] = frozenset(
    {"pending", "applied", "skipped", "filed"}
)

# Dispositions resolve_finding() may set. Excludes "pending" — a finding
# starts pending and resolve_finding() moves it to a terminal state; there
# is no resolution outcome that means "still pending".
TERMINAL_FINDING_DISPOSITIONS: frozenset[str] = frozenset(
    {"applied", "skipped", "filed"}
)

VALID_DESIGN_LEVELS: frozenset[str] = frozenset({"Yes", "No"})

REQUIRED_BATCH_FIELDS: tuple[str, ...] = (
    "finding_num",
    "title",
    "severity",
    "visibility",
    "raised_by",
)

# Required only for main findings (visibility 'presented' or 'overflow'), not
# for 'likely-invalid' entries — the Likely Invalid section's template
# (findings-protocol.md) carries no Type/Design-level/Classification/
# Why-it-matters fields, so these would legitimately be absent there.
MAIN_FINDING_REQUIRED_FIELDS: tuple[str, ...] = (
    "finding_type",
    "design_level",
    "classification",
    "why_it_matters",
)

_INSERT_FINDING_SQL = """INSERT INTO findings
         (run_id, gate_id, source, finding_num, title, target, severity,
          finding_type, design_level, raised_by, classification, visibility,
          disposition, why_it_matters, context_pct, created_at)
       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))"""


def default_finding_disposition(
    visibility: str | None, disposition: str | None
) -> str | None:
    """Default an omitted disposition to 'pending' for a presented finding.

    Only 'presented' findings enter the resolution flow (see
    resolve_finding()'s pending-only guard); 'overflow' and 'likely-invalid'
    findings never do, so an omitted disposition stays NULL for those. An
    explicit disposition (including an explicit 'pending') always wins. Not
    to be confused with resolve_finding(), which transitions an existing
    pending row to a terminal disposition — this function only fills in a
    missing value at write time.
    """
    if disposition is None and visibility == "presented":
        return "pending"
    return disposition


def validate_finding_fields(
    severity: str | None,
    visibility: str | None,
    disposition: str | None,
    design_level: str | None,
    source: str | None = None,
    classification: str | None = None,
) -> None:
    """Validate one finding's severity/visibility/disposition/design_level/source/classification.

    Shared by record_finding and record_finding_batch so the six tiers of
    validation are defined once. Warns for unknown severity, source, or
    classification but still returns. Exits 2 for invalid visibility,
    disposition, or design_level.
    """
    if severity not in KNOWN_SEVERITIES:
        output_module.emit_warning(
            f"Unknown severity '{severity}'. Known: {sorted(KNOWN_SEVERITIES)}",
            code="unknown_severity",
        )

    if source is not None and source not in KNOWN_SOURCES:
        output_module.emit_warning(
            f"Unknown source '{source}'. Known: {sorted(KNOWN_SOURCES)}",
            code="unknown_source",
        )

    if classification is not None and classification not in KNOWN_CLASSIFICATIONS:
        output_module.emit_warning(
            f"Unknown classification '{classification}'."
            f" Known: {sorted(KNOWN_CLASSIFICATIONS)}",
            code="unknown_classification",
        )

    if visibility not in VALID_VISIBILITIES:
        output_module.emit_error(
            f"Unknown visibility '{visibility}'."
            f" Use: {', '.join(sorted(VALID_VISIBILITIES))}.",
            code="invalid_visibility",
            exit_code=2,
        )

    if disposition is not None and disposition not in VALID_FINDING_DISPOSITIONS:
        output_module.emit_error(
            f"Unknown disposition '{disposition}'."
            f" Use: {', '.join(sorted(VALID_FINDING_DISPOSITIONS))}.",
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

    Warns for unknown severity, source, or classification but still writes.
    Exits 2 for invalid visibility, invalid disposition, or invalid design_level.
    An omitted disposition defaults to 'pending' for a 'presented' finding —
    see default_finding_disposition().
    """
    disposition = default_finding_disposition(visibility, disposition)

    validate_finding_fields(
        severity,
        visibility,
        disposition,
        design_level,
        source=source,
        classification=classification,
    )

    context_pct = read_context_pct()

    cursor = conn.execute(
        _INSERT_FINDING_SQL,
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
    batch (exit 2) with no partial writes. An omitted disposition defaults to
    'pending' for a 'presented' finding, same as record_finding — see
    default_finding_disposition(). Returns the number of rows written.

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

    resolved_dispositions: list[str | None] = []
    for finding in findings:
        if not isinstance(finding, dict):
            output_module.emit_error(
                f"Each finding must be a JSON object, got {type(finding).__name__}",
                code="invalid_findings_file",
                exit_code=2,
            )

        required_fields = REQUIRED_BATCH_FIELDS
        if finding.get("visibility") != "likely-invalid":
            required_fields = REQUIRED_BATCH_FIELDS + MAIN_FINDING_REQUIRED_FIELDS

        missing = [field for field in required_fields if finding.get(field) is None]
        if missing:
            output_module.emit_error(
                f"Finding is missing required field(s): {', '.join(missing)}",
                code="invalid_findings_file",
                exit_code=2,
            )

        disposition = default_finding_disposition(
            finding.get("visibility"), finding.get("disposition")
        )
        validate_finding_fields(
            finding.get("severity"),
            finding.get("visibility"),
            disposition,
            finding.get("design_level"),
            source=source,
            classification=finding.get("classification"),
        )
        resolved_dispositions.append(disposition)

    context_pct = read_context_pct()

    conn.execute("BEGIN IMMEDIATE")
    try:
        for finding, disposition in zip(findings, resolved_dispositions, strict=True):
            conn.execute(
                _INSERT_FINDING_SQL,
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
                    disposition,
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
    """Move a presented, pending finding to a terminal disposition and stamp
    resolved_at.

    Exits 2 for a non-terminal disposition (including "pending" — a finding
    starts pending; there is no resolution outcome that means "still
    pending").
    The `visibility = 'presented'` and `disposition = 'pending'` guards mean
    an overflow/likely-invalid finding, or one already resolved, is never
    touched — a retry or a stray re-resolve can't clobber the first
    resolved_at. Returns the updated row count (0 or 1) so the caller can
    detect a finding_num with no matching pending-presented row.
    """
    if disposition not in TERMINAL_FINDING_DISPOSITIONS:
        output_module.emit_error(
            f"Unknown disposition '{disposition}'."
            f" Use: {', '.join(sorted(TERMINAL_FINDING_DISPOSITIONS))}.",
            code="invalid_disposition",
            exit_code=2,
        )

    cursor = conn.execute(
        """UPDATE findings SET disposition = ?, resolved_at = datetime('now')
           WHERE gate_id = ? AND finding_num = ? AND visibility = 'presented'
             AND disposition = 'pending'""",
        (disposition, gate_id, finding_num),
    )
    updated = cursor.rowcount

    resolved_at = None
    if updated:
        row = conn.execute(
            "SELECT resolved_at FROM findings"
            " WHERE gate_id = ? AND finding_num = ? AND visibility = 'presented'",
            (gate_id, finding_num),
        ).fetchone()
        resolved_at = row[0] if row else None

    output_module.emit(
        {
            "updated": updated,
            "gate_id": gate_id,
            "finding_num": finding_num,
            "disposition": disposition,
            "resolved_at": resolved_at,
        }
    )
    return updated
