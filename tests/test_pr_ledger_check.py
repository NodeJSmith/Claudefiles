"""Tests for bin/pr-ledger-check: field contract, embedded-count, and convergence checks."""

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
    author_kind: str = "bot",
    finding: str = "f",
    root_cause: str = "rc",
    proposed_fix: str = "pf",
    depth: str = "light",
    outcome: str = "fixed",
    related: list | None = None,
    embedded_count: int = 0,
) -> dict:
    # Mirrors the real ledger shape: fields conditionally required by status/
    # disposition are only present when that condition applies, same as a real
    # ledger row would have them.
    data = {
        "id": rid,
        "mechanism": mechanism,
        "status": status,
        "disposition_reason": reason,
        "disposition": disposition,
        "author_kind": author_kind,
        "related": related if related is not None else [],
        "embedded_count": embedded_count,
    }
    if status == "resolved":
        data["outcome"] = outcome
    if status == "open" and disposition == "actionable":
        data["finding"] = finding
        data["root_cause"] = root_cause
        data["proposed_fix"] = proposed_fix
        data["depth"] = depth
    return data


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
    rows = complete_rows()
    rows[-1] = row("https://x/comment-1", "walkthrough", embedded_count=1)
    ledger = {
        "rows": [*rows, row("https://x/comment-1#1", "walkthrough check")],
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
        "row PRRT_c has invalid mechanism: ' '",
        "row PRRT_c has invalid disposition_reason: ''",
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


def test_invalid_author_kind_is_reported() -> None:
    rows = complete_rows()
    rows[2] = row("PRRT_c", author_kind="maintainer")

    problems = check_ledger(GITHUB_FEEDBACK, {"rows": rows, "convergences": []})

    assert "row PRRT_c has invalid author_kind: 'maintainer'" in problems


def test_resolved_row_requires_a_valid_outcome() -> None:
    rows = complete_rows()
    rows[0] = row("PRRT_a", "cursor sync", status="resolved", outcome="done")

    problems = check_ledger(GITHUB_FEEDBACK, {"rows": rows, "convergences": []})

    assert "row PRRT_a has invalid outcome: 'done'" in problems


def test_outcome_not_required_on_open_rows() -> None:
    # complete_rows()'s open rows never set "outcome" at all (row() omits the key
    # unless status is resolved) -- confirms _is_resolved gates the requirement.
    assert (
        check_ledger(GITHUB_FEEDBACK, {"rows": complete_rows(), "convergences": []})
        == []
    )


def test_open_actionable_row_requires_execution_fields() -> None:
    rows = complete_rows()
    rows[1] = row("PRRT_b", "cursor sync", depth="urgent")

    problems = check_ledger(GITHUB_FEEDBACK, {"rows": rows, "convergences": []})

    assert "row PRRT_b has invalid depth: 'urgent'" in problems


def test_execution_fields_not_required_off_the_open_actionable_path() -> None:
    rows = complete_rows()
    # already-addressed: finding/root_cause/proposed_fix/depth are all omitted by
    # row(), same as a real ledger row that isn't open+actionable.
    rows[2] = row("PRRT_c", "docs tone", disposition="already-addressed")

    assert check_ledger(GITHUB_FEEDBACK, {"rows": rows, "convergences": []}) == []


def test_duplicate_row_requires_related() -> None:
    rows = complete_rows()
    rows[2] = row("PRRT_c", "docs tone", disposition="duplicate", related=[])

    problems = check_ledger(GITHUB_FEEDBACK, {"rows": rows, "convergences": []})

    assert "row PRRT_c has invalid related: []" in problems


def test_duplicate_row_with_related_passes() -> None:
    rows = complete_rows()
    rows[2] = row("PRRT_c", "docs tone", disposition="duplicate", related=["PRRT_b"])

    assert check_ledger(GITHUB_FEEDBACK, {"rows": rows, "convergences": []}) == []


def test_missing_embedded_count_is_reported_on_an_embeddable_row() -> None:
    rows = complete_rows()
    rows[-1] = {
        k: v
        for k, v in row("https://x/comment-1", "walkthrough").items()
        if k != "embedded_count"
    }

    problems = check_ledger(GITHUB_FEEDBACK, {"rows": rows, "convergences": []})

    assert (
        "row https://x/comment-1 has no valid embedded_count (must be a non-negative integer)"
        in problems
    )


def test_negative_embedded_count_is_reported() -> None:
    rows = complete_rows()
    rows[-1] = row("https://x/comment-1", "walkthrough", embedded_count=-1)

    problems = check_ledger(GITHUB_FEEDBACK, {"rows": rows, "convergences": []})

    assert (
        "row https://x/comment-1 has no valid embedded_count (must be a non-negative integer)"
        in problems
    )


def test_bool_embedded_count_is_rejected_despite_being_an_int_subclass() -> None:
    rows = complete_rows()
    rows[-1] = row("https://x/comment-1", "walkthrough", embedded_count=True)

    problems = check_ledger(GITHUB_FEEDBACK, {"rows": rows, "convergences": []})

    assert (
        "row https://x/comment-1 has no valid embedded_count (must be a non-negative integer)"
        in problems
    )


def test_embedded_count_not_required_on_a_github_inline_thread() -> None:
    rows = complete_rows()
    rows[1] = {
        k: v for k, v in row("PRRT_b", "cursor sync").items() if k != "embedded_count"
    }

    assert check_ledger(GITHUB_FEEDBACK, {"rows": rows, "convergences": []}) == []


def test_declared_embedded_count_short_of_actual_rows_is_reported() -> None:
    rows = complete_rows()
    rows[-1] = row("https://x/comment-1", "walkthrough", embedded_count=2)
    ledger = {
        "rows": [*rows, row("https://x/comment-1#1", "walkthrough check")],
        "convergences": [],
    }

    assert check_ledger(GITHUB_FEEDBACK, ledger) == [
        "https://x/comment-1 declares embedded_count=2 but has 1 embedded row(s)"
    ]


def test_declared_embedded_count_matching_actual_rows_passes() -> None:
    rows = complete_rows()
    rows[-1] = row("https://x/comment-1", "walkthrough", embedded_count=2)
    ledger = {
        "rows": [
            *rows,
            row("https://x/comment-1#1", "walkthrough check a"),
            row("https://x/comment-1#2", "walkthrough check b"),
        ],
        "convergences": [],
    }

    assert check_ledger(GITHUB_FEEDBACK, ledger) == []


def test_declared_embedded_count_of_zero_with_an_actual_row_is_reported() -> None:
    # A parent row that says "no embedded findings" but has an embedded row
    # anyway is exactly as inconsistent as under-declaring a positive count.
    rows = complete_rows()
    ledger = {
        "rows": [*rows, row("https://x/comment-1#1", "walkthrough check")],
        "convergences": [],
    }

    assert check_ledger(GITHUB_FEEDBACK, ledger) == [
        "https://x/comment-1 declares embedded_count=0 but has 1 embedded row(s)"
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
        "rows": [
            row("41", embedded_count=1),
            row(42, status="resolved"),
            row("41#1"),
        ],
        "convergences": [],
    }

    assert check_ledger(feedback, ledger) == []
    assert check_ledger(feedback, {"rows": [row("41")], "convergences": []}) == [
        "input item has no row: 42"
    ]


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
