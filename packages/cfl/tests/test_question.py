"""Tests for cfl.question — discovery question tracking."""

import json

import pytest

from cfl.question import (
    KNOWN_SKILLS,
    KNOWN_TOPICS,
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

    record_question(db_conn, run_id, "mine-define", "problem", status="asked")

    out = json.loads(capsys.readouterr().out)
    assert "question_id" in out
    assert isinstance(out["question_id"], int)
    assert out["run_id"] == run_id
    assert out["skill"] == "mine-define"
    assert out["topic"] == "problem"
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

    record_question(db_conn, run_id, "mine-define", "problem", status="asked")
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

    record_question(db_conn, run_id, "unknown-skill", "problem", status="asked")

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
        record_question(db_conn, run_id, "mine-define", "problem", status="answered")
    assert exc_info.value.code == 2

    err = json.loads(capsys.readouterr().err)
    assert err["code"] == "invalid_status"


def test_record_question_all_valid_statuses_accepted(db_conn, capsys):
    """Both 'asked' and 'skipped' are accepted."""
    _, run_id = insert_spec_with_run(db_conn, 1, "my-feature", REMOTE_URL)

    for status in sorted(VALID_STATUSES):
        record_question(db_conn, run_id, "mine-define", "problem", status=status)
        _ = capsys.readouterr()


# ---------------------------------------------------------------------------
# list_questions
# ---------------------------------------------------------------------------


def test_list_questions_returns_all(db_conn, capsys):
    """list_questions returns all questions when no filters applied."""
    _, run_id = insert_spec_with_run(db_conn, 1, "my-feature", REMOTE_URL)

    record_question(db_conn, run_id, "mine-define", "problem", status="asked")
    _ = capsys.readouterr()
    record_question(db_conn, run_id, "mine-define", "success", status="asked")
    _ = capsys.readouterr()

    list_questions(db_conn)

    out = json.loads(capsys.readouterr().out)
    assert out["count"] == 2


def test_list_questions_filter_by_skill(db_conn, capsys):
    """list_questions filters by skill."""
    _, run_id = insert_spec_with_run(db_conn, 1, "my-feature", REMOTE_URL)

    record_question(db_conn, run_id, "mine-define", "problem", status="asked")
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

    record_question(db_conn, run_id, "mine-define", "problem", status="asked")
    _ = capsys.readouterr()
    record_question(db_conn, run_id, "mine-define", "edge-cases", status="skipped")
    _ = capsys.readouterr()

    list_questions(db_conn, status="skipped")

    out = json.loads(capsys.readouterr().out)
    assert out["count"] == 1
    assert out["questions"][0]["topic"] == "edge-cases"


def test_list_questions_filter_by_topic(db_conn, capsys):
    """list_questions filters by topic."""
    _, run_id = insert_spec_with_run(db_conn, 1, "my-feature", REMOTE_URL)

    record_question(db_conn, run_id, "mine-define", "problem", status="asked")
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

    for topic in ["problem", "success", "scope-mode"]:
        record_question(db_conn, run_id, "mine-define", topic, status="asked")
        _ = capsys.readouterr()

    list_questions(db_conn, limit=2)

    out = json.loads(capsys.readouterr().out)
    assert out["count"] == 2


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
    assert "pain-point" in KNOWN_TOPICS
    assert "open-question" in KNOWN_TOPICS
    assert "sign-off" in KNOWN_TOPICS


def test_valid_statuses_exported():
    """VALID_STATUSES contains asked and skipped."""
    assert VALID_STATUSES == frozenset({"asked", "skipped"})
