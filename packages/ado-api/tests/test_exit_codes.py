"""Tests for the exit-code rules commands share."""

import pytest
from ado_api.commands.approve import approve_exit_code
from ado_api.exit_codes import combined_exit_code


@pytest.mark.parametrize(
    ("codes", "expected"),
    [((), 0), ((0, 0), 0), ((1, 0), 1), ((1, 5), 5), ((5, 1), 5), ((130, 1), 130), ((130, 5), 5)],
)
def test_combined_exit_code_ranks_an_ado_failure_first(codes: tuple[int, ...], expected: int) -> None:
    assert combined_exit_code(*codes) == expected


@pytest.mark.parametrize(
    ("statuses", "expected"),
    [
        ((), 0),
        (("approved", "already_approved", "planned"), 0),
        (("approved", "refused"), 1),
        (("unverified",), 1),
        (("refused", "failed"), 5),
    ],
)
def test_approve_exit_code(statuses: tuple[str, ...], expected: int) -> None:
    assert approve_exit_code([{"build_id": i, "status": s} for i, s in enumerate(statuses)]) == expected
