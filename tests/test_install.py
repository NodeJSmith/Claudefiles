"""Tests for install.py core logic."""

import itertools
import json
import os
import subprocess
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

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
        (repo / "skills-impeccable" / "capabilities-impeccable.md").write_text("caps")
        (repo / "skills-memory" / "cm-recall").mkdir(parents=True)
        (repo / "skills-memory" / "cm-recall" / "SKILL.md").write_text("skill")
        (repo / "skills-memory" / "capabilities-memory.md").write_text("caps")
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
        # Capability fragments go to rules/common, not skills/
        assert not (claude_dir / "skills" / "capabilities-impeccable.md").exists()
        assert (
            claude_dir / "rules" / "common" / "capabilities-impeccable.md"
        ).is_symlink()
        # Memory skills NOT installed (deselected)
        assert not (claude_dir / "skills" / "cm-recall").exists()
        assert not (claude_dir / "rules" / "common" / "capabilities-memory.md").exists()

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

    def test_deselected_group_removes_rule_fragments(self, tmp_path: Path) -> None:
        repo = tmp_path / "repo"
        claude_dir = tmp_path / "claude"

        (repo / "skills" / "mine.build").mkdir(parents=True)
        (repo / "skills" / "mine.build" / "SKILL.md").write_text("skill")
        (repo / "skills-impeccable" / "i-audit").mkdir(parents=True)
        (repo / "skills-impeccable" / "i-audit" / "SKILL.md").write_text("skill")
        (repo / "skills-impeccable" / "capabilities-impeccable.md").write_text("caps")
        (repo / "skills-memory" / "cm-recall").mkdir(parents=True)
        (repo / "skills-memory" / "cm-recall" / "SKILL.md").write_text("skill")
        (repo / "skills-memory" / "capabilities-memory.md").write_text("caps")
        (repo / "agents").mkdir()
        (repo / "rules" / "common").mkdir(parents=True)
        (repo / "rules" / "common" / "test.md").write_text("rule")

        rules_common = claude_dir / "rules" / "common"

        # First install with impeccable enabled
        config_v1 = {
            "skills": {"core": True, "impeccable": True, "memory": True},
            "agents": {},
            "hooks": {},
            "packages": {},
        }
        agent_groups = install.discover_agent_groups(repo)
        with (
            patch("install.install_package"),
            patch.object(Path, "home", return_value=tmp_path / "home"),
        ):
            (tmp_path / "home" / ".local" / "bin").mkdir(parents=True)
            install.do_install(
                repo, claude_dir, config_v1, agent_groups, interactive=False
            )

        assert (rules_common / "capabilities-impeccable.md").is_symlink()
        assert (rules_common / "capabilities-memory.md").is_symlink()

        # Re-install with impeccable deselected
        config_v2 = {
            "skills": {"core": True, "impeccable": False, "memory": True},
            "agents": {},
            "hooks": {},
            "packages": {},
        }
        with (
            patch("install.install_package"),
            patch.object(Path, "home", return_value=tmp_path / "home"),
        ):
            install.do_install(
                repo, claude_dir, config_v2, agent_groups, interactive=False
            )

        assert not (rules_common / "capabilities-impeccable.md").exists()
        assert (rules_common / "capabilities-memory.md").is_symlink()
        assert (claude_dir / "skills" / "cm-recall").is_symlink()
        assert not (claude_dir / "skills" / "i-audit").exists()

    def test_deselection_preserves_unowned_rule_fragments(self, tmp_path: Path) -> None:
        repo = tmp_path / "repo"
        claude_dir = tmp_path / "claude"

        (repo / "skills-impeccable" / "i-audit").mkdir(parents=True)
        (repo / "skills-impeccable" / "i-audit" / "SKILL.md").write_text("skill")
        (repo / "skills-impeccable" / "capabilities-impeccable.md").write_text("caps")
        (repo / "skills" / "mine.build").mkdir(parents=True)
        (repo / "skills" / "mine.build" / "SKILL.md").write_text("skill")
        (repo / "agents").mkdir()
        (repo / "rules" / "common").mkdir(parents=True)

        rules_common = claude_dir / "rules" / "common"
        rules_common.mkdir(parents=True)

        # Place an unowned file where capabilities-impeccable.md would go
        other_repo = tmp_path / "other-repo"
        other_repo.mkdir()
        other_source = other_repo / "capabilities-impeccable.md"
        other_source.write_text("other caps")
        (rules_common / "capabilities-impeccable.md").symlink_to(other_source)

        config = {
            "skills": {"core": True, "impeccable": False, "memory": False},
            "agents": {},
            "hooks": {},
            "packages": {},
        }
        agent_groups = install.discover_agent_groups(repo)
        with (
            patch("install.install_package"),
            patch.object(Path, "home", return_value=tmp_path / "home"),
        ):
            (tmp_path / "home" / ".local" / "bin").mkdir(parents=True)
            install.do_install(
                repo, claude_dir, config, agent_groups, interactive=False
            )

        # Unowned fragment must survive deselection
        assert (rules_common / "capabilities-impeccable.md").is_symlink()
        assert (
            rules_common / "capabilities-impeccable.md"
        ).resolve() == other_source.resolve()


# ---------------------------------------------------------------------------
# Package install / uninstall tests
# ---------------------------------------------------------------------------


def _minimal_repo(tmp_path: Path) -> Path:
    """Create a minimal repo structure for do_install."""
    repo = tmp_path / "repo"
    (repo / "skills" / "mine.build").mkdir(parents=True)
    (repo / "skills" / "mine.build" / "SKILL.md").write_text("skill")
    (repo / "agents").mkdir()
    (repo / "rules" / "common").mkdir(parents=True)
    return repo


class TestPackageInstall:
    def test_skips_already_installed(self, tmp_path: Path) -> None:
        repo = _minimal_repo(tmp_path)
        claude_dir = tmp_path / "claude"

        config = {
            "skills": {"core": True},
            "agents": {},
            "hooks": {},
            "packages": {"ado-api": True},
        }
        agent_groups = install.discover_agent_groups(repo)
        mock_install = MagicMock()
        with (
            patch("install.install_package", mock_install),
            patch("install._get_installed_packages", return_value={"ado-api"}),
            patch.object(Path, "home", return_value=tmp_path / "home"),
        ):
            (tmp_path / "home" / ".local" / "bin").mkdir(parents=True)
            install.do_install(
                repo, claude_dir, config, agent_groups, interactive=False
            )

        mock_install.assert_not_called()

    def test_installs_when_not_present(self, tmp_path: Path) -> None:
        repo = _minimal_repo(tmp_path)
        claude_dir = tmp_path / "claude"

        config = {
            "skills": {"core": True},
            "agents": {},
            "hooks": {},
            "packages": {"ado-api": True},
        }
        agent_groups = install.discover_agent_groups(repo)
        mock_install = MagicMock(return_value=(True, ""))
        with (
            patch("install.install_package", mock_install),
            patch("install._get_installed_packages", return_value=set()),
            patch.object(Path, "home", return_value=tmp_path / "home"),
        ):
            (tmp_path / "home" / ".local" / "bin").mkdir(parents=True)
            install.do_install(
                repo, claude_dir, config, agent_groups, interactive=False
            )

        mock_install.assert_called_once_with(repo, "ado-api")

    def test_uninstalls_deselected_package(self, tmp_path: Path) -> None:
        repo = _minimal_repo(tmp_path)
        claude_dir = tmp_path / "claude"

        prev_config = {
            "skills": {"core": True},
            "agents": {},
            "hooks": {},
            "packages": {"ado-api": True},
        }
        new_config = {
            "skills": {"core": True},
            "agents": {},
            "hooks": {},
            "packages": {"ado-api": False},
        }
        agent_groups = install.discover_agent_groups(repo)
        mock_uninstall = MagicMock(return_value=(True, ""))
        with (
            patch("install.install_package"),
            patch("install.uninstall_package", mock_uninstall),
            patch("install._get_installed_packages", return_value=set()),
            patch.object(Path, "home", return_value=tmp_path / "home"),
        ):
            (tmp_path / "home" / ".local" / "bin").mkdir(parents=True)
            install.do_install(
                repo,
                claude_dir,
                new_config,
                agent_groups,
                prev_config=prev_config,
                interactive=False,
            )

        mock_uninstall.assert_called_once_with("ado-api")

    def test_no_uninstall_without_prev_config(self, tmp_path: Path) -> None:
        repo = _minimal_repo(tmp_path)
        claude_dir = tmp_path / "claude"

        config = {
            "skills": {"core": True},
            "agents": {},
            "hooks": {},
            "packages": {"ado-api": False},
        }
        agent_groups = install.discover_agent_groups(repo)
        mock_uninstall = MagicMock()
        with (
            patch("install.install_package"),
            patch("install.uninstall_package", mock_uninstall),
            patch("install._get_installed_packages", return_value=set()),
            patch.object(Path, "home", return_value=tmp_path / "home"),
        ):
            (tmp_path / "home" / ".local" / "bin").mkdir(parents=True)
            install.do_install(
                repo, claude_dir, config, agent_groups, interactive=False
            )

        mock_uninstall.assert_not_called()


# ---------------------------------------------------------------------------
# Worktree detection tests
# ---------------------------------------------------------------------------


class TestIsGitWorktree:
    def test_returns_false_when_git_not_found(self, tmp_path: Path) -> None:
        with patch("install.subprocess.run", side_effect=FileNotFoundError):
            assert install._is_git_worktree(tmp_path) is False

    def test_returns_false_on_timeout(self, tmp_path: Path) -> None:
        with patch(
            "install.subprocess.run", side_effect=subprocess.TimeoutExpired("git", 5)
        ):
            assert install._is_git_worktree(tmp_path) is False

    def test_returns_false_when_git_dir_equals_common_dir(self, tmp_path: Path) -> None:
        results = [
            MagicMock(returncode=0, stdout=".git\n"),
            MagicMock(returncode=0, stdout=".git\n"),
        ]
        with patch("install.subprocess.run", side_effect=results):
            assert install._is_git_worktree(tmp_path) is False

    def test_returns_true_when_dirs_differ(self, tmp_path: Path) -> None:
        results = [
            MagicMock(returncode=0, stdout="/repo/.git/worktrees/branch\n"),
            MagicMock(returncode=0, stdout="/repo/.git\n"),
        ]
        with patch("install.subprocess.run", side_effect=results):
            assert install._is_git_worktree(tmp_path) is True

    def test_returns_false_when_git_fails(self, tmp_path: Path) -> None:
        mock_result = MagicMock()
        mock_result.returncode = 128
        mock_result.stdout = ""
        with patch("install.subprocess.run", return_value=mock_result):
            assert install._is_git_worktree(tmp_path) is False


# ---------------------------------------------------------------------------
# main() non-interactive path tests
# ---------------------------------------------------------------------------


class TestMainNonInteractive:
    """Test main() behavior when stdin is not a TTY."""

    def test_non_interactive_with_saved_config(self, tmp_path: Path) -> None:
        claude_dir = tmp_path / "claude_home"
        claude_dir.mkdir()
        repo = _minimal_repo(tmp_path)

        saved = {
            "skills": {"core": True, "impeccable": False},
            "agents": {},
            "hooks": {},
            "packages": {},
        }
        cfg_path = install.config_path(claude_dir)
        install.save_config(cfg_path, saved)

        mock_do_install = MagicMock(return_value=0)
        with (
            patch("sys.argv", ["install.py"]),
            patch("install._is_git_worktree", return_value=False),
            patch("install.do_install", mock_do_install),
            patch("install.discover_agent_groups", return_value={}),
            patch.dict(os.environ, {"CLAUDE_HOME": str(claude_dir)}),
            patch("install.sys") as mock_sys,
        ):
            mock_sys.stdin.isatty.return_value = False
            mock_sys.exit = sys.exit
            # re-import won't work, so let's call main directly
            # but main reads __file__ — need to patch that too
            with patch.object(install, "__file__", str(repo / "install.py")):
                result = install.main()

        assert result == 0
        mock_do_install.assert_called_once()
        call_config = mock_do_install.call_args[0][2]
        assert call_config["skills"]["core"] is True
        assert call_config["skills"]["impeccable"] is False

    def test_non_interactive_no_saved_config_installs_all(self, tmp_path: Path) -> None:
        claude_dir = tmp_path / "claude_home"
        claude_dir.mkdir()
        repo = _minimal_repo(tmp_path)

        mock_do_install = MagicMock(return_value=0)
        with (
            patch("sys.argv", ["install.py"]),
            patch("install._is_git_worktree", return_value=False),
            patch("install.do_install", mock_do_install),
            patch("install.discover_agent_groups", return_value={"core": ["r.md"]}),
            patch.dict(os.environ, {"CLAUDE_HOME": str(claude_dir)}),
            patch("install.sys") as mock_sys,
            patch("install.save_config"),
        ):
            mock_sys.stdin.isatty.return_value = False
            mock_sys.exit = sys.exit
            with patch.object(install, "__file__", str(repo / "install.py")):
                result = install.main()

        assert result == 0
        mock_do_install.assert_called_once()
        call_config = mock_do_install.call_args[0][2]
        # All groups should be True
        for group_key in install.SKILL_GROUPS:
            assert call_config["skills"][group_key] is True
        assert call_config["agents"]["core"] is True

    def test_non_interactive_reconfigure_warns(self, tmp_path: Path, capsys) -> None:
        claude_dir = tmp_path / "claude_home"
        claude_dir.mkdir()
        repo = _minimal_repo(tmp_path)

        saved = {
            "skills": {"core": True},
            "agents": {},
            "hooks": {},
            "packages": {},
        }
        cfg_path = install.config_path(claude_dir)
        install.save_config(cfg_path, saved)

        mock_do_install = MagicMock(return_value=0)
        with (
            patch("sys.argv", ["install.py", "--reconfigure"]),
            patch("install._is_git_worktree", return_value=False),
            patch("install.do_install", mock_do_install),
            patch("install.discover_agent_groups", return_value={}),
            patch.dict(os.environ, {"CLAUDE_HOME": str(claude_dir)}),
            patch("install.sys") as mock_sys,
        ):
            mock_sys.stdin.isatty.return_value = False
            mock_sys.exit = sys.exit
            with patch.object(install, "__file__", str(repo / "install.py")):
                result = install.main()

        assert result == 0
        captured = capsys.readouterr()
        assert "--reconfigure has no effect in non-interactive mode" in captured.out
        call_config = mock_do_install.call_args[0][2]
        assert call_config["skills"]["core"] is True


# ---------------------------------------------------------------------------
# ConfigLock tests
# ---------------------------------------------------------------------------


class TestConfigLock:
    def test_timeout_raises_runtime_error(self, tmp_path: Path) -> None:
        cfg_path = tmp_path / "config.json"
        lock = install.ConfigLock(cfg_path)

        # Simulate flock always failing + deadline already passed
        with (
            patch("install.fcntl.flock", side_effect=OSError("locked")),
            patch(
                "install.time.monotonic",
                side_effect=itertools.chain([100.0], itertools.repeat(111.0)),
            ),
            patch("install.time.sleep"),
        ):
            with pytest.raises(RuntimeError, match="Could not acquire lock"):
                lock.__enter__()

    def test_acquires_and_releases(self, tmp_path: Path) -> None:
        cfg_path = tmp_path / "config.json"
        with install.ConfigLock(cfg_path) as lock:
            assert lock._fd is not None
            lock_file = str(cfg_path) + ".lock"
            assert os.path.exists(lock_file)
        assert lock._fd is None


# ---------------------------------------------------------------------------
# save_config exception cleanup tests
# ---------------------------------------------------------------------------


class TestSaveConfigException:
    def test_temp_file_removed_on_write_failure(self, tmp_path: Path) -> None:
        cfg_path = tmp_path / "config.json"
        cfg_path.write_text("original")

        with (
            patch("install.os.write", side_effect=OSError("disk full")),
            pytest.raises(OSError, match="disk full"),
        ):
            install.save_config(cfg_path, {"skills": {"core": True}})

        # Original file untouched
        assert cfg_path.read_text() == "original"
        # No leftover .tmp files
        tmp_files = list(tmp_path.glob("*.tmp"))
        assert tmp_files == []

    def test_temp_file_removed_on_replace_failure(self, tmp_path: Path) -> None:
        cfg_path = tmp_path / "config.json"
        cfg_path.write_text("original")

        with (
            patch("install.os.replace", side_effect=OSError("permission denied")),
            pytest.raises(OSError, match="permission denied"),
        ):
            install.save_config(cfg_path, {"skills": {"core": True}})

        assert cfg_path.read_text() == "original"
        tmp_files = list(tmp_path.glob("*.tmp"))
        assert tmp_files == []


# ---------------------------------------------------------------------------
# Malformed frontmatter tests
# ---------------------------------------------------------------------------


class TestParseAgentGroup:
    def test_no_frontmatter(self, tmp_path: Path) -> None:
        f = tmp_path / "agent.md"
        f.write_text("Just a plain file with no frontmatter.")
        assert install._parse_agent_group(f) is None

    def test_no_closing_dashes(self, tmp_path: Path) -> None:
        f = tmp_path / "agent.md"
        f.write_text("---\nname: agent\ngroup: core\n")
        assert install._parse_agent_group(f) is None

    def test_empty_group_value(self, tmp_path: Path) -> None:
        f = tmp_path / "agent.md"
        f.write_text("---\nname: agent\ngroup: \n---\n")
        assert install._parse_agent_group(f) == ""

    def test_no_group_key(self, tmp_path: Path) -> None:
        f = tmp_path / "agent.md"
        f.write_text("---\nname: agent\ndescription: something\n---\n")
        assert install._parse_agent_group(f) is None

    def test_unreadable_file(self, tmp_path: Path) -> None:
        f = tmp_path / "agent.md"
        f.write_text("---\ngroup: core\n---\n")
        with patch.object(Path, "read_text", side_effect=OSError("perm")):
            assert install._parse_agent_group(f) is None


class TestDiscoverAgentGroupsEdgeCases:
    def test_empty_group_is_filtered_out(self, tmp_path: Path) -> None:
        agents = tmp_path / "agents"
        agents.mkdir()
        (agents / "a.md").write_text("---\nname: a\ngroup: \n---\n")
        groups = install.discover_agent_groups(tmp_path)
        assert groups == {}

    def test_mixed_valid_and_malformed(self, tmp_path: Path) -> None:
        agents = tmp_path / "agents"
        agents.mkdir()
        (agents / "good.md").write_text("---\nname: good\ngroup: core\n---\n")
        (agents / "no-close.md").write_text("---\nname: x\ngroup: core\n")
        (agents / "no-fm.md").write_text("Just text.")
        (agents / "no-group.md").write_text("---\nname: y\n---\n")
        groups = install.discover_agent_groups(tmp_path)
        assert groups == {"core": ["good.md"]}

    def test_no_agents_dir(self, tmp_path: Path) -> None:
        assert install.discover_agent_groups(tmp_path) == {}
