"""Tests for bin/pr-ledger-check: ledger completeness and convergence/label consistency."""

import runpy
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent.parent / "bin" / "pr-ledger-check"
# The script has no .py extension and isn't a package module, so load its namespace via runpy.
MODULE = runpy.run_path(str(SCRIPT))
check_ledger = MODULE["check_ledger"]

GITHUB_FEEDBACK = {
    "threads": [{"id": "PRRT_a"}, {"id": "PRRT_b"}, {"id": "PRRT_c"}],
    "reviewComments": [{"url": "https://x/review-1"}],
    "issueComments": [{"url": "https://x/comment-1"}],
}


def row(
    rid: str,
    mechanism: str = "m",
    status: str = "open",
    reason: str = "r",
    disposition: str = "actionable",
) -> dict:
    return {
        "id": rid,
        "mechanism": mechanism,
        "status": status,
        "disposition_reason": reason,
        "disposition": disposition,
    }


def convergence(mechanism: str, members: list[str]) -> dict:
    return {
        "mechanism": mechanism,
        "members": members,
        "summary": "s",
        "open_questions": ["q"],
    }


def complete_rows() -> list[dict]:
    return [
        row("PRRT_a", "cursor sync", status="resolved"),
        row("PRRT_b", "cursor sync"),
        row("PRRT_c", "docs tone"),
        row("https://x/review-1", "review summary"),
        row("https://x/comment-1", "walkthrough"),
    ]


def test_complete_consistent_ledger_passes() -> None:
    ledger = {
        "rows": [*complete_rows(), row("https://x/comment-1#1", "walkthrough check")],
        "convergences": [convergence("cursor sync", ["PRRT_a", "PRRT_b"])],
    }

    assert check_ledger(GITHUB_FEEDBACK, ledger) == []


def test_missing_input_item_is_reported() -> None:
    ledger = {
        "rows": [r for r in complete_rows() if r["id"] != "https://x/comment-1"],
        "convergences": [],
    }

    assert check_ledger(GITHUB_FEEDBACK, ledger) == [
        "input item has no row: https://x/comment-1"
    ]


def test_embedded_row_does_not_stand_in_for_its_parent() -> None:
    rows = [r for r in complete_rows() if r["id"] != "https://x/comment-1"]
    ledger = {"rows": [*rows, row("https://x/comment-1#1")], "convergences": []}

    assert "input item has no row: https://x/comment-1" in check_ledger(
        GITHUB_FEEDBACK, ledger
    )


def test_embedded_rows_hang_only_off_url_keyed_items_on_github() -> None:
    ledger = {"rows": [*complete_rows(), row("PRRT_a#1")], "convergences": []}

    problems = check_ledger(GITHUB_FEEDBACK, ledger)

    assert len(problems) == 1
    assert problems[0].startswith("row PRRT_a#1 is neither an input item")


def test_unknown_row_id_is_reported() -> None:
    ledger = {"rows": [*complete_rows(), row("PRRT_zzz")], "convergences": []}

    problems = check_ledger(GITHUB_FEEDBACK, ledger)

    assert len(problems) == 1
    assert problems[0].startswith("row PRRT_zzz is neither an input item")


def test_row_without_id_is_reported() -> None:
    ledger = {
        "rows": [*complete_rows(), {"mechanism": "m", "disposition_reason": "r"}],
        "convergences": [],
    }

    assert check_ledger(GITHUB_FEEDBACK, ledger) == ["row 5 has no id"]


def test_rows_need_mechanism_and_reason() -> None:
    rows = complete_rows()
    rows[2] = row("PRRT_c", mechanism=" ", reason="")

    problems = check_ledger(GITHUB_FEEDBACK, {"rows": rows, "convergences": []})

    assert problems == [
        "row PRRT_c has no mechanism",
        "row PRRT_c has no disposition_reason",
    ]


def test_row_sharing_a_convergence_label_must_be_a_member() -> None:
    ledger = {
        "rows": complete_rows(),
        "convergences": [convergence("cursor sync", ["PRRT_b"])],
    }

    problems = check_ledger(GITHUB_FEEDBACK, ledger)

    assert len(problems) == 1
    assert "row PRRT_a carries this mechanism but is not a member" in problems[0]


def test_member_with_a_different_label_is_reported() -> None:
    ledger = {
        "rows": complete_rows(),
        "convergences": [convergence("cursor sync", ["PRRT_a", "PRRT_b", "PRRT_c"])],
    }

    problems = check_ledger(GITHUB_FEEDBACK, ledger)

    assert len(problems) == 1
    assert "member PRRT_c is labelled 'docs tone'" in problems[0]


def test_convergence_of_only_resolved_history_is_allowed() -> None:
    rows = complete_rows()
    rows[1] = row("PRRT_b", "cursor sync", status="resolved")
    ledger = {
        "rows": rows,
        "convergences": [convergence("cursor sync", ["PRRT_a", "PRRT_b"])],
    }

    assert check_ledger(GITHUB_FEEDBACK, ledger) == []


def test_ado_threads_are_keyed_by_id_as_strings() -> None:
    feedback = [{"id": 41, "status": "active"}, {"id": 42, "status": "closed"}]
    ledger = {
        "rows": [row("41"), row(42, status="resolved"), row("41#1")],
        "convergences": [],
    }

    assert check_ledger(feedback, ledger) == []
    assert check_ledger(feedback, {"rows": [row("41")], "convergences": []}) == [
        "input item has no row: 42"
    ]


def test_embedded_findings_must_be_verified_not_just_the_parent_row() -> None:
    feedback = {
        "threads": [],
        "reviewComments": [
            {
                "url": "https://x/review-2",
                "body": "<details><summary>Outside diff range comments (2)</summary>a</details>",
            }
        ],
        "issueComments": [],
    }
    ledger = {
        "rows": [
            row("https://x/review-2", "review summary"),
            row("https://x/review-2#1", "outside-diff finding a"),
        ],
        "convergences": [],
    }

    assert check_ledger(feedback, ledger) == [
        "https://x/review-2 claims 2 embedded finding(s) but only 1 embedded row(s) exist"
    ]


def test_embedded_findings_satisfied_by_matching_row_count() -> None:
    feedback = {
        "threads": [],
        "reviewComments": [
            {
                "url": "https://x/review-2",
                "body": "<details><summary>Outside diff range comments (2)</summary>a</details>",
            }
        ],
        "issueComments": [],
    }
    ledger = {
        "rows": [
            row("https://x/review-2", "review summary"),
            row("https://x/review-2#1", "outside-diff finding a"),
            row("https://x/review-2#2", "outside-diff finding b"),
        ],
        "convergences": [],
    }

    assert check_ledger(feedback, ledger) == []


def test_embedded_findings_counted_from_severity_badges() -> None:
    feedback = {
        "threads": [],
        "reviewComments": [],
        "issueComments": [
            {
                "url": "https://x/comment-2",
                "body": (
                    "![P1 Badge](url) first finding\n\n![P2 Badge](url) second finding"
                ),
            }
        ],
    }
    ledger = {"rows": [row("https://x/comment-2", "walkthrough")], "convergences": []}

    assert check_ledger(feedback, ledger) == [
        "https://x/comment-2 claims 2 embedded finding(s) but only 0 embedded row(s) exist"
    ]


def test_invalid_status_is_reported() -> None:
    rows = complete_rows()
    rows[2] = row("PRRT_c", status="in-progress")

    problems = check_ledger(GITHUB_FEEDBACK, {"rows": rows, "convergences": []})

    assert "row PRRT_c has invalid status: 'in-progress'" in problems


def test_invalid_disposition_is_reported() -> None:
    rows = complete_rows()
    rows[2] = row("PRRT_c", disposition="ignored")

    problems = check_ledger(GITHUB_FEEDBACK, {"rows": rows, "convergences": []})

    assert "row PRRT_c has invalid disposition: 'ignored'" in problems


def test_incomplete_convergence_record_is_rejected() -> None:
    ledger = {"rows": complete_rows(), "convergences": [{}]}

    problems = check_ledger(GITHUB_FEEDBACK, ledger)

    assert problems == [
        "convergence 0 ('None'): missing mechanism, members, summary, open_questions"
    ]


def test_incomplete_convergence_record_skips_membership_checks() -> None:
    # PRRT_b also carries "cursor sync" but isn't listed as a member: were the
    # membership checks not skipped for this incomplete record, that mismatch
    # would add a second problem alongside the missing-fields one.
    ledger = {
        "rows": complete_rows(),
        "convergences": [{"mechanism": "cursor sync", "members": ["PRRT_a"]}],
    }

    problems = check_ledger(GITHUB_FEEDBACK, ledger)

    assert problems == [
        "convergence 0 ('cursor sync'): missing summary, open_questions"
    ]
