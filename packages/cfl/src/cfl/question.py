"""Discovery question tracking for cfl.

Records which interview/discovery questions were asked vs skipped across
mine-define and mine-plan runs, with the user's selected answer.
mine-grill vocabulary is declared for forward compatibility but not yet wired
(grill has no cfl run).

Status and disposition are separate axes. Status is about the asking: was the
question put to the user at all. Disposition is about the answering: which file
the user's decision was written into. Every disposition names a destination —
`resolved` into a design section, `accepted` into Dependencies and Assumptions,
`deferred` into a task's Focus. A question whose answer has no destination has
no disposition: most interview questions, where the answer simply is the design,
and the path where the user stops the run rather than answering (the halt itself
is already recorded as `runs.status='stopped'`).

Rows are append-only, and topics are not per-question identifiers — a run that
triages five open questions writes five rows all topicked `open-question`. So a
count of `deferred` rows is a count of deferral decisions, not of questions
currently deferred, and there is no way to ask the latter from this table alone.
"""

import sqlite3

import cfl.output as output_module
from cfl.session import read_context_pct

KNOWN_SKILLS: frozenset[str] = frozenset({"mine-define", "mine-grill", "mine-plan"})

KNOWN_TOPICS: frozenset[str] = frozenset(
    {
        # mine-define
        "success",
        "scope-mode",
        "scope",
        "user-flow",
        "edge-cases",
        "lifecycle",
        "deps",
        "perf",
        "rollback",
        "test-reqs",
        "impl-prefs",
        "confirm-intent",
        "sign-off",
        # mine-plan
        "design-doc",
        "open-question",
        "plan-approval",
        # mine-grill
        "pain-point",
        "handoff",
    }
)

VALID_STATUSES: frozenset[str] = frozenset({"asked", "skipped"})

VALID_DISPOSITIONS: frozenset[str] = frozenset({"resolved", "accepted", "deferred"})


def record_question(
    conn: sqlite3.Connection,
    run_id: int,
    skill: str,
    topic: str,
    *,
    status: str,
    answer: str | None = None,
    disposition: str | None = None,
) -> None:
    """Record a discovery question as asked or skipped.

    Warns for unknown skill or topic but still writes.
    Exits 2 for invalid status, invalid disposition, or a disposition on a
    skipped question.
    """
    if skill not in KNOWN_SKILLS:
        output_module.emit_warning(
            f"Unknown skill '{skill}'. Known: {sorted(KNOWN_SKILLS)}",
            code="unknown_skill",
        )

    if topic not in KNOWN_TOPICS:
        output_module.emit_warning(
            f"Unknown topic '{topic}'. Known: {sorted(KNOWN_TOPICS)}",
            code="unknown_topic",
        )

    if status not in VALID_STATUSES:
        output_module.emit_error(
            f"Unknown status '{status}'. Use: {', '.join(sorted(VALID_STATUSES))}.",
            code="invalid_status",
            exit_code=2,
        )

    if disposition is not None:
        if disposition not in VALID_DISPOSITIONS:
            output_module.emit_error(
                f"Unknown disposition '{disposition}'."
                f" Use: {', '.join(sorted(VALID_DISPOSITIONS))}.",
                code="invalid_disposition",
                exit_code=2,
            )
        if status != "asked":
            output_module.emit_error(
                f"Disposition '{disposition}' requires --status asked."
                " A skipped question was never put to the user, so its answer"
                " has nowhere to land.",
                code="disposition_without_ask",
                exit_code=2,
            )

    context_pct = read_context_pct()

    cursor = conn.execute(
        """INSERT INTO questions
             (run_id, skill, topic, status, disposition, answer, context_pct, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, datetime('now'))""",
        (run_id, skill, topic, status, disposition, answer, context_pct),
    )
    question_id = cursor.lastrowid

    output_module.emit(
        {
            "question_id": question_id,
            "run_id": run_id,
            "skill": skill,
            "topic": topic,
            "status": status,
            "disposition": disposition,
        }
    )


def list_questions(
    conn: sqlite3.Connection,
    *,
    skill: str | None = None,
    topic: str | None = None,
    status: str | None = None,
    disposition: str | None = None,
    run_id: int | None = None,
    limit: int = 50,
) -> None:
    """Query questions with optional filters.

    Exits 2 for invalid status, invalid disposition, or a negative limit.
    """
    if status is not None and status not in VALID_STATUSES:
        output_module.emit_error(
            f"Unknown status '{status}'. Use: {', '.join(sorted(VALID_STATUSES))}.",
            code="invalid_status",
            exit_code=2,
        )

    if disposition is not None and disposition not in VALID_DISPOSITIONS:
        output_module.emit_error(
            f"Unknown disposition '{disposition}'."
            f" Use: {', '.join(sorted(VALID_DISPOSITIONS))}.",
            code="invalid_disposition",
            exit_code=2,
        )

    if limit < 0:
        output_module.emit_error(
            f"Invalid limit '{limit}'. Must be non-negative.",
            code="invalid_limit",
            exit_code=2,
        )

    conditions: list[str] = []
    params: list[str | int] = []

    if skill is not None:
        conditions.append("skill = ?")
        params.append(skill)
    if topic is not None:
        conditions.append("topic = ?")
        params.append(topic)
    if status is not None:
        conditions.append("status = ?")
        params.append(status)
    if disposition is not None:
        conditions.append("disposition = ?")
        params.append(disposition)
    if run_id is not None:
        conditions.append("run_id = ?")
        params.append(run_id)

    where = f" WHERE {' AND '.join(conditions)}" if conditions else ""
    params.append(limit)

    rows = conn.execute(
        "SELECT id, run_id, skill, topic, status, disposition, answer,"
        " context_pct, created_at"
        f" FROM questions{where} ORDER BY id DESC LIMIT ?",
        params,
    ).fetchall()

    questions = []
    for r in rows:
        question = dict(r)
        if question.get("created_at"):
            question["created_at"] = output_module.to_iso(question["created_at"])
        questions.append(question)

    output_module.emit({"count": len(questions), "questions": questions})
