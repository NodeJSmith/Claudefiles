"""Tests for consolidation check overhaul: cooldown, randomization, threshold."""

import io
import json
import sqlite3
import sys
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest

import claude_memory.db as _db_mod
import claude_memory.hooks.consolidation_check as cc


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def cm_dir(tmp_path):
    """Temporary ~/.claude-memory/ directory."""
    d = tmp_path / ".claude-memory"
    d.mkdir()
    return d


@pytest.fixture()
def projects_dir(tmp_path):
    """Temporary ~/.claude/projects/ directory."""
    d = tmp_path / ".claude" / "projects"
    d.mkdir(parents=True)
    return d


@pytest.fixture()
def in_memory_db():
    """An in-memory SQLite DB with the claude-memory schema."""
    conn = sqlite3.connect(":memory:")
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS projects (
          id INTEGER PRIMARY KEY,
          path TEXT UNIQUE NOT NULL,
          key TEXT UNIQUE NOT NULL,
          name TEXT,
          created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS sessions (
          id INTEGER PRIMARY KEY,
          uuid TEXT UNIQUE NOT NULL,
          project_id INTEGER REFERENCES projects(id),
          parent_session_id INTEGER REFERENCES sessions(id),
          git_branch TEXT,
          cwd TEXT,
          imported_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS branches (
          id INTEGER PRIMARY KEY,
          session_id INTEGER NOT NULL REFERENCES sessions(id),
          leaf_uuid TEXT NOT NULL,
          fork_point_uuid TEXT,
          is_active INTEGER DEFAULT 1,
          started_at DATETIME,
          ended_at DATETIME,
          exchange_count INTEGER DEFAULT 0
        );
    """)
    return conn


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _insert_sessions(conn, project_key, count, ended_at="2026-01-01T12:00:00"):
    """Insert a project and N sessions with branches into the in-memory DB."""
    conn.execute(
        "INSERT OR IGNORE INTO projects(path, key, name) VALUES (?, ?, ?)",
        (f"/fake/{project_key}", project_key, project_key),
    )
    row = conn.execute(
        "SELECT id FROM projects WHERE key = ?", (project_key,)
    ).fetchone()
    project_id = row[0]

    for i in range(count):
        uuid = f"session-{project_key}-{i}"
        conn.execute(
            "INSERT OR IGNORE INTO sessions(uuid, project_id) VALUES (?, ?)",
            (uuid, project_id),
        )
        session_row = conn.execute(
            "SELECT id FROM sessions WHERE uuid = ?", (uuid,)
        ).fetchone()
        session_id = session_row[0]
        conn.execute(
            "INSERT OR IGNORE INTO branches(session_id, leaf_uuid, ended_at) VALUES (?, ?, ?)",
            (session_id, f"leaf-{uuid}", ended_at),
        )
    conn.commit()


# ---------------------------------------------------------------------------
# Test: default threshold is 10
# ---------------------------------------------------------------------------


class TestDefaultThreshold:
    def test_default_threshold_is_10(self):
        """DEFAULT_SETTINGS must define consolidation_min_sessions as 10."""
        assert _db_mod.DEFAULT_SETTINGS["consolidation_min_sessions"] == 10


# ---------------------------------------------------------------------------
# Test: nudge marker read/write helpers
# ---------------------------------------------------------------------------


class TestNudgeMarkers:
    def test_read_last_nudge_returns_none_when_missing(self, cm_dir, monkeypatch):
        monkeypatch.setattr(cc, "CLAUDE_MEMORY_DIR", cm_dir)
        result = cc.read_last_nudge("myproject")
        assert result is None

    def test_read_global_nudge_returns_none_when_missing(self, cm_dir, monkeypatch):
        monkeypatch.setattr(cc, "CLAUDE_MEMORY_DIR", cm_dir)
        result = cc.read_global_nudge()
        assert result is None

    def test_write_nudge_markers_creates_both_files(self, cm_dir, monkeypatch):
        monkeypatch.setattr(cc, "CLAUDE_MEMORY_DIR", cm_dir)
        cc.write_nudge_markers("myproject")

        project_marker = cm_dir / ".last-nudge-myproject"
        global_marker = cm_dir / ".last-nudge-global"
        assert project_marker.exists()
        assert global_marker.exists()

    def test_write_nudge_markers_writes_iso_timestamp(self, cm_dir, monkeypatch):
        monkeypatch.setattr(cc, "CLAUDE_MEMORY_DIR", cm_dir)
        before = datetime.now(timezone.utc)
        cc.write_nudge_markers("myproject")
        after = datetime.now(timezone.utc)

        project_marker = cm_dir / ".last-nudge-myproject"
        text = project_marker.read_text().strip()
        ts = datetime.fromisoformat(text)
        assert before <= ts <= after

    def test_read_last_nudge_returns_written_time(self, cm_dir, monkeypatch):
        monkeypatch.setattr(cc, "CLAUDE_MEMORY_DIR", cm_dir)
        cc.write_nudge_markers("myproject")
        result = cc.read_last_nudge("myproject")
        assert result is not None
        # Should be recent
        assert (datetime.now(timezone.utc) - result).total_seconds() < 5

    def test_read_global_nudge_returns_written_time(self, cm_dir, monkeypatch):
        monkeypatch.setattr(cc, "CLAUDE_MEMORY_DIR", cm_dir)
        cc.write_nudge_markers("myproject")
        result = cc.read_global_nudge()
        assert result is not None
        assert (datetime.now(timezone.utc) - result).total_seconds() < 5


# ---------------------------------------------------------------------------
# Test: per-project cooldown
# ---------------------------------------------------------------------------


class TestPerProjectCooldown:
    def test_cooldown_suppresses_within_24h(
        self, cm_dir, in_memory_db, monkeypatch, tmp_path
    ):
        """If per-project nudge marker is 1 hour old, nudge must not fire."""
        project_key = "testproject"
        monkeypatch.setattr(cc, "CLAUDE_MEMORY_DIR", cm_dir)

        # Write a marker 1 hour ago
        one_hour_ago = datetime.now(timezone.utc) - timedelta(hours=1)
        marker_path = cm_dir / f".last-nudge-{project_key}"
        marker_path.write_text(one_hour_ago.isoformat())

        # Set up 15 sessions (above threshold)
        _insert_sessions(in_memory_db, project_key, 15)

        # Patch get_db_connection to return our in-memory DB
        monkeypatch.setattr(cc, "get_db_connection", lambda settings=None: in_memory_db)
        # Patch db_path check to always pass
        monkeypatch.setattr(
            _db_mod, "get_db_path", lambda settings=None: tmp_path / "conversations.db"
        )
        fake_db = tmp_path / "conversations.db"
        fake_db.touch()

        # Provide valid hook input
        hook_input = json.dumps({"source": "startup", "cwd": f"/fake/{project_key}"})

        with patch.object(sys, "stdin", io.StringIO(hook_input)):
            # Patch get_project_key to return our key directly
            with patch.object(cc, "get_project_key", return_value=project_key):
                # Patch load_settings to return settings enabling nudge
                with patch.object(
                    cc,
                    "load_settings",
                    return_value={
                        "consolidation_reminder_enabled": True,
                        "consolidation_min_hours": 24,
                        "consolidation_min_sessions": 10,
                    },
                ):
                    with patch.object(
                        cc, "load_config", return_value={"onboarding_completed": True}
                    ):
                        output = []
                        with patch("builtins.print", side_effect=output.append):
                            cc.main()

        assert len(output) == 1
        result = json.loads(output[0])
        # No hookSpecificOutput means nudge was suppressed
        assert "hookSpecificOutput" not in result

    def test_cooldown_allows_after_24h(
        self, cm_dir, in_memory_db, monkeypatch, tmp_path
    ):
        """If per-project nudge marker is 25 hours old, nudge can fire (subject to probability)."""
        project_key = "testproject2"
        monkeypatch.setattr(cc, "CLAUDE_MEMORY_DIR", cm_dir)

        # Write a marker 25 hours ago
        old_time = datetime.now(timezone.utc) - timedelta(hours=25)
        marker_path = cm_dir / f".last-nudge-{project_key}"
        marker_path.write_text(old_time.isoformat())

        # Set up 15 sessions (above threshold)
        _insert_sessions(in_memory_db, project_key, 15, ended_at="2026-04-20T12:00:00")

        monkeypatch.setattr(cc, "get_db_connection", lambda settings=None: in_memory_db)
        monkeypatch.setattr(
            _db_mod, "get_db_path", lambda settings=None: tmp_path / "conversations.db"
        )
        fake_db = tmp_path / "conversations.db"
        fake_db.touch()

        hook_input = json.dumps({"source": "startup", "cwd": f"/fake/{project_key}"})

        # Also need last_consolidation marker so "hours elapsed" gate passes
        # (no last_consolidation -> never-consolidated path, which also fires)

        with patch.object(sys, "stdin", io.StringIO(hook_input)):
            with patch.object(cc, "get_project_key", return_value=project_key):
                with patch.object(
                    cc,
                    "load_settings",
                    return_value={
                        "consolidation_reminder_enabled": True,
                        "consolidation_min_hours": 24,
                        "consolidation_min_sessions": 10,
                    },
                ):
                    with patch.object(
                        cc, "load_config", return_value={"onboarding_completed": True}
                    ):
                        # Force random.random() to return < NUDGE_PROBABILITY (fires)
                        with patch("random.random", return_value=0.10):
                            output = []
                            with patch("builtins.print", side_effect=output.append):
                                cc.main()

        assert len(output) == 1
        result = json.loads(output[0])
        # nudge should fire
        assert "hookSpecificOutput" in result


# ---------------------------------------------------------------------------
# Test: global cooldown
# ---------------------------------------------------------------------------


class TestGlobalCooldown:
    def test_global_cooldown_suppresses_cross_project(
        self, cm_dir, in_memory_db, monkeypatch, tmp_path
    ):
        """If global nudge marker is 1 hour old, project B's nudge must be suppressed."""
        project_key = "projectB"
        monkeypatch.setattr(cc, "CLAUDE_MEMORY_DIR", cm_dir)

        # Write global marker 1 hour ago (no project-specific marker)
        one_hour_ago = datetime.now(timezone.utc) - timedelta(hours=1)
        global_marker = cm_dir / ".last-nudge-global"
        global_marker.write_text(one_hour_ago.isoformat())

        # Set up 15 sessions
        _insert_sessions(in_memory_db, project_key, 15)

        monkeypatch.setattr(cc, "get_db_connection", lambda settings=None: in_memory_db)
        monkeypatch.setattr(
            _db_mod, "get_db_path", lambda settings=None: tmp_path / "conversations.db"
        )
        fake_db = tmp_path / "conversations.db"
        fake_db.touch()

        hook_input = json.dumps({"source": "startup", "cwd": f"/fake/{project_key}"})

        with patch.object(sys, "stdin", io.StringIO(hook_input)):
            with patch.object(cc, "get_project_key", return_value=project_key):
                with patch.object(
                    cc,
                    "load_settings",
                    return_value={
                        "consolidation_reminder_enabled": True,
                        "consolidation_min_hours": 24,
                        "consolidation_min_sessions": 10,
                    },
                ):
                    with patch.object(
                        cc, "load_config", return_value={"onboarding_completed": True}
                    ):
                        output = []
                        with patch("builtins.print", side_effect=output.append):
                            cc.main()

        assert len(output) == 1
        result = json.loads(output[0])
        assert "hookSpecificOutput" not in result


# ---------------------------------------------------------------------------
# Test: randomization
# ---------------------------------------------------------------------------


class TestRandomization:
    def test_randomization_suppresses_when_above_threshold(
        self, cm_dir, in_memory_db, monkeypatch, tmp_path
    ):
        """When random.random() >= NUDGE_PROBABILITY, nudge must be suppressed."""
        project_key = "randproject"
        monkeypatch.setattr(cc, "CLAUDE_MEMORY_DIR", cm_dir)

        _insert_sessions(in_memory_db, project_key, 15)

        monkeypatch.setattr(cc, "get_db_connection", lambda settings=None: in_memory_db)
        monkeypatch.setattr(
            _db_mod, "get_db_path", lambda settings=None: tmp_path / "conversations.db"
        )
        fake_db = tmp_path / "conversations.db"
        fake_db.touch()

        hook_input = json.dumps({"source": "startup", "cwd": f"/fake/{project_key}"})

        with patch.object(sys, "stdin", io.StringIO(hook_input)):
            with patch.object(cc, "get_project_key", return_value=project_key):
                with patch.object(
                    cc,
                    "load_settings",
                    return_value={
                        "consolidation_reminder_enabled": True,
                        "consolidation_min_hours": 24,
                        "consolidation_min_sessions": 10,
                    },
                ):
                    with patch.object(
                        cc, "load_config", return_value={"onboarding_completed": True}
                    ):
                        with patch("random.random", return_value=0.99):
                            output = []
                            with patch("builtins.print", side_effect=output.append):
                                cc.main()

        result = json.loads(output[0])
        assert "hookSpecificOutput" not in result

    def test_randomization_fires_when_below_threshold(
        self, cm_dir, in_memory_db, monkeypatch, tmp_path
    ):
        """When random.random() < NUDGE_PROBABILITY, nudge must fire."""
        project_key = "randproject2"
        monkeypatch.setattr(cc, "CLAUDE_MEMORY_DIR", cm_dir)

        _insert_sessions(in_memory_db, project_key, 15)

        monkeypatch.setattr(cc, "get_db_connection", lambda settings=None: in_memory_db)
        monkeypatch.setattr(
            _db_mod, "get_db_path", lambda settings=None: tmp_path / "conversations.db"
        )
        fake_db = tmp_path / "conversations.db"
        fake_db.touch()

        hook_input = json.dumps({"source": "startup", "cwd": f"/fake/{project_key}"})

        with patch.object(sys, "stdin", io.StringIO(hook_input)):
            with patch.object(cc, "get_project_key", return_value=project_key):
                with patch.object(
                    cc,
                    "load_settings",
                    return_value={
                        "consolidation_reminder_enabled": True,
                        "consolidation_min_hours": 24,
                        "consolidation_min_sessions": 10,
                    },
                ):
                    with patch.object(
                        cc, "load_config", return_value={"onboarding_completed": True}
                    ):
                        with patch("random.random", return_value=0.10):
                            output = []
                            with patch("builtins.print", side_effect=output.append):
                                cc.main()

        result = json.loads(output[0])
        assert "hookSpecificOutput" in result

    def test_nudge_probability_constant_is_0_30(self):
        """NUDGE_PROBABILITY must be 0.30."""
        assert cc.NUDGE_PROBABILITY == 0.30


# ---------------------------------------------------------------------------
# Test: never-consolidated users — no pre-write suppression marker
# ---------------------------------------------------------------------------


class TestNeverConsolidatedNoPresuppression:
    def test_never_consolidated_no_presuppression(
        self, cm_dir, in_memory_db, monkeypatch, tmp_path
    ):
        """Never-consolidated users with 15+ sessions must get probability gate
        without any marker being pre-written to suppress them for 24h.
        Specifically: when random.random() >= NUDGE_PROBABILITY (no nudge fires),
        no .last-nudge marker must be written."""
        project_key = "freshproject"
        monkeypatch.setattr(cc, "CLAUDE_MEMORY_DIR", cm_dir)

        # 15 sessions, no markers
        _insert_sessions(in_memory_db, project_key, 15)

        monkeypatch.setattr(cc, "get_db_connection", lambda settings=None: in_memory_db)
        monkeypatch.setattr(
            _db_mod, "get_db_path", lambda settings=None: tmp_path / "conversations.db"
        )
        fake_db = tmp_path / "conversations.db"
        fake_db.touch()

        hook_input = json.dumps({"source": "startup", "cwd": f"/fake/{project_key}"})

        with patch.object(sys, "stdin", io.StringIO(hook_input)):
            with patch.object(cc, "get_project_key", return_value=project_key):
                with patch.object(
                    cc,
                    "load_settings",
                    return_value={
                        "consolidation_reminder_enabled": True,
                        "consolidation_min_hours": 24,
                        "consolidation_min_sessions": 10,
                    },
                ):
                    with patch.object(
                        cc, "load_config", return_value={"onboarding_completed": True}
                    ):
                        # random.random() returns 0.99 → no nudge fires
                        with patch("random.random", return_value=0.99):
                            output = []
                            with patch("builtins.print", side_effect=output.append):
                                cc.main()

        result = json.loads(output[0])
        assert "hookSpecificOutput" not in result

        # No markers should have been written
        project_marker = cm_dir / f".last-nudge-{project_key}"
        global_marker = cm_dir / ".last-nudge-global"
        assert not project_marker.exists(), (
            "Pre-suppression marker must NOT be written when nudge didn't fire"
        )
        assert not global_marker.exists(), (
            "Global marker must NOT be written when nudge didn't fire"
        )

    def test_never_consolidated_markers_written_when_nudge_fires(
        self, cm_dir, in_memory_db, monkeypatch, tmp_path
    ):
        """When nudge fires for never-consolidated user, markers must be written."""
        project_key = "freshproject2"
        monkeypatch.setattr(cc, "CLAUDE_MEMORY_DIR", cm_dir)

        _insert_sessions(in_memory_db, project_key, 15)

        monkeypatch.setattr(cc, "get_db_connection", lambda settings=None: in_memory_db)
        monkeypatch.setattr(
            _db_mod, "get_db_path", lambda settings=None: tmp_path / "conversations.db"
        )
        fake_db = tmp_path / "conversations.db"
        fake_db.touch()

        hook_input = json.dumps({"source": "startup", "cwd": f"/fake/{project_key}"})

        with patch.object(sys, "stdin", io.StringIO(hook_input)):
            with patch.object(cc, "get_project_key", return_value=project_key):
                with patch.object(
                    cc,
                    "load_settings",
                    return_value={
                        "consolidation_reminder_enabled": True,
                        "consolidation_min_hours": 24,
                        "consolidation_min_sessions": 10,
                    },
                ):
                    with patch.object(
                        cc, "load_config", return_value={"onboarding_completed": True}
                    ):
                        with patch("random.random", return_value=0.10):
                            output = []
                            with patch("builtins.print", side_effect=output.append):
                                cc.main()

        result = json.loads(output[0])
        assert "hookSpecificOutput" in result

        # Markers must be written
        project_marker = cm_dir / f".last-nudge-{project_key}"
        global_marker = cm_dir / ".last-nudge-global"
        assert project_marker.exists()
        assert global_marker.exists()


# ---------------------------------------------------------------------------
# Test: write_config imports from db
# ---------------------------------------------------------------------------


class TestWriteConfigImportsFromDb:
    def test_write_config_imports_from_db(self):
        """write_config must not define its own DEFAULT_CONFIG dict; uses DEFAULT_SETTINGS from db."""
        import claude_memory.hooks.write_config as wc

        assert not hasattr(wc, "DEFAULT_CONFIG"), (
            "write_config must not have a local DEFAULT_CONFIG — use DEFAULT_SETTINGS from db.py"
        )

    def test_write_config_consolidation_min_sessions_matches_db_default(
        self, tmp_path, monkeypatch
    ):
        """write_config --defaults must write consolidation_min_sessions == 10 (from DEFAULT_SETTINGS)."""
        import claude_memory.hooks.write_config as wc

        cfg = tmp_path / "config.json"
        monkeypatch.setattr(_db_mod, "CONFIG_PATH", cfg)
        monkeypatch.setattr(wc, "CONFIG_PATH", cfg)

        orig = sys.argv[:]
        sys.argv = ["write_config.py", "--defaults"]
        try:
            wc.main()
        finally:
            sys.argv = orig

        result = json.loads(cfg.read_text())
        assert result["consolidation_min_sessions"] == 10


# ---------------------------------------------------------------------------
# Test: uses get_db_connection, not raw sqlite3.connect
# ---------------------------------------------------------------------------


class TestUsesGetDbConnection:
    def test_uses_get_db_connection(self):
        """consolidation_check must use get_db_connection, not raw sqlite3.connect."""
        import ast
        import inspect

        source = inspect.getsource(cc)
        tree = ast.parse(source)

        for node in ast.walk(tree):
            if isinstance(node, ast.Attribute):
                if (
                    isinstance(node.value, ast.Name)
                    and node.value.id == "sqlite3"
                    and node.attr == "connect"
                ):
                    pytest.fail(
                        "consolidation_check.py calls sqlite3.connect() directly — "
                        "must use get_db_connection() instead"
                    )
