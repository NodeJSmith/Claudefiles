"""Integration tests for scripts/hooks/tmux-autoname.sh.

Each test runs a real tmux server on a throwaway socket, so the hook's
rename-session, has-session, and session-option calls hit real tmux.
"""

import os
import shutil
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).parent.parent
HOOK = REPO_ROOT / "scripts" / "hooks" / "tmux-autoname.sh"

pytestmark = pytest.mark.skipif(
    shutil.which("tmux") is None, reason="tmux not installed"
)


def clean_env() -> dict[str, str]:
    return {k: v for k, v in os.environ.items() if not k.startswith(("GIT_", "TMUX"))}


def git(cwd: Path, *args: str) -> None:
    subprocess.run(
        ["git", "-C", str(cwd), *args], check=True, capture_output=True, env=clean_env()
    )


def make_repo(path: Path, branch: str) -> Path:
    path.mkdir(parents=True)
    git(path, "init", "-q", "-b", branch)
    git(
        path,
        "-c",
        "user.name=t",
        "-c",
        "user.email=t@t",
        "commit",
        "-q",
        "--allow-empty",
        "-m",
        "init",
    )
    return path


class TmuxServer:
    def __init__(self, socket: Path):
        self.socket = socket

    def tmux(self, *args: str) -> str:
        result = subprocess.run(
            ["tmux", "-S", str(self.socket), *args],
            capture_output=True,
            text=True,
            env=clean_env(),
            check=False,
        )
        return result.stdout.strip()

    def new_session(self, name: str, cwd: Path) -> str:
        """Start a detached session and return its pane id."""
        self.tmux("new-session", "-d", "-s", name, "-c", str(cwd))
        return self.tmux("display-message", "-p", "-t", f"={name}:", "#{pane_id}")

    def session_of(self, pane: str) -> str:
        return self.tmux("display-message", "-p", "-t", pane, "#{session_name}")

    def run_hook(self, pane: str, cwd: Path) -> subprocess.CompletedProcess:
        env = clean_env()
        env["TMUX"] = f"{self.socket},0,0"
        env["TMUX_PANE"] = pane
        return subprocess.run(
            [str(HOOK)],
            input="{}",
            capture_output=True,
            text=True,
            cwd=cwd,
            env=env,
            timeout=10,
            check=False,
        )


@pytest.fixture
def server(tmp_path):
    srv = TmuxServer(tmp_path / "tmux.sock")
    yield srv
    srv.tmux("kill-server")


def test_renames_to_project_and_branch(server, tmp_path):
    repo = make_repo(tmp_path / "Hassette", "main")
    pane = server.new_session("hassette", repo)

    result = server.run_hook(pane, repo)

    assert result.returncode == 0
    assert server.session_of(pane) == "hassette-main"
    assert '"hassette-main"' in result.stdout


def test_worktree_uses_main_clone_name(server, tmp_path):
    repo = make_repo(tmp_path / "Dotfiles", "main")
    worktree = tmp_path / "Dotfiles" / ".claude" / "worktrees" / "fix-thing"
    git(repo, "worktree", "add", "-q", "-b", "Fix/Thing", str(worktree))
    pane = server.new_session("dotfiles", worktree)

    server.run_hook(pane, worktree)

    assert server.session_of(pane) == "dotfiles-fix-thing"


def test_second_run_does_not_stack(server, tmp_path):
    repo = make_repo(tmp_path / "hassette", "main")
    pane = server.new_session("hassette", repo)

    server.run_hook(pane, repo)
    server.tmux("rename-session", "-t", pane, "hassette-picked-by-claude")
    server.run_hook(pane, repo)

    assert server.session_of(pane) == "hassette-picked-by-claude"


def test_collision_adds_random_suffix(server, tmp_path):
    repo = make_repo(tmp_path / "hassette", "main")
    server.new_session("hassette-main", repo)
    pane = server.new_session("hassette", repo)

    server.run_hook(pane, repo)

    name = server.session_of(pane)
    assert name.startswith("hassette-main-")
    assert len(name) == len("hassette-main-") + 4


def test_name_extending_desired_is_kept_and_marked(server, tmp_path):
    repo = make_repo(tmp_path / "hassette", "main")
    pane = server.new_session("hassette-main-x1y2", repo)

    server.run_hook(pane, repo)

    assert server.session_of(pane) == "hassette-main-x1y2"
    assert server.tmux("show-options", "-qv", "-t", pane, "@claude_autonamed") == "1"


def test_outside_git_uses_directory_name(server, tmp_path):
    plain = tmp_path / "Scratch Dir"
    plain.mkdir()
    pane = server.new_session("main", plain)

    server.run_hook(pane, plain)

    assert server.session_of(pane) == "scratch-dir"


def test_bare_tab_name_is_freed_outside_git(server, tmp_path):
    plain = tmp_path / "scratch"
    plain.mkdir()
    pane = server.new_session("scratch", plain)

    server.run_hook(pane, plain)

    name = server.session_of(pane)
    assert name.startswith("scratch-")
    assert len(name) == len("scratch-") + 4


def test_long_name_is_truncated(server, tmp_path):
    repo = make_repo(tmp_path / "claudefiles", "a-very-long-branch-name-for-testing")
    pane = server.new_session("claudefiles", repo)

    server.run_hook(pane, repo)

    name = server.session_of(pane)
    assert len(name) <= 30
    assert not name.endswith("-")


def test_silent_outside_tmux(tmp_path):
    result = subprocess.run(
        [str(HOOK)],
        input="{}",
        capture_output=True,
        text=True,
        cwd=tmp_path,
        env=clean_env(),
        check=False,
    )

    assert result.returncode == 0
    assert result.stdout == ""
