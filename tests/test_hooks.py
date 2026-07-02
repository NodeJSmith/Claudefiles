"""Integration tests for hook scripts (tmux-drift, compaction).

Each test crafts JSON input matching the PreToolUse/PostToolUse schema, invokes
the hook via subprocess.run, and asserts on exit code and stdout.
"""

import hashlib
import json
import os
import shutil
import subprocess
import tempfile
import time
import uuid
from pathlib import Path

# Resolve hook paths relative to the repo root
REPO_ROOT = Path(__file__).parent.parent
COMPACTION_HOOK = REPO_ROOT / "scripts" / "hooks" / "subagent-compaction-check.sh"
CASS_UPDATE = REPO_ROOT / "bin" / "cass-update"
CASS_SESSION_START_HOOK = REPO_ROOT / "scripts" / "hooks" / "cass-session-start.sh"
CASS_CLEAR_HANDOFF_HOOK = REPO_ROOT / "scripts" / "hooks" / "cass-clear-handoff.sh"


def run_hook(
    script: Path,
    stdin: str,
    tmpdir: str | None = None,
    extra_env: dict | None = None,
    env: dict | None = None,
    timeout: float | None = None,
) -> subprocess.CompletedProcess:
    """Run a hook script with given stdin.

    Pass `tmpdir` for hooks that read CLAUDE_CODE_TMPDIR (sets it on a copy of
    the current environment, optionally overlaid with `extra_env`). Pass a
    full `env` override instead for hooks that don't consume
    CLAUDE_CODE_TMPDIR and need direct control over PATH/HOME.
    """
    if env is None:
        env = os.environ.copy()
        if tmpdir is not None:
            env["CLAUDE_CODE_TMPDIR"] = tmpdir
        if extra_env:
            env.update(extra_env)
    return subprocess.run(
        [str(script)],
        input=stdin,
        capture_output=True,
        text=True,
        env=env,
        timeout=timeout,
    )


# ---------------------------------------------------------------------------
# tmux-drift-check.sh tests
# ---------------------------------------------------------------------------

DRIFT_CHECK_HOOK = REPO_ROOT / "scripts" / "hooks" / "tmux-drift-check.sh"


def _drift_session_id(test_name: str) -> str:
    return f"drift-test-{test_name}-{uuid.uuid4().hex[:8]}"


def _write_drift_counter(session_id: str, count: int) -> Path:
    p = Path(f"/tmp/claude-tmux-drift-{session_id}.txt")
    p.write_text(str(count))
    return p


def _read_drift_counter(session_id: str) -> int | None:
    p = Path(f"/tmp/claude-tmux-drift-{session_id}.txt")
    if not p.exists():
        return None
    text = p.read_text().strip()
    return int(text) if text else None


def _cleanup_drift(session_id: str) -> None:
    p = Path(f"/tmp/claude-tmux-drift-{session_id}.txt")
    if p.exists():
        p.unlink()


def _make_tmux_stub(tmpdir: Path, session_name: str) -> Path:
    """Write a tmux stub script that prints session_name for display-message."""
    stub = tmpdir / "tmux"
    stub.write_text(f'#!/usr/bin/env bash\necho "{session_name}"\n')
    stub.chmod(0o755)
    return stub


def _run_drift_check(
    session_id: str,
    session_name: str = "test-session",
    extra_env: dict[str, str] | None = None,
    tmux_stub_dir: Path | None = None,
) -> subprocess.CompletedProcess:
    env = os.environ.copy()
    env["TMUX"] = "/tmp/tmux-stub,1,0"
    if tmux_stub_dir:
        env["PATH"] = str(tmux_stub_dir) + ":" + env.get("PATH", "")
        stub_ctx = None
    else:
        stub_ctx = tempfile.TemporaryDirectory()
        _td = Path(stub_ctx.name)
        _make_tmux_stub(_td, session_name)
        env["PATH"] = str(_td) + ":" + env.get("PATH", "")
    if extra_env:
        env.update(extra_env)
    try:
        return subprocess.run(
            [str(DRIFT_CHECK_HOOK)],
            input=json.dumps({"session_id": session_id}),
            capture_output=True,
            text=True,
            env=env,
        )
    finally:
        if stub_ctx is not None:
            stub_ctx.cleanup()


class TestTmuxDriftCheckSilentBelowInterval:
    """Hook stays silent while counter is below the heartbeat interval."""

    def test_first_call_silent(self):
        sid = _drift_session_id("first_silent")
        try:
            result = _run_drift_check(sid)
            assert result.returncode == 0
            assert result.stdout.strip() == ""
        finally:
            _cleanup_drift(sid)

    def test_below_interval_silent(self):
        sid = _drift_session_id("below_interval")
        try:
            _write_drift_counter(sid, 27)  # will become 28, threshold is 30
            result = _run_drift_check(
                sid, extra_env={"CLAUDE_TMUX_DRIFT_HEARTBEAT": "30"}
            )
            assert result.returncode == 0
            assert result.stdout.strip() == ""
            assert _read_drift_counter(sid) == 28
        finally:
            _cleanup_drift(sid)

    def test_counter_increments_each_call(self):
        sid = _drift_session_id("increments")
        try:
            _write_drift_counter(sid, 5)
            _run_drift_check(sid, extra_env={"CLAUDE_TMUX_DRIFT_HEARTBEAT": "30"})
            assert _read_drift_counter(sid) == 6
        finally:
            _cleanup_drift(sid)


class TestTmuxDriftCheckEmitsAtThreshold:
    """Hook emits session name context at the heartbeat threshold."""

    def test_emits_at_threshold(self):
        sid = _drift_session_id("at_threshold")
        try:
            _write_drift_counter(sid, 29)  # will become 30, fires
            result = _run_drift_check(
                sid,
                session_name="myapp-feature",
                extra_env={"CLAUDE_TMUX_DRIFT_HEARTBEAT": "30"},
            )
            assert result.returncode == 0
            output = json.loads(result.stdout)
            context = output["hookSpecificOutput"]["additionalContext"]
            assert "myapp-feature" in context
            assert "claude-tmux rename" in context
        finally:
            _cleanup_drift(sid)

    def test_counter_resets_after_firing(self):
        sid = _drift_session_id("resets")
        try:
            _write_drift_counter(sid, 29)
            _run_drift_check(sid, extra_env={"CLAUDE_TMUX_DRIFT_HEARTBEAT": "30"})
            assert _read_drift_counter(sid) == 0
        finally:
            _cleanup_drift(sid)

    def test_custom_heartbeat_interval(self):
        sid = _drift_session_id("custom_interval")
        try:
            _write_drift_counter(sid, 4)  # will become 5, fires at interval=5
            result = _run_drift_check(
                sid, extra_env={"CLAUDE_TMUX_DRIFT_HEARTBEAT": "5"}
            )
            assert result.returncode == 0
            assert result.stdout.strip() != ""
        finally:
            _cleanup_drift(sid)


class TestTmuxDriftCheckNoTmux:
    """Hook exits silently when not inside tmux."""

    def test_no_tmux_env_silent(self):
        sid = _drift_session_id("no_tmux")
        env = os.environ.copy()
        env.pop("TMUX", None)
        result = subprocess.run(
            [str(DRIFT_CHECK_HOOK)],
            input=json.dumps({"session_id": sid}),
            capture_output=True,
            text=True,
            env=env,
        )
        assert result.returncode == 0
        assert result.stdout.strip() == ""


class TestTmuxDriftCheckInvalidSessionId:
    """Hook rejects session IDs with path-unsafe characters."""

    def test_slash_in_session_id_silent(self):
        env = os.environ.copy()
        env["TMUX"] = "/tmp/tmux-stub,1,0"
        result = subprocess.run(
            [str(DRIFT_CHECK_HOOK)],
            input=json.dumps({"session_id": "foo/bar"}),
            capture_output=True,
            text=True,
            env=env,
        )
        assert result.returncode == 0
        assert result.stdout.strip() == ""

    def test_dot_in_session_id_silent(self):
        env = os.environ.copy()
        env["TMUX"] = "/tmp/tmux-stub,1,0"
        result = subprocess.run(
            [str(DRIFT_CHECK_HOOK)],
            input=json.dumps({"session_id": "foo.bar"}),
            capture_output=True,
            text=True,
            env=env,
        )
        assert result.returncode == 0
        assert result.stdout.strip() == ""

    def test_empty_session_id_silent(self):
        env = os.environ.copy()
        env["TMUX"] = "/tmp/tmux-stub,1,0"
        result = subprocess.run(
            [str(DRIFT_CHECK_HOOK)],
            input=json.dumps({"session_id": ""}),
            capture_output=True,
            text=True,
            env=env,
        )
        assert result.returncode == 0
        assert result.stdout.strip() == ""


class TestTmuxDriftCheckHeartbeatConfig:
    """Heartbeat interval env var edge cases."""

    def test_zero_interval_falls_back_to_default(self):
        # CLAUDE_TMUX_DRIFT_HEARTBEAT=0 is rejected; the hook falls back to 30.
        # With counter at 29, the next call brings it to 30 (>= 30), so the hook fires.
        sid = _drift_session_id("zero_interval")
        try:
            _write_drift_counter(sid, 29)
            result = _run_drift_check(
                sid,
                session_name="zero-fallback-session",
                extra_env={"CLAUDE_TMUX_DRIFT_HEARTBEAT": "0"},
            )
            assert result.returncode == 0
            output = json.loads(result.stdout)
            context = output["hookSpecificOutput"]["additionalContext"]
            assert "zero-fallback-session" in context
            assert _read_drift_counter(sid) == 0
        finally:
            _cleanup_drift(sid)

    def test_invalid_interval_falls_back_to_default(self):
        sid = _drift_session_id("invalid_interval")
        try:
            _write_drift_counter(sid, 5)
            result = _run_drift_check(
                sid, extra_env={"CLAUDE_TMUX_DRIFT_HEARTBEAT": "abc"}
            )
            assert result.returncode == 0
            assert result.stdout.strip() == ""  # 6 < 30 default
        finally:
            _cleanup_drift(sid)


def _make_compaction_input(session_id: str, transcript_path: str) -> str:
    return json.dumps(
        {
            "session_id": session_id,
            "transcript_path": transcript_path,
            "tool_input": {"description": "test agent"},
            "tool_response": {},
        }
    )


def _write_compact_boundary(jsonl_path: Path, pre: int, post: int) -> None:
    entry = {
        "type": "system",
        "subtype": "compact_boundary",
        "compactMetadata": {
            "trigger": "auto",
            "preTokens": pre,
            "postTokens": post,
            "durationMs": 5000,
        },
    }
    with open(jsonl_path, "a") as f:
        f.write(json.dumps(entry) + "\n")


def _write_agent_meta(meta_path: Path, description: str) -> None:
    meta = {
        "agentType": "general-purpose",
        "description": description,
        "toolUseId": "toolu_test",
    }
    meta_path.write_text(json.dumps(meta))


def _compaction_fixture(tmpdir: str) -> tuple[str, str, Path]:
    """Create a session transcript and subagent directory. Returns (sid, transcript_path, subagent_dir)."""
    sid = f"compaction-{uuid.uuid4().hex[:8]}"
    transcript = Path(tmpdir) / "session.jsonl"
    transcript.write_text("")
    subagent_dir = Path(tmpdir) / "session" / "subagents"
    subagent_dir.mkdir(parents=True)
    return sid, str(transcript), subagent_dir


class TestCompactionHookDetectsCompaction:
    """Hook detects compact_boundary events and emits a warning."""

    def test_compaction_detected(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            sid, transcript_path, subagent_dir = _compaction_fixture(tmpdir)

            agent_jsonl = subagent_dir / "agent-abc123.jsonl"
            _write_compact_boundary(agent_jsonl, 170000, 8000)
            _write_agent_meta(subagent_dir / "agent-abc123.meta.json", "T01 executor")

            stdin = _make_compaction_input(sid, transcript_path)
            result = run_hook(COMPACTION_HOOK, stdin, tmpdir)

            assert result.returncode == 0
            assert "Subagent compaction detected" in result.stdout
            assert "T01 executor" in result.stdout
            assert "170,000" in result.stdout
            assert "8,000" in result.stdout


class TestCompactionHookNoCompaction:
    """Hook exits silently when no compaction events are present."""

    def test_no_compaction_silent(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            sid, transcript_path, subagent_dir = _compaction_fixture(tmpdir)

            agent_jsonl = subagent_dir / "agent-abc123.jsonl"
            agent_jsonl.write_text('{"type":"assistant","content":"hello"}\n')

            stdin = _make_compaction_input(sid, transcript_path)
            result = run_hook(COMPACTION_HOOK, stdin, tmpdir)

            assert result.returncode == 0
            assert result.stdout.strip() == ""


class TestCompactionHookDedup:
    """Hook deduplicates — second call for same session is silent."""

    def test_dedup(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            sid, transcript_path, subagent_dir = _compaction_fixture(tmpdir)

            agent_jsonl = subagent_dir / "agent-abc123.jsonl"
            _write_compact_boundary(agent_jsonl, 170000, 8000)

            stdin = _make_compaction_input(sid, transcript_path)

            result1 = run_hook(COMPACTION_HOOK, stdin, tmpdir)
            assert "Subagent compaction detected" in result1.stdout

            result2 = run_hook(COMPACTION_HOOK, stdin, tmpdir)
            assert result2.stdout.strip() == ""


class TestCompactionHookMissingPostTokens:
    """Hook handles missing postTokens gracefully."""

    def test_missing_post_tokens(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            sid, transcript_path, subagent_dir = _compaction_fixture(tmpdir)

            agent_jsonl = subagent_dir / "agent-abc123.jsonl"
            entry = {
                "type": "system",
                "subtype": "compact_boundary",
                "compactMetadata": {"trigger": "auto", "preTokens": 175000},
            }
            agent_jsonl.write_text(json.dumps(entry) + "\n")

            stdin = _make_compaction_input(sid, transcript_path)
            result = run_hook(COMPACTION_HOOK, stdin, tmpdir)

            assert result.returncode == 0
            assert "175,000" in result.stdout
            assert "not recorded" in result.stdout
            assert "0%" not in result.stdout


class TestCompactionHookMultipleEvents:
    """Hook reports all compaction events for an agent that compacted twice."""

    def test_multiple_compactions(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            sid, transcript_path, subagent_dir = _compaction_fixture(tmpdir)

            agent_jsonl = subagent_dir / "agent-abc123.jsonl"
            _write_compact_boundary(agent_jsonl, 170000, 8000)
            _write_compact_boundary(agent_jsonl, 165000, 9000)

            stdin = _make_compaction_input(sid, transcript_path)
            result = run_hook(COMPACTION_HOOK, stdin, tmpdir)

            assert result.returncode == 0
            assert "170,000" in result.stdout
            assert "165,000" in result.stdout


class TestCompactionHookNoSubagentDir:
    """Hook exits silently when no subagent directory exists."""

    def test_no_subagent_dir(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            sid = f"compaction-{uuid.uuid4().hex[:8]}"
            transcript = Path(tmpdir) / "session.jsonl"
            transcript.write_text("")

            stdin = _make_compaction_input(sid, str(transcript))
            result = run_hook(COMPACTION_HOOK, stdin, tmpdir)

            assert result.returncode == 0
            assert result.stdout.strip() == ""


# ---------------------------------------------------------------------------
# bin/cass-update tests
# ---------------------------------------------------------------------------
#
# cass-update shells out to curl (GitHub API + asset downloads) and to cass
# itself (update path). Both are stubbed via PATH so tests never touch the
# real GitHub API or a real cass install. tar/sha256sum/mv/mkdir/chmod are
# left as the real system binaries — they're deterministic and safe to run
# for real against a throwaway HOME.

CASS_RELEASE_TAG = "v1.2.3"

_CURL_STUB_TEMPLATE = """#!/usr/bin/env bash
outfile=""
url=""
args=("$@")
i=0
while [[ $i -lt ${#args[@]} ]]; do
  a="${args[$i]}"
  if [[ "$a" == "-o" ]]; then
    i=$((i + 1))
    outfile="${args[$i]}"
  elif [[ "$a" != -* ]]; then
    url="$a"
  fi
  i=$((i + 1))
done

echo "$url" >> "__LOG_PATH__"

if [[ "$url" == *"api.github.com"* ]]; then
  echo '{"tag_name": "__TAG__"}'
  exit 0
fi
if [[ "$url" == *".sha256" ]]; then
  cp "__CHECKSUM_FILE__" "$outfile"
  exit 0
fi
if [[ "$url" == *"cass-linux-amd64.tar.gz" ]]; then
  cp "__TARBALL__" "$outfile"
  exit 0
fi
exit 1
"""

_CASS_STUB_TEMPLATE = """#!/usr/bin/env bash
echo "$@" >> "__LOG_PATH__"
exit __EXIT_CODE__
"""


def _make_cass_release_asset(tmpdir: Path) -> tuple[Path, Path]:
    """Build a real cass-linux-amd64.tar.gz + matching .sha256 fixture,
    using the real tar/sha256sum binaries so the fixture is bit-for-bit what
    cass-update's own tar/sha256sum invocations will see."""
    payload_dir = tmpdir / "payload"
    payload_dir.mkdir()
    cass_bin = payload_dir / "cass"
    cass_bin.write_text("#!/usr/bin/env bash\necho fake-cass\n")
    cass_bin.chmod(0o755)

    tarball = tmpdir / "cass-linux-amd64.tar.gz"
    subprocess.run(
        ["tar", "czf", str(tarball), "-C", str(payload_dir), "cass"], check=True
    )
    digest = hashlib.sha256(tarball.read_bytes()).hexdigest()
    checksum_file = tmpdir / "cass-linux-amd64.tar.gz.sha256"
    checksum_file.write_text(f"{digest}  cass-linux-amd64.tar.gz\n")
    return tarball, checksum_file


def _write_curl_stub(
    stub_dir: Path,
    tarball: Path,
    checksum_file: Path,
    log_path: Path,
    tag: str = CASS_RELEASE_TAG,
) -> Path:
    """A curl stand-in serving the release JSON + fixture asset files, logging
    every requested URL so tests can assert on what was fetched."""
    script = (
        _CURL_STUB_TEMPLATE.replace("__LOG_PATH__", str(log_path))
        .replace("__TAG__", tag)
        .replace("__CHECKSUM_FILE__", str(checksum_file))
        .replace("__TARBALL__", str(tarball))
    )
    stub = stub_dir / "curl"
    stub.write_text(script)
    stub.chmod(0o755)
    return stub


def _write_failing_curl_stub(stub_dir: Path) -> Path:
    """A curl stand-in that always fails, simulating GitHub being unreachable."""
    stub = stub_dir / "curl"
    stub.write_text("#!/usr/bin/env bash\nexit 7\n")
    stub.chmod(0o755)
    return stub


def _write_cass_stub(stub_dir: Path, log_path: Path, exit_code: int = 0) -> Path:
    """A cass stand-in that logs `cass upgrade --yes` invocations."""
    script = _CASS_STUB_TEMPLATE.replace("__LOG_PATH__", str(log_path)).replace(
        "__EXIT_CODE__", str(exit_code)
    )
    stub = stub_dir / "cass"
    stub.write_text(script)
    stub.chmod(0o755)
    return stub


def _cass_update_env(fake_home: Path, stub_dir: Path) -> dict:
    """Env for running cass-update in isolation: a throwaway HOME (so
    ~/.local/bin and ~/.local/share/claudefiles-cass are sandboxed) and a PATH
    that puts stubs first, followed only by the standard system directories —
    never the real ~/.local/bin, so a real cass on the dev machine can't leak
    into "command -v cass"."""
    env = os.environ.copy()
    env["HOME"] = str(fake_home)
    env["PATH"] = f"{stub_dir}:/usr/bin:/bin"
    return env


def _run_cass_update(args: list[str], env: dict) -> subprocess.CompletedProcess:
    return subprocess.run(
        [str(CASS_UPDATE), *args], capture_output=True, text=True, env=env
    )


class TestCassUpdateBootstrap:
    """Bootstrap path: cass is not on PATH, so cass-update downloads it."""

    def test_downloads_and_verifies_checksum(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            fake_home = tmp / "home"
            fake_home.mkdir()
            stub_dir = tmp / "stubs"
            stub_dir.mkdir()

            tarball, checksum_file = _make_cass_release_asset(tmp)
            _write_curl_stub(stub_dir, tarball, checksum_file, tmp / "curl.log")

            env = _cass_update_env(fake_home, stub_dir)
            result = _run_cass_update([], env)

            assert result.returncode == 0, result.stderr
            installed = fake_home / ".local" / "bin" / "cass"
            assert installed.is_file()
            assert os.access(installed, os.X_OK)
            assert installed.read_text() == (tmp / "payload" / "cass").read_text()

    def test_checksum_mismatch_aborts_leaving_no_binary(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            fake_home = tmp / "home"
            fake_home.mkdir()
            stub_dir = tmp / "stubs"
            stub_dir.mkdir()

            tarball, checksum_file = _make_cass_release_asset(tmp)
            # Corrupt the checksum so it no longer matches the tarball.
            checksum_file.write_text("0" * 64 + "  cass-linux-amd64.tar.gz\n")
            _write_curl_stub(stub_dir, tarball, checksum_file, tmp / "curl.log")

            env = _cass_update_env(fake_home, stub_dir)
            result = _run_cass_update([], env)

            assert result.returncode == 1
            assert "checksum mismatch" in result.stderr.lower()
            installed = fake_home / ".local" / "bin" / "cass"
            assert not installed.exists()

    def test_github_unreachable_warns_and_exits_zero(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            fake_home = tmp / "home"
            fake_home.mkdir()
            stub_dir = tmp / "stubs"
            stub_dir.mkdir()
            _write_failing_curl_stub(stub_dir)

            env = _cass_update_env(fake_home, stub_dir)
            result = _run_cass_update([], env)

            assert result.returncode == 0
            assert result.stderr.strip() != ""
            installed = fake_home / ".local" / "bin" / "cass"
            assert not installed.exists()


class TestCassUpdateUpdate:
    """Update path: cass is already on PATH, so cass-update delegates to it."""

    def test_delegates_to_cass_upgrade(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            fake_home = tmp / "home"
            fake_home.mkdir()
            stub_dir = tmp / "stubs"
            stub_dir.mkdir()
            log = tmp / "cass-invocations.log"
            _write_cass_stub(stub_dir, log)

            env = _cass_update_env(fake_home, stub_dir)
            result = _run_cass_update([], env)

            assert result.returncode == 0, result.stderr
            assert log.exists()
            assert log.read_text().strip() == "upgrade --yes"

    def test_upgrade_failure_warns_and_exits_zero(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            fake_home = tmp / "home"
            fake_home.mkdir()
            stub_dir = tmp / "stubs"
            stub_dir.mkdir()
            log = tmp / "cass-invocations.log"
            _write_cass_stub(stub_dir, log, exit_code=1)

            env = _cass_update_env(fake_home, stub_dir)
            result = _run_cass_update([], env)

            assert result.returncode == 0
            assert result.stderr.strip() != ""


class TestCassUpdateIfStale:
    """--if-stale gate: skip when the timestamp marker is fresh, run when not."""

    def test_exits_early_when_timestamp_fresh(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            fake_home = tmp / "home"
            fake_home.mkdir()
            stub_dir = tmp / "stubs"
            stub_dir.mkdir()
            log = tmp / "cass-invocations.log"
            _write_cass_stub(stub_dir, log)

            state_dir = fake_home / ".local" / "share" / "claudefiles-cass"
            state_dir.mkdir(parents=True)
            marker = state_dir / "last-update-check"
            marker.touch()  # fresh mtime — "just checked"

            env = _cass_update_env(fake_home, stub_dir)
            result = _run_cass_update(["--if-stale"], env)

            assert result.returncode == 0
            assert not log.exists()  # cass was never invoked

    def test_runs_when_timestamp_is_old(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            fake_home = tmp / "home"
            fake_home.mkdir()
            stub_dir = tmp / "stubs"
            stub_dir.mkdir()
            log = tmp / "cass-invocations.log"
            _write_cass_stub(stub_dir, log)

            state_dir = fake_home / ".local" / "share" / "claudefiles-cass"
            state_dir.mkdir(parents=True)
            marker = state_dir / "last-update-check"
            marker.touch()
            old = time.time() - (25 * 60 * 60)  # 25h ago
            os.utime(marker, (old, old))

            env = _cass_update_env(fake_home, stub_dir)
            result = _run_cass_update(["--if-stale"], env)

            assert result.returncode == 0
            assert log.exists()
            assert log.read_text().strip() == "upgrade --yes"


class TestCassUpdateTimestamp:
    """The timestamp marker is refreshed after any completed check."""

    def test_writes_timestamp_after_bootstrap(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            fake_home = tmp / "home"
            fake_home.mkdir()
            stub_dir = tmp / "stubs"
            stub_dir.mkdir()

            tarball, checksum_file = _make_cass_release_asset(tmp)
            _write_curl_stub(stub_dir, tarball, checksum_file, tmp / "curl.log")

            marker = (
                fake_home
                / ".local"
                / "share"
                / "claudefiles-cass"
                / "last-update-check"
            )
            assert not marker.exists()

            env = _cass_update_env(fake_home, stub_dir)
            result = _run_cass_update([], env)

            assert result.returncode == 0, result.stderr
            assert marker.exists()

    def test_writes_timestamp_after_update(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            fake_home = tmp / "home"
            fake_home.mkdir()
            stub_dir = tmp / "stubs"
            stub_dir.mkdir()
            log = tmp / "cass-invocations.log"
            _write_cass_stub(stub_dir, log)

            marker = (
                fake_home
                / ".local"
                / "share"
                / "claudefiles-cass"
                / "last-update-check"
            )
            assert not marker.exists()

            env = _cass_update_env(fake_home, stub_dir)
            result = _run_cass_update([], env)

            assert result.returncode == 0, result.stderr
            assert marker.exists()


# ---------------------------------------------------------------------------
# scripts/hooks/cass-session-start.sh and cass-clear-handoff.sh tests
# ---------------------------------------------------------------------------
#
# The SessionStart hook shells out to `cass`, `cass-update`, and `jq`, all
# stubbed via a PATH prefix so tests never touch the real GitHub API or a
# real cass install. jq itself is left as the real system binary (it's
# already a hard dependency of other hooks in this file) — only `cass` and
# `cass-update` are faked.


def _write_cass_multi_stub(
    stub_dir: Path,
    *,
    search_json: str = '{"hits": []}',
    search_sleep: float = 0,
    index_log: Path | None = None,
) -> Path:
    """A `cass` stand-in supporting the `index` and `search` subcommands used
    by the SessionStart hook. `index` logs an invocation marker; `search`
    optionally sleeps (to exercise the hook's 3s timeout) before printing
    canned --robot JSON."""
    index_log = index_log or (stub_dir / "index.log")
    script = f"""#!/usr/bin/env bash
if [[ "$1" == "index" ]]; then
  echo "indexed" >> "{index_log}"
  exit 0
fi
if [[ "$1" == "search" ]]; then
  sleep {search_sleep}
  cat << 'JSON'
{search_json}
JSON
  exit 0
fi
exit 1
"""
    stub = stub_dir / "cass"
    stub.write_text(script)
    stub.chmod(0o755)
    return stub


def _write_cass_update_logging_stub(stub_dir: Path, log_path: Path) -> Path:
    """A `cass-update` stand-in that logs its arguments instead of hitting
    the real GitHub API — used to verify the SessionStart hook triggers it,
    without exercising cass-update's own bootstrap/update logic (covered by
    TestCassUpdate* above)."""
    script = f"""#!/usr/bin/env bash
echo "$@" >> "{log_path}"
exit 0
"""
    stub = stub_dir / "cass-update"
    stub.write_text(script)
    stub.chmod(0o755)
    return stub


def _wait_for_file(path: Path, timeout: float = 2.0) -> bool:
    """Poll for a file written by a detached background process instead of
    a blind sleep — the hook's background spawns are async by design."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if path.exists():
            return True
        time.sleep(0.05)
    return path.exists()


def _make_no_jq_path(tmp: Path, extra_names: list[str]) -> Path:
    """Build a PATH directory with symlinks to real coreutils but no `jq`, so
    a test can deterministically exercise a hook's jq-absent fallback branch
    rather than relying on the dev machine happening to lack jq (it always
    has it — jq is a hard dependency of other hooks in this file)."""
    stub = tmp / "no-jq-path"
    stub.mkdir()
    for name in ["env", "bash", *extra_names]:
        resolved = shutil.which(name)
        assert resolved, f"required binary not found on PATH: {name}"
        (stub / name).symlink_to(resolved)
    return stub


class TestSessionStartHookNoCassInstalled:
    """Hook exits silently when cass is not on PATH."""

    def test_exits_silently_when_cass_not_installed(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            # A PATH with just enough on it to exec the script's own
            # `#!/usr/bin/env bash` shebang and its `command -v` builtin
            # check — deliberately excluding any directory that might have
            # a real `cass` on it, so this test is independent of whether
            # the host machine happens to have cass installed.
            bare_path = tmp / "bare-path"
            bare_path.mkdir()
            (bare_path / "bash").symlink_to(shutil.which("bash"))
            fake_home = tmp / "home"
            fake_home.mkdir()

            env = os.environ.copy()
            env["PATH"] = str(bare_path)
            env["HOME"] = str(fake_home)

            result = run_hook(CASS_SESSION_START_HOOK, "", env=env, timeout=10)

            assert result.returncode == 0
            assert result.stdout.strip() == ""


class TestSessionStartHookBackgroundSpawns:
    """Hook spawns cass index and cass-update --if-stale as detached
    background processes (FR#3, FR#11)."""

    def test_spawns_background_cass_index(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            stub_dir = tmp / "stubs"
            stub_dir.mkdir()
            fake_home = tmp / "home"
            fake_home.mkdir()
            index_log = tmp / "index.log"

            _write_cass_multi_stub(stub_dir, index_log=index_log)

            env = os.environ.copy()
            env["PATH"] = f"{stub_dir}:{env['PATH']}"
            env["HOME"] = str(fake_home)

            result = run_hook(CASS_SESSION_START_HOOK, "", env=env, timeout=10)

            assert result.returncode == 0
            assert _wait_for_file(index_log)
            assert index_log.read_text().strip() == "indexed"

    def test_triggers_cass_update_if_stale(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            stub_dir = tmp / "stubs"
            stub_dir.mkdir()
            fake_home = tmp / "home"
            fake_home.mkdir()
            update_log = tmp / "update.log"

            _write_cass_multi_stub(stub_dir)
            _write_cass_update_logging_stub(stub_dir, update_log)

            env = os.environ.copy()
            env["PATH"] = f"{stub_dir}:{env['PATH']}"
            env["HOME"] = str(fake_home)

            result = run_hook(CASS_SESSION_START_HOOK, "", env=env, timeout=10)

            assert result.returncode == 0
            assert _wait_for_file(update_log)
            assert update_log.read_text().strip() == "--if-stale"


class TestSessionStartHookContextInjection:
    """Synchronous context injection: emits a summary or degrades to silence
    within the 3s budget (FR#4, edge case: timeout/empty results)."""

    def test_context_injection_produces_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            stub_dir = tmp / "stubs"
            stub_dir.mkdir()
            fake_home = tmp / "home"
            fake_home.mkdir()

            search_json = json.dumps(
                {
                    "hits": [
                        {
                            "title": "pytest fixtures work",
                            "date": "2026-06-30",
                            "snippet": "discussed fixture scoping",
                        }
                    ]
                }
            )
            _write_cass_multi_stub(stub_dir, search_json=search_json)

            env = os.environ.copy()
            env["PATH"] = f"{stub_dir}:{env['PATH']}"
            env["HOME"] = str(fake_home)

            result = run_hook(CASS_SESSION_START_HOOK, "", env=env, timeout=10)

            assert result.returncode == 0
            assert "pytest fixtures work" in result.stdout
            assert "2026-06-30" in result.stdout
            assert "discussed fixture scoping" in result.stdout

    def test_context_injection_exits_zero_on_timeout(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            stub_dir = tmp / "stubs"
            stub_dir.mkdir()
            fake_home = tmp / "home"
            fake_home.mkdir()

            _write_cass_multi_stub(stub_dir, search_sleep=5)

            env = os.environ.copy()
            env["PATH"] = f"{stub_dir}:{env['PATH']}"
            env["HOME"] = str(fake_home)

            start = time.monotonic()
            result = run_hook(CASS_SESSION_START_HOOK, "", env=env, timeout=10)
            elapsed = time.monotonic() - start

            assert result.returncode == 0
            assert result.stdout.strip() == ""
            # The hook's own `timeout 3` must cap this, not the stub's 5s sleep.
            assert elapsed < 5


class TestSessionStartHookNoJqFallback:
    """Hook degrades to silent context injection when jq is absent
    (cass-session-start.sh:32-34), but the two background spawns — which
    don't depend on jq — still fire. Every other context-injection test in
    this file runs with real jq on PATH, so this fallback would otherwise
    ship untested."""

    def test_no_jq_skips_context_but_still_spawns_background_work(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            stub_dir = tmp / "stubs"
            stub_dir.mkdir()
            fake_home = tmp / "home"
            fake_home.mkdir()
            index_log = tmp / "index.log"
            update_log = tmp / "update.log"

            _write_cass_multi_stub(stub_dir, index_log=index_log)
            _write_cass_update_logging_stub(stub_dir, update_log)

            no_jq_path = _make_no_jq_path(tmp, ["cat", "nohup"])

            env = os.environ.copy()
            env["HOME"] = str(fake_home)
            env["PATH"] = f"{no_jq_path}:{stub_dir}"

            result = run_hook(CASS_SESSION_START_HOOK, "", env=env, timeout=10)

            assert result.returncode == 0
            assert result.stdout.strip() == ""
            assert _wait_for_file(index_log)
            assert index_log.read_text().strip() == "indexed"
            assert _wait_for_file(update_log)
            assert update_log.read_text().strip() == "--if-stale"


class TestClearHandoffHookWritesFile:
    """SessionEnd hook writes a per-project handoff JSON file (FR#5, AC#6)."""

    def test_writes_handoff_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            fake_home = tmp / "home"
            fake_home.mkdir()

            stdin_payload = json.dumps(
                {"session_id": "sess-abc123", "cwd": "/home/jessica/myproject"}
            )

            env = os.environ.copy()
            env["HOME"] = str(fake_home)

            result = run_hook(CASS_CLEAR_HANDOFF_HOOK, stdin_payload, env=env)

            assert result.returncode == 0

            handoff_dir = (
                fake_home / ".local" / "share" / "claudefiles-cass" / "clear-handoff"
            )
            files = list(handoff_dir.glob("*.json"))
            assert len(files) == 1
            assert files[0].name == "-home-jessica-myproject.json"

            data = json.loads(files[0].read_text())
            assert data["session_id"] == "sess-abc123"
            assert data["project_path"] == "/home/jessica/myproject"
            assert "timestamp" in data


class TestClearHandoffHookNoJqFallback:
    """SessionEnd hook falls back to hand-rolled JSON escaping when jq is
    absent (cass-clear-handoff.sh:44-58) — every other test in this file
    runs with real jq on PATH, so this fallback would otherwise ship
    untested."""

    def test_escapes_quotes_and_backslashes_without_jq(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            fake_home = tmp / "home"
            fake_home.mkdir()
            no_jq_path = _make_no_jq_path(tmp, ["cat", "mkdir", "date", "sed", "grep"])

            # A cwd containing a quote and a backslash — the exact characters
            # the hand-rolled `sed 's/\\/\\\\/g; s/"/\\"/g'` escape must get
            # right. Delivered via the process's actual working directory
            # rather than the stdin JSON's "cwd" field, so this test
            # isolates the write-side escaping (lines 44-58) from the
            # separate stdin-JSON field-extraction fallback (lines 26-27),
            # which is a different code path than the one this finding is
            # about.
            tricky_dir = tmp / 'weird"quote\\dir'
            tricky_dir.mkdir()

            stdin_payload = json.dumps({"session_id": "sess-xyz"})
            env = os.environ.copy()
            env["HOME"] = str(fake_home)
            env["PATH"] = str(no_jq_path)

            result = subprocess.run(
                [str(CASS_CLEAR_HANDOFF_HOOK)],
                input=stdin_payload,
                capture_output=True,
                text=True,
                env=env,
                cwd=str(tricky_dir),
            )

            assert result.returncode == 0

            handoff_dir = (
                fake_home / ".local" / "share" / "claudefiles-cass" / "clear-handoff"
            )
            files = list(handoff_dir.glob("*.json"))
            assert len(files) == 1

            data = json.loads(files[0].read_text())
            assert data["project_path"] == str(tricky_dir)
            assert data["session_id"] == "sess-xyz"
            assert "timestamp" in data
