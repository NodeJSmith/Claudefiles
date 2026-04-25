"""Tests for the shared project_ops module."""

import shutil
import tempfile
from pathlib import Path

from claude_memory.project_ops import upsert_project

FIXTURE_DIR = Path(__file__).parent / "fixtures"


class TestUpsertProjectWithCwd:
    """Verify upsert_project with direct cwd creates a project correctly."""

    def test_upsert_project_with_cwd(self, memory_db):
        """upsert_project should create a project using the provided cwd path."""

        cursor = memory_db.cursor()
        project_id = upsert_project(
            cursor, "-home-user-myrepo", cwd="/home/user/myrepo"
        )
        memory_db.commit()

        assert project_id is not None
        assert isinstance(project_id, int)

        cursor.execute("SELECT path, name FROM projects WHERE id = ?", (project_id,))
        row = cursor.fetchone()
        assert row is not None
        assert row[0] == "/home/user/myrepo", "Path should match provided cwd"
        assert row[1] == "myrepo", "Name should be derived from path basename"

    def test_upsert_project_with_cwd_idempotent(self, memory_db):
        """Calling upsert_project twice with same key returns same project_id."""

        cursor = memory_db.cursor()
        id1 = upsert_project(cursor, "-home-user-myrepo", cwd="/home/user/myrepo")
        memory_db.commit()
        id2 = upsert_project(cursor, "-home-user-myrepo", cwd="/home/user/myrepo")
        memory_db.commit()

        assert id1 == id2, "Idempotent call should return same project_id"

        cursor.execute(
            "SELECT COUNT(*) FROM projects WHERE key = ?", ("-home-user-myrepo",)
        )
        assert cursor.fetchone()[0] == 1, "Should have exactly one project row"

    def test_upsert_project_updates_path_when_better_data(self, memory_db):
        """If project exists with stale path, upsert updates it with cwd."""

        cursor = memory_db.cursor()
        # Insert with lossy hyphen path
        cursor.execute(
            "INSERT INTO projects (path, key, name) VALUES (?, ?, ?)",
            ("/home/user/my-repo", "-home-user-my-repo", "my-repo"),
        )
        memory_db.commit()

        # Upsert with real cwd (same key but different path from cwd metadata)
        project_id = upsert_project(
            cursor, "-home-user-my-repo", cwd="/home/user/my-repo"
        )
        memory_db.commit()

        assert project_id is not None
        cursor.execute("SELECT path FROM projects WHERE id = ?", (project_id,))
        row = cursor.fetchone()
        # Path should be updated to the cwd value
        assert row[0] == "/home/user/my-repo"

    def test_upsert_project_with_worktree_cwd(self, memory_db):
        """Worktree cwd suffix should be normalized away."""

        cursor = memory_db.cursor()
        project_id = upsert_project(
            cursor,
            "-home-user-myrepo",
            cwd="/home/user/myrepo/.claude/worktrees/my-feature",
        )
        memory_db.commit()

        cursor.execute("SELECT path FROM projects WHERE id = ?", (project_id,))
        row = cursor.fetchone()
        # normalize_cwd strips the worktree suffix
        assert row[0] == "/home/user/myrepo", (
            "Worktree suffix should be stripped from cwd"
        )


class TestUpsertProjectProbesJsonl:
    """Verify upsert_project uses JSONL-probe strategy when cwd is absent."""

    def test_upsert_project_probes_jsonl(self, memory_db):
        """When project_dir is given (no cwd), probe first JSONL for cwd metadata."""

        # The fixture has cwd metadata in it; let's use a real fixture directory
        with tempfile.TemporaryDirectory() as tmpdir:
            project_dir = Path(tmpdir) / "-home-user-node-banana"
            project_dir.mkdir()

            # linear_3_exchange.jsonl has cwd="/Users/samarthgupta/repos/forks/node-banana"
            shutil.copy(
                FIXTURE_DIR / "linear_3_exchange.jsonl", project_dir / "sess.jsonl"
            )

            cursor = memory_db.cursor()
            # Use the encoded directory name as project_key, no cwd
            project_key = "-home-user-node-banana"
            project_id = upsert_project(cursor, project_key, project_dir=project_dir)
            memory_db.commit()

        assert project_id is not None

        cursor.execute("SELECT path, name FROM projects WHERE id = ?", (project_id,))
        row = cursor.fetchone()
        assert row is not None
        # path should come from the JSONL cwd (probed), not lossy hyphen reconstruction
        # linear_3_exchange.jsonl has cwd="/Users/samarthgupta/repos/forks/node-banana"
        assert row[0] == "/Users/samarthgupta/repos/forks/node-banana", (
            "Path should come from probed JSONL cwd, not lossy hyphen reconstruction"
        )
        assert row[1] == "node-banana"

    def test_upsert_project_falls_back_to_key_when_no_jsonl(self, memory_db):
        """When project_dir has no JSONL, fall back to lossy hyphen reconstruction."""

        with tempfile.TemporaryDirectory() as tmpdir:
            project_dir = Path(tmpdir) / "-home-user-myproject"
            project_dir.mkdir()

            cursor = memory_db.cursor()
            project_id = upsert_project(
                cursor, "-home-user-myproject", project_dir=project_dir
            )
            memory_db.commit()

        assert project_id is not None

        cursor.execute("SELECT path, name FROM projects WHERE id = ?", (project_id,))
        row = cursor.fetchone()
        assert row is not None
        # Falls back to parse_project_key (lossy) when no JSONL available
        assert "myproject" in row[0], (
            "Fallback path should contain project name from key reconstruction"
        )
