"""Tests for install.py."""

import json
import subprocess
import sys
from pathlib import Path
from unittest.mock import MagicMock, call, patch

import pytest

# install.py lives one level up and is a single-file script, not an installed package,
# so prepend its directory before importing it.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import install

REPO_ROOT = Path(__file__).resolve().parent.parent
CLAUDE_BIN = "/usr/bin/claude"
PLUGIN_LISTED = json.dumps([{"id": install.CCRECALL_PLUGIN_REF}])
NEW_PLUGIN_CALLS = [
    call(CLAUDE_BIN, ["list", "--json"]),
    call(CLAUDE_BIN, ["marketplace", "add", install.CCRECALL_MARKETPLACE_REPO]),
    call(CLAUDE_BIN, ["install", install.CCRECALL_PLUGIN_REF]),
]


def fake_plugin(listing: str = "[]", **failures: str) -> MagicMock:
    """Fake run_claude_plugin. `listing` is the list output; kwargs fail a subcommand."""

    def run(claude_bin, args):
        if args[0] in failures:
            return False, failures[args[0]]
        return True, listing if args[0] == "list" else ""

    return MagicMock(side_effect=run)


@pytest.fixture
def sandbox(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Path, Path]:
    """A fake repo and config dir, with HOME and every external command stubbed."""
    repo = tmp_path / "repo"
    for rel in (
        "skills/mine-a/SKILL.md",
        "agents/reviewer.md",
        "commands/mine-c.md",
        "scripts/hooks/hook.sh",
        "rules/common/style.md",
        "references/common/testing.md",
        "bin/tool",
        "bin/.private-lib.sh",
    ):
        (repo / rel).parent.mkdir(parents=True, exist_ok=True)
        (repo / rel).write_text("x")

    monkeypatch.setattr(Path, "home", lambda: tmp_path / "home")
    monkeypatch.setattr(install, "run_tool", MagicMock(return_value=(True, "")))
    monkeypatch.setattr(install, "run_claude_plugin", fake_plugin())
    monkeypatch.setattr(install.shutil, "which", lambda name: f"/usr/bin/{name}")
    return repo, tmp_path / "claude"


def uv_calls() -> list[list[str]]:
    return [c.args[0] for c in install.run_tool.call_args_list if c.args[0][0] == "uv"]


class TestLinking:
    def test_links_every_managed_item(self, sandbox: tuple[Path, Path]) -> None:
        repo, claude = sandbox
        assert install.do_install(repo, claude) == 0

        for rel in (
            "skills/mine-a",
            "agents/reviewer.md",
            "commands/mine-c.md",
            "scripts/hooks/hook.sh",
            "rules/common/style.md",
            "references/common/testing.md",
        ):
            assert (claude / rel).resolve() == repo / rel
        assert (Path.home() / ".local/bin/tool").resolve() == repo / "bin/tool"

    def test_skips_dotfiles(self, sandbox: tuple[Path, Path]) -> None:
        repo, claude = sandbox
        install.do_install(repo, claude)
        assert not (Path.home() / ".local/bin/.private-lib.sh").exists()

    def test_rerun_is_idempotent(self, sandbox: tuple[Path, Path]) -> None:
        repo, claude = sandbox
        assert install.do_install(repo, claude) == 0
        assert install.do_install(repo, claude) == 0
        assert (claude / "agents/reviewer.md").resolve() == repo / "agents/reviewer.md"

    def test_relinks_owned_symlink(self, sandbox: tuple[Path, Path]) -> None:
        repo, claude = sandbox
        dest = claude / "agents/reviewer.md"
        dest.parent.mkdir(parents=True)
        dest.symlink_to(repo / "agents/old.md")

        install.do_install(repo, claude)

        assert dest.resolve() == repo / "agents/reviewer.md"

    def test_leaves_unowned_symlink_and_real_file(
        self, sandbox: tuple[Path, Path], tmp_path: Path, capsys
    ) -> None:
        repo, claude = sandbox
        other = tmp_path / "other.md"
        other.write_text("theirs")
        unowned = claude / "agents/reviewer.md"
        unowned.parent.mkdir(parents=True)
        unowned.symlink_to(other)
        real = claude / "rules/common/style.md"
        real.parent.mkdir(parents=True)
        real.write_text("mine")

        assert install.do_install(repo, claude) == 0

        assert unowned.resolve() == other
        assert real.read_text() == "mine"
        out = capsys.readouterr().out
        assert str(unowned) in out and str(real) in out

    def test_keeps_users_own_files_alongside(self, sandbox: tuple[Path, Path]) -> None:
        repo, claude = sandbox
        mine = claude / "rules/common/my-rule.md"
        mine.parent.mkdir(parents=True)
        mine.write_text("mine")

        install.do_install(repo, claude)

        assert mine.read_text() == "mine"

    def test_missing_source_dir_is_skipped(self, sandbox: tuple[Path, Path]) -> None:
        repo, claude = sandbox
        for item in (repo / "commands").iterdir():
            item.unlink()
        (repo / "commands").rmdir()

        assert install.do_install(repo, claude) == 0

    def test_writes_no_state_file(self, sandbox: tuple[Path, Path]) -> None:
        repo, claude = sandbox
        install.do_install(repo, claude)
        assert not [p for p in claude.iterdir() if p.is_file()]

    @pytest.mark.parametrize("tree", ["rules", "references"])
    def test_every_real_subdir_is_linked(self, tree: str) -> None:
        """A new rules/ or references/ subdir must be added to LINKED_DIRS to install."""
        for sub in (REPO_ROOT / tree).iterdir():
            if sub.is_dir():
                assert f"{tree}/{sub.name}" in install.LINKED_DIRS


class TestOwnership:
    def test_prefix_collision_is_not_owned(self, tmp_path: Path) -> None:
        repo = tmp_path / "repo"
        repo.mkdir()
        sibling = tmp_path / "repo-other" / "file"
        sibling.parent.mkdir()
        sibling.write_text("x")
        link = tmp_path / "link"
        link.symlink_to(sibling)
        assert not install.is_owned_by(link, repo)

    def test_relative_target_is_resolved(self, tmp_path: Path) -> None:
        repo = tmp_path / "repo"
        repo.mkdir()
        (repo / "file").write_text("x")
        link = tmp_path / "link"
        link.symlink_to("repo/file")
        assert install.is_owned_by(link, repo)


class TestStaleSweep:
    @pytest.mark.parametrize(
        "rel", ["rules/common/retired.md", "skills/mine-retired", "agents/retired.md"]
    )
    def test_removes_owned_dangling_link(
        self, sandbox: tuple[Path, Path], rel: str
    ) -> None:
        repo, claude = sandbox
        link = claude / rel
        link.parent.mkdir(parents=True)
        link.symlink_to(repo / rel)

        install.do_install(repo, claude)

        assert not link.is_symlink()

    def test_removes_owned_dangling_link_in_bin(
        self, sandbox: tuple[Path, Path]
    ) -> None:
        repo, claude = sandbox
        link = Path.home() / ".local/bin/retired"
        link.parent.mkdir(parents=True)
        link.symlink_to(repo / "bin/retired")

        install.do_install(repo, claude)

        assert not link.is_symlink()

    def test_keeps_unowned_dangling_link(
        self, sandbox: tuple[Path, Path], tmp_path: Path
    ) -> None:
        repo, claude = sandbox
        link = claude / "rules/common/theirs.md"
        link.parent.mkdir(parents=True)
        link.symlink_to(tmp_path / "elsewhere/gone.md")

        install.do_install(repo, claude)

        assert link.is_symlink()


class TestPackages:
    def test_installs_packages_editable_and_skips_ccrecall_on_path(
        self, sandbox: tuple[Path, Path]
    ) -> None:
        repo, claude = sandbox
        install.do_install(repo, claude)
        assert uv_calls() == [
            ["uv", "tool", "install", "-e", str(repo / "packages" / name)]
            for name in install.PACKAGES
        ]

    def test_installs_ccrecall_when_absent(
        self, sandbox: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        repo, claude = sandbox
        monkeypatch.setattr(
            install.shutil,
            "which",
            lambda name: None if name == install.CCRECALL_PACKAGE else CLAUDE_BIN,
        )
        install.do_install(repo, claude)
        assert ["uv", "tool", "install", install.CCRECALL_PACKAGE] in uv_calls()

    def test_package_failure_counts_as_error_but_still_links(
        self, sandbox: tuple[Path, Path]
    ) -> None:
        repo, claude = sandbox
        install.run_tool.return_value = (False, "boom")

        assert install.do_install(repo, claude) == len(install.PACKAGES)
        assert (claude / "agents/reviewer.md").is_symlink()


class TestCcrecallPlugin:
    def test_installs_via_resolved_binary_when_absent(self) -> None:
        """Uses the shutil.which path, never bare `claude`: the shell function runs --bare."""
        run = fake_plugin()
        with (
            patch("install.shutil.which", return_value=CLAUDE_BIN),
            patch("install.run_claude_plugin", run),
        ):
            assert install.ensure_ccrecall_plugin() == 0
        assert run.call_args_list == NEW_PLUGIN_CALLS

    @pytest.mark.parametrize("listing", ["not json", '{"a": 1}', '["bad", 123, null]'])
    def test_malformed_list_counts_as_not_installed(self, listing: str) -> None:
        run = fake_plugin(listing)
        with (
            patch("install.shutil.which", return_value=CLAUDE_BIN),
            patch("install.run_claude_plugin", run),
        ):
            assert install.ensure_ccrecall_plugin() == 0
        assert run.call_args_list == NEW_PLUGIN_CALLS

    def test_updates_when_already_installed(self) -> None:
        run = fake_plugin(PLUGIN_LISTED)
        with (
            patch("install.shutil.which", return_value=CLAUDE_BIN),
            patch("install.run_claude_plugin", run),
        ):
            assert install.ensure_ccrecall_plugin() == 0
        assert run.call_args_list == [
            call(CLAUDE_BIN, ["list", "--json"]),
            call(CLAUDE_BIN, ["update", install.CCRECALL_PLUGIN_REF]),
        ]

    def test_update_failure_is_not_an_error(self) -> None:
        with (
            patch("install.shutil.which", return_value=CLAUDE_BIN),
            patch(
                "install.run_claude_plugin", fake_plugin(PLUGIN_LISTED, update="boom")
            ),
        ):
            assert install.ensure_ccrecall_plugin() == 0

    def test_marketplace_failure_is_not_an_error(self) -> None:
        run = fake_plugin(marketplace="boom")
        with (
            patch("install.shutil.which", return_value=CLAUDE_BIN),
            patch("install.run_claude_plugin", run),
        ):
            assert install.ensure_ccrecall_plugin() == 0
        assert run.call_args_list == NEW_PLUGIN_CALLS

    def test_install_failure_is_an_error(self) -> None:
        with (
            patch("install.shutil.which", return_value=CLAUDE_BIN),
            patch("install.run_claude_plugin", fake_plugin(install="boom")),
        ):
            assert install.ensure_ccrecall_plugin() == 1

    def test_skips_when_claude_absent(self) -> None:
        run = fake_plugin()
        with (
            patch("install.shutil.which", return_value=None),
            patch("install.run_claude_plugin", run),
        ):
            assert install.ensure_ccrecall_plugin() == 0
            install.remove_ccrecall_plugin()
        run.assert_not_called()

    def test_remove_uninstalls_when_installed(self) -> None:
        run = fake_plugin(PLUGIN_LISTED)
        with (
            patch("install.shutil.which", return_value=CLAUDE_BIN),
            patch("install.run_claude_plugin", run),
        ):
            install.remove_ccrecall_plugin()
        assert run.call_args_list == [
            call(CLAUDE_BIN, ["list", "--json"]),
            call(CLAUDE_BIN, ["uninstall", install.CCRECALL_PLUGIN_REF]),
        ]


class TestUninstall:
    def test_removes_owned_links_only(
        self, sandbox: tuple[Path, Path], tmp_path: Path
    ) -> None:
        repo, claude = sandbox
        install.do_install(repo, claude)
        other = tmp_path / "other.md"
        other.write_text("theirs")
        unowned = claude / "rules/common/theirs.md"
        unowned.symlink_to(other)

        install.do_uninstall(repo, claude)

        assert not (claude / "agents/reviewer.md").is_symlink()
        assert not (claude / "rules/common/style.md").is_symlink()
        assert not (Path.home() / ".local/bin/tool").is_symlink()
        assert unowned.resolve() == other

    def test_uninstalls_packages_and_plugin(self, sandbox: tuple[Path, Path]) -> None:
        repo, claude = sandbox
        install.run_claude_plugin = fake_plugin(PLUGIN_LISTED)

        install.do_uninstall(repo, claude)

        assert uv_calls() == [
            ["uv", "tool", "uninstall", name]
            for name in (*install.PACKAGES, install.CCRECALL_PACKAGE)
        ]
        install.run_claude_plugin.assert_called_with(
            "/usr/bin/claude", ["uninstall", install.CCRECALL_PLUGIN_REF]
        )


class TestRunTool:
    def test_returns_stripped_stdout(self) -> None:
        assert install.run_tool(["echo", "hi"], 5) == (True, "hi")

    def test_failure_returns_stderr(self) -> None:
        ok, detail = install.run_tool(["sh", "-c", "echo boom >&2; exit 3"], 5)
        assert (ok, detail) == (False, "boom")

    def test_missing_binary(self) -> None:
        assert install.run_tool(["no-such-binary-xyz"], 5) == (
            False,
            "no-such-binary-xyz not found",
        )

    def test_timeout(self) -> None:
        with patch(
            "install.subprocess.run", side_effect=subprocess.TimeoutExpired("x", 5)
        ):
            assert install.run_tool(["x"], 5) == (False, "timed out after 5s")


class TestIsGitWorktree:
    @pytest.fixture
    def repo(self, tmp_path: Path) -> Path:
        repo = tmp_path / "repo"
        repo.mkdir()
        for cmd in (
            ["init", "-q"],
            [
                "-c",
                "user.name=t",
                "-c",
                "user.email=t@example.com",
                "commit",
                "-q",
                "--allow-empty",
                "-m",
                "x",
            ],
        ):
            subprocess.run(["git", "-C", str(repo), *cmd], check=True)
        return repo

    def test_main_clone_is_not_worktree(self, repo: Path) -> None:
        assert install.is_git_worktree(repo) is False

    def test_worktree_is_detected(self, repo: Path, tmp_path: Path) -> None:
        worktree = tmp_path / "wt"
        subprocess.run(
            ["git", "-C", str(repo), "worktree", "add", "-q", str(worktree)],
            check=True,
        )
        assert install.is_git_worktree(worktree) is True

    def test_non_repo_is_not_worktree(self, tmp_path: Path) -> None:
        assert install.is_git_worktree(tmp_path) is False


class TestMain:
    def test_refuses_to_run_from_worktree(self) -> None:
        do_install = MagicMock()
        with (
            patch.object(sys, "argv", ["install.py"]),
            patch("install.is_git_worktree", return_value=True),
            patch("install.do_install", do_install),
        ):
            assert install.main() == 1
        do_install.assert_not_called()

    @pytest.mark.parametrize("errors,code", [(0, 0), (2, 1)])
    def test_exit_code_reflects_errors(
        self, errors: int, code: int, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("CLAUDE_CONFIG_DIR", "/tmp/fake-claude")
        do_install = MagicMock(return_value=errors)
        with (
            patch.object(sys, "argv", ["install.py"]),
            patch("install.is_git_worktree", return_value=False),
            patch("install.do_install", do_install),
        ):
            assert install.main() == code
        do_install.assert_called_once_with(REPO_ROOT, Path("/tmp/fake-claude"))

    def test_uninstall_flag(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("CLAUDE_CONFIG_DIR", "/tmp/fake-claude")
        do_uninstall = MagicMock()
        with (
            patch.object(sys, "argv", ["install.py", "--uninstall"]),
            patch("install.is_git_worktree", return_value=False),
            patch("install.do_uninstall", do_uninstall),
        ):
            assert install.main() == 0
        do_uninstall.assert_called_once_with(REPO_ROOT, Path("/tmp/fake-claude"))
