"""Tests for bin/pr-ledger-check: skeleton derivation and the ledger invariants."""

import copy
import runpy
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent.parent / "bin" / "pr-ledger-check"
# The script has no .py extension and isn't a package module, so load its namespace via runpy.
MODULE = runpy.run_path(str(SCRIPT))
check_ledger = MODULE["check_ledger"]
init_ledger = MODULE["init_ledger"]
JUDGMENT_FIELDS = MODULE["JUDGMENT_FIELDS"]

PR_AUTHOR = "me"
BOT = {"login": "codex", "__typename": "Bot"}
HUMAN = {"login": "reviewer", "__typename": "User"}
SELF = {"login": "Me", "__typename": "User"}
T1, T2 = "2026-01-01T00:00:00Z", "2026-01-02T00:00:00Z"
COMMENT_URL = "https://x/pull/1#issuecomment-1"


def thread(tid: str, author: dict, created: str, resolved: bool = False) -> dict:
    return {
        "id": tid,
        "isResolved": resolved,
        "comments": {"nodes": [{"author": author, "createdAt": created}]},
    }


FEEDBACK = {
    "pr": {"title": "a PR"},
    "threads": [
        thread("PRRT_a", BOT, T1, resolved=True),
        thread("PRRT_b", BOT, T2),
        thread("PRRT_c", HUMAN, T2),
    ],
    "reviewComments": [{"url": "https://x/review-1", "author": BOT, "createdAt": T2}],
    "issueComments": [{"url": COMMENT_URL, "author": SELF, "createdAt": T1}],
}


def fill(row: dict, **changes) -> dict:
    """Fill a skeleton row's judgment fields with valid values, after applying `changes`."""
    row.update(changes)
    row["status"] = row["status"] or "open"
    row["mechanism"] = row["mechanism"] or f"mechanism of {row['id']}"
    row["disposition"] = row["disposition"] or "actionable"
    row["disposition_reason"] = row["disposition_reason"] or "reason"
    row["fix_adds"] = row["fix_adds"] or "correction: fixes a value"
    if row["status"] == "resolved" and row["outcome"] is None:
        row["outcome"] = "fixed"
    if row["status"] == "open" and row["disposition"] == "actionable":
        for field in ("finding", "root_cause", "proposed_fix"):
            row[field] = row[field] or field
        row["depth"] = row["depth"] or "light"
    if (
        row["source"] in ("reviewBody", "issueComment")
        and row["embedded_count"] is None
    ):
        row["embedded_count"] = 0
    return row


def filled_ledger(feedback: dict | list = FEEDBACK, **per_row: dict) -> dict:
    ledger = init_ledger(feedback, PR_AUTHOR)
    for row in ledger["rows"]:
        fill(row, **per_row.get(row["id"], {}))
    return ledger


def at(ledger: dict, rid: str) -> dict:
    return next(r for r in ledger["rows"] if r["id"] == rid)


def add_embedded(ledger: dict, parent_id: str, n: int, **changes) -> dict:
    parent = at(ledger, parent_id)
    row = {
        **copy.deepcopy(JUDGMENT_FIELDS),
        "id": f"{parent_id}#{n}",
        "source": "embedded",
        "author": parent["author"],
        "author_kind": parent["author_kind"],
        "round": parent["round"],
    }
    ledger["rows"].append(fill(row, **changes))
    return row


def convergence(mechanism: str, members: list[str]) -> dict:
    return {
        "mechanism": mechanism,
        "members": members,
        "rounds": 2,
        "summary": "s",
        "open_questions": ["q"],
    }


def test_init_writes_one_row_per_item_with_derived_facts() -> None:
    ledger = init_ledger(FEEDBACK, PR_AUTHOR)

    assert ledger["pr"] == "a PR"
    assert ledger["pr_author"] == PR_AUTHOR
    assert ledger["convergences"] == []
    facts = {
        r["id"]: (
            r["source"],
            r["author_kind"],
            r["round"],
            r["status"],
            r["embedded_count"],
        )
        for r in ledger["rows"]
    }
    assert facts == {
        "PRRT_a": ("thread", "bot", T1, "resolved", None),
        "PRRT_b": ("thread", "bot", T2, "open", None),
        "PRRT_c": ("thread", "human", T2, "open", None),
        "https://x/review-1": ("reviewBody", "bot", T2, None, None),
        COMMENT_URL: ("issueComment", "self", T1, None, None),
    }


def test_unfilled_skeleton_fails_the_check() -> None:
    # In particular a parent row's embedded_count starts null, not 0, so a
    # review body nobody examined can't pass as "no embedded findings".
    problems = check_ledger(FEEDBACK, init_ledger(FEEDBACK, PR_AUTHOR))

    assert (
        "row https://x/review-1 has no valid embedded_count (must be a non-negative integer)"
        in problems
    )


def test_complete_consistent_ledger_passes() -> None:
    ledger = filled_ledger(
        PRRT_a={"mechanism": "cursor sync"},
        PRRT_b={"mechanism": "cursor sync"},
        **{COMMENT_URL: {"embedded_count": 1}},
    )
    add_embedded(ledger, COMMENT_URL, 1)
    ledger["convergences"] = [convergence("cursor sync", ["PRRT_a", "PRRT_b"])]

    assert check_ledger(FEEDBACK, ledger) == []


def test_ledger_without_pr_author_is_rejected() -> None:
    ledger = filled_ledger()
    del ledger["pr_author"]

    assert check_ledger(FEEDBACK, ledger) == [
        "ledger has no pr_author; create it with `pr-ledger-check init`"
    ]


def test_missing_input_item_is_reported() -> None:
    ledger = filled_ledger()
    ledger["rows"] = [r for r in ledger["rows"] if r["id"] != COMMENT_URL]

    assert check_ledger(FEEDBACK, ledger) == [f"input item has no row: {COMMENT_URL}"]


def test_embedded_row_does_not_stand_in_for_its_parent() -> None:
    ledger = filled_ledger()
    add_embedded(ledger, COMMENT_URL, 1)
    ledger["rows"] = [r for r in ledger["rows"] if r["id"] != COMMENT_URL]

    assert f"input item has no row: {COMMENT_URL}" in check_ledger(FEEDBACK, ledger)


def test_embedded_rows_hang_only_off_url_keyed_items_on_github() -> None:
    ledger = filled_ledger()
    add_embedded(ledger, "PRRT_a", 1)

    problems = check_ledger(FEEDBACK, ledger)

    assert len(problems) == 1
    assert problems[0].startswith("row PRRT_a#1 is neither an input item")


def test_unknown_row_id_is_reported() -> None:
    ledger = filled_ledger()
    ledger["rows"].append({**at(ledger, "PRRT_b"), "id": "PRRT_zzz"})

    problems = check_ledger(FEEDBACK, ledger)

    assert len(problems) == 1
    assert problems[0].startswith("row PRRT_zzz is neither an input item")


def test_row_without_id_and_duplicate_ids_are_reported() -> None:
    ledger = filled_ledger()
    ledger["rows"] += [{"mechanism": "m"}, dict(at(ledger, "PRRT_b"))]

    problems = check_ledger(FEEDBACK, ledger)

    assert problems == ["row 5 has no id", "duplicate row id: PRRT_b"]


def test_changed_thread_status_is_reported() -> None:
    # An open thread marked resolved would drop out of the plan unanswered.
    ledger = filled_ledger(PRRT_b={"status": "resolved"})

    assert (
        "row PRRT_b has status 'resolved' but the feedback says 'open'"
        in check_ledger(FEEDBACK, ledger)
    )


def test_changed_author_kind_is_reported() -> None:
    ledger = filled_ledger(PRRT_c={"author_kind": "bot"})

    assert check_ledger(FEEDBACK, ledger) == [
        "row PRRT_c has author_kind 'bot' but the feedback says 'human'"
    ]


def test_embedded_row_must_inherit_its_parents_facts() -> None:
    ledger = filled_ledger(**{COMMENT_URL: {"embedded_count": 1}})
    add_embedded(ledger, COMMENT_URL, 1, author_kind="human")

    assert check_ledger(FEEDBACK, ledger) == [
        f"row {COMMENT_URL}#1 has author_kind 'human' but the feedback says 'self'"
    ]


def test_thread_cannot_declare_embedded_findings() -> None:
    ledger = filled_ledger(PRRT_b={"embedded_count": 1})

    assert check_ledger(FEEDBACK, ledger) == [
        "row PRRT_b has embedded_count 1 but the feedback says None"
    ]


def test_rows_need_mechanism_and_reason() -> None:
    ledger = filled_ledger()
    at(ledger, "PRRT_c").update(mechanism=" ", disposition_reason="")

    assert check_ledger(FEEDBACK, ledger) == [
        "row PRRT_c has invalid mechanism: ' '",
        "row PRRT_c has invalid disposition_reason: ''",
    ]


def test_invalid_disposition_is_reported() -> None:
    ledger = filled_ledger(PRRT_c={"disposition": "ignored"})

    assert "row PRRT_c has invalid disposition: 'ignored'" in check_ledger(
        FEEDBACK, ledger
    )


def test_comment_item_status_must_be_set() -> None:
    ledger = filled_ledger()
    at(ledger, "https://x/review-1")["status"] = None

    assert "row https://x/review-1 has invalid status: None" in check_ledger(
        FEEDBACK, ledger
    )


def test_fix_adds_must_start_with_a_known_kind() -> None:
    for bad in ("tweak: adjusts a value", "guard", "statement: says a thing"):
        ledger = filled_ledger(PRRT_c={"fix_adds": bad})

        assert check_ledger(FEEDBACK, ledger) == [
            f"row PRRT_c has invalid fix_adds: {bad!r}"
        ]


def test_resolved_row_requires_a_valid_outcome() -> None:
    ledger = filled_ledger(PRRT_a={"outcome": "done"})

    assert check_ledger(FEEDBACK, ledger) == ["row PRRT_a has invalid outcome: 'done'"]


def test_open_actionable_row_requires_execution_fields() -> None:
    ledger = filled_ledger(PRRT_b={"depth": "urgent"})

    assert check_ledger(FEEDBACK, ledger) == ["row PRRT_b has invalid depth: 'urgent'"]


def test_execution_fields_not_required_off_the_open_actionable_path() -> None:
    ledger = filled_ledger(PRRT_c={"disposition": "already-addressed"})

    assert at(ledger, "PRRT_c")["depth"] is None
    assert check_ledger(FEEDBACK, ledger) == []


def test_malformed_decision_is_reported() -> None:
    ledger = filled_ledger(
        PRRT_b={
            "decision": {"why": "w", "options": ["only one"], "recommendation": "r"}
        }
    )

    assert check_ledger(FEEDBACK, ledger) == [
        "row PRRT_b has invalid decision: {'why': 'w', 'options': ['only one'], 'recommendation': 'r'}"
    ]


def test_well_formed_decision_passes() -> None:
    ledger = filled_ledger(
        PRRT_b={"decision": {"why": "w", "options": ["a", "b"], "recommendation": "a"}}
    )

    assert check_ledger(FEEDBACK, ledger) == []


def test_negative_or_bool_embedded_count_is_reported() -> None:
    for bad in (-1, True):
        ledger = filled_ledger(**{COMMENT_URL: {"embedded_count": bad}})

        assert check_ledger(FEEDBACK, ledger) == [
            f"row {COMMENT_URL} has no valid embedded_count (must be a non-negative integer)"
        ]


def test_declared_embedded_count_must_match_actual_rows() -> None:
    ledger = filled_ledger(**{COMMENT_URL: {"embedded_count": 2}})
    add_embedded(ledger, COMMENT_URL, 1)

    assert check_ledger(FEEDBACK, ledger) == [
        f"{COMMENT_URL} declares embedded_count=2 but has 1 embedded row(s)"
    ]


def test_declared_embedded_count_of_zero_with_an_actual_row_is_reported() -> None:
    ledger = filled_ledger()
    add_embedded(ledger, COMMENT_URL, 1)

    assert check_ledger(FEEDBACK, ledger) == [
        f"{COMMENT_URL} declares embedded_count=0 but has 1 embedded row(s)"
    ]


def test_duplicate_naming_a_missing_row_is_reported() -> None:
    ledger = filled_ledger(PRRT_c={"disposition": "duplicate", "related": ["PRRT_zzz"]})

    assert check_ledger(FEEDBACK, ledger) == [
        "row PRRT_c lists related row PRRT_zzz, which does not exist",
        "open duplicate row PRRT_c names no open actionable, already-addressed, or not-actionable row in related",
    ]


def test_open_duplicate_of_a_resolved_row_is_reported() -> None:
    # The plan carries duplicates only under open substantive rows; a restatement
    # of resolved history must be substantive itself to get an answer.
    ledger = filled_ledger(PRRT_c={"disposition": "duplicate", "related": ["PRRT_a"]})

    assert check_ledger(FEEDBACK, ledger) == [
        "open duplicate row PRRT_c names no open actionable, already-addressed, or not-actionable row in related"
    ]


def test_duplicate_of_an_open_substantive_row_passes() -> None:
    ledger = filled_ledger(PRRT_c={"disposition": "duplicate", "related": ["PRRT_b"]})

    assert check_ledger(FEEDBACK, ledger) == []


def test_restated_concern_with_two_substantive_rows_is_reported() -> None:
    ledger = filled_ledger(
        PRRT_b={"related": ["PRRT_c"]}, PRRT_c={"related": ["PRRT_b"]}
    )

    assert check_ledger(FEEDBACK, ledger) == [
        "open rows PRRT_b, PRRT_c restate one concern but 2 keep a substantive disposition (exactly one must; the rest are duplicate)"
    ]


def test_row_sharing_a_convergence_label_must_be_a_member() -> None:
    ledger = filled_ledger(
        PRRT_a={"mechanism": "cursor sync"},
        PRRT_b={"mechanism": "cursor sync"},
        PRRT_c={"mechanism": "cursor sync"},
    )
    ledger["convergences"] = [convergence("cursor sync", ["PRRT_a", "PRRT_b"])]

    problems = check_ledger(FEEDBACK, ledger)

    assert len(problems) == 1
    assert "row PRRT_c carries this mechanism but is not a member" in problems[0]


def test_member_with_a_different_label_is_reported() -> None:
    ledger = filled_ledger(
        PRRT_a={"mechanism": "cursor sync"}, PRRT_b={"mechanism": "cursor sync"}
    )
    ledger["convergences"] = [
        convergence("cursor sync", ["PRRT_a", "PRRT_b", "PRRT_c"])
    ]

    problems = check_ledger(FEEDBACK, ledger)

    assert len(problems) == 1
    assert "member PRRT_c is labelled 'mechanism of PRRT_c'" in problems[0]


def test_convergence_of_only_resolved_history_is_allowed() -> None:
    feedback = copy.deepcopy(FEEDBACK)
    feedback["threads"][1]["isResolved"] = True
    ledger = filled_ledger(
        feedback,
        PRRT_a={"mechanism": "cursor sync"},
        PRRT_b={"mechanism": "cursor sync"},
    )
    ledger["convergences"] = [convergence("cursor sync", ["PRRT_a", "PRRT_b"])]

    assert check_ledger(feedback, ledger) == []


def test_convergence_rounds_must_be_a_positive_integer() -> None:
    ledger = filled_ledger(
        PRRT_a={"mechanism": "cursor sync"}, PRRT_b={"mechanism": "cursor sync"}
    )
    ledger["convergences"] = [
        {**convergence("cursor sync", ["PRRT_a", "PRRT_b"]), "rounds": 0}
    ]

    assert check_ledger(FEEDBACK, ledger) == [
        "convergence 0 ('cursor sync'): invalid rounds: 0 (must be a positive integer)"
    ]


def test_single_member_convergence_is_rejected() -> None:
    ledger = filled_ledger(PRRT_a={"mechanism": "lonely"})
    ledger["convergences"] = [convergence("lonely", ["PRRT_a"])]

    assert check_ledger(FEEDBACK, ledger) == [
        "convergence 0 ('lonely'): needs at least 2 distinct findings, has 1 (rows that list each other in related count as one)"
    ]


def test_restatements_count_as_one_finding_in_a_convergence() -> None:
    ledger = filled_ledger(
        PRRT_b={"mechanism": "cursor sync"},
        PRRT_c={
            "mechanism": "cursor sync",
            "disposition": "duplicate",
            "related": ["PRRT_b"],
        },
    )
    ledger["convergences"] = [convergence("cursor sync", ["PRRT_b", "PRRT_c"])]

    assert check_ledger(FEEDBACK, ledger) == [
        "convergence 0 ('cursor sync'): needs at least 2 distinct findings, has 1 (rows that list each other in related count as one)"
    ]


def test_incomplete_convergence_record_is_rejected_without_membership_checks() -> None:
    # PRRT_b also carries "cursor sync" but isn't a member: were the membership
    # checks not skipped for the incomplete record, that would add a problem.
    ledger = filled_ledger(
        PRRT_a={"mechanism": "cursor sync"}, PRRT_b={"mechanism": "cursor sync"}
    )
    ledger["convergences"] = [{}, {"mechanism": "cursor sync", "members": ["PRRT_a"]}]

    assert check_ledger(FEEDBACK, ledger) == [
        "convergence 0 ('None'): missing mechanism, members, summary, open_questions",
        "convergence 1 ('cursor sync'): missing summary, open_questions",
    ]


def test_ado_threads_derive_status_and_author_kind() -> None:
    feedback = [
        {
            "id": 41,
            "status": "active",
            "comments": [{"author": "rev@corp.com", "publishedDate": T1}],
        },
        {
            "id": 42,
            "status": "closed",
            "comments": [{"author": "Build Service", "publishedDate": T2}],
        },
        {
            "id": 43,
            "status": "pending",
            "comments": [{"author": "ME@corp.com", "publishedDate": T2}],
        },
        {
            "id": 44,
            "status": "closed",
            "comments": [
                {
                    "author": "00000002-0000-8888-8000-000000000000@2c895908-04e0-4952-89fd-54b0046d6288",
                    "publishedDate": T2,
                }
            ],
        },
    ]
    skeleton = init_ledger(feedback, "me@corp.com")

    assert [(r["id"], r["status"], r["author_kind"]) for r in skeleton["rows"]] == [
        ("41", "open", "human"),
        ("42", "resolved", "bot"),
        ("43", "open", "self"),
        ("44", "resolved", "bot"),
    ]

    ledger = copy.deepcopy(skeleton)
    for row in ledger["rows"]:
        fill(row, embedded_count=1 if row["id"] == "41" else 0)
    embedded = {
        **copy.deepcopy(JUDGMENT_FIELDS),
        "id": "41#1",
        "source": "embedded",
        "author": "rev@corp.com",
        "author_kind": "human",
        "round": T1,
    }
    ledger["rows"].append(fill(embedded))

    assert check_ledger(feedback, ledger) == []
    ledger["rows"] = [r for r in ledger["rows"] if r["id"] != "42"]
    assert check_ledger(feedback, ledger) == ["input item has no row: 42"]
