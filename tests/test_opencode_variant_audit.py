"""Tests for bin/opencode-variant-audit.

The tool's whole job is telling a real variant-resolution regression apart from
a healthy sync, so the classification table is the thing worth locking down: a
wrong verdict here would either hide the bug it exists to catch or cry wolf
about a working config.
"""

import runpy
import sqlite3
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parent.parent / "bin" / "opencode-variant-audit"


def _load_script() -> dict:
    return runpy.run_path(str(SCRIPT), run_name="_test_opencode_variant_audit")


def _make_db(path: Path, rows: list[tuple]) -> None:
    """Build a minimal stand-in for opencode.db's `session` table.

    Only the columns the audit query touches are recreated; `model` is stored
    as the JSON blob OpenCode writes so `json_extract` is exercised for real
    rather than stubbed.
    """
    conn = sqlite3.connect(path)
    try:
        conn.execute(
            "CREATE TABLE session ("
            "  agent TEXT, model TEXT, parent_id TEXT, time_created INTEGER)"
        )
        conn.executemany("INSERT INTO session VALUES (?, ?, ?, ?)", rows)
        conn.commit()
    finally:
        conn.close()


@pytest.mark.parametrize(
    ("variant", "expected_resolved"),
    [
        ("high", True),
        ("xhigh", True),
        # "none" is a real OpenCode variant (explicitly no reasoning), not the
        # absence of one -- it must not be confused with the failure cases.
        ("none", True),
        ("default", False),
        (None, False),
    ],
)
def test_classify_verdicts(variant: str | None, expected_resolved: bool) -> None:
    module = _load_script()

    resolved, reason = module["classify"](variant)

    assert resolved is expected_resolved
    assert reason


@pytest.mark.parametrize("variant", ["minimal", "thinking", "ultra"])
def test_classify_accepts_foreign_model_family_variants(variant: str) -> None:
    """A name outside the gpt-5.6 vocabulary is a PASS, not a failure.

    `classify()`'s docstring carries the reasoning and the upstream citations;
    the short version is that OpenCode rewrites a name it rejected to
    "default", so any name that survives is one it already accepted.
    """
    module = _load_script()

    resolved, _ = module["classify"](variant)

    assert resolved is True


def test_fetch_excludes_primary_sessions(tmp_path: Path) -> None:
    """`default` is normal on a primary session and only meaningful on a
    dispatched one, so a primary row must never reach the verdict.
    """
    module = _load_script()
    db = tmp_path / "opencode.db"
    _make_db(
        db,
        [
            ("build", '{"id":"m","variant":"default"}', None, 2000),
            ("worker-standard", '{"id":"m","variant":"high"}', "ses_parent", 2000),
        ],
    )

    rows = module["fetch_subagent_sessions"](db, 0)

    assert [row["agent"] for row in rows] == ["worker-standard"]


def test_fetch_keeps_rows_with_no_agent_name(tmp_path: Path) -> None:
    """A dispatched session with a NULL agent is an anomaly worth showing, not
    silently dropping from the audit's own totals.
    """
    module = _load_script()
    db = tmp_path / "opencode.db"
    _make_db(db, [(None, '{"id":"m","variant":"high"}', "ses_parent", 2000)])

    assert len(module["fetch_subagent_sessions"](db, 0)) == 1


def test_fetch_honors_cutoff(tmp_path: Path) -> None:
    module = _load_script()
    db = tmp_path / "opencode.db"
    _make_db(
        db,
        [
            ("old", '{"id":"m","variant":"high"}', "ses_parent", 1000),
            ("new", '{"id":"m","variant":"high"}', "ses_parent", 3000),
        ],
    )

    rows = module["fetch_subagent_sessions"](db, 2000)

    assert [row["agent"] for row in rows] == ["new"]


def test_main_exit_codes(tmp_path: Path, capsys: pytest.CaptureFixture) -> None:
    """The exit code is the tool's machine-readable verdict: a fallback (1) and
    a broken audit (2) must never be conflated.
    """
    module = _load_script()

    clean = tmp_path / "clean.db"
    _make_db(clean, [("worker", '{"id":"m","variant":"high"}', "ses_p", 2000)])
    assert module["main"](["--all", "--db", str(clean)]) == 0

    regressed = tmp_path / "regressed.db"
    _make_db(regressed, [("worker", '{"id":"m","variant":"default"}', "ses_p", 2000)])
    assert module["main"](["--all", "--db", str(regressed)]) == 1

    empty = tmp_path / "empty.db"
    _make_db(empty, [])
    assert module["main"](["--all", "--db", str(empty)]) == 3

    assert module["main"](["--db", str(tmp_path / "absent.db")]) == 2

    wrong_schema = tmp_path / "wrong.db"
    conn = sqlite3.connect(wrong_schema)
    conn.execute("CREATE TABLE unrelated (x)")
    conn.close()
    assert module["main"](["--all", "--db", str(wrong_schema)]) == 2

    capsys.readouterr()


def test_main_rejects_negative_window(tmp_path: Path) -> None:
    """argparse turns a bad --since into a usage error rather than letting it
    reach the query as a nonsense cutoff.
    """
    module = _load_script()

    with pytest.raises(SystemExit) as excinfo:
        module["main"](["--since", "-5"])

    assert excinfo.value.code == 2
