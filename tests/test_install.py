"""Tests for install.py core logic."""

import json
import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import install  # noqa: E402


# ---------------------------------------------------------------------------
# Config tests
# ---------------------------------------------------------------------------


class TestConfigLoadSave:
    def test_roundtrip(self, tmp_path: Path) -> None:
        cfg_path = tmp_path / install.CONFIG_FILENAME
        data = {
            "skills": {"core": True, "impeccable": False},
            "agents": {"core": True},
        }
        install.save_config(cfg_path, data)
        loaded = install.load_config(cfg_path)
        assert loaded is not None
        assert loaded["skills"] == {"core": True, "impeccable": False}
        assert loaded["agents"] == {"core": True}
        assert loaded["version"] == install.CONFIG_VERSION

    def test_corrupt_recovery(self, tmp_path: Path) -> None:
        cfg_path = tmp_path / install.CONFIG_FILENAME
        cfg_path.write_text("{{not json!!")
        assert install.load_config(cfg_path) is None

    def test_wrong_version(self, tmp_path: Path) -> None:
        cfg_path = tmp_path / install.CONFIG_FILENAME
        cfg_path.write_text(json.dumps({"version": 999}))
        assert install.load_config(cfg_path) is None

    def test_missing_file(self, tmp_path: Path) -> None:
        cfg_path = tmp_path / install.CONFIG_FILENAME
        assert install.load_config(cfg_path) is None

    def test_atomic_write(self, tmp_path: Path) -> None:
        cfg_path = tmp_path / install.CONFIG_FILENAME
        cfg_path.write_text("original content")
        install.save_config(cfg_path, {"skills": {"core": True}})
        loaded = install.load_config(cfg_path)
        assert loaded is not None
        assert loaded["skills"]["core"] is True


# ---------------------------------------------------------------------------
# Ownership guard tests
# ---------------------------------------------------------------------------


class TestOwnershipGuard:
    def test_owned_symlink(self, tmp_path: Path) -> None:
        repo = tmp_path / "repo"
        repo.mkdir()
        source = repo / "skill-a"
        source.mkdir()
        link = tmp_path / "target" / "skill-a"
        link.parent.mkdir()
        link.symlink_to(source)
        assert install.is_owned_by(link, repo) is True

    def test_unowned_symlink(self, tmp_path: Path) -> None:
        repo = tmp_path / "repo"
        repo.mkdir()
        other = tmp_path / "other-repo"
        other.mkdir()
        source = other / "skill-b"
        source.mkdir()
        link = tmp_path / "target" / "skill-b"
        link.parent.mkdir()
        link.symlink_to(source)
        assert install.is_owned_by(link, repo) is False

    def test_prefix_collision(self, tmp_path: Path) -> None:
        """Claudefiles-backup/ should NOT be treated as owned by Claudefiles/."""
        repo = tmp_path / "Claudefiles"
        repo.mkdir()
        backup = tmp_path / "Claudefiles-backup"
        backup.mkdir()
        source = backup / "skill-c"
        source.mkdir()
        link = tmp_path / "target" / "skill-c"
        link.parent.mkdir()
        link.symlink_to(source)
        assert install.is_owned_by(link, repo) is False


# ---------------------------------------------------------------------------
# Stale symlink tests
# ---------------------------------------------------------------------------


class TestStaleSymlinks:
    def test_detects_stale(self, tmp_path: Path) -> None:
        repo = tmp_path / "repo"
        repo.mkdir()
        dest = tmp_path / "dest"
        dest.mkdir()
        source = repo / "old-skill"
        source.mkdir()
        link = dest / "old-skill"
        link.symlink_to(source)
        source.rmdir()
        stale = install.find_stale_symlinks(dest, repo)
        assert len(stale) == 1
        assert stale[0].name == "old-skill"

    def test_ignores_valid(self, tmp_path: Path) -> None:
        repo = tmp_path / "repo"
        repo.mkdir()
        dest = tmp_path / "dest"
        dest.mkdir()
        source = repo / "good-skill"
        source.mkdir()
        link = dest / "good-skill"
        link.symlink_to(source)
        assert install.find_stale_symlinks(dest, repo) == []

    def test_ignores_unowned_stale(self, tmp_path: Path) -> None:
        repo = tmp_path / "repo"
        repo.mkdir()
        other = tmp_path / "other"
        other.mkdir()
        dest = tmp_path / "dest"
        dest.mkdir()
        source = other / "ext-skill"
        source.mkdir()
        link = dest / "ext-skill"
        link.symlink_to(source)
        source.rmdir()
        assert install.find_stale_symlinks(dest, repo) == []


# ---------------------------------------------------------------------------
# Symlink creation tests
# ---------------------------------------------------------------------------


class TestSymlinkCreation:
    def test_dir_level(self, tmp_path: Path) -> None:
        src = tmp_path / "src"
        src.mkdir()
        (src / "a").mkdir()
        (src / "b").mkdir()
        dest = tmp_path / "dest"
        count = install.create_symlinks_dir_level(src, dest)
        assert count == 2
        assert (dest / "a").is_symlink()
        assert (dest / "b").is_symlink()
        assert (dest / "a").resolve() == (src / "a").resolve()

    def test_file_level(self, tmp_path: Path) -> None:
        src = tmp_path / "src"
        (src / "common").mkdir(parents=True)
        (src / "common" / "file1.md").write_text("x")
        (src / "common" / "file2.md").write_text("y")
        dest = tmp_path / "dest"
        count = install.create_symlinks_file_level(src, dest)
        assert count == 2
        assert (dest / "common" / "file1.md").is_symlink()
        assert (dest / "common" / "file2.md").is_symlink()

    def test_replaces_existing_symlink(self, tmp_path: Path) -> None:
        src = tmp_path / "src"
        src.mkdir()
        (src / "a").mkdir()
        dest = tmp_path / "dest"
        dest.mkdir()
        old_target = tmp_path / "old"
        old_target.mkdir()
        (dest / "a").symlink_to(old_target)
        install.create_symlinks_dir_level(src, dest)
        assert (dest / "a").resolve() == (src / "a").resolve()

    def test_collects_shadowed(self, tmp_path: Path) -> None:
        src = tmp_path / "src"
        src.mkdir()
        (src / "a").mkdir()
        dest = tmp_path / "dest"
        dest.mkdir()
        (dest / "a").mkdir()
        shadowed: list[tuple[Path, Path]] = []
        install.create_symlinks_dir_level(src, dest, shadowed_out=shadowed)
        assert len(shadowed) == 1
        assert shadowed[0][0] == dest / "a"

    def test_skips_dotfiles(self, tmp_path: Path) -> None:
        src = tmp_path / "src"
        src.mkdir()
        (src / ".hidden").mkdir()
        (src / "visible").mkdir()
        dest = tmp_path / "dest"
        count = install.create_symlinks_dir_level(src, dest)
        assert count == 1
        assert not (dest / ".hidden").exists()


# ---------------------------------------------------------------------------
# Deselection cleanup tests
# ---------------------------------------------------------------------------


class TestDeselectionCleanup:
    def test_removes_owned(self, tmp_path: Path) -> None:
        repo = tmp_path / "repo"
        repo.mkdir()
        source = repo / "my-skill"
        source.mkdir()
        dest = tmp_path / "dest"
        dest.mkdir()
        (dest / "my-skill").symlink_to(source)
        removed = install.remove_owned_symlinks(dest, repo)
        assert removed == 1
        assert not (dest / "my-skill").exists()

    def test_preserves_unowned(self, tmp_path: Path) -> None:
        repo = tmp_path / "repo"
        repo.mkdir()
        other = tmp_path / "other"
        other.mkdir()
        ext_source = other / "ext-skill"
        ext_source.mkdir()
        dest = tmp_path / "dest"
        dest.mkdir()
        (dest / "ext-skill").symlink_to(ext_source)
        removed = install.remove_owned_symlinks(dest, repo)
        assert removed == 0
        assert (dest / "ext-skill").is_symlink()

    def test_filters_by_name(self, tmp_path: Path) -> None:
        repo = tmp_path / "repo"
        repo.mkdir()
        (repo / "a").mkdir()
        (repo / "b").mkdir()
        dest = tmp_path / "dest"
        dest.mkdir()
        (dest / "a").symlink_to(repo / "a")
        (dest / "b").symlink_to(repo / "b")
        removed = install.remove_owned_symlinks(dest, repo, names=["a"])
        assert removed == 1
        assert not (dest / "a").exists()
        assert (dest / "b").is_symlink()


# ---------------------------------------------------------------------------
# Smart diff tests
# ---------------------------------------------------------------------------


class TestSmartDiff:
    def test_new_group_detected(self) -> None:
        saved = {"skills": {"core": True}}
        new = install.find_new_groups(saved, "skills", ["core", "impeccable"])
        assert new == ["impeccable"]

    def test_no_changes(self) -> None:
        saved = {"skills": {"core": True, "impeccable": False}}
        new = install.find_new_groups(saved, "skills", ["core", "impeccable"])
        assert new == []

    def test_missing_section(self) -> None:
        saved = {}
        new = install.find_new_groups(saved, "skills", ["core", "impeccable"])
        assert new == ["core", "impeccable"]


# ---------------------------------------------------------------------------
# Agent group discovery tests
# ---------------------------------------------------------------------------


class TestAgentDiscovery:
    def test_discovers_groups(self, tmp_path: Path) -> None:
        agents = tmp_path / "agents"
        agents.mkdir()
        (agents / "reviewer.md").write_text("---\nname: reviewer\ngroup: core\n---\n")
        (agents / "frontend.md").write_text(
            "---\nname: frontend\ngroup: engineering\n---\n"
        )
        (agents / "auditor.md").write_text("---\nname: auditor\ngroup: memory\n---\n")
        groups = install.discover_agent_groups(tmp_path)
        assert sorted(groups.keys()) == ["core", "engineering", "memory"]
        assert groups["core"] == ["reviewer.md"]

    def test_skips_no_group(self, tmp_path: Path) -> None:
        agents = tmp_path / "agents"
        agents.mkdir()
        (agents / "orphan.md").write_text("---\nname: orphan\n---\n")
        groups = install.discover_agent_groups(tmp_path)
        assert groups == {}


# ---------------------------------------------------------------------------
# Integration test
# ---------------------------------------------------------------------------


class TestFullInstallFlow:
    def test_install_creates_correct_symlinks(self, tmp_path: Path) -> None:
        repo = tmp_path / "repo"
        claude_dir = tmp_path / "claude"

        # Build mock repo
        (repo / "skills" / "mine.build").mkdir(parents=True)
        (repo / "skills" / "mine.build" / "SKILL.md").write_text("skill")
        (repo / "skills-impeccable" / "i-audit").mkdir(parents=True)
        (repo / "skills-impeccable" / "i-audit" / "SKILL.md").write_text("skill")
        (repo / "skills-memory" / "cm-recall").mkdir(parents=True)
        (repo / "skills-memory" / "cm-recall" / "SKILL.md").write_text("skill")
        (repo / "agents").mkdir()
        (repo / "agents" / "reviewer.md").write_text(
            "---\nname: reviewer\ngroup: core\n---\n"
        )
        (repo / "commands" / "test-cmd").mkdir(parents=True)
        (repo / "scripts" / "hooks").mkdir(parents=True)
        (repo / "scripts" / "hooks" / "pytest-guard.sh").write_text("#!/bin/bash")
        (repo / "scripts" / "hooks" / "sudo-poll.sh").write_text("#!/bin/bash")
        (repo / "rules" / "common").mkdir(parents=True)
        (repo / "rules" / "common" / "test.md").write_text("rule")

        config = {
            "skills": {"core": True, "impeccable": True, "memory": False},
            "agents": {"core": True},
            "hooks": {"pytest": True, "sudo": False, "tmux": False},
            "packages": {},
        }

        agent_groups = install.discover_agent_groups(repo)
        with patch("install.install_package"):
            with patch.object(Path, "home", return_value=tmp_path / "home"):
                (tmp_path / "home" / ".local" / "bin").mkdir(parents=True)
                errors = install.do_install(
                    repo, claude_dir, config, agent_groups, interactive=False
                )

        assert errors == 0

        # Core skills installed
        assert (claude_dir / "skills" / "mine.build").is_symlink()
        # Impeccable skills installed
        assert (claude_dir / "skills" / "i-audit").is_symlink()
        # Memory skills NOT installed (deselected)
        assert not (claude_dir / "skills" / "cm-recall").exists()

        # Agent installed
        assert (claude_dir / "agents" / "reviewer.md").is_symlink()

        # Commands always installed
        assert (claude_dir / "commands" / "test-cmd").is_symlink()

        # Selected hooks installed
        assert (claude_dir / "scripts" / "hooks" / "pytest-guard.sh").is_symlink()
        # Deselected hooks not installed
        assert not (claude_dir / "scripts" / "hooks" / "sudo-poll.sh").exists()

        # Rules always installed (file-level)
        assert (claude_dir / "rules" / "common" / "test.md").is_symlink()
