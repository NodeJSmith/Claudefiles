"""Integration tests for hook scripts (pytest-loop-detector, context-tier, etc).

Each test creates a temp directory, writes a session ID file, crafts JSON input
matching the PreToolUse/PostToolUse schema, invokes the hook via subprocess.run,
and asserts on exit code and stdout.
"""

import json
import os
import subprocess
import tempfile
import uuid
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
    env.pop("CLAUDE_PYTEST_LOOP_BYPASS", None)
    env.pop("CLAUDE_PYTEST_LOOP_MAX", None)
    env.pop("CLAUDE_PYTEST_LOOP_TOTAL_MAX", None)
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


def write_total(tmpdir: str, uuid: str, count: int) -> None:
    """Write a total failure counter file."""
    total_file = Path(tmpdir) / f"claude-pytest-loop-{uuid}.total"
    total_file.write_text(str(count) + "\n")


def read_total(tmpdir: str, uuid: str) -> int | None:
    """Read the total failure counter; returns None if file doesn't exist."""
    total_file = Path(tmpdir) / f"claude-pytest-loop-{uuid}.total"
    if not total_file.exists():
        return None
    content = total_file.read_text().strip()
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


class TestTotalCounterIncrements:
    """Total failure counter increments on each failure, independent of edits."""

    def test_total_increments_on_first_failure(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            uuid = write_session_id(tmpdir)
            write_status(tmpdir, uuid, 1)

            inp = make_pretooluse_input("timeout 300 pytest tests/")
            run_hook(DETECTOR_HOOK, inp, tmpdir)

            assert read_total(tmpdir, uuid) == 1

    def test_total_increments_alongside_noedit_counter(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            uuid = write_session_id(tmpdir)
            write_status(tmpdir, uuid, 1)
            write_counter(tmpdir, uuid, 1)
            write_total(tmpdir, uuid, 3)

            inp = make_pretooluse_input("timeout 300 pytest tests/")
            run_hook(DETECTOR_HOOK, inp, tmpdir)

            assert read_counter(tmpdir, uuid) == 2
            assert read_total(tmpdir, uuid) == 4

    def test_total_keeps_counting_after_edit_resets_noedit(self):
        """Simulates: fail→edit(resets .count)→fail. Total should be 6, count should be 1."""
        with tempfile.TemporaryDirectory() as tmpdir:
            uuid = write_session_id(tmpdir)
            write_status(tmpdir, uuid, 1)
            write_counter(tmpdir, uuid, 0)  # reset by edit
            write_total(tmpdir, uuid, 5)  # accumulated over many failures

            inp = make_pretooluse_input("timeout 300 pytest tests/")
            run_hook(DETECTOR_HOOK, inp, tmpdir)

            assert read_counter(tmpdir, uuid) == 1
            assert read_total(tmpdir, uuid) == 6


class TestTotalCounterDenies:
    """Total counter >= 8 causes denial."""

    def test_denies_at_total_8(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            uuid = write_session_id(tmpdir)
            write_status(tmpdir, uuid, 1)
            write_counter(tmpdir, uuid, 0)  # below no-edit threshold
            write_total(tmpdir, uuid, 7)  # will become 8 → deny

            inp = make_pretooluse_input("timeout 300 pytest tests/")
            result = run_hook(DETECTOR_HOOK, inp, tmpdir)

            output = json.loads(result.stdout)
            assert output["hookSpecificOutput"]["permissionDecision"] == "deny"
            reason = output["hookSpecificOutput"]["permissionDecisionReason"]
            assert "8 times" in reason
            assert "/mine.debug" in reason

    def test_denies_above_total_8(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            uuid = write_session_id(tmpdir)
            write_status(tmpdir, uuid, 1)
            write_counter(tmpdir, uuid, 0)
            write_total(tmpdir, uuid, 12)

            inp = make_pretooluse_input("timeout 300 pytest tests/")
            result = run_hook(DETECTOR_HOOK, inp, tmpdir)

            output = json.loads(result.stdout)
            assert output["hookSpecificOutput"]["permissionDecision"] == "deny"

    def test_total_denial_does_not_inflate_counters(self):
        """Denied runs must not write counter files (counters stay at pre-deny values)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            uuid = write_session_id(tmpdir)
            write_status(tmpdir, uuid, 1)
            write_counter(tmpdir, uuid, 0)
            write_total(tmpdir, uuid, 7)

            inp = make_pretooluse_input("timeout 300 pytest tests/")
            run_hook(DETECTOR_HOOK, inp, tmpdir)

            assert read_counter(tmpdir, uuid) == 0
            assert read_total(tmpdir, uuid) == 7

    def test_noedit_denial_does_not_inflate_total(self):
        """No-edit denial must not write to the total counter either."""
        with tempfile.TemporaryDirectory() as tmpdir:
            uuid = write_session_id(tmpdir)
            write_status(tmpdir, uuid, 1)
            write_counter(tmpdir, uuid, 2)  # will become 3 → no-edit deny
            write_total(tmpdir, uuid, 2)

            inp = make_pretooluse_input("timeout 300 pytest tests/")
            run_hook(DETECTOR_HOOK, inp, tmpdir)

            assert read_counter(tmpdir, uuid) == 2
            assert read_total(tmpdir, uuid) == 2


class TestTotalCounterEnvVarOverride:
    """CLAUDE_PYTEST_LOOP_TOTAL_MAX overrides the default threshold."""

    def test_custom_total_max(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            uuid = write_session_id(tmpdir)
            write_status(tmpdir, uuid, 1)
            write_counter(tmpdir, uuid, 0)
            write_total(tmpdir, uuid, 4)  # will become 5 → deny at max=5

            inp = make_pretooluse_input("timeout 300 pytest tests/")
            result = run_hook(
                DETECTOR_HOOK,
                inp,
                tmpdir,
                extra_env={"CLAUDE_PYTEST_LOOP_TOTAL_MAX": "5"},
            )

            output = json.loads(result.stdout)
            assert output["hookSpecificOutput"]["permissionDecision"] == "deny"

    def test_custom_total_max_allows_below_threshold(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            uuid = write_session_id(tmpdir)
            write_status(tmpdir, uuid, 1)
            write_counter(tmpdir, uuid, 0)
            write_total(tmpdir, uuid, 3)  # will become 4, threshold is 5

            inp = make_pretooluse_input("timeout 300 pytest tests/")
            result = run_hook(
                DETECTOR_HOOK,
                inp,
                tmpdir,
                extra_env={"CLAUDE_PYTEST_LOOP_TOTAL_MAX": "5"},
            )

            assert result.stdout.strip() == ""
            assert read_total(tmpdir, uuid) == 4


class TestTotalCounterResetsOnSuccess:
    """Green run resets both counters."""

    def test_green_run_resets_total(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            uuid = write_session_id(tmpdir)
            write_status(tmpdir, uuid, 0)  # success
            write_total(tmpdir, uuid, 5)

            inp = make_pretooluse_input("timeout 300 pytest tests/")
            run_hook(DETECTOR_HOOK, inp, tmpdir)

            assert read_total(tmpdir, uuid) == 0

    def test_bypass_resets_total(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            uuid = write_session_id(tmpdir)
            write_status(tmpdir, uuid, 1)
            write_total(tmpdir, uuid, 10)

            inp = make_pretooluse_input("timeout 300 pytest tests/")
            run_hook(
                DETECTOR_HOOK,
                inp,
                tmpdir,
                extra_env={"CLAUDE_PYTEST_LOOP_BYPASS": "1"},
            )

            assert read_total(tmpdir, uuid) == 0


class TestEditHookPreservesTotal:
    """The PostToolUse edit hook resets .count but not .total."""

    def test_edit_resets_count_not_total(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            uuid = write_session_id(tmpdir)
            write_counter(tmpdir, uuid, 2)
            write_total(tmpdir, uuid, 5)

            inp = make_posttooluse_input("Edit")
            run_hook(RESET_HOOK, inp, tmpdir)

            assert read_counter(tmpdir, uuid) == 0
            assert read_total(tmpdir, uuid) == 5


class TestBinScriptClearsBothCounters:
    """bin/pytest-loop-reset clears both .count and .total files."""

    def test_bin_clears_both(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            uuid = write_session_id(tmpdir)
            write_counter(tmpdir, uuid, 3)
            write_total(tmpdir, uuid, 7)

            result = subprocess.run(
                [str(BIN_RESET)],
                capture_output=True,
                text=True,
                env={**os.environ, "CLAUDE_CODE_TMPDIR": tmpdir},
            )

            assert result.returncode == 0
            assert read_counter(tmpdir, uuid) == 0
            assert read_total(tmpdir, uuid) == 0

    def test_bin_clears_total_only(self):
        """When only total file exists (count already cleared), still works."""
        with tempfile.TemporaryDirectory() as tmpdir:
            uuid = write_session_id(tmpdir)
            write_total(tmpdir, uuid, 5)

            result = subprocess.run(
                [str(BIN_RESET)],
                capture_output=True,
                text=True,
                env={**os.environ, "CLAUDE_CODE_TMPDIR": tmpdir},
            )

            assert result.returncode == 0
            assert read_total(tmpdir, uuid) == 0
            assert "cleared" in result.stdout


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


# ---------------------------------------------------------------------------
# context-tier.sh tests
# ---------------------------------------------------------------------------

CONTEXT_TIER_HOOK = REPO_ROOT / "scripts" / "hooks" / "context-tier.sh"


def _context_tier_session_id(test_name: str) -> str:
    """Generate a unique session ID for a context-tier test to avoid cross-talk."""
    return f"ct-test-{test_name}-{uuid.uuid4().hex[:8]}"


def _write_sidecar(session_id: str, percent: str) -> Path:
    """Write the sidecar file that claude-context-writer would produce."""
    p = Path(f"/tmp/claude-context-{session_id}.txt")
    p.write_text(percent)
    return p


def _read_tier(session_id: str) -> str | None:
    """Read the tier state file; returns None if absent."""
    p = Path(f"/tmp/claude-context-tier-{session_id}.txt")
    if not p.exists():
        return None
    return p.read_text().strip()


def _write_tier(session_id: str, tier: str) -> Path:
    """Pre-seed the tier state file to simulate a prior call."""
    p = Path(f"/tmp/claude-context-tier-{session_id}.txt")
    p.write_text(tier)
    return p


def _cleanup_context_tier(session_id: str) -> None:
    """Remove sidecar, tier, and counter files for a session."""
    for pattern in (
        f"/tmp/claude-context-{session_id}.txt",
        f"/tmp/claude-context-tier-{session_id}.txt",
        f"/tmp/claude-context-calls-{session_id}.txt",
    ):
        p = Path(pattern)
        if p.exists():
            p.unlink()


def _write_counter(session_id: str, count: int) -> Path:
    """Pre-seed the heartbeat counter file."""
    p = Path(f"/tmp/claude-context-calls-{session_id}.txt")
    p.write_text(str(count))
    return p


def _read_counter(session_id: str) -> int | None:
    """Read the heartbeat counter; returns None if absent."""
    p = Path(f"/tmp/claude-context-calls-{session_id}.txt")
    if not p.exists():
        return None
    text = p.read_text().strip()
    return int(text) if text else None


def _make_context_tier_input(session_id: str) -> str:
    """Build JSON stdin for the context-tier hook."""
    return json.dumps({"session_id": session_id})


def _run_context_tier(
    session_id: str,
    extra_env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess:
    """Run the context-tier hook with the given session_id."""
    env = os.environ.copy()
    if extra_env:
        env.update(extra_env)
    return subprocess.run(
        [str(CONTEXT_TIER_HOOK)],
        input=_make_context_tier_input(session_id),
        capture_output=True,
        text=True,
        env=env,
    )


class TestContextTierFirstCallEmits:
    """First call (no prior tier state) emits a tier message."""

    def test_context_tier_first_call_emits_low(self):
        sid = _context_tier_session_id("first_low")
        try:
            _write_sidecar(sid, "10")
            result = _run_context_tier(sid)

            assert result.returncode == 0
            assert "low usage (10%)" in result.stdout
            assert _read_tier(sid) == "low"
        finally:
            _cleanup_context_tier(sid)

    def test_context_tier_first_call_emits_critical(self):
        sid = _context_tier_session_id("first_crit")
        try:
            _write_sidecar(sid, "90")
            result = _run_context_tier(sid)

            assert result.returncode == 0
            assert "critical usage (90%)" in result.stdout
            assert _read_tier(sid) == "critical"
        finally:
            _cleanup_context_tier(sid)


class TestContextTierSameTierSuppressed:
    """Repeat call at the same tier is suppressed (until heartbeat threshold)."""

    def test_context_tier_same_tier_silent(self):
        sid = _context_tier_session_id("same_tier")
        try:
            _write_sidecar(sid, "15")
            _write_tier(sid, "low")  # already at low

            result = _run_context_tier(sid)

            assert result.returncode == 0
            assert result.stdout.strip() == ""
        finally:
            _cleanup_context_tier(sid)

    def test_context_tier_same_tier_moderate_silent(self):
        sid = _context_tier_session_id("same_mod")
        try:
            _write_sidecar(sid, "50")
            _write_tier(sid, "moderate")

            result = _run_context_tier(sid)

            assert result.returncode == 0
            assert result.stdout.strip() == ""
        finally:
            _cleanup_context_tier(sid)


class TestContextTierTransitionEmits:
    """Tier change emits a new message and updates the state file."""

    def test_context_tier_low_to_low_mid(self):
        sid = _context_tier_session_id("low_lowmid")
        try:
            _write_sidecar(sid, "30")
            _write_tier(sid, "low")

            result = _run_context_tier(sid)

            assert result.returncode == 0
            assert "Plenty of room" in result.stdout
            assert _read_tier(sid) == "low-mid"
        finally:
            _cleanup_context_tier(sid)

    def test_context_tier_low_mid_to_moderate(self):
        sid = _context_tier_session_id("lowmid_mod")
        try:
            _write_sidecar(sid, "45")
            _write_tier(sid, "low-mid")

            result = _run_context_tier(sid)

            assert result.returncode == 0
            assert "moderate usage (45%)" in result.stdout
            assert _read_tier(sid) == "moderate"
        finally:
            _cleanup_context_tier(sid)

    def test_context_tier_moderate_to_high(self):
        sid = _context_tier_session_id("mod_high")
        try:
            _write_sidecar(sid, "70")
            _write_tier(sid, "moderate")

            result = _run_context_tier(sid)

            assert result.returncode == 0
            assert "high usage (70%)" in result.stdout
            assert _read_tier(sid) == "high"
        finally:
            _cleanup_context_tier(sid)

    def test_context_tier_high_to_critical(self):
        sid = _context_tier_session_id("high_crit")
        try:
            _write_sidecar(sid, "85")
            _write_tier(sid, "high")

            result = _run_context_tier(sid)

            assert result.returncode == 0
            assert "critical usage (85%)" in result.stdout
            assert _read_tier(sid) == "critical"
        finally:
            _cleanup_context_tier(sid)

    def test_context_tier_full_escalation_sequence(self):
        """Walk through all five tiers in sequence."""
        sid = _context_tier_session_id("full_seq")
        try:
            # low (first call)
            _write_sidecar(sid, "5")
            result = _run_context_tier(sid)
            assert "low usage (5%)" in result.stdout
            assert _read_tier(sid) == "low"

            # low → low-mid
            _write_sidecar(sid, "30")
            result = _run_context_tier(sid)
            assert "Plenty of room" in result.stdout
            assert _read_tier(sid) == "low-mid"

            # low-mid → moderate
            _write_sidecar(sid, "50")
            result = _run_context_tier(sid)
            assert "moderate usage (50%)" in result.stdout
            assert _read_tier(sid) == "moderate"

            # moderate → high
            _write_sidecar(sid, "65")
            result = _run_context_tier(sid)
            assert "high usage (65%)" in result.stdout
            assert _read_tier(sid) == "high"

            # high → critical
            _write_sidecar(sid, "80")
            result = _run_context_tier(sid)
            assert "critical usage (80%)" in result.stdout
            assert _read_tier(sid) == "critical"
        finally:
            _cleanup_context_tier(sid)


class TestContextTierMissingSidecar:
    """Missing sidecar file is a no-op."""

    def test_context_tier_missing_sidecar_exits_zero(self):
        sid = _context_tier_session_id("no_sidecar")
        try:
            # Do NOT create a sidecar file
            result = _run_context_tier(sid)

            assert result.returncode == 0
            assert result.stdout.strip() == ""
        finally:
            _cleanup_context_tier(sid)


class TestContextTierInvalidSidecar:
    """Invalid or non-numeric sidecar content is a no-op."""

    def test_context_tier_empty_sidecar(self):
        sid = _context_tier_session_id("empty_sc")
        try:
            _write_sidecar(sid, "")
            result = _run_context_tier(sid)

            assert result.returncode == 0
            assert result.stdout.strip() == ""
        finally:
            _cleanup_context_tier(sid)

    def test_context_tier_non_numeric_sidecar(self):
        sid = _context_tier_session_id("nonnumeric")
        try:
            _write_sidecar(sid, "abc")
            result = _run_context_tier(sid)

            assert result.returncode == 0
            assert result.stdout.strip() == ""
        finally:
            _cleanup_context_tier(sid)

    def test_context_tier_negative_number_sidecar(self):
        sid = _context_tier_session_id("negative")
        try:
            _write_sidecar(sid, "-5")
            result = _run_context_tier(sid)

            assert result.returncode == 0
            assert result.stdout.strip() == ""
        finally:
            _cleanup_context_tier(sid)

    def test_context_tier_float_sidecar(self):
        sid = _context_tier_session_id("float")
        try:
            _write_sidecar(sid, "42.5")
            result = _run_context_tier(sid)

            assert result.returncode == 0
            assert result.stdout.strip() == ""
        finally:
            _cleanup_context_tier(sid)


class TestContextTierHeartbeat:
    """Heartbeat re-injects the message every N calls even without a tier change."""

    def test_heartbeat_fires_at_threshold(self):
        sid = _context_tier_session_id("hb_fire")
        try:
            _write_sidecar(sid, "15")
            # First call emits (tier change from empty → low), resets counter to 0
            result = _run_context_tier(sid, extra_env={"CLAUDE_CONTEXT_HEARTBEAT": "5"})
            assert "low usage (15%)" in result.stdout

            # Calls 2-5: suppressed (counter 1-4)
            for _ in range(4):
                result = _run_context_tier(
                    sid, extra_env={"CLAUDE_CONTEXT_HEARTBEAT": "5"}
                )
                assert result.stdout.strip() == ""

            # Call 6: heartbeat fires (counter hits 5)
            result = _run_context_tier(sid, extra_env={"CLAUDE_CONTEXT_HEARTBEAT": "5"})
            assert "low usage (15%)" in result.stdout
            assert _read_counter(sid) == 0
        finally:
            _cleanup_context_tier(sid)

    def test_tier_change_resets_counter(self):
        sid = _context_tier_session_id("hb_reset")
        try:
            _write_sidecar(sid, "15")
            _write_tier(sid, "low")
            _write_counter(sid, 20)

            # Tier change (low → moderate) should emit and reset counter
            _write_sidecar(sid, "45")
            result = _run_context_tier(sid)
            assert "moderate usage (45%)" in result.stdout
            assert _read_counter(sid) == 0
        finally:
            _cleanup_context_tier(sid)

    def test_non_numeric_env_falls_back_to_default(self):
        sid = _context_tier_session_id("hb_badenv")
        try:
            _write_sidecar(sid, "15")
            _write_tier(sid, "low")
            _write_counter(sid, 23)

            # With bad env, interval falls back to 25; counter 23+1=24 < 25
            result = _run_context_tier(
                sid, extra_env={"CLAUDE_CONTEXT_HEARTBEAT": "off"}
            )
            assert result.stdout.strip() == ""
            assert _read_counter(sid) == 24
        finally:
            _cleanup_context_tier(sid)

    def test_zero_env_falls_back_to_default(self):
        sid = _context_tier_session_id("hb_zero")
        try:
            _write_sidecar(sid, "15")
            _write_tier(sid, "low")
            _write_counter(sid, 23)

            result = _run_context_tier(sid, extra_env={"CLAUDE_CONTEXT_HEARTBEAT": "0"})
            assert result.stdout.strip() == ""
            assert _read_counter(sid) == 24
        finally:
            _cleanup_context_tier(sid)


class TestContextTierMissingSessionId:
    """Missing session_id in input is a no-op."""

    def test_context_tier_no_session_id_field(self):
        result = subprocess.run(
            [str(CONTEXT_TIER_HOOK)],
            input=json.dumps({"tool_name": "Bash"}),
            capture_output=True,
            text=True,
            env=os.environ.copy(),
        )

        assert result.returncode == 0
        assert result.stdout.strip() == ""

    def test_context_tier_empty_session_id(self):
        result = subprocess.run(
            [str(CONTEXT_TIER_HOOK)],
            input=json.dumps({"session_id": ""}),
            capture_output=True,
            text=True,
            env=os.environ.copy(),
        )

        assert result.returncode == 0
        assert result.stdout.strip() == ""


class TestContextTierPathTraversal:
    """Session IDs with path traversal characters are rejected."""

    def test_context_tier_slash_in_session_id(self):
        result = subprocess.run(
            [str(CONTEXT_TIER_HOOK)],
            input=json.dumps({"session_id": "../etc/passwd"}),
            capture_output=True,
            text=True,
            env=os.environ.copy(),
        )

        assert result.returncode == 0
        assert result.stdout.strip() == ""

    def test_context_tier_dot_in_session_id(self):
        result = subprocess.run(
            [str(CONTEXT_TIER_HOOK)],
            input=json.dumps({"session_id": "foo.bar"}),
            capture_output=True,
            text=True,
            env=os.environ.copy(),
        )

        assert result.returncode == 0
        assert result.stdout.strip() == ""

    def test_context_tier_dotdot_in_session_id(self):
        result = subprocess.run(
            [str(CONTEXT_TIER_HOOK)],
            input=json.dumps({"session_id": ".."}),
            capture_output=True,
            text=True,
            env=os.environ.copy(),
        )

        assert result.returncode == 0
        assert result.stdout.strip() == ""


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


# ---------------------------------------------------------------------------
# Subagent compaction check hook tests
# ---------------------------------------------------------------------------

COMPACTION_HOOK = REPO_ROOT / "scripts" / "hooks" / "subagent-compaction-check.sh"


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


class TestCompactionHookDetectsCompaction:
    """Hook detects compact_boundary events and emits a warning."""

    def test_compaction_detected(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            sid = f"compaction-test-{uuid.uuid4().hex[:8]}"
            transcript = Path(tmpdir) / "session.jsonl"
            transcript.write_text("")
            subagent_dir = Path(tmpdir) / "session" / "subagents"
            subagent_dir.mkdir(parents=True)

            agent_jsonl = subagent_dir / "agent-abc123.jsonl"
            _write_compact_boundary(agent_jsonl, 170000, 8000)
            _write_agent_meta(subagent_dir / "agent-abc123.meta.json", "T01 executor")

            stdin = _make_compaction_input(sid, str(transcript))
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
            sid = f"no-compact-{uuid.uuid4().hex[:8]}"
            transcript = Path(tmpdir) / "session.jsonl"
            transcript.write_text("")
            subagent_dir = Path(tmpdir) / "session" / "subagents"
            subagent_dir.mkdir(parents=True)

            agent_jsonl = subagent_dir / "agent-abc123.jsonl"
            agent_jsonl.write_text('{"type":"assistant","content":"hello"}\n')

            stdin = _make_compaction_input(sid, str(transcript))
            result = run_hook(COMPACTION_HOOK, stdin, tmpdir)

            assert result.returncode == 0
            assert result.stdout.strip() == ""


class TestCompactionHookDedup:
    """Hook deduplicates — second call for same session is silent."""

    def test_dedup(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            sid = f"dedup-{uuid.uuid4().hex[:8]}"
            transcript = Path(tmpdir) / "session.jsonl"
            transcript.write_text("")
            subagent_dir = Path(tmpdir) / "session" / "subagents"
            subagent_dir.mkdir(parents=True)

            agent_jsonl = subagent_dir / "agent-abc123.jsonl"
            _write_compact_boundary(agent_jsonl, 170000, 8000)

            stdin = _make_compaction_input(sid, str(transcript))

            result1 = run_hook(COMPACTION_HOOK, stdin, tmpdir)
            assert "Subagent compaction detected" in result1.stdout

            result2 = run_hook(COMPACTION_HOOK, stdin, tmpdir)
            assert result2.stdout.strip() == ""


class TestCompactionHookMissingPostTokens:
    """Hook handles missing postTokens gracefully."""

    def test_missing_post_tokens(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            sid = f"no-post-{uuid.uuid4().hex[:8]}"
            transcript = Path(tmpdir) / "session.jsonl"
            transcript.write_text("")
            subagent_dir = Path(tmpdir) / "session" / "subagents"
            subagent_dir.mkdir(parents=True)

            agent_jsonl = subagent_dir / "agent-abc123.jsonl"
            entry = {
                "type": "system",
                "subtype": "compact_boundary",
                "compactMetadata": {"trigger": "auto", "preTokens": 175000},
            }
            agent_jsonl.write_text(json.dumps(entry) + "\n")

            stdin = _make_compaction_input(sid, str(transcript))
            result = run_hook(COMPACTION_HOOK, stdin, tmpdir)

            assert result.returncode == 0
            assert "175,000" in result.stdout
            assert "not recorded" in result.stdout
            assert "0%" not in result.stdout


class TestCompactionHookMultipleEvents:
    """Hook reports all compaction events for an agent that compacted twice."""

    def test_multiple_compactions(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            sid = f"multi-{uuid.uuid4().hex[:8]}"
            transcript = Path(tmpdir) / "session.jsonl"
            transcript.write_text("")
            subagent_dir = Path(tmpdir) / "session" / "subagents"
            subagent_dir.mkdir(parents=True)

            agent_jsonl = subagent_dir / "agent-abc123.jsonl"
            _write_compact_boundary(agent_jsonl, 170000, 8000)
            _write_compact_boundary(agent_jsonl, 165000, 9000)

            stdin = _make_compaction_input(sid, str(transcript))
            result = run_hook(COMPACTION_HOOK, stdin, tmpdir)

            assert result.returncode == 0
            assert "170,000" in result.stdout
            assert "165,000" in result.stdout


class TestCompactionHookNoSubagentDir:
    """Hook exits silently when no subagent directory exists."""

    def test_no_subagent_dir(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            sid = f"no-dir-{uuid.uuid4().hex[:8]}"
            transcript = Path(tmpdir) / "session.jsonl"
            transcript.write_text("")

            stdin = _make_compaction_input(sid, str(transcript))
            result = run_hook(COMPACTION_HOOK, stdin, tmpdir)

            assert result.returncode == 0
            assert result.stdout.strip() == ""
