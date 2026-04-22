"""Integration tests for pytest-loop-detector.sh and pytest-loop-reset.sh hooks.

Each test creates a temp directory, writes a session ID file, crafts JSON input
matching the PreToolUse/PostToolUse schema, invokes the hook via subprocess.run,
and asserts on exit code and stdout JSON.
"""

import json
import os
import subprocess
import tempfile
from pathlib import Path

# Resolve hook paths relative to the repo root
REPO_ROOT = Path(__file__).parent.parent
DETECTOR_HOOK = REPO_ROOT / "scripts" / "hooks" / "pytest-loop-detector.sh"
RESET_HOOK = REPO_ROOT / "scripts" / "hooks" / "pytest-loop-reset.sh"
STATUS_HOOK = REPO_ROOT / "scripts" / "hooks" / "pytest-loop-status.sh"
BIN_RESET = REPO_ROOT / "bin" / "pytest-loop-reset"


def make_pretooluse_input(command: str, cwd: str = "/tmp") -> str:
    """Build a PreToolUse JSON payload for a Bash command."""
    return json.dumps(
        {"tool_name": "Bash", "tool_input": {"command": command}, "cwd": cwd}
    )


def make_posttooluse_input(tool_name: str = "Edit") -> str:
    """Build a PostToolUse JSON payload."""
    return json.dumps({"tool_name": tool_name, "tool_input": {}, "tool_response": {}})


def make_posttooluse_bash_input(command: str, exit_code: int = 0) -> str:
    """Build a PostToolUse JSON payload for a Bash command with exit code."""
    return json.dumps(
        {
            "tool_name": "Bash",
            "tool_input": {"command": command},
            "tool_response": {"exit_code": exit_code},
        }
    )


def run_hook(
    script: Path,
    stdin: str,
    tmpdir: str,
    extra_env: dict | None = None,
) -> subprocess.CompletedProcess:
    """Run a hook script with given stdin and CLAUDE_CODE_TMPDIR set to tmpdir."""
    env = os.environ.copy()
    env["CLAUDE_CODE_TMPDIR"] = tmpdir
    env.pop("CLAUDE_PYTEST_LOOP_BYPASS", None)  # remove bypass by default
    if extra_env:
        env.update(extra_env)
    return subprocess.run(
        [str(script)],
        input=stdin,
        capture_output=True,
        text=True,
        env=env,
    )


def write_session_id(tmpdir: str, uuid: str = "test-session-uuid-1234") -> str:
    """Write a session ID file and return the UUID."""
    session_file = Path(tmpdir) / "claude-pytest-loop-session.id"
    session_file.write_text(uuid + "\n")
    return uuid


def write_counter(tmpdir: str, uuid: str, count: int) -> None:
    """Write a counter file with the given count."""
    counter_file = Path(tmpdir) / f"claude-pytest-loop-{uuid}.count"
    counter_file.write_text(str(count) + "\n")


def write_status(tmpdir: str, uuid: str, exit_code: int) -> None:
    """Write a status file (previous pytest exit code)."""
    status_file = Path(tmpdir) / f"claude-pytest-loop-{uuid}.status"
    status_file.write_text(str(exit_code) + "\n")


def read_counter(tmpdir: str, uuid: str) -> int | None:
    """Read the current counter value; returns None if file doesn't exist."""
    counter_file = Path(tmpdir) / f"claude-pytest-loop-{uuid}.count"
    if not counter_file.exists():
        return None
    content = counter_file.read_text().strip()
    return int(content) if content else 0


class TestDetectorIncrementsAfterFailure:
    """Counter increments when previous pytest run failed."""

    def test_increments_on_first_failure(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            uuid = write_session_id(tmpdir)
            write_status(tmpdir, uuid, 1)  # previous run failed
            # No counter file yet

            inp = make_pretooluse_input("timeout 300 pytest tests/")
            result = run_hook(DETECTOR_HOOK, inp, tmpdir)

            assert result.returncode == 0
            count = read_counter(tmpdir, uuid)
            assert count == 1

    def test_increments_on_subsequent_failure(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            uuid = write_session_id(tmpdir)
            write_status(tmpdir, uuid, 1)  # previous run failed
            write_counter(tmpdir, uuid, 1)  # already incremented once

            inp = make_pretooluse_input("timeout 300 pytest tests/")
            result = run_hook(DETECTOR_HOOK, inp, tmpdir)

            assert result.returncode == 0
            count = read_counter(tmpdir, uuid)
            assert count == 2


class TestDetectorDeniesAtThreshold:
    """Counter >= 3 causes a deny response."""

    def test_denies_at_count_3(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            uuid = write_session_id(tmpdir)
            write_status(tmpdir, uuid, 1)  # previous run failed
            write_counter(tmpdir, uuid, 2)  # count at 2 → will become 3 → deny

            inp = make_pretooluse_input("timeout 300 pytest tests/")
            result = run_hook(DETECTOR_HOOK, inp, tmpdir)

            assert result.returncode == 0
            output = json.loads(result.stdout)
            assert output["hookSpecificOutput"]["permissionDecision"] == "deny"
            reason = output["hookSpecificOutput"]["permissionDecisionReason"]
            assert "/mine.debug" in reason
            assert "CLAUDE_PYTEST_LOOP_BYPASS" in reason
            assert "pytest-loop-reset" in reason

    def test_denies_at_count_above_3(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            uuid = write_session_id(tmpdir)
            write_status(tmpdir, uuid, 1)  # previous run failed
            write_counter(tmpdir, uuid, 5)

            inp = make_pretooluse_input("timeout 300 pytest tests/")
            result = run_hook(DETECTOR_HOOK, inp, tmpdir)

            assert result.returncode == 0
            output = json.loads(result.stdout)
            assert output["hookSpecificOutput"]["permissionDecision"] == "deny"

    def test_deny_message_includes_override_mechanisms(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            uuid = write_session_id(tmpdir)
            write_status(tmpdir, uuid, 1)
            write_counter(tmpdir, uuid, 2)  # will become 3

            inp = make_pretooluse_input("timeout 300 pytest tests/")
            result = run_hook(DETECTOR_HOOK, inp, tmpdir)

            output = json.loads(result.stdout)
            reason = output["hookSpecificOutput"]["permissionDecisionReason"]
            # Both override mechanisms must be mentioned
            assert "CLAUDE_PYTEST_LOOP_BYPASS=1" in reason
            assert "pytest-loop-reset" in reason


class TestDetectorAllowsGreenRuns:
    """Green (exit code 0) pytest runs do not increment the counter."""

    def test_green_run_does_not_increment(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            uuid = write_session_id(tmpdir)
            write_status(tmpdir, uuid, 0)  # previous run succeeded
            write_counter(tmpdir, uuid, 0)

            inp = make_pretooluse_input("timeout 300 pytest tests/")
            result = run_hook(DETECTOR_HOOK, inp, tmpdir)

            assert result.returncode == 0
            # stdout should be empty (no deny)
            assert result.stdout.strip() == ""
            count = read_counter(tmpdir, uuid)
            assert count == 0

    def test_green_run_resets_counter(self):
        """A green run should reset the counter (not just stop incrementing)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            uuid = write_session_id(tmpdir)
            write_status(tmpdir, uuid, 0)  # previous run succeeded
            write_counter(tmpdir, uuid, 2)  # had accumulated failures

            inp = make_pretooluse_input("timeout 300 pytest tests/")
            result = run_hook(DETECTOR_HOOK, inp, tmpdir)

            assert result.returncode == 0
            assert result.stdout.strip() == ""
            count = read_counter(tmpdir, uuid)
            assert count == 0


class TestDetectorEnvVarBypass:
    """CLAUDE_PYTEST_LOOP_BYPASS=1 allows the run and resets the counter."""

    def test_bypass_allows_run(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            uuid = write_session_id(tmpdir)
            write_status(tmpdir, uuid, 1)
            write_counter(tmpdir, uuid, 5)  # would otherwise be denied

            inp = make_pretooluse_input("timeout 300 pytest tests/")
            result = run_hook(
                DETECTOR_HOOK, inp, tmpdir, extra_env={"CLAUDE_PYTEST_LOOP_BYPASS": "1"}
            )

            assert result.returncode == 0
            assert result.stdout.strip() == ""  # no deny

    def test_bypass_resets_counter(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            uuid = write_session_id(tmpdir)
            write_status(tmpdir, uuid, 1)
            write_counter(tmpdir, uuid, 5)

            inp = make_pretooluse_input("timeout 300 pytest tests/")
            run_hook(
                DETECTOR_HOOK, inp, tmpdir, extra_env={"CLAUDE_PYTEST_LOOP_BYPASS": "1"}
            )

            count = read_counter(tmpdir, uuid)
            assert count == 0


class TestDetectorMissingSessionId:
    """Missing session ID file is handled gracefully (no-op)."""

    def test_no_crash_when_session_id_missing(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            # No session ID file written
            inp = make_pretooluse_input("timeout 300 pytest tests/")
            result = run_hook(DETECTOR_HOOK, inp, tmpdir)

            assert result.returncode == 0
            assert result.stdout.strip() == ""


class TestDetectorMissingCounterFile:
    """Missing counter file (first run) treats count as 0."""

    def test_first_failure_starts_count_at_1(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            uuid = write_session_id(tmpdir)
            write_status(tmpdir, uuid, 1)  # previous run failed
            # No counter file

            inp = make_pretooluse_input("timeout 300 pytest tests/")
            result = run_hook(DETECTOR_HOOK, inp, tmpdir)

            assert result.returncode == 0
            count = read_counter(tmpdir, uuid)
            assert count == 1

    def test_missing_counter_on_green_run(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            uuid = write_session_id(tmpdir)
            write_status(tmpdir, uuid, 0)  # green run, no counter
            # No counter file

            inp = make_pretooluse_input("timeout 300 pytest tests/")
            result = run_hook(DETECTOR_HOOK, inp, tmpdir)

            assert result.returncode == 0
            assert result.stdout.strip() == ""


class TestDetectorNonPytestCommands:
    """Non-pytest commands are ignored by the detector."""

    def test_ignores_non_pytest_command(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            uuid = write_session_id(tmpdir)
            write_status(tmpdir, uuid, 1)
            write_counter(tmpdir, uuid, 5)

            inp = make_pretooluse_input("ls -la /tmp")
            result = run_hook(DETECTOR_HOOK, inp, tmpdir)

            assert result.returncode == 0
            assert result.stdout.strip() == ""

    def test_ignores_empty_command(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            write_session_id(tmpdir)
            inp = json.dumps({"tool_name": "Bash", "tool_input": {}, "cwd": "/tmp"})
            result = run_hook(DETECTOR_HOOK, inp, tmpdir)

            assert result.returncode == 0
            assert result.stdout.strip() == ""


class TestDetectorAtomicWrite:
    """Counter is written atomically (no partial file)."""

    def test_counter_file_contains_valid_integer_after_write(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            uuid = write_session_id(tmpdir)
            write_status(tmpdir, uuid, 1)

            inp = make_pretooluse_input("timeout 300 pytest tests/")
            run_hook(DETECTOR_HOOK, inp, tmpdir)

            counter_file = Path(tmpdir) / f"claude-pytest-loop-{uuid}.count"
            assert counter_file.exists()
            content = counter_file.read_text().strip()
            # Must be a valid integer
            assert content.isdigit()

    def test_no_tmp_file_left_after_write(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            uuid = write_session_id(tmpdir)
            write_status(tmpdir, uuid, 1)

            inp = make_pretooluse_input("timeout 300 pytest tests/")
            run_hook(DETECTOR_HOOK, inp, tmpdir)

            # No .tmp file should remain
            tmp_files = list(Path(tmpdir).glob("*.tmp"))
            assert tmp_files == []


class TestResetHookClearsCounter:
    """pytest-loop-reset.sh PostToolUse hook clears the counter."""

    def test_reset_clears_counter(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            uuid = write_session_id(tmpdir)
            write_counter(tmpdir, uuid, 2)

            inp = make_posttooluse_input("Edit")
            result = run_hook(RESET_HOOK, inp, tmpdir)

            assert result.returncode == 0
            count = read_counter(tmpdir, uuid)
            assert count == 0

    def test_reset_clears_counter_on_write_tool(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            uuid = write_session_id(tmpdir)
            write_counter(tmpdir, uuid, 3)

            inp = make_posttooluse_input("Write")
            result = run_hook(RESET_HOOK, inp, tmpdir)

            assert result.returncode == 0
            count = read_counter(tmpdir, uuid)
            assert count == 0


class TestResetHookNoOpWhenMissing:
    """pytest-loop-reset.sh is a no-op when session/counter files are absent."""

    def test_no_op_when_session_id_missing(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            inp = make_posttooluse_input("Edit")
            result = run_hook(RESET_HOOK, inp, tmpdir)

            assert result.returncode == 0

    def test_no_op_when_counter_file_missing(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            write_session_id(tmpdir)
            # No counter file

            inp = make_posttooluse_input("Edit")
            result = run_hook(RESET_HOOK, inp, tmpdir)

            assert result.returncode == 0


class TestBinScriptClearsCounter:
    """bin/pytest-loop-reset user script clears the counter and prints confirmation."""

    def test_bin_clears_counter(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            uuid = write_session_id(tmpdir)
            write_counter(tmpdir, uuid, 3)

            result = subprocess.run(
                [str(BIN_RESET)],
                capture_output=True,
                text=True,
                env={**os.environ, "CLAUDE_CODE_TMPDIR": tmpdir},
            )

            assert result.returncode == 0
            count = read_counter(tmpdir, uuid)
            assert count == 0

    def test_bin_prints_confirmation(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            uuid = write_session_id(tmpdir)
            write_counter(tmpdir, uuid, 2)

            result = subprocess.run(
                [str(BIN_RESET)],
                capture_output=True,
                text=True,
                env={**os.environ, "CLAUDE_CODE_TMPDIR": tmpdir},
            )

            assert result.returncode == 0
            assert result.stdout.strip() != ""  # some confirmation message

    def test_bin_exits_cleanly_when_no_counter(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            write_session_id(tmpdir)
            # No counter file

            result = subprocess.run(
                [str(BIN_RESET)],
                capture_output=True,
                text=True,
                env={**os.environ, "CLAUDE_CODE_TMPDIR": tmpdir},
            )

            assert result.returncode == 0

    def test_bin_exits_cleanly_when_no_session_id(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            result = subprocess.run(
                [str(BIN_RESET)],
                capture_output=True,
                text=True,
                env={**os.environ, "CLAUDE_CODE_TMPDIR": tmpdir},
            )

            assert result.returncode == 0


class TestPostToolUseBashStatusTracking:
    """The PostToolUse hook for Bash records the exit code to the status file."""

    # Note: this is an integration test that tests the full flow:
    # detector reads the status file that the PostToolUse Bash hook writes.
    # We test the detector's response to the status file content,
    # which is the observable behavior from the test perspective.

    def test_detector_uses_status_file_for_failure_detection(self):
        """Verify detector reads status file — zero exit = no increment."""
        with tempfile.TemporaryDirectory() as tmpdir:
            uuid = write_session_id(tmpdir)
            write_status(tmpdir, uuid, 0)  # 0 = success
            write_counter(tmpdir, uuid, 0)

            inp = make_pretooluse_input("timeout 300 pytest tests/")
            result = run_hook(DETECTOR_HOOK, inp, tmpdir)

            assert result.returncode == 0
            count = read_counter(tmpdir, uuid)
            assert count == 0  # no increment for green run

    def test_detector_uses_status_file_for_increment(self):
        """Verify detector reads status file — non-zero exit = increment."""
        with tempfile.TemporaryDirectory() as tmpdir:
            uuid = write_session_id(tmpdir)
            write_status(tmpdir, uuid, 1)  # 1 = failure
            write_counter(tmpdir, uuid, 0)

            inp = make_pretooluse_input("timeout 300 pytest tests/")
            result = run_hook(DETECTOR_HOOK, inp, tmpdir)

            assert result.returncode == 0
            count = read_counter(tmpdir, uuid)
            assert count == 1  # incremented after failure


class TestDetectorPytestVariants:
    """Detector recognizes various pytest invocation patterns."""

    def test_detects_uv_run_pytest(self):
        # Note: the regex (copied from pytest-guard.sh) matches `uv run pytest`
        # when timeout is absent or when timeout appears immediately before pytest
        # (not before uv run). This is consistent with pytest-guard.sh behavior.
        with tempfile.TemporaryDirectory() as tmpdir:
            uuid = write_session_id(tmpdir)
            write_status(tmpdir, uuid, 1)

            inp = make_pretooluse_input("uv run pytest tests/")
            result = run_hook(DETECTOR_HOOK, inp, tmpdir)

            assert result.returncode == 0
            count = read_counter(tmpdir, uuid)
            assert count == 1

    def test_detects_python_m_pytest(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            uuid = write_session_id(tmpdir)
            write_status(tmpdir, uuid, 1)

            inp = make_pretooluse_input("timeout 300 python -m pytest tests/")
            result = run_hook(DETECTOR_HOOK, inp, tmpdir)

            assert result.returncode == 0
            count = read_counter(tmpdir, uuid)
            assert count == 1


class TestStatusHook:
    """Direct tests for pytest-loop-status.sh PostToolUse hook."""

    def _read_status(self, tmpdir: str, uuid: str) -> str | None:
        status_file = Path(tmpdir) / f"claude-pytest-loop-{uuid}.status"
        if not status_file.exists():
            return None
        return status_file.read_text().strip()

    def test_writes_nonzero_exit_code(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            uuid = write_session_id(tmpdir)
            inp = make_posttooluse_bash_input("timeout 300 pytest tests/", exit_code=1)
            result = run_hook(STATUS_HOOK, inp, tmpdir)
            assert result.returncode == 0
            assert self._read_status(tmpdir, uuid) == "1"

    def test_writes_zero_exit_code(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            uuid = write_session_id(tmpdir)
            inp = make_posttooluse_bash_input("timeout 300 pytest tests/", exit_code=0)
            result = run_hook(STATUS_HOOK, inp, tmpdir)
            assert result.returncode == 0
            assert self._read_status(tmpdir, uuid) == "0"

    def test_missing_exit_code_defaults_to_zero(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            uuid = write_session_id(tmpdir)
            inp = json.dumps(
                {
                    "tool_name": "Bash",
                    "tool_input": {"command": "timeout 300 pytest tests/"},
                    "tool_response": {},
                }
            )
            result = run_hook(STATUS_HOOK, inp, tmpdir)
            assert result.returncode == 0
            assert self._read_status(tmpdir, uuid) == "0"

    def test_ignores_non_pytest_commands(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            uuid = write_session_id(tmpdir)
            inp = make_posttooluse_bash_input("ls /tmp", exit_code=1)
            result = run_hook(STATUS_HOOK, inp, tmpdir)
            assert result.returncode == 0
            assert self._read_status(tmpdir, uuid) is None

    def test_no_op_when_session_missing(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            inp = make_posttooluse_bash_input("timeout 300 pytest tests/", exit_code=1)
            result = run_hook(STATUS_HOOK, inp, tmpdir)
            assert result.returncode == 0

    def test_writes_high_exit_code(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            uuid = write_session_id(tmpdir)
            inp = make_posttooluse_bash_input(
                "timeout 300 pytest tests/", exit_code=137
            )
            result = run_hook(STATUS_HOOK, inp, tmpdir)
            assert result.returncode == 0
            assert self._read_status(tmpdir, uuid) == "137"
