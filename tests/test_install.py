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
            "bundles": {"frontend": True, "cli": False},
        }
        install.save_config(cfg_path, data)
        loaded = install.load_config(cfg_path)
        assert loaded is not None
        assert loaded["bundles"] == {"frontend": True, "cli": False}
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
        install.save_config(cfg_path, {"bundles": {"frontend": True}})
        loaded = install.load_config(cfg_path)
        assert loaded is not None
        assert loaded["bundles"]["frontend"] is True


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

    def test_create_symlink_single(self, tmp_path: Path) -> None:
        repo = tmp_path / "repo"
        repo.mkdir()
        source = repo / "my-skill"
        source.mkdir()
        dest = tmp_path / "dest" / "my-skill"
        result = install.create_symlink(source, dest, repo_dir=repo)
        assert result is True
        assert dest.is_symlink()
        assert dest.resolve() == source.resolve()

    def test_create_symlink_skips_unowned_existing(self, tmp_path: Path) -> None:
        repo = tmp_path / "repo"
        repo.mkdir()
        other = tmp_path / "other"
        other.mkdir()
        source_other = other / "my-skill"
        source_other.mkdir()
        dest = tmp_path / "dest" / "my-skill"
        dest.parent.mkdir()
        dest.symlink_to(source_other)

        new_source = repo / "my-skill"
        new_source.mkdir()
        shadowed: list[tuple[Path, Path]] = []
        result = install.create_symlink(
            new_source, dest, repo_dir=repo, shadowed_out=shadowed
        )
        assert result is False
        assert len(shadowed) == 1
        # Original symlink untouched
        assert dest.resolve() == source_other.resolve()

    def test_create_symlink_replaces_owned(self, tmp_path: Path) -> None:
        repo = tmp_path / "repo"
        repo.mkdir()
        old_source = repo / "old-skill"
        old_source.mkdir()
        new_source = repo / "new-skill"
        new_source.mkdir()
        dest = tmp_path / "dest" / "my-skill"
        dest.parent.mkdir()
        dest.symlink_to(old_source)

        result = install.create_symlink(new_source, dest, repo_dir=repo)
        assert result is True
        assert dest.resolve() == new_source.resolve()


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
        saved = {"bundles": {"frontend": True}}
        new = install.find_new_groups(saved, "bundles", ["frontend", "cli"])
        assert new == ["cli"]

    def test_no_changes(self) -> None:
        saved = {"bundles": {"frontend": True, "cli": False}}
        new = install.find_new_groups(saved, "bundles", ["frontend", "cli"])
        assert new == []

    def test_missing_section(self) -> None:
        saved = {}
        new = install.find_new_groups(saved, "bundles", ["frontend", "cli"])
        assert new == ["frontend", "cli"]


# ---------------------------------------------------------------------------
# Bundle data model tests
# ---------------------------------------------------------------------------


class TestBundleModel:
    def test_base_bundle_always_installed(self, tmp_path: Path) -> None:
        """Base bundle must have always_installed=True."""
        _setup_minimal_repo(tmp_path)
        bundles = install.get_bundles(tmp_path)
        assert "base" in bundles
        assert bundles["base"].always_installed is True

    def test_optional_bundles_not_always_installed(self, tmp_path: Path) -> None:
        """Optional bundles must have always_installed=False."""
        _setup_minimal_repo(tmp_path)
        opt = install.optional_bundles(tmp_path)
        assert "base" not in opt
        for key, bundle in opt.items():
            assert bundle.always_installed is False, (
                f"{key} should not be always_installed"
            )

    def test_five_optional_bundles(self, tmp_path: Path) -> None:
        """Exactly 5 optional bundles."""
        _setup_minimal_repo(tmp_path)
        opt = install.optional_bundles(tmp_path)
        assert set(opt.keys()) == {
            "frontend",
            "cli",
            "memory",
            "engineering",
            "extra-agents",
        }

    def test_base_agents(self, tmp_path: Path) -> None:
        """Base bundle has exactly 8 agents from FR#1."""
        _setup_minimal_repo(tmp_path)
        bundles = install.get_bundles(tmp_path)
        base = bundles["base"]
        assert set(base.agents) == {
            "code-reviewer",
            "integration-reviewer",
            "wtf-reviewer",
            "researcher",
            "llm-checker",
            "lazy-checker",
            "nitpicker",
            "issue-refiner",
        }

    def test_base_packages(self, tmp_path: Path) -> None:
        """Base bundle has spec-helper and merge-settings packages."""
        _setup_minimal_repo(tmp_path)
        bundles = install.get_bundles(tmp_path)
        assert set(bundles["base"].packages) == {"spec-helper", "merge-settings"}

    def test_memory_bundle_has_claude_memory(self, tmp_path: Path) -> None:
        _setup_minimal_repo(tmp_path)
        bundles = install.get_bundles(tmp_path)
        assert "claude-memory" in bundles["memory"].packages

    def test_memory_capabilities_file(self, tmp_path: Path) -> None:
        _setup_minimal_repo(tmp_path)
        bundles = install.get_bundles(tmp_path)
        assert "capabilities-memory.md" in bundles["memory"].capabilities_files

    def test_frontend_capabilities_file(self, tmp_path: Path) -> None:
        _setup_minimal_repo(tmp_path)
        bundles = install.get_bundles(tmp_path)
        assert "capabilities-impeccable.md" in bundles["frontend"].capabilities_files

    def test_cli_capabilities_file(self, tmp_path: Path) -> None:
        _setup_minimal_repo(tmp_path)
        bundles = install.get_bundles(tmp_path)
        assert "capabilities-cli.md" in bundles["cli"].capabilities_files

    def test_base_excludes_mine_wp(self, tmp_path: Path) -> None:
        """mine.wp must NOT be in the base bundle."""
        # Create a skills dir with mine.wp and another skill
        skills_dir = tmp_path / "skills"
        (skills_dir / "mine.build").mkdir(parents=True)
        (skills_dir / "mine.wp").mkdir(parents=True)
        bundles = install.get_bundles(tmp_path)
        assert "mine.wp" not in bundles["base"].skills
        assert "mine.build" in bundles["base"].skills


# ---------------------------------------------------------------------------
# find_skill_source tests
# ---------------------------------------------------------------------------


class TestFindSkillSource:
    def test_finds_in_skills(self, tmp_path: Path) -> None:
        (tmp_path / "skills" / "mine.build").mkdir(parents=True)
        result = install.find_skill_source("mine.build", tmp_path)
        assert result == tmp_path / "skills" / "mine.build"

    def test_finds_in_skills_impeccable(self, tmp_path: Path) -> None:
        (tmp_path / "skills-impeccable" / "i-audit").mkdir(parents=True)
        result = install.find_skill_source("i-audit", tmp_path)
        assert result == tmp_path / "skills-impeccable" / "i-audit"

    def test_finds_in_skills_cli(self, tmp_path: Path) -> None:
        (tmp_path / "skills-cli" / "cli-harden").mkdir(parents=True)
        result = install.find_skill_source("cli-harden", tmp_path)
        assert result == tmp_path / "skills-cli" / "cli-harden"

    def test_finds_in_skills_memory(self, tmp_path: Path) -> None:
        (tmp_path / "skills-memory" / "cm-recall-conversations").mkdir(parents=True)
        result = install.find_skill_source("cm-recall-conversations", tmp_path)
        assert result == tmp_path / "skills-memory" / "cm-recall-conversations"

    def test_raises_when_not_found(self, tmp_path: Path) -> None:
        with pytest.raises(FileNotFoundError, match="Skill not found: nonexistent"):
            install.find_skill_source("nonexistent", tmp_path)

    def test_prefers_skills_over_others(self, tmp_path: Path) -> None:
        """skills/ is checked first in SKILL_DIRS order."""
        (tmp_path / "skills" / "mine.build").mkdir(parents=True)
        (tmp_path / "skills-impeccable" / "mine.build").mkdir(parents=True)
        result = install.find_skill_source("mine.build", tmp_path)
        assert result == tmp_path / "skills" / "mine.build"


# ---------------------------------------------------------------------------
# Bundle dependency completeness
# ---------------------------------------------------------------------------


class TestBundleDependencyCompleteness:
    def test_all_base_skills_resolve(self) -> None:
        """Every skill in the base bundle must exist in the actual repo."""
        repo_dir = Path(__file__).resolve().parent.parent
        # Reset cache to use actual repo
        install._BUNDLES_CACHE = None
        bundles = install.get_bundles(repo_dir)
        base = bundles["base"]
        missing = []
        for skill_name in base.skills:
            try:
                install.find_skill_source(skill_name, repo_dir)
            except FileNotFoundError:
                missing.append(skill_name)
        assert missing == [], f"Missing skills from base bundle: {missing}"

    def test_all_optional_skills_resolve(self) -> None:
        """Every skill in every optional bundle must exist in the actual repo."""
        repo_dir = Path(__file__).resolve().parent.parent
        install._BUNDLES_CACHE = None
        opt = install.optional_bundles(repo_dir)
        missing = []
        for bundle_key, bundle in opt.items():
            for skill_name in bundle.skills:
                try:
                    install.find_skill_source(skill_name, repo_dir)
                except FileNotFoundError:
                    missing.append(f"{bundle_key}/{skill_name}")
        assert missing == [], f"Missing skills from optional bundles: {missing}"

    def test_mine_wp_not_in_base(self) -> None:
        """mine.wp must not be in base bundle (deprecated)."""
        repo_dir = Path(__file__).resolve().parent.parent
        install._BUNDLES_CACHE = None
        bundles = install.get_bundles(repo_dir)
        assert "mine.wp" not in bundles["base"].skills


# ---------------------------------------------------------------------------
# Integration test: full install flow (bundle-based)
# ---------------------------------------------------------------------------


def _setup_minimal_repo(path: Path) -> None:
    """Create a minimal repo directory structure for testing."""
    # Clear bundle cache so tests use this path
    install._BUNDLES_CACHE = None
    install._BUNDLES_REPO_DIR = None

    (path / "skills" / "mine.build").mkdir(parents=True)
    (path / "skills" / "mine.build" / "SKILL.md").write_text("skill")
    (path / "agents").mkdir(parents=True)
    (path / "rules" / "common").mkdir(parents=True)
    (path / "rules" / "common" / "test.md").write_text("rule")


def _setup_full_repo(path: Path) -> None:
    """Create a repo with skills, agents, hooks, etc. for integration tests."""
    install._BUNDLES_CACHE = None
    install._BUNDLES_REPO_DIR = None

    # Base skills
    (path / "skills" / "mine.build").mkdir(parents=True)
    (path / "skills" / "mine.build" / "SKILL.md").write_text("skill")
    # Frontend skills
    (path / "skills-impeccable" / "i-audit").mkdir(parents=True)
    (path / "skills-impeccable" / "i-audit" / "SKILL.md").write_text("skill")
    (path / "skills-impeccable" / "capabilities-impeccable.md").write_text("caps")
    # Memory skills
    (path / "skills-memory" / "cm-recall-conversations").mkdir(parents=True)
    (path / "skills-memory" / "cm-recall-conversations" / "SKILL.md").write_text(
        "skill"
    )
    (path / "skills-memory" / "capabilities-memory.md").write_text("caps")
    # CLI skills
    (path / "skills-cli" / "cli-harden").mkdir(parents=True)
    (path / "skills-cli" / "cli-harden" / "SKILL.md").write_text("skill")
    (path / "skills-cli" / "capabilities-cli.md").write_text("caps")
    # Agents
    (path / "agents").mkdir(parents=True)
    for name in [
        "code-reviewer",
        "integration-reviewer",
        "wtf-reviewer",
        "researcher",
        "llm-checker",
        "lazy-checker",
        "nitpicker",
        "issue-refiner",
        "cm-memory-auditor",
        "cm-signal-discoverer",
        "engineering-backend-developer",
        "engineering-data-engineer",
        "engineering-frontend-developer",
        "engineering-sre",
        "engineering-technical-writer",
        "testing-reality-checker",
        "architect",
        "planner",
        "qa-specialist",
        "visual-diff",
    ]:
        (path / "agents" / f"{name}.md").write_text(f"---\nname: {name}\n---\n")
    # Hooks
    (path / "scripts" / "hooks").mkdir(parents=True)
    (path / "scripts" / "hooks" / "pytest-guard.sh").write_text("#!/bin/bash")
    (path / "scripts" / "hooks" / "sudo-poll.sh").write_text("#!/bin/bash")
    # Rules
    (path / "rules" / "common").mkdir(parents=True)
    (path / "rules" / "common" / "test.md").write_text("rule")
    # Commands
    (path / "commands" / "test-cmd").mkdir(parents=True)


class TestFullInstallFlow:
    def test_base_installs_regardless_of_bundle_selections(
        self, tmp_path: Path
    ) -> None:
        """Base skills/agents always install, no prompt."""
        repo = tmp_path / "repo"
        claude_dir = tmp_path / "claude"
        _setup_full_repo(repo)

        # Override bundles to use test repo with minimal skills
        install._BUNDLES_CACHE = None
        install._BUNDLES_REPO_DIR = None

        config = {"bundles": {k: False for k in install.optional_bundles(repo)}}

        with (
            patch("install.install_package"),
            patch("install._get_installed_packages", return_value=set()),
            patch.object(Path, "home", return_value=tmp_path / "home"),
        ):
            (tmp_path / "home" / ".local" / "bin").mkdir(parents=True)
            errors = install.do_install(repo, claude_dir, config, interactive=False)

        assert errors == 0
        # Base skill mine.build installed
        assert (claude_dir / "skills" / "mine.build").is_symlink()
        # Base agents installed
        assert (claude_dir / "agents" / "code-reviewer.md").is_symlink()
        assert (claude_dir / "agents" / "issue-refiner.md").is_symlink()
        # Optional skills NOT installed (all deselected)
        assert not (claude_dir / "skills" / "i-audit").exists()
        assert not (claude_dir / "skills" / "cm-recall-conversations").exists()

    def test_selected_bundle_installs_skills_and_agents(self, tmp_path: Path) -> None:
        repo = tmp_path / "repo"
        claude_dir = tmp_path / "claude"
        _setup_full_repo(repo)
        install._BUNDLES_CACHE = None
        install._BUNDLES_REPO_DIR = None

        config = {
            "bundles": {
                "frontend": True,
                "cli": False,
                "memory": False,
                "engineering": False,
                "extra-agents": False,
            }
        }

        with (
            patch("install.install_package"),
            patch("install._get_installed_packages", return_value=set()),
            patch.object(Path, "home", return_value=tmp_path / "home"),
        ):
            (tmp_path / "home" / ".local" / "bin").mkdir(parents=True)
            errors = install.do_install(repo, claude_dir, config, interactive=False)

        assert errors == 0
        # Frontend skill installed
        assert (claude_dir / "skills" / "i-audit").is_symlink()
        # Frontend capabilities file installed into rules/common
        assert (
            claude_dir / "rules" / "common" / "capabilities-impeccable.md"
        ).is_symlink()
        # Capability file NOT in skills/
        assert not (claude_dir / "skills" / "capabilities-impeccable.md").exists()
        # Memory NOT installed
        assert not (claude_dir / "skills" / "cm-recall-conversations").exists()
        assert not (claude_dir / "rules" / "common" / "capabilities-memory.md").exists()

    def test_hooks_always_installed(self, tmp_path: Path) -> None:
        """All hooks install regardless of bundle selection."""
        repo = tmp_path / "repo"
        claude_dir = tmp_path / "claude"
        _setup_full_repo(repo)
        install._BUNDLES_CACHE = None
        install._BUNDLES_REPO_DIR = None

        config = {"bundles": {k: False for k in install.optional_bundles(repo)}}

        with (
            patch("install.install_package"),
            patch("install._get_installed_packages", return_value=set()),
            patch.object(Path, "home", return_value=tmp_path / "home"),
        ):
            (tmp_path / "home" / ".local" / "bin").mkdir(parents=True)
            install.do_install(repo, claude_dir, config, interactive=False)

        assert (claude_dir / "scripts" / "hooks" / "pytest-guard.sh").is_symlink()
        assert (claude_dir / "scripts" / "hooks" / "sudo-poll.sh").is_symlink()

    def test_rules_always_installed(self, tmp_path: Path) -> None:
        """Rules always install, including capabilities-core.md if present."""
        repo = tmp_path / "repo"
        claude_dir = tmp_path / "claude"
        _setup_full_repo(repo)
        install._BUNDLES_CACHE = None
        install._BUNDLES_REPO_DIR = None

        config = {"bundles": {k: False for k in install.optional_bundles(repo)}}

        with (
            patch("install.install_package"),
            patch("install._get_installed_packages", return_value=set()),
            patch.object(Path, "home", return_value=tmp_path / "home"),
        ):
            (tmp_path / "home" / ".local" / "bin").mkdir(parents=True)
            install.do_install(repo, claude_dir, config, interactive=False)

        assert (claude_dir / "rules" / "common" / "test.md").is_symlink()

    def test_deselected_bundle_removes_symlinks(self, tmp_path: Path) -> None:
        """Deselecting a bundle removes its skill and agent symlinks."""
        repo = tmp_path / "repo"
        claude_dir = tmp_path / "claude"
        _setup_full_repo(repo)
        install._BUNDLES_CACHE = None
        install._BUNDLES_REPO_DIR = None

        # First: install with memory selected
        config_v1 = {
            "bundles": {
                "frontend": False,
                "cli": False,
                "memory": True,
                "engineering": False,
                "extra-agents": False,
            }
        }
        with (
            patch("install.install_package", return_value=(True, "")),
            patch("install._get_installed_packages", return_value=set()),
            patch.object(Path, "home", return_value=tmp_path / "home"),
        ):
            (tmp_path / "home" / ".local" / "bin").mkdir(parents=True)
            install.do_install(repo, claude_dir, config_v1, interactive=False)

        assert (claude_dir / "skills" / "cm-recall-conversations").is_symlink()
        assert (claude_dir / "agents" / "cm-memory-auditor.md").is_symlink()
        assert (claude_dir / "rules" / "common" / "capabilities-memory.md").is_symlink()

        # Second: deselect memory
        config_v2 = {
            "bundles": {
                "frontend": False,
                "cli": False,
                "memory": False,
                "engineering": False,
                "extra-agents": False,
            }
        }
        mock_uninstall = MagicMock(return_value=(True, ""))
        with (
            patch("install.install_package"),
            patch("install.uninstall_package", mock_uninstall),
            patch("install._get_installed_packages", return_value=set()),
            patch.object(Path, "home", return_value=tmp_path / "home"),
        ):
            install.do_install(
                repo, claude_dir, config_v2, prev_config=config_v1, interactive=False
            )

        assert not (claude_dir / "skills" / "cm-recall-conversations").exists()
        assert not (claude_dir / "agents" / "cm-memory-auditor.md").exists()
        assert not (claude_dir / "rules" / "common" / "capabilities-memory.md").exists()
        # Package uninstall triggered
        mock_uninstall.assert_called_with("claude-memory")

    def test_deselection_preserves_unowned_capabilities_file(
        self, tmp_path: Path
    ) -> None:
        """Deselecting a bundle must not remove capabilities files owned by another repo."""
        repo = tmp_path / "repo"
        claude_dir = tmp_path / "claude"
        _setup_full_repo(repo)
        install._BUNDLES_CACHE = None
        install._BUNDLES_REPO_DIR = None

        rules_common = claude_dir / "rules" / "common"
        rules_common.mkdir(parents=True)

        # Place an unowned symlink for capabilities-impeccable.md
        other_repo = tmp_path / "other-repo"
        other_repo.mkdir()
        other_source = other_repo / "capabilities-impeccable.md"
        other_source.write_text("other caps")
        (rules_common / "capabilities-impeccable.md").symlink_to(other_source)

        config = {
            "bundles": {
                "frontend": False,
                "cli": False,
                "memory": False,
                "engineering": False,
                "extra-agents": False,
            }
        }
        with (
            patch("install.install_package"),
            patch("install._get_installed_packages", return_value=set()),
            patch.object(Path, "home", return_value=tmp_path / "home"),
        ):
            (tmp_path / "home" / ".local" / "bin").mkdir(parents=True)
            install.do_install(repo, claude_dir, config, interactive=False)

        # Unowned fragment must survive deselection
        assert (rules_common / "capabilities-impeccable.md").is_symlink()
        assert (
            rules_common / "capabilities-impeccable.md"
        ).resolve() == other_source.resolve()

    def test_deselected_group_removes_rule_fragments(self, tmp_path: Path) -> None:
        """Re-run with bundle deselected removes rule fragment; other bundle's fragment survives."""
        repo = tmp_path / "repo"
        claude_dir = tmp_path / "claude"
        _setup_full_repo(repo)
        install._BUNDLES_CACHE = None
        install._BUNDLES_REPO_DIR = None

        rules_common = claude_dir / "rules" / "common"

        # First install with frontend and memory enabled
        config_v1 = {
            "bundles": {
                "frontend": True,
                "cli": False,
                "memory": True,
                "engineering": False,
                "extra-agents": False,
            }
        }
        with (
            patch("install.install_package", return_value=(True, "")),
            patch("install._get_installed_packages", return_value=set()),
            patch.object(Path, "home", return_value=tmp_path / "home"),
        ):
            (tmp_path / "home" / ".local" / "bin").mkdir(parents=True)
            install.do_install(repo, claude_dir, config_v1, interactive=False)

        assert (rules_common / "capabilities-impeccable.md").is_symlink()
        assert (rules_common / "capabilities-memory.md").is_symlink()

        # Re-install with frontend deselected
        config_v2 = {
            "bundles": {
                "frontend": False,
                "cli": False,
                "memory": True,
                "engineering": False,
                "extra-agents": False,
            }
        }
        with (
            patch("install.install_package", return_value=(True, "")),
            patch("install._get_installed_packages", return_value=set()),
            patch.object(Path, "home", return_value=tmp_path / "home"),
        ):
            install.do_install(
                repo, claude_dir, config_v2, prev_config=config_v1, interactive=False
            )

        assert not (rules_common / "capabilities-impeccable.md").exists()
        assert (rules_common / "capabilities-memory.md").is_symlink()
        assert (claude_dir / "skills" / "cm-recall-conversations").is_symlink()
        assert not (claude_dir / "skills" / "i-audit").exists()


# ---------------------------------------------------------------------------
# Package install / uninstall tests
# ---------------------------------------------------------------------------


def _minimal_repo(tmp_path: Path) -> Path:
    """Create a minimal repo structure for do_install."""
    repo = tmp_path / "repo"
    install._BUNDLES_CACHE = None
    install._BUNDLES_REPO_DIR = None
    (repo / "skills" / "mine.build").mkdir(parents=True)
    (repo / "skills" / "mine.build" / "SKILL.md").write_text("skill")
    (repo / "agents").mkdir()
    (repo / "rules" / "common").mkdir(parents=True)
    return repo


class TestPackageInstall:
    def test_skips_already_installed(self, tmp_path: Path) -> None:
        repo = _minimal_repo(tmp_path)
        claude_dir = tmp_path / "claude"
        install._BUNDLES_CACHE = None
        install._BUNDLES_REPO_DIR = None

        # memory bundle selects claude-memory
        config = {
            "bundles": {
                "frontend": False,
                "cli": False,
                "memory": True,
                "engineering": False,
                "extra-agents": False,
            }
        }
        # Add memory skill dirs to repo so bundle can be installed
        (repo / "skills-memory" / "cm-extract-learnings").mkdir(parents=True)
        (repo / "skills-memory" / "cm-get-token-insights").mkdir(parents=True)
        (repo / "skills-memory" / "cm-recall-conversations").mkdir(parents=True)
        for name in ("cm-memory-auditor", "cm-signal-discoverer"):
            (repo / "agents" / f"{name}.md").write_text(f"---\nname: {name}\n---\n")

        mock_install = MagicMock()
        with (
            patch("install.install_package", mock_install),
            patch("install._get_installed_packages", return_value={"claude-memory"}),
            patch.object(Path, "home", return_value=tmp_path / "home"),
        ):
            (tmp_path / "home" / ".local" / "bin").mkdir(parents=True)
            install.do_install(repo, claude_dir, config, interactive=False)

        mock_install.assert_not_called()

    def test_installs_when_not_present(self, tmp_path: Path) -> None:
        repo = _minimal_repo(tmp_path)
        claude_dir = tmp_path / "claude"
        install._BUNDLES_CACHE = None
        install._BUNDLES_REPO_DIR = None

        # memory bundle selects claude-memory
        (repo / "skills-memory" / "cm-extract-learnings").mkdir(parents=True)
        (repo / "skills-memory" / "cm-get-token-insights").mkdir(parents=True)
        (repo / "skills-memory" / "cm-recall-conversations").mkdir(parents=True)
        for name in ("cm-memory-auditor", "cm-signal-discoverer"):
            (repo / "agents" / f"{name}.md").write_text(f"---\nname: {name}\n---\n")

        config = {
            "bundles": {
                "frontend": False,
                "cli": False,
                "memory": True,
                "engineering": False,
                "extra-agents": False,
            }
        }
        mock_install = MagicMock(return_value=(True, ""))
        with (
            patch("install.install_package", mock_install),
            patch("install._get_installed_packages", return_value=set()),
            patch.object(Path, "home", return_value=tmp_path / "home"),
        ):
            (tmp_path / "home" / ".local" / "bin").mkdir(parents=True)
            install.do_install(repo, claude_dir, config, interactive=False)

        mock_install.assert_called_once_with(repo, "claude-memory")

    def test_uninstalls_deselected_package(self, tmp_path: Path) -> None:
        repo = _minimal_repo(tmp_path)
        claude_dir = tmp_path / "claude"
        install._BUNDLES_CACHE = None
        install._BUNDLES_REPO_DIR = None

        prev_config = {
            "bundles": {
                "frontend": False,
                "cli": False,
                "memory": True,
                "engineering": False,
                "extra-agents": False,
            }
        }
        new_config = {
            "bundles": {
                "frontend": False,
                "cli": False,
                "memory": False,
                "engineering": False,
                "extra-agents": False,
            }
        }

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
                prev_config=prev_config,
                interactive=False,
            )

        mock_uninstall.assert_called_once_with("claude-memory")

    def test_no_uninstall_without_prev_config(self, tmp_path: Path) -> None:
        repo = _minimal_repo(tmp_path)
        claude_dir = tmp_path / "claude"
        install._BUNDLES_CACHE = None
        install._BUNDLES_REPO_DIR = None

        config = {
            "bundles": {
                "frontend": False,
                "cli": False,
                "memory": False,
                "engineering": False,
                "extra-agents": False,
            }
        }
        mock_uninstall = MagicMock()
        with (
            patch("install.install_package"),
            patch("install.uninstall_package", mock_uninstall),
            patch("install._get_installed_packages", return_value=set()),
            patch.object(Path, "home", return_value=tmp_path / "home"),
        ):
            (tmp_path / "home" / ".local" / "bin").mkdir(parents=True)
            install.do_install(repo, claude_dir, config, interactive=False)

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
        install._BUNDLES_CACHE = None
        install._BUNDLES_REPO_DIR = None

        saved = {
            "bundles": {
                "frontend": True,
                "cli": False,
                "memory": False,
                "engineering": False,
                "extra-agents": False,
            },
        }
        cfg_path = install.config_path(claude_dir)
        install.save_config(cfg_path, saved)

        mock_do_install = MagicMock(return_value=0)
        with (
            patch("sys.argv", ["install.py"]),
            patch("install._is_git_worktree", return_value=False),
            patch("install.do_install", mock_do_install),
            patch.dict(os.environ, {"CLAUDE_HOME": str(claude_dir)}),
            patch("install.sys") as mock_sys,
        ):
            mock_sys.stdin.isatty.return_value = False
            mock_sys.exit = sys.exit
            with patch.object(install, "__file__", str(repo / "install.py")):
                result = install.main()

        assert result == 0
        mock_do_install.assert_called_once()
        call_config = mock_do_install.call_args[0][2]
        assert call_config["bundles"]["frontend"] is True
        assert call_config["bundles"]["cli"] is False

    def test_non_interactive_no_saved_config_installs_all(self, tmp_path: Path) -> None:
        claude_dir = tmp_path / "claude_home"
        claude_dir.mkdir()
        repo = _minimal_repo(tmp_path)
        install._BUNDLES_CACHE = None
        install._BUNDLES_REPO_DIR = None

        mock_do_install = MagicMock(return_value=0)
        with (
            patch("sys.argv", ["install.py"]),
            patch("install._is_git_worktree", return_value=False),
            patch("install.do_install", mock_do_install),
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
        # All optional bundles should be True
        for bundle_key in install.optional_bundles(repo):
            assert call_config["bundles"][bundle_key] is True

    def test_non_interactive_reconfigure_warns(self, tmp_path: Path, capsys) -> None:
        claude_dir = tmp_path / "claude_home"
        claude_dir.mkdir()
        repo = _minimal_repo(tmp_path)
        install._BUNDLES_CACHE = None
        install._BUNDLES_REPO_DIR = None

        saved = {
            "bundles": {
                "frontend": False,
                "cli": False,
                "memory": False,
                "engineering": False,
                "extra-agents": False,
            },
        }
        cfg_path = install.config_path(claude_dir)
        install.save_config(cfg_path, saved)

        mock_do_install = MagicMock(return_value=0)
        with (
            patch("sys.argv", ["install.py", "--reconfigure"]),
            patch("install._is_git_worktree", return_value=False),
            patch("install.do_install", mock_do_install),
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
        assert call_config["bundles"]["frontend"] is False


# ---------------------------------------------------------------------------
# Config save timing: saved after do_install, not before
# ---------------------------------------------------------------------------


class TestConfigSaveTiming:
    def test_config_saved_after_install(self, tmp_path: Path) -> None:
        """Config must be written after do_install completes, not before."""
        claude_dir = tmp_path / "claude_home"
        claude_dir.mkdir()
        repo = _minimal_repo(tmp_path)
        install._BUNDLES_CACHE = None
        install._BUNDLES_REPO_DIR = None

        save_order: list[str] = []

        def mock_do_install(*args, **kwargs):
            save_order.append("install")
            return 0

        def mock_save_config(*args, **kwargs):
            save_order.append("save")

        with (
            patch("sys.argv", ["install.py"]),
            patch("install._is_git_worktree", return_value=False),
            patch("install.do_install", side_effect=mock_do_install),
            patch("install.save_config", side_effect=mock_save_config),
            patch.dict(os.environ, {"CLAUDE_HOME": str(claude_dir)}),
            patch("install.sys") as mock_sys,
        ):
            mock_sys.stdin.isatty.return_value = False
            mock_sys.exit = sys.exit
            with patch.object(install, "__file__", str(repo / "install.py")):
                install.main()

        assert save_order == ["install", "save"], (
            f"Expected install before save, got: {save_order}"
        )


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
            install.save_config(cfg_path, {"bundles": {"frontend": True}})

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
            install.save_config(cfg_path, {"bundles": {"frontend": True}})

        assert cfg_path.read_text() == "original"
        tmp_files = list(tmp_path.glob("*.tmp"))
        assert tmp_files == []


# ---------------------------------------------------------------------------
# Capabilities file tests
# ---------------------------------------------------------------------------


class TestCapabilitiesFiles:
    def test_capabilities_core_not_in_any_bundle(self, tmp_path: Path) -> None:
        """capabilities-core.md must not be in any bundle — it lives in rules/common/."""
        _setup_minimal_repo(tmp_path)
        bundles = install.get_bundles(tmp_path)
        for key, bundle in bundles.items():
            assert "capabilities-core.md" not in bundle.capabilities_files, (
                f"capabilities-core.md should not be in bundle '{key}'"
            )

    def test_capabilities_files_install_with_bundle(self, tmp_path: Path) -> None:
        """capabilities-*.md files install to rules/common/ when bundle selected."""
        repo = tmp_path / "repo"
        claude_dir = tmp_path / "claude"
        _setup_full_repo(repo)
        install._BUNDLES_CACHE = None
        install._BUNDLES_REPO_DIR = None

        config = {
            "bundles": {
                "frontend": False,
                "cli": True,
                "memory": False,
                "engineering": False,
                "extra-agents": False,
            }
        }
        with (
            patch("install.install_package"),
            patch("install._get_installed_packages", return_value=set()),
            patch.object(Path, "home", return_value=tmp_path / "home"),
        ):
            (tmp_path / "home" / ".local" / "bin").mkdir(parents=True)
            install.do_install(repo, claude_dir, config, interactive=False)

        assert (claude_dir / "rules" / "common" / "capabilities-cli.md").is_symlink()
        assert not (claude_dir / "rules" / "common" / "capabilities-memory.md").exists()
        assert not (
            claude_dir / "rules" / "common" / "capabilities-impeccable.md"
        ).exists()

    def test_capabilities_files_removed_on_deselect(self, tmp_path: Path) -> None:
        """capabilities-*.md files removed from rules/common/ when bundle deselected."""
        repo = tmp_path / "repo"
        claude_dir = tmp_path / "claude"
        _setup_full_repo(repo)
        install._BUNDLES_CACHE = None
        install._BUNDLES_REPO_DIR = None

        config_v1 = {
            "bundles": {
                "frontend": False,
                "cli": True,
                "memory": False,
                "engineering": False,
                "extra-agents": False,
            }
        }
        config_v2 = {
            "bundles": {
                "frontend": False,
                "cli": False,
                "memory": False,
                "engineering": False,
                "extra-agents": False,
            }
        }
        with (
            patch("install.install_package"),
            patch("install._get_installed_packages", return_value=set()),
            patch.object(Path, "home", return_value=tmp_path / "home"),
        ):
            (tmp_path / "home" / ".local" / "bin").mkdir(parents=True)
            install.do_install(repo, claude_dir, config_v1, interactive=False)

        assert (claude_dir / "rules" / "common" / "capabilities-cli.md").is_symlink()

        with (
            patch("install.install_package"),
            patch("install._get_installed_packages", return_value=set()),
            patch.object(Path, "home", return_value=tmp_path / "home"),
        ):
            install.do_install(
                repo, claude_dir, config_v2, prev_config=config_v1, interactive=False
            )

        assert not (claude_dir / "rules" / "common" / "capabilities-cli.md").exists()
