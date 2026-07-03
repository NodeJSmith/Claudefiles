"""Tests for install.py core logic."""

import io
import itertools
import json
import os
import subprocess
import sys
from contextlib import AbstractContextManager
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from rich.console import Console

# install.py lives one level up and is a single-file script, not an installed package,
# so prepend its directory before importing it.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import install  # noqa: E402

# Base bundle packages, derived from the live bundle definition so this value
# cannot drift from install.py. Used as the already-installed set in tests not
# concerned with package installation, so the always-installed package loop is a
# no-op there.
BASE_PACKAGES = frozenset(
    install.get_bundles(Path(__file__).resolve().parent.parent)["base"].packages
)

# Fake binary paths returned by patched shutil.which across plugin/cass tests, and
# a config version no migration handles.
MISE_CLAUDE_BIN = "/home/u/.local/share/mise/shims/claude"
MISE_CASS_BIN = "/home/u/.local/share/mise/shims/cass"
USR_BIN_CLAUDE = "/usr/bin/claude"
UNKNOWN_CONFIG_VERSION = 999


@pytest.fixture(autouse=True)
def _clear_bundle_cache():
    """Reset the memoized bundles before each test so per-test temp repos aren't
    served a stale dict cached under a previous test's path. Replaces the manual
    cache_clear() each test used to call by hand."""
    install.get_bundles.cache_clear()
    yield


@pytest.fixture(autouse=True)
def _stub_cass_side_effects(monkeypatch):
    """Stop do_install/do_uninstall from shelling out to real cass/ccrecall commands.

    do_install always calls ensure_cass, which checks `shutil.which("cass")`, may run
    bin/cass-update, and then — only if ccrecall/its plugin are still present — removes
    them. Force cass "present" and ccrecall "absent" by default so unrelated
    do_install/do_uninstall tests take the already-installed-and-already-migrated skip
    branches, regardless of whether the test host actually has cass or ccrecall on
    PATH. Tests that assert on ensure_cass's own behavior (TestCassBinary) re-patch
    shutil.which, run_cass_update, uninstall_package, and run_claude_plugin directly.
    """
    _real_which = install.shutil.which

    def fake_which(name):
        if name == "cass":
            return MISE_CASS_BIN
        if name == "ccrecall":
            return None
        return _real_which(name)

    monkeypatch.setattr(install.shutil, "which", fake_which)
    monkeypatch.setattr(install, "run_cass_update", lambda script: (True, ""))
    monkeypatch.setattr(install, "uninstall_package", lambda name: (True, ""))
    monkeypatch.setattr(
        install, "run_claude_plugin", lambda claude_bin, args: (True, "")
    )


def _fake_home_patch(tmp_path: Path) -> AbstractContextManager[MagicMock]:
    """Point Path.home() at tmp_path/home with ~/.local/bin created for bin symlinks.

    Returned as a context manager so it drops straight into a test's existing `with`
    block alongside the other patches. Replaces the per-test
    patch.object(Path, "home", ...) + bin.mkdir boilerplate. Note the bin dir is created
    when this is called (at `with`-expression evaluation), before the patch is entered;
    tmp_path is unique per test so that side effect is harmless.
    """
    (tmp_path / "home" / ".local" / "bin").mkdir(parents=True, exist_ok=True)
    return patch.object(Path, "home", return_value=tmp_path / "home")


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
        cfg_path.write_text(json.dumps({"version": UNKNOWN_CONFIG_VERSION}))
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

    def test_file_level_preserves_unowned_subdir_symlink(self, tmp_path: Path) -> None:
        """A subdir-level symlink we don't own is shadowed, not destroyed.

        Regression: the sub_dest unlink used to skip the ownership check, so a
        foreign symlink at e.g. references/common would be replaced with a real
        directory, dropping every file it pointed to.
        """
        repo = tmp_path / "repo"
        (repo / "common").mkdir(parents=True)
        (repo / "common" / "file1.md").write_text("x")

        other = tmp_path / "other"
        (other / "common").mkdir(parents=True)
        (other / "common" / "preexisting.md").write_text("keep me")

        dest = tmp_path / "dest"
        dest.mkdir()
        (dest / "common").symlink_to(other / "common")

        shadowed: list[tuple[Path, Path]] = []
        count = install.create_symlinks_file_level(
            repo, dest, repo_dir=repo, shadowed_out=shadowed
        )

        assert count == 0
        assert (dest / "common").is_symlink()
        assert (dest / "common").resolve() == (other / "common").resolve()
        assert (dest / "common" / "preexisting.md").read_text() == "keep me"
        assert len(shadowed) == 1
        assert shadowed[0][0] == dest / "common"

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


class TestLinkBundleArtifacts:
    def test_missing_agent_skipped_not_dangling(self, tmp_path: Path) -> None:
        """A bundle agent with no source file is warned and skipped, never linked.

        Regression: agent symlinks used to bypass the existence check that skills
        had, so a missing agent file produced a silent dangling symlink.
        """
        repo = tmp_path / "repo"
        (repo / "agents").mkdir(parents=True)
        (repo / "agents" / "real.md").write_text("---\nname: real\n---\n")

        claude = tmp_path / "claude"
        bundle = install.Bundle(label="x", description="d", agents=("real", "missing"))
        shadowed: list[tuple[Path, Path]] = []
        links = install.link_bundle_artifacts(
            bundle,
            repo,
            skills_dest=claude / "skills",
            agents_dest=claude / "agents",
            rules_common_dest=claude / "rules" / "common",
            console=Console(),
            shadowed_out=shadowed,
        )

        assert links == 1
        assert (claude / "agents" / "real.md").is_symlink()
        assert not (claude / "agents" / "missing.md").is_symlink()
        assert not (claude / "agents" / "missing.md").exists()


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

    def test_four_optional_bundles(self, tmp_path: Path) -> None:
        """Exactly 4 optional bundles (conversation memory is now built-in via cass)."""
        _setup_minimal_repo(tmp_path)
        opt = install.optional_bundles(tmp_path)
        assert set(opt.keys()) == {
            "frontend",
            "cli",
            "engineering",
            "extra-agents",
        }

    def test_base_agents(self, tmp_path: Path) -> None:
        """Base bundle holds the advisory reviewers plus the credential/registry agents."""
        _setup_minimal_repo(tmp_path)
        bundles = install.get_bundles(tmp_path)
        base = bundles["base"]
        assert set(base.agents) == {
            "code-reviewer",
            "integration-reviewer",
            "wtf-reviewer",
            "fine-toothed-comb",
            "code-judo-reviewer",
            "researcher",
            "llm-checker",
            "lazy-checker",
            "nitpicker",
            "issue-refiner",
            "secrets-auditor",
        }

    def test_base_packages(self, tmp_path: Path) -> None:
        """Base bundle has cfl and merge-settings packages."""
        _setup_minimal_repo(tmp_path)
        bundles = install.get_bundles(tmp_path)
        assert set(bundles["base"].packages) == {"cfl", "merge-settings"}

    def test_no_memory_bundle(self, tmp_path: Path) -> None:
        """Conversation memory is now built-in via cass skills/hooks, not a bundle."""
        _setup_minimal_repo(tmp_path)
        bundles = install.get_bundles(tmp_path)
        assert "memory" not in bundles

    def test_frontend_capabilities_file(self, tmp_path: Path) -> None:
        _setup_minimal_repo(tmp_path)
        bundles = install.get_bundles(tmp_path)
        assert "capabilities-impeccable.md" in bundles["frontend"].capabilities_files

    def test_cli_capabilities_file(self, tmp_path: Path) -> None:
        _setup_minimal_repo(tmp_path)
        bundles = install.get_bundles(tmp_path)
        assert "capabilities-cli.md" in bundles["cli"].capabilities_files


# ---------------------------------------------------------------------------
# find_skill_source tests
# ---------------------------------------------------------------------------


class TestFindSkillSource:
    def test_finds_in_skills(self, tmp_path: Path) -> None:
        (tmp_path / "skills" / "mine-build").mkdir(parents=True)
        result = install.find_skill_source("mine-build", tmp_path)
        assert result == tmp_path / "skills" / "mine-build"

    def test_finds_in_skills_impeccable(self, tmp_path: Path) -> None:
        (tmp_path / "skills-impeccable" / "i-audit").mkdir(parents=True)
        result = install.find_skill_source("i-audit", tmp_path)
        assert result == tmp_path / "skills-impeccable" / "i-audit"

    def test_finds_in_skills_cli(self, tmp_path: Path) -> None:
        (tmp_path / "skills-cli" / "cli-harden").mkdir(parents=True)
        result = install.find_skill_source("cli-harden", tmp_path)
        assert result == tmp_path / "skills-cli" / "cli-harden"

    def test_raises_when_not_found(self, tmp_path: Path) -> None:
        with pytest.raises(FileNotFoundError, match="Skill not found: nonexistent"):
            install.find_skill_source("nonexistent", tmp_path)

    def test_prefers_skills_over_others(self, tmp_path: Path) -> None:
        """skills/ is checked first in SKILL_DIRS order."""
        (tmp_path / "skills" / "mine-build").mkdir(parents=True)
        (tmp_path / "skills-impeccable" / "mine-build").mkdir(parents=True)
        result = install.find_skill_source("mine-build", tmp_path)
        assert result == tmp_path / "skills" / "mine-build"


# ---------------------------------------------------------------------------
# Bundle dependency completeness
# ---------------------------------------------------------------------------


class TestBundleDependencyCompleteness:
    def test_all_base_skills_resolve(self) -> None:
        """Every skill in the base bundle must exist in the actual repo."""
        repo_dir = Path(__file__).resolve().parent.parent
        # Reset cache to use actual repo
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
        opt = install.optional_bundles(repo_dir)
        missing = []
        for bundle_key, bundle in opt.items():
            for skill_name in bundle.skills:
                try:
                    install.find_skill_source(skill_name, repo_dir)
                except FileNotFoundError:
                    missing.append(f"{bundle_key}/{skill_name}")
        assert missing == [], f"Missing skills from optional bundles: {missing}"

    def test_all_skill_dirs_in_base(self) -> None:
        """Every directory under skills/ appears in the base bundle."""
        repo_dir = Path(__file__).resolve().parent.parent
        bundles = install.get_bundles(repo_dir)
        skills_dir = repo_dir / "skills"
        expected = {d.name for d in skills_dir.iterdir() if d.is_dir()}
        assert expected == set(bundles["base"].skills)


# ---------------------------------------------------------------------------
# Integration test: full install flow (bundle-based)
# ---------------------------------------------------------------------------


def _write_rule_files(path: Path, content_map: dict[str, str] | None = None) -> None:
    """Create every rules/common file declared in install.RULE_CATEGORIES.

    Derived from the live category map so the fixture cannot drift from install.py.
    content_map overrides the body of named files (used to plant cross-references).
    """
    common = path / "rules" / "common"
    common.mkdir(parents=True, exist_ok=True)
    overrides = content_map or {}
    for category in install.RULE_CATEGORIES.values():
        for fname in category.files:
            (common / fname).write_text(overrides.get(fname, "rule"))


def _setup_minimal_repo(path: Path) -> None:
    """Create a minimal repo directory structure for testing."""
    (path / "skills" / "mine-build").mkdir(parents=True)
    (path / "skills" / "mine-build" / "SKILL.md").write_text("skill")
    (path / "agents").mkdir(parents=True)
    _write_rule_files(path)


def _setup_full_repo(path: Path) -> None:
    """Create a repo with skills, agents, hooks, etc. for integration tests."""
    # Base skills
    (path / "skills" / "mine-build").mkdir(parents=True)
    (path / "skills" / "mine-build" / "SKILL.md").write_text("skill")
    # Frontend skills
    (path / "skills-impeccable" / "i-audit").mkdir(parents=True)
    (path / "skills-impeccable" / "i-audit" / "SKILL.md").write_text("skill")
    (path / "skills-impeccable" / "capabilities-impeccable.md").write_text("caps")
    # CLI skills
    (path / "skills-cli" / "cli-harden").mkdir(parents=True)
    (path / "skills-cli" / "cli-harden" / "SKILL.md").write_text("skill")
    (path / "skills-cli" / "capabilities-cli.md").write_text("caps")
    # Agents — write a stub for every agent named by any bundle, derived from the live
    # bundle definitions so the fixture can't drift from install.py's agent lists.
    (path / "agents").mkdir(parents=True)
    all_agents = {
        name for bundle in install.get_bundles(path).values() for name in bundle.agents
    }
    for name in sorted(all_agents):
        (path / "agents" / f"{name}.md").write_text(f"---\nname: {name}\n---\n")
    # Hooks
    (path / "scripts" / "hooks").mkdir(parents=True)
    (path / "scripts" / "hooks" / "sudo-poll.sh").write_text("#!/bin/bash")
    # Rules
    _write_rule_files(path)
    refs = path / "references" / "common"
    refs.mkdir(parents=True, exist_ok=True)
    for fname in [
        "agents.md",
        "dependency-injection.md",
        "frontend.md",
        "instruction-quality.md",
        "receiving-code-review.md",
        "reliability.md",
        "security.md",
        "testing.md",
        "typescript.md",
        "writing-quality.md",
    ]:
        (refs / fname).write_text("reference")
    # Commands
    (path / "commands" / "test-cmd").mkdir(parents=True)
    # Deriving agents above cached bundles mid-build; clear so install code under test
    # rescans the now-complete tree rather than reusing that partial snapshot.
    install.get_bundles.cache_clear()


class TestFullInstallFlow:
    def test_base_installs_regardless_of_bundle_selections(
        self, tmp_path: Path
    ) -> None:
        """Base skills/agents always install, no prompt."""
        repo = tmp_path / "repo"
        claude_dir = tmp_path / "claude"
        _setup_full_repo(repo)

        # Override bundles to use test repo with minimal skills

        config = {"bundles": {k: False for k in install.optional_bundles(repo)}}

        with (
            patch("install.install_package"),
            patch("install.get_installed_packages", return_value=BASE_PACKAGES),
            _fake_home_patch(tmp_path),
        ):
            errors = install.do_install(repo, claude_dir, config, interactive=False)

        assert errors == 0
        # Base skill mine-build installed
        assert (claude_dir / "skills" / "mine-build").is_symlink()
        # Base agents installed
        assert (claude_dir / "agents" / "code-reviewer.md").is_symlink()
        assert (claude_dir / "agents" / "issue-refiner.md").is_symlink()
        # Optional skills NOT installed (all deselected)
        assert not (claude_dir / "skills" / "i-audit").exists()

    def test_selected_bundle_installs_skills_and_agents(self, tmp_path: Path) -> None:
        repo = tmp_path / "repo"
        claude_dir = tmp_path / "claude"
        _setup_full_repo(repo)

        config = {
            "bundles": {
                "frontend": True,
                "cli": False,
                "engineering": False,
                "extra-agents": False,
            }
        }

        with (
            patch("install.install_package"),
            patch("install.get_installed_packages", return_value=BASE_PACKAGES),
            _fake_home_patch(tmp_path),
        ):
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

    def test_hooks_always_installed(self, tmp_path: Path) -> None:
        """All hooks install regardless of bundle selection."""
        repo = tmp_path / "repo"
        claude_dir = tmp_path / "claude"
        _setup_full_repo(repo)

        config = {"bundles": {k: False for k in install.optional_bundles(repo)}}

        with (
            patch("install.install_package"),
            patch("install.get_installed_packages", return_value=BASE_PACKAGES),
            _fake_home_patch(tmp_path),
        ):
            install.do_install(repo, claude_dir, config, interactive=False)

        assert (claude_dir / "scripts" / "hooks" / "sudo-poll.sh").is_symlink()

    def test_rules_always_installed(self, tmp_path: Path) -> None:
        """Core rules always install; a config without rule_categories installs all rules."""
        repo = tmp_path / "repo"
        claude_dir = tmp_path / "claude"
        _setup_full_repo(repo)

        # No rule_categories key → absence means "all selected" (backward compat).
        config = {"bundles": {k: False for k in install.optional_bundles(repo)}}

        with (
            patch("install.install_package"),
            patch("install.get_installed_packages", return_value=BASE_PACKAGES),
            _fake_home_patch(tmp_path),
        ):
            install.do_install(repo, claude_dir, config, interactive=False)

        common = claude_dir / "rules" / "common"
        # Core files always present
        for fname in install.RULE_CATEGORIES["core"].files:
            assert (common / fname).is_symlink(), fname
        # Optional files present too, since rule_categories was absent
        assert (common / "python.md").is_symlink()
        assert (common / "verification.md").is_symlink()
        # Reference files always installed
        refs = claude_dir / "references" / "common"
        assert (refs / "testing.md").is_symlink()
        assert (refs / "frontend.md").is_symlink()

    def test_deselected_bundle_removes_symlinks(self, tmp_path: Path) -> None:
        """Deselecting a bundle removes its skill and capability symlinks."""
        repo = tmp_path / "repo"
        claude_dir = tmp_path / "claude"
        _setup_full_repo(repo)

        # First: install with frontend selected
        config_v1 = {
            "bundles": {
                "frontend": True,
                "cli": False,
                "engineering": False,
                "extra-agents": False,
            }
        }
        with (
            patch("install.install_package", return_value=(True, "")),
            patch("install.get_installed_packages", return_value=BASE_PACKAGES),
            _fake_home_patch(tmp_path),
        ):
            install.do_install(repo, claude_dir, config_v1, interactive=False)

        assert (claude_dir / "skills" / "i-audit").is_symlink()
        assert (
            claude_dir / "rules" / "common" / "capabilities-impeccable.md"
        ).is_symlink()

        # Second: deselect frontend
        config_v2 = {
            "bundles": {
                "frontend": False,
                "cli": False,
                "engineering": False,
                "extra-agents": False,
            }
        }
        with (
            patch("install.install_package"),
            patch("install.get_installed_packages", return_value=BASE_PACKAGES),
            _fake_home_patch(tmp_path),
        ):
            install.do_install(
                repo, claude_dir, config_v2, prev_config=config_v1, interactive=False
            )

        assert not (claude_dir / "skills" / "i-audit").exists()
        assert not (
            claude_dir / "rules" / "common" / "capabilities-impeccable.md"
        ).exists()

    def test_deselection_preserves_unowned_capabilities_file(
        self, tmp_path: Path
    ) -> None:
        """Deselecting a bundle must not remove capabilities files owned by another repo."""
        repo = tmp_path / "repo"
        claude_dir = tmp_path / "claude"
        _setup_full_repo(repo)

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
                "engineering": False,
                "extra-agents": False,
            }
        }
        with (
            patch("install.install_package"),
            patch("install.get_installed_packages", return_value=BASE_PACKAGES),
            _fake_home_patch(tmp_path),
        ):
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

        rules_common = claude_dir / "rules" / "common"

        # First install with frontend and cli enabled
        config_v1 = {
            "bundles": {
                "frontend": True,
                "cli": True,
                "engineering": False,
                "extra-agents": False,
            }
        }
        with (
            patch("install.install_package", return_value=(True, "")),
            patch("install.get_installed_packages", return_value=BASE_PACKAGES),
            _fake_home_patch(tmp_path),
        ):
            install.do_install(repo, claude_dir, config_v1, interactive=False)

        assert (rules_common / "capabilities-impeccable.md").is_symlink()
        assert (rules_common / "capabilities-cli.md").is_symlink()

        # Re-install with frontend deselected
        config_v2 = {
            "bundles": {
                "frontend": False,
                "cli": True,
                "engineering": False,
                "extra-agents": False,
            }
        }
        with (
            patch("install.install_package", return_value=(True, "")),
            patch("install.get_installed_packages", return_value=BASE_PACKAGES),
            _fake_home_patch(tmp_path),
        ):
            install.do_install(
                repo, claude_dir, config_v2, prev_config=config_v1, interactive=False
            )

        assert not (rules_common / "capabilities-impeccable.md").exists()
        assert (rules_common / "capabilities-cli.md").is_symlink()
        assert (claude_dir / "skills" / "cli-harden").is_symlink()
        assert not (claude_dir / "skills" / "i-audit").exists()


# ---------------------------------------------------------------------------
# Rule category selection tests
# ---------------------------------------------------------------------------


def _run_rule_install(
    repo: Path,
    claude_dir: Path,
    tmp_path: Path,
    rule_categories: dict[str, bool],
    *,
    prev_config: dict | None = None,
) -> None:
    """Install with all optional bundles off and the given rule_categories selection."""
    config = {
        "bundles": {k: False for k in install.optional_bundles(repo)},
        "rule_categories": rule_categories,
    }
    with (
        patch("install.install_package"),
        patch("install.get_installed_packages", return_value=BASE_PACKAGES),
        _fake_home_patch(tmp_path),
    ):
        install.do_install(
            repo, claude_dir, config, prev_config=prev_config, interactive=False
        )


class TestRuleCategories:
    def test_categories_cover_every_rule_file(self) -> None:
        """Every file in the real rules/common is mapped to exactly one category."""
        repo = Path(__file__).resolve().parent.parent
        actual = {p.name for p in (repo / "rules" / "common").glob("*.md")}
        mapped = [f for c in install.RULE_CATEGORIES.values() for f in c.files]
        assert len(mapped) == len(set(mapped)), "a rule file appears in two categories"
        assert set(mapped) == actual, (
            "RULE_CATEGORIES is out of sync with rules/common/; "
            f"unmapped={actual - set(mapped)}, missing={set(mapped) - actual}"
        )

    def test_core_rules_always_install(self, tmp_path: Path) -> None:
        """With every optional category off, core files install and optional ones don't."""
        repo = tmp_path / "repo"
        claude_dir = tmp_path / "claude"
        _setup_full_repo(repo)

        _run_rule_install(
            repo,
            claude_dir,
            tmp_path,
            {k: False for k in install.optional_rule_categories()},
        )

        common = claude_dir / "rules" / "common"
        for fname in install.RULE_CATEGORIES["core"].files:
            assert (common / fname).is_symlink(), fname
        # A representative optional file from each of two categories is absent
        assert not (common / "python.md").exists()
        assert not (common / "testing.md").exists()

    def test_selected_category_installs_files(self, tmp_path: Path) -> None:
        """Selecting one category installs its files and leaves others uninstalled."""
        repo = tmp_path / "repo"
        claude_dir = tmp_path / "claude"
        _setup_full_repo(repo)

        selection = {k: False for k in install.optional_rule_categories()}
        selection["verification"] = True
        _run_rule_install(repo, claude_dir, tmp_path, selection)

        common = claude_dir / "rules" / "common"
        for fname in install.RULE_CATEGORIES["verification"].files:
            assert (common / fname).is_symlink(), fname
        # A file from an unselected category is absent
        assert not (common / "python.md").exists()

    def test_deselected_category_removes_files(self, tmp_path: Path) -> None:
        """Deselecting a previously-installed category removes its owned symlinks."""
        repo = tmp_path / "repo"
        claude_dir = tmp_path / "claude"
        _setup_full_repo(repo)

        on = {k: False for k in install.optional_rule_categories()}
        on["languages"] = True
        _run_rule_install(repo, claude_dir, tmp_path, on)
        common = claude_dir / "rules" / "common"
        assert (common / "python.md").is_symlink()

        off = {k: False for k in install.optional_rule_categories()}
        _run_rule_install(
            repo,
            claude_dir,
            tmp_path,
            off,
            prev_config={"bundles": {}, "rule_categories": on},
        )
        assert not (common / "python.md").exists()
        # Core survives the deselection
        assert (common / "interaction.md").is_symlink()

    def test_deselect_preserves_unowned_rule_file(self, tmp_path: Path) -> None:
        """A rule symlink owned by another repo is not removed when its category is off."""
        repo = tmp_path / "repo"
        claude_dir = tmp_path / "claude"
        _setup_full_repo(repo)

        common = claude_dir / "rules" / "common"
        common.mkdir(parents=True)
        other_repo = tmp_path / "other-repo"
        other_repo.mkdir()
        other_source = other_repo / "python.md"
        other_source.write_text("other rule")
        (common / "python.md").symlink_to(other_source)

        _run_rule_install(
            repo,
            claude_dir,
            tmp_path,
            {k: False for k in install.optional_rule_categories()},
        )

        assert (common / "python.md").is_symlink()
        assert install.is_owned_by(common / "python.md", repo) is False

    def test_absent_rule_categories_means_all_selected(self) -> None:
        """A config with no rule_categories key selects every optional category."""
        keys = install.selected_rule_category_keys({"bundles": {}})
        assert keys == set(install.optional_rule_categories())

    def test_partial_rule_categories_treats_missing_as_off(self) -> None:
        """A present-but-partial dict deselects categories not listed."""
        keys = install.selected_rule_category_keys(
            {"rule_categories": {"verification": True}}
        )
        assert keys == {"verification"}

    def test_new_category_detected_against_saved_config(self) -> None:
        """find_new_groups flags an optional category missing from the saved config."""
        saved = {"rule_categories": {"verification": True}}
        opt_keys = list(install.optional_rule_categories().keys())
        new = install.find_new_groups(saved, "rule_categories", opt_keys)
        assert "verification" not in new
        assert "languages" in new

    def test_warn_dangling_refs_fires(self, tmp_path: Path) -> None:
        """A kept rule that references an uninstalled rule produces a warning."""
        repo = tmp_path / "repo"
        _write_rule_files(
            repo,
            {"eval-discipline.md": "Check evidence; see `verification.md`."},
        )
        buf = io.StringIO()
        console = Console(file=buf, width=120)
        # 'authoring' is selected (contains eval-discipline); 'verification' is not.
        install.warn_dangling_rule_refs(repo, {"authoring"}, console)
        out = buf.getvalue()
        assert "eval-discipline.md" in out
        assert "verification.md" in out

    def test_warn_dangling_refs_silent_when_target_installed(
        self, tmp_path: Path
    ) -> None:
        """No warning when the referenced rule's category is also selected."""
        repo = tmp_path / "repo"
        _write_rule_files(
            repo,
            {"eval-discipline.md": "Check evidence; see `verification.md`."},
        )
        buf = io.StringIO()
        console = Console(file=buf, width=120)
        install.warn_dangling_rule_refs(repo, {"authoring", "verification"}, console)
        assert "eval-discipline.md" not in buf.getvalue()


# ---------------------------------------------------------------------------
# Package install / uninstall tests
# ---------------------------------------------------------------------------


def _minimal_repo(tmp_path: Path) -> Path:
    """Create a minimal repo under tmp_path/repo and return it.

    Thin wrapper over _setup_minimal_repo so the build steps live in one place.
    """
    repo = tmp_path / "repo"
    _setup_minimal_repo(repo)
    return repo


class TestCassBinary:
    def test_skips_when_cass_on_path(self, tmp_path: Path) -> None:
        """ensure_cass does not run cass-update when cass is already on PATH."""
        mock_update = MagicMock(return_value=(True, ""))
        mock_uninstall = MagicMock(return_value=(True, ""))
        mock_plugin = MagicMock(return_value=(True, ""))
        with (
            _fake_home_patch(tmp_path),
            patch("install.shutil.which", return_value=MISE_CASS_BIN),
            patch("install.run_cass_update", mock_update),
            patch("install.uninstall_package", mock_uninstall),
            patch("install.run_claude_plugin", mock_plugin),
        ):
            errors = install.ensure_cass(Path("/repo"), install.Console())
        assert errors == 0
        mock_update.assert_not_called()

    def test_installs_when_absent(self, tmp_path: Path) -> None:
        """ensure_cass invokes bin/cass-update when cass is not on PATH, then verifies
        via shutil.which that the install succeeded before touching ccrecall."""
        cass_which_calls = {"count": 0}

        def fake_which(name):
            if name != "cass":
                return MISE_CLAUDE_BIN
            cass_which_calls["count"] += 1
            return None if cass_which_calls["count"] == 1 else MISE_CASS_BIN

        mock_update = MagicMock(return_value=(True, ""))
        with (
            _fake_home_patch(tmp_path),
            patch("install.shutil.which", side_effect=fake_which),
            patch("install.run_cass_update", mock_update),
            patch("install.uninstall_package", return_value=(True, "")),
            patch("install.run_claude_plugin", return_value=(True, "")),
        ):
            errors = install.ensure_cass(Path("/repo"), install.Console())
        assert errors == 0
        mock_update.assert_called_once_with(Path("/repo") / "bin" / "cass-update")

    def test_handles_download_failure(self) -> None:
        """A cass-update failure that leaves cass off PATH is a hard error, and
        ccrecall/its plugin are never touched."""
        mock_uninstall = MagicMock()
        mock_plugin = MagicMock()
        with (
            patch("install.shutil.which", return_value=None),
            patch("install.run_cass_update", return_value=(False, "download failed")),
            patch("install.uninstall_package", mock_uninstall),
            patch("install.run_claude_plugin", mock_plugin),
        ):
            errors = install.ensure_cass(Path("/repo"), install.Console())
        assert errors == 1
        mock_uninstall.assert_not_called()
        mock_plugin.assert_not_called()

    def test_removes_ccrecall_after_cass_installed(self, tmp_path: Path) -> None:
        """Once cass is confirmed present, ensure_cass removes a still-present ccrecall
        and its still-tracked plugin registration."""

        def fake_which(name):
            return {
                "cass": MISE_CASS_BIN,
                "claude": MISE_CLAUDE_BIN,
                "ccrecall": "/usr/bin/ccrecall",
            }.get(name)

        def fake_plugin(claude_bin, args):
            if args == ["list", "--json"]:
                return True, json.dumps([{"id": install.CCRECALL_PLUGIN_REF}])
            return True, ""

        mock_uninstall = MagicMock(return_value=(True, ""))
        mock_plugin = MagicMock(side_effect=fake_plugin)
        with (
            _fake_home_patch(tmp_path),
            patch("install.shutil.which", side_effect=fake_which),
            patch("install.run_cass_update", return_value=(True, "")),
            patch("install.uninstall_package", mock_uninstall),
            patch("install.run_claude_plugin", mock_plugin),
        ):
            errors = install.ensure_cass(Path("/repo"), install.Console())
        assert errors == 0
        mock_uninstall.assert_called_once_with("ccrecall")
        mock_plugin.assert_any_call(
            MISE_CLAUDE_BIN, ["uninstall", install.CCRECALL_PLUGIN_REF]
        )

    def test_skips_ccrecall_uninstall_when_already_absent(self, tmp_path: Path) -> None:
        """ensure_cass does not call uninstall_package when ccrecall isn't on PATH —
        otherwise every re-run of an already-migrated machine reprints "Removing
        legacy package: ccrecall..." followed by a spurious warning, forever."""

        def fake_which(name):
            return {"cass": MISE_CASS_BIN, "claude": MISE_CLAUDE_BIN}.get(name)

        mock_uninstall = MagicMock(return_value=(True, ""))
        with (
            _fake_home_patch(tmp_path),
            patch("install.shutil.which", side_effect=fake_which),
            patch("install.run_cass_update", return_value=(True, "")),
            patch("install.uninstall_package", mock_uninstall),
            patch("install.run_claude_plugin", return_value=(True, "[]")),
        ):
            errors = install.ensure_cass(Path("/repo"), install.Console())
        assert errors == 0
        mock_uninstall.assert_not_called()

    def test_skips_plugin_uninstall_when_not_tracked(self, tmp_path: Path) -> None:
        """ensure_cass checks `claude plugin list` before uninstalling — once the
        plugin is no longer a tracked install, it does not re-attempt the uninstall
        (and its warning-on-failure) on every subsequent run."""

        def fake_which(name):
            return {"cass": MISE_CASS_BIN, "claude": MISE_CLAUDE_BIN}.get(name)

        mock_plugin = MagicMock(return_value=(True, "[]"))
        with (
            _fake_home_patch(tmp_path),
            patch("install.shutil.which", side_effect=fake_which),
            patch("install.run_cass_update", return_value=(True, "")),
            patch("install.uninstall_package", return_value=(True, "")),
            patch("install.run_claude_plugin", mock_plugin),
        ):
            errors = install.ensure_cass(Path("/repo"), install.Console())
        assert errors == 0
        mock_plugin.assert_called_once_with(MISE_CLAUDE_BIN, ["list", "--json"])

    def test_keeps_ccrecall_if_cass_fails(self) -> None:
        """Safety invariant: ccrecall and its plugin are never removed while cass is
        absent — never leave the machine with neither search tool."""
        mock_uninstall = MagicMock()
        mock_plugin = MagicMock()
        with (
            patch("install.shutil.which", return_value=None),
            patch("install.run_cass_update", return_value=(False, "boom")),
            patch("install.uninstall_package", mock_uninstall),
            patch("install.run_claude_plugin", mock_plugin),
        ):
            errors = install.ensure_cass(Path("/repo"), install.Console())
        assert errors == 1
        mock_uninstall.assert_not_called()
        mock_plugin.assert_not_called()

    def test_not_on_path_yet_hints_shell_restart(self, tmp_path: Path) -> None:
        """When cass-update reports success and the binary lands on disk but this
        shell's PATH doesn't include ~/.local/bin, ensure_cass tells the user to
        restart their terminal instead of a bare 'still not on PATH' warning that
        reads like an install failure."""
        buf = io.StringIO()
        console = Console(file=buf, width=120)
        with (
            _fake_home_patch(tmp_path),
            patch("install.shutil.which", return_value=None),
            patch("install.run_cass_update", return_value=(True, "")),
        ):
            (install.local_bin_dir() / "cass").touch()
            errors = install.ensure_cass(Path("/repo"), console)
        assert errors == 1
        out = buf.getvalue()
        assert "restart your terminal" in out
        assert "still not on PATH — leaving ccrecall" not in out

    def test_genuine_failure_keeps_original_warning(self, tmp_path: Path) -> None:
        """When cass-update fails outright (binary never lands on disk), the original
        'still not on PATH' warning is shown, not the shell-restart hint."""
        buf = io.StringIO()
        console = Console(file=buf, width=120)
        with (
            _fake_home_patch(tmp_path),
            patch("install.shutil.which", return_value=None),
            patch("install.run_cass_update", return_value=(False, "download failed")),
        ):
            errors = install.ensure_cass(Path("/repo"), console)
        assert errors == 1
        out = buf.getvalue()
        assert "still not on PATH — leaving ccrecall" in out
        assert "restart your terminal" not in out

    def test_hints_first_index_when_unpopulated(self, tmp_path: Path) -> None:
        """ensure_cass hints to run `cass index` when cass is present but has never
        indexed anything on this machine, instead of leaving search silently empty
        until the next SessionStart hook fires."""
        buf = io.StringIO()
        console = Console(file=buf, width=120)

        def fake_which(name):
            return {"cass": MISE_CASS_BIN, "claude": MISE_CLAUDE_BIN}.get(name)

        with (
            _fake_home_patch(tmp_path),
            patch("install.shutil.which", side_effect=fake_which),
            patch("install.run_cass_update", return_value=(True, "")),
            patch("install.uninstall_package", return_value=(True, "")),
            patch("install.run_claude_plugin", return_value=(True, "[]")),
        ):
            errors = install.ensure_cass(Path("/repo"), console)
        assert errors == 0
        output = buf.getvalue()
        assert "cass models install" in output
        assert "cass index --semantic" in output
        assert "cass index`" in output

    def test_index_hint_with_model_installed(self, tmp_path: Path) -> None:
        """When model is installed but index is empty, hints `cass index --semantic`
        without mentioning `cass models install`. This state is unlikely in practice
        (model dir lives inside index dir), but the branch should work correctly."""
        buf = io.StringIO()
        console = Console(file=buf, width=120)

        def fake_which(name):
            return {"cass": MISE_CASS_BIN, "claude": MISE_CLAUDE_BIN}.get(name)

        with (
            _fake_home_patch(tmp_path),
            patch("install.shutil.which", side_effect=fake_which),
            patch("install.run_cass_update", return_value=(True, "")),
            patch("install.uninstall_package", return_value=(True, "")),
            patch("install.run_claude_plugin", return_value=(True, "[]")),
            patch("install.cass_index_populated", return_value=False),
            patch("install.cass_semantic_model_installed", return_value=True),
        ):
            errors = install.ensure_cass(Path("/repo"), console)
        assert errors == 0
        output = buf.getvalue()
        assert "cass index --semantic" in output
        assert "cass models install" not in output

    def test_no_index_hint_when_already_populated(self, tmp_path: Path) -> None:
        """No first-index hint once cass has already indexed something on this
        machine — otherwise every re-run of an already-working install nags forever."""
        buf = io.StringIO()
        console = Console(file=buf, width=120)

        def fake_which(name):
            return {"cass": MISE_CASS_BIN, "claude": MISE_CLAUDE_BIN}.get(name)

        with (
            _fake_home_patch(tmp_path),
            patch("install.shutil.which", side_effect=fake_which),
            patch("install.run_cass_update", return_value=(True, "")),
            patch("install.uninstall_package", return_value=(True, "")),
            patch("install.run_claude_plugin", return_value=(True, "[]")),
        ):
            index_dir = install.cass_index_dir()
            index_dir.mkdir(parents=True)
            (index_dir / "index.db").touch()
            model_dir = index_dir / "models" / "all-MiniLM-L6-v2"
            model_dir.mkdir(parents=True)
            (model_dir / "model.onnx").touch()
            errors = install.ensure_cass(Path("/repo"), console)
        assert errors == 0
        assert "run `cass index`" not in buf.getvalue()
        assert "cass models install" not in buf.getvalue()

    def test_semantic_model_hint_when_not_installed(self, tmp_path: Path) -> None:
        """Hints at semantic model even when base index is populated."""
        buf = io.StringIO()
        console = Console(file=buf, width=120)

        def fake_which(name):
            return {"cass": MISE_CASS_BIN, "claude": MISE_CLAUDE_BIN}.get(name)

        with (
            _fake_home_patch(tmp_path),
            patch("install.shutil.which", side_effect=fake_which),
            patch("install.run_cass_update", return_value=(True, "")),
            patch("install.uninstall_package", return_value=(True, "")),
            patch("install.run_claude_plugin", return_value=(True, "[]")),
        ):
            index_dir = install.cass_index_dir()
            index_dir.mkdir(parents=True)
            (index_dir / "index.db").touch()
            errors = install.ensure_cass(Path("/repo"), console)
        assert errors == 0
        assert "run `cass index`" not in buf.getvalue()
        assert "cass models install" in buf.getvalue()
        assert "cass index --semantic" in buf.getvalue()

    def test_no_semantic_hint_when_model_installed(self, tmp_path: Path) -> None:
        """No semantic model hint when a model is already downloaded."""
        buf = io.StringIO()
        console = Console(file=buf, width=120)

        def fake_which(name):
            return {"cass": MISE_CASS_BIN, "claude": MISE_CLAUDE_BIN}.get(name)

        with (
            _fake_home_patch(tmp_path),
            patch("install.shutil.which", side_effect=fake_which),
            patch("install.run_cass_update", return_value=(True, "")),
            patch("install.uninstall_package", return_value=(True, "")),
            patch("install.run_claude_plugin", return_value=(True, "[]")),
        ):
            index_dir = install.cass_index_dir()
            index_dir.mkdir(parents=True)
            (index_dir / "index.db").touch()
            model_dir = index_dir / "models" / "all-MiniLM-L6-v2"
            model_dir.mkdir(parents=True)
            (model_dir / "model.onnx").touch()
            errors = install.ensure_cass(Path("/repo"), console)
        assert errors == 0
        assert "cass models install" not in buf.getvalue()


class TestCassIndexPopulated:
    def test_false_when_dir_missing(self, tmp_path: Path) -> None:
        with _fake_home_patch(tmp_path):
            assert install.cass_index_populated() is False

    def test_false_when_dir_empty(self, tmp_path: Path) -> None:
        with _fake_home_patch(tmp_path):
            install.cass_index_dir().mkdir(parents=True)
            assert install.cass_index_populated() is False

    def test_true_when_dir_has_contents(self, tmp_path: Path) -> None:
        with _fake_home_patch(tmp_path):
            index_dir = install.cass_index_dir()
            index_dir.mkdir(parents=True)
            (index_dir / "index.db").touch()
            assert install.cass_index_populated() is True

    def test_false_when_dir_unreadable(self, tmp_path: Path) -> None:
        with _fake_home_patch(tmp_path):
            install.cass_index_dir().mkdir(parents=True)
            with patch.object(Path, "iterdir", side_effect=PermissionError("denied")):
                assert install.cass_index_populated() is False


class TestCassSemanticModelInstalled:
    def test_false_when_models_dir_missing(self, tmp_path: Path) -> None:
        with _fake_home_patch(tmp_path):
            assert install.cass_semantic_model_installed() is False

    def test_false_when_models_dir_empty(self, tmp_path: Path) -> None:
        with _fake_home_patch(tmp_path):
            (install.cass_index_dir() / "models").mkdir(parents=True)
            assert install.cass_semantic_model_installed() is False

    def test_false_when_model_subdir_has_no_onnx(self, tmp_path: Path) -> None:
        with _fake_home_patch(tmp_path):
            model_dir = install.cass_index_dir() / "models" / "some-model"
            model_dir.mkdir(parents=True)
            (model_dir / "config.json").touch()
            assert install.cass_semantic_model_installed() is False

    def test_true_when_model_onnx_exists(self, tmp_path: Path) -> None:
        with _fake_home_patch(tmp_path):
            model_dir = install.cass_index_dir() / "models" / "all-MiniLM-L6-v2"
            model_dir.mkdir(parents=True)
            (model_dir / "model.onnx").touch()
            assert install.cass_semantic_model_installed() is True

    def test_false_when_models_dir_unreadable(self, tmp_path: Path) -> None:
        with _fake_home_patch(tmp_path):
            (install.cass_index_dir() / "models").mkdir(parents=True)
            with patch.object(Path, "iterdir", side_effect=PermissionError("denied")):
                assert install.cass_semantic_model_installed() is False


class TestRunManagedSubprocess:
    def test_permission_error_returns_failure_not_raises(self) -> None:
        """A non-executable script (PermissionError) degrades gracefully like every
        other failure mode here, instead of crashing the caller (e.g. ensure_cass)."""
        with patch("install.subprocess.run", side_effect=PermissionError("denied")):
            ok, detail = install.run_managed_subprocess(["./script"], timeout=5)

        assert ok is False
        assert detail == "denied"


class TestPackageInstall:
    def test_base_packages_installed(self, tmp_path: Path) -> None:
        """Base bundle packages install on a fresh run with nothing present."""
        repo = _minimal_repo(tmp_path)
        claude_dir = tmp_path / "claude"

        config = {"bundles": dict.fromkeys(install.optional_bundles(repo), False)}
        mock_install = MagicMock(return_value=(True, ""))
        with (
            patch("install.install_package", mock_install),
            patch("install.get_installed_packages", return_value=set()),
            _fake_home_patch(tmp_path),
        ):
            install.do_install(repo, claude_dir, config, interactive=False)

        # install_package is called as install_package(repo_dir, pkg_name)
        installed = [call.args[1] for call in mock_install.call_args_list]
        assert sorted(installed) == sorted(install.get_bundles(repo)["base"].packages)

    def test_base_package_failure_increments_errors(self, tmp_path: Path) -> None:
        """A failed base-package install is counted in the returned error total."""
        repo = _minimal_repo(tmp_path)
        claude_dir = tmp_path / "claude"

        config = {"bundles": dict.fromkeys(install.optional_bundles(repo), False)}
        with (
            patch("install.install_package", return_value=(False, "uv not found")),
            patch("install.get_installed_packages", return_value=set()),
            _fake_home_patch(tmp_path),
        ):
            errors = install.do_install(repo, claude_dir, config, interactive=False)

        # cass contributes 0 errors here — the autouse stub makes ensure_cass succeed.
        assert errors == len(install.get_bundles(repo)["base"].packages)

    def test_base_packages_skip_only_already_present(self, tmp_path: Path) -> None:
        """Only base packages missing from the installed set get (re)installed."""
        repo = _minimal_repo(tmp_path)
        claude_dir = tmp_path / "claude"

        base_pkgs = install.get_bundles(repo)["base"].packages
        missing = base_pkgs[0]
        already_present = set(base_pkgs[1:])

        config = {"bundles": dict.fromkeys(install.optional_bundles(repo), False)}
        mock_install = MagicMock(return_value=(True, ""))
        with (
            patch("install.install_package", mock_install),
            patch("install.get_installed_packages", return_value=already_present),
            _fake_home_patch(tmp_path),
        ):
            install.do_install(repo, claude_dir, config, interactive=False)

        mock_install.assert_called_once_with(repo, missing)


class TestDoUninstall:
    def test_base_packages_uninstalled_without_config(self, tmp_path: Path) -> None:
        """Even with no config, base bundle packages are uninstalled. ccrecall is not
        a uv-tool package removal target here — do_install's ensure_cass already
        removes it once cass is confirmed present."""
        repo = _minimal_repo(tmp_path)
        claude_dir = tmp_path / "claude"
        claude_dir.mkdir()

        mock_uninstall = MagicMock(return_value=(True, ""))
        with (
            patch("install.uninstall_package", mock_uninstall),
            _fake_home_patch(tmp_path),
        ):
            install.do_uninstall(repo, claude_dir, {})

        # uninstall_package is called as uninstall_package(pkg_name)
        uninstalled = {call.args[0] for call in mock_uninstall.call_args_list}
        assert uninstalled == set(install.get_bundles(repo)["base"].packages)

    def test_removes_cass_binary(self, tmp_path: Path) -> None:
        """do_uninstall deletes ~/.local/bin/cass when present and cass_state_dir()
        (written exclusively by bin/cass-update) confirms Claudefiles put it there."""
        repo = _minimal_repo(tmp_path)
        claude_dir = tmp_path / "claude"
        claude_dir.mkdir()

        with (
            _fake_home_patch(tmp_path),
            patch("install.uninstall_package", return_value=(True, "")),
        ):
            cass_bin = install.local_bin_dir() / "cass"
            cass_bin.write_text("#!/bin/sh\n")
            install.cass_state_dir().mkdir(parents=True)
            install.do_uninstall(repo, claude_dir, {})
            assert not cass_bin.exists()

    def test_preserves_cass_binary_without_state_dir(self, tmp_path: Path) -> None:
        """A binary at ~/.local/bin/cass is left alone if cass_state_dir() doesn't
        exist — the ownership check that stops do_uninstall from deleting a binary
        Claudefiles never installed (e.g. manually placed, or installed by another
        tool at the same path)."""
        repo = _minimal_repo(tmp_path)
        claude_dir = tmp_path / "claude"
        claude_dir.mkdir()

        with (
            _fake_home_patch(tmp_path),
            patch("install.uninstall_package", return_value=(True, "")),
        ):
            cass_bin = install.local_bin_dir() / "cass"
            cass_bin.write_text("#!/bin/sh\n")
            install.do_uninstall(repo, claude_dir, {})
            assert cass_bin.exists()

    def test_missing_cass_binary_is_silent_no_op(self, tmp_path: Path) -> None:
        """A missing cass binary is a silent no-op, not an error."""
        repo = _minimal_repo(tmp_path)
        claude_dir = tmp_path / "claude"
        claude_dir.mkdir()

        with (
            _fake_home_patch(tmp_path),
            patch("install.uninstall_package", return_value=(True, "")),
        ):
            install.do_uninstall(repo, claude_dir, {})  # must not raise

    def test_removes_cass_state_dir(self, tmp_path: Path) -> None:
        """do_uninstall deletes ~/.local/share/claudefiles-cass/ when present."""
        repo = _minimal_repo(tmp_path)
        claude_dir = tmp_path / "claude"
        claude_dir.mkdir()

        with (
            _fake_home_patch(tmp_path),
            patch("install.uninstall_package", return_value=(True, "")),
        ):
            state_dir = install.cass_state_dir()
            state_dir.mkdir(parents=True)
            (state_dir / "last-update-check").write_text("")
            install.do_uninstall(repo, claude_dir, {})
            assert not state_dir.exists()

    def test_attempts_ccrecall_plugin_cleanup(self, tmp_path: Path) -> None:
        """do_uninstall best-effort uninstalls any lingering ccrecall plugin
        registration — for a machine that goes straight to uninstall without ever
        running install.py post-migration."""
        repo = _minimal_repo(tmp_path)
        claude_dir = tmp_path / "claude"
        claude_dir.mkdir()

        mock_plugin = MagicMock(return_value=(True, ""))
        with (
            _fake_home_patch(tmp_path),
            patch("install.uninstall_package", return_value=(True, "")),
            patch("install.shutil.which", return_value=USR_BIN_CLAUDE),
            patch("install.run_claude_plugin", mock_plugin),
        ):
            install.do_uninstall(repo, claude_dir, {})

        mock_plugin.assert_called_once_with(
            USR_BIN_CLAUDE, ["uninstall", install.CCRECALL_PLUGIN_REF]
        )

    def test_skips_plugin_cleanup_when_claude_absent(self, tmp_path: Path) -> None:
        """A missing claude binary makes the plugin cleanup a no-op, not an error."""
        repo = _minimal_repo(tmp_path)
        claude_dir = tmp_path / "claude"
        claude_dir.mkdir()

        mock_plugin = MagicMock()
        with (
            _fake_home_patch(tmp_path),
            patch("install.uninstall_package", return_value=(True, "")),
            patch("install.shutil.which", return_value=None),
            patch("install.run_claude_plugin", mock_plugin),
        ):
            install.do_uninstall(repo, claude_dir, {})

        mock_plugin.assert_not_called()


# ---------------------------------------------------------------------------
# Worktree detection tests
# ---------------------------------------------------------------------------


class TestIsGitWorktree:
    def test_returns_false_when_git_not_found(self, tmp_path: Path) -> None:
        with patch("install.subprocess.run", side_effect=FileNotFoundError):
            assert install.is_git_worktree(tmp_path) is False

    def test_returns_false_on_timeout(self, tmp_path: Path) -> None:
        with patch(
            "install.subprocess.run", side_effect=subprocess.TimeoutExpired("git", 5)
        ):
            assert install.is_git_worktree(tmp_path) is False

    def test_returns_false_when_git_dir_equals_common_dir(self, tmp_path: Path) -> None:
        results = [
            MagicMock(returncode=0, stdout=".git\n"),
            MagicMock(returncode=0, stdout=".git\n"),
        ]
        with patch("install.subprocess.run", side_effect=results):
            assert install.is_git_worktree(tmp_path) is False

    def test_returns_true_when_dirs_differ(self, tmp_path: Path) -> None:
        results = [
            MagicMock(returncode=0, stdout="/repo/.git/worktrees/branch\n"),
            MagicMock(returncode=0, stdout="/repo/.git\n"),
        ]
        with patch("install.subprocess.run", side_effect=results):
            assert install.is_git_worktree(tmp_path) is True

    def test_returns_false_when_git_fails(self, tmp_path: Path) -> None:
        mock_result = MagicMock()
        mock_result.returncode = 128
        mock_result.stdout = ""
        with patch("install.subprocess.run", return_value=mock_result):
            assert install.is_git_worktree(tmp_path) is False


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
            "bundles": {
                "frontend": True,
                "cli": False,
                "engineering": False,
                "extra-agents": False,
            },
        }
        cfg_path = install.config_path(claude_dir)
        install.save_config(cfg_path, saved)

        mock_do_install = MagicMock(return_value=0)
        with (
            patch("sys.argv", ["install.py"]),
            patch("install.is_git_worktree", return_value=False),
            patch("install.do_install", mock_do_install),
            patch.dict(os.environ, {"CLAUDE_CONFIG_DIR": str(claude_dir)}),
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

        mock_do_install = MagicMock(return_value=0)
        with (
            patch("sys.argv", ["install.py"]),
            patch("install.is_git_worktree", return_value=False),
            patch("install.do_install", mock_do_install),
            patch.dict(os.environ, {"CLAUDE_CONFIG_DIR": str(claude_dir)}),
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

        saved = {
            "bundles": {
                "frontend": False,
                "cli": False,
                "engineering": False,
                "extra-agents": False,
            },
        }
        cfg_path = install.config_path(claude_dir)
        install.save_config(cfg_path, saved)

        mock_do_install = MagicMock(return_value=0)
        with (
            patch("sys.argv", ["install.py", "--reconfigure"]),
            patch("install.is_git_worktree", return_value=False),
            patch("install.do_install", mock_do_install),
            patch.dict(os.environ, {"CLAUDE_CONFIG_DIR": str(claude_dir)}),
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

        save_order: list[str] = []

        def mock_do_install(*args, **kwargs):
            save_order.append("install")
            return 0

        def mock_save_config(*args, **kwargs):
            save_order.append("save")

        with (
            patch("sys.argv", ["install.py"]),
            patch("install.is_git_worktree", return_value=False),
            patch("install.do_install", side_effect=mock_do_install),
            patch("install.save_config", side_effect=mock_save_config),
            patch.dict(os.environ, {"CLAUDE_CONFIG_DIR": str(claude_dir)}),
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
            lock_file = str(cfg_path) + install.LOCK_SUFFIX
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

        config = {
            "bundles": {
                "frontend": False,
                "cli": True,
                "engineering": False,
                "extra-agents": False,
            }
        }
        with (
            patch("install.install_package"),
            patch("install.get_installed_packages", return_value=BASE_PACKAGES),
            _fake_home_patch(tmp_path),
        ):
            install.do_install(repo, claude_dir, config, interactive=False)

        assert (claude_dir / "rules" / "common" / "capabilities-cli.md").is_symlink()
        assert not (
            claude_dir / "rules" / "common" / "capabilities-impeccable.md"
        ).exists()

    def test_capabilities_files_removed_on_deselect(self, tmp_path: Path) -> None:
        """capabilities-*.md files removed from rules/common/ when bundle deselected."""
        repo = tmp_path / "repo"
        claude_dir = tmp_path / "claude"
        _setup_full_repo(repo)

        config_v1 = {
            "bundles": {
                "frontend": False,
                "cli": True,
                "engineering": False,
                "extra-agents": False,
            }
        }
        config_v2 = {
            "bundles": {
                "frontend": False,
                "cli": False,
                "engineering": False,
                "extra-agents": False,
            }
        }
        with (
            patch("install.install_package"),
            patch("install.get_installed_packages", return_value=BASE_PACKAGES),
            _fake_home_patch(tmp_path),
        ):
            install.do_install(repo, claude_dir, config_v1, interactive=False)

        assert (claude_dir / "rules" / "common" / "capabilities-cli.md").is_symlink()

        with (
            patch("install.install_package"),
            patch("install.get_installed_packages", return_value=BASE_PACKAGES),
            _fake_home_patch(tmp_path),
        ):
            install.do_install(
                repo, claude_dir, config_v2, prev_config=config_v1, interactive=False
            )

        assert not (claude_dir / "rules" / "common" / "capabilities-cli.md").exists()


# ---------------------------------------------------------------------------
# Config migration tests (v1 → v2)
# ---------------------------------------------------------------------------


V1_ALL_SELECTED = {
    "version": install.CONFIG_VERSION_V1,
    "skills": {
        "core": True,
        "impeccable": True,
        "cli": True,
    },
    "agents": {
        "core": True,
        "engineering": True,
        "memory": True,
    },
    "packages": {
        "spec-helper": True,
        "merge-settings": True,
        "ado-api": True,
    },
    "hooks": {
        "all": True,
    },
}

V1_NONE_SELECTED = {
    "version": install.CONFIG_VERSION_V1,
    "skills": {
        "core": False,
        "impeccable": False,
        "cli": False,
    },
    "agents": {
        "core": False,
        "engineering": False,
        "memory": False,
    },
    "packages": {
        "spec-helper": False,
        "merge-settings": False,
        "ado-api": False,
    },
    "hooks": {
        "all": False,
    },
}


class TestMigrateV1ToV2:
    def test_all_selected_maps_all_bundles_true(self) -> None:
        result = install.migrate_v1_to_v2(V1_ALL_SELECTED)
        assert result["version"] == install.CONFIG_VERSION
        bundles = result["bundles"]
        assert bundles["frontend"] is True
        assert bundles["cli"] is True
        assert bundles["engineering"] is True
        assert bundles["extra-agents"] is True

    def test_none_selected_maps_all_bundles_false(self) -> None:
        result = install.migrate_v1_to_v2(V1_NONE_SELECTED)
        bundles = result["bundles"]
        assert bundles["frontend"] is False
        assert bundles["cli"] is False
        assert bundles["engineering"] is False
        assert bundles["extra-agents"] is False

    def test_partial_impeccable_only(self) -> None:
        v1 = {
            "version": install.CONFIG_VERSION_V1,
            "skills": {"core": True, "impeccable": True, "cli": False, "memory": False},
            "agents": {"core": False, "engineering": False, "memory": False},
            "packages": {},
        }
        result = install.migrate_v1_to_v2(v1)
        bundles = result["bundles"]
        assert bundles["frontend"] is True
        assert bundles["cli"] is False
        assert bundles["engineering"] is False
        assert bundles["extra-agents"] is False

    def test_agents_core_deselected_extra_agents_false(self) -> None:
        """agents.core=False → extra-agents=False (base agents still install)."""
        v1 = {
            "version": install.CONFIG_VERSION_V1,
            "skills": {},
            "agents": {"core": False, "engineering": False},
            "packages": {},
        }
        result = install.migrate_v1_to_v2(v1)
        assert result["bundles"]["extra-agents"] is False

    def test_agents_core_selected_extra_agents_true(self) -> None:
        """agents.core=True → extra-agents=True."""
        v1 = {
            "version": install.CONFIG_VERSION_V1,
            "skills": {},
            "agents": {"core": True, "engineering": False},
            "packages": {},
        }
        result = install.migrate_v1_to_v2(v1)
        assert result["bundles"]["extra-agents"] is True

    def test_skills_core_false_does_not_affect_bundles(self) -> None:
        """skills.core=False is ignored; base always installs (no bundle for it)."""
        v1 = {
            "version": install.CONFIG_VERSION_V1,
            "skills": {
                "core": False,
                "impeccable": False,
                "cli": False,
                "memory": False,
            },
            "agents": {},
            "packages": {},
        }
        result = install.migrate_v1_to_v2(v1)
        # No bundle key for 'base' in the v2 bundles section (base is always_installed)
        assert "base" not in result["bundles"]

    def test_missing_v1_fields_default_false(self) -> None:
        """Completely empty v1 config → all optional bundles false."""
        result = install.migrate_v1_to_v2({"version": install.CONFIG_VERSION_V1})
        for key in ("frontend", "cli", "engineering", "extra-agents"):
            assert result["bundles"][key] is False

    def test_result_is_v2_format(self) -> None:
        """Result has version and bundles keys only (no packages)."""
        result = install.migrate_v1_to_v2(V1_ALL_SELECTED)
        assert set(result.keys()) == {"version", "bundles"}

    def test_is_pure_no_io(self, tmp_path: Path) -> None:
        """migrate_v1_to_v2 must not write any files."""
        files_before = set(os.listdir(tmp_path))
        install.migrate_v1_to_v2(V1_ALL_SELECTED)
        files_after = set(os.listdir(tmp_path))
        assert files_before == files_after


class TestLoadConfigReturnsV1:
    def test_v1_config_returned_for_migration(self, tmp_path: Path) -> None:
        """load_config must return the raw dict for v1 config (not None)."""
        cfg_path = tmp_path / install.CONFIG_FILENAME
        v1_data = {"version": install.CONFIG_VERSION_V1, "skills": {"core": True}}
        cfg_path.write_text(json.dumps(v1_data))
        result = install.load_config(cfg_path)
        assert result is not None
        assert result["version"] == install.CONFIG_VERSION_V1

    def test_unknown_version_still_returns_none(self, tmp_path: Path) -> None:
        """load_config returns None for truly unknown versions (e.g. 999)."""
        cfg_path = tmp_path / install.CONFIG_FILENAME
        cfg_path.write_text(json.dumps({"version": UNKNOWN_CONFIG_VERSION}))
        assert install.load_config(cfg_path) is None


class TestMigrationMainFlow:
    """Test main() detects v1 config, migrates, backs up, and saves v2."""

    @staticmethod
    def _write_v1_config(cfg_path: Path, v1_data: dict) -> None:
        cfg_path.write_text(json.dumps(v1_data))

    def test_v1_config_triggers_migration(self, tmp_path: Path) -> None:
        """When main() sees a v1 config, it must migrate and save v2."""
        claude_dir = tmp_path / "claude_home"
        claude_dir.mkdir()
        repo = _minimal_repo(tmp_path)

        cfg_path = install.config_path(claude_dir)
        v1 = {
            "version": install.CONFIG_VERSION_V1,
            "skills": {"core": True, "impeccable": True, "cli": False, "memory": False},
            "agents": {"core": True, "engineering": False},
            "packages": {"ado-api": False},
        }
        self._write_v1_config(cfg_path, v1)

        saved_configs: list[dict] = []

        def capture_save(path, data):
            saved_configs.append(data)

        mock_do_install = MagicMock(return_value=0)
        with (
            patch("sys.argv", ["install.py"]),
            patch("install.is_git_worktree", return_value=False),
            patch("install.do_install", mock_do_install),
            patch("install.save_config", side_effect=capture_save),
            patch.dict(os.environ, {"CLAUDE_CONFIG_DIR": str(claude_dir)}),
            patch("install.sys") as mock_sys,
        ):
            mock_sys.stdin.isatty.return_value = False
            mock_sys.exit = sys.exit
            with patch.object(install, "__file__", str(repo / "install.py")):
                result = install.main()

        assert result == 0
        # save_config must have been called with v2 data
        assert len(saved_configs) == 1
        assert saved_configs[0]["bundles"]["frontend"] is True
        assert saved_configs[0]["bundles"]["extra-agents"] is True
        assert "packages" not in saved_configs[0]

    def test_v1_backup_written(self, tmp_path: Path) -> None:
        """Backup file .claudefiles-install-config.v1.json.bak must be written."""
        claude_dir = tmp_path / "claude_home"
        claude_dir.mkdir()
        repo = _minimal_repo(tmp_path)

        cfg_path = install.config_path(claude_dir)
        v1 = {
            "version": install.CONFIG_VERSION_V1,
            "skills": {"core": True, "impeccable": False, "cli": False, "memory": True},
            "agents": {"core": False, "engineering": True},
            "packages": {"ado-api": True},
        }
        self._write_v1_config(cfg_path, v1)

        mock_do_install = MagicMock(return_value=0)
        with (
            patch("sys.argv", ["install.py"]),
            patch("install.is_git_worktree", return_value=False),
            patch("install.do_install", mock_do_install),
            patch.dict(os.environ, {"CLAUDE_CONFIG_DIR": str(claude_dir)}),
            patch("install.sys") as mock_sys,
        ):
            mock_sys.stdin.isatty.return_value = False
            mock_sys.exit = sys.exit
            with patch.object(install, "__file__", str(repo / "install.py")):
                install.main()

        bak_path = claude_dir / ".claudefiles-install-config.v1.json.bak"
        assert bak_path.exists(), "Backup file must be written"
        bak_data = json.loads(bak_path.read_text())
        assert bak_data["version"] == install.CONFIG_VERSION_V1
        assert bak_data["packages"]["ado-api"] is True

    def test_v1_backup_is_raw_v1_data(self, tmp_path: Path) -> None:
        """Backup must contain original v1 content, not v2."""
        claude_dir = tmp_path / "claude_home"
        claude_dir.mkdir()
        repo = _minimal_repo(tmp_path)

        cfg_path = install.config_path(claude_dir)
        v1 = {
            "version": install.CONFIG_VERSION_V1,
            "skills": {"core": True},
            "agents": {},
            "packages": {},
        }
        self._write_v1_config(cfg_path, v1)

        mock_do_install = MagicMock(return_value=0)
        with (
            patch("sys.argv", ["install.py"]),
            patch("install.is_git_worktree", return_value=False),
            patch("install.do_install", mock_do_install),
            patch.dict(os.environ, {"CLAUDE_CONFIG_DIR": str(claude_dir)}),
            patch("install.sys") as mock_sys,
        ):
            mock_sys.stdin.isatty.return_value = False
            mock_sys.exit = sys.exit
            with patch.object(install, "__file__", str(repo / "install.py")):
                install.main()

        bak_path = claude_dir / ".claudefiles-install-config.v1.json.bak"
        bak_data = json.loads(bak_path.read_text())
        # Must NOT have been stamped with version=2 by save_config
        assert bak_data["version"] == install.CONFIG_VERSION_V1
        assert "bundles" not in bak_data

    def test_v2_config_not_migrated(self, tmp_path: Path) -> None:
        """A valid v2 config must not trigger migration."""
        claude_dir = tmp_path / "claude_home"
        claude_dir.mkdir()
        repo = _minimal_repo(tmp_path)

        cfg_path = install.config_path(claude_dir)
        v2 = {
            "bundles": {
                "frontend": False,
                "cli": False,
                "engineering": False,
                "extra-agents": False,
            },
        }
        install.save_config(cfg_path, v2)

        mock_do_install = MagicMock(return_value=0)
        with (
            patch("sys.argv", ["install.py"]),
            patch("install.is_git_worktree", return_value=False),
            patch("install.do_install", mock_do_install),
            patch("install.save_config"),
            patch.dict(os.environ, {"CLAUDE_CONFIG_DIR": str(claude_dir)}),
            patch("install.sys") as mock_sys,
        ):
            mock_sys.stdin.isatty.return_value = False
            mock_sys.exit = sys.exit
            with patch.object(install, "__file__", str(repo / "install.py")):
                install.main()

        bak_path = claude_dir / ".claudefiles-install-config.v1.json.bak"
        assert not bak_path.exists(), "No backup should be written for v2 config"

    def test_dry_run_v1_writes_no_backup_and_no_save(self, tmp_path: Path) -> None:
        """--dry-run with a v1 config must not write the backup or save config."""
        claude_dir = tmp_path / "claude_home"
        claude_dir.mkdir()
        repo = _minimal_repo(tmp_path)

        cfg_path = install.config_path(claude_dir)
        v1 = {
            "version": install.CONFIG_VERSION_V1,
            "skills": {"core": True, "impeccable": True, "cli": False, "memory": False},
            "agents": {"core": True, "engineering": False},
            "packages": {"ado-api": False},
        }
        self._write_v1_config(cfg_path, v1)

        mock_do_install = MagicMock(return_value=0)
        mock_save = MagicMock()
        with (
            patch("sys.argv", ["install.py", "--dry-run"]),
            patch("install.is_git_worktree", return_value=False),
            patch("install.do_install", mock_do_install),
            patch("install.save_config", mock_save),
            patch.dict(os.environ, {"CLAUDE_CONFIG_DIR": str(claude_dir)}),
            patch("install.sys") as mock_sys,
        ):
            mock_sys.stdin.isatty.return_value = False
            mock_sys.exit = sys.exit
            with patch.object(install, "__file__", str(repo / "install.py")):
                result = install.main()

        assert result == 0
        bak_path = claude_dir / ".claudefiles-install-config.v1.json.bak"
        assert not bak_path.exists(), "--dry-run must not write the v1 backup"
        mock_save.assert_not_called()
        mock_do_install.assert_not_called()
        # The original v1 config on disk must be untouched.
        assert json.loads(cfg_path.read_text())["version"] == install.CONFIG_VERSION_V1


# ---------------------------------------------------------------------------
# First-install ado-api tip
# ---------------------------------------------------------------------------


class TestFirstInstallAdoTip:
    """The ado-api discoverability tip prints only on fresh installs."""

    def test_tip_prints_on_fresh_install(self, tmp_path: Path, capsys) -> None:
        """When no prior config exists (fresh install) and install succeeds, print the tip."""
        claude_dir = tmp_path / "claude_home"
        claude_dir.mkdir()
        repo = _minimal_repo(tmp_path)

        # No saved config file — fresh install
        mock_do_install = MagicMock(return_value=0)
        with (
            patch("sys.argv", ["install.py"]),
            patch("install.is_git_worktree", return_value=False),
            patch("install.do_install", mock_do_install),
            patch("install.save_config"),
            patch.dict(os.environ, {"CLAUDE_CONFIG_DIR": str(claude_dir)}),
            patch("install.sys") as mock_sys,
        ):
            mock_sys.stdin.isatty.return_value = False
            mock_sys.exit = sys.exit
            with patch.object(install, "__file__", str(repo / "install.py")):
                result = install.main()

        assert result == 0
        out = capsys.readouterr().out
        assert "ado-api" in out
        assert "uv tool install" in out

    def test_tip_suppressed_when_existing_config(self, tmp_path: Path, capsys) -> None:
        """When a saved config already exists, the tip must NOT print."""
        claude_dir = tmp_path / "claude_home"
        claude_dir.mkdir()
        repo = _minimal_repo(tmp_path)

        # Write an existing v2 config so original_saved is not None
        saved = {
            "bundles": {
                "frontend": False,
                "cli": False,
                "engineering": False,
                "extra-agents": False,
            },
        }
        cfg_path = install.config_path(claude_dir)
        install.save_config(cfg_path, saved)

        mock_do_install = MagicMock(return_value=0)
        with (
            patch("sys.argv", ["install.py"]),
            patch("install.is_git_worktree", return_value=False),
            patch("install.do_install", mock_do_install),
            patch("install.save_config"),
            patch.dict(os.environ, {"CLAUDE_CONFIG_DIR": str(claude_dir)}),
            patch("install.sys") as mock_sys,
        ):
            mock_sys.stdin.isatty.return_value = False
            mock_sys.exit = sys.exit
            with patch.object(install, "__file__", str(repo / "install.py")):
                result = install.main()

        assert result == 0
        out = capsys.readouterr().out
        assert "uv tool install" not in out

    def test_tip_suppressed_when_install_has_errors(
        self, tmp_path: Path, capsys
    ) -> None:
        """A fresh install that reported errors must NOT print the tip."""
        claude_dir = tmp_path / "claude_home"
        claude_dir.mkdir()
        repo = _minimal_repo(tmp_path)

        mock_do_install = MagicMock(return_value=1)  # one error
        with (
            patch("sys.argv", ["install.py"]),
            patch("install.is_git_worktree", return_value=False),
            patch("install.do_install", mock_do_install),
            patch("install.save_config"),
            patch.dict(os.environ, {"CLAUDE_CONFIG_DIR": str(claude_dir)}),
            patch("install.sys") as mock_sys,
        ):
            mock_sys.stdin.isatty.return_value = False
            mock_sys.exit = sys.exit
            with patch.object(install, "__file__", str(repo / "install.py")):
                result = install.main()

        assert result == 1
        assert "uv tool install" not in capsys.readouterr().out

    def test_tip_suppressed_on_reconfigure_without_config(
        self, tmp_path: Path, capsys
    ) -> None:
        """--reconfigure is an explicit choice, not a first encounter — no tip."""
        claude_dir = tmp_path / "claude_home"
        claude_dir.mkdir()
        repo = _minimal_repo(tmp_path)

        mock_do_install = MagicMock(return_value=0)
        with (
            patch("sys.argv", ["install.py", "--reconfigure"]),
            patch("install.is_git_worktree", return_value=False),
            patch("install.do_install", mock_do_install),
            patch("install.save_config"),
            patch(
                "install.run_wizard",
                return_value={
                    "bundles": {k: False for k in install.optional_bundles(repo)}
                },
            ),
            patch.dict(os.environ, {"CLAUDE_CONFIG_DIR": str(claude_dir)}),
            patch("install.sys") as mock_sys,
        ):
            mock_sys.stdin.isatty.return_value = True
            mock_sys.exit = sys.exit
            with patch.object(install, "__file__", str(repo / "install.py")):
                result = install.main()

        assert result == 0
        assert "uv tool install" not in capsys.readouterr().out
