"""Tests for claude_memory.summarizer — context summary extraction and rendering."""

import inspect
import json
import sqlite3

import pytest

from claude_memory.hooks import backfill_summaries, memory_setup
from claude_memory.summarizer import (
    build_exchange_pairs,
    detect_disposition,
    truncate_mid,
    build_context_summary_json,
    compute_context_summary,
    render_context_summary,
)
from claude_memory.db import SCHEMA, _migrate_columns


class TestTruncateMid:
    def test_short_text_unchanged(self):
        text = "Short text."
        assert truncate_mid(text) == text

    def test_long_text_truncated(self):
        text = "A" * 300 + "B" * 100 + "C" * 600
        result = truncate_mid(text)
        assert result.startswith("A" * 300)
        assert "[... truncated ...]" in result
        assert result.endswith("C" * 600)
        assert len(result) < len(text)

    def test_empty_text(self):
        assert truncate_mid("") == ""
        assert truncate_mid(None) is None


class TestBuildExchangePairs:
    def test_simple_exchange(self):
        messages = [
            {"role": "user", "content": "Hello", "timestamp": "2025-01-01T10:00:00Z"},
            {
                "role": "assistant",
                "content": "Hi there",
                "timestamp": "2025-01-01T10:01:00Z",
            },
        ]
        exchanges = build_exchange_pairs(messages)
        assert len(exchanges) == 1
        assert exchanges[0]["user"] == "Hello"
        assert exchanges[0]["assistant"] == "Hi there"
        assert exchanges[0]["index"] == 0

    def test_multiple_exchanges(self):
        messages = [
            {"role": "user", "content": "Q1", "timestamp": "2025-01-01T10:00:00Z"},
            {"role": "assistant", "content": "A1", "timestamp": "2025-01-01T10:01:00Z"},
            {"role": "user", "content": "Q2", "timestamp": "2025-01-01T10:02:00Z"},
            {"role": "assistant", "content": "A2", "timestamp": "2025-01-01T10:03:00Z"},
        ]
        exchanges = build_exchange_pairs(messages)
        assert len(exchanges) == 2
        assert exchanges[0]["user"] == "Q1"
        assert exchanges[1]["user"] == "Q2"

    def test_tool_markers_stripped(self):
        messages = [
            {
                "role": "user",
                "content": "Read file",
                "timestamp": "2025-01-01T10:00:00Z",
            },
            {
                "role": "assistant",
                "content": "Content [Tool: Read] here",
                "timestamp": "2025-01-01T10:01:00Z",
            },
        ]
        exchanges = build_exchange_pairs(messages)
        assert "[Tool: Read]" not in exchanges[0]["assistant"]
        assert "Content" in exchanges[0]["assistant"]

    def test_user_without_response(self):
        messages = [
            {
                "role": "user",
                "content": "Last question",
                "timestamp": "2025-01-01T10:00:00Z",
            },
        ]
        exchanges = build_exchange_pairs(messages)
        assert len(exchanges) == 1
        assert exchanges[0]["user"] == "Last question"
        assert exchanges[0]["assistant"] == ""


class TestBuildContextSummaryJson:
    def test_basic_structure(self):
        branch_row = {
            "started_at": "2025-01-15T14:00:00Z",
            "ended_at": "2025-01-15T15:00:00Z",
            "exchange_count": 3,
            "files_modified": '["src/main.py"]',
            "commits": '["fix: bug"]',
            "tool_counts": '{"Read": 5}',
            "git_branch": "main",
        }
        messages = [
            {
                "role": "user",
                "content": "Fix the bug in main.py",
                "timestamp": "2025-01-15T14:00:00Z",
            },
            {
                "role": "assistant",
                "content": "Found the issue.",
                "timestamp": "2025-01-15T14:01:00Z",
            },
            {
                "role": "user",
                "content": "Apply the fix",
                "timestamp": "2025-01-15T14:02:00Z",
            },
            {
                "role": "assistant",
                "content": "Done, fixed.",
                "timestamp": "2025-01-15T14:03:00Z",
            },
        ]
        result = build_context_summary_json(branch_row, messages)

        assert result["version"] == 3
        assert result["topic"] == "Fix the bug in main.py"
        assert len(result["first_exchanges"]) == 2
        assert result["first_exchanges"][0]["user"] == "Fix the bug in main.py"
        assert result["metadata"]["git_branch"] == "main"
        assert result["metadata"]["files_modified"] == ["src/main.py"]
        assert result["metadata"]["tool_counts"] == {"Read": 5}

    def test_empty_messages(self):
        branch_row = {"started_at": None, "ended_at": None}
        result = build_context_summary_json(branch_row, [])
        assert result["first_exchanges"] == []
        assert result["last_exchanges"] == []

    def test_short_session_all_in_last(self):
        branch_row = {"exchange_count": 5}
        messages = []
        for i in range(5):
            messages.append({"role": "user", "content": f"Q{i}", "timestamp": f"t{i}"})
            messages.append(
                {"role": "assistant", "content": f"A{i}", "timestamp": f"t{i}"}
            )
        result = build_context_summary_json(branch_row, messages)
        # Short/medium session (<=8): all exchanges in last_exchanges
        assert len(result["last_exchanges"]) == 5
        assert len(result["first_exchanges"]) == 2

    def test_medium_session_all_in_last(self):
        branch_row = {"exchange_count": 8}
        messages = []
        for i in range(8):
            messages.append({"role": "user", "content": f"Q{i}", "timestamp": f"t{i}"})
            messages.append(
                {"role": "assistant", "content": f"A{i}", "timestamp": f"t{i}"}
            )
        result = build_context_summary_json(branch_row, messages)
        # At threshold (<=8): all exchanges in last_exchanges
        assert len(result["last_exchanges"]) == 8
        assert len(result["first_exchanges"]) == 2

    def test_long_session_last_6(self):
        branch_row = {"exchange_count": 10}
        messages = []
        for i in range(10):
            messages.append({"role": "user", "content": f"Q{i}", "timestamp": f"t{i}"})
            messages.append(
                {"role": "assistant", "content": f"A{i}", "timestamp": f"t{i}"}
            )
        result = build_context_summary_json(branch_row, messages)
        assert len(result["last_exchanges"]) == 6
        assert result["last_exchanges"][0]["user"] == "Q4"
        assert len(result["first_exchanges"]) == 2
        assert result["first_exchanges"][0]["user"] == "Q0"
        assert result["first_exchanges"][1]["user"] == "Q1"

    def test_topic_truncated(self):
        branch_row = {}
        long_msg = "x" * 200
        messages = [
            {"role": "user", "content": long_msg, "timestamp": "t1"},
            {"role": "assistant", "content": "OK", "timestamp": "t1"},
        ]
        result = build_context_summary_json(branch_row, messages)
        assert len(result["topic"]) <= 123  # 120 + "..."


class TestRenderContextSummary:
    def test_short_session_no_first_last_split(self):
        summary = {
            "version": 2,
            "topic": "test",
            "first_exchanges": [
                {"user": "Q1", "assistant": "A1", "timestamp": "2025-01-15T10:00:00Z"},
            ],
            "last_exchanges": [
                {"user": "Q1", "assistant": "A1", "timestamp": "2025-01-15T10:00:00Z"},
                {"user": "Q2", "assistant": "A2", "timestamp": "2025-01-15T10:01:00Z"},
            ],
            "metadata": {
                "exchange_count": 2,
                "started_at": "2025-01-15T10:00:00Z",
                "ended_at": "2025-01-15T10:30:00Z",
                "git_branch": "main",
                "files_modified": [],
                "commits": [],
                "tool_counts": {},
            },
        }
        result = render_context_summary(summary)
        assert "### Conversation" in result
        assert "### First Exchanges" not in result
        assert "### Where We Left Off" not in result
        assert "/cm-recall-conversations" in result

    def test_long_session_has_first_and_last(self):
        summary = {
            "version": 2,
            "topic": "test",
            "first_exchanges": [
                {"user": "Q1", "assistant": "A1", "timestamp": "2025-01-15T10:00:00Z"},
                {"user": "Q2", "assistant": "A2", "timestamp": "2025-01-15T10:01:00Z"},
            ],
            "last_exchanges": [
                {"user": "Q7", "assistant": "A7", "timestamp": "2025-01-15T10:09:00Z"},
                {"user": "Q8", "assistant": "A8", "timestamp": "2025-01-15T10:10:00Z"},
                {"user": "Q9", "assistant": "A9", "timestamp": "2025-01-15T10:11:00Z"},
                {
                    "user": "Q10",
                    "assistant": "A10",
                    "timestamp": "2025-01-15T10:12:00Z",
                },
                {
                    "user": "Q11",
                    "assistant": "A11",
                    "timestamp": "2025-01-15T10:13:00Z",
                },
                {
                    "user": "Q12",
                    "assistant": "A12",
                    "timestamp": "2025-01-15T10:14:00Z",
                },
            ],
            "metadata": {
                "exchange_count": 12,
                "started_at": "2025-01-15T10:00:00Z",
                "ended_at": "2025-01-15T11:00:00Z",
                "git_branch": "feat/x",
                "files_modified": ["src/a.py", "src/b.py"],
                "commits": ["fix: thing"],
                "tool_counts": {"Read": 10, "Edit": 3},
            },
        }
        result = render_context_summary(summary)
        assert "### Earlier in This Session" in result
        assert "### Where We Left Off" in result
        assert (
            "[... 4 earlier exchanges covering: a.py, b.py ...]" in result
        )  # 12 - 2 - 6 = 4
        assert "feat/x" in result
        assert "Modified:" in result
        assert "Tools:" in result
        assert "/cm-recall-conversations" in result

    def test_mid_truncation_in_render(self):
        long_response = "Start " + "x" * 1000 + " End"
        summary = {
            "version": 2,
            "topic": "test",
            "first_exchanges": [
                {
                    "user": "Q1",
                    "assistant": long_response,
                    "timestamp": "2025-01-15T10:00:00Z",
                },
            ],
            "last_exchanges": [
                {
                    "user": "Q1",
                    "assistant": long_response,
                    "timestamp": "2025-01-15T10:00:00Z",
                }
            ],
            "metadata": {
                "exchange_count": 1,
                "started_at": "2025-01-15T10:00:00Z",
                "ended_at": "2025-01-15T10:30:00Z",
                "git_branch": "main",
                "files_modified": [],
                "commits": [],
                "tool_counts": {},
            },
        }
        result = render_context_summary(summary)
        assert "[... truncated ...]" in result

    def test_empty_summary(self):
        assert render_context_summary({}) == ""
        assert render_context_summary({"first_exchanges": []}) == ""


class TestComputeContextSummary:
    """End-to-end test with a real in-memory DB."""

    @pytest.fixture
    def db_with_session(self):
        conn = sqlite3.connect(":memory:")
        conn.executescript(SCHEMA)
        conn.commit()
        _migrate_columns(conn)

        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO projects (path, key, name) VALUES (?, ?, ?)",
            ("/test/proj", "-test-proj", "proj"),
        )
        cursor.execute(
            "INSERT INTO sessions (uuid, project_id, git_branch) VALUES (?, ?, ?)",
            ("sess-1", 1, "main"),
        )
        cursor.execute(
            """
            INSERT INTO branches (session_id, leaf_uuid, is_active, started_at, ended_at,
                                  exchange_count, files_modified, commits, tool_counts)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
            (
                1,
                "leaf-1",
                1,
                "2025-01-15T10:00:00Z",
                "2025-01-15T11:00:00Z",
                3,
                '["src/main.py"]',
                '["fix: bug"]',
                '{"Read": 5}',
            ),
        )
        branch_id = cursor.lastrowid

        # Add messages
        msgs = [
            (
                1,
                "user-1",
                "2025-01-15T10:00:00Z",
                "user",
                "How do I fix the parser bug?",
            ),
            (
                1,
                "asst-1",
                "2025-01-15T10:01:00Z",
                "assistant",
                "The bug is in the tokenizer. Let me show you.",
            ),
            (1, "user-2", "2025-01-15T10:05:00Z", "user", "Can you apply that fix?"),
            (
                1,
                "asst-2",
                "2025-01-15T10:06:00Z",
                "assistant",
                "Done. I decided to use a regex-based approach for the fix.",
            ),
            (1, "user-3", "2025-01-15T10:10:00Z", "user", "Run the tests"),
            (
                1,
                "asst-3",
                "2025-01-15T10:11:00Z",
                "assistant",
                "All tests pass. Next step is deploying to staging.",
            ),
        ]
        for session_id, uuid, ts, role, content in msgs:
            cursor.execute(
                """
                INSERT INTO messages (session_id, uuid, timestamp, role, content, is_notification)
                VALUES (?, ?, ?, ?, ?, 0)
            """,
                (session_id, uuid, ts, role, content),
            )
            msg_id = cursor.lastrowid
            cursor.execute(
                "INSERT INTO branch_messages (branch_id, message_id) VALUES (?, ?)",
                (branch_id, msg_id),
            )

        conn.commit()
        yield conn, branch_id
        conn.close()

    def test_compute_returns_markdown_and_json(self, db_with_session):
        conn, branch_id = db_with_session
        cursor = conn.cursor()

        md, json_str = compute_context_summary(cursor, branch_id)

        assert md
        assert json_str
        assert "### Session:" in md
        assert "/cm-recall-conversations" in md

        parsed = json.loads(json_str)
        assert parsed["version"] == 3
        assert parsed["topic"] == "How do I fix the parser bug?"
        assert parsed["metadata"]["git_branch"] == "main"
        assert (
            len(parsed["last_exchanges"]) == 3
        )  # Short session (3 exchanges, <=8), all in last
        assert len(parsed["first_exchanges"]) == 2

    def test_compute_nonexistent_branch(self, db_with_session):
        conn, _ = db_with_session
        cursor = conn.cursor()
        md, json_str = compute_context_summary(cursor, 99999)
        assert md == ""
        assert json_str == ""


class TestDetectDispositionWithCommits:
    """Tests for the improved detect_disposition() with commits parameter."""

    def _make_exchanges(self, count: int, last_user: str = "ok") -> list[dict]:
        exchanges = []
        for i in range(count - 1):
            exchanges.append(
                {"user": f"Q{i}", "assistant": f"A{i}", "timestamp": f"t{i}"}
            )
        exchanges.append(
            {"user": last_user, "assistant": "Done.", "timestamp": "t_last"}
        )
        return exchanges

    def test_detect_disposition_completed_with_commits(self):
        """Non-empty commits list returns COMPLETED regardless of exchange content."""
        exchanges = [{"user": "start", "assistant": "working...", "timestamp": "t0"}]
        result = detect_disposition(exchanges, commits=["fix: resolve issue #42"])
        assert result == "COMPLETED"

    def test_detect_disposition_completed_with_multiple_commits(self):
        """Multiple commits still return COMPLETED."""
        exchanges = [{"user": "what now?", "assistant": "no idea", "timestamp": "t0"}]
        result = detect_disposition(exchanges, commits=["feat: add thing", "fix: bug"])
        assert result == "COMPLETED"

    def test_detect_disposition_completed_with_text_only(self):
        """Existing text heuristics still work when commits is None (or empty)."""
        exchanges = [
            {
                "user": "Run the tests",
                "assistant": "All tests pass.",
                "timestamp": "t0",
            },
            {"user": "ok", "assistant": "", "timestamp": "t1"},
        ]
        result = detect_disposition(exchanges, commits=None)
        assert result == "COMPLETED"

    def test_detect_disposition_completed_with_empty_commits(self):
        """Empty commits list does not trigger COMPLETED — falls through to text heuristics."""
        exchanges = [
            {
                "user": "What should I do?",
                "assistant": "Keep going.",
                "timestamp": "t0",
            },
        ]
        result = detect_disposition(exchanges, commits=[])
        assert result == "IN_PROGRESS"

    def test_detect_disposition_abandoned_replaces_interrupted(self):
        """Zero-exchange sessions return ABANDONED (not INTERRUPTED)."""
        result = detect_disposition([])
        assert result == "ABANDONED"
        # Confirm INTERRUPTED is not returned
        assert result != "INTERRUPTED"

    def test_detect_disposition_abandoned_no_user_followup(self):
        """Final exchange with no user reply AND >2 exchanges returns ABANDONED."""
        # Build exchanges where the last user message is empty (assistant replied, no followup)
        exchanges = [
            {"user": "Q1", "assistant": "A1", "timestamp": "t0"},
            {"user": "Q2", "assistant": "A2", "timestamp": "t1"},
            {"user": "Q3", "assistant": "Final answer here.", "timestamp": "t2"},
        ]
        # Simulate: last exchange has assistant content but no user reply after
        # We can test this by checking disposition of a last exchange where user="" and assistant is non-empty
        exchanges_with_no_reply = exchanges[:2] + [
            {"user": "", "assistant": "No followup.", "timestamp": "t3"}
        ]
        result = detect_disposition(exchanges_with_no_reply)
        assert result == "ABANDONED"

    def test_detect_disposition_not_abandoned_for_short_sessions(self):
        """Sessions with <=2 exchanges are not classified as ABANDONED when no user followup."""
        # Only 1 exchange — too short for ABANDONED heuristic
        exchanges = [{"user": "", "assistant": "Some response.", "timestamp": "t0"}]
        result = detect_disposition(exchanges)
        # Should not be ABANDONED (<=2 exchanges condition not met)
        assert result != "ABANDONED"


class TestBuildContextSummaryJsonTruncation:
    """Tests for exchange text truncation in build_context_summary_json."""

    def test_build_context_summary_json_truncates_exchanges(self):
        """Verify exchange text is truncated in JSON output; JSON size bounded."""
        # Create a branch with very long exchange content
        long_user = "U" * 1500  # way over _FRONT_CHARS + _BACK_CHARS
        long_asst = "A" * 2000
        branch_row = {
            "started_at": "2025-01-15T10:00:00Z",
            "ended_at": "2025-01-15T11:00:00Z",
            "exchange_count": 1,
            "files_modified": "[]",
            "commits": "[]",
            "tool_counts": "{}",
            "git_branch": "main",
        }
        messages = [
            {"role": "user", "content": long_user, "timestamp": "2025-01-15T10:00:00Z"},
            {
                "role": "assistant",
                "content": long_asst,
                "timestamp": "2025-01-15T10:01:00Z",
            },
        ]
        result = build_context_summary_json(branch_row, messages)

        # Exchange text should be truncated
        ex = result["last_exchanges"][0]
        assert len(ex["user"]) < len(long_user), "User text should be truncated in JSON"
        assert len(ex["assistant"]) < len(long_asst), (
            "Assistant text should be truncated in JSON"
        )
        assert "[... truncated ...]" in ex["user"] or len(ex["user"]) <= 920
        assert "[... truncated ...]" in ex["assistant"] or len(ex["assistant"]) <= 920

        # JSON should be bounded in size
        json_size = len(json.dumps(result))
        # With 1 short exchange of truncated text, should be well under 50KB
        assert json_size < 50_000, f"JSON size {json_size} exceeds 50KB limit"

    def test_version_is_3(self):
        """build_context_summary_json returns version 3."""
        branch_row = {}
        messages = [
            {"role": "user", "content": "Hello", "timestamp": "t1"},
            {"role": "assistant", "content": "Hi", "timestamp": "t2"},
        ]
        result = build_context_summary_json(branch_row, messages)
        assert result["version"] == 3


class TestNeedsBackfillVersionBump:
    """Test that the backfill threshold is 3 (not 2) in both backfill_summaries and memory_setup."""

    def _make_db_with_branch(self, summary_version: int) -> sqlite3.Connection:
        """Create an in-memory DB with one branch at the given summary_version."""
        conn = sqlite3.connect(":memory:")
        conn.executescript(SCHEMA)
        conn.commit()
        _migrate_columns(conn)
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO projects (path, key, name) VALUES (?, ?, ?)",
            ("/test/proj", "-test-proj", "proj"),
        )
        cursor.execute(
            "INSERT INTO sessions (uuid, project_id) VALUES (?, ?)",
            ("sess-1", 1),
        )
        cursor.execute(
            """
            INSERT INTO branches (session_id, leaf_uuid, is_active, summary_version)
            VALUES (?, ?, 1, ?)
            """,
            (1, "leaf-1", summary_version),
        )
        conn.commit()
        return conn

    def test_needs_backfill_version_bump_query(self):
        """Branches with summary_version=2 should be picked up by the < 3 backfill query."""
        conn = self._make_db_with_branch(summary_version=2)
        cursor = conn.cursor()
        # This is the query used by both backfill_summaries.py and memory_setup.py
        cursor.execute(
            "SELECT COUNT(*) FROM branches WHERE summary_version IS NULL OR summary_version < 3"
        )
        count = cursor.fetchone()[0]
        assert count == 1, (
            "summary_version=2 branches must be detected by the < 3 backfill query"
        )
        conn.close()

    def test_needs_backfill_version_3_not_triggered(self):
        """Branches with summary_version=3 should NOT be picked up by the < 3 backfill query."""
        conn = self._make_db_with_branch(summary_version=3)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT COUNT(*) FROM branches WHERE summary_version IS NULL OR summary_version < 3"
        )
        count = cursor.fetchone()[0]
        assert count == 0, (
            "summary_version=3 branches must NOT be detected by the < 3 backfill query"
        )
        conn.close()

    def test_backfill_summaries_uses_version_3_threshold(self):
        """Verify backfill_summaries.py source contains 'summary_version < 3' (not 2)."""
        source = inspect.getsource(backfill_summaries)
        assert "summary_version < 3" in source, (
            "backfill_summaries.py must query for summary_version < 3"
        )
        assert "summary_version = 3" in source, (
            "backfill_summaries.py must write summary_version = 3"
        )

    def test_memory_setup_uses_version_3_threshold(self):
        """Verify memory_setup.py _needs_backfill uses 'summary_version < 3' (not 2)."""
        source = inspect.getsource(memory_setup._needs_backfill)
        assert "summary_version < 3" in source, (
            "_needs_backfill() must check for summary_version < 3"
        )
