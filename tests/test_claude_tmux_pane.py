"""Tests for bin/claude-tmux-pane and the tmux tools that rely on it.

A Claude Code session moved to the background (left arrow on an empty prompt)
keeps running as a job in Claude's daemon. The job's process has no TMUX or
TMUX_PANE, but CLAUDE_JOB_DIR=<config>/jobs/<job>, and the pane's own Claude
(the front end) records "tmux": "<session>:@<window>.%<pane>" and
"parkedJobId": "<job>" in <config>/sessions/<pid>.json.

Each test runs a real tmux server as the *default* server under a throwaway
TMUX_TMPDIR, because a background job reaches tmux without $TMUX, the same way.
"""

import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).parent.parent
RESOLVER = REPO_ROOT / "bin" / "claude-tmux-pane"
CLAUDE_TMUX = REPO_ROOT / "bin" / "claude-tmux"
EDIT_MANIFEST = REPO_ROOT / "bin" / "edit-manifest"
AUTONAME_HOOK = REPO_ROOT / "scripts" / "hooks" / "tmux-autoname.sh"
DRIFT_HOOK = REPO_ROOT / "scripts" / "hooks" / "tmux-drift-check.sh"
JOB = "4609d4ad"

pytestmark = pytest.mark.skipif(
    shutil.which("tmux") is None, reason="tmux not installed"
)


class DefaultServer:
    """A tmux server at the default socket under its own TMUX_TMPDIR."""

    def __init__(self, tmpdir: Path):
        self.tmpdir = tmpdir

    def base_env(self) -> dict[str, str]:
        env = {
            k: v
            for k, v in os.environ.items()
            if not k.startswith(("GIT_", "TMUX", "CLAUDE_"))
        }
        env["TMUX_TMPDIR"] = str(self.tmpdir)
        return env

    def tmux(self, *args: str) -> str:
        result = subprocess.run(
            ["tmux", *args],
            capture_output=True,
            text=True,
            env=self.base_env(),
            check=False,
        )
        return result.stdout.strip()

    def new_session(self, name: str, cwd: Path) -> str:
        self.tmux("new-session", "-d", "-s", name, "-c", str(cwd))
        return self.tmux("display-message", "-p", "-t", f"={name}:", "#{pane_id}")

    def session_of(self, pane: str) -> str:
        return self.tmux("display-message", "-p", "-t", pane, "#{session_name}")


@pytest.fixture
def server():
    # Short path: tmux socket paths are capped near 100 characters.
    tmpdir = Path(tempfile.mkdtemp(prefix="ctp", dir="/tmp"))
    srv = DefaultServer(tmpdir)
    yield srv
    srv.tmux("kill-server")
    shutil.rmtree(tmpdir, ignore_errors=True)


@pytest.fixture
def config(tmp_path) -> Path:
    (tmp_path / "config" / "sessions").mkdir(parents=True)
    return tmp_path / "config"


def front_end_record(config: Path, pane: str, job: str = JOB, pid: int | None = None):
    record = {
        "pid": os.getpid() if pid is None else pid,
        "kind": "interactive",
        # The session name here is the one the front end started under; it goes stale.
        "tmux": f"stale-name:@0.{pane}",
        "parkedJobId": job,
    }
    (config / "sessions" / "front.json").write_text(json.dumps(record))


def job_env(server: DefaultServer, config: Path) -> dict[str, str]:
    env = server.base_env()
    env["CLAUDE_CONFIG_DIR"] = str(config)
    env["CLAUDE_JOB_DIR"] = str(config / "jobs" / JOB)
    return env


def run(cmd: list[str], env: dict[str, str], **kwargs) -> subprocess.CompletedProcess:
    return subprocess.run(
        cmd, capture_output=True, text=True, env=env, timeout=10, check=False, **kwargs
    )


class TestResolver:
    def test_prints_tmux_pane_when_set(self, server):
        env = server.base_env()
        env["TMUX"] = "/some/socket,1,0"
        env["TMUX_PANE"] = "%4"
        result = run([str(RESOLVER)], env)
        assert result.returncode == 0
        assert result.stdout.strip() == "%4"

    def test_finds_background_jobs_pane(self, server, config, tmp_path):
        pane = server.new_session("work", tmp_path)
        front_end_record(config, pane)
        result = run([str(RESOLVER)], job_env(server, config))
        assert result.returncode == 0
        assert result.stdout.strip() == pane

    def test_asks_tmux_when_only_tmux_is_set(self, server, tmp_path):
        server.new_session("work", tmp_path)
        pane = server.tmux("display-message", "-p", "-t", "=work:", "#{pane_id}")
        env = server.base_env()
        # Points at the throwaway default server, so plain `tmux` reaches it.
        env["TMUX"] = f"{server.tmpdir}/tmux-{os.getuid()}/default,1,0"
        result = run([str(RESOLVER)], env)
        assert result.returncode == 0
        assert result.stdout.strip() == pane

    def test_ignores_tmux_pane_inherited_without_tmux(self, server):
        env = server.base_env()
        env["TMUX_PANE"] = "%4"
        result = run([str(RESOLVER)], env)
        assert result.returncode == 1
        assert result.stdout == ""

    def test_skips_exited_front_end(self, server, config, tmp_path):
        pane = server.new_session("work", tmp_path)
        # Above any real pid_max, so no live process has it.
        front_end_record(config, pane, pid=2147483646)
        result = run([str(RESOLVER)], job_env(server, config))
        assert result.returncode == 1
        assert result.stdout == ""

    def test_skips_gone_pane(self, server, config, tmp_path):
        server.new_session("work", tmp_path)
        front_end_record(config, "%999")
        result = run([str(RESOLVER)], job_env(server, config))
        assert result.returncode == 1

    def test_ignores_another_jobs_front_end(self, server, config, tmp_path):
        pane = server.new_session("work", tmp_path)
        front_end_record(config, pane, job="4f9f4a02")
        result = run([str(RESOLVER)], job_env(server, config))
        assert result.returncode == 1

    def test_fails_outside_tmux_and_outside_a_job(self, server):
        result = run([str(RESOLVER)], server.base_env())
        assert result.returncode == 1
        assert result.stdout == ""


class TestInstalledLayout:
    """Scripts are installed as per-file symlinks (bin/ into ~/.local/bin, hooks
    into the config dir) and find claude-tmux-pane through their resolved path."""

    def test_claude_tmux_and_hook_work_through_symlinks(self, server, config, tmp_path):
        links = tmp_path / "installed"
        (links / "bin").mkdir(parents=True)
        (links / "hooks").mkdir()
        claude_tmux = links / "bin" / "claude-tmux"
        drift_hook = links / "hooks" / "tmux-drift-check.sh"
        claude_tmux.symlink_to(CLAUDE_TMUX)
        drift_hook.symlink_to(DRIFT_HOOK)
        pane = server.new_session("work", tmp_path)
        front_end_record(config, pane)
        env = job_env(server, config)

        current = run([str(claude_tmux), "current"], env)
        env["CLAUDE_TMUX_DRIFT_HEARTBEAT"] = "1"
        session_id = f"ctp-link-{os.getpid()}"
        try:
            drift = run(
                [str(drift_hook)], env, input=json.dumps({"session_id": session_id})
            )
        finally:
            Path(f"/tmp/claude-tmux-drift-{session_id}.txt").unlink(missing_ok=True)

        assert current.stdout.strip() == "work"
        assert "current name is work." in drift.stdout


class TestEditManifest:
    def test_falls_back_when_no_pane_shows_the_session(self, server, tmp_path):
        manifest = tmp_path / "manifest.md"
        manifest.write_text("x\n")
        env = server.base_env()
        env["HOME"] = str(tmp_path)
        result = run([str(EDIT_MANIFEST), str(manifest)], env)
        assert result.returncode == 2
        assert "No tmux detected" in result.stdout


class TestClaudeTmuxFromBackgroundJob:
    def test_rename_targets_the_jobs_pane(self, server, config, tmp_path):
        pane = server.new_session("work", tmp_path)
        server.new_session("other", tmp_path)
        front_end_record(config, pane)

        result = run(
            [str(CLAUDE_TMUX), "rename", "proj-feature"], job_env(server, config)
        )

        assert result.returncode == 0, result.stderr
        assert server.session_of(pane) == "proj-feature"
        assert (
            server.tmux("show-options", "-qv", "-t", pane, "@claude_autonamed") == "1"
        )
        assert server.tmux("has-session", "-t", "=other") == ""

    def test_current_reports_the_jobs_session(self, server, config, tmp_path):
        pane = server.new_session("work", tmp_path)
        front_end_record(config, pane)
        result = run([str(CLAUDE_TMUX), "current"], job_env(server, config))
        assert result.stdout.strip() == "work"

    def test_not_in_tmux_without_a_pane(self, server):
        result = run([str(CLAUDE_TMUX), "current"], server.base_env())
        assert result.returncode == 0
        assert result.stdout.strip() == "Not in tmux"


class TestHooksFromBackgroundJob:
    def test_autoname_names_the_jobs_session(self, server, config, tmp_path):
        work = tmp_path / "myproj"
        work.mkdir()
        pane = server.new_session("myproj", work)
        front_end_record(config, pane)

        result = run(
            [str(AUTONAME_HOOK)], job_env(server, config), input="{}", cwd=work
        )

        assert result.returncode == 0, result.stderr
        name = server.session_of(pane)
        assert name.startswith("myproj-")
        assert f'"{name}"' in result.stdout

    def test_drift_check_names_the_jobs_session(self, server, config, tmp_path):
        pane = server.new_session("work", tmp_path)
        front_end_record(config, pane)
        env = job_env(server, config)
        env["CLAUDE_TMUX_DRIFT_HEARTBEAT"] = "1"
        session_id = f"ctp-drift-{os.getpid()}"
        try:
            result = run(
                [str(DRIFT_HOOK)], env, input=json.dumps({"session_id": session_id})
            )
        finally:
            Path(f"/tmp/claude-tmux-drift-{session_id}.txt").unlink(missing_ok=True)

        assert result.returncode == 0, result.stderr
        assert "current name is work." in result.stdout
