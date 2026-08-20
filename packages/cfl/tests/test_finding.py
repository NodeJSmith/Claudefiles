"""Tests for cfl.finding — challenge/review finding tracking."""

import json

import pytest

from cfl.finding import (
    KNOWN_SEVERITIES,
    VALID_DESIGN_LEVELS,
    VALID_DISPOSITIONS,
    VALID_VISIBILITIES,
    list_findings,
    record_finding,
    record_finding_batch,
    resolve_finding,
)
from cfl.gate import record_gate
from tests.helpers import REMOTE_URL, insert_spec_with_run

# ---------------------------------------------------------------------------
# record_finding — happy path
# ---------------------------------------------------------------------------


def test_record_finding_creates_row_with_all_columns(db_conn, capsys):
    """record_finding inserts a findings row with every column populated."""
    _, run_id = insert_spec_with_run(db_conn, 1, "my-feature", REMOTE_URL)
    record_gate(db_conn, run_id, "sketch-challenge", verdict="FAIL")
    gate_id = json.loads(capsys.readouterr().out)["gate_id"]

    record_finding(
        db_conn,
        run_id,
        gate_id,
        "challenge",
        1,
        title="Missing timeout",
        severity="HIGH",
        visibility="presented",
        target="design.md",
        finding_type="reliability",
        design_level="Yes",
        raised_by="critic-1",
        classification="User-directed",
        disposition="pending",
        why_it_matters="Calls can hang forever",
    )

    row = db_conn.execute(
        "SELECT * FROM findings WHERE run_id=? AND finding_num=1", (run_id,)
    ).fetchone()
    assert row is not None
    assert row["gate_id"] == gate_id
    assert row["source"] == "challenge"
    assert row["title"] == "Missing timeout"
    assert row["target"] == "design.md"
    assert row["severity"] == "HIGH"
    assert row["finding_type"] == "reliability"
    assert row["design_level"] == "Yes"
    assert row["raised_by"] == "critic-1"
    assert row["classification"] == "User-directed"
    assert row["visibility"] == "presented"
    assert row["disposition"] == "pending"
    assert row["why_it_matters"] == "Calls can hang forever"
    assert row["created_at"] is not None


def test_record_finding_outputs_json_with_finding_id(db_conn, capsys):
    """record_finding emits JSON with finding_id, run_id, gate_id, source, finding_num."""
    _, run_id = insert_spec_with_run(db_conn, 1, "my-feature", REMOTE_URL)
    record_gate(db_conn, run_id, "sketch-challenge", verdict="FAIL")
    gate_id = json.loads(capsys.readouterr().out)["gate_id"]

    record_finding(
        db_conn,
        run_id,
        gate_id,
        "challenge",
        1,
        title="Missing timeout",
        severity="HIGH",
        visibility="presented",
    )

    out = json.loads(capsys.readouterr().out)
    assert "finding_id" in out
    assert isinstance(out["finding_id"], int)
    assert out["run_id"] == run_id
    assert out["gate_id"] == gate_id
    assert out["source"] == "challenge"
    assert out["finding_num"] == 1


def test_record_finding_gate_id_links_to_gate_row(db_conn, capsys):
    """A finding's gate_id resolves to a real row in gates."""
    _, run_id = insert_spec_with_run(db_conn, 1, "my-feature", REMOTE_URL)
    record_gate(db_conn, run_id, "ship-challenge", verdict="FAIL")
    gate_id = json.loads(capsys.readouterr().out)["gate_id"]

    record_finding(
        db_conn,
        run_id,
        gate_id,
        "challenge",
        1,
        title="Missing timeout",
        severity="HIGH",
        visibility="presented",
    )

    row = db_conn.execute(
        "SELECT g.gate_type FROM findings f JOIN gates g ON f.gate_id = g.id"
        " WHERE f.run_id=?",
        (run_id,),
    ).fetchone()
    assert row["gate_type"] == "ship-challenge"


def test_record_finding_run_id_none_writes_successfully(db_conn, capsys):
    """A finding recorded outside an active run (run_id=None) still writes."""
    record_finding(
        db_conn,
        None,
        None,
        "challenge",
        1,
        title="Missing timeout",
        severity="HIGH",
        visibility="presented",
    )

    row = db_conn.execute(
        "SELECT run_id, gate_id FROM findings WHERE title='Missing timeout'"
    ).fetchone()
    assert row is not None
    assert row["run_id"] is None
    assert row["gate_id"] is None


# ---------------------------------------------------------------------------
# Open-vocabulary validation — severity warns but still writes
# ---------------------------------------------------------------------------


def test_record_finding_unknown_severity_warns_stderr(db_conn, capsys):
    """record_finding emits a warning to stderr for unknown severity."""
    _, run_id = insert_spec_with_run(db_conn, 1, "my-feature", REMOTE_URL)

    record_finding(
        db_conn,
        run_id,
        None,
        "challenge",
        1,
        title="Style nit",
        severity="LOW",
        visibility="presented",
    )

    captured = capsys.readouterr()
    assert "unknown_severity" in captured.err


def test_record_finding_unknown_severity_still_writes_row(db_conn, capsys):
    """record_finding writes the row even when severity is unknown."""
    _, run_id = insert_spec_with_run(db_conn, 1, "my-feature", REMOTE_URL)

    record_finding(
        db_conn,
        run_id,
        None,
        "challenge",
        1,
        title="Style nit",
        severity="LOW",
        visibility="presented",
    )

    row = db_conn.execute(
        "SELECT severity FROM findings WHERE run_id=? AND title='Style nit'",
        (run_id,),
    ).fetchone()
    assert row is not None
    assert row["severity"] == "LOW"


# ---------------------------------------------------------------------------
# Closed-vocabulary validation — exit 2, write nothing
# ---------------------------------------------------------------------------


def test_record_finding_invalid_visibility_exits_2_and_writes_nothing(db_conn, capsys):
    """record_finding exits 2 for invalid visibility and does not write a row."""
    _, run_id = insert_spec_with_run(db_conn, 1, "my-feature", REMOTE_URL)

    with pytest.raises(SystemExit) as exc_info:
        record_finding(
            db_conn,
            run_id,
            None,
            "challenge",
            1,
            title="Missing timeout",
            severity="HIGH",
            visibility="bogus",
        )
    assert exc_info.value.code == 2

    err = json.loads(capsys.readouterr().err)
    assert err["code"] == "invalid_visibility"

    count = db_conn.execute(
        "SELECT COUNT(*) AS cnt FROM findings WHERE run_id=?", (run_id,)
    ).fetchone()["cnt"]
    assert count == 0


def test_record_finding_invalid_disposition_exits_2_and_writes_nothing(db_conn, capsys):
    """record_finding exits 2 for invalid disposition and does not write a row."""
    _, run_id = insert_spec_with_run(db_conn, 1, "my-feature", REMOTE_URL)

    with pytest.raises(SystemExit) as exc_info:
        record_finding(
            db_conn,
            run_id,
            None,
            "challenge",
            1,
            title="Missing timeout",
            severity="HIGH",
            visibility="presented",
            disposition="punted",
        )
    assert exc_info.value.code == 2

    err = json.loads(capsys.readouterr().err)
    assert err["code"] == "invalid_disposition"

    count = db_conn.execute(
        "SELECT COUNT(*) AS cnt FROM findings WHERE run_id=?", (run_id,)
    ).fetchone()["cnt"]
    assert count == 0


def test_record_finding_invalid_design_level_exits_2_and_writes_nothing(
    db_conn, capsys
):
    """record_finding exits 2 for invalid design_level and does not write a row."""
    _, run_id = insert_spec_with_run(db_conn, 1, "my-feature", REMOTE_URL)

    with pytest.raises(SystemExit) as exc_info:
        record_finding(
            db_conn,
            run_id,
            None,
            "challenge",
            1,
            title="Missing timeout",
            severity="HIGH",
            visibility="presented",
            design_level="Maybe",
        )
    assert exc_info.value.code == 2

    err = json.loads(capsys.readouterr().err)
    assert err["code"] == "invalid_design_level"

    count = db_conn.execute(
        "SELECT COUNT(*) AS cnt FROM findings WHERE run_id=?", (run_id,)
    ).fetchone()["cnt"]
    assert count == 0


# ---------------------------------------------------------------------------
# list_findings
# ---------------------------------------------------------------------------


def test_list_findings_returns_recorded_rows(db_conn, capsys):
    """list_findings returns rows written by record_finding."""
    _, run_id = insert_spec_with_run(db_conn, 1, "my-feature", REMOTE_URL)

    record_finding(
        db_conn,
        run_id,
        None,
        "challenge",
        1,
        title="Missing timeout",
        severity="HIGH",
        visibility="presented",
    )
    _ = capsys.readouterr()

    list_findings(db_conn)

    out = json.loads(capsys.readouterr().out)
    assert out["count"] == 1
    assert out["findings"][0]["title"] == "Missing timeout"


def test_list_findings_filter_by_source(db_conn, capsys):
    """list_findings filters by source."""
    _, run_id = insert_spec_with_run(db_conn, 1, "my-feature", REMOTE_URL)

    record_finding(
        db_conn,
        run_id,
        None,
        "challenge",
        1,
        title="Missing timeout",
        severity="HIGH",
        visibility="presented",
    )
    _ = capsys.readouterr()
    record_finding(
        db_conn,
        run_id,
        None,
        "code-reviewer",
        1,
        title="Unused import",
        severity="LOW",
        visibility="presented",
    )
    _ = capsys.readouterr()

    list_findings(db_conn, source="code-reviewer")

    out = json.loads(capsys.readouterr().out)
    assert out["count"] == 1
    assert out["findings"][0]["source"] == "code-reviewer"


def test_list_findings_filter_by_severity(db_conn, capsys):
    """list_findings filters by severity."""
    _, run_id = insert_spec_with_run(db_conn, 1, "my-feature", REMOTE_URL)

    record_finding(
        db_conn,
        run_id,
        None,
        "challenge",
        1,
        title="Missing timeout",
        severity="HIGH",
        visibility="presented",
    )
    _ = capsys.readouterr()
    record_finding(
        db_conn,
        run_id,
        None,
        "challenge",
        2,
        title="Naming nit",
        severity="TENSION",
        visibility="presented",
    )
    _ = capsys.readouterr()

    list_findings(db_conn, severity="TENSION")

    out = json.loads(capsys.readouterr().out)
    assert out["count"] == 1
    assert out["findings"][0]["title"] == "Naming nit"


def test_list_findings_filter_by_gate_id(db_conn, capsys):
    """list_findings filters by gate_id."""
    _, run_id = insert_spec_with_run(db_conn, 1, "my-feature", REMOTE_URL)
    record_gate(db_conn, run_id, "sketch-challenge", verdict="FAIL")
    gate_id_1 = json.loads(capsys.readouterr().out)["gate_id"]
    record_gate(db_conn, run_id, "ship-challenge", verdict="FAIL")
    gate_id_2 = json.loads(capsys.readouterr().out)["gate_id"]

    record_finding(
        db_conn,
        run_id,
        gate_id_1,
        "challenge",
        1,
        title="Sketch-time finding",
        severity="HIGH",
        visibility="presented",
    )
    _ = capsys.readouterr()
    record_finding(
        db_conn,
        run_id,
        gate_id_2,
        "challenge",
        1,
        title="Ship-time finding",
        severity="HIGH",
        visibility="presented",
    )
    _ = capsys.readouterr()

    list_findings(db_conn, gate_id=gate_id_2)

    out = json.loads(capsys.readouterr().out)
    assert out["count"] == 1
    assert out["findings"][0]["title"] == "Ship-time finding"


def test_list_findings_negative_limit_exits_2(db_conn, capsys):
    """list_findings exits 2 for a negative limit (SQLite treats it as unlimited)."""
    with pytest.raises(SystemExit) as exc_info:
        list_findings(db_conn, limit=-1)
    assert exc_info.value.code == 2

    err = json.loads(capsys.readouterr().err)
    assert err["code"] == "invalid_limit"


# ---------------------------------------------------------------------------
# resolve_finding
# ---------------------------------------------------------------------------


def test_resolve_finding_updates_disposition_and_stamps_resolved_at(db_conn, capsys):
    """resolve_finding updates disposition and sets resolved_at for a presented finding."""
    _, run_id = insert_spec_with_run(db_conn, 1, "my-feature", REMOTE_URL)
    record_gate(db_conn, run_id, "sketch-challenge", verdict="FAIL")
    gate_id = json.loads(capsys.readouterr().out)["gate_id"]
    record_finding(
        db_conn,
        run_id,
        gate_id,
        "challenge",
        1,
        title="Missing timeout",
        severity="HIGH",
        visibility="presented",
        disposition="pending",
    )
    _ = capsys.readouterr()

    updated = resolve_finding(db_conn, gate_id, 1, "applied")

    assert updated == 1
    row = db_conn.execute(
        "SELECT disposition, resolved_at FROM findings WHERE gate_id=? AND finding_num=1",
        (gate_id,),
    ).fetchone()
    assert row["disposition"] == "applied"
    assert row["resolved_at"] is not None


def test_resolve_finding_returns_0_for_missing_finding_num(db_conn, capsys):
    """resolve_finding returns 0 when no finding matches gate_id/finding_num."""
    _, run_id = insert_spec_with_run(db_conn, 1, "my-feature", REMOTE_URL)
    record_gate(db_conn, run_id, "sketch-challenge", verdict="FAIL")
    gate_id = json.loads(capsys.readouterr().out)["gate_id"]

    updated = resolve_finding(db_conn, gate_id, 99, "applied")

    assert updated == 0


def test_resolve_finding_does_not_resolve_likely_invalid(db_conn, capsys):
    """resolve_finding refuses to touch a likely-invalid finding."""
    _, run_id = insert_spec_with_run(db_conn, 1, "my-feature", REMOTE_URL)
    record_gate(db_conn, run_id, "sketch-challenge", verdict="FAIL")
    gate_id = json.loads(capsys.readouterr().out)["gate_id"]
    record_finding(
        db_conn,
        run_id,
        gate_id,
        "challenge",
        1,
        title="Likely false positive",
        severity="MEDIUM",
        visibility="likely-invalid",
    )
    _ = capsys.readouterr()

    updated = resolve_finding(db_conn, gate_id, 1, "applied")

    assert updated == 0
    row = db_conn.execute(
        "SELECT disposition FROM findings WHERE gate_id=? AND finding_num=1", (gate_id,)
    ).fetchone()
    assert row["disposition"] is None


def test_resolve_finding_invalid_disposition_exits_2(db_conn, capsys):
    """resolve_finding exits 2 for an unknown disposition."""
    _, run_id = insert_spec_with_run(db_conn, 1, "my-feature", REMOTE_URL)
    record_gate(db_conn, run_id, "sketch-challenge", verdict="FAIL")
    gate_id = json.loads(capsys.readouterr().out)["gate_id"]

    with pytest.raises(SystemExit) as exc_info:
        resolve_finding(db_conn, gate_id, 1, "punted")
    assert exc_info.value.code == 2

    err = json.loads(capsys.readouterr().err)
    assert err["code"] == "invalid_disposition"


# ---------------------------------------------------------------------------
# record_finding_batch
# ---------------------------------------------------------------------------


def test_record_finding_batch_writes_all_rows_in_one_transaction(
    db_conn, capsys, tmp_path
):
    """record_finding_batch writes every finding from the JSON file."""
    _, run_id = insert_spec_with_run(db_conn, 1, "my-feature", REMOTE_URL)
    record_gate(db_conn, run_id, "ship-challenge", verdict="FAIL")
    gate_id = json.loads(capsys.readouterr().out)["gate_id"]

    findings_file = tmp_path / "findings.json"
    findings_file.write_text(
        json.dumps(
            [
                {
                    "finding_num": 1,
                    "title": "Missing timeout",
                    "severity": "HIGH",
                    "visibility": "presented",
                    "disposition": "pending",
                },
                {
                    "finding_num": 2,
                    "title": "Naming nit",
                    "severity": "TENSION",
                    "visibility": "presented",
                    "disposition": "pending",
                },
                {
                    "finding_num": 2,
                    "title": "Naming nit (LI)",
                    "severity": "TENSION",
                    "visibility": "likely-invalid",
                },
            ]
        )
    )

    written = record_finding_batch(
        db_conn, gate_id, str(findings_file), source="challenge", run_id=run_id
    )

    assert written == 3
    count = db_conn.execute(
        "SELECT COUNT(*) AS cnt FROM findings WHERE gate_id=?", (gate_id,)
    ).fetchone()["cnt"]
    assert count == 3

    out = json.loads(capsys.readouterr().out)
    assert out["batch_size"] == 3
    assert out["gate_id"] == gate_id
    assert out["source"] == "challenge"


def test_record_finding_batch_rolls_back_on_validation_error(db_conn, capsys, tmp_path):
    """record_finding_batch writes nothing if any finding fails validation."""
    _, run_id = insert_spec_with_run(db_conn, 1, "my-feature", REMOTE_URL)
    record_gate(db_conn, run_id, "ship-challenge", verdict="FAIL")
    gate_id = json.loads(capsys.readouterr().out)["gate_id"]

    findings_file = tmp_path / "findings.json"
    findings_file.write_text(
        json.dumps(
            [
                {
                    "finding_num": 1,
                    "title": "Missing timeout",
                    "severity": "HIGH",
                    "visibility": "presented",
                },
                {
                    "finding_num": 2,
                    "title": "Bad visibility",
                    "severity": "HIGH",
                    "visibility": "bogus",
                },
            ]
        )
    )

    with pytest.raises(SystemExit) as exc_info:
        record_finding_batch(
            db_conn, gate_id, str(findings_file), source="challenge", run_id=run_id
        )
    assert exc_info.value.code == 2

    err = json.loads(capsys.readouterr().err)
    assert err["code"] == "invalid_visibility"

    count = db_conn.execute(
        "SELECT COUNT(*) AS cnt FROM findings WHERE gate_id=?", (gate_id,)
    ).fetchone()["cnt"]
    assert count == 0


def test_record_finding_batch_missing_file_exits_2(db_conn, capsys, tmp_path):
    """record_finding_batch exits 2 with invalid_findings_file for a missing path."""
    _, run_id = insert_spec_with_run(db_conn, 1, "my-feature", REMOTE_URL)
    record_gate(db_conn, run_id, "ship-challenge", verdict="FAIL")
    gate_id = json.loads(capsys.readouterr().out)["gate_id"]

    missing_file = tmp_path / "does-not-exist.json"

    with pytest.raises(SystemExit) as exc_info:
        record_finding_batch(
            db_conn, gate_id, str(missing_file), source="challenge", run_id=run_id
        )
    assert exc_info.value.code == 2

    err = json.loads(capsys.readouterr().err)
    assert err["code"] == "invalid_findings_file"

    count = db_conn.execute(
        "SELECT COUNT(*) AS cnt FROM findings WHERE gate_id=?", (gate_id,)
    ).fetchone()["cnt"]
    assert count == 0


def test_record_finding_batch_malformed_json_exits_2(db_conn, capsys, tmp_path):
    """record_finding_batch exits 2 with invalid_findings_file for malformed JSON."""
    _, run_id = insert_spec_with_run(db_conn, 1, "my-feature", REMOTE_URL)
    record_gate(db_conn, run_id, "ship-challenge", verdict="FAIL")
    gate_id = json.loads(capsys.readouterr().out)["gate_id"]

    findings_file = tmp_path / "findings.json"
    findings_file.write_text("{not valid json")

    with pytest.raises(SystemExit) as exc_info:
        record_finding_batch(
            db_conn, gate_id, str(findings_file), source="challenge", run_id=run_id
        )
    assert exc_info.value.code == 2

    err = json.loads(capsys.readouterr().err)
    assert err["code"] == "invalid_findings_file"

    count = db_conn.execute(
        "SELECT COUNT(*) AS cnt FROM findings WHERE gate_id=?", (gate_id,)
    ).fetchone()["cnt"]
    assert count == 0


def test_record_finding_batch_non_dict_element_exits_2(db_conn, capsys, tmp_path):
    """record_finding_batch exits 2 with invalid_findings_file for a non-dict array element."""
    _, run_id = insert_spec_with_run(db_conn, 1, "my-feature", REMOTE_URL)
    record_gate(db_conn, run_id, "ship-challenge", verdict="FAIL")
    gate_id = json.loads(capsys.readouterr().out)["gate_id"]

    findings_file = tmp_path / "findings.json"
    findings_file.write_text(json.dumps(["not-a-dict"]))

    with pytest.raises(SystemExit) as exc_info:
        record_finding_batch(
            db_conn, gate_id, str(findings_file), source="challenge", run_id=run_id
        )
    assert exc_info.value.code == 2

    err = json.loads(capsys.readouterr().err)
    assert err["code"] == "invalid_findings_file"

    count = db_conn.execute(
        "SELECT COUNT(*) AS cnt FROM findings WHERE gate_id=?", (gate_id,)
    ).fetchone()["cnt"]
    assert count == 0


def test_record_finding_batch_missing_required_field_exits_2(db_conn, capsys, tmp_path):
    """record_finding_batch exits 2 with invalid_findings_file when a finding lacks required fields."""
    _, run_id = insert_spec_with_run(db_conn, 1, "my-feature", REMOTE_URL)
    record_gate(db_conn, run_id, "ship-challenge", verdict="FAIL")
    gate_id = json.loads(capsys.readouterr().out)["gate_id"]

    findings_file = tmp_path / "findings.json"
    findings_file.write_text(
        json.dumps([{"severity": "HIGH", "visibility": "presented"}])
    )

    with pytest.raises(SystemExit) as exc_info:
        record_finding_batch(
            db_conn, gate_id, str(findings_file), source="challenge", run_id=run_id
        )
    assert exc_info.value.code == 2

    err = json.loads(capsys.readouterr().err)
    assert err["code"] == "invalid_findings_file"
    assert "finding_num" in err["error"]
    assert "title" in err["error"]

    count = db_conn.execute(
        "SELECT COUNT(*) AS cnt FROM findings WHERE gate_id=?", (gate_id,)
    ).fetchone()["cnt"]
    assert count == 0


def test_record_finding_batch_non_list_json_exits_2(db_conn, capsys, tmp_path):
    """record_finding_batch exits 2 with invalid_findings_file when JSON is not an array."""
    _, run_id = insert_spec_with_run(db_conn, 1, "my-feature", REMOTE_URL)
    record_gate(db_conn, run_id, "ship-challenge", verdict="FAIL")
    gate_id = json.loads(capsys.readouterr().out)["gate_id"]

    findings_file = tmp_path / "findings.json"
    findings_file.write_text(json.dumps({"title": "not an array"}))

    with pytest.raises(SystemExit) as exc_info:
        record_finding_batch(
            db_conn, gate_id, str(findings_file), source="challenge", run_id=run_id
        )
    assert exc_info.value.code == 2

    err = json.loads(capsys.readouterr().err)
    assert err["code"] == "invalid_findings_file"

    count = db_conn.execute(
        "SELECT COUNT(*) AS cnt FROM findings WHERE gate_id=?", (gate_id,)
    ).fetchone()["cnt"]
    assert count == 0


# ---------------------------------------------------------------------------
# Vocabulary constants are exported
# ---------------------------------------------------------------------------


def test_known_severities_exported():
    """KNOWN_SEVERITIES matches challenge's severity taxonomy."""
    assert KNOWN_SEVERITIES == frozenset({"CRITICAL", "HIGH", "MEDIUM", "TENSION"})


def test_valid_visibilities_exported():
    """VALID_VISIBILITIES contains the three synthesis-time filtering values."""
    assert VALID_VISIBILITIES == frozenset({"presented", "overflow", "likely-invalid"})


def test_valid_dispositions_exported():
    """VALID_DISPOSITIONS contains the four resolution-time outcome values."""
    assert VALID_DISPOSITIONS == frozenset({"pending", "applied", "skipped", "filed"})


def test_valid_design_levels_exported():
    """VALID_DESIGN_LEVELS is Yes/No."""
    assert VALID_DESIGN_LEVELS == frozenset({"Yes", "No"})
