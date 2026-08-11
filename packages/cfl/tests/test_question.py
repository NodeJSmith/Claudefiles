"""Tests for cfl.question — discovery question tracking."""

import json
import sqlite3

import pytest

from cfl.question import (
    KNOWN_SKILLS,
    KNOWN_TOPICS,
    VALID_DISPOSITIONS,
    VALID_STATUSES,
    list_questions,
    record_question,
)
from tests.helpers import REMOTE_URL, insert_spec_with_run

# ---------------------------------------------------------------------------
# record_question — happy path
# ---------------------------------------------------------------------------


def test_record_question_creates_row(db_conn, capsys):
    """record_question inserts a questions row with all fields."""
    _, run_id = insert_spec_with_run(db_conn, 1, "my-feature", REMOTE_URL)

    record_question(
        db_conn,
        run_id,
        "mine-define",
        "scope-mode",
        status="asked",
        answer="Hold — make this bulletproof",
    )

    row = db_conn.execute(
        "SELECT * FROM questions WHERE run_id=? AND topic='scope-mode'",
        (run_id,),
    ).fetchone()
    assert row is not None
    assert row["skill"] == "mine-define"
    assert row["topic"] == "scope-mode"
    assert row["status"] == "asked"
    assert row["answer"] == "Hold — make this bulletproof"


def test_record_question_outputs_json(db_conn, capsys):
    """record_question emits JSON with question_id, run_id, skill, topic, status."""
    _, run_id = insert_spec_with_run(db_conn, 1, "my-feature", REMOTE_URL)

    record_question(db_conn, run_id, "mine-define", "success", status="asked")

    out = json.loads(capsys.readouterr().out)
    assert "question_id" in out
    assert isinstance(out["question_id"], int)
    assert out["run_id"] == run_id
    assert out["skill"] == "mine-define"
    assert out["topic"] == "success"
    assert out["status"] == "asked"


def test_record_question_skipped_with_no_answer(db_conn, capsys):
    """record_question stores skipped questions with answer=NULL."""
    _, run_id = insert_spec_with_run(db_conn, 1, "my-feature", REMOTE_URL)

    record_question(db_conn, run_id, "mine-define", "edge-cases", status="skipped")

    row = db_conn.execute(
        "SELECT answer FROM questions WHERE run_id=? AND topic='edge-cases'",
        (run_id,),
    ).fetchone()
    assert row["answer"] is None


def test_record_question_multiple_per_run(db_conn, capsys):
    """Multiple questions can be recorded for the same run."""
    _, run_id = insert_spec_with_run(db_conn, 1, "my-feature", REMOTE_URL)

    record_question(db_conn, run_id, "mine-define", "success", status="asked")
    _ = capsys.readouterr()
    record_question(db_conn, run_id, "mine-define", "success", status="asked")
    _ = capsys.readouterr()
    record_question(db_conn, run_id, "mine-define", "edge-cases", status="skipped")

    count = db_conn.execute(
        "SELECT COUNT(*) AS cnt FROM questions WHERE run_id=?",
        (run_id,),
    ).fetchone()["cnt"]
    assert count == 3


# ---------------------------------------------------------------------------
# Vocabulary validation — warn but still write
# ---------------------------------------------------------------------------


def test_record_question_unknown_skill_warns(db_conn, capsys):
    """record_question emits a warning for unknown skill but still writes."""
    _, run_id = insert_spec_with_run(db_conn, 1, "my-feature", REMOTE_URL)

    record_question(db_conn, run_id, "unknown-skill", "success", status="asked")

    captured = capsys.readouterr()
    assert "unknown_skill" in captured.err
    row = db_conn.execute(
        "SELECT skill FROM questions WHERE run_id=? AND skill='unknown-skill'",
        (run_id,),
    ).fetchone()
    assert row is not None


def test_record_question_unknown_topic_warns(db_conn, capsys):
    """record_question emits a warning for unknown topic but still writes."""
    _, run_id = insert_spec_with_run(db_conn, 1, "my-feature", REMOTE_URL)

    record_question(db_conn, run_id, "mine-define", "unknown-topic", status="asked")

    captured = capsys.readouterr()
    assert "unknown_topic" in captured.err
    row = db_conn.execute(
        "SELECT topic FROM questions WHERE run_id=? AND topic='unknown-topic'",
        (run_id,),
    ).fetchone()
    assert row is not None


# ---------------------------------------------------------------------------
# Invalid status — exit 2
# ---------------------------------------------------------------------------


def test_record_question_invalid_status_exits_2(db_conn, capsys):
    """record_question exits 2 for unknown status strings."""
    _, run_id = insert_spec_with_run(db_conn, 1, "my-feature", REMOTE_URL)

    with pytest.raises(SystemExit) as exc_info:
        record_question(db_conn, run_id, "mine-define", "success", status="answered")
    assert exc_info.value.code == 2

    err = json.loads(capsys.readouterr().err)
    assert err["code"] == "invalid_status"


def test_record_question_all_valid_statuses_accepted(db_conn, capsys):
    """Both 'asked' and 'skipped' are accepted."""
    _, run_id = insert_spec_with_run(db_conn, 1, "my-feature", REMOTE_URL)

    for status in sorted(VALID_STATUSES):
        record_question(db_conn, run_id, "mine-define", "success", status=status)
        _ = capsys.readouterr()


# ---------------------------------------------------------------------------
# disposition
# ---------------------------------------------------------------------------


def test_record_question_stores_disposition(db_conn, capsys):
    """record_question persists disposition alongside status."""
    _, run_id = insert_spec_with_run(db_conn, 1, "my-feature", REMOTE_URL)

    record_question(
        db_conn,
        run_id,
        "mine-plan",
        "open-question",
        status="asked",
        answer="Defer to implementation",
        disposition="deferred",
    )

    row = db_conn.execute(
        "SELECT status, disposition FROM questions WHERE run_id=?", (run_id,)
    ).fetchone()
    assert row["status"] == "asked"
    assert row["disposition"] == "deferred"


def test_record_question_disposition_defaults_to_null(db_conn, capsys):
    """Questions recorded without a disposition store NULL, not a placeholder."""
    _, run_id = insert_spec_with_run(db_conn, 1, "my-feature", REMOTE_URL)

    record_question(db_conn, run_id, "mine-define", "success", status="asked")

    row = db_conn.execute(
        "SELECT disposition FROM questions WHERE run_id=?", (run_id,)
    ).fetchone()
    assert row["disposition"] is None


def test_record_question_emits_disposition(db_conn, capsys):
    """record_question includes disposition in its JSON output."""
    _, run_id = insert_spec_with_run(db_conn, 1, "my-feature", REMOTE_URL)

    record_question(
        db_conn,
        run_id,
        "mine-plan",
        "open-question",
        status="asked",
        disposition="accepted",
    )

    out = json.loads(capsys.readouterr().out)
    assert out["disposition"] == "accepted"


def test_record_question_all_valid_dispositions_accepted(db_conn, capsys):
    """Every declared disposition is writable."""
    _, run_id = insert_spec_with_run(db_conn, 1, "my-feature", REMOTE_URL)

    for disposition in sorted(VALID_DISPOSITIONS):
        record_question(
            db_conn,
            run_id,
            "mine-plan",
            "open-question",
            status="asked",
            disposition=disposition,
        )
        _ = capsys.readouterr()

    count = db_conn.execute(
        "SELECT COUNT(*) AS cnt FROM questions WHERE disposition IS NOT NULL"
    ).fetchone()["cnt"]
    assert count == len(VALID_DISPOSITIONS)


def test_record_question_invalid_disposition_exits_2(db_conn, capsys):
    """record_question exits 2 for an unknown disposition."""
    _, run_id = insert_spec_with_run(db_conn, 1, "my-feature", REMOTE_URL)

    with pytest.raises(SystemExit) as exc_info:
        record_question(
            db_conn,
            run_id,
            "mine-plan",
            "open-question",
            status="asked",
            disposition="punted",
        )
    assert exc_info.value.code == 2

    err = json.loads(capsys.readouterr().err)
    assert err["code"] == "invalid_disposition"


def test_record_question_disposition_on_skipped_exits_2(db_conn, capsys):
    """A skipped question was never asked, so it cannot carry a disposition."""
    _, run_id = insert_spec_with_run(db_conn, 1, "my-feature", REMOTE_URL)

    with pytest.raises(SystemExit) as exc_info:
        record_question(
            db_conn,
            run_id,
            "mine-define",
            "edge-cases",
            status="skipped",
            disposition="deferred",
        )
    assert exc_info.value.code == 2

    err = json.loads(capsys.readouterr().err)
    assert err["code"] == "disposition_without_ask"


def test_schema_rejects_disposition_on_skipped(db_conn):
    """The status/disposition invariant is enforced in SQL, not only in Python."""
    _, run_id = insert_spec_with_run(db_conn, 1, "my-feature", REMOTE_URL)

    with pytest.raises(sqlite3.IntegrityError):
        db_conn.execute(
            "INSERT INTO questions"
            " (run_id, skill, topic, status, disposition, created_at)"
            " VALUES (?, 'mine-plan', 'open-question', 'skipped', 'deferred',"
            " datetime('now'))",
            (run_id,),
        )


def test_schema_rejects_unknown_disposition(db_conn):
    """The disposition vocabulary is enforced in SQL, not only in Python."""
    _, run_id = insert_spec_with_run(db_conn, 1, "my-feature", REMOTE_URL)

    with pytest.raises(sqlite3.IntegrityError):
        db_conn.execute(
            "INSERT INTO questions"
            " (run_id, skill, topic, status, disposition, created_at)"
            " VALUES (?, 'mine-plan', 'open-question', 'asked', 'punted',"
            " datetime('now'))",
            (run_id,),
        )


# ---------------------------------------------------------------------------
# list_questions
# ---------------------------------------------------------------------------


def test_list_questions_returns_all(db_conn, capsys):
    """list_questions returns all questions when no filters applied."""
    _, run_id = insert_spec_with_run(db_conn, 1, "my-feature", REMOTE_URL)

    record_question(db_conn, run_id, "mine-define", "success", status="asked")
    _ = capsys.readouterr()
    record_question(db_conn, run_id, "mine-define", "success", status="asked")
    _ = capsys.readouterr()

    list_questions(db_conn)

    out = json.loads(capsys.readouterr().out)
    assert out["count"] == 2


def test_list_questions_filter_by_skill(db_conn, capsys):
    """list_questions filters by skill."""
    _, run_id = insert_spec_with_run(db_conn, 1, "my-feature", REMOTE_URL)

    record_question(db_conn, run_id, "mine-define", "success", status="asked")
    _ = capsys.readouterr()
    record_question(db_conn, run_id, "mine-grill", "pain-point", status="asked")
    _ = capsys.readouterr()

    list_questions(db_conn, skill="mine-grill")

    out = json.loads(capsys.readouterr().out)
    assert out["count"] == 1
    assert out["questions"][0]["skill"] == "mine-grill"


def test_list_questions_filter_by_status(db_conn, capsys):
    """list_questions filters by status."""
    _, run_id = insert_spec_with_run(db_conn, 1, "my-feature", REMOTE_URL)

    record_question(db_conn, run_id, "mine-define", "success", status="asked")
    _ = capsys.readouterr()
    record_question(db_conn, run_id, "mine-define", "edge-cases", status="skipped")
    _ = capsys.readouterr()

    list_questions(db_conn, status="skipped")

    out = json.loads(capsys.readouterr().out)
    assert out["count"] == 1
    assert out["questions"][0]["topic"] == "edge-cases"


def test_list_questions_filter_by_disposition(db_conn, capsys):
    """list_questions filters by disposition — the metric this column exists for."""
    _, run_id = insert_spec_with_run(db_conn, 1, "my-feature", REMOTE_URL)

    for disposition in ["resolved", "deferred", "accepted"]:
        record_question(
            db_conn,
            run_id,
            "mine-plan",
            "open-question",
            status="asked",
            disposition=disposition,
        )
        _ = capsys.readouterr()

    list_questions(db_conn, disposition="deferred")

    out = json.loads(capsys.readouterr().out)
    assert out["count"] == 1
    assert out["questions"][0]["disposition"] == "deferred"


def test_list_questions_status_asked_includes_dispositioned(db_conn, capsys):
    """Disposition is orthogonal — a deferred question still counts as asked."""
    _, run_id = insert_spec_with_run(db_conn, 1, "my-feature", REMOTE_URL)

    record_question(db_conn, run_id, "mine-define", "success", status="asked")
    _ = capsys.readouterr()
    record_question(
        db_conn,
        run_id,
        "mine-plan",
        "open-question",
        status="asked",
        disposition="deferred",
    )
    _ = capsys.readouterr()

    list_questions(db_conn, status="asked")

    out = json.loads(capsys.readouterr().out)
    assert out["count"] == 2


def test_disposition_count_counts_decisions_not_questions(db_conn, capsys):
    """A re-dispositioned question adds a row rather than replacing one.

    Topics are not per-question identifiers, so a count of `deferred` rows is a
    count of deferral decisions. mine-plan Phase 3 can revisit a Phase 1
    deferral, and both rows stand.
    """
    _, run_id = insert_spec_with_run(db_conn, 1, "my-feature", REMOTE_URL)

    record_question(
        db_conn,
        run_id,
        "mine-plan",
        "open-question",
        status="asked",
        disposition="deferred",
        answer="Defer to implementation",
    )
    _ = capsys.readouterr()
    record_question(
        db_conn,
        run_id,
        "mine-plan",
        "open-question",
        status="asked",
        disposition="accepted",
        answer="Unowned in Phase 3 — Accept it as a known risk",
    )
    _ = capsys.readouterr()

    list_questions(db_conn, topic="open-question")

    out = json.loads(capsys.readouterr().out)
    assert out["count"] == 2
    assert [q["disposition"] for q in out["questions"]] == ["accepted", "deferred"]


def test_list_questions_invalid_disposition_exits_2(db_conn, capsys):
    """list_questions exits 2 for an unknown disposition."""
    with pytest.raises(SystemExit) as exc_info:
        list_questions(db_conn, disposition="punted")
    assert exc_info.value.code == 2

    err = json.loads(capsys.readouterr().err)
    assert err["code"] == "invalid_disposition"


def test_list_questions_filter_by_topic(db_conn, capsys):
    """list_questions filters by topic."""
    _, run_id = insert_spec_with_run(db_conn, 1, "my-feature", REMOTE_URL)

    record_question(db_conn, run_id, "mine-define", "success", status="asked")
    _ = capsys.readouterr()
    record_question(db_conn, run_id, "mine-define", "scope-mode", status="asked")
    _ = capsys.readouterr()

    list_questions(db_conn, topic="scope-mode")

    out = json.loads(capsys.readouterr().out)
    assert out["count"] == 1
    assert out["questions"][0]["topic"] == "scope-mode"


def test_list_questions_respects_limit(db_conn, capsys):
    """list_questions honors the limit parameter."""
    _, run_id = insert_spec_with_run(db_conn, 1, "my-feature", REMOTE_URL)

    for topic in ["success", "scope-mode", "edge-cases"]:
        record_question(db_conn, run_id, "mine-define", topic, status="asked")
        _ = capsys.readouterr()

    list_questions(db_conn, limit=2)

    out = json.loads(capsys.readouterr().out)
    assert out["count"] == 2


# ---------------------------------------------------------------------------
# list_questions — invalid status / limit — exit 2
# ---------------------------------------------------------------------------


def test_list_questions_invalid_status_exits_2(db_conn, capsys):
    """list_questions exits 2 for unknown status strings."""
    with pytest.raises(SystemExit) as exc_info:
        list_questions(db_conn, status="answered")
    assert exc_info.value.code == 2

    err = json.loads(capsys.readouterr().err)
    assert err["code"] == "invalid_status"


def test_list_questions_negative_limit_exits_2(db_conn, capsys):
    """list_questions exits 2 for a negative limit (SQLite treats it as unlimited)."""
    with pytest.raises(SystemExit) as exc_info:
        list_questions(db_conn, limit=-1)
    assert exc_info.value.code == 2

    err = json.loads(capsys.readouterr().err)
    assert err["code"] == "invalid_limit"


# ---------------------------------------------------------------------------
# Vocabulary constants are exported
# ---------------------------------------------------------------------------


def test_known_skills_exported():
    """KNOWN_SKILLS contains the expected skill names."""
    assert "mine-define" in KNOWN_SKILLS
    assert "mine-grill" in KNOWN_SKILLS
    assert "mine-plan" in KNOWN_SKILLS


def test_known_topics_exported():
    """KNOWN_TOPICS contains expected topics from all skills."""
    assert "scope-mode" in KNOWN_TOPICS
    assert "edge-cases" in KNOWN_TOPICS
    assert "lifecycle" in KNOWN_TOPICS
    assert "pain-point" in KNOWN_TOPICS
    assert "open-question" in KNOWN_TOPICS
    assert "sign-off" in KNOWN_TOPICS


def test_valid_statuses_exported():
    """VALID_STATUSES contains asked and skipped."""
    assert VALID_STATUSES == frozenset({"asked", "skipped"})


def test_valid_dispositions_exported():
    """Every disposition names a destination file; outcomes without one are NULL."""
    assert VALID_DISPOSITIONS == frozenset({"resolved", "accepted", "deferred"})
