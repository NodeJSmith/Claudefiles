"""Shared test fixtures for ado-api."""

from unittest.mock import patch

import pytest
import whenever
from ado_api.commands.gate import GateStatus


@pytest.fixture(autouse=True)
def central_time(monkeypatch: pytest.MonkeyPatch):
    """Tables show local time, so pin the zone: the same tests pass on every machine."""
    monkeypatch.setenv("TZ", "America/Chicago")
    whenever.reset_system_tz()
    yield
    monkeypatch.undo()
    whenever.reset_system_tz()


@pytest.fixture
def readable_gates():
    """Every build's prod gate reads as 0 of 2 approvals, so list tests never reach ADO's checks API."""

    def statuses(_ctx, builds, **_kwargs):
        return {b["id"]: GateStatus(build_id=b["id"], approved=0, groups_missing=[], eligible=[]) for b in builds}

    with patch("ado_api.commands.approve.gate_statuses", side_effect=statuses) as mock:
        yield mock
